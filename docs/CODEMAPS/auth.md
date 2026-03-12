# Authentication & Authorization Codemap

**Last Updated:** 2026-03-12
**Auth Provider:** Supabase Authentication (JWT)
**Frontend Auth:** Supabase JS Client + React Context
**Backend Auth:** Middleware + JWT validation

## Architecture

```
Supabase Auth
  ├─ Frontend (Supabase JS Client)
  │  ├─ Sign Up / Sign In flow
  │  ├─ JWT generation
  │  └─ Token refresh
  │
  ├─ Backend (Middleware)
  │  ├─ JWT validation
  │  ├─ User ID extraction
  │  └─ Authorization checks
  │
  └─ Guest Mode
     ├─ No auth required
     ├─ Local state tracking
     └─ Claim on sign-up
```

## Frontend Authentication (`AuthContext`)

**File:** `frontend/src/context/AuthContext.tsx`

### State Structure

```typescript
type User = {
  id: string;           // Supabase user UUID
  email: string;
  metadata?: Record<string, any>;
};

type AuthContextType = {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  signInWithProvider: (provider: "github" | "google") => Promise<void>;
};
```

### Key Functions

```typescript
const { user, loading, signIn, signUp, signOut } = useAuth();
```

**useAuth()** — Hook to access auth state and methods

**Flow:**

1. **Mount:**
   - Calls `supabase.auth.getSession()` to check for existing session
   - Sets loading=true while checking
   - If session found, parses user object

2. **Sign Up:**
   ```typescript
   await supabase.auth.signUp({
     email: "user@example.com",
     password: "securePassword"
   });
   // User receives confirmation email (optional in dev)
   // Session auto-established
   ```

3. **Sign In:**
   ```typescript
   await supabase.auth.signIn({
     email: "user@example.com",
     password: "password"
   });
   // Returns session with access_token (JWT)
   ```

4. **Sign Out:**
   ```typescript
   await supabase.auth.signOut();
   // Clears session, JWT removed
   ```

5. **Token Refresh:**
   - Automatic via Supabase client
   - Called before JWT expires (60 min default)
   - New JWT stored in localStorage

### JWT Token

**Format:** Standard Supabase JWT (RS256)

**Payload:**
```json
{
  "aud": "authenticated",
  "exp": 1678632000,
  "iat": 1678628400,
  "iss": "https://[project].supabase.co/auth/v1",
  "sub": "user-uuid",
  "email": "user@example.com",
  "email_verified": false,
  "phone_verified": false
}
```

**Stored in:** `localStorage` (Supabase JS client auto-manages)

**Sent to Backend:**
```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Backend Authentication (`middleware.py`)

**File:** `backend/src/auth/middleware.py`

### Implementation

```python
from flask import request, g
import jwt
from functools import wraps

def get_optional_user_id():
    """
    Extract user_id from JWT (None if not present).
    Sets g.user_id for request duration.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]  # Remove "Bearer "
    try:
        # Verify token with Supabase public key
        decoded = jwt.decode(
            token,
            SUPABASE_PUBLIC_KEY,
            algorithms=["RS256"],
            audience="authenticated"
        )
        user_id = decoded.get("sub")  # "sub" is user UUID
        g.user_id = user_id
        return user_id
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """
    Decorator to enforce authentication.
    Returns 401 if no valid JWT.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_optional_user_id()
        if not user_id:
            return create_response(
                error="Authentication required",
                status_code=401
            )
        return f(*args, **kwargs)
    return decorated_function
```

### Usage in Routes

```python
from ...auth.middleware import get_optional_user_id, require_auth

@api_bp.route("/generate-grid", methods=["GET"])
def generate_grid():
    user_id = get_optional_user_id()  # None for guests
    game = create_new_game(user_id=user_id)
    return create_response(data={"gameId": game["gameId"]})

@api_bp.route("/user/stats", methods=["GET"])
@require_auth
def user_stats():
    # g.user_id is guaranteed to be set
    stats = get_user_stats(g.user_id)
    return create_response(data=stats)
```

## Authorization Patterns

### 1. Optional Authentication (Guest OK)

```python
@api_bp.route("/generate-grid", methods=["GET"])
def generate_grid():
    user_id = get_optional_user_id()  # Can be None
    if user_id:
        # Authenticated user: use DB exclusions
        exclusions = get_completed_puzzle_ids_for_user(user_id)
    else:
        # Guest: use query param exclusions
        guest_exclude = request.args.get("exclude", "").split(",")
        exclusions = guest_exclude

    puzzle = get_puzzle_from_pool(config_id, exclude_ids=exclusions)
    return create_response(data={"gameId": ...})
