---
date: 2026-03-08
patterns: [cosine similarity, centroid, geometric intuition]
project: Connections
---

# Cosine Similarity and Centroids — Geometry as a Quality Signal

## The Core Idea

Once words are represented as vectors (embeddings), group quality becomes a
geometry problem. Two patterns show up repeatedly in the validator:

### 1. Pairwise cosine similarity → group coherence

Average cosine similarity across all pairs in a group tells you if the words
are semantically clustered together.

```python
# All 6 pairs from 4 words: (0,1), (0,2), (0,3), (1,2), (1,3), (2,3)
sims = [
    _cosine_sim(embeddings[i], embeddings[j])
    for i, j in itertools.combinations(range(len(embeddings)), 2)
]
coherence = np.mean(sims)
```

High coherence (0.28+) → words clearly belong together.
Low coherence (< 0.12) → words may be connected by something non-semantic.

### 2. Centroid comparison → bridge word detection

A centroid is the average of all embeddings in a group — the geometric "center
of gravity" of the group's meaning.

```python
centroid = np.mean(group_embeddings, axis=0)  # shape: (768,)
```

For each word, we compare its similarity to its own group's centroid vs. every
other group's centroid. If a word is nearly as close to another group's center
as its own (> 80%), it's a bridge word — it "straddles" groups.

```python
own_sim = cosine_sim(word_emb, own_centroid)
cross_sim = cosine_sim(word_emb, other_centroid)
if cross_sim > 0.80 * own_sim:
    # This word could plausibly belong to either group
```

## Why This Matters for Puzzle Design

Bridge words are either:
- **Intentional red herrings** — great puzzle design (players are tricked)
- **Accidental ambiguity** — bad puzzle design (players are confused and frustrated)

The validator flags them; a human decides which it is. Embedding geometry can
detect the structural condition but not the designer's intent.

## Separation Ratio

For two groups, we want within-group similarity to be higher than cross-group
similarity. We express this as a ratio:

```
ratio = avg_within / avg_cross
```

Target ratio ≥ 1.5. Below 1.2 = potential ambiguity. Below 1.0 = the groups
are more similar to each other than to themselves (almost certainly wrong).
