# Backend Development Guidelines

## Stack

- **Language:** Python 3.10+
- **Framework:** Flask
- **Database:** Supabase (PostgreSQL) — accessed via `supabase-py`
- **LLM:** Anthropic API (`anthropic` SDK) — Claude Opus 4.6 / Sonnet 4.6
- **Virtual Environment:** `.venv/`

## Project Structure

```
backend/
├── src/
│   ├── app.py                    # Flask app factory, blueprint registration
│   ├── blueprints/
│   │   ├── api/routes.py         # Game endpoints (/connections/...)
│   │   └── admin/routes.py       # Admin endpoints (/admin/...)
│   ├── game/game.py              # Core game logic (guesses, win/loss)
│   ├── dal/                      # Data access layer (Supabase queries)
│   ├── generation/
│   │   ├── group_generator.py    # Generates individual word groups (Claude)
│   │   ├── puzzle_generator.py   # Multi-step pipeline: seed → brainstorm → refine
│   │   └── batch_generator.py    # Batch API path: single-shot, 50% cheaper
│   ├── services/
│   │   ├── puzzle_pool_service.py  # Pool management: fetch, seed, approve
│   │   ├── usage_tracker.py        # Record Anthropic token usage + cost
│   │   ├── validation_pipeline.py  # Embedding + LLM validation of candidates
│   │   ├── embedding_validator.py  # Cosine similarity checks
│   │   ├── llm_validator.py        # Claude-based ambiguity/quality review
│   │   └── game_session_service.py # Game session CRUD
│   ├── workers/
│   │   ├── worker.py             # Background generation worker (polls job queue)
│   │   ├── pool_monitor.py       # Daemon that triggers refill when pool runs low
│   │   └── run_workers.py        # Entry point: starts worker + monitor threads
│   └── auth/middleware.py        # Supabase JWT validation
├── supabase/
│   └── migrations/               # SQL migration files (apply in order)
│       ├── 20260210000000_puzzle_pool.sql
│       ├── 20260224000000_game_sessions.sql
│       └── 20260309000000_api_usage.sql
├── tests/                        # pytest test suite
└── requirements.txt
```

## Development Setup

### 1. Activate the virtual environment

```bash
source .venv/bin/activate       # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

Always use `uv` — it's dramatically faster than plain pip:

```bash
pip install uv          # one-time setup
uv pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY
```

### 4. Apply database migrations

Run each SQL file against your Supabase project in chronological order:

```bash
# Via Supabase CLI:
supabase db push

# Or directly via psql:
psql "$DATABASE_URL" -f supabase/migrations/20260210000000_puzzle_pool.sql
psql "$DATABASE_URL" -f supabase/migrations/20260224000000_game_sessions.sql
psql "$DATABASE_URL" -f supabase/migrations/20260309000000_api_usage.sql
```

### 5. Start the Flask server

```bash
python -m src.app
```

Runs at `http://localhost:5000`.

## Running the Generation System

### Background worker (quality path)

The worker polls `puzzle_generation_jobs` and runs the multi-step generation pipeline:

```bash
python -m src.workers.run_workers
```

This starts two threads:
- **Worker thread** — claims and processes queued generation jobs
- **Pool monitor thread** — watches pool depth; triggers a fill when it drops below threshold

Both are daemon threads — they shut down automatically when you `Ctrl+C` the main process.

Trigger a generation run via the admin endpoint (worker must be running):

```bash
curl -X POST http://localhost:5000/admin/generate-puzzles \
  -H "Content-Type: application/json" \
  -d '{"count": 5, "config_name": "classic"}'
```

### Batch generator (volume/nightly path)

Skips the multi-step pipeline; uses the Anthropic Batch API (50% cost reduction).
Blocks until the batch completes (up to 1 hour):

```python
from backend.src.generation.batch_generator import run_batch_fill

result = run_batch_fill(count=20, config_name="classic")
# {"submitted": 20, "succeeded": 17, "failed": 3, "puzzle_ids": [...]}
```

Use this for nightly restocking — not for on-demand requests where quality matters.

### Comparing the two paths

