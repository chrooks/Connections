# Connections Project — Codemap Index

**Last Updated:** 2026-03-12

This directory contains architectural codemaps for the Connections game project. Each map covers a major area of the system and documents the structure, key modules, data flow, and external dependencies.

## Overview

Connections is a web-based word puzzle game where players identify groups of four words that share a hidden connection. The system is split into a React/TypeScript frontend (Vite) and a Python Flask backend, with AI-powered puzzle generation and a Supabase cloud database.

### Core Architecture

```
Frontend (React/TS)          Backend (Flask)              Database (Supabase)
   ├── Game Grid        ──┬──  API Routes           ──────  game_sessions
   ├── Auth Modal       ──┤    ├── Game Logic           puzzle_*
   ├── Admin Panel      ──┤    ├── Puzzle Pool          api_usage
   └── Profile          ──┤    └── Admin Routes
                           │
                   Generation Pipeline (Workers)
                   ├── puzzle_generator (quality)
                   ├── batch_generator (volume)
                   └── Validation Pipeline
```

## Codemaps

1. **[Frontend Codemap](frontend.md)** — React/TypeScript UI components, state management, authentication, game interactions
2. **[Backend Codemap](backend.md)** — Flask API, game logic, services, database layer
3. **[Generation Pipeline](generation.md)** — Puzzle generation (worker & batch paths), validation, cost tracking
4. **[Database Schema](database.md)** — Supabase tables, migrations, relationships
5. **[API Reference](api.md)** — Game endpoints, admin endpoints, request/response formats
6. **[Authentication & Authorization](auth.md)** — Supabase JWT, guest mode, admin access control

## Key Design Patterns

### Puzzle Lifecycle

```
Draft (seed_to_pool)
  ↓ (validation_pipeline)
Rejected / Approved (via auto-validator)
  ↓ (human override possible)
Pool (approved_puzzles)
  ↓ (get_puzzle_from_pool)
Game Session
```

### Generation Paths

| Path | Use Case | Cost | Quality | Latency |
|------|----------|------|---------|---------|
| **Worker Pipeline** | On-demand, admin-triggered | ~$0.05/puzzle | High (iterative) | Minutes |
| **Batch Generator** | Nightly bulk fill | ~$0.015/puzzle | Lower (single-shot) | 15-60 min |

### Game State Flow

```
1. Player requests /generate-grid
2. API creates game_session (IN_PROGRESS)
3. Player submits guess → /submit-guess
4. Backend checks against connections
5. If correct: mark connection as guessed
6. If all 4 found: status = WIN
7. If mistakes exhausted: status = LOSS
8. Player can restart → new puzzle from pool
```

## Technology Stack

| Layer | Tech | Purpose |
|-------|------|---------|
| **Frontend** | React 18 + TypeScript + Vite | UI, game interaction |
| **Styling** | SCSS + Bootstrap 5 + react-bootstrap | Responsive design |
| **Auth** | Supabase Auth (JWT) | User sessions, guest mode |
| **Backend** | Python 3.10+ + Flask | REST API, game logic |
| **Database** | Supabase (PostgreSQL) | All persistent state |
| **Puzzle Gen** | Claude (Anthropic API) | AI puzzle generation |
| **Embeddings** | `sentence-transformers` | Validation similarity checks |

## Environment Setup

### Quick Start

**Backend:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt  # Use uv, not plain pip
cp .env.example .env
python -m src.app
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

**Worker (background generation):**
```bash
cd backend
source .venv/bin/activate
python -m src.workers.run_workers
```

## Key Files

### Frontend
- `/frontend/src/components/App/App.tsx` — Root component, view routing
- `/frontend/src/components/ConnectionsGame/ConnectionsGame.tsx` — Main game loop
- `/frontend/src/context/AuthContext.tsx` — Auth state provider
- `/frontend/src/context/SelectedWordsContext.tsx` — Game grid selection state

### Backend
- `/backend/src/app.py` — Flask app factory
- `/backend/src/blueprints/api/routes.py` — Game endpoints
- `/backend/src/blueprints/admin/routes.py` — Admin endpoints
- `/backend/src/game/game.py` — Core game logic
- `/backend/src/generation/puzzle_generator.py` — Multi-step generation
- `/backend/src/generation/batch_generator.py` — Batch API path
- `/backend/src/services/puzzle_pool_service.py` — Pool management

### Database
- `/backend/supabase/migrations/` — SQL migration files
- `/backend/src/dal/` — Data access layer (WIP)

## Development Guidelines

### When to Update Codemaps

- Major feature addition
- API endpoint changes
- Generation pipeline updates
- Database schema changes
- Architecture refactoring

### Cross-Referencing

All codemaps are interconnected. For example:
- Backend codemap links to database codemap for schema details
- API reference links to backend codemap for implementation
- Generation pipeline codemap shows cost tracking (in database codemap)

---

**For detailed information on each area, see the individual codemaps above.**
