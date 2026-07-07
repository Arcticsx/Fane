from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Edge:
    source: int
    target: int
    kind: str  # "causal" | "structural" | "spine"

def build_beat_graph(beats: list[dict]) -> list[Edge]:

    n = len(beats)
    edges: list[Edge] = []
    parent: dict[int, int] = {}          # scene_id -> single parent id
    parent_kind: dict[int, str] = {}     # scene_id -> "causal" | "structural"

    # tag -> id of beat that introduced it (tags are globally unique, so this is 1:1)
    tag_producer: dict[str, int] = {}

    def prev_mandatory(pos: int) -> int | None:
        for j in range(pos - 1, -1, -1):
            if beats[j]["classification"] == "mandatory":
                return j
        return None

    def next_mandatory(pos: int) -> int | None:
        for j in range(pos + 1, n):
            if beats[j]["classification"] == "mandatory":
                return j
        return None

    # --- 1. Spine: mandatory beats in sequence ---
    mandatory_ids = [i for i, b in enumerate(beats) if b["classification"] == "mandatory"]
    for a, b in zip(mandatory_ids, mandatory_ids[1:]):
        edges.append(Edge(a, b, "spine"))

    # --- 2. Assign a single parent to each scene beat ---
    for pos, beat in enumerate(beats):
        if beat["classification"] == "scene":
            producers = [
                tag_producer[tag] for tag in beat.get("requires", []) if tag in tag_producer
            ]
            if producers:
                chosen = max(producers)  # most recent producer = most immediate causal link
                parent[pos] = chosen
                parent_kind[pos] = "causal"
            else:
                owner = prev_mandatory(pos)
                if owner is not None:
                    parent[pos] = owner
                    parent_kind[pos] = "structural"
                # if no preceding mandatory beat exists (beat is before the first
                # mandatory beat), it's simply unparented — flag this upstream if it matters.

        # register tags this beat introduces (after computing its own parent,
        # since a beat can't depend on something it itself introduces)
        for tag in beat.get("introduces", []):
            tag_producer[tag] = pos

    for scene_id, p in parent.items():
        edges.append(Edge(p, scene_id, parent_kind[scene_id]))

    # --- 3. Leaf-closure: every scene beat with no children must reach the next mandatory beat ---
    has_children = defaultdict(bool)
    for scene_id, p in parent.items():
        has_children[p] = True  # mark the parent as "has at least one child"

    for pos, beat in enumerate(beats):
        if beat["classification"] == "scene" and not has_children[pos]:
            target = next_mandatory(pos)
            if target is not None:
                edges.append(Edge(pos, target, "structural"))

    edge_json = [
        {
            "source": e.source,
            "target": e.target,
            "kind": e.kind
        }
        for e in edges
    ]
    
    return edge_json