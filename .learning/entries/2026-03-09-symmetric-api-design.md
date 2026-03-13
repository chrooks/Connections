---
date: 2026-03-09
patterns: [API design, symmetric operations, silent omission bug]
project: Connections
---

# Symmetric Operations Need Symmetric Signatures

## Problem being solved

`approve_puzzle()` and `reject_puzzle()` are conceptually symmetric — both transition
a puzzle's status and record evidence about why. But `reject_puzzle()` was missing the
`validation_score` parameter that `approve_puzzle()` had. Rejected puzzles had `NULL`
in the `validation_score` column, making it impossible to compare scores across
approve/reject decisions.

This is a **silent omission bug** — no error is thrown, the code runs fine, the data
just quietly isn't there.

## Why asymmetry happens

The functions were probably written at different times, or `approve_puzzle()` was
written first (when score tracking was the focus) and `reject_puzzle()` was added
later as a simpler counterpart. The asymmetry crept in gradually.

## The fix

Add the missing parameter and write it to the DB. Using a default of `0.0` keeps
existing call sites working without changes:

```python
# Before — score silently dropped
def reject_puzzle(puzzle_id: str, validation_report: dict) -> None:
    supabase.table("puzzles").update({
        "status": "rejected",
        "validation_report": validation_report,
    }).eq("id", puzzle_id).execute()

# After — symmetric with approve_puzzle
def reject_puzzle(
    puzzle_id: str,
    validation_report: dict,
    validation_score: float = 0.0,   # added
) -> None:
    supabase.table("puzzles").update({
        "status": "rejected",
        "validation_score": validation_score,   # added
        "validation_report": validation_report,
    }).eq("id", puzzle_id).execute()
```

The call site in `validate_and_store()` becomes explicit:

```python
# Before
reject_puzzle(puzzle_id, report)

# After — mirrors how approve_puzzle is called
reject_puzzle(puzzle_id, report, report["score"])
```

## The principle

Whenever you have two functions that are the "success" and "failure" sides of the same
operation, audit them side by side. They should store the same set of evidence columns.
If one stores more than the other, ask whether that asymmetry is intentional. Usually
it isn't.
