import json
import random
import uuid
from flask import Flask, request, jsonify
app = Flask(__name__)

# Placeholder for in-memory game state
# In-memory storage for game states; in production, consider using a database.
games = {}


def call_gpt_api(prompt):
    # Mock response for demonstration
    response = """
    Apple, Banana, Cherry, Date: Fruits
    Python, Java, C++, Rust: Programming Languages
    Everest, Kilimanjaro, Elbrus, Denali: Mountains
    Tesla, Edison, Curie, Newton: Scientists
    """
    return response.strip()


def generate_game_grid():
    try:
        # Attempt to open and read the prompt from 'prompt.txt'
        with open('backend/prompt.txt', 'r') as file:
            prompt = file.read().strip()
    except FileNotFoundError:
        # Handle the case where 'prompt.txt' does not exist
        print("Error: 'prompt.txt' file not found.")
        return [], {}
    except Exception as e:
        # Handle other potential errors
        print(f"An error occurred while reading 'prompt.txt': {e}")
        return [], {}

    # Simulating a GPT call
    gpt_response = call_gpt_api(prompt)

    # Parsing the GPT response
    sets = gpt_response.split('\n')
    grid = []
    relationships = {}
    for set_line in sets:
        # Splitting the set into words and the relationship, stripping whitespace
        words, relationship = [item.strip()
                               for item in set_line.rsplit(':', 1)]
        words_list = [word.strip() for word in words.split(',')]
        grid.extend(words_list)
        relationships[tuple(words_list)] = relationship

    random.shuffle(grid)
    print(json.dumps(relationships, indent=4))

    return grid, relationships


def validate_game_id(game_id):
    """
    Validates if the provided game_id exists in the games storage.

    :param game_id: The game ID to check.
    :return: True if the game exists, False otherwise.
    """
    return game_id in games


def parse_and_validate_request(required_fields):
    """
    Parses the request JSON payload and validates the presence of required fields.

    :param required_fields: A list of strings representing required field names.
    :return: A tuple of (data, error). If successful, data contains the parsed JSON 
             and error is None. On failure, data is None and error contains an error message.
    """
    try:
        data = request.get_json(force=True)
        if not data:
            raise ValueError("Request payload is empty")

        missing_fields = [
            field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(
                f"Missing required fields: {', '.join(missing_fields)}")

        return data, None
    except Exception as e:
        return None, str(e)


@app.route('/generate-grid', methods=['POST'])
def generate_grid():
    """
    Generates a new game grid with randomly selected words upon receiving a POST request.
    This creates a new game session and returns a unique game ID along with the initial grid state.

    If an error occurs during grid generation (e.g., the prompt file is missing), 
    the endpoint will return an error message.
    """
    game_id = str(uuid.uuid4())
    grid, relationships = generate_game_grid()

    # Check if the grid generation was successful
    if not grid or not relationships:
        # Since generate_game_grid() returns empty lists in case of an error,
        # we handle this by returning an appropriate error response.
        return jsonify({"error": "Failed to generate the game grid. Please check the server configuration or prompt file."}), 500

    games[game_id] = {
        "grid": grid,
        "relationships": relationships,
        "remainingGuesses": 4,
        "gameOver": False
    }

    # Return the newly created game ID and the initial grid
    return jsonify({"gameId": game_id, "grid": grid}), 201


@app.route('/submit-guess', methods=['POST'])
def submit_guess():
    """
    Processes a player's guess, updating the game state accordingly.
    Requires JSON payload with gameId and the player's guess.
    """
    required_fields = ['gameId', 'guess']
    data, error = parse_and_validate_request(required_fields)
    if error:
        return jsonify({"error": error}), 400

    game_id = data['gameId']
    if not validate_game_id(game_id):
        return jsonify({"error": "Invalid game ID."}), 404

    guess = data['guess']
    # TODO: Implement guess validation logic

    # Placeholder for guess validation result
    is_correct = True

    # Update game state based on guess validation result
    # This is simplified; actual implementation needed
    if is_correct:
        return jsonify({"success": True, "message": "Correct guess!"})
    else:
        games[game_id]['remainingGuesses'] -= 1
        if games[game_id]['remainingGuesses'] <= 0:
            games[game_id]['gameOver'] = True
            return jsonify({"success": False, "message": "Game over!"})
        return jsonify({"success": False, "message": "Incorrect guess. Try again."})


@app.route('/game-status', methods=['GET'])
def game_status():
    """
    Returns the current status of a game, including the grid, remaining guesses, and game over flag.
    Requires gameId as a query parameter.
    """
    game_id = request.args.get('gameId')
    if not game_id or not validate_game_id(game_id):
        return jsonify({"error": "Invalid or missing game ID."}), 404

    return jsonify({
        "grid": games[game_id]["grid"],
        "remainingGuesses": games[game_id]["remainingGuesses"],
        "gameOver": games[game_id]["gameOver"]
    })


@app.route('/restart-game', methods=['POST'])
def restart_game():
    """
    Restarts the game with a new grid, resetting remaining guesses.
    Requires JSON payload with gameId.
    """
    required_fields = ['gameId']
    data, error = parse_and_validate_request(required_fields)
    if error:
        return jsonify({"error": error}), 400

    game_id = data['gameId']
    if not validate_game_id(game_id):
        return jsonify({"error": "Invalid game ID."}), 404

    # TODO: Implement game reset logic similar to generate_grid
    games[game_id] = {
        "grid": [],  # TODO: Generate new grid logic
        "remainingGuesses": 4,
        "gameOver": False
    }

    return jsonify({"success": True, "message": "Game restarted."})


if __name__ == '__main__':
    app.run(debug=True)
