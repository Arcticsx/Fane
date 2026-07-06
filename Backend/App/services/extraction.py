try:
    from .vectorstore import query_chroma_by_page_range
except ImportError:
    from vectorstore import query_chroma_by_page_range

try:
    from ..response import get_response
except ImportError:
    from response import get_response

import json
import re
from ..database import get_db
from ..models.rpg_sessions import StoryBeat
from typing import List, Dict, Any

SYSTEM_PROMPT = '''
You are a Narrative Architect. Extract ALL story beats from the given novel text, covering pages {start_page}-{end_page}.

If the text isn't part of the story (Acknowledgements, Author's Note, Editor's Note, Table of Contents, etc.), skip it and return an empty list.

## What is a story beat?

Any narrative unit that advances the plot, develops a character, builds the world, or provides meaningful interaction with the environment/NPCs. Extract every beat — don't cap the count — and classify each:

- **mandatory**: an irreversible event the main plot requires. Skipping it breaks later events. E.g. "The hero accepts the quest."
- **scene**: optional but meaningful flavor — conversation, exploration, atmosphere. Can be skipped without breaking the plot. E.g. "The hero chats with the innkeeper about the weather."

Rule of thumb: if skipping it makes a later event illogical, it's mandatory; if it only adds flavor, it's a scene.

## Beat types (pick one per beat)

- `decision_point` — meaningful choice affecting plot ("Will you accept the quest?")
- `transition` — travel, time passing, scene change ("You ride three days to the mountains.")
- `dialogue` — conversation conveying info or advancing relationships
- `combat` — fight, duel, physical confrontation
- `revelation` — discovery of crucial info, object, or truth
- `exploration` — investigating a location, object, or situation
- `reaction` — world/NPCs react to prior player action, no player input
- `flashback` — fixed memory sequence, player cannot change it
- `dream_vision` — fixed dream, prophecy, or hallucination

## Output format

Return a JSON list, beats in the order they occur:

```json
[
  {
    "classification": "mandatory",
    "beat_type": "decision_point",
    "description": "One-sentence, immutable summary.",
    "start_page": 12,
    "end_page": 14,
    "requires": ["asset1"],
    "introduces": ["asset2"],
    "key_dialogues": ["Verbatim quote", "..."]
  }
]
```

Field notes:
- `description`: immutable — must never change during gameplay.
- `start_page`/`end_page`: must stay within {start_page}-{end_page}; ranges must not overlap between beats. Use the inline "[page N]" markers in the text to determine these.
- `requires`: tags that must already exist from earlier beats, anywhere in the story so far. `[]` if none.
- `introduces`: new tags this beat creates (knowledge, items, relationships, state changes). `[]` if none.
- `key_dialogues`: up to 5 verbatim quotes critical to the beat. `[]` if none.

## Example

Input (pages 10-15): "The elder handed the map to the hero. 'You must take this,' he said. 'The Shadow Dragon grows stronger.' The hero hesitated, then nodded. They packed their bags and left the village at dawn. On the road, a stranger approached and warned them of the dark forest."

Output:
```json
[
  {
    "classification": "mandatory",
    "beat_type": "decision_point",
    "description": "The hero decides whether to accept the elder's quest and take the map.",
    "start_page": 10,
    "end_page": 11,
    "requires": [],
    "introduces": ["quest_accepted"],
    "key_dialogues": ["You must take this.", "The Shadow Dragon grows stronger."]
  },
  {
    "classification": "scene",
    "beat_type": "transition",
    "description": "The hero packs supplies and leaves the village.",
    "start_page": 12,
    "end_page": 12,
    "requires": ["quest_accepted"],
    "introduces": ["left_village"],
    "key_dialogues": []
  },
  {
    "classification": "scene",
    "beat_type": "dialogue",
    "description": "A stranger warns the hero about the dangers of the dark forest.",
    "start_page": 13,
    "end_page": 15,
    "requires": ["left_village"],
    "introduces": ["forest_warning"],
    "key_dialogues": ["Beware the dark forest, traveler."]
  }
]
```

## Now extract beats from the following text:

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



def sort_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    
    def get_sort_key(beat: Dict[str, Any]) -> tuple[int, int]:
        
        start = beat.get('start_page', 0) or 0
        end = beat.get('end_page', 0) or 0
        
        
        try:
            start = int(start)
            end = int(end)
        except (ValueError, TypeError):
            start = 0
            end = 0
            
        return (start, end)
    
    return sorted(candidates, key=get_sort_key)

def save_candidate_beats(source_doc_id: str, session_id: str, candidates: list[dict]) -> int:
    
    if not candidates:
        return 0
 
    db = next(get_db())
    saved = 0
 
    try:
        for order, c in enumerate(candidates):
            beat = StoryBeat(
                session_id=session_id,
                source_document_id=source_doc_id,
                beat_type=c.get("beat_type"),
                description=c.get("description"),
                status = "candidate",
                starting_page=c.get("start_page"),
                ending_page=c.get("end_page"),
                beat_order = order,
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

def clean_candidate_beats():
    
    
    
    pass