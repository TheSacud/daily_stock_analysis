# -*- coding: utf-8 -*-
"""
===================================
\u5168\u5c40\u5f02\u5e38\u5904\u7406Medium\u95f4\u4ef6
===================================

\u804c\u8d23:
1. \u6355\u83b7\u672a\u5904\u7406\u7684\u5f02\u5e38
2. \u7edf\u4e00error\u54cd\u5e94\u683c\u5f0f
3. \u8bb0\u5f55errorlog
"""

import logging
import traceback
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    \u5168\u5c40\u5f02\u5e38\u5904\u7406Medium\u95f4\u4ef6

    \u6355\u83b7\u6240\u6709\u672a\u5904\u7406\u7684\u5f02\u5e38; \u8fd4\u56de\u7edf\u4e00\u683c\u5f0f\u7684error\u54cd\u5e94
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        \u5904\u7406request; \u6355\u83b7\u5f02\u5e38

        Args:
            request: request\u5bf9\u8c61
            call_next: \u4e0b\u4e00\u4e2a\u5904\u7406\u5668

        Returns:
            Response: \u54cd\u5e94\u5bf9\u8c61
        """
        try:
            response = await call_next(request)
            return response

        except Exception as e:
            # \u8bb0\u5f55errorlog
            logger.error(
                f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {e}\n"
                f"request\u8def\u5f84: {request.url.path}\n"
                f"request\u65b9\u6cd5: {request.method}\n"
                f"\u5806\u6808: {traceback.format_exc()}"
            )

            # \u8fd4\u56de\u7edf\u4e00\u683c\u5f0f\u7684error\u54cd\u5e94
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "\u670d\u52a1\u5668\u5185\u90e8error; \u8bf7\u7a0d\u540e\u91cd\u8bd5",
                    "detail": str(e) if logger.isEnabledFor(logging.DEBUG) else None
                }
            )


def add_error_handlers(app) -> None:
    """
    \u6dfb\u52a0\u5168\u5c40\u5f02\u5e38\u5904\u7406\u5668

    \u4e3a FastAPI \u5e94\u7528\u6dfb\u52a0\u5404\u7c7b\u5f02\u5e38\u7684\u5904\u7406\u5668

    Args:
        app: FastAPI \u5e94\u7528\u5b9e\u4f8b
    """
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """\u5904\u7406 HTTP \u5f02\u5e38"""
        # \u5982\u679c detail \u5df2\u7ecf\u662f ErrorResponse \u683c\u5f0f\u7684 dict; \u76f4\u63a5\u4f7f\u7528
        if isinstance(exc.detail, dict) and "error" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
        # \u5426\u5219\u5c06 detail \u5305\u88c5\u6210 ErrorResponse \u683c\u5f0f
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "message": str(exc.detail) if exc.detail else "HTTP Error",
                "detail": None
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """\u5904\u7406request\u9a8c\u8bc1\u5f02\u5e38"""
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "requestparameter\u9a8c\u8bc1failed",
                "detail": exc.errors()
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """\u5904\u7406\u901a\u7528\u5f02\u5e38"""
        logger.error(
            f"\u672a\u5904\u7406\u7684\u5f02\u5e38: {exc}\n"
            f"request\u8def\u5f84: {request.url.path}\n"
            f"\u5806\u6808: {traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "\u670d\u52a1\u5668\u5185\u90e8error",
                "detail": None
            }
        )
