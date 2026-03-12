# Backend Codemap

**Last Updated:** 2026-03-12
**Entry Points:** `backend/src/app.py`, `backend/src/workers/run_workers.py`
**Tech Stack:** Python 3.10+ + Flask + Supabase + Anthropic API

## Architecture Overview

```
Flask App (src/app.py)
├─ API Blueprint (/connections/*)
│  ├─ generate_grid() — GET /generate-grid
│  ├─ submit_guess() — POST /submit-guess
│  ├─ game_status() — POST /game-status
│  ├─ restart_game() — POST /restart-game
│  ├─ forfeit_game() — POST /forfeit-game
│  ├─ record_time() — POST /record-completion-time
│  ├─ user_stats() — GET /user/stats
│  ├─ user_history() — GET /user/history
│  └─ claim_guest_data() — POST /claim-guest-data
│
├─ Admin Blueprint (/admin/*)
│  ├─ generate_puzzles() — POST /generate-puzzles
│  ├─ get_rejected_puzzles() — GET /puzzles/rejected
│  ├─ start_review_game() — POST /puzzles/{id}/start-review-game
│  └─ approve_puzzle() — POST /puzzles/{id}/approve
│
└─ Services (core logic)
   ├─ game.py — Game state & logic
   ├─ game_session_service.py — DB ops for sessions
   ├─ puzzle_pool_service.py — Pool management
   ├─ usage_tracker.py — API cost tracking
   ├─ auth/middleware.py — JWT validation
   └─ workers/ — Background processes

Workers (src/workers/)
├─ run_workers.py — Entry point
├─ worker.py — Job poller & processor
├─ pool_monitor.py — Puzzle pool health check
└─ Generation Pipeline
   ├─ puzzle_generator.py — Multi-step generation
   ├─ group_generator.py — Single category generation
   ├─ batch_generator.py — Batch API generation
   └─ Validation Pipeline
      ├─ embedding_validator.py — Semantic similarity
      ├─ llm_validator.py — LLM-based quality check
      └─ validation_pipeline.py — Orchestration
```

## Key Modules

### Game Logic (`game/`)

| Module | Purpose | Key Functions |
|--------|---------|---|
| `game.py` | Core game state & logic | `create_new_game()`, `process_guess()`, `restart_game()`, `_replenish_pool_async()` |

**game.py exports:**
- `create_new_game(user_id, guest_exclude_ids)` — Create game session, fetch puzzle from pool
- `get_game_state(game_id)` — Current grid, guesses, connections, mistakes
- `process_guess(game_id, guess)` — Validate & check guess against connections
- `restart_game(game_id, user_id)` — New puzzle for same session
- `get_all_games_data()` — Debug: all games in DB

**Key Logic:**
- Pool replenishment: async daemon thread monitors pool health, queues jobs when < 10 approved puzzles
- Guess validation: checks word membership, duplicate detection, connection matching
- Status transitions: IN_PROGRESS → WIN/LOSS

### Services (`services/`)

| Module | Purpose |
|--------|---------|
| `game_session_service.py` | DB CRUD for game_sessions, user stats, guest data transfer |
| `puzzle_pool_service.py` | Puzzle pool queries (approved only), seed/validate/approve/reject |
| `usage_tracker.py` | Log Claude API calls, costs, tokens |
| `embedding_validator.py` | Semantic similarity checks for puzzle validation |
| `llm_validator.py` | LLM-based puzzle quality checks |
| `validation_pipeline.py` | Orchestrates embeddings + LLM validation |
| `utils.py` | Common response formatting, request validation |

**game_session_service.py exports:**
- `add_new_game(puzzle_id, user_id)` — Insert game_sessions row
- `get_game_from_db(game_id)` — Full game state from DB
- `get_active_game_for_user(user_id)` — User's current in-progress game
- `get_completed_puzzle_ids_for_user(user_id)` — Exclusion list for pool
- `check_guess(game_id, words)` — Validate guess against grid & connections
- `reset_game(game_id)` — Clear guesses, reset mistakes
- `update_game_state(game_id, updates)` — Merge game state changes
- `record_completion_time(game_id, seconds)` — Log play duration
- `forfeit_game(game_id)` — Mark as forfeited loss
- `transfer_guest_data(user_id, active_game_id, completed_puzzle_ids)` — Migrate guest data
- `get_user_stats(user_id)` — Wins, losses, avg time
- `get_user_history(user_id)` — All completed games

**puzzle_pool_service.py exports:**
- `get_puzzle_from_pool(config_name, exclude_ids)` — Fetch & format approved puzzle
- `get_pool_stats(config_name)` — Count by status (approved, pending, rejected)
- `seed_puzzle_to_pool(puzzle_data)` — Insert draft puzzle
- `approve_puzzle(puzzle_id, score, report)` — Mark approved
- `reject_puzzle(puzzle_id, report)` — Mark rejected
- `PlayerExhaustedPoolError` — Exception when player has completed all puzzles

**usage_tracker.py exports:**
- `log_api_call(model, input_tokens, output_tokens, source, puzzle_id)` — Record API usage
- `get_cost_summary(start_date, end_date)` — Query cost by date range

