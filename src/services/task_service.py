# -*- coding: utf-8 -*-
"""
===================================
\u5f02\u6b65task\u670d\u52a1\u5c42
===================================

\u804c\u8d23:
1. \u7ba1\u7406\u5f02\u6b65analysis task (\u7ebf\u7a0b\u6c60)
2. \u6267\u884c\u80a1\u7968analyze\u5e76\u63a8\u9001result
3. querytaskstatus\u548chistory

\u8fc1\u79fb\u81ea web/services.py \u7684 AnalysisService \u7c7b
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from src.enums import ReportType
from src.storage import get_db
from bot.models import BotMessage
from src.services.stock_code_utils import resolve_index_stock_code_for_analysis

logger = logging.getLogger(__name__)


class TaskService:
    """
    \u5f02\u6b65task\u670d\u52a1

    \u8d1f\u8d23:
    1. \u7ba1\u7406\u5f02\u6b65analysis task
    2. \u6267\u884c\u80a1\u7968analyze
    3. \u89e6\u53d1\u901a\u77e5\u63a8\u9001
    """

    _instance: Optional['TaskService'] = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 3):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = max_workers
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'TaskService':
        """\u83b7\u53d6\u5355\u4f8b\u5b9e\u4f8b"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def executor(self) -> ThreadPoolExecutor:
        """\u83b7\u53d6or\u521b\u5efa\u7ebf\u7a0b\u6c60"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="analysis_"
            )
        return self._executor

    def submit_analysis(
        self,
        code: str,
        report_type: Union[ReportType, str] = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None,
        save_context_snapshot: Optional[bool] = None,
        query_source: str = "bot"
    ) -> Dict[str, Any]:
        """
        \u63d0\u4ea4\u5f02\u6b65analysis task

        Args:
            code: stock code
            report_type: report type\u679a\u4e3e
            source_message: source\u6d88\u606f (\u7528\u4e8e\u56de\u590d)
            save_context_snapshot: \u662f\u5426\u4fdd\u5b58\u4e0a\u4e0b\u6587\u5feb\u7167
            query_source: tasksource\u6807\u8bc6 (bot/api/cli/system)

        Returns:
            taskinfo\u5b57\u5178
        """
        # \u786e\u4fdd report_type \u662f\u679a\u4e3e\u7c7b\u578b
        if isinstance(report_type, str):
            report_type = ReportType.from_str(report_type)

        normalized_code = resolve_index_stock_code_for_analysis(code)
        if not normalized_code:
            raise ValueError("stock codecannot be emptyorcontain only whitespace")

        task_id = f"{normalized_code}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # \u63d0\u4ea4\u5230\u7ebf\u7a0b\u6c60
        self.executor.submit(
            self._run_analysis,
            normalized_code,
            task_id,
            report_type,
            source_message,
            save_context_snapshot,
            query_source
        )

        logger.info(
            f"[TaskService] \u5df2\u63d0\u4ea4\u80a1\u7968 {normalized_code} \u7684analysis task, "
            f"task_id={task_id}, report_type={report_type.value}"
        )

        return {
            "success": True,
            "message": "analysis task\u5df2\u63d0\u4ea4; \u5c06\u5f02\u6b65\u6267\u884c\u5e76\u63a8\u9001\u901a\u77e5",
            "code": normalized_code,
            "task_id": task_id,
            "report_type": report_type.value
        }

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """\u83b7\u53d6taskstatus"""
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """\u5217\u51fa\u6700\u8fd1\u7684task"""
        with self._tasks_lock:
            tasks = list(self._tasks.values())
        # \u6309\u5f00\u59cb\u65f6\u95f4\u5012\u5e8f
        tasks.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return tasks[:limit]

    def get_analysis_history(
        self,
        code: Optional[str] = None,
        query_id: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """\u83b7\u53d6analyzehistory records"""
        db = get_db()
        records = db.get_analysis_history(code=code, query_id=query_id, days=days, limit=limit)
        return [r.to_dict() for r in records]

    def _run_analysis(
        self,
        code: str,
        task_id: str,
        report_type: ReportType = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None,
        save_context_snapshot: Optional[bool] = None,
        query_source: str = "bot"
    ) -> Dict[str, Any]:
        """
        \u6267\u884c\u5355stocksanalyze

        \u5185\u90e8\u65b9\u6cd5; \u5728\u7ebf\u7a0b\u6c60Medium\u8fd0\u884c
        """
        # \u521d\u59cb\u5316taskstatus
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "running",
                "start_time": datetime.now().isoformat(),
                "result": None,
                "error": None,
                "report_type": report_type.value
            }

        try:
            # \u5ef6\u8fdf\u5bfc\u5165\u907f\u514d\u5faa\u73af\u4f9d\u8d56
            from src.config import get_config
            from main import StockAnalysisPipeline

            logger.info(f"[TaskService] \u5f00\u59cbanalyze stock: {code}")

            # \u521b\u5efaanalyze\u7ba1\u9053
            config = get_config()
            pipeline = StockAnalysisPipeline(
                config=config,
                max_workers=1,
                source_message=source_message,
                query_id=task_id,
                query_source=query_source,
                save_context_snapshot=save_context_snapshot
            )

            # \u6267\u884c\u5355stocksanalyze (\u542f\u7528\u5355\u80a1\u63a8\u9001)
            result = pipeline.process_single_stock(
                code=code,
                skip_analysis=False,
                single_stock_notify=True,
                report_type=report_type
            )

            if result and result.success:
                result_data = {
                    "code": result.code,
                    "name": result.name,
                    "sentiment_score": result.sentiment_score,
                    "operation_advice": result.operation_advice,
                    "trend_prediction": result.trend_prediction,
                    "analysis_summary": result.analysis_summary,
                }

                with self._tasks_lock:
                    self._tasks[task_id].update({
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                        "result": result_data
                    })

                logger.info(f"[TaskService] \u80a1\u7968 {code} analysis completed: {result.operation_advice}")
                return {"success": True, "task_id": task_id, "result": result_data}
            else:
                fail_message = "analysis returned empty result"
                if result is not None:
                    fail_message = result.error_message or fail_message
                with self._tasks_lock:
                    self._tasks[task_id].update({
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "error": fail_message
                    })

                logger.warning(f"[TaskService] \u80a1\u7968 {code} analyzefailed: {fail_message}")
                return {"success": False, "task_id": task_id, "error": fail_message}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[TaskService] \u80a1\u7968 {code} analyze\u5f02\u5e38: {error_msg}")

            with self._tasks_lock:
                self._tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now().isoformat(),
                    "error": error_msg
                })

            return {"success": False, "task_id": task_id, "error": error_msg}


# ============================================================
# \u4fbf\u6377\u51fd\u6570
# ============================================================

def get_task_service() -> TaskService:
    """\u83b7\u53d6task\u670d\u52a1\u5355\u4f8b"""
    return TaskService.get_instance()
