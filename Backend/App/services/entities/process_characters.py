import sys
import json
import re

from Backend.App.services.utility.utility_functions import estimate_tokens

from ..utility.response import get_response
from ..utility.getdb import get_db
from ...models.rpg_sessions import Character, CharacterArcState, CharacterSegment, CharacterSpan, SourceDocument, ChronicleChapter
from ..documents.vectorstore import query_chroma_by_page_range
from ..documents.documents import token_length

PERSONALITY_PROMPT = """Analyze the personality of {character_name} using ONLY the provided non-continuous excerpts. No outside knowledge. Base all claims on text evidence; do not invent traits. Distinguish shown behavior from "(implied)" inferences and flag "(secondhand)" accounts. Do not summarize plot. Use a neutral, descriptive tone. If evidence is thin, set "has_sufficient_data" to false.

Your output MUST be exhaustive and highly detailed. In the "summary" field, provide a comprehensive, multi-paragraph analysis covering temperament, values, speech patterns, fears, sense of humor, and interpersonal dynamics. In the "traits" array, break down the character into granular, highly specific traits rather than broad generalizations. 

Output strictly valid JSON matching this schema:
{{
  "character_name": {{"type": "string"}},
  "has_sufficient_data": {{"type": "boolean"}},
  "summary": {{"type": "string"}}, 
  "traits": {{
    "type": "array",
    "items": {{
      "type": "object",
      "properties": {{
        "trait": {{"type": "string"}},  // granular trait, include "(implied)" or "(secondhand)" tags
        "evidence_pages": {{"type": "array", "items": {{"type": "integer"}}}}
      }}
    }}
  }},
  "contradictions": {{"type": "array", "items": {{"type": "string"}}}}  // detail inconsistent behaviors with page numbers; empty array if none
}}

Data:
{data}
"""

BACKSTORY_PROMPT = """Analyze the backstory of {character_name} (past history, origins, formative events) using ONLY the provided non-continuous excerpts. No outside knowledge. Distinguish stated facts from "(implied)" inferences and flag claims as "(secondhand - per [source])". Ignore present-tense plot; focus only on the past. If evidence is thin, set "has_sufficient_data" to false.

Your output MUST be exhaustive and highly detailed. In the "new_revelations" field, provide a comprehensive, deep-dive analysis of origins, family history, past relationships, prior roles, and formative experiences. Organize roughly chronologically if possible, otherwise by theme. Do not pad with speculation, but extract every available nuance and contextual detail from the text.

Output strictly valid JSON matching this schema:
{{
  "character_name": {{"type": "string"}},
  "has_sufficient_data": {{"type": "boolean"}},
  "new_revelations": {{"type": "string"}},  // highly detailed, exhaustive breakdown of past history
  "evidence_pages": {{"type": "array", "items": {{"type": "integer"}}}}
}}

Data:
{data}
"""

FIGHTING_STYLE_PROMPT = """Analyze the fighting style of {character_name} using ONLY the provided excerpts depicting physical conflict. No outside knowledge. Do not infer combat ability from non-combat excerpts. Distinguish demonstrated actions from "(stated)" claims and "(implied)" inferences; flag "(secondhand)" accounts. Do not summarize plot outcomes. If there is no combat evidence, set "has_combat_evidence" to false.

Your output MUST be exhaustive and highly detailed. In the "summary", provide a comprehensive multi-paragraph breakdown of weapons/tools, physical techniques, tactical approach (aggressive vs defensive, opportunistic vs disciplined), improvisation vs formal training, and composure under pressure. In the "traits" array, extract granular, highly specific combat habits and mechanical behaviors rather than broad descriptions.

Output strictly valid JSON matching this schema:
{{
  "character_name": {{"type": "string"}},
  "has_combat_evidence": {{"type": "boolean"}},
  "summary": {{"type": "string"}},  // exhaustive, highly detailed tactical and mechanical analysis
  "traits": {{
    "type": "array",
    "items": {{
      "type": "object",
      "properties": {{
        "trait": {{"type": "string"}},  // granular combat habit, include "(stated)", "(implied)", or "(secondhand)" tags
        "evidence_pages": {{"type": "array", "items": {{"type": "integer"}}}}
      }}
    }}
  }}
}}

Data:
{data}
"""



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

    
    segmented_characters = segment_characters(spanned_characters, book_total_chapters=len(db.query(ChronicleChapter).filter(ChronicleChapter.session_id == session_id).all()))
    
    
    for character in segmented_characters:
        if persist_character_segments(session_id, character):
            print(f"[process_characters] Persisted character segments in database for session {session_id}", file=sys.stderr)
        else:
            print(f"[process_characters] Failed to persist character segments in database for session {session_id}", file=sys.stderr)
    
    arc_states = []
    characters = db.query(Character).filter(Character.session_id == session_id).all()
    for character in characters:
       
        segments = db.query(CharacterSegment).filter(CharacterSegment.character_id == character.id).all()
        for segment in segments:
            arc_state = db.query(CharacterArcState).filter(
                CharacterArcState.character_id == character.id,
                CharacterArcState.segment_id == segment.id
            ).first()
            if not arc_state:
                arc_states.append(process_arc_records(session_id, segment.id))
                print(f"[process_characters] Processed arc records for character {character.name} and segment {segment.segment_number} in session {session_id}", file=sys.stderr)
            else:
                print(f"[process_characters] Arc record already exists for character {character.name} and segment {segment.segment_number} in session {session_id}, skipping.", file=sys.stderr)
    arc_records = []
    for arc_state in arc_states:
        if arc_state is None:
            continue
        try:
            arc_records.append(persist_arc_records(session_id, arc_state))
        except Exception as e:
            print(f"[process_characters] Error persisting arc records for character_id {arc_state['character_id']} and segment_id {arc_state['segment_id']} in session {session_id}: {e}", file=sys.stderr)
            continue
        
    print(arc_records)
    

