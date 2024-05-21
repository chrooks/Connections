import unittest
from unittest.mock import patch
from backend.src.dal import (
    add_new_game,
    check_game_exists,
    get_game_from_db,
    update_game_state,
    is_guess_correct,
    reset_game,
)
from backend.src.models import db, Game


class TestDAL(unittest.TestCase):

    @patch("backend.src.dal.db.session.add")
    @patch("backend.src.dal.db.session.commit")
    def test_add_new_game(self, mock_commit, mock_add):
        # Test to ensure a new game can be added to the database correctly.
        # This test checks if the `add` and `commit` methods of the database session are called.
        game_id = add_new_game(["word1", "word2"], {("word1", "word2"): "relationship"})
        self.assertIsNotNone(game_id)  # Ensure that a game ID is returned (not None)
        mock_add.assert_called()  # Verify that the session's add method was called
        mock_commit.assert_called()  # Verify that the session's commit method was called

    @patch("backend.src.dal.Game.query")
    def test_check_game_exists(self, mock_query):
        # Test to check if the function correctly identifies existing and non-existing games.
        # This test uses a mock query object to simulate database responses.
        mock_query.filter_by.return_value.first.return_value = Game()
        self.assertTrue(check_game_exists(1))  # Check for an existing game
        mock_query.filter_by.return_value.first.return_value = None
        self.assertFalse(check_game_exists(999))  # Check for a non-existing game

    @patch("backend.src.dal.check_game_exists", return_value=True)
    @patch("backend.src.dal.Game.query")
    def test_get_game_from_db(self, mock_query, mock_check_game_exists):
        # Test to ensure a game can be retrieved from the database when it exists.
        # This test also checks if the function returns a Game instance.
        mock_query.filter_by.return_value.first.return_value = Game()
        game = get_game_from_db(1)
        self.assertIsInstance(game, Game)  # Verify that the returned object is an instance of Game

    @patch("backend.src.dal.check_game_exists", return_value=False)
    def test_get_game_from_db_raises(self, mock_check_game_exists):
        # Test to ensure that an exception is raised when trying to retrieve a non-existing game.
        # This test checks the error handling of the function.
        with self.assertRaises(ValueError):
            get_game_from_db(999)

    @patch("backend.src.dal.get_game_from_db")
    @patch("backend.src.dal.db.session.commit")
    def test_update_game_state(self, mock_commit, mock_get_game_from_db):
        # Test to verify that the game state is updated correctly based on a guess.
        # This test checks if the previous guesses list and mistakes count are updated.
        game = Game(previous_guesses=[], mistakes_left=3)
        mock_get_game_from_db.return_value = game
        update_game_state(1, "guess", False)
        self.assertIn(
            "guess", game.previous_guesses
        )  # Check if the guess was added to previous guesses
        self.assertEqual(game.mistakes_left, 2)  # Check if the mistakes left decreased
        mock_commit.assert_called()  # Verify that changes are committed to the database

    @patch("backend.src.dal.get_game_from_db")
    def test_is_guess_correct(self, mock_get_game_from_db):
        # Test to check if the function correctly identifies correct and incorrect guesses.
        # This test uses a mock game object with predefined relationships.
        game = Game(relationships={("word1", "word2"): "relationship"})
        mock_get_game_from_db.return_value = game
        self.assertTrue(is_guess_correct(1, ["word1", "word2"]))  # Test a correct guess
        self.assertFalse(is_guess_correct(1, ["word3", "word4"]))  # Test an incorrect guess

    @patch("backend.src.dal.get_game_from_db")
    @patch("backend.src.dal.db.session.commit")
    def test_reset_game(self, mock_commit, mock_get_game_from_db):
        # Test to ensure that a game can be reset correctly.
        # This test checks if the game grid, relationships, and previous guesses are reset, and mistakes are decremented.
        game = Game(grid=[], relationships={}, previous_guesses=["old_guess"], mistakes_left=3)
        mock_get_game_from_db.return_value = game
        updated_game = reset_game(
            1, ["new_word1", "new_word2"], {("new_word1", "new_word2"): "new_relationship"}
        )
        self.assertEqual(
            updated_game.grid, ["new_word1", "new_word2"]
        )  # Check if the grid is updated
        self.assertEqual(
            updated_game.relationships, {("new_word1", "new_word2"): "new_relationship"}
        )  # Check if relationships are updated
        self.assertEqual(updated_game.previous_guesses, [])  # Check if previous guesses are cleared
        self.assertEqual(updated_game.mistakes_left, 2)  # Check if mistakes left are decremented
        mock_commit.assert_called()  # Verify that changes are committed to the database
