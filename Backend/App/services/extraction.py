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
import sys
from ..database import get_db
from ..models.rpg_sessions import StoryBeat
from typing import List, Dict, Any, Set
from difflib import get_close_matches

SYSTEM_PROMPT = '''
You are a Narrative Architect. Extract ALL story beats from the novel text below, covering pages {start_page}-{end_page}.
Skip non-story text (Acknowledgements, Author's Note, Table of Contents, etc.) and return an empty list for it.

A beat is any unit that advances plot, develops character, builds world, or is a meaningful interaction. Extract every beat, don't cap the count.

classification:
- "mandatory": irreversible, plot-required. Skipping it breaks later events.
- "scene": optional flavor, skippable without breaking plot.

beat_type (pick one): decision_point, transition, dialogue, combat, revelation, exploration, reaction, flashback, dream_vision

Return ONLY a JSON list, no prose before or after. Each beat must use exactly these keys:
```json
[
{{
    "classification": "mandatory",
    "beat_type": "decision_point",
    "description": "Two-sentences, immutable summary.",
    "start_page": 12,
    "end_page": 14,
    "requires": ["asset1"],
    "introduces": ["asset2"],
    "key_dialogues": ["Verbatim quote", "..."]
}}
]
```

Rules:
- description: immutable, never changes during gameplay.
- start_page/end_page: must stay within {start_page}-{end_page}, no overlapping ranges. Use "[page N]" markers in the text.
- requires: tags needed from earlier beats (anywhere in story so far). [] if none.
- introduces: new tags this beat creates. [] if none.
- key_dialogues: up to 5 verbatim quotes. [] if none.

## Text to extract from:

{pages_text}
'''


def _parse_json_response(response):
    if isinstance(response, (list, dict)):
        return response

    if not isinstance(response, str):
        return None

    # Strip markdown fences if present
    text = re.sub(r'```json\s*', '', response)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()

    # Try parsing as-is first (covers clean responses with no surrounding prose)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to extracting the first JSON array or object from the text,
    # in case the model wrapped it in explanatory prose.
    match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

VALID_BEAT_TYPES = {
    "decision_point", "transition", "dialogue", "combat",
    "revelation", "exploration", "reaction", "flashback", "dream_vision",
}
VALID_CLASSIFICATIONS = {"mandatory", "scene"}

def _normalize_beat(beat: dict) -> dict | None:
    if not isinstance(beat, dict):
        return None
    if not beat.get("description"):
        return None

    beat_type = beat.get("beat_type")
    if beat_type not in VALID_BEAT_TYPES:
        beat_type = "reaction"  # safe fallback, or log and drop instead

    classification = beat.get("classification")
    if classification not in VALID_CLASSIFICATIONS:
        classification = "scene"

    return {
        "classification": classification,
        "beat_type": beat_type,
        "description": beat["description"],
        "start_page": beat.get("start_page"),
        "end_page": beat.get("end_page"),
        "requires": beat.get("requires", []),
        "introduces": beat.get("introduces", []),
        "key_dialogues": beat.get("key_dialogues", []),
    }


def _coerce_int(value):
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
    approx_tokens = len(prompt) // 4  # rough chars-to-tokens estimate
    print(f"[DEBUG] window {start_page}-{end_page}: ~{approx_tokens} tokens, {len(chunks)} chunks")
    
    response = get_response(prompt, mode="chronicle")
    print(response)
    beats = _parse_json_response(response)
    
    if beats is None or not isinstance(beats, list):
        print(f"Failed to parse beats for pages {start_page}-{end_page}: invalid JSON response")
        return []

    normalized = [_normalize_beat(b) for b in beats]
    normalized = [b for b in normalized if b is not None]
    return normalized



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
 
    saved = 0
    with get_db() as db:
        try:
            
            for order, c in enumerate(candidates):
                if not isinstance(c, dict):
                    continue

                beat = StoryBeat(
                    session_id=session_id,
                    source_document_id=source_doc_id,
                    beat_type=c.get("beat_type"),
                    description=c.get("description"),
                    status="candidate",
                    starting_page=_coerce_int(c.get("start_page")),
                    ending_page=_coerce_int(c.get("end_page")),
                    classification = c.get("classification"),
                    beat_order = order,
                    requires=json.dumps(c.get("requires", [])),
                    introduces=json.dumps(c.get("introduces", [])),
                    key_dialogues=json.dumps(c.get("key_dialogues", [])),
                )
                db.add(beat)
                saved += 1
    
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[extraction.save_candidate_beats] Failed to save candidate beats for {source_doc_id}: {e}", file=sys.stderr)
            raise
        finally:
            db.close()
 
    return saved

