# API Reference Codemap

**Last Updated:** 2026-03-12
**Base URL:** `http://localhost:5000` (or production domain)
**Authentication:** Supabase JWT (Bearer token in Authorization header)

## Overview

The Connections API is organized into two main suites:

1. **Game Endpoints** (`/connections/*`) — Public, gameplay mechanics
2. **Admin Endpoints** (`/admin/*`) — Restricted, puzzle management

All responses follow a standard envelope format with optional error handling.

## Response Format

**Success (200 OK):**
```json
{
  "data": { /* response payload */ }
}
```

**Error (4xx/5xx):**
```json
{
  "error": "Human-readable error message",
  "code": "OPTIONAL_ERROR_CODE"
}
```

## Game Endpoints

### 1. Generate Grid

**Create a new game session with a random puzzle**

```
GET /connections/generate-grid
```

**Query Parameters:**
- `exclude` (optional) — Comma-separated puzzle IDs to exclude (guest mode only)

**Authentication:** Optional (guest OK)

**Request:**
```bash
curl http://localhost:5000/connections/generate-grid
# OR with guest exclusions:
curl "http://localhost:5000/connections/generate-grid?exclude=uuid-1,uuid-2"
```

**Response `201 Created`:**
```json
{
  "data": {
    "gameId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response `503 Service Unavailable`:**
```json
{
  "error": "You've completed all available puzzles! Check back soon for more.",
  "code": "POOL_EXHAUSTED"
}
```

**Behavior:**
- If authenticated: uses user_id to fetch exclusions from DB
- If guest: uses exclude query param (frontend tracks locally)
- Fetches approved puzzle from pool via `puzzle_pool_service.get_puzzle_from_pool()`
- On pool empty: fallback to fallback generation job (if exists)
- Creates game_sessions row (IN_PROGRESS)
- Returns gameId only (frontend calls /game-status next)

---

### 2. Game Status

**Fetch current game state (grid, guesses, connections)**

```
POST /connections/game-status
```

**Authentication:** Not required

**Request Body:**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Request Example:**
```bash
curl -X POST http://localhost:5000/connections/game-status \
  -H "Content-Type: application/json" \
  -d '{"gameId": "550e8400-e29b-41d4-a716-446655440000"}'
```

**Response `200 OK`:**
```json
{
  "data": {
    "gameId": "550e8400-e29b-41d4-a716-446655440000",
    "grid": ["WORD1", "WORD2", ..., "WORD16"],
    "guesses": [
      ["WORD1", "WORD2", "WORD3", "WORD4"],
      ["WORD5", "WORD6", "WORD7", "WORD8"]
    ],
    "mistakesLeft": 2,
    "status": "IN_PROGRESS",
    "connections": [
      {
        "words": ["WORD1", "WORD2", "WORD3", "WORD4"],
        "category": "Things that are red",
        "guessed": true
      },
      {
        "words": ["WORD5", "WORD6", "WORD7", "WORD8"],
        "category": "Words ending in -tion",
        "guessed": false
      },
      /* ... more groups ... */
    ]
  }
}
```

**Response `404 Not Found`:**
```json
{
  "error": "Invalid game ID."
}
```

**Fields:**
- `gameId` — UUID of game
- `grid` — Shuffled 16-word array
- `guesses` — Array of past guesses (each is 4-word array)
- `mistakesLeft` — 0-4 remaining
- `status` — IN_PROGRESS, WIN, or LOSS
- `connections` — Array of 4 category objects with words, category name, and guessed status

---

### 3. Submit Guess

**Validate a 4-word guess against the game's connections**

```
POST /connections/submit-guess
```

**Authentication:** Not required

**Request Body:**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000",
  "guess": ["WORD1", "WORD2", "WORD3", "WORD4"]
}
```

**Validation Rules:**
- `guess` must be exactly 4 words
- All words must exist in current grid
- No duplicate words within guess
- Game must be IN_PROGRESS

