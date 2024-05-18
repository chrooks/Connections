"""
API routes module for the Connections game API.

This module defines the API endpoints and handles incoming requests related to the game.

Routes:
- /generate-grid (POST): Generates a new game grid and creates a game session.
- /submit-guess (POST): Receives a player's guess and validates it against the game's relationships.
- /game-status (GET): Returns the current status of a game.
- /restart-game (POST): Restarts the game with a new grid and resets the game state.
- /shuffle-board (POST): Shuffles the words on the game board for a specified game session.

Functions:
- generate_grid(): Handles the generation of a new game grid and creates a game session.
- submit_guess(): Receives a player's guess and validates it against the game's relationships.
- game_status(): Returns the current status of a game.
- restart_game_route(): Restarts the game with a new grid and resets the game state.
- shuffle_board(): Shuffles the words on the game board for a specified game session.
"""
from flask import Blueprint, request
from .game import (
    create_new_game,
    get_game_state,
    update_game_state,
    restart_game,
    shuffle_game_board,
    is_guess_correct,
)
from .utils import parse_and_validate_request, create_response

api_bp = Blueprint("connections", __name__)



@api_bp.route("/generate-grid", methods=["POST"])
def generate_grid():
    """
    Generates a new game grid with randomly selected words upon receiving a POST request.
    This creates a new game session and returns a unique game ID along with the initial grid state.

    If an error occurs during grid generation, the endpoint will return an error message.
    """
    game_id, game_state = create_new_game()

    if not game_state:
        return create_response(error="Failed to generate the game grid.", status_code=500)

    return create_response(data={"gameId": game_id, "grid": game_state["grid"]}, status_code=201)


@api_bp.route("/submit-guess", methods=["POST"])
def submit_guess():
    """
    Receives a guess from the player and validates it against the game's relationships.
    Updates the game state accordingly based on the guess's validity.

    :return: A JSON response indicating whether the guess was correct or not,
             and relevant game state information.
    """
    required_fields = ["gameId", "guess"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    game_id = data["gameId"]
    guess = data["guess"]

    game_state = get_game_state(game_id)
    if not game_state:
        return create_response(error="Invalid game ID.", status_code=404)

    # Validate the guess format (must be a list of four words)
    if not isinstance(guess, list) or len(guess) != 4:
        return create_response(
            error="Invalid guess format. A guess should be a list of four words.", status_code=400
        )

    guess_result = is_guess_correct(game_id, guess)
    update_game_state(game_id, guess_result)

    is_correct, message = guess_result
    game_over = game_state["gameOver"]

    if game_over:
        return create_response(data={"success": False, "message": "Game over!"})

    return create_response(
        data={
            "success": is_correct,
            "message": message,
            "remainingGuesses": game_state["remainingGuesses"],
            "gameOver": game_over,
        }
    )


@api_bp.route("/game-status", methods=["GET"])
def game_status():
    """
    Returns the current status of a game, including the grid, remaining guesses, and game over flag.
    Requires gameId as a query parameter.
    """
    game_id = request.args.get("gameId")
    game_state = get_game_state(game_id)

    if not game_state:
        return create_response(error="Invalid or missing game ID.", status_code=404)

    return create_response(
        data={
            "grid": game_state["grid"],
            "remainingGuesses": game_state["remainingGuesses"],
            "gameOver": game_state["gameOver"],
        }
    )


@api_bp.route("/restart-game", methods=["POST"])
def restart_game_route():
    """
    Restarts the game with a new grid, resetting remaining guesses.
    Requires JSON payload with gameId.
    """
    required_fields = ["gameId"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    game_id = data["gameId"]
    game_state = restart_game(game_id)

    if not game_state:
        return create_response(error="Invalid game ID.", status_code=404)

    return create_response(
        data={
            "success": True,
            "message": "Game restarted.",
            "gameId": game_id,
            "grid": game_state["grid"],
        }
    )
