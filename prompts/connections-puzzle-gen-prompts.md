# Connections Puzzle Generator — Claude Code Prompts

Each phase below is a self-contained prompt you can paste into Claude Code. Work through them in order — each builds on the previous. Before each prompt, make sure Claude Code has your project open so it can see your existing codebase.

---

## Phase 1: Database Schema & Puzzle Pool Tables

### What this produces
New Supabase tables for storing generated puzzles separately from active games. This decouples puzzle *creation* from puzzle *serving*.

### Prompt

```
I'm building an AI-powered puzzle generation pipeline for my Connections word game. My existing stack is Python + Flask + Supabase.

Currently, my game works by reading puzzle data from a connections schema and serving it through a Flask API. I need to add a puzzle pool system — a set of pre-generated, validated puzzles that my existing `generate-grid` endpoint can pull from instead of using hardcoded data.

Create Supabase migration SQL for these tables:

1. `puzzle_configs` — defines puzzle shape parameters:
   - `id` (uuid, PK, default gen_random_uuid())
   - `num_groups` (integer, default 4)
   - `words_per_group` (integer, default 4)
   - `name` (text, e.g., "classic", "mini", "extended")
   - `created_at` (timestamptz)
   - Insert a default "classic" config (4 groups, 4 words)

2. `puzzles` — the puzzle pool:
   - `id` (uuid, PK)
   - `config_id` (uuid, FK → puzzle_configs)
   - `status` (text: 'draft', 'validating', 'approved', 'rejected', 'served')
   - `difficulty_score` (float, nullable) — overall difficulty 0-1
   - `validation_score` (float, nullable) — quality score from validation pipeline
   - `validation_report` (jsonb, nullable) — full validation details
   - `generation_model` (text) — which Claude model generated it
   - `generation_metadata` (jsonb, nullable) — prompt versions, temperatures, etc.
   - `times_served` (integer, default 0)
   - `created_at` (timestamptz)
   - `approved_at` (timestamptz, nullable)

3. `puzzle_groups` — the 4 (or N) categories in a puzzle:
   - `id` (uuid, PK)
   - `puzzle_id` (uuid, FK → puzzles, ON DELETE CASCADE)
   - `category_name` (text) — the connection label
   - `difficulty_rank` (integer) — 1=yellow/easiest, 2=green, 3=blue, 4=purple/hardest
   - `sort_order` (integer)

4. `puzzle_words` — individual words:
   - `id` (uuid, PK)
   - `group_id` (uuid, FK → puzzle_groups, ON DELETE CASCADE)
   - `word` (text)
   - `display_text` (text, nullable) — if different from word (e.g., casing)
   - Unique constraint: no duplicate words within the same puzzle (write a unique index on puzzle_id + lower(word) — you'll need to join through puzzle_groups to get puzzle_id, so use a function or a denormalized puzzle_id column)

5. `puzzle_generation_jobs` — tracks async generation:
   - `id` (uuid, PK)
   - `config_id` (uuid, FK → puzzle_configs)
   - `status` (text: 'queued', 'generating', 'validating', 'complete', 'failed')
   - `error_message` (text, nullable)
   - `puzzle_id` (uuid, FK → puzzles, nullable) — set when puzzle is created
   - `attempts` (integer, default 0)
   - `created_at` (timestamptz)
   - `updated_at` (timestamptz)

Add indexes on:
- `puzzles.status` (for querying approved puzzles)
- `puzzles.config_id` + `puzzles.status` (for pool level checks)
- `puzzle_generation_jobs.status` (for worker polling)

Also create a `get_random_approved_puzzle` Postgres function that:
- Takes a config_id parameter
- Selects a random puzzle with status='approved' for that config
- Updates its times_served counter
- Returns the puzzle_id

Write this as a single .sql migration file. Add comments explaining each table's purpose.
```

---

## Phase 2: Puzzle Service Layer (Connect Pool to Existing API)

### What this produces
A Python service that your existing `generate-grid` endpoint can call to fetch a puzzle from the pool instead of hardcoded data.

