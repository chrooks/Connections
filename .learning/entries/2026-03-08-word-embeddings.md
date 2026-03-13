---
date: 2026-03-08
patterns: [embeddings, semantic similarity, vector representation]
project: Connections
---

# Word Embeddings — Representing Meaning as Numbers

## Problem

Computers can't inherently understand that "dog" and "puppy" are more
related than "dog" and "refrigerator." We need a way to represent meaning
numerically so we can do math on it.

## What an Embedding Is

An embedding is a list of numbers (a vector) that represents the "meaning"
of a word or sentence. A model trained on massive amounts of text learns to
place similar words near each other in this high-dimensional space.

`sentence-transformers` with `all-mpnet-base-v2` produces 768-number vectors:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-mpnet-base-v2")
embs = model.encode(["dog", "puppy", "refrigerator"], convert_to_numpy=True)
# embs.shape == (3, 768)
# embs[0] and embs[1] will be numerically close
# embs[2] will be far from both
```

## Cosine Similarity — Measuring Closeness

Once you have two vectors you measure how similar they are with cosine similarity
— the angle between them in 768-dimensional space. Why angle, not distance?
Because we care about direction (what the word is *about*), not magnitude.

```python
def _cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

Returns 0–1 for word meanings: 1.0 = same meaning, ~0.1 = unrelated.

## Why This Matters for Connections

The validator uses this to ask: "do these four words actually belong together
semantically?" A group of pasta types should have high pairwise cosine similarity.
A group connected by wordplay ("___ fish") will have low cosine similarity —
and that's fine, but it's a signal that the category type is non-semantic.

## Key Insight

Embeddings turn qualitative questions ("are these words related?") into
quantitative ones ("is this cosine similarity above 0.25?"). That's what
makes automated validation possible at all.
