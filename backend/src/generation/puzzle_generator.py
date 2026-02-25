"""
Puzzle Generator — Phase 4 of the Connections puzzle generation pipeline.

Composes group_generator.py into a full iterative puzzle generation pipeline.
Each step calls Claude at a different temperature calibrated to its task:

  Step 1 (temp=1.0): Diversity Seed — four domain seeds + creative story to
                     prevent thematic repetition across pipeline runs.
  Step 2 (temp=0.9): Category Brainstorm — 6-8 candidate themes; select best N.
  Step 3 (varies):   Iterative Group Building — generate_single_group() per category.
  Step 4 (temp=0.7): Red Herring Refinement — swap words to maximise misdirection.
  Step 5:            Final Assembly — package into puzzle dict for seed_puzzle_to_pool().

Token tracking note: steps 1, 2, and 4 call Claude directly so input/output token
counts are exact. Step 3 delegates to generate_single_group() which manages its own
client; those tokens are not captured in total_*_tokens but are reflected in api_calls.

Usage:
    from backend.src.generation.puzzle_generator import generate_puzzle

    puzzle = generate_puzzle({
        "num_groups": 4,
        "words_per_group": 4,
        "difficulty_profile": "standard",
        "theme_hint": "food",
    })
    # Returns: {"groups": [...], "generation_metadata": {...}}
    # Returns None on unrecoverable failure — details logged at ERROR level.
"""

import logging
import os
import time
from typing import Optional

import anthropic

from .group_generator import CATEGORY_TYPES, generate_single_group

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2048

# Canonical difficulty order — used for sorting and rank assignment.
_LEVEL_ORDER = ["yellow", "green", "blue", "purple"]

_DIFFICULTY_TO_RANK = {level: i + 1 for i, level in enumerate(_LEVEL_ORDER)}

# Four-group difficulty sequences per profile. _get_difficulty_sequence() scales
# these to other group counts by sampling or repeating.
_BASE_PROFILES = {
    "easy":     ["yellow", "yellow", "green",  "blue"],
    "standard": ["yellow", "green",  "blue",   "purple"],
    "hard":     ["green",  "blue",   "purple", "purple"],
}


# ---------------------------------------------------------------------------
# Token tracker
# ---------------------------------------------------------------------------

class _TokenTracker:
    """
    Accumulates token usage and API call counts across pipeline steps.

    Only steps that call the Anthropic client directly (1, 2, 4) contribute
    to total_input_tokens and total_output_tokens. Step 3, which delegates to
    generate_single_group(), increments api_calls via add_calls() only.
    """

    def __init__(self) -> None:
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0

    def record(self, response: anthropic.types.Message) -> None:
        """Record usage from a direct API response object."""
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        self.api_calls += 1

    def add_calls(self, count: int) -> None:
        """Increment call counter for steps that manage their own client."""
        self.api_calls += count


# ---------------------------------------------------------------------------
# Tool schemas for structured Claude outputs
# ---------------------------------------------------------------------------

_SEED_TOOL = {
    "name": "submit_seed",
    "description": "Submit 4 seed words from different domains and a creative story.",
    "input_schema": {
        "type": "object",
        "properties": {
            "seed_words": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 4 UPPERCASE seed words, each from a different domain.",
            },
            "story": {
                "type": "string",
                "description": (
                    "A creative 2-3 sentence story incorporating all 4 seed words naturally. "
                    "The story's domain juxtaposition should spark varied category ideas."
                ),
            },
        },
        "required": ["seed_words", "story"],
    },
}

_BRAINSTORM_TOOL = {
    "name": "submit_categories",
    "description": "Submit 6-8 candidate category themes and select the best subset.",
    "input_schema": {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "description": "Between 6 and 8 candidate category themes.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_name": {
                            "type": "string",
                            "description": "Specific, evocative label (not generic like 'Animals').",
                        },
                        "category_type": {
                            "type": "string",
                            "enum": CATEGORY_TYPES,
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["yellow", "green", "blue", "purple"],
                        },
                        "red_herring_potential": {
                            "type": "string",
                            "description": "Brief note on why this category could be confused with others.",
                        },
                    },
                    "required": [
                        "category_name", "category_type",
                        "difficulty", "red_herring_potential",
                    ],
                },
            },
            "selected_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "0-based indices of the best categories from candidates[]. "
                    "Must satisfy: ≥2 different category_types, difficulty levels span the range."
                ),
            },
            "selection_reasoning": {
                "type": "string",
                "description": "Why this selection maximises puzzle quality and cross-group misdirection.",
            },
        },
        "required": ["candidates", "selected_indices", "selection_reasoning"],
    },
}

