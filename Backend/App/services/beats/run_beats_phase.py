import sys
import json
import time
from ..utility.getdb import get_db
from ..utility.status import is_step_completed, start_step, complete_step, fail_step
from ...models.rpg_sessions import SourceDocument, StoryBeat
from ..documents.documents import generate_page_windows
from .extraction import extract_beats_from_window, save_candidate_beats, replace_candidates_with_final_beats
from .beats_reduce import split_and_reduce
from .extraction import cluster_candidates, reduce_cluster, merge_clusters, global_polish
from .graph import build_beat_graph, persist_beat_graph


def run_beats_phase(source_doc_id: str, session_id: str):
    phase = "story_beats"
    candidate_beats = None
    final_beats = None

    candidate_beats = _step_beats_extract(source_doc_id, session_id)

    final_beats = _step_beats_reduce(source_doc_id, session_id, candidate_beats, final_beats)

    _step_beats_save_reduced(source_doc_id, session_id, final_beats)

    _step_beats_graph(source_doc_id, session_id)


def _step_beats_extract(source_doc_id: str, session_id: str):
    phase = "story_beats"
    step = "beats_extract"

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
            source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
            if not source_doc or not source_doc.total_pages:
                raise ValueError("Source document missing or has no total_pages")
            total_pages = source_doc.total_pages

        windows = generate_page_windows(total_pages=total_pages, window_size=5, overlap=1)
        all_beats = []
        consecutive_failures = 0

        
        for start_page, end_page in windows:
            beats = None
            
            with get_db() as db:
                existing = (
                    db.query(StoryBeat)
                    .filter(
                        StoryBeat.session_id == session_id,
                        StoryBeat.source_document_id == source_doc_id,
                        StoryBeat.window_start_page == start_page,
                        StoryBeat.window_end_page == end_page,
                    )
                    .first()
                )
                if existing:
                    print(f"[run_beats] Skipping extraction for pages {start_page}-{end_page} (already exists)", file=sys.stderr)
                    continue
            
            try:
                beats = extract_beats_from_window(session_id, source_doc_id, start_page, end_page)
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                print(
                    f"[run_beats] Error extracting pages {start_page}-{end_page}: {e}",
                    file=sys.stderr,
                )
                if "connection refused" in str(e).lower() or "server disconnected" in str(e).lower():
                    print(f"[run_beats] Ollama unresponsive, backing off 15s", file=sys.stderr)
                    time.sleep(15)
                    try:
                        beats = extract_beats_from_window(session_id, source_doc_id, start_page, end_page)
                        consecutive_failures = 0
                    except Exception as retry_e:
                        print(f"[run_beats] Retry failed for pages {start_page}-{end_page}: {retry_e}", file=sys.stderr)

                if beats is None and consecutive_failures >= 5:
                    raise RuntimeError(
                        f"Too many consecutive extraction failures ({consecutive_failures}); aborting"
                    )

            # Save this window's beats immediately, instead of waiting until the end
            if beats:
                try:
                    save_candidate_beats(
                        source_doc_id=source_doc_id,
                        session_id=session_id,
                        candidates=beats,
                        window_start_page=start_page,
                        window_end_page=end_page
                    )
                    all_beats.extend(beats)
                except Exception as save_e:
                    print(
                        f"[run_beats] Error saving beats for pages {start_page}-{end_page}: {save_e}",
                        file=sys.stderr,
                    )
                    raise

            time.sleep(3)

        if not all_beats:
            raise ValueError("No beats extracted")

        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return all_beats

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_beats] Fatal error extracting beats for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_beats_reduce(source_doc_id: str, session_id: str, candidate_beats: list | None, final_beats: list | None):
    phase = "story_beats"
    step = "beats_reduce"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return candidate_beats, final_beats

    if candidate_beats is None:
        candidate_beats = _load_candidate_beats_from_db(session_id, source_doc_id)
    if not candidate_beats:
        raise ValueError("No candidate beats available for reduction")

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        clusters = cluster_candidates(candidate_beats)
        reduced_clusters = split_and_reduce(
            clusters, reduce_cluster,
            token_budget=4000, chars_per_token=4, format_fn=json.dumps,
        )
        merged_beats = merge_clusters(reduced_clusters)
        for i, beat in enumerate(merged_beats):
            beat["order"] = i
        merged_beats.sort(key=lambda b: b["order"])
        final_beats = merged_beats

        with get_db() as db:
            complete_step(db, session_id, phase, step)

        return final_beats

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_beats] Error reducing beats for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_beats_save_reduced(source_doc_id: str, session_id: str, final_beats: list | None):
    phase = "story_beats"
    step = "beats_save_reduced"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            return

    if final_beats is None:
        candidate_beats = _load_candidate_beats_from_db(session_id, source_doc_id)
        if not candidate_beats:
            raise ValueError("No candidate beats available for re-reduction")
        clusters = cluster_candidates(candidate_beats)
        reduced_clusters = split_and_reduce(
            clusters, reduce_cluster,
            token_budget=4000, chars_per_token=4, format_fn=json.dumps,
        )
        final_beats = merge_clusters(reduced_clusters)
        for i, beat in enumerate(final_beats):
            beat["order"] = i
        final_beats.sort(key=lambda b: b["order"])

    with get_db() as db:
        try:
            start_step(db, session_id, phase, step)
        except Exception:
            pass

    try:
        with get_db() as db:
            replace_candidates_with_final_beats(db, session_id, source_doc_id, final_beats)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_beats] Error saving reduced beats for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _step_beats_graph(source_doc_id: str, session_id: str):
    phase = "story_beats"
    step = "beats_graph"

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
            beats = (
                db.query(StoryBeat)
                .filter(StoryBeat.session_id == session_id, StoryBeat.status != "candidate")
                .order_by(StoryBeat.beat_order)
                .all()
            )
            if not beats:
                raise ValueError("No final beats found for graph construction")

            beat_dicts = [
                {
                    "id": b.id,
                    "classification": b.classification,
                    "start_page": b.starting_page or 0,
                    "end_page": b.ending_page or 0,
                    "order": b.beat_order,
                }
                for b in beats
            ]

            graph_edges = build_beat_graph(beat_dicts)
            persist_beat_graph(db, session_id, graph_edges)

        with get_db() as db:
            complete_step(db, session_id, phase, step)

    except Exception as e:
        with get_db() as db:
            fail_step(db, session_id, phase, step, e)
            _mark_source_failed(db, source_doc_id, e)
        print(f"[run_beats] Error building graph for {source_doc_id}: {e}", file=sys.stderr)
        raise


