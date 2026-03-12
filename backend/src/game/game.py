"""
Game logic module for the Connections game API.

This module contains functions for managing game state, generating game grids,
validating guesses, and performing game-related operations. It is designed to interact
with the game session service to fetch and update game data as needed.

Functions:
- validate_id(game_id): Validates if a game ID exists.
- generate_game_grid(): Generates the game grid and word connections.
- process_guess(game_id, guess): Processes a guess and updates the game state.
- create_new_game(): Creates a new game session.
- get_game_state(game_id): Retrieves the current game state.
- restart_game(game_id): Restarts the game with a new grid and resets the game state.
- get_all_games_data(): Retrieves the status of all games.
"""

import logging
import random
import threading
from os import path
import json

logger = logging.getLogger(__name__)

# Trigger replenishment when the approved pool drops below this count.
_POOL_LOW_WATER_MARK = 10
# Queue enough jobs to reach this target (halfway to pool_monitor's 50).
_POOL_REPLENISHMENT_TARGET = 30


def _replenish_pool_async(config_name: str) -> None:
    """
    Fire-and-forget pool health check.  Runs in a daemon thread so it never
    blocks the HTTP response.  If approved puzzles have dropped below
    _POOL_LOW_WATER_MARK, queues enough generation jobs to reach
    _POOL_REPLENISHMENT_TARGET.

    All errors are swallowed — this is best-effort monitoring only.
    """
    try:
        from ..services.puzzle_pool_service import get_pool_stats, _get_client

        stats = get_pool_stats(config_name)
        approved = stats.get("approved", 0)

        if approved >= _POOL_LOW_WATER_MARK:
            return  # pool is healthy

        logger.warning(
            "Pool '%s' is low (%d approved < %d threshold) — queueing replenishment jobs",
            config_name, approved, _POOL_LOW_WATER_MARK,
        )

        client = _get_client()
        cfg = (
            client.table("puzzle_configs")
            .select("id")
            .eq("name", config_name)
            .single()
            .execute()
        )
        if not cfg.data:
            logger.warning("Unknown puzzle config '%s' — cannot replenish", config_name)
            return

        needed = max(0, _POOL_REPLENISHMENT_TARGET - approved)
        if needed == 0:
            return

        rows = [{"config_id": cfg.data["id"], "status": "queued"} for _ in range(needed)]
        client.table("puzzle_generation_jobs").insert(rows).execute()
        logger.info("Queued %d replenishment jobs for config '%s'", needed, config_name)

    except Exception:
        logger.warning("Pool replenishment check failed", exc_info=True)

from ..services.game_session_service import (
    add_new_game,
    get_game_from_db,
    get_active_game_for_user,
    get_completed_puzzle_ids_for_user,
    check_guess,
    reset_game,
    update_game_state,
    check_game_exists,
    get_all_games,
)


def validate_id(game_id):
    """
    Validates if a game ID exists in the database.

    :param game_id: The ID of the game to validate.
    :return: True if the game exists, False otherwise.
    """
    return check_game_exists(game_id)


def generate_game_grid(
    user_id: "str | None" = None,
    guest_exclude_ids: "list[str] | None" = None,
) -> "tuple[list[str], list[dict], str | None]":
    """
    Generates the game grid and connections using a pool-first strategy.

    Strategy:
      1. Try to fetch a pre-generated, validated puzzle from the Supabase pool.
         The pool is the primary source once puzzles have been seeded and approved.
         For authenticated users, puzzles they have already completed (WIN or LOSS)
         are excluded so they never receive a repeat.
         For guests, an optional client-supplied exclusion list (sourced from
         localStorage) is used to avoid serving the same puzzle twice.
      2. Fall back to the static connections.json when the pool is empty (expected
         during local dev before any puzzles are seeded) or unavailable (network
         error, missing env vars, etc.).

    :param user_id: The authenticated player's UUID, or None for guests. When
                    provided, already-completed puzzle IDs are fetched and passed
                    to the pool so the player is never served a repeat.
    :param guest_exclude_ids: Optional list of puzzle IDs to exclude for guest
                    sessions. Ignored when user_id is set (auth users use the
                    server-side completed-puzzle list instead).
    :return: A tuple of (grid, connections, puzzle_id) where:
             - grid is a shuffled list of 16 word strings
             - connections is a list of dicts: [{relationship, words, guessed}, ...]
             - puzzle_id is the Supabase UUID of the pool puzzle, or None for the
               static-fallback case
    """
    # --- Pool-first: fetch from Supabase if possible ---
    # Import here so that missing the supabase package (before requirements are
    # installed) raises at call-time rather than crashing the whole module on import.
    try:
        from ..services.puzzle_pool_service import (
            PuzzlePoolEmptyError,
            PlayerExhaustedPoolError,
            get_puzzle_from_pool,
        )

        # Build the exclusion list based on who's playing:
        #   - Auth users: query the DB for their completed puzzle IDs (ground truth).
        #   - Guests: use the client-supplied list from localStorage (best-effort).
        # Errors on the auth path are non-fatal — log and fall through to no exclusions.
        exclude_ids: "list[str]" = []
        if user_id:
            try:
                exclude_ids = get_completed_puzzle_ids_for_user(user_id)
                if exclude_ids:
                    logger.info(
                        "Excluding %d already-completed puzzles for user %s",
                        len(exclude_ids), user_id,
                    )
            except Exception as e:
                logger.warning(
                    "Could not fetch completed puzzle IDs for user %s (%s) — "
                    "serving without exclusions",
                    user_id, e,
                )
        elif guest_exclude_ids:
            exclude_ids = guest_exclude_ids
            logger.info("Guest excluding %d already-completed puzzles", len(exclude_ids))

        connections, puzzle_id = get_puzzle_from_pool(
            config_name="classic",
            exclude_puzzle_ids=exclude_ids,
        )
        grid = []
        for connection in connections:
            grid.extend(connection["words"])

        random.shuffle(grid)
        logger.info("Generated game grid from puzzle pool (%d groups)", len(connections))

        # Non-blocking: check pool level and queue replenishment jobs if needed.
        # Runs in a daemon thread so it never delays the HTTP response.
        threading.Thread(
            target=_replenish_pool_async,
            args=("classic",),
            daemon=True,
        ).start()

        return grid, connections, puzzle_id

    except ImportError:
        # supabase package not installed — silently fall back during early dev
        logger.warning("supabase package not available; using static fallback")
    except PlayerExhaustedPoolError:
        # Player has completed every approved puzzle — propagate so the route
        # can return a "come back later" response instead of serving static JSON.
        raise
    except PuzzlePoolEmptyError:
        # Expected during local development before any puzzles have been seeded
        logger.warning("Puzzle pool is empty — falling back to static connections.json")
    except Exception as e:
        # Unexpected error (bad credentials, network down, etc.) — log and degrade
        logger.warning("Puzzle pool unavailable (%s) — falling back to static JSON", e)

    # --- Static fallback: read from the bundled JSON file ---
    current_dir = path.dirname(__file__)  # directory of this script
    json_path = path.join(current_dir, "../../schemas/connections.json")

    with open(json_path, "r") as file:
        data = json.load(file)

    grid = []
    connections = []

    for connection in data:
        grid.extend(connection["words"])
        connections.append(connection)

    # Shuffle the grid so each game session has a different layout
    random.shuffle(grid)
    return grid, connections, None