### Prompt

```
I have a Flask + Supabase backend for a Connections word game. I just added puzzle pool tables (puzzles, puzzle_groups, puzzle_words, puzzle_configs — see the migration file).

My existing generate-grid endpoint creates a game by reading word groups from a connections schema. I need a service layer that fetches a random approved puzzle from the pool and formats it for my existing game creation logic.

Here is my existing API contract for reference — the game-status response shows the data shape my frontend expects:

{
  "connections": [
    {
      "relationship": "Category Name",
      "words": ["word1", "word2", "word3", "word4"],
      "guessed": false
    }
  ],
  "grid": ["word1", "word2", "...16 total"]
}

Create a `puzzle_pool_service.py` module with:

1. `get_puzzle_from_pool(config_name="classic")` — calls the `get_random_approved_puzzle` DB function, fetches the full puzzle with groups and words, and returns a dict matching my existing connections format (list of {relationship, words} objects). Raises a clear error if the pool is empty.

2. `get_pool_stats(config_name="classic")` — returns counts of puzzles by status (approved, draft, etc.) for monitoring.

3. `seed_puzzle_to_pool(puzzle_data)` — takes a puzzle dict (from the generation pipeline we'll build later) and inserts it into the puzzle/groups/words tables with status='draft'. Returns the puzzle_id.

4. `approve_puzzle(puzzle_id, validation_score, validation_report)` — updates a puzzle's status to 'approved' with validation results.

5. `reject_puzzle(puzzle_id, validation_report)` — marks a puzzle as 'rejected'.

Use the Supabase Python client for all DB operations. Include proper error handling and logging. Write it so I can later drop it into my existing Flask app as an import.

Also show me how to modify my existing generate-grid route to try the pool first and fall back to the old behavior if the pool is empty.
```

---

## Phase 3: Single Group Generation (The Atomic Unit)

### What this produces
A standalone module that makes one Claude API call to generate a single word group. This is the building block for everything else.

### Prompt

```
I'm building a Connections puzzle generator using the Anthropic Python SDK and Claude API. Before building the full pipeline, I need the atomic unit: generating a single high-quality word group.

Create a `group_generator.py` module with:

1. A `generate_single_group` function that:
   - Takes parameters: `category_type` (str), `existing_groups` (list of dicts, may be empty), `words_per_group` (int, default 4), `difficulty` (str: "yellow"|"green"|"blue"|"purple")
   - Calls the Anthropic API (Claude claude-sonnet-4-5-20250929) with a well-crafted prompt
   - Returns a dict: {"category_name": str, "words": list[str], "candidate_words": list[str], "design_notes": str}

   The prompt should:
   - Request 8 candidate words (not just 4) for later flexibility
   - Include all existing groups as context so words don't overlap
   - Require that at least one word plausibly fits an existing group (for red herring potential) — skip this requirement when generating the first group
   - Specify the difficulty level and what that means:
     - yellow: obvious/common knowledge connections
     - green: requires moderate thought
     - blue: non-obvious, cultural or specialized knowledge
     - purple: wordplay, lateral thinking, hidden patterns
   - Instruct that category names should be specific (not generic like "Animals") and that category name words should not appear in the word list

2. Use structured output (tool_use with a JSON schema) to guarantee valid response format. Define the schema clearly.

3. A `CATEGORY_TYPES` constant listing the category styles to rotate through:
   - "synonyms" — words that share a meaning
   - "members_of_set" — items belonging to a specific category
   - "fill_in_the_blank" — words that complete a common phrase with a shared word (e.g., ___ card: credit, business, playing, wild)
   - "wordplay" — anagrams, homophones, hidden words, letter patterns
   - "compound_words" — words that combine with a common word (e.g., fire___: truck, fly, work, place)
   - "cultural_knowledge" — requires knowledge of pop culture, history, etc.

4. Configuration for model, temperature (default 0.9), and max_tokens as module-level constants.

5. Proper error handling: retry up to 3 times on API errors with exponential backoff.

Include a `if __name__ == "__main__"` block that generates 3 sample groups iteratively (each seeing the previous ones) and prints them formatted. This lets me test the quality immediately.

Use the `anthropic` Python package. Assume ANTHROPIC_API_KEY is set as an environment variable.
```

