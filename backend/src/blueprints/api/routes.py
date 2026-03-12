"""
This module, 'routes.py', serves as the core interface for the Connections game API, defining and managing all the necessary API endpoints for game interaction.

Detailed Endpoint Descriptions:
- GET /generate-grid: Initiates a new game session by generating a fresh game grid.
- POST /submit-guess: Accepts and evaluates a player's guess, comparing it to established game connections.
- POST /game-status: Provides the current status and progress of an ongoing game session.
- POST /restart-game: Resets an existing game with a new grid, effectively starting a new game session.
- GET /get-game-data: Retrieves data for all game sessions.


Associated Functions:
- generate_grid(): Constructs a new game grid and initiates a game session.
- submit_guess(): Processes a player's guess and checks its accuracy against the game's connections.
- game_status(): Fetches and returns the current state of a game session.
- restart_game_route(): Resets and starts a new game with a fresh grid.
- get_all_game_data(): Retrieves data for all game sessions.
"""

from flask import Blueprint, jsonify, request, g
from ...game.game import (
    create_new_game,
    get_game_state,
    get_all_games_data,
    process_guess,
    validate_id,
    restart_game,
)
from ...services.game_session_service import (
    record_completion_time,
    forfeit_game,
    get_user_stats,
    get_user_history,
    transfer_guest_data,
)
from ...services.puzzle_pool_service import PlayerExhaustedPoolError
from ...auth.middleware import get_optional_user_id, require_auth
from ...services.utils import parse_and_validate_request, create_response

api_bp = Blueprint("connections", __name__)


@api_bp.route("/generate-grid", methods=["GET"])
def generate_grid():
    """
    Generates a new game grid with randomly selected words upon receiving a GET request.
    This creates a new game session and returns a unique game ID along with the initial grid state,
    mistakes left, previous guesses, game over status, and connections.

    If an authenticated user token is present it is extracted and linked to the session;
    guest requests (no token) create an unowned session.
    """
    user_id = get_optional_user_id()

    # Guests may supply a comma-separated list of already-completed puzzle IDs via
    # the ?exclude= query param so the pool skips them — mirrors the server-side
    # exclusion used for authenticated users.  Auth users ignore this param since
    # their exclusion list is derived from the database.
    guest_exclude: "list[str]" = []
    if not user_id:
        raw_exclude = request.args.get("exclude", "")
        if raw_exclude:
            guest_exclude = [pid.strip() for pid in raw_exclude.split(",") if pid.strip()]

    try:
        game = create_new_game(user_id=user_id, guest_exclude_ids=guest_exclude or None)
    except PlayerExhaustedPoolError:
        return jsonify({"error": "You've completed all available puzzles! Check back soon for more.", "code": "POOL_EXHAUSTED"}), 503

    if not game:
        return create_response(error="Failed to generate the game grid.", status_code=500)

    return create_response(
        data={"gameId": game["gameId"]},
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
    game_state, is_valid, is_correct, is_new, is_one_away, error_message = process_guess(game_id, guess)
    if not is_valid:
        return create_response(error="Invalid guess: " + error_message, status_code=400)

    response_data = {
        "gameState": {
            "mistakesLeft": game_state["mistakesLeft"],
            "status": game_state["status"],
            "guessedConnections": [connection["guessed"] for connection in game_state["connections"]],
        },
        "isCorrect": is_correct,
        "isNewGuess": is_new,
        "isOneAway": is_one_away,
    }
    return create_response(data=response_data)


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

    game = get_game_state(game_id)
    return create_response(data=game)


@api_bp.route("/restart-game", methods=["POST"])
def restart():
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

    user_id = get_optional_user_id()
    try:
        game = restart_game(game_id, user_id=user_id)
    except PlayerExhaustedPoolError:
        return jsonify({"error": "You've completed all available puzzles! Check back soon for more.", "code": "POOL_EXHAUSTED"}), 503
    return create_response(data=game)


@api_bp.route("/forfeit-game", methods=["POST"])
def forfeit():
    """
    Ends an IN_PROGRESS game as a forfeit (voluntary give-up).
    Sets status=LOSS and marks forfeited=True on the session row.

    Requires JSON payload: { gameId }
    """
    required_fields = ["gameId"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    game_id = data["gameId"]
    if not validate_id(game_id):
        return create_response(error="Invalid game ID.", status_code=404)

    success = forfeit_game(game_id)
    if not success:
        return create_response(error="Game cannot be forfeited (not IN_PROGRESS).", status_code=409)

    return create_response(data={"forfeited": True})


@api_bp.route("/record-completion-time", methods=["POST"])
def record_time():
    """
    Records the elapsed time (in seconds) for a completed game session.
    The frontend calls this once immediately after the game ends.

    Requires JSON payload: { gameId, timeSeconds }
    """
    required_fields = ["gameId", "timeSeconds"]
    data, error = parse_and_validate_request(required_fields)
    if error:
        return create_response(error=error, status_code=400)

    game_id = data["gameId"]
    if not validate_id(game_id):
        return create_response(error="Invalid game ID.", status_code=404)

    time_seconds = data["timeSeconds"]
    if not isinstance(time_seconds, int) or time_seconds < 0:
        return create_response(error="timeSeconds must be a non-negative integer.", status_code=400)

    record_completion_time(game_id, time_seconds)
    return create_response(data={"recorded": True})


@api_bp.route("/get-game-data", methods=["GET"])
def get_all_game_data():
    """
    Returns the game statuses of all games in the database.
    """
    games_data = get_all_games_data()
    return create_response(data={"games": games_data})


@api_bp.route("/user/stats", methods=["GET"])
@require_auth
def user_stats():
    """
    Returns aggregate play stats for the authenticated user:
    wins, losses, forfeits, and average completion time (wins only).
    """
    stats = get_user_stats(g.user_id)
    return create_response(data=stats)


@api_bp.route("/user/history", methods=["GET"])
@require_auth
def user_history():
    """
    Returns all completed game sessions for the authenticated user,
    ordered newest first. Forfeited games appear with outcome='FORFEIT'.
    """
    history = get_user_history(g.user_id)
    return create_response(data={"history": history})


@api_bp.route("/claim-guest-data", methods=["POST"])
@require_auth
def claim_guest_data():
    """
    Transfers guest session data to the authenticated user's account after
    sign-up or sign-in.  Two operations:

      1. Claim active game — sets user_id on the unclaimed game_sessions row so
         the user can continue their in-progress game. Skipped if the user
         already has an active game.

      2. Record completed-puzzle exclusions — inserts the puzzle IDs the guest
         already played into user_puzzle_exclusions so the pool never re-serves
         them to this user.

    Body:
      { "activeGameId": "<uuid>" | null,
        "completedPuzzleIds": ["<uuid>", ...] }
    """
    data = request.get_json(silent=True) or {}
    active_game_id = data.get("activeGameId")
    completed_puzzle_ids = data.get("completedPuzzleIds", [])

    # Basic validation: completedPuzzleIds must be a list of strings
    if not isinstance(completed_puzzle_ids, list) or not all(
        isinstance(pid, str) for pid in completed_puzzle_ids
    ):
        return create_response(error="completedPuzzleIds must be a list of strings", status_code=400)

    result = transfer_guest_data(
        user_id=g.user_id,
        active_game_id=active_game_id if isinstance(active_game_id, str) else None,
        completed_puzzle_ids=completed_puzzle_ids,
    )
    return create_response(data=result)
