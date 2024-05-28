import unittest
from unittest.mock import patch, mock_open
from backend.src.game import (
    generate_game_grid,
    create_new_game,
    restart_game,
    process_guess,
    get_game_state,
)


class TestGame(unittest.TestCase):

    def test_generate_game_grid_success(self):
        # This test checks if the game grid and connections are successfully generated.
        # It mocks the file reading and API calling processes.
        m = mock_open(read_data="prompt data")
        with patch("builtins.open", m):
            with patch(
                "backend.src.game.call_llm_api",
                return_value="word1, word2: relationship\nword3, word4: relationship2",
            ):
                grid, connections = generate_game_grid()
                self.assertTrue(len(grid) > 0)  # Ensure the grid is not empty
                self.assertTrue(len(connections) > 0)  # Ensure connections are not empty

    def test_generate_game_grid_file_not_found(self):
        # This test ensures that the function handles a FileNotFoundError correctly
        # by returning empty grid and connections.
        with patch("builtins.open", side_effect=FileNotFoundError):
            grid, connections = generate_game_grid()
            self.assertEqual(grid, [])  # Grid should be empty
            self.assertEqual(connections, {})  # Connections should be empty

    def test_create_new_game(self):
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