_REFINEMENT_TOOL = {
    "name": "submit_refinement",
    "description": "Submit cross-group red herring analysis and suggested word swaps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "existing_red_herrings": {
                "type": "array",
                "description": "Cross-group red herrings already present in the puzzle.",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "actual_group": {"type": "string"},
                        "confused_with_group": {"type": "string"},
                        "strength": {
                            "type": "string",
                            "enum": ["weak", "moderate", "strong"],
                        },
                    },
                    "required": ["word", "actual_group", "confused_with_group", "strength"],
                },
            },
            "suggested_swaps": {
                "type": "array",
                "description": "Up to 3 word swaps that increase cross-group misdirection.",
                "items": {
                    "type": "object",
                    "properties": {
                        "group_index": {
                            "type": "integer",
                            "description": "0-based index of the group to modify.",
                        },
                        "old_word": {"type": "string"},
                        "new_word": {
                            "type": "string",
                            "description": "Must appear in that group's candidate_words list.",
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["group_index", "old_word", "new_word", "reason"],
                },
            },
            "flagged_obscure": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Words that feel too obscure or ambiguous for the puzzle.",
            },
            "analysis": {
                "type": "string",
                "description": "Overall cross-group misdirection assessment.",
            },
        },
        "required": [
            "existing_red_herrings", "suggested_swaps",
            "flagged_obscure", "analysis",
        ],
    },
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_difficulty_sequence(profile: str, num_groups: int) -> list[str]:
    """
    Returns a list of difficulty levels for the given profile and group count.

    For num_groups == 4, returns the base profile directly. For smaller counts,
    samples evenly across the 4-level base. For larger counts, cycles through
    _LEVEL_ORDER to fill the remaining slots.
    """
    base = _BASE_PROFILES.get(profile, _BASE_PROFILES["standard"])

    if num_groups == 4:
        return list(base)

    if num_groups < 4:
        # Evenly-spaced samples so we always cover the difficulty ramp.
        step = 4 / num_groups
        return [base[int(i * step)] for i in range(num_groups)]

    # num_groups > 4: start with the full base, then cycle _LEVEL_ORDER.
    difficulties = list(base)
    for i in range(num_groups - 4):
        difficulties.append(_LEVEL_ORDER[i % len(_LEVEL_ORDER)])
    return sorted(difficulties, key=lambda d: _LEVEL_ORDER.index(d))


def _call_with_tool(
    client: anthropic.Anthropic,
    tracker: _TokenTracker,
    prompt: str,
    tool: dict,
    temperature: float,
    step_name: str,
) -> Optional[dict]:
    """
    Calls Claude with a forced tool_use and records token usage.

    Retries up to 3 times with exponential backoff on APIError.
    Returns the tool input dict, or None if all attempts fail.
    """
    last_error: Exception | None = None

    for attempt in range(3):
        if attempt > 0:
            wait = 2 ** (attempt - 1)  # 1s, then 2s
            logger.warning("%s: retry attempt %d/3 in %ds", step_name, attempt + 1, wait)
            time.sleep(wait)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=temperature,
                tools=[tool],
                # Forcing a specific tool name prevents plain-text fallback,
                # guaranteeing a parseable structured response.
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": prompt}],
            )
            tracker.record(response)

            tool_block = next(
                (b for b in response.content if b.type == "tool_use"),
                None,
            )
            if tool_block is None:
                raise RuntimeError(
                    f"No tool_use block in response despite forced tool_choice: {response.content}"
                )

            return tool_block.input

        except anthropic.APIError as exc:
            last_error = exc
            logger.error("%s: API error on attempt %d/3: %s", step_name, attempt + 1, exc)

    logger.error("%s: all 3 attempts failed. Last error: %s", step_name, last_error)
    return None


