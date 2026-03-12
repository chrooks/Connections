# Database Schema Codemap

**Last Updated:** 2026-03-12
**Platform:** Supabase (PostgreSQL)
**Migrations:** `backend/supabase/migrations/` (timestamped SQL files)

## Overview

All persistent state lives in Supabase PostgreSQL. The schema is organized into three logical zones:

1. **Game Sessions** — Player games, state, results
2. **Puzzle Catalog** — Pre-generated puzzles, categories, words
3. **Operations** — Generation jobs, API usage, user preferences

## Core Tables

### 1. game_sessions

**Purpose:** Track active and completed games

**Schema:**
```sql
CREATE TABLE game_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- NULL for guest games
    puzzle_id UUID NOT NULL REFERENCES puzzles(id),
    grid TEXT NOT NULL,  -- JSON: ["WORD1", "WORD2", ..., "WORD16"]
    guesses TEXT NOT NULL DEFAULT '[]',  -- JSON: [["WORD1", "WORD2", "WORD3", "WORD4"], ...]
    mistakes_left INT NOT NULL DEFAULT 4,
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',  -- IN_PROGRESS, WIN, LOSS
    forfeited BOOLEAN DEFAULT FALSE,
    completion_time_seconds INT,  -- Set when game ends
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_game_sessions_user_id ON game_sessions(user_id);
CREATE INDEX idx_game_sessions_status ON game_sessions(status);
```

**Fields:**
- `id` — Unique game identifier
- `user_id` — Supabase auth user (NULL = guest)
- `puzzle_id` — Link to puzzle used in this game
- `grid` — JSON array of 16 shuffled words
- `guesses` — JSON array of 4-word guesses made
- `mistakes_left` — 0-4
- `status` — IN_PROGRESS, WIN (all 4 groups found), LOSS (mistakes exhausted)
- `forfeited` — True if user voluntarily gave up
- `completion_time_seconds` — Logged on win/loss
- `created_at`, `updated_at` — Audit trail

**Queries:**
```sql
-- Get user's active game
SELECT * FROM game_sessions
WHERE user_id = $1 AND status = 'IN_PROGRESS'
LIMIT 1;

-- Get user's game history
SELECT * FROM game_sessions
WHERE user_id = $1 AND status IN ('WIN', 'LOSS')
ORDER BY created_at DESC;

-- Get all completed puzzles for a user
SELECT DISTINCT puzzle_id FROM game_sessions
WHERE user_id = $1 AND status IN ('WIN', 'LOSS');
```

### 2. puzzles

**Purpose:** Master puzzle records with validation scores

**Schema:**
```sql
CREATE TABLE puzzles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES puzzle_configs(id),
    status TEXT NOT NULL DEFAULT 'draft',  -- draft, approved, rejected
    validation_score DECIMAL(5, 2),  -- 0-100, NULL if not validated
    validation_report TEXT,  -- JSON summary of validation results
    times_served INT DEFAULT 0,
    difficulty_estimate TEXT,  -- easy, medium, hard, expert
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_puzzles_config_id ON puzzles(config_id);
CREATE INDEX idx_puzzles_status ON puzzles(status);
CREATE INDEX idx_puzzles_validation_score ON puzzles(validation_score);
```

**Fields:**
- `id` — Unique puzzle identifier
- `config_id` — Links to generation config (classic, etc.)
- `status` — draft (not yet validated), approved (ready to serve), rejected
- `validation_score` — 0-100 from validation pipeline
- `validation_report` — JSON {embedding_score, llm_score, issues: [...]}
- `times_served` — Counter for analytics
- `difficulty_estimate` — Computed during generation
- `created_at`, `updated_at` — Tracking

**Queries:**
```sql
-- Get a random approved puzzle (with exclusions)
SELECT * FROM puzzles
WHERE config_id = $1 AND status = 'approved' AND id NOT IN (...)
ORDER BY RANDOM()
LIMIT 1;

-- Get rejected puzzles for admin review
SELECT * FROM puzzles
WHERE status = 'rejected'
ORDER BY validation_score DESC;

-- Get pool stats
SELECT status, COUNT(*) FROM puzzles WHERE config_id = $1
GROUP BY status;
```

### 3. puzzle_groups

**Purpose:** Categories within puzzles (1:4 relationship)

