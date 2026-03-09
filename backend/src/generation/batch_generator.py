"""
Batch Puzzle Generator — uses the Anthropic Batch API for cost-efficient pool fills.

Unlike the multi-step puzzle_generator pipeline (~10-20 Claude calls per puzzle),
each batch request is a SINGLE Claude call that generates a complete puzzle in one
shot. This halves the per-puzzle cost (Anthropic charges 50% less for batch requests)
at the expense of quality — the iterative diversity seed, category brainstorm, and
red-herring refinement steps are skipped.

Intended use: nightly pool refills when you want volume cheaply, not on-demand
generation where quality is paramount. The higher-quality worker pipeline in
worker.py remains the preferred path for real-time generation.

Batch processing is async — results aren't available immediately. Batches complete
within 1-60 minutes. `run_batch_fill()` blocks until the batch is done.

Usage:
    from backend.src.generation.batch_generator import run_batch_fill

    result = run_batch_fill(count=20, config_name="classic")
    # result: {"submitted": 20, "succeeded": 17, "failed": 3, "puzzle_ids": [...]}
"""

import logging
import os
import time
from typing import Optional

import anthropic

from ..generation.group_generator import CATEGORY_TYPES
from ..services.puzzle_pool_service import seed_puzzle_to_pool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Opus 4.6 is used here because batch puzzles skip the iterative refinement steps,
# so a stronger model compensates for the reduced scaffolding. The 50% batch
# discount still makes this cheaper than multi-step Sonnet.
MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096

# How often (seconds) to poll the batch API for completion.
_POLL_INTERVAL_SECONDS = 30

# Maximum time to wait for a batch to complete before giving up.
_MAX_WAIT_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Tool schema — generates a complete 4-group puzzle in one call
# ---------------------------------------------------------------------------

_PUZZLE_TOOL = {
    "name": "submit_puzzle",
    "description": (
        "Submit a complete NYT Connections puzzle: exactly 4 groups of 4 words, "
        "each group sharing a hidden connection. Groups must span all four difficulty "
        "levels (one YELLOW, one GREEN, one BLUE, one PURPLE) and use distinct "
        "category types where possible."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "groups": {
                "type": "array",
                "description": "Exactly 4 groups, ordered easiest (YELLOW) to hardest (PURPLE).",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_name": {
                            "type": "string",
                            "description": (
                                "Specific, evocative label for the category. "
                                "Not generic like 'Animals' — be precise."
                            ),
                        },
                        "category_type": {
                            "type": "string",
                            "enum": CATEGORY_TYPES,
                            "description": "The connection style this group uses.",
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["yellow", "green", "blue", "purple"],
                        },
                        "words": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exactly 4 UPPERCASE words for this group.",
                        },
                        "design_notes": {
                            "type": "string",
                            "description": (
                                "Brief explanation of why this connection is valid and "
                                "any red-herring potential between groups."
                            ),
                        },
                    },
                    "required": [
                        "category_name", "category_type",
                        "difficulty", "words", "design_notes",
                    ],
                },
            },
        },
        "required": ["groups"],
    },
    # Cache breakpoint: system prompt + tool schema combined exceeds the 1024-token
    # Sonnet/Opus minimum required for prompt caching. All N batch requests reuse
    # the same cache entry, saving ~90% on input tokens for calls 2-N.
    "cache_control": {"type": "ephemeral"},
}

# ---------------------------------------------------------------------------
# System prompt (static, cached across all requests in the batch)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert puzzle designer for the NYT Connections game.

THE CONNECTIONS GAME:
Players see a 4×4 grid of 16 words and sort them into exactly 4 groups of 4, \
each sharing a hidden connection. Groups are colour-coded YELLOW (easiest) → \
GREEN → BLUE → PURPLE (hardest). Players get 4 attempts; wrong guesses cost one.

DIFFICULTY CALIBRATION:
  YELLOW — immediately obvious to most adults. Everyday knowledge.
  GREEN — requires a moment of thought or slightly less-common knowledge.
  BLUE — non-obvious; relies on specialised, cultural, or domain-specific knowledge.
  PURPLE — wordplay, lateral thinking, hidden patterns, or an 'aha!' reveal.

CATEGORY TYPES:
  synonyms         — words sharing a single meaning (e.g. 'Words meaning EXHAUSTED').
  members_of_set   — items in a specific named real-world category (e.g. 'Types of PASTA').
  fill_in_the_blank— each word completes the same phrase with a shared hidden word.
  wordplay         — structural/phonetic trick: hidden words, anagrams, homophones.
  compound_words   — each word pairs with the same hidden word to form a compound.
  cultural_knowledge— connection requires pop culture, history, or domain expertise.

QUALITY RULES:
  1. All 16 words must be distinct — no word appears in more than one group.
  2. Words must be UPPERCASE.
  3. Category names must be specific, not generic labels like 'Animals'.
  4. The category name's key word must NOT appear in the word list.
  5. Design for misdirection: words in each group should superficially fit other groups.
  6. Avoid clichés: no days of week, seasons, months, primary colours, planets, or \