**Request Example:**
```bash
curl -X POST http://localhost:5000/connections/submit-guess \
  -H "Content-Type: application/json" \
  -d '{
    "gameId": "550e8400-e29b-41d4-a716-446655440000",
    "guess": ["WORD1", "WORD2", "WORD3", "WORD4"]
  }'
```

**Response `200 OK` (Correct Guess):**
```json
{
  "data": {
    "gameState": {
      "mistakesLeft": 2,
      "status": "IN_PROGRESS",
      "guessedConnections": [true, false, false, false]
    },
    "isCorrect": true,
    "isNewGuess": true,
    "isOneAway": false
  }
}
```

**Response `200 OK` (Incorrect Guess):**
```json
{
  "data": {
    "gameState": {
      "mistakesLeft": 1,
      "status": "IN_PROGRESS",
      "guessedConnections": [false, false, false, false]
    },
    "isCorrect": false,
    "isNewGuess": true,
    "isOneAway": false
  }
}
```

**Response `400 Bad Request`:**
```json
{
  "error": "Invalid guess format. A guess should be a list of four words."
}
```

**Fields:**
- `isCorrect` — Boolean, true if guess matches a category
- `isNewGuess` — Boolean, true if this exact guess wasn't made before
- `isOneAway` — Boolean, true if 3 of 4 words are in same category (hint for UI)
- `gameState` — Updated game state after guess processing
  - `mistakesLeft` — Decremented if incorrect, unchanged if correct
  - `status` — Updated to WIN if all groups found, LOSS if mistakes exhausted
  - `guessedConnections` — Boolean array indicating which groups have been found

**Behavior:**
1. Validates gameId and guess format
2. Checks words are in grid (returns 400 if not)
3. Checks for duplicate words (returns 400 if found)
4. Checks against connections (category matching)
5. If match: marks connection guessed, checks for win
6. If no match: decrements mistakesLeft, checks for loss
7. Detects duplicate guesses (known guess = doesn't cost mistake, isNewGuess=false)
8. Detects near misses (3 of 4 words match a category, isOneAway=true for UI nudge)
9. Updates game_sessions row in DB
10. Returns updated game state

---

### 4. Restart Game

**Reset current game with a new puzzle (new grid, same session)**

```
POST /connections/restart-game
```

**Authentication:** Optional (guest OK)

**Request Body:**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Request Example:**
```bash
curl -X POST http://localhost:5000/connections/restart-game \
  -H "Content-Type: application/json" \
  -d '{"gameId": "550e8400-e29b-41d4-a716-446655440000"}'
```

**Response `200 OK`:**
```json
{
  "data": {
    "gameId": "550e8400-e29b-41d4-a716-446655440000",
    "grid": ["WORD1", "WORD2", ..., "WORD16"],
    "guesses": [],
    "mistakesLeft": 4,
    "status": "IN_PROGRESS",
    "connections": [ /* new puzzle groups */ ]
  }
}
```

**Response `503 Service Unavailable`:**
```json
{
  "error": "You've completed all available puzzles! Check back soon for more.",
  "code": "POOL_EXHAUSTED"
}
```

**Behavior:**
1. Fetches next puzzle from pool (respects user exclusions)
2. Resets guesses to [], mistakes to 4, status to IN_PROGRESS
3. Updates game_sessions row (new puzzle_id)
4. Returns full game state (like /game-status)

---

### 5. Forfeit Game

**Voluntarily end an in-progress game as a loss**

```
POST /connections/forfeit-game
```

**Authentication:** Not required

**Request Body:**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Request Example:**
```bash
curl -X POST http://localhost:5000/connections/forfeit-game \
  -H "Content-Type: application/json" \
  -d '{"gameId": "550e8400-e29b-41d4-a716-446655440000"}'
```

**Response `200 OK`:**
```json
{
  "data": {
    "forfeited": true
  }
}
```

**Response `409 Conflict`:**
```json
{
  "error": "Game cannot be forfeited (not IN_PROGRESS)."
}
```

**Behavior:**
1. Checks game status is IN_PROGRESS (else 409)
2. Sets status to LOSS and forfeited to true
3. Updates game_sessions row
4. Returns success

---

### 6. Record Completion Time

**Log elapsed play time after game ends (called by frontend)**

```
POST /connections/record-completion-time
```

**Authentication:** Not required

**Request Body:**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000",
  "timeSeconds": 120
}
```

**Validation:**
- `timeSeconds` must be non-negative integer

**Request Example:**
```bash
curl -X POST http://localhost:5000/connections/record-completion-time \
  -H "Content-Type: application/json" \
  -d '{
    "gameId": "550e8400-e29b-41d4-a716-446655440000",
    "timeSeconds": 120
  }'
