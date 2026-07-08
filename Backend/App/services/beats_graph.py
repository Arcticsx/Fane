from .graph import build_beat_graph, persist_beat_graph


def run_graph_phase(db, session_id, final_beats):
    graph_edges = build_beat_graph(final_beats)
    persist_beat_graph(db, session_id, graph_edges)
    return graph_edges
