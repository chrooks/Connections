-- =============================================================================
-- Migration: add_forfeited
-- Description: Adds a forfeited flag to game_sessions so the profile screen
--              can distinguish a voluntary give-up from a natural loss.
--              Status remains 'LOSS' in both cases; this flag carries the detail.
-- =============================================================================

ALTER TABLE game_sessions
    ADD COLUMN forfeited boolean NOT NULL DEFAULT false;
