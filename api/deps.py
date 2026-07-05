# -*- coding: utf-8 -*-
"""
===================================
API \u4f9d\u8d56\u6ce8\u5165\u6a21chunks
===================================

\u804c\u8d23:
1. \u63d0\u4f9b\u6570\u636elibrary Session \u4f9d\u8d56
2. \u63d0\u4f9bconfig\u4f9d\u8d56
3. \u63d0\u4f9b\u670d\u52a1\u5c42\u4f9d\u8d56
"""

from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.system_config_service import SystemConfigService
from src.services.runtime_scheduler import RuntimeSchedulerService


def get_db() -> Generator[Session, None, None]:
    """
    \u83b7\u53d6\u6570\u636elibrary Session \u4f9d\u8d56

    \u4f7f\u7528 FastAPI \u4f9d\u8d56\u6ce8\u5165\u673a\u5236; \u786e\u4fddrequest\u7ed3\u675f\u540e\u81ea\u52a8\u5173\u95ed Session

    Yields:
        Session: SQLAlchemy Session \u5bf9\u8c61

    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    \u83b7\u53d6config\u4f9d\u8d56

    Returns:
        Config: config\u5355\u4f8b\u5bf9\u8c61
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    \u83b7\u53d6\u6570\u636elibrary\u7ba1\u7406\u5668\u4f9d\u8d56

    Returns:
        DatabaseManager: \u6570\u636elibrary\u7ba1\u7406\u5668\u5355\u4f8b\u5bf9\u8c61
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service


def get_runtime_scheduler_service(request: Request) -> RuntimeSchedulerService:
    """Get app-lifecycle shared RuntimeSchedulerService instance."""
    service = getattr(request.app.state, "runtime_scheduler_service", None)
    if service is None:
        service = RuntimeSchedulerService()
        request.app.state.runtime_scheduler_service = service
    return service
