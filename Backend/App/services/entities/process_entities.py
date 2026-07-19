import sys
import time

from Backend.App.models.rpg_sessions import Entities

from ..utility.response import get_response
from ..beats.extraction import _assemble_pages_text, _parse_json_response
from ..documents.vectorstore import query_chroma_by_page_range
SYSTEM_PROMPT = '''
You are an entity extraction system for a narrative processing pipeline. Given a chunk of novel text, covering pages {start_page}-{end_page}, extract every distinct named entity that is explicitly present in the text.

ENTITY TYPES (assign exactly one):
- character: named people, deities, animals, or sentient beings
- location: named places, buildings, regions, realms
- faction: named groups, organizations, orders, camps, species-as-group
- item: named objects, weapons, artifacts, or magical items (must have a proper name or clear unique identifier — not generic objects like "a sword")
- concept: named prophecies, curses, magical systems, laws, or significant abstract ideas that are explicitly labeled/named in the text (not general themes you infer)

RULES:
1. Only extract entities explicitly named in the text. Do not infer unnamed entities, and do not describe or summarize them.
2. Use the fullest form of the name given anywhere in this chunk (e.g., "Percy Jackson" not "Percy", "Camp Half-Blood" not "the camp") — but only names that actually appear; do not invent a fuller name that isn't in the text.
3. Merge references to the same entity under ONE canonical entry, even if the text calls them different things (e.g., "Percy," "he," "the boy" referring to the same named character should collapse into one entry using the fullest name — pronouns alone don't count as a new mention unless needed to resolve which page they appear on).
4. Do not create duplicate entries for the same entity with slightly different name strings. Pick one canonical spelling/form per entity.
5. For "pages", list every page number where the entity is mentioned as a sorted list of integers (not a range string) — e.g. [12, 13, 14], not "12-14". If it only appears on one page, return a single-element list.
6. If no entities of a given type exist, simply omit that type — do not include empty placeholders.
7. If the text contains no extractable entities at all, return an empty JSON list: []

OUTPUT FORMAT:
Return ONLY a valid JSON list, no preamble, no markdown code fences, no trailing commentary. Each object must have exactly these keys: "name" (string), "type" (one of the five types above), "pages" (list of integers).

Example output:
[
  {{"name": "Percy Jackson", "type": "character", "pages": [12, 14]}},
  {{"name": "Metropolitan Museum of Art", "type": "location", "pages": [12, 13]}},
  {{"name": "Mrs. Dodds", "type": "character", "pages": [13, 14]}}
]

TEXT:
{text}
'''

def _normalize_entity(entity):
    if not isinstance(entity, dict):
        print(f"[process_entities._normalize_entity] Invalid entity format: {entity!r}", file=sys.stderr)
        return None

    name = entity.get("name")
    entity_type = entity.get("type")
    if isinstance(entity_type, str):
        entity_type = entity_type.strip().lower()
    pages = entity.get("pages")

    if not name or not isinstance(name, str):
        print(f"[process_entities._normalize_entity] Invalid or missing 'name' in entity: {entity!r}", file=sys.stderr)
        return None
    if entity_type not in ["character", "location", "faction", "item", "concept"]:
        print(f"[process_entities._normalize_entity] Invalid 'type' in entity: {entity!r}", file=sys.stderr)
        return None
    if not isinstance(pages, list) or not all(isinstance(p, int) for p in pages):
        print(f"[process_entities._normalize_entity] Invalid 'pages' in entity: {entity!r}", file=sys.stderr)
        return None
    

    # Normalize the name (e.g., strip whitespace)
    normalized_name = " ".join(name.split())
    # Remove duplicates and sort pages
    unique_pages = sorted(set(pages))

    return {
        "name": normalized_name,
        "type": entity_type,
        "pages": unique_pages,
    }



