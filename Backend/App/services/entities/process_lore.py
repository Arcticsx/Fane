
from ...models.rpg_sessions import LoreEntity, LoreSegment, LoreSpan, LoreState, ChronicleChapter

def classify_lore(lore, book_total_pages):
    
    size_threshold = 0.15 * book_total_pages
    gap_threshold = 0.05 * book_total_pages
    QUALIFYING_SPAN_FLOOR = 1
    MIN_RECURRING_SPANS = 4

    spans = lore.get("spans", [])
    num_spans = len(spans)
    total_pages = lore.get("total_pages", 0)
    entity_type = lore.get("type")

    if entity_type in ("Item", "Concept"):
        return {
            "name": lore["name"],
            "total_pages": total_pages,
            "spans": spans,
            "num_spans": num_spans,
            "type": entity_type,
            "classification": "static"
        }

    qualifying_spans = [s for s in spans if s["page_count"] >= QUALIFYING_SPAN_FLOOR]
    num_qualifying = len(qualifying_spans)

    max_gap = 0
    if num_qualifying > 1:
        for i in range(num_qualifying - 1):
            max_gap = max(max_gap, qualifying_spans[i + 1]["start"] - qualifying_spans[i]["end"])

    is_frequent_recurrence = num_spans >= MIN_RECURRING_SPANS

    if total_pages >= size_threshold or is_frequent_recurrence or (
        num_qualifying > 1 and max_gap > gap_threshold
    ):
        classification = "arc-based"
    else:
        classification = "static"

    return {
        "name": lore["name"],
        "total_pages": total_pages,
        "spans": spans,
        "num_spans": num_spans,
        "type": entity_type,
        "classification": classification
    }
    
def persist_lore_in_chapter(db, session_id, lore_entities):
    
    chapters = (
        db.query(LoreEntity)
        .filter(LoreEntity.session_id == session_id)
        .all()
    )

    if not chapters:
        return

    for chapter in chapters:
        
        if chapter.lore:
            continue  # Skip if characters are already stored for this chapter   
        
        chapter_lore = []

        for lore in lore_entities:
            matching_spans = []

            for span in lore.get("spans", []):
                if (
                    span["start"] <= chapter.end_page
                    and span["end"] >= chapter.start_page
                ):
                    matching_spans.append({
                        "start": span["start"],
                        "end": span["end"]
                    })

            if matching_spans:
                chapter.lore.append({
                    "name": lore["name"],
                    "spans": matching_spans
                })

        chapter.lore = chapter_lore

        db.commit()
    
    return True

def persist_lore(db, session_id, lore_entities):
    for lore in lore_entities:
        existing_lore = (
            db.query(LoreEntity)
            .filter(
                LoreEntity.session_id == session_id,
                LoreEntity.name == lore["name"]
            )
            .first()
        )
        
        chapters = db.query(ChronicleChapter).filter_by(session_id=session_id).all()
        num_chapters_present = 0
        
        for chapter in chapters:
            for i in range(len(chapter.lore)):
                if chapter.lore[i]["name"] == lore["name"]:
                    num_chapters_present += 1

        if existing_lore:
            pass  # Update existing lore if needed
        else:
            new_lore = LoreEntity(
                session_id=session_id,
                name=lore["name"],
                total_pages=lore.get("total_pages", 0),
                type=lore.get("type"),
                classification=lore.get("classification"),
                num_chapters=num_chapters_present,
                num_spans=lore.get("num_spans", 0),
            )
            db.add(new_lore)
    db.commit()
    return True

def persist_lore_segments(session_id, lore_entity, db):
    lore_record = db.query(LoreEntity).filter(
        LoreEntity.session_id == session_id,
        LoreEntity.name == lore_entity.get("name")
    ).first()

    if not lore_record:
        print(f"[persist_lore_segments] Lore entity {lore_entity.get('name')} not found in database for session {session_id}, skipping segment insertion.", file=sys.stderr)
        return False

    # Clear existing segments so reruns don't leave stale data from old thresholds
    db.query(LoreSegment).filter(
        LoreSegment.entity_id == lore_record.id
    ).delete()

    for segment in lore_entity.get("segments", []):
        db.add(LoreSegment(
            entity_id=lore_record.id,
            segment_number=segment.get("segment_number"),
            chapter_start=segment.get("chapter_start"),
            chapter_end=segment.get("chapter_end")
        ))

    db.commit()
    return True