**Schema:**
```sql
CREATE TABLE puzzle_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    puzzle_id UUID NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
    category TEXT NOT NULL,  -- e.g., "Things that are sweet"
    hint TEXT,
    difficulty TEXT,  -- easy, medium, hard, expert
    category_type TEXT,  -- WORDPLAY, COMPOUND, SEMANTIC, CULTURAL, SPATIAL
    group_order INT NOT NULL DEFAULT 0,  -- 0-3
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_puzzle_groups_puzzle_id ON puzzle_groups(puzzle_id);
```

**Fields:**
- `id` — Unique group identifier
- `puzzle_id` — Parent puzzle
- `category` — Human-readable category name
- `hint` — Optional hint text
- `difficulty` — Relative difficulty of this group
- `category_type` — Type (controls validation rules)
- `group_order` — Position 0-3 (for display)

**Queries:**
```sql
-- Get all groups for a puzzle
SELECT * FROM puzzle_groups
WHERE puzzle_id = $1
ORDER BY group_order;
```

### 4. puzzle_words

**Purpose:** Words within groups (4 per group, 16 per puzzle)

**Schema:**
```sql
CREATE TABLE puzzle_words (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES puzzle_groups(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    word_order INT NOT NULL DEFAULT 0,  -- 0-3
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_puzzle_words_group_id ON puzzle_words(group_id);
```

**Fields:**
- `id` — Unique word identifier
- `group_id` — Parent group
- `word` — Uppercase word (e.g., "APPLE")
- `word_order` — Position 0-3 within group

**Queries:**
```sql
-- Get all words for a puzzle (16 total)
SELECT pw.word
FROM puzzle_words pw
JOIN puzzle_groups pg ON pw.group_id = pg.id
WHERE pg.puzzle_id = $1;

-- Check if a word is in a group
SELECT EXISTS(
    SELECT 1 FROM puzzle_words pw
    JOIN puzzle_groups pg ON pw.group_id = pg.id
    WHERE pg.puzzle_id = $1 AND pw.word = $2
);
```

### 5. puzzle_generation_jobs

**Purpose:** Work queue for background puzzle generation

**Schema:**
```sql
CREATE TABLE puzzle_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES puzzle_configs(id),
    status TEXT NOT NULL DEFAULT 'queued',  -- queued, processing, completed, failed
    puzzle_id UUID REFERENCES puzzles(id),  -- Set on completion
    error_message TEXT,  -- Set if failed
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_puzzle_generation_jobs_status ON puzzle_generation_jobs(status);
CREATE INDEX idx_puzzle_generation_jobs_config_id ON puzzle_generation_jobs(config_id);
```

**Fields:**
- `id` — Job identifier
- `config_id` — Generation config template
- `status` — queued (awaiting worker), processing (claimed), completed (done), failed
- `puzzle_id` — Link to generated puzzle (NULL until completed)
- `error_message` — Failure reason
- `created_at` — Job enqueued
- `started_at` — Worker claimed
- `completed_at` — Worker finished

**Pattern:** Optimistic locking for claims
```sql
UPDATE puzzle_generation_jobs
SET status = 'processing', started_at = NOW()
WHERE id = $1 AND status = 'queued';
```

**Queries:**
```sql
-- Poll for queued jobs
SELECT * FROM puzzle_generation_jobs
WHERE status = 'queued'
ORDER BY created_at
LIMIT 1;

-- Check job status
SELECT status, puzzle_id, error_message FROM puzzle_generation_jobs
WHERE id = $1;
```

### 6. api_usage

**Purpose:** Append-only audit trail of Claude API calls

**Schema:**
```sql
CREATE TABLE api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model TEXT NOT NULL,  -- claude-sonnet, claude-opus, etc.
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cache_creation_tokens INT DEFAULT 0,  -- Prompt caching
    cache_read_tokens INT DEFAULT 0,      -- Prompt caching
    cost_usd DECIMAL(10, 8),
    source TEXT NOT NULL,  -- puzzle_generator, batch_generator, llm_validator
    puzzle_id UUID REFERENCES puzzles(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_usage_created_at ON api_usage(created_at);
CREATE INDEX idx_api_usage_puzzle_id ON api_usage(puzzle_id);
```

**Fields:**
- `id` — Log entry identifier
- `model` — Model name
- `input_tokens`, `output_tokens` — API usage
- `cache_creation_tokens`, `cache_read_tokens` — Prompt caching (90% discount)
- `cost_usd` — Calculated cost
- `source` — Component that made call
- `puzzle_id` — If call was for puzzle generation
- `created_at` — Timestamp

**Cost Calculation:**
```python
# Claude 3.5 Sonnet pricing (as of 2026)
input_cost = (input_tokens * 3 + cache_creation_tokens * 3.75) / 1_000_000
cache_cost = (cache_read_tokens * 0.3) / 1_000_000
output_cost = (output_tokens * 15) / 1_000_000
total_cost = input_cost + cache_cost + output_cost
```

**Queries:**
```sql
-- Cost summary by date
SELECT DATE(created_at) as date,
       SUM(cost_usd) as daily_cost,
       COUNT(*) as api_calls
FROM api_usage
WHERE created_at >= $1
GROUP BY date
ORDER BY date;

-- Cost by source
SELECT source,
       SUM(cost_usd) as total_cost,
       COUNT(*) as calls,
       AVG(cost_usd) as avg_cost_per_call
FROM api_usage
WHERE created_at >= $1
GROUP BY source;

-- Cost per puzzle generated
SELECT puzzle_id,
       SUM(cost_usd) as puzzle_cost,
       COUNT(*) as api_calls
FROM api_usage
WHERE source = 'puzzle_generator'
GROUP BY puzzle_id
ORDER BY puzzle_cost DESC;
```

### 7. puzzle_configs

**Purpose:** Generation config templates

**Schema:**
```sql
CREATE TABLE puzzle_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,  -- e.g., 'classic'
    description TEXT,
    num_groups INT DEFAULT 4,
    words_per_group INT DEFAULT 4,
    difficulty_profile TEXT DEFAULT 'standard',
    theme_hint TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` — Config identifier
- `name` — Unique config slug (classic, hard, easy, etc.)
- `description` — Purpose/guidance
- `num_groups`, `words_per_group` — Puzzle structure
- `difficulty_profile` — Difficulty level hint for generator
- `theme_hint` — Optional theme hint for brainstorm step

**Default Data:**
```sql
INSERT INTO puzzle_configs (name, description, difficulty_profile)
VALUES ('classic', 'Standard Connections puzzle', 'standard');
```

### 8. user_puzzle_exclusions

**Purpose:** Track completed puzzles per user (prevent re-serving)

**Schema:**
```sql
CREATE TABLE user_puzzle_exclusions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    puzzle_id UUID NOT NULL REFERENCES puzzles(id),
    UNIQUE(user_id, puzzle_id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_puzzle_exclusions_user_id ON user_puzzle_exclusions(user_id);
```

**Fields:**
- `user_id` — Supabase auth user
- `puzzle_id` — Completed puzzle
- Unique constraint prevents duplicates

**Usage:**
```python
# When guest signs up, insert their completed puzzles
for puzzle_id in completed_puzzle_ids:
    insert_exclusion(user_id, puzzle_id)

# When fetching puzzle for user:
exclusions = get_user_exclusions(user_id)
puzzle = get_puzzle_from_pool(config_id, exclude_ids=exclusions)
```

## Data Relationships

```
puzzles (1) ──── (many) puzzle_groups (1) ──── (many) puzzle_words
    │                           │
    │                      (4 words each)
    │
    └── (many) game_sessions
        │
        ├─ (many guesses per game)
        └─ (references puzzle used)

puzzle_configs (1) ──── (many) puzzles
    │
    └── (many) puzzle_generation_jobs

auth.users (1) ──── (many) game_sessions
    │
    └── (many) user_puzzle_exclusions
        │
        └── (many) puzzles

api_usage (many) → puzzles (for audit trail)
```

## Migrations

**Location:** `backend/supabase/migrations/`

**Pattern:** Timestamped SQL files
```
20250301_001_initial_schema.sql
20250305_002_add_validation_score.sql
20250310_003_add_cache_tokens.sql
```

**Apply:**
```bash
cd backend
supabase db push  # Applies unapplied migrations
```

**Important:** Always apply migrations immediately after writing. Never leave unapplied migrations.

## Queries & Operations

### Player Pool Queries

```python
# Get next puzzle for player
puzzle = (
    supabase.table("puzzles")
    .select("id, groups:puzzle_groups(*)")
    .eq("config_id", config_id)
    .eq("status", "approved")
    .not_in("id", user_exclusions)  # Exclude completed
    .order_by("RANDOM()")
    .limit(1)
    .execute()
)

# Fetch full puzzle for game
groups = (
    supabase.table("puzzle_groups")
    .select("*, words:puzzle_words(*)")
    .eq("puzzle_id", puzzle_id)
    .order_by("group_order")
    .execute()
)
```

### Admin Queries

```python
# List rejected puzzles with scores
rejected = (
    supabase.table("puzzles")
    .select("id, validation_score, validation_report, groups:puzzle_groups(*)")
    .eq("status", "rejected")
    .order_by("validation_score", desc=True)
    .limit(10)
    .execute()
)

# Get pool stats
stats = (
    supabase.table("puzzles")
    .select("status, count=count()")
    .eq("config_id", config_id)
    .group_by("status")
    .execute()
)
```

### Cost Tracking

```python
# Log API call
supabase.table("api_usage").insert({
    "model": "claude-sonnet-4-5-20250929",
    "input_tokens": 2500,
    "output_tokens": 1000,
    "cache_creation_tokens": 500,
    "cache_read_tokens": 0,
    "cost_usd": 0.045,
    "source": "puzzle_generator",
    "puzzle_id": puzzle_id
}).execute()

# Query costs
from datetime import datetime, timedelta
start = datetime.now() - timedelta(days=7)

costs = supabase.table("api_usage").select(
    "source, SUM(cost_usd) as total"
).gte("created_at", start.isoformat()).group_by("source").execute()
```

## Row-Level Security (RLS)

**Note:** The Flask backend uses the service_role key (bypasses RLS), but RLS policies should still be defined for frontend access and data safety.

**Suggested Policies:**

```sql
-- game_sessions: Users can only see their own games
CREATE POLICY "Users can view own game_sessions"
ON game_sessions FOR SELECT
USING (auth.uid() = user_id OR user_id IS NULL);

-- user_puzzle_exclusions: Users can only see their own
CREATE POLICY "Users can view own puzzle_exclusions"
ON user_puzzle_exclusions FOR SELECT
USING (auth.uid() = user_id);
```

## Performance Considerations

**Indexes:**
- `game_sessions(user_id)` — User history queries
- `puzzles(config_id, status)` — Pool queries
- `puzzle_groups(puzzle_id)` — Puzzle detail fetch
- `puzzle_generation_jobs(status)` — Worker polling
- `api_usage(created_at)` — Cost summaries

**Query Optimization:**
- Batch word fetches with `puzzle_groups(*, words:puzzle_words(*))`
- Use LIMIT for large result sets
- Denormalize `times_served` on puzzles to avoid counts

## Common Patterns

### Create a Game
```python
# 1. Get puzzle from pool
puzzle = get_puzzle_from_pool(config_id, user_exclusions)

# 2. Shuffle 16 words
grid = shuffle(puzzle["all_words"])

# 3. Insert game_sessions row
game = supabase.table("game_sessions").insert({
    "user_id": user_id,
    "puzzle_id": puzzle["id"],
    "grid": json.dumps(grid),
    "guesses": "[]",
    "mistakes_left": 4,
    "status": "IN_PROGRESS"
}).execute()

return game.data[0]["id"]
```

### Process a Guess
```python
# 1. Fetch game state
game = get_game_from_db(game_id)

# 2. Check words are in grid
if not all(word in game["grid"] for word in guess):
    return error("Invalid words")

# 3. Check against connections
matching_group = None
for group in game["connections"]:
    if set(guess) == set(group["words"]):
        matching_group = group
        break

if matching_group:
    # Correct — mark group guessed
    update_game_state(game_id, {
        "guesses": game["guesses"] + [guess],
        "connections": mark_guessed(game["connections"], matching_group)
    })
else:
    # Incorrect — lose a mistake
    update_game_state(game_id, {
        "guesses": game["guesses"] + [guess],
        "mistakes_left": game["mistakes_left"] - 1
    })

# 4. Check win/loss conditions
if all_guessed(game["connections"]):
    update_game_state(game_id, {"status": "WIN"})
elif game["mistakes_left"] == 0:
    update_game_state(game_id, {"status": "LOSS"})
```

---

**See also:** [Backend Codemap](backend.md), [Generation Pipeline](generation.md), [API Reference](api.md)
