---
date: 2026-03-09
patterns: [polling-worker, producer-consumer, background-job]
project: Connections
---

# Polling Worker Pattern

## Problem being solved

Puzzle generation is expensive (~2 minutes, ~20 LLM API calls per puzzle). It can't happen
synchronously inside a web request — a user hitting `/generate-grid` shouldn't wait 2 minutes.
The solution is to decouple *requesting* a puzzle from *generating* one.

## Why this pattern fits

The **polling worker** is the simplest form of a producer-consumer system:
- A **producer** (the pool monitor, or the admin endpoint) inserts job rows into a database table
- A **consumer** (the worker process) loops on a fixed interval, picks up jobs, and does the work

No message broker (Redis, RabbitMQ, Celery) is needed. The database *is* the queue.
This trades some latency (up to `POLL_INTERVAL` seconds before a job starts) for zero
additional infrastructure.

```python
# worker.py — the core loop
def run(self):
    while not self._shutdown.is_set():
        job = self._claim_job()         # check the queue
        if job:
            self._process_job(job)      # do the work
        else:
            self._shutdown.wait(POLL_INTERVAL)   # sleep, then check again
```

## Shape: why is it structured this way?

The worker runs in the **main thread** and owns `SIGINT`/`SIGTERM` signal handlers.
The pool monitor (a separate scheduled task) runs in a **daemon thread**.

Daemon threads die automatically when the main thread exits — so a hard kill of the process
takes the monitor down too, with no orphaned processes. The `finally` block handles the clean path:

```python
# run_workers.py
try:
    worker.run()        # blocks in main thread until signal
finally:
    monitor.stop()      # ask it to stop cleanly
    monitor_thread.join(timeout=5)
```

## What would break with a different structure

- If the worker ran in a thread instead of the main thread, signal handlers would be unreliable
  (Python only delivers signals to the main thread).
- If the monitor weren't a daemon thread, a crashed worker would leave the monitor running forever.
- If you used `time.sleep()` instead of `threading.Event.wait()`, the shutdown signal
  would have to wait out the full sleep interval before the process exits.
