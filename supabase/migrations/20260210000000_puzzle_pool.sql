-- =============================================================================
-- Migration: puzzle_pool
-- Description: Creates the puzzle generation pipeline tables for the
--              Connections game. Adds a pre-generated puzzle pool that the
--              generate-grid endpoint can pull from, along with job tracking
--              for async puzzle generation.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- puzzle_configs
-- Defines the shape of a puzzle (how many groups, words per group, etc.).
-- A "classic" config (4 groups × 4 words) is inserted as the default.
-- The generate-grid endpoint references this to know what format to produce.
-- -----------------------------------------------------------------------------
CREATE TABLE puzzle_configs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Human-readable name used to select config by slug (e.g. "classic", "mini")
    name            text        NOT NULL UNIQUE,
    num_groups      integer     NOT NULL DEFAULT 4,
    words_per_group integer     NOT NULL DEFAULT 4,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Seed the only config the game currently needs
INSERT INTO puzzle_configs (name, num_groups, words_per_group)
VALUES ('classic', 4, 4);


-- -----------------------------------------------------------------------------
-- puzzles
-- The puzzle pool. Each row is one complete puzzle that has been (or is being)
-- generated, validated, and eventually served to players.
--
-- Lifecycle:  draft → validating → approved → served
--                              └──→ rejected
-- -----------------------------------------------------------------------------
CREATE TABLE puzzles (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Which shape/format this puzzle conforms to
    config_id             uuid        NOT NULL REFERENCES puzzle_configs(id),

    -- State machine status for the generation/validation pipeline
    status                text        NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft', 'validating', 'approved', 'rejected', 'served')),

    -- Overall difficulty estimate (0.0 = easiest, 1.0 = hardest); set after validation
    difficulty_score      float,
    -- Composite quality score produced by the validation pipeline (0.0–1.0)
    validation_score      float,
    -- Full structured report from the validator (category scores, failure reasons, etc.)
    validation_report     jsonb,

    -- Which Claude model (or other LLM) was used to generate this puzzle
    generation_model      text        NOT NULL,
    -- Prompt version, temperature, seed, and any other generation params for reproducibility
    generation_metadata   jsonb,

    -- How many times this puzzle has been served to players; used for load-balancing the pool
    times_served          integer     NOT NULL DEFAULT 0,

    created_at            timestamptz NOT NULL DEFAULT now(),
    -- Set when a human or automated validator marks the puzzle approved
    approved_at           timestamptz
);

-- Fast lookup of all approved puzzles (primary hot-path for generate-grid)
CREATE INDEX idx_puzzles_status
    ON puzzles (status);

-- Allows pool-size checks per config without a sequential scan
CREATE INDEX idx_puzzles_config_status
    ON puzzles (config_id, status);


-- -----------------------------------------------------------------------------
-- puzzle_groups
-- The N categories (connections) that make up a single puzzle.
-- difficulty_rank mirrors the NYT colour scheme: 1=yellow … 4=purple.
-- -----------------------------------------------------------------------------
CREATE TABLE puzzle_groups (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    puzzle_id       uuid        NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
    -- The category label shown to the player on a correct guess (e.g. "Things that are red")
    category_name   text        NOT NULL,
    -- 1 = easiest (yellow), 2 = medium-easy (green), 3 = medium-hard (blue), 4 = hardest (purple)
    difficulty_rank integer     NOT NULL CHECK (difficulty_rank BETWEEN 1 AND 10),
    -- Explicit ordering so the frontend can render groups in a stable sequence
    sort_order      integer     NOT NULL
);


