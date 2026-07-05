# -*- coding: utf-8 -*-
"""Prompt rendering for Issue #1386 runtime market phase context."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_PHASE_LABELS_ZH = {
    "premarket": "\u76d8\u524d",
    "intraday": "\u76d8Medium",
    "lunch_break": "\u5348\u95f4\u4f11\u5e02",
    "closing_auction": "\u4e34\u8fd1\u6536\u76d8",
    "postmarket": "\u76d8\u540e",
    "non_trading": "\u975e\u4ea4\u6613\u65e5",
    "unknown": "unknown\u9636\u6bb5",
}

_PHASE_LABELS_EN = {
    "premarket": "pre-market",
    "intraday": "intraday",
    "lunch_break": "lunch break",
    "closing_auction": "near close",
    "postmarket": "post-market",
    "non_trading": "non-trading day",
    "unknown": "unknown phase",
}

_KNOWN_PHASES = set(_PHASE_LABELS_ZH)

_WARNING_LABELS_ZH = {
    "unknown_market": "unknownmarket",
    "calendar_unavailable": "\u4ea4\u6613\u65e5\u5386unavailable",
    "calendar_error": "\u4ea4\u6613\u65e5\u5386\u5f02\u5e38",
}

_WARNING_LABELS_EN = {
    "unknown_market": "unknown market",
    "calendar_unavailable": "trading calendar unavailable",
    "calendar_error": "trading calendar error",
}


def format_market_phase_prompt_section(
    market_phase_context: Optional[Dict[str, Any]],
    *,
    report_language: str = "en",
) -> str:
    """Return a human-readable prompt section for a P1a market phase payload.

    The helper is intentionally narrow: callers pass the runtime dict produced
    by ``MarketPhaseContext.to_dict()`` when available. Missing optional fields
    are omitted, unknown phases use the conservative ``unknown`` template, and
    raw runtime keys such as ``market_phase_context`` are never rendered.
    """
    if not isinstance(market_phase_context, dict) or not market_phase_context:
        return ""

    # Korean reuses the English structural context; the output-language
    # directive (see decision agent) constrains the model to write in Korean.
    lang = "en" if str(report_language or "").lower() in {"en", "ko"} else "zh"
    raw_phase = market_phase_context.get("phase")
    phase = raw_phase if isinstance(raw_phase, str) and raw_phase in _KNOWN_PHASES else "unknown"

    if lang == "en":
        return _format_en(market_phase_context, phase)
    return _format_zh(market_phase_context, phase)


def _format_zh(ctx: Dict[str, Any], phase: str) -> str:
    label = _PHASE_LABELS_ZH[phase]
    lines = ["", "## market\u9636\u6bb5\u4e0a\u4e0b\u6587", f"- \u5f53\u524dmarket\u9636\u6bb5: {label}"]
    lines.extend(_metadata_lines_zh(ctx))
    lines.append(f"- \u9636\u6bb5\u7ea6\u675f: {_phase_rule_zh(ctx, phase)}")

    warning_text = _warning_text(ctx.get("warnings"), lang="zh")
    if warning_text:
        lines.append(f"- \u964d\u7ea7\u8bf4\u660e: {warning_text}; \u8bf7\u4fdd\u6301\u4fdd\u5b88\u8868\u8ff0.")

    return "\n".join(lines) + "\n"


def _format_en(ctx: Dict[str, Any], phase: str) -> str:
    label = _PHASE_LABELS_EN[phase]
    lines = ["", "## Market Phase Context", f"- Current market phase: {label}"]
    lines.extend(_metadata_lines_en(ctx))
    lines.append(f"- Phase constraint: {_phase_rule_en(ctx, phase)}")

    warning_text = _warning_text(ctx.get("warnings"), lang="en")
    if warning_text:
        lines.append(f"- Degradation note: {warning_text}; keep the analysis conservative.")

    return "\n".join(lines) + "\n"


def _metadata_lines_zh(ctx: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    market = _string_value(ctx.get("market"))
    market_time = _string_value(ctx.get("market_local_time"))
    effective_date = _string_value(ctx.get("effective_daily_bar_date"))
    minutes_to_open = _int_like(ctx.get("minutes_to_open"))
    minutes_to_close = _int_like(ctx.get("minutes_to_close"))

    if market:
        items.append(f"- market: {market}")
    if market_time:
        items.append(f"- market\u672c\u5730\u65f6\u95f4: {market_time}")
    if effective_date:
        items.append(f"- \u6700\u65b0\u53ef\u590d\u7528\u5b8c\u6574daily datadate: {effective_date}")
    if minutes_to_open is not None:
        items.append(f"- \u8ddd\u5e38\u89c4\u5f00\u76d8\u7ea6 {minutes_to_open} \u5206\u949f.")
    if minutes_to_close is not None:
        items.append(f"- \u8ddd\u5e38\u89c4\u6536\u76d8\u7ea6 {minutes_to_close} \u5206\u949f.")
    return items


def _metadata_lines_en(ctx: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    market = _string_value(ctx.get("market"))
    market_time = _string_value(ctx.get("market_local_time"))
    effective_date = _string_value(ctx.get("effective_daily_bar_date"))
    minutes_to_open = _int_like(ctx.get("minutes_to_open"))
    minutes_to_close = _int_like(ctx.get("minutes_to_close"))

    if market:
        items.append(f"- Market: {market}")
    if market_time:
        items.append(f"- Market-local time: {market_time}")
    if effective_date:
        items.append(f"- Latest reusable complete daily bar date: {effective_date}")
    if minutes_to_open is not None:
        items.append(f"- About {minutes_to_open} minutes until the regular session opens.")
    if minutes_to_close is not None:
        items.append(f"- About {minutes_to_close} minutes until the regular session closes.")
    return items


def _phase_rule_zh(ctx: Dict[str, Any], phase: str) -> str:
    effective_date = _string_value(ctx.get("effective_daily_bar_date"))
    date_hint = f" ({effective_date})" if effective_date else ""

    if phase == "premarket":
        return (
            f"\u5f53\u524d\u5c1a\u672a\u5f00\u76d8; \u4e0d\u5f97\u63cf\u8ff0“\u4eca\u65e5\u8d70\u52bf\u5df2\u7ecf\u53d1\u751f”；\u53ea\u80fd\u57fa\u4e8e\u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5{date_hint}"
            "\u548c\u76d8\u524dinfo\u751f\u6210\u5f00\u76d8\u8ba1\u5212、\u89c2\u5bdf\u4ef7characters\u4e0e\u98ce\u9669\u9884\u6848."
        )
    if phase in {"intraday", "lunch_break", "closing_auction"}:
        base = "\u5f53\u524d\u4e0d\u662f\u76d8\u540e\u590d\u76d8; \u5e94\u805a\u7126\u5f53\u524d\u76d8Mediumstatus、\u89c2\u5bdf\u6761\u4ef6\u4e0e\u4e0b\u4e00\u6b21\u68c0check\u70b9."
        if ctx.get("is_partial_bar") is True:
            base += " \u4eca\u65e5\u6700\u540e\u4e00\u6839daily data\u53ef\u80fd\u5c1a\u672a\u5b8c\u6210; \u4e0d\u5f97\u5f53\u4f5c\u5b8c\u6574daily data\u590d\u76d8."
        if phase == "lunch_break":
            base += " \u5348\u95f4\u4f11\u5e02\u671f\u95f4\u5e94\u8bf4\u660e\u540e\u7eed\u590d\u76d8\u4ecd\u9700\u4e0b\u5348\u4ea4\u6613\u786e\u8ba4."
        if phase == "closing_auction":
            base += " \u4e34\u8fd1\u6536\u76d8\u65f6\u5e94\u66f4Slightly \u5411\u6536\u76d8\u524d\u98ce\u9669\u63a7\u5236\u548c\u662f\u5426\u9694\u591c\u6301\u4ed3."
        return base
    if phase == "postmarket":
        return "\u5e38\u89c4\u4ea4\u6613\u65f6\u6bb5\u5df2\u7ed3\u675f; \u53ef\u4ee5\u4fdd\u7559\u5b8c\u6574\u4ea4\u6613\u65e5\u590d\u76d8\u8bed\u4e49."
    if phase == "non_trading":
        return f"\u5f53\u524d\u4e0d\u662f\u4ea4\u6613\u65e5or\u5c5e\u4e8e\u5f3a\u5236\u8fd0\u884c; \u53ea\u80fd\u57fa\u4e8e\u4e0a\u4e00\u5b8c\u6574\u4ea4\u6613\u65e5{date_hint}\u548c\u5df2\u77e5\u4e8b\u4ef6analyze; \u4e0d\u5f97\u4f2a\u9020\u4eca\u65e5\u76d8Medium\u8d70\u52bf."
    return "\u5f53\u524dmarket\u9636\u6bb5\u4e0d\u53ef\u53ef\u9760\u63a8\u65ad; \u4e0d\u8981\u8865\u5168does not exist\u7684\u76d8Mediumor\u76d8\u524d\u4e8b\u5b9e; \u7ed3\u8bba\u9700\u4fdd\u6301\u4fdd\u5b88."


def _phase_rule_en(ctx: Dict[str, Any], phase: str) -> str:
    effective_date = _string_value(ctx.get("effective_daily_bar_date"))
    date_hint = f" ({effective_date})" if effective_date else ""

    if phase == "premarket":
        return (
            f"The regular session has not opened. Do not describe today's price action as already happened; "
            f"use only the latest complete daily bar{date_hint} and pre-market information for the opening plan."
        )
    if phase in {"intraday", "lunch_break", "closing_auction"}:
        base = "This is not a post-market recap. Focus on the current intraday state, watch conditions, and next check point."
        if ctx.get("is_partial_bar") is True:
            base += " The latest daily bar may be unfinished; do not treat it as a complete daily candle."
        if phase == "lunch_break":
            base += " During the lunch break, later confirmation depends on the afternoon session."
        if phase == "closing_auction":
            base += " Near the close, emphasize end-of-day risk control and overnight-position decisions."
        return base
    if phase == "postmarket":
        return "The regular session has ended, so a complete-session recap style is acceptable."
    if phase == "non_trading":
        return (
            f"This is a non-trading day or forced run. Use the latest complete daily bar{date_hint} and known events; "
            "do not invent today's intraday movement."
        )
    return "The market phase cannot be inferred reliably. Do not invent pre-market or intraday facts, and keep conclusions conservative."


def _warning_text(value: Any, *, lang: str) -> str:
    if not isinstance(value, list):
        return ""
    labels = _WARNING_LABELS_EN if lang == "en" else _WARNING_LABELS_ZH
    rendered = [labels[item] for item in value if isinstance(item, str) and item in labels]
    if not rendered:
        return ""
    if lang == "en":
        return ", ".join(rendered)
    return "、".join(rendered)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _int_like(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