def _load_candidate_beats_from_db(session_id: str, source_doc_id: str) -> list[dict]:
    with get_db() as db:
        rows = (
            db.query(StoryBeat)
            .filter(
                StoryBeat.session_id == session_id,
                StoryBeat.source_document_id == source_doc_id,
                StoryBeat.status == "candidate",
            )
            .order_by(StoryBeat.beat_order)
            .all()
        )
        if not rows:
            return []
        return [
            {
                "beat_type": r.beat_type,
                "description": r.description,
                "start_page": r.starting_page,
                "end_page": r.ending_page,
                "classification": r.classification,
                "characters": json.loads(r.characters) if r.characters else [],
                "requires": json.loads(r.requires) if r.requires else [],
                "introduces": json.loads(r.introduces) if r.introduces else [],
                "key_dialogues": json.loads(r.key_dialogues) if r.key_dialogues else [],
                "order": r.beat_order,
            }
            for r in rows
        ]


def _re_extract_beats(source_doc_id: str, session_id: str) -> list[dict]:
    print(f"[run_beats] Re-extracting beats for {source_doc_id}", file=sys.stderr)
    with get_db() as db:
        source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
        if not source_doc or not source_doc.total_pages:
            raise ValueError("Source document missing for re-extraction")
        total_pages = source_doc.total_pages

    windows = generate_page_windows(total_pages=total_pages, window_size=5, overlap=1)
    candidate_beats = []
    import time
    for start_page, end_page in windows:
        beats = extract_beats_from_window(session_id, source_doc_id, start_page, end_page)
        candidate_beats.extend(beats)
        time.sleep(3)

    if not candidate_beats:
        raise ValueError("No beats extracted during re-extraction")
    return candidate_beats


def _mark_source_failed(db, source_doc_id: str, error):
    source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_doc_id).first()
    if source_doc:
        source_doc.error_message = str(error)[:1000]
        source_doc.status = "failed"
        db.commit()
