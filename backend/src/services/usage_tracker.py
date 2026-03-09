"""
API Usage Tracker — logs Anthropic token consumption to the Supabase api_usage table.

Every call to the Anthropic API in the generation pipeline costs money. This module
provides a lightweight record_usage() function that appends one row per API response
to the api_usage table, capturing input/output tokens, cache hit counts, and an
estimated USD cost.

Two pricing schedules are baked in:
  - Standard (real-time requests)
  - Batch (Anthropic Batch API — 50% cheaper)

Usage:
    from backend.src.services.usage_tracker import record_usage, get_cost_summary

    # After any client.messages.create() call:
    record_usage(
        source="puzzle_generator",
        model="claude-sonnet-4-5-20250929",
        response=response,           # anthropic.types.Message
        puzzle_id="abc-123",         # optional
        metadata={"step": "Step 1"},
    )

    # Cost report for last 7 days:
    summary = get_cost_summary(start_date="2026-03-02", end_date="2026-03-09")
    # {"total_cost_usd": 1.23, "total_input_tokens": 500000, ...}
"""

import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing tables — USD per 1 million tokens (as of 2026-03)
#
# Cache read tokens cost ~10% of the standard input price;
# cache write tokens cost ~125% of the standard input price.
# ---------------------------------------------------------------------------

# Standard (real-time) pricing
_STANDARD_PRICING: dict[str, dict[str, float]] = {
    # input_per_mtok, output_per_mtok, cache_read_per_mtok, cache_write_per_mtok
    "claude-opus-4-6": {
        "input": 5.00, "output": 25.00,
        "cache_read": 0.50, "cache_write": 6.25,
    },
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
    },
    "claude-haiku-4-5": {
        "input": 1.00, "output": 5.00,
        "cache_read": 0.10, "cache_write": 1.25,
    },
    # Legacy Sonnet used by puzzle_generator and group_generator
    "claude-sonnet-4-5-20250929": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
    },
}

# Batch pricing — 50% of standard for input/output; cache discounts apply on top.
_BATCH_PRICING: dict[str, dict[str, float]] = {
    model: {k: v * 0.5 for k, v in prices.items()}
    for model, prices in _STANDARD_PRICING.items()
}


def _get_client():
    """Lazy Supabase client import — avoids namespace collision with /backend/supabase/."""
    from ..services.puzzle_pool_service import _get_client as _pool_client
    return _pool_client()


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    is_batch: bool,
) -> float:
    """
    Return an estimated USD cost for one API response.

    Falls back to the Sonnet 4.6 price table when the exact model isn't found,
    since most generation uses Sonnet-family models.
    """
    pricing_table = _BATCH_PRICING if is_batch else _STANDARD_PRICING
    # Normalise model name: strip date suffixes if any (e.g. -20250929)
    prices = pricing_table.get(model) or pricing_table.get("claude-sonnet-4-6", {})

    def _mtok(tokens: int, rate: float) -> float:
        return (tokens / 1_000_000) * rate

    # Billable input = non-cached tokens; cache reads are cheaper; writes are extra.
    non_cached_input = max(0, input_tokens - cache_read_tokens)
    cost = (
        _mtok(non_cached_input, prices.get("input", 3.00))
        + _mtok(output_tokens, prices.get("output", 15.00))
        + _mtok(cache_read_tokens, prices.get("cache_read", 0.30))
        + _mtok(cache_write_tokens, prices.get("cache_write", 3.75))
    )
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_usage(
    source: str,
    model: str,
    response,
    puzzle_id: Optional[str] = None,
    job_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    is_batch: bool = False,
) -> None:
    """
    Record token usage from one Anthropic API response to the api_usage table.

    Args:
        source:     Calling context label (e.g. 'puzzle_generator', 'group_generator').
        model:      Model ID used for the call (e.g. 'claude-sonnet-4-5-20250929').
        response:   The anthropic.types.Message object returned by client.messages.create().
        puzzle_id:  Supabase UUID of the puzzle being generated (optional).
        job_id:     Supabase UUID of the generation job (optional).
        metadata:   Extra context dict (e.g. {"step": "Step 1", "temperature": 1.0}).
        is_batch:   True when the response came from the Batch API (50% discount).

    Errors are swallowed — usage tracking must never break the generation pipeline.
    """
    try:
        usage = response.usage
        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0
        # cache_read_input_tokens / cache_creation_input_tokens are present when
        # prompt caching is active; fall back to 0 when the attribute is missing.
        cache_read_tokens = getattr(usage, "cache_read_input_tokens", None) or 0
        cache_write_tokens = getattr(usage, "cache_creation_input_tokens", None) or 0

        estimated_cost = _estimate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            is_batch=is_batch,
        )

        row: dict = {
            "source": source,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens or None,
            "cache_write_tokens": cache_write_tokens or None,
            "estimated_cost_usd": str(estimated_cost),  # Supabase numeric
            "metadata": metadata,
        }
        if puzzle_id:
            row["puzzle_id"] = puzzle_id
        if job_id:
            row["job_id"] = job_id

        _get_client().table("api_usage").insert(row).execute()

        logger.debug(
            "Usage recorded: source=%s model=%s in=%d out=%d cache_read=%d cost=$%.4f",
            source, model, input_tokens, output_tokens, cache_read_tokens, estimated_cost,
        )

    except Exception:
        # Usage tracking is best-effort; never let it propagate into the calling pipeline.
        logger.warning("Failed to record API usage", exc_info=True)