---

## Phase 4: Full Iterative Generation Pipeline

### What this produces
The complete multi-step puzzle generation pipeline that chains group generation with brainstorming and red herring injection.

### Prompt

```
I have a `group_generator.py` module that generates single word groups using Claude (see the file in my project). Now I need to compose it into a full iterative puzzle generation pipeline.

Create a `puzzle_generator.py` module with:

1. `generate_puzzle(config)` — the main entry point. Takes a config dict with:
   - `num_groups` (int, default 4)
   - `words_per_group` (int, default 4)
   - `difficulty_profile` (str: "easy"|"standard"|"hard", default "standard")
   - `theme_hint` (optional str, e.g., "food" or "90s pop culture")

   Returns a complete puzzle dict ready for `seed_puzzle_to_pool()`.

The pipeline should execute these steps:

**Step 1 — Diversity Seed (Claude claude-sonnet-4-5-20250929, temp=1.0)**
Generate 4 random seed words from different domains. Ask Claude to write a brief creative story (2-3 sentences) incorporating them. This story becomes context for category brainstorming to prevent repetitive themes.

**Step 2 — Category Brainstorm (Claude claude-sonnet-4-5-20250929, temp=0.9)**
Given the seed story and difficulty profile, generate 6-8 candidate category themes. Each should include:
- A proposed category name
- The category type (from CATEGORY_TYPES in group_generator.py)
- A proposed difficulty level (yellow/green/blue/purple)
- A brief note on red herring potential

Then select the best `num_groups` categories, ensuring:
- At least 2 different category types are represented
- Difficulty levels span the range (at least one easy, one hard)
- Maximum red herring potential between groups

**Step 3 — Iterative Group Building**
For each selected category, call `generate_single_group()` from group_generator.py, passing all previously generated groups as context. From each group's 8 candidate words, select the best `words_per_group` based on:
- Red herring potential with other groups
- Word familiarity (avoid obscure words unless difficulty demands it)
- No exact duplicates across groups

**Step 4 — Red Herring Refinement (Claude claude-sonnet-4-5-20250929, temp=0.7)**
Given all groups with their final words, ask Claude to:
- Identify existing cross-group red herrings and rate their strength
- Suggest up to 3 word swaps that would increase misdirection
- Flag any words that feel too obscure or ambiguous
Apply suggested swaps if they improve overall puzzle quality.

**Step 5 — Final Assembly**
Package everything into the puzzle dict format expected by `seed_puzzle_to_pool()`:
{
  "groups": [
    {"category_name": str, "words": [str], "difficulty_rank": int, "sort_order": int}
  ],
  "generation_metadata": {
    "model": str, "seed_story": str, "category_candidates": list,
    "red_herring_analysis": str, "total_api_calls": int,
    "total_input_tokens": int, "total_output_tokens": int
  }
}

2. Track token usage across all API calls and include in metadata.

3. Add logging at each step so I can see the pipeline progress.

4. Handle failures gracefully: if any step fails after retries, return None with error details rather than crashing.

Include a `if __name__ == "__main__"` block that generates one puzzle and pretty-prints it.
```

---

## Phase 5: Embedding-Based Validation

### What this produces
A validation module using sentence-transformers that checks puzzle quality without any LLM calls (fast and free).

### Prompt

