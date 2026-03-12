# Connections Game - Development Guidelines

## Project Overview

This is a web-based Connections game inspired by the NY Times, where players identify connections between words in a grid.

**Tech Stack:**
- **Frontend:** React 18 + TypeScript + Vite + Supabase Auth
- **Backend:** Python 3.10+ + Flask + Supabase (PostgreSQL)
- **Puzzle Gen:** Claude (Anthropic API) + sentence-transformers (validation)
- **Architecture:** React frontend ↔ Flask REST API ↔ Supabase PostgreSQL

## Documentation

**Start with the architectural codemaps** in `docs/CODEMAPS/`:
- **[INDEX.md](docs/CODEMAPS/INDEX.md)** — Architecture overview, tech stack, key patterns
- **[Frontend.md](docs/CODEMAPS/frontend.md)** — Component hierarchy, state management, API integration
- **[Backend.md](docs/CODEMAPS/backend.md)** — Flask routes, services, game logic, workers
- **[Generation.md](docs/CODEMAPS/generation.md)** — Puzzle generation pipeline (two paths), validation, costs
- **[Database.md](docs/CODEMAPS/database.md)** — Schema, relationships, queries, migrations
- **[API.md](docs/CODEMAPS/api.md)** — 10 game + 4 admin endpoints with examples
- **[Auth.md](docs/CODEMAPS/auth.md)** — JWT, guest mode, RBAC patterns

Each codemap covers one area deeply and links to related codemaps. Read the INDEX first, then dive into specific areas as needed.

## Project Structure

```
/backend/       - Flask API server, game logic, worker processes
/frontend/      - React/TypeScript UI with Vite, Supabase auth
/docs/          - Architecture codemaps and deployment guides
  /CODEMAPS/    - Detailed architectural documentation (7 files)
```

## Development Workflow

### Running the Application

**Backend:**
```bash
cd backend
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m src.app
```

**Installing Python dependencies:**
Always use `uv` instead of plain `pip` — it resolves and installs packages dramatically faster:
```bash
pip install uv          # one-time setup
uv pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm run dev
```

### Before Making Changes

1. **Understand the scope** - Is this a frontend, backend, or full-stack change?
2. **Read existing code** - Find similar features/patterns before implementing
3. **Check both layers** - Changes may require updates to both frontend and backend
4. **Follow the existing patterns** - This codebase has established conventions

## Code Organization

### API Communication
- Backend exposes REST endpoints (typically at `localhost:5000`)
- Frontend makes API calls to backend
- Ensure API contracts match between frontend/backend

### State Management
- Frontend uses React state and Supabase for authentication
- Backend manages game state in SQLite database

### Authentication
- Supabase authentication is integrated
- Support for both authenticated and guest modes

## Common Tasks

### Adding a New Feature

1. Determine if it's frontend-only, backend-only, or requires both
2. Start with the backend API if data/logic changes are needed
3. Update frontend to consume new API endpoints
4. Test the full flow from UI to backend and back

### Modifying Game Logic

- Game logic lives in the backend (`/backend/src/`)
- Word generation uses LLM integration
- Database schema in `/backend/schemas/`

### UI Changes

- React components in `/frontend/src/components/`
- Styles using SCSS
- Bootstrap and react-bootstrap for UI components

## Testing

- Backend tests in `/backend/tests/`
- Run backend tests: `pytest` (from backend directory)
- Frontend testing: Follow existing patterns if tests exist

## Environment Variables

- Backend: `/backend/.env` (not tracked, see `.env.example`)
- Frontend: `/frontend/.env` (not tracked, see `.env.example` if exists)
- Never commit `.env` files with secrets

## Git Workflow

- Branch naming: Use descriptive names (e.g., `feature/add-user-stats`, `fix/grid-layout`)
- Commits: Descriptive messages following existing style
- Testing: Ensure both frontend and backend work together before committing

## Database Migrations

Migrations live in `backend/supabase/migrations/` as timestamped SQL files.
**After writing any new migration file, always apply it immediately:**

```bash
cd backend
supabase db push
```

`db push` tracks which migrations have been applied and only runs new ones — safe to run repeatedly. Never leave a migration file uncommitted or unapplied; an unapplied migration means the Python code and the live database are out of sync, causing 500 errors at runtime.

## Deployment

See [docs/deployment.md](docs/deployment.md) for the full guide. Summary:

- **Frontend** → Vercel (free static hosting; `vite build` → `dist/`)
- **Flask API** → Railway or Render using `backend/Dockerfile.api` (~$5–7/mo)
- **Worker** → GitHub Actions nightly cron using the batch generator path (free)
- **Database + Auth** → Supabase (already in use)

### Dependency split

The backend has two requirements files with different purposes:

| File | Used by | Notable exclusions |
|---|---|---|
| `backend/requirements-api.txt` | API container | `torch`, `nvidia-*`, `sentence-transformers`, `anthropic`, `scikit-learn` |
| `backend/requirements.txt` | Worker container | Nothing — full stack |

The Flask API never calls `embedding_validator`, `validation_pipeline`, or any generation
code — it only writes rows to the job queue. This keeps the API Docker image small (~200 MB).

### Docker images

```
backend/Dockerfile.api     — lightweight API image (python:3.12-slim + requirements-api.txt)
backend/Dockerfile.worker  — full worker image (python:3.12-slim + requirements.txt + baked model)
```

The worker image bakes `all-mpnet-base-v2` (~420 MB) into the image at build time via
`TRANSFORMERS_CACHE` + a `RUN python -c "SentenceTransformer('all-mpnet-base-v2')"` layer.

## Important Notes

- **Update the knowledge journal** refer to user-level CLAUDE.md for instructions
- **Do not bypass pre-commit hooks** with `--no-verify`
- **Keep frontend and backend in sync** when changing APIs
- **Test locally** before committing (run both servers)
- **Read CLAUDE.md files** in `/backend/` and `/frontend/` for layer-specific guidelines