def get_cost_summary(
    start_date: "str | date",
    end_date: "str | date",
    source: Optional[str] = None,
) -> dict:
    """
    Return aggregated cost and token counts for the given date range.

    Args:
        start_date: ISO date string or date object (inclusive).
        end_date:   ISO date string or date object (inclusive).
        source:     Optional filter — only include rows from this source.

    Returns:
        {
            "start_date":           str,
            "end_date":             str,
            "source_filter":        str | None,
            "total_cost_usd":       float,
            "total_input_tokens":   int,
            "total_output_tokens":  int,
            "total_cache_read_tokens":  int,
            "total_cache_write_tokens": int,
            "row_count":            int,
        }

    Raises RuntimeError on Supabase query failure.
    """
    # Normalise to ISO strings for the Supabase query.
    start_str = start_date.isoformat() if isinstance(start_date, date) else start_date
    end_str = end_date.isoformat() if isinstance(end_date, date) else end_date

    # Supabase REST API doesn't support SUM aggregation natively via the Python
    # client's fluent API, so we fetch rows and aggregate in Python.
    # For large tables, replace with an RPC (PostgreSQL function) call.
    query = (
        _get_client()
        .table("api_usage")
        .select(
            "input_tokens, output_tokens, cache_read_tokens, "
            "cache_write_tokens, estimated_cost_usd"
        )
        .gte("created_at", f"{start_str}T00:00:00Z")
        .lte("created_at", f"{end_str}T23:59:59Z")
    )
    if source:
        query = query.eq("source", source)

    result = query.execute()
    if not result.data:
        rows = []
    else:
        rows = result.data

    total_cost = sum(float(r.get("estimated_cost_usd") or 0) for r in rows)
    total_input = sum(int(r.get("input_tokens") or 0) for r in rows)
    total_output = sum(int(r.get("output_tokens") or 0) for r in rows)
    total_cache_read = sum(int(r.get("cache_read_tokens") or 0) for r in rows)
    total_cache_write = sum(int(r.get("cache_write_tokens") or 0) for r in rows)

    return {
        "start_date": start_str,
        "end_date": end_str,
        "source_filter": source,
        "total_cost_usd": round(total_cost, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_tokens": total_cache_read,
        "total_cache_write_tokens": total_cache_write,
        "row_count": len(rows),
    }
