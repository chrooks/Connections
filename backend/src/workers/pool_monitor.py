"""
Pool monitor: checks approved puzzle counts every 5 minutes and queues
generation jobs to keep each config's pool above the low-water mark.

Run standalone (from /backend, with venv active):
    python -m src.workers.pool_monitor

Or via the combined entry point:
    python -m src.workers.run_workers
"""

import logging
import threading

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MONITOR_INTERVAL = 5 * 60  # seconds between health checks
LOW_WATER_MARK = 20         # queue new jobs when approved count falls below this
TARGET_POOL_SIZE = 50       # fill up to this many (approved + in-flight)


def _client():
    from src.services.puzzle_pool_service import _get_client
    return _get_client()


def _get_all_configs() -> list:
    result = _client().table("puzzle_configs").select("id, name").execute()
    return result.data or []


def _count_approved(config_id: str) -> int:
    result = (
        _client()
        .table("puzzles")
        .select("id", count="exact")
        .eq("config_id", config_id)
        .eq("status", "approved")
        .execute()
    )
    return result.count or 0


def _count_in_flight(config_id: str) -> int:
    """Count jobs that are queued, generating, or validating for a config."""
    result = (
        _client()
        .table("puzzle_generation_jobs")
        .select("id", count="exact")
        .eq("config_id", config_id)
        .in_("status", ["queued", "generating", "validating"])
        .execute()
    )
    return result.count or 0


def _queue_jobs(config_id: str, count: int) -> list:
    """Insert `count` queued generation jobs and return their IDs."""
    if count <= 0:
        return []
    rows = [{"config_id": config_id, "status": "queued"} for _ in range(count)]
    result = _client().table("puzzle_generation_jobs").insert(rows).execute()
    return [r["id"] for r in (result.data or [])]


def check_and_replenish() -> dict:
    """
    Inspect the pool for every config and queue generation jobs as needed.

    Considers both approved puzzles and in-flight jobs when deciding how many
    new jobs to queue, so it avoids piling on duplicate work.

    Returns a stats dict keyed by config name — useful for logging/monitoring.
    """
    configs = _get_all_configs()
    stats = {}

    for cfg in configs:
        config_id = cfg["id"]
        config_name = cfg["name"]

        approved = _count_approved(config_id)
        in_flight = _count_in_flight(config_id)

        # Jobs already running will eventually become approved puzzles,
        # so count them toward the target to avoid over-queuing.
        projected = approved + in_flight
        needed = max(0, TARGET_POOL_SIZE - projected)

        queued_ids = []
        if approved < LOW_WATER_MARK and needed > 0:
            queued_ids = _queue_jobs(config_id, needed)
            logger.info(
                "Pool '%s': approved=%d in_flight=%d projected=%d — queued %d new jobs",
                config_name, approved, in_flight, projected, len(queued_ids),
            )
        else:
            logger.info(
                "Pool '%s': approved=%d in_flight=%d projected=%d — healthy",
                config_name, approved, in_flight, projected,
            )

        stats[config_name] = {
            "approved": approved,
            "in_flight": in_flight,
            "queued_now": len(queued_ids),
        }

    return stats


class PoolMonitor:
    """
    Runs check_and_replenish() on a fixed interval in a background thread.

    Designed to be started from run_workers.py as a daemon thread alongside
    the main PuzzleWorker. Call stop() to request a clean shutdown.
    """

    def __init__(self, interval: int = MONITOR_INTERVAL):
        self._interval = interval
        self._shutdown = threading.Event()

    def stop(self):
        self._shutdown.set()

    def run(self):
        logger.info(
            "Pool monitor started (interval=%ds, low_water=%d, target=%d)",
            self._interval, LOW_WATER_MARK, TARGET_POOL_SIZE,
        )
        # Run immediately on startup so we don't wait a full interval before
        # the first health check.
        while not self._shutdown.is_set():
            try:
                stats = check_and_replenish()
                logger.info("Pool health snapshot: %s", stats)
            except Exception:
                logger.exception("Pool monitor encountered an error during check")
            self._shutdown.wait(self._interval)

        logger.info("Pool monitor stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    PoolMonitor().run()