def process_guess(game_id: str, guess: "list[str]") -> "tuple[dict, bool, bool, bool, bool, str]":
    """
    Validates the guess and updates the game state by calling the respective functions from game_session_service.py.
    Returns the updated game state, a boolean confirming whether the guess is valid, whether the guess was correct,
    whether the guess was new, whether the guess was one away, and an error message if the guess is invalid.
    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A tuple containing the updated game state,
                                a boolean indicating if the guess was valid,
                                a boolean indicating if the guess was correct,
                                a boolean indicating if the guess was new,
                                a boolean indicating if the guess was one word away from a connection,
                                and an error message if the guess is invalid.
    """
    is_correct, is_valid, is_new, is_one_away, error_message = check_guess(game_id, guess)
    if not is_valid:
        return None, is_valid, False, is_new, False, error_message

    update_game_state(game_id, guess, is_correct)
    game_state = get_game_from_db(game_id)
    return game_state, is_valid, is_correct, is_new, is_one_away, ""


def create_new_game(
    user_id: "str | None" = None,
    guest_exclude_ids: "list[str] | None" = None,
) -> dict:
    """
    Get-or-create: for authenticated users, returns the existing IN_PROGRESS
    game session rather than creating a new one on every call. This is what
    makes the game persist across page refreshes and devices for logged-in users.

    For guests (user_id=None), always creates a fresh session — the frontend
    handles persistence via localStorage for single-device continuity.

    :param user_id: The Supabase auth user UUID, or None for guest sessions.
    :param guest_exclude_ids: Puzzle IDs to skip when picking a puzzle for a guest.
                    Sourced from the guest's localStorage; ignored for auth users.
    :return: The game state dict (existing or newly created).
    """
    if user_id:
        existing_id = get_active_game_for_user(user_id)
        if existing_id:
            logger.info(
                "Resuming existing IN_PROGRESS game %s for user %s",
                existing_id, user_id,
            )
            return get_game_from_db(existing_id)

    grid, connections, puzzle_id = generate_game_grid(
        user_id=user_id,
        guest_exclude_ids=guest_exclude_ids,
    )
    game_id = add_new_game(grid, connections, user_id=user_id, puzzle_id=puzzle_id)
    return get_game_from_db(game_id)


def get_game_state(game_id: str) -> dict:
    """
    Retrieves the current game state for the specified game ID.

    :param game_id: The ID of the game session.
    :return: The game state dict if the game exists, raises ValueError otherwise.
    """
    game_state = get_game_from_db(game_id)
    if game_state is None:
        raise ValueError("No game found with the provided ID.")
    return game_state


def restart_game(game_id: str, user_id: "str | None" = None) -> dict:
    """
    Restarts the game specified by this id with a new grid and resets the game state.
    Returns the restarted game state.

    :param game_id: The ID of the game session to restart.
    :param user_id: The authenticated player's UUID, or None for guests. Passed
                    to generate_game_grid so already-completed puzzles are excluded.
    :return: The restarted game state dict.
    """
    grid, connections, puzzle_id = generate_game_grid(user_id=user_id)
    return reset_game(game_id, grid, connections, puzzle_id=puzzle_id)


def get_all_games_data() -> dict:
    """
    Retrieves the status of all games from the database.

    :return: A dictionary containing the status of all games.
    """
    all_games = get_all_games()
    return {game["gameId"]: game for game in all_games}
