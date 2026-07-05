# -*- coding: utf-8 -*-
"""
===================================
LongbridgeFetcher - Longbridge\u515c\u5e95data source (Priority 5)
===================================

\u6570\u636esource: Longbridge OpenAPI (https://open.longbridge.com)
\u7279\u70b9: \u8986\u76d6US stock + HK stock; \u53ef\u8ba1\u7b97\u91cf\u6bd4/turnover/PE \u7b49 yfinance \u7f3a\u5931\u5b57\u6bb5
\u5b9acharacters: US stock/HK stock\u6700\u540e\u515c\u5e95data source

\u5173\u952estrategy:
1. \u7ec4\u5408 quote + static_info \u63a5\u53e3\u8ba1\u7b97 turnover_rate / pe_ratio / total_mv
2. \u901a\u8fc7 history_candlesticks \u8ba1\u7b97 volume_ratio (\u8fd15\u65e5\u5747\u91cf\u6bd4)
3. \u61d2load QuoteContext; \u9996\u6b21\u8c03\u7528\u65f6\u624d\u5efa\u7acb\u8fde\u63a5
4. static_info \u8fdb\u7a0b\u5185\u77edcache; \u51cf\u5c11\u91cd\u590drequest (default 24h; \u53ef\u8c03；\u89c1 LONGBRIDGE_STATIC_INFO_TTL_SECONDS)

\u51ed\u8bc1: \u4f18\u5148\u4f7f\u7528 `LONGBRIDGE_OAUTH_CLIENT_ID` + SDK token cache (OAuth 2.0)；
Legacy API Key \u4e09\u4ef6\u5957 (`LONGBRIDGE_APP_KEY` / `LONGBRIDGE_APP_SECRET` / `LONGBRIDGE_ACCESS_TOKEN`)\u4ecd\u517c\u5bb9.
optional: `LONGBRIDGE_STATIC_INFO_TTL_SECONDS`；SDK `language` \u53d6\u81ea `REPORT_LANGUAGE`; `log_path` \u4e3a `{LOG_DIR}/longbridge_sdk.log`；
`LONGBRIDGE_HTTP_URL` / `LONGBRIDGE_QUOTE_WS_URL` / `LONGBRIDGE_TRADE_WS_URL` / `LONGBRIDGE_REGION`  (\u89c1\u5b98\u65b9docsdefault\u503c).
"""

import base64
import binascii
import json
import logging
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd

from .base import BaseFetcher, STANDARD_COLUMNS
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource, safe_float
from .us_index_mapping import is_us_stock_code, is_us_index_code

logger = logging.getLogger(__name__)

_DEFAULT_STATIC_INFO_TTL = 86400  # 24h
_DEFAULT_CONNECTION_COOLDOWN_SECONDS = 15


def _static_info_ttl_seconds() -> int:
    """TTL for static_info cache; 0 disables caching (always fetch)."""
    raw = os.getenv("LONGBRIDGE_STATIC_INFO_TTL_SECONDS", "").strip()
    if raw == "":
        return _DEFAULT_STATIC_INFO_TTL
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_STATIC_INFO_TTL


def _connection_cooldown_seconds() -> int:
    """Cooldown after connection-close errors to avoid reconnect thrashing."""
    raw = os.getenv("LONGBRIDGE_CONNECTION_COOLDOWN_SECONDS", "").strip()
    if raw == "":
        return _DEFAULT_CONNECTION_COOLDOWN_SECONDS
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_CONNECTION_COOLDOWN_SECONDS


_REGION_URL_MAP: Dict[str, Dict[str, str]] = {
    "cn": {
        "http_url": "https://openapi.longbridge.cn",
        "quote_ws_url": "wss://openapi-quote.longbridge.cn/v2",
        "trade_ws_url": "wss://openapi-trade.longbridge.cn/v2",
    },
    "hk": {
        "http_url": "https://openapi.longbridge.com",
        "quote_ws_url": "wss://openapi-quote.longbridge.com/v2",
        "trade_ws_url": "wss://openapi-trade.longbridge.com/v2",
    },
}


