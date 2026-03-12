# Codemaps & Documentation Update — 2026-03-12

## Summary

Generated comprehensive architectural codemaps and updated all documentation to reflect the current state of the Connections codebase. All docs are now authoritative, up-to-date, and cross-referenced.

## Files Created

### Codemaps (`docs/CODEMAPS/`)

1. **INDEX.md** (5.1 KB)
   - Entry point with architecture overview
   - Tech stack table, environment setup, key files
   - Development guidelines and when to update codemaps

2. **frontend.md** (8.5 KB)
   - Component hierarchy and state management
   - Context API (AuthContext, SelectedWordsContext)
   - Game flow and API integration points
   - Admin features (PuzzleEditor, PuzzleReviewCard)

3. **backend.md** (14 KB)
   - Flask app factory and blueprint routes (api + admin)
   - Services layer (game logic, puzzle pool, validation, usage tracking)
   - Worker lifecycle and pool monitoring
   - Configuration, Docker, testing, common tasks

4. **generation.md** (16 KB)
   - Worker pipeline architecture (5-step quality path with prompt caching)
   - Batch generator (3x cheaper, for nightly fills)
   - Validation pipeline (embedding + LLM validators)
   - Cost tracking, worker polling, pool monitor
   - Detailed task examples

5. **database.md** (17 KB)
   - 8 core tables with full schemas (game_sessions, puzzles, puzzle_groups, puzzle_words, puzzle_generation_jobs, api_usage, puzzle_configs, user_puzzle_exclusions)
   - Relationships and cardinality
   - Query examples and patterns
   - Migrations workflow
   - Performance indexes and RLS policies

6. **api.md** (19 KB)
   - 10 game endpoints (generate-grid, submit-guess, game-status, restart-game, forfeit-game, record-completion-time, user/stats, user/history, claim-guest-data, get-game-data)
   - 4 admin endpoints (generate-puzzles, get-rejected-puzzles, start-review-game, approve-puzzle)
   - Every endpoint includes request/response examples with all fields documented
   - Error codes and edge cases

7. **auth.md** (16 KB)
   - Frontend auth (Supabase JWT, AuthContext, sign in/up/out)
   - Backend middleware (optional & required auth, JWT validation)
   - Authorization patterns (guest OK, authenticated required, admin-only)
   - Guest mode flow and guest → user transition
   - Social login setup, role-based access control, security considerations

### Documentation Updates

1. **README.md** — Added codemaps section linking to all 7 codemaps with brief descriptions
2. **CLAUDE.md** — Updated tech stack (PostgreSQL, not SQLite), added codemaps reference, improved project structure

### Knowledge Journal

1. **`~/.learning/entries/2026-03-12-documentation-as-architecture-reflection.md`** — Explains codemap design, cross-referencing strategy, generalized pattern for any project

## Codemaps at a Glance

| File | Focus | Size | Key Content |
|------|-------|------|---|
| INDEX | Overview | 5.1 KB | Architecture diagram, tech stack, links |
| Frontend | React | 8.5 KB | Components, hooks, state, API calls |
| Backend | Flask | 14 KB | Routes, services, workers, config |
| Generation | Pipeline | 16 KB | Quality & batch paths, validation, costs |
| Database | Schema | 17 KB | 8 tables, relationships, queries, RLS |
| API | Endpoints | 19 KB | 14 endpoints, examples, error codes |
| Auth | Security | 16 KB | JWT, guest mode, RBAC, flows |

**Total:** 95 KB of detailed, actionable documentation

## Cross-Reference Map

```
INDEX
├── Links to Frontend, Backend, Generation, Database, API, Auth
├── Tech stack → Dependencies listed in each codemap
└── Quick-start → All setup commands verified

Frontend
├── Uses AuthContext (see Auth)
├── Calls /connections/* endpoints (see API)
├── State stored in Supabase (see Database)
└── Admin features → See Backend (admin routes)

Backend
├── Implements endpoints from (see API)
├── Uses Database schema & queries (see Database)
├── Services layer explained fully
├── Generation pipeline workers (see Generation)
├── Auth middleware (see Auth)
└── Cost tracking uses api_usage table (see Database)

Generation
├── Stores puzzles in (see Database)
├── Seeds to pool via puzzle_pool_service
├── Calls Claude API, costs tracked
├── Validates with embedding_validator
└── Results stored in puzzles table (see Database)

Database
├── Supports all API endpoints (see API)
├── Used by Backend services
├── Migrations in supabase/migrations/
├── Queries shown in SQL examples
└── RLS policies linked from Auth

API
├── Implemented by Backend (see Backend)
├── Frontend integration points (see Frontend)
├── Auth requirements (see Auth)
└── Database schema for responses (see Database)

Auth
├── Frontend: AuthContext.tsx (see Frontend)
├── Backend: middleware.py (see Backend)
├── Guest data transferred via API endpoint (see API)
└── Storage: Supabase tables (see Database)
```

## Quality Checklist

- [x] All file paths verified to exist
- [x] Code examples extracted from actual source
- [x] Endpoints documented with working examples
- [x] Database schemas match Supabase structure
- [x] Cross-references tested (no broken links)
- [x] Timestamps included (2026-03-12)
- [x] ASCII diagrams for complex flows
- [x] Tables for quick reference
- [x] Common tasks documented with examples
- [x] Error codes and edge cases covered
- [x] README updated with links
- [x] Project CLAUDE.md updated with tech stack
- [x] Knowledge journal entry written

## How to Use These Docs

### For New Developers

1. **Start:** Read `docs/CODEMAPS/INDEX.md` (5 min overview)
2. **Understand your area:** Read relevant codemap (Frontend, Backend, etc.)
3. **Deep dive:** Follow cross-references as needed

### For Adding Features

1. **Game feature:** Backend → API → Database → Frontend codemaps
2. **Admin feature:** Backend (admin routes) → API (admin endpoints)
3. **Generation tweaks:** Generation → Database (api_usage) → Backend (cost tracking)
4. **Auth changes:** Auth → Backend (middleware) → Frontend (AuthContext)

### For Deployment

1. Read `docs/deployment.md` (not updated, but still current)
2. Review Backend codemap (Docker images, dependency split)
3. Check Database codemap (migrations must be applied)

### Staying Current

When you change something:
1. Update relevant codemap (timestamp it)
2. Update cross-references if schema/endpoints change
3. Check all linked codemaps still match reality

## Files Not Updated

- `docs/API.md` — Older API docs, made redundant by codemaps/api.md (keep for now, deprecate later)
- `docs/deployment.md` — Still current, no changes needed
- Other existing docs — Left as-is

## Next Steps

1. **Review & Feedback** — Codemaps are current as of 2026-03-12 but should be reviewed for accuracy
2. **Integration** — Link codemaps in CI/CD pipelines or development guidelines
3. **Maintenance** — Update codemaps when PRs change architecture/schema/endpoints
4. **Automation** — Consider generating API docs from OpenAPI spec (future enhancement)

---

**All codemaps are authoritative and generated from the actual codebase.**
**Start reading at: `docs/CODEMAPS/INDEX.md`**
