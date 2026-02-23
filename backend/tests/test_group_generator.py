"""
Tests for group_generator.py — Phase 3 of the puzzle generation pipeline.

All Anthropic API calls are mocked so tests run instantly and offline.
The strategy mirrors test_puzzle_pool_service.py: patch the external dependency
at the import path used by the module under test.

Coverage:
  - generate_single_group → happy path, argument validation, API call shape,
                            retry logic, RuntimeError on exhausted retries,
                            RuntimeError when no tool_use block in response
  - _build_prompt         → first group vs. subsequent groups, existing group
                            listing, anti-cliché warning, red herring rule,
                            field-ordering instruction, difficulty/category type
"""

import os
import unittest
from unittest.mock import MagicMock, call, patch

import anthropic as anthropic_lib

from src.generation.group_generator import (
    CATEGORY_TYPES,
    MAX_TOKENS,
    MODEL,
    TEMPERATURE,
    _build_prompt,
    generate_single_group,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

# A valid tool_use response dict that satisfies the tool schema.
_VALID_GROUP = {
    "category_name": "Things with HANDLES",
    "design_notes": (
        "RULE: Each word can precede HANDLE to form a compound word. "
        "VERIFICATION: MUG: mughandle ✓. DOOR: doorhandle ✓. "
        "BAG: baghandle ✓. PAN: panhandle ✓."
    ),
    "words": ["MUG", "DOOR", "BAG", "PAN"],
    "candidate_words": ["MUG", "DOOR", "BAG", "PAN", "KNIFE", "BROOM", "CUP", "DRAWER"],
}

# A pre-existing group to use as context when testing the red herring path.
_EXISTING_GROUP = {
    "category_name": "___ BALL",
    "words": ["FIRE", "SNOW", "FOOT", "BASE"],
}


def _make_tool_use_response(input_data: dict) -> MagicMock:
    """Returns a mock Anthropic Message containing one tool_use content block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = input_data

    response = MagicMock()
    response.content = [tool_block]
    return response


def _make_api_error() -> anthropic_lib.APIConnectionError:
    """Creates a real APIConnectionError instance (the simplest APIError subclass).

    We use the real exception class (not a MagicMock) so that the
    `except anthropic.APIError` clause in generate_single_group actually catches it.
    APIConnectionError only requires a `request` argument, which we mock.
    """
    return anthropic_lib.APIConnectionError(request=MagicMock())


# ---------------------------------------------------------------------------
# generate_single_group — argument validation (no API calls)
# ---------------------------------------------------------------------------

class TestGenerateSingleGroupValidation(unittest.TestCase):

    def test_raises_on_invalid_difficulty(self):
        """Unknown difficulty tier must raise ValueError before any API call is made."""
        with self.assertRaises(ValueError) as ctx:
            generate_single_group("synonyms", [], difficulty="red")
        self.assertIn("red", str(ctx.exception))

    def test_raises_on_invalid_category_type(self):
        """Unknown category_type must raise ValueError before any API call is made."""
        with self.assertRaises(ValueError) as ctx:
            generate_single_group("made_up_type", [], difficulty="yellow")
        self.assertIn("made_up_type", str(ctx.exception))

    def test_all_valid_difficulties_are_accepted(self):
        """All four NYT colour tiers must not raise ValueError."""
        for difficulty in ("yellow", "green", "blue", "purple"):
            with (
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
                patch("src.generation.group_generator.anthropic.Anthropic") as mock_cls,
            ):
                mock_cls.return_value.messages.create.return_value = (
                    _make_tool_use_response(_VALID_GROUP)
                )
                # Should not raise — the loop will fail the test if it does.
                try:
                    generate_single_group("synonyms", [], difficulty=difficulty)
                except ValueError:
                    self.fail(f"ValueError raised unexpectedly for difficulty={difficulty!r}")

    def test_all_valid_category_types_are_accepted(self):
        """Every entry in CATEGORY_TYPES must not raise ValueError."""
        for cat_type in CATEGORY_TYPES:
            with (
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
                patch("src.generation.group_generator.anthropic.Anthropic") as mock_cls,
            ):
                mock_cls.return_value.messages.create.return_value = (
                    _make_tool_use_response(_VALID_GROUP)
                )
                try:
                    generate_single_group(cat_type, [], difficulty="green")
                except ValueError:
                    self.fail(f"ValueError raised unexpectedly for category_type={cat_type!r}")


# ---------------------------------------------------------------------------
# generate_single_group — happy path (API call shape + return value)
# ---------------------------------------------------------------------------

class TestGenerateSingleGroupHappyPath(unittest.TestCase):
    """Verifies that the function calls the Anthropic API correctly and returns
    the tool_use block's input dict unchanged."""

    def setUp(self):
        # Start patches that every test in this class needs.
        self.env_patcher = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
        self.env_patcher.start()

        self.anthropic_patcher = patch(
            "src.generation.group_generator.anthropic.Anthropic"
        )
        self.mock_cls = self.anthropic_patcher.start()
        self.mock_client = self.mock_cls.return_value
        self.mock_client.messages.create.return_value = _make_tool_use_response(_VALID_GROUP)

    def tearDown(self):
        self.env_patcher.stop()
        self.anthropic_patcher.stop()

    def test_returns_tool_input_dict(self):
        """The function must return the tool_use block's input dict, not the whole response."""
        result = generate_single_group("synonyms", [], difficulty="green")
        self.assertEqual(result, _VALID_GROUP)

    def test_passes_correct_model_constant(self):
        """The API call must use the module-level MODEL constant."""
        generate_single_group("synonyms", [], difficulty="green")
        _, kwargs = self.mock_client.messages.create.call_args
        self.assertEqual(kwargs["model"], MODEL)

    def test_passes_correct_temperature_constant(self):
        """The API call must use the module-level TEMPERATURE constant."""
        generate_single_group("synonyms", [], difficulty="green")
        _, kwargs = self.mock_client.messages.create.call_args
        self.assertEqual(kwargs["temperature"], TEMPERATURE)

    def test_passes_correct_max_tokens_constant(self):
        """The API call must use the module-level MAX_TOKENS constant."""
        generate_single_group("synonyms", [], difficulty="green")
        _, kwargs = self.mock_client.messages.create.call_args
        self.assertEqual(kwargs["max_tokens"], MAX_TOKENS)

    def test_forces_specific_tool_choice(self):
        """tool_choice must force submit_word_group to guarantee structured output."""
        generate_single_group("synonyms", [], difficulty="green")
        _, kwargs = self.mock_client.messages.create.call_args
        self.assertEqual(kwargs["tool_choice"]["type"], "tool")
        self.assertEqual(kwargs["tool_choice"]["name"], "submit_word_group")

    def test_sends_user_message_with_prompt(self):
        """The messages list must contain a user-role message with the built prompt."""
        generate_single_group("synonyms", [], difficulty="green")
        _, kwargs = self.mock_client.messages.create.call_args
        messages = kwargs["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertIsInstance(messages[0]["content"], str)
        # The prompt is non-empty and contains key structural elements.
        self.assertGreater(len(messages[0]["content"]), 50)

    def test_initialises_client_with_api_key_from_env(self):
        """Anthropic client must be initialised with ANTHROPIC_API_KEY from the environment."""
        generate_single_group("synonyms", [], difficulty="green")
        self.mock_cls.assert_called_once_with(api_key="test-key")

    def test_custom_words_per_group_appears_in_prompt(self):
        """A non-default words_per_group value must be reflected in the sent prompt."""
        generate_single_group("synonyms", [], words_per_group=5, difficulty="green")
        _, kwargs = self.mock_client.messages.create.call_args
        prompt = kwargs["messages"][0]["content"]
        self.assertIn("5", prompt)


# ---------------------------------------------------------------------------
# generate_single_group — retry logic and error handling
# ---------------------------------------------------------------------------

class TestGenerateSingleGroupRetry(unittest.TestCase):

    @patch("src.generation.group_generator.time.sleep")  # skip real waits
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.generation.group_generator.anthropic.Anthropic")
    def test_retries_on_api_error_and_eventually_succeeds(self, mock_cls, mock_sleep):
        """Two APIErrors followed by a success → return the successful result."""
        mock_client = mock_cls.return_value
        mock_client.messages.create.side_effect = [
            _make_api_error(),
            _make_api_error(),
            _make_tool_use_response(_VALID_GROUP),
        ]

        result = generate_single_group("synonyms", [], difficulty="green")

        self.assertEqual(result, _VALID_GROUP)
        # Should have been called exactly 3 times (2 failures + 1 success).
        self.assertEqual(mock_client.messages.create.call_count, 3)

    @patch("src.generation.group_generator.time.sleep")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.generation.group_generator.anthropic.Anthropic")
    def test_exponential_backoff_sleep_durations(self, mock_cls, mock_sleep):
        """Retry waits must be 1 s then 2 s (2^0, 2^1) — not constant or linear."""
        mock_client = mock_cls.return_value
        mock_client.messages.create.side_effect = [
            _make_api_error(),
            _make_api_error(),
            _make_tool_use_response(_VALID_GROUP),
        ]

        generate_single_group("synonyms", [], difficulty="green")

        # First retry sleeps 1 s, second retry sleeps 2 s.
        self.assertEqual(mock_sleep.call_args_list, [call(1), call(2)])

    @patch("src.generation.group_generator.time.sleep")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.generation.group_generator.anthropic.Anthropic")
    def test_raises_runtime_error_after_three_failures(self, mock_cls, mock_sleep):
        """Three consecutive APIErrors must surface as RuntimeError — not be swallowed."""
        mock_client = mock_cls.return_value
        mock_client.messages.create.side_effect = [
            _make_api_error(),
            _make_api_error(),
            _make_api_error(),
        ]

        with self.assertRaises(RuntimeError):
            generate_single_group("synonyms", [], difficulty="green")

        # All 3 attempts must have been tried before giving up.
        self.assertEqual(mock_client.messages.create.call_count, 3)

    @patch("src.generation.group_generator.time.sleep")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.generation.group_generator.anthropic.Anthropic")
    def test_no_sleep_on_first_attempt(self, mock_cls, mock_sleep):
        """The first attempt must not sleep — backoff only applies to retries."""
        mock_client = mock_cls.return_value
        mock_client.messages.create.return_value = _make_tool_use_response(_VALID_GROUP)

        generate_single_group("synonyms", [], difficulty="green")

        mock_sleep.assert_not_called()

    @patch("src.generation.group_generator.time.sleep")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.generation.group_generator.anthropic.Anthropic")
    def test_raises_runtime_error_when_no_tool_use_block(self, mock_cls, mock_sleep):
        """A response with only text blocks (no tool_use) must raise RuntimeError."""
        mock_client = mock_cls.return_value
        # A text-only response — what happens if tool_choice is ignored.
        text_block = MagicMock()
        text_block.type = "text"
        mock_client.messages.create.return_value = MagicMock(content=[text_block])

        with self.assertRaises(RuntimeError):
            generate_single_group("synonyms", [], difficulty="green")


# ---------------------------------------------------------------------------
# _build_prompt — structure and content (pure function, no mocking needed)
# ---------------------------------------------------------------------------

class TestBuildPrompt(unittest.TestCase):
    """Tests _build_prompt directly since it's a pure function.

    All conditional behaviour (first group vs. later groups, red herring rules,
    existing group listing) can be verified without any API calls or mocks.
    """

    # --- Anti-cliché and category/difficulty embedding ---

    def test_contains_anti_cliche_warning(self):
        """The prompt must warn against overused categories like days and seasons."""
        prompt = _build_prompt("synonyms", [], 4, "yellow")
        self.assertIn("days of the week", prompt)
        self.assertIn("seasons", prompt)

    def test_embeds_category_type_description(self):
        """Each category type's description must appear verbatim in the prompt."""
        prompt = _build_prompt("fill_in_the_blank", [], 4, "green")
        self.assertIn("FILL IN THE BLANK", prompt)

    def test_embeds_difficulty_description_for_all_tiers(self):
        """The difficulty tier name must appear in the prompt for every valid tier."""
        for difficulty in ("yellow", "green", "blue", "purple"):
            prompt = _build_prompt("synonyms", [], 4, difficulty)
            self.assertIn(difficulty.upper(), prompt)

    def test_words_per_group_appears_in_prompt(self):
        """The words_per_group count must be stated in the prompt."""
        for n in (4, 5, 6):
            prompt = _build_prompt("synonyms", [], n, "green")
            self.assertIn(str(n), prompt)

    # --- First group (no existing groups) ---

    def test_first_group_shows_no_existing_groups_message(self):
        """With no prior groups, the prompt must state there are none."""
        prompt = _build_prompt("synonyms", [], 4, "yellow")
        self.assertIn("None", prompt)

    def test_first_group_omits_red_herring_rule(self):
        """First group has no prior groups to plant a red herring into — rule must be absent."""
        prompt = _build_prompt("synonyms", [], 4, "yellow")
        # The strict RED HERRING rule block only appears for subsequent groups.
        self.assertNotIn("RED HERRING —", prompt)
        self.assertNotIn("GENUINELY satisfies THIS group", prompt)

    # --- Subsequent groups (existing groups provided) ---

    def test_existing_groups_trigger_red_herring_rule(self):
        """With prior groups present, the strict red herring definition must be included."""
        prompt = _build_prompt("synonyms", [_EXISTING_GROUP], 4, "green")
        self.assertIn("RED HERRING —", prompt)
        self.assertIn("GENUINELY satisfies THIS group", prompt)

    def test_red_herring_rule_includes_forbidden_shortcut_warning(self):
        """The FORBIDDEN line must be present so Claude doesn't just recycle old words."""
        prompt = _build_prompt("synonyms", [_EXISTING_GROUP], 4, "green")
        self.assertIn("FORBIDDEN", prompt)

    def test_existing_group_words_listed_in_prompt(self):
        """Words from prior groups must appear so Claude avoids reusing them."""
        prompt = _build_prompt("synonyms", [_EXISTING_GROUP], 4, "green")
        for word in _EXISTING_GROUP["words"]:
            self.assertIn(word, prompt)

    def test_existing_group_category_name_listed_in_prompt(self):
        """Category names of prior groups must appear so Claude understands the context."""
        prompt = _build_prompt("synonyms", [_EXISTING_GROUP], 4, "green")
        self.assertIn(_EXISTING_GROUP["category_name"], prompt)

    def test_multiple_existing_groups_all_listed(self):
        """ALL prior groups must be listed, not just the most recent one."""
        group_a = {"category_name": "Group A", "words": ["ALPHA", "BETA"]}
        group_b = {"category_name": "Group B", "words": ["GAMMA", "DELTA"]}
        prompt = _build_prompt("synonyms", [group_a, group_b], 4, "green")

        for word in ("ALPHA", "BETA", "GAMMA", "DELTA"):
            self.assertIn(word, prompt)
        self.assertIn("Group A", prompt)
        self.assertIn("Group B", prompt)

    # --- Field ordering instruction (design_notes before words) ---

    def test_field_ordering_instruction_is_present(self):
        """The prompt must instruct Claude to fill design_notes before the word lists."""
        prompt = _build_prompt("synonyms", [], 4, "green")
        self.assertIn("design_notes", prompt)
        self.assertIn("words", prompt)

    def test_design_notes_mentioned_before_words_in_ordering_section(self):
        """design_notes must appear earlier than words in the ordering instruction.

        The schema places design_notes before words so the model verifies words
        in its notes before committing to the word list. The prompt ordering
        instruction must reinforce this same sequence.
        """
        prompt = _build_prompt("synonyms", [], 4, "green")
        # Locate the positions within the ordering instruction block.
        # Both terms appear elsewhere too, so we find the ordering section first.
        ordering_start = prompt.index("WHEN CALLING THE TOOL")
        ordering_section = prompt[ordering_start:]

        notes_pos = ordering_section.index("design_notes")
        words_pos = ordering_section.index("words")
        self.assertLess(notes_pos, words_pos)


if __name__ == "__main__":
    unittest.main()
