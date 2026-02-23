import json
import unittest
from unittest.mock import patch, MagicMock

from flask import Flask
from src.blueprints.api.routes import api_bp

GAME_STATE = {
    "gameId": "test-game-id",
    "grid": ["apple", "banana", "cherry", "date"],
    "connections": [
        {"relationship": "Fruits", "words": ["apple", "banana", "cherry", "date"], "guessed": False}
    ],
    "mistakesLeft": 4,
    "status": "IN_PROGRESS",
    "previousGuesses": [],
    "puzzleNumber": 1,
}


class TestAPI(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(api_bp, url_prefix="/connections")
        self.client = self.app.test_client()

    # ---------------------------------------------------------------------------
    # GET /generate-grid
    # ---------------------------------------------------------------------------

    @patch("src.blueprints.api.routes.get_optional_user_id", return_value=None)
    @patch("src.blueprints.api.routes.create_new_game", return_value=GAME_STATE)
    def test_generate_grid_success(self, mock_create, mock_user_id):
        response = self.client.get("/connections/generate-grid")
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data["data"]["gameId"], "test-game-id")

    @patch("src.blueprints.api.routes.get_optional_user_id", return_value=None)
    @patch("src.blueprints.api.routes.create_new_game", return_value=None)
    def test_generate_grid_failure(self, mock_create, mock_user_id):
        response = self.client.get("/connections/generate-grid")
        self.assertEqual(response.status_code, 500)

    @patch("src.blueprints.api.routes.get_optional_user_id", return_value="user-uuid")
    @patch("src.blueprints.api.routes.create_new_game", return_value=GAME_STATE)
    def test_generate_grid_passes_user_id(self, mock_create, mock_user_id):
        self.client.get("/connections/generate-grid")
        mock_create.assert_called_once_with(user_id="user-uuid")

    # ---------------------------------------------------------------------------
    # POST /submit-guess
    # ---------------------------------------------------------------------------

    @patch("src.blueprints.api.routes.validate_id", return_value=True)
    @patch("src.blueprints.api.routes.process_guess")
    def test_submit_guess_correct(self, mock_process, mock_validate):
        guessed_connections = [
            {"relationship": "Fruits", "words": ["apple", "banana", "cherry", "date"], "guessed": True}
        ]
        mock_process.return_value = (
            {**GAME_STATE, "connections": guessed_connections},
            True, True, True, ""
        )
        response = self.client.post(
            "/connections/submit-guess",
            json={"gameId": "test-game-id", "guess": ["apple", "banana", "cherry", "date"]},
        )
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["data"]["isCorrect"])

    @patch("src.blueprints.api.routes.validate_id", return_value=False)
    def test_submit_guess_invalid_game_id(self, mock_validate):
        response = self.client.post(
            "/connections/submit-guess",
            json={"gameId": "bad-id", "guess": ["a", "b", "c", "d"]},
        )
        self.assertEqual(response.status_code, 404)

    @patch("src.blueprints.api.routes.validate_id", return_value=True)
    @patch("src.blueprints.api.routes.process_guess", return_value=(None, False, False, False, "duplicate"))
    def test_submit_guess_invalid_guess(self, mock_process, mock_validate):
        response = self.client.post(
            "/connections/submit-guess",
            json={"gameId": "test-game-id", "guess": ["a", "b", "c", "d"]},
        )
        self.assertEqual(response.status_code, 400)

    def test_submit_guess_missing_fields(self):
        response = self.client.post(
            "/connections/submit-guess",
            json={"gameId": "test-game-id"},
        )
        self.assertEqual(response.status_code, 400)

    # ---------------------------------------------------------------------------
    # POST /game-status
    # ---------------------------------------------------------------------------

    @patch("src.blueprints.api.routes.validate_id", return_value=True)
    @patch("src.blueprints.api.routes.get_game_state", return_value=GAME_STATE)
    def test_game_status_valid(self, mock_get_state, mock_validate):
        response = self.client.post(
            "/connections/game-status",
            json={"gameId": "test-game-id"},
        )
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["data"]["gameId"], "test-game-id")
        self.assertEqual(data["data"]["status"], "IN_PROGRESS")

    @patch("src.blueprints.api.routes.validate_id", return_value=False)
    def test_game_status_invalid_id(self, mock_validate):
        response = self.client.post(
            "/connections/game-status",
            json={"gameId": "bad-id"},
        )
        self.assertEqual(response.status_code, 404)

    def test_game_status_missing_game_id(self):
        response = self.client.post("/connections/game-status", json={})
        self.assertEqual(response.status_code, 400)

    # ---------------------------------------------------------------------------
    # POST /restart-game
    # ---------------------------------------------------------------------------

    @patch("src.blueprints.api.routes.validate_id", return_value=True)
    @patch("src.blueprints.api.routes.restart_game", return_value=GAME_STATE)
    def test_restart_game_valid(self, mock_restart, mock_validate):
        response = self.client.post(
            "/connections/restart-game",
            json={"gameId": "test-game-id"},
        )
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["data"]["status"], "IN_PROGRESS")

    @patch("src.blueprints.api.routes.validate_id", return_value=False)
    def test_restart_game_invalid_id(self, mock_validate):
        response = self.client.post(
            "/connections/restart-game",
            json={"gameId": "bad-id"},
        )
        self.assertEqual(response.status_code, 404)

    def test_restart_game_missing_game_id(self):
        response = self.client.post("/connections/restart-game", json={})
        self.assertEqual(response.status_code, 400)
