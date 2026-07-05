# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis system - \u5f02\u6b65taskqueue
===================================

\u804c\u8d23:
1. \u7ba1\u7406\u5f02\u6b65analysis task\u7684\u751f\u547d\u5468\u671f
2. \u9632\u6b62\u76f8\u540cstock code\u91cd\u590d\u63d0\u4ea4
3. \u63d0\u4f9b SSE \u4e8b\u4ef6\u5e7f\u64ad\u673a\u5236
4. task\u5b8c\u6210\u540e\u6301\u4e45\u5316\u5230\u6570\u636elibrary
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any, TYPE_CHECKING, Tuple, Literal, Callable

if TYPE_CHECKING:
    from asyncio import Queue as AsyncQueue

from data_provider.base import canonical_stock_code, normalize_stock_code
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    get_current_diagnostic_context,
    reset_run_diagnostic_context,
)
from src.utils.analysis_metadata import SELECTION_SOURCES
from src.services.stock_code_utils import resolve_index_stock_code_for_analysis

logger = logging.getLogger(__name__)


def _dedupe_stock_code_key(stock_code: str) -> str:
    """
    Build the internal duplicate-detection key for a stock code.

    The task queue should treat equivalent market code shapes as the same
    underlying stock, e.g. ``600519`` and ``600519.SH``.
    """
    return resolve_index_stock_code_for_analysis(normalize_stock_code(stock_code))


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"        # Waiting for execution
    PROCESSING = "processing"  # In progress
    COMPLETED = "completed"    # Completed
    FAILED = "failed"          # Failed
    CANCEL_REQUESTED = "cancel_requested"  # Cancellation requested
    CANCELLED = "cancelled"    # Cancelled by user/system