def _step1_diversity_seed(
    client: anthropic.Anthropic,
    tracker: _TokenTracker,
    theme_hint: Optional[str],
) -> Optional[dict]:
    """
    Step 1 — Diversity Seed (temp=1.0).

    Generates 4 seed words from different domains and a creative 2-3 sentence
    story that naturally incorporates them. The story's domain juxtaposition
    acts as thematic context for Step 2, steering category brainstorming away
    from repetitive themes across pipeline runs.

    Returns: {"seed_words": [...], "story": "..."} or None on failure.
    """
    logger.info("Step 1 — Diversity Seed: generating seed words and story")

    theme_clause = (
        f" The puzzle has a theme hint of '{theme_hint}' — seed words may loosely "
        f"relate to it, but must still span different domains."
        if theme_hint
        else " There is no theme constraint — choose seeds from wildly different domains."
    )

    prompt = (
        "You are seeding the creative process for a NYT Connections puzzle.\n\n"
        "Choose 4 seed words, each from a DIFFERENT domain (e.g. cooking, sport, "
        "technology, history, nature, fashion, music, film, science, geography). "
        "The domains should be as varied as possible to ensure the final puzzle "
        "doesn't cluster around a single theme.\n\n"
        f"{theme_clause}\n\n"
        "Then write a brief, creative 2-3 sentence story that naturally incorporates "
        "all 4 seed words. The story's domain juxtaposition will guide category "
        "brainstorming in the next step — make it imaginative and specific.\n\n"
        "Call the submit_seed tool now."
    )

    result = _call_with_tool(
        client, tracker, prompt, _SEED_TOOL, temperature=1.0, step_name="Step 1"
    )
    if result is None:
        return None

    logger.info(
        "Step 1 complete — seeds: %s",
        ", ".join(result.get("seed_words", [])),
    )
    logger.debug("Step 1 story: %s", result.get("story", ""))
    return result


