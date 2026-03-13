---
date: 2026-03-13
patterns: [reverse-proxy, port-routing, deployment]
project: Connections
---

## Problem

Deploying a Flask/gunicorn app to Railway resulted in persistent 502 errors and
missing CORS headers, even after the container built and started successfully.
The deploy logs showed gunicorn running fine on port 8080.

## Why This Pattern Fits

Railway (and most PaaS platforms) use a **reverse proxy** in front of your container.
The proxy terminates the public HTTPS connection and forwards requests to your app
over plain HTTP on an internal port. Two separate port values must agree:

1. **`PORT` env var** — Railway injects this; your app binds to it (e.g. 8080)
2. **Public networking port** — configured in service settings; Railway's proxy uses
   this to forward traffic *into* the container

When these disagree, the proxy knocks on the wrong port → nothing responds → 502.
The 502 happens before Flask ever sees the request, so no CORS headers are ever added —
making it look like a CORS problem when the root cause is a port mismatch.

## The Fix

Remove the manually-set networking port in Railway settings and let Railway
auto-manage it. Both sides then agree on the same `PORT` value (8080 by default).

In the Dockerfile, use shell-form CMD with `${PORT:-8000}` so the app respects
whatever Railway injects, with a sensible local fallback:

```dockerfile
# Shell-form CMD lets the shell expand $PORT at runtime.
# JSON-array form runs the binary directly with no shell, so $PORT would be
# passed as a literal string — not what you want.
CMD gunicorn --workers 2 --bind "0.0.0.0:${PORT:-8000}" "src.app:create_app()"
```

## Key Takeaway

502 errors from Railway (or nginx/Caddy in front of any app) almost always mean
the proxy and the app disagree on the internal port. Check both the injected `PORT`
env var and the service's networking settings — they must match.
