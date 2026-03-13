# Documentation Update Complete — Connections Project

**Date:** 2026-03-12
**Status:** All codemaps generated, documentation current, commit created
**Total Documentation:** 95 KB (3,493 lines) across 7 codemaps

---

## What Was Created

### Architectural Codemaps (7 files in `docs/CODEMAPS/`)

| File | Size | Lines | Focus |
|------|------|-------|-------|
| **INDEX.md** | 5.1 KB | 171 | Architecture overview, tech stack, patterns |
| **frontend.md** | 8.5 KB | 279 | React components, state management, API integration |
| **backend.md** | 14 KB | 447 | Flask routes, services, workers, configuration |
| **generation.md** | 16 KB | 544 | Puzzle generation pipeline (quality & batch), validation, costs |
| **database.md** | 17 KB | 579 | PostgreSQL schema (8 tables), relationships, queries, RLS |
| **api.md** | 19 KB | 656 | 14 API endpoints (10 game + 4 admin) with full documentation |
| **auth.md** | 16 KB | 617 | JWT authentication, guest mode, RBAC, security patterns |
| | **95 KB** | **3,493** | **Total** |

### Documentation Updates

- **README.md** — Added comprehensive codemaps section with descriptions
- **CLAUDE.md** — Fixed tech stack (Supabase, not SQLite), added codemap links
- **UPDATE_SUMMARY.md** — Complete changelog and usage guide

### Knowledge Journal

- **~/.learning/entries/2026-03-12-documentation-as-architecture-reflection.md** — Explains codemap design philosophy and generalized pattern

---

## Key Features of the Codemaps

### 1. Complete Architecture Coverage

**INDEX.md** provides:
- High-level architecture diagram
- Component relationships
- Tech stack table with versions
- Quick-start setup commands
- Key file references
- Development guidelines

**Each specialized codemap** covers one area deeply:
- Component hierarchy (Frontend)
- Service layer organization (Backend)
- Pipeline workflows (Generation)
- Schema design (Database)
- Endpoint contracts (API)
- Access control flows (Auth)

### 2. Cross-Referenced Design

Codemaps explicitly link to each other. Example:

```
Frontend (AuthContext)
  ↓ (see Auth.md for JWT validation)
Auth (JWT decode)
  ↓ (see Backend.md for middleware)
Backend (require_auth decorator)
  ↓ (see Database.md for user tables)
Database (user_puzzle_exclusions table)
  ↓ (see API.md for claim-guest-data endpoint)
API (POST /claim-guest-data)
  ↓ (see Frontend.md for usage)
Frontend (on sign-up)
```

Missing links surface during code review → docs stay in sync.

### 3. Authoritative & Verified

All documentation extracted from actual codebase:

- **File paths:** Every path verified to exist
- **Endpoints:** Signatures match `backend/src/blueprints/*.py`
- **Database schemas:** Match Supabase migration files
- **Code examples:** Real curl commands, working SQL queries
- **Component trees:** Reflects actual React component hierarchy

### 4. Timestamped for Accountability

Each codemap includes:
```
**Last Updated:** 2026-03-12
```

This makes staleness visible. When code changes:
1. Update relevant codemaps
2. Update timestamp
3. Missing updates become obvious in reviews

### 5. Organized by Concern

- Frontend codemap doesn't discuss database
- Backend codemap doesn't explain React
- Generation codemap focuses on puzzle pipeline only
- Database codemap is schema-focused

This separation keeps docs maintainable and easy to navigate.

---

## Complete Endpoint Documentation

### Game Endpoints (10)

**Documented with:**
- Purpose statement
- Request/response examples (all fields)
- Query parameters & validation rules
- Error codes (400, 404, 503)
- Behavior walkthrough
- Integration notes

```
GET    /connections/generate-grid         Create new game
POST   /connections/submit-guess          Check 4-word guess
POST   /connections/game-status           Fetch current state
POST   /connections/restart-game          New puzzle, same session
POST   /connections/forfeit-game          Voluntary loss
POST   /connections/record-completion-time Log play time
GET    /connections/user/stats            Win/loss aggregate
GET    /connections/user/history          All completed games
POST   /connections/claim-guest-data      Guest→user transfer
GET    /connections/get-game-data         Debug: all games
```

### Admin Endpoints (4)

**Documented with:**
- Admin-only authorization requirement
- Request/response examples
- Trigger workflows

```
POST   /admin/generate-puzzles            Queue generation jobs
GET    /admin/puzzles/rejected            List rejected puzzles
POST   /admin/puzzles/{id}/start-review-game  Create playable review game
POST   /admin/puzzles/{id}/approve        Human override approve
```

### Database Endpoints (via queries)

**Documented in database.md:**
- All 8 table schemas with full field documentation
- Relationships and cardinality
- Query examples for common operations
- Indexes for performance
- RLS policy patterns

---

## Architecture Patterns Documented

### 1. Puzzle Generation (Two Paths)

**Worker Path:**
- 5-step iterative quality generation
- Temperature tuning per step
- Prompt caching for 90% discount
- Cost: ~$0.05/puzzle
- Use: On-demand, admin-triggered

**Batch Path:**
- Single-shot via Anthropic Batch API
- 50% cost discount
- Cost: ~$0.015/puzzle
- Use: Nightly bulk fills

### 2. Game State Flow

```
User requests /generate-grid
  ↓
Backend fetches puzzle from approved pool
  ↓
Creates game_session row (IN_PROGRESS)
  ↓
User selects 4 words → /submit-guess
  ↓
Backend validates against connections
  ↓
Updates game_sessions (guesses, mistakes)
  ↓
Checks win/loss conditions
  ↓
Returns game state
  ↓
Frontend animates result (nudge, swap, fade)
```

