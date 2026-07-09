from .extraction import (
    cluster_candidates,
    reduce_cluster,
    merge_clusters,
    global_polish,
    replace_candidates_with_final_beats,
)


def run_reduce_phase(db, session_id, candidate_beats):
    try:
        clusters = cluster_candidates(candidate_beats)
        reduced_clusters = reduce_cluster(clusters)
        merged_beats = merge_clusters(reduced_clusters)
        final_beats = global_polish(merged_beats)

        replace_candidates_with_final_beats(db, session_id, final_beats)

        return final_beats
    except Exception as e:
        import sys
        print(f"[run_reduce_phase] Error reducing beats for session {session_id}: {e}", file=sys.stderr)
        raise