```

**Endpoints:**
- `GET /connections/generate-grid`
- `POST /connections/submit-guess`
- `POST /connections/game-status`
- `POST /connections/restart-game`

### 2. Required Authentication

```python
@api_bp.route("/user/stats", methods=["GET"])
@require_auth
def user_stats():
    # g.user_id guaranteed to exist (enforced by decorator)
    stats = get_user_stats(g.user_id)
    return create_response(data=stats)
```

**Endpoints:**
- `GET /connections/user/stats`
- `GET /connections/user/history`
- `POST /connections/claim-guest-data`

### 3. Admin Authorization (Future Enhancement)

```python
def require_admin(f):
    """Verify user is in admin email list."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_optional_user_id()
        if not user_id:
            return create_response(error="Unauthorized", status_code=401)

        # Check email against admin list
        user_email = get_user_email(user_id)
        if user_email not in ADMIN_EMAILS:
            return create_response(error="Forbidden", status_code=403)

        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/generate-puzzles", methods=["POST"])
@require_admin
def generate_puzzles():
    # User is confirmed admin
    data = request.get_json()
    ...
```

**Admin Endpoints:**
- `POST /admin/generate-puzzles`
- `GET /admin/puzzles/rejected`
- `POST /admin/puzzles/{id}/start-review-game`
- `POST /admin/puzzles/{id}/approve`

## Guest Mode

**Frontend Flow:**

```typescript
const [isGuestMode, setIsGuestMode] = useState(false);

// User clicks "Play as Guest"
const handlePlayAsGuest = () => {
  setIsGuestMode(true);
};

// Store completed puzzle IDs locally
const [completedPuzzles, setCompletedPuzzles] = useState<string[]>([]);

// On game end (WIN or LOSS)
const handleGameEnd = (puzzleId: string) => {
  setCompletedPuzzles([...completedPuzzles, puzzleId]);
  localStorage.setItem("completedPuzzles", JSON.stringify(completedPuzzles));
};

// When starting new game
const generateGrid = async () => {
  const exclude = completedPuzzles.join(",");
  const response = await fetch(
    `/connections/generate-grid?exclude=${exclude}`,
    { method: "GET" }
  );
  const { gameId } = await response.json();
  return gameId;
};
```

**Backend Handling:**

```python
@api_bp.route("/generate-grid", methods=["GET"])
def generate_grid():
    user_id = get_optional_user_id()

    # Guest exclusions from query param
    guest_exclude: "list[str]" = []
    if not user_id:
        raw_exclude = request.args.get("exclude", "")
        if raw_exclude:
            guest_exclude = [pid.strip() for pid in raw_exclude.split(",")]

    game = create_new_game(user_id=user_id, guest_exclude_ids=guest_exclude or None)
    return create_response(data={"gameId": game["gameId"]})
```

**Guest → User Transition:**

```typescript
// After successful sign-in
const claimGuestData = async (jwtToken: string) => {
  const activeGameId = localStorage.getItem("guestGameId");
  const completedPuzzles = JSON.parse(
    localStorage.getItem("completedPuzzles") || "[]"
  );

  await fetch("/connections/claim-guest-data", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      activeGameId: activeGameId || null,
      completedPuzzleIds: completedPuzzles
    })
  });

  // Clear local storage
  localStorage.removeItem("guestGameId");
  localStorage.removeItem("completedPuzzles");
};
```

## Frontend Auth UI Components

### AuthModal

**File:** `frontend/src/components/Auth/AuthModal.tsx`

**Purpose:** Sign in / Sign up form

**Props:**
```typescript
type AuthModalProps = {
  show: boolean;
  onClose: () => void;
  onSuccess: () => void;
};
```

**Features:**
- Tab switching (Sign In / Sign Up)
- Email + password form
- Social login buttons (GitHub, Google) — optional
- Error message display
- Loading state

**Usage:**
```typescript
const [showAuthModal, setShowAuthModal] = useState(false);

<AuthModal
  show={showAuthModal}
  onClose={() => setShowAuthModal(false)}
  onSuccess={() => {
    setShowAuthModal(false);
    // Redirect to game
  }}
/>
```

### UserMenu

**File:** `frontend/src/components/Auth/UserMenu.tsx`

**Purpose:** Authenticated user dropdown menu

**Features:**
- Display user email
- Link to Profile
- Sign Out button

**Shown when:** `user !== null` (i.e., authenticated)

## Role-Based Access Control (RBAC)

**Frontend Admin Check:**

```typescript
// File: frontend/src/lib/adminUtils.ts
const ADMIN_EMAILS = ["admin@example.com"];

export function isAdminEmail(email?: string): boolean {
  return email ? ADMIN_EMAILS.includes(email) : false;
}

// In App.tsx
const isAdmin = isAdminEmail(user?.email);

// Conditionally render admin screens
{isAdmin && (
  <button onClick={() => setCurrentView("admin")}>
    Admin Panel
  </button>
)}
```

**Backend Admin Check:**

```python
# Environment variable (from .env)
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")

def is_admin(user_id: str) -> bool:
    """Check if user is in admin list."""
    user = supabase.auth.admin.get_user(user_id)
    return user.email in ADMIN_EMAILS
```

## Environment Setup

### Frontend .env

```bash
VITE_SUPABASE_URL=https://[project].supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Note:** These are public keys (no secrets)

### Backend .env

```bash
SUPABASE_URL=https://[project].supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Service role key
SUPABASE_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...   # For JWT validation
ADMIN_EMAILS=admin@example.com,admin2@example.com
```

**Note:** SUPABASE_KEY is the service role key (use for admin ops only)

## Security Considerations

### JWT Validation

**Verify token signature** with Supabase public key (RS256)

```python
import jwt

SUPABASE_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
...(from Supabase dashboard)...
-----END PUBLIC KEY-----"""

