"""
Scheduler Module for Controlled Background Refresh and Manual Triggers.
Maintains state, prevents overlapping runs via thread-safe lock,
and coordinates timed refreshes with SQLite audit logging.
"""

import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

import config
import scraper

logger = logging.getLogger("AgriPriceTracker.Scheduler")

class ScrapeScheduler:
    """Thread-safe background scheduler for market price collection."""
    
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ScrapeScheduler, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.is_active = False
        self.is_job_running = False
        self.interval_minutes = config.DEFAULT_REFRESH_INTERVAL_MINUTES
        self.source_mode = config.DEFAULT_SOURCE_MODE
        self.last_run_time: Optional[datetime] = None
        self.next_run_time: Optional[datetime] = None
        self.last_run_result: Optional[Dict[str, Any]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._execution_lock = threading.Lock()

    def start(self, interval_minutes: int = 60, source_mode: str = config.DEFAULT_SOURCE_MODE) -> None:
        """Starts background periodic execution."""
        if self.is_active:
            logger.info("Scheduler already active.")
            return

        self.interval_minutes = max(config.MIN_REFRESH_INTERVAL_MINUTES, interval_minutes)
        self.source_mode = source_mode
        self.is_active = True
        self._stop_event.clear()
        
        self.next_run_time = datetime.now(timezone.utc) + timedelta(minutes=self.interval_minutes)
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AgriPriceScheduler")
        self._thread.start()
        logger.info(f"Scheduler started with interval {self.interval_minutes}m, mode: {self.source_mode}")

    def stop(self) -> None:
        """Stops background periodic execution."""
        if not self.is_active:
            return
        self.is_active = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.next_run_time = None
        logger.info("Scheduler stopped.")

    def trigger_now(self, source_mode: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Executes an immediate manual collection run."""
        mode = source_mode or self.source_mode
        with self._execution_lock:
            self.is_job_running = True
            try:
                adapter = scraper.get_adapter(mode=mode, **kwargs)
                result = adapter.run_pipeline()
                self.last_run_time = datetime.now(timezone.utc)
                if self.is_active:
                    self.next_run_time = self.last_run_time + timedelta(minutes=self.interval_minutes)
                self.last_run_result = result
                return result
            finally:
                self.is_job_running = False

    def _run_loop(self) -> None:
        """Internal polling loop."""
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            if self.next_run_time and now >= self.next_run_time:
                try:
                    self.trigger_now()
                except Exception as ex:
                    logger.error(f"Scheduled run error: {ex}", exc_info=True)
            self._stop_event.wait(timeout=10.0)

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "is_job_running": self.is_job_running,
            "interval_minutes": self.interval_minutes,
            "source_mode": self.source_mode,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "last_result": self.last_run_result
        }

# Global singleton instance
scheduler_instance = ScrapeScheduler()
