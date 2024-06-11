import unittest
from unittest.mock import patch, mock_open
from backend.src.game import (
    generate_game_grid,
    create_new_game,
    process_guess,
    restart_game,
    validate_id,
)


class TestGame(unittest.TestCase):

    def setUp(self):
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

    def test_validate_id_exists(self):
        # This test checks if the validate_id function correctly identifies an existing game ID.
        with patch("backend.src.game.check_game_exists", return_value=True):
            self.assertTrue(validate_id(1))  # Test with an ID that exists

    def test_validate_id_not_exists(self):
        # This test checks if the validate_id function correctly identifies a non-existing game ID.
        with patch("backend.src.game.check_game_exists", return_value=False):
            self.assertFalse(validate_id(999))  # Test with an ID that does not exist

    def test_generate_game_grid(self):
        # This test verifies that the generate_game_grid function returns a grid and connections correctly.
        with patch("backend.src.game.path.dirname", return_value="/fake/dir"):
            with patch("backend.src.game.path.join", return_value="/fake/dir/connections.json"):
                with patch("builtins.open", mock_open(read_data='[{"words": ["apple", "banana"], "relationship": "fruits"}]')):
                    with patch("json.load", return_value=[{"words": ["apple", "banana"], "relationship": "fruits"}]):
                        with patch("random.shuffle", side_effect=lambda x: x.reverse()):
                            grid, connections = generate_game_grid()
                            self.assertEqual(grid, ["banana", "apple"])  # Check if grid is correctly generated and shuffled
                            self.assertEqual(connections, [{"words": ["apple", "banana"], "relationship": "fruits"}])  # Check if connections are correctly loaded

    def test_process_guess_correct_and_valid(self):
        # This test checks if the process_guess function correctly handles a valid and correct guess.
        correct_guess = ["apple", "banana", "cherry", "date"]
        with patch("backend.src.game.is_guess_correct", return_value=(True, True)):
            with patch("backend.src.game.update_game_state"):
                with patch("backend.src.game.get_game_from_db", return_value={"game_state": "updated"}):
                    game_state, is_valid, is_correct = process_guess(1, correct_guess)
                    self.assertTrue(is_valid)
                    self.assertTrue(is_correct)
                    self.assertEqual(game_state, {"game_state": "updated"})

    def test_process_guess_incorrect_but_valid(self):
        # This test checks if the process_guess function correctly handles a valid but incorrect guess.
        incorrect_guess = ["whale", "coral", "shark", "dolphin"]
        with patch("backend.src.game.is_guess_correct", return_value=(False, True)):
            with patch("backend.src.game.update_game_state"):
                with patch("backend.src.game.get_game_from_db", return_value={"game_state": "updated"}):
                    game_state, is_valid, is_correct = process_guess(1, incorrect_guess)
                    self.assertTrue(is_valid)
                    self.assertFalse(is_correct)
                    self.assertEqual(game_state, {"game_state": "updated"})

    def test_process_guess_invalid(self):
        # This test checks if the process_guess function correctly handles an invalid guess.
        invalid_guess = ["guitar", "piano", "violin", "violin"]  # Duplicate word makes it invalid
        with patch("backend.src.game.is_guess_correct", return_value=(False, False)):
            game_state, is_valid, is_correct = process_guess(1, invalid_guess)
            self.assertFalse(is_valid)
            self.assertFalse(is_correct)
            self.assertIsNone(game_state)
        # This test verifies that a new game can be created successfully.
        # It mocks the grid generation, adding a new game to the database, and retrieving the game state.
        with patch(
            "backend.src.game.generate_game_grid",
            return_value=(["word1", "word2"], {("word1", "word2"): "relationship"}),
        ):
            with patch("backend.src.game.add_new_game", return_value=1):
                with patch(
                    "backend.src.game.get_game_from_db",
                    return_value={
                        "game_id": 1,
                        "grid": ["word1", "word2"],
                        "connections": {("word1", "word2"): "relationship"},
                    },
                ):
                    game_id, game_state = create_new_game()
                    self.assertEqual(game_id, 1)  # Check if the correct game ID is returned
                    self.assertIn("grid", game_state)  # Check if the game state contains a grid

    def test_restart_game_exists(self):
        # This test checks if an existing game can be restarted successfully.
        # It mocks the game existence check, grid generation, and game reset.
        with patch("backend.src.game.check_game_exists", return_value=True):
            with patch(
                "backend.src.game.generate_game_grid",
                return_value=(["word1", "word2"], {("word1", "word2"): "relationship"}),
            ):
                with patch("backend.src.game.reset_game", return_value=True):
                    self.assertTrue(restart_game(1))  # Assert the game restarts successfully

    def test_restart_game_not_exists(self):
        # This test ensures that attempting to restart a non-existent game raises a ValueError.
        with patch("backend.src.game.check_game_exists", return_value=False):
            with self.assertRaises(ValueError) as context:
                restart_game(999)
            self.assertEqual(
                str(context.exception), "No game found with the provided ID."
            )  # Check the error message
