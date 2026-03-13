---
date: 2026-03-09
patterns: [react-state, hot-module-replacement, state-initialization, derived-state]
project: Connections
---

# Problem: React State Desync After Vite HMR

## The Problem

During development, submitting a guess returned "All words in the guess must be in the game grid" — the backend correctly rejected the submission because the words being sent didn't match the stored game session.

## Why It Happened

Three parts interact:

1. **Module-level variable for game ID** — `useGameState` uses a module-level `let currentGameId = null` that persists within a JS module instance.
2. **Vite HMR with React Fast Refresh** — when you save a file, HMR _reloads the module_ (resetting `currentGameId → null`) but _preserves React component state_ (`gridWords`, `gameId`, `words` all stay set from before).
3. **A guard that prevents re-initialization** — `if (words.length > 0 && gridWords.length === 0)` meant `gridWords` was only ever set once per component lifecycle.

**Sequence of failure:**
```
HMR fires → module reloads → currentGameId = null
React state preserved: gameId="abc", words=grid_abc, gridWords=grid_abc
initializeGame() sees currentGameId=null → creates NEW game "xyz"
setGameId("xyz"), setWords(grid_xyz)
gridWords sync effect: words.length > 0 BUT gridWords.length > 0 → skipped!
Result: gameId="xyz" + words=grid_xyz, but gridWords=grid_abc (stale!)
User submits grid_abc words with gameId "xyz" → backend rejects
```

## The Fix

Remove `&& gridWords.length === 0` from the guard. Use only `words` in the dependency array so `gridWords` always resets whenever a new game's words arrive:

```typescript
// Before
useEffect(() => {
  if (words.length > 0 && gridWords.length === 0) {
    setGridWords(words);
  }
}, [words, gridWords.length]);

// After — resets all game state when words change (new game)
useEffect(() => {
  if (words.length > 0) {
    setGridWords(words);
    setSolvedOrder([]);
    setGuessHistory([]);
    setGameComplete(false);
    setGameResult(null);
    setShowEndScreen(false);
  }
}, [words]);
```

This is safe because `words` is set by `fetchGameState` (called once on init) and never mutated by shuffling — `handleShuffle` updates `gridWords` directly, leaving `words` unchanged. So the effect only triggers when a genuinely new game is fetched.

## Key Lesson

When React state is initialized from an async source (backend fetch), guard conditions like `&& someState.length === 0` work fine in production but break under HMR. The fix is to make the initialization idempotent (safe to re-run) by tracking the *source of truth* (`words` from the fetch) rather than the derived state (`gridWords`).
