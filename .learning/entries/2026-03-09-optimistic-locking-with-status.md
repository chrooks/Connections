---
date: 2026-03-09
patterns: [optimistic-locking, compare-and-swap, job-queue]
project: Connections
---

# Optimistic Locking with Status Columns

## Problem being solved

If two workers start at the same time and both see the same `queued` job row, they'd both
try to process it — duplicating ~20 API calls and producing two puzzles for one job slot.
You need a way to let only one worker "win" the race without a distributed lock.

## Why optimistic locking fits

**Optimistic locking** assumes contention is rare. Instead of pre-emptively locking a row,
you read it freely, then attempt an update that will only succeed if the row is still in
the state you expect. If another worker already changed it, your update matches nothing
and you know you lost the race.

```python
def _claim_job(self) -> Optional[dict]:
    # Step 1: find the oldest queued job (no lock taken here)
    result = (
        client.table("puzzle_generation_jobs")
        .select("*, puzzle_configs(*)")
        .eq("status", "queued")
        .order("created_at")
        .limit(1)
        .execute()
    )
    job = result.data[0]

    # Step 2: attempt to claim it — but ONLY if it's still 'queued'
    # This is the compare-and-swap: eq("status", "queued") is the guard
    claim = (
        client.table("puzzle_generation_jobs")
        .update({"status": "generating", "attempts": job["attempts"] + 1})
        .eq("id", job["id"])
        .eq("status", "queued")   # ← the optimistic lock condition
        .execute()
    )

    if not claim.data:
        return None  # Another worker claimed it first — skip and move on
```

## Why this works

PostgREST (Supabase's query layer) translates this into a single SQL statement:

```sql
UPDATE puzzle_generation_jobs
   SET status = 'generating', attempts = attempts + 1
 WHERE id = $1
   AND status = 'queued';
```

If Worker A runs this first, the row transitions to `'generating'`. When Worker B runs the
same statement microseconds later, the `AND status = 'queued'` condition fails — the row
is already `'generating'` — so zero rows are updated and `claim.data` is empty.

## Contrast with pessimistic locking

An alternative is `SELECT ... FOR UPDATE SKIP LOCKED` (used by `get_random_approved_puzzle`
in this same codebase for serving puzzles). That approach takes a row-level lock during
the SELECT, preventing other readers from seeing the row at all. It's stronger but requires
a transaction. The optimistic approach works well with Supabase's stateless REST API where
you can't hold a transaction open across two HTTP calls.

## The job status column as a state machine

The `status` column doing double duty as both state and lock is a common pattern in
queue-backed systems. Each transition is meaningful:

```
queued → generating  (worker claimed it)
generating → validating  (puzzle stored, now validating)
validating → complete | failed  (validation done)
failed → queued  (retry, if attempts < MAX_ATTEMPTS)
```

Only one valid transition exists at each state, so the optimistic lock condition on
the *current* status is always unambiguous.
