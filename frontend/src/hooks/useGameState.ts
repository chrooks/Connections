import { useState, useEffect, useRef } from "react";
import { apiPost, apiGet } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "react-toastify";

// localStorage key for guest session persistence (single-device only)
const GUEST_GAME_KEY = "guestGameId";
// localStorage key for the list of puzzle IDs a guest has already completed.
// Stored as a JSON array of UUID strings; sent to /generate-grid as ?exclude=...
// so the backend skips puzzles the guest has already played.
const GUEST_COMPLETED_KEY = "guestCompletedPuzzles";

/** Returns the stored list of completed puzzle IDs for the current guest session. */
function getGuestCompletedPuzzleIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(GUEST_COMPLETED_KEY) ?? "[]");
  } catch {
    return [];
  }
}

/**
 * Records a puzzle ID as completed for the current guest session.
 * No-ops if puzzleId is null (static-fallback game with no pool puzzle).
 */
function markGuestPuzzleCompleted(puzzleId: string | null): void {
  if (!puzzleId) return;
  try {
    const completed = getGuestCompletedPuzzleIds();
    if (!completed.includes(puzzleId)) {
      completed.push(puzzleId);
      localStorage.setItem(GUEST_COMPLETED_KEY, JSON.stringify(completed));
    }
  } catch {
    // localStorage may be unavailable in some private-browsing contexts — not fatal
  }
}

/**
 * Custom hook to manage the game grid state.
 * Fetches the game grid data from the server and handles loading and error states.
 *
 * Session persistence strategy:
 *   - Authenticated users: backend does get-or-create via /generate-grid, keyed
 *     on user_id. The game persists across devices and page refreshes server-side.
 *     Puzzle deduplication is handled entirely server-side.
 *   - Guests: game ID is stored in localStorage for single-device persistence.
 *     Completed (WIN/LOSS) games are automatically cleared so the next refresh
 *     starts fresh. Completed puzzle IDs are stored in a separate localStorage
 *     key and passed to /generate-grid as ?exclude=... so the backend avoids
 *     serving the same puzzle again (best-effort; resets if localStorage is cleared).
 *   - Admin play-test: when reviewGameId is provided, the hook skips /generate-grid
 *     entirely and loads the pre-created review game session directly.
 *
 * @param setMistakesLeft - A function to update the mistakesLeft state.
 * @param reviewGameId    - Optional game ID for admin play-test mode. When set,
 *                          the hook loads this specific game instead of creating/resuming.
 * @returns words, loading, error, connections, gameId, puzzleNumber, shuffleWords
 */