def extract_entities_from_window(session_id, start_page, end_page):
       
    chunks = query_chroma_by_page_range(
        session_id=session_id,
        start_page=start_page,
        end_page=end_page,
        n_results=1000,
    )

    if not chunks:
        print(
            f"[process_entities.extract_entities_from_window] No chunks found for "
            f"session_id={session_id}, window={start_page}-{end_page}",
            file=sys.stderr,
        )
        return []

    pages_text = _assemble_pages_text(chunks)

    prompt = SYSTEM_PROMPT.format(
        start_page=start_page,
        end_page=end_page,
        text=pages_text,
    )
    approx_tokens = len(prompt) // 4  # rough chars-to-tokens estimate
    print(
        f"[process_entities.extract_entities_from_window] window={start_page}-{end_page}, "
        f"session_id={session_id}, ~{approx_tokens} tokens, chunks={len(chunks)}",
        file=sys.stderr,
    )
    
    try:
        response = get_response(prompt, mode="chronicle_entities")
    except Exception as response_error:
        print(
            f"[process_entities.extract_entities_from_window] LLM call failed for "
            f"session_id={session_id}, window={start_page}-{end_page}: "
            f"{type(response_error).__name__}: {response_error}",
            file=sys.stderr,
        )
        raise

    print(
        f"[process_entities.extract_entities_from_window] Raw entity response for "
        f"session_id={session_id}, window={start_page}-{end_page}: {response}",
        file=sys.stderr,
    )

    try:
        entities = _parse_json_response(response)
    except Exception as parse_error:
        print(
            f"[process_entities.extract_entities_from_window] JSON parse failed for "
            f"session_id={session_id}, window={start_page}-{end_page}: "
            f"{type(parse_error).__name__}: {parse_error}",
            file=sys.stderr,
        )
        raise
    
    if entities is None or not isinstance(entities, list):
        print(
            f"[process_entities.extract_entities_from_window] Failed to parse entities for "
            f"session_id={session_id}, window={start_page}-{end_page}: invalid JSON response {entities!r}",
            file=sys.stderr,
        )
        return []

    normalized = [_normalize_entity(e) for e in entities]
    normalized = [e for e in normalized if e is not None]
    return normalized
  
def store_candidate_entities(session_id, candidate_entities, window_start_page, window_end_page, db):
    
    for entity in candidate_entities:
        if not isinstance(entity, dict):
            print(f"[process_entities.store_candidate_entities] Invalid entity format: {entity!r}", file=sys.stderr)
            continue

        name = entity.get("name")
        entity_type = entity.get("type")
        pages = entity.get("pages")

        start_page = min(pages) if pages else window_start_page
        end_page = max(pages) if pages else window_end_page


        new_entity = Entities(
            session_id=session_id,
            name=name,
            type=entity_type,
            window_start_page=window_start_page,
            window_end_page=window_end_page,
            pages = pages
        )
        db.add(new_entity)
    db.commit()
    return True

def seperate_candidates(candidate_entities):
    """
    Separate candidate entities into their respective types.
    Returns a dictionary with keys: 'character', 'location', 'faction', 'item', 'concept'.  
    """
    characters = []
    lore = []
    for entity in candidate_entities:
        if not isinstance(entity, dict):
            print(f"[process_entities.seperate_candidates] Invalid entity format: {entity!r}", file=sys.stderr)
            continue

        entity_type = entity.get("type")
        if entity_type == "character":
            characters.append(entity)
        elif entity_type in ["location", "faction", "item", "concept"]:
            lore.append(entity)
        else:   
            print(f"[process_entities.seperate_candidates] Unknown entity type: {entity_type!r} in entity: {entity!r}", file=sys.stderr)
            continue
    
    return characters, lore


def span_construction(pages, gap_tolerance=2):
    
    if not pages:
        return []

    sorted_pages = sorted(set(pages))

    spans = []
    current_run = [sorted_pages[0]]
    total_pages = len(sorted_pages)
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

    return spans, total_pages      
         
      
      

  

    
    