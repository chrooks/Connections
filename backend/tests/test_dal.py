import unittest
from unittest.mock import patch
from flask import Flask
from sqlalchemy.ext.mutable import MutableDict
from backend.src.dal import (
    add_new_game,
    all_conditions_for_win_met,
    check_game_exists,
    check_game_over,
    get_game_from_db,
    update_game_state,
    check_guess,
    reset_game,
)
from backend.src.models import GameStatus, db, ConnectionsGame


class TestDAL(unittest.TestCase):

    def setUp(self):
        # Set up Flask app and push application context
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["TESTING"] = True
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.connections = [
            {
                "relationship": "Fruits",
                "guessed": False,
                "words": ["apple", "banana", "cherry", "date"],
            },
            {
                "relationship": "Ocean Life",
                "guessed": False,
                "words": ["whale", "coral", "shark", "dolphin"],
            },
            {
                "relationship": "Space Exploration",
                "guessed": False,
                "words": ["astronaut", "rocket", "satellite", "nebula"],
            },
            {
                "relationship": "Musical Instruments",
                "guessed": False,
                "words": ["guitar", "piano", "violin", "drum"],
            },
        ]
        self.grid = [word for connection in self.connections for word in connection["words"]]

    def tearDown(self):
        # Close all sessions first while the application context is still active
        db.session.remove()
        # Then pop the application context
        self.ctx.pop()

    @patch("backend.src.dal.db.session.add")
    @patch("backend.src.dal.db.session.commit")
    def test_add_new_game(self, mock_commit, mock_add):
        # Test to ensure a new game can be added to the database correctly.
        # This test checks if the `add` and `commit` methods of the database session are called.
        game_id = add_new_game(self.grid, self.connections)
        self.assertIsNotNone(game_id)  # Ensure that a game ID is returned (not None)
        mock_add.assert_called()  # Verify that the session's add method was called
        mock_commit.assert_called()  # Verify that the session's commit method was called

    @patch("backend.src.models.ConnectionsGame.query")
    def test_check_game_exists(self, mock_query):
        # Test to check if the function correctly identifies existing and non-existing games.
        # This test uses a mock query object to simulate database responses.
        with self.app.app_context():
            mock_query.filter_by.return_value.first.return_value = ConnectionsGame()
            self.assertTrue(check_game_exists(1))  # Check for an existing game
            mock_query.filter_by.return_value.first.return_value = None
            self.assertFalse(check_game_exists(999))  # Check for a non-existing game

    @patch("backend.src.dal.check_game_exists", return_value=True)
    @patch("backend.src.models.ConnectionsGame.query")
    def test_get_game_from_db(self, mock_query, mock_check_game_exists):
        # Test to ensure a game can be retrieved from the database when it exists.
        # This test also checks if the function returns a ConnectionsGame instance and verifies mutable connections.
        mock_game = ConnectionsGame()
        mock_game.connections = [{"key": "value"}]  # Setup a mock connections list
        mock_query.filter_by.return_value.first.return_value = mock_game
        game = get_game_from_db(1)
        self.assertIsInstance(
            game, ConnectionsGame
        )  # Verify that the returned object is an instance of Game
        self.assertIsInstance(
            game.connections[0], MutableDict
        )  # Verify that the connections are mutable dictionaries

    @patch("backend.src.dal.check_game_exists", return_value=False)
    def test_get_game_from_db_returns_none(self, mock_check_game_exists):
        # Test to ensure that None is returned when trying to retrieve a non-existing game.
        # This test checks the error handling of the function.
        result = get_game_from_db(999)
        self.assertIsNone(result)

    @patch("backend.src.dal.get_game_from_db")
    @patch("backend.src.dal.db.session.commit")
    def test_update_game_state(self, mock_commit, mock_get_game_from_db):
        # Setup
        game = ConnectionsGame(
            id="test_game_id",
            grid=["word1", "word2", "word3", "word4"],
            connections=[
                {"words": ["word1", "word2"], "relationship": "synonyms", "guessed": False},
                {"words": ["word3", "word4"], "relationship": "antonyms", "guessed": False},
            ],
            mistakes_left=3,
            previous_guesses=[],
        )
        mock_get_game_from_db.return_value = game

        # Test that no update occurs if the guess has already been made
        game.previous_guesses.append(["word1", "word2"])
        update_game_state("test_game_id", ["word1", "word2"], True)
        self.assertEqual(game.mistakes_left, 3)
        self.assertFalse(game.connections[0]["guessed"])
        mock_commit.assert_not_called()

        # Test that a new guess is added to previous guesses
        update_game_state("test_game_id", ["word3", "word4"], False)
        self.assertIn(["word3", "word4"], game.previous_guesses)
        self.assertEqual(game.mistakes_left, 2)  # Mistakes should decrease by 1
        mock_commit.assert_called()

        # Reset mock
        mock_commit.reset_mock()

        # Test that a correct guess updates the guessed status of the connection
        game.previous_guesses = []
        update_game_state("test_game_id", ["word1", "word2"], True)
        self.assertTrue(game.connections[0]["guessed"])
        mock_commit.assert_called()

    @patch("backend.src.dal.db.session.commit")
    def test_check_game_over_loss(self, mock_commit):
        # Test to ensure the game status is set to LOSS when no mistakes are left
        game = ConnectionsGame(mistakes_left=0, connections=[{"guessed": False}])
        check_game_over(game)
        self.assertEqual(game.status, GameStatus.LOSS)
        mock_commit.assert_called()

    @patch("backend.src.dal.all_conditions_for_win_met", return_value=True)
    @patch("backend.src.dal.db.session.commit")
    def test_check_game_over_win(self, mock_commit, mock_all_conditions_for_win_met):
        # Test to ensure the game status is set to WIN when all conditions for a win are met
        game = ConnectionsGame(mistakes_left=3, connections=[{"guessed": True}])
        check_game_over(game)
        self.assertEqual(game.status, GameStatus.WIN)
        mock_commit.assert_called()

    @patch("backend.src.dal.all_conditions_for_win_met", return_value=False)
    @patch("backend.src.dal.db.session.commit")
    def test_check_game_over_in_progress(self, mock_commit, mock_all_conditions_for_win_met):
        # Test to ensure the game status remains IN PROGRESS when not all conditions for a win are met and mistakes are left
        game = ConnectionsGame(mistakes_left=1, connections=[{"guessed": False}])
        check_game_over(game)
        self.assertEqual(game.status, GameStatus.IN_PROGRESS)
        mock_commit.assert_called()

    @patch("backend.src.dal.ConnectionsGame")
    def test_all_conditions_for_win_met(self, mock_game):
        # Create a mock game instance with all connections guessed
        mock_game.return_value.connections = [
            {"guessed": True},
            {"guessed": True},
            {"guessed": True},
            {"guessed": True},
        ]
        # Test when all conditions for a win are met
        self.assertTrue(all_conditions_for_win_met(mock_game.return_value))

        # Modify the mock to have one unguessed connection
        mock_game.return_value.connections = [
            {"guessed": True},
            {"guessed": True},
            {"guessed": True},
            {"guessed": False},
        ]
        # Test when not all conditions for a win are met
        self.assertFalse(all_conditions_for_win_met(mock_game.return_value))

    @patch("backend.src.dal.get_game_from_db")
    def test_is_guess_correct(self, mock_get_game_from_db):
        # Setup
        game_id = "test_game_id"
        correct_guess = ["apple", "banana", "cherry", "date"]
        incorrect_guess = ["apple", "banana", "cherry", "pear"]
        invalid_guess = ["apple", "banana", "banana", "date"]
        duplicate_guess = ["apple", "banana", "cherry", "date"]
        short_guess = ["apple", "banana", "cherry"]  # Less than 4 words
        non_grid_word_guess = ["apple", "banana", "cherry", "mango"]  # 'mango' is not in the grid

        game = ConnectionsGame(
            id=game_id,
            grid=["apple", "banana", "cherry", "date", "pear", "peach", "plum", "grape"],
            connections=[
                {"words": ["apple", "banana", "cherry", "date"], "guessed": False},
                {"words": ["pear", "peach", "plum", "grape"], "guessed": False},
            ],
            mistakes_left=3,
            status=GameStatus.IN_PROGRESS,
            previous_guesses=[],
        )

        # Mock the database call to return the game object
        mock_get_game_from_db.return_value = game

        # Test correct guess
        is_correct, is_valid, is_new = check_guess(game_id, correct_guess)
        self.assertTrue(is_correct)
        self.assertTrue(is_valid)
        self.assertTrue(is_new)

        # Test incorrect guess
        is_correct, is_valid, is_new = check_guess(game_id, incorrect_guess)
        self.assertFalse(is_correct)
        self.assertTrue(is_valid)
        self.assertTrue(is_new)

        # Test invalid guess (duplicate words)
        is_correct, is_valid, is_new = check_guess(game_id, invalid_guess)
        self.assertFalse(is_correct)
        self.assertFalse(is_valid)
        self.assertTrue(is_new)

        # Test duplicate guess (already guessed)
        game.previous_guesses.append(correct_guess)
        is_correct, is_valid, is_new = check_guess(game_id, duplicate_guess)
        self.assertTrue(is_correct)
        self.assertTrue(is_valid)
        self.assertFalse(is_new)

        # Test short guess (less than 4 words)
        is_correct, is_valid, is_new = check_guess(game_id, short_guess)
        self.assertFalse(is_correct)
        self.assertFalse(is_valid)
        self.assertTrue(is_new)

        # Test guess with a word not in the grid
        is_correct, is_valid, is_new = check_guess(game_id, non_grid_word_guess)
        self.assertFalse(is_correct)
        self.assertFalse(is_valid)
        self.assertTrue(is_new)

        # Ensure the game status is still in progress
        self.assertEqual(game.status, GameStatus.IN_PROGRESS)

        # Ensure no changes to the guessed status of connections
        self.assertFalse(game.connections[0]["guessed"])
        self.assertFalse(game.connections[1]["guessed"])

    @patch("backend.src.dal.get_game_from_db")
    @patch("backend.src.dal.db.session.commit")
    def test_reset_game(self, mock_commit, mock_get_game_from_db):
        # Test to ensure that a game can be reset correctly.
        # This test checks if the game grid, connections, and previous guesses are reset, and mistakes are decremented.
        game = ConnectionsGame(
            grid=[], connections=[], previous_guesses=["old_guess"], mistakes_left=3
        )
        mock_get_game_from_db.return_value = game
        updated_game = reset_game(1, self.grid, self.connections)
        self.assertEqual(updated_game.grid, self.grid)  # Check if the grid is updated
        # Coerce connections into MutableDict
        mutable_connections = ConnectionsGame.make_connections_mutable(self.connections)
        self.assertEqual(
            updated_game.connections, mutable_connections
        )  # Check if connections are updated
        self.assertEqual(updated_game.previous_guesses, [])  # Check if previous guesses are cleared
        self.assertEqual(updated_game.mistakes_left, 4)  # Check if mistakes left are reset to 4
        mock_commit.assert_called()  # Verify that changes are committed to the database