```

**Response `200 OK`:**
```json
{
  "data": {
    "recorded": true
  }
}
```

**Behavior:**
1. Validates timeSeconds is non-negative integer
2. Updates game_sessions.completion_time_seconds
3. Returns success

**Note:** Frontend calls this immediately after game ends (WIN/LOSS), before showing results modal

---

### 7. User Stats (Authenticated)

**Get aggregate stats for the authenticated user**

```
GET /connections/user/stats
```

**Authentication:** Required (JWT in Authorization header)

**Request:**
```bash
curl http://localhost:5000/connections/user/stats \
  -H "Authorization: Bearer <jwt_token>"
```

**Response `200 OK`:**
```json
{
  "data": {
    "wins": 42,
    "losses": 5,
    "forfeits": 2,
    "avgCompletionTime": 145.3,
    "totalGamesPlayed": 49
  }
}
```

**Fields:**
- `wins` — Number of WIN games
- `losses` — Number of LOSS games
- `forfeits` — Number of forfeited games (subset of losses)
- `avgCompletionTime` — Average completion_time_seconds for wins only
- `totalGamesPlayed` — wins + losses

---

### 8. User History (Authenticated)

**Get all completed games for the authenticated user**

```
GET /connections/user/history
```

**Authentication:** Required (JWT in Authorization header)

**Request:**
```bash
curl http://localhost:5000/connections/user/history \
  -H "Authorization: Bearer <jwt_token>"
```

**Response `200 OK`:**
```json
{
  "data": {
    "history": [
      {
        "gameId": "uuid-1",
        "puzzleId": "uuid-puzzle-1",
        "outcome": "WIN",
        "completionTime": 120,
        "createdAt": "2026-03-12T10:30:00Z",
        "difficulty": "medium"
      },
      {
        "gameId": "uuid-2",
        "puzzleId": "uuid-puzzle-2",
        "outcome": "LOSS",
        "completionTime": null,
        "createdAt": "2026-03-12T09:15:00Z",
        "difficulty": "hard"
      },
      {
        "gameId": "uuid-3",
        "puzzleId": "uuid-puzzle-3",
        "outcome": "FORFEIT",
        "completionTime": null,
        "createdAt": "2026-03-12T08:00:00Z",
        "difficulty": "easy"
      }
    ]
  }
}
```

**Fields (per game):**
- `gameId` — UUID of game session
- `puzzleId` — UUID of puzzle used
- `outcome` — WIN, LOSS, or FORFEIT
- `completionTime` — Seconds played (NULL if not completed)
- `createdAt` — Game start timestamp
- `difficulty` — Puzzle difficulty estimate

**Ordering:** Newest first (DESC by created_at)

---

### 9. Claim Guest Data (Authenticated)

**Transfer guest game/puzzle data to authenticated user after sign-up**

```
POST /connections/claim-guest-data
```

**Authentication:** Required (JWT in Authorization header)

**Request Body:**
```json
{
  "activeGameId": "550e8400-e29b-41d4-a716-446655440000",
  "completedPuzzleIds": [
    "puzzle-uuid-1",
    "puzzle-uuid-2"
  ]
}
```

**Fields:**
- `activeGameId` (string | null) — Current guest game, will be assigned to user
- `completedPuzzleIds` (string[]) — Puzzles already played as guest

**Request Example:**
```bash
curl -X POST http://localhost:5000/connections/claim-guest-data \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "activeGameId": "550e8400-e29b-41d4-a716-446655440000",
    "completedPuzzleIds": ["puzzle-1", "puzzle-2"]
  }'
