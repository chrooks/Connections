"""
Game logic module for the Connections game API.

This module contains functions for managing game state, generating game grids,
validating guesses, and performing game-related operations.

Functions:
- generate_game_grid(): Generates the game grid and word relationships.
- validate_game_id(game_id): Validates if a game ID exists.
- validate_guess(game_id, guess): Validates a player's guess against the game's relationships.
- create_new_game(): Creates a new game session.
- get_game_state(game_id): Retrieves the current game state.
- update_game_state(game_id, guess_result): Updates the game state based on a guess result.
- restart_game(game_id): Restarts the game with a new grid and resets the game state.
- shuffle_game_board(game_id): Shuffles the words on the game board.
"""

import random
from os import path
import json
from dal import (
    add_new_game,
    get_game_from_db,
    is_guess_correct,
    reset_game,
    update_game_state,
    check_game_exists,
)
from utils import call_llm_api


def generate_game_grid():
    """
    Generates the game grid and relationships by reading the contents of 'placeholder.json'.

    :return: A tuple containing the game grid (list of words) and the relationships
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

    # Construct the absolute path to the placeholder.json file
    current_dir = path.dirname(__file__)  # Gets the directory where this script is located
    json_path = path.join(
        current_dir, "placeholder.json"
    )  # Constructs the path to the JSON file

    # Load data from placeholder.json
    with open(json_path, "r") as file:
        data = json.load(file)

    grid = []
    relationships = {}
    for relationship, words_list in data.items():
        grid.extend(words_list)
        relationships[relationship] = words_list

    # Shuffle the grid for game variability
    random.shuffle(grid)
    return grid, relationships


def process_guess(game_id, guess):
    """
    Validates the guess and updates the game state by calling the respective functions from dal.py.
    Returns the updated game state and whether the guess was correct.

    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A tuple containing the updated game state and a boolean indicating if the guess was correct.
    """
    is_correct = is_guess_correct(game_id, guess)
    update_game_state(game_id, guess, is_correct)

    return get_game_from_db(game_id), is_correct


def create_new_game():
    """
    Creates a new game session with a generated game grid and relationships, and stores it in the database.

    :return: A tuple containing the game ID and the initial game state.
    """
    grid, relationships = generate_game_grid()

    # Add the new game to the database using the DAL method
    game_id = add_new_game(grid, relationships)

    # Retrieve the newly created game state from the database
    game_state = get_game_from_db(game_id)

    return game_id, game_state


def get_game_state(game_id):
    """
    Retrieves the current game state for the specified game ID.

    :param game_id: The ID of the game session.
    :return: The Game object if the game exists, raises ValueError otherwise.
    """
    return get_game_from_db(game_id)


def restart_game(game_id):
    """
    Restarts the game specified by this id with a new grid and resets the game state.

    :param game_id: The ID of the game session to restart.
    """
    # Check if the game exists
    if not check_game_exists(game_id):
        raise ValueError("No game found with the provided ID.")

    # Generate a new game grid and relationships
    grid, relationships = generate_game_grid()

    # Call the helper function to update the game in the database with the new grid and reset the game state
    return reset_game(game_id, grid, relationships)
