# -*- coding: utf-8 -*-
"""
===================================
logconfig\u6a21chunks - \u7edf\u4e00\u7684log\u7cfb\u7edf\u521d\u59cb\u5316
===================================

\u804c\u8d23:
1. \u63d0\u4f9b\u7edf\u4e00\u7684log\u683c\u5f0f\u548cconfig\u5e38\u91cf
2. \u652f\u6301\u63a7\u5236\u53f0 + \u6587\u4ef6 (\u5e38\u89c4/\u8c03\u8bd5)\u4e09\u5c42log\u8f93\u51fa
3. \u81ea\u52a8\u964dLow\u7b2c\u4e09\u65b9librarylog\u7ea7\u522b
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Tuple


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(pathname)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_ALLOWED_LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}
_DEFAULT_LITELLM_LOG_LEVEL = 'WARNING'


class RelativePathFormatter(logging.Formatter):
    """\u81ea\u5b9a\u4e49 Formatter; \u8f93\u51fa\u76f8\u5bf9\u8def\u5f84\u800c\u975e\u7edd\u5bf9\u8def\u5f84"""

    def __init__(self, fmt=None, datefmt=None, relative_to=None):
        super().__init__(fmt, datefmt)
        self.relative_to = Path(relative_to) if relative_to else Path.cwd()

    def format(self, record):
        # \u5c06\u7edd\u5bf9\u8def\u5f84\u8f6c\u4e3a\u76f8\u5bf9\u8def\u5f84
        try:
            record.pathname = str(Path(record.pathname).relative_to(self.relative_to))
        except ValueError:
            # \u5982\u679c\u65e0\u6cd5\u8f6c\u6362\u4e3a\u76f8\u5bf9\u8def\u5f84; \u4fdd\u6301\u539f\u6837
            pass
        return super().format(record)



# default\u9700\u8981\u964dLowlog\u7ea7\u522b\u7684\u7b2c\u4e09\u65b9library
DEFAULT_QUIET_LOGGERS = [
    'urllib3',
    'sqlalchemy',
    'google',
    'httpx',
]

LITELLM_LOGGERS = [
    'LiteLLM',
    'LiteLLM Router',
    'LiteLLM Proxy',
    'litellm',
]


def _resolve_litellm_log_level(raw_level: Optional[str] = None) -> Tuple[int, Optional[str]]:
    """Resolve LiteLLM logger level from env, returning invalid raw value if any."""
    if raw_level is None:
        raw_level = os.getenv('LITELLM_LOG_LEVEL', '')

    normalized = (raw_level or '').strip().upper()
    if not normalized:
        normalized = _DEFAULT_LITELLM_LOG_LEVEL

    level = _ALLOWED_LOG_LEVELS.get(normalized)
    if level is None:
        return _ALLOWED_LOG_LEVELS[_DEFAULT_LITELLM_LOG_LEVEL], raw_level
    return level, None


def setup_logging(
    log_prefix: str = "app",
    log_dir: str = "./logs",
    console_level: Optional[int] = None,
    debug: bool = False,
    extra_quiet_loggers: Optional[List[str]] = None,
) -> None:
    """
    \u7edf\u4e00\u7684log\u7cfb\u7edf\u521d\u59cb\u5316

    config\u4e09\u5c42log\u8f93\u51fa:
    1. \u63a7\u5236\u53f0: \u6839\u636e debug parameteror console_level \u8bbe\u7f6e\u7ea7\u522b
    2. \u5e38\u89c4log\u6587\u4ef6: INFO \u7ea7\u522b; 10MB \u8f6e\u8f6c; \u4fdd\u7559 5 \u4e2a\u5907\u4efd
    3. \u8c03\u8bd5log\u6587\u4ef6: DEBUG \u7ea7\u522b; 50MB \u8f6e\u8f6c; \u4fdd\u7559 3 \u4e2a\u5907\u4efd

    Args:
        log_prefix: log\u6587\u4ef6\u540dprefix (\u5982 "api_server" -> api_server_20240101.log)
        log_dir: log\u6587\u4ef6\u76ee\u5f55; default ./logs
        console_level: \u63a7\u5236\u53f0log\u7ea7\u522b (optional; \u4f18\u5148\u4e8e debug parameter)
        debug: \u662f\u5426\u542f\u7528\u8c03\u8bd5mode (\u63a7\u5236\u53f0\u8f93\u51fa DEBUG \u7ea7\u522b)
        extra_quiet_loggers: \u989d\u5916\u9700\u8981\u964dLowlog\u7ea7\u522b\u7684\u7b2c\u4e09\u65b9library\u5217\u8868
    """
    # \u786e\u5b9a\u63a7\u5236\u53f0log\u7ea7\u522b
    if console_level is not None:
        level = console_level
    else:
        level = logging.DEBUG if debug else logging.INFO

    # \u521b\u5efalog\u76ee\u5f55
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # log\u6587\u4ef6\u8def\u5f84 (\u6309date\u5206\u6587\u4ef6)
    today_str = datetime.now().strftime('%Y%m%d')
    log_file = log_path / f"{log_prefix}_{today_str}.log"
    debug_log_file = log_path / f"{log_prefix}_debug_{today_str}.log"

    # config\u6839 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # \u6839 logger \u8bbe\u4e3a DEBUG; \u7531 handler \u63a7\u5236\u8f93\u51fa\u7ea7\u522b

    # \u6e05\u9664\u5df2\u6709 handler; \u907f\u514d\u91cd\u590d\u6dfb\u52a0
    if root_logger.handlers:
        root_logger.handlers.clear()
    # \u521b\u5efa\u76f8\u5bf9\u8def\u5f84 Formatter (\u76f8\u5bf9\u4e8e\u9879\u76ee\u6839\u76ee\u5f55)
    project_root = Path.cwd()
    rel_formatter = RelativePathFormatter(
        LOG_FORMAT, LOG_DATE_FORMAT, relative_to=project_root
    )
    # Handler 1: \u63a7\u5236\u53f0\u8f93\u51fa
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(rel_formatter)
    root_logger.addHandler(console_handler)

    # Handler 2: \u5e38\u89c4log\u6587\u4ef6 (INFO \u7ea7\u522b; 10MB \u8f6e\u8f6c)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(rel_formatter)
    root_logger.addHandler(file_handler)

    # Handler 3: \u8c03\u8bd5log\u6587\u4ef6 (DEBUG \u7ea7\u522b; \u5305\u542b\u6240\u6709\u8be6\u7ec6info)
    debug_handler = RotatingFileHandler(
        debug_log_file,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=3,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(rel_formatter)
    root_logger.addHandler(debug_handler)

    # \u964dLow\u7b2c\u4e09\u65b9library\u7684log\u7ea7\u522b
    quiet_loggers = DEFAULT_QUIET_LOGGERS.copy()
    if extra_quiet_loggers:
        quiet_loggers.extend(extra_quiet_loggers)

    for logger_name in quiet_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    litellm_level, invalid_litellm_level = _resolve_litellm_log_level()
    for logger_name in LITELLM_LOGGERS:
        logging.getLogger(logger_name).setLevel(litellm_level)

    # \u8f93\u51fainitialization completeinfo (\u4f7f\u7528\u76f8\u5bf9\u8def\u5f84)
    try:
        rel_log_path = log_path.resolve().relative_to(project_root)
    except ValueError:
        rel_log_path = log_path

    try:
        rel_log_file = log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_log_file = log_file

    try:
        rel_debug_log_file = debug_log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_debug_log_file = debug_log_file

    logging.info(f"log\u7cfb\u7edfinitialization complete; log\u76ee\u5f55: {rel_log_path}")
    logging.info(f"\u5e38\u89c4log: {rel_log_file}")
    logging.info(f"\u8c03\u8bd5log: {rel_debug_log_file}")
    if invalid_litellm_level is not None:
        logging.warning(
            "LITELLM_LOG_LEVEL=%r \u65e0\u6548; \u5df2\u56de\u9000\u4e3a %s；optional\u503c: %s",
            invalid_litellm_level,
            _DEFAULT_LITELLM_LOG_LEVEL,
            ", ".join(_ALLOWED_LOG_LEVELS),
        )
