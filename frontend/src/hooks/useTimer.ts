import { useState, useEffect, useRef } from "react";

/**
 * Tracks elapsed seconds for a game session.
 *
 * - Ticks every second while `isActive` is true.
 * - Resets to 0 whenever `resetKey` changes (e.g. when a new game starts).
 * - Exposes `elapsedRef` for stale-closure-safe reads inside effects
 *   that capture `elapsed` before the final tick.
 *
 * @param isActive  - Whether the timer should be ticking right now.
 * @param resetKey  - Any value whose change signals a new game (typically gameId).
 */
const useTimer = (isActive: boolean, resetKey: string | null) => {
  const [elapsed, setElapsed] = useState<number>(0);
  // Keep a ref in sync so callers can read the latest value without
  // the stale-closure problem that affects useEffect deps.
  const elapsedRef = useRef<number>(0);
  useEffect(() => {
    elapsedRef.current = elapsed;
  }, [elapsed]);

  // Reset when a new game begins
  useEffect(() => {
    setElapsed(0);
  }, [resetKey]);

  // Tick once per second while active
  useEffect(() => {
    if (!isActive) return;
    const id = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(id);
  }, [isActive]);

  return { elapsed, elapsedRef };
};

export default useTimer;