const useGameState = (
  setMistakesLeft: (mistakesLeft: number) => void,
  reviewGameId: string | null = null,
) => {
  const { user, loading: authLoading } = useAuth();

  const [words, setWords] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // True when the authenticated player has completed every puzzle in the pool.
  const [poolExhausted, setPoolExhausted] = useState<boolean>(false);
  const [connections, setConnections] = useState<any[]>([]);
  const [gameId, setGameId] = useState<string | null>(null);
  const [puzzleNumber, setPuzzleNumber] = useState<number | null>(null);
  // The pool puzzle UUID for the currently loaded game. Used by startNewGame to
  // record the completed puzzle before starting a fresh one (guest mode only).
  const currentPuzzleIdRef = useRef<string | null>(null);
  // Ref holding the solved indices for the game that's currently being loaded.
  // Set synchronously BEFORE setWords so the `words` effect in ConnectionsGame
  // always reads the value that belongs to the new game, never the previous one.
  // Using a ref (not state) avoids any React batching edge cases.
  const initialSolvedIndicesRef = useRef<number[]>([]);
  // Holds the guess list returned by the server on load, used to reconstruct
  // guessHistory when resuming a game after a page refresh.
  const initialPreviousGuessesRef = useRef<string[][]>([]);
  // Incrementing this triggers the useEffect to run again, starting a fresh game.
  const [gameKey, setGameKey] = useState<number>(0);
  // Tracks whether the current load was triggered by startNewGame (not initial load).
  const isReloadingRef = useRef<boolean>(false);

  useEffect(() => {
    // Wait for Supabase to resolve the session before initialising the game.
    // Without this guard we would treat a logged-in user as a guest during the
    // brief window while auth is loading, incorrectly writing their game ID to
    // localStorage.
    if (authLoading) return;

    /**
     * Transfers any guest session data to the authenticated user's account.
     * Called at the start of every effect run when `user` is set.
     * - If there is no guest data in localStorage, returns immediately (no-op).
     * - On success, clears the localStorage keys so the transfer never runs twice.
     * - Errors are non-fatal: we log and continue so the normal game init runs.
     */
    const transferGuestData = async () => {
      if (!user) return;

      const activeGameId = localStorage.getItem(GUEST_GAME_KEY);
      const completedPuzzleIds = getGuestCompletedPuzzleIds();

      if (!activeGameId && completedPuzzleIds.length === 0) return;

      try {
        const response = await apiPost("/claim-guest-data", {
          activeGameId: activeGameId,
          completedPuzzleIds: completedPuzzleIds,
        });
        if (response.ok) {
          // Transfer succeeded — clear guest localStorage so this never re-runs.
          localStorage.removeItem(GUEST_GAME_KEY);
          localStorage.removeItem(GUEST_COMPLETED_KEY);
        }
      } catch {
        // Non-fatal: the user will just get a fresh game as normal.
      }
    };

    /**
     * Creates a new game and returns the game ID.
     * For authenticated users the backend applies get-or-create logic, so this
     * transparently returns an existing IN_PROGRESS game when one exists.
     * For guests, passes already-completed puzzle IDs so the backend skips them.
     */
    const createNewGame = async (): Promise<string | null> => {
      try {
        // Build exclusion query param for guests — auth users are handled server-side.
        let url = "/generate-grid";
        if (!user) {
          const completedIds = getGuestCompletedPuzzleIds();
          if (completedIds.length > 0) {
            url += `?exclude=${completedIds.join(",")}`;
          }
        }
        const response = await apiGet(url);
        const jsonResponse = await response.json();
        if (response.ok && jsonResponse.data?.gameId) {
          return jsonResponse.data.gameId;
        }
        // Authenticated player has played every available puzzle.
        if (jsonResponse.code === "POOL_EXHAUSTED") {
          setPoolExhausted(true);
        }
        return null;
      } catch {
        return null;
      }
    };

    /**
     * Fetches the game state for the given game ID and hydrates local state.
     * Returns { success, status, puzzleId } so the caller can act on game completion.
     */
    const fetchGameState = async (
      id: string
    ): Promise<{ success: boolean; status?: string; puzzleId?: string | null }> => {
      try {
        const response = await apiPost("/game-status", { gameId: id });
        const jsonResponse = await response.json();

        if (response.ok && jsonResponse.data) {
          const data = jsonResponse.data;
          // Write solved indices into the ref BEFORE calling setWords.
          // The `words` effect in ConnectionsGame fires after the render triggered
          // by setWords, at which point this ref already holds the correct value.
          initialSolvedIndicesRef.current = (data.connections as any[])
            .map((conn: any, idx: number) => ({ conn, idx }))
            .filter(({ conn }: { conn: any }) => conn.guessed)
            .map(({ idx }: { idx: number }) => idx);
          initialPreviousGuessesRef.current = data.previousGuesses ?? [];
          currentPuzzleIdRef.current = data.puzzleId ?? null;
          setWords(data.grid);
          setMistakesLeft(data.mistakesLeft);
          setConnections(data.connections);
          setPuzzleNumber(data.puzzleNumber);
          return { success: true, status: data.status, puzzleId: data.puzzleId };
        }
        return { success: false };
      } catch {
        return { success: false };
      }
    };

    /**
     * Main initialization: determines the correct game session to load.
     */
    const initializeGame = async () => {
      // Transfer any in-progress or completed guest data to the user's account
      // before running game init. This ensures the backend's get-or-create
      // logic finds the claimed game when /generate-grid is called below.
      await transferGuestData();

      try {
        // Admin play-test mode: skip /generate-grid and load the pre-created
        // review game session directly. The game session was created by
        // POST /admin/puzzles/<id>/start-review-game before this hook ran.
        if (reviewGameId) {
          const result = await fetchGameState(reviewGameId);
          if (result.success) {
            setGameId(reviewGameId);
          } else {
            setError("Failed to load review game");
          }
          setLoading(false);
          return;
        }

        // Guests: attempt to resume from localStorage
        if (!user) {
          const savedId = localStorage.getItem(GUEST_GAME_KEY);
          if (savedId) {
            const result = await fetchGameState(savedId);
            if (result.success && result.status === "IN_PROGRESS") {
              setGameId(savedId);
              setLoading(false);
              return;
            }
            // Saved game is invalid, expired, or already completed — record the
            // puzzle as done (so we don't serve it again) then discard the game key.
            if (result.success && result.puzzleId) {
              markGuestPuzzleCompleted(result.puzzleId);
            }
            localStorage.removeItem(GUEST_GAME_KEY);
          }
        }

        // Authenticated users: /generate-grid does get-or-create on the backend.
        // Guests with no valid saved game: create a new session.
        const newGameId = await createNewGame();
        if (newGameId) {
          setGameId(newGameId);
          // Only persist to localStorage for guests; auth users are tracked server-side.
          if (!user) {
            localStorage.setItem(GUEST_GAME_KEY, newGameId);
          }
          await fetchGameState(newGameId);
        } else {
          setError("Failed to create a new game");
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
        // Dismiss the "Loading next puzzle" toast once the new game is ready.
        if (isReloadingRef.current) {
          toast.dismiss("next-puzzle-loading");
          isReloadingRef.current = false;
        }
      }
    };

    initializeGame();
  }, [authLoading, user, gameKey, reviewGameId, setMistakesLeft]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Starts a fresh game session. For guests, records the completed puzzle ID
   * so the next game excludes it, then clears the saved localStorage game so
   * the effect creates a new one rather than resuming the completed session.
   * For authenticated users, the backend's get-or-create logic returns a new
   * session automatically because the completed game is no longer IN_PROGRESS.
   */
  const startNewGame = () => {
    if (!user) {
      // Record the just-finished puzzle before clearing the active game key,
      // so the next call to /generate-grid can exclude it.
      markGuestPuzzleCompleted(currentPuzzleIdRef.current);
      localStorage.removeItem(GUEST_GAME_KEY);
    }
    setPoolExhausted(false);
    isReloadingRef.current = true;
    toast.loading("Loading next puzzle...", {
      toastId: "next-puzzle-loading",
      position: "top-center",
    });
    setLoading(true);
    setGameKey(k => k + 1);
  };

  /**
   * Shuffles the words in the game grid.
   * Uses the Fisher-Yates algorithm to randomly shuffle the array of words.
   */
  const shuffleWords = () => {
    setWords((prevWords) => {
      // Create a copy of the previous words array to avoid mutating the state directly
      const shuffledWords = [...prevWords];
      // Iterate over the array from the last element to the second element
      for (let i = shuffledWords.length - 1; i > 0; i--) {
        // Generate a random index from 0 to i
        const j = Math.floor(Math.random() * (i + 1));
        // Swap the elements at indices i and j
        [shuffledWords[i], shuffledWords[j]] = [
          shuffledWords[j],
          shuffledWords[i],
        ];
      }
      // Return the shuffled array to update the state
      return shuffledWords;
    });
  };

  return { words, loading, error, poolExhausted, connections, shuffleWords, gameId, puzzleNumber, startNewGame, initialSolvedIndicesRef, initialPreviousGuessesRef };
};

export default useGameState;
