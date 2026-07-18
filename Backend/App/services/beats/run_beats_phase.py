import sys
import json
import time
from ..utility.getdb import get_db
from ..utility.status import is_step_completed, start_step, complete_step, fail_step
from ...models.rpg_sessions import SourceDocument, StoryBeat
from ..documents.documents import generate_page_windows
from .extraction import extract_beats_from_window, save_candidate_beats, replace_candidates_with_final_beats, save_reduced_beats
from .extraction import chunk_candidates_by_budget, reduce_cluster, merge_clusters
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
                    .all()
                )
                if existing:
                    print(f"[run_beats] Skipping extraction for pages {start_page}-{end_page} (already exists)", file=sys.stderr)
                    all_beats.append(
                        [{
                        "beat_type": beats.beat_type,
                        "description": beats.description,
                        "start_page": beats.starting_page,
                        "end_page": beats.ending_page,
                        "classification": beats.classification,
                        "characters": json.loads(beats.characters) if beats.characters else [],
                        "requires": json.loads(beats.requires) if beats.requires else [],
                        "introduces": json.loads(beats.introduces) if beats.introduces else [],
                        "key_dialogues": json.loads(beats.key_dialogues) if beats.key_dialogues else
                        [],
                    } 
                        for beats in existing
                    
                    ])
            
            try:
                beats = extract_beats_from_window(session_id, source_doc_id, start_page, end_page)
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                print(
                    f"[run_beats] Error extracting pages {start_page}-{end_page}: {e}",
                    file=sys.stderr,
                )
                
                if consecutive_failures >= 3:
                    raise RuntimeError(f"Failed to extract beats for 3 consecutive windows, last error: {e}")

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


def _step_beats_reduce(source_doc_id, session_id, candidate_beats, final_beats):
    phase = "story_beats"
    step = "beats_reduce"

    with get_db() as db:
        if is_step_completed(db, session_id, phase, step):
            final_beats = merge_clusters(
                db.query(StoryBeat)
                .filter(StoryBeat.session_id == session_id, StoryBeat.status == "reduced")
                .order_by(StoryBeat.beat_order)
                .all()
            )
            final_beats.sort(key=lambda b: (b["start_page"], b.get("end_page", b["start_page"])))
            for i, beat in enumerate(final_beats):
                beat["order"] = i
                
            return final_beats

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
        chunks = chunk_candidates_by_budget(
            candidate_beats,
            token_budget=4000,
            chars_per_token=4,
            overlap_count=3,
            format_fn=json.dumps,
        )
        
        reduced_clusters = []

        for i, chunk in enumerate(chunks):
            window_start_page = min(c.get("start_page", float('inf')) for c in chunk)
            window_end_page = max(c.get("end_page", float('-inf')) for c in chunk)

            existing_reduced = (
                db.query(StoryBeat)
                .filter(
                    StoryBeat.session_id == session_id,
                    StoryBeat.source_document_id == source_doc_id,
                    StoryBeat.status == "reduced",
                    StoryBeat.window_start_page == window_start_page,
                    StoryBeat.window_end_page == window_end_page,
                )
                .order_by(StoryBeat.beat_order)
                .all()
            )
            if existing_reduced:
                reduced_clusters.append(
                    [
                        {
                            "beat_type": beat.beat_type,
                            "description": beat.description,
                            "start_page": beat.starting_page,
                            "end_page": beat.ending_page,
                            "classification": beat.classification,
                            "characters": json.loads(beat.characters) if beat.characters else [],
                            "requires": json.loads(beat.requires) if beat.requires else [],
                            "introduces": json.loads(beat.introduces) if beat.introduces else [],
                            "key_dialogues": json.loads(beat.key_dialogues) if beat.key_dialogues else [],
                            "order": beat.beat_order,
                        }
                        for beat in existing_reduced
                    ]
                )
                continue

            print(f"[run_beats] Reducing chunk {i+1}/{len(chunks)} with {len(chunk)} candidates")
            reduced = reduce_cluster(chunk)
            reduced_clusters.append(reduced)
            save_reduced_beats(source_doc_id, session_id, reduced, window_start_page, window_end_page)
            
        merged_beats = merge_clusters(reduced_clusters)

        merged_beats.sort(key=lambda b: (b["start_page"], b.get("end_page", b["start_page"])))
        for i, beat in enumerate(merged_beats):
            beat["order"] = i

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
        with get_db() as db:
            reduced_rows = (
                db.query(StoryBeat)
                .filter(
                    StoryBeat.session_id == session_id,
                    StoryBeat.source_document_id == source_doc_id,
                    StoryBeat.status == "reduced",
                )
                .order_by(StoryBeat.beat_order)
                .all()
            )
            final_beats = merge_clusters([
                [
                    {
                        "beat_type": row.beat_type,
                        "description": row.description,
                        "start_page": row.starting_page,
                        "end_page": row.ending_page,
                        "classification": row.classification,
                        "characters": json.loads(row.characters) if row.characters else [],
                        "requires": json.loads(row.requires) if row.requires else [],
                        "introduces": json.loads(row.introduces) if row.introduces else [],
                        "key_dialogues": json.loads(row.key_dialogues) if row.key_dialogues else [],
                        "order": row.beat_order,
                    }
                    for row in reduced_rows
                ]
            ])
        final_beats.sort(key=lambda b: (b["start_page"], b.get("end_page", b["start_page"])))
        for i, beat in enumerate(final_beats):
            beat["order"] = i
        

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