-- -----------------------------------------------------------------------------
-- puzzle_words
-- The individual words (tiles) belonging to a group.
--
-- Uniqueness constraint: the same word must not appear twice in the same puzzle.
-- Because puzzle_id lives on puzzle_groups (not here), we denormalise it onto
-- puzzle_words so a plain unique index can enforce the rule efficiently.
-- The column is kept in sync via an INSERT trigger — application code must NOT
-- set it directly.
-- -----------------------------------------------------------------------------
CREATE TABLE puzzle_words (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id        uuid        NOT NULL REFERENCES puzzle_groups(id) ON DELETE CASCADE,
    -- Denormalised from puzzle_groups so the unique index below can reference it
    puzzle_id       uuid        NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
    -- The canonical lowercase form of the word used for logic / dedup
    word            text        NOT NULL,
    -- Optional override for display (e.g. "McCARTHY" instead of "mccarthy"); NULL means use word as-is
    display_text    text
);

-- Enforce no duplicate words within a puzzle (case-insensitive).
-- lower(word) ensures "Apple" and "apple" are treated as the same word.
CREATE UNIQUE INDEX idx_puzzle_words_unique_per_puzzle
    ON puzzle_words (puzzle_id, lower(word));

-- Keep puzzle_id in sync with the parent group whenever a word is inserted or its group is changed.
CREATE OR REPLACE FUNCTION sync_puzzle_word_puzzle_id()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    -- Resolve puzzle_id from the parent group row
    SELECT puzzle_id
      INTO NEW.puzzle_id
      FROM puzzle_groups
     WHERE id = NEW.group_id;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_puzzle_words_set_puzzle_id
    BEFORE INSERT OR UPDATE OF group_id ON puzzle_words
    FOR EACH ROW EXECUTE FUNCTION sync_puzzle_word_puzzle_id();


-- -----------------------------------------------------------------------------
-- puzzle_generation_jobs
-- Tracks each async request to generate a new puzzle.
-- A worker polls for 'queued' jobs, attempts generation, and either sets the
-- status to 'complete' (with a puzzle_id) or 'failed' (with an error_message).
-- -----------------------------------------------------------------------------
CREATE TABLE puzzle_generation_jobs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Which puzzle shape to generate
    config_id       uuid        NOT NULL REFERENCES puzzle_configs(id),

    -- Async job lifecycle: queued → generating → validating → complete | failed
    status          text        NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'generating', 'validating', 'complete', 'failed')),

    -- Populated once the puzzle row is created (may be mid-pipeline if status is 'validating')
    puzzle_id       uuid        REFERENCES puzzles(id),

    -- Human- or machine-readable reason for failure; NULL when job succeeds
    error_message   text,

    -- Number of generation attempts made; workers use this to implement retry limits
    attempts        integer     NOT NULL DEFAULT 0,

    created_at      timestamptz NOT NULL DEFAULT now(),
    -- Refreshed by the worker on every status transition so stale jobs can be detected
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Workers poll this index to pick up pending work without scanning completed jobs
CREATE INDEX idx_generation_jobs_status
    ON puzzle_generation_jobs (status);

-- Auto-update updated_at on every write so stale-job detection is reliable
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_generation_jobs_updated_at
    BEFORE UPDATE ON puzzle_generation_jobs
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();


-- -----------------------------------------------------------------------------
-- get_random_approved_puzzle(config_id uuid) → uuid
--
-- Selects one approved puzzle at random for the given config, increments its
-- times_served counter atomically, and returns the puzzle_id.
-- Returns NULL if no approved puzzle exists for that config.
--
-- The FOR UPDATE SKIP LOCKED pattern prevents two concurrent callers from
-- serving the same puzzle when the pool is small.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_random_approved_puzzle(p_config_id uuid)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_puzzle_id uuid;
BEGIN
    -- Lock one random approved puzzle; skip any row already locked by a concurrent call
    SELECT id
      INTO v_puzzle_id
      FROM puzzles
     WHERE config_id = p_config_id
       AND status    = 'approved'
     ORDER BY random()
     LIMIT 1
       FOR UPDATE SKIP LOCKED;

    -- Nothing available in the pool for this config
    IF v_puzzle_id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Atomically record that this puzzle was served
    UPDATE puzzles
       SET times_served = times_served + 1
     WHERE id = v_puzzle_id;

    RETURN v_puzzle_id;
END;
$$;
