---
date: 2026-03-09
patterns: [append-only log, cost tracking, observability]
project: Connections
---

# Append-Only Tables for Cost and Usage Tracking

## Problem being solved

Every Anthropic API call costs money. Without a record of what was called, when,
and how much it cost, you can't answer: "How much did generating those 20 puzzles
cost?" or "Is the batch generator actually cheaper than the worker pipeline?"

## Why append-only fits

Usage data is naturally append-only — you record what happened, you never need to
update or delete it. Using an insert-only pattern gives you:

- A permanent audit trail (costs are frozen at insert time, surviving pricing changes)
- No UPDATE contention — each row is written once and never touched again
- Simple aggregation queries for reporting

The `api_usage` table captures one row per API response:

```sql
CREATE TABLE api_usage (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source              text NOT NULL,        -- 'puzzle_generator', 'batch_generator', etc.
    model               text NOT NULL,
    input_tokens        integer NOT NULL DEFAULT 0,
    output_tokens       integer NOT NULL DEFAULT 0,
    cache_read_tokens   integer,              -- NULL when caching not used
    cache_write_tokens  integer,
    estimated_cost_usd  numeric(10, 6),       -- snapshot at insert time
    puzzle_id           uuid REFERENCES puzzles(id) ON DELETE SET NULL,
    metadata            jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);
```

## The calling pattern

`record_usage()` is a fire-and-forget wrapper — errors are swallowed so tracking
can never block the generation pipeline:

```python
def record_usage(source, model, response, puzzle_id=None, metadata=None):
    try:
        usage = response.usage
        cost = _estimate_cost(model, usage.input_tokens, usage.output_tokens, ...)
        _get_client().table("api_usage").insert({...}).execute()
    except Exception:
        logger.warning("Failed to record API usage", exc_info=True)
        # never re-raise — tracking is best-effort
```

## Estimated cost is stored at write time

The cost estimate is computed and stored at insert time, not derived on read. This
matters because API pricing changes over time. If you stored only token counts and
computed cost dynamically, old records would appear to cost different amounts after a
price change. Freezing the estimate at write time makes historical reports stable.

## Aggregation in Python vs. DB

The Supabase REST API doesn't support `SUM()` natively via the fluent client, so
`get_cost_summary()` fetches raw rows and aggregates in Python. This is fine for
reporting (infrequent, offline) but would need to be replaced with a PostgreSQL RPC
function for large tables or frequent queries:

```python
# Works fine for now; replace with supabase.rpc("summarise_api_usage", ...) at scale
total_cost = sum(float(r.get("estimated_cost_usd") or 0) for r in rows)
```