def _step2_category_brainstorm(
    client: anthropic.Anthropic,
    tracker: _TokenTracker,
    seed_story: str,
    seed_words: list[str],
    difficulty_profile: str,
    num_groups: int,
    theme_hint: Optional[str],
) -> Optional[tuple[list[dict], list[dict]]]:
    """
    Step 2 — Category Brainstorm (temp=0.9).

    Generates 6-8 candidate category themes given the seed story and difficulty
    profile, then selects the best num_groups. Validates the selection in Python
    to guarantee at least 2 different category_types are represented.

    Returns: (all_candidates, selected_categories) or None on failure.
    """
    logger.info(
        "Step 2 — Category Brainstorm: targeting %d groups (profile=%s)",
        num_groups, difficulty_profile,
    )

    difficulty_sequence = _get_difficulty_sequence(difficulty_profile, num_groups)
    difficulties_str = " → ".join(difficulty_sequence)
    category_types_str = ", ".join(CATEGORY_TYPES)

    theme_clause = (
        f"\nTHEME HINT: '{theme_hint}' — weave this into at most half the categories."
        if theme_hint
        else ""
    )

    prompt = (
        "You are designing a NYT Connections puzzle. A creative story was written to "
        "spark varied ideas:\n\n"
        f'SEED STORY: "{seed_story}"\n'
        f"SEED WORDS: {', '.join(seed_words)}\n"
        f"{theme_clause}\n\n"
        f"DIFFICULTY PROFILE: {difficulty_profile.upper()}\n"
        f"TARGET DIFFICULTY SEQUENCE: {difficulties_str} (easiest → hardest)\n"
        f"GROUPS TO SELECT: {num_groups}\n\n"
        "Generate 6-8 candidate category themes. For each candidate specify:\n"
        "  - A specific, evocative category_name (not generic like 'Animals' or 'Colors')\n"
        f"  - A category_type from: {category_types_str}\n"
        "  - A difficulty level: yellow (easy), green (moderate), blue (hard), purple (hardest)\n"
        "  - A red_herring_potential note: why this category could be confused with others\n\n"
        f"Then select the best {num_groups} categories by index, ensuring:\n"
        "  1. At least 2 DIFFERENT category_types are represented\n"
        "  2. Difficulty levels approximately match the target sequence\n"
        "  3. Maximum cross-group misdirection potential between the selected categories\n"
        "  4. No two fill_in_the_blank categories share the same connector/blank word\n\n"
        "HARD RULES — violating any of these disqualifies a candidate:\n"
        "  - SEED WORDS ARE INSPIRATION ONLY. Do NOT build a category whose primary subject\n"
        "    IS a seed word. If TRUMPET is a seed, 'brass instruments' is banned. If BISHOP\n"
        "    is a seed, 'chess pieces' and 'religious leaders' are banned. Use the seed story's\n"
        "    MOOD and JUXTAPOSITION, not its nouns, as creative fuel.\n"
        "  - AVOID these overused Connections themes: days of week, seasons, months, primary\n"
        "    colors, planets, card suits, Monopoly board properties, chess pieces, playing card\n"
        "    ranks, dice or board game taxonomies, types of fruit, US states, '___ PARTY'\n"
        "    fill-in-the-blank. These are the first things anyone thinks of and make for\n"
        "    boring, predictable puzzles.\n\n"
        "Call the submit_categories tool now."
    )

    result = _call_with_tool(
        client, tracker, prompt, _BRAINSTORM_TOOL, temperature=0.9, step_name="Step 2"
    )
    if result is None:
        return None

    candidates = result.get("candidates", [])
    selected_indices = result.get("selected_indices", [])

    # Clamp indices to valid range.
    valid_indices = [i for i in selected_indices if 0 <= i < len(candidates)]
    if len(valid_indices) < num_groups:
        logger.warning(
            "Step 2: only %d valid indices (need %d); padding with first available",
            len(valid_indices), num_groups,
        )
        # Fill from the front of candidates, skipping already-selected indices.
        used = set(valid_indices)
        for i in range(len(candidates)):
            if len(valid_indices) >= num_groups:
                break
            if i not in used:
                valid_indices.append(i)
                used.add(i)

    selected = [candidates[i] for i in valid_indices[:num_groups]]

    # Enforce: at least 2 different category_types.
    unique_types = {c["category_type"] for c in selected}
    if len(unique_types) < 2:
        existing_type = next(iter(unique_types))
        logger.warning(
            "Step 2: selection contains only one category_type (%s); swapping last entry",
            existing_type,
        )
        # Replace the last selected with the first non-selected candidate that differs.
        selected_set = set(valid_indices[:num_groups])
        for i, candidate in enumerate(candidates):
            if i not in selected_set and candidate["category_type"] != existing_type:
                selected[-1] = candidate
                logger.info(
                    "Step 2: swapped last selection for '%s' (%s)",
                    candidate["category_name"], candidate["category_type"],
                )
                break

    # Enforce: no two selected categories share the same difficulty level.
    # Duplicate difficulty tiers (e.g. two purples) cause sort_order and
    # difficulty_rank to be non-deterministic and mislead solvers about the ramp.
    seen_difficulties: dict[str, int] = {}
    for sel_idx, candidate in enumerate(selected):
        diff = candidate["difficulty"]
        if diff in seen_difficulties:
            logger.warning(
                "Step 2: duplicate difficulty '%s' in selection (indices %d and %d) — "
                "swapping later duplicate for a different-difficulty candidate",
                diff, seen_difficulties[diff], sel_idx,
            )
            selected_set = {valid_indices[i] for i in range(len(selected))}
            used_difficulties = {c["difficulty"] for c in selected}
            for i, candidate_sub in enumerate(candidates):
                if i not in selected_set and candidate_sub["difficulty"] not in used_difficulties:
                    selected[sel_idx] = candidate_sub
                    logger.info(
                        "Step 2: replaced duplicate '%s' difficulty with '%s' (%s)",
                        diff, candidate_sub["category_name"], candidate_sub["difficulty"],
                    )
                    break
        else:
            seen_difficulties[diff] = sel_idx

    # Enforce: no two fill_in_the_blank categories with the same connector word.
    # Structural twins ("Preceded by STREET" + "Preceded by CORNER") confuse players
    # about the puzzle's logic and produce trivially-guessable groups once one is found.
    # Heuristic: extract long words (≥4 chars) from each fill_in_the_blank name and
    # flag any word that appears in 2+ category names as a likely shared connector.
    _STOP_WORDS = {"WORDS", "THAT", "EACH", "WITH", "BEFORE", "AFTER", "BLANK",
                   "FILL", "TYPE", "TYPES", "THINGS", "PRECEDED", "FOLLOWED",
                   "CONTAINS", "COMPOUND", "PHRASES", "PHRASE"}

    fitb_selected = [
        (i, c) for i, c in enumerate(selected)
        if c["category_type"] == "fill_in_the_blank"
    ]
    if len(fitb_selected) >= 2:
        # Collect meaningful words from each fill_in_the_blank category name.
        connector_words: dict[str, list[int]] = {}  # word → indices of categories using it
        for sel_idx, candidate in fitb_selected:
            tokens = {
                w.upper() for w in candidate["category_name"].split()
                if len(w.strip("_'\",.")) >= 4
                and w.strip("_'\",.").upper() not in _STOP_WORDS
            }
            for token in tokens:
                connector_words.setdefault(token, []).append(sel_idx)

        shared = {w: idxs for w, idxs in connector_words.items() if len(idxs) >= 2}
        if shared:
            logger.warning(
                "Step 2: fill_in_the_blank categories share connector word(s) %s — swapping last duplicate",
                list(shared.keys()),
            )
            # Find the last selected fill_in_the_blank and replace it with a
            # non-fill_in_the_blank candidate (or a fill_in_the_blank with no overlap).
            last_fitb_idx = fitb_selected[-1][0]
            selected_names = {valid_indices[i] for i in range(len(selected))}
            for i, candidate in enumerate(candidates):
                if i in selected_names:
                    continue
                if candidate["category_type"] != "fill_in_the_blank":
                    selected[last_fitb_idx] = candidate
                    logger.info(
                        "Step 2: replaced duplicate fill_in_the_blank with '%s' (%s)",
                        candidate["category_name"], candidate["category_type"],
                    )
                    break

    logger.info(
        "Step 2 complete — selected: %s",
        [c["category_name"] for c in selected],
    )
    return candidates, selected


