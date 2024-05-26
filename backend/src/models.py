import uuid
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Game(db.Model):
    """
    Represents a game session in the database.

    Attributes:
        id (str): The primary key that uniquely identifies a game session.
        grid (PickleType): The serialized form of the game grid which contains the list of words.
        relationships (PickleType): The serialized form of relationships between words in the game grid.
        remaining_guesses (int): The number of guesses left for the player in the current game session.
        game_over (bool): A flag indicating whether the game session has ended.
        previous_guesses (PickleType): A list of previous guesses made during the game session.
    """

    id = db.Column(
        db.String, primary_key=True, default=lambda: str(uuid.uuid4())
    )  # Unique identifier for the game session
    grid = db.Column(db.PickleType)  # Serialized game grid containing the list of words
    relationships = db.Column(db.PickleType)  # Serialized relationships between words
    mistakes_left = db.Column(db.Integer)  # Number of remaining guesses in the game
    game_over = db.Column(db.Boolean)  # Flag to indicate if the game is over
    previous_guesses = db.Column(db.PickleType)  # List of previous guesses made during the game

    def __repr__(self):
        """
        Provides a string representation of the Game instance, primarily for debugging purposes.

        Returns:
            str: A string representation of the Game instance, showing the game ID.
        """
        return "<Game %r>" % self.id
