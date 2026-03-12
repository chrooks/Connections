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


class PlayerExhaustedPoolError(PuzzlePoolEmptyError):
    """
    Raised when a specific player has already completed every approved puzzle
    in the pool. Subclasses PuzzlePoolEmptyError so callers that don't need
    to distinguish the two cases can catch the parent class; callers that do
    (e.g. routes.py) can catch this more specific class first.
    """
    pass


class PuzzleIntegrityError(Exception):
    """
    Raised when repeated attempts to fetch a valid puzzle all return malformed
    data (e.g. a connection with the wrong number of words). Indicates a pool
    integrity problem that requires admin attention.

    Intentionally does NOT subclass PuzzlePoolEmptyError so it is never
    silently swallowed by a fallback-to-static handler.
    """
    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_puzzle_from_pool(
    config_name: str = "classic",
    exclude_puzzle_ids: "list[str] | None" = None,
) -> "tuple[list[dict], str]":
    """
    Fetches one random approved puzzle and returns it in the connections format.

    Calls the get_random_approved_puzzle Postgres function (defined in the
    migration), which atomically:
      1. Selects a random approved puzzle using FOR UPDATE SKIP LOCKED to
         prevent two concurrent requests from serving the same puzzle.
      2. Skips any puzzle whose ID appears in exclude_puzzle_ids (already
         completed by this player).
      3. Increments times_served so the pool can be load-balanced over time.

    Args:
        config_name:        Pool config slug to pull from (default "classic").
        exclude_puzzle_ids: List of puzzle UUIDs to skip — pass the player's
                            completed puzzle IDs to avoid repeats. An empty
                            list or None means no exclusions.

    Returns:
        A tuple of (connections, puzzle_id) where connections is a list of
        connection dicts ready for game_session_service.py:
        [
            {"relationship": "Category Name", "words": ["w1", "w2", "w3", "w4"],
             "guessed": False},
            ...
        ]
        and puzzle_id is the UUID of the puzzle row in Supabase, used to link
        the new game_session back to the pool puzzle it was drawn from.

    Raises:
        PuzzlePoolEmptyError: No approved puzzles exist for this config (or all
                              approved puzzles have already been played).
        ValueError:           config_name doesn't match any puzzle_configs row.
        RuntimeError:         Puzzle exists but has no groups (data integrity issue).
    """
    supabase = _get_client()
    config_id = _get_config_id(supabase, config_name)

    # Call the atomic DB function — returns the UUID of the selected puzzle,
    # or None if the pool is empty / all approved puzzles are excluded.
    rpc_result = supabase.rpc(
        "get_random_approved_puzzle",
        {
            "p_config_id": config_id,
            "p_exclude_ids": exclude_puzzle_ids or [],
        },
    ).execute()

    puzzle_id = rpc_result.data
    if not puzzle_id:
        if exclude_puzzle_ids:
            raise PlayerExhaustedPoolError(
                f"Player has completed all approved puzzles for config '{config_name}'."
            )
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

    # Transform DB shape → the format that game_session_service.py expects.
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

    return connections, puzzle_id


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


def _fetch_puzzle_connections(puzzle_id: str, supabase=None) -> list[dict]:
    """
    Fetches groups + words for any puzzle regardless of status.

    Returns a list of connection dicts compatible with game_session_service:
        [{"relationship": "...", "words": [...], "guessed": False}, ...]

    Raises:
        ValueError: puzzle_id not found or has no groups.
    """
    client = supabase or _get_client()
    result = (
        client.table("puzzle_groups")
        .select("category_name, sort_order, puzzle_words(word, display_text)")
        .eq("puzzle_id", puzzle_id)
        .order("sort_order")
        .execute()
    )
    if not result.data:
        raise ValueError(
            f"Puzzle {puzzle_id} not found or has no groups."
        )
    return [
        {
            "relationship": g["category_name"],
            "words": [pw.get("display_text") or pw["word"] for pw in g["puzzle_words"]],
            "guessed": False,
        }
        for g in result.data
    ]


