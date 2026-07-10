import json
from .extraction import (
    cluster_candidates,
    reduce_cluster,
    merge_clusters,
    global_polish,
    replace_candidates_with_final_beats,
)


def run_reduce_phase(db, session_id, candidate_beats, source_doc_id):
    try:
        clusters = cluster_candidates(candidate_beats)
        reduced_clusters = split_and_reduce(
            clusters,
            reduce_cluster,
            token_budget=4000,
            chars_per_token=4,
            format_fn=json.dumps,
        )

        merged_beats = merge_clusters(reduced_clusters)
        final_beats = global_polish(merged_beats)

        replace_candidates_with_final_beats(db, session_id, source_doc_id, final_beats)

        return final_beats
    except Exception as e:
        import sys
        print(f"[run_reduce_phase] Error reducing beats for session {session_id}: {e}", file=sys.stderr)
        raise


def split_and_reduce(clusters, reduce_cluster, token_budget=4000, chars_per_token=4, format_fn=json.dumps):
    char_budget = token_budget * chars_per_token
    reduced_clusters = []

    for cluster in clusters:
        current_split = []
        current_len = 0

        for candidate in cluster:
            candidate_len = len(format_fn(candidate))

            # if adding this candidate would blow the budget, flush current split first
            if current_split and current_len + candidate_len > char_budget:
                reduced_clusters.append(reduce_cluster(current_split))
                current_split = []
                current_len = 0

            current_split.append(candidate)
            current_len += candidate_len

        # flush whatever's left in this cluster
        if current_split:
            reduced_clusters.append(reduce_cluster(current_split))

    return reduced_clusters
