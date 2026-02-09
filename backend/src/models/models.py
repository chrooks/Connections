"""
This module defines the database models for the Connections game using SQLAlchemy. It includes the definition of the game session model `ConnectionsGame` which stores all relevant game information such as the game grid, connections, and game status. It also includes the `GameStatus` enum for defining possible game states.

Classes:
- GameStatus: Enum defining possible states of a game session.
- ConnectionsGame: SQLAlchemy model representing a game session in the database.

Functions:
- make_connections_mutable(connections): Helper function to make connection dictionaries mutable for SQLAlchemy tracking.
"""

import uuid
from flask_sqlalchemy import SQLAlchemy
from typing import List
from sqlalchemy.ext.mutable import MutableList, MutableDict
import enum

db = SQLAlchemy()


class GameStatus(enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    WIN = "WIN"
    LOSS = "LOSS"


class ConnectionsGame(db.Model):
    """
    Represents a game session in the database.

    Attributes:
        id (str): The primary key that uniquely identifies a game session.
        grid (JSON): Flat list of the 16 words the contains the list of words.
        connections (JSON): A list of connection objects, each containing a relationship key and a list of four words.
        mistakes_left (int): The number of incorrect guesses left for the player in the current game session.
        status (Enum): The current status of the game session, represented by an enum value.
        previous_guesses (JSON): A list of previous guesses made during the game session.
    """

    id: str = db.Column(db.String, primary_key=True)  # Unique identifier for the game session
    connections: List["dict"] = db.Column(
        MutableList.as_mutable(db.JSON), default=list
    )  # Serialized list of connection objects
    grid: List[str] = db.Column(db.JSON)  # Serialized game grid containing the list of words
    mistakes_left: int = db.Column(db.Integer)  # Number of mistakes left in the game
    status: GameStatus = db.Column(
        db.Enum(GameStatus), default=GameStatus.IN_PROGRESS
    )  # Game status represented by an enum
    previous_guesses: List[str] = db.Column(
        MutableList.as_mutable(db.JSON), default=list
    )  # List of previous guesses made during the game
    puzzle_number: int = db.Column(db.Integer, nullable=True)  # Sequential puzzle number for sharing results

    @staticmethod
    def make_connections_mutable(connections):
        """
        Converts each dictionary in the connections list to MutableDict.
        This ensures changes to the dictionary contents are tracked by SQLAlchemy.
        """
        if connections is None:
            return []
        # This line iterates over the connections list, enumerates it to get both index and value,
        # and converts each connection dictionary into a MutableDict to track changes in SQLAlchemy.
        return [MutableDict.coerce(key, conn) for key, conn in enumerate(connections)]

    def __init__(self, *args, **kwargs):
        super(ConnectionsGame, self).__init__(*args, **kwargs)
        self.connections = self.make_connections_mutable(self.connections)

    def to_state(self):
        """
        Retrieves the current state of the game session.

        Returns:
            dict: A dictionary containing the game's ID, grid, remaining mistakes, and game status.
        """
        return {
            "gameId": self.id,
            "grid": self.grid,
            "connections": self.connections,
            "mistakesLeft": self.mistakes_left,
            "status": self.status.value,
            "previousGuesses": self.previous_guesses,
            "puzzleNumber": self.puzzle_number,
        }

    def __repr__(self):
        """
        Provides a string representation of the Game instance, primarily for debugging purposes.

        Returns:
            str: A string representation of the Game instance, showing the game ID.
        """
        return "<Game %r>" % self.id
