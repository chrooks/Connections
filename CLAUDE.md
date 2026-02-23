# Connections Game - Development Guidelines

## Project Overview

This is a web-based Connections game inspired by the NY Times, where players identify connections between words in a grid.

**Tech Stack:**
- **Frontend:** React + TypeScript + Vite + Supabase
- **Backend:** Python + Flask + SQLite
- **Architecture:** Separate frontend/backend with REST API communication

## Project Structure

```
/backend/       - Flask API server, game logic, database
/frontend/      - React/TypeScript UI with Vite
/docs/          - Project documentation
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

## Important Notes

- **Do not bypass pre-commit hooks** with `--no-verify`
- **Keep frontend and backend in sync** when changing APIs
- **Test locally** before committing (run both servers)
- **Read CLAUDE.md files** in `/backend/` and `/frontend/` for layer-specific guidelines
