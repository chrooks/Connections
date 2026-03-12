# Frontend Codemap

**Last Updated:** 2026-03-12
**Entry Points:** `frontend/src/main.tsx`, `frontend/src/components/App/App.tsx`
**Tech Stack:** React 18 + TypeScript + Vite + Supabase JS Client + SCSS + Bootstrap 5

## Architecture Overview

```
main.tsx (entry)
  ↓
App.tsx (view router)
  ├─ LandingPage (unauthenticated)
  ├─ ConnectionsGame (main game loop)
  │  ├─ GameGrid (4x4 word cards)
  │  ├─ ControlButtonBar (submit, deselect, shuffle)
  │  ├─ ResultsModal (win/loss reveal)
  │  ├─ MistakeTracker (visual feedback)
  │  └─ SolvedConnections (category reveal)
  ├─ ProfileScreen (user stats & history)
  ├─ AdminScreen (puzzle management - admin only)
  │  ├─ PuzzleReviewCard (rejected puzzles)
  │  └─ PuzzleEditor (create/edit puzzles)
  └─ Navbar (top nav with auth)
     ├─ HelpButton
     ├─ SettingsButton
     ├─ AuthModal (sign in/up)
     └─ UserMenu (logout, profile)

Context Providers:
  ├─ AuthContext (user state, login/logout)
  └─ SelectedWordsContext (game grid selection state)
```

## Key Modules

| Module | Purpose | Exports | Dependencies |
|--------|---------|---------|--------------|
| `App.tsx` | View routing, mode switching | `App` component | React, AuthContext, all screens |
| `AuthContext.tsx` | User session state | `useAuth()`, `AuthProvider` | Supabase, React |
| `SelectedWordsContext.tsx` | Game grid selection | `useSelectedWords()` | React Context |
| `ConnectionsGame.tsx` | Main game loop | `ConnectionsGame` component | Game API, context, modals |
| `GameGrid.tsx` | 4x4 word card grid | `GameGrid` component | WordCard, SelectedWordsContext |
| `WordCard.tsx` | Individual word button | `WordCard` component | SelectedWordsContext |
| `ResultsModal.tsx` | Win/loss screen | `ResultsModal` component | React Bootstrap |
| `AdminScreen.tsx` | Puzzle review & approval | `AdminScreen` component | Puzzle API calls |
| `PuzzleEditor.tsx` | Create/edit puzzles manually | `PuzzleEditor` component | Backend API |
| `Navbar.tsx` | Top navigation | `Navbar` component | AuthContext, routes |

## State Management

### Global State (Context)

**AuthContext**
- User object (email, id, metadata)
- Loading state
- Sign in/out functions
- Guest mode flag

**SelectedWordsContext**
- Selected word indices (0-3 per selection)
- Selection reset function
- Word order preservation

### Local Component State

**ConnectionsGame**
- gameId
- gameState (grid, guesses, mistakes)
- UI modes (playing, won, lost, loading)
- Animation states (nudge, swap, fade)

**AdminScreen**
- Tab selection (rejected/approved)
- Pagination for puzzle list
- Filters (validation score, date)

## Data Flow

### Game Start
```
1. User clicks "Play" (LandingPage or guest mode)
2. ConnectionsGame mounts → calls /connections/generate-grid
3. Backend returns gameId
4. Frontend calls /connections/game-status to fetch full state
5. GameGrid renders 16-word cards
```

### Guess Submission
```
1. Player selects 4 words → SelectedWordsContext tracks indices
2. Player clicks Submit → /connections/submit-guess
3. Backend validates & returns {isCorrect, mistakesLeft, status}
4. Frontend:
   - If correct: animate card slide, update guessed connections
   - If incorrect: nudge cards, decrement mistakes
5. If mistakes=0 or all found: show ResultsModal
```

### Admin Puzzle Review
```
1. Admin navigates to AdminScreen
2. Fetch /admin/puzzles/rejected with filters
3. Admin clicks "Play Test" on puzzle
4. Create game session from rejected puzzle ID
5. Admin plays through to validate
6. Admin clicks approve → /admin/puzzles/{id}/approve
7. Puzzle moves to approved pool
```

## Component Hierarchy

```
App (top-level router)
├── Navbar
│   ├── HelpButton
│   ├── SettingsButton
│   ├── AuthModal
│   └── UserMenu
├── (conditional screens)
│   ├── LandingPage
│   ├── ConnectionsGame
│   │   ├── GameGrid
│   │   │   └── WordCard (x16)
│   │   ├── ControlButtonBar
│   │   │   ├── ShuffleButton
│   │   │   ├── DeselectButton
│   │   │   └── SubmitButton
│   │   ├── MistakeTracker
│   │   │   └── MistakeBubble (x4)
│   │   ├── SolvedConnection (x0-4)
│   │   ├── ResultsModal
│   │   └── PuzzleTimer
│   ├── ProfileScreen
│   │   └── GameHistoryModal
│   ├── AdminScreen
│   │   ├── PuzzleReviewCard (x10-20)
│   │   └── (puzzle list pagination)
│   └── PuzzleEditor
└── (providers)
    ├── AuthContext
    └── SelectedWordsContext
```

