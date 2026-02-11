# Connections Game — Backend API Reference

## Base URL

```
http://localhost:5000
```

All game endpoints are prefixed with `/connections`.

---

## Summary

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Health check |
| `/connections/generate-grid` | GET | Create a new game |
| `/connections/submit-guess` | POST | Submit a player guess |
| `/connections/game-status` | POST | Get the current state of a game |
| `/connections/restart-game` | POST | Reset a game with a new grid |
| `/connections/get-game-data` | GET | Retrieve all games (debug/admin) |

---

## Endpoints

### Health Check

**`GET /`**

Verifies the API server is running.

**Response `200 OK`**
```json
{
  "data": {
    "message": "Welcome to the Connections game API!"
  }
}
```

---

### Generate Grid

**`GET /connections/generate-grid`**

Creates a new game session. Reads word groups from the connections schema, shuffles the 16-word grid, assigns a UUID and sequential puzzle number, and stores the game in the database with 4 mistakes allowed and `IN_PROGRESS` status.

**Response `201 Created`**
```json
{
  "data": {
    "gameId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response `500 Internal Server Error`**
```json
{
  "error": "Internal Server Error"
}
```

---

### Submit Guess

**`POST /connections/submit-guess`**

Validates and processes a player's 4-word guess against the game's connections. If the guess is correct, the matching connection is marked as guessed. If incorrect, `mistakesLeft` is decremented. When all 4 connections are found the status becomes `WIN`; when `mistakesLeft` reaches 0 the status becomes `LOSS`.

Duplicate guesses are tracked but do not consume an additional mistake.

**Request Body**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000",
  "guess": ["word1", "word2", "word3", "word4"]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `gameId` | string | Yes | UUID of an existing game |
| `guess` | string[] | Yes | Exactly 4 words from the current grid |

**Validation Rules**
- `guess` must be a list of exactly 4 words
- All 4 words must be present in the game grid
- No duplicate words within a single guess
- Game must have status `IN_PROGRESS`

**Response `200 OK`**
```json
{
  "data": {
    "gameState": {
      "mistakesLeft": 3,
      "status": "IN_PROGRESS",
      "guessedConnections": [true, false, false, false]
    },
    "isCorrect": true,
    "isNewGuess": true
  }
}
```

| Field | Type | Description |
|---|---|---|
| `gameState.mistakesLeft` | number | Remaining incorrect guesses (0–4) |
| `gameState.status` | string | `IN_PROGRESS`, `WIN`, or `LOSS` |
| `gameState.guessedConnections` | boolean[] | Which of the 4 connections have been found |
| `isCorrect` | boolean | Whether this guess matched a connection |
| `isNewGuess` | boolean | Whether this exact guess has been submitted before |

**Error Responses**

| Status | Condition |
|---|---|
| `400 Bad Request` | Missing/invalid fields, wrong number of words, words not in grid, game not `IN_PROGRESS` |
| `404 Not Found` | `gameId` does not exist |

---

### Game Status

**`POST /connections/game-status`**

Returns the full current state of a game without modifying it. Used to restore UI state on page load or after a reconnect.

**Request Body**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response `200 OK`**
```json
{
  "data": {
    "gameId": "550e8400-e29b-41d4-a716-446655440000",
    "grid": ["word1", "word2", "word3", "...16 total"],
    "connections": [
      {
        "relationship": "Category Name",
        "words": ["word1", "word2", "word3", "word4"],
        "guessed": true
      },
      {
        "relationship": "Another Category",
        "words": ["word5", "word6", "word7", "word8"],
        "guessed": false
      }
    ],
    "mistakesLeft": 3,
    "status": "IN_PROGRESS",
    "previousGuesses": [
      ["word1", "word2", "word3", "word4"]
    ],
    "puzzleNumber": 42
  }
}
```

| Field | Type | Description |
|---|---|---|
| `gameId` | string | Unique game identifier |
| `grid` | string[] | All 16 words in current shuffled order |
| `connections` | object[] | The 4 connection groups with their words and guessed status |
| `mistakesLeft` | number | Remaining incorrect guesses (0–4) |
| `status` | string | `IN_PROGRESS`, `WIN`, or `LOSS` |
| `previousGuesses` | string[][] | Every guess submitted so far |
| `puzzleNumber` | number | Sequential puzzle number (used for share results) |

**Error Responses**

| Status | Condition |
|---|---|
| `400 Bad Request` | Missing `gameId` field |
| `404 Not Found` | `gameId` does not exist |

---

### Restart Game

**`POST /connections/restart-game`**

Resets an existing game by generating a completely new grid and connections while keeping the same `gameId`. Resets `mistakesLeft` to 4, clears `previousGuesses`, and sets status back to `IN_PROGRESS`.

**Request Body**
```json
{
  "gameId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response `200 OK`**

Returns the full game state object in the same shape as [Game Status](#game-status), with a fresh grid and reset progress.

```json
{
  "data": {
    "gameId": "550e8400-e29b-41d4-a716-446655440000",
    "grid": ["new_word1", "new_word2", "...16 total"],
    "connections": [
      {
        "relationship": "Category Name",
        "words": ["new_word1", "new_word2", "new_word3", "new_word4"],
        "guessed": false
      }
    ],
    "mistakesLeft": 4,
    "status": "IN_PROGRESS",
    "previousGuesses": [],
    "puzzleNumber": 43
  }
}
```

**Error Responses**

| Status | Condition |
|---|---|
| `400 Bad Request` | Missing `gameId` field |
| `404 Not Found` | `gameId` does not exist |

---

### Get All Games

**`GET /connections/get-game-data`**

Returns the full state of every game in the database, keyed by `gameId`. Intended for debugging and admin use.

**Response `200 OK`**
```json
{
  "data": {
    "games": {
      "550e8400-e29b-41d4-a716-446655440000": {
        "gameId": "550e8400-e29b-41d4-a716-446655440000",
        "grid": ["word1", "..."],
        "connections": ["..."],
        "mistakesLeft": 2,
        "status": "IN_PROGRESS",
        "previousGuesses": ["..."],
        "puzzleNumber": 42
      }
    }
  }
}
```

Returns an empty `games` object `{}` if no games exist.

---

## Error Handling

All unhandled errors return one of the following:

**`404 Not Found`** — Route does not exist
```json
{ "error": "Not Found" }
```

**`500 Internal Server Error`** — Unhandled server exception
```json
{ "error": "Internal Server Error" }
```

---

## Game Logic Notes

- **Grid:** 16 words drawn from 4 connection groups of 4 words each; shuffled on every `generate-grid` and `restart-game` call.
- **Guessing:** A correct guess marks that connection as found. An incorrect guess decrements `mistakesLeft`.
- **Win condition:** All 4 connections guessed → status `WIN`.
- **Loss condition:** `mistakesLeft` reaches 0 → status `LOSS`.
- **Duplicate guesses:** Recorded in `previousGuesses` but do not cost a mistake.
- **Persistence:** Game state is stored in SQLite via SQLAlchemy. All changes are committed immediately.
