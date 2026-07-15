import sys
import json
import re
from ..database import get_db
from ..models.rpg_sessions import Character, CharacterArcState, CharacterSegment, CharacterSpan, SourceDocument, ChronicleChapter
from .vectorstore import query_chroma_by_page_range

def process_characters(session_id, source_document_id, characters):
    
    ranked_characters = rank_characters(characters)
    
    with get_db() as db:
        source_document = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
        book_total_pages = source_document.total_pages if source_document else 0
    
    
    spanned_characters = []
    for character in ranked_characters:
        span_stats = span_statistic_of_character(character, book_total_pages)
        spanned_characters.append(span_stats)
        
    
    persist_characters_in_chapters(spanned_characters, session_id)
    print(f"[process_characters] Persisted characters in chapters for session {session_id}", file=sys.stderr)
    
    if persist_characters(session_id, spanned_characters, source_document_id):
        print(f"[process_characters] Persisted characters in database for session {session_id}", file=sys.stderr)
    else:
        print(f"[process_characters] Failed to persist characters in database for session {session_id}", file=sys.stderr)
    
    
    for character in spanned_characters:
        if persist_character_spans(session_id, character):
            print(f"[process_characters] Persisted character spans in database for session {session_id}", file=sys.stderr)
        else:
            print(f"[process_characters] Failed to persist character spans in database for session {session_id}", file=sys.stderr)

    print(f"[process_characters] Spans with chapter numbers:\n{format_with_inline_pages(spanned_characters)}", file=sys.stderr)
    
    segmented_characters = segment_characters(spanned_characters, book_total_chapters=len(db.query(ChronicleChapter).filter(ChronicleChapter.session_id == session_id).all()))
    
    print(f"[process_characters] Segmented characters:\n{format_with_inline_pages(segmented_characters)}", file=sys.stderr)
    
    for character in segmented_characters:
        if persist_character_segments(session_id, character):
            print(f"[process_characters] Persisted character segments in database for session {session_id}", file=sys.stderr)
        else:
            print(f"[process_characters] Failed to persist character segments in database for session {session_id}", file=sys.stderr)
    
    
    characters = db.query(Character).filter(Character.session_id == session_id).all()
    for character in characters:
        if character.classification == "arc-based":
            segments = db.query(CharacterSegment).filter(CharacterSegment.character_id == character.id).all()
            for segment in segments:
                arc_state = db.query(CharacterArcState).filter(
                    CharacterArcState.character_id == character.id,
                    CharacterArcState.segment_id == segment.id
                ).first()
                if not arc_state:
                    process_arc_records(session_id, segment.id)
                    print(f"[process_characters] Processed arc records for character {character.name} and segment {segment.segment_number} in session {session_id}", file=sys.stderr)
                else:
                    print(f"[process_characters] Arc record already exists for character {character.name} and segment {segment.segment_number} in session {session_id}, skipping.", file=sys.stderr)
    
    
    
def rank_characters(characters):
    return sorted(characters, key=lambda c: (c.get("total_pages", 0), len(c.get("spans", []))), reverse=True)

def span_statistic_of_character(character, book_total_pages):
    spans = character.get("spans", [])
    num_spans = len(spans)
    total_pages = character.get("total_pages", 0)

    size_threshold = 0.15 * book_total_pages
    gap_threshold = 0.05 * book_total_pages
    QUALIFYING_SPAN_FLOOR = 3  # spans shorter than this are cameo noise, ignored for arc detection

    # Filter out cameo-length spans before evaluating count/gap
    qualifying_spans = [s for s in spans if s["page_count"] >= QUALIFYING_SPAN_FLOOR]
    num_qualifying = len(qualifying_spans)

    max_gap = 0
    if num_qualifying > 1:
        for i in range(num_qualifying - 1):
            gap = qualifying_spans[i + 1]["start"] - qualifying_spans[i]["end"]
            max_gap = max(max_gap, gap)

    if total_pages >= size_threshold or (
        num_qualifying > 1
        and max_gap > gap_threshold
    ):
        classification = "arc-based"
    else:
        classification = "static"

    return {
        "name": character.get("name"),
        "total_pages": total_pages,
        "num_spans": num_spans,
        "num_qualifying_spans": num_qualifying,
        "max_gap": max_gap,
        "classification": classification,
        "spans": spans
    }