def rank_characters(characters):
    return sorted(characters, key=lambda c: (c.get("total_pages", 0), len(c.get("spans", []))), reverse=True)

def span_statistic_of_character(character, book_total_pages):
    spans = character.get("spans", [])
    num_spans = len(spans)
    total_pages = character.get("total_pages", 0)

    size_threshold = 0.15 * book_total_pages
    gap_threshold = 0.05 * book_total_pages
    QUALIFYING_SPAN_FLOOR = 1  # lowered — even 1-page appearances count if the pattern recurs
    MIN_RECURRING_SPANS = 4    # new: raw appearance count alone can justify arc-based

    qualifying_spans = [s for s in spans if s["page_count"] >= QUALIFYING_SPAN_FLOOR]
    num_qualifying = len(qualifying_spans)

    max_gap = 0
    if num_qualifying > 1:
        for i in range(num_qualifying - 1):
            gap = qualifying_spans[i + 1]["start"] - qualifying_spans[i]["end"]
            max_gap = max(max_gap, gap)

    is_frequent_recurrence = num_spans >= MIN_RECURRING_SPANS

    if total_pages >= size_threshold or is_frequent_recurrence or (
        num_qualifying > 1 and max_gap > gap_threshold
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
                    character_name = character.get("name"),
                    start_page=span["start"],
                    end_page=span["end"],
                    chapter_number=chapter_number,
                    page_count = span["page_count"]
                )
                db.add(character_span_record)
            
        db.commit()
        return True