def _sanitize_longbridge_env() -> None:
    """Remove empty-string LONGBRIDGE_*_URL env vars.

    GitHub Actions sets ``LONGBRIDGE_HTTP_URL: ${{ vars.X || secrets.X }}``
    which resolves to an empty string ``""`` when neither var nor secret is
    configured.  The Rust SDK's ``Config.from_apikey()`` auto-reads these
    env vars, and an empty string is *not* the same as "unset" — it causes
    the SDK to use a blank URL, which breaks the WebSocket handshake and
    results in "context dropped" / "Client is closed" within milliseconds.

    Also mirrors ``LONGBRIDGE_REGION`` → ``LONGPORT_REGION`` because the
    Rust SDK's internal ``is_cn()`` function only checks ``LONGPORT_REGION``
    (not ``LONGBRIDGE_REGION``) when deciding which default endpoints to use.
    """
    for key in (
        "LONGBRIDGE_HTTP_URL",
        "LONGBRIDGE_QUOTE_WS_URL",
        "LONGBRIDGE_TRADE_WS_URL",
        "LONGBRIDGE_ENABLE_OVERNIGHT",
        "LONGBRIDGE_PUSH_CANDLESTICK_MODE",
        "LONGBRIDGE_PRINT_QUOTE_PACKAGES",
        "LONGBRIDGE_REGION",
        "LONGBRIDGE_STATIC_INFO_TTL_SECONDS",
        "LONGBRIDGE_LOG_PATH",
    ):
        val = os.environ.get(key)
        if val is not None and val.strip() == "":
            del os.environ[key]
            logger.debug("[Longbridge] \u5220\u9664\u7a7a\u73af\u5883\u53d8\u91cf %s", key)

    # App default: quiet (false). Matches README / docs/full-guide / .env.example; SDK alone may default verbose.
    if "LONGBRIDGE_PRINT_QUOTE_PACKAGES" not in os.environ:
        os.environ["LONGBRIDGE_PRINT_QUOTE_PACKAGES"] = "false"

    if not os.environ.get("LONGBRIDGE_LOG_PATH"):
        try:
            log_dir = (os.getenv("LOG_DIR") or "./logs").strip() or "./logs"
            p = Path(log_dir).expanduser()
            p.mkdir(parents=True, exist_ok=True)
            os.environ["LONGBRIDGE_LOG_PATH"] = str(p / "longbridge_sdk.log")
            logger.debug("[Longbridge] \u8bbe\u7f6e LONGBRIDGE_LOG_PATH=%s",
                         os.environ["LONGBRIDGE_LOG_PATH"])
        except Exception:
            pass

    region = (os.getenv("LONGBRIDGE_REGION") or "").strip().lower()
    if region:
        if not os.environ.get("LONGPORT_REGION"):
            os.environ["LONGPORT_REGION"] = region
            logger.debug("[Longbridge] \u540c\u6b65 LONGPORT_REGION=%s", region)

        urls = _REGION_URL_MAP.get(region, {})
        for env_name, default_url in (
            ("LONGBRIDGE_HTTP_URL", urls.get("http_url")),
            ("LONGBRIDGE_QUOTE_WS_URL", urls.get("quote_ws_url")),
            ("LONGBRIDGE_TRADE_WS_URL", urls.get("trade_ws_url")),
        ):
            if default_url and not os.environ.get(env_name):
                os.environ[env_name] = default_url
                logger.debug("[Longbridge] \u6839\u636e REGION=%s \u8bbe\u7f6e %s=%s",
                             region, env_name, default_url)


