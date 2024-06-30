"""
This module, 'routes.py', serves as the core interface for the Connections game API, defining and managing all the necessary API endpoints for game interaction.

Detailed Endpoint Descriptions:
- POST /generate-grid: Initiates a new game session by generating a fresh game grid.
- POST /submit-guess: Accepts and evaluates a player's guess, comparing it to established game connections.
- GET /game-status: Provides the current status and progress of an ongoing game session.
- POST /restart-game: Resets an existing game with a new grid, effectively starting a new game session.
- GET /all-games: Retrieves data for all game sessions.


Associated Functions:
- generate_grid(): Constructs a new game grid and initiates a game session.
- submit_guess(): Processes a player's guess and checks its accuracy against the game's connections.
- game_status(): Fetches and returns the current state of a game session.
- restart_game_route(): Resets and starts a new game with a fresh grid.
- get_all_game_data(): Retrieves data for all game sessions.
"""

from flask import Blueprint, request
from ...game.game import (
    create_new_game,
    get_game_state,
    get_all_games_data,
    restart_game,
    process_guess,
    validate_id,
)
from ...services.utils import parse_and_validate_request, create_response

api_bp = Blueprint("connections", __name__)


@api_bp.route("/generate-grid", methods=["GET"])
def generate_grid():
    """
    Generates a new game grid with randomly selected words upon receiving a POST request.
    This creates a new game session and returns a unique game ID along with the initial grid state,
    mistakes left, previous guesses, game over status, and connections.

    If an error occurs during grid generation, the endpoint will return an error message.
    """
    game = create_new_game()

    if not game:
        return create_response(error="Failed to generate the game grid.", status_code=500)

    return create_response(
        data={"gameId": game.id},
        status_code=201,
    )


@api_bp.route("/submit-guess", methods=["POST"])
def submit_guess():
    """
    Receives a guess from the player and validates it against the game's connections.
    Updates the game state accordingly based on the guess's validity.

    :return: A JSON response indicating whether the guess was correct or not,
             and relevant game state information.
    """
    required_fields = ["gameId", "guess"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    # Validate the game id
    game_id = data["gameId"]
    if not validate_id(game_id):
        return create_response(error="Invalid game ID.", status_code=404)
    guess = data["guess"]

    # Validate the guess format (must be a list of four words)
    if not isinstance(guess, list) or len(guess) != 4:
        return create_response(
            error="Invalid guess format. A guess should be a list of four words.", status_code=400
        )

    # Process the guess and update the game state
    game_state, is_valid, is_correct, is_new = process_guess(game_id, guess)
    if not is_valid:
        return create_response(error="Invalid guess.", status_code=400)

    game_state.update({"isCorrect": is_correct, "isNewGuess": is_new})
    return create_response(data=game_state)


@api_bp.route("/game-status", methods=["POST"])
def game_status():
    """
    Returns the current status of a game, including the grid, mistakes left, and game over flag.
    Requires gameId in the JSON payload.
    """
    required_fields = ["gameId"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    # Validate the game id
    game_id = data["gameId"]
    if not validate_id(game_id):
        return create_response(error="Invalid game ID.", status_code=404)

    # Get the game state
    game = get_game_state(game_id)

    return create_response(data=game.to_state())


@api_bp.route("/restart-game", methods=["POST"])
def restart_game():
    """
    Restarts the game with a new grid, resetting mistakes left.
    Requires JSON payload with gameId.
    """
    required_fields = ["gameId"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    # Validate the game id
    game_id = data["gameId"]
    if not validate_id(game_id):
        return create_response(error="Invalid game ID.", status_code=404)

    game = restart_game(game_id)

    return create_response(data=game.to_state())


@api_bp.route("/get-game-data", methods=["GET"])
def get_all_game_data():
    """
    Returns the game statuses of all games in the database.
    """
    games_data = get_all_games_data()

    return create_response(data={"games": games_data})
