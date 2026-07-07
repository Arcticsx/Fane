from bisect import bisect_left, bisect_right
from dataclasses import dataclass


@dataclass
class Edge:
    source: int
    target: int
    kind: str  # "causal" | "structural" | "spine"


def build_beat_graph(beats: list[dict]) -> list[dict]:
    n = len(beats)
    edges: list[Edge] = []
    parent: dict[int, int] = {}          # scene_id -> single parent id
    parent_kind: dict[int, str] = {}     # scene_id -> "causal" | "structural"
    tag_producer: dict[str, int] = {}    # tag -> id of beat that introduced it (1:1, tags globally unique)

    mandatory_ids = [i for i, b in enumerate(beats) if b["classification"] == "mandatory"]

    def prev_mandatory(pos: int) -> int | None:
        i = bisect_left(mandatory_ids, pos) - 1
        return mandatory_ids[i] if i >= 0 else None

    def next_mandatory(pos: int) -> int | None:
        i = bisect_right(mandatory_ids, pos)
        return mandatory_ids[i] if i < len(mandatory_ids) else None

    # --- 1. Spine: mandatory beats in sequence ---
    for a, b in zip(mandatory_ids, mandatory_ids[1:]):
        edges.append(Edge(a, b, "spine"))

    # --- 2. Assign a single parent to each scene beat ---
    for pos, beat in enumerate(beats):
        if beat["classification"] == "scene":
            producers = [
                tag_producer[tag] for tag in beat.get("requires", []) if tag in tag_producer
            ]
            if producers:
                parent[pos] = max(producers)  # most recent producer = most immediate causal link
                parent_kind[pos] = "causal"
            else:
                owner = prev_mandatory(pos)
                if owner is not None:
                    parent[pos] = owner
                    parent_kind[pos] = "structural"
                # else: no preceding mandatory beat — unparented, flag upstream if it matters.

        # register tags this beat introduces (after computing its own parent,
        # since a beat can't depend on something it itself introduces)
        for tag in beat.get("introduces", []):
            tag_producer[tag] = pos

    for scene_id, p in parent.items():
        edges.append(Edge(p, scene_id, parent_kind[scene_id]))

    # --- 3. Leaf-closure: every scene beat with no children must reach the next mandatory beat ---
    has_children: set[int] = set(parent.values())
    for pos, beat in enumerate(beats):
        if beat["classification"] == "scene" and pos not in has_children:
            target = next_mandatory(pos)
            if target is not None:
                edges.append(Edge(pos, target, "structural"))

    return [{"source": e.source, "target": e.target, "kind": e.kind} for e in edges]