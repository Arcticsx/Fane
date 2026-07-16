from difflib import get_close_matches
import sys
from typing import List, Dict, Set


def merge_entity_clusters(cleaned_clusters: List[List[Dict]]) -> List[Dict]:
    """
    Merge entity-extraction results from multiple page-window chunks into a
    single deduplicated entity list.
    Each input dict looks like: {"name": str, "type": str, "pages": List[int]}
    """
    # 1. Flatten all clusters
    all_entities = []
    for cluster_index, cluster in enumerate(cleaned_clusters):
        if not isinstance(cluster, list):
            print(
                f"[entities_reduce.merge_entity_clusters] Skipping non-list cluster at index {cluster_index}: {cluster!r}",
                file=sys.stderr,
            )
            continue
        for entity_index, entity in enumerate(cluster):
            if not isinstance(entity, dict):
                print(
                    f"[entities_reduce.merge_entity_clusters] Skipping invalid entity at cluster {cluster_index}, index {entity_index}: {entity!r}",
                    file=sys.stderr,
                )
                continue
            if "type" not in entity or "name" not in entity or "pages" not in entity:
                print(
                    f"[entities_reduce.merge_entity_clusters] Skipping incomplete entity at cluster {cluster_index}, index {entity_index}: {entity!r}",
                    file=sys.stderr,
                )
                continue
            all_entities.append(entity)

    # 2. Exact-match merge: same (type, name) -> union pages
    exact_merged: Dict[tuple, Dict] = {}
    for ent in all_entities:
        if not isinstance(ent.get("pages", []), list):
            print(
                f"[entities_reduce.merge_entity_clusters] Skipping entity with invalid pages: {ent!r}",
                file=sys.stderr,
            )
            continue
        key = (ent["type"], ent["name"])
        if key not in exact_merged:
            exact_merged[key] = {
                "name": ent["name"],
                "type": ent["type"],
                "pages": set(ent.get("pages", [])),
            }
        else:
            exact_merged[key]["pages"].update(ent.get("pages", []))

    merged = list(exact_merged.values())

    # 3. Fuzzy-match canonicalization across near-duplicate names, scoped by type
    merged = _canonicalize_entities_globally(merged)

    # 4. Final cleanup: sort pages, sort entity list for determinism
    for ent in merged:
        ent["pages"] = sorted(ent["pages"])
    merged.sort(key=lambda e: (e["type"], e["name"]))

    return merged


def _names_match(a: str, b: str) -> bool:
    """
    True if a and b are likely the same entity.

    Handles two cases:
    1. Containment: one name's tokens are a subset of the other's
       (e.g. "Grover" -> "Grover Underwood", "Annabeth" -> "Annabeth Chase").
       difflib's ratio-based cutoff misses these because the length delta
       between a short name and a full name tanks the similarity score even
       when one is a clean substring of the other.
    2. Fuzzy ratio: catches typos / minor spelling variants of otherwise
       similar-length names.

    NOTE: this does NOT catch narrative aliases (e.g. "Mr. Brunner" ==
    "Chiron") since there's no string-level signal connecting them — that
    requires semantic/context-aware resolution, not string matching.
    """
    a_norm, b_norm = a.lower(), b.lower()
    a_tokens, b_tokens = set(a_norm.split()), set(b_norm.split())

    if a_tokens.issubset(b_tokens) or b_tokens.issubset(a_tokens):
        return True

    return get_close_matches(a, [b], n=1, cutoff=0.85) != []


def _split_compound_name(name: str) -> List[str]:
    """
    Split a compound alias name like 'Mr. Brunner/Chiron' into its parts.
    The LLM emits these when it's hedging between an earlier name and a
    later-revealed one for the same entity (e.g. mentor -> true identity).
    Returns [name] unchanged if there's no '/' to split on.
    """
    if "/" not in name:
        return [name]
    return [p.strip() for p in name.split("/") if p.strip()]


def _canonicalize_entities_globally(entities: List[Dict]) -> List[Dict]:
    by_type: Dict[str, List[Dict]] = {}
    for ent in entities:
        if not isinstance(ent, dict):
            print(
                f"[entities_reduce._canonicalize_entities_globally] Skipping non-dict entity: {ent!r}",
                file=sys.stderr,
            )
            continue
        if "type" not in ent or "name" not in ent or "pages" not in ent:
            print(
                f"[entities_reduce._canonicalize_entities_globally] Skipping incomplete entity: {ent!r}",
                file=sys.stderr,
            )
            continue
        by_type.setdefault(ent["type"], []).append(ent)

    result: List[Dict] = []

    for etype, ents in by_type.items():
        names = [e["name"] for e in ents]
        name_to_entity = {e["name"]: e for e in ents}

        parent = {n: n for n in names}

        def find(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]  # path compression
                n = parent[n]
            return n

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Build edges between any names that are close enough (containment
        # or fuzzy ratio), then union them
        for name in names:
            for other in names:
                if other != name and _names_match(name, other):
                    union(name, other)

        # Bridge compound alias names ("Mr. Brunner/Chiron") to the standalone
        # entities they hedge between ("Mr. Brunner", "Chiron"). This lets us
        # collapse a name change revealed mid-book without any LLM call:
        # earlier chunks tag the old name, transition chunks emit "Old/New",
        # later chunks tag the new name — the compound entry is the bridge.
        for name in names:
            parts = _split_compound_name(name)
            if len(parts) < 2:
                continue
            for other in names:
                if other == name:
                    continue
                if any(_names_match(part, other) for part in parts):
                    union(name, other)

        # Group names by their root
        groups: Dict[str, List[str]] = {}
        for n in names:
            root = find(n)
            groups.setdefault(root, []).append(n)

        # Pick canonical = longest name (tie-break by page count) within each group
        for root, group_names in groups.items():
            canonical = max(
                group_names,
                key=lambda m: (len(m), len(name_to_entity[m]["pages"])),
            )
            merged_pages = set()
            for n in group_names:
                merged_pages.update(name_to_entity[n]["pages"])
            result.append({
                "name": canonical,
                "type": etype,
                "pages": merged_pages,
            })

    return result