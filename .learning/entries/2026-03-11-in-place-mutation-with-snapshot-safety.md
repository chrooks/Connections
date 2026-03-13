---
date: 2026-03-11
patterns: [snapshot, in-place mutation, audit trail, batch-fetch join]
project: Connections
---

## Problem

Admin needs to edit puzzle content (words and category names) after a puzzle has
been generated and potentially served to players. The naive concern is: "won't
editing the source rows break existing game sessions?"

## Why In-Place Mutation Is Safe Here

Game sessions store their puzzle data as a **JSONB snapshot** at creation time:

```python
# game_session_service.py — when a new game starts
add_new_game(grid, connections, puzzle_id=puzzle_id)
# connections = [{"relationship": "...", "words": [...], "guessed": False}, ...]
# This dict is stored verbatim in game_sessions.connections (JSONB column)
```

This means `game_sessions.connections` is a complete copy of the puzzle data,
not a foreign-key reference to `puzzle_words`. Editing the source `puzzle_words`
rows later has zero effect on any existing session. The only consequence is a
mild audit inconsistency: the player's history shows the snapshot from when they
played, while the pool now shows the edited version.

## The Pattern: Audit Timestamp + Batch-Fetch Join

To surface this inconsistency transparently, we added an `edited_at` timestamp to
the `puzzles` table and computed `puzzle_modified_since_played` in the history
query. Instead of N+1 queries (one per history entry), we batch-fetch:

```python
def get_user_history(user_id):
    # Step 1: fetch all game sessions
    rows = supabase.table("game_sessions").select("id, puzzle_id, created_at, ...").execute()

    # Step 2: batch-fetch edited_at for all referenced puzzles in ONE query
    puzzle_ids = list({r["puzzle_id"] for r in rows if r.get("puzzle_id")})
    puzzles = supabase.table("puzzles").select("id, edited_at").in_("id", puzzle_ids).execute()
    edited_at_by_puzzle = {p["id"]: p["edited_at"] for p in puzzles.data}

    # Step 3: join in Python
    for row in rows:
        puzzle_edited_at = edited_at_by_puzzle.get(row["puzzle_id"])
        puzzle_modified = bool(puzzle_edited_at and puzzle_edited_at > row["created_at"])
```

This is the **batch-then-join** pattern: two queries total regardless of how many
history entries exist, rather than 1+N queries. It's the right trade-off when the
ORM/client doesn't support efficient joins natively (supabase-py uses PostgREST,
which has limited JOIN syntax).

## Strategy Pattern for Validation

The editor's validation rules are decoupled from the component via a config object:

```typescript
interface PuzzleEditorConfig { groupCount: number; wordsPerGroup: number; }
const CLASSIC_CONFIG = { groupCount: 4, wordsPerGroup: 4 };

function isPuzzleValid(groups: EditableGroup[], config: PuzzleEditorConfig): boolean
```

Instead of hardcoding "4 groups of 4 words", the editor is parameterized. Adding
a new puzzle shape (3×3, 5×4) only requires a new config constant — the component
and validation logic don't change. This is the **Strategy pattern**: behavior is
selected by swapping the config object, not by subclassing or branching.
