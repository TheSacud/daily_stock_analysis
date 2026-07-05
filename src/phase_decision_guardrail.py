# -*- coding: utf-8 -*-
"""Phase-aware decision guardrails for Issue #1386 P5."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.analysis_context_pack_prompt import CORE_DEGRADED_STATUSES
from src.market_phase_summary import render_market_phase_summary
from src.report_language import localize_confidence_level, normalize_report_language

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult


INTRADAY_PHASES = {"intraday", "lunch_break", "closing_auction"}
CONSERVATIVE_ACTION_PHASES = {"premarket", "non_trading", "unknown"}
CORE_DATA_BLOCKS = {"quote", "daily_bars", "technical"}

_PHASE_CONTEXT_KEYS = (
    "phase",
    "market",
    "market_local_time",
    "session_date",
    "effective_daily_bar_date",
    "is_trading_day",
    "is_market_open_now",
    "is_partial_bar",
    "minutes_to_open",
    "minutes_to_close",
    "trigger_source",
    "analysis_intent",
    "warnings",
)

_ZH_POSTMARKET_RECAP_PATTERNS = (
    "\u4eca\u65e5\u6536\u76d8\u540e",
    "\u6536\u76d8\u540e\u590d\u76d8",
    "\u76d8\u540e\u590d\u76d8",
    "\u660e\u65e5\u91cd\u70b9\u5173\u6ce8",
    "\u660e\u5929\u91cd\u70b9\u5173\u6ce8",
    "\u5b8c\u6574\u4ea4\u6613\u65e5\u590d\u76d8",
)

_EN_POSTMARKET_RECAP_PATTERNS = (
    "after today's close",
    "after today’s close",
    "after the close",
    "post-market recap",
    "post market recap",
    "focus tomorrow",
    "tomorrow's focus",
    "tomorrow’s focus",
)

_IMMEDIATE_ACTION_MARKERS_ZH = (
    "\u7acb\u5373\u4e70\u5165",
    "\u9a6c\u4e0a\u4e70\u5165",
    "\u7acb\u5373\u52a0\u4ed3",
    "\u9a6c\u4e0a\u52a0\u4ed3",
    "\u7acb\u5373\u5356\u51fa",
    "\u9a6c\u4e0a\u5356\u51fa",
    "\u7acb\u5373\u51cf\u4ed3",
    "\u9a6c\u4e0a\u51cf\u4ed3",
)
_IMMEDIATE_ACTION_MARKERS_EN = ("buy now", "sell now", "immediate buy", "immediate sell", "add now", "reduce now")
_NEGATION_PREFIXES_ZH = ("\u6682\u4e0d", "\u4e0d\u5efa\u8bae", "\u7981\u6b62", "\u4e0d\u8981", "\u65e0\u9700", "\u907f\u514d", "\u4e0d\u80fd", "\u4e0d\u53ef", "\u4e0d\u5b9c", "\u52ff", "\u4e0d")
_NEGATION_PREFIXES_EN = ("do not", "don't", "dont", "not", "no", "avoid", "hold off", "without")

_KO_POSTMARKET_RECAP_PATTERNS = (
    "오늘 장 마감 후",
    "장 마감 후 리뷰",
    "장 마감 후",
    "마감 후 리뷰",
    "내일 주목",
    "내일 집중",
    "완전한 거래일 리뷰",
)
_IMMEDIATE_ACTION_MARKERS_KO = ("즉시 매수", "지금 매수", "즉시 비중확대", "즉시 매도", "지금 매도", "즉시 비중축소")
_NEGATION_PREFIXES_KO = ("하지", "권하지 않", "금지", "삼가", "불필요", "피하", "불가", "않", "안")


def _recap_patterns_for(language: str) -> tuple[str, ...]:
    if language == "en":
        return _EN_POSTMARKET_RECAP_PATTERNS
    if language == "ko":
        return _KO_POSTMARKET_RECAP_PATTERNS
    return _ZH_POSTMARKET_RECAP_PATTERNS


def _immediate_markers_for(language: str) -> tuple[str, ...]:
    if language == "en":
        return _IMMEDIATE_ACTION_MARKERS_EN
    if language == "ko":
        return _IMMEDIATE_ACTION_MARKERS_KO
    return _IMMEDIATE_ACTION_MARKERS_ZH


def _negations_for(language: str) -> tuple[str, ...]:
    if language == "en":
        return _NEGATION_PREFIXES_EN
    if language == "ko":
        return _NEGATION_PREFIXES_KO
    return _NEGATION_PREFIXES_ZH


def _reason_text(language: str, *, en: str, zh: str, ko: str) -> str:
    if language == "en":
        return en
    if language == "ko":
        return ko
    return zh


def apply_phase_decision_guardrails(
    result: "AnalysisResult",
    *,
    market_phase_summary: Optional[Dict[str, Any]],
    analysis_context_pack_overview: Optional[Dict[str, Any]],
    report_language: str = "en",
) -> List[str]:
    """Apply phase/data-quality guardrails to an AnalysisResult in place."""

    if result is None:
        return []

    language = normalize_report_language(report_language or getattr(result, "report_language", "en"))
    phase_summary = _safe_phase_summary(market_phase_summary)
    overview = analysis_context_pack_overview if isinstance(analysis_context_pack_overview, Mapping) else None
    adjustments: List[str] = []

    dashboard_value = getattr(result, "dashboard", None)
    if not isinstance(dashboard_value, dict):
        dashboard_value = {}
        setattr(result, "dashboard", dashboard_value)
    dashboard = dashboard_value
    phase_decision = dashboard.get("phase_decision")
    if not isinstance(phase_decision, dict):
        phase_decision = {}
    dashboard["phase_decision"] = phase_decision

    _ensure_phase_decision_shape(phase_decision)

    if phase_summary:
        phase_decision["phase_context"] = _phase_context_from_summary(phase_summary)

    merged_limitations = _merge_limitations(
        _list_strings(phase_decision.get("data_limitations")),
        _phase_warning_limitations(phase_summary, language=language),
        _overview_limitations(overview),
    )
    phase_decision["data_limitations"] = merged_limitations

    phase = _safe_text(phase_summary.get("phase")) if phase_summary else ""
    core_degraded = _has_core_degraded_block(overview)
    initially_high_confidence = _is_high_confidence(getattr(result, "confidence_level", ""))

    if core_degraded and initially_high_confidence:
        result.confidence_level = localize_confidence_level("medium", language)
        reason = _reason_text(
            language,
            en="Core quote, daily-bar, or technical data is degraded; high confidence was capped.",
            zh="\u6838\u5fc3\u884c\u60c5、daily dataor\u6280\u672f\u6570\u636e\u53d7\u9650; \u5df2limitHigh\u7f6e\u4fe1\u7ed3\u8bba.",
            ko="핵심 시세·일봉·기술 데이터가 제한되어 높은 신뢰도를 하향 조정했습니다.",
        )
        _append_reason(phase_decision, reason)
        adjustments.append("confidence_capped_core_data_degraded")

    has_non_intraday_action = (
        phase in CONSERVATIVE_ACTION_PHASES
        and _has_immediate_buy_sell_signal(result, phase_decision, language=language)
    )
    if has_non_intraday_action:
        phase_decision["immediate_action"] = _safe_wait_action(language)
        reason = _reason_text(
            language,
            en="Current market phase does not support immediate intraday buy/sell action.",
            zh="\u5f53\u524dmarket\u9636\u6bb5does not support\u5373\u65f6\u76d8Medium\u4e70\u5356\u52a8\u4f5c.",
            ko="현재 시장 단계에서는 즉시 장중 매수/매도 동작을 지원하지 않습니다.",
        )
        _append_reason(phase_decision, reason)
        adjustments.append("non_intraday_action_adjusted")
        if initially_high_confidence:
            result.confidence_level = localize_confidence_level("low", language)
            adjustments.append("confidence_capped_non_intraday_action")

    if phase in INTRADAY_PHASES and _contains_postmarket_recap(result, phase_decision, language=language):
        reason = _reason_text(
            language,
            en="Intraday output contained post-market recap wording; replaced with phase-safe action wording.",
            zh="\u76d8Medium\u8f93\u51fa\u5305\u542b\u76d8\u540e\u590d\u76d8\u53e3\u543b; \u5df2\u66ff\u6362\u4e3a\u9636\u6bb5\u5b89\u5168\u52a8\u4f5c\u8868\u8ff0.",
            ko="장중 출력에 장 마감 후 리뷰 표현이 있어 단계에 맞는 안전한 표현으로 교체했습니다.",
        )
        _replace_postmarket_recap_fields(result, phase_decision, language=language)
        _append_reason(phase_decision, reason)
        adjustments.append("postmarket_recap_wording_adjusted")

    if adjustments:
        phase_decision["data_limitations"] = _merge_limitations(
            phase_decision.get("data_limitations"),
            [_adjustment_limitation_text(item, language=language) for item in adjustments],
        )

    return adjustments


def _ensure_phase_decision_shape(phase_decision: Dict[str, Any]) -> None:
    phase_decision.setdefault("phase_context", None)
    phase_decision.setdefault("action_window", None)
    phase_decision.setdefault("immediate_action", None)
    phase_decision["watch_conditions"] = _list_strings(phase_decision.get("watch_conditions"))
    phase_decision.setdefault("next_check_time", None)
    phase_decision.setdefault("confidence_reason", None)
    phase_decision["data_limitations"] = _list_strings(phase_decision.get("data_limitations"))


def _safe_phase_summary(value: Any) -> Optional[Dict[str, Any]]:
    summary = render_market_phase_summary(value)
    if not summary:
        return None
    return summary


def _phase_context_from_summary(summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: summary.get(key) for key in _PHASE_CONTEXT_KEYS if key in summary}


def _has_core_degraded_block(overview: Optional[Mapping[str, Any]]) -> bool:
    if not isinstance(overview, Mapping):
        return False
    blocks = overview.get("blocks")
    if not isinstance(blocks, list):
        return False
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        key = _safe_text(block.get("key"))
        status = _safe_text(block.get("status"))
        if key in CORE_DATA_BLOCKS and status in CORE_DEGRADED_STATUSES:
            return True
    return False


def _overview_limitations(overview: Optional[Mapping[str, Any]]) -> List[str]:
    if not isinstance(overview, Mapping):
        return []
    data_quality = overview.get("data_quality")
    if not isinstance(data_quality, Mapping):
        return []
    return _list_strings(data_quality.get("limitations"))


def _phase_warning_limitations(summary: Optional[Mapping[str, Any]], *, language: str) -> List[str]:
    if not isinstance(summary, Mapping):
        return []
    warnings = _list_strings(summary.get("warnings"))
    if not warnings:
        return []
    if language == "en":
        return [f"market phase warning: {item}" for item in warnings]
    if language == "ko":
        return [f"시장 단계 경고: {item}" for item in warnings]
    return [f"market\u9636\u6bb5\u63d0\u9192: {item}" for item in warnings]


def _merge_limitations(*groups: Any, limit: int = 5) -> List[str]:
    merged: List[str] = []
    for group in groups:
        for item in _list_strings(group):
            if item not in merged:
                merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def _is_high_confidence(value: Any) -> bool:
    text = _safe_text(value).lower()
    return text in {"High", "high", "높음"}


def _has_immediate_buy_sell_signal(
    result: "AnalysisResult",
    phase_decision: Mapping[str, Any],
    *,
    language: str,
) -> bool:
    haystack = " ".join(
        _safe_text(value)
        for value in (
            getattr(result, "operation_advice", ""),
            phase_decision.get("immediate_action"),
        )
    ).lower()
    immediate_markers = _immediate_markers_for(language)
    if _contains_non_negated_marker(haystack, immediate_markers, language=language):
        return True
    return _safe_text(getattr(result, "decision_type", "")).lower() in {"buy", "sell"}


def _contains_non_negated_marker(text: str, markers: tuple[str, ...], *, language: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    for marker in markers:
        marker_text = marker.lower()
        start = 0
        while True:
            index = lowered.find(marker_text, start)
            if index < 0:
                break
            if not _is_negated_marker(lowered, index, language=language):
                return True
            start = index + len(marker_text)
    return False


def _is_negated_marker(text: str, marker_index: int, *, language: str) -> bool:
    window = 24 if language == "en" else 8
    prefix = text[max(0, marker_index - window):marker_index].rstrip()
    negations = _negations_for(language)
    return any(prefix.endswith(item) for item in negations)


def _contains_postmarket_recap(result: "AnalysisResult", phase_decision: Mapping[str, Any], *, language: str) -> bool:
    dashboard_value = getattr(result, "dashboard", None)
    dashboard = dashboard_value if isinstance(dashboard_value, dict) else {}
    core = dashboard.get("core_conclusion")
    core = core if isinstance(core, Mapping) else {}
    values = (
        core.get("one_sentence"),
        getattr(result, "operation_advice", ""),
        getattr(result, "analysis_summary", ""),
        phase_decision.get("immediate_action"),
    )
    patterns = _recap_patterns_for(language)
    return any(_contains_any(value, patterns) for value in values)


def _replace_postmarket_recap_fields(
    result: "AnalysisResult",
    phase_decision: Dict[str, Any],
    *,
    language: str,
) -> None:
    dashboard_value = getattr(result, "dashboard", None)
    dashboard = dashboard_value if isinstance(dashboard_value, dict) else {}
    core = dashboard.get("core_conclusion")
    if not isinstance(core, dict):
        core = {}
        dashboard["core_conclusion"] = core
    safe_action = _safe_wait_action(language)
    safe_summary = _reason_text(
        language,
        en=(
            "This is an intraday phase; use live state, watch conditions, and the next "
            "check point rather than post-market recap wording."
        ),
        zh="\u5f53\u524d\u5904\u4e8e\u76d8Medium\u9636\u6bb5; \u5e94\u4ee5\u5b9e\u65f6status、\u89c2\u5bdf\u6761\u4ef6\u548c\u4e0b\u4e00\u6b21\u68c0check\u70b9\u4e3a\u51c6; \u907f\u514d\u76d8\u540e\u590d\u76d8\u53e3\u5f84.",
        ko="현재 장중 단계이므로 장 마감 후 리뷰 표현 대신 실시간 상태·관찰 조건·다음 점검 시점을 기준으로 합니다.",
    )
    if _contains_any(core.get("one_sentence"), _patterns(language)):
        core["one_sentence"] = safe_action
    if _contains_any(getattr(result, "operation_advice", ""), _patterns(language)):
        result.operation_advice = safe_action
    if _contains_any(getattr(result, "analysis_summary", ""), _patterns(language)):
        result.analysis_summary = safe_summary
    if _contains_any(phase_decision.get("immediate_action"), _patterns(language)):
        phase_decision["immediate_action"] = safe_action


def _append_reason(phase_decision: Dict[str, Any], reason: str) -> None:
    existing = _safe_text(phase_decision.get("confidence_reason"))
    if not existing:
        phase_decision["confidence_reason"] = reason
        return
    if reason not in existing:
        phase_decision["confidence_reason"] = f"{existing}；{reason}"


def _adjustment_limitation_text(adjustment: str, *, language: str) -> str:
    if adjustment == "postmarket_recap_wording_adjusted":
        return _reason_text(
            language,
            en="post-market recap wording adjusted",
            zh="\u5df2\u4fee\u6b63\u76d8\u540e\u590d\u76d8\u53e3\u543b",
            ko="장 마감 후 리뷰 표현을 수정함",
        )
    if adjustment == "non_intraday_action_adjusted":
        return _reason_text(
            language,
            en="non-intraday immediate action adjusted",
            zh="\u975e\u76d8Medium\u9636\u6bb5\u5df2\u4fee\u6b63\u5373\u65f6\u4e70\u5356\u52a8\u4f5c",
            ko="비장중 단계의 즉시 매매 동작을 수정함",
        )
    if adjustment == "confidence_capped_non_intraday_action":
        return _reason_text(
            language,
            en="confidence capped for non-intraday action",
            zh="\u975e\u76d8Medium\u9636\u6bb5\u5df2limit\u4e70\u5356\u7f6e\u4fe1\u5ea6",
            ko="비장중 단계 매매에 대해 신뢰도를 제한함",
        )
    if adjustment == "confidence_capped_core_data_degraded":
        return _reason_text(
            language,
            en="confidence capped due to degraded core data",
            zh="\u6838\u5fc3\u6570\u636e\u53d7\u9650\u5df2\u964dLow\u7f6e\u4fe1\u5ea6",
            ko="핵심 데이터 제한으로 신뢰도를 낮춤",
        )
    return adjustment


def _safe_wait_action(language: str) -> str:
    return _reason_text(
        language,
        en="Wait for intraday confirmation; do not chase.",
        zh="waiting\u76d8Medium\u786e\u8ba4; \u7981\u6b62\u8ffdHigh.",
        ko="장중 확인을 기다리고 추격 매수하지 마세요.",
    )


def _patterns(language: str) -> tuple[str, ...]:
    return _recap_patterns_for(language)


def _contains_any(value: Any, patterns: tuple[str, ...]) -> bool:
    text = _safe_text(value).lower()
    return bool(text) and any(pattern.lower() in text for pattern in patterns)


def _list_strings(value: Any, *, limit: int = 20) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = _safe_text(item)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (Mapping, list, tuple, set)):
        return ""
    return str(value).strip()
