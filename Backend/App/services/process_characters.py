import sys
import json
import re
from ..database import get_db
from ..models.rpg_sessions import Character, SourceDocument


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