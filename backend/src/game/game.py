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
from os import path
import json

logger = logging.getLogger(__name__)

from ..services.game_session_service import (
    add_new_game,
    get_game_from_db,
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


def generate_game_grid() -> "tuple[list[str], list[dict], str | None]":
    """
    Generates the game grid and connections using a pool-first strategy.

    Strategy:
      1. Try to fetch a pre-generated, validated puzzle from the Supabase pool.
         The pool is the primary source once puzzles have been seeded and approved.
      2. Fall back to the static connections.json when the pool is empty (expected
         during local dev before any puzzles are seeded) or unavailable (network
         error, missing env vars, etc.).

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
            get_puzzle_from_pool,
        )

        connections, puzzle_id = get_puzzle_from_pool(config_name="classic")
        grid = []
        for connection in connections:
            grid.extend(connection["words"])

        random.shuffle(grid)
        logger.info("Generated game grid from puzzle pool (%d groups)", len(connections))
        return grid, connections, puzzle_id

    except ImportError:
        # supabase package not installed — silently fall back during early dev
        logger.warning("supabase package not available; using static fallback")
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


def process_guess(game_id: str, guess: "list[str]") -> "tuple[dict, bool, bool, bool, str]":
    """
    Validates the guess and updates the game state by calling the respective functions from game_session_service.py.
    Returns the updated game state, a boolean confirming whether the guess is valid, whether the guess was correct,
    whether the guess was new, and an error message if the guess is invalid.
    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A tuple containing the updated game state,
                                a boolean indicating if the guess was valid,
                                a boolean indicating if the guess was correct,
                                a boolean indicating if the guess was new,
                                and an error message if the guess is invalid.
    """
    is_correct, is_valid, is_new, error_message = check_guess(game_id, guess)
    if not is_valid:
        return None, is_valid, False, is_new, error_message

    update_game_state(game_id, guess, is_correct)
    game_state = get_game_from_db(game_id)
    return game_state, is_valid, is_correct, is_new, ""


def create_new_game(user_id: "str | None" = None) -> dict:
    """
    Creates a new game session with a generated game grid and connections, and stores it in Supabase.

    :param user_id: The Supabase auth user UUID, or None for guest sessions.
    :return: The new game state dict.
    """
    grid, connections, puzzle_id = generate_game_grid()
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


def restart_game(game_id: str) -> dict:
    """
    Restarts the game specified by this id with a new grid and resets the game state.
    Returns the restarted game state.

    :param game_id: The ID of the game session to restart.
    :return: The restarted game state dict.
    """
    grid, connections, puzzle_id = generate_game_grid()
    return reset_game(game_id, grid, connections, puzzle_id=puzzle_id)


def get_all_games_data() -> dict:
    """
    Retrieves the status of all games from the database.

    :return: A dictionary containing the status of all games.
    """
    all_games = get_all_games()
    return {game["gameId"]: game for game in all_games}
