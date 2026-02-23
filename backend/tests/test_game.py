import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
from src.game.game import (
    generate_game_grid,
    create_new_game,
    get_all_games_data,
    get_game_state,
    process_guess,
    restart_game,
    validate_id,
)


CONNECTIONS = [
    {"relationship": "Fruits", "guessed": False, "words": ["apple", "banana", "cherry", "date"]},
    {"relationship": "Ocean Life", "guessed": False, "words": ["whale", "coral", "shark", "dolphin"]},
    {"relationship": "Space Exploration", "guessed": False, "words": ["astronaut", "rocket", "satellite", "nebula"]},
    {"relationship": "Musical Instruments", "guessed": False, "words": ["guitar", "piano", "violin", "drum"]},
]
GRID = [word for conn in CONNECTIONS for word in conn["words"]]
GAME_STATE = {
    "gameId": "test-id",
    "grid": GRID,
    "connections": CONNECTIONS,
    "mistakesLeft": 4,
    "status": "IN_PROGRESS",
    "previousGuesses": [],
    "puzzleNumber": 1,
}


class TestGame(unittest.TestCase):

    def test_validate_id_exists(self):
        with patch("src.game.game.check_game_exists", return_value=True):
            self.assertTrue(validate_id("some-id"))

    def test_validate_id_not_exists(self):
        with patch("src.game.game.check_game_exists", return_value=False):
            self.assertFalse(validate_id("nonexistent-id"))

    def test_generate_game_grid_static_fallback(self):
        # Pool is empty → should fall back to the bundled connections.json.
        from src.services.puzzle_pool_service import PuzzlePoolEmptyError

        with patch(
            "src.services.puzzle_pool_service.get_puzzle_from_pool",
            side_effect=PuzzlePoolEmptyError("pool is empty"),
        ):
            with patch("src.game.game.path.dirname", return_value="/fake/dir"):
                with patch("src.game.game.path.join", return_value="/fake/dir/connections.json"):
                    with patch(
                        "builtins.open",
                        mock_open(read_data='[]'),
                    ):
                        with patch(
                            "json.load",
                            return_value=[{"words": ["apple", "banana"], "relationship": "fruits"}],
                        ):
                            with patch("random.shuffle", side_effect=lambda x: x.reverse()):
                                grid, connections, puzzle_id = generate_game_grid()
                                self.assertEqual(grid, ["banana", "apple"])
                                self.assertIsNone(puzzle_id)

    def test_generate_game_grid_uses_pool_when_available(self):
        # Pool returns a puzzle → grid is built from it, puzzle_id is threaded through.
        pool_connections = [
            {"relationship": "Fruits", "words": ["apple", "banana", "cherry", "date"], "guessed": False},
        ]
        pool_puzzle_id = "pool-puzzle-uuid"
        with patch(
            "src.services.puzzle_pool_service.get_puzzle_from_pool",
            return_value=(pool_connections, pool_puzzle_id),
        ):
            with patch("random.shuffle", side_effect=lambda x: None):
                grid, connections, puzzle_id = generate_game_grid()

        self.assertEqual(connections, pool_connections)
        self.assertEqual(puzzle_id, pool_puzzle_id)
        self.assertIn("apple", grid)

    def test_generate_game_grid_returns_none_puzzle_id_for_fallback(self):
        from src.services.puzzle_pool_service import PuzzlePoolEmptyError
        with patch(
            "src.services.puzzle_pool_service.get_puzzle_from_pool",
            side_effect=PuzzlePoolEmptyError(),
        ):
            with patch("src.game.game.path.dirname", return_value="/fake"):
                with patch("src.game.game.path.join", return_value="/fake/connections.json"):
                    with patch("builtins.open", mock_open(read_data='[]')):
                        with patch("json.load", return_value=[]):
                            with patch("random.shuffle"):
                                _, _, puzzle_id = generate_game_grid()
                                self.assertIsNone(puzzle_id)

    def test_process_guess_correct_and_valid(self):
        with patch("src.game.game.check_guess", return_value=(True, True, True, "")):
            with patch("src.game.game.update_game_state"):
                with patch("src.game.game.get_game_from_db", return_value=GAME_STATE):
                    game_state, is_valid, is_correct, is_new, err = process_guess("test-id", ["apple", "banana", "cherry", "date"])
                    self.assertTrue(is_valid)
                    self.assertTrue(is_correct)
                    self.assertTrue(is_new)
                    self.assertEqual(game_state, GAME_STATE)

    def test_process_guess_incorrect_but_valid(self):
        with patch("src.game.game.check_guess", return_value=(False, True, True, "")):
            with patch("src.game.game.update_game_state"):
                with patch("src.game.game.get_game_from_db", return_value=GAME_STATE):
                    game_state, is_valid, is_correct, is_new, err = process_guess("test-id", ["apple", "whale", "astronaut", "guitar"])
                    self.assertTrue(is_valid)
                    self.assertFalse(is_correct)
                    self.assertEqual(game_state, GAME_STATE)

    def test_process_guess_invalid(self):
        with patch("src.game.game.check_guess", return_value=(False, False, True, "duplicate word")):
            game_state, is_valid, is_correct, is_new, err = process_guess("test-id", ["apple", "apple", "apple", "apple"])
            self.assertFalse(is_valid)
            self.assertIsNone(game_state)

    def test_create_new_game(self):
        with patch("src.game.game.generate_game_grid", return_value=(GRID, CONNECTIONS, "puzzle-uuid")):
            with patch("src.game.game.add_new_game", return_value="new-game-id"):
                with patch("src.game.game.get_game_from_db", return_value=GAME_STATE):
                    result = create_new_game()
                    self.assertEqual(result, GAME_STATE)

    def test_create_new_game_passes_user_id(self):
        with patch("src.game.game.generate_game_grid", return_value=(GRID, CONNECTIONS, "puzzle-uuid")):
            with patch("src.game.game.add_new_game", return_value="new-game-id") as mock_add:
                with patch("src.game.game.get_game_from_db", return_value=GAME_STATE):
                    create_new_game(user_id="user-uuid")
                    mock_add.assert_called_once_with(GRID, CONNECTIONS, user_id="user-uuid", puzzle_id="puzzle-uuid")

    def test_get_game_state_exists(self):
        with patch("src.game.game.get_game_from_db", return_value=GAME_STATE):
            result = get_game_state("test-id")
            self.assertEqual(result, GAME_STATE)

    def test_get_game_state_not_exists(self):
        with patch("src.game.game.get_game_from_db", return_value=None):
            with self.assertRaises(ValueError):
                get_game_state("nonexistent-id")

    def test_restart_game(self):
        with patch("src.game.game.generate_game_grid", return_value=(GRID, CONNECTIONS, "new-puzzle-uuid")):
            with patch("src.game.game.reset_game", return_value=GAME_STATE) as mock_reset:
                result = restart_game("test-id")
                mock_reset.assert_called_once_with("test-id", GRID, CONNECTIONS, puzzle_id="new-puzzle-uuid")
                self.assertEqual(result, GAME_STATE)

    def test_get_all_games_data(self):
        game_a = {**GAME_STATE, "gameId": "id-a"}
        game_b = {**GAME_STATE, "gameId": "id-b"}
        with patch("src.game.game.get_all_games", return_value=[game_a, game_b]):
            result = get_all_games_data()
            self.assertIn("id-a", result)
            self.assertIn("id-b", result)
            self.assertEqual(result["id-a"], game_a)
