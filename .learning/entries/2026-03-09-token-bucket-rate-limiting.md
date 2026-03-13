---
date: 2026-03-09
patterns: [token-bucket, rate-limiting, leaky-bucket]
project: Connections
---

# Token Bucket Rate Limiting

## Problem being solved

The puzzle generation pipeline makes ~20 Claude API calls per puzzle (generation + validation).
Running jobs back-to-back without any throttle risks hitting Anthropic's API rate limits
(requests per minute / tokens per minute), which causes 429 errors and failed jobs.

## Why the token bucket fits

A **token bucket** models your API budget as a bucket of tokens:
- The bucket has a fixed **capacity** (e.g. 10 tokens = 10 allowed API calls at once)
- It **refills** at a steady rate (10 tokens/minute)
- Each operation **consumes** tokens proportional to its cost
- If not enough tokens are available, the consumer **waits** the calculated time

This is better than a simple "sleep N seconds between requests" because it allows bursting
when tokens are available, and only throttles when the budget is actually exceeded.

```python
class TokenBucket:
    def consume(self, tokens: int = 1) -> float:
        with self._lock:
            # Refill based on elapsed time
            elapsed = time.monotonic() - self._last_refill
            self.tokens = min(
                float(self.capacity),
                self.tokens + (elapsed / self.refill_period) * self.capacity,
            )
            self._last_refill = time.monotonic()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0          # no wait needed

            deficit = tokens - self.tokens
            return (deficit / self.capacity) * self.refill_period   # seconds to wait
```

## How it's used in the worker

Rather than counting individual API calls inside the pipeline (which would require
instrumenting every Claude call), the worker estimates costs at the phase level:

```python
_API_CALLS_GENERATION = 10   # steps 1+2+4 + group generator calls
_API_CALLS_VALIDATION = 10   # 8 self-consistency + devil's advocate + calibration

def _process_job(self, job):
    self._throttle(_API_CALLS_GENERATION)   # consume before generation phase
    puzzle = generate_puzzle(...)

    self._throttle(_API_CALLS_VALIDATION)   # consume before validation phase
    report = validate_and_store(puzzle_id)
```

At 10 tokens/minute, consuming 10 then 10 means each job takes at minimum ~60 seconds
of "budget time" — which naturally spaces out jobs without requiring any external coordination.

## Threading note

The `_lock` inside the bucket is essential. Without it, two threads could both read
`self.tokens`, both see enough tokens, and both subtract — producing a negative balance
and allowing more calls than intended. The lock makes the read-modify-write atomic.
