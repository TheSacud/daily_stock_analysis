# -*- coding: utf-8 -*-
"""Prompt rendering for Issue #1389 AnalysisContextPack runtime summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Iterable, List, Optional


BLOCK_LABELS_ZH = {
    "quote": "\u884c\u60c5",
    "daily_bars": "daily data",
    "technical": "\u6280\u672f",
    "chip": "\u7b79\u7801",
    "fundamentals": "fundamentals",
    "news": "news",
}

BLOCK_LABELS_EN = {
    "quote": "quote",
    "daily_bars": "daily bars",
    "technical": "technical",
    "chip": "chip",
    "fundamentals": "fundamentals",
    "news": "news",
}

STATUS_LABELS_ZH = {
    "available": "\u53ef\u7528",
    "missing": "\u7f3a\u5931",
    "not_supported": "does not support",
    "fallback": "\u964d\u7ea7",
    "stale": "\u8fc7\u671f",
    "estimated": "\u4f30\u7b97",
    "partial": "\u90e8\u5206\u53ef\u7528",
    "fetch_failed": "\u6293\u53d6failed",
}

STATUS_LABELS_EN = {
    "available": "available",
    "missing": "missing",
    "not_supported": "not supported",
    "fallback": "fallback",
    "stale": "stale",
    "estimated": "estimated",
    "partial": "partial",
    "fetch_failed": "fetch failed",
}

QUALITY_LEVEL_LABELS_ZH = {
    "good": "\u826f\u597d",
    "usable": "\u53ef\u7528",
    "limited": "\u53d7\u9650",
    "poor": "\u8f83\u5dee",
}

QUALITY_LEVEL_LABELS_EN = {
    "good": "good",
    "usable": "usable",
    "limited": "limited",
    "poor": "poor",
}

CORE_DEGRADED_STATUSES = {
    "stale",
    "fallback",
    "missing",
    "fetch_failed",
    "partial",
    "estimated",
}

KNOWN_MARKET_PHASES = frozenset(
    {
        "premarket",
        "intraday",
        "lunch_break",
        "closing_auction",
        "postmarket",
        "non_trading",
        "unknown",
    }
)

INTRADAY_MARKET_PHASES = frozenset({"intraday", "lunch_break", "closing_auction"})
CONSERVATIVE_MARKET_PHASES = frozenset({"non_trading", "unknown"})

SENSITIVE_MARKERS = (
    "api_key",
    "access_token",
    "refresh_token",
    "authorization",
    "webhook",
    "password",
    "cookie",
    "secret",
    "token",
    "sendkey",
    "license_key",
)


def normalize_analysis_context_pack_language(report_language: str = "en") -> str:
    # Korean reuses the English structural context labels; the model is
    # constrained to Korean output via the analysis output-language directive.
    return "en" if str(report_language or "").lower() in {"en", "ko"} else "zh"


def get_analysis_context_pack_block_labels(report_language: str = "en") -> Dict[str, str]:
    return (
        BLOCK_LABELS_EN
        if normalize_analysis_context_pack_language(report_language) == "en"
        else BLOCK_LABELS_ZH
    )


def iter_analysis_context_pack_block_keys(blocks: Mapping[str, Any]) -> List[str]:
    ordered_keys = [key for key in BLOCK_LABELS_ZH if key in blocks]
    ordered_keys.extend(key for key in blocks if key not in ordered_keys)
    return ordered_keys


def format_analysis_context_pack_prompt_section(
    pack: Any,
    *,
    report_language: str = "en",
) -> str:
    """Return a low-sensitivity prompt summary for an AnalysisContextPack.

    The renderer intentionally ignores item values. P3 consumes the pack as a
    runtime prompt signal only; P4 exposes a separate low-sensitivity overview,
    not this prompt string or the full pack.
    """
    payload = _pack_to_dict(pack)
    if not payload:
        return ""

    subject = payload.get("subject")
    blocks = payload.get("blocks")
    if not isinstance(subject, Mapping) or not isinstance(blocks, Mapping):
        return ""

    lang = normalize_analysis_context_pack_language(report_language)
    return _format_en(payload) if lang == "en" else _format_zh(payload)


def analysis_context_pack_to_dict(pack: Any) -> Dict[str, Any]:
    if pack is None:
        return {}
    if isinstance(pack, Mapping):
        return dict(pack)
    model_dump = getattr(pack, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="json")
        except TypeError:
            dumped = model_dump()
        except Exception:
            return {}
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


_pack_to_dict = analysis_context_pack_to_dict


def _format_zh(payload: Dict[str, Any]) -> str:
    lines = ["", "## analyze\u4e0a\u4e0b\u6587\u5305summary"]
    lines.extend(_subject_lines(payload, lang="zh"))
    block_lines = _block_lines(payload, lang="zh")
    if block_lines:
        lines.append("- \u6570\u636echunksstatus: ")
        lines.extend(f"  - {line}" for line in block_lines)
    metadata_lines = _metadata_lines(payload, lang="zh")
    if metadata_lines:
        lines.extend(metadata_lines)
    warnings = _list_strings(_nested(payload, "data_quality", "warnings"))
    if warnings:
        lines.append(f"- \u6570\u636e\u8d28\u91cf\u63d0\u9192: {_join_text(warnings, lang='zh')}")
    lines.extend(_data_limitation_lines(payload, lang="zh"))
    return "\n".join(lines) + "\n"


def _format_en(payload: Dict[str, Any]) -> str:
    lines = ["", "## Analysis Context Pack Summary"]
    lines.extend(_subject_lines(payload, lang="en"))
    block_lines = _block_lines(payload, lang="en")
    if block_lines:
        lines.append("- Data block status:")
        lines.extend(f"  - {line}" for line in block_lines)
    metadata_lines = _metadata_lines(payload, lang="en")
    if metadata_lines:
        lines.extend(metadata_lines)
    warnings = _list_strings(_nested(payload, "data_quality", "warnings"))
    if warnings:
        lines.append(f"- Data quality notes: {_join_text(warnings, lang='en')}")
    lines.extend(_data_limitation_lines(payload, lang="en"))
    return "\n".join(lines) + "\n"


def _subject_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    subject = payload.get("subject") if isinstance(payload.get("subject"), Mapping) else {}
    code = _safe_text(subject.get("code"))
    name = _safe_text(subject.get("stock_name"))
    market = _safe_text(subject.get("market"))
    version = _safe_text(payload.get("pack_version"))

    if lang == "en":
        label = code or "unknown"
        if name:
            label += f" ({name})"
        line = f"- Subject: {label}"
        details = []
        if market:
            details.append(f"market={market}")
        if version:
            details.append(f"pack_version={version}")
        if details:
            line += f"; {', '.join(details)}"
        return [line]

    label = code or "unknown\u6807\u7684"
    if name:
        label += f" ({name})"
    line = f"- \u6807\u7684: {label}"
    details = []
    if market:
        details.append(f"market={market}")
    if version:
        details.append(f"pack_version={version}")
    if details:
        line += f"；{'; '.join(details)}"
    return [line]


def _block_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    blocks = payload.get("blocks")
    if not isinstance(blocks, Mapping):
        return []

    labels = get_analysis_context_pack_block_labels(lang)
    ordered_keys = iter_analysis_context_pack_block_keys(blocks)

    lines: List[str] = []
    for key in ordered_keys:
        block = blocks.get(key)
        if not isinstance(block, Mapping):
            continue
        status = _safe_text(block.get("status")) or "unknown"
        label = labels.get(key, _safe_text(key))
        parts = [f"{label}: {status}"]

        source = _first_non_empty(
            block.get("source"),
            _first_item_field(block.get("items"), "source"),
        )
        if source:
            parts.append(f"source={source}")

        warnings = _list_strings(block.get("warnings"))
        if warnings:
            warning_label = "warnings" if lang == "en" else "\u544a\u8b66"
            parts.append(f"{warning_label}={_join_text(warnings, lang=lang)}")

        reasons = _item_missing_reasons(block.get("items"))
        if reasons:
            reason_label = "missing_reason" if lang == "en" else "missing_reason"
            parts.append(f"{reason_label}={_join_text(reasons, lang=lang)}")

        lines.append("；".join(parts) if lang == "zh" else "; ".join(parts))
    return lines


def _metadata_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return []
    news_count = metadata.get("news_result_count")
    if news_count is None:
        return []
    return [
        f"- News result count: {news_count}"
        if lang == "en"
        else f"- newsresult\u6570: {news_count}"
    ]


def _data_limitation_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    lines = ["", "## Data Limitations" if lang == "en" else "## \u6570\u636elimit"]
    data_quality = payload.get("data_quality")
    if not isinstance(data_quality, Mapping):
        data_quality = {}

    score = _safe_score(data_quality.get("overall_score"))
    level = _safe_text(data_quality.get("level"))
    if score is not None:
        level_text = _quality_level_label(level, lang=lang)
        if lang == "en":
            line = f"- Data quality score: {score}/100"
            if level_text:
                line += f" ({level_text})"
        else:
            line = f"- \u6570\u636e\u8d28\u91cf\u8bc4\u5206: {score}/100"
            if level_text:
                line += f" ({level_text})"
        lines.append(line)

    limitations = _localized_limitations(
        _list_strings(data_quality.get("limitations")),
        lang=lang,
    )
    if limitations:
        label = "Known limitations" if lang == "en" else "\u5df2\u77e5limit"
        separator = ": " if lang == "en" else ": "
        lines.append(f"- {label}{separator}{_join_text(limitations, lang=lang)}")

    lines.extend(_phase_data_quality_constraint_lines(payload, lang=lang))

    if _has_core_degraded_block(payload):
        if lang == "en":
            lines.append(
                "- Confidence rule: when quote, daily bars, or technical data is "
                "stale, fallback, missing, fetch_failed, partial, or estimated, "
                "the final JSON confidence_level must not be High."
            )
        else:
            lines.append(
                "- \u7f6e\u4fe1\u5ea6\u89c4\u5219: \u5f53 quote、daily_bars or technical \u4e3a stale、fallback、missing、"
                "fetch_failed、partial or estimated \u65f6; \u6700\u7ec8 JSON \u7684 confidence_level \u4e0d\u5f97\u4e3aHigh."
            )

    if lang == "en":
        lines.append(
            "- Analysis rule: missing auxiliary blocks only limit their matching "
            "analysis sections; do not treat missing data itself as bullish or bearish."
        )
        lines.append(
            "- Safety rule: use only status, source, warnings, and missing_reason "
            "from this summary; do not reproduce raw payloads, news body text, "
            "raw trend values, secrets, tokens, or webhooks."
        )
    else:
        lines.append(
            "- analyze\u89c4\u5219: \u8f85\u52a9\u6570\u636echunks\u7f3a\u5931\u53ealimit\u5bf9\u5e94analyze\u6bb5\u843d; \u4e0d\u8981\u628a\u7f3a\u5931\u672c\u8eab\u89e3\u91ca\u4e3a\u5229\u597dor\u5229\u7a7a."
        )
        lines.append(
            "- \u5b89\u5168\u89c4\u5219: \u53ea\u4f7f\u7528\u672csummaryMedium\u7684 status、source、warnings \u548c missing_reason；"
            "\u4e0d\u8981\u590d\u8ff0 raw payload、news\u6b63\u6587、\u8d8b\u52bf\u539f\u59cb\u503c、secret、token or webhook."
        )
    return lines


def _localized_limitations(limitations: List[str], *, lang: str) -> List[str]:
    labels = get_analysis_context_pack_block_labels(lang)
    status_labels = STATUS_LABELS_EN if lang == "en" else STATUS_LABELS_ZH
    result: List[str] = []
    for item in limitations:
        key, separator, status = item.partition(":")
        if not separator:
            result.append(item)
            continue
        normalized_key = key.strip()
        normalized_status = status.strip()
        label = labels.get(normalized_key, _safe_text(normalized_key))
        status_label = status_labels.get(normalized_status, _safe_text(normalized_status))
        if not label or not status_label:
            continue
        result.append(
            f"{label}: {status_label}" if lang == "en" else f"{label}: {status_label}"
        )
    return result[:5]


def _has_core_degraded_block(payload: Dict[str, Any]) -> bool:
    blocks = payload.get("blocks")
    if not isinstance(blocks, Mapping):
        return False
    for key in ("quote", "daily_bars", "technical"):
        block = blocks.get(key)
        if not isinstance(block, Mapping):
            continue
        status = _safe_text(block.get("status"))
        if status in CORE_DEGRADED_STATUSES:
            return True
    return False


def _phase_data_quality_constraint_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    if not _has_core_degraded_block(payload):
        return []

    phase = _phase_value(payload)
    if not phase or phase == "postmarket":
        return []

    if lang == "en":
        if phase in INTRADAY_MARKET_PHASES:
            return [
                "- Phase/data rule: intraday judgment is limited by quote, daily-bar, "
                "or technical data quality; state those limitations before making "
                "near-term trading conclusions."
            ]
        if phase == "premarket":
            return [
                "- Phase/data rule: the opening plan is limited by data freshness "
                "or fallback status; do not describe degraded quote data as "
                "today's completed price action."
            ]
        if phase in CONSERVATIVE_MARKET_PHASES:
            return [
                "- Phase/data rule: use only available data conservatively and do "
                "not fill in nonexistent intraday facts."
            ]
        return []

    if phase in INTRADAY_MARKET_PHASES:
        return [
            "- \u9636\u6bb5\u6570\u636e\u89c4\u5219: \u76d8Medium\u5224\u65ad\u53d7realtime quote、daily dataor\u6280\u672f\u6570\u636e\u8d28\u91cflimit；"
            "\u7ed9\u51fa\u77ed\u7ebf\u7ed3\u8bba\u524d\u5fc5\u987b\u8bf4\u660e\u8fd9\u4e9blimit."
        ]
    if phase == "premarket":
        return [
            "- \u9636\u6bb5\u6570\u636e\u89c4\u5219: \u5f00\u76d8\u8ba1\u5212\u53d7\u6570\u636e\u65b0\u9c9c\u5ea6or\u964d\u7ea7statuslimit；"
            "\u4e0d\u5f97\u628a\u964d\u7ea7\u884c\u60c5\u63cf\u8ff0\u6210\u4eca\u65e5\u8d70\u52bf\u5df2\u7ecf\u53d1\u751f."
        ]
    if phase in CONSERVATIVE_MARKET_PHASES:
        return [
            "- \u9636\u6bb5\u6570\u636e\u89c4\u5219: \u53ea\u80fd\u4fdd\u5b88\u4f7f\u7528\u5f53\u524d\u53ef\u7528\u6570\u636e; \u4e0d\u5f97\u8865\u5168does not exist\u7684\u76d8Medium\u4e8b\u5b9e."
        ]
    return []


def _phase_value(payload: Dict[str, Any]) -> str:
    phase_payload = payload.get("phase")
    if not isinstance(phase_payload, Mapping):
        return ""
    phase = _safe_text(phase_payload.get("phase"))
    return phase if phase in KNOWN_MARKET_PHASES else ""


def _quality_level_label(level: str, *, lang: str) -> str:
    labels = QUALITY_LEVEL_LABELS_EN if lang == "en" else QUALITY_LEVEL_LABELS_ZH
    return labels.get(level, "")


def _safe_score(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if 0 <= value <= 100:
        return value
    return None


def _first_item_field(items: Any, field: str) -> Optional[str]:
    if not isinstance(items, Mapping):
        return None
    for item in items.values():
        if not isinstance(item, Mapping):
            continue
        value = _safe_text(item.get(field))
        if value:
            return value
    return None


def _item_missing_reasons(items: Any) -> List[str]:
    if not isinstance(items, Mapping):
        return []
    reasons: List[str] = []
    for item in items.values():
        if not isinstance(item, Mapping):
            continue
        reason = _safe_text(item.get("missing_reason"))
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons[:3]


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _list_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = _safe_text(item)
        if text and text not in result:
            result.append(text)
    return result[:5]


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(marker in lowered for marker in SENSITIVE_MARKERS):
        return "[REDACTED]"
    return text


def _join_text(values: Iterable[str], *, lang: str) -> str:
    separator = ", " if lang == "en" else "、"
    return separator.join(values)
