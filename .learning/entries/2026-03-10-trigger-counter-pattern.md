---
date: 2026-03-10
patterns: [trigger-counter, useEffect-rerun, state-machine-reset]
project: Connections
---

# Trigger Counter Pattern for Re-running useEffect

## Problem

`useEffect` in React runs when its dependencies change. For the game initialization
logic in `useGameState`, the effect runs once (when auth loads). But "Next Puzzle"
needs to re-run the exact same initialization logic on demand — without duplicating
the async setup code.

## Why a Trigger Counter Fits

A simple integer state variable acts as a "version" for the effect. Incrementing it
causes React to see a dependency change and re-run the effect. The initialization
logic itself doesn't change — only *when* it runs.

```ts
const [gameKey, setGameKey] = useState(0);

useEffect(() => {
  if (authLoading) return;
  initializeGame(); // same logic as initial load
}, [authLoading, user, gameKey]); // gameKey re-triggers on demand

const startNewGame = () => {
  if (!user) localStorage.removeItem(GUEST_GAME_KEY); // guest cleanup
  setLoading(true);
  setGameKey(k => k + 1); // triggers effect re-run
};
```

## Why Not Alternatives?

- **Extracting into a callback and calling directly**: Would require the async setup
  function to live outside `useEffect`, making cleanup and cancellation harder.
- **Remounting the component** (`key` prop on `ConnectionsGame`): Works but destroys
  all component state including animations in progress.
- **Duplicating init logic in `startNewGame`**: Violates DRY and risks drift.

## Shape Consequence

This pattern keeps the "what initializes a game" logic in one place. The game reset
in `ConnectionsGame` (the `useEffect` watching `words`) handles the downstream state
reset automatically when new words arrive from the hook.