def _longbridge_config_kwargs() -> Dict[str, Any]:
    """Optional kwargs for ``Config.from_apikey`` (Longbridge OpenAPI SDK)."""
    try:
        import inspect
        from longbridge.openapi import Config, Language, PushCandlestickMode
    except Exception:
        return {}

    try:
        params = inspect.signature(Config.from_apikey).parameters
    except Exception:
        return {}

    kw: Dict[str, Any] = {}

    if "enable_print_quote_packages" in params:
        # Unset / empty → False (quiet); SDK default would be verbose — we opt in explicitly.
        raw = os.getenv("LONGBRIDGE_PRINT_QUOTE_PACKAGES")
        if raw is None or not str(raw).strip():
            kw["enable_print_quote_packages"] = False
        else:
            raw_norm = str(raw).strip().lower()
            kw["enable_print_quote_packages"] = raw_norm not in ("0", "false", "no")

    for pname, envname in (
        ("http_url", "LONGBRIDGE_HTTP_URL"),
        ("quote_ws_url", "LONGBRIDGE_QUOTE_WS_URL"),
        ("trade_ws_url", "LONGBRIDGE_TRADE_WS_URL"),
    ):
        if pname in params:
            v = os.getenv(envname, "").strip()
            if v:
                kw[pname] = v

    if "language" in params:
        try:
            from src.report_language import normalize_report_language

            rl = normalize_report_language(os.getenv("REPORT_LANGUAGE"), default="zh")
            if rl == "zh":
                kw["language"] = Language.ZH_CN
            elif rl == "en":
                kw["language"] = Language.EN
        except Exception as e:
            logger.debug("Longbridge language from REPORT_LANGUAGE skipped: %s", e)

    if "enable_overnight" in params:
        o = os.getenv("LONGBRIDGE_ENABLE_OVERNIGHT", "").strip().lower()
        if o:
            kw["enable_overnight"] = o in ("1", "true", "yes")

    if "push_candlestick_mode" in params:
        cm = os.getenv("LONGBRIDGE_PUSH_CANDLESTICK_MODE", "").strip().lower()
        if cm == "realtime":
            kw["push_candlestick_mode"] = PushCandlestickMode.Realtime
        elif cm == "confirmed":
            kw["push_candlestick_mode"] = PushCandlestickMode.Confirmed
        elif cm:
            logger.warning(
                "Unknown LONGBRIDGE_PUSH_CANDLESTICK_MODE=%r; use realtime or confirmed", cm
            )

    if "log_path" in params:
        try:
            log_dir = (os.getenv("LOG_DIR") or "./logs").strip() or "./logs"
            p = Path(log_dir).expanduser()
            p.mkdir(parents=True, exist_ok=True)
            kw["log_path"] = str(p / "longbridge_sdk.log")
        except Exception as e:
            logger.debug("Longbridge log_path from LOG_DIR skipped: %s", e)

    return kw


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _oauth_token_cache_path(client_id: str) -> Path:
    return Path.home() / ".longbridge" / "openapi" / "tokens" / client_id


