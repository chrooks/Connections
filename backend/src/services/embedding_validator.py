"""
Embedding-based validator for AI-generated Connections puzzles.

Analyzes puzzle quality using semantic embeddings from sentence-transformers.
This is the first layer of the validation pipeline — fast, free, and catches
structural quality issues before more expensive LLM-based checks.

The validator produces a structured report covering:
  - Within-group coherence (do words belong together semantically?)
  - Between-group distinctiveness (are groups clearly separated?)
  - Bridge word detection (which words could belong to multiple groups?)
  - Clustering recovery (can k-means reconstruct the intended groupings?)

Public API
----------
validate_puzzle_embeddings(puzzle_data)  → dict   - full validation report
compute_difficulty_score(report)         → float  - estimated difficulty 0-1
"""

from __future__ import annotations

import itertools
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Difficulty labels by group index (0=easiest/yellow … 3=hardest/purple)
DIFFICULTY_LABELS = ["yellow", "green", "blue", "purple"]

# Expected within-group coherence ranges per difficulty tier.
# Lower coherence = harder to spot the connection.
COHERENCE_THRESHOLDS: dict[str, tuple[float, float]] = {
    "yellow": (0.28, 0.32),
    "green":  (0.22, 0.28),
    "blue":   (0.18, 0.22),
    "purple": (0.12, 0.18),
}

# Auto-fail conditions
BETWEEN_GROUP_AMBIGUITY_LIMIT = 0.55  # cross-group similarity > this → too ambiguous
MIN_WITHIN_COHERENCE = 0.05           # within-group coherence < this → essentially random
ARI_TOO_EASY_THRESHOLD = 0.85         # ARI above this + all-semantic → trivially solvable

# Warning-level separation thresholds
SEPARATION_RATIO_WARNING = 1.2   # ratio < this → flag as "potential ambiguity"
SEPARATION_RATIO_TARGET = 1.5    # ratio < this → flag as "borderline"

# Bridge word: cross-group sim > this fraction of own-group sim
BRIDGE_WORD_FRACTION = 0.80

# ARI below this → groupings rely on non-semantic connections
ARI_NON_SEMANTIC_THRESHOLD = 0.20

