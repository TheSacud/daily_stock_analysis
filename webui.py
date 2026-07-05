# -*- coding: utf-8 -*-
"""
===================================
WebUI \u542f\u52a8\u811a\u672c
===================================

\u7528\u4e8e\u542f\u52a8 Web \u670d\u52a1\u754c\u9762。
\u76f4\u63a5\u8fd0\u884c `python webui.py` \u5c06\u542f\u52a8 Web \u540e\u7aef\u670d\u52a1。

\u7b49\u6548\u547d\u4ee4：
    python main.py --webui-only

Usage:
  python webui.py
  WEBUI_HOST=0.0.0.0 WEBUI_PORT=8000 python webui.py
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


def main() -> int:
    """
    \u542f\u52a8 Web \u670d\u52a1
    """
    # \u517c\u5bb9\u65e7\u7248\u73af\u5883\u53d8\u91cf\u540d
    host = os.getenv("WEBUI_HOST", os.getenv("API_HOST", "127.0.0.1"))
    port = int(os.getenv("WEBUI_PORT", os.getenv("API_PORT", "8000")))

    print(f"\u6b63\u5728\u542f\u52a8 Web \u670d\u52a1: http://{host}:{port}")
    print(f"API \u6587\u6863: http://{host}:{port}/docs")
    print()

    try:
        import uvicorn
        from src.config import setup_env
        from src.logging_config import setup_logging

        setup_env()
        setup_logging(log_prefix="web_server")

        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
