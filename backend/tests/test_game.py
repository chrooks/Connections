import unittest
from unittest.mock import Mock, patch, mock_open
from flask import Flask
from backend.src.dal.dal import db
from backend.src.game.game import (
    generate_game_grid,
    create_new_game,
    get_all_games_data,
    get_game_state,
    process_guess,
    restart,
    validate_id,
)
from backend.src.models.models import ConnectionsGame


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
                            self.assertEqual(
                                grid, ["banana", "apple"]
                            )  # Check if grid is correctly generated and shuffled
                            self.assertEqual(
                                connections,
                                [{"words": ["apple", "banana"], "relationship": "fruits"}],
                            )  # Check if connections are correctly loaded

    def test_process_guess_correct_and_valid(self):
        # This test checks if the process_guess function correctly handles a valid and correct guess.
        correct_guess = ["apple", "banana", "cherry", "date"]
        with patch("backend.src.game.check_guess", return_value=(True, True, True)):
            with patch("backend.src.game.update_game_state"):
                with patch(
                    "backend.src.game.get_game_from_db", return_value={"game_state": "updated"}
                ):
                    game_state, is_valid, is_correct, is_new = process_guess(1, correct_guess)
                    self.assertTrue(is_valid)
                    self.assertTrue(is_correct)
                    self.assertTrue(is_new)
                    self.assertEqual(game_state, {"game_state": "updated"})

    def test_process_guess_incorrect_but_valid(self):
        # This test checks if the process_guess function correctly handles a valid but incorrect guess.
        incorrect_guess = ["whale", "coral", "shark", "dolphin"]
        with patch("backend.src.game.check_guess", return_value=(False, True, True)):
            with patch("backend.src.game.update_game_state"):
                with patch(
                    "backend.src.game.get_game_from_db", return_value={"game_state": "updated"}
                ):
                    game_state, is_valid, is_correct, is_new = process_guess(1, incorrect_guess)
                    self.assertTrue(is_valid)
                    self.assertFalse(is_correct)
                    self.assertTrue(is_new)
                    self.assertEqual(game_state, {"game_state": "updated"})

    def test_process_guess_invalid(self):
        # This test checks if the process_guess function correctly handles an invalid guess.
        invalid_guess = ["guitar", "piano", "violin", "violin"]  # Duplicate word makes it invalid
        with patch("backend.src.game.check_guess", return_value=(False, False, True)):
            game_state, is_valid, is_correct, is_new = process_guess(1, invalid_guess)
            self.assertFalse(is_valid)
            self.assertFalse(is_correct)
            self.assertTrue(is_new)
            self.assertIsNone(game_state)

    def test_process_guess_new_and_not_new(self):
        # This test checks if the process_guess function correctly identifies new and not new guesses.
        game_id = 1
        new_guess = ["apple", "banana", "cherry", "date"]
        not_new_guess = ["apple", "banana", "cherry", "date"]

        # Mock the game state to include the not new guess in previous guesses
        game_state_with_previous = {"game_state": "updated", "previous_guesses": [not_new_guess]}

        with patch(
            "backend.src.game.check_guess",
            side_effect=[
                (True, True, True),  # First call for new guess
                (True, True, False),  # Second call for not new guess
            ],
        ):
            with patch("backend.src.game.update_game_state"):
                with patch(
                    "backend.src.game.get_game_from_db",
                    side_effect=[game_state_with_previous, game_state_with_previous],
                ):
                    # Test with new guess
                    state_new, is_valid_new, is_correct_new, is_new_new = process_guess(
                        game_id, new_guess
                    )
                    self.assertTrue(is_new_new)
                    self.assertTrue(is_valid_new)
                    self.assertTrue(is_correct_new)
                    self.assertEqual(state_new, game_state_with_previous)

                    # Test with not new guess
                    state_not_new, is_valid_not_new, is_correct_not_new, is_new_not_new = (
                        process_guess(game_id, not_new_guess)
                    )
                    self.assertFalse(is_new_not_new)
                    self.assertTrue(is_valid_not_new)
                    self.assertTrue(is_correct_not_new)
                    self.assertEqual(state_not_new, game_state_with_previous)

    def test_create_new_game(self):
        # This test checks if a new game is created successfully with the correct game grid and connections.
        expected_grid = self.grid
        expected_connections = self.connections
        with patch(
            "backend.src.game.generate_game_grid",
            return_value=(expected_grid, expected_connections),
        ):
            with patch("backend.src.game.add_new_game", return_value=1):
                with patch(
                    "backend.src.game.get_game_from_db",
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
        with patch("backend.src.game.get_game_from_db", return_value=expected_game_state):
            game_state = get_game_state(game_id)
            self.assertEqual(game_state, expected_game_state)

    def test_get_game_state_not_exists(self):
        # This test checks if the get_game_state function raises a ValueError when the game does not exist.
        game_id = 999
        with patch("backend.src.game.get_game_from_db", return_value=None):
            with self.assertRaises(ValueError):
                get_game_state(game_id)

    def test_restart_game_exists(self):
        # This test checks if an existing game can be restarted successfully.
        # It mocks the game existence check, grid generation, and game reset.
        with patch("backend.src.game.check_game_exists", return_value=True):
            with patch(
                "backend.src.game.generate_game_grid",
                return_value=(["word1", "word2"], {("word1", "word2"): "relationship"}),
            ):
                with patch("backend.src.game.reset_game", return_value=True):
                    self.assertTrue(restart(1))  # Assert the game restarts successfully

    def test_restart_game_not_exists(self):
        # This test ensures that attempting to restart a non-existent game raises a ValueError.
        with self.app.app_context():
            with patch("backend.src.game.check_game_exists", return_value=False):
                with self.assertRaises(ValueError) as context:
                    restart(999)
                self.assertEqual(
                    str(context.exception), "No game found with the provided ID: 999"
                )  # Check the error message

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
        with patch("backend.src.game.get_all_games", return_value=mock_games):
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
