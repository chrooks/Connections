---
date: 2026-03-08
patterns: [k-means, clustering, adjusted rand index, quality gate]
project: Connections
---

# K-Means Clustering and ARI — Using Unsupervised Learning as a Quality Test

## Problem

We want to know: "is this puzzle trivially solvable just by word similarity?"
The clustering recovery test answers this by asking: if you forgot the category
labels and just looked at where the words sit in embedding space, could you
reconstruct the groups?

## K-Means in One Paragraph

K-means takes N points and partitions them into K clusters by finding K
"centers" (centroids) that minimise the total distance from each point to
its nearest center. It's an iterative algorithm: place centroids randomly,
assign each point to the nearest centroid, recompute centroids, repeat until
stable.

```python
kmeans = KMeans(n_clusters=4, n_init=10, random_state=42)
predicted_labels = kmeans.fit_predict(all_embeddings)
# predicted_labels[i] = which cluster word i was assigned to
```

`n_init=10` means it restarts 10 times with different initial centroids and
keeps the best result — this matters because k-means can get stuck in local
minima.

## Adjusted Rand Index (ARI)

ARI measures how well two labelings of the same items agree, corrected for
chance agreement. In our case: how well do `predicted_labels` (k-means output)
match `true_labels` (the intended groups)?

```python
ari = adjusted_rand_score(true_labels, predicted_labels)
```

- ARI = 1.0 → perfect match; k-means perfectly recovered the intended groups
- ARI ≈ 0.0 → no better than random
- ARI can be slightly negative (worse than random, rare)

"Adjusted for chance" means a random labeling always scores near 0 regardless
of group sizes — raw accuracy would look deceptively good if groups are unequal.

## How the Validator Uses It

```python
if ari > 0.85 and all_groups_are_semantic:
    # Auto-fail: embeddings alone can solve the puzzle
    # Players who know how to think about word similarity would find it trivial
elif ari < 0.20:
    # Groupings are non-semantic (wordplay, fill-in-the-blank)
    # This is fine — but flag if no groups look like wordplay
```

The conditional on `all_groups_are_semantic` is critical: an ARI of 0.9 is
acceptable for a puzzle where one group is fill-in-the-blank (that group's
wordplay drags the ARI up because it's weird/random in embedding space, not
because the puzzle is too easy).

## Key Insight

K-means here isn't being used to *learn* anything — we're using it as a
**simulation of a naive player** who groups words by surface similarity alone.
If k-means succeeds, a thoughtful player following intuition probably will too,
and the puzzle lacks the depth that makes Connections satisfying.