def format_with_inline_pages(data):
    dumped = json.dumps(data, indent=4)

    def collapse_pages(match):
        # extract the numbers inside the matched "pages": [ ... ] block
        nums = re.findall(r'\d+', match.group(0))
        return f'"pages": [{", ".join(nums)}]'

    return re.sub(r'"pages":\s*\[[^\]]*\]', collapse_pages, dumped, flags=re.DOTALL)


def persist_characters_in_chapters(characters, session_id):
    with get_db() as db:
        chapters = (
            db.query(ChronicleChapter)
            .filter(ChronicleChapter.session_id == session_id)
            .all()
        )

        if not chapters:
            return

        for chapter in chapters:
            
            if chapter.characters:
                continue  # Skip if characters are already stored for this chapter   
            
            chapter_characters = []

            for character in characters:
                matching_spans = []

                for span in character.get("spans", []):
                    if (
                        span["start"] <= chapter.end_page
                        and span["end"] >= chapter.start_page
                    ):
                        matching_spans.append({
                            "start": span["start"],
                            "end": span["end"]
                        })

                if matching_spans:
                    chapter_characters.append({
                        "name": character["name"],
                        "spans": matching_spans
                    })

            chapter.characters = chapter_characters

        db.commit()
        
def persist_characters(sessionid, characters, source_doc_id):
    with get_db() as db:
        
        if (db.query(Character).filter(Character.session_id == sessionid).first() is not None):
            print(f"[persist_characters] Characters already exist for session {sessionid}, skipping insertion.", file=sys.stderr)
            return False 
        
        for character in characters:
            num_chapters_present = 0
            chapters = (
                db.query(ChronicleChapter)
                .filter(ChronicleChapter.session_id == sessionid)
                .all()
            )
            for chapter in chapters:
                for i in range(len(chapter.characters)):
                    if chapter.characters[i]["name"] == character.get("name"):
                        num_chapters_present += 1
                        break

            character_record = Character(
                session_id=sessionid,
                source_document_id=source_doc_id,
                name=character.get("name"),
                classification=character.get("classification"),
                total_pages=character.get("total_pages"),
                num_spans=character.get("num_spans"),
                num_chapters_present=num_chapters_present,
                
            )
            db.add(character_record)
        db.commit()
    return True



def persist_character_spans(session_id, character):
    with get_db() as db:
        
        
        chapters = (
                db.query(ChronicleChapter)
                .filter(ChronicleChapter.session_id == session_id)
                .all()
            )
        character_record = db.query(Character).filter(Character.session_id == session_id, Character.name == character.get("name")).first()
        if not character_record:
            print(f"[store_character_spans] Character {character.get('name')} not found in database for session {session_id}, skipping span insertion.", file=sys.stderr)
            return False
        
        # if db.query(CharacterSpan).filter(CharacterSpan.character_id == character_record.id).first() is not None:
        #     print(f"[store_character_spans] Spans for character {character.get('name')} already exist for session {session_id}, skipping insertion.", file=sys.stderr)
        #     return False
   
        for span in character.get("spans",[]):
            chapter_number = None
            for chapter in chapters:
                if span["start"] <= chapter.end_page and span["end"] >= chapter.start_page:
                    chapter_number = chapter.number
                    break
                
            span["chapter_number"] = chapter_number 
            if db.query(CharacterSpan).filter(CharacterSpan.character_id == character_record.id).first() is not None:
                print(f"[store_character_spans] Spans for character {character.get('name')} already exist for session {session_id}, skipping insertion.", file=sys.stderr)
                continue
            
            if chapter_number is not None:
                character_span_record = CharacterSpan(
                    character_id = character_record.id,
                    start_page=span["start"],
                    end_page=span["end"],
                    chapter_number=chapter_number,
                    page_count = span["page_count"]
                )
                db.add(character_span_record)
            
        db.commit()
        return True


