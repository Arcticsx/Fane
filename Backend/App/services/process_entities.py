import sys
import time

from Backend.App.models.rpg_sessions import SourceDocument
from Backend.App.response import get_response
from Backend.App.services.extraction import _assemble_pages_text, _normalize_beat, _parse_json_response, extract_beats_from_window
from Backend.App.services.vectorstore import query_chroma_by_page_range

from .documents import generate_page_windows
from ..database import get_db

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
        print(f"Invalid entity format: {entity}")
        return None

    name = entity.get("name")
    entity_type = entity.get("type")
    pages = entity.get("pages")

    if not name or not isinstance(name, str):
        print(f"Invalid or missing 'name' in entity: {entity}")
        return None
    if entity_type not in ["character", "location", "faction", "item", "concept"]:
        print(f"Invalid 'type' in entity: {entity}")
        return None
    if not isinstance(pages, list) or not all(isinstance(p, int) for p in pages):
        print(f"Invalid 'pages' in entity: {entity}")
        return None

    # Normalize the name (e.g., strip whitespace)
    normalized_name = name.strip()

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
        return []

    pages_text = _assemble_pages_text(chunks)

    prompt = SYSTEM_PROMPT.format(
        start_page=start_page,
        end_page=end_page,
        pages_text=pages_text,
    )
    approx_tokens = len(prompt) // 4  # rough chars-to-tokens estimate
    print(f"[DEBUG] window {start_page}-{end_page}: ~{approx_tokens} tokens, {len(chunks)} chunks")
    
    response = get_response(prompt, mode="chronicle_entities")
    print(response)
    entities = _parse_json_response(response)
    
    if entities is None or not isinstance(entities, list):
        print(f"Failed to parse entities for pages {start_page}-{end_page}: invalid JSON response")
        return []

    normalized = [_normalize_entity(e) for e in entities]
    normalized = [e for e in normalized if e is not None]
    return normalized
  


def process_entities(session_id, source_document_id):
    with get_db() as db:
      source_doc = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
      
      if not source_doc or not source_doc.total_pages:
        raise ValueError("Source document missing or has no total_pages")
      
      windows = generate_page_windows(total_pages=source_doc.total_pages, window_size=5, overlap=1)
      candidate_entities = []
      consecutive_failures = 0

      for start_page, end_page in windows:
          try:
              entities = extract_entities_from_window(session_id, start_page, end_page)
              candidate_entities.extend(entities)
              consecutive_failures = 0
          except Exception as e:
              consecutive_failures += 1
              print(
                  f"[process_story_beats] Error extracting pages {start_page}-{end_page} "
                  f"for {source_document_id}: {e}",
                  file=sys.stderr,
              )
              # If the local model server itself is down, back off harder before
              # hammering it with the next window's request.
              if "connection refused" in str(e).lower() or "server disconnected" in str(e).lower():
                  print(f"[process_story_beats] Ollama appears unresponsive, backing off 15s", file=sys.stderr)
                  time.sleep(15)
                  entities = extract_entities_from_window(session_id, start_page, end_page)
              if consecutive_failures >= 5:
                  raise RuntimeError(
                      f"Too many consecutive extraction failures ({consecutive_failures}); "
                      f"aborting rather than continuing to degrade"
                  )
          finally:
              time.sleep(3) 
        
         
      
      

  

    
    