card suits. These are the first things anyone thinks of — be surprising.\
"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_batch_fill(
    count: int,
    config_name: str = "classic",
    puzzle_config: Optional[dict] = None,
) -> dict:
    """
    Generate `count` puzzles via the Anthropic Batch API and seed them to the pool.

    Blocks until the batch completes (up to 1 hour). Use this for scheduled
    nightly runs, not on-demand requests.

    Args:
        count:         Number of puzzles to generate (1-100).
        config_name:   Pool config name (default "classic").
        puzzle_config: Optional hint dict passed as context to Claude
                       (e.g. {"theme_hint": "food"}).

    Returns:
        {
            "submitted":  int,        # number of batch requests sent
            "succeeded":  int,        # puzzles successfully generated and stored
            "failed":     int,        # requests that errored or produced invalid output
            "puzzle_ids": list[str],  # Supabase UUIDs of stored puzzles
        }
    """
    if not 1 <= count <= 100:
        raise ValueError(f"count must be between 1 and 100 (got {count})")

    client = _get_client()

    logger.info("Batch fill: submitting %d puzzle generation requests", count)
    batch = _submit_batch(client, count, puzzle_config or {})
    logger.info("Batch submitted: id=%s", batch.id)

    results = _poll_until_complete(client, batch.id)

    succeeded_count = 0
    failed_count = 0
    puzzle_ids: list[str] = []

    for result in results:
        if result.result.type != "succeeded":
            failed_count += 1
            logger.warning(
                "Batch request %s %s: %s",
                result.custom_id,
                result.result.type,
                getattr(result.result, "error", "no detail"),
            )
            continue

        puzzle_id = _store_result(result, config_name)
        if puzzle_id:
            succeeded_count += 1
            puzzle_ids.append(puzzle_id)
        else:
            failed_count += 1

    logger.info(
        "Batch fill complete: %d succeeded, %d failed, batch_id=%s",
        succeeded_count, failed_count, batch.id,
    )
    return {
        "submitted": count,
        "succeeded": succeeded_count,
        "failed": failed_count,
        "puzzle_ids": puzzle_ids,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


def _build_request(request_id: str, puzzle_config: dict) -> dict:
    """
    Build one Anthropic Batch API request dict for a single puzzle generation.
    """
    theme_clause = (
        f"Generate a puzzle with a loose theme of '{puzzle_config['theme_hint']}' "
        "— not every group needs to relate, but the overall flavour should lean that way.\n\n"
        if puzzle_config.get("theme_hint")
        else ""
    )

    prompt = (
        f"{theme_clause}"
        "Generate one complete NYT Connections puzzle: exactly 4 groups of 4 words.\n\n"
        "Requirements:\n"
        "- One group at each difficulty: YELLOW, GREEN, BLUE, PURPLE\n"
        "- Use at least 3 different category_types across the 4 groups\n"
        "- All 16 words must be unique — check before submitting\n"
        "- Words that superficially fit multiple groups make a better puzzle\n\n"
        "Call the submit_puzzle tool now."
    )

    return {
        "custom_id": request_id,
        "params": {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": [{"type": "text", "text": _SYSTEM_PROMPT}],
            "tools": [_PUZZLE_TOOL],
            "tool_choice": {"type": "tool", "name": "submit_puzzle"},
            "messages": [{"role": "user", "content": prompt}],
        },
    }


def _submit_batch(
    client: anthropic.Anthropic,
    count: int,
    puzzle_config: dict,
) -> anthropic.types.messages.MessageBatch:
    """Submit N puzzle generation requests as a single Anthropic batch."""
    requests = [
        _build_request(f"puzzle-{i:04d}", puzzle_config)
        for i in range(count)
    ]
    return client.messages.batches.create(requests=requests)


def _poll_until_complete(
    client: anthropic.Anthropic,
    batch_id: str,
) -> list:
    """
    Poll the batch API until processing_status == 'ended', then return all results.

    Raises RuntimeError if the batch doesn't complete within _MAX_WAIT_SECONDS.
    """
    deadline = time.monotonic() + _MAX_WAIT_SECONDS
    waited = 0

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            logger.info(
                "Batch %s ended: %d succeeded, %d errored, %d cancelled",
                batch_id,
                batch.request_counts.succeeded,
                batch.request_counts.errored,
                batch.request_counts.canceled,
            )
            return list(client.messages.batches.results(batch_id))

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Batch {batch_id} did not complete within {_MAX_WAIT_SECONDS}s "
                f"(status={batch.processing_status})"
            )

        logger.debug(
            "Batch %s still processing (waited %ds, processing=%d)",
            batch_id, waited, batch.request_counts.processing,
        )
        time.sleep(_POLL_INTERVAL_SECONDS)
        waited += _POLL_INTERVAL_SECONDS


def _store_result(result, config_name: str) -> Optional[str]:
    """
    Parse one succeeded batch result and seed it into the puzzle pool.

    Returns the puzzle UUID on success, or None if the result is malformed.
    """
    try:
        message = result.result.message
        tool_block = next(
            (b for b in message.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            logger.warning("Batch result %s: no tool_use block", result.custom_id)
            return None

        groups_raw = tool_block.input.get("groups", [])
        if len(groups_raw) != 4:
            logger.warning(
                "Batch result %s: expected 4 groups, got %d",
                result.custom_id, len(groups_raw),
            )
            return None

        # Validate all 16 words are unique.
        all_words = [w for g in groups_raw for w in g.get("words", [])]
        if len(all_words) != len(set(all_words)):
            logger.warning(
                "Batch result %s: duplicate words detected — skipping", result.custom_id
            )
            return None

        seed_data = {
            "config_name": config_name,
            "connections": [
                {
                    "relationship": g["category_name"],
                    "words": g["words"],
                    "category_type": g.get("category_type"),
                }
                for g in groups_raw
            ],
        }

        puzzle_id = seed_puzzle_to_pool(
            seed_data,
            generation_model=MODEL,
            generation_metadata={
                "source": "batch_generator",
                "difficulty_profile": "standard",
                "request_id": result.custom_id,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )
        logger.info("Stored batch puzzle: id=%s (request=%s)", puzzle_id, result.custom_id)
        return puzzle_id

    except Exception:
        logger.error(
            "Failed to store batch result %s", result.custom_id, exc_info=True
        )
        return None
