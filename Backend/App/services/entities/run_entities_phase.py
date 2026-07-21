import sys
import time

from Backend.App.services.entities.process_lore import classify_lore, persist_lore, persist_lore_in_chapter

from ..utility.getdb import get_db
from ..utility.response import get_response
from ..utility.status import is_step_completed, start_step, complete_step, fail_step
from ...models.rpg_sessions import Entities, LoreEntity, SourceDocument, Character, CharacterSegment, CharacterArcState, ChronicleChapter
from ..documents.documents import generate_page_windows
from .process_entities import extract_entities_from_window, span_construction, seperate_candidates, store_candidate_entities, rank_entities
from .entities_reduce import merge_entity_clusters
from .process_characters import (
    
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
from ..utility.utility_functions import estimate_tokens


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
    
    spanned_lore = _step_lore_classify(source_doc_id, session_id, lore)
    _step_lore_persist(source_doc_id, session_id, spanned_lore)
    _step_lore_segment(source_doc_id, session_id, spanned_lore)


def _get_source_doc_total_pages(source_doc_id: str):
    with get_db() as db:
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if not source_doc or not source_doc.total_pages:
            raise ValueError(f"Source document missing or has no total_pages: {source_doc_id}")
        return source_doc.total_pages


def _re_extract_entities(source_doc_id: str, session_id: str) -> tuple:
    print(f"[run_entities] Re-extracting entities for {source_doc_id}", file=sys.stderr)
    total_pages = _get_source_doc_total_pages(source_doc_id)
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
            entities = db.query(Entities).filter(Entities.session_id == session_id).all()
            return [e.to_dict() for e in entities]

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        total_pages = _get_source_doc_total_pages(source_doc_id)
        windows = generate_page_windows(total_pages=total_pages, window_size=5, overlap=1)
        candidate_entities = []
        consecutive_failures = 0
        

        for start_page, end_page in windows:
            with get_db() as db:
                exists = db.query(Entities).filter(
                    Entities.session_id == session_id,
                    Entities.window_start_page == start_page,
                    Entities.window_end_page == end_page
                ).all()
                
                if exists:
                    print(f"[run_entities] Entities already exist for pages {start_page}-{end_page}, skipping extraction", file=sys.stderr)
                    for e in exists:
                        candidate_entities.append({
                            "name": e.name,
                            "type": e.type,
                            "pages": e.pages
                        })
                    continue
                
                try:
                    entities = extract_entities_from_window(session_id, start_page, end_page)
                    
                    store_candidate_entities(session_id = session_id, candidate_entities=entities, window_start_page=start_page, window_end_page=end_page, db = db)
                    
                    candidate_entities.append(entities)
                    consecutive_failures = 0
                except Exception as e:
                            consecutive_failures += 1
                            print(f"[run_entities] Error extracting pages {start_page}-{end_page}: {e}", file=sys.stderr)

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
        candidate_entities = db.query(Entities).filter(Entities.session_id == session_id).all()

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
        merged_entities = _step_entities_merge(source_doc_id, session_id, None)

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
        with get_db() as db:
            entities = db.query(Entities).filter(Entities.session_id == session_id).all()
        characters = _step_entities_separate(source_doc_id, session_id, [e.to_dict() for e in entities])[0]    
    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        book_total_pages = _get_source_doc_total_pages(source_doc_id)

        ranked_entities = rank_entities(characters)
        spanned_characters = []
        for character in ranked_entities:
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
        spanned_characters = _step_characters_classify(source_doc_id, session_id, None)

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
        spanned_characters = _step_characters_classify(source_doc_id, session_id, None)

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
    step = "characters_arc"

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


def _step_lore_classify(source_doc_id: str, session_id: str, lore: list | None):
    phase = "lore_processing"
    step = "lore_classify"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return None

        if lore is None:
            entities = db.query(Entities).filter(Entities.session_id == session_id).all()
            lore = _step_entities_separate(source_doc_id, session_id, [e.to_dict() for e in entities])[1]
        
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        ranked_lore = rank_entities(lore)
        book_total_pages = _get_source_doc_total_pages(source_doc_id)
        classified_lore = []
        
        for entry in ranked_lore:
            classified_entry = classify_lore(entry, book_total_pages)  # Replace 100 with actual total pages if available
            classified_lore.append(classified_entry)
        
        
        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return classified_lore

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_entities] Error classifying lore for {source_doc_id}: {e}", file=sys.stderr)
        raise

def _step_lore_persist(source_doc_id: str, session_id: str, classified_lore: list | None):
    phase = "lore_processing"
    step = "lore_persist"

    with get_db() as db:
        
        if is_step_completed(db, session_id, phase, step):
            return

        if classified_lore is None:
            classified_lore = _step_lore_classify(source_doc_id, session_id, None)
        
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

        try:
            persisted_chapter = persist_lore_in_chapter(db, session_id, classified_lore)
            persisted_lore = persist_lore(db, session_id, classified_lore)
            
            if persisted_chapter and persisted_lore:
                complete_step(db, session_id, phase, step)

        except Exception as e:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
            print(f"[run_entities] Error persisting lore for {source_doc_id}: {e}", file=sys.stderr)
            raise

def _step_lore_segment(source_doc_id: str, session_id: str, classified_lore: list | None):
    phase = "lore_processing"
    step = "lore_segment"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return

        if classified_lore is None:
            classified_lore = _step_lore_classify(source_doc_id, session_id, None)
        
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

        try:
            # Implement lore segmentation logic here
            # For now, we just mark the step as complete
            complete_step(db, session_id, phase, step)

        except Exception as e:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
            print(f"[run_entities] Error segmenting lore for {source_doc_id}: {e}", file=sys.stderr)
            raise