def cluster_candidates(candidates: List[Dict], cluster_size: int = 18, overlap: int = 5) -> List[List[Dict]]:
    
    # 1. Sort globally
    sorted_candidates = sort_candidates(candidates)  # uses (start_page, end_page, order)
    
    clusters = []
    i = 0
    n = len(sorted_candidates)
    while i < n:
        cluster = sorted_candidates[i : i + cluster_size]
        clusters.append(cluster)
        # Move i forward by cluster_size - overlap (so next cluster overlaps)
        i += cluster_size - overlap
        if i >= n:
            break
    return clusters

def reduce_cluster(cluster: List[Dict]) -> List[Dict]:

    prompt = f"""
You will receive a list of candidate beats (15–20) with inconsistent requires and introduces tags.
Your first task is to unify these tags into a single canonical vocabulary within this cluster.
For example, if one beat uses 'sword', another uses 'sword_of_light', you MUST replace them all with 'sword_of_light'.
Then, deduplicate and merge overlapping/duplicate beats within this cluster.
Output the final 10–12 definitive beats for this section.

Candidate beats (JSON):
{json.dumps(cluster, indent=2)}

Output ONLY a JSON list of the cleaned beats, each with:
- start_page, end_page
- description
- beat_type
- requires (list of canonical tags)
- introduces (list of canonical tags)
- key_dialogues (list)
- classification ("mandatory" or "scene")

Do NOT include 'order' – that will be assigned later.
"""
    response = get_response(prompt)
    # Clean markdown fences
    clean = re.sub(r'```json\s*', '', response)
    clean = re.sub(r'```\s*', '', clean)
    try:
        return json.loads(clean.strip())
    except json.JSONDecodeError:
        # fallback: return the original cluster (better than losing data)
        print("Cluster LLM failed, returning original cluster")
        return cluster
    
def merge_clusters(cleaned_clusters: List[List[Dict]]) -> List[Dict]:
    
    # 1. Flatten all clusters
    all_beats = []
    for cluster in cleaned_clusters:
        all_beats.extend(cluster)
    
    # 2. Sort again by (start_page, end_page, order)
    all_beats = sort_candidates(all_beats)
    
    # 3. Deduplicate using a sliding window
    merged = []
    for beat in all_beats:
        if not merged:
            merged.append(beat)
            continue
        last = merged[-1]
        # Check if this beat overlaps with the last kept beat
        if beat["start_page"] <= last["end_page"]:
            # Overlap: decide which to keep
            last_span = last["end_page"] - last["start_page"]
            beat_span = beat["end_page"] - beat["start_page"]
            if beat_span > last_span:
                merged[-1] = beat
            elif beat_span == last_span:
                if len(beat.get("key_dialogues", [])) > len(last.get("key_dialogues", [])):
                    merged[-1] = beat
        else:
            merged.append(beat)
    
    
    merged = _canonicalize_tags_globally(merged)
    
    return merged