### Auth (`auth/`)

| Module | Purpose |
|--------|---------|
| `middleware.py` | JWT extraction & validation |

**auth/middleware.py exports:**
- `get_optional_user_id()` — Extract user_id from JWT (None if not present)
- `require_auth` — Decorator to enforce authentication

**Implementation:**
- Extracts JWT from `Authorization: Bearer <token>` header
- Decodes via Supabase JS client (or validates locally)
- Sets `g.user_id` for request duration
- Guests requests have `user_id = None`

### Blueprints (Routes)

#### API Routes (`blueprints/api/routes.py`)

| Route | Method | Purpose | Auth |
|-------|--------|---------|------|
| `/connections/generate-grid` | GET | Start new game | Optional (guest OK) |
| `/connections/submit-guess` | POST | Process guess | No |
| `/connections/game-status` | POST | Fetch game state | No |
| `/connections/restart-game` | POST | New puzzle | Optional |
| `/connections/forfeit-game` | POST | Voluntary loss | No |
| `/connections/record-completion-time` | POST | Log play time | No |
| `/connections/get-game-data` | GET | All games (debug) | No |
| `/connections/user/stats` | GET | User aggregate stats | Required |
| `/connections/user/history` | GET | User game history | Required |
| `/connections/claim-guest-data` | POST | Transfer guest data | Required |

#### Admin Routes (`blueprints/admin/routes.py`)

| Route | Method | Purpose | Auth |
|-------|--------|---------|------|
| `/admin/generate-puzzles` | POST | Queue generation jobs | Required (admin) |
| `/admin/puzzles/rejected` | GET | List rejected puzzles | Required (admin) |
| `/admin/puzzles/{id}/start-review-game` | POST | Create review game | Required (admin) |
| `/admin/puzzles/{id}/approve` | POST | Human override approve | Required (admin) |

## Data Flow

### Game Start
```
1. GET /generate-grid
2. Backend calls get_puzzle_from_pool(config_name, exclude_ids)
3. If pool empty → checks for fallback generation job
4. Creates game_sessions row with puzzle_id, grid, connections
5. Returns gameId
```

### Guess Processing
```
1. POST /submit-guess { gameId, guess }
2. Backend calls check_guess(game_id, guess)
3. Validates: word membership, duplicates, not already guessed
4. If valid:
   - Checks against connections
   - If match: mark connection "guessed"
   - If no match: decrement mistakesLeft
5. Checks win/loss conditions
6. Saves state to DB
7. Returns { isCorrect, mistakesLeft, status }
```

### Puzzle Generation (Worker Path)
```
1. Admin POST /admin/generate-puzzles { count: 5 }
2. Routes writes N rows to puzzle_generation_jobs (status=queued)
3. Returns immediately
4. Worker polls for queued jobs (optimistic lock: UPDATE WHERE status=queued)
5. Claims job, executes generate_puzzle() multi-step pipeline:
   - Step 1: Diversity seed (temp=1.0) + 4 domain ideas
   - Step 2: Category brainstorm (temp=0.9) → 6-8 themes
   - Step 3: Iterative group building per category
   - Step 3.5: Embedding bridge analysis
   - Step 4: Red herring refinement (temp=0.7)
   - Step 5: Package into puzzle dict
6. Runs validation_pipeline (embedding + LLM)
7. Seeds to pool (draft) or rejects
8. Updates job status=completed/failed
```

### Puzzle Validation
```
1. validation_pipeline.validate(puzzle) called by worker
2. embedding_validator: cosine similarity within groups < 0.7, between groups > 0.8
3. llm_validator: LLM review of difficulty, connection clarity, misdirection
4. Returns score (0-100) + detailed report
5. If score >= threshold: approve_puzzle()
6. Else: reject_puzzle() (human can override via admin endpoint)
```

## Database Integration

**Supabase Tables:**
- `game_sessions` — Active/completed games
- `puzzles` — Master puzzle records
- `puzzle_groups` — Categories within puzzles
- `puzzle_words` — Words within groups
- `puzzle_generation_jobs` — Work queue
- `api_usage` — API call log
- `user_puzzle_exclusions` — Completed puzzle tracking (per user)
- `puzzle_configs` — Generation config templates

**Data Access:**
- Lazy singleton Supabase client in `puzzle_pool_service._get_client()`
- Service role key (bypasses RLS) for server-side ops
- Optimistic locking in worker (UPDATE ... WHERE status=queued)

## Workers (`workers/`)

| Module | Purpose |
|--------|---------|
| `run_workers.py` | Entry point: spawns worker & pool_monitor threads |
| `worker.py` | Polls jobs, claims, generates, validates, seeds |
| `pool_monitor.py` | Monitors pool health, triggers replenishment |

**Typical Worker Flow:**
```
1. Poll puzzle_generation_jobs WHERE status='queued' every 5s
2. Try UPDATE to claim job (status: queued → processing)
3. If success, call generate_puzzle()
4. Run validation_pipeline()
5. seed_puzzle_to_pool() or mark rejected
6. Update job row (status: completed/failed)
7. Log cost to usage_tracker
```

