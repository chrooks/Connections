"""
Game logic module for the Connections game API.

This module contains functions for managing game state, generating game grids,
validating guesses, and performing game-related operations. It is designed to interact
with the database layer to fetch and update game data as needed.

Functions:
- validate_id(game_id): Validates if a game ID exists.
- generate_game_grid(): Generates the game grid and word connections.
- process_guess(game_id, guess): Processes a guess and updates the game state.
- create_new_game(): Creates a new game session.
- get_game_state(game_id): Retrieves the current game state.
- restart_game(game_id): Restarts the game with a new grid and resets the game state.
- get_all_games_data(): Retrieves the status of all games.
"""

import random
from os import path
import json

from backend.src.models import ConnectionsGame
from .dal import (
    add_new_game,
    get_game_from_db,
    check_guess,
    reset_game,
    update_game_state,
    check_game_exists,
    get_all_games,
)

# from utils import call_llm_api


def validate_id(game_id):
    """
    Validates if a game ID exists in the database.

    :param game_id: The ID of the game to validate.
    :return: True if the game exists, False otherwise.
    """
    return check_game_exists(game_id)


def generate_game_grid():
    """
    Generates the game grid and connections by reading the contents of 'placeholder.json'.

    :return: A tuple containing the game grid (list of words) and the connections
             dictionary mapping word tuples to their connection (relationship).
    """
    # Commenting out the previous functionality
    # try:
    #     # Attempt to open and read the prompt from 'prompt.txt' with UTF-8 encoding
    #     with open("backend/prompt.txt", "r", encoding="utf-8") as file:
    #         prompt = file.read().strip()
    # except FileNotFoundError:
    #     # Handle the case where 'prompt.txt' does not exist
    #     print("Error: 'prompt.txt' file not found.")
    #     return [], {}
    # except Exception as e:
    #     # Handle other potential errors
    #     print(f"An error occurred while reading 'prompt.txt': {e}")
    #     return [], {}

    # # Simulating a LLM call
    # llm_response = call_llm_api(prompt)

    # # Parsing the LLM response
    # sets = llm_response.split("\n")

    # TODO: Replace with more sophisticated logic using an LLM
    # Construct the absolute path to the placeholder.json file
    current_dir = path.dirname(__file__)  # Gets the directory where this script is located
    json_path = path.join(
        current_dir, "../schemas/connections.json"
    )  # Constructs the path to the JSON file

    # Load data from placeholder.json
    with open(json_path, "r") as file:
        data = json.load(file)

    grid = []
    connections = []

    for connection in data:
        grid.extend(connection["words"])
        connections.append(connection)

    # Shuffle the grid for game variability
    random.shuffle(grid)
    return grid, connections


def process_guess(game_id: str, guess: "list[str]") -> "tuple[dict, bool, bool, bool]":
    """
    Validates the guess and updates the game state by calling the respective functions from dal.py.
    Returns the updated game game state, a boolean confirming whether the guess is valid, whether the guess was correct,
    and whether the guess was new.
    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A tuple containing the updated game state,
                                a boolean indicating if the guess was valid,
                                a boolean indicating if the guess was correct,
                                and a boolean indicating if the guess was new.
    """
    is_correct, is_valid, is_new = check_guess(game_id, guess)
    if not is_valid:
        return None, is_valid, False, is_new

    update_game_state(game_id, guess, is_correct)
    game_state = get_game_from_db(game_id)
    return game_state, is_valid, is_correct, is_new


def create_new_game() -> "ConnectionsGame":
    """
    Creates a new game session with a generated game grid and connections, and stores it in the database.

    :return: The newly created ConnectionsGame object.
    """
    grid, connections = generate_game_grid()

    # Add the new game to the database using the DAL method
    game_id = add_new_game(grid, connections)

    # Retrieve the newly created game state from the database
    game = get_game_from_db(game_id)

    return game


def get_game_state(game_id: str) -> dict:
    """
    Retrieves the current game state for the specified game ID.

    :param game_id: The ID of the game session.
    :return: The Game object if the game exists, raises ValueError otherwise.
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
    :return: The restarted game state.
    """
    # Generate a new game grid and connections
    grid, connections = generate_game_grid()

    # Call the helper function to update the game in the database with the new grid and reset the game state
    return reset_game(game_id, grid, connections)


def get_all_games_data() -> dict:
    """
    Retrieves the status of all games from the database.

    :return: A dictionary containing the status of all games.
    """
    all_games = get_all_games()
    games_data = {}
    for game in all_games:
        games_data[game.id] = game.to_state()
    return games_data


