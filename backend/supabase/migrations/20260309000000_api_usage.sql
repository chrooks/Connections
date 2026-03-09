-- =============================================================================
-- Migration: api_usage
-- Description: Adds a table for tracking Anthropic API token consumption and
--              estimated cost per generation pipeline call. Enables cost
--              reporting and rate-limit debugging.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- api_usage
-- One row per API call (or logical batch of calls within a pipeline step).
-- Recorded by usage_tracker.record_usage() after each Claude response.
--
-- Designed for append-only writes — rows are never updated after insert.
-- -----------------------------------------------------------------------------
CREATE TABLE api_usage (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Which calling context produced this usage entry.
    -- 'group_generator', 'puzzle_generator', 'batch_generator', 'validator', etc.
    source          text        NOT NULL,

    -- Claude model that was called (e.g. 'claude-sonnet-4-5-20250929')
    model           text        NOT NULL,

    -- Token counts from the API response usage object
    input_tokens    integer     NOT NULL DEFAULT 0,
    output_tokens   integer     NOT NULL DEFAULT 0,

    -- Tokens served from the prompt cache (subset of input_tokens).
    -- NULL when caching was not used or the source doesn't report it.
    cache_read_tokens   integer,
    cache_write_tokens  integer,

    -- Estimated cost in USD, computed at insert time from known per-model pricing.
    -- Stored as a snapshot so historical reports survive pricing changes.
    estimated_cost_usd  numeric(10, 6),

    -- Optional foreign key to the puzzle being generated (if applicable).
    puzzle_id       uuid        REFERENCES puzzles(id) ON DELETE SET NULL,

    -- Optional job reference for worker-driven generation
    job_id          uuid        REFERENCES puzzle_generation_jobs(id) ON DELETE SET NULL,

    -- Free-form metadata: step name, temperature, batch request ID, etc.
    metadata        jsonb,

    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Index for time-range cost queries (most common query pattern)
CREATE INDEX idx_api_usage_created_at ON api_usage (created_at DESC);

-- Index for per-source reporting
CREATE INDEX idx_api_usage_source ON api_usage (source, created_at DESC);

-- Index for looking up usage by puzzle
CREATE INDEX idx_api_usage_puzzle_id ON api_usage (puzzle_id)
    WHERE puzzle_id IS NOT NULL;