| | Worker pipeline | Batch generator |
|---|---|---|
| Claude calls per puzzle | ~10–15 (multi-step) | 1 (single-shot) |
| Relative cost | ~$0.05 | ~$0.015 |
| Quality | High (iterative refinement) | Lower (no refinement) |
| Latency | Minutes (sequential) | 15–60 min (batch) |
| Use case | On-demand, admin trigger | Nightly bulk fill |

## Human Review of Rejected Puzzles

The validation pipeline is automated but not infallible. Three admin endpoints let you review, play, and override rejected puzzles:

```bash
# 1. List rejected puzzles — shows words, score, and fail reasons
curl "http://localhost:5000/admin/puzzles/rejected"

# 2. Start a playable game session from a rejected puzzle
curl -X POST http://localhost:5000/admin/puzzles/<puzzle_id>/start-review-game
# → returns game_id; play it through the normal frontend

# 3. Approve it if the validator was wrong
curl -X POST http://localhost:5000/admin/puzzles/<puzzle_id>/approve
```

The relevant service functions are in `puzzle_pool_service.py`:
- `get_rejected_puzzles(config_name, limit)` — query layer for the list endpoint
- `_fetch_puzzle_connections(puzzle_id)` — fetches groups+words for any puzzle status; used by both the review game and `validate_and_store()`
- `manually_approve_puzzle(puzzle_id)` — force-approves without re-running validation; preserves the original `validation_score` and `validation_report` for audit

## Cost Tracking

Every Anthropic API call should call `record_usage()` after the response:

```python
from ..services.usage_tracker import record_usage

response = client.messages.create(...)

record_usage(
    source="my_feature",        # label for this calling context
    model="claude-opus-4-6",
    response=response,
    puzzle_id="...",            # optional
    metadata={"step": "Step 1"},
)
```

Errors are swallowed — usage tracking must never block the generation pipeline.

Query aggregated costs:

```python
from ..services.usage_tracker import get_cost_summary

summary = get_cost_summary(start_date="2026-03-01", end_date="2026-03-09")
# {"total_cost_usd": 1.23, "total_input_tokens": 500000, "row_count": 42, ...}

# Filter by calling context:
summary = get_cost_summary("2026-03-01", "2026-03-09", source="batch_generator")
```

## Code Style

- **Follow PEP 8** — standard Python style
- **Type hints** — use where it improves clarity
- **Descriptive names** — explicit over clever
- **Comments** — explain *why*, not *what*
- **Files end with a newline**

## Flask Patterns

- Routes are grouped in blueprints under `src/blueprints/`
- All responses use consistent JSON: `{"status": "success", "data": {...}}` or `{"status": "error", "message": "..."}`
- Use appropriate HTTP status codes (200 / 201 / 400 / 404 / 500)

## Database

- **Supabase client** — use `_get_client()` helpers in each service module (lazy import avoids circular imports with the `supabase/` directory)
- **Migrations** — all schema changes go in `supabase/migrations/` as timestamped SQL files
- **No raw SQL strings in app code** — use the `supabase-py` fluent API for queries
- **Optimistic locking** — the job queue uses `UPDATE ... WHERE status='queued'` as a compare-and-swap to prevent multiple workers claiming the same job

## Testing

```bash
# From the backend directory
pytest
```

Tests cover game logic, the DAL, API endpoints, puzzle generation, and the pool service. Fix failing tests — never skip them.

## Security

- **Input validation** — always validate user input before processing
- **Parameterised queries** — the Supabase client handles this; don't build SQL strings manually
- **Environment variables** — secrets in `.env` only, never in code
- **JWT validation** — `auth/middleware.py` validates Supabase JWTs on protected routes
- **Error messages** — don't expose internal stack traces to API callers

## Adding New Dependencies

```bash
uv pip install <package>
uv pip freeze > requirements.txt
```

Document why the dependency is needed in the commit message.

## Important Reminders

- **Always use `uv`** for installing packages — not bare `pip`
- **Python 3.10+** is required (match/case syntax, newer type hints)
- **Never commit `.env`** — it contains production secrets
- **Run tests before committing** — `pytest` from the backend directory
- **Keep API contracts in sync** — frontend must match any endpoint changes
- **Usage tracking** — add `record_usage()` after every new Claude API call