def _step3_build_groups(
    tracker: _TokenTracker,
    selected_categories: list[dict],
    words_per_group: int,
) -> Optional[list[dict]]:
    """
    Step 3 — Iterative Group Building.

    Calls generate_single_group() once per selected category, passing all
    previously built groups as context so Claude can plan red herrings across
    the full set. Deduplicates words across groups by substituting from
    candidate_words when the primary selection contains a collision.

    Returns: list of assembled group dicts, or None if any group fails.
    """
    logger.info(
        "Step 3 — Iterative Group Building: %d groups × %d words/group",
        len(selected_categories), words_per_group,
    )

    groups: list[dict] = []
    all_used_words: set[str] = set()

    for i, category in enumerate(selected_categories):
        logger.info(
            "Step 3 [%d/%d]: generating '%s' (%s, %s)",
            i + 1, len(selected_categories),
            category["category_name"],
            category["category_type"],
            category["difficulty"],
        )

        # Retry loop for semantic failures (empty candidate lists, all-duplicate
        # returns). This is separate from generate_single_group()'s own retry
        # which handles API errors — here we retry when the API call succeeds but
        # the model returned too few usable words (e.g. a tightly constrained
        # wordplay category where it couldn't verify enough candidates).
        _MAX_GROUP_ATTEMPTS = 3
        final_words: list[str] = []
        raw_group: dict = {}

        for attempt in range(_MAX_GROUP_ATTEMPTS):
            if attempt > 0:
                logger.warning(
                    "Step 3 [%d/%d]: retrying group generation (attempt %d/%d) — "
                    "previous attempt yielded %d/%d usable words",
                    i + 1, len(selected_categories),
                    attempt + 1, _MAX_GROUP_ATTEMPTS,
                    len(final_words), words_per_group,
                )

            try:
                raw_group = generate_single_group(
                    category_type=category["category_type"],
                    existing_groups=groups,
                    words_per_group=words_per_group,
                    difficulty=category["difficulty"],
                    # Pass the brainstorm's proposed concept so Claude generates words
                    # for THIS specific idea rather than any concept of that type.
                    category_hint=category.get("category_name"),
                )
            except (ValueError, RuntimeError) as exc:
                logger.error(
                    "Step 3 [%d/%d]: generate_single_group raised on attempt %d: %s",
                    i + 1, len(selected_categories), attempt + 1, exc,
                )
                if attempt == _MAX_GROUP_ATTEMPTS - 1:
                    return None
                continue

            tracker.add_calls(1)

            # Deduplicate: use the pre-selected `words` first, then backfill from
            # `candidate_words` for any collision with an earlier group.
            final_words = []
            candidates_pool = [
                w.upper() for w in (raw_group.get("candidate_words") or [])
                if w.upper() not in all_used_words
            ]

            for word in (raw_group.get("words") or []):
                upper = word.upper()
                if upper not in all_used_words:
                    final_words.append(upper)
                    all_used_words.add(upper)
                else:
                    logger.warning(
                        "Step 3: duplicate word '%s' found — replacing from candidate pool", upper
                    )

            # Backfill gaps from the remaining candidate pool.
            for candidate in candidates_pool:
                if len(final_words) >= words_per_group:
                    break
                if candidate not in all_used_words:
                    final_words.append(candidate)
                    all_used_words.add(candidate)

            if len(final_words) >= words_per_group:
                break  # Success — move on to assembling this group.

            # Log the raw response so failures are diagnosable.
            logger.error(
                "Step 3 [%d/%d] attempt %d: only %d/%d usable words. "
                "raw words=%s, raw candidates=%s",
                i + 1, len(selected_categories), attempt + 1,
                len(final_words), words_per_group,
                raw_group.get("words"),
                raw_group.get("candidate_words"),
            )
            # Un-add any partial words so the next attempt starts clean.
            for w in final_words:
                all_used_words.discard(w)
            final_words = []

        if len(final_words) < words_per_group:
            logger.error(
                "Step 3 [%d/%d]: failed to get %d usable words after %d attempts — aborting pipeline",
                i + 1, len(selected_categories), words_per_group, _MAX_GROUP_ATTEMPTS,
            )
            return None

        assembled = {
            "category_name": raw_group["category_name"],
            "words": final_words[:words_per_group],
            # Preserve the full candidate pool for Step 4 swap validation.
            "candidate_words": [w.upper() for w in raw_group.get("candidate_words", [])],
            "design_notes": raw_group.get("design_notes", ""),
            "difficulty": category["difficulty"],
            "difficulty_rank": _DIFFICULTY_TO_RANK[category["difficulty"]],
        }
        groups.append(assembled)

        logger.info(
            "Step 3 [%d/%d] complete — '%s': %s",
            i + 1, len(selected_categories),
            assembled["category_name"],
            ", ".join(assembled["words"]),
        )

    return groups