@dataclass
class TaskInfo:
    """
    Task information dataclass.

    Used for API responses and internal task management.
    """
    task_id: str
    stock_code: str
    stock_name: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    report_type: str = "detailed"
    analysis_phase: str = "auto"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    original_query: Optional[str] = None
    selection_source: Optional[str] = None
    query_source: str = "api"
    portfolio_context: Optional[Dict[str, Any]] = None
    skills: Optional[List[str]] = None
    report_language: Optional[str] = None
    trace_id: Optional[str] = None
    flow_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task info into an API-friendly dictionary."""
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id or self.task_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "report_type": self.report_type,
            "analysis_phase": self.analysis_phase,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "original_query": self.original_query,
            "selection_source": self.selection_source,
            "skills": self.skills,
        }

    def copy(self) -> 'TaskInfo':
        """Create a shallow copy of the task information."""
        return TaskInfo(
            task_id=self.task_id,
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            status=self.status,
            progress=self.progress,
            message=self.message,
            result=self.result,
            error=self.error,
            report_type=self.report_type,
            analysis_phase=self.analysis_phase,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            original_query=self.original_query,
            selection_source=self.selection_source,
            query_source=self.query_source,
            portfolio_context=dict(self.portfolio_context) if isinstance(self.portfolio_context, dict) else None,
            skills=list(self.skills) if self.skills is not None else None,
            report_language=self.report_language,
            trace_id=self.trace_id or self.task_id,
            flow_events=copy.deepcopy(self.flow_events),
        )


class DuplicateTaskError(Exception):
    """
    \u91cd\u590d\u63d0\u4ea4\u5f02\u5e38

    \u5f53\u80a1\u7968\u5df2\u5728analyzeMedium\u65f6\u629b\u51fa\u6b64\u5f02\u5e38
    """
    def __init__(self, stock_code: str, existing_task_id: str):
        self.stock_code = stock_code
        self.existing_task_id = existing_task_id
        super().__init__(f"\u80a1\u7968 {stock_code} \u6b63\u5728analyzeMedium (task_id: {existing_task_id})")


class AnalysisTaskQueue:
    """
    \u5f02\u6b65analysis taskqueue

    \u5355\u4f8bmode; \u5168\u5c40\u552f\u4e00\u5b9e\u4f8b

    \u7279:
    1. \u9632\u6b62\u76f8\u540cstock code\u91cd\u590d\u63d0\u4ea4
    2. \u7ebf\u7a0b\u6c60\u6267\u884canalysis task
    3. SSE \u4e8b\u4ef6\u5e7f\u64ad\u673a\u5236
    4. task\u5b8c\u6210\u540e\u81ea\u52a8\u6301\u4e45\u5316
    """

    _instance: Optional['AnalysisTaskQueue'] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_workers: int = 3):
        # \u9632\u6b62\u91cd\u590d\u521d\u59cb\u5316
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None

        # \u6838\u5fc3\u6570\u636e\u7ed3\u6784
        self._tasks: Dict[str, TaskInfo] = {}           # task_id -> TaskInfo
        self._analyzing_stocks: Dict[str, str] = {}     # dedupe_key -> task_id
        self._futures: Dict[str, Future] = {}           # task_id -> Future

        # SSE \u8ba2\u9605\u8005\u5217\u8868 (asyncio.Queue \u5b9e\u4f8b)
        self._subscribers: List['AsyncQueue'] = []
        self._subscribers_lock = threading.Lock()

        # \u4e3b\u4e8b\u4ef6\u5faa\u73af\u5f15\u7528 (\u7528\u4e8e\u8de8\u7ebf\u7a0b\u5e7f\u64ad)
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

        # \u7ebf\u7a0b\u5b89\u5168\u9501
        self._data_lock = threading.RLock()

        # taskhistory\u4fdd\u7559count (\u5185\u5b58Medium)
        self._max_history = 100
        self._max_flow_events_per_task = 200

        self._initialized = True
        logger.info(f"[TaskQueue] initialization complete; \u6700\u5927\u5e76\u53d1: {max_workers}")

    @property
    def executor(self) -> ThreadPoolExecutor:
        """\u61d2load\u7ebf\u7a0b\u6c60"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="analysis_task_"
            )
        return self._executor

    @property
    def max_workers(self) -> int:
        """Return current executor max worker setting."""
        return self._max_workers

    def _has_inflight_tasks_locked(self) -> bool:
        """Check whether queue has any pending/processing tasks."""
        if self._analyzing_stocks:
            return True
        return any(
            task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
            for task in self._tasks.values()
        )

    def sync_max_workers(
        self,
        max_workers: int,
        *,
        log: bool = True,
    ) -> Literal["applied", "unchanged", "deferred_busy"]:
        """
        Try to sync queue concurrency without replacing singleton instance.

        Returns:
            - "applied": new value applied immediately (idle queue only)
            - "unchanged": target equals current value or invalid target
            - "deferred_busy": queue is busy, apply is deferred
        """
        try:
            target = max(1, int(max_workers))
        except (TypeError, ValueError):
            if log:
                logger.warning("[TaskQueue] \u5ffd\u7565\u975e\u6cd5 MAX_WORKERS \u503c: %r", max_workers)
            return "unchanged"

        executor_to_shutdown: Optional[ThreadPoolExecutor] = None
        previous: int
        with self._data_lock:
            previous = self._max_workers
            if target == previous:
                return "unchanged"

            if self._has_inflight_tasks_locked():
                if log:
                    logger.info(
                        "[TaskQueue] \u6700\u5927\u5e76\u53d1\u8c03\u6574\u5ef6\u540e: \u5f53\u524d\u7e41\u5fd9 (%s -> %s)",
                        previous,
                        target,
                    )
                return "deferred_busy"

            self._max_workers = target
            executor_to_shutdown = self._executor
            self._executor = None

        if executor_to_shutdown is not None:
            executor_to_shutdown.shutdown(wait=False)

        if log:
            logger.info("[TaskQueue] \u6700\u5927\u5e76\u53d1\u5df2\u66f4\u65b0: %s -> %s", previous, target)
        return "applied"

    # ========== task\u63d0\u4ea4\u4e0equery ==========

    def is_analyzing(self, stock_code: str) -> bool:
        """
        \u68c0check\u80a1\u7968\u662f\u5426\u6b63\u5728analyzeMedium

        Args:
            stock_code: stock code

        Returns:
            True \u8868\u793a\u6b63\u5728analyzeMedium
        """
        dedupe_key = _dedupe_stock_code_key(stock_code)
        with self._data_lock:
            return dedupe_key in self._analyzing_stocks

    def get_analyzing_task_id(self, stock_code: str) -> Optional[str]:
        """
        \u83b7\u53d6\u6b63\u5728analyze\u8be5\u80a1\u7968\u7684task ID

        Args:
            stock_code: stock code

        Returns:
            task ID; \u5982\u679c\u6ca1\u6709\u5219\u8fd4\u56de None
        """
        dedupe_key = _dedupe_stock_code_key(stock_code)
        with self._data_lock:
            return self._analyzing_stocks.get(dedupe_key)

    def validate_selection_source(self, selection_source: Optional[str]) -> None:
        """
        Validate the selection source parameter.

        Args:
            selection_source: Selection source label.

        Raises:
            ValueError: Raised when the selection source is invalid.
        """
        if selection_source is not None and selection_source not in SELECTION_SOURCES:
            raise ValueError(
                f"Invalid selection_source: {selection_source}. "
                f"Must be one of {SELECTION_SOURCES}"
            )

    def submit_task(
        self,
        stock_code: str,
        stock_name: Optional[str] = None,
        original_query: Optional[str] = None,
        selection_source: Optional[str] = None,
        query_source: str = "api",
        portfolio_context: Optional[Dict[str, Any]] = None,
        report_type: str = "detailed",
        analysis_phase: str = "auto",
        force_refresh: bool = False,
        skills: Optional[List[str]] = None,
        report_language: Optional[str] = None,
    ) -> TaskInfo:
        """
        Submit a single analysis task.

        Args:
            stock_code: Stock code
            stock_name: Optional stock name
            original_query: Optional raw user input
            selection_source: Optional source label
            report_type: Report type
            analysis_phase: Requested analysis phase override
            force_refresh: Whether to bypass cache

        Returns:
            TaskInfo: Accepted task information

        Raises:
            DuplicateTaskError: Raised when the stock is already being analyzed
        """
        stock_code = resolve_index_stock_code_for_analysis(stock_code)
        if not stock_code:
            raise ValueError("stock codecannot be emptyorcontain only whitespace")

        accepted, duplicates = self.submit_tasks_batch(
            [stock_code],
            stock_name=stock_name,
            original_query=original_query,
            selection_source=selection_source,
            query_source=query_source,
            portfolio_context=portfolio_context,
            report_type=report_type,
            analysis_phase=analysis_phase,
            force_refresh=force_refresh,
            skills=skills,
            report_language=report_language,
        )
        if duplicates:
            raise duplicates[0]
        return accepted[0]

    def submit_tasks_batch(
        self,
        stock_codes: List[str],
        stock_name: Optional[str] = None,
        original_query: Optional[str] = None,
        selection_source: Optional[str] = None,
        query_source: str = "api",
        portfolio_context: Optional[Dict[str, Any]] = None,
        report_type: str = "detailed",
        analysis_phase: str = "auto",
        force_refresh: bool = False,
        notify: bool = True,
        skills: Optional[List[str]] = None,
        report_language: Optional[str] = None,
    ) -> Tuple[List[TaskInfo], List[DuplicateTaskError]]:
        """
        Submit analysis tasks in batch.

        - Duplicate stocks are skipped and recorded in duplicates.
        - If executor submission fails, the current batch is rolled back.
        """
        self.validate_selection_source(selection_source)

        accepted: List[TaskInfo] = []
        duplicates: List[DuplicateTaskError] = []
        created_task_ids: List[str] = []

        canonical_codes = [
            normalized for normalized in (resolve_index_stock_code_for_analysis(code) for code in stock_codes)
            if normalized
        ]

        with self._data_lock:
            for stock_code in canonical_codes:
                dedupe_key = _dedupe_stock_code_key(stock_code)
                if dedupe_key in self._analyzing_stocks:
                    existing_task_id = self._analyzing_stocks[dedupe_key]
                    duplicates.append(DuplicateTaskError(stock_code, existing_task_id))
                    continue

                task_id = uuid.uuid4().hex
                task_skills = list(skills) if skills is not None else None
                task_info = TaskInfo(
                    task_id=task_id,
                    trace_id=task_id,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    status=TaskStatus.PENDING,
                    message="taskaddedqueue",
                    report_type=report_type,
                    analysis_phase=analysis_phase or "auto",
                    original_query=original_query,
                    selection_source=selection_source,
                    query_source=query_source or "api",
                    portfolio_context=dict(portfolio_context) if isinstance(portfolio_context, dict) else None,
                    skills=task_skills,
                    report_language=report_language,
                )
                self._tasks[task_id] = task_info
                self._analyzing_stocks[dedupe_key] = task_id

                try:
                    future = self.executor.submit(
                        self._execute_task,
                        task_id,
                        stock_code,
                        report_type,
                        force_refresh,
                        notify,
                        task_skills,
                        report_language,
                    )
                except Exception:
                    # Roll back the current batch to avoid partial submission.
                    self._rollback_submitted_tasks_locked(created_task_ids + [task_id])
                    raise

                self._futures[task_id] = future
                accepted.append(task_info)
                created_task_ids.append(task_id)
                logger.info(f"[TaskQueue] task\u5df2\u63d0\u4ea4: {stock_code} -> {task_id}")

            # Keep task_created ordered before worker-emitted task_started/task_completed.
            # Broadcasting here also preserves batch rollback semantics because we only
            # reach this point after every submit in the batch has succeeded.
            for task_info in accepted:
                self._broadcast_event("task_created", task_info.to_dict())

        return accepted, duplicates

    def submit_background_task(
        self,
        run_task: Callable[[], Optional[Any]],
        *,
        stock_code: str,
        stock_name: Optional[str] = None,
        report_type: str = "detailed",
        message: Optional[str] = "taskaddedqueue",
        task_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> TaskInfo:
        """
        Submit a generic background callable with task lifecycle tracking.

        This is used by callers that need task status visibility but do not
        map to standard per-stock async analysis flow.
        """
        task_id = task_id or uuid.uuid4().hex
        task_info = TaskInfo(
            task_id=task_id,
            trace_id=trace_id or task_id,
            stock_code=stock_code,
            stock_name=stock_name,
            status=TaskStatus.PENDING,
            message=message,
            report_type=report_type,
        )

        with self._data_lock:
            if task_id in self._tasks:
                raise ValueError(f"task ID already exists: {task_id}")
            self._tasks[task_id] = task_info
            try:
                future = self.executor.submit(self._execute_background_task, task_id, run_task)
            except Exception:
                del self._tasks[task_id]
                raise

            self._futures[task_id] = future
            self._broadcast_event("task_created", task_info.to_dict())

        return task_info.copy()

    def _rollback_submitted_tasks_locked(self, task_ids: List[str]) -> None:
        """\u56de\u6eda\u5f53\u524d\u6279\u6b21\u5df2\u521b\u5efa\u4f46\u5c1a\u672a\u7a33\u5b9a\u8fd4\u56de\u7ed9\u8c03\u7528\u65b9\u7684task."""
        for task_id in task_ids:
            future = self._futures.pop(task_id, None)
            if future is not None:
                future.cancel()

            task = self._tasks.pop(task_id, None)
            if task:
                dedupe_key = _dedupe_stock_code_key(task.stock_code)
                if self._analyzing_stocks.get(dedupe_key) == task_id:
                    del self._analyzing_stocks[dedupe_key]

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        \u83b7\u53d6taskinfo

        Args:
            task_id: task ID

        Returns:
            TaskInfo or None
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            return task.copy() if task else None

    def append_task_flow_event(
        self,
        task_id: str,
        flow_event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Append a recent run-flow event to an active task and broadcast it.

        The event cache is deliberately bounded and fail-open; diagnostics must
        never affect the analysis pipeline.
        """
        try:
            event_payload = copy.deepcopy(flow_event)
        except Exception:
            logger.debug("[TaskQueue] \u5ffd\u7565\u4e0d\u53ef\u590d\u5236\u7684\u8fd0\u884c\u6d41\u4e8b\u4ef6: task_id=%s", task_id)
            return None

        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.flow_events.append(event_payload)
            if len(task.flow_events) > self._max_flow_events_per_task:
                task.flow_events = task.flow_events[-self._max_flow_events_per_task:]
            task_snapshot = task.copy()

        payload = task_snapshot.to_dict()
        payload["flow_event"] = event_payload
        self._broadcast_event("task_progress", payload)
        return event_payload

    def get_task_flow_events(self, task_id: str) -> List[Dict[str, Any]]:
        """Return a copy of the recent run-flow events for a task."""
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return []
            return copy.deepcopy(task.flow_events)

    def list_pending_tasks(self) -> List[TaskInfo]:
        """
        \u83b7\u53d6\u6240\u6709in progress\u7684task (pending + processing)

        Returns:
            task\u5217\u8868 (\u526f\u672c)
        """
        with self._data_lock:
            return [
                task.copy() for task in self._tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.CANCEL_REQUESTED)
            ]

    def list_all_tasks(self, limit: int = 50) -> List[TaskInfo]:
        """
        \u83b7\u53d6\u6240\u6709task (\u6309\u521b\u5efa\u65f6\u95f4\u5012\u5e8f)

        Args:
            limit: \u8fd4\u56decountlimit

        Returns:
            task\u5217\u8868 (\u526f\u672c)
        """
        with self._data_lock:
            tasks = sorted(
                self._tasks.values(),
                key=lambda t: t.created_at,
                reverse=True
            )
            return [t.copy() for t in tasks[:limit]]

    def get_task_stats(self) -> Dict[str, int]:
        """
        \u83b7\u53d6task\u7edf\u8ba1info

        Returns:
            \u7edf\u8ba1info\u5b57\u5178
        """
        with self._data_lock:
            stats = {
                "total": len(self._tasks),
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            }
            for task in self._tasks.values():
                stats[task.status.value] = stats.get(task.status.value, 0) + 1
            return stats

    def update_task_progress(
        self,
        task_id: str,
        progress: int,
        message: Optional[str] = None,
        *,
        event_type: str = "task_progress",
    ) -> Optional[TaskInfo]:
        """
        Update in-flight task progress and broadcast an SSE event.

        Only pending/processing tasks are updated. Progress is clamped to
        [0, 99] so terminal states remain controlled by completion/failure.
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task or task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                return None

            next_progress = max(task.progress, max(0, min(99, int(progress))))
            changed = False
            if next_progress != task.progress:
                task.progress = next_progress
                changed = True
            if message is not None and message != task.message:
                task.message = message
                changed = True

            if not changed:
                return task.copy()

            task_snapshot = task.copy()

        self._broadcast_event(event_type, task_snapshot.to_dict())
        return task_snapshot

    # ========== task\u6267\u884c ==========

    def _execute_task(
        self,
        task_id: str,
        stock_code: str,
        report_type: str,
        force_refresh: bool,
        notify: bool = True,
        skills: Optional[List[str]] = None,
        report_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        \u6267\u884canalysis task (\u5728\u7ebf\u7a0b\u6c60Medium\u8fd0\u884c)

        Args:
            task_id: task ID
            stock_code: stock code
            report_type: report type
            force_refresh: \u662f\u5426\u5f3a\u5236\u5237\u65b0

        Returns:
            analysis result\u5b57\u5178
        """
        # \u66f4\u65b0status\u4e3a\u5904\u7406Medium
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            trace_id = task.trace_id or task_id
            analysis_phase = task.analysis_phase
            query_source = task.query_source or "api"
            portfolio_context = dict(task.portfolio_context) if isinstance(task.portfolio_context, dict) else None
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            task.message = "\u6b63\u5728analyzeMedium..."
            task.progress = 10

        self._broadcast_event("task_started", task.to_dict())

        try:
            # \u5bfc\u5165analyze\u670d\u52a1 (\u5ef6\u8fdf\u5bfc\u5165\u907f\u514d\u5faa\u73af\u4f9d\u8d56)
            from src.services.analysis_service import AnalysisService

            # \u6267\u884canalyze
            service = AnalysisService()

            def _on_progress(progress: int, message: str) -> None:
                self.update_task_progress(task_id, progress, message)

            diag_token = None
            if get_current_diagnostic_context() is None:
                diag_token = activate_run_diagnostic_context(
                    trace_id=trace_id,
                    task_id=task_id,
                    query_id=task_id,
                    stock_code=stock_code,
                    trigger_source=query_source,
                    event_sink=lambda event: self.append_task_flow_event(task_id, event),
                )
            result = service.analyze_stock(
                stock_code=stock_code,
                report_type=report_type,
                force_refresh=force_refresh,
                query_id=task_id,
                trace_id=trace_id,
                send_notification=notify,
                progress_callback=_on_progress,
                skills=skills,
                analysis_phase=analysis_phase,
                query_source=query_source,
                portfolio_context=portfolio_context,
                report_language=report_language,
            )
            reset_run_diagnostic_context(diag_token)
            diag_token = None

            if result:
                # \u66f4\u65b0taskstatus\u4e3a\u5b8c\u6210
                with self._data_lock:
                    task = self._tasks.get(task_id)
                    if task:
                        task.status = TaskStatus.COMPLETED
                        task.progress = 100
                        task.completed_at = datetime.now()
                        task.result = result
                        task.message = "analysis completed"
                        task.stock_name = result.get("stock_name", task.stock_name)

                        # \u4eceanalyzeMedium\u96c6\u5408\u79fb\u9664
                        dedupe_key = _dedupe_stock_code_key(task.stock_code)
                        if dedupe_key in self._analyzing_stocks:
                            del self._analyzing_stocks[dedupe_key]

                self._broadcast_event("task_completed", task.to_dict())
                logger.info(f"[TaskQueue] task\u5b8c\u6210: {task_id} ({stock_code})")

                # \u6e05\u7406\u8fc7\u671ftask
                self._cleanup_old_tasks()

                return result
            else:
                # analysis returned empty result
                raise Exception(service.last_error or "analysis returned empty result")

        except Exception as e:
            if "diag_token" in locals():
                reset_run_diagnostic_context(diag_token)
            error_msg = str(e)
            logger.error(f"[TaskQueue] taskfailed: {task_id} ({stock_code}), error: {error_msg}")

            with self._data_lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = error_msg[:200]  # limiterrorinfo\u957f\u5ea6
                    task.message = f"analyzefailed: {error_msg[:50]}"

                    # \u4eceanalyzeMedium\u96c6\u5408\u79fb\u9664
                    dedupe_key = _dedupe_stock_code_key(task.stock_code)
                    if dedupe_key in self._analyzing_stocks:
                        del self._analyzing_stocks[dedupe_key]

            self._broadcast_event("task_failed", task.to_dict())

            # \u6e05\u7406\u8fc7\u671ftask
            self._cleanup_old_tasks()

            return None

    def _execute_background_task(
        self,
        task_id: str,
        run_task: Callable[[], Optional[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """
        \u6267\u884c\u901a\u7528\u540e\u53f0task (\u652f\u6301\u81ea\u5b9a\u4e49\u8fd0\u884c\u903b\u8f91)

        Args:
            task_id: task ID
            run_task: task\u6267\u884c\u51fd\u6570

        Returns:
            task\u6267\u884cresult\u5b57\u5178 (optional)
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            trace_id = task.trace_id or task_id
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            task.message = "task\u6267\u884cMedium"
            task.progress = 10
            self._broadcast_event("task_started", task.to_dict())

        try:
            diag_token = None
            if get_current_diagnostic_context() is None:
                diag_token = activate_run_diagnostic_context(
                    trace_id=trace_id,
                    task_id=task_id,
                    query_id=task_id,
                    stock_code=task.stock_code,
                    trigger_source="api",
                    event_sink=lambda event: self.append_task_flow_event(task_id, event),
                )
            try:
                result = run_task()
            finally:
                reset_run_diagnostic_context(diag_token)
            if result is None:
                raise RuntimeError("taskreturned empty result; no persistable content was generated")

            with self._data_lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    task.completed_at = datetime.now()
                    task.result = result
                    task.message = "taskcompleted"

            self._broadcast_event("task_completed", task.to_dict())
            logger.info(f"[TaskQueue] \u81ea\u5b9a\u4e49task\u5b8c\u6210: {task_id}")

            self._cleanup_old_tasks()
            return result

        except Exception as e:  # pragma: no cover - behavior verified in downstream tests
            error_msg = str(e)
            logger.error(
                f"[TaskQueue] \u81ea\u5b9a\u4e49taskfailed: {task_id}, error: {error_msg}"
            )

            with self._data_lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = error_msg[:200]
                    task.message = f"taskfailed: {error_msg[:80]}"

            if task:
                self._broadcast_event("task_failed", task.to_dict())

            self._cleanup_old_tasks()
            return None

    def _cleanup_old_tasks(self) -> int:
        """
        \u6e05\u7406\u8fc7\u671f\u7684completedtask

        \u4fdd\u7559\u6700\u8fd1 _max_history \u4e2atask

        Returns:
            \u6e05\u7406\u7684taskcount
        """
        with self._data_lock:
            if len(self._tasks) <= self._max_history:
                return 0

            # \u6309\u65f6\u95f4\u6392\u5e8f; \u5220\u9664\u65e7\u7684completedtask
            completed_tasks = sorted(
                [t for t in self._tasks.values()
                 if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)],
                key=lambda t: t.created_at
            )

            to_remove = len(self._tasks) - self._max_history
            removed = 0

            for task in completed_tasks[:to_remove]:
                del self._tasks[task.task_id]
                if task.task_id in self._futures:
                    del self._futures[task.task_id]
                removed += 1

            if removed > 0:
                logger.debug(f"[TaskQueue] \u6e05\u7406\u4e86 {removed} \u4e2a\u8fc7\u671ftask")

            return removed

    # ========== SSE \u4e8b\u4ef6\u5e7f\u64ad ==========

    def subscribe(self, queue: 'AsyncQueue') -> None:
        """
        \u8ba2\u9605task\u4e8b\u4ef6

        Args:
            queue: asyncio.Queue \u5b9e\u4f8b; \u7528\u4e8e\u63a5\u6536\u4e8b\u4ef6
        """
        with self._subscribers_lock:
            self._subscribers.append(queue)
            # \u6355\u83b7\u5f53\u524d\u4e8b\u4ef6\u5faa\u73af (\u5e94\u5728\u4e3b\u7ebf\u7a0b\u7684 async \u4e0a\u4e0b\u6587Medium\u8c03\u7528)
            try:
                self._main_loop = asyncio.get_running_loop()
            except RuntimeError:
                # \u5982\u679c\u4e0d\u5728 async \u4e0a\u4e0b\u6587Medium; \u5c1d\u8bd5\u83b7\u53d6\u4e8b\u4ef6\u5faa\u73af
                try:
                    self._main_loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass
            logger.debug(f"[TaskQueue] \u65b0\u8ba2\u9605\u8005\u52a0\u5165; \u5f53\u524d\u8ba2\u9605\u8005\u6570: {len(self._subscribers)}")

    def unsubscribe(self, queue: 'AsyncQueue') -> None:
        """
        \u53d6\u6d88\u8ba2\u9605task\u4e8b\u4ef6

        Args:
            queue: \u8981\u53d6\u6d88\u8ba2\u9605\u7684 asyncio.Queue \u5b9e\u4f8b
        """
        with self._subscribers_lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
                logger.debug(f"[TaskQueue] \u8ba2\u9605\u8005\u79bb\u5f00; \u5f53\u524d\u8ba2\u9605\u8005\u6570: {len(self._subscribers)}")

    def _broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        \u5e7f\u64ad\u4e8b\u4ef6\u5230\u6240\u6709\u8ba2\u9605\u8005

        \u4f7f\u7528 call_soon_threadsafe \u786e\u4fdd\u8de8\u7ebf\u7a0b\u5b89\u5168

        Args:
            event_type: \u4e8b\u4ef6\u7c7b\u578b
            data: \u4e8b\u4ef6\u6570\u636e
        """
        event = {"type": event_type, "data": data}

        with self._subscribers_lock:
            subscribers = self._subscribers.copy()
            loop = self._main_loop

        if not subscribers:
            return

        if loop is None:
            logger.warning("[TaskQueue] \u65e0\u6cd5\u5e7f\u64ad\u4e8b\u4ef6: \u4e3b\u4e8b\u4ef6\u5faa\u73af\u672a\u8bbe\u7f6e")
            return

        for queue in subscribers:
            try:
                # \u4f7f\u7528 call_soon_threadsafe \u5c06\u4e8b\u4ef6\u653e\u5165 asyncio queue
                # \u8fd9\u662f\u4ece\u5de5\u4f5c\u7ebf\u7a0b\u5411\u4e3b\u4e8b\u4ef6\u5faa\u73af\u53d1\u9001\u6d88\u606f\u7684\u5b89\u5168\u65b9\u5f0f
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError as e:
                # \u4e8b\u4ef6\u5faa\u73af\u5df2\u5173\u95ed
                logger.debug(f"[TaskQueue] \u5e7f\u64ad\u4e8b\u4ef6skipping (\u5faa\u73af\u5df2\u5173\u95ed): {e}")
            except Exception as e:
                logger.warning(f"[TaskQueue] \u5e7f\u64ad\u4e8b\u4ef6failed: {e}")

    # ========== \u6e05\u7406\u65b9\u6cd5 ==========

    def shutdown(self) -> None:
        """\u5173\u95edtaskqueue"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
            logger.info("[TaskQueue] \u7ebf\u7a0b\u6c60\u5df2\u5173\u95ed")


# ========== \u4fbf\u6377\u51fd\u6570 ==========

def get_task_queue() -> AnalysisTaskQueue:
    """
    \u83b7\u53d6taskqueue\u5355\u4f8b

    Returns:
        AnalysisTaskQueue \u5b9e\u4f8b
    """
    queue = AnalysisTaskQueue()
    try:
        from src.config import get_config

        config = get_config()
        target_workers = max(1, int(getattr(config, "max_workers", queue.max_workers)))
        queue.sync_max_workers(target_workers, log=False)
    except Exception as exc:
        logger.debug("[TaskQueue] \u8bfb\u53d6 MAX_WORKERS failed; \u4f7f\u7528\u5f53\u524d\u5e76\u53d1\u8bbe\u7f6e: %s", exc)

    return queue