```
I'm building a validation pipeline for AI-generated Connections puzzles. The first layer is embedding-based analysis using sentence-transformers — it's fast, free, and catches structural quality issues.

Create a `embedding_validator.py` module with:

1. Use the `sentence-transformers` library with model `all-mpnet-base-v2`.

2. `validate_puzzle_embeddings(puzzle_data)` — takes a puzzle dict with groups/words and returns a validation report dict with:

   **a) Within-group coherence scores**
   For each group, compute average pairwise cosine similarity between word embeddings. Flag groups where coherence doesn't match expected difficulty thresholds:
   - Yellow (easiest): expected 0.28-0.32
   - Green: expected 0.22-0.28
   - Blue: expected 0.18-0.22
   - Purple (hardest): expected 0.12-0.18

   Note: these are guidelines, not hard cutoffs. Report the scores and whether they fall within expected ranges. Some category types (like wordplay/fill-in-the-blank) may have low embedding similarity but still be good puzzles — flag these as "embedding-divergent, manual review recommended" rather than auto-failing them.

   **b) Between-group distinctiveness**
   For each pair of groups, compute average cross-group cosine similarity. The ratio of within-group to between-group similarity should be > 1.5 for clear separation. Flag pairs where ratio < 1.2 as potential ambiguity.

   **c) Bridge word detection**
   For each word, compute its similarity to its own group centroid vs. every other group centroid. Flag words where cross-group similarity exceeds 80% of own-group similarity — these are potential bridge words (could be good red herrings or problematic ambiguity).

   **d) Clustering recovery test**
   Run constrained k-means (k = num_groups) on all word embeddings and check if the clusters match the intended groupings. Report the adjusted Rand index score. Score > 0.7 means embeddings alone can solve it (probably too easy). Score < 0.2 means groupings rely on non-semantic connections (fine for wordplay categories, concerning for semantic ones).

3. `compute_difficulty_score(validation_report)` — uses the embedding metrics to estimate overall difficulty on a 0-1 scale.

4. The overall report should include:
   - `passed` (bool) — whether the puzzle meets minimum quality thresholds
   - `score` (float, 0-1) — overall quality score
   - `group_coherence` (list of per-group scores and flags)
   - `group_distinctiveness` (matrix of between-group scores)
   - `bridge_words` (list of flagged words with details)
   - `clustering_recovery` (ARI score and interpretation)
   - `warnings` (list of human-readable issues)
   - `auto_fail_reasons` (list — if any, puzzle should be rejected)

   Auto-fail conditions:
   - Any two groups have between-group similarity > 0.55 (too ambiguous)
   - Any group has within-group coherence < 0.05 (words are essentially random)
   - Duplicate words detected across groups
   - Clustering ARI > 0.85 AND all groups are semantic type (too trivially solvable)

Include `if __name__ == "__main__"` that validates a hardcoded example puzzle (make up a reasonable one) and prints the full report.

Dependencies: sentence-transformers, scikit-learn (for k-means and ARI), numpy. Use requirements.txt or note what to pip install.
```

---

## Phase 6: LLM Solver Validation

### What this produces
A second validation layer that uses cheap Claude Haiku calls to verify puzzles are solvable and unambiguous.

### Prompt

