---
date: 2026-03-08
patterns: [pipeline, multi-signal validation, semantic embeddings, quality gate]
project: Connections
---

# Multi-Signal Validation Pipeline

## Problem

AI-generated Connections puzzles can fail in very different ways:
- Words in a group are semantically unrelated (random noise)
- Two groups are so similar players can't distinguish them
- A word fits naturally in multiple groups (unintentional ambiguity)
- The puzzle is trivially solvable (too easy)

No single metric catches all of these. A simple coherence threshold misses the "trivially easy" failure; ARI alone misses random noise within a group.

## Why Multi-Signal Fits

The validator combines four orthogonal signals — each catches a distinct failure mode:

| Signal | Failure caught |
|---|---|
| Within-group coherence | Random / incoherent groups |
| Between-group separation | Groups too similar to distinguish |
| Bridge word ratio | Ambiguous word placement |
| Clustering ARI | Puzzle trivially solved by embedding alone |

The key insight: Connections puzzles have two dimensions of "hard" — *semantic obscurity* (words are related but subtly) and *non-semantic trickery* (wordplay, fill-in-the-blank). Cosine similarity only captures the first. ARI and bridge words add orthogonal signals.

## Relevant Code Pattern

```python
# Within-group coherence — flags if embedding similarity doesn't match
# expected range for the difficulty tier (yellow/green/blue/purple)
def _avg_pairwise_cosine(embeddings: np.ndarray) -> float:
    sims = [
        _cosine_sim(embeddings[i], embeddings[j])
        for i, j in itertools.combinations(range(len(embeddings)), 2)
    ]
    return float(np.mean(sims))

# Bridge word: cross-group sim > 80% of own-group sim → ambiguous placement
own_sim = _cosine_sim(emb, g["centroid"])
if max_cross_sim > BRIDGE_WORD_FRACTION * own_sim:
    bridge_words.append({...})

# ARI: k-means cluster recovery measures if puzzle is trivially solvable
ari = adjusted_rand_score(true_labels, kmeans.fit_predict(all_embeddings))
```

## What Would Break With a Different Structure

If we used a single threshold (e.g., "reject if coherence < 0.1"), we'd miss:
- Wordplay groups (legitimately low coherence, but valid puzzles)
- Groups that are internally coherent but identical to another group
- Puzzles where every group passes individually but the puzzle is trivially easy overall

The multi-signal approach lets wordplay groups pass coherence checks while still catching structural failures — by flagging "embedding-divergent, manual review recommended" rather than auto-failing.