def segment_characters(characters, book_total_chapters, gap_threshold_ratio=0.15, min_gap_chapters=2):

    gap_threshold = max(min_gap_chapters, round(gap_threshold_ratio * book_total_chapters))

    for character in characters:
        if character.get("classification") == "arc-based":
            chapters = list(dict.fromkeys([
                span.get("chapter_number") for span in character.get("spans", [])
                if span.get("chapter_number") is not None
            ]))
            chapters.sort()

            if not chapters:
                character["segments"] = []
                continue

            # Determine presence pattern: continuous vs clustered
            span_of_range = chapters[-1] - chapters[0] + 1
            coverage_ratio = len(chapters) / span_of_range if span_of_range > 0 else 1.0

            # Check largest gap between consecutive present-chapters
            max_gap = 0
            for i in range(len(chapters) - 1):
                gap = chapters[i + 1] - chapters[i]
                max_gap = max(max_gap, gap)

            is_continuous = max_gap <= gap_threshold or coverage_ratio >= 0.6

            segments = []
            if is_continuous:
                # Continuous path: divide the full chapter range into fixed-size blocks
                num_segments = max(1, min(6, book_total_chapters // 4))
                first_chapter = chapters[0]
                last_chapter = chapters[-1]
                total_span = last_chapter - first_chapter + 1
                block_size = max(1, round(total_span / num_segments))

                seg_num = 1
                start = first_chapter
                while start <= last_chapter:
                    end = min(start + block_size - 1, last_chapter)
                    segments.append({
                        "segment_number": seg_num,
                        "chapter_start": start,
                        "chapter_end": end
                    })
                    seg_num += 1
                    start = end + 1
            else:
                # Clustered path: group present-chapters, breaking on gaps > threshold
                seg_num = 1
                current_group = [chapters[0]]
                for i in range(1, len(chapters)):
                    gap = chapters[i] - chapters[i - 1]
                    if gap > gap_threshold:
                        segments.append({
                            "segment_number": seg_num,
                            "chapter_start": current_group[0],
                            "chapter_end": current_group[-1]
                        })
                        seg_num += 1
                        current_group = [chapters[i]]
                    else:
                        current_group.append(chapters[i])
                # flush last group
                segments.append({
                    "segment_number": seg_num,
                    "chapter_start": current_group[0],
                    "chapter_end": current_group[-1]
                })

            character["segments"] = segments

        elif character.get("classification") == "static":
            character["segment_number"] = 1
            spans = character.get("spans", [])
            chapter_numbers = [s["chapter_number"] for s in spans]
            chapter_start = min(chapter_numbers)
            chapter_end = max(chapter_numbers)
            character["segments"] = [{
                "segment_number": 1,
                "chapter_start": chapter_start,
                "chapter_end": chapter_end
            }]

    return characters

def persist_character_segments(session_id, character):
    with get_db() as db:
        character_record = db.query(Character).filter(
            Character.session_id == session_id,
            Character.name == character.get("name")
        ).first()

        if not character_record:
            print(f"[persist_character_segments] Character {character.get('name')} not found in database for session {session_id}, skipping segment insertion.", file=sys.stderr)
            return False

        # Clear existing segments so reruns don't leave stale data from old thresholds
        db.query(CharacterSegment).filter(
            CharacterSegment.character_id == character_record.id
        ).delete()

        for segment in character.get("segments", []):
            db.add(CharacterSegment(
                character_id=character_record.id,
                character_name=character.get("name"),
                segment_number=segment.get("segment_number"),
                chapter_start=segment.get("chapter_start"),
                chapter_end=segment.get("chapter_end")
            ))

        db.commit()
    return True

def process_arc_records(session_id, segment_id):
    with get_db() as db:
        segment = db.query(CharacterSegment).filter(CharacterSegment.id == segment_id).first()
        if not segment:
            print(f"[process_arc_records] No segment found for segment_id {segment_id} in session {session_id}, skipping arc record insertion.", file=sys.stderr)
            return False

        character = db.query(Character).filter(Character.id == segment.character_id).first()
        if not character:
            print(f"[process_arc_records] No character found for segment_id {segment_id} in session {session_id}, skipping arc record insertion.", file=sys.stderr)
            return False

        chapter_start = segment.chapter_start
        chapter_end = segment.chapter_end

        starting_chapter = db.query(ChronicleChapter).filter(
            ChronicleChapter.session_id == session_id,
            ChronicleChapter.number == chapter_start,
        ).first()
        
        ending_chapter = db.query(ChronicleChapter).filter(
            ChronicleChapter.session_id == session_id,
            ChronicleChapter.number == chapter_end,
        ).first()
        
        if not starting_chapter or not ending_chapter:
            print(f"[process_arc_records] Starting or ending chapter not found for segment_id {segment_id} in session {session_id}, skipping arc record insertion.", file=sys.stderr)
            return False

        starting_page = starting_chapter.start_page
        ending_page = ending_chapter.end_page

        chunks = query_chroma_by_page_range(
            session_id=session_id,
            start_page=starting_page,
            end_page=ending_page,
        )
        if not chunks:
            print(f"[process_arc_records] No chunks found for segment_id {segment_id} in session {session_id}, skipping arc record insertion.", file=sys.stderr)
            return False

        # Score every candidate chunk on all three axes, with name-proximity weighting
        scored_chunks = []
        for i, chunk in enumerate(chunks):
            proximity = name_proximity_weight(character.name, chunk, chunks, i)
            scored_chunks.append({
                "chunk": chunk,
                "personality_score": rank_personality_chunks(chunk) * proximity,
                "backstory_score": rank_backstory_chunks(chunk) * proximity,
                "fighting_style_score": rank_fighting_style_chunks(chunk) * proximity,
            })

        # --- Debug: print score distributions before thresholding ---
        for key in ["personality_score", "backstory_score", "fighting_style_score"]:
            values = sorted(sc[key] for sc in scored_chunks)
            n = len(values)
            if n == 0:
                print(f"[process_arc_records] {character.name} segment {segment_id} — no chunks to score for {key}", file=sys.stderr)
                continue
            print(
                f"[process_arc_records] {character.name} segment {segment_id} — {key}: "
                f"n={n} min={values[0]:.3f} p25={values[n // 4]:.3f} "
                f"median={values[n // 2]:.3f} p75={values[(3 * n) // 4]:.3f} max={values[-1]:.3f}",
                file=sys.stderr
            )

        # TODO: arbitrary placeholder — replace once real distributions are reviewed
        MIN_SCORE_THRESHOLD = 0.5

        # Bin by page position within the segment's page range
        bins = bin_chunks_by_page(scored_chunks, starting_page, ending_page, num_bins=5)

        personality_pool = select_top_per_bin(bins, "personality_score", min_score=MIN_SCORE_THRESHOLD)
        backstory_pool = select_top_per_bin(bins, "backstory_score", min_score=MIN_SCORE_THRESHOLD)
        fighting_style_pool = select_top_per_bin(bins, "fighting_style_score", min_score=MIN_SCORE_THRESHOLD)

        print(
            f"[process_arc_records] {character.name} segment {segment_id} — pool sizes: "
            f"personality={len(personality_pool)} backstory={len(backstory_pool)} fighting_style={len(fighting_style_pool)}",
            file=sys.stderr
        )

        return {
            "character_id": character.id,
            "segment_id": segment.id,
            "personality_pool": personality_pool,
            "backstory_pool": backstory_pool,
            "fighting_style_pool": fighting_style_pool,
        }
            
            
            

def rank_personality_chunks(chunk):
    text = chunk["text"] or ""
    dialogue_score = text.count('"') / 2
    emotion_words = ["felt", "wondered", "feared", "hoped", "laughed", "snapped", "smiled", "wished"]
    emotion_score = sum(text.lower().count(w) for w in emotion_words)
    word_count = max(len(text.split()), 1)
    return (dialogue_score * 1.0 + emotion_score * 1.5) / word_count * 1000


def rank_backstory_chunks(chunk):
    text = chunk["text"] or ""
    retrospective_words = ["had been", "used to", "years ago", "remembered", "grew up", "once was"]
    retro_score = sum(text.lower().count(w) for w in retrospective_words)
    header_text = " ".join(filter(None, [chunk.get("section"), chunk.get("subsection")])).lower()
    header_boost = 5 if any(kw in header_text for kw in ["origin", "past", "history", "before"]) else 0
    word_count = max(len(text.split()), 1)
    return (retro_score * 2.0 + header_boost) / word_count * 1000


def rank_fighting_style_chunks(chunk):
    text = chunk["text"] or ""
    combat_words = ["sword", "struck", "dodged", "blocked", "parried", "charged", "attacked", "blade", "fought"]
    combat_score = sum(text.lower().count(w) for w in combat_words)
    header_text = " ".join(filter(None, [chunk.get("section"), chunk.get("subsection")])).lower()
    header_boost = 5 if any(kw in header_text for kw in ["battle", "duel", "fight", "war"]) else 0
    word_count = max(len(text.split()), 1)
    return (combat_score * 2.0 + header_boost) / word_count * 1000


def name_proximity_weight(character_name, chunk, all_chunks, index):
    text = chunk["text"] or ""
    if character_name.lower() in text.lower():
        return 1.0

    # Check adjacent chunks via position in the already page/start_index-ordered list
    neighbors = []
    if index > 0:
        neighbors.append(all_chunks[index - 1])
    if index < len(all_chunks) - 1:
        neighbors.append(all_chunks[index + 1])

    for neighbor in neighbors:
        if character_name.lower() in (neighbor["text"] or "").lower():
            return 0.6

    return 0.25  # low baseline — not nearby, but not excluded outright


def bin_chunks_by_page(scored_chunks, start_page, end_page, num_bins=5):
    total_span = max(end_page - start_page + 1, 1)
    num_bins = max(1, min(num_bins, total_span))
    bin_size = total_span / num_bins

    bins = [[] for _ in range(num_bins)]
    for sc in scored_chunks:
        page = sc["chunk"]["page"] or start_page
        bin_index = int((page - start_page) / bin_size)
        bin_index = min(bin_index, num_bins - 1)  # guard against edge rounding at end_page
        bins[bin_index].append(sc)

    return bins


def select_top_per_bin(bins, score_key, min_score=0.0):
    pool = []
    for bin_chunks in bins:
        if not bin_chunks:
            continue
        best = max(bin_chunks, key=lambda sc: sc[score_key])
        if best[score_key] >= min_score:
            pool.append(best["chunk"])
    return pool   
            
            


def persist_arc_records(session_id):
    with get_db() as db:
        characters = db.query(Character).filter(Character.session_id == session_id).all()
        if db.query(CharacterArcState).filter(CharacterArcState.character_id.in_([c.id for c in characters])).first() is not None:
            print(f"[persist_arc_records] Arc records already exist for session {session_id}, skipping insertion.", file=sys.stderr)
            return False
        for character in characters:
            if character.classification == "arc-based":
                segments = db.query(CharacterSegment).filter(CharacterSegment.character_id == character.id).all()
                for segment in segments:
                    
                    db.add(CharacterArcState(
                        character_id=character.id,
                        character_name=character.name,
                        segment_id= segment.id,
                        segment_number=segment.segment_number,
                    ))
        db.commit()