import random
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

# Placeholder for in-memory game state
# In-memory storage for game states; in production, consider using a database.
# TODO: use a database here instead of storing in-memory
games = {}


def call_gpt_api(prompt):
    """
    Simulates calling a GPT-based API to generate words and their connections based on the given prompt.

    This is a mock function for demonstration purposeIntas and returns a hardcoded response.

    :param prompt: The prompt to send to the GPT API.
    :return: A string containing categories and items (words) related to those categories.
    """
    # Mock response for demonstration
    # TODO: actually call the GPT API here
    response = """
    Apple, Banana, Cherry, Date: Fruits
    Python, Java, C++, Rust: Programming Languages
    Everest, Kilimanjaro, Elbrus, Denali: Mountains
    Tesla, Edison, Curie, Newton: Scientists
    """
    return response.strip()


def generate_game_grid():
    """
    Generates the game grid and relationships by reading a prompt from 'prompt.txt',
    calling a GPT API with the prompt, and parsing the API's response.

    :return: A tuple containing the game grid (list of words) and the relationships
             dictionary mapping word tuples to their connection (relationship).
             Returns empty list and dictionary if there's an error reading the file or parsing.
    """
    try:
        # Attempt to open and read the prompt from 'prompt.txt' with UTF-8 encoding
        with open('backend/prompt.txt', 'r', encoding='utf-8') as file:
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

    # Shuffle the grid for game variability
    random.shuffle(grid)

    # Optionally print relationships for debugging/verification
    # print(json.dumps(relationships, indent=4))

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

    relationships = games[game_id]['relationships']
    for words, relation in relationships.items():
        if set(guess) == set(words):
            # Correct guess, remove this relationship from the game state to prevent reuse
            del relationships[words]
            return True, f"Correct! The connection is: {relation}"

    return False, "Incorrect guess. Try again."


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
    Receives a guess from the player and validates it against the game's relationships.
    Updates the game state accordingly based on the guess's validity.

    :return: A JSON response indicating whether the guess was correct or not, 
             and relevant game state information.
    """
    required_fields = ['gameId', 'guess']
    data, error = parse_and_validate_request(required_fields)
    if error:
        return jsonify({"error": error}), 400

    game_id = data['gameId']
    if not validate_game_id(game_id):
        return jsonify({"error": "Invalid game ID."}), 404

    guess = data['guess']

    # Validate the guess format (must be a list of four words)
    if not isinstance(guess, list) or len(guess) != 4:
        return jsonify({"error": "Invalid guess format. A guess should be a list of four words."}), 400

    is_valid, message = validate_guess(game_id, guess)

    if not is_valid:
        games[game_id]['remainingGuesses'] -= 1
        if games[game_id]['remainingGuesses'] <= 0:
            games[game_id]['gameOver'] = True
            return jsonify({"success": False, "message": "Game over!"})

    return jsonify({
        "success": is_valid,
        "message": message,
        "remainingGuesses": games[game_id]['remainingGuesses'],
        "gameOver": games[game_id]['gameOver']
    })


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

    # Use the generate_game_grid method to create a new grid and relationships
    grid, relationships = generate_game_grid()

    # Update the game state with the new grid, reset remaining guesses, and set gameOver to False
    games[game_id] = {
        "grid": grid,
        "relationships": relationships,
        "remainingGuesses": 4,
        "gameOver": False
    }

    # Respond with success message and include the new grid for client-side rendering
    return jsonify({"success": True, "message": "Game restarted.", "gameId": game_id, "grid": grid}), 200


@app.route('/shuffle-board', methods=['POST'])
def shuffle_board():
    """
    Shuffles the words on the current game board for a specified game session.

    This endpoint expects a JSON payload with a 'gameId' key identifying the game
    to shuffle. It randomizes the order of the words in the game's grid while
    preserving the underlying relationships and game state.

    :return: A JSON response containing the shuffled grid for the game session
             or an error message if the game ID is not found.
    """
    required_fields = ['gameId']
    data, error = parse_and_validate_request(required_fields)
    if error:
        return jsonify({"error": error}), 400

    game_id = data['gameId']
    if game_id not in games:
        return jsonify({"error": "Game ID not found."}), 404

    # Shuffle the grid while maintaining the game state
    random.shuffle(games[game_id]['grid'])

    return jsonify({
        "success": True,
        "message": "Board shuffled successfully.",
        "grid": games[game_id]['grid']
    })


if __name__ == '__main__':
    app.run(debug=True)
