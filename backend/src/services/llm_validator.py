"""
LLM-based validator for AI-generated Connections puzzles.

Uses Claude to attempt to solve the puzzle and check for ambiguity.
This is the second layer of the validation pipeline — more expensive than
embedding analysis, but catches logical ambiguity, difficulty calibration,
and alternative-grouping problems that embeddings cannot see.

The validator produces a structured report covering:
  - Solver consistency  (can Claude repeatedly solve it the same way?)
  - Devil's advocate    (does Claude find alternative valid groupings?)
  - Difficulty calibration (is the puzzle appropriately hard for Haiku?)

Public API
----------
solve_puzzle_attempt(puzzle_words, num_groups, words_per_group, ...)  → list
self_consistency_check(puzzle_data, num_attempts=8)                   → dict
devils_advocate_check(puzzle_data, model=...)                         → dict
difficulty_calibration(puzzle_data)                                   → dict
validate_with_llm(puzzle_data)                                        → dict
"""

from __future__ import annotations

import logging
import os
import random
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_SOLVE_TEMPERATURE = 0.5
DEFAULT_NUM_ATTEMPTS = 8

# Auto-fail thresholds for validate_with_llm
AGREEMENT_TOO_EASY_THRESHOLD = 0.9   # agreement_rate above this + "too_easy" → reject
AGREEMENT_TOO_HARD_THRESHOLD = 0.1   # agreement_rate below this → unsolvable/ambiguous


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client():
    """Lazy-loads the Anthropic client (avoids import cost at module load time)."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic is not installed. Run: uv pip install anthropic"
        )
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return anthropic.Anthropic(api_key=api_key)


class _TokenTracker:
    """Accumulates token usage and API call counts across a validation run."""

    def __init__(self) -> None:
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0

    def record(self, response: Any) -> None:
        """Record usage from a direct API response object."""
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        self.api_calls += 1

    def to_dict(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "api_calls": self.api_calls,
        }


def _merge_token_usage(*usages: dict) -> dict:
    """Sums token_usage dicts returned by individual check functions."""
    merged = {"total_input_tokens": 0, "total_output_tokens": 0, "api_calls": 0}
    for u in usages:
        merged["total_input_tokens"] += u.get("total_input_tokens", 0)
        merged["total_output_tokens"] += u.get("total_output_tokens", 0)
        merged["api_calls"] += u.get("api_calls", 0)
    return merged


def _score_attempt(
    proposed: list[dict], intended: list[dict]
) -> tuple[int, list[bool]]:
    """
    Scores one solver attempt against the intended solution.

    Uses frozenset comparison on lowercased words so capitalisation differences
    don't count as mismatches.

    Returns:
        (num_correct_groups, per_intended_group_matched)
        where per_intended_group_matched[i] is True if intended group i was
        exactly reproduced in the proposed solution.
    """
    intended_sets = [frozenset(w.lower() for w in g["words"]) for g in intended]
    proposed_sets = [frozenset(w.lower() for w in p.get("words", [])) for p in proposed]
    per_group_matched = [iset in proposed_sets for iset in intended_sets]
    return sum(per_group_matched), per_group_matched


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

# reasoning is listed FIRST so Claude articulates its logic before committing
# to word assignments — same technique as design_notes in group_generator.py.
_SOLVE_TOOL = {
    "name": "submit_solution",
    "description": (
        "Submit your proposed solution to the Connections puzzle. "
        "You MUST complete the 'reasoning' field before listing groups."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": (
                    "Step-by-step analysis: spot candidate groupings, consider overlaps "
                    "and red herrings, rule out alternatives, then commit to your final answer."
                ),
            },
            "groups": {
                "type": "array",
                "description": "Your proposed groups. Each group must use exactly the right number of words.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_name": {
                            "type": "string",
                            "description": "A short name for the connection shared by these words.",
                        },
                        "words": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "The words in this group.",
                        },
                    },
                    "required": ["category_name", "words"],
                },
            },
        },
        "required": ["reasoning", "groups"],
    },
}

_DEVIL_TOOL = {
    "name": "submit_alternative",
    "description": "Submit your analysis of whether an alternative valid grouping exists.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": (
                    "Explain your search. What alternatives did you consider? "
                    "Why do or don't they constitute a genuinely valid alternative grouping?"
                ),
            },
            "found_alternative": {
                "type": "boolean",
                "description": "True only if you found a genuinely valid, fully defensible alternative.",
            },
            "alternative_groupings": {
                "type": ["array", "null"],
                "description": "The alternative groupings if found, else null.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_name": {"type": "string"},
                        "words": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["category_name", "words"],
                },
            },
        },
        "required": ["reasoning", "found_alternative", "alternative_groupings"],
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def solve_puzzle_attempt(
    puzzle_words: list[str],
    num_groups: int,
    words_per_group: int,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_SOLVE_TEMPERATURE,
    tracker: _TokenTracker | None = None,
) -> list[dict]:
    """
    Asks Claude to solve the puzzle given only the shuffled word list.

    The model sees no category names or hints — only the words and the
    structural constraints (how many groups, how many words per group).

    Args:
        puzzle_words:    All words in any order (caller shuffles before passing).
        num_groups:      Number of groups to find.
        words_per_group: Words per group.
        model:           Claude model ID.
        temperature:     Use > 0 for varied self-consistency sampling, 0 for
                         deterministic difficulty calibration.
        tracker:         Optional token tracker to accumulate usage.

    Returns:
        List of {"category_name": str, "words": list[str]}.
        Returns [] if the model produces no tool_use block.
    """
    client = _get_client()
    words_display = ", ".join(f'"{w}"' for w in puzzle_words)
    prompt = (
        f"You are solving a Connections puzzle. You will see {len(puzzle_words)} words "
        f"that must be divided into {num_groups} groups of exactly {words_per_group} words each.\n\n"
        f"Words: {words_display}\n\n"
        "Rules:\n"
        "- Each word belongs to exactly one group.\n"
        "- Every word must appear in exactly one group — no word may be repeated or omitted.\n"
        "- Groups share a hidden connection; find the most specific, defensible grouping.\n\n"
        "Think step-by-step: spot candidate groupings, consider overlaps and red herrings, "
        "then commit to your final answer."
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        tools=[_SOLVE_TOOL],
        tool_choice={"type": "tool", "name": "submit_solution"},
        messages=[{"role": "user", "content": prompt}],
    )
    if tracker:
        tracker.record(response)

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        logger.warning("solve_puzzle_attempt: no tool_use block in response")
        return []

    return [
        {"category_name": g["category_name"], "words": g["words"]}
        for g in tool_block.input.get("groups", [])
    ]


def self_consistency_check(
    puzzle_data: dict,
    num_attempts: int = DEFAULT_NUM_ATTEMPTS,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_SOLVE_TEMPERATURE,
) -> dict:
    """
    Runs solve_puzzle_attempt multiple times and aggregates results.

    Each attempt shuffles the word order independently so the model can't
    exploit positional patterns across runs.

    Returns:
        {
            "agreement_rate":     float  — fraction of attempts with all groups correct,
            "per_group_solve_rate": list[float] — per intended group solve rate,
            "common_mistakes":    list   — frequent wrong groupings across attempts,
            "consensus_solution": list   — most common non-overlapping groupings,
            "token_usage":        dict,
        }
    """
    connections = puzzle_data.get("connections", [])
    num_groups = len(connections)
    words_per_group = max((len(c.get("words", [])) for c in connections), default=4)
    all_words = [w for c in connections for w in c.get("words", [])]

    tracker = _TokenTracker()
    all_attempts: list[list[dict]] = []
    correct_full_attempts = 0
    per_group_matches: list[int] = [0] * num_groups

    for _ in range(num_attempts):
        shuffled = all_words.copy()
        random.shuffle(shuffled)
        proposed = solve_puzzle_attempt(
            puzzle_words=shuffled,
            num_groups=num_groups,
            words_per_group=words_per_group,
            model=model,
            temperature=temperature,
            tracker=tracker,
        )
        all_attempts.append(proposed)

        num_correct, per_group_matched = _score_attempt(proposed, connections)
        if num_correct == num_groups:
            correct_full_attempts += 1
        for i, matched in enumerate(per_group_matched):
            if matched:
                per_group_matches[i] += 1

    agreement_rate = correct_full_attempts / num_attempts if num_attempts > 0 else 0.0
    per_group_solve_rate = [count / num_attempts for count in per_group_matches]

    # Build a frequency table of every proposed (word_set, category_name) across attempts.
    intended_sets = [frozenset(w.lower() for w in c["words"]) for c in connections]
    proposed_counter: Counter = Counter()
    for attempt in all_attempts:
        for g in attempt:
            key = (frozenset(w.lower() for w in g.get("words", [])), g.get("category_name", ""))
            proposed_counter[key] += 1

    # Consensus solution: greedily pick the most frequent non-overlapping groups.
    consensus_solution: list[dict] = []
    used_words: set[str] = set()
    for (word_set, cat_name), count in proposed_counter.most_common(num_groups * 4):
        if len(consensus_solution) >= num_groups:
            break
        if not word_set & used_words:
            consensus_solution.append({
                "category_name": cat_name,
                "words": sorted(word_set),
                "frequency": count,
                "frequency_rate": round(count / num_attempts, 3),
            })
            used_words |= word_set

    # Common mistakes: frequent proposed groups that don't match any intended group.
    common_mistakes: list[dict] = []
    for (word_set, cat_name), count in proposed_counter.most_common(30):
        if word_set in intended_sets or count < 2:
            continue
        common_mistakes.append({
            "words": sorted(word_set),
            "category_name": cat_name,
            "frequency": count,
            "frequency_rate": round(count / num_attempts, 3),
        })
        if len(common_mistakes) >= 5:
            break

    return {
        "agreement_rate": round(agreement_rate, 4),
        "per_group_solve_rate": [round(r, 4) for r in per_group_solve_rate],
        "common_mistakes": common_mistakes,
        "consensus_solution": consensus_solution,
        "token_usage": tracker.to_dict(),
    }


def devils_advocate_check(
    puzzle_data: dict,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Shows Claude the full puzzle (words + intended groupings) and asks it to
    find a genuinely valid alternative grouping. If it finds one, the puzzle
    has an ambiguity problem.

    Uses a low temperature (0.3) to encourage careful, consistent analysis
    rather than creative free-association.

    Returns:
        {
            "found_alternative": bool,
            "alternative_groupings": list | None,
            "reasoning": str,
            "token_usage": dict,
        }
    """
    connections = puzzle_data.get("connections", [])
    groupings_text = "\n".join(
        f'  Group {i + 1} — "{c["relationship"]}": '
        + ", ".join(f'"{w}"' for w in c.get("words", []))
        for i, c in enumerate(connections)
    )
    all_words_sorted = sorted(w for c in connections for w in c.get("words", []))
    words_display = ", ".join(f'"{w}"' for w in all_words_sorted)

    prompt = (
        "You are a puzzle quality reviewer. Below is a Connections puzzle with its "
        "intended solution. Your job is to play devil's advocate: search hard for an "
        "ALTERNATIVE valid grouping — a completely different way to group the same words "
        "into the same number of groups that would also be logical and defensible.\n\n"
        f"All words: {words_display}\n\n"
        f"Intended solution:\n{groupings_text}\n\n"
        "An alternative grouping is valid ONLY if:\n"
        "- It uses ALL the same words.\n"
        "- Each word appears in exactly one group.\n"
        "- Each group has a clear, specific, defensible connection.\n"
        "- The alternative is meaningfully different from the intended solution "
        "(not just renaming a category).\n\n"
        "Think hard. If you cannot find a genuinely valid alternative, say so honestly. "
        "Do not manufacture a weak or vague alternative just to have one."
    )

    tracker = _TokenTracker()
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0.3,
        tools=[_DEVIL_TOOL],
        tool_choice={"type": "tool", "name": "submit_alternative"},
        messages=[{"role": "user", "content": prompt}],
    )
    tracker.record(response)

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        logger.warning("devils_advocate_check: no tool_use block in response")
        return {
            "found_alternative": False,
            "alternative_groupings": None,
            "reasoning": "No tool response received.",
            "token_usage": tracker.to_dict(),
        }

    result = tool_block.input
    return {
        "found_alternative": bool(result.get("found_alternative", False)),
        "alternative_groupings": result.get("alternative_groupings"),
        "reasoning": result.get("reasoning", ""),
        "token_usage": tracker.to_dict(),
    }


