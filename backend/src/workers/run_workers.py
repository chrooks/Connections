"""
Entry point for the background worker system.

Runs the PuzzleWorker (job processor) and PoolMonitor (pool health checker)
in the same OS process using threads.

Usage (from /backend, with venv active):
    python -m src.workers.run_workers

The worker system is intentionally separate from the Flask app so it can be
started and stopped independently without affecting API availability.

    Terminal 1:  python -m src.app          # Flask API
    Terminal 2:  python -m src.workers.run_workers   # Background workers
"""

import logging
import threading

from dotenv import load_dotenv

load_dotenv()

from src.workers.pool_monitor import PoolMonitor
from src.workers.worker import PuzzleWorker


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting worker system")

    worker = PuzzleWorker()
    monitor = PoolMonitor()

    # Pool monitor runs as a daemon thread. Daemon threads are killed
    # automatically when the main thread exits, so we don't need to join them
    # on a crash — but we do call monitor.stop() for a clean shutdown path.
    monitor_thread = threading.Thread(
        target=monitor.run,
        name="pool-monitor",
        daemon=True,
    )
    monitor_thread.start()

    try:
        # Worker runs in the main thread so it owns SIGINT/SIGTERM.
        # It blocks here until a shutdown signal is received.
        worker.run()
    finally:
        logger.info("Stopping pool monitor…")
        monitor.stop()
        monitor_thread.join(timeout=5)
        logger.info("Worker system shut down cleanly")


if __name__ == "__main__":
    main()
