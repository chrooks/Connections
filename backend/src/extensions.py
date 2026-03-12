"""
Shared Flask extensions.

Instantiated here (without an app) so they can be imported by both app.py
and blueprint modules without causing circular imports. app.py calls
limiter.init_app(app) to bind the instance to the running application.

Storage: in-memory by default — counters reset on restart, which is fine for
a single-process deployment. To persist limits across restarts or share them
across multiple containers, set storage_uri to a Redis URL:
    LIMITER_STORAGE_URI=redis://localhost:6379
"""

import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.getenv("LIMITER_STORAGE_URI", "memory://"),
)