```

**Response `200 OK`:**
```json
{
  "data": {
    "claimedActiveGame": true,
    "excludedPuzzleCount": 2,
    "message": "Guest data transferred successfully"
  }
}
```

**Response `400 Bad Request`:**
```json
{
  "error": "completedPuzzleIds must be a list of strings"
}
```

**Behavior:**
1. If activeGameId provided: UPDATE game_sessions.user_id = auth user (only if user has no other IN_PROGRESS game)
2. For each puzzleId in completedPuzzleIds: INSERT into user_puzzle_exclusions
3. Returns summary

**Frontend Usage:**
```javascript
// After successful sign-in
const activeGameId = localStorage.getItem("guestGameId");
const completedPuzzles = localStorage.getItem("completedPuzzles");

await fetch("/connections/claim-guest-data", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${jwtToken}`
  },
  body: JSON.stringify({
    activeGameId: activeGameId || null,
    completedPuzzleIds: completedPuzzles || []
  })
});

// Clear local storage
localStorage.removeItem("guestGameId");
localStorage.removeItem("completedPuzzles");
```

---

### 10. Get All Games (Debug)

**Retrieve all games in the database (debugging/analytics)**

```
GET /connections/get-game-data
```

**Authentication:** Not required (but should be admin-only in production)

**Request:**
```bash
curl http://localhost:5000/connections/get-game-data
```

**Response `200 OK`:**
```json
{
  "data": {
    "games": [
      {
        "gameId": "uuid-1",
        "userId": "user-uuid",
        "puzzleId": "puzzle-uuid",
        "status": "WIN",
        "mistakesLeft": 2,
        "createdAt": "2026-03-12T10:30:00Z"
      },
      /* ... more games ... */
    ]
  }
}
```

**Note:** This endpoint is for debugging/analytics. In production, restrict to admins or remove.

---

## Admin Endpoints

All admin endpoints require authentication and admin role verification.

**Authentication:** Required (JWT in Authorization header)

**Admin Check:** Backend verifies user_id against admin email list (configured in `.env`)

---

### 1. Generate Puzzles (Queue Jobs)

**Enqueue N puzzle generation jobs**

```
POST /admin/generate-puzzles
```

**Request Body:**
```json
{
  "count": 5,
  "config_name": "classic"
}
```

**Request Example:**
```bash
curl -X POST http://localhost:5000/admin/generate-puzzles \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{"count": 5, "config_name": "classic"}'
```

**Response `201 Created`:**
```json
{
  "data": {
    "jobsQueued": 5,
    "configName": "classic",
    "message": "5 puzzles queued for generation"
  }
}
```

**Behavior:**
1. Validates config_name exists in puzzle_configs
2. Inserts N rows into puzzle_generation_jobs (status=queued)
3. Returns immediately (async)
4. Worker process will poll and claim jobs

**Note:** Worker must be running for jobs to be processed. See `/backend/src/workers/run_workers.py`

---

### 2. Get Rejected Puzzles

**List puzzles that failed validation (for human review)**

```
GET /admin/puzzles/rejected
```

**Query Parameters:**
- `limit` (optional, default 10) — Max results
- `offset` (optional, default 0) — Pagination offset

**Request:**
```bash
curl "http://localhost:5000/admin/puzzles/rejected?limit=20&offset=0" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response `200 OK`:**
```json
{
  "data": {
    "puzzles": [
      {
        "id": "puzzle-uuid-1",
        "validationScore": 65.5,
        "validationReport": {
          "embeddingScore": 72,
          "llmScore": 58,
          "issues": [
            "Excessive similarity between WORD1 and WORD5",
            "Connection clarity below threshold"
          ]
        },
        "groups": [
          {
            "category": "Things that are sweet",
            "words": ["CANDY", "HONEY", "SUGAR", "DESSERT"],
            "difficulty": "easy"
          },
          /* ... more groups ... */
        ],
        "createdAt": "2026-03-12T10:30:00Z"
      },
      /* ... more puzzles ... */
    ],
    "total": 42
  }
}
```

**Fields:**
- `validationScore` — 0-100, below threshold (70)
- `validationReport` — Details of why rejected
- `groups` — Full category structure with words
- `total` — Total rejected puzzles (for pagination)

---

### 3. Start Review Game

**Create a playable game session from a rejected puzzle (for manual testing)**

```
POST /admin/puzzles/{id}/start-review-game
```

**Path Parameters:**
- `id` — Puzzle UUID

**Request:**
```bash
curl -X POST http://localhost:5000/admin/puzzles/puzzle-uuid-1/start-review-game \
  -H "Authorization: Bearer <jwt_token>"
```

**Response `201 Created`:**
```json
{
  "data": {
    "gameId": "game-uuid-for-review",
    "puzzleId": "puzzle-uuid-1",
    "message": "Review game created. Go to /connections/game-status to fetch state."
  }
}
```

**Behavior:**
1. Creates new game_sessions row with rejected puzzle_id
2. Sets status to IN_PROGRESS (as if starting normal game)
3. Returns gameId
4. Admin then plays via normal game endpoints (/game-status, /submit-guess, etc.)

**Frontend Flow:**
```javascript
// Admin clicks "Play Test" on rejected puzzle card
const gameId = await startReviewGame(puzzleId);
// Navigate to game screen with reviewGameId = gameId
// After finish, show "Approve" or "Reject" buttons
```

---

### 4. Approve Puzzle

**Human override: mark a rejected puzzle as approved**

```
POST /admin/puzzles/{id}/approve
```

**Path Parameters:**
- `id` — Puzzle UUID

**Request:**
```bash
curl -X POST http://localhost:5000/admin/puzzles/puzzle-uuid-1/approve \
  -H "Authorization: Bearer <jwt_token>"
```

**Response `200 OK`:**
```json
{
  "data": {
    "puzzleId": "puzzle-uuid-1",
    "status": "approved",
    "validationScore": 65.5,
    "message": "Puzzle approved and moved to pool"
  }
}
```

**Behavior:**
1. Updates puzzles.status = approved
2. Puzzle becomes available for get_puzzle_from_pool()
3. Original validation_score and report preserved in DB (audit trail)

**Note:** Use sparingly—indicates validator threshold may need tuning

---

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `POOL_EXHAUSTED` | 503 | Player completed all puzzles |
| (none) | 400 | Bad request (validation error) |
| (none) | 404 | Game not found |
| (none) | 500 | Server error (logged) |

---

## Authentication

**Supabase JWT Bearer Token:**
```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Middleware:** Defined in `backend/src/auth/middleware.py`

- `get_optional_user_id()` — Extract user_id from token (None if not present)
- `require_auth` — Decorator to enforce authentication

**Guest Access:**
- No token required for game endpoints
- Pool treats as new player
- Tracks completed puzzles via `exclude` query param

---

## Rate Limiting

**Not currently implemented.** Consider adding in production:
- Per-user: 10 guesses/minute
- Per-IP: 100 requests/minute
- Admin endpoints: 10 requests/minute

---

## Webhooks (Future)

Future enhancement: Supabase database webhooks for:
- Puzzle generation completion
- Player milestone achievements
- Pool health alerts

---

**See also:** [Backend Codemap](backend.md), [Database Schema](database.md), [Frontend Codemap](frontend.md)
