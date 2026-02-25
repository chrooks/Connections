"""
Group Generator — Phase 3 of the Connections puzzle generation pipeline.

Generates a single, high-quality word group for a Connections puzzle using
the Anthropic API with structured output (tool_use).

This is the atomic unit of the pipeline: given a category type, a list of
already-generated groups, and a target difficulty, it asks Claude to produce
8 candidate words and return them in a guaranteed-valid JSON structure.

Usage:
    from backend.src.generation.group_generator import generate_single_group, CATEGORY_TYPES

    group = generate_single_group(
        category_type="fill_in_the_blank",
        existing_groups=[],
        words_per_group=4,
        difficulty="yellow",
    )
    # Returns: {"category_name": str, "words": [...], "candidate_words": [...], "design_notes": str}
"""

import logging
import os
import time

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------

# Sonnet balances creativity (needed at high temperature) with reliable
# tool_use compliance — important for guaranteed structured output.
MODEL = "claude-sonnet-4-5-20250929"

# 0.9 drives word variety and avoids repetitive themes across runs while
# staying coherent enough to follow the tool schema constraints.
TEMPERATURE = 0.9

# design_notes now contains the full rule statement + per-word verification log
# before any word lists are committed. 2048 gives room for 8+ words with proofs.
MAX_TOKENS = 2048

# Category styles the pipeline rotates through to keep puzzle variety high.
# Each style targets a different cognitive skill in the player.
CATEGORY_TYPES = [
    "synonyms",           # words that share a meaning
    "members_of_set",     # items belonging to a specific named category
    "fill_in_the_blank",  # words completing a common phrase with a shared word
    "wordplay",           # anagrams, homophones, hidden words, letter patterns
    "compound_words",     # words that pair with a shared word to form a compound
    "cultural_knowledge", # requires pop culture, history, or domain expertise
]

# ---------------------------------------------------------------------------
# Difficulty definitions — passed verbatim into the prompt so Claude
# understands the exact calibration target for each colour tier.
# ---------------------------------------------------------------------------
_DIFFICULTY_DESCRIPTIONS = {
    "yellow": (
        "YELLOW (easiest) — the connection is obvious and relies only on common everyday "
        "knowledge. Most players should recognise this group immediately."
    ),
    "green": (
        "GREEN (moderate) — the connection requires a moment of thought or slightly "
        "less-common knowledge. Players may need to rule out other options first."
    ),
    "blue": (
        "BLUE (hard) — the connection is non-obvious and may rely on specialised, "
        "cultural, or domain-specific knowledge. Expect many players to struggle here."
    ),
    "purple": (
        "PURPLE (hardest) — the connection depends on wordplay, lateral thinking, hidden "
        "patterns, or a trick that makes players say 'aha!' only after the reveal."
    ),
}

# ---------------------------------------------------------------------------
# Category type descriptions with examples — grounding Claude in what each
# style looks like helps it produce on-theme, well-calibrated groups.
# ---------------------------------------------------------------------------
_CATEGORY_TYPE_DESCRIPTIONS = {
    "synonyms": (
        "SYNONYMS — words that share a single meaning or can replace each other in a sentence. "
        "Example category: 'Words meaning EXHAUSTED' → SPENT, DRAINED, BEAT, WASHED OUT."
    ),
    "members_of_set": (
        "MEMBERS OF A SET — items that all belong to a specific, named real-world category. "
        "Example: 'Types of PASTA' → RIGATONI, FARFALLE, ORZO, BUCATINI."
    ),
    "fill_in_the_blank": (
        "FILL IN THE BLANK — each word completes the same common phrase when combined with a "
        "shared hidden word. Example: '___ CARD' → CREDIT, WILD, PLAYING, BUSINESS."
    ),
    "wordplay": (
        "WORDPLAY — the connection is a structural or phonetic trick. You MUST choose a single, "
        "precise, verifiable rule and confirm every word satisfies it before including it. "
        "Good rule types (pick ONE):\n"
        "  • Hidden word: each word contains a smaller word inside it — e.g. 'Each hides a METAL': "
        "gOLDen, coPPEr, fEARth... verify by finding the metal in each word letter-by-letter.\n"
        "  • Anagrams of each other: every word uses the exact same letters — e.g. LISTEN, SILENT, "
        "ENLIST, TINSEL. Verify by sorting letters: L-E-I-N-S-T for all four.\n"
        "  • Homophones of a category: each word sounds like a member of a set — e.g. 'Sounds like "
        "a number': ATE (eight), TOO (two), FOR (four), WON (one). Verify the sound match explicitly.\n"
        "Do NOT include a word unless you can prove the rule applies to it. SPRING is not a "
        "homophone of a letter. EARTH is only an anagram of HEART if the category is 'anagrams of HEART'."
    ),
    "compound_words": (
        "COMPOUND WORDS — each word pairs with the same hidden word to form a valid compound. "
        "Example: 'FIRE ___' → TRUCK, WORKS, FLY, PLACE."
    ),
    "cultural_knowledge": (
        "CULTURAL KNOWLEDGE — the connection requires knowing pop culture, history, sport, "
        "literature, or another domain. Example: 'Bowie alter egos' → ZIGGY, ALADDIN, JARETH, MAJOR TOM."
    ),
}

