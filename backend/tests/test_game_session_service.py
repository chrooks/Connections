"""
Tests for game_session_service.py.

All Supabase client calls are mocked — no real DB connection is needed.
Each test patches _get_client() at the module level so the Supabase fluent
chain never actually runs.

Coverage:
  - add_new_game          → happy path, returns id
  - check_game_exists     → found / not found
  - get_game_from_db      → camelCase transformation, not found
  - check_guess           → correct, incorrect, invalid, duplicate
  - update_game_state     → correct guess, incorrect guess, duplicate guard
  - check_game_over       → pure logic (no DB)
  - all_conditions_for_win_met → pure logic (no DB)
  - reset_game            → happy path
  - get_all_games         → list transformation
"""

import unittest
from unittest.mock import MagicMock, patch, call

from src.services.game_session_service import (
    add_new_game,
    check_game_exists,
    check_game_over,
    check_guess,
    get_all_games,
    get_game_from_db,
    all_conditions_for_win_met,
    reset_game,
    update_game_state,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

GAME_ID = "aaaaaaaa-0000-0000-0000-000000000001"
USER_ID = "bbbbbbbb-0000-0000-0000-000000000002"
PUZZLE_ID = "cccccccc-0000-0000-0000-000000000003"

CONNECTIONS = [
    {"relationship": "Fruits", "words": ["apple", "banana", "cherry", "date"], "guessed": False},
    {"relationship": "Ocean Life", "words": ["whale", "coral", "shark", "dolphin"], "guessed": False},
    {"relationship": "Space", "words": ["astronaut", "rocket", "satellite", "nebula"], "guessed": False},
    {"relationship": "Music", "words": ["guitar", "piano", "violin", "drum"], "guessed": False},
]

GRID = [word for conn in CONNECTIONS for word in conn["words"]]

RAW_ROW = {
    "id":               GAME_ID,
    "user_id":          None,
    "puzzle_id":        None,
    "grid":             GRID,
    "connections":      CONNECTIONS,
    "mistakes_left":    4,
    "status":           "IN_PROGRESS",
    "previous_guesses": [],
    "puzzle_number":    1,
}


def _mock_client():
    return MagicMock()


# ---------------------------------------------------------------------------
# add_new_game
# ---------------------------------------------------------------------------

class TestAddNewGame(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_returns_new_game_id(self, mock_get_client):
        """INSERT should return the UUID of the created row."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": GAME_ID}]
        )

        result = add_new_game(GRID, CONNECTIONS)
        self.assertEqual(result, GAME_ID)

    @patch("src.services.game_session_service._get_client")
    def test_passes_user_and_puzzle_ids(self, mock_get_client):
        """user_id and puzzle_id should appear in the INSERT payload."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": GAME_ID}]
        )

        add_new_game(GRID, CONNECTIONS, user_id=USER_ID, puzzle_id=PUZZLE_ID)

        insert_payload = client.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_payload["user_id"], USER_ID)
        self.assertEqual(insert_payload["puzzle_id"], PUZZLE_ID)

    @patch("src.services.game_session_service._get_client")
    def test_guest_game_has_null_user_id(self, mock_get_client):
        """Omitting user_id should insert NULL (None) for guest sessions."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": GAME_ID}]
        )

        add_new_game(GRID, CONNECTIONS)

        insert_payload = client.table.return_value.insert.call_args[0][0]
        self.assertIsNone(insert_payload["user_id"])


# ---------------------------------------------------------------------------
# check_game_exists
# ---------------------------------------------------------------------------

class TestCheckGameExists(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_returns_true_when_found(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )
        self.assertTrue(check_game_exists(GAME_ID))

    @patch("src.services.game_session_service._get_client")
    def test_returns_false_when_not_found(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        self.assertFalse(check_game_exists("nonexistent-id"))


# ---------------------------------------------------------------------------
# get_game_from_db
# ---------------------------------------------------------------------------

class TestGetGameFromDb(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_transforms_to_camel_case(self, mock_get_client):
        """The returned dict must use camelCase keys matching the old to_state() output."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        result = get_game_from_db(GAME_ID)

        self.assertEqual(result["gameId"], GAME_ID)
        self.assertEqual(result["mistakesLeft"], 4)
        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(result["previousGuesses"], [])
        self.assertEqual(result["puzzleNumber"], 1)
        self.assertIn("grid", result)
        self.assertIn("connections", result)

    @patch("src.services.game_session_service._get_client")
    def test_returns_none_when_not_found(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        self.assertIsNone(get_game_from_db("nonexistent"))


# ---------------------------------------------------------------------------
# check_guess
# ---------------------------------------------------------------------------

class TestCheckGuess(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_correct_guess(self, mock_get_client):
        """A guess matching a connection exactly should be correct and valid."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        is_correct, is_valid, is_new, err = check_guess(GAME_ID, ["apple", "banana", "cherry", "date"])

        self.assertTrue(is_correct)
        self.assertTrue(is_valid)
        self.assertTrue(is_new)
        self.assertEqual(err, "")

    @patch("src.services.game_session_service._get_client")
    def test_incorrect_guess(self, mock_get_client):
        """A valid 4-word guess that doesn't match any connection should not be correct."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        is_correct, is_valid, is_new, err = check_guess(GAME_ID, ["apple", "whale", "astronaut", "guitar"])

        self.assertFalse(is_correct)
        self.assertTrue(is_valid)

    @patch("src.services.game_session_service._get_client")
    def test_duplicate_guess_is_not_new(self, mock_get_client):
        """Submitting the same 4-word set twice should set is_new=False."""
        client = _mock_client()
        mock_get_client.return_value = client
        row = {**RAW_ROW, "previous_guesses": [["apple", "banana", "cherry", "date"]]}
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        _, _, is_new, _ = check_guess(GAME_ID, ["apple", "banana", "cherry", "date"])

        self.assertFalse(is_new)

    @patch("src.services.game_session_service._get_client")
    def test_wrong_word_count_invalid(self, mock_get_client):
        """A guess with fewer than 4 words must be rejected."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        _, is_valid, _, err = check_guess(GAME_ID, ["apple", "banana", "cherry"])

        self.assertFalse(is_valid)
        self.assertIn("four words", err)

    @patch("src.services.game_session_service._get_client")
    def test_duplicate_words_invalid(self, mock_get_client):
        """A guess with repeated words must be rejected."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        _, is_valid, _, err = check_guess(GAME_ID, ["apple", "apple", "apple", "apple"])

        self.assertFalse(is_valid)

    @patch("src.services.game_session_service._get_client")
    def test_game_not_in_progress_is_invalid(self, mock_get_client):
        """Guessing on a finished game must be rejected."""
        client = _mock_client()
        mock_get_client.return_value = client
        row = {**RAW_ROW, "status": "WIN"}
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        _, is_valid, _, err = check_guess(GAME_ID, ["apple", "banana", "cherry", "date"])

        self.assertFalse(is_valid)


# ---------------------------------------------------------------------------
# update_game_state
# ---------------------------------------------------------------------------

class TestUpdateGameState(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_correct_guess_marks_connection_guessed(self, mock_get_client):
        """A correct guess should flip guessed=True on the matching connection."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        update_game_state(GAME_ID, ["apple", "banana", "cherry", "date"], is_correct=True)

        update_payload = client.table.return_value.update.call_args[0][0]
        # The Fruits connection should now be guessed
        fruits = next(c for c in update_payload["connections"] if c["relationship"] == "Fruits")
        self.assertTrue(fruits["guessed"])
        # mistakes_left unchanged on correct guess
        self.assertEqual(update_payload["mistakes_left"], 4)

    @patch("src.services.game_session_service._get_client")
    def test_incorrect_guess_decrements_mistakes(self, mock_get_client):
        """An incorrect guess should decrement mistakes_left by 1."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW]
        )

        update_game_state(GAME_ID, ["apple", "whale", "astronaut", "guitar"], is_correct=False)

        update_payload = client.table.return_value.update.call_args[0][0]
        self.assertEqual(update_payload["mistakes_left"], 3)

    @patch("src.services.game_session_service._get_client")
    def test_duplicate_guess_is_not_reapplied(self, mock_get_client):
        """Submitting the same guess twice should not trigger a second UPDATE."""
        client = _mock_client()
        mock_get_client.return_value = client
        row = {**RAW_ROW, "previous_guesses": [["apple", "banana", "cherry", "date"]]}
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        update_game_state(GAME_ID, ["apple", "banana", "cherry", "date"], is_correct=True)

        client.table.return_value.update.assert_not_called()

    @patch("src.services.game_session_service._get_client")
    def test_status_becomes_loss_when_no_mistakes_left(self, mock_get_client):
        """Game status should transition to LOSS when mistakes_left hits 0."""
        client = _mock_client()
        mock_get_client.return_value = client
        row = {**RAW_ROW, "mistakes_left": 1}
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[row]
        )

        update_game_state(GAME_ID, ["apple", "whale", "astronaut", "guitar"], is_correct=False)

        update_payload = client.table.return_value.update.call_args[0][0]
        self.assertEqual(update_payload["status"], "LOSS")
        self.assertEqual(update_payload["mistakes_left"], 0)


# ---------------------------------------------------------------------------
# check_game_over / all_conditions_for_win_met (pure logic)
# ---------------------------------------------------------------------------

class TestPureLogic(unittest.TestCase):

    def test_check_game_over_in_progress(self):
        game = {"connections": CONNECTIONS, "mistakes_left": 4}
        self.assertEqual(check_game_over(game), "IN_PROGRESS")

    def test_check_game_over_loss(self):
        game = {"connections": CONNECTIONS, "mistakes_left": 0}
        self.assertEqual(check_game_over(game), "LOSS")

    def test_check_game_over_win(self):
        all_guessed = [{**c, "guessed": True} for c in CONNECTIONS]
        game = {"connections": all_guessed, "mistakes_left": 2}
        self.assertEqual(check_game_over(game), "WIN")

    def test_all_conditions_for_win_met_true(self):
        all_guessed = [{**c, "guessed": True} for c in CONNECTIONS]
        self.assertTrue(all_conditions_for_win_met({"connections": all_guessed}))

    def test_all_conditions_for_win_met_false(self):
        self.assertFalse(all_conditions_for_win_met({"connections": CONNECTIONS}))

    def test_accepts_camel_case_key(self):
        """check_game_over should work with camelCase dict from get_game_from_db."""
        game = {"connections": CONNECTIONS, "mistakesLeft": 4}
        self.assertEqual(check_game_over(game), "IN_PROGRESS")


# ---------------------------------------------------------------------------
# reset_game
# ---------------------------------------------------------------------------

class TestResetGame(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_reset_updates_row_and_returns_state(self, mock_get_client):
        """reset_game should UPDATE the row and return the fresh state dict."""
        client = _mock_client()
        mock_get_client.return_value = client

        new_connections = [{**c, "guessed": False} for c in CONNECTIONS]
        new_grid = [w for c in new_connections for w in c["words"]]
        reset_row = {
            **RAW_ROW,
            "grid":          new_grid,
            "connections":   new_connections,
            "mistakes_left": 4,
            "status":        "IN_PROGRESS",
            "previous_guesses": [],
        }

        # First call is the UPDATE (returns nothing useful), second is the SELECT in get_game_from_db
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[reset_row]
        )

        result = reset_game(GAME_ID, new_grid, new_connections)

        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(result["mistakesLeft"], 4)
        self.assertEqual(result["previousGuesses"], [])


# ---------------------------------------------------------------------------
# get_all_games
# ---------------------------------------------------------------------------

class TestGetAllGames(unittest.TestCase):

    @patch("src.services.game_session_service._get_client")
    def test_returns_list_of_state_dicts(self, mock_get_client):
        """get_all_games should return every row transformed to a camelCase dict."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[RAW_ROW, {**RAW_ROW, "id": "different-id"}]
        )

        result = get_all_games()

        self.assertEqual(len(result), 2)
        self.assertIn("gameId", result[0])
        self.assertIn("gameId", result[1])

    @patch("src.services.game_session_service._get_client")
    def test_empty_database_returns_empty_list(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])

        result = get_all_games()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