def difficulty_calibration(
    puzzle_data: dict,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Runs one deterministic (temperature=0) solve attempt as a difficulty signal.

    Assessment:
      "too_easy"      — solver gets all groups correct
      "appropriate"   — solver gets 2–3 groups correct
      "hard_or_flawed"  — solver gets 0–1 groups correct

    A "too_easy" result combined with a high self-consistency agreement rate is
    the trigger for the auto-fail in validate_with_llm.

    Returns:
        {
            "assessment":      str,
            "groups_correct":  int,
            "solver_solution": list[dict],
            "token_usage":     dict,
        }
    """
    connections = puzzle_data.get("connections", [])
    num_groups = len(connections)
    words_per_group = max((len(c.get("words", [])) for c in connections), default=4)
    all_words = [w for c in connections for w in c.get("words", [])]
    random.shuffle(all_words)

    tracker = _TokenTracker()
    proposed = solve_puzzle_attempt(
        puzzle_words=all_words,
        num_groups=num_groups,
        words_per_group=words_per_group,
        model=model,
        temperature=0,
        tracker=tracker,
    )

    num_correct, _ = _score_attempt(proposed, connections)

    if num_correct == num_groups:
        assessment = "too_easy"
    elif num_correct >= 2:
        assessment = "appropriate"
    else:
        assessment = "hard_or_flawed"

    return {
        "assessment": assessment,
        "groups_correct": num_correct,
        "solver_solution": proposed,
        "token_usage": tracker.to_dict(),
    }


def validate_with_llm(puzzle_data: dict) -> dict:
    """
    Orchestrates all LLM-based validation checks and returns a combined report.

    Runs in order:
      1. difficulty_calibration — quick single-shot signal (1 API call)
      2. self_consistency_check — 8 attempts at temperature 0.5 (8 API calls)
      3. devils_advocate_check  — one careful ambiguity probe (1 API call)

    Auto-fail conditions:
      - agreement_rate > 0.9 AND difficulty is "too_easy" → trivially easy puzzle
      - devils_advocate found a valid alternative grouping → ambiguous puzzle
      - agreement_rate < 0.1 → puzzle may be unsolvable or deeply flawed

    Args:
        puzzle_data: {"connections": [...]} — same format as embedding_validator.

    Returns:
        {
            "passed":               bool,
            "solver_consistency":   dict,
            "ambiguity_check":      dict,
            "difficulty_assessment": dict,
            "warnings":             list[str],
            "auto_fail_reasons":    list[str],
            "token_usage":          dict,
        }
    """
    warnings: list[str] = []
    auto_fail_reasons: list[str] = []

    # ── (a) Difficulty calibration ────────────────────────────────────────────
    logger.info("Running difficulty calibration (1 API call, temp=0) …")
    difficulty = difficulty_calibration(puzzle_data)

    # ── (b) Self-consistency check ────────────────────────────────────────────
    logger.info("Running self-consistency check (%d attempts) …", DEFAULT_NUM_ATTEMPTS)
    consistency = self_consistency_check(puzzle_data)

    # ── (c) Devil's advocate ──────────────────────────────────────────────────
    logger.info("Running devil's advocate check …")
    ambiguity = devils_advocate_check(puzzle_data)

    # ── Evaluate auto-fail conditions ─────────────────────────────────────────
    agreement_rate = consistency["agreement_rate"]

    if agreement_rate > AGREEMENT_TOO_EASY_THRESHOLD and difficulty["assessment"] == "too_easy":
        auto_fail_reasons.append(
            f"Puzzle is trivially easy: Haiku solved it at temp=0 AND self-consistency "
            f"agreement_rate {agreement_rate:.2%} > {AGREEMENT_TOO_EASY_THRESHOLD:.0%}."
        )

    if ambiguity["found_alternative"]:
        auto_fail_reasons.append(
            "Devil's advocate found a valid alternative grouping — puzzle is ambiguous."
        )

    if agreement_rate < AGREEMENT_TOO_HARD_THRESHOLD:
        auto_fail_reasons.append(
            f"Self-consistency agreement_rate {agreement_rate:.2%} < "
            f"{AGREEMENT_TOO_HARD_THRESHOLD:.0%} — puzzle may be unsolvable or deeply ambiguous."
        )

    # ── Soft warnings ─────────────────────────────────────────────────────────
    if difficulty["assessment"] == "hard_or_flawed" and agreement_rate >= AGREEMENT_TOO_HARD_THRESHOLD:
        warnings.append(
            f"Haiku got {difficulty['groups_correct']} group(s) correct at temp=0 — "
            "consider whether the puzzle is appropriately hard or structurally flawed."
        )

    if consistency["common_mistakes"]:
        top_mistake = consistency["common_mistakes"][0]
        warnings.append(
            f"Most common wrong grouping (rate {top_mistake['frequency_rate']:.0%}): "
            f"{sorted(top_mistake['words'])} as \"{top_mistake['category_name']}\""
        )

    # ── Aggregate token usage ─────────────────────────────────────────────────
    total_token_usage = _merge_token_usage(
        difficulty["token_usage"],
        consistency["token_usage"],
        ambiguity["token_usage"],
    )

    return {
        "passed": len(auto_fail_reasons) == 0,
        "solver_consistency": consistency,
        "ambiguity_check": ambiguity,
        "difficulty_assessment": difficulty,
        "warnings": warnings,
        "auto_fail_reasons": auto_fail_reasons,
        "token_usage": total_token_usage,
    }


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    # Same puzzle used in embedding_validator.py for easy back-to-back comparison.
    # Group 0 (yellow): pasta types — high semantic coherence, should be easy
    # Group 1 (green):  string instruments — moderate coherence
    # Group 2 (blue):   ___ fish — low embedding coherence (fill-in-the-blank)
    # Group 3 (purple): things that can be "grand" — tricky cross-domain group
    EXAMPLE_PUZZLE = {
        "connections": [
            {
                "relationship": "Types of pasta",
                "words": ["penne", "rigatoni", "fusilli", "farfalle"],
                "category_type": "members_of_set",
            },
            {
                "relationship": "Orchestral string instruments",
                "words": ["violin", "viola", "cello", "double bass"],
                "category_type": "members_of_set",
            },
            {
                "relationship": "___ fish",
                "words": ["sword", "cat", "star", "jelly"],
                "category_type": "fill_in_the_blank",
            },
            {
                "relationship": "Things that can be 'grand'",
                "words": ["piano", "jury", "canyon", "slam"],
                "category_type": "compound_words",
            },
        ]
    }

    print("Running LLM validation …\n")
    report = validate_with_llm(EXAMPLE_PUZZLE)

    # Strip large nested dicts for cleaner terminal output
    printable = {
        k: v for k, v in report.items()
        if k not in ("solver_consistency", "ambiguity_check", "difficulty_assessment")
    }
    printable["difficulty_assessment"] = {
        k: v for k, v in report["difficulty_assessment"].items()
        if k != "token_usage"
    }
    printable["solver_consistency"] = {
        k: v for k, v in report["solver_consistency"].items()
        if k not in ("consensus_solution", "token_usage")
    }
    printable["ambiguity_check"] = {
        k: v for k, v in report["ambiguity_check"].items()
        if k != "token_usage"
    }

    print(json.dumps(printable, indent=2))
    print(f"\nPassed: {report['passed']}")
    print(f"Token usage: {report['token_usage']}")

    if report["auto_fail_reasons"]:
        print("\nAuto-fail reasons:")
        for r in report["auto_fail_reasons"]:
            print(f"  ✗ {r}")
    if report["warnings"]:
        print("\nWarnings:")
        for w in report["warnings"]:
            print(f"  ⚠ {w}")
