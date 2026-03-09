"""
Validation pipeline for AI-generated Connections puzzles.

Orchestrates structural, embedding, and LLM checks into a single
validate_puzzle() call that returns a unified quality report.

Pipeline stages
---------------
  Stage 1 — Structural checks  (no API calls, ~0 ms)
  Stage 2 — Embedding validation  (local model, ~200 ms)
  Stage 3 — LLM validation  (10 Claude API calls, ~$0.001)

Each stage short-circuits the pipeline on failure to avoid wasting money
on a puzzle that a cheaper check already caught.

Public API
----------
validate_puzzle(puzzle_data)              → dict   full validation report
validate_and_store(puzzle_id, supabase)   → dict   validates + approves/rejects in DB
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Final score weighting
EMBEDDING_WEIGHT = 0.4
LLM_WEIGHT = 0.6

# Minimum combined score to consider a puzzle "passed"
PASSING_SCORE_THRESHOLD = 0.5

# Expected puzzle dimensions for the classic 4×4 layout
EXPECTED_GROUPS = 4
EXPECTED_WORDS_PER_GROUP = 4

# Any phrase with more tokens than this is treated as a sentence (invalid)
MAX_TOKENS_IN_PHRASE = 5


# ---------------------------------------------------------------------------
# Stage 1: Structural checks
# ---------------------------------------------------------------------------

def _structural_checks(puzzle_data: dict) -> tuple[list[str], list[str]]:
    """
    Validates puzzle shape without any API calls.

    Returns:
        (warnings, auto_fail_reasons) — lists of human-readable strings.
        auto_fail_reasons being non-empty means the puzzle must be rejected.
    """
    connections = puzzle_data.get("connections", [])
    warnings: list[str] = []
    auto_fail_reasons: list[str] = []

    # ── Group count ───────────────────────────────────────────────────────────
    if len(connections) != EXPECTED_GROUPS:
        auto_fail_reasons.append(
            f"Expected {EXPECTED_GROUPS} groups, got {len(connections)}."
        )

    # ── Per-group word count + sentence detection ─────────────────────────────
    for idx, conn in enumerate(connections):
        label = conn.get("relationship") or f"group[{idx}]"
        words = conn.get("words", [])

        if len(words) != EXPECTED_WORDS_PER_GROUP:
            auto_fail_reasons.append(
                f"'{label}' has {len(words)} word(s); expected {EXPECTED_WORDS_PER_GROUP}."
            )

        for word in words:
            token_count = len(word.split())
            if token_count > MAX_TOKENS_IN_PHRASE:
                auto_fail_reasons.append(
                    f"Entry '{word}' in '{label}' looks like a sentence "
                    f"({token_count} tokens; max is {MAX_TOKENS_IN_PHRASE})."
                )

    # ── Duplicate words (case-insensitive) ────────────────────────────────────
    all_words = [w.lower() for c in connections for w in c.get("words", [])]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for w in all_words:
        if w in seen:
            duplicates.add(w)
        seen.add(w)
    if duplicates:
        auto_fail_reasons.append(
            f"Duplicate word(s) across groups: {sorted(duplicates)}"
        )

    # ── Category names: non-empty and distinct ────────────────────────────────
    seen_names: set[str] = set()
    for idx, conn in enumerate(connections):
        name = (conn.get("relationship") or "").strip()
        if not name:
            auto_fail_reasons.append(
                f"Group at index {idx} has an empty category name."
            )
            continue
        lower = name.lower()
        if lower in seen_names:
            auto_fail_reasons.append(
                f"Duplicate category name '{name}' (case-insensitive)."
            )
        seen_names.add(lower)

    return warnings, auto_fail_reasons


# ---------------------------------------------------------------------------
# LLM score derivation
# ---------------------------------------------------------------------------

def _derive_llm_score(llm_report: dict) -> float:
    """
    Converts validate_with_llm() output into a 0-1 quality score.

    The LLM stage is primarily a gate: its auto-fail rules already handle the
    bad extremes (< 10% agreement = unsolvable, > 90% + too_easy = trivial).
    Anything that clears those gates is acceptable difficulty — difficulty is
    not the same as poor quality, so we don't penalise hard puzzles.

    Scoring:
      - auto-fail triggered        →  0.0  (rejected)
      - passed, appropriate        →  0.75 (good)
      - passed, too_easy           →  0.70 (borderline easy, not fatal)
      - passed, hard_or_flawed     →  0.55 (0 groups correct at temp=0 — suspect)
    """
    if llm_report.get("auto_fail_reasons"):
        return 0.0

    assessment: str = llm_report.get("difficulty_assessment", {}).get("assessment", "")

    base = 0.75
    if assessment == "hard_or_flawed":
        base -= 0.20   # Haiku got 0 correct at temp=0 — structurally suspect
    elif assessment == "too_easy":
        base -= 0.05   # Borderline, but not an auto-fail

    return round(base, 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_puzzle(puzzle_data: dict) -> dict:
    """
    Runs the full validation pipeline on a Connections puzzle.

    Args:
        puzzle_data: {
            "connections": [
                {"relationship": "Category Name", "words": ["w1", "w2", "w3", "w4"]},
                ...
            ]
        }
        Groups should be ordered by difficulty (index 0 = easiest/yellow).

    Returns:
        {
            "passed":            bool,
            "score":             float,   # 0–1 combined quality score
            "structural":        dict,    # Stage 1 results
            "embedding":         dict | None,  # Stage 2 results (None if skipped)
            "llm":               dict | None,  # Stage 3 results (None if skipped)
            "auto_fail_reasons": list[str],
            "warnings":          list[str],
        }
    """
    logger.info("=== Starting validation pipeline ===")

    # ── Stage 1: Structural checks ────────────────────────────────────────────
    logger.info("Stage 1 — structural checks …")
    struct_warnings, struct_fails = _structural_checks(puzzle_data)

    structural_report: dict[str, Any] = {
        "warnings": struct_warnings,
        "auto_fail_reasons": struct_fails,
    }

    if struct_fails:
        logger.warning("Stage 1 FAILED (%d reason(s)): %s", len(struct_fails), struct_fails)
        return {
            "passed": False,
            "score": 0.0,
            "structural": structural_report,
            "embedding": None,
            "llm": None,
            "auto_fail_reasons": struct_fails,
            "warnings": struct_warnings,
        }

    logger.info("Stage 1 passed.")

    # ── Stage 2: Embedding validation ────────────────────────────────────────
    logger.info("Stage 2 — embedding validation …")
    from .embedding_validator import validate_puzzle_embeddings

    embedding_report = validate_puzzle_embeddings(puzzle_data)
    embedding_score: float = embedding_report.get("score", 0.0)
    embedding_fails: list[str] = embedding_report.get("auto_fail_reasons", [])

    if embedding_fails:
        logger.warning(
            "Stage 2 FAILED — skipping LLM validation to save API cost. "
            "Reasons: %s",
            embedding_fails,
        )
        return {
            "passed": False,
            "score": round(embedding_score * EMBEDDING_WEIGHT, 4),
            "structural": structural_report,
            "embedding": embedding_report,
            "llm": None,
            "auto_fail_reasons": embedding_fails,
            "warnings": struct_warnings + embedding_report.get("warnings", []),
        }

    logger.info("Stage 2 passed (embedding score=%.3f).", embedding_score)

    # ── Stage 3: LLM validation ───────────────────────────────────────────────
    logger.info("Stage 3 — LLM validation (10 API calls) …")
    from .llm_validator import validate_with_llm

    llm_report = validate_with_llm(puzzle_data)
    llm_score = _derive_llm_score(llm_report)
    llm_fails: list[str] = llm_report.get("auto_fail_reasons", [])

    logger.info(
        "Stage 3 complete (derived score=%.3f, auto_fail_reasons=%d).",
        llm_score,
        len(llm_fails),
    )

    # ── Final scoring ─────────────────────────────────────────────────────────
    combined_score = round(
        (embedding_score * EMBEDDING_WEIGHT) + (llm_score * LLM_WEIGHT), 4
    )

    all_auto_fails = embedding_fails + llm_fails
    all_warnings = (
        struct_warnings
        + embedding_report.get("warnings", [])
        + llm_report.get("warnings", [])
    )

    passed = (not all_auto_fails) and (combined_score > PASSING_SCORE_THRESHOLD)

    logger.info(
        "=== Validation complete: passed=%s, score=%.3f "
        "(embedding=%.3f × %.0f%% + llm=%.3f × %.0f%%) ===",
        passed,
        combined_score,
        embedding_score, EMBEDDING_WEIGHT * 100,
        llm_score, LLM_WEIGHT * 100,
    )

    return {
        "passed": passed,
        "score": combined_score,
        "structural": structural_report,
        "embedding": embedding_report,
        "llm": llm_report,
        "auto_fail_reasons": all_auto_fails,
        "warnings": all_warnings,
    }


def validate_and_store(puzzle_id: str, supabase_client=None) -> dict:
    """
    Fetches a draft puzzle from the DB, validates it, and persists the result.

    Transitions the puzzle to 'approved' or 'rejected' based on the pipeline
    outcome, and stores the full validation report for debugging / model tuning.

    Args:
        puzzle_id:       UUID of a puzzles row with status='draft'.
        supabase_client: Optional pre-created Supabase client. If not provided,
                         the shared service-role client from puzzle_pool_service
                         is used (requires SUPABASE_URL / SUPABASE_KEY env vars).

    Returns:
        The validation report dict returned by validate_puzzle().

    Raises:
        ValueError:   puzzle_id not found in the DB.
        RuntimeError: Supabase env vars missing and no client provided.
    """
    from .puzzle_pool_service import approve_puzzle, reject_puzzle

    # ── Resolve Supabase client ───────────────────────────────────────────────
    if supabase_client is None:
        # Reuse the lazy singleton from puzzle_pool_service so we don't create
        # a second connection with the same credentials.
        from .puzzle_pool_service import _get_client as _pool_get_client
        supabase_client = _pool_get_client()

    # ── Fetch the puzzle from DB ──────────────────────────────────────────────
    logger.info("Fetching draft puzzle %s from DB …", puzzle_id)

    groups_result = (
        supabase_client.table("puzzle_groups")
        .select("category_name, sort_order, puzzle_words(word, display_text)")
        .eq("puzzle_id", puzzle_id)
        .order("sort_order")
        .execute()
    )

    if not groups_result.data:
        raise ValueError(
            f"Puzzle {puzzle_id} not found or has no groups. "
            "Verify the puzzle was seeded via seed_puzzle_to_pool()."
        )

    # Reconstruct the standard connections format expected by validators.
    # Prefer display_text (original casing) over the canonical lowercase 'word'.
    connections = [
        {
            "relationship": group["category_name"],
            "words": [
                pw.get("display_text") or pw["word"]
                for pw in group["puzzle_words"]
            ],
        }
        for group in groups_result.data
    ]
    puzzle_data = {"connections": connections}

    logger.info("Loaded puzzle %s (%d groups).", puzzle_id, len(connections))

    # ── Run validation pipeline ───────────────────────────────────────────────
    report = validate_puzzle(puzzle_data)

    # ── Persist result ────────────────────────────────────────────────────────
    if report["passed"]:
        logger.info("Puzzle %s APPROVED (score=%.3f).", puzzle_id, report["score"])
        approve_puzzle(puzzle_id, report["score"], report)
    else:
        logger.warning(
            "Puzzle %s REJECTED. Reasons: %s",
            puzzle_id,
            report["auto_fail_reasons"],
        )
        reject_puzzle(puzzle_id, report, report["score"])

    return report


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys
    from datetime import datetime
    from pathlib import Path

    from dotenv import load_dotenv
    load_dotenv()

    # Import at module level only for the demo — avoids circular import in prod
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.generation.puzzle_generator import generate_puzzle

    print("Generating puzzle …\n")
    puzzle = generate_puzzle()

    if puzzle is None:
        print("ERROR: puzzle_generator returned None — check logs for details.")
        sys.exit(1)

    # Convert generate_puzzle() output → {"connections": [...]} format
    puzzle_data = {
        "connections": [
            {
                "relationship": g["category_name"],
                "words": g["words"],
                # category_type is passed through so embedding validator can
                # correctly skip coherence checks for fill_in_the_blank etc.
                "category_type": g.get("category_type", "members_of_set"),
            }
            for g in puzzle["groups"]
        ]
    }

    print("Generated puzzle:")
    for conn in puzzle_data["connections"]:
        print(f"  [{conn['relationship']}] {conn['words']}")
    print()

    print("Running validation pipeline …\n")
    report = validate_puzzle(puzzle_data)

    print(f"Passed: {report['passed']}")
    print(f"Score:  {report['score']:.3f}  "
          f"(embedding × {EMBEDDING_WEIGHT:.0%} + LLM × {LLM_WEIGHT:.0%})")

    if report["auto_fail_reasons"]:
        print("\nAuto-fail reasons:")
        for r in report["auto_fail_reasons"]:
            print(f"  ✗ {r}")

    if report["warnings"]:
        print("\nWarnings:")
        for w in report["warnings"]:
            print(f"  ⚠ {w}")

    if report["embedding"]:
        emb = report["embedding"]
        print(f"\nEmbedding score: {emb.get('score', 'n/a'):.3f}")

    if report["llm"]:
        llm = report["llm"]
        consistency = llm.get("solver_consistency", {})
        print(f"LLM agreement rate: {consistency.get('agreement_rate', 'n/a'):.0%}")
        print(f"LLM difficulty assessment: "
              f"{llm.get('difficulty_assessment', {}).get('assessment', 'n/a')}")
        print(f"LLM token usage: {llm.get('token_usage', {})}")

    # ── Write full report to file ─────────────────────────────────────────────
    output_dir = Path(__file__).resolve().parents[2] / "validation_runs"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = output_dir / f"{timestamp}.json"

    file_record = {
        "timestamp": timestamp,
        "puzzle": puzzle_data["connections"],
        "passed": report["passed"],
        "score": report["score"],
        "embedding_score": report["embedding"].get("score") if report["embedding"] else None,
        "llm_agreement_rate": (
            report["llm"]["solver_consistency"].get("agreement_rate")
            if report["llm"] else None
        ),
        "llm_difficulty_assessment": (
            report["llm"]["difficulty_assessment"].get("assessment")
            if report["llm"] else None
        ),
        "auto_fail_reasons": report["auto_fail_reasons"],
        "warnings": report["warnings"],
        "llm_token_usage": report["llm"]["token_usage"] if report["llm"] else None,
    }

    output_path.write_text(json.dumps(file_record, indent=2))
    print(f"\nFull report written to: {output_path}")
