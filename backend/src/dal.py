from models import db, ConnectionsGame, GameStatus
from sqlalchemy.ext.mutable import MutableDict


def add_new_game(grid, connections):
    """
    Adds a new game to the database.
    """
    new_game = ConnectionsGame(
        grid=grid,
        connections=connections,
        mistakes_left=4,
        previous_guesses=[],
        status=GameStatus.IN_PROGRESS,
    )
    db.session.add(new_game)
    db.session.commit()
    return new_game.id


def check_game_exists(game_id):
    """
    Checks if a game with the given ID exists in the database.
    """
    return ConnectionsGame.query.filter_by(id=game_id).first() is not None


def get_game_from_db(game_id):
    """
    Retrieves a game from the database using the game ID after checking its existence.

    :param game_id: The ID of the game to retrieve.
    :return: The Game object if found, with connections converted to MutableDict.
    :raises ValueError: If no game is found with the provided ID.
    """
    # Check if the game with the specified ID exists in the database
    if not check_game_exists(game_id):
        return None  # Return None if the game does not exist
    
    # Retrieve the game object from the database
    game = ConnectionsGame.query.filter_by(id=game_id).first()
    
    # If the game object is found, convert its connections to MutableDict
    if game:
        # Convert each connection dictionary in the list to a MutableDict
        # This allows SQLAlchemy to track changes to the dictionary contents
        game.connections = [MutableDict.coerce(key, conn) for key, conn in enumerate(game.connections)]
    
    # Return the game object
    return game


def update_game_state(game_id, guess, is_correct):
    """
    Updates the game state based on the result of a guess, adding the guess to previous guesses,
    decrementing the number of guesses if the guess was incorrect, and updating the guessed status
    of the connection if the guess was correct.

    :param game_id: The ID of the game session.
    :param guess: The guess made by the player.
    :param is_correct: A boolean indicating whether the guess was valid.
    """
    game = get_game_from_db(game_id)

    # Check if the current guess has already been made
    if guess in game.previous_guesses:
        # If the guess has already been made, do not modify the game state
        return

    # Add the new guess to the list of previous guesses
    game.previous_guesses.append(guess)

    print("Before update:", [conn["guessed"] for conn in game.connections])
    # Update logic here

    # If the guess is incorrect, decrement the number of mistakes left
    if not is_correct:
        game.mistakes_left -= 1
    else:
        # If the guess is correct, update the guessed status of the corresponding connection
        for connection in game.connections:
            if set(guess) == set(connection["words"]):
                connection["guessed"] = True
                break

    print("After update:", [conn["guessed"] for conn in game.connections])

    check_game_over(game)

    # Save the updated game state to the database
    # flag_modified(game, "connections")
    db.session.commit()


def check_game_over(game):
    """
    Evaluates the game's status based on the remaining mistakes and win conditions.

    If the number of mistakes left is zero, the game status is set to LOSS.
    If all conditions for a win are met, the game status is set to WIN.
    Otherwise, the game remains IN PROGRESS.

    The game status is then committed to the database.

    :param game: The game object whose status is to be evaluated.
    """
    if game.mistakes_left <= 0:
        game.status = GameStatus.LOSS
    elif all_conditions_for_win_met(game):
        game.status = GameStatus.WIN
    else:
        game.status = GameStatus.IN_PROGRESS
    db.session.commit()


def all_conditions_for_win_met(game):
    """
    Checks if all conditions for a win are met in the game.

    :param game: The game object to check.
    :return: True if all connections have been guessed correctly, False otherwise.
    """
    # Check if all connections have been guessed
    return all(connection["guessed"] for connection in game.connections)


def is_guess_correct(game_id, guess):
    """
    Determines if the guess is correct and valid based on the game's relationship definitions and rules.

    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A tuple (is_correct, is_valid) where:
        - is_correct is a boolean indicating if the guess is correct.
        - is_valid is a boolean indicating if the guess is valid.
    """

    game = get_game_from_db(game_id)

    if game is None:
        raise ValueError("Game not found with the provided game ID.")

    # If the game is not in progress, return False for both is_correct and is_valid
    if game.status != GameStatus.IN_PROGRESS:
        return False, False

    # Check if the guess is valid
    is_valid = (
        len(guess) == 4
        and all(word in game.grid for word in guess)
        and len(set(guess)) == 4  # Ensure no duplicate words in the guess
        and guess not in game.previous_guesses
    )

    # Check if the guess is correct
    is_correct = False
    if is_valid:
        connections = game.connections
        for connection in connections:
            if set(guess) == set(connection["words"]):
                is_correct = True
                break

    return is_correct, is_valid


def reset_game(game_id, grid, connections):
    """
    Resets the game with a new grid and connections, updating the game state in the database.

    :param game_id: The ID of the game session to reset.
    :param grid: The new list of words for the game grid.
    :param connections: The new connections dictionary.
    :return: The updated game state.
    """
    game = get_game_from_db(game_id)

    game.grid = grid
    game.connections = connections
    game.previous_guesses = []
    game.mistakes_left = 4
    game.status = GameStatus.IN_PROGRESS
    db.session.commit()

    return game


def get_all_games():
    """
    Retrieves all game data from the database.

    :return: A list of all game objects.
    """
    return ConnectionsGame.query.all()
