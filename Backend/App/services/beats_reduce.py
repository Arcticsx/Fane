from .extraction import (
    cluster_candidates,
    reduce_cluster,
    merge_clusters,
    global_polish,
    replace_candidates_with_final_beats,
)
import sys
import json
import re
from typing import List, Dict
from ..config import _dbg


def run_reduce_phase(db, session_id, candidate_beats, source_doc_id):
    try:
        _dbg(f"run_reduce_phase: session={session_id} doc={source_doc_id} candidate_beats={len(candidate_beats)}")

        clusters = cluster_candidates(candidate_beats)
        _dbg(f"cluster_candidates -> {len(clusters)} clusters, sizes={[len(c) for c in clusters]}")

        reduced_clusters = split_and_reduce(
            clusters,
            reduce_cluster,
            token_budget=4000,
            chars_per_token=4,
            format_fn=json.dumps,
        )
        _dbg(f"split_and_reduce -> {len(reduced_clusters)} reduced sub-clusters, "
             f"sizes={[len(rc) for rc in reduced_clusters]}")

        merged_beats = merge_clusters(reduced_clusters)
        _dbg(f"merge_clusters -> {len(merged_beats)} final merged beats")
        
        for i, beat in enumerate(merged_beats):
            beat["order"] = i

        merged_beats.sort(key=lambda b: b["order"])

        
        replace_candidates_with_final_beats(db, session_id, source_doc_id, merged_beats)
        _dbg(f"persisted {len(merged_beats)} final beats for session={session_id} doc={source_doc_id}")
        
        

        return merged_beats

    except Exception as e:
        print(f"[run_reduce_phase] Error reducing beats for session {session_id}: {e}", file=sys.stderr)
        raise
    
def split_and_reduce(clusters, reduce_cluster, token_budget=4000, chars_per_token=4, format_fn=json.dumps):
    char_budget = token_budget * chars_per_token
    _dbg(f"split_and_reduce: token_budget={token_budget} chars_per_token={chars_per_token} "
         f"-> char_budget={char_budget}, num_clusters={len(clusters)}")

    reduced_clusters = []

    for cluster_idx, cluster in enumerate(clusters):
        _dbg(f"  cluster[{cluster_idx}]: {len(cluster)} candidates total")
        current_split = []
        current_len = 0
        split_idx = 0

        for candidate in cluster:
            candidate_len = len(format_fn(candidate))

            # if adding this candidate would blow the budget, flush current split first
            if current_split and current_len + candidate_len > char_budget:
                _dbg(f"    cluster[{cluster_idx}] split[{split_idx}]: flushing {len(current_split)} "
                     f"candidates, current_len={current_len} (would exceed with +{candidate_len})")
                reduced_clusters.append(reduce_cluster(current_split))
                split_idx += 1
                current_split = []
                current_len = 0

            current_split.append(candidate)
            current_len += candidate_len

        # flush whatever's left in this cluster
        if current_split:
            _dbg(f"    cluster[{cluster_idx}] split[{split_idx}]: final flush, {len(current_split)} "
                 f"candidates, current_len={current_len}")
            reduced_clusters.append(reduce_cluster(current_split))

    _dbg(f"split_and_reduce done: produced {len(reduced_clusters)} sub-clusters total")
    return reduced_clusters
