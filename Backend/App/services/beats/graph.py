from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import sys
import sqlalchemy
from sqlalchemy.orm import Session
from typing import List, Dict

from ...models.rpg_sessions import GraphEdge, StoryBeat


@dataclass
class Edge:
    source: int
    target: int
    kind: str  # "causal" | "structural" | "spine"


def build_beat_graph(beats: list[dict]) -> list[dict]:
    """
    beats: each dict has at least:
        id, beat_type ("mandatory" | "scene"), start_page (and optionally end_page)
    Assumes `beats` is indexable by position (pos == index into this list);
    edges reference these positions as source/target, matching the original convention.
    """
    n = len(beats)
    edges: list[Edge] = []

    # --- 1. Mandatory spine, sorted by start_page ---
    mandatory_positions = [i for i, b in enumerate(beats) if b["classification"] == "mandatory"]
    mandatory_positions.sort(key=lambda i: beats[i]["start_page"])

    for a, b in zip(mandatory_positions, mandatory_positions[1:]):
        edges.append(Edge(a, b, "sequential"))

    # sorted start_pages for bisecting, kept parallel to mandatory_positions
    mandatory_start_pages = [beats[i]["start_page"] for i in mandatory_positions]

    def nearest_preceding_mandatory(start_page: int) -> int | None:
        """Largest-start_page mandatory beat with start_page <= given start_page.
        Falls back to the first mandatory beat if none qualifies."""
        if not mandatory_positions:
            return None
        i = bisect_right(mandatory_start_pages, start_page) - 1
        if i >= 0:
            return mandatory_positions[i]
        return mandatory_positions[0]  # scene occurs before any mandatory beat

    # --- 2. Attach each scene to its parent mandatory beat ---
    scene_positions = [i for i, b in enumerate(beats) if b["classification"] == "scene"]

    groups: dict[int, list[int]] = {}  # parent mandatory pos -> [scene positions]
    for pos in scene_positions:
        parent = nearest_preceding_mandatory(beats[pos]["start_page"])
        if parent is None:
            # no mandatory beats at all — nothing to attach to
            continue
        edges.append(Edge(parent, pos, "attachment"))
        edges.append(Edge(pos, parent, "return"))
        groups.setdefault(parent, []).append(pos)

    # --- 3. Scene-to-scene sequencing within each group ---
    for parent, scenes in groups.items():
        scenes.sort(key=lambda i: beats[i]["start_page"])
        for a, b in zip(scenes, scenes[1:]):
            edges.append(Edge(a, b, "sequential"))

    output = [{"source": e.source, "target": e.target, "kind": e.kind} for e in edges]
    print(f"[graph.build_beat_graph] built {len(output)} edges for {n} beats", file=sys.stderr)
    print(f"[graph.build_beat_graph] edges: {output}", file=sys.stderr)
    return output

def persist_beat_graph(
    db: Session,
    session_id: str,
    edges: List[Dict],
) -> int:
    """
    Persist graph edges produced by build_beat_graph() into the graph_edges table.
    Uses the caller's session — does not open its own.

    Queries StoryBeat rows for session_id, ordered by beat_order, to reconstruct
    the same positional indexing that build_beat_graph used when it produced `edges`
    (edge["source"]/edge["target"] are positions into that ordered list).
    """
    beats = (
        db.query(StoryBeat)
        .filter(StoryBeat.session_id == session_id)
        .order_by(StoryBeat.beat_order)
        .all()
    )
    n = len(beats)
    beat_ids = [b.id for b in beats]

    try:
        deleted = db.query(GraphEdge).filter(
            GraphEdge.session_id == session_id,
            GraphEdge.source_beat_id.in_(beat_ids),
        ).delete(synchronize_session=False)
        print(f"Deleted {deleted} existing graph edges for session {session_id}")

        inserted = 0
        for edge in edges:
            src, tgt = edge["source"], edge["target"]
            if not (0 <= src < n and 0 <= tgt < n):
                print(f"Skipping edge with out-of-range index: {edge}")
                continue

            db.add(GraphEdge(
                session_id=session_id,
                source_beat_id=beat_ids[src],
                target_beat_id=beat_ids[tgt],
                edge_type=edge["kind"],
                condition_tag=edge.get("condition_tag"),
            ))
            inserted += 1

        db.commit()
        print(f"Inserted {inserted} graph edges")
        return inserted

    except Exception as e:
        db.rollback()
        print(f"[graph.persist_beat_graph] Failed to persist beat graph for session {session_id}: {e}", file=sys.stderr)
        raise RuntimeError(f"Failed to persist beat graph for session {session_id}: {e}") from e