# Category types where low embedding coherence is expected by design.
# These groups connect words via a shared word/phrase or wordplay trick,
# not semantic similarity — so the embedding model won't "see" the connection.
NON_SEMANTIC_TYPES = {"fill_in_the_blank", "wordplay", "compound_words"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_model():
    """Lazy-loads the sentence-transformer model (avoids slow startup cost)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: uv pip install sentence-transformers"
        )
    logger.info("Loading sentence-transformer model 'all-mpnet-base-v2' …")
    return SentenceTransformer("all-mpnet-base-v2")


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _avg_pairwise_cosine(embeddings: np.ndarray) -> float:
    """Average cosine similarity across all pairs in a group."""
    if len(embeddings) < 2:
        return 1.0
    sims = [
        _cosine_sim(embeddings[i], embeddings[j])
        for i, j in itertools.combinations(range(len(embeddings)), 2)
    ]
    return float(np.mean(sims))


def _avg_cross_cosine(a_embs: np.ndarray, b_embs: np.ndarray) -> float:
    """Average cosine similarity between every pair of vectors from two groups."""
    sims = [_cosine_sim(a, b) for a in a_embs for b in b_embs]
    return float(np.mean(sims))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_puzzle_embeddings(puzzle_data: dict) -> dict:
    """
    Validates a Connections puzzle using embedding-based analysis.

    Args:
        puzzle_data: Dict with shape:
            {
                "connections": [
                    {"relationship": "Category Name",
                     "words": ["w1", "w2", "w3", "w4"]},
                    ...
                ]
            }
            Groups should be ordered by difficulty (index 0 = easiest/yellow).

    Returns:
        Validation report with keys:
            passed             (bool)  — True if no auto-fail conditions triggered
            score              (float) — overall quality score 0–1
            group_coherence    (list)  — per-group within-group analysis
            group_distinctiveness (list) — per-pair between-group analysis
            bridge_words       (list)  — flagged words with similarity details
            clustering_recovery (dict) — ARI score and interpretation
            warnings           (list)  — human-readable non-fatal issues
            auto_fail_reasons  (list)  — if non-empty, puzzle should be rejected
    """
    connections = puzzle_data.get("connections", [])
    warnings: list[str] = []
    auto_fail_reasons: list[str] = []

    # ── Structural check: duplicate words ────────────────────────────────────
    all_words_flat = [w.lower() for conn in connections for w in conn.get("words", [])]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for w in all_words_flat:
        if w in seen:
            duplicates.add(w)
        seen.add(w)
    if duplicates:
        auto_fail_reasons.append(
            f"Duplicate words detected across groups: {sorted(duplicates)}"
        )

    if not connections:
        return {
            "passed": False,
            "score": 0.0,
            "group_coherence": [],
            "group_distinctiveness": [],
            "bridge_words": [],
            "clustering_recovery": {"ari": None, "interpretation": "no groups provided"},
            "warnings": ["No connections provided"],
            "auto_fail_reasons": auto_fail_reasons or ["No connections provided"],
        }

    # ── Embed all words in one batch call ────────────────────────────────────
    model = _load_model()

    groups: list[dict[str, Any]] = []
    for idx, conn in enumerate(connections):
        words = conn.get("words", [])
        label = DIFFICULTY_LABELS[idx] if idx < len(DIFFICULTY_LABELS) else f"group_{idx}"
        embs = model.encode(words, convert_to_numpy=True)
        groups.append({
            "index": idx,
            "label": label,
            "category": conn.get("relationship", f"Group {idx}"),
            "category_type": conn.get("category_type", "semantic"),
            "words": words,
            "embeddings": embs,
            "centroid": np.mean(embs, axis=0),
        })

    num_groups = len(groups)

    # ── (a) Within-group coherence ────────────────────────────────────────────
    group_coherence: list[dict] = []
    for g in groups:
        score = _avg_pairwise_cosine(g["embeddings"])
        lo, hi = COHERENCE_THRESHOLDS.get(g["label"], (0.10, 0.35))
        in_range = lo <= score <= hi

        is_non_semantic = g["category_type"] in NON_SEMANTIC_TYPES
        flag: str | None = None
        if not in_range:
            if score < lo:
                if is_non_semantic:
                    flag = (
                        f"non-semantic category type ({g['category_type']}) — "
                        "low coherence is expected; embedding analysis is not a reliable signal here"
                    )
                else:
                    flag = "embedding-divergent, manual review recommended"
            else:
                flag = "embedding-convergent (may be too easy for this difficulty tier)"

        group_coherence.append({
            "group_index": g["index"],
            "label": g["label"],
            "category": g["category"],
            "coherence_score": round(score, 4),
            "expected_range": list(COHERENCE_THRESHOLDS.get(g["label"], (0.10, 0.35))),
            "in_expected_range": in_range,
            "flag": flag,
        })

        if score < MIN_WITHIN_COHERENCE:
            auto_fail_reasons.append(
                f"Group '{g['category']}' ({g['label']}) within-group coherence "
                f"{score:.4f} < {MIN_WITHIN_COHERENCE} — words appear essentially random."
            )

    # ── (b) Between-group distinctiveness ─────────────────────────────────────
    # Only process each (i, j) pair once (upper triangle) to avoid duplicates.
    group_distinctiveness: list[dict] = []
    for i, j in itertools.combinations(range(num_groups), 2):
        cross_sim = _avg_cross_cosine(groups[i]["embeddings"], groups[j]["embeddings"])
        within_i = group_coherence[i]["coherence_score"]
        within_j = group_coherence[j]["coherence_score"]
        avg_within = (within_i + within_j) / 2.0
        ratio = avg_within / cross_sim if cross_sim > 0 else float("inf")

        either_non_semantic = (
            groups[i]["category_type"] in NON_SEMANTIC_TYPES
            or groups[j]["category_type"] in NON_SEMANTIC_TYPES
        )

        flag = None
        if cross_sim > BETWEEN_GROUP_AMBIGUITY_LIMIT:
            # Non-semantic groups can still auto-fail on raw cross-similarity — a
            # fill_in_the_blank group shouldn't be semantically identical to any other group.
            auto_fail_reasons.append(
                f"Groups '{groups[i]['category']}' and '{groups[j]['category']}' "
                f"between-group similarity {cross_sim:.4f} > {BETWEEN_GROUP_AMBIGUITY_LIMIT} "
                f"— too ambiguous to distinguish."
            )
            flag = f"auto-fail: between-group similarity {cross_sim:.4f} is too high"
        elif ratio < SEPARATION_RATIO_WARNING:
            if either_non_semantic:
                # Low ratio between a semantic and non-semantic group is expected:
                # the non-semantic group's words are generic nouns that land near everything.
                flag = (
                    f"low separation ratio {ratio:.2f} — expected when a non-semantic "
                    f"category type is involved"
                )
            else:
                warnings.append(
                    f"Groups '{groups[i]['category']}' and '{groups[j]['category']}': "
                    f"separation ratio {ratio:.2f} < {SEPARATION_RATIO_WARNING} — potential ambiguity."
                )
                flag = f"potential ambiguity (separation ratio {ratio:.2f})"
        elif ratio < SEPARATION_RATIO_TARGET:
            if not either_non_semantic:
                warnings.append(
                    f"Groups '{groups[i]['category']}' and '{groups[j]['category']}': "
                    f"separation ratio {ratio:.2f} is borderline (target ≥ {SEPARATION_RATIO_TARGET})."
                )
            flag = f"borderline separation (ratio {ratio:.2f})"

        group_distinctiveness.append({
            "group_i": groups[i]["category"],
            "group_j": groups[j]["category"],
            "cross_similarity": round(cross_sim, 4),
            "separation_ratio": round(ratio, 4) if ratio != float("inf") else None,
            "flag": flag,
        })

    # ── (c) Bridge word detection ────────────────────────────────────────────
    bridge_words: list[dict] = []
    for g in groups:
        other_groups = [og for og in groups if og["index"] != g["index"]]

        for word, emb in zip(g["words"], g["embeddings"]):
            own_sim = _cosine_sim(emb, g["centroid"])
            cross_sims = [
                (_cosine_sim(emb, og["centroid"]), og["category"])
                for og in other_groups
            ]
            max_cross_sim, max_cross_cat = max(cross_sims, key=lambda x: x[0])

            if own_sim > 0 and max_cross_sim > BRIDGE_WORD_FRACTION * own_sim:
                bridge_words.append({
                    "word": word,
                    "own_group": g["category"],
                    "own_similarity": round(own_sim, 4),
                    "closest_other_group": max_cross_cat,
                    "cross_similarity": round(max_cross_sim, 4),
                    "cross_to_own_ratio": round(max_cross_sim / own_sim, 4),
                    "note": (
                        "potential bridge word — could be an intentional red herring "
                        "or an ambiguous placement that may confuse players"
                    ),
                })

    # ── (d) Clustering recovery test ─────────────────────────────────────────
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import adjusted_rand_score

        all_embeddings = np.vstack([g["embeddings"] for g in groups])
        true_labels = np.array([
            g["index"] for g in groups for _ in g["words"]
        ])

        # Standard k-means with k = num_groups. We use n_init=10 for stability.
        kmeans = KMeans(n_clusters=num_groups, n_init=10, random_state=42)
        predicted_labels = kmeans.fit_predict(all_embeddings)
        ari = float(adjusted_rand_score(true_labels, predicted_labels))

        if ari > ARI_TOO_EASY_THRESHOLD:
            interpretation = (
                f"ARI {ari:.3f} — embeddings alone can reconstruct the groupings; "
                "puzzle may be too easy if all groups are semantic"
            )
            # Auto-fail only when all groups are semantic — a wordplay group in
            # the mix would inflate ARI without the puzzle being trivially easy.
            all_semantic = all(
                g["category_type"] not in NON_SEMANTIC_TYPES for g in groups
            )
            if all_semantic:
                auto_fail_reasons.append(
                    f"Clustering ARI {ari:.3f} > {ARI_TOO_EASY_THRESHOLD} and all groups "
                    "appear semantic — puzzle is trivially solvable by embedding similarity alone."
                )
        elif ari < ARI_NON_SEMANTIC_THRESHOLD:
            interpretation = (
                f"ARI {ari:.3f} — groupings rely on non-semantic connections "
                "(wordplay, fill-in-the-blank, etc. — this is fine for those category types)"
            )
            # Warn if no group is explicitly a non-semantic type — low ARI with
            # only semantic groups is a sign the puzzle is structurally incoherent.
            any_non_semantic = any(
                g["category_type"] in NON_SEMANTIC_TYPES for g in groups
            )
            if not any_non_semantic:
                warnings.append(
                    f"Clustering ARI {ari:.3f} < {ARI_NON_SEMANTIC_THRESHOLD} — groupings "
                    "appear non-semantic, but no groups are flagged embedding-divergent. "
                    "Manual review recommended."
                )
        else:
            interpretation = (
                f"ARI {ari:.3f} — reasonable semantic structure; "
                "puzzle has moderate embedding-based difficulty"
            )

        clustering_recovery = {"ari": round(ari, 4), "interpretation": interpretation}

    except ImportError:
        warnings.append(
            "scikit-learn not installed — clustering recovery test skipped. "
            "Run: uv pip install scikit-learn"
        )
        clustering_recovery = {
            "ari": None,
            "interpretation": "skipped (scikit-learn not installed)",
        }

    # ── Assemble report and compute overall score ────────────────────────────
    passed = len(auto_fail_reasons) == 0

    report: dict = {
        "passed": passed,
        "score": 0.0,  # filled below
        "group_coherence": group_coherence,
        "group_distinctiveness": group_distinctiveness,
        "bridge_words": bridge_words,
        "clustering_recovery": clustering_recovery,
        "warnings": warnings,
        "auto_fail_reasons": auto_fail_reasons,
    }
    report["score"] = round(compute_difficulty_score(report), 4)

    return report


def compute_difficulty_score(validation_report: dict) -> float:
    """
    Estimates puzzle difficulty on a 0–1 scale from embedding metrics.

    Higher score = harder puzzle. The four contributing signals:

    1. Coherence (35%): Lower avg within-group coherence → harder for semantic puzzles.
    2. ARI (30%): Lower clustering recovery → harder (embeddings alone can't solve it).
    3. Bridge words (15%): More bridge words → more player traps → harder.
    4. Separation (20%): Lower between-group separation → groups are easily confused.

    Returns:
        float in [0, 1]. 0 = trivially easy, 1 = extremely hard.
    """
    coherence_scores = [
        gc["coherence_score"]
        for gc in validation_report.get("group_coherence", [])
    ]
    if not coherence_scores:
        return 0.5

    # 1. Coherence component — normalised from [0.05, 0.40] → [0, 1]
    avg_coherence = float(np.mean(coherence_scores))
    coherence_component = 1.0 - min(max((avg_coherence - 0.05) / 0.35, 0.0), 1.0)

    # 2. ARI component — lower ARI = harder (can't be solved by embeddings alone)
    ari = validation_report.get("clustering_recovery", {}).get("ari")
    ari_component = 1.0 - float(ari) if ari is not None else 0.5

    # 3. Bridge word component — normalise against a ceiling of 4 bridge words
    num_bridge = len(validation_report.get("bridge_words", []))
    bridge_component = min(num_bridge / 4.0, 1.0)

    # 4. Separation component — lower separation ratio = groups are more confused
    distinctiveness = validation_report.get("group_distinctiveness", [])
    ratios = [
        d["separation_ratio"]
        for d in distinctiveness
        if d.get("separation_ratio") is not None
    ]
    if ratios:
        # ratio ≥ 2.0 → easy; ratio ≤ 1.0 → hard
        avg_ratio = float(np.mean(ratios))
        separation_component = 1.0 - min(max((avg_ratio - 1.0) / 1.0, 0.0), 1.0)
    else:
        separation_component = 0.5

    difficulty = (
        0.35 * coherence_component
        + 0.30 * ari_component
        + 0.15 * bridge_component
        + 0.20 * separation_component
    )
    return float(min(max(difficulty, 0.0), 1.0))


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # A puzzle that mixes clean semantic groups with a wordplay group.
    # Group 0 (yellow): obvious pasta types — high expected coherence
    # Group 1 (green): orchestral instruments — moderate coherence
    # Group 2 (blue): ___ fish — low embedding coherence (wordplay/fill-in-the-blank)
    # Group 3 (purple): things that can be "grand" — tricky cross-domain group
    EXAMPLE_PUZZLE = {
        "connections": [
            {
                "relationship": "Types of pasta",
                "words": ["penne", "rigatoni", "fusilli", "farfalle"],
                "category_type": "members_of_set",
            },
            {
                "relationship": "Orchestral string instruments",
                "words": ["violin", "viola", "cello", "double bass"],
                "category_type": "members_of_set",
            },
            {
                "relationship": "___ fish",
                "words": ["sword", "cat", "star", "jelly"],
                "category_type": "fill_in_the_blank",
            },
            {
                "relationship": "Things that can be 'grand'",
                "words": ["piano", "jury", "canyon", "slam"],
                "category_type": "compound_words",
            },
        ]
    }

    print("Validating example puzzle …\n")
    report = validate_puzzle_embeddings(EXAMPLE_PUZZLE)

    # Pretty-print, excluding the raw embedding arrays
    print(json.dumps(report, indent=2))
    print(f"\nDifficulty estimate: {report['score']:.3f} (0=easiest, 1=hardest)")
    print(f"Passed: {report['passed']}")
    if report["auto_fail_reasons"]:
        print("\nAuto-fail reasons:")
        for reason in report["auto_fail_reasons"]:
            print(f"  ✗ {reason}")
    if report["warnings"]:
        print("\nWarnings:")
        for w in report["warnings"]:
            print(f"  ⚠ {w}")
