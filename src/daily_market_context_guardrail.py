# -*- coding: utf-8 -*-
"""Decision guardrail using daily market context for Issue #1381."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, List

from src.report_language import (
    localize_confidence_level,
    localize_operation_advice,
    normalize_report_language,
)


_CONSERVATIVE_TAGS = {"high_risk", "market_cooling", "conservative", "low_position_cap"}
_CONSERVATIVE_TEXT_MARKERS_ZH = ("\u9000\u6f6e", "Watch", "High\u98ce\u9669", "\u8c28\u614e", "\u4fdd\u5b88", "\u4ed3characters\u4e0a\u9650", "\u4ed3characters\u4e0d\u8d85\u8fc7", "\u8f7b\u4ed3")
_CONSERVATIVE_TEXT_MARKERS_EN = ("high risk", "risk-off", "risk off", "watch", "cautious", "conservative", "position cap", "position limit")
_CONSERVATIVE_TEXT_MARKERS_KO = ("고위험", "관망", "위험", "신중", "보수", "비중 상한", "비중 축소", "경량")
_AGGRESSIVE_BUY_MARKERS_ZH = (
    "\u7acb\u5373\u4e70\u5165",
    "\u9a6c\u4e0a\u4e70\u5165",
    "\u5efa\u8bae\u4e70\u5165",
    "\u5206\u6279\u4e70\u5165",
    "\u5206\u6279Low\u5438",
    "\u56de\u8e29\u4e70\u5165",
    "\u79ef\u6781\u4e70\u5165",
    "\u6fc0\u8fdb\u4e70\u5165",
    "\u8ffdHigh",
    "\u52a0\u4ed3",
)
_AGGRESSIVE_BUY_MARKERS_EN = ("buy now", "strong buy", "aggressive buy", "chase", "add aggressively")
_AGGRESSIVE_BUY_MARKERS_KO = (
    "즉시 매수",
    "지금 매수",
    "매수 추천",
    "분할 매수",
    "적극 매수",
    "공격적 매수",
    "추격 매수",
    "비중 확대",
)
_NEGATION_HINTS_ZH = ("\u6682\u4e0d", "\u4e0d\u5efa\u8bae", "\u4e0d\u5e94", "\u4e0d\u5b9c", "\u4e0d\u80fd", "\u65e0\u6cd5", "\u4e0d\u5141\u8bb8", "\u7981\u6b62", "\u907f\u514d", "\u4e0d\u8981", "\u522b", "\u5148\u4e0d")
_NEGATION_HINTS_EN = (" not ", "do not", "don't", "no ", "never", "avoid")
_NEGATION_HINTS_KO = ("권하지 않", "하지 않", "하지 마", "불가", "금지", "피하", "보류", "않", "말")
_NEGATION_LOOKBACK = 16
_GUARDRAIL_SENTIMENT_SCORE = 52


def _softened_operation_advice(language: str) -> str:
    return localize_operation_advice("Watch", language)


def _negation_hints_for(language: str) -> tuple[str, ...]:
    if language == "en":
        return _NEGATION_HINTS_EN
    if language == "ko":
        return _NEGATION_HINTS_KO
    return _NEGATION_HINTS_ZH


def apply_daily_market_context_guardrail(
    result: Any,
    *,
    daily_market_context: Any,
    report_language: str = "zh",
) -> List[str]:
    """Soften aggressive buy advice when daily market context is conservative."""

    if result is None or not _is_conservative_context(daily_market_context):
        return []

    language = normalize_report_language(report_language or getattr(result, "report_language", "zh"))
    if not _has_aggressive_buy_signal(result, language=language):
        return []

    adjustments: List[str] = []
    if str(getattr(result, "decision_type", "") or "").lower() == "buy":
        result.decision_type = "hold"
        adjustments.append("daily_market_context_buy_softened")
    elif _contains_any(str(getattr(result, "operation_advice", "") or ""), _buy_markers(language)):
        adjustments.append("daily_market_context_buy_softened")

    softened_advice = _softened_operation_advice(language)
    result.operation_advice = softened_advice

    if _is_high_confidence(getattr(result, "confidence_level", "")):
        result.confidence_level = localize_confidence_level("medium", language)
        adjustments.append("confidence_capped_daily_market_context")

    result.sentiment_score = _cap_conservative_sentiment_score(
        getattr(result, "sentiment_score", 0)
    )

    dashboard = getattr(result, "dashboard", None)
    if not isinstance(dashboard, dict):
        dashboard = {}
        result.dashboard = dashboard

    _sync_softened_dashboard_fields(
        dashboard,
        softened_advice=softened_advice,
        language=language,
    )

    phase_decision = dashboard.get("phase_decision")
    if not isinstance(phase_decision, dict):
        phase_decision = {}
        dashboard["phase_decision"] = phase_decision
    _append_softening_limitation(phase_decision, language=language)

    return adjustments


def _sync_softened_dashboard_fields(
    dashboard: dict[str, Any],
    *,
    softened_advice: str,
    language: str,
) -> None:
    dashboard["sentiment_score"] = _cap_conservative_sentiment_score(
        dashboard.get("sentiment_score", _GUARDRAIL_SENTIMENT_SCORE)
    )
    dashboard["operation_advice"] = softened_advice
    dashboard["decision_type"] = "hold"

    core = dashboard.get("core_conclusion")
    if isinstance(core, dict):
        core["one_sentence"] = softened_advice
        core["position_advice"] = _softened_position_advice(language)

    battle_plan = dashboard.get("battle_plan")
    if isinstance(battle_plan, dict):
        battle_plan["position_strategy"] = _softened_position_strategy(language)


def _softened_position_advice(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "no_position": "Do not open a new position until market risk eases or confirmation appears.",
            "has_position": "Hold only a small position; do not increase exposure, and reduce if risk controls break.",
        }
    if language == "ko":
        return {
            "no_position": "시장 위험이 완화되거나 확인 신호가 나오기 전까지 신규 진입하지 마세요.",
            "has_position": "소량만 보유하고 비중을 늘리지 마세요. 리스크 관리선이 무너지면 비중을 줄이세요.",
        }
    return {
        "no_position": "\u5927\u76d8\u73af\u5883Slightly \u8c28\u614e; \u6682\u4e0d\u5f00\u65b0\u4ed3; waiting\u98ce\u9669\u7f13\u89e3or\u786e\u8ba4\u4fe1\u53f7.",
        "has_position": "\u4ec5\u4fdd\u7559\u5c0f\u4ed3\u89c2\u5bdf; \u6682\u4e0d\u6269\u5927\u4ed3characters；\u82e5\u8dcc\u7834\u98ce\u63a7characters\u4f18\u5148\u964dLow\u4ed3characters.",
    }


def _softened_position_strategy(language: str) -> dict[str, str]:
    position_advice = _softened_position_advice(language)
    if language == "en":
        return {
            "suggested_position": "Small/defensive position",
            "entry_plan": position_advice["no_position"],
            "risk_control": "Do not increase exposure before market risk eases; control drawdown strictly.",
        }
    if language == "ko":
        return {
            "suggested_position": "소량/방어적 비중",
            "entry_plan": position_advice["no_position"],
            "risk_control": "시장 위험이 완화되기 전까지 비중을 늘리지 말고 낙폭을 엄격히 관리하세요.",
        }
    return {
        "suggested_position": "\u5c0f\u4ed3/Low\u4ed3characters",
        "entry_plan": position_advice["no_position"],
        "risk_control": "\u5927\u76d8\u98ce\u9669\u672a\u7f13\u89e3\u524d\u4e0d\u6269\u5927\u4ed3characters; \u4e25\u683c\u63a7\u5236\u56de\u64a4.",
    }


def _append_softening_limitation(phase_decision: dict[str, Any], *, language: str) -> None:
    limitations = phase_decision.get("data_limitations")
    if not isinstance(limitations, list):
        limitations = []
    if language == "en":
        limitation = "Daily market context is conservative/high risk; aggressive buy advice was softened."
    elif language == "ko":
        limitation = "대시장 환경이 보수적/고위험이라 공격적 매수 권고를 완화했습니다."
    else:
        limitation = "\u5927\u76d8\u73af\u5883Slightly \u8c28\u614e/High\u98ce\u9669; \u5df2\u8f6f\u5316\u6fc0\u8fdb\u4e70\u5165\u5efa\u8bae."
    if limitation not in limitations:
        limitations.append(limitation)
    phase_decision["data_limitations"] = limitations
    reason = str(phase_decision.get("confidence_reason") or "").strip()
    if language == "en":
        reason_note = "Market context requires conservative sizing."
    elif language == "ko":
        reason_note = "시장 환경상 보수적인 비중 관리가 필요합니다."
    else:
        reason_note = "\u5927\u76d8\u73af\u5883\u8981\u6c42\u964dLow\u8fdb\u653b\u5e76Control position size."
    separator = "; " if language == "en" else "；"
    phase_decision["confidence_reason"] = (
        f"{reason}{separator}{reason_note}" if reason else reason_note
    )


def _is_conservative_context(context: Any) -> bool:
    if not isinstance(context, Mapping):
        return False
    tags = context.get("risk_tags")
    if isinstance(tags, list) and any(str(tag) in _CONSERVATIVE_TAGS for tag in tags):
        return True
    if str(context.get("position_cap") or "").strip():
        return True
    summary = str(context.get("summary") or "")
    lowered = summary.lower()
    return (
        any(marker in summary for marker in _CONSERVATIVE_TEXT_MARKERS_ZH)
        or any(marker in summary for marker in _CONSERVATIVE_TEXT_MARKERS_KO)
        or any(marker in lowered for marker in _CONSERVATIVE_TEXT_MARKERS_EN)
    )


def _has_aggressive_buy_signal(result: Any, *, language: str) -> bool:
    decision_type = str(getattr(result, "decision_type", "") or "").lower()
    if decision_type == "buy":
        advice = str(getattr(result, "operation_advice", "") or "")
        markers = _buy_markers(language)
        if _contains_any(advice, markers, language=language):
            return True
        if _contains_any(advice, markers, language=language, require_negation=True):
            return False
        return True
    advice = str(getattr(result, "operation_advice", "") or "")
    return _contains_any(advice, _buy_markers(language), language=language)


def _buy_markers(language: str) -> tuple[str, ...]:
    if language == "en":
        return _AGGRESSIVE_BUY_MARKERS_EN
    if language == "ko":
        return _AGGRESSIVE_BUY_MARKERS_KO
    return _AGGRESSIVE_BUY_MARKERS_ZH


def _contains_any(
    text: str,
    markers: tuple[str, ...],
    *,
    language: str = "zh",
    require_negation: bool = False,
) -> bool:
    lowered = text.lower()
    negation_hints = _negation_hints_for(language)
    for marker in markers:
        marker_lower = marker.lower()
        marker_pos = 0
        while True:
            marker_pos = lowered.find(marker_lower, marker_pos)
            if marker_pos == -1:
                break
            context = lowered[max(0, marker_pos - _NEGATION_LOOKBACK):marker_pos]
            has_negation = _contains_negation_near_marker(context, negation_hints)
            if require_negation:
                if has_negation:
                    return True
            elif not has_negation:
                return True
            marker_pos += len(marker_lower)
    return False


def _contains_negation_near_marker(context: str, negation_hints: tuple[str, ...]) -> bool:
    separators = ("; ", ",", ".", "；", ";", ": ", ":", "？", "!", "！", ")", ")", " (", "(")
    tail = context
    sep_pos = -1
    for separator in separators:
        candidate = context.rfind(separator)
        if candidate > sep_pos:
            sep_pos = candidate
    if sep_pos >= 0:
        tail = context[sep_pos + 1 :]
    return any(hint in tail for hint in negation_hints)


def _cap_conservative_sentiment_score(value: Any) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return _GUARDRAIL_SENTIMENT_SCORE
    return min(_GUARDRAIL_SENTIMENT_SCORE, max(0, score))

def _is_high_confidence(value: Any) -> bool:
    return str(value or "").strip().lower() in {"High", "high", "높음"}
