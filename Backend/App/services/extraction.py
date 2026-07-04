try:
    from .vectorstore import query_chroma_by_page_range
except ImportError:
    from vectorstore import query_chroma_by_page_range

try:
    from .response import get_response
except ImportError:
    from response import get_response

import json
import re
from database import get_db
from models.rpg_sessions import StoryBeat

SYSTEM_PROMPT = '''
You are a Narrative Architect. Extract all mandatory plot beats from the given novel text, which covers pages {start_page}-{end_page}.

A mandatory beat is a concrete, irreversible event that advances the main arc, changes a character's situation/knowledge/relationships, and cannot be skipped without breaking the story.

OUTPUT
Return a JSON list (empty list if no beats exist). Each beat:
{{
  "order": 1,
  "beat_type": "decision_point",
  "description": "One-sentence, immutable summary.",
  "start_page": 12,
  "end_page": 14,
  "requires": ["asset1"],
  "introduces": ["asset2"],
  "key_dialogues": ["Verbatim quote", "..."]
}}

BEAT TYPES
- decision_point - meaningful choice affecting plot
- transition - travel/time passing, no major plot impact
- dialogue - conversation conveying info or advancing relationships
- combat - fight/duel/confrontation
- revelation - discovery of crucial info/object/truth
- exploration - investigating a location/object/situation
- reaction - world/NPCs react to prior player action (no input)
- flashback - fixed memory sequence
- dream_vision - fixed dream/prophecy/hallucination

RULES
1. Extract every mandatory beat - no cap.
2. Page ranges stay within {start_page}-{end_page}, non-overlapping between beats.
3. requires: tags that must already exist from earlier beats (overall story), else [].
4. introduces: new tags this beat creates (knowledge, items, relationship/state changes).
5. key_dialogues: up to 5 verbatim quotes critical to the scene.
6. description must be fixed/immutable - never changes during gameplay.
7. Page numbers are marked inline in the source text as "[page N]" - use these
   markers to determine accurate start_page/end_page values for each beat.

TEXT TO ANALYZE (pages {start_page}-{end_page}):
{pages_text}
'''


def _assemble_pages_text(chunks):
    
    ordered = sorted(
        chunks,
        key=lambda c: (c.get("page") or 0, c.get("start_index") or 0),
    )
    parts = []
    for c in ordered:
        page = c.get("page")
        text = c.get("text", "")
        parts.append(f"[page {page}]\n{text}")
    return "\n\n".join(parts)


def extract_beats_from_window(session_id, source_doc_id, start_page, end_page):
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

    response = get_response(prompt)

    clean_response = re.sub(r'```json\s*', '', response)
    clean_response = re.sub(r'```\s*', '', clean_response)

    try:
        beats = json.loads(clean_response.strip())
    except json.JSONDecodeError as e:
        print(f"Failed to parse beats for pages {start_page}-{end_page}: {e}")
        return []

    if not isinstance(beats, list):
        print(
            f"Unexpected beats shape for pages {start_page}-{end_page}: "
            f"expected list, got {type(beats).__name__}"
        )
        return []

    return beats

def save_candidate_beats(source_doc_id: str, session_id: str, candidates: list[dict]) -> int:
    
    if not candidates:
        return 0
 
    db = next(get_db())
    saved = 0
 
    try:
        for c in candidates:
            beat = StoryBeat(
                session_id=session_id,
                source_document_id=source_doc_id,
                beat_type=c.get("beat_type"),
                description=c.get("description"),
                starting_page=c.get("start_page"),
                ending_page=c.get("end_page"),
                beat_order=c.get("order"),
                requires=json.dumps(c.get("requires", [])),
                introduces=json.dumps(c.get("introduces", [])),
                key_dialogues=json.dumps(c.get("key_dialogues", [])),
            )
            db.add(beat)
            saved += 1
 
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
 
    return saved
