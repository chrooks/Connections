"""
Tests for puzzle_pool_service.py.

All Supabase client calls are mocked — no real DB connection is needed.
Each test patches _get_client() (and often _get_config_id()) at the module
level so the Supabase fluent chain never actually runs.

Coverage:
  - get_puzzle_from_pool  → correct data transformation, empty pool, bad config
  - get_pool_stats        → counting by status, empty pool
  - seed_puzzle_to_pool   → happy path, validation errors, word canonicalisation
  - approve_puzzle        → correct UPDATE payload and WHERE clause
  - reject_puzzle         → correct UPDATE payload and WHERE clause
"""

import unittest
from unittest.mock import MagicMock, patch

from src.services.puzzle_pool_service import (
    PuzzlePoolEmptyError,
    approve_puzzle,
    get_pool_stats,
    get_puzzle_from_pool,
    reject_puzzle,
    seed_puzzle_to_pool,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

CONFIG_ID = "aaaaaaaa-0000-0000-0000-000000000001"
PUZZLE_ID = "bbbbbbbb-0000-0000-0000-000000000002"
GROUP_ID = "cccccccc-0000-0000-0000-000000000003"


def _mock_client():
    """Returns a fresh MagicMock that stands in for the Supabase Client.

    MagicMock automatically returns a new MagicMock for any attribute access or
    call, which is exactly how Supabase's fluent builder chain works:
        client.table("x").select("y").eq("z", v).execute()
    Each step returns something you can keep calling methods on.
    """
    return MagicMock()


# ---------------------------------------------------------------------------
# get_puzzle_from_pool
# ---------------------------------------------------------------------------

class TestGetPuzzleFromPool(unittest.TestCase):

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_returns_connections_format(self, mock_get_client, _mock_config_id):
        """Happy path: pool returns a puzzle → result matches the connections dict format."""
        client = _mock_client()
        mock_get_client.return_value = client

        # The RPC returns the selected puzzle's UUID
        client.rpc.return_value.execute.return_value = MagicMock(data=PUZZLE_ID)

        # The nested groups+words query returns one group with two words
        client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "category_name": "Fruits",
                    "sort_order": 0,
                    "puzzle_words": [
                        {"word": "apple", "display_text": "APPLE"},   # has display_text
                        {"word": "banana", "display_text": None},     # no display_text
                    ],
                }
            ]
        )

        result = get_puzzle_from_pool("classic")

        # Shape: list of dicts with relationship, words, guessed
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["relationship"], "Fruits")
        self.assertFalse(result[0]["guessed"])  # all groups start unguessed
        # display_text wins when present; falls back to word when None
        self.assertIn("APPLE", result[0]["words"])
        self.assertIn("banana", result[0]["words"])

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_raises_puzzle_pool_empty_error(self, mock_get_client, _mock_config_id):
        """RPC returning None (empty pool) must raise PuzzlePoolEmptyError."""
        client = _mock_client()
        mock_get_client.return_value = client
        # NULL return from the DB function → data is None
        client.rpc.return_value.execute.return_value = MagicMock(data=None)

        with self.assertRaises(PuzzlePoolEmptyError):
            get_puzzle_from_pool("classic")

    @patch("src.services.puzzle_pool_service._get_config_id")
    @patch("src.services.puzzle_pool_service._get_client")
    def test_raises_on_unknown_config(self, mock_get_client, mock_config_id):
        """A config slug that doesn't exist in the DB should propagate a ValueError."""
        mock_get_client.return_value = _mock_client()
        mock_config_id.side_effect = ValueError("Config 'mini' not found")

        with self.assertRaises(ValueError):
            get_puzzle_from_pool("mini")

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_display_text_takes_precedence_over_word(self, mock_get_client, _mock_config_id):
        """display_text (e.g. 'McCARTHY') should be used instead of the canonical lowercase word."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.rpc.return_value.execute.return_value = MagicMock(data=PUZZLE_ID)
        client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{
                "category_name": "Names",
                "sort_order": 0,
                "puzzle_words": [{"word": "mccarthy", "display_text": "McCARTHY"}],
            }]
        )

        result = get_puzzle_from_pool()
        self.assertIn("McCARTHY", result[0]["words"])
        self.assertNotIn("mccarthy", result[0]["words"])

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_calls_rpc_with_config_id(self, mock_get_client, _mock_config_id):
        """The DB function must be called with the config's UUID, not its name."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.rpc.return_value.execute.return_value = MagicMock(data=None)

        try:
            get_puzzle_from_pool("classic")
        except PuzzlePoolEmptyError:
            pass

        client.rpc.assert_called_once_with(
            "get_random_approved_puzzle",
            {"p_config_id": CONFIG_ID},
        )