def _canonicalize_tags_globally(beats: List[Dict]) -> List[Dict]:
    """
    Post-process all tags across the entire beat list using fuzzy matching.
    This catches variations that the LLM might have missed.
    
    Uses get_close_matches with a cutoff of 0.85 (85% similarity).
    """
    # 1. Collect all unique tags from requires and introduces
    all_tags: Set[str] = set()
    for beat in beats:
        all_tags.update(beat.get("requires", []))
        all_tags.update(beat.get("introduces", []))
    
    all_tags = list(all_tags)
    
    # 2. Build a canonical mapping using fuzzy matching
    tag_map: Dict[str, str] = {}
    processed = set()
    
    for tag in sorted(all_tags):  # Sort for deterministic order
        if tag in processed:
            continue
        # Find close matches (80%+ similarity)
        matches = get_close_matches(tag, all_tags, n=10, cutoff=0.85)
        if len(matches) > 1:
            # Choose the shortest/most generic one as canonical
            # Or pick the first one (alphabetically) for consistency
            canonical = min(matches, key=len)  # Shortest is usually most generic
            # But if there's a "sword_of_light" and "sword", "sword_of_light" is better
            # Let's pick the one that appears most frequently (popularity vote)
            if len(matches) > 2:
                # Count occurrences in the actual beats
                tag_counts = {}
                for m in matches:
                    count = 0
                    for beat in beats:
                        count += beat.get("requires", []).count(m)
                        count += beat.get("introduces", []).count(m)
                    tag_counts[m] = count
                canonical = max(tag_counts, key=tag_counts.get)
            else:
                canonical = matches[0]
        else:
            canonical = tag
        
        # Map all close matches to the canonical tag
        for m in matches:
            tag_map[m] = canonical
            processed.add(m)
    
    # 3. Apply the mapping to all beats
    for beat in beats:
        # Fix requires
        if beat.get("requires"):
            beat["requires"] = [tag_map.get(t, t) for t in beat["requires"]]
        # Fix introduces
        if beat.get("introduces"):
            beat["introduces"] = [tag_map.get(t, t) for t in beat["introduces"]]
        
        # Remove duplicates within each list
        if beat.get("requires"):
            beat["requires"] = list(dict.fromkeys(beat["requires"]))  # Preserves order
        if beat.get("introduces"):
            beat["introduces"] = list(dict.fromkeys(beat["introduces"]))
    
    return beats


def global_polish(merged_beats: List[Dict]) -> List[Dict]:
    """
    Renumber beats globally and fix cross-cluster dependency issues.
    """
    prompt = f"""
Here is a list of final, non-overlapping beats. Do NOT change descriptions, page ranges, or merge anything.
Your ONLY tasks are:
1. Renumber them sequentially (1 to N) based on start_page.
2. Review requires and introduces globally. If a beat uses a tag that isn't introduced earlier, correct it.
Output the full list with 'order' added.
Beats:
{json.dumps(merged_beats, indent=2)}
"""
    response = get_response(prompt)
    clean = re.sub(r'```json\s*', '', response)
    clean = re.sub(r'```\s*', '', clean).strip()

    try:
        result = json.loads(clean)
        if not isinstance(result, list) or len(result) != len(merged_beats):
            raise ValueError(
                f"Expected {len(merged_beats)} beats, got "
                f"{len(result) if isinstance(result, list) else type(result).__name__}"
            )
        return result
    except (json.JSONDecodeError, ValueError) as e:
        print(f"global_polish LLM output invalid ({e}), falling back to deterministic renumbering")
        ordered = sorted(merged_beats, key=lambda b: b["start_page"])
        for i, beat in enumerate(ordered, 1):
            beat["order"] = i
        return ordered


def replace_candidates_with_final_beats(
    db: Session,
    session_id: str,
    source_doc_id: str,
    final_beats: List[Dict]
) -> int:
    
    try:
        deleted = db.query(StoryBeat).filter(
            StoryBeat.session_id == session_id,
            StoryBeat.source_document_id == source_doc_id,
            StoryBeat.status == "candidate"
        ).delete(synchronize_session=False)
        print(f"Deleted {deleted} candidate beats for {source_doc_id}")

        inserted = 0
        skipped = 0
        for beat_data in final_beats:
            description = beat_data.get("description")
            if not description:
                skipped += 1
                continue

            db.add(StoryBeat(
                session_id=session_id,
                source_document_id=source_doc_id,
                status="pending",  # ready for gameplay
                beat_order=beat_data.get("order", 0),
                beat_type=beat_data.get("beat_type"),
                classification=beat_data.get("classification", "scene"),
                description=description,
                starting_page=_coerce_int(beat_data.get("start_page")),
                ending_page=_coerce_int(beat_data.get("end_page")),
                requires=json.dumps(beat_data.get("requires", [])),
                introduces=json.dumps(beat_data.get("introduces", [])),
                key_dialogues=json.dumps(beat_data.get("key_dialogues", [])),
                retry_count=0,
                importance=beat_data.get("importance", 1),
            ))
            inserted += 1

        db.commit()
        if skipped:
            print(f"Skipped {skipped} beat(s) missing 'description'")
        print(f"Inserted {inserted} final beats with status='pending'")
        return inserted

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Failed to replace candidates for {source_doc_id}: {e}") from e