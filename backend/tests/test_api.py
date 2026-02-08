import json
import unittest
from unittest import mock
from unittest.mock import patch
from unittest.mock import MagicMock

from flask import Flask
from backend.src.blueprints.api.routes import (
    game_status,
    generate_grid,
    submit_guess,
    restart,
)
from backend.src.services.utils import create_response
from backend.src.models.models import db


class TestAPI(unittest.TestCase):

    def setUp(self):
        # API
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

    def tearDown(self):
        # Close all sessions first while the application context is still active
        db.session.remove()
        # Then pop the application context
        self.ctx.pop()

    @patch("backend.src.api.create_new_game")
    @patch("backend.src.api.create_response")
    def test_generate_grid(self, mock_create_response, mock_create_new_game):
        # Setup
        mock_game = mock_create_new_game.return_value
        mock_game.id = "12345"

        # Test successful grid generation
        mock_create_new_game.return_value = mock_game
        expected_response = create_response(data={"gameId": "12345"}, status_code=201)
        mock_create_response.return_value = expected_response

        response = generate_grid()
        mock_create_response.assert_called_once_with(data={"gameId": "12345"}, status_code=201)
        self.assertEqual(response, expected_response)

        # Test failure in grid generation
        mock_create_new_game.return_value = None
        error_response = create_response(error="Failed to generate the game grid.", status_code=500)
        mock_create_response.return_value = error_response

        response = generate_grid()
        mock_create_response.assert_called_with(
            error="Failed to generate the game grid.", status_code=500
        )
        self.assertEqual(response, error_response)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.parse_and_validate_request")
    @patch("backend.src.api.validate_id")
    @patch("backend.src.api.process_guess")
    def test_submit_guess_valid_guess(
        self,
        mock_process_guess,
        mock_validate_id,
        mock_parse_and_validate_request,
        mock_create_response,
    ):
        # Setup for valid guess
        mock_parse_and_validate_request.return_value = (
            {"gameId": "12345", "guess": ["word1", "word2", "word3", "word4"]},
            None,
        )
        mock_validate_id.return_value = True
        mock_process_guess.return_value = (MagicMock(), True, True, True)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_create_response.return_value = mock_response

        # Execute
        response = submit_guess()

        # Verify
        mock_create_response.assert_called_once_with(data=mock.ANY)
        self.assertEqual(response.status_code, 200)

    @patch("backend.src.api.create_response")
    @patch("backend.src.game.validate_id")
    def test_submit_guess_invalid_game_id(self, mock_validate_id, mock_create_response):
        # Setup for invalid game ID
        mock_validate_id.return_value = False

        # Execute
        with self.app.test_request_context(
            "/path",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"gameId": "12345", "guess": ["word1", "word2", "word3", "word4"]}),
        ):
            response = submit_guess()

        # Verify
        mock_create_response.assert_called_with(error="Invalid game ID.", status_code=404)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.process_guess")
    @patch("backend.src.api.validate_id")
    def test_submit_guess_invalid_guess(
        self, mock_validate_id, mock_process_guess, mock_create_response
    ):
        # Setup for invalid guess
        mock_validate_id.return_value = True
        mock_process_guess.return_value = (None, False, False, False)
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_create_response.return_value = mock_response

        # Execute
        with self.app.test_request_context(
            "/path",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"gameId": "12345", "guess": ["word1", "word2", "word3", "word4"]}),
        ):
            response = submit_guess()

        # Verify
        mock_create_response.assert_called_with(error="Invalid guess.", status_code=400)
        self.assertEqual(response.status_code, 400)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.parse_and_validate_request")
    def test_submit_guess_error_in_request_parsing(
        self, mock_parse_and_validate_request, mock_create_response
    ):
        # Setup
        mock_parse_and_validate_request.return_value = (None, "Error parsing request")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_create_response.return_value = mock_response

        # Execute
        with self.app.test_request_context(
            "/path",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"gameId": "12345", "guess": ["word1", "word2", "word3", "word4"]}),
        ):
            response = submit_guess()

        # Verify
        mock_create_response.assert_called_with(error="Error parsing request", status_code=400)
        self.assertEqual(response.status_code, 400)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.parse_and_validate_request")
    def test_game_status_error_in_request_parsing(
        self, mock_parse_and_validate_request, mock_create_response
    ):
        # Setup
        mock_parse_and_validate_request.return_value = (None, "Error parsing request")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_create_response.return_value = mock_response

        # Execute
        response = game_status()

        # Verify
        mock_create_response.assert_called_with(error="Error parsing request", status_code=400)
        self.assertEqual(response.status_code, 400)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.validate_id")
    @patch("backend.src.api.parse_and_validate_request")
    def test_game_status_invalid_id(
        self, mock_parse_and_validate_request, mock_validate_id, mock_create_response
    ):
        # Setup
        mock_parse_and_validate_request.return_value = ({"gameId": "invalid_id"}, None)
        mock_validate_id.return_value = False
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_create_response.return_value = mock_response

        # Execute
        response = game_status()

        # Verify
        mock_create_response.assert_called_with(error="Invalid game ID.", status_code=404)
        self.assertEqual(response.status_code, 404)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.get_game_state")
    @patch("backend.src.api.validate_id")
    @patch("backend.src.api.parse_and_validate_request")
    def test_game_status_valid_input(
        self,
        mock_parse_and_validate_request,
        mock_validate_id,
        mock_get_game_state,
        mock_create_response,
    ):
        # Setup
        mock_parse_and_validate_request.return_value = ({"gameId": "valid_id"}, None)
        mock_validate_id.return_value = True
        mock_game_state = MagicMock()
        mock_game_state.to_state.return_value = {"gameId": "valid_id", "status": "IN_PROGRESS"}
        mock_get_game_state.return_value = mock_game_state
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_create_response.return_value = mock_response

        # Execute
        response = game_status()

        # Verify
        mock_create_response.assert_called_with(
            data={"gameId": "valid_id", "status": "IN_PROGRESS"}
        )
        self.assertEqual(response.status_code, 200)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.parse_and_validate_request")
    def test_restart_game_error_in_request_parsing(
        self, mock_parse_and_validate_request, mock_create_response
    ):
        # Setup
        mock_parse_and_validate_request.return_value = (None, "Error parsing request")
        mock_create_response.return_value = MagicMock(status_code=400)

        # Execute
        response = restart()  # Added dummy ID for the function call

        # Verify
        mock_create_response.assert_called_with(error="Error parsing request", status_code=400)
        self.assertEqual(response.status_code, 400)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.validate_id")
    @patch("backend.src.api.parse_and_validate_request")
    def test_restart_game_invalid_id(
        self, mock_parse_and_validate_request, mock_validate_id, mock_create_response
    ):
        # Setup
        mock_parse_and_validate_request.return_value = ({"gameId": "invalid_id"}, None)
        mock_validate_id.return_value = False
        mock_create_response.return_value = MagicMock(status_code=404)

        # Execute
        response = restart()  # Using the specific invalid ID

        # Verify
        mock_create_response.assert_called_with(error="Invalid game ID.", status_code=404)
        self.assertEqual(response.status_code, 404)

    @patch("backend.src.api.create_response")
    @patch("backend.src.api.restart_game")
    @patch("backend.src.api.validate_id")
    @patch("backend.src.api.parse_and_validate_request")
    def test_restart_game_valid_request(
        self,
        mock_parse_and_validate_request,
        mock_validate_id,
        mock_restart_game,
        mock_create_response,
    ):
        # Setup
        mock_parse_and_validate_request.return_value = ({"gameId": "valid_id"}, None)
        mock_validate_id.return_value = True
        mock_game = MagicMock()
        mock_game.to_state.return_value = {"gameId": "valid_id", "status": "RESTARTED"}
        mock_restart_game.return_value = mock_game
        mock_create_response.return_value = MagicMock(status_code=200)

        # Execute
        response = restart()  # Using the specific valid ID

        # Verify
        mock_create_response.assert_called_with(data={"gameId": "valid_id", "status": "RESTARTED"})
        self.assertEqual(response.status_code, 200)