# ---------------------------------------------------------------------------
# get_pool_stats
# ---------------------------------------------------------------------------

class TestGetPoolStats(unittest.TestCase):

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_counts_statuses_correctly(self, mock_get_client, _mock_config_id):
        """Puzzles with different statuses should be counted and returned per-status."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"status": "approved"},
                {"status": "approved"},
                {"status": "draft"},
                {"status": "rejected"},
            ]
        )

        stats = get_pool_stats("classic")

        self.assertEqual(stats["approved"], 2)
        self.assertEqual(stats["draft"], 1)
        self.assertEqual(stats["rejected"], 1)
        # Statuses that weren't seen should still be 0, not missing
        self.assertEqual(stats["validating"], 0)
        self.assertEqual(stats["served"], 0)
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["config"], "classic")

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_empty_pool_all_zeros(self, mock_get_client, _mock_config_id):
        """An empty pool should return all-zero counts, not KeyErrors."""
        client = _mock_client()
        mock_get_client.return_value = client
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        stats = get_pool_stats("classic")

        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["approved"], 0)
        self.assertIn("config", stats)


# ---------------------------------------------------------------------------
# seed_puzzle_to_pool
# ---------------------------------------------------------------------------

class TestSeedPuzzleToPool(unittest.TestCase):

    def _setup_seed_client(self, mock_get_client, mock_config_id, num_groups=1):
        """Configures the mock client for a seed with `num_groups` groups.

        The call sequence for each group is:
          1. table("puzzles").insert().execute()      → {id: PUZZLE_ID}
          2. table("puzzle_groups").insert().execute() → {id: GROUP_ID}
          3. table("puzzle_words").insert().execute()  → [] (we don't use the result)
        """
        client = _mock_client()
        mock_get_client.return_value = client
        mock_config_id.return_value = CONFIG_ID

        # Build the side_effect list: puzzle once, then (group + words) per group
        effects = [MagicMock(data=[{"id": PUZZLE_ID}])]
        for _ in range(num_groups):
            effects.append(MagicMock(data=[{"id": GROUP_ID}]))  # group insert
            effects.append(MagicMock(data=[]))                   # word batch insert

        client.table.return_value.insert.return_value.execute.side_effect = effects
        return client

    @patch("src.services.puzzle_pool_service._get_config_id")
    @patch("src.services.puzzle_pool_service._get_client")
    def test_returns_puzzle_id(self, mock_get_client, mock_config_id):
        """A successful seed should return the UUID of the newly created puzzle."""
        self._setup_seed_client(mock_get_client, mock_config_id)

        puzzle_data = {
            "connections": [
                {"relationship": "Fruits", "words": ["apple", "banana", "cherry", "date"]},
            ]
        }
        result = seed_puzzle_to_pool(puzzle_data, generation_model="claude-opus-4-6")

        self.assertEqual(result, PUZZLE_ID)

    @patch("src.services.puzzle_pool_service._get_config_id")
    @patch("src.services.puzzle_pool_service._get_client")
    def test_puzzle_seeded_with_draft_status(self, mock_get_client, mock_config_id):
        """The puzzle row must be inserted with status='draft'."""
        client = self._setup_seed_client(mock_get_client, mock_config_id)

        seed_puzzle_to_pool(
            {"connections": [{"relationship": "Fruits", "words": ["a", "b", "c", "d"]}]},
            generation_model="test-model",
        )

        # The very first insert call is the puzzles row
        first_insert_payload = client.table.return_value.insert.call_args_list[0][0][0]
        self.assertEqual(first_insert_payload["status"], "draft")
        self.assertEqual(first_insert_payload["generation_model"], "test-model")

    @patch("src.services.puzzle_pool_service._get_config_id")
    @patch("src.services.puzzle_pool_service._get_client")
    def test_words_stored_lowercase(self, mock_get_client, mock_config_id):
        """The 'word' column must always be lowercase; display_text preserves original case."""
        client = self._setup_seed_client(mock_get_client, mock_config_id)

        seed_puzzle_to_pool(
            {"connections": [{"relationship": "Names", "words": ["McCARTHY", "APPLE"]}]}
        )

        # The 3rd insert call (index 2) is the word batch for the first group
        word_batch = client.table.return_value.insert.call_args_list[2][0][0]
        for row in word_batch:
            self.assertEqual(row["word"], row["word"].lower())  # canonical form is lowercase
            self.assertEqual(row["display_text"], row["display_text"])  # preserves original

    @patch("src.services.puzzle_pool_service._get_config_id", return_value=CONFIG_ID)
    @patch("src.services.puzzle_pool_service._get_client")
    def test_raises_on_missing_connections(self, mock_get_client, _mock_config_id):
        """Omitting 'connections' entirely should raise ValueError with a clear message."""
        mock_get_client.return_value = _mock_client()

        with self.assertRaises(ValueError):
            seed_puzzle_to_pool({})

    @patch("src.services.puzzle_pool_service._get_config_id")
    @patch("src.services.puzzle_pool_service._get_client")
    def test_raises_on_connection_missing_relationship(self, mock_get_client, mock_config_id):
        """A connection dict without 'relationship' should raise ValueError."""
        client = _mock_client()
        mock_get_client.return_value = client
        mock_config_id.return_value = CONFIG_ID
        # The puzzle row is inserted before validation of individual connections
        client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": PUZZLE_ID}]
        )

        bad_data = {"connections": [{"words": ["apple", "banana", "cherry", "date"]}]}
        with self.assertRaises(ValueError):
            seed_puzzle_to_pool(bad_data)

    @patch("src.services.puzzle_pool_service._get_config_id")
    @patch("src.services.puzzle_pool_service._get_client")
    def test_sort_order_matches_connection_index(self, mock_get_client, mock_config_id):
        """sort_order on each group must match its position in the connections list."""
        client = self._setup_seed_client(mock_get_client, mock_config_id, num_groups=2)

        seed_puzzle_to_pool({
            "connections": [
                {"relationship": "Group A", "words": ["a", "b", "c", "d"]},
                {"relationship": "Group B", "words": ["e", "f", "g", "h"]},
            ]
        })

        # Insert calls: [0]=puzzle, [1]=group0, [2]=words0, [3]=group1, [4]=words1
        group0_payload = client.table.return_value.insert.call_args_list[1][0][0]
        group1_payload = client.table.return_value.insert.call_args_list[3][0][0]
        self.assertEqual(group0_payload["sort_order"], 0)
        self.assertEqual(group1_payload["sort_order"], 1)


# ---------------------------------------------------------------------------
# approve_puzzle
# ---------------------------------------------------------------------------

class TestApprovePuzzle(unittest.TestCase):

    @patch("src.services.puzzle_pool_service._get_client")
    def test_sets_status_approved(self, mock_get_client):
        """approve_puzzle must update status to 'approved' with score and report."""
        client = _mock_client()
        mock_get_client.return_value = client

        report = {"uniqueness": "pass", "ambiguity": "pass"}
        approve_puzzle(PUZZLE_ID, validation_score=0.92, validation_report=report)

        # Check what was passed to .update()
        update_payload = client.table.return_value.update.call_args[0][0]
        self.assertEqual(update_payload["status"], "approved")
        self.assertAlmostEqual(update_payload["validation_score"], 0.92)
        self.assertEqual(update_payload["validation_report"], report)
        # approved_at must be set (any non-None truthy value is acceptable)
        self.assertTrue(update_payload.get("approved_at"))

    @patch("src.services.puzzle_pool_service._get_client")
    def test_targets_correct_puzzle(self, mock_get_client):
        """The WHERE clause must use the provided puzzle_id."""
        client = _mock_client()
        mock_get_client.return_value = client

        approve_puzzle(PUZZLE_ID, validation_score=0.8, validation_report={})

        # .update({...}).eq("id", PUZZLE_ID)
        eq_args = client.table.return_value.update.return_value.eq.call_args[0]
        self.assertEqual(eq_args, ("id", PUZZLE_ID))


# ---------------------------------------------------------------------------
# reject_puzzle
# ---------------------------------------------------------------------------

class TestRejectPuzzle(unittest.TestCase):

    @patch("src.services.puzzle_pool_service._get_client")
    def test_sets_status_rejected(self, mock_get_client):
        """reject_puzzle must update status to 'rejected' with the validation report."""
        client = _mock_client()
        mock_get_client.return_value = client

        report = {"reason": "duplicate categories", "categories": ["Fruits", "Plants"]}
        reject_puzzle(PUZZLE_ID, validation_report=report)

        update_payload = client.table.return_value.update.call_args[0][0]
        self.assertEqual(update_payload["status"], "rejected")
        self.assertEqual(update_payload["validation_report"], report)

    @patch("src.services.puzzle_pool_service._get_client")
    def test_targets_correct_puzzle(self, mock_get_client):
        """The WHERE clause must use the provided puzzle_id."""
        client = _mock_client()
        mock_get_client.return_value = client

        reject_puzzle(PUZZLE_ID, validation_report={})

        eq_args = client.table.return_value.update.return_value.eq.call_args[0]
        self.assertEqual(eq_args, ("id", PUZZLE_ID))


if __name__ == "__main__":
    unittest.main()