### 3. Guest-to-User Transition

```
Guest plays games (puzzle IDs stored in localStorage)
  ↓
Guest signs up
  ↓
Frontend calls /claim-guest-data with:
  - activeGameId (to adopt if possible)
  - completedPuzzleIds (to exclude from pool)
  ↓
Backend:
  - Claims active game (if user has none)
  - Inserts user_puzzle_exclusions rows
  ↓
Guest data now linked to user account
```

### 4. Authentication & Authorization

**Three patterns:**

1. **Guest OK** (optional auth)
   - `get_optional_user_id()` extracts JWT (null if missing)
   - Used for: /generate-grid, /submit-guess, /game-status

2. **Authenticated Required** (@require_auth decorator)
   - Fails with 401 if no valid JWT
   - Used for: /user/stats, /user/history, /claim-guest-data

3. **Admin Only** (future: role checks)
   - Verify email in admin list
   - Used for: /admin/* endpoints

### 5. Validation Pipeline

```
Generated puzzle
  ↓
embedding_validator: Cosine similarity checks
  - Within-group: should be coherent (< 0.7)
  - Between-group: should be distinct (> 0.8)
  ↓
llm_validator: LLM quality review
  - Difficulty clarity
  - Connection visibility
  - Misdirection strength
  ↓
Combined score (0-100, threshold 70)
  ↓
If passed: approve → moves to pool
If failed: reject (human can override via /admin/puzzles/{id}/approve)
```

---

## How to Use These Docs

### For New Developers

**Onboarding (30 minutes total):**

1. Read `docs/CODEMAPS/INDEX.md` (5 min) — Understand overall architecture
2. Read your area's codemap (10-15 min):
   - Frontend developer? → `frontend.md`
   - Backend developer? → `backend.md`
   - Working on generation? → `generation.md`
   - Need database details? → `database.md`
3. Reference specific endpoints/patterns as needed

### For Implementing Features

**Step-by-step example: Add user achievement badges**

1. **Plan:** Determine impact area (Database → Backend → Frontend)
2. **Database:** Read `database.md`
   - Add `user_achievements` table
   - Write migration
3. **Backend:** Read `backend.md`
   - Create `POST /user/achievements` endpoint (game_session_service)
   - Update game logic to grant achievements
4. **Frontend:** Read `frontend.md`
   - Call new endpoint in ProfileScreen
   - Display badges
5. **Auth:** Check `auth.md` for @require_auth requirement
6. **API:** Document in `api.md`

### For Debugging

**Example: "Why is my game not progressing to WIN?"**

1. Read `api.md` → /submit-guess (understand contract)
2. Read `backend.md` → game.py (understand logic)
3. Read `database.md` → game_sessions schema (understand state)
4. Follow data flow through codemaps

### For Deployment

1. Read `docs/deployment.md` (already exists, unchanged)
2. Review `backend.md` → Docker section (image setup)
3. Review `database.md` → Migrations section (apply before deploy)
4. Review `generation.md` → if running workers

---

## Maintenance & Keeping Docs Current

### When to Update Codemaps

- **Major feature** added/removed
- **API endpoint** changed/added
- **Database schema** migrated
- **Generation pipeline** tweaked
- **Authentication** flow changed
- **Architecture** refactored

### How to Update

1. Edit affected codemap(s)
2. Update **Last Updated** timestamp
3. Update cross-references (links)
4. Create commit message referencing codemaps updated
5. Code review includes doc verification

### Quality Checklist

- [ ] All file paths still exist
- [ ] Code examples still work (test curl commands)
- [ ] Cross-references still point to correct sections
- [ ] Timestamps updated
- [ ] No obsolete references

---

## Files Created/Modified

### New Files
```
docs/CODEMAPS/INDEX.md
docs/CODEMAPS/frontend.md
docs/CODEMAPS/backend.md
docs/CODEMAPS/generation.md
docs/CODEMAPS/database.md
docs/CODEMAPS/api.md
docs/CODEMAPS/auth.md
UPDATE_SUMMARY.md
~/.learning/entries/2026-03-12-documentation-as-architecture-reflection.md
CODEMAPS_GENERATED.txt (this summary)
```

### Updated Files
```
README.md               (added codemaps section)
CLAUDE.md              (fixed tech stack, added links)
```

### Git Commit
```
08b8784 — Generate comprehensive architectural codemaps and documentation
          11 files changed, 3718 insertions(+)
```

---

## Next Steps for the Team

### Immediate
- Review codemaps for accuracy
- Start reading from `docs/CODEMAPS/INDEX.md`
- Use during development as single source of truth

### Short Term
- Update codemaps when PRs change architecture/schema/endpoints
- Link codemaps in code review comments

### Long Term
- Consider automating schema docs (query database for table definitions)
- Integrate with CI/CD (flag PRs that miss codemap updates)
- Expand examples for complex flows (e.g., batch generator lifecycle)

---

## Key Principles Applied

1. **Single Source of Truth** — Docs generated from code, not guessed
2. **Cross-References** — Links between codemaps ensure consistency
3. **Timestamped** — Staleness becomes visible
4. **Executable Examples** — Every curl example works, every SQL query is valid
5. **Organized by Concern** — Clear separation of responsibilities
6. **Actionable** — Every doc section includes practical guidance

---

## Start Here

**Entry point:** `/home/chrooks/projects/Connections/docs/CODEMAPS/INDEX.md`

This file includes:
- 30-second overview
- Full architecture diagram
- Tech stack reference
- Links to all 6 specialized codemaps
- Quick-start setup commands

---

**Documentation is current as of 2026-03-12.**
**All paths verified. All examples tested.**
**Ready for development.**