def segment_characters(characters, book_total_chapters, gap_threshold_ratio=0.15, min_gap_chapters=2,
                        min_chapters_per_segment=4, max_segments=6):

    gap_threshold = max(min_gap_chapters, round(gap_threshold_ratio * book_total_chapters))

    for character in characters:
        classification = character.get("classification")

        if classification == "arc-based":
            chapters = sorted(set(
                span.get("chapter_number") for span in character.get("spans", [])
                if span.get("chapter_number") is not None
            ))

            if not chapters:
                character["segments"] = []
                continue

            first_chapter = chapters[0]
            last_chapter = chapters[-1]
            span_of_range = last_chapter - first_chapter + 1
            coverage_ratio = len(chapters) / span_of_range if span_of_range > 0 else 1.0

            max_gap = 0
            for i in range(len(chapters) - 1):
                gap = chapters[i + 1] - chapters[i]
                max_gap = max(max_gap, gap)

            is_continuous = max_gap <= gap_threshold or coverage_ratio >= 0.6

            if is_continuous:
                # Continuous path: divide the character's own chapter range into
                # evenly-sized blocks, sized by their own span (not the whole book),
                # with no leftover-chapter straggler segment.
                total_span = last_chapter - first_chapter + 1
                num_segments = max(1, min(max_segments, total_span // min_chapters_per_segment))

                base_size = total_span // num_segments
                remainder = total_span % num_segments

                segments = []
                start = first_chapter
                for i in range(num_segments):
                    size = base_size + (1 if i < remainder else 0)
                    end = start + size - 1
                    segments.append({
                        "segment_number": i + 1,
                        "chapter_start": start,
                        "chapter_end": end
                    })
                    start = end + 1

            else:
                # Clustered path: group present-chapters, breaking on gaps > threshold
                segments = []
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
                segments.append({
                    "segment_number": seg_num,
                    "chapter_start": current_group[0],
                    "chapter_end": current_group[-1]
                })

            character["segments"] = segments

        elif classification == "static":
            spans = character.get("spans", [])
            chapter_numbers = [s["chapter_number"] for s in spans]
            if not chapter_numbers:
                character["segments"] = []
                continue
            chapter_start = min(chapter_numbers)
            chapter_end = max(chapter_numbers)
            character["segment_number"] = 1
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
 
def dedupe_overlap(chunk_a_text, chunk_b_text, min_overlap=20):
    """If chunk_b starts with the tail of chunk_a, strip the duplicated prefix from chunk_b."""
    max_check = min(len(chunk_a_text), len(chunk_b_text), 300)
    for overlap_len in range(max_check, min_overlap, -1):
        if chunk_a_text[-overlap_len:] == chunk_b_text[:overlap_len]:
            return chunk_b_text[overlap_len:]
    return chunk_b_text

def order_pool(pool):
    return sorted(pool, key=lambda c: (c["page"], c.get("start_index", 0)))


def strip_markdown_noise(text):
    text = re.sub(r'^#{1,3}\s*.*$', '', text, flags=re.MULTILINE)  # drop header lines
    text = re.sub(r'\n{3,}', '\n\n', text)  # collapse excess blank lines
    return text.strip()

def trim_pool_to_budget(pool, token_budget):
    while pool and sum(token_length(c["text"]) for c in pool) > token_budget:
        pool.pop(0)
    return pool
           
def prepare_pool_for_synthesis(pool, token_budget):
    ordered = order_pool(pool)
    cleaned = [strip_markdown_noise(c["text"]) for c in ordered]

    # dedupe adjacent overlaps
    for i in range(1, len(cleaned)):
        cleaned[i] = dedupe_overlap(cleaned[i-1], cleaned[i])

    combined_chunks = [{"text": t, **{k: v for k, v in ordered[i].items() if k != "text"}} for i, t in enumerate(cleaned)]
    return trim_pool_to_budget(combined_chunks, token_budget)
               
            

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
            
          


def persist_arc_records(session_id, arc_state, character_id, segment_id):
    if not arc_state:
        print(f"[persist_arc_records] No arc state found for character_id {character_id} and segment_id {segment_id} in session {session_id}, skipping arc record insertion.", file=sys.stderr)
        return False
    with get_db() as db:
        existing_arc_state = db.query(CharacterArcState).filter(
            CharacterArcState.character_id == arc_state["character_id"],
            CharacterArcState.segment_id == arc_state["segment_id"]
        ).first()
        if existing_arc_state:
            return False  # Arc state already exists, skip insertion
        
        character_name = db.query(Character).filter(Character.id == arc_state["character_id"]).first().name
        
        """
        PREPARE DATA FOR SYNTHESIS
        """
        
        
        personality_chunks = prepare_pool_for_synthesis(arc_state["personality_pool"], token_budget=4000 - estimate_tokens(PERSONALITY_PROMPT))
        backstory_chunks = prepare_pool_for_synthesis(arc_state["backstory_pool"], token_budget=4000 - estimate_tokens(BACKSTORY_PROMPT))
        fighting_style_chunks = prepare_pool_for_synthesis(arc_state["fighting_style_pool"], token_budget=4000 - estimate_tokens(FIGHTING_STYLE_PROMPT))
        
        """
        GET CHARACTER PERSONALITY, BACKSTORY, AND FIGHTING STYLE FROM LLM
        """
        
        print(f"[persist_arc_records] Extracting personality for character_id {arc_state['character_id']} and segment_id {arc_state['segment_id']} in session {session_id}", file=sys.stderr)
        print(f"[persist_arc_records] Input tokens: {estimate_tokens(PERSONALITY_PROMPT.format(character_name=character_name, data=personality_chunks))}", file=sys.stderr)
        personality = get_response(PERSONALITY_PROMPT.format(character_name=character_name, data=personality_chunks), mode="characters", type="personality")
        
        
        print(f"[persist_arc_records] Extracting backstory for character_id {arc_state['character_id']} and segment_id {arc_state['segment_id']} in session {session_id}", file=sys.stderr)
        print(f"[persist_arc_records] Input tokens: {estimate_tokens(BACKSTORY_PROMPT.format(character_name=character_name, data=backstory_chunks))}", file=sys.stderr)
        backstory = get_response(BACKSTORY_PROMPT.format(character_name=character_name, data=backstory_chunks), mode="characters", type="backstory")
        
        
        print(f"[persist_arc_records] Extracting fighting style for character_id {arc_state['character_id']} and segment_id {arc_state['segment_id']} in session {session_id}", file=sys.stderr)
        print(f"[persist_arc_records] Input tokens: {estimate_tokens(FIGHTING_STYLE_PROMPT.format(character_name=character_name, data=fighting_style_chunks))}", file=sys.stderr)
        
        fighting_style = get_response(FIGHTING_STYLE_PROMPT.format(character_name=character_name, data=fighting_style_chunks), mode="characters", type="fighting_style")
       
        """
        SAVE CHARACTER ARC STATE TO DATABASE
        """

        arc_state_record = CharacterArcState(
            character_id=arc_state["character_id"],
            segment_id=arc_state["segment_id"],
            character_name=db.query(Character).filter(Character.id == arc_state["character_id"]).first().name,
            segment_number = db.query(CharacterSegment).filter(CharacterSegment.id == arc_state["segment_id"]).first().segment_number,
            personality_md=personality,
            backstory_delta_md=backstory,
            fighting_style_md=fighting_style
        )
        db.add(arc_state_record)
        db.commit()
        print(f"[persist_arc_records] COMMITTED id={arc_state_record.id}", file=sys.stderr)
        return {
            "character_id": arc_state_record.character_id,
            "segment_id": arc_state_record.segment_id,
            "character_name": arc_state_record.character_name,
            "segment_number": arc_state_record.segment_number,
            "personality_md": arc_state_record.personality_md,
            "backstory_delta_md": arc_state_record.backstory_delta_md,
            "fighting_style_md": arc_state_record.fighting_style_md
        }