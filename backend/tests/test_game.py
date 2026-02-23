import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
from flask import Flask
from src.dal.dal import db
from src.game.game import (
    generate_game_grid,
    create_new_game,
    get_all_games_data,
    get_game_state,
    process_guess,
    restart_game,
    validate_id,
)
from src.models.models import ConnectionsGame


class TestGame(unittest.TestCase):

    def setUp(self):
        # Game Logic
        # Set up Flask app and push application context
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["TESTING"] = True
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()  # Create all tables
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

    def test_validate_id_exists(self):
        # This test checks if the validate_id function correctly identifies an existing game ID.
        # Patch target: src.game.game — the module where check_game_exists is imported
        with patch("src.game.game.check_game_exists", return_value=True):
            self.assertTrue(validate_id(1))  # Test with an ID that exists

    def test_validate_id_not_exists(self):
        # This test checks if the validate_id function correctly identifies a non-existing game ID.
        with patch("src.game.game.check_game_exists", return_value=False):
            self.assertFalse(validate_id(999))  # Test with an ID that does not exist

    def test_generate_game_grid_static_fallback(self):
        # Simulates the puzzle pool being empty so generate_game_grid falls back to
        # the bundled connections.json. This is the expected path during local dev
        # before any puzzles have been seeded into Supabase.
        #
        # get_puzzle_from_pool is imported inside the function body, so we patch it
        # at its source module — that's the name Python will look up at call time.
        from src.services.puzzle_pool_service import PuzzlePoolEmptyError

        with patch(
            "src.services.puzzle_pool_service.get_puzzle_from_pool",
            side_effect=PuzzlePoolEmptyError("pool is empty"),
        ):
            with patch("src.game.game.path.dirname", return_value="/fake/dir"):
                with patch("src.game.game.path.join", return_value="/fake/dir/connections.json"):
                    with patch(
                        "builtins.open",
                        mock_open(
                            read_data='[{"words": ["apple", "banana"], "relationship": "fruits"}]'
                        ),
                    ):
                        with patch(
                            "json.load",
                            return_value=[{"words": ["apple", "banana"], "relationship": "fruits"}],
                        ):
                            with patch("random.shuffle", side_effect=lambda x: x.reverse()):
                                grid, connections = generate_game_grid()
                                self.assertEqual(grid, ["banana", "apple"])
                                self.assertEqual(
                                    connections,
                                    [{"words": ["apple", "banana"], "relationship": "fruits"}],
                                )

    def test_generate_game_grid_uses_pool_when_available(self):
        # When the pool has an approved puzzle, generate_game_grid should return its
        # connections and skip the static JSON file entirely.
        pool_connections = [
            {"relationship": "Fruits", "words": ["apple", "banana", "cherry", "date"], "guessed": False},
        ]
        with patch(
            "src.services.puzzle_pool_service.get_puzzle_from_pool",
            return_value=pool_connections,
        ):
            with patch("random.shuffle", side_effect=lambda x: None):  # no-op shuffle
                grid, connections = generate_game_grid()

        self.assertEqual(connections, pool_connections)
        # grid is built from the words in each connection group
        self.assertIn("apple", grid)

    def test_process_guess_correct_and_valid(self):
        # This test checks if the process_guess function correctly handles a valid and correct guess.
        # check_guess returns 4 values: (is_correct, is_valid, is_new, error_message)
        correct_guess = ["apple", "banana", "cherry", "date"]
        mock_game = MagicMock()
        mock_game.to_state.return_value = {"game_state": "updated"}
        with patch("src.game.game.check_guess", return_value=(True, True, True, "")):
            with patch("src.game.game.update_game_state"):
                with patch("src.game.game.get_game_from_db", return_value=mock_game):
                    game_state, is_valid, is_correct, is_new, error_msg = process_guess(1, correct_guess)
                    self.assertTrue(is_valid)
                    self.assertTrue(is_correct)
                    self.assertTrue(is_new)
                    self.assertEqual(game_state, {"game_state": "updated"})

    def test_process_guess_incorrect_but_valid(self):
        # This test checks if the process_guess function correctly handles a valid but incorrect guess.
        incorrect_guess = ["whale", "coral", "shark", "dolphin"]
        mock_game = MagicMock()
        mock_game.to_state.return_value = {"game_state": "updated"}
        with patch("src.game.game.check_guess", return_value=(False, True, True, "")):
            with patch("src.game.game.update_game_state"):
                with patch("src.game.game.get_game_from_db", return_value=mock_game):
                    game_state, is_valid, is_correct, is_new, error_msg = process_guess(1, incorrect_guess)
                    self.assertTrue(is_valid)
                    self.assertFalse(is_correct)
                    self.assertTrue(is_new)
                    self.assertEqual(game_state, {"game_state": "updated"})

    def test_process_guess_invalid(self):
        # This test checks if the process_guess function correctly handles an invalid guess.
        invalid_guess = ["guitar", "piano", "violin", "violin"]  # Duplicate word makes it invalid
        with patch("src.game.game.check_guess", return_value=(False, False, True, "duplicate word")):
            game_state, is_valid, is_correct, is_new, error_msg = process_guess(1, invalid_guess)
            self.assertFalse(is_valid)
            self.assertFalse(is_correct)
            self.assertTrue(is_new)
            self.assertIsNone(game_state)

    def test_process_guess_new_and_not_new(self):
        # This test checks if the process_guess function correctly identifies new and not new guesses.
        game_id = 1
        new_guess = ["apple", "banana", "cherry", "date"]
        not_new_guess = ["apple", "banana", "cherry", "date"]

        mock_game = MagicMock()
        mock_game.to_state.return_value = {"game_state": "updated", "previous_guesses": [not_new_guess]}

        with patch(
            "src.game.game.check_guess",
            side_effect=[
                (True, True, True, ""),   # First call: new guess, correct
                (True, True, False, ""),  # Second call: repeated guess
            ],
        ):
            with patch("src.game.game.update_game_state"):
                with patch(
                    "src.game.game.get_game_from_db",
                    return_value=mock_game,
                ):
                    # Test with new guess
                    state_new, is_valid_new, is_correct_new, is_new_new, _ = process_guess(
                        game_id, new_guess
                    )
                    self.assertTrue(is_new_new)
                    self.assertTrue(is_valid_new)
                    self.assertTrue(is_correct_new)

                    # Test with not new guess
                    state_not_new, is_valid_not_new, is_correct_not_new, is_new_not_new, _ = (
                        process_guess(game_id, not_new_guess)
                    )
                    self.assertFalse(is_new_not_new)
                    self.assertTrue(is_valid_not_new)
                    self.assertTrue(is_correct_not_new)

    def test_create_new_game(self):
        # This test checks if a new game is created successfully with the correct game grid and connections.
        expected_grid = self.grid
        expected_connections = self.connections
        with patch(
            "src.game.game.generate_game_grid",
            return_value=(expected_grid, expected_connections),
        ):
            with patch("src.game.game.add_new_game", return_value=1):
                with patch(
                    "src.game.game.get_game_from_db",
                    return_value=ConnectionsGame(
                        id=1,
                        grid=expected_grid,
                        connections=expected_connections,
                    ),
                ):
                    game_state = create_new_game()
                    self.assertEqual(game_state.id, 1)
                    self.assertEqual(game_state.grid, expected_grid)
                    self.assertEqual(game_state.connections, expected_connections)

    def test_get_game_state_exists(self):
        # This test checks if the get_game_state function retrieves the correct game state when the game exists.
        game_id = 1
        expected_game_state = {"game_id": game_id, "grid": ["word1", "word2"], "connections": {}}
        with patch("src.game.game.get_game_from_db", return_value=expected_game_state):
            game_state = get_game_state(game_id)
            self.assertEqual(game_state, expected_game_state)

    def test_get_game_state_not_exists(self):
        # This test checks if the get_game_state function raises a ValueError when the game does not exist.
        game_id = 999
        with patch("src.game.game.get_game_from_db", return_value=None):
            with self.assertRaises(ValueError):
                get_game_state(game_id)

    def test_restart_game(self):
        # Verifies that restart_game generates a new grid and passes it to reset_game.
        # Note: game ID validation is the route handler's responsibility, not restart_game's.
        with patch(
            "src.game.game.generate_game_grid",
            return_value=(["word1", "word2"], {("word1", "word2"): "relationship"}),
        ):
            with patch("src.game.game.reset_game", return_value=True):
                self.assertTrue(restart_game(1))  # Assert the game restarts successfully

    def test_get_all_games_data(self):
        # This test checks if the get_all_games_data function retrieves all games data correctly
        # using predefined connections and grid.
        mock_games = [
            Mock(
                id=1,
                to_state=lambda: {
                    "game_id": 1,
                    "grid": self.grid[:2],
                    "connections": self.connections[0],
                },
            ),
            Mock(
                id=2,
                to_state=lambda: {
                    "game_id": 2,
                    "grid": self.grid[2:4],
                    "connections": self.connections[1],
                },
            ),
        ]
        with patch("src.game.game.get_all_games", return_value=mock_games):
            all_games_data = get_all_games_data()
            expected_data = {
                1: {
                    "game_id": 1,
                    "grid": self.grid[:2],
                    "connections": self.connections[0],
                },
                2: {
                    "game_id": 2,
                    "grid": self.grid[2:4],
                    "connections": self.connections[1],
                },
            }
            self.assertEqual(all_games_data, expected_data)
