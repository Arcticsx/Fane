from .extraction import (
    cluster_candidates,
    reduce_cluster,
    merge_clusters,
    global_polish,
)


def run_reduce_phase(candidate_beats):
    clusters = cluster_candidates(candidate_beats)
    reduced_clusters = [reduce_cluster(cluster) for cluster in clusters]
    merged_beats = merge_clusters(reduced_clusters)
    return global_polish(merged_beats)
