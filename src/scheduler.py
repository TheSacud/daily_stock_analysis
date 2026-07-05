# -*- coding: utf-8 -*-
"""
===================================
\u5b9a\u65f6\u8c03\u5ea6\u6a21chunks
===================================

\u804c\u8d23:
1. \u652f\u6301\u6bcf\u65e5\u5b9a\u65f6\u6267\u884c\u80a1\u7968analyze
2. \u652f\u6301\u5b9a\u65f6\u6267\u884cmarket review
3. \u4f18\u96c5\u5904\u7406\u4fe1\u53f7; \u786e\u4fdd\u53ef\u9760\u9000\u51fa

\u4f9d\u8d56:
- schedule: \u8f7b\u91cf\u7ea7scheduled tasklibrary
"""

import logging
import re
import signal
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)


def normalize_schedule_times(
    schedule_times: Optional[Union[Sequence[str], str]],
    *,
    fallback_time: str = "18:00",
) -> List[str]:
    """Return sorted unique HH:MM schedule times with SCHEDULE_TIME fallback."""
    if isinstance(schedule_times, str):
        raw_items = [item.strip() for item in schedule_times.split(",")]
    elif schedule_times is None:
        raw_items = []
    else:
        raw_items = [str(item).strip() for item in schedule_times]

    valid = {
        item
        for item in raw_items
        if item and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item)
    }
    if not valid:
        fallback = (fallback_time or "18:00").strip() or "18:00"
        valid.add(fallback if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", fallback) else "18:00")
    return sorted(valid)


class GracefulShutdown:
    """
    \u4f18\u96c5\u9000\u51fa\u5904\u7406\u5668

    \u6355\u83b7 SIGTERM/SIGINT \u4fe1\u53f7; \u786e\u4fddtask\u5b8c\u6210\u540e\u518d\u9000\u51fa
    """

    def __init__(self, register_signals: bool = True):
        self.shutdown_requested = False
        self._lock = threading.Lock()
        if not register_signals:
            return

        # \u6ce8\u518c\u4fe1\u53f7\u5904\u7406\u5668
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """\u4fe1\u53f7\u5904\u7406\u51fd\u6570"""
        with self._lock:
            if not self.shutdown_requested:
                logger.info(f"received\u9000\u51fa\u4fe1\u53f7 ({signum}); waiting\u5f53\u524dtask\u5b8c\u6210...")
                self.shutdown_requested = True

    @property
    def should_shutdown(self) -> bool:
        """\u68c0check\u662f\u5426\u5e94\u8be5\u9000\u51fa"""
        with self._lock:
            return self.shutdown_requested


class Scheduler:
    """
    scheduled task\u8c03\u5ea6\u5668

    \u57fa\u4e8e schedule library\u5b9e\u73b0; \u652f\u6301:
    - \u6bcf\u65e5\u5b9a\u65f6\u6267\u884c
    - run immediately on startup
    - \u4f18\u96c5\u9000\u51fa
    """

    def __init__(
        self,
        schedule_time: str = "18:00",
        schedule_time_provider: Optional[Callable[[], str]] = None,
        schedule_times: Optional[Sequence[str]] = None,
        schedule_times_provider: Optional[Callable[[], Union[Sequence[str], str]]] = None,
        register_signals: bool = True,
    ):
        """
        \u521d\u59cb\u5316\u8c03\u5ea6\u5668

        Args:
            schedule_time: daily run time; \u683c\u5f0f "HH:MM"
        """
        try:
            import schedule
            self.schedule = schedule
        except ImportError:
            logger.error("schedule library is not installed; \u8bf7\u6267\u884c: pip install schedule")
            raise ImportError("please install schedule library: pip install schedule")

        self.schedule_time = schedule_time
        self.schedule_times = (
            normalize_schedule_times(schedule_times, fallback_time=schedule_time)
            if schedule_times is not None
            else [(schedule_time or "").strip()]
        )
        self._schedule_time_provider = schedule_time_provider
        self._schedule_times_provider = schedule_times_provider
        self.shutdown_handler = GracefulShutdown(register_signals=register_signals)
        self._task_callback: Optional[Callable] = None
        self._daily_job: Optional[Any] = None
        self._daily_jobs: List[Any] = []
        self._background_tasks: List[Dict[str, Any]] = []
        self._running = False

    def set_daily_task(self, task: Callable, run_immediately: bool = True):
        """
        \u8bbe\u7f6e\u6bcf\u65e5scheduled task

        Args:
            task: \u8981\u6267\u884c\u7684task\u51fd\u6570 (\u65e0parameter)
            run_immediately: \u662f\u5426\u5728\u8bbe\u7f6e\u540e\u7acb\u5373\u6267\u884c\u4e00\u6b21
        """
        self._task_callback = task
        if not self._configure_daily_tasks(self.schedule_times):
            raise ValueError(f"invalid scheduled run time: {self.schedule_time!r}")

        if run_immediately:
            logger.info("\u7acb\u5373\u6267\u884c\u4e00\u6b21task...")
            self._safe_run_task()

    @staticmethod
    def _is_valid_schedule_time(schedule_time: str) -> bool:
        """Validate time string in HH:MM 24-hour format."""
        candidate = (schedule_time or "").strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", candidate):
            return False
        return True

    def _cancel_daily_job(self) -> None:
        """Remove the currently registered daily job if one exists."""
        if self._daily_job is None and not self._daily_jobs:
            return

        for job in list(self._daily_jobs or [self._daily_job]):
            if job is None:
                continue
            if hasattr(self.schedule, "cancel_job"):
                self.schedule.cancel_job(job)
            else:  # pragma: no cover - compatibility fallback
                jobs = getattr(self.schedule, "jobs", None)
                if isinstance(jobs, list) and job in jobs:
                    jobs.remove(job)

        self._daily_job = None
        self._daily_jobs = []

    def _configure_daily_task(self, schedule_time: str) -> bool:
        """(Re)register the daily job at the requested time."""
        candidate = (schedule_time or "").strip()
        if not self._is_valid_schedule_time(candidate):
            logger.warning(
                "\u68c0\u6d4b\u5230invalid scheduled run time %r; \u7ee7\u7eed\u6cbf\u7528\u5f53\u524d\u65f6\u95f4 %s",
                schedule_time,
                self.schedule_time,
            )
            return False

        previous_time = self.schedule_time
        self._cancel_daily_job()
        self._daily_job = self.schedule.every().day.at(candidate).do(self._safe_run_task)
        self.schedule_time = candidate

        if previous_time == candidate:
            logger.info("\u5df2\u8bbe\u7f6e\u6bcf\u65e5scheduled task; \u6267\u884c\u65f6\u95f4: %s", self.schedule_time)
        else:
            logger.info(
                "\u68c0\u6d4b\u5230 SCHEDULE_TIME \u53d8\u66f4; \u5df2\u5c06\u6bcf\u65e5scheduled task\u4ece %s \u66f4\u65b0\u4e3a %s",
                previous_time,
                self.schedule_time,
            )
        return True

    def _refresh_daily_schedule_if_needed(self) -> None:
        """Reload daily schedule time from the latest runtime config if needed."""
        if self._task_callback is None or self._schedule_time_provider is None:
            return

        try:
            latest_schedule_time = (self._schedule_time_provider() or "").strip()
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.warning("\u8bfb\u53d6\u6700\u65b0 SCHEDULE_TIME failed; \u7ee7\u7eed\u6cbf\u7528 %s: %s", self.schedule_time, exc)
            return

        if not latest_schedule_time or latest_schedule_time == self.schedule_time:
            return

        if self._configure_daily_task(latest_schedule_time):
            logger.info("\u66f4\u65b0\u540e\u7684\u4e0b\u6b21\u6267\u884c\u65f6\u95f4: %s", self._get_next_run_time())

    def _configure_daily_tasks(self, schedule_times: Union[Sequence[str], str]) -> bool:
        """(Re)register daily jobs at the requested times."""
        raw_items = (
            [item.strip() for item in schedule_times.split(",")]
            if isinstance(schedule_times, str)
            else [str(item).strip() for item in schedule_times]
        )
        invalid_items = [item for item in raw_items if item and not self._is_valid_schedule_time(item)]
        if invalid_items:
            logger.warning(
                "Invalid schedule time values %r; keeping current times %s",
                invalid_items,
                ",".join(self.schedule_times),
            )
            return False

        candidates = normalize_schedule_times(raw_items, fallback_time=self.schedule_time)
        previous_times = list(self.schedule_times)
        self._cancel_daily_job()
        self._daily_jobs = [
            self.schedule.every().day.at(candidate).do(self._safe_run_task)
            for candidate in candidates
        ]
        self._daily_job = self._daily_jobs[0] if self._daily_jobs else None
        self.schedule_times = candidates
        self.schedule_time = candidates[0] if candidates else "18:00"

        if previous_times == candidates:
            logger.info("Daily scheduled jobs configured at: %s", ",".join(self.schedule_times))
        else:
            logger.info(
                "Schedule times changed from %s to %s",
                ",".join(previous_times),
                ",".join(self.schedule_times),
            )
        return True

    def _refresh_daily_schedule_if_needed(self) -> None:
        """Reload daily schedule times from the latest runtime config if needed."""
        if self._task_callback is None:
            return

        try:
            if self._schedule_times_provider is not None:
                latest_schedule_times = self._schedule_times_provider()
            elif self._schedule_time_provider is not None:
                latest_schedule_times = [(self._schedule_time_provider() or "").strip()]
            else:
                return
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.warning(
                "Failed to read latest schedule times; keeping %s: %s",
                ",".join(self.schedule_times),
                exc,
            )
            return

        latest = normalize_schedule_times(latest_schedule_times, fallback_time=self.schedule_time)
        if latest == self.schedule_times:
            return

        if self._configure_daily_tasks(latest):
            logger.info("Schedule refreshed; next run: %s", self._get_next_run_time())

    def refresh_daily_schedule_if_needed(self) -> None:
        """Public wrapper for runtime scheduler reconciliation."""
        self._refresh_daily_schedule_if_needed()

    def _safe_run_task(self):
        """\u5b89\u5168\u6267\u884ctask (\u5e26\u5f02\u5e38\u6355\u83b7)"""
        if self._task_callback is None:
            return

        try:
            logger.info("=" * 50)
            logger.info(f"scheduled taskstarting - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 50)

            self._task_callback()

            logger.info(f"scheduled taskcompleted - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            logger.exception(f"scheduled taskexecution failed: {e}")

    def add_background_task(
        self,
        task: Callable,
        interval_seconds: int,
        run_immediately: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """Register a periodic background task executed inside the scheduler loop.

        Note: The scheduler loop polls every 30 seconds, so *interval_seconds*
        below 30 will be clamped to 30 to avoid promising unreachable precision.
        """
        clamped_interval = max(30, int(interval_seconds))
        if int(interval_seconds) < 30:
            logger.warning(
                "\u540e\u53f0task %s request\u95f4\u9694 %ds; \u4f46\u8c03\u5ea6\u5faa\u73af\u6bcf 30s \u8f6e\u8be2\u4e00\u6b21; \u5df2\u81ea\u52a8\u8c03\u6574\u4e3a 30s",
                name or getattr(task, "__name__", "background_task"),
                interval_seconds,
            )
        entry = {
            "task": task,
            "interval_seconds": clamped_interval,
            "last_run": 0.0,
            "name": name or getattr(task, "__name__", "background_task"),
            "thread": None,
            "running": False,
        }
        if not run_immediately:
            entry["last_run"] = time.time()
        self._background_tasks.append(entry)
        logger.info(
            "registered\u540e\u53f0task: %s (\u95f4\u9694 %s \u79d2; \u7acb\u5373\u6267\u884c=%s)",
            entry["name"],
            entry["interval_seconds"],
            run_immediately,
        )
        if run_immediately:
            self._start_background_task(entry)

    def _start_background_task(self, entry: Dict[str, Any]) -> bool:
        """Start one background task in a dedicated daemon thread."""
        worker = entry.get("thread")
        if worker is not None and worker.is_alive():
            return False

        def _runner() -> None:
            try:
                logger.info("\u540e\u53f0taskstarting: %s", entry["name"])
                entry["task"]()
            except Exception as exc:
                logger.exception("\u540e\u53f0taskexecution failed [%s]: %s", entry["name"], exc)
            finally:
                entry["running"] = False
                entry["thread"] = None

        entry["last_run"] = time.time()
        entry["running"] = True
        worker = threading.Thread(
            target=_runner,
            daemon=True,
            name=f"scheduler-bg-{entry['name']}",
        )
        entry["thread"] = worker
        worker.start()
        return True

    def _run_background_tasks(self) -> None:
        """Execute any background tasks whose interval has elapsed."""
        if not self._background_tasks:
            return

        now = time.time()
        for entry in self._background_tasks:
            worker = entry.get("thread")
            if worker is not None and worker.is_alive():
                continue
            if entry.get("running"):
                entry["running"] = False
                entry["thread"] = None
            if now - entry["last_run"] < entry["interval_seconds"]:
                continue
            self._start_background_task(entry)

    def run(self):
        """
        \u8fd0\u884c\u8c03\u5ea6\u5668\u4e3b\u5faa\u73af

        \u963b\u585e\u8fd0\u884c; \u76f4\u5230received\u9000\u51fa\u4fe1\u53f7
        """
        self._running = True
        logger.info("\u8c03\u5ea6\u5668\u5f00\u59cb\u8fd0\u884c...")
        logger.info(f"\u4e0b\u6b21\u6267\u884c\u65f6\u95f4: {self._get_next_run_time()}")

        while self._running and not self.shutdown_handler.should_shutdown:
            self._refresh_daily_schedule_if_needed()
            self.schedule.run_pending()
            self._run_background_tasks()
            time.sleep(30)  # \u6bcf30\u79d2\u68c0check\u4e00\u6b21

            # \u6bcf\u5c0f\u65f6\u6253\u5370\u4e00\u6b21\u5fc3\u8df3
            if datetime.now().minute == 0 and datetime.now().second < 30:
                logger.info(f"\u8c03\u5ea6\u5668\u8fd0\u884cMedium... \u4e0b\u6b21\u6267\u884c: {self._get_next_run_time()}")

        logger.info("\u8c03\u5ea6\u5668\u5df2\u505c\u6b62")

    def _get_next_run_time(self) -> str:
        """\u83b7\u53d6\u4e0b\u6b21\u6267\u884c\u65f6\u95f4"""
        jobs = self.schedule.get_jobs()
        if jobs:
            next_run = min(job.next_run for job in jobs)
            return next_run.strftime('%Y-%m-%d %H:%M:%S')
        return "\u672a\u8bbe\u7f6e"

    def stop(self):
        """\u505c\u6b62\u8c03\u5ea6\u5668"""
        self._running = False
        self._cancel_daily_job()


def run_with_schedule(
    task: Callable,
    schedule_time: str = "18:00",
    run_immediately: bool = True,
    background_tasks: Optional[List[Dict[str, Any]]] = None,
    schedule_time_provider: Optional[Callable[[], str]] = None,
    schedule_times: Optional[Sequence[str]] = None,
    schedule_times_provider: Optional[Callable[[], Union[Sequence[str], str]]] = None,
):
    """
    \u4fbf\u6377\u51fd\u6570: \u4f7f\u7528\u5b9a\u65f6\u8c03\u5ea6\u8fd0\u884ctask

    Args:
        task: \u8981\u6267\u884c\u7684task\u51fd\u6570
        schedule_time: daily run time
        run_immediately: \u662f\u5426\u7acb\u5373\u6267\u884c\u4e00\u6b21
        background_tasks: optional\u7684\u540e\u53f0task\u5b9a\u4e49\u5217\u8868.\u6bcf\u9879\u4e3a\u4e00\u4e2a\u5b57\u5178;
            \u9700\u5305\u542b `task` \u4e0e `interval_seconds`; optional\u5305\u542b `name`
            \u548c `run_immediately`.`interval_seconds` \u5355characters\u4e3a\u79d2.
        schedule_time_provider: optional\u7684\u65f6\u95f4\u63d0\u4f9b\u5668；\u8c03\u5ea6\u5668\u6bcf\u8f6e\u68c0check\u524d\u4f1a\u8bfb\u53d6;
            \u5f53\u8fd4\u56de\u503c\u53d8\u5316\u65f6\u81ea\u52a8\u91cd\u5efa daily job.
    """
    scheduler_kwargs: Dict[str, Any] = {
        "schedule_time": schedule_time,
        "schedule_time_provider": schedule_time_provider,
    }
    if schedule_times is not None:
        scheduler_kwargs["schedule_times"] = schedule_times
    if schedule_times_provider is not None:
        scheduler_kwargs["schedule_times_provider"] = schedule_times_provider
    scheduler = Scheduler(**scheduler_kwargs)
    for entry in background_tasks or []:
        scheduler.add_background_task(
            task=entry["task"],
            interval_seconds=entry["interval_seconds"],
            run_immediately=entry.get("run_immediately", False),
            name=entry.get("name"),
        )
    scheduler.set_daily_task(task, run_immediately=run_immediately)
    scheduler.run()


if __name__ == "__main__":
    # \u6d4b\u8bd5\u5b9a\u65f6\u8c03\u5ea6
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    )

    def test_task():
        print(f"task\u6267\u884cMedium... {datetime.now()}")
        time.sleep(2)
        print("task\u5b8c\u6210!")

    print("started\u6d4b\u8bd5\u8c03\u5ea6\u5668 (press Ctrl+C to exit)")
    run_with_schedule(test_task, schedule_time="23:59", run_immediately=True)
