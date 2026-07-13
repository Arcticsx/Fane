from ..database import get_db
from ..models.rpg_sessions import Character, SourceDocument


def process_characters(session_id, source_document_id, characters):
    
    spanned_characters = []
    
    for character in characters:
        spans = span_construction(character["pages"], gap_tolerance=2)
        spanned_characters.append({
            "name": character["name"],
            "pages": spans
        })
    
      
    
    
    
    pass


def span_construction(pages, gap_tolerance=2):
    
    if not pages:
        return []

    sorted_pages = sorted(set(pages))

    spans = []
    current_run = [sorted_pages[0]]

    for prev_page, page in zip(sorted_pages, sorted_pages[1:]):
        gap = page - prev_page
        if gap <= gap_tolerance:
            current_run.append(page)
        else:
            spans.append({
                "start": current_run[0],
                "end": current_run[-1],
                "page_count": len(current_run),
                "pages": current_run,
            })
            current_run = [page]

    spans.append({
        "start": current_run[0],
        "end": current_run[-1],
        "page_count": len(current_run),
        "pages": current_run,
    })

    return spans