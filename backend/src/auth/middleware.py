"""
Authentication middleware for validating Supabase JWT tokens.

This module provides a decorator that validates the Authorization header
containing a Supabase JWT token. It extracts the user ID and attaches it
to Flask's g object for use in route handlers.

Supports both HS256 (symmetric, older Supabase projects) and RS256
(asymmetric, newer Supabase projects) by inspecting the token header and
fetching the public key from the Supabase JWKS endpoint when needed.
"""

import os
import logging
import jwt
from jwt import PyJWKClient
from functools import wraps
from flask import request, g
from ..services.utils import create_response

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")

# Used only for HS256 tokens (older Supabase projects).
# Newer projects use RS256 and verify via JWKS — the secret is not needed for those.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    logger.warning(
        "SUPABASE_JWT_SECRET is not set. "
        "RS256 tokens will still work via JWKS; HS256 tokens will be rejected."
    )

# Lazy singleton PyJWKClient for RS256 token verification.
# Fetches and caches the public keys from Supabase's JWKS endpoint.
_jwks_client: "PyJWKClient | None" = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not SUPABASE_URL:
            raise RuntimeError(
                "SUPABASE_URL is not set — cannot fetch JWKS for RS256 token verification."
            )
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _decode_supabase_token(token: str) -> dict:
    """
    Decodes and verifies a Supabase JWT.

    Inspects the token header to determine the algorithm, then verifies with
    the appropriate key:
      - HS256 (older projects): symmetric secret from SUPABASE_JWT_SECRET
      - RS256 (newer projects): public key fetched from the JWKS endpoint

    Raises jwt.InvalidTokenError on any verification failure.
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "HS256")

    if alg == "HS256":
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )

    # Asymmetric algorithm (RS256, ES256, etc.) — verify with JWKS public key
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[alg],
        audience="authenticated",
    )


def require_auth(f):
    """
    Decorator that requires a valid Supabase JWT token in the Authorization header.

    Extracts the user ID from the token's 'sub' claim and stores it in Flask's g.user_id.
    Returns 401 if token is missing, malformed, or invalid.

    Usage:
        @api_bp.route("/protected")
        @require_auth
        def protected_route():
            user_id = g.user_id
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return create_response(error="Missing Authorization header", status_code=401)

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return create_response(error="Invalid Authorization header format", status_code=401)

        token = parts[1]

        try:
            payload = _decode_supabase_token(token)

            user_id = payload.get("sub")
            if not user_id:
                return create_response(error="Invalid token: missing user ID", status_code=401)

            g.user_id = user_id
            g.user_email = payload.get("email")

        except jwt.ExpiredSignatureError:
            return create_response(error="Token has expired", status_code=401)
        except jwt.InvalidTokenError as e:
            return create_response(error=f"Invalid token: {str(e)}", status_code=401)

        return f(*args, **kwargs)

    return decorated_function


def get_current_user_id():
    """
    Helper function to get the current authenticated user's ID from Flask's g object.

    Returns:
        str: The user ID if authenticated, None otherwise.
    """
    return getattr(g, "user_id", None)


def get_optional_user_id():
    """
    Attempts to extract user ID from Authorization header without requiring auth.

    Useful for routes that work for both authenticated and anonymous users,
    but want to link data to users when they are logged in.

    Returns:
        str: The user ID if a valid token is present, None otherwise.
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        logger.debug("get_optional_user_id: no Authorization header")
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug("get_optional_user_id: malformed Authorization header")
        return None

    token = parts[1]

    try:
        payload = _decode_supabase_token(token)
        user_id = payload.get("sub")
        logger.debug("get_optional_user_id: resolved user_id=%s", user_id)
        return user_id
    except jwt.InvalidTokenError as e:
        logger.warning("get_optional_user_id: JWT decode failed — %s", e)
        return None