```
I have an embedding-based validator for my Connections puzzles. Now I need the second validation layer: an LLM solver that attempts to solve the puzzle and checks for ambiguity.

Create a `llm_validator.py` module with:

1. `solve_puzzle_attempt(puzzle_words, num_groups, words_per_group, model="claude-haiku-4-5-20251001", temperature=0.5)` — Given ONLY the shuffled list of all words (no categories revealed), ask Claude to solve the puzzle. Return its proposed groupings as a list of {"category_name": str, "words": list[str]}.

   The prompt should:
   - Present only the shuffled words
   - Tell the model how many groups and words per group to find
   - Ask it to reason step-by-step about possible groupings before committing
   - Use structured output to get clean JSON back

2. `self_consistency_check(puzzle_data, num_attempts=8)` — Run `solve_puzzle_attempt` multiple times at temperature > 0. For each attempt, score how many groups match the intended solution (exact word set match). Return:
   - `agreement_rate` (float) — what fraction of attempts got the full puzzle right
   - `per_group_solve_rate` (list of floats) — for each intended group, what fraction of attempts found it
   - `common_mistakes` (list) — most frequent incorrect groupings that appeared across attempts
   - `consensus_solution` (list) — the most common grouping across all attempts

3. `devils_advocate_check(puzzle_data, model="claude-haiku-4-5-20251001")` — A separate prompt that:
   - Shows all 16 words AND the intended groupings
   - Asks Claude to find an alternative valid grouping — different categories that also make logical sense
   - If it finds one, the puzzle has an ambiguity problem
   - Return: {"found_alternative": bool, "alternative_groupings": list|None, "reasoning": str}

4. `difficulty_calibration(puzzle_data)` — Quick heuristic based on solver results:
   - Haiku solves on first try at temp=0 → "too_easy"
   - Haiku gets 2-3 groups right → "appropriate"
   - Haiku gets 0-1 groups right → "hard_or_flawed"
   Return the assessment plus the Haiku temp=0 solution for review.

5. `validate_with_llm(puzzle_data)` — Orchestrates all checks and returns a combined report:
   - `passed` (bool)
   - `solver_consistency` (self-consistency results)
   - `ambiguity_check` (devil's advocate results)
   - `difficulty_assessment` (calibration results)
   - `warnings` (list)
   - `auto_fail_reasons` (list)

   Auto-fail conditions:
   - self-consistency agreement_rate > 0.9 AND difficulty_assessment is "too_easy" (trivial puzzle)
   - devils_advocate found a fully valid alternative grouping
   - self-consistency agreement_rate < 0.1 (puzzle may be unsolvable or deeply ambiguous)

Use the anthropic Python SDK. Track token usage across all calls. Include `if __name__ == "__main__"` with a test puzzle.
```

---

## Phase 7: Validation Orchestrator

### What this produces
A single entry point that runs both validators and produces a final pass/fail decision.

### Prompt

```
I have two puzzle validators:
- `embedding_validator.py` — fast, free, checks structural quality via sentence embeddings
- `llm_validator.py` — uses Claude Haiku to verify solvability and check for ambiguity

Create a `validation_pipeline.py` module that orchestrates them:

1. `validate_puzzle(puzzle_data)` — runs the full validation pipeline:

   **Stage 1: Structural checks (no API calls)**
   - Correct number of groups and words per group
   - No duplicate words (case-insensitive)
   - All words are single words or short phrases (no sentences)
   - Category names are non-empty and distinct

   **Stage 2: Embedding validation**
   - Call `validate_puzzle_embeddings()`
   - If it auto-fails, skip LLM validation (save money) and return rejection

   **Stage 3: LLM validation**
   - Call `validate_with_llm()`
   - Only run if embedding validation passed

   **Final scoring:**
   - Combine embedding score (40% weight) and LLM score (60% weight) into a final 0-1 quality score
   - `passed` = no auto-fail reasons from either validator AND combined score > 0.6
   - Return a unified report with sections from both validators

2. `validate_and_store(puzzle_id, supabase_client)` — fetches a draft puzzle from the DB, runs validation, and calls either `approve_puzzle()` or `reject_puzzle()` from puzzle_pool_service.py based on results.

3. Logging throughout so I can monitor validation in production.

Include `if __name__ == "__main__"` that generates a puzzle using `puzzle_generator.py`, validates it, and prints whether it passed.
```

---

## Phase 8: Background Worker & Pool Management

### What this produces
The async job system that keeps the puzzle pool replenished.

### Prompt

