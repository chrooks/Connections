-- =============================================================================
-- Migration: add_completion_time
-- Description: Adds completion_time_seconds to game_sessions so the profile
--              screen can display how long each puzzle took to solve.
--              NULL = game not yet completed or time not recorded.
-- =============================================================================

ALTER TABLE game_sessions
    ADD COLUMN completion_time_seconds integer;