# ---------------------------------------------------------------------------
# Structured output schema (tool_use)
#
# Defining the expected shape as a tool and forcing the model to call it
# (tool_choice={"type": "tool", "name": "submit_word_group"}) guarantees a
# valid dict response — no JSON parsing, no format guessing.
# ---------------------------------------------------------------------------
_GROUP_SCHEMA_TOOL = {
    "name": "submit_word_group",
    "description": (
        "Submit the completed word group for this Connections puzzle category. "
        "Call this tool ONCE with all four fields populated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category_name": {
                "type": "string",
                "description": (
                    "A specific, evocative category label — not a generic phrase like 'Animals' "
                    "or 'Colors'. The label's own words must NOT appear in the word list. "
                    "Example of good label: 'Preceded by WILD', not just 'WILD ___'."
                ),
            },
            # design_notes is intentionally placed BEFORE words and candidate_words.
            # Claude fills tool parameters roughly in schema property order, so putting
            # verification here forces the model to commit its reasoning (rule statement +
            # letter-by-letter proof) BEFORE it writes the word lists. This prevents the
            # common failure mode where wrong words are committed before verification runs.
            "design_notes": {
                "type": "string",
                "description": (
                    "Fill this field FIRST, before words or candidate_words. "
                    "Structure it in three parts:\n"
                    "1. RULE: State the exact rule precisely (e.g. 'Each word contains the "
                    "letters E-A-R consecutively').\n"
                    "2. VERIFICATION: For every word you plan to include, write "
                    "'[WORD]: [proof it satisfies the rule]'. Discard any word that fails.\n"
                    "3. RED HERRING: Name the red herring candidate, prove it passes the rule, "
                    "and explain which existing group it could be confused with."
                ),
            },
            "words": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Fill this AFTER design_notes. The final words_per_group words — only "
                    "words that passed verification in design_notes. All uppercase."
                ),
            },
            "candidate_words": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Fill this AFTER design_notes. Exactly 8 uppercase words, all of which "
                    "passed verification in design_notes. Must include all words in 'words'."
                ),
            },
        },
        "required": ["category_name", "words", "candidate_words", "design_notes"],
    },
}


# ---------------------------------------------------------------------------
# Core public function
# ---------------------------------------------------------------------------

