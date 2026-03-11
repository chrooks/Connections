import { useState, useEffect, useRef } from "react";

const TIMER_STORAGE_PREFIX = "timer:";

/**
 * Tracks elapsed seconds for a game session.
 *
 * - Ticks every second while `isActive` is true.
 * - Persists elapsed time to localStorage keyed by `resetKey` so the timer
 *   survives page refreshes and tab switches mid-game.
 * - When `resetKey` changes (new game or initial load), reads any stored value
 *   for the new key — so a refresh resumes where it left off.
 * - Exposes `elapsedRef` for stale-closure-safe reads inside effects
 *   that capture `elapsed` before the final tick.
 *
 * @param isActive  - Whether the timer should be ticking right now.
 * @param resetKey  - Any value whose change signals a new game (typically gameId).
 */
const useTimer = (isActive: boolean, resetKey: string | null) => {
  // Start at 0; the resetKey effect below will hydrate from localStorage once
  // the gameId arrives (gameId starts null and is set after the first fetch).
  const [elapsed, setElapsed] = useState<number>(0);

  // Keep a ref in sync so callers can read the latest value without
  // the stale-closure problem that affects useEffect deps.
  const elapsedRef = useRef<number>(0);
  useEffect(() => {
    elapsedRef.current = elapsed;
  }, [elapsed]);

  // Track the previous resetKey so we can clean up its localStorage entry
  // when a new game begins.
  const prevKeyRef = useRef<string | null>(null);

  // When resetKey changes (null→gameId on first load, or gameId→gameId on new game):
  //   - Remove the previous game's stored timer if there was one
  //   - Load any saved time for the new key (handles page refresh resume)
  useEffect(() => {
    if (prevKeyRef.current === resetKey) return;

    if (prevKeyRef.current) {
      // Real game transition — clean up the completed game's timer entry
      localStorage.removeItem(TIMER_STORAGE_PREFIX + prevKeyRef.current);
    }

    prevKeyRef.current = resetKey;

    if (resetKey) {
      // Resume from storage if available; otherwise start at 0
      const stored = localStorage.getItem(TIMER_STORAGE_PREFIX + resetKey);
      setElapsed(stored ? parseInt(stored, 10) : 0);
    } else {
      setElapsed(0);
    }
  }, [resetKey]);

  // Persist elapsed time to localStorage on every tick so refreshes resume correctly
  useEffect(() => {
    if (!resetKey) return;
    localStorage.setItem(TIMER_STORAGE_PREFIX + resetKey, String(elapsed));
  }, [elapsed, resetKey]);

  // Tick once per second while active
  useEffect(() => {
    if (!isActive) return;
    const id = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(id);
  }, [isActive]);

  return { elapsed, elapsedRef };
};

export default useTimer;