def _restore_oauth_token_cache_from_env(client_id: str) -> bool:
    """Restore the SDK OAuth token cache from a GitHub Actions/Docker secret.

    The Longbridge SDK expects its OAuth token cache at
    ``~/.longbridge/openapi/tokens/<client_id>``.  In headless environments the
    file can be provided as base64 through ``LONGBRIDGE_OAUTH_TOKEN_CACHE_B64``.
    If an env cache is supplied and differs from the existing file, treat the
    env value as the operator-provided recovery source for headless runs.
    """
    raw = os.getenv("LONGBRIDGE_OAUTH_TOKEN_CACHE_B64")
    if not raw:
        return False

    try:
        payload = base64.b64decode("".join(raw.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        logger.warning("[Longbridge] OAuth token cache base64 \u89e3\u7801failed: %s", exc)
        return False

    if not payload:
        logger.warning("[Longbridge] OAuth token cache base64 \u4e3a\u7a7a; skipping\u6062\u590d")
        return False

    token_cache = _oauth_token_cache_path(client_id)
    if token_cache.exists():
        try:
            if token_cache.read_bytes() == payload:
                logger.debug("[Longbridge] OAuth token cache\u5df2\u4e0e env secret \u4e00\u81f4; skipping\u6062\u590d: %s", token_cache)
                return False
        except OSError as exc:
            logger.warning("[Longbridge] \u8bfb\u53d6\u73b0\u6709 OAuth token cachefailed; \u5c06\u5c1d\u8bd5\u7528 env secret \u8986\u76d6: %s", exc)

    try:
        token_cache.parent.mkdir(parents=True, exist_ok=True)
        token_cache.write_bytes(payload)
        token_cache.chmod(0o600)
        logger.info("[Longbridge] \u5df2\u4ece LONGBRIDGE_OAUTH_TOKEN_CACHE_B64 \u6062\u590d OAuth token cache")
        return True
    except Exception as exc:
        logger.warning("[Longbridge] \u5199\u5165 OAuth token cachefailed: %s", exc)
        return False


def _is_valid_oauth_cache_file(token_cache: Path) -> bool:
    """Basic health check for SDK token cache content.

    We avoid attempting interactive OAuth flows when the cache is missing or
    malformed, so headless jobs fail explicitly instead of hanging for manual
    re-authorization.
    """
    if not token_cache.exists():
        return False

    try:
        raw = token_cache.read_bytes()
    except OSError as exc:
        logger.warning("[Longbridge] \u8bfb\u53d6 OAuth token cachefailed: %s", exc)
        return False

    if not raw.strip():
        logger.warning("[Longbridge] OAuth token cache\u4e3a\u7a7a\u6587\u4ef6: %s", token_cache)
        return False

    try:
        payload = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        logger.warning("[Longbridge] OAuth token cache\u4e0d\u662f UTF-8 \u6587\u672c: %s", exc)
        return False

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.warning("[Longbridge] OAuth token cache\u4e0d\u662f\u5408\u6cd5 JSON: %s", exc)
        return False

    if not isinstance(data, dict) or not data:
        logger.warning("[Longbridge] OAuth token cache\u5185\u5bb9\u4e3a\u7a7aor\u683c\u5f0f\u4e0d\u7b26\u5408\u9884\u671f: %s", token_cache)
        return False

    return True


def _oauth_reauth_not_supported(url: str) -> None:
    raise RuntimeError(
        f"OAuth token cache\u5df2\u5931\u6548or\u7f3a\u5931; \u5f53\u524d\u4e3a\u65e0\u5934\u8fd0\u884cdoes not support\u6253\u5f00\u6388\u6743\u9875\u9762; \u8bf7\u91cd\u5efa LONGBRIDGE_OAUTH_TOKEN_CACHE_B64: {url}"
    )


def _oauth_sdk_unavailable_error() -> RuntimeError:
    return RuntimeError(
        "\u5f53\u524d\u5b89\u88c5\u7684 longbridge SDK does not support OAuth 2.0 (\u7f3a\u5c11 OAuthBuilder/Config.from_oauth)."
        "\u8bf7\u5728\u652f\u6301\u8be5 SDK \u7248\u672c\u7684\u5e73\u53f0\u5b89\u88c5 longbridge>=4.0.0; or\u7ee7\u7eed\u4f7f\u7528 Legacy \u4e09\u4ef6\u5957."
    )


def _longbridge_credentials(config: Any = None) -> Dict[str, Optional[str]]:
    """Collect Longbridge auth inputs from Config/env without exposing secrets."""
    app_key = _clean_optional(getattr(config, "longbridge_app_key", None))
    app_secret = _clean_optional(getattr(config, "longbridge_app_secret", None))
    access_token = _clean_optional(getattr(config, "longbridge_access_token", None))
    oauth_client_id = _clean_optional(getattr(config, "longbridge_oauth_client_id", None))

    app_key = app_key or _clean_optional(os.getenv("LONGBRIDGE_APP_KEY"))
    app_secret = app_secret or _clean_optional(os.getenv("LONGBRIDGE_APP_SECRET"))
    access_token = access_token or _clean_optional(os.getenv("LONGBRIDGE_ACCESS_TOKEN"))
    oauth_client_id = oauth_client_id or _clean_optional(os.getenv("LONGBRIDGE_OAUTH_CLIENT_ID"))

    # Some Longbridge pages label the OAuth public client id as "App Key".
    # Use it as a compatibility alias only when no Legacy access token exists.
    if not oauth_client_id and app_key and not access_token:
        oauth_client_id = app_key

    return {
        "app_key": app_key,
        "app_secret": app_secret,
        "access_token": access_token,
        "oauth_client_id": oauth_client_id,
    }


def _has_legacy_credentials(creds: Dict[str, Optional[str]]) -> bool:
    return bool(creds.get("app_key") and creds.get("app_secret") and creds.get("access_token"))


def _has_oauth_credentials(creds: Dict[str, Optional[str]]) -> bool:
    return bool(creds.get("oauth_client_id"))


def _is_us_code(stock_code: str) -> bool:
    normalized = stock_code.strip().upper()
    return is_us_stock_code(normalized) or is_us_index_code(normalized)


def _is_hk_code(stock_code: str) -> bool:
    normalized = (stock_code or "").strip().upper()
    if normalized.startswith("HK"):
        digits = normalized[2:]
        return digits.isdigit() and 1 <= len(digits) <= 5
    if normalized.endswith(".HK"):
        return True
    if normalized.isdigit() and len(normalized) == 5:
        return True
    return False


def _to_longbridge_symbol(stock_code: str) -> Optional[str]:
    """Convert internal stock code to Longbridge symbol format.

    Examples:
        AAPL      -> AAPL.US
        HK00700   -> 0700.HK
        00700     -> 0700.HK (5-digit pure number treated as HK)
    """
    code = stock_code.strip()
    upper = code.upper()

    if upper.endswith(".US"):
        return upper
    if upper.endswith(".HK"):
        return upper

    if _is_us_code(code):
        return f"{upper}.US"

    if _is_hk_code(code):
        upper = code.upper()
        if upper.startswith("HK"):
            digits = upper[2:]
        else:
            digits = upper
        digits = digits.lstrip("0") or "0"
        return f"{digits.zfill(4)}.HK"

    return None


class LongbridgeFetcher(BaseFetcher):
    """
    Longbridge OpenAPI data source\u5b9e\u73b0

    \u4f18\u5148\u7ea7: 5 (\u6700Low; \u4f5c\u4e3aUS stock/HK stock\u6700\u540e\u515c\u5e95)
    \u6570\u636esource: Longbridge OpenAPI

    \u901a\u8fc7\u7ec4\u5408\u591a\u4e2a API \u8ba1\u7b97 yfinance \u7f3a\u5931\u7684\u6307\u6807:
    - turnover_rate = volume / circulating_shares * 100
    - volume_ratio = today_volume / avg_5day_volume
    - pe_ratio = price / eps_ttm
    """

    name = "LongbridgeFetcher"
    priority = int(os.getenv("LONGBRIDGE_PRIORITY", "5"))

    _CONNECTION_ERRORS = ("client is closed", "context closed", "connection closed")

    def __init__(self):
        self._ctx = None
        self._config = None
        self._ctx_lock = threading.Lock()
        self._available = None
        self._cooldown_until = 0.0
        # {symbol: (StaticInfo, timestamp)}
        self._static_cache: Dict[str, Any] = {}
        self._static_cache_lock = threading.Lock()

    def _is_connection_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(s in msg for s in self._CONNECTION_ERRORS)

    def _invalidate_ctx(self):
        """Reset cached context so the next call rebuilds the connection."""
        with self._ctx_lock:
            self._ctx = None
            self._config = None

    def _mark_connection_cooldown(self, exc: Exception) -> None:
        cooldown_seconds = _connection_cooldown_seconds()
        self._invalidate_ctx()
        if cooldown_seconds <= 0:
            return
        self._cooldown_until = time.time() + cooldown_seconds
        logger.warning(
            "[Longbridge] \u68c0\u6d4b\u5230\u8fde\u63a5\u5f02\u5e38; \u8fdb\u5165 %ss \u51b7\u5374\u671f\u4ee5\u907f\u514d\u9891\u7e41\u91cd\u8fde: %s",
            cooldown_seconds,
            exc,
        )

    def is_available_for_request(self, capability: str = "") -> bool:
        """Report request-time availability including temporary cooldown."""
        if not self._is_available():
            return False
        if self._cooldown_until > time.time():
            logger.debug(
                "[Longbridge] %s \u51b7\u5374Medium; \u6682\u65f6skippingrequest; \u5269\u4f59 %.1fs",
                capability or "request",
                self._cooldown_until - time.time(),
            )
            return False
        if self._cooldown_until:
            self._cooldown_until = 0.0
        return True

    def _is_available(self) -> bool:
        """Check if Longbridge credentials are configured (OAuth or Legacy)."""
        if self._available is not None:
            return self._available
        try:
            from src.config import get_config
            creds = _longbridge_credentials(get_config())
        except Exception:
            creds = _longbridge_credentials()
        self._available = _has_legacy_credentials(creds) or _has_oauth_credentials(creds)
        return self._available

    @staticmethod
    def has_configured_credentials(config: Any = None) -> bool:
        """Return True when runtime config can attempt Longbridge auth."""
        creds = _longbridge_credentials(config)
        return _has_legacy_credentials(creds) or _has_oauth_credentials(creds)

    def _get_ctx(self):
        """Lazy-init the QuoteContext (thread-safe)."""
        if self._ctx is not None:
            return self._ctx
        with self._ctx_lock:
            if self._ctx is not None:
                return self._ctx
            if not self._is_available():
                return None
            try:
                from longbridge.openapi import QuoteContext, Config

                # ── 1. Clean up empty URL env vars & apply REGION mapping ──
                _sanitize_longbridge_env()

                # ── 2. Collect credentials and mirror Legacy values to env ──
                try:
                    from src.config import get_config
                    app_config = get_config()
                except Exception:
                    app_config = None

                creds = _longbridge_credentials(app_config)
                app_key = creds["app_key"]
                app_secret = creds["app_secret"]
                access_token = creds["access_token"]
                oauth_client_id = creds["oauth_client_id"]
                has_legacy = _has_legacy_credentials(creds)

                for k, v in {
                    "LONGBRIDGE_APP_KEY": app_key,
                    "LONGBRIDGE_APP_SECRET": app_secret,
                    "LONGBRIDGE_ACCESS_TOKEN": access_token,
                }.items():
                    if v and not os.environ.get(k):
                        os.environ[k] = v
                if oauth_client_id and not os.environ.get("LONGBRIDGE_OAUTH_CLIENT_ID"):
                    os.environ["LONGBRIDGE_OAUTH_CLIENT_ID"] = oauth_client_id

                # ── 3. Build Config ──
                extra_kw = _longbridge_config_kwargs()
                lb_config = None
                oauth_error: Optional[Exception] = None

                if oauth_client_id:
                    token_cache = _oauth_token_cache_path(oauth_client_id)
                    _restore_oauth_token_cache_from_env(oauth_client_id)

                    if _is_valid_oauth_cache_file(token_cache):
                        try:
                            from longbridge.openapi import OAuthBuilder

                            oauth = OAuthBuilder(oauth_client_id).build(
                                _oauth_reauth_not_supported,
                            )
                            from_oauth = getattr(Config, "from_oauth", None)
                            if from_oauth is None:
                                raise AttributeError("Config.from_oauth")
                            lb_config = from_oauth(oauth)
                            logger.info("[Longbridge] Config.from_oauth() create succeeded")
                        except (ImportError, AttributeError):
                            oauth_error = _oauth_sdk_unavailable_error()
                            logger.warning("[Longbridge] OAuth SDK unavailable: %s", oauth_error)
                        except Exception as exc:
                            oauth_error = exc
                            logger.warning("[Longbridge] OAuth initialization failed: %s", exc)
                    elif token_cache.exists():
                        logger.warning(
                            "[Longbridge] OAuth token cache\u5185\u5bb9\u5f02\u5e38; \u5df2\u62d2\u7edd\u4ea4\u4e92\u5f0f\u7eed\u671f: %s."
                            "\u8bf7\u5148\u6267\u884c scripts/generate_longbridge_oauth_token.py \u91cd\u5efacache.",
                            token_cache,
                        )
                    else:
                        logger.warning(
                            "[Longbridge] OAuth client \u5df2config; \u4f46 token cachedoes not exist: %s."
                            "\u8bf7\u5148\u6267\u884c scripts/generate_longbridge_oauth_token.py \u751f\u6210cache；"
                            "GitHub Actions/Docker \u53ef\u63d0\u4f9b LONGBRIDGE_OAUTH_TOKEN_CACHE_B64.",
                            token_cache,
                        )

                if lb_config is None and has_legacy:
                    # Legacy fallback is allowed only when the full non-empty
                    # three-piece credential exists; this keeps OAuth-only
                    # failures from being rewritten as API-key failures.
                    for factory_name in ("from_apikey_env", "from_env"):
                        factory = getattr(Config, factory_name, None)
                        if factory is None:
                            continue
                        try:
                            lb_config = factory()
                            logger.info("[Longbridge] Config.%s() success", factory_name)
                            break
                        except Exception as e:
                            logger.debug(
                                "[Longbridge] Config.%s() failed: %s", factory_name, e
                            )

                if lb_config is None and has_legacy:
                    lb_config = Config.from_apikey(
                        app_key,
                        app_secret,
                        access_token,
                        **extra_kw,
                    )
                    logger.info("[Longbridge] Config.from_apikey() create succeeded")
                elif lb_config is None:
                    reason = (
                        f"OAuth initialization failed: {oauth_error}"
                        if oauth_error
                        else "\u672a\u627e\u5230\u53ef\u7528 OAuth token cache\u4e14not configured\u5b8c\u6574 Legacy \u4e09\u4ef6\u5957"
                    )
                    logger.warning("[Longbridge] \u672a\u5efa\u7acb\u8ba4\u8bc1config: %s", reason)
                    self._available = False
                    return None

                # Diagnostic logging
                region = os.getenv("LONGBRIDGE_REGION") or os.getenv("LONGPORT_REGION") or "(auto)"
                logger.info(
                    "[Longbridge] config: region=%s, http=%s, quote_ws=%s",
                    region,
                    os.getenv("LONGBRIDGE_HTTP_URL", "(default)"),
                    os.getenv("LONGBRIDGE_QUOTE_WS_URL", "(default)"),
                )

                self._config = lb_config
                self._ctx = QuoteContext(lb_config)
                logger.info("[Longbridge] QuoteContext initialization succeeded")
                return self._ctx
            except Exception as e:
                logger.warning("[Longbridge] QuoteContext initialization failed: %s", e)
                self._available = False
                return None

    # ------------------------------------------------------------------
    # static_info with cache
    # ------------------------------------------------------------------

    def _get_static_info(self, symbol: str) -> Optional[Any]:
        """Fetch static info (shares, EPS, BPS, name) with optional in-process TTL cache."""
        ttl = _static_info_ttl_seconds()
        now = time.time()
        if ttl > 0:
            with self._static_cache_lock:
                cached = self._static_cache.get(symbol)
                if cached and (now - cached[1]) < ttl:
                    return cached[0]

        ctx = self._get_ctx()
        if ctx is None:
            return None
        try:
            infos = ctx.static_info([symbol])
            if infos:
                info = infos[0]
                if ttl > 0:
                    with self._static_cache_lock:
                        self._static_cache[symbol] = (info, now)
                return info
        except Exception as e:
            logger.debug(f"[Longbridge] static_info({symbol}) failed: {e}")
            if self._is_connection_error(e):
                self._mark_connection_cooldown(e)
        return None

    # ------------------------------------------------------------------
    # get_stock_name via static_info
    # ------------------------------------------------------------------

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """Return stock name from Longbridge static_info (name_cn or name_en)."""
        symbol = _to_longbridge_symbol(stock_code)
        if symbol is None:
            return None
        info = self._get_static_info(symbol)
        if info is None:
            return None
        name = getattr(info, "name_cn", "") or getattr(info, "name_en", "") or ""
        return name.strip() or None

    # ------------------------------------------------------------------
    # volume_ratio from history
    # ------------------------------------------------------------------

    def _ts_sort_key(self, candle: Any) -> float:
        """Monotonic sort key for a candle timestamp (UTC seconds or datetime)."""
        ts = getattr(candle, "timestamp", None)
        if ts is None:
            return 0.0
        if hasattr(ts, "timestamp"):
            return float(ts.timestamp())
        return float(int(ts))

    def _compute_volume_ratio(self, symbol: str, today_volume: int) -> Optional[float]:
        """Compute volume_ratio = today_volume / avg(recent completed daily volumes).

        Uses the most recent daily bar as \"today/incomplete\" reference window: average
        volume of the next 5 older daily bars. Avoids local `date.today()` matching, which
        breaks for US symbols when the shell runs in CN timezone.
        """
        if not today_volume or today_volume <= 0:
            return None
        ctx = self._get_ctx()
        if ctx is None:
            return None
        try:
            from longbridge.openapi import Period, AdjustType

            candles = ctx.history_candlesticks_by_offset(
                symbol,
                Period.Day,
                AdjustType.NoAdjust,
                False,
                6,
                datetime.now(),
            )
            if not candles or len(candles) < 2:
                return None

            ordered = sorted(candles, key=self._ts_sort_key, reverse=True)
            past_vols: list = []
            for c in ordered[1:6]:
                vol = int(getattr(c, "volume", 0) or 0)
                if vol > 0:
                    past_vols.append(vol)

            if not past_vols:
                return None

            avg_vol = sum(past_vols) / len(past_vols)
            if avg_vol <= 0:
                return None

            return round(today_volume / avg_vol, 2)
        except Exception as e:
            logger.debug(f"[Longbridge] \u8ba1\u7b97\u91cf\u6bd4failed({symbol}): {e}")
            return None

    # ------------------------------------------------------------------
    # get_realtime_quote
    # ------------------------------------------------------------------

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """Fetch realtime quote from Longbridge, computing derived fields."""
        if not self.is_available_for_request("realtime_quote"):
            return None

        symbol = _to_longbridge_symbol(stock_code)
        if symbol is None:
            logger.debug(f"[Longbridge] \u65e0\u6cd5\u8f6c\u6362code: {stock_code}")
            return None

        ctx = self._get_ctx()
        if ctx is None:
            return None

        try:
            quotes = ctx.quote([symbol])
            if not quotes:
                return None
            q = quotes[0]
        except Exception as e:
            logger.info(f"[Longbridge] quote({symbol}) failed: {e}")
            if self._is_connection_error(e):
                self._mark_connection_cooldown(e)
            return None

        price = safe_float(getattr(q, "last_done", None))
        if price is None or price <= 0:
            return None

        prev_close = safe_float(getattr(q, "prev_close", None))
        open_price = safe_float(getattr(q, "open", None))
        high = safe_float(getattr(q, "high", None))
        low = safe_float(getattr(q, "low", None))
        volume = int(getattr(q, "volume", 0) or 0)
        turnover = safe_float(getattr(q, "turnover", None))

        change_amount = None
        change_pct = None
        amplitude = None
        if prev_close and prev_close > 0:
            change_amount = round(price - prev_close, 4)
            change_pct = round((price - prev_close) / prev_close * 100, 2)
            if high is not None and low is not None:
                amplitude = round((high - low) / prev_close * 100, 2)

        # Fetch static info for derived fields
        static = self._get_static_info(symbol)

        turnover_rate = None
        pe_ratio = None
        pb_ratio = None
        total_mv = None
        circ_mv = None
        name = ""

        if static is not None:
            name = getattr(static, "name_cn", "") or getattr(static, "name_en", "") or ""
            circulating = int(getattr(static, "circulating_shares", 0) or 0)
            total_shares = int(getattr(static, "total_shares", 0) or 0)
            eps_ttm = safe_float(getattr(static, "eps_ttm", None))
            eps_plain = safe_float(getattr(static, "eps", None))
            bps = safe_float(getattr(static, "bps", None))

            # US names often report circulating_shares=0 while total_shares is set — use total for turnover.
            shares_for_turnover = circulating if circulating > 0 else total_shares
            if shares_for_turnover > 0 and volume > 0:
                turnover_rate = round(volume / shares_for_turnover * 100, 4)
            elif volume > 0:
                logger.debug(
                    "[Longbridge] %s \u65e0\u6cd5\u8ba1\u7b97turnover: volume=%s circulating=%s total_shares=%s",
                    symbol,
                    volume,
                    circulating,
                    total_shares,
                )

            eps_for_pe = None
            if eps_ttm is not None and eps_ttm > 0:
                eps_for_pe = eps_ttm
            elif eps_plain is not None and eps_plain > 0:
                eps_for_pe = eps_plain
            if eps_for_pe:
                pe_ratio = round(price / eps_for_pe, 2)

            if bps is not None and bps > 0:
                pb_ratio = round(price / bps, 2)
            if total_shares > 0:
                total_mv = round(price * total_shares, 2)
            if circulating > 0:
                circ_mv = round(price * circulating, 2)

        volume_ratio = self._compute_volume_ratio(symbol, volume)

        quote = UnifiedRealtimeQuote(
            code=stock_code,
            name=name,
            source=RealtimeSource.LONGBRIDGE,
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            volume=volume if volume > 0 else None,
            amount=turnover,
            volume_ratio=volume_ratio,
            turnover_rate=turnover_rate,
            amplitude=amplitude,
            open_price=open_price,
            high=high,
            low=low,
            pre_close=prev_close,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            total_mv=total_mv,
            circ_mv=circ_mv,
        )

        logger.info(
            f"[Longbridge] {symbol} \u884c\u60c5fetch succeeded: "
            f"price={price}, \u91cf\u6bd4={volume_ratio}, turnover={turnover_rate}"
        )
        return quote

    # ------------------------------------------------------------------
    # BaseFetcher abstract methods (historical daily data)
    # ------------------------------------------------------------------

    def _fetch_raw_data(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch historical candlesticks from Longbridge."""
        if not self.is_available_for_request("daily_data"):
            raise RuntimeError("Longbridge temporarily unavailable for daily_data")

        symbol = _to_longbridge_symbol(stock_code)
        if symbol is None:
            raise ValueError(f"Cannot convert {stock_code} to Longbridge symbol")

        ctx = self._get_ctx()
        if ctx is None:
            raise RuntimeError("Longbridge QuoteContext not available")

        from longbridge.openapi import Period, AdjustType

        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        try:
            candles = ctx.history_candlesticks_by_date(
                symbol,
                Period.Day,
                AdjustType.ForwardAdjust,
                start_dt,
                end_dt,
            )
        except Exception as e:
            if self._is_connection_error(e):
                self._mark_connection_cooldown(e)
            raise

        if not candles:
            return pd.DataFrame()

        rows = []
        for c in candles:
            ts = getattr(c, "timestamp", None)
            if ts is None:
                continue
            if hasattr(ts, "date"):
                dt = ts.date()
            else:
                dt = datetime.fromtimestamp(int(ts)).date()

            rows.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": safe_float(getattr(c, "open", None)),
                "high": safe_float(getattr(c, "high", None)),
                "low": safe_float(getattr(c, "low", None)),
                "close": safe_float(getattr(c, "close", None)),
                "volume": int(getattr(c, "volume", 0) or 0),
                "turnover": safe_float(getattr(c, "turnover", None)),
            })

        return pd.DataFrame(rows)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """Normalize column names to standard format."""
        if df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)

        rename_map = {"turnover": "amount"}
        df = df.rename(columns=rename_map)

        if "pct_chg" not in df.columns and "close" in df.columns:
            df["pct_chg"] = df["close"].pct_change() * 100

        for col in STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = None

        return df[STANDARD_COLUMNS]
