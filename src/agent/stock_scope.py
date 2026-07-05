# -*- coding: utf-8 -*-
"""Stock-scope helpers for ask-stock follow-up chat turns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set


SWITCH_CLEANUP_KEYS = {
    "stock_name",
    "previous_analysis_summary",
    "previous_strategy",
    "previous_price",
    "previous_change_pct",
    "realtime_quote",
    "daily_history",
    "chip_distribution",
    "trend_result",
    "news_context",
    "fundamental_context",
    "analysis_context_pack_summary",
    "market_phase_context",
}

_STRONG_COMPARE_PATTERN = re.compile(r"\u6bd4\u8f83|\u5bf9\u6bd4|vs\b|\u548c[^; .,.!?！？]{0,40}\u6bd4", re.IGNORECASE)
_WEAK_COMPARE_HINT_PATTERN = re.compile(r"\u5dee\u5f02(?!\u5316)|\u533a\u522b|\u4e0d\u540c|\u76f8\u6bd4|\u5bf9\u7167|\u6bd4\u4e00\u6bd4")
_CHOICE_COMPARE_PATTERN = re.compile(r"\u54ea\u4e2a|\u54ea\u53ea|\u54ea\u4e00\u4e2a|\u8c01\u66f4|\u66f4\u503c\u5f97|\u66f4\u9002\u5408|\u600e\u4e48\u9009|\u9009\u54ea|\u4e8c\u9009\u4e00")
_LINKED_COMPARE_PATTERN = re.compile(
    r"(?:\u548c|\u4e0e|\u8ddf|\u540c)(?P<body>[^; .,.!?！？]{0,40})(?:\u5dee\u5f02(?!\u5316)|\u533a\u522b|\u4e0d\u540c|\u76f8\u6bd4|\u5bf9\u7167|\u6bd4\u4e00\u6bd4)"
)
_SWITCH_PATTERN = re.compile(r"\u6362\u6210|\u6539\u770b|analyze|\u770b\u770b|\u7814\u7a76|\u8bca\u65ad")
_LOWERCASE_TICKER_PATTERN = re.compile(r"(?<![a-zA-Z.])([a-z]{2,5}(?:\.[a-z]{1,2})?)(?![a-zA-Z0-9])")
_EXCHANGE_TOKEN_CANDIDATES = {"SH", "SZ", "BJ", "HK", "SS"}
_CONTEXTUAL_INDICATOR_TOKENS = {"MA"}
_INDICATOR_CONTEXT_PATTERN = re.compile(
    r"\u6307\u6807|\u5747\u7ebf|\u79fb\u52a8\u5e73\u5747|\u6392\u5217|\u591a\u5934|\u7a7a\u5934|\u91d1\u53c9|\u6b7b\u53c9|\u652f\u6491|\u538b\u529b|MA\d|SMA|EMA",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StockScope:
    """Runtime stock-scope contract for one chat turn."""

    expected_stock_code: str = ""
    allowed_stock_codes: Set[str] = field(default_factory=set)
    mode: str = "maintain"

    def as_log_payload(self) -> Dict[str, Any]:
        return {
            "expected_stock_code": self.expected_stock_code,
            "allowed_stock_codes": sorted(self.allowed_stock_codes),
            "mode": self.mode,
        }


@dataclass(frozen=True)
class StockScopeResolution:
    """Result produced before a chat turn enters the agent loop."""

    effective_context: Dict[str, Any]
    stock_scope: Optional[StockScope]


def _normalize_stock_code(value: Any) -> str:
    """Normalize a code with the runner's canonical stock-code rules."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    try:
        from src.agent.runner import _normalize_tool_stock_code

        normalized = _normalize_tool_stock_code(text)
    except Exception:
        normalized = text.strip().upper()
    return normalized if isinstance(normalized, str) else str(normalized)


def _is_denied_candidate(candidate: str, text: str = "") -> bool:
    token = candidate.strip().upper()
    if token in _EXCHANGE_TOKEN_CANDIDATES:
        return True
    if token in _CONTEXTUAL_INDICATOR_TOKENS and _INDICATOR_CONTEXT_PATTERN.search(text or ""):
        return True
    try:
        from src.agent.orchestrator import _COMMON_WORDS

        return token in _COMMON_WORDS
    except Exception:
        return False


def _append_candidate(candidates: List[str], candidate: str, text: str = "") -> None:
    normalized = _normalize_stock_code(candidate)
    if not normalized or _is_denied_candidate(normalized, text):
        return
    if normalized not in candidates:
        candidates.append(normalized)


def extract_stock_codes(text: str) -> List[str]:
    """Extract all explicit stock-code candidates from free text."""
    if not text:
        return []

    candidates: List[str] = []

    for pattern, flags in (
        (r"(?<![a-zA-Z])(?:SH|SZ|BJ)\d{6}(?!\d)", re.IGNORECASE),
        (r"(?<![a-zA-Z])hk\d{4,5}(?!\d)", re.IGNORECASE),
        (r"(?<![a-zA-Z])\d{1,5}\.HK(?![a-zA-Z])", re.IGNORECASE),
        (r"(?<!\d)(?:[03648]\d{5}|92\d{4})(?!\d)", 0),
        (r"(?<!\d)\d{5}(?!\d)", 0),
        (r"(?<![a-zA-Z.])([A-Z]{2,5}(?:\.[A-Z]{1,2})?)(?![a-zA-Z0-9])", 0),
    ):
        for match in re.finditer(pattern, text, flags):
            raw = match.group(1) if match.lastindex else match.group(0)
            _append_candidate(candidates, raw, text)

    if (
        _SWITCH_PATTERN.search(text)
        or _STRONG_COMPARE_PATTERN.search(text)
        or _WEAK_COMPARE_HINT_PATTERN.search(text)
        or _CHOICE_COMPARE_PATTERN.search(text)
    ):
        for match in _LOWERCASE_TICKER_PATTERN.finditer(text):
            _append_candidate(candidates, match.group(1), text)

    return candidates


def _is_compare_message(message: str, candidates: List[str], current_code: str) -> bool:
    if _STRONG_COMPARE_PATTERN.search(message):
        return True
    new_candidates = {code for code in candidates if code != current_code}
    if len(new_candidates) >= 2:
        return True
    if _CHOICE_COMPARE_PATTERN.search(message) and len(candidates) >= 2:
        return True
    if not _WEAK_COMPARE_HINT_PATTERN.search(message):
        return False
    if len(candidates) >= 2:
        return True

    if not new_candidates:
        return False

    for match in _LINKED_COMPARE_PATTERN.finditer(message):
        body_candidates = set(extract_stock_codes(f"\u6bd4\u8f83 {match.group('body')}"))
        if body_candidates & new_candidates:
            return True
    return False


def _with_skills(context: Dict[str, Any], skills: Optional[Iterable[str]]) -> Dict[str, Any]:
    if skills is None:
        return context
    next_context = dict(context)
    next_context["skills"] = list(skills)
    return next_context


def _switch_context(context: Dict[str, Any], stock_code: str) -> Dict[str, Any]:
    next_context = {
        key: value
        for key, value in context.items()
        if key not in SWITCH_CLEANUP_KEYS and key != "allowed_stock_codes"
    }
    next_context["stock_code"] = stock_code
    next_context["stock_name"] = ""
    return next_context


def resolve_stock_scope(
    message: str,
    context: Optional[Dict[str, Any]],
    *,
    skills: Optional[Iterable[str]] = None,
) -> StockScopeResolution:
    """Resolve the effective context and stock tool scope for one chat turn."""
    original_context = dict(context or {})
    message_text = message or ""
    current_code = _normalize_stock_code(original_context.get("stock_code"))
    invalid_context_code = bool(current_code and _is_denied_candidate(current_code, message_text))
    original_context.pop("allowed_stock_codes", None)
    if invalid_context_code:
        original_context.pop("stock_code", None)
        original_context.pop("stock_name", None)
        current_code = ""

    if not current_code:
        if invalid_context_code:
            candidates = extract_stock_codes(message_text)
            allowed = set(candidates)
            expected = candidates[0] if len(candidates) == 1 else ""
            effective_context = dict(original_context)
            mode = "switch" if expected else ("compare" if len(candidates) > 1 else "maintain")
            if expected:
                effective_context["stock_code"] = expected
                effective_context["stock_name"] = ""
            return StockScopeResolution(
                effective_context=_with_skills(effective_context, skills),
                stock_scope=StockScope(
                    expected_stock_code=expected,
                    allowed_stock_codes=allowed,
                    mode=mode,
                ),
            )
        return StockScopeResolution(
            effective_context=_with_skills(original_context, skills),
            stock_scope=None,
        )

    candidates = extract_stock_codes(message_text)
    new_candidates = [code for code in candidates if code != current_code]
    mode = "maintain"
    effective_context = dict(original_context)
    expected = current_code
    allowed = {current_code}

    if _is_compare_message(message_text, candidates, current_code):
        mode = "compare"
        allowed.update(candidates)
    elif _SWITCH_PATTERN.search(message_text) and len(new_candidates) == 1:
        mode = "switch"
        expected = new_candidates[0]
        allowed = {expected}
        effective_context = _switch_context(original_context, expected)

    effective_context["stock_code"] = expected if mode == "switch" else current_code
    effective_context = _with_skills(effective_context, skills)

    return StockScopeResolution(
        effective_context=effective_context,
        stock_scope=StockScope(
            expected_stock_code=expected,
            allowed_stock_codes=allowed,
            mode=mode,
        ),
    )
