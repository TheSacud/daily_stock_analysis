# -*- coding: utf-8 -*-
"""
===================================
\u80a1\u7968\u6570\u636e\u63a5\u53e3
===================================

\u804c\u8d23:
1. POST /api/v1/stocks/extract-from-image \u4ece\u56fe\u7247\u63d0\u53d6stock code
2. POST /api/v1/stocks/parse-import \u89e3\u6790 CSV/Excel/\u526a\u8d34\u677f
3. GET /api/v1/stocks/{code}/quote realtime quote\u63a5\u53e3
4. GET /api/v1/stocks/{code}/history history\u884c\u60c5\u63a5\u53e3
"""

import logging
from typing import Optional
import re

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Depends

from api.deps import get_system_config_service

from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockQuote,
)
from api.v1.schemas.history import WatchlistRequest, WatchlistResponse
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService
from src.services.stock_list_parser import split_stock_list
from src.services.system_config_service import SystemConfigService
from data_provider.base import normalize_stock_code

logger = logging.getLogger(__name__)

router = APIRouter()

# \u987b\u5728 /{stock_code} \u8def\u7531\u4e4b\u524d\u5b9a\u4e49
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


def _read_watchlist_codes(service: SystemConfigService) -> list:
    """Read STOCK_LIST codes as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    stock_list_str = ""
    for item in config_data.get("items", []):
        if item.get("key") == "STOCK_LIST":
            stock_list_str = str(item.get("value", ""))
            break
    return split_stock_list(stock_list_str)


def _write_watchlist_codes(service: SystemConfigService, codes: list) -> None:
    """Persist stock codes to STOCK_LIST as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    config_version = config_data.get("config_version", "")
    service.update(
        config_version=config_version,
        items=[{"key": "STOCK_LIST", "value": ",".join(codes)}],
        mask_token="******",
        reload_now=True,
    )


# Stock code validation patterns (aligned with frontend validateStockCode)
_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"                              # A-share 6-digit
    r"|(?:SH|SZ|BJ)\d{6}"                     # exchange-prefixed A-share
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"                # exchange-suffixed A-share
    r"|\d{1,5}\.HK"                           # HK suffix format
    r"|HK\d{1,5}"                             # HK prefix format
    r"|\d{5}"                                 # bare 5-digit HK code
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"         # US ticker
    r")$",
    re.IGNORECASE,
)


def _validate_and_normalize_stock_code(code: str) -> str:
    """Validate stock code format and return canonical form.

    Raises HTTPException(400) if the code does not match supported formats.
    """
    stripped = code.strip()
    if not stripped:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "stock codecannot be empty"},
        )
    if not _STOCK_CODE_RE.match(stripped):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_stock_code",
                "message": f"'{stripped}' \u4e0d\u662f\u5408\u6cd5\u7684stock code\u683c\u5f0f",
            },
        )
    return normalize_stock_code(stripped)


