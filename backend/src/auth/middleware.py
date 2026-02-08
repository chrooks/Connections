"""
Authentication middleware for validating Supabase JWT tokens.

This module provides a decorator that validates the Authorization header
containing a Supabase JWT token. It extracts the user ID and attaches it
to Flask's g object for use in route handlers.
"""

import os
import jwt
from functools import wraps
from flask import request, g
from ..services.utils import create_response


# Load JWT secret from environment - used to validate Supabase tokens
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


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
        # Extract the Authorization header from the request
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return create_response(error="Missing Authorization header", status_code=401)

        # Expect format: "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return create_response(error="Invalid Authorization header format", status_code=401)

        token = parts[1]

        try:
            # Decode and validate the JWT using Supabase's HS256 algorithm
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )

            # Extract user ID from the 'sub' claim (standard JWT subject field)
            user_id = payload.get("sub")
            if not user_id:
                return create_response(error="Invalid token: missing user ID", status_code=401)

            # Store user info in Flask's g object for access in route handlers
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
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None
