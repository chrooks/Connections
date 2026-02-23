-- =============================================================================
-- Migration: game_sessions
-- Description: Replaces the local SQLite game state storage with a Supabase
--              table. Games are now persisted in the cloud, linked to
--              authenticated users (nullable for guests) and to the puzzle they
--              were drawn from (nullable for static-fallback games).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- game_sessions
-- One row per active or completed game session.
--
-- user_id  — nullable: guest games have no owner.
-- puzzle_id — nullable: games served from the static fallback connections.json
--             have no corresponding pool puzzle to reference.
-- puzzle_number — Postgres identity sequence. Globally sequential and
--                 consistent across all environments, unlike the old SQLite
--                 local counter.
-- -----------------------------------------------------------------------------
CREATE TABLE game_sessions (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The authenticated player who started this game; NULL for guest sessions
    user_id          uuid        REFERENCES auth.users(id) ON DELETE SET NULL,

    -- Which pool puzzle was served; NULL when the static JSON fallback was used
    puzzle_id        uuid        REFERENCES puzzles(id) ON DELETE SET NULL,

    -- Flat list of the 16 words shown in the grid (shuffled order)
    grid             jsonb       NOT NULL,

    -- List of 4 connection dicts: {relationship, words, guessed}
    connections      jsonb       NOT NULL,

    -- Remaining incorrect guesses; starts at 4, decrements on wrong answer
    mistakes_left    integer     NOT NULL DEFAULT 4
                         CHECK (mistakes_left BETWEEN 0 AND 4),

    -- State machine: IN_PROGRESS until the player wins or exhausts mistakes
    status           text        NOT NULL DEFAULT 'IN_PROGRESS'
                         CHECK (status IN ('IN_PROGRESS', 'WIN', 'LOSS')),

    -- Ordered list of every 4-word guess submitted this session
    previous_guesses jsonb       NOT NULL DEFAULT '[]',

    -- Globally sequential puzzle number used for results sharing
    puzzle_number    integer     GENERATED ALWAYS AS IDENTITY,

    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);


-- Fast lookup of all games for a given user (game history, stats)
CREATE INDEX idx_game_sessions_user_id
    ON game_sessions (user_id);

-- Enables per-puzzle analytics (completion rate, average mistakes, etc.)
CREATE INDEX idx_game_sessions_puzzle_id
    ON game_sessions (puzzle_id);


-- Auto-update updated_at on every write.
-- touch_updated_at() is defined in the puzzle_pool migration (20260210000000).
CREATE TRIGGER trg_game_sessions_updated_at
    BEFORE UPDATE ON game_sessions
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
