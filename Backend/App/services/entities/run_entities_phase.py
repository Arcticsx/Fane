import sys
import time

from ..utility.getdb import get_db
from ..utility.response import get_response
from ..utility.status import is_step_completed, start_step, complete_step, fail_step
from ...models.rpg_sessions import SourceDocument, Character, CharacterSegment, CharacterArcState, ChronicleChapter
from ..documents.documents import generate_page_windows
from .process_entities import extract_entities_from_window, span_construction, seperate_candidates
from .entities_reduce import merge_entity_clusters
from .process_characters import (
    rank_characters,
    span_statistic_of_character,
    persist_characters_in_chapters,
    persist_characters,
    persist_character_spans,
    segment_characters,
    persist_character_segments,
    process_arc_records,
    prepare_pool_for_synthesis,
    PERSONALITY_PROMPT,
    BACKSTORY_PROMPT,
    FIGHTING_STYLE_PROMPT,
)
from Backend.App.services.utility.utility_functions import estimate_tokens


def run_entities_phase(source_doc_id: str, session_id: str):
    candidate_entities = None
    merged_entities = None
    characters = None
    lore = None
    spanned_characters = None

    candidate_entities = _step_entities_extract(source_doc_id, session_id)

    merged_entities = _step_entities_merge(source_doc_id, session_id, candidate_entities)

    characters, lore = _step_entities_separate(source_doc_id, session_id, merged_entities)

    spanned_characters = _step_characters_classify(source_doc_id, session_id, characters)

    _step_characters_persist(source_doc_id, session_id, spanned_characters)

    _step_characters_segment(source_doc_id, session_id, spanned_characters)

    _step_characters_arc_llm(source_doc_id, session_id)

    _step_characters_arc_persist(source_doc_id, session_id)


def _get_source_doc(source_doc_id: str):
    with get_db() as db:
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if not source_doc or not source_doc.total_pages:
            raise ValueError(f"Source document missing or has no total_pages: {source_doc_id}")
        return source_doc.total_pages


def _re_extract_entities(source_doc_id: str, session_id: str) -> tuple:
    print(f"[run_entities] Re-extracting entities for {source_doc_id}", file=sys.stderr)
    total_pages = _get_source_doc(source_doc_id)
    windows = generate_page_windows(total_pages=total_pages, window_size=5, overlap=1)
    candidate_entities = []
    for start_page, end_page in windows:
        try:
            entities = extract_entities_from_window(session_id, start_page, end_page)
            candidate_entities.append(entities)
        except Exception as e:
            print(f"[run_entities] Re-extraction error pages {start_page}-{end_page}: {e}", file=sys.stderr)
            raise
        time.sleep(3)
    merged = merge_entity_clusters(candidate_entities)
    spanned = []
    for entity in merged:
        spans, tp = span_construction(entity["pages"], gap_tolerance=2)
        spanned.append({"name": entity["name"], "type": entity["type"], "spans": spans, "total_pages": tp})
    characters, lore = seperate_candidates(spanned)
    return candidate_entities, merged, characters, lore


def _mark_source_failed(db, source_doc_id: str, error):
    source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
    if source_doc:
        source_doc.error_message = str(error)[:1000]
        source_doc.status = "failed"
        db.commit()


# ── Entity extraction sub-steps ──────────────────────────────────────────────

def _step_entities_extract(source_doc_id: str, session_id: str):
    phase = "entity_extraction"
    step = "entities_extract"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return None

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        total_pages = _get_source_doc(source_doc_id)
        windows = generate_page_windows(total_pages=total_pages, window_size=5, overlap=1)
        candidate_entities = []
        consecutive_failures = 0

        for start_page, end_page in windows:
            try:
                entities = extract_entities_from_window(session_id, start_page, end_page)
                candidate_entities.append(entities)
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                print(f"[run_entities] Error extracting pages {start_page}-{end_page}: {e}", file=sys.stderr)
                if "connection refused" in str(e).lower() or "server disconnected" in str(e).lower():
                    print(f"[run_entities] Ollama unresponsive, backing off 15s", file=sys.stderr)
                    time.sleep(15)
                    try:
                        entities = extract_entities_from_window(session_id, start_page, end_page)
                        candidate_entities.append(entities)
                        consecutive_failures = 0
                    except Exception as retry_e:
                        print(f"[run_entities] Retry also failed: {retry_e}", file=sys.stderr)
                if consecutive_failures >= 5:
                    raise RuntimeError(
                        f"Too many consecutive extraction failures ({consecutive_failures}); aborting"
                    )
            finally:
                time.sleep(3)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return candidate_entities

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error extracting entities for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_entities_merge(source_doc_id: str, session_id: str, candidate_entities: list | None):
    phase = "entity_extraction"
    step = "entities_merge"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return None

    if candidate_entities is None:
        candidate_entities, _, _, _ = _re_extract_entities(source_doc_id, session_id)

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        merged_entities = merge_entity_clusters(candidate_entities)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return merged_entities

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error merging entities for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_entities_separate(source_doc_id: str, session_id: str, merged_entities: list | None):
    phase = "entity_extraction"
    step = "entities_separate"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return None, None

    if merged_entities is None:
        _, merged_entities, _, _ = _re_extract_entities(source_doc_id, session_id)

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        spanned_entities = []
        for entity in merged_entities:
            spans, total_pages = span_construction(entity["pages"], gap_tolerance=2)
            spanned_entities.append({
                "name": entity["name"],
                "type": entity["type"],
                "spans": spans,
                "total_pages": total_pages,
            })

        characters, lore = seperate_candidates(spanned_entities)
        print(f"[run_entities] Separated {len(characters)} characters, {len(lore)} lore entries")

        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return characters, lore

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error separating entities for {source_doc_id}: {e}", file=sys.stderr)
        raise