def get_rejected_puzzles(
    config_name: str = "classic",
    limit: int = 50,
) -> list[dict]:
    """
    Returns rejected puzzles with their content, validation score, and fail reasons.

    Each item includes the puzzle words so you can review them before deciding
    whether to start a review game or leave them rejected.

    Args:
        config_name: Pool config slug to filter by (default "classic").
        limit:       Maximum number of puzzles to return, most recent first.

    Returns:
        List of dicts:
        [
            {
                "puzzle_id":        str,
                "validation_score": float | None,
                "auto_fail_reasons": list[str],
                "warnings":         list[str],
                "created_at":       str,
                "groups": [
                    {"relationship": str, "words": [str, str, str, str]},
                    ...
                ],
            },
            ...
        ]
    """
    supabase = _get_client()
    config_id = _get_config_id(supabase, config_name)

    # Single query: PostgREST resource embedding joins puzzle_groups and puzzle_words
    # server-side, returning nested JSON in one round trip instead of 1+N queries.
    result = (
        supabase.table("puzzles")
        .select(
            "id, validation_score, validation_report, created_at, edited_at, times_served,"
            "puzzle_groups(category_name, sort_order, puzzle_words(word, display_text))"
        )
        .eq("config_id", config_id)
        .eq("status", "rejected")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    puzzles = []
    for row in (result.data or []):
        report = row.get("validation_report") or {}
        groups = sorted(row.get("puzzle_groups") or [], key=lambda g: g["sort_order"])
        puzzles.append({
            "puzzle_id": row["id"],
            "validation_score": row.get("validation_score"),
            "auto_fail_reasons": report.get("auto_fail_reasons", []),
            "warnings": report.get("warnings", []),
            "created_at": row["created_at"],
            "edited_at": row.get("edited_at"),
            "times_served": row.get("times_served", 0),
            "groups": [
                {
                    "relationship": g["category_name"],
                    "words": [pw.get("display_text") or pw["word"] for pw in g["puzzle_words"]],
                }
                for g in groups
            ],
        })

    return puzzles


def get_approved_puzzles(
    config_name: str = "classic",
    limit: int = 50,
) -> list[dict]:
    """
    Returns approved puzzles with their content and validation data.

    Mirrors get_rejected_puzzles() but queries status='approved' and includes
    approved_at so the admin can see when each puzzle entered the pool.

    Args:
        config_name: Pool config slug to filter by (default "classic").
        limit:       Maximum number of puzzles to return, most recent first.

    Returns:
        List of dicts with the same shape as get_rejected_puzzles(), plus
        an optional "approved_at" field.
    """
    supabase = _get_client()
    config_id = _get_config_id(supabase, config_name)

    result = (
        supabase.table("puzzles")
        .select(
            "id, validation_score, validation_report, approved_at, created_at, edited_at, times_served,"
            "puzzle_groups(category_name, sort_order, puzzle_words(word, display_text))"
        )
        .eq("config_id", config_id)
        .eq("status", "approved")
        .order("approved_at", desc=True)
        .limit(limit)
        .execute()
    )

    puzzles = []
    for row in (result.data or []):
        report = row.get("validation_report") or {}
        groups = sorted(row.get("puzzle_groups") or [], key=lambda g: g["sort_order"])
        puzzles.append({
            "puzzle_id": row["id"],
            "validation_score": row.get("validation_score"),
            "auto_fail_reasons": report.get("auto_fail_reasons", []),
            "warnings": report.get("warnings", []),
            "approved_at": row.get("approved_at"),
            "created_at": row["created_at"],
            "edited_at": row.get("edited_at"),
            "times_served": row.get("times_served", 0),
            "groups": [
                {
                    "relationship": g["category_name"],
                    "words": [pw.get("display_text") or pw["word"] for pw in g["puzzle_words"]],
                }
                for g in groups
            ],
        })

    return puzzles


def update_puzzle_content(puzzle_id: str, groups: list[dict]) -> str:
    """
    Mutates an existing puzzle's category names and words in-place.

    Intended for admin use when a puzzle needs to be corrected after it was
    generated. The update is safe to perform on approved puzzles because
    game_sessions store connections as a JSONB snapshot — editing the source
    rows in puzzle_groups/puzzle_words has no effect on existing sessions.

    Steps:
      1. Update puzzle_groups.category_name for each group (matched by sort_order)
      2. Delete all existing puzzle_words for this puzzle
      3. Re-insert fresh word rows from the new word lists
      4. Stamp edited_at = now() and clear stale validation data

    Args:
        puzzle_id: UUID of the puzzle to update.
        groups:    List of dicts in difficulty order (index = sort_order):
                   [{"category_name": str, "words": [str, str, str, str]}, ...]

    Returns:
        ISO timestamp string of the new edited_at value.
    """
    supabase = _get_client()
    edited_at = datetime.now(timezone.utc).isoformat()

    for sort_order, group in enumerate(groups):
        category_name = group["category_name"]
        # Fetch the group row by puzzle_id + sort_order to get its id for word insertion
        group_result = (
            supabase.table("puzzle_groups")
            .select("id")
            .eq("puzzle_id", puzzle_id)
            .eq("sort_order", sort_order)
            .limit(1)
            .execute()
        )
        if not group_result.data:
            raise ValueError(
                f"No group found at sort_order={sort_order} for puzzle {puzzle_id}."
            )
        group_id = group_result.data[0]["id"]

        # Update category name
        supabase.table("puzzle_groups").update({
            "category_name": category_name,
        }).eq("id", group_id).execute()

        # Delete existing words for this group and re-insert fresh ones
        supabase.table("puzzle_words").delete().eq("group_id", group_id).execute()

        word_rows = [
            {
                "group_id": group_id,
                "puzzle_id": puzzle_id,
                "word": word.lower(),
                "display_text": word,
            }
            for word in group["words"]
        ]
        supabase.table("puzzle_words").insert(word_rows).execute()

    # Stamp edited_at and clear stale validation data
    supabase.table("puzzles").update({
        "edited_at": edited_at,
        "validation_score": None,
        "validation_report": None,
    }).eq("id", puzzle_id).execute()

    logger.info("Admin edited puzzle %s content", puzzle_id)
    return edited_at


def create_manual_puzzle(groups: list[dict], config_name: str = "classic") -> str:
    """
    Creates a new puzzle from scratch and immediately approves it.

    Reuses seed_puzzle_to_pool() (status='draft') then immediately calls
    manually_approve_puzzle() so the new puzzle is eligible for serving right away.
    Records generation_model='manual' for audit trail.

    Args:
        groups:      List of dicts [{"category_name": str, "words": [str, ...]}, ...]
                     in difficulty order (index 0 = easiest).
        config_name: Pool config slug (default "classic").

    Returns:
        str: UUID of the newly created puzzle.
    """
    puzzle_data = {
        "config_name": config_name,
        "connections": [
            {"relationship": g["category_name"], "words": g["words"]}
            for g in groups
        ],
    }
    puzzle_id = seed_puzzle_to_pool(puzzle_data, generation_model="manual")
    manually_approve_puzzle(puzzle_id)
    logger.info("Admin manually created puzzle %s (config=%s)", puzzle_id, config_name)
    return puzzle_id


def manually_reject_puzzle(puzzle_id: str) -> None:
    """
    Demotes an approved puzzle back to rejected status.

    Intended for admin use when a puzzle in the approved pool is found to be
    problematic after manual review. The existing validation_score and
    validation_report are preserved for audit purposes.

    Args:
        puzzle_id: UUID of the puzzle to reject (any status accepted).
    """
    supabase = _get_client()

    supabase.table("puzzles").update({
        "status": "rejected",
    }).eq("id", puzzle_id).execute()

    logger.info("Admin manually rejected puzzle %s (human override)", puzzle_id)


def manually_approve_puzzle(puzzle_id: str) -> None:
    """
    Force-approves a puzzle, overriding the validation pipeline decision.

    Intended for human review of borderline or incorrectly rejected puzzles.
    Sets status to 'approved' and records the current timestamp as approved_at.
    The existing validation_score and validation_report are preserved for audit.

    Args:
        puzzle_id: UUID of the puzzle to approve (any status accepted).
    """
    supabase = _get_client()

    supabase.table("puzzles").update({
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", puzzle_id).execute()

    logger.info("Manually approved puzzle %s (human override)", puzzle_id)


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


def reject_puzzle(
    puzzle_id: str,
    validation_report: dict,
    validation_score: float = 0.0,
) -> None:
    """
    Transitions a puzzle to 'rejected', permanently excluding it from the pool.

    Rejected puzzles are never served. The validation_report should explain
    which checks failed so the generation pipeline can be tuned accordingly.
    validation_score is stored even for rejections so quality trends can be
    compared across approved and rejected puzzles.

    Args:
        puzzle_id:         UUID of the puzzle to reject.
        validation_report: Structured dict explaining which checks failed and why.
        validation_score:  Composite quality score at time of rejection (0–1).
    """
    supabase = _get_client()

    supabase.table("puzzles").update({
        "status": "rejected",
        "validation_score": validation_score,
        "validation_report": validation_report,
    }).eq("id", puzzle_id).execute()

    logger.info(
        "Rejected puzzle %s (validation_score=%.3f)", puzzle_id, validation_score
    )