## API Integration Points

All game API calls made via `/connections/*` endpoints:

| Function | Endpoint | Purpose |
|----------|----------|---------|
| `generateGrid()` | GET `/generate-grid` | Start new game |
| `getGameStatus()` | POST `/game-status` | Fetch current state |
| `submitGuess()` | POST `/submit-guess` | Submit 4-word guess |
| `restartGame()` | POST `/restart-game` | New puzzle, same session |
| `forfeitGame()` | POST `/forfeit-game` | Voluntary give-up |
| `recordCompletionTime()` | POST `/record-completion-time` | Log elapsed time |
| `getUserStats()` | GET `/user/stats` | Aggregate win/loss counts |
| `getUserHistory()` | GET `/user/history` | All completed games |
| `claimGuestData()` | POST `/claim-guest-data` | Transfer guest → user |

Admin endpoints (admin only):
| Function | Endpoint | Purpose |
|----------|----------|---------|
| `getRejectedPuzzles()` | GET `/admin/puzzles/rejected` | List rejected puzzles |
| `startReviewGame()` | POST `/admin/puzzles/{id}/start-review-game` | Play & review |
| `approvePuzzle()` | POST `/admin/puzzles/{id}/approve` | Human override approve |
| `getPuzzle()` | GET `/admin/puzzles/{id}` | Fetch puzzle details |
| `savePuzzle()` | POST `/admin/puzzles` | Create/update puzzle |

## Authentication Flow

**Sign In**
```
1. User clicks Auth button → AuthModal
2. Modal uses Supabase Auth UI (or custom form)
3. On success: AuthContext stores user & JWT
4. App switches from landing page to game
5. All subsequent requests include JWT in header
```

**Guest Mode**
```
1. User clicks "Play as Guest"
2. isGuestMode = true (local state only)
3. API requests omit user_id
4. Pool treats guest as new player
5. On sign-up: claimGuestData() transfers completedPuzzleIds
```

**Admin Access**
```
1. User signs in with admin email (checked via isAdminEmail())
2. AdminScreen & PuzzleEditor tabs become visible
3. Admin endpoints require valid JWT
4. Backend verifies user_id against admin list
```

## Styling & Theming

**Framework:** SCSS + Bootstrap 5 + react-bootstrap

**Key stylesheets:**
- `/src/App.scss` — Global styles, game grid layout
- `/src/components/*/[Component].scss` — Component-specific styles

**Design Principles:**
- Responsive grid (flex/grid for word cards)
- Bootstrap classes for buttons, modals, forms
- Custom SCSS for animations (nudge, swap, fade, slide)
- Light/dark mode support (WIP)

## Performance Considerations

**Code Splitting:**
- `ConnectionsGame` lazy-loaded when not on landing
- Admin screens only load for authenticated users

**API Calls:**
- Batch user stats/history in ProfileScreen (single endpoint)
- Debounce shuffle (prevent spam requests)
- Cache game state locally until backend confirms

**Animations:**
- CSS transitions (prefer `transform` & `opacity` over layout shifts)
- Framer Motion or CSS keyframes for complex sequences

## Common Tasks

### Adding a New Game Screen
1. Create component in `/src/components/[ScreenName]/`
2. Add view type to `AppView` union in `App.tsx`
3. Add conditional render and state setter
4. Connect navigation via Navbar callbacks

### Adding a Game Feature
1. Define new endpoint in backend (`/connections/[feature]`)
2. Create API client function in `/src/lib/api.ts` (or similar)
3. Call from component, store result in local state
4. Add unit tests

### Admin Features
1. Create component in `/src/components/AdminScreen/`
2. Guard with `isAdminEmail()` check
3. Call `/admin/*` endpoints
4. Validate responses before state update

## External Dependencies

- `react@18.x` — UI framework
- `react-bootstrap@2.x` — Bootstrap component wrapper
- `typescript@5.x` — Type safety
- `vite@5.x` — Build tool
- `supabase@2.x` — Auth & API client
- `scss` (via vite) — Styling
- `axios` or `fetch` — HTTP (check package.json for actual)

---

**See also:** [Backend Codemap](backend.md), [API Reference](api.md), [Database Schema](database.md)
