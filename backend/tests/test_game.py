from unittest.mock import mock_open, patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.src import game


def test_generate_game_grid_success():
    # This test checks if the game grid and relationships are successfully generated.
    # It mocks the file reading and API calling processes.
    m = mock_open(read_data="prompt data")
    with patch("builtins.open", m):
        with patch(
            "backend.src.game.call_llm_api",
            return_value="word1, word2: relationship\nword3, word4: relationship2",
        ):
            grid, relationships = game.generate_game_grid()
            assert len(grid) > 0  # Ensure the grid is not empty
            assert len(relationships) > 0  # Ensure relationships are not empty


def test_generate_game_grid_file_not_found():
    # This test ensures that the function handles a FileNotFoundError correctly
    # by returning empty grid and relationships.
    with patch("builtins.open", side_effect=FileNotFoundError):
        grid, relationships = game.generate_game_grid()
        assert grid == []  # Grid should be empty
        assert relationships == {}  # Relationships should be empty


def test_create_new_game():
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
                    "relationships": {("word1", "word2"): "relationship"},
                },
            ):
                game_id, game_state = game.create_new_game()
                assert game_id == 1  # Check if the correct game ID is returned
                assert "grid" in game_state  # Check if the game state contains a grid


def test_restart_game_exists():
    # This test checks if an existing game can be restarted successfully.
    # It mocks the game existence check, grid generation, and game reset.
    with patch("backend.src.game.check_game_exists", return_value=True):
        with patch(
            "backend.src.game.generate_game_grid",
            return_value=(["word1", "word2"], {("word1", "word2"): "relationship"}),
        ):
            with patch("backend.src.game.reset_game", return_value=True):
                assert game.restart_game(1) == True  # Assert the game restarts successfully


def test_restart_game_not_exists():
    # This test ensures that attempting to restart a non-existent game raises a ValueError.
    with patch("backend.src.game.check_game_exists", return_value=False):
        try:
            game.restart_game(999)
        except ValueError as e:
            assert str(e) == "No game found with the provided ID."  # Check the error message
