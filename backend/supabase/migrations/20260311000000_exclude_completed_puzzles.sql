-- =============================================================================
-- Migration: exclude_completed_puzzles
-- Description: Updates get_random_approved_puzzle to accept an optional array
--              of puzzle UUIDs to exclude from selection. This allows the game
--              server to pass a player's already-completed puzzle IDs so they
--              are never served the same puzzle twice.
--
-- The p_exclude_ids parameter defaults to an empty array so existing callers
-- that don't pass it continue to work without any changes.
-- =============================================================================

CREATE OR REPLACE FUNCTION get_random_approved_puzzle(
    p_config_id   uuid,
    p_exclude_ids uuid[] DEFAULT '{}'
)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_puzzle_id uuid;
BEGIN
    -- Lock one random approved puzzle; skip any row already locked by a
    -- concurrent call (FOR UPDATE SKIP LOCKED) and skip any puzzle the player
    -- has already completed (id != ALL(p_exclude_ids)).
    SELECT id
      INTO v_puzzle_id
      FROM puzzles
     WHERE config_id = p_config_id
       AND status    = 'approved'
       AND (cardinality(p_exclude_ids) = 0 OR id != ALL(p_exclude_ids))
     ORDER BY random()
     LIMIT 1
       FOR UPDATE SKIP LOCKED;

    -- Nothing available for this config (pool empty or all approved puzzles
    -- have already been played by this player).
    IF v_puzzle_id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Atomically record that this puzzle was served.
    UPDATE puzzles
       SET times_served = times_served + 1
     WHERE id = v_puzzle_id;

    RETURN v_puzzle_id;
END;
$$;