def generate_single_group(
    category_type: str,
    existing_groups: list[dict],
    words_per_group: int = 4,
    difficulty: str = "green",
    category_hint: "str | None" = None,
) -> dict:
    """
    Generates one high-quality word group for a Connections puzzle.

    Calls the Anthropic API with tool_use to guarantee a structured response.
    Retries up to 3 times with exponential backoff on API errors.

    Args:
        category_type:   One of CATEGORY_TYPES. Controls the style of connection
                         (e.g. "synonyms", "fill_in_the_blank").
        existing_groups: Already-generated groups so Claude avoids word overlap
                         and can plan cross-group red herrings. Each item should
                         have at minimum: {"category_name": str, "words": list[str]}.
                         Pass an empty list when generating the first group.
        words_per_group: How many words the final group should contain (default 4).
        difficulty:      Target difficulty tier: "yellow" | "green" | "blue" | "purple".
        category_hint:   Optional proposed category concept from the brainstorm step
                         (e.g. "Beatles songs missing 'LOVE'"). When provided, Claude
                         uses this as a starting point rather than inventing a concept
                         from scratch, keeping Step 3 aligned with Step 2's plan.

    Returns:
        {
            "category_name":   str,        # specific, evocative label
            "words":           list[str],  # the final words_per_group words
            "candidate_words": list[str],  # 8-word pool for later refinement
            "design_notes":    str,        # creative reasoning + red herring notes
        }

    Raises:
        ValueError:   If difficulty or category_type is not recognised.
        RuntimeError: If the API fails after all 3 retries, or returns no tool_use block.
    """
    # Validate arguments early so callers get a clear error before any API call.
    if difficulty not in _DIFFICULTY_DESCRIPTIONS:
        raise ValueError(
            f"difficulty must be one of {list(_DIFFICULTY_DESCRIPTIONS)}, got {difficulty!r}"
        )
    if category_type not in CATEGORY_TYPES:
        raise ValueError(
            f"category_type must be one of {CATEGORY_TYPES}, got {category_type!r}"
        )

    # Build the prompt once — it doesn't change across retries.
    prompt = _build_prompt(category_type, existing_groups, words_per_group, difficulty, category_hint)

    # Initialise the client here (not at module level) so tests can patch the
    # environment variable without side effects at import time.
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    last_error: Exception | None = None
    for attempt in range(3):
        # Exponential backoff before each retry (skipped on the first attempt).
        if attempt > 0:
            wait_seconds = 2 ** (attempt - 1)  # attempt 1 → 1s, attempt 2 → 2s
            logger.warning(
                "Retrying group generation (attempt %d/3) in %ds — prior error: %s",
                attempt + 1,
                wait_seconds,
                last_error,
            )
            time.sleep(wait_seconds)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                tools=[_GROUP_SCHEMA_TOOL],
                # Forcing a specific tool call prevents Claude from replying with
                # plain text, which would break the structured-output contract.
                tool_choice={"type": "tool", "name": "submit_word_group"},
                messages=[{"role": "user", "content": prompt}],
            )

            # With forced tool_choice there will always be exactly one tool_use
            # block, but we use next() defensively in case the SDK changes.
            tool_block = next(
                (b for b in response.content if b.type == "tool_use"),
                None,
            )
            if tool_block is None:
                # This shouldn't happen under forced tool_choice, but if it does
                # we want a loud, descriptive failure rather than a KeyError later.
                raise RuntimeError(
                    "API returned no tool_use block despite forced tool_choice. "
                    f"Full response content: {response.content}"
                )

            # tool_block.input is already a Python dict — no JSON parsing needed.
            return tool_block.input

        except anthropic.APIError as exc:
            # Catch the base class to retry on rate limits, connection errors,
            # server errors, etc. Authentication errors are subclasses too, but
            # retrying them is harmless (they'll just fail again quickly).
            last_error = exc
            logger.error("Anthropic API error on attempt %d/3: %s", attempt + 1, exc)

    raise RuntimeError(
        f"Failed to generate group after 3 attempts. Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Prompt builder (private)
# ---------------------------------------------------------------------------

def _build_prompt(
    category_type: str,
    existing_groups: list[dict],
    words_per_group: int,
    difficulty: str,
    category_hint: "str | None" = None,
) -> str:
    """
    Constructs the user message sent to Claude.

    Kept as a separate function so:
    - The retry loop stays readable.
    - Prompt wording can be iterated without touching retry logic.
    - Unit tests can call _build_prompt() directly to inspect prompt content.
    """
    lines = [
        "You are designing one group for a NYT Connections-style word puzzle.",
        "",
        # Anti-cliché instruction — prevents the model from defaulting to the
        # safest/most common categories (days, seasons, months) on every run.
        # Board games are explicitly listed because Monopoly properties and chess
        # pieces are the new go-to easy categories once classic clichés are blocked.
        "AVOID OVERUSED CONNECTIONS THEMES:",
        "  Do not use: days of the week, seasons (spring/summer/fall/winter), months of the year,",
        "  primary colors, planets, cardinal directions, card suits, or broad taxonomies like",
        "  'Types of fruit' or 'US states'. These are the first things anyone thinks of.",
        "  Also avoid: Monopoly properties, chess pieces, playing card ranks, dice games,",
        "  or any other board game taxonomy. These have become the new default clichés.",
        "  Choose something more specific, surprising, or cross-domain.",
        "",
        f"CATEGORY TYPE: {_CATEGORY_TYPE_DESCRIPTIONS[category_type]}",
        "",
        f"DIFFICULTY: {_DIFFICULTY_DESCRIPTIONS[difficulty]}",
        "",
        (
            f"GROUP SIZE: Provide exactly {words_per_group} final words in 'words', "
            f"plus 8 total candidate words in 'candidate_words' "
            f"(the 8 includes your final {words_per_group})."
        ),
        "",
        "RULES:",
        "  1. All words must be UPPERCASE.",
        (
            "  2. The category name must be specific and evocative — not generic "
            "labels like 'Animals' or 'Colors'."
        ),
        "  3. Words that appear in the category name must NOT appear in the word list.",
        "  4. No word may appear in any existing group listed below.",
    ]

    # Red herring requirement only applies after the first group exists.
    # The definition here is very explicit to prevent the model from taking the
    # shortcut of simply recycling existing-group words as "distractors."
    if existing_groups:
        lines += [
            "  5. RED HERRING — Among your 8 candidate_words, at least one must be a word that:",
            "       (a) GENUINELY satisfies THIS group's category rule — it is a valid member, AND",
            "       (b) Could plausibly be mistaken for a member of a specific existing group,",
            "           causing a player to assign it to the wrong group.",
            "     In design_notes: name the red herring word, prove it passes (a) by showing",
            "     how it fits this group's rule, then name which existing group it could be",
            "     confused with and explain the surface-level similarity.",
            "     FORBIDDEN: Do NOT put words from existing groups into candidate_words just",
            "     because they appear there. If a word doesn't pass THIS group's rule, it is not",
            "     a red herring — it's a mistake. Every candidate_word must fit this category.",
        ]
    else:
        lines.append(
            "  5. (First group — no red herring requirement. Focus on originality.)"
        )

    # List existing groups so Claude can avoid overlap and plan red herrings.
    if existing_groups:
        lines += ["", "EXISTING GROUPS (do not reuse any of these words):"]
        for i, group in enumerate(existing_groups, 1):
            words_str = ", ".join(group.get("words", []))
            name = group.get("category_name", f"Group {i}")
            lines.append(f"  {i}. {name}: {words_str}")
    else:
        lines += ["", "EXISTING GROUPS: None — this is the first group."]

    # If the pipeline brainstormed a specific concept, anchor Claude to it.
    # Without this, generate_single_group() freely invents its own concept for
    # the given category_type — leading to mismatches like "Beatles songs" ending
    # up with Santa's reindeer words because the hint was silently discarded.
    if category_hint:
        lines += [
            "",
            f"PROPOSED CONCEPT: \"{category_hint}\"",
            "  Use this as your starting point. You may refine the category_name wording,",
            "  but the core concept and theme MUST remain the same.",
        ]

    lines += [
        "",
        # Explicit ordering instruction: design_notes first (rule + per-word proof),
        # then and only then commit to the word lists. This mirrors the schema field
        # ordering, which nudges Claude to fill fields in the right sequence.
        "WHEN CALLING THE TOOL — fill the fields in this order:",
        "  1. category_name — the specific label.",
        "  2. design_notes — write your rule statement, then prove EACH word letter-by-letter.",
        "     Only move on once every planned word has passed. If a word fails, replace it.",
        "  3. words — copy only the words that passed step 2.",
        "  4. candidate_words — copy only the 8 words that passed step 2.",
        "",
        "Do not fill words or candidate_words with unverified words.",
        "Call the submit_word_group tool now.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Manual smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint
    from datetime import datetime
    from pathlib import Path

    from dotenv import load_dotenv

    # Load backend/.env so ANTHROPIC_API_KEY is available when running this
    # script directly (outside Flask, which would normally load it via app.py).
    load_dotenv()

    # Generate 3 groups iteratively, each one seeing the previous groups as
    # context. Simulates Phase 3 of the pipeline end-to-end in miniature.
    groups: list[dict] = []

    # Three representative combos that exercise red herring planting across
    # two sequential passes (groups 2, 3, and 4 each see prior context).
    test_sequence = [
        ("members_of_set", "yellow"),
        ("fill_in_the_blank", "green"),
        ("compound_words", "blue"),
        ("wordplay", "purple"),
    ]

    # Build the output string in memory so we can print AND write the same content.
    lines_out: list[str] = []

    def emit(line: str = "") -> None:
        """Print a line and buffer it for the output file."""
        print(line)
        lines_out.append(line)

    emit("=" * 60)
    emit("Connections Group Generator — Smoke Test")
    emit(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("=" * 60)

    for i, (cat_type, diff) in enumerate(test_sequence, 1):
        emit(f"\nGenerating group {i}/{len(test_sequence)}  [{cat_type}  |  {diff}] ...")

        group = generate_single_group(
            category_type=cat_type,
            existing_groups=groups,
            words_per_group=4,
            difficulty=diff,
        )

        # Accumulate so the next iteration receives prior groups as context.
        groups.append(group)

        emit(f"\n--- Group {i} ---")
        emit(f"  Category   : {group['category_name']}")
        emit(f"  Words      : {', '.join(group['words'])}")
        emit(f"  Candidates : {', '.join(group['candidate_words'])}")
        emit(f"  Notes      : {group['design_notes']}")

    emit("\n" + "=" * 60)
    emit("Full structured output:")
    structured = pprint.pformat(groups, width=80)
    emit(structured)

    # Write a timestamped file next to this script so results are easy to find
    # and share without hunting through terminal scroll-back.
    output_dir = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"smoke_test_{timestamp}.txt"
    output_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")

    print(f"\nResults saved to: {output_path}")
