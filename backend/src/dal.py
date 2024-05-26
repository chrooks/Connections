from models import db, Game


def add_new_game(grid, relationships):
    """
    Adds a new game to the database.
    """
    new_game = Game(
        grid=grid,
        relationships=relationships,
        mistakes_left=4,
        previous_guesses=[],
        game_over=False,
    )
    db.session.add(new_game)
    db.session.commit()
    return new_game.id


def check_game_exists(game_id):
    """
    Checks if a game with the given ID exists in the database.
    """
    return Game.query.filter_by(id=game_id).first() is not None


def get_game_from_db(game_id):
    """
    Retrieves a game from the database using the game ID after checking its existence.

    :param game_id: The ID of the game to retrieve.
    :return: The Game object if found.
    :raises ValueError: If no game is found with the provided ID.
    """
    if not check_game_exists(game_id):
        raise ValueError("No game found with the provided ID.")
    return Game.query.filter_by(id=game_id).first()


def update_game_state(game_id, guess, is_correct):
    """
    Updates the game state based on the result of a guess, adding the guess to previous guesses,
    and decrementing the number of guesses if the guess was incorrect.

    :param game_id: The ID of the game session.
    :param guess: The guess made by the player.
    :param is_correct: A boolean indicating whether the guess was valid.
    """
    game = get_game_from_db(game_id)

    # Retrieve the list of previous guesses from the game state
    previous_guesses = game.previous_guesses

    # Check if the current guess has already been made
    if guess in previous_guesses:
        # If the guess has already been made, do not modify the game state
        return

    # Add the new guess to the list of previous guesses
    previous_guesses.append(guess)
    game.previous_guesses = previous_guesses

    # If the guess is incorrect, decrement the number of mistakes left
    if not is_correct:
        game.mistakes_left -= 1

    # Save the updated game state to the database
    db.session.commit()


def is_guess_correct(game_id, guess):
    """
    Determines if the guess is correct based on the game's relationship definitions.

    :param game_id: The ID of the game session where the guess is being made.
    :param guess: A list of four words that represent the player's guess.
    :return: A boolean indicating if the guess is correct.
    """

    game = get_game_from_db(game_id)

    relationships = game.relationships
    for words, relation in relationships.items():
        if set(guess) == set(words):
            return True

    return False


def reset_game(game_id, grid, relationships):
    """
    Resets the game with a new grid and relationships, updating the game state in the database.

    :param game_id: The ID of the game session to reset.
    :param grid: The new list of words for the game grid.
    :param relationships: The new relationships dictionary.
    :return: The updated game state.
    """
    game = get_game_from_db(game_id)

    game.grid = grid
    game.relationships = relationships
    game.previous_guesses = []
    game.mistakes_left -= 1
    db.session.commit()

    return game