try:
    decoded = jwt.decode(
        token,
        SUPABASE_PUBLIC_KEY,
        algorithms=["RS256"],
        audience="authenticated"
    )
except jwt.InvalidTokenError:
    # Token invalid (forged, expired, etc.)
    return 401
```

### Token Expiry

- Default: 60 minutes
- Configurable in Supabase dashboard
- Frontend auto-refreshes via Supabase client
- Backend accepts expired tokens within refresh window

### HTTPS (Production)

- Always use HTTPS for token transmission
- Set Secure flag on auth cookies (Supabase handles)
- CORS configured to allow only your domain

### Row-Level Security (RLS)

**Suggested policies on game_sessions:**

```sql
-- Users can only view their own games
CREATE POLICY "Users can view own games"
ON game_sessions FOR SELECT
USING (auth.uid() = user_id);

-- Guests can view any game by checking no user_id (not recommended in prod)
-- Better: Only backend accesses via service_role key
```

### Password Requirements

- Supabase default: 6+ characters
- Configurable in Supabase dashboard
- Consider enforcing strong passwords (12+, complexity rules)

## Token Refresh Cycle

```
1. User signs in → JWT issued (exp in 60 min)
2. Token stored in localStorage
3. Frontend makes API call with JWT
4. Supabase client detects expiry approaching
5. Automatic refresh via refresh_token
6. New JWT issued, stored
7. Original API call proceeds
```

**No action needed by developer** — Supabase JS client handles automatically.

## Logout & Session Cleanup

```typescript
// Frontend
const handleLogout = async () => {
  await supabase.auth.signOut();
  // Redirects to landing page
  setUser(null);
};

// Clears:
// - localStorage session
// - JWT cookie (if used)
// - Resets auth context
```

## Multi-Device Sessions

- Each sign-in generates new JWT
- Multiple devices = multiple active sessions
- Sign out on one device clears that device's JWT
- Other devices remain logged in

**Optional:** Implement device-level session tracking in DB for auditing

## Social Login (Optional)

**Supabase supports OAuth via:**
- Google
- GitHub
- Discord
- Apple
- Twitch
- Spotify

**Setup:**
1. Register OAuth app with provider
2. Add redirect URLs in Supabase dashboard
3. In frontend, call `signInWithOAuth(provider)`

```typescript
// Example
const handleGoogleSignIn = async () => {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: 'http://localhost:5173/auth/callback'
    }
  });
};
```

## Common Issues & Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Token not sent to backend | Missing Authorization header | Check fetch config, bearer format |
| JWT decode fails | Invalid public key | Verify SUPABASE_PUBLIC_KEY in .env |
| 401 on authenticated endpoint | Expired token, not refreshed | Check Supabase client is initialized |
| Guest data not transferred | Missing claim-guest-data call | Call on sign-in success |
| Admin access denied | Email not in ADMIN_EMAILS | Add email to .env, restart backend |

## Testing Auth Flows

### Test Guest → User Transition

```python
# Backend test
def test_claim_guest_data():
    # Create guest game
    guest_game = create_new_game(user_id=None)

    # Sign up user
    user = supabase.auth.sign_up({"email": "test@example.com"})
    user_id = user.user.id

    # Claim guest data
    transfer_guest_data(
        user_id=user_id,
        active_game_id=guest_game["gameId"],
        completed_puzzle_ids=["puzzle-1", "puzzle-2"]
    )

    # Verify guest game now assigned to user
    game = get_game_from_db(guest_game["gameId"])
    assert game["user_id"] == user_id
```

### Test Admin Authorization

```python
def test_admin_only_endpoint():
    # Non-admin request → 403
    response = client.post(
        "/admin/generate-puzzles",
        json={"count": 5},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403

    # Admin request → 201
    response = client.post(
        "/admin/generate-puzzles",
        json={"count": 5},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 201
```

---

**See also:** [API Reference](api.md), [Backend Codemap](backend.md), [Frontend Codemap](frontend.md)