def _step4_red_herring_refinement(
    client: anthropic.Anthropic,
    tracker: _TokenTracker,
    groups: list[dict],
) -> tuple[list[dict], str]:
    """
    Step 4 — Red Herring Refinement (temp=0.7).

    Presents the complete puzzle to Claude and asks it to:
      1. Identify existing cross-group red herrings and rate their strength.
      2. Suggest up to 3 word swaps (new_word must come from candidate_words).
      3. Flag any words that feel too obscure or ambiguous.

    Applies only valid swaps — new_word must appear in the group's candidate_words
    and must not already be used in another group. On API failure, returns the
    original groups unchanged with a note in the analysis string.

    Returns: (refined_groups, analysis_text)
    """
    logger.info("Step 4 — Red Herring Refinement: analysing cross-group misdirection")

    groups_description = "\n".join(
        f"  Group {i} [{g['difficulty'].upper()}] — {g['category_name']}\n"
        f"    Words:      {', '.join(g['words'])}\n"
        f"    Candidates: {', '.join(g.get('candidate_words', []))}"
        for i, g in enumerate(groups)
    )

    prompt = (
        "You are reviewing a NYT Connections puzzle for cross-group misdirection quality.\n\n"
        "CURRENT PUZZLE:\n"
        f"{groups_description}\n\n"
        "Your three tasks:\n\n"
        "1. IDENTIFY existing red herrings — words in one group that a player might "
        "plausibly assign to a different group. Rate each as weak/moderate/strong.\n\n"
        "2. SUGGEST up to 3 word swaps that would increase misdirection. "
        "IMPORTANT: new_word MUST appear in that group's 'Candidates' list above. "
        "Do not invent words that aren't in the candidates — the swap will be rejected.\n\n"
        "3. FLAG words that feel too obscure or ambiguous for the intended difficulty tier.\n\n"
        "Call the submit_refinement tool now."
    )

    result = _call_with_tool(
        client, tracker, prompt, _REFINEMENT_TOOL, temperature=0.7, step_name="Step 4"
    )

    if result is None:
        logger.warning("Step 4: refinement failed — keeping original groups unchanged")
        return groups, "Refinement step skipped due to API failure."

    # Track which words are in use across all groups for duplicate checking.
    all_used_words: set[str] = {w for g in groups for w in g["words"]}
    swaps_applied = 0

    for swap in result.get("suggested_swaps", [])[:3]:
        group_idx: Optional[int] = swap.get("group_index")
        old_word: str = swap.get("old_word", "").upper()
        new_word: str = swap.get("new_word", "").upper()

        if group_idx is None or group_idx >= len(groups):
            logger.warning("Step 4: invalid group_index %s in swap — skipping", group_idx)
            continue

        group = groups[group_idx]
        candidates_upper = [w.upper() for w in group.get("candidate_words", [])]

        if new_word not in candidates_upper:
            logger.info(
                "Step 4: rejected swap — '%s' not in candidates for group %d (%s)",
                new_word, group_idx, group["category_name"],
            )
            continue

        # Allow swapping a word with itself (no-op) but block cross-group collisions.
        if new_word in all_used_words and new_word != old_word:
            logger.info(
                "Step 4: rejected swap — '%s' already used in another group", new_word
            )
            continue

        if old_word not in group["words"]:
            logger.info(
                "Step 4: rejected swap — '%s' not in current words for group %d", old_word, group_idx
            )
            continue

        word_idx = group["words"].index(old_word)
        group["words"][word_idx] = new_word
        all_used_words.discard(old_word)
        all_used_words.add(new_word)
        swaps_applied += 1

        logger.info(
            "Step 4: applied swap '%s' → '%s' in group %d (%s)",
            old_word, new_word, group_idx, group["category_name"],
        )

    logger.info("Step 4 complete — %d swap(s) applied", swaps_applied)
    return groups, result.get("analysis", "")


