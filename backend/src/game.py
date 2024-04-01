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
import uuid
from .utils import call_llm_api

# In-memory storage for game states; in production, consider using a database.
games = {}


def generate_game_grid():
    """
    Generates the game grid and relationships by reading a prompt from 'prompt.txt',
    calling a LLM API with the prompt, and parsing the API's response.

    :return: A tuple containing the game grid (list of words) and the relationships
             dictionary mapping word tuples to their connection (relationship).
             Returns empty list and dictionary if there's an error reading the file or parsing.
    """
    try:
        # Attempt to open and read the prompt from 'prompt.txt' with UTF-8 encoding
        with open("backend/prompt.txt", "r", encoding="utf-8") as file:
            prompt = file.read().strip()
    except FileNotFoundError:
        # Handle the case where 'prompt.txt' does not exist
        print("Error: 'prompt.txt' file not found.")
        return [], {}
    except Exception as e:
        # Handle other potential errors
        print(f"An error occurred while reading 'prompt.txt': {e}")
        return [], {}

    # Simulating a LLM call
    llm_response = call_llm_api(prompt)

    # Parsing the LLM response
    sets = llm_response.split("\n")
    grid = []
    relationships = {}
    for set_line in sets:
        # Splitting the set into words and the relationship, stripping whitespace
        words, relationship = [item.strip() for item in set_line.rsplit(":", 1)]
        words_list = [word.strip() for word in words.split(",")]
        grid.extend(words_list)
        relationships[tuple(words_list)] = relationship

    # Shuffle the grid for game variability
    random.shuffle(grid)

    return grid, relationships


def validate_game_id(game_id):
    """
    Validates if the provided game_id exists in the games storage.

    :param game_id: The game ID to check.
    :return: True if the game exists, False otherwise.
    """
    return game_id in games


def validate_guess(game_id, guess):
    """
    Validates whether the provided guess (a list of four words) forms a valid relationship
    as per the game's definitions.

    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A tuple (is_valid, message). `is_valid` is a boolean indicating whether the guess was valid.
             `message` provides feedback or the relationship if the guess is correct.
    """
    # Ensure the game exists and the guess matches a known relationship
    if validate_game_id(game_id):
        return False, "Game ID not found."

    relationships = games[game_id]["relationships"]
    for words, relation in relationships.items():
        if set(guess) == set(words):
            # Correct guess, remove this relationship from the game state to prevent reuse
            del relationships[words]
            return True, f"Correct! The connection is: {relation}"

    return False, "Incorrect guess. Try again."


def create_new_game():
    """
    Creates a new game session with a generated game grid and relationships.

    :return: A tuple containing the game ID and the initial game state.
    """
    game_id = str(uuid.uuid4())
    grid, relationships = generate_game_grid()

    game_state = {
        "grid": grid,
        "relationships": relationships,
        "remainingGuesses": 4,
        "gameOver": False,
    }

    games[game_id] = game_state

    return game_id, game_state


def get_game_state(game_id):
    """
    Retrieves the current game state for the specified game ID.

    :param game_id: The ID of the game session.
    :return: The game state dictionary if the game exists, None otherwise.
    """
    if validate_game_id(game_id):
        return games[game_id]
    return None


def update_game_state(game_id, guess_result):
    """
    Updates the game state based on the result of a guess.

    :param game_id: The ID of the game session.
    :param guess_result: A tuple containing the validity of the guess and the corresponding message.
    """
    if validate_game_id(game_id):
        game_state = games[game_id]
        is_valid, message = guess_result

        if not is_valid:
            game_state["remainingGuesses"] -= 1
            if game_state["remainingGuesses"] <= 0:
                game_state["gameOver"] = True


def restart_game(game_id):
    """
    Restarts the game with a new grid and resets the game state.

    :param game_id: The ID of the game session to restart.
    :return: The updated game state with the new grid and reset values.
    """
    if validate_game_id(game_id):
        grid, relationships = generate_game_grid()
        game_state = {
            "grid": grid,
            "relationships": relationships,
            "remainingGuesses": 4,
            "gameOver": False,
        }
        games[game_id] = game_state
        return game_state
    return None


def shuffle_game_board(game_id):
    """
    Shuffles the words on the game board while preserving the game state.

    :param game_id: The ID of the game session.
    :return: The updated game state with the shuffled grid.
    """
    if validate_game_id(game_id):
        game_state = games[game_id]
        random.shuffle(game_state["grid"])
        return game_state
    return None