**Pool Monitor:**
```
1. Every 30s, check pool stats
2. If approved < 30 (target), queue replenishment jobs
3. Maintains healthy puzzle supply for game sessions
```

## Generation Pipeline Details

### Worker Path (`puzzle_generator.py` + `group_generator.py`)

**Multi-Step Quality Path:**

1. **Diversity Seed** (temp=1.0)
   - 4 random domain seeds (history, nature, food, tech)
   - Creative story to prevent thematic repetition
   - Prompt caching: system + tool schema cached

2. **Category Brainstorm** (temp=0.9)
   - Generate 6-8 candidate themes
   - Score & select best 4 for groups

3. **Iterative Group Building** (delegates to `generate_single_group()`)
   - Per category: generate 4 words matching theme
   - With difficulty profile (easy/medium/hard/expert)
   - Prompt caching reuses system prompt

4. **Embedding Bridge Analysis** (free, no API call)
   - Run `embedding_validator` on draft puzzle
   - Identify "bridge words" (high similarity to other groups)
   - Flag for red herring refinement

5. **Red Herring Refinement** (temp=0.7)
   - Swap words to maximize misdirection
   - Prioritize replacing bridge words
   - Ensure categories remain distinct

6. **Final Assembly**
   - Package into puzzle dict
   - Seed to pool (draft)

**Cost:** ~$0.05/puzzle (with prompt caching ~90% discount on steps 2-5)

### Batch Path (`batch_generator.py`)

**Volume Path (Nightly Fills):**

1. Build N single-shot prompts (one per puzzle)
2. Submit via Anthropic Batch API (50% cost discount)
3. Poll for completion (overnight, ~30-60 min)
4. Validate all results
5. Seed approved to pool directly

**Cost:** ~$0.015/puzzle
**Quality:** Lower (single-shot, no iterative refinement)
**Use:** Restocking overnight, bulk fills

## Configuration & Deployment

### Environment Variables

**Flask:**
- `FLASK_ENV` — development/production
- `FLASK_DEBUG` — Enable debug mode
- `SECRET_KEY` — Flask session signing

**Supabase:**
- `SUPABASE_URL` — Database URL
- `SUPABASE_KEY` — Service role key (bypass RLS)

**Anthropic:**
- `ANTHROPIC_API_KEY` — Claude API key

**Worker:**
- `WORKER_POLL_INTERVAL` — Job poll frequency (default 5s)
- `POOL_MONITOR_INTERVAL` — Pool check frequency (default 30s)

### Docker

- `Dockerfile.api` — Lightweight API image (python:3.12-slim + requirements-api.txt)
- `Dockerfile.worker` — Full worker image (python:3.12-slim + requirements.txt + transformer model cache)

**requirements split:**
- `requirements-api.txt` — Flask, Supabase, auth (no ML stack)
- `requirements.txt` — Everything (includes torch, sentence-transformers, anthropic)

## Testing

**Test Suite:** `backend/tests/`

Run with:
```bash
cd backend
source .venv/bin/activate
pytest
```

**Coverage:**
- Game logic (guess validation, state transitions)
- API endpoints (request validation, response format)
- Data access layer (DB mocking)
- Generation pipeline (prompt assembly)
- Validation pipeline (scoring)

## Error Handling

**Game Errors:**
- `ValueError` — Invalid game_id, malformed guess
- `PlayerExhaustedPoolError` — Player completed all puzzles

**Generation Errors:**
- `RuntimeError` — Missing env vars (SUPABASE_URL, ANTHROPIC_API_KEY)
- `Exception` — API failures (logged, job marked failed)

**Pattern:** Fail fast with descriptive messages, logged at ERROR level

## Common Tasks

### Adding a Game Endpoint
1. Create route in `blueprints/api/routes.py`
2. Add helper function to `game_session_service.py`
3. Call via `get_game_from_db()` or `update_game_state()`
4. Return response via `create_response()`
5. Add tests in `tests/`

### Tweaking Generation Quality
1. Adjust temperatures in `puzzle_generator.py` (default: 1.0, 0.9, 0.7)
2. Adjust embedding thresholds in `embedding_validator.py`
3. Adjust LLM validation scores in `llm_validator.py`
4. Re-run worker to generate test puzzles

### Monitoring Costs
```python
from src.services.usage_tracker import get_cost_summary
summary = get_cost_summary(start_date="2026-03-01")
print(f"Total: ${summary['total_cost_usd']}")
```

## External Dependencies

- `flask@2.x` — Web framework
- `flask-cors@4.x` — CORS handling
- `supabase@2.x` — Database & auth client
- `python-dotenv` — .env loading
- `anthropic@0.28+` — Claude API
- `sentence-transformers@2.x` — Embeddings (worker only)
- `torch` — ML backend (worker only)
- `scikit-learn` — Metrics (worker only)

---

**See also:** [Frontend Codemap](frontend.md), [Generation Pipeline](generation.md), [Database Schema](database.md)