def _watchlist_match_key(code: str) -> str:
    """Return the equivalence key used for watchlist add/remove matching."""
    normalized = normalize_stock_code(code.strip())
    if re.fullmatch(r"\d{5}", normalized):
        return f"HK{normalized}"
    return normalized.upper()


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "\u63d0\u53d6\u7684stock code"},
        400: {"description": "\u56fe\u7247\u65e0\u6548", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u4ece\u56fe\u7247\u63d0\u53d6stock code",
    description="\u4e0a\u4f20\u622a\u56fe/\u56fe\u7247; \u901a\u8fc7 Vision LLM \u63d0\u53d6stock code.\u652f\u6301 JPEG、PNG、WebP、GIF; \u6700\u5927 5MB.",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="\u56fe\u7247\u6587\u4ef6 (\u8868\u5355\u5b57\u6bb5\u540d file)"),
    include_raw: bool = Query(False, description="\u662f\u5426\u5728resultMedium\u5305\u542b\u539f\u59cb LLM \u54cd\u5e94"),
) -> ExtractFromImageResponse:
    """
    \u4ece\u4e0a\u4f20\u7684\u56fe\u7247Medium\u63d0\u53d6stock code (\u4f7f\u7528 Vision LLM).

    \u8868\u5355\u5b57\u6bb5please use file \u4e0a\u4f20\u56fe\u7247.\u4f18\u5148\u7ea7: Gemini / Anthropic / OpenAI (\u9996\u4e2a\u53ef\u7528).
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "\u672a\u63d0\u4f9b\u6587\u4ef6; please use\u8868\u5355\u5b57\u6bb5 file \u4e0a\u4f20\u56fe\u7247"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"does not support\u7684\u7c7b\u578b: {content_type}.\u5141\u8bb8: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # \u5148\u8bfb\u53d6\u9650\u5b9a\u5927\u5c0f; \u518d\u68c0check\u662f\u5426\u8fd8\u6709\u5269\u4f59 (\u8bed\u4e49\u6e05\u6670: \u8d85\u51fa\u5219\u62d2\u7edd)
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"\u56fe\u7247\u8d85\u8fc7 {MAX_SIZE_BYTES // (1024 * 1024)}MB limit",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"\u8bfb\u53d6\u4e0a\u4f20\u6587\u4ef6failed: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "\u8bfb\u53d6\u4e0a\u4f20\u6587\u4ef6failed"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"\u56fe\u7247\u63d0\u53d6failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "\u56fe\u7247\u63d0\u53d6failed"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "\u89e3\u6790result"},
        400: {"description": "\u672a\u63d0\u4f9b\u6570\u636eorparse failed", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u89e3\u6790 CSV/Excel/\u526a\u8d34\u677f",
    description="\u4e0a\u4f20 CSV/Excel \u6587\u4ef6or\u7c98\u8d34\u6587\u672c; \u81ea\u52a8\u89e3\u6790stock code.\u6587\u4ef6\u4e0a\u9650 2MB; \u6587\u672c\u4e0a\u9650 100KB.",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    \u89e3\u6790 CSV/Excel \u6587\u4ef6or\u526a\u8d34\u677f\u6587\u672c.

    - multipart/form-data + file: \u4e0a\u4f20\u6587\u4ef6
    - application/json + {"text": "..."}: \u7c98\u8d34\u6587\u672c
    - \u4f18\u5148\u4f7f\u7528 file; \u82e5\u540c\u65f6\u63d0\u4f9b\u5219\u5ffd\u7565 text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"JSON parse failed: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "\u672a\u63d0\u4f9b text; please use {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "\u672a\u63d0\u4f9b\u6587\u4ef6; please use\u8868\u5355\u5b57\u6bb5 file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"file exceeds {MAX_FILE_BYTES // (1024 * 1024)}MB limit",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"file exceeds {MAX_FILE_BYTES // (1024 * 1024)}MB limit",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "\u8bfb\u53d6\u6587\u4ef6failed"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "please use multipart/form-data \u4e0a\u4f20\u6587\u4ef6; or application/json \u63d0\u4ea4 {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "current watchlist hasqueue"},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6\u81ea\u9009queue",
    description="\u8fd4\u56de\u5f53\u524d STOCK_LIST configMedium\u7684\u6240\u6709stock code.",
)
def get_watchlist(
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        codes = _read_watchlist_codes(service)
        return WatchlistResponse(stock_codes=codes, message=f"current watchlist has {len(codes)} stocks")
    except Exception as e:
        logger.error(f"\u83b7\u53d6\u81ea\u9009queuefailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"\u83b7\u53d6\u81ea\u9009queuefailed: {str(e)}"},
        )


@router.post(
    "/watchlist/add",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "added\u81ea\u9009"},
        400: {"description": "invalid parameters", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u52a0\u5165\u81ea\u9009queue",
    description="\u5c06\u6307\u5b9astock code\u52a0\u5165 STOCK_LIST.",
)
def add_to_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        if _watchlist_match_key(validated) not in existing_keys:
            codes.append(request.stock_code.strip())
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"added {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"\u52a0\u5165\u81ea\u9009failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"\u52a0\u5165\u81ea\u9009failed: {str(e)}"},
        )


@router.post(
    "/watchlist/remove",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "\u5df2\u4ece\u81ea\u9009\u5220\u9664"},
        400: {"description": "invalid parameters", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u4ece\u81ea\u9009queue\u5220\u9664",
    description="\u4ece STOCK_LIST Medium\u79fb\u9664\u6307\u5b9astock code.",
)
def remove_from_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        requested_key = _watchlist_match_key(validated)
        if requested_key in existing_keys:
            idx = existing_keys.index(requested_key)
            codes.pop(idx)
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"removed {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"\u4ece\u81ea\u9009delete failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"\u4ece\u81ea\u9009delete failed: {str(e)}"},
        )


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "\u884c\u60c5\u6570\u636e"},
        404: {"description": "\u80a1\u7968does not exist", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6\u80a1\u7968realtime quote",
    description="\u83b7\u53d6\u6307\u5b9a\u80a1\u7968\u7684\u6700\u65b0\u884c\u60c5\u6570\u636e"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    \u83b7\u53d6\u80a1\u7968realtime quote

    \u83b7\u53d6\u6307\u5b9a\u80a1\u7968\u7684\u6700\u65b0\u884c\u60c5\u6570\u636e

    Args:
        stock_code: stock code (\u5982 600519、00700、AAPL)

    Returns:
        StockQuote: realtime quote\u6570\u636e

    Raises:
        HTTPException: 404 - \u80a1\u7968does not exist
    """
    try:
        service = StockService()

        # \u4f7f\u7528 def \u800c\u975e async def; FastAPI \u81ea\u52a8\u5728\u7ebf\u7a0b\u6c60Medium\u6267\u884c
        result = service.get_realtime_quote(stock_code)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"\u672a\u627e\u5230\u80a1\u7968 {stock_code} \u7684\u884c\u60c5\u6570\u636e"
                }
            )

        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"\u83b7\u53d6realtime quotefailed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"\u83b7\u53d6realtime quotefailed: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "history\u884c\u60c5\u6570\u636e"},
        422: {"description": "does not support\u7684\u5468\u671fparameter", "model": ErrorResponse},
        500: {"description": "\u670d\u52a1\u5668error", "model": ErrorResponse},
    },
    summary="\u83b7\u53d6\u80a1\u7968history\u884c\u60c5",
    description="\u83b7\u53d6\u6307\u5b9a\u80a1\u7968\u7684history K \u7ebf\u6570\u636e"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K \u7ebf\u5468\u671f", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="\u83b7\u53d6\u5929\u6570")
) -> StockHistoryResponse:
    """
    \u83b7\u53d6\u80a1\u7968history\u884c\u60c5

    \u83b7\u53d6\u6307\u5b9a\u80a1\u7968\u7684history K \u7ebf\u6570\u636e

    Args:
        stock_code: stock code
        period: K \u7ebf\u5468\u671f (daily/weekly/monthly)
        days: \u83b7\u53d6\u5929\u6570

    Returns:
        StockHistoryResponse: history\u884c\u60c5\u6570\u636e
    """
    try:
        service = StockService()

        # \u4f7f\u7528 def \u800c\u975e async def; FastAPI \u81ea\u52a8\u5728\u7ebf\u7a0b\u6c60Medium\u6267\u884c
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )

        # \u8f6c\u6362\u4e3a\u54cd\u5e94\u6a21\u578b
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]

        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data
        )

    except ValueError as e:
        # period parameterdoes not support\u7684error (\u5982 weekly/monthly)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"\u83b7\u53d6history\u884c\u60c5failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"\u83b7\u53d6history\u884c\u60c5failed: {str(e)}"
            }
        )
