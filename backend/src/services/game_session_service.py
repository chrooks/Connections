"""
Game Session Service for the Connections game.

Manages active and completed game sessions in Supabase, replacing the previous
SQLite/SQLAlchemy layer (dal.py + models.py).

Follows the same lazy-singleton client pattern as puzzle_pool_service.py.
The service_role key is used for all operations so RLS is bypassed — these are
server-side calls, never direct client calls.

Public API (mirrors the old dal.py interface):
    add_new_game(grid, connections, user_id, puzzle_id) → str
    check_game_exists(game_id)                          → bool
    get_game_from_db(game_id)                           → dict | None
    get_active_game_for_user(user_id)                   → str | None
    check_guess(game_id, guess)                         → (bool, bool, bool, str)
    update_game_state(game_id, guess, is_correct)       → None
    check_game_over(game_row)                           → str
    all_conditions_for_win_met(game_row)                → bool
    reset_game(game_id, grid, connections, puzzle_id)   → dict
    get_all_games()                                     → list[dict]
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supabase client — lazy singleton.
# Deferred import avoids the supabase/ migrations directory shadowing the
# real supabase-py package when running from the project root.
# Tests mock _get_client() directly so the real import never runs in CI.
# ---------------------------------------------------------------------------
_supabase = None


def _get_client():
    """Returns the shared Supabase client, creating it on first call."""
    global _supabase
    if _supabase is None:
        import os
        try:
            from supabase import create_client
        except ImportError:
            raise RuntimeError(
                "supabase package is not installed. "
                "Run: pip install 'supabase>=2.0.0'"
            )
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set. "
                "Add them to backend/.env (use .env.example as a template)."
            )
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_game_row(game_id: str) -> "dict | None":
    """
    SELECT a single game_sessions row by id.

    Returns the raw snake_case dict from Supabase, or None if not found.
    Used internally by service functions that need to read-then-write.
    """
    supabase = _get_client()
    result = (
        supabase.table("game_sessions")
        .select("*")
        .eq("id", game_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _row_to_state(row: dict) -> dict:
    """
    Transforms a raw Supabase snake_case row into the camelCase dict that
    routes.py and game.py expect — equivalent to the old ConnectionsGame.to_state().
    """
    return {
        "gameId":          row["id"],
        "grid":            row["grid"],
        "connections":     row["connections"],
        "mistakesLeft":    row["mistakes_left"],
        "status":          row["status"],           # already a plain string
        "previousGuesses": row["previous_guesses"],
        "puzzleNumber":    row["puzzle_number"],
        "puzzleId":        row.get("puzzle_id"),    # None for static-fallback games
    }


def _compute_status(connections: "list[dict]", mistakes_left: int) -> str:
    """
    Derives the new game status from the current connections and remaining mistakes.
    Pure logic — no DB call.
    """
    if mistakes_left <= 0:
        return "LOSS"
    if all(c["guessed"] for c in connections):
        return "WIN"
    return "IN_PROGRESS"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_new_game(
    grid: "list[str]",
    connections: "list[dict]",
    user_id: "str | None" = None,
    puzzle_id: "str | None" = None,
) -> str:
    """
    Inserts a new game session row and returns its UUID.

    Args:
        grid:        Shuffled list of 16 words for the grid.
        connections: List of 4 connection dicts (relationship, words, guessed).
        user_id:     Supabase auth user UUID, or None for guest sessions.
        puzzle_id:   UUID of the pool puzzle that was served, or None for the
                     static-fallback case.

    Returns:
        str: UUID of the newly created game_sessions row.
    """
    supabase = _get_client()
    result = (
        supabase.table("game_sessions")
        .insert({
            "grid":             grid,
            "connections":      connections,
            "mistakes_left":    4,
            "status":           "IN_PROGRESS",
            "previous_guesses": [],
            "user_id":          user_id,
            "puzzle_id":        puzzle_id,
        })
        .execute()
    )
    game_id: str = result.data[0]["id"]
    logger.info(
        "Created game session %s (user_id=%s, puzzle_id=%s)",
        game_id, user_id, puzzle_id,
    )
    return game_id


def check_game_exists(game_id: str) -> bool:
    """Returns True if a game_sessions row with this id exists."""
    return _fetch_game_row(game_id) is not None


def get_game_from_db(game_id: str) -> "dict | None":
    """
    Fetches the game and returns it as a camelCase state dict.

    The returned shape matches the old ConnectionsGame.to_state() exactly so
    callers (game.py, routes.py) require no changes.

    Returns None if the game does not exist.
    """
    row = _fetch_game_row(game_id)
    if row is None:
        return None
    return _row_to_state(row)


def get_active_game_for_user(user_id: str) -> "str | None":
    """
    Returns the game_id of the most recent IN_PROGRESS session for this user,
    or None if no active session exists.

    Used to implement get-or-create semantics in create_new_game so that
    authenticated users resume their existing game rather than starting fresh
    on every page load.
    """
    supabase = _get_client()
    result = (
        supabase.table("game_sessions")
        .select("id")
        .eq("user_id", user_id)
        .eq("status", "IN_PROGRESS")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def get_completed_puzzle_ids_for_user(user_id: str) -> "list[str]":
    """
    Returns all puzzle IDs this user should not be served again.

    Sources (union of both):
      1. Completed (WIN or LOSS) game_sessions rows — real games the user played.
      2. user_puzzle_exclusions rows — puzzles the user played as a guest that
         were transferred to their account when they signed up/in.

    Used by generate_game_grid to exclude already-played puzzles so a player
    is never served the same puzzle twice.
    """
    supabase = _get_client()

    games_result = (
        supabase.table("game_sessions")
        .select("puzzle_id")
        .eq("user_id", user_id)
        .in_("status", ["WIN", "LOSS"])
        .filter("puzzle_id", "not.is", "null")
        .execute()
    )
    excl_result = (
        supabase.table("user_puzzle_exclusions")
        .select("puzzle_id")
        .eq("user_id", user_id)
        .execute()
    )

    ids: set[str] = {row["puzzle_id"] for row in games_result.data}
    ids.update(row["puzzle_id"] for row in excl_result.data)
    return list(ids)


def transfer_guest_data(
    user_id: str,
    active_game_id: "str | None",
    completed_puzzle_ids: "list[str]",
) -> dict:
    """
    Transfers guest session data to an authenticated user account.

    Two operations:
      1. Claim the active guest game session: sets user_id on the unclaimed
         game_sessions row so it becomes the user's current IN_PROGRESS game.
         Skipped if the user already has an active game (existing progress wins).
      2. Record completed puzzle exclusions: inserts rows into
         user_puzzle_exclusions so puzzles played as a guest are not re-served.
         Uses upsert to silently handle duplicates.

    Returns a dict with "claimed_game" (bool) and "exclusions_added" (int).
    """
    supabase = _get_client()
    claimed_game = False
    exclusions_added = 0

    # --- Claim the active game session ---
    if active_game_id:
        # Only transfer if the user has no existing IN_PROGRESS game; their
        # existing progress should not be clobbered by the guest session.
        existing_active = get_active_game_for_user(user_id)
        if not existing_active:
            result = (
                supabase.table("game_sessions")
                .update({"user_id": user_id})
                .eq("id", active_game_id)
                .is_("user_id", "null")   # safety: only claim un-owned sessions
                .execute()
            )
            claimed_game = bool(result.data)
            logger.info(
                "Claimed guest game %s for user %s: %s",
                active_game_id, user_id, claimed_game,
            )
        else:
            logger.info(
                "User %s already has active game %s — not overwriting with guest game %s",
                user_id, existing_active, active_game_id,
            )

    # --- Record completed-puzzle exclusions ---
    if completed_puzzle_ids:
        rows = [{"user_id": user_id, "puzzle_id": pid} for pid in completed_puzzle_ids]
        supabase.table("user_puzzle_exclusions").upsert(rows).execute()
        exclusions_added = len(completed_puzzle_ids)
        logger.info(
            "Added %d puzzle exclusion(s) for user %s from guest transfer",
            exclusions_added, user_id,
        )

    return {"claimed_game": claimed_game, "exclusions_added": exclusions_added}


def check_guess(
    game_id: str, guess: "list[str]"
) -> "tuple[bool, bool, bool, bool, str]":
    """
    Validates a 4-word guess against the current game state.

    Returns:
        (is_correct, is_valid, is_new, is_one_away, error_message)
        - is_correct:    guess exactly matches one of the unsolved connections
        - is_valid:      guess passes all format/content checks
        - is_new:        guess has not been submitted before
        - is_one_away:   guess shares exactly 3 words with an unsolved connection
        - error_message: non-empty string when is_valid is False
    """
    row = _fetch_game_row(game_id)
    if row is None:
        raise ValueError("Game not found with the provided game ID.")

    if row["status"] != "IN_PROGRESS":
        return False, False, False, False, "Game is not in progress."

    if len(guess) != 4:
        return False, False, False, False, "Guess must contain exactly four words."
    if not all(word in row["grid"] for word in guess):
        return False, False, False, False, "All words in the guess must be in the game grid."
    if len(set(guess)) != 4:
        return False, False, False, False, "Guess must not contain duplicate words."

    guess_set = set(guess)

    # Check whether this exact combination has been submitted before
    is_new = not any(
        set(prev) == guess_set for prev in row["previous_guesses"]
    )

    # Check whether the guess matches any connection
    is_correct = any(
        set(c["words"]) == guess_set for c in row["connections"]
    )

    # Detect "one away": guess overlaps exactly 3 words with any unsolved connection
    is_one_away = not is_correct and any(
        len(guess_set & set(c["words"])) == 3
        for c in row["connections"]
        if not c.get("guessed", False)
    )

    logger.debug(
        "check_guess game=%s is_correct=%s is_new=%s is_one_away=%s guess=%s",
        game_id, is_correct, is_new, is_one_away, guess,
    )
    return is_correct, True, is_new, is_one_away, ""


def update_game_state(game_id: str, guess: "list[str]", is_correct: bool) -> None:
    """
    Applies a validated guess to the game state and writes the result back.

    Pattern: fetch row → compute new state in Python → single UPDATE.
    This replaces the SQLAlchemy pattern of mutating an ORM object in-place.

    Duplicate guesses (same set of words) are silently ignored to match the
    original DAL behaviour.
    """
    row = _fetch_game_row(game_id)
    if row is None:
        raise ValueError(f"Game {game_id} not found during state update.")

    guess_set = set(guess)

    # Idempotency guard: do not re-apply an already-recorded guess
    if any(set(prev) == guess_set for prev in row["previous_guesses"]):
        logger.debug("Duplicate guess ignored for game %s: %s", game_id, guess)
        return

    new_guesses = row["previous_guesses"] + [guess]

    # Mark the matching connection as guessed (if correct)
    new_connections = []
    for conn in row["connections"]:
        if is_correct and set(conn["words"]) == guess_set:
            new_connections.append({**conn, "guessed": True})
        else:
            new_connections.append(conn)

    new_mistakes = row["mistakes_left"] - (0 if is_correct else 1)
    new_status = _compute_status(new_connections, new_mistakes)

    supabase = _get_client()
    supabase.table("game_sessions").update({
        "previous_guesses": new_guesses,
        "connections":       new_connections,
        "mistakes_left":     new_mistakes,
        "status":            new_status,
    }).eq("id", game_id).execute()

    logger.debug(
        "Updated game %s: status=%s mistakes_left=%d",
        game_id, new_status, new_mistakes,
    )


def check_game_over(game_row: dict) -> str:
    """
    Pure logic: derives the game status from a state dict (snake_case row OR
    camelCase state dict — only 'connections' and 'mistakes_left'/'mistakesLeft'
    are read).

    Returns the status string: 'IN_PROGRESS', 'WIN', or 'LOSS'.
    """
    # Accept both snake_case (raw row) and camelCase (state dict)
    mistakes = game_row.get("mistakes_left", game_row.get("mistakesLeft", 0))
    connections = game_row.get("connections", [])
    return _compute_status(connections, mistakes)


def all_conditions_for_win_met(game_row: dict) -> bool:
    """
    Pure logic: returns True when every connection in the game has been guessed.
    """
    connections = game_row.get("connections", [])
    return bool(connections) and all(c["guessed"] for c in connections)


def reset_game(
    game_id: str,
    grid: "list[str]",
    connections: "list[dict]",
    puzzle_id: "str | None" = None,
) -> dict:
    """
    Resets an existing game session with a new grid and connections.

    Returns the updated game state dict (camelCase), ready for the API response.
    """
    supabase = _get_client()
    supabase.table("game_sessions").update({
        "grid":             grid,
        "connections":      connections,
        "mistakes_left":    4,
        "status":           "IN_PROGRESS",
        "previous_guesses": [],
        "puzzle_id":        puzzle_id,
    }).eq("id", game_id).execute()

    logger.info("Reset game session %s (new puzzle_id=%s)", game_id, puzzle_id)
    return get_game_from_db(game_id)


def forfeit_game(game_id: str) -> bool:
    """
    Force-ends an IN_PROGRESS game as a forfeit.

    Sets status='LOSS', mistakes_left=0, and forfeited=True so the profile
    screen can distinguish a voluntary give-up from a natural loss.

    Returns True if the forfeit was applied, False if the game was not found
    or was already in a terminal state.
    """
    row = _fetch_game_row(game_id)
    if row is None:
        logger.warning("forfeit_game: game %s not found", game_id)
        return False

    if row["status"] != "IN_PROGRESS":
        logger.warning(
            "forfeit_game: game %s already in terminal state %s",
            game_id, row["status"],
        )
        return False

    supabase = _get_client()
    supabase.table("game_sessions").update({
        "status":        "LOSS",
        "mistakes_left": 0,
        "forfeited":     True,
    }).eq("id", game_id).execute()

    logger.info("Game %s forfeited", game_id)
    return True


def record_completion_time(game_id: str, time_seconds: int) -> None:
    """
    Persists the time (in seconds) it took the player to complete the puzzle.

    Only writes if the game exists and has a terminal status (WIN or LOSS) —
    avoids recording a partial time if the call arrives before the last guess
    has been processed.

    Args:
        game_id:      UUID of the game session to update.
        time_seconds: Elapsed wall-clock seconds measured by the frontend timer.
    """
    row = _fetch_game_row(game_id)
    if row is None:
        logger.warning("record_completion_time: game %s not found", game_id)
        return

    if row["status"] not in ("WIN", "LOSS"):
        logger.warning(
            "record_completion_time: game %s is still IN_PROGRESS, skipping",
            game_id,
        )
        return

    supabase = _get_client()
    supabase.table("game_sessions").update({
        "completion_time_seconds": time_seconds,
    }).eq("id", game_id).execute()

    logger.info(
        "Recorded completion time %ds for game %s", time_seconds, game_id
    )


def get_all_games() -> "list[dict]":
    """
    Fetches all game sessions and returns them as a list of camelCase state dicts.
    Used by the debug /get-game-data endpoint.
    """
    supabase = _get_client()
    result = supabase.table("game_sessions").select("*").execute()
    return [_row_to_state(row) for row in result.data]


def get_user_stats(user_id: str) -> dict:
    """
    Returns aggregate stats for an authenticated user across all completed games.

    Forfeits are a subset of LOSS rows — distinguished by the forfeited flag so
    the profile screen can show three separate counts (wins / natural losses / forfeits).
    Average completion time is only computed over wins, since timed-out or forfeited
    games don't have a meaningful "how fast did you solve it" value.
    """
    supabase = _get_client()
    result = (
        supabase.table("game_sessions")
        .select("status, forfeited, completion_time_seconds")
        .eq("user_id", user_id)
        .in_("status", ["WIN", "LOSS"])
        .execute()
    )
    rows = result.data
    wins = [r for r in rows if r["status"] == "WIN"]
    losses = [r for r in rows if r["status"] == "LOSS" and not r.get("forfeited")]
    forfeits = [r for r in rows if r.get("forfeited")]
    win_times = [r["completion_time_seconds"] for r in wins if r["completion_time_seconds"]]
    avg_time = round(sum(win_times) / len(win_times)) if win_times else None
    return {
        "wins": len(wins),
        "losses": len(losses),
        "forfeits": len(forfeits),
        "avgCompletionTimeSeconds": avg_time,
    }


def get_user_history(user_id: str) -> "list[dict]":
    """
    Returns completed game sessions for an authenticated user, newest first.

    Translates the DB representation (status='LOSS', forfeited=True) into a
    clean 'FORFEIT' outcome string so the frontend doesn't need to know the
    underlying schema detail.
    """
    supabase = _get_client()
    result = (
        supabase.table("game_sessions")
        .select(
            "id, puzzle_id, puzzle_number, status, forfeited, completion_time_seconds, "
            "created_at, connections, previous_guesses"
        )
        .eq("user_id", user_id)
        .in_("status", ["WIN", "LOSS"])
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data

    # Batch-fetch edited_at for all puzzles referenced in this history,
    # then join in Python to avoid N+1 queries.
    puzzle_ids = list({r["puzzle_id"] for r in rows if r.get("puzzle_id")})
    edited_at_by_puzzle: dict = {}
    if puzzle_ids:
        puzzles_result = (
            supabase.table("puzzles")
            .select("id, edited_at")
            .in_("id", puzzle_ids)
            .execute()
        )
        edited_at_by_puzzle = {
            p["id"]: p.get("edited_at")
            for p in (puzzles_result.data or [])
        }

    history = []
    for row in rows:
        outcome = "FORFEIT" if row.get("forfeited") else row["status"]
        puzzle_edited_at = edited_at_by_puzzle.get(row.get("puzzle_id"))
        puzzle_modified = bool(
            puzzle_edited_at and puzzle_edited_at > row["created_at"]
        )
        history.append({
            "gameId": row["id"],
            "puzzleNumber": row["puzzle_number"],
            "outcome": outcome,
            "completionTimeSeconds": row["completion_time_seconds"],
            "playedAt": row["created_at"],
            # Full connection data so the profile modal can render the solution grid
            "connections": row["connections"],
            "previousGuesses": row["previous_guesses"],
            "puzzleModifiedSincePlayed": puzzle_modified,
        })
    return history