```
I have the full puzzle generation and validation pipeline:
- `puzzle_generator.py` — generates puzzles using Claude
- `validation_pipeline.py` — validates them (embeddings + LLM)
- `puzzle_pool_service.py` — stores them in Supabase

I need a background worker system to keep the puzzle pool replenished. My backend is Python + Flask + Supabase. I do NOT want to add Redis/Celery — I want something simpler that I can run as a separate process.

Create:

1. `worker.py` — a standalone Python process that:
   - Polls `puzzle_generation_jobs` table for 'queued' jobs every 30 seconds
   - For each job: sets status to 'generating', runs the pipeline (generate → validate → store), updates job status
   - Handles failures: increment attempts, set status to 'failed' after 3 attempts, log errors
   - Rate limits itself to max 10 Claude API calls per minute (use a simple token bucket)
   - Graceful shutdown on SIGINT/SIGTERM

2. `pool_monitor.py` — a scheduled task (runs every 5 minutes) that:
   - Checks puzzle pool levels per config
   - If approved puzzles < 20 for any config, queues generation jobs to bring it up to 50
   - Avoids queuing duplicate jobs (check for existing 'queued'/'generating' jobs)
   - Logs pool health stats

3. `run_workers.py` — entry point that runs both the job worker and pool monitor in the same process using threading or asyncio.

4. A Flask CLI command or admin endpoint `POST /admin/generate-puzzles` that:
   - Takes `count` (int) and optional `config_name` (str)
   - Queues that many generation jobs
   - Returns the job IDs

Keep it simple. No message queue, no Celery. Just Supabase polling + Python threading. It's fine if this only handles moderate throughput — I can always upgrade later.

Include clear instructions for how to run the worker alongside my Flask app (separate terminal/process).
```

---

## Phase 9: API Integration & Prompt Caching

### What this produces
Connects everything to your existing Flask API and optimizes costs.

### Prompt

```
I have the full puzzle generation pipeline, validation, and background workers. Now I need to:

1. **Wire up the existing API**: Modify my Flask `generate-grid` endpoint to pull from the puzzle pool. Show me the minimal changes needed — the endpoint should:
   - Call `get_puzzle_from_pool("classic")`
   - If pool is empty, fall back to existing behavior and log a warning
   - If pool is running low (< 10 approved), trigger async generation jobs

2. **Add Anthropic prompt caching**: Update `group_generator.py` and `puzzle_generator.py` to use prompt caching for the system prompts. The system prompt + few-shot examples should be marked with `cache_control: {"type": "ephemeral"}`. Show me:
   - How to structure the API calls with cache_control
   - Where to add the cache breakpoints in my existing prompts
   - Expected cost savings

3. **Add batch processing support**: Create a `batch_generator.py` that:
   - Collects multiple puzzle generation requests
   - Submits them via the Anthropic Batch API for 50% cost reduction
   - Polls for completion and processes results
   - This is for non-urgent pool replenishment (e.g., nightly batch fills)

4. **Token usage tracking**: Add a simple `usage_tracker.py` that logs every API call's token counts and estimated cost to a Supabase `api_usage` table. Include a function to get cost summaries by date range.

Show me exactly which files to modify and what to add. Keep changes minimal and surgical.
```

---

## How to Use These Prompts

1. **Open your project in Claude Code** so it has full context of your existing codebase.

2. **Work through phases sequentially.** Each phase references modules built in previous phases.

3. **Test each phase before moving on:**
   - Phase 1: Run the migration, verify tables exist in Supabase
   - Phase 2: Write a quick test that seeds a puzzle and reads it back
   - Phase 3: Run the `__main__` block, review generated groups for quality
   - Phase 4: Generate a full puzzle, check it looks reasonable
   - Phase 5: Validate your generated puzzle, review the report
   - Phase 6: Run solver validation, check if difficulty assessment makes sense
   - Phase 7: End-to-end: generate → validate → see pass/fail
   - Phase 8: Start the worker, verify it polls and processes jobs
   - Phase 9: Hit your API, get a puzzle from the pool

4. **Iterate on prompt quality in Phase 3.** This is where puzzle quality lives. Spend time tweaking the system prompt, adding few-shot examples, and adjusting temperature until you're happy with the word groups Claude produces. Everything downstream depends on this.

5. **When pasting a prompt**, also tell Claude Code: "Here's my existing project structure" and let it explore. It'll adapt the code to fit your patterns (import style, error handling, logging, etc.).

6. **For future extensibility** (variable grid sizes, difficulty tuning): the `puzzle_configs` table and parameterized functions handle this from day one. When you're ready, just add new configs ("mini" = 3×3, "extended" = 5×4) and the entire pipeline adapts.
