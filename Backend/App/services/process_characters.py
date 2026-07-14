import sys
import json
import re
from ..database import get_db
from ..models.rpg_sessions import Character, CharacterSpan, SourceDocument, ChronicleChapter


def process_characters(session_id, source_document_id, characters):
    
    ranked_characters = rank_characters(characters)
    
    with get_db() as db:
        source_document = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
        book_total_pages = source_document.total_pages if source_document else 0
    
    
    spanned_characters = []
    for character in ranked_characters:
        span_stats = span_statistic_of_character(character, book_total_pages)
        spanned_characters.append(span_stats)
        
    print(f"[process_characters] Spanned characters:\n{format_with_inline_pages(spanned_characters)}",file=sys.stderr,)    
    
    store_characters_in_chapters(spanned_characters, session_id)
    print(f"[process_characters] Stored characters in chapters for session {session_id}", file=sys.stderr)
    
    if store_characters(session_id, spanned_characters, source_document_id):
        print(f"[process_characters] Stored characters in database for session {session_id}", file=sys.stderr)
    else:
        print(f"[process_characters] Failed to store characters in database for session {session_id}", file=sys.stderr)
    
    
    for character in spanned_characters:
        if store_character_spans(session_id, character):
            print(f"[process_characters] Stored character spans in database for session {session_id}", file=sys.stderr)
        else:
            print(f"[process_characters] Failed to store character spans in database for session {session_id}", file=sys.stderr)

    
    


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


def store_characters_in_chapters(characters, session_id):
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
        
def store_characters(sessionid, characters, source_doc_id):
    with get_db() as db:
        
        if (db.query(Character).filter(Character.session_id == sessionid).first() is not None):
            print(f"[store_characters] Characters already exist for session {sessionid}, skipping insertion.", file=sys.stderr)
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


def store_character_spans(session_id, character):
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
   
        for span in character.get("spans",[]):
            chapter_number = None
            for chapter in chapters:
                if span["start"] <= chapter.end_page and span["end"] >= chapter.start_page:
                    chapter_number = chapter.number
                    break
            if chapter_number is not None:
                character_span_record = CharacterSpan(
                    session_id=session_id,
                    character_id = character_record.character_id,
                    start_page=span["start"],
                    end_page=span["end"],
                    chapter_number=chapter_number,
                    page_count = span["page_count"]
                )
                db.add(character_span_record)
            
        db.commit()
        return True

