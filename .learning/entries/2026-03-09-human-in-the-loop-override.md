---
date: 2026-03-09
patterns: [human-in-the-loop, override pattern, audit trail]
project: Connections
---

# Human-in-the-Loop Override Pattern

## Problem being solved

Automated validators make mistakes. An embedding + LLM pipeline that rejects puzzles
will sometimes incorrectly flag borderline-but-valid cases. If there's no way to
override the decision, every false rejection is a permanently wasted puzzle.

The question is: how do you let a human override an AI decision without throwing
away the evidence that led to that decision?

## Why this pattern fits

The key insight is that "approved" and "rejected" are not states you write once — they
are states you can revisit. The audit trail (score + report) is preserved regardless of
the final status, so a human override doesn't destroy information; it just changes the
outcome column while leaving the why intact.

## Shape of the implementation

Three endpoints form the review workflow:

```python
# 1. Browse — see what was rejected and why
GET /admin/puzzles/rejected
# Returns: puzzle words + validation_score + auto_fail_reasons

# 2. Experience — play the puzzle as a real game session
POST /admin/puzzles/<id>/start-review-game
# Creates a game_session row using the same add_new_game() path as normal play

# 3. Override — approve it if the validator was wrong
POST /admin/puzzles/<id>/approve
```

The approve endpoint calls `manually_approve_puzzle()`, which only changes `status`
and `approved_at` — it deliberately leaves `validation_score` and `validation_report`
untouched:

```python
def manually_approve_puzzle(puzzle_id: str) -> None:
    supabase.table("puzzles").update({
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        # validation_score and validation_report NOT cleared — preserved for audit
    }).eq("id", puzzle_id).execute()
```

## Why this structure works

- **Reuse the existing game path** — `start-review-game` calls the same `add_new_game()`
  and `_fetch_puzzle_connections()` as normal gameplay. There's no separate "preview" mode.
- **Audit by default** — because `validation_score` persists on manually-approved puzzles,
  you can later query: "how many puzzles were manually approved and what were their scores?"
  This tells you if the validator's threshold is calibrated correctly.
- **No re-validation needed** — the human *is* the validator in the override flow. Running
  the pipeline again would just give the same rejection.