# ── Character processing sub-steps ───────────────────────────────────────────

def _step_characters_classify(source_doc_id: str, session_id: str, characters: list | None):
    phase = "character_processing"
    step = "characters_classify"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return None

    if characters is None:
        _, _, characters, _ = _re_extract_entities(source_doc_id, session_id)

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        with get_db() as db:
            source_document = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            book_total_pages = source_document.total_pages if source_document else 0

        ranked_characters = rank_characters(characters)
        spanned_characters = []
        for character in ranked_characters:
            span_stats = span_statistic_of_character(character, book_total_pages)
            spanned_characters.append(span_stats)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return spanned_characters

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error classifying characters for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_characters_persist(source_doc_id: str, session_id: str, spanned_characters: list | None):
    phase = "character_processing"
    step = "characters_persist"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return

    if spanned_characters is None:
        _, _, characters, _ = _re_extract_entities(source_doc_id, session_id)
        with get_db() as db:
            source_document = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            book_total_pages = source_document.total_pages if source_document else 0
        ranked = rank_characters(characters)
        spanned_characters = []
        for character in ranked:
            span_stats = span_statistic_of_character(character, book_total_pages)
            spanned_characters.append(span_stats)

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        persist_characters_in_chapters(spanned_characters, session_id)
        persist_characters(session_id, spanned_characters, source_doc_id)

        for character in spanned_characters:
            persist_character_spans(session_id, character)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error persisting characters for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_characters_segment(source_doc_id: str, session_id: str, spanned_characters: list | None):
    phase = "character_processing"
    step = "characters_segment"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return

    if spanned_characters is None:
        _, _, characters, _ = _re_extract_entities(source_doc_id, session_id)
        with get_db() as db:
            source_document = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            book_total_pages = source_document.total_pages if source_document else 0
        ranked = rank_characters(characters)
        spanned_characters = []
        for character in ranked:
            span_stats = span_statistic_of_character(character, book_total_pages)
            spanned_characters.append(span_stats)

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        with get_db() as db:
            total_chapters = len(
                db.query(ChronicleChapter).filter(ChronicleChapter.session_id == session_id).all()
            )
        segmented_characters = segment_characters(spanned_characters, book_total_chapters=total_chapters)

        for character in segmented_characters:
            persist_character_segments(session_id, character)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error segmenting characters for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_characters_arc_llm(source_doc_id: str, session_id: str):
    phase = "character_processing"
    step = "characters_arc_llm"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        _run_arc_llm_for_session(session_id)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error running arc LLM for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_characters_arc_persist(source_doc_id: str, session_id: str):
    phase = "character_processing"
    step = "characters_arc_persist"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        with get_db() as db:
            characters = db.query(Character).filter(Character.session_id == session_id).all()
            total_expected = 0
            total_existing = 0
            for character in characters:
                segments = db.query(CharacterSegment).filter(
                    CharacterSegment.character_id == character.id
                ).all()
                for segment in segments:
                    total_expected += 1
                    existing = db.query(CharacterArcState).filter(
                        CharacterArcState.character_id == character.id,
                        CharacterArcState.segment_id == segment.id,
                    ).first()
                    if existing:
                        total_existing += 1

            missing = total_expected - total_existing
            if missing > 0:
                print(f"[run_entities] {missing} missing arc states — re-running LLM for gaps", file=sys.stderr)
                _run_arc_llm_for_session(session_id)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error persisting arc records for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _run_arc_llm_for_session(session_id: str):
    with get_db() as db:
        characters = db.query(Character).filter(Character.session_id == session_id).all()

        for character in characters:
            segments = db.query(CharacterSegment).filter(
                CharacterSegment.character_id == character.id
            ).all()

            for segment in segments:
                existing = db.query(CharacterArcState).filter(
                    CharacterArcState.character_id == character.id,
                    CharacterArcState.segment_id == segment.id,
                ).first()
                if existing:
                    continue

                arc_state = process_arc_records(session_id, segment.id)
                if not arc_state or isinstance(arc_state, bool):
                    continue

                character_name = character.name

                personality_chunks = prepare_pool_for_synthesis(
                    arc_state["personality_pool"],
                    token_budget=4000 - estimate_tokens(PERSONALITY_PROMPT),
                )
                backstory_chunks = prepare_pool_for_synthesis(
                    arc_state["backstory_pool"],
                    token_budget=4000 - estimate_tokens(BACKSTORY_PROMPT),
                )
                fighting_style_chunks = prepare_pool_for_synthesis(
                    arc_state["fighting_style_pool"],
                    token_budget=4000 - estimate_tokens(FIGHTING_STYLE_PROMPT),
                )

                print(f"[run_entities] Arc LLM: {character_name} segment {segment.segment_number}", file=sys.stderr)
                personality = get_response(
                    PERSONALITY_PROMPT.format(character_name=character_name, data=personality_chunks),
                    mode="characters", type="personality",
                )
                backstory = get_response(
                    BACKSTORY_PROMPT.format(character_name=character_name, data=backstory_chunks),
                    mode="characters", type="backstory",
                )
                fighting_style = get_response(
                    FIGHTING_STYLE_PROMPT.format(character_name=character_name, data=fighting_style_chunks),
                    mode="characters", type="fighting_style",
                )

                with get_db() as db:
                    arc_record = CharacterArcState(
                        character_id=character.id,
                        segment_id=segment.id,
                        character_name=character_name,
                        segment_number=segment.segment_number,
                        personality_md=personality,
                        backstory_delta_md=backstory,
                        fighting_style_md=fighting_style,
                    )
                    db.add(arc_record)
                    db.commit()
                    print(f"[run_entities] Saved arc state for {character_name} segment {segment.segment_number}", file=sys.stderr)
