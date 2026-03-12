-- =============================================================================
-- Migration: user_puzzle_exclusions
-- Description: Stores explicit puzzle exclusions for authenticated users so
--              that puzzles played as a guest can be excluded from future
--              serving after the player creates an account.
--
--              get_completed_puzzle_ids_for_user unions this table with
--              completed game_sessions rows so the pool-fetch logic treats
--              both sources identically.
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_puzzle_exclusions (
    user_id    uuid NOT NULL REFERENCES auth.users(id)  ON DELETE CASCADE,
    puzzle_id  uuid NOT NULL REFERENCES puzzles(id)     ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, puzzle_id)
);

CREATE INDEX idx_user_puzzle_exclusions_user_id
    ON user_puzzle_exclusions (user_id);
