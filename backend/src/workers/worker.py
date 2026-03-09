"""
Background worker: polls puzzle_generation_jobs for 'queued' jobs and
runs the full generate → validate → store pipeline.

Run as a standalone process (from /backend, with venv active):
    python -m src.workers.worker

Or via the combined entry point:
    python -m src.workers.run_workers
"""

import logging
import signal
import threading
import time
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
POLL_INTERVAL = 30  # seconds between polls when the queue is empty

# Rough Claude API call estimates per pipeline phase.
# Generation: steps 1+2+4 plus one group_generator call per group (~4 groups) = ~9-10 calls.
# Validation: 8 self-consistency attempts + devil's advocate + calibration = ~10 calls.
_API_CALLS_GENERATION = 10
_API_CALLS_VALIDATION = 10


class TokenBucket:
    """
    Simple token bucket for rate limiting Claude API calls.

    Refills at `capacity` tokens per `refill_period` seconds. Calling
    consume(n) returns the number of seconds the caller must sleep before
    n tokens become available — 0.0 when tokens are already present.
    """

    def __init__(self, capacity: int, refill_period: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_period = refill_period
        self._lock = threading.Lock()
        self._last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> float:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self.tokens = min(
                float(self.capacity),
                self.tokens + (elapsed / self.refill_period) * self.capacity,
            )
            self._last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            deficit = tokens - self.tokens
            return (deficit / self.capacity) * self.refill_period


class PuzzleWorker:
    """
    Polls puzzle_generation_jobs for queued work, runs the generation and
    validation pipeline, and updates job/puzzle status in Supabase.

    Runs in the main thread so it can own SIGINT/SIGTERM handlers.
    """

    def __init__(self):
        self._shutdown = threading.Event()
        # 10 tokens/minute matches the requested max Claude API call rate.
        self._rate_limiter = TokenBucket(capacity=10, refill_period=60.0)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received — finishing current job then stopping")
        self._shutdown.set()

    def _client(self):
        # Reuse the lazy singleton from puzzle_pool_service to avoid a
        # second Supabase connection with identical credentials.
        from src.services.puzzle_pool_service import _get_client
        return _get_client()

    def _throttle(self, estimated_calls: int):
        """Block until the token bucket allows `estimated_calls` API calls."""
        wait = self._rate_limiter.consume(estimated_calls)
        if wait > 0:
            logger.info(
                "Rate limiting: waiting %.1fs before %d estimated API calls",
                wait, estimated_calls,
            )
            time.sleep(wait)

    def _claim_job(self) -> Optional[dict]:
        """
        Fetch the oldest queued job and atomically claim it by transitioning
        to 'generating'. Returns None if no queued jobs exist or if another
        worker claimed the row first (optimistic lock).
        """
        client = self._client()

        result = (
            client.table("puzzle_generation_jobs")
            .select("*, puzzle_configs(name, num_groups, words_per_group)")
            .eq("status", "queued")
            .order("created_at")
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        job = result.data[0]
        new_attempts = job["attempts"] + 1

        # The eq("status", "queued") on the UPDATE acts as an optimistic lock:
        # if two workers race, only one will match the row.
        claim = (
            client.table("puzzle_generation_jobs")
            .update({"status": "generating", "attempts": new_attempts})
            .eq("id", job["id"])
            .eq("status", "queued")
            .execute()
        )

        if not claim.data:
            return None  # Another worker claimed it first

        job["attempts"] = new_attempts
        return job

    def _mark_failed(self, job_id: str, error: str, attempts: int):
        """Permanently fail a job or requeue it for another attempt."""
        client = self._client()
        if attempts >= MAX_ATTEMPTS:
            logger.error(
                "Job %s failed permanently after %d attempts: %s",
                job_id, attempts, error,
            )
            client.table("puzzle_generation_jobs").update(
                {"status": "failed", "error_message": error}
            ).eq("id", job_id).execute()
        else:
            logger.warning(
                "Job %s failed (attempt %d/%d), requeuing: %s",
                job_id, attempts, MAX_ATTEMPTS, error,
            )
            client.table("puzzle_generation_jobs").update(
                {"status": "queued", "error_message": error}
            ).eq("id", job_id).execute()

    def _process_job(self, job: dict):
        from src.generation.puzzle_generator import generate_puzzle
        from src.services.puzzle_pool_service import seed_puzzle_to_pool
        from src.services.validation_pipeline import validate_and_store

        client = self._client()
        job_id = job["id"]
        config = job["puzzle_configs"]
        config_name = config["name"]
        attempts = job["attempts"]

        logger.info(
            "Processing job %s (config=%s, attempt=%d/%d)",
            job_id, config_name, attempts, MAX_ATTEMPTS,
        )

        try:
            # ── Phase 1: Generate ─────────────────────────────────────────────
            self._throttle(_API_CALLS_GENERATION)

            puzzle = generate_puzzle(config={
                "num_groups": config["num_groups"],
                "words_per_group": config["words_per_group"],
            })

            if puzzle is None:
                raise RuntimeError("generate_puzzle returned None — see logs for details")

            # Convert from generate_puzzle output format to seed_puzzle_to_pool format.
            # (Pattern taken directly from puzzle_generator.py docstring.)
            seed_data = {
                "connections": [
                    {
                        "relationship": g["category_name"],
                        "words": g["words"],
                        "category_type": g.get("category_type"),
                    }
                    for g in puzzle["groups"]
                ],
                "config_name": config_name,
            }
            meta = puzzle["generation_metadata"]
            puzzle_id = seed_puzzle_to_pool(
                seed_data,
                generation_model=meta.get("model", "unknown"),
                generation_metadata=meta,
            )

            # Record the linked puzzle_id and advance to the validation phase.
            client.table("puzzle_generation_jobs").update(
                {"status": "validating", "puzzle_id": puzzle_id}
            ).eq("id", job_id).execute()

            # ── Phase 2: Validate ─────────────────────────────────────────────
            self._throttle(_API_CALLS_VALIDATION)

            report = validate_and_store(puzzle_id)
            passed = report.get("passed", False)
            score = report.get("score", 0.0)

            client.table("puzzle_generation_jobs").update({
                "status": "complete" if passed else "failed",
                "error_message": (
                    None if passed
                    else f"Validation failed (score={score:.2f})"
                ),
            }).eq("id", job_id).execute()

            if passed:
                logger.info(
                    "Job %s complete: puzzle %s approved (score=%.2f)",
                    job_id, puzzle_id, score,
                )
            else:
                logger.warning(
                    "Job %s complete: puzzle %s rejected (score=%.2f)",
                    job_id, puzzle_id, score,
                )

        except Exception:
            logger.exception("Job %s raised an unhandled exception", job_id)
            self._mark_failed(job_id, "Unhandled exception — see worker logs", attempts)

    def run(self):
        logger.info(
            "Puzzle worker started (poll_interval=%ds, max_attempts=%d)",
            POLL_INTERVAL, MAX_ATTEMPTS,
        )
        while not self._shutdown.is_set():
            try:
                job = self._claim_job()
                if job:
                    self._process_job(job)
                else:
                    logger.debug("No queued jobs — sleeping %ds", POLL_INTERVAL)
                    self._shutdown.wait(POLL_INTERVAL)
            except Exception:
                logger.exception("Unexpected error in worker loop — backing off 10s")
                self._shutdown.wait(10)

        logger.info("Puzzle worker stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    PuzzleWorker().run()