def _step5_assemble(
    groups: list[dict],
    seed_story: str,
    seed_words: list[str],
    all_candidates: list[dict],
    red_herring_analysis: str,
    tracker: _TokenTracker,
    config: dict,
) -> dict:
    """
    Step 5 — Final Assembly.

    Sorts groups by difficulty_rank (yellow → purple), assigns 0-indexed
    sort_order values to match the NYT difficulty ramp, then packages
    everything into the puzzle dict expected by the caller.
    """
    logger.info("Step 5 — Final Assembly: packaging puzzle dict")

    sorted_groups = sorted(groups, key=lambda g: g["difficulty_rank"])

    final_groups = [
        {
            "category_name": g["category_name"],
            "words": g["words"],
            "difficulty_rank": g["difficulty_rank"],
            "sort_order": i,
        }
        for i, g in enumerate(sorted_groups)
    ]

    return {
        "groups": final_groups,
        "generation_metadata": {
            "model": MODEL,
            "seed_words": seed_words,
            "seed_story": seed_story,
            "category_candidates": all_candidates,
            "red_herring_analysis": red_herring_analysis,
            "difficulty_profile": config.get("difficulty_profile", "standard"),
            "theme_hint": config.get("theme_hint"),
            # total_input_tokens and total_output_tokens cover steps 1, 2, 4 only.
            # Step 3 token counts are internal to generate_single_group().
            "total_api_calls": tracker.api_calls,
            "total_input_tokens": tracker.total_input_tokens,
            "total_output_tokens": tracker.total_output_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_puzzle(config: Optional[dict] = None) -> Optional[dict]:
    """
    Generates a complete Connections puzzle through the 5-step pipeline.

    Args:
        config: Optional configuration dict:
            {
                "num_groups":         int  (default 4),
                "words_per_group":    int  (default 4),
                "difficulty_profile": str  ("easy"|"standard"|"hard", default "standard"),
                "theme_hint":         str  (optional, e.g. "food" or "90s pop culture"),
            }

    Returns:
        {
            "groups": [
                {
                    "category_name": str,
                    "words":         list[str],
                    "difficulty_rank": int,   # 1=yellow … 4=purple
                    "sort_order":    int,     # 0-indexed, sorted easiest first
                }
            ],
            "generation_metadata": {
                "model":               str,
                "seed_words":          list[str],
                "seed_story":          str,
                "category_candidates": list[dict],
                "red_herring_analysis": str,
                "difficulty_profile":  str,
                "theme_hint":          str | None,
                "total_api_calls":     int,
                "total_input_tokens":  int,   # steps 1, 2, 4 only
                "total_output_tokens": int,   # steps 1, 2, 4 only
            },
        }

        Returns None on unrecoverable failure — details logged at ERROR level.
        Callers should check for None before attempting to use the result.

    To seed the result into the puzzle pool:
        from backend.src.services.puzzle_pool_service import seed_puzzle_to_pool
        puzzle = generate_puzzle(config)
        if puzzle:
            seed_data = {
                "connections": [
                    {"relationship": g["category_name"], "words": g["words"]}
                    for g in puzzle["groups"]
                ],
            }
            puzzle_id = seed_puzzle_to_pool(
                seed_data,
                generation_model=puzzle["generation_metadata"]["model"],
                generation_metadata=puzzle["generation_metadata"],
            )
    """
    if config is None:
        config = {}

    num_groups: int = config.get("num_groups", 4)
    words_per_group: int = config.get("words_per_group", 4)
    difficulty_profile: str = config.get("difficulty_profile", "standard")
    theme_hint: Optional[str] = config.get("theme_hint")

    if difficulty_profile not in _BASE_PROFILES:
        logger.error(
            "Invalid difficulty_profile '%s'. Must be one of %s.",
            difficulty_profile, list(_BASE_PROFILES),
        )
        return None

    logger.info(
        "generate_puzzle: starting pipeline "
        "(groups=%d, words_per_group=%d, profile=%s, theme=%s)",
        num_groups, words_per_group, difficulty_profile, theme_hint or "none",
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tracker = _TokenTracker()

    # --- Step 1: Diversity Seed ---
    seed_result = _step1_diversity_seed(client, tracker, theme_hint)
    if seed_result is None:
        logger.error("generate_puzzle: Step 1 failed — aborting")
        return None
    seed_words = seed_result["seed_words"]
    seed_story = seed_result["story"]

    # --- Step 2: Category Brainstorm ---
    brainstorm_result = _step2_category_brainstorm(
        client, tracker, seed_story, seed_words,
        difficulty_profile, num_groups, theme_hint,
    )
    if brainstorm_result is None:
        logger.error("generate_puzzle: Step 2 failed — aborting")
        return None
    all_candidates, selected_categories = brainstorm_result

    # --- Step 3: Iterative Group Building ---
    groups = _step3_build_groups(tracker, selected_categories, words_per_group)
    if groups is None:
        logger.error("generate_puzzle: Step 3 failed — aborting")
        return None

    # --- Step 4: Red Herring Refinement ---
    refined_groups, red_herring_analysis = _step4_red_herring_refinement(
        client, tracker, groups
    )

    # --- Step 5: Final Assembly ---
    puzzle = _step5_assemble(
        refined_groups, seed_story, seed_words,
        all_candidates, red_herring_analysis,
        tracker, config,
    )

    logger.info(
        "generate_puzzle: complete — %d groups, %d API calls, "
        "%d input tokens, %d output tokens (steps 1,2,4)",
        len(puzzle["groups"]),
        tracker.api_calls,
        tracker.total_input_tokens,
        tracker.total_output_tokens,
    )

    return puzzle


# ---------------------------------------------------------------------------
# Manual end-to-end test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys
    from datetime import datetime
    from pathlib import Path

    from dotenv import load_dotenv

    # Load backend/.env so ANTHROPIC_API_KEY is available when running directly.
    # Run from project root: python -m backend.src.generation.puzzle_generator
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 70)
    print("Connections Puzzle Generator — Full Pipeline Test")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    puzzle = generate_puzzle({
        "num_groups": 4,
        "words_per_group": 4,
        "difficulty_profile": "standard",
        # "theme_hint": "food",  # uncomment to test themed generation
    })

    if puzzle is None:
        print("\n[FAILED] Pipeline returned None — check logs above for details.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("GENERATED PUZZLE")
    print("=" * 70)

    rank_labels = {1: "YELLOW", 2: "GREEN", 3: "BLUE", 4: "PURPLE"}
    for group in puzzle["groups"]:
        label = rank_labels.get(group["difficulty_rank"], "UNKNOWN")
        print(f"\n  [{label}] {group['category_name']}")
        print(f"  Words: {', '.join(group['words'])}")

    meta = puzzle["generation_metadata"]
    print("\n" + "-" * 70)
    print("GENERATION METADATA")
    print(f"  Model:          {meta['model']}")
    print(f"  Seed words:     {', '.join(meta['seed_words'])}")
    print(f"  Difficulty:     {meta['difficulty_profile']}")
    print(f"  Theme hint:     {meta['theme_hint'] or 'none'}")
    print(f"  API calls:      {meta['total_api_calls']} total")
    print(f"  Input tokens:   {meta['total_input_tokens']} (steps 1,2,4 only)")
    print(f"  Output tokens:  {meta['total_output_tokens']} (steps 1,2,4 only)")
    print(f"\n  Seed story:\n  {meta['seed_story']}")
    print(f"\n  Red herring analysis:\n  {meta['red_herring_analysis']}")

    # Attempt to seed the puzzle into the Supabase pool.
    try:
        from backend.src.services.puzzle_pool_service import seed_puzzle_to_pool

        seed_data = {
            "connections": [
                {"relationship": g["category_name"], "words": g["words"]}
                for g in puzzle["groups"]
            ],
        }
        puzzle_id = seed_puzzle_to_pool(
            seed_data,
            generation_model=meta["model"],
            generation_metadata={k: v for k, v in meta.items() if k != "model"},
        )
        print(f"\n  Seeded to pool as: {puzzle_id}")
    except Exception as exc:
        print(f"\n  (Pool seeding skipped: {exc})")

    # Write full structured output to a JSON file for offline inspection.
    output_dir = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"puzzle_gen_{timestamp}.json"
    output_path.write_text(json.dumps(puzzle, indent=2), encoding="utf-8")
    print(f"\nFull output saved to: {output_path}")
