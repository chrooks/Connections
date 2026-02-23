"""
Puzzle Pool Service for the Connections game.

Manages the puzzle lifecycle in Supabase:

    seed (draft) → validate → approve/reject → serve

This module is the bridge between the puzzle generation pipeline and the
generate-grid endpoint. Import it into game.py (or a route) and call
get_puzzle_from_pool() to pull a ready-to-serve puzzle.

Public API
----------
get_puzzle_from_pool(config_name)  → list[dict]  - fetch & format one puzzle
get_pool_stats(config_name)        → dict         - count puzzles by status
seed_puzzle_to_pool(puzzle_data)   → str          - insert draft puzzle, return id
approve_puzzle(id, score, report)  → None         - mark approved
reject_puzzle(id, report)          → None         - mark rejected
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supabase client — lazy singleton.
#
# The import of 'supabase' is deferred to _get_client() for two reasons:
#   1. The project has a supabase/ directory (migrations) at the repo root that
#      creates a Python namespace package, shadowing the real supabase-py library
#      when tests run from the project root.
#   2. Tests mock _get_client() directly, so the real import never runs in the
#      test suite — meaning tests work even before 'pip install supabase' is run.
#
# We use the service_role key (not the anon key) so all operations bypass Row
# Level Security — appropriate for server-to-server calls inside Flask.
# ---------------------------------------------------------------------------
_supabase = None


def _get_client():
    """Returns the shared Supabase client, creating it on first call."""
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client  # deferred to avoid namespace collision
        except ImportError:
            raise RuntimeError(
                "supabase package is not installed. "
                "Run: pip install 'supabase>=2.0.0'"
            )
        url = os.getenv("SUPABASE_URL")
        # service_role key — bypasses RLS for server-side operations
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set. "
                "Add them to backend/.env (use .env.example as a template)."
            )
        _supabase = create_client(url, key)
    return _supabase


def _get_config_id(supabase, config_name: str) -> str:
    """
    Resolves a config slug (e.g. 'classic') to its UUID in puzzle_configs.

    This lookup is cheap and infrequent; puzzle_configs has at most a handful
    of rows and the name column has a UNIQUE index.

    Raises:
        ValueError: If no config with that name exists.
    """
    result = (
        supabase.table("puzzle_configs")
        .select("id")
        .eq("name", config_name)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(
            f"Puzzle config '{config_name}' not found in puzzle_configs. "
            "Verify the migration has been applied and the config row exists."
        )
    return result.data[0]["id"]


# ---------------------------------------------------------------------------
# Public exception — lets callers distinguish "pool is empty" from other errors
# so they can degrade gracefully (e.g. fall back to static JSON).
# ---------------------------------------------------------------------------
class PuzzlePoolEmptyError(Exception):
    """Raised when no approved puzzles exist for the requested config."""
    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_puzzle_from_pool(config_name: str = "classic") -> "list[dict]":
    """
    Fetches one random approved puzzle and returns it in the connections format.

    Calls the get_random_approved_puzzle Postgres function (defined in the
    migration), which atomically:
      1. Selects a random approved puzzle using FOR UPDATE SKIP LOCKED to
         prevent two concurrent requests from serving the same puzzle.
      2. Increments times_served so the pool can be load-balanced over time.

    Returns:
        List of connection dicts ready for game.py / dal.py:
        [
            {"relationship": "Category Name", "words": ["w1", "w2", "w3", "w4"],
             "guessed": False},
            ...
        ]

    Raises:
        PuzzlePoolEmptyError: No approved puzzles exist for this config.
        ValueError:           config_name doesn't match any puzzle_configs row.
        RuntimeError:         Puzzle exists but has no groups (data integrity issue).
    """
    supabase = _get_client()
    config_id = _get_config_id(supabase, config_name)

    # Call the atomic DB function — returns the UUID of the selected puzzle,
    # or None if the pool is empty for this config.
    rpc_result = supabase.rpc(
        "get_random_approved_puzzle",
        {"p_config_id": config_id},
    ).execute()

    puzzle_id = rpc_result.data
    if not puzzle_id:
        raise PuzzlePoolEmptyError(
            f"No approved puzzles in the pool for config '{config_name}'. "
            "Seed puzzles via seed_puzzle_to_pool() and approve them first."
        )

    logger.info("Fetched puzzle %s from pool (config=%s)", puzzle_id, config_name)

    # Fetch all groups with their words in a single nested query.
    # PostgREST supports embedding related rows via foreign keys using the
    # "table(columns)" syntax inside select().
    groups_result = (
        supabase.table("puzzle_groups")
        .select("category_name, sort_order, puzzle_words(word, display_text)")
        .eq("puzzle_id", puzzle_id)
        .order("sort_order")  # stable ordering matches the NYT difficulty ramp
        .execute()
    )

    if not groups_result.data:
        raise RuntimeError(
            f"Puzzle {puzzle_id} has no groups — data integrity error. "
            "Check that seed_puzzle_to_pool completed without errors."
        )

    # Transform DB shape → the format that game.py and dal.py expect.
    # Each connection dict must have: relationship, words, guessed.
    connections = []
    for group in groups_result.data:
        words = [
            # Use display_text (e.g. "McCARTHY") when set; fall back to the
            # canonical lowercase form stored in word.
            pw.get("display_text") or pw["word"]
            for pw in group["puzzle_words"]
        ]
        connections.append({
            "relationship": group["category_name"],
            "words": words,
            "guessed": False,  # all groups start unguessed when a new game is created
        })

    return connections


def get_pool_stats(config_name: str = "classic") -> dict:
    """
    Returns a count of puzzles by status for the given config.

    Useful for monitoring the pool's health — e.g. alerting when the
    approved count drops too low or too many puzzles are being rejected.

    Example return value:
        {
            "config": "classic",
            "approved": 12,
            "draft": 3,
            "validating": 0,
            "rejected": 1,
            "served": 45,
            "total": 61
        }
    """
    supabase = _get_client()
    config_id = _get_config_id(supabase, config_name)

    # Fetch only the status column — lightweight even for large pools.
    # We aggregate in Python rather than adding another DB function because
    # this is a low-frequency monitoring call and simplicity wins here.
    result = (
        supabase.table("puzzles")
        .select("status")
        .eq("config_id", config_id)
        .execute()
    )

    # Initialise all known statuses to 0 so the dict is always complete,
    # even when a status has never been used.
    counts: dict = {
        "draft": 0,
        "validating": 0,
        "approved": 0,
        "rejected": 0,
        "served": 0,
    }
    for row in result.data:
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1

    return {"config": config_name, "total": sum(counts.values()), **counts}


def seed_puzzle_to_pool(
    puzzle_data: dict,
    generation_model: str = "unknown",
    generation_metadata: "dict | None" = None,
) -> str:
    """
    Inserts a generated puzzle into the pool with status='draft'.

    The puzzle is written as three related DB rows:
      puzzles → puzzle_groups → puzzle_words

    The puzzle_id column on puzzle_words is filled automatically by the
    trg_puzzle_words_set_puzzle_id trigger, but we also pass it explicitly
    so PostgREST doesn't reject the NOT NULL column before the trigger fires.

    Args:
        puzzle_data: Dict with shape:
            {
                "connections": [
                    {"relationship": "Category Name",
                     "words": ["w1", "w2", "w3", "w4"]},
                    ...
                ],
                "config_name": "classic"   # optional, defaults to "classic"
            }
        generation_model:    Name/ID of the model that generated the puzzle
                             (e.g. "claude-opus-4-6"). Stored for reproducibility.
        generation_metadata: Arbitrary dict with generation params (prompt version,
                             temperature, seed, etc.).

    Returns:
        str: UUID of the newly created puzzles row.

    Raises:
        ValueError: If puzzle_data is malformed or the config doesn't exist.
    """
    supabase = _get_client()
    config_name = puzzle_data.get("config_name", "classic")
    config_id = _get_config_id(supabase, config_name)

    connections = puzzle_data.get("connections")
    if not connections:
        raise ValueError(
            "puzzle_data must include a non-empty 'connections' list. "
            "Each item needs 'relationship' (str) and 'words' (list)."
        )

    # Step 1: Insert the parent puzzle row to obtain its UUID.
    # All downstream inserts reference this id.
    puzzle_result = (
        supabase.table("puzzles")
        .insert({
            "config_id": config_id,
            "status": "draft",
            "generation_model": generation_model,
            "generation_metadata": generation_metadata or {},
        })
        .execute()
    )
    puzzle_id: str = puzzle_result.data[0]["id"]
    logger.info("Seeded puzzle %s to pool as 'draft' (model=%s)", puzzle_id, generation_model)

    # Step 2: Insert each group, then its words.
    # sort_order is 0-indexed; difficulty_rank 1–4 maps to the NYT colour scheme
    # (1=yellow/easiest … 4=purple/hardest).
    for sort_order, connection in enumerate(connections):
        relationship = connection.get("relationship")
        words = connection.get("words", [])

        if not relationship:
            raise ValueError(
                f"Connection at index {sort_order} is missing 'relationship'."
            )
        if not words:
            raise ValueError(
                f"Connection '{relationship}' (index {sort_order}) has an empty 'words' list."
            )

        # Insert the group row for this category
        group_result = (
            supabase.table("puzzle_groups")
            .insert({
                "puzzle_id": puzzle_id,
                "category_name": relationship,
                "difficulty_rank": sort_order + 1,
                "sort_order": sort_order,
            })
            .execute()
        )
        group_id: str = group_result.data[0]["id"]

        # Insert all words for this group in one batch call.
        # We store word.lower() as the canonical form for dedup/logic and
        # preserve the original capitalisation in display_text for the UI.
        # puzzle_id is denormalised here (the trigger also sets it from group_id).
        word_rows = [
            {
                "group_id": group_id,
                "puzzle_id": puzzle_id,   # explicit for PostgREST NOT NULL safety
                "word": word.lower(),
                "display_text": word,     # original casing for display
            }
            for word in words
        ]
        supabase.table("puzzle_words").insert(word_rows).execute()

    return puzzle_id


def approve_puzzle(
    puzzle_id: str,
    validation_score: float,
    validation_report: dict,
) -> None:
    """
    Transitions a puzzle to 'approved', making it eligible for serving.

    Once approved, get_puzzle_from_pool() will include this puzzle in the
    random selection. The validation_score and validation_report are stored
    for debugging and future quality analysis.

    Args:
        puzzle_id:         UUID of the puzzle to approve.
        validation_score:  Composite quality score, 0.0 (worst) to 1.0 (best).
        validation_report: Structured dict with per-category scores, pass/fail
                           reasons, and any flagged issues.
    """
    supabase = _get_client()

    supabase.table("puzzles").update({
        "status": "approved",
        "validation_score": validation_score,
        "validation_report": validation_report,
        # Pass a Python datetime string — PostgREST does not interpret raw SQL
        # expressions like "now()" passed as strings.
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", puzzle_id).execute()

    logger.info("Approved puzzle %s (validation_score=%.3f)", puzzle_id, validation_score)


def reject_puzzle(puzzle_id: str, validation_report: dict) -> None:
    """
    Transitions a puzzle to 'rejected', permanently excluding it from the pool.

    Rejected puzzles are never served. The validation_report should explain
    which checks failed so the generation pipeline can be tuned accordingly.

    Args:
        puzzle_id:         UUID of the puzzle to reject.
        validation_report: Structured dict explaining which checks failed and why.
    """
    supabase = _get_client()

    supabase.table("puzzles").update({
        "status": "rejected",
        "validation_report": validation_report,
    }).eq("id", puzzle_id).execute()

    logger.info("Rejected puzzle %s", puzzle_id)
