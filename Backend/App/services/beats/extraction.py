from ..documents.vectorstore import query_chroma_by_page_range
from ..utility.response import get_response

import json
import re
import time
import sys
from ..utility.getdb import get_db
from ...models.rpg_sessions import StoryBeat
from typing import List, Dict, Any, Set
from difflib import get_close_matches
from ..utility.config import _dbg

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
    "description": "2-4 sentence immutable summary. Cover: what happens, who does it and why, what changes (physically, emotionally, or relationally) as a result, and any concrete detail (place, object, number, name) that makes the beat useful as game-state context later.",
    "start_page": 12,
    "end_page": 14,
    "requires": ["spoke with the village elder"],
    "introduces": ["received the mystic amulet"],
    "characters": ["Character Name", "..."],
    "key_dialogues": ["Verbatim quote", "..."]
}}
]
```
Rules:
- description: immutable, never changes during gameplay. Write it so someone who has NOT read the book understands the beat on its own — no pronouns standing in for names, no vague references like "the artifact" without saying which one. Favor specificity over brevity: name the location, state the stakes, name what was said or decided and by whom, and note the consequence or emotional shift if there is one.
- start_page/end_page: must stay within {start_page}-{end_page}, no overlapping ranges. Use "[page N]" markers in the text.
- requires: short natural-language phrases describing prior events, knowledge, items, or relationships this beat depends on (from anywhere earlier in the story). [] if none. Rules for phrasing:
    - 3-8 words per phrase, simple past tense, no pronouns — name characters/objects explicitly (e.g. "learned about the hidden passage", not "learned about it").
    - Phrase each requirement the same way you would phrase the matching fact if it had been introduced — these get matched by semantic similarity at runtime, so consistent, literal phrasing matters more than variety.
    - Describe the underlying fact/event, not the beat name (e.g. "received the mystic amulet", not "amulet beat").
- introduces: short natural-language phrases describing new facts, events, items, or relationships established by this beat. [] if none. Rules for phrasing:
    - Same style as requires: 3-8 words, simple past tense, no pronouns, self-contained (readable with zero surrounding context).
    - Write these as the concrete, reusable fact the rest of the story would need to reference (e.g. "met the old hermit in the forest", "learned the innkeeper's secret", "received the mystic amulet from the hermit").
    - Do not include vague or purely emotional entries (e.g. "felt sad") unless that emotional state is itself a plot-relevant condition later beats depend on.
    - One phrase per discrete fact — don't bundle multiple facts into one string.
- characters: List EVERY character present or active in the beat, including the protagonist/POV character even if they are only referred to as "I," "he," "she," or by pronoun in the text. Do not omit the protagonist just because they are the narrator — if they act, speak, react, or are simply in the scene, include their name. Use the most complete form the text gives you (e.g. "Percy Jackson" not "he" or "the boy"). Include characters who are spoken about and directly participate via dialogue or action, but exclude characters who are merely mentioned in passing with no active role. [] if none.
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
        "characters": beat.get("characters", []),
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
    
    response = get_response(prompt, mode="chronicle_beats")
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
                    characters = json.dumps(c.get("characters", [])),
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
You will receive a list of candidate beats with inconsistent requires and introduces tags.
Your first task is to unify these tags into a single canonical vocabulary within this cluster.
For example, if one beat uses 'sword', another uses 'sword_of_light', you MUST replace them all with 'sword_of_light'.
Apply the same canonicalization to character names — if one beat uses 'Nyx' and another uses 'Nyx Shadowbane' or 'the assassin', unify them under a single canonical name per character.
Then, deduplicate and merge overlapping/duplicate beats within this cluster.
Output the final definitive beats for this section.

Candidate beats (JSON):
{json.dumps(cluster, indent=2)}

Output ONLY a JSON list of the cleaned beats, each with:
- start_page, end_page
- description
- beat_type
- requires (list of canonical tags)
- introduces (list of canonical tags)
- characters (list of canonical character names present/active in this beat)
- key_dialogues (list)
- classification ("mandatory" or "scene")

Do NOT include 'order' – that will be assigned later.
"""
    prompt_chars = len(prompt)
    _dbg(f"reduce_cluster: input={len(cluster)} candidates, prompt_len={prompt_chars} chars "
         f"(~{prompt_chars // 4} tokens)")

    try:
        response = get_response(prompt, mode="chronicle_beats")
        _dbg(f"reduce_cluster: raw response_len={len(response)} chars, "
            f"head={response[:120]!r}")
    except Exception as e:
        print(f"[reduce_cluster] Error calling LLM for cluster reduction: {e}", file=sys.stderr)
        time.sleep(15)  # back off a bit before retrying
        response = get_response(prompt, mode="chronicle_beats")
    finally:
        time.sleep(3)  # cooldown between LLM calls

    # Clean markdown fences
    clean = re.sub(r'```json\s*', '', response)
    clean = re.sub(r'```\s*', '', clean)

    try:
        parsed = json.loads(clean.strip())
        _dbg(f"reduce_cluster: parsed OK, output={len(parsed)} beats "
             f"(input was {len(cluster)})")
        return parsed
    except json.JSONDecodeError as je:
        print(f"Cluster LLM failed, returning original cluster", file=sys.stderr)
        _dbg(f"reduce_cluster: JSONDecodeError={je}, cleaned_response_len={len(clean)}, "
             f"cleaned_tail={clean[-200:]!r}")
        # fallback: return the original cluster (better than losing data)
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
    Post-process all tags and characters across the entire beat list using fuzzy matching.
    This catches variations that the LLM might have missed.
    Uses get_close_matches with a cutoff of 0.85 (85% similarity).
    """
    # 1. Collect all unique tags from requires and introduces
    all_tags: Set[str] = set()
    for beat in beats:
        all_tags.update(beat.get("requires", []))
        all_tags.update(beat.get("introduces", []))
    all_tags = list(all_tags)

    # 1b. Collect all unique character names
    all_characters: Set[str] = set()
    for beat in beats:
        all_characters.update(beat.get("characters", []))
    all_characters = list(all_characters)

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

    # 2b. Build a canonical mapping for characters using fuzzy matching
    character_map: Dict[str, str] = {}
    processed_characters = set()
    for name in sorted(all_characters):  # Sort for deterministic order
        if name in processed_characters:
            continue
        matches = get_close_matches(name, all_characters, n=10, cutoff=0.85)
        if len(matches) > 1:
            # Prefer the longest/most complete name as canonical (opposite of tags)
            # "Percy Jackson" is better than "Percy"
            if len(matches) > 2:
                name_counts = {}
                for m in matches:
                    count = 0
                    for beat in beats:
                        count += beat.get("characters", []).count(m)
                    name_counts[m] = count
                # Tie-break popularity against length: prefer longer name unless
                # a shorter variant is overwhelmingly more common
                canonical = max(matches, key=lambda m: (name_counts[m], len(m)))
            else:
                canonical = max(matches, key=len)
        else:
            canonical = name
        for m in matches:
            character_map[m] = canonical
            processed_characters.add(m)

    # 3. Apply the mapping to all beats
    for beat in beats:
        # Fix requires
        if beat.get("requires"):
            beat["requires"] = [tag_map.get(t, t) for t in beat["requires"]]
        # Fix introduces
        if beat.get("introduces"):
            beat["introduces"] = [tag_map.get(t, t) for t in beat["introduces"]]
        # Fix characters
        if beat.get("characters"):
            beat["characters"] = [character_map.get(c, c) for c in beat["characters"]]
        # Remove duplicates within each list
        if beat.get("requires"):
            beat["requires"] = list(dict.fromkeys(beat["requires"]))  # Preserves order
        if beat.get("introduces"):
            beat["introduces"] = list(dict.fromkeys(beat["introduces"]))
        if beat.get("characters"):
            beat["characters"] = list(dict.fromkeys(beat["characters"]))
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
                characters = json.dumps(beat_data.get("characters")),
                description=description,
                starting_page=_coerce_int(beat_data.get("start_page")),
                ending_page=_coerce_int(beat_data.get("end_page")),
                requires=json.dumps(beat_data.get("requires", [])),
                introduces=json.dumps(beat_data.get("introduces", [])),
                key_dialogues=json.dumps(beat_data.get("key_dialogues", [])),
                retry_count=0,
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