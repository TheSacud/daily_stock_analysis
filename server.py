# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis - FastAPI \u540e\u7aef\u670d\u52a1\u5165\u53e3
===================================

\u804c\u8d23:
1. \u63d0\u4f9b RESTful API \u670d\u52a1
2. config CORS \u8de8\u57df\u652f\u6301
3. \u5065\u5eb7\u68c0check\u63a5\u53e3
4. \u6258\u7ba1\u524d\u7aef\u9759\u6001\u6587\u4ef6 (\u751f\u4ea7mode)

started\u65b9\u5f0f:
    uvicorn server:app --reload --host 0.0.0.0 --port 8000

    or\u4f7f\u7528 main.py:
    python main.py --serve-only      # \u4ec5started API \u670d\u52a1
    python main.py --serve           # API \u670d\u52a1 + \u6267\u884canalyze
"""

import logging

from src.config import setup_env, get_config
from src.logging_config import setup_logging

# \u521d\u59cb\u5316\u73af\u5883\u53d8\u91cf\u4e0elog
setup_env()

config = get_config()
level_name = (config.log_level or "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

setup_logging(
    log_prefix="api_server",
    console_level=level,
    extra_quiet_loggers=['uvicorn', 'fastapi'],
)

# \u4ece api.app \u5bfc\u5165\u5e94\u7528\u5b9e\u4f8b
from api.app import app  # noqa: E402

# \u5bfc\u51fa app \u4f9b uvicorn \u4f7f\u7528
__all__ = ['app']


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
