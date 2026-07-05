# -*- coding: utf-8 -*-
"""Decision action taxonomy helpers for Issue #1390 P0.

This module is deliberately separate from ``src.agent.protocols``:
``DecisionAction`` is the new eight-state display taxonomy, while
``decision_type`` remains the existing buy/hold/sell statistics contract.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Literal, Optional, TypedDict, get_args

from src.report_language import normalize_report_language
from src.schemas.decision_scale import action_for_score, score_action_conflicts_without_guardrail

DecisionAction = Literal["buy", "add", "hold", "reduce", "sell", "watch", "avoid", "alert"]


class DecisionActionFields(TypedDict):
    action: Optional[DecisionAction]
    action_label: Optional[str]


_ACTION_VALUES = set(get_args(DecisionAction))
_NON_STOCK_REPORT_TYPES = {"market_review"}

_ACTION_LABELS: Dict[str, Dict[str, str]] = {
    "buy": {"zh": "\u4e70\u5165", "en": "Buy"},
    "add": {"zh": "\u52a0\u4ed3", "en": "Add"},
    "hold": {"zh": "\u6301\u6709", "en": "Hold"},
    "reduce": {"zh": "\u51cf\u4ed3", "en": "Reduce"},
    "sell": {"zh": "\u5356\u51fa", "en": "Sell"},
    "watch": {"zh": "Watch", "en": "Watch"},
    "avoid": {"zh": "\u56de\u907f", "en": "Avoid"},
    "alert": {"zh": "\u9884\u8b66", "en": "Alert"},
}

_EXPLICIT_ALIASES: Dict[str, DecisionAction] = {
    "strong buy": "buy",
    "accumulate": "add",
    "trim": "reduce",
    "strong sell": "sell",
    "wait": "watch",
}

_ACTION_PHRASES: Dict[DecisionAction, tuple[str, ...]] = {
    "avoid": (
        "\u4e0d\u5efa\u8bae\u4e70\u5165",
        "\u907f\u514d\u4e70\u5165",
        "do not buy",
        "don't buy",
        "dont buy",
        "\u56de\u907f",
        "\u89c4\u907f",
        "avoid",
    ),
    "alert": (
        "\u98ce\u9669\u9884\u8b66",
        "\u89e6\u53d1\u544a\u8b66",
        "risk alert",
        "\u8b66\u60d5",
        "alert",
    ),
    "buy": (
        "\u5f3a\u70c8\u4e70\u5165",
        "strong_buy",
        "strong buy",
        "\u4e70\u5165",
        "\u5e03\u5c40",
        "\u5efa\u4ed3",
        "buy",
    ),
    "add": (
        "\u52a0\u4ed3",
        "\u589e\u6301",
        "accumulate",
        "add",
    ),
    "hold": (
        "\u6301\u6709\u89c2\u5bdf",
        "\u6d17\u76d8\u89c2\u5bdf",
        "\u6301\u6709",
        "hold",
    ),
    "watch": (
        "Watch",
        "waiting",
        "wait",
        "watch",
    ),
    "reduce": (
        "\u51cf\u4ed3",
        "trim",
        "reduce",
    ),
    "sell": (
        "\u5f3a\u70c8\u5356\u51fa",
        "strong_sell",
        "strong sell",
        "\u5356\u51fa",
        "\u6e05\u4ed3",
        "sell",
    ),
}

_NEGATED_ACTION_PHRASES: Dict[DecisionAction, tuple[str, ...]] = {
    "avoid": (
        "\u6682\u4e0d\u4e70\u5165",
        "\u4e0d\u8981\u4e70\u5165",
        "\u4e0d\u5b9c\u4e70\u5165",
        "\u5148\u4e0d\u4e70\u5165",
        "\u4e0d\u5efa\u8bae\u5efa\u4ed3",
        "\u6682\u4e0d\u5efa\u4ed3",
        "\u4e0d\u8981\u5efa\u4ed3",
        "\u4e0d\u5b9c\u5efa\u4ed3",
        "\u5148\u4e0d\u5efa\u4ed3",
        "\u65e0\u9700\u5efa\u4ed3",
        "\u65e0\u987b\u5efa\u4ed3",
        "\u4e0d\u5efa\u8bae\u5e03\u5c40",
        "\u6682\u4e0d\u5e03\u5c40",
        "\u4e0d\u8981\u5e03\u5c40",
        "\u4e0d\u5b9c\u5e03\u5c40",
        "\u5148\u4e0d\u5e03\u5c40",
        "\u65e0\u9700\u5e03\u5c40",
        "\u65e0\u987b\u5e03\u5c40",
        "\u65e0\u9700\u4e70\u5165",
        "\u65e0\u987b\u4e70\u5165",
        "not buy",
        "do not buy",
        "don't buy",
        "dont buy",
        "no buy",
        "no need to buy",
        "need not buy",
        "cannot buy",
        "can't buy",
        "cant buy",
    ),
    "hold": (
        "\u4e0d\u5efa\u8bae\u52a0\u4ed3",
        "\u65e0\u9700\u52a0\u4ed3",
        "\u4e0d\u8981\u52a0\u4ed3",
        "\u4e0d\u5b9c\u52a0\u4ed3",
        "\u6682\u4e0d\u52a0\u4ed3",
        "\u65e0\u987b\u52a0\u4ed3",
        "\u4e0d\u5efa\u8bae\u589e\u6301",
        "\u65e0\u9700\u589e\u6301",
        "\u4e0d\u8981\u589e\u6301",
        "\u4e0d\u5b9c\u589e\u6301",
        "\u6682\u4e0d\u589e\u6301",
        "\u65e0\u987b\u589e\u6301",
        "\u4e0d\u5efa\u8bae\u5356\u51fa",
        "\u65e0\u9700\u5356\u51fa",
        "\u4e0d\u8981\u5356\u51fa",
        "\u4e0d\u5b9c\u5356\u51fa",
        "\u6682\u4e0d\u5356\u51fa",
        "\u65e0\u987b\u5356\u51fa",
        "\u4e0d\u5efa\u8bae\u51cf\u4ed3",
        "\u65e0\u9700\u51cf\u4ed3",
        "\u4e0d\u8981\u51cf\u4ed3",
        "\u4e0d\u5b9c\u51cf\u4ed3",
        "\u6682\u4e0d\u51cf\u4ed3",
        "\u65e0\u987b\u51cf\u4ed3",
        "\u4e0d\u5efa\u8bae\u6e05\u4ed3",
        "\u65e0\u9700\u6e05\u4ed3",
        "\u4e0d\u8981\u6e05\u4ed3",
        "\u4e0d\u5b9c\u6e05\u4ed3",
        "\u6682\u4e0d\u6e05\u4ed3",
        "\u65e0\u987b\u6e05\u4ed3",
        "not add",
        "do not add",
        "don't add",
        "dont add",
        "no add",
        "no need to add",
        "need not add",
        "cannot add",
        "can't add",
        "cant add",
        "not accumulate",
        "do not accumulate",
        "don't accumulate",
        "dont accumulate",
        "no accumulate",
        "no need to accumulate",
        "need not accumulate",
        "cannot accumulate",
        "can't accumulate",
        "cant accumulate",
        "not sell",
        "do not sell",
        "don't sell",
        "dont sell",
        "no sell",
        "no need to sell",
        "need not sell",
        "cannot sell",
        "can't sell",
        "cant sell",
        "not reduce",
        "do not reduce",
        "don't reduce",
        "dont reduce",
        "no reduce",
        "no need to reduce",
        "need not reduce",
        "cannot reduce",
        "can't reduce",
        "cant reduce",
        "not trim",
        "do not trim",
        "don't trim",
        "dont trim",
        "no trim",
        "no need to trim",
        "need not trim",
        "cannot trim",
        "can't trim",
        "cant trim",
    ),
}

_GUARD_ACTIONS: tuple[DecisionAction, ...] = ("avoid", "alert")
_ENGLISH_NEGATED_ACTION_TERMS: Dict[DecisionAction, tuple[str, ...]] = {
    "avoid": ("buy",),
    "hold": ("add", "accumulate", "sell", "reduce", "trim"),
}
_ENGLISH_AVOIDED_HOLD_ACTION_TERMS = ("adding", "accumulating", "selling", "reducing", "trimming")
_ENGLISH_DEFERRED_ACTION_TERMS = ("buy", "add", "accumulate", "sell", "reduce", "trim")
_FINANCIAL_COMPOUND_SENTINEL = "financialcompound"


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _mask_english_financial_compounds(text: str) -> str:
    text = re.sub(
        r"(?<![a-z0-9_])buy\s*back(?![a-z0-9_])",
        _FINANCIAL_COMPOUND_SENTINEL,
        text,
    )
    return re.sub(
        r"(?<![a-z0-9_])sell\s*off(?![a-z0-9_])",
        _FINANCIAL_COMPOUND_SENTINEL,
        text,
    )


def _word_or_substring_match(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    normalized_phrase = _normalize_key(phrase)
    if re.search(r"[a-z]", normalized_phrase):
        return bool(re.search(rf"(?<![a-z0-9_]){re.escape(normalized_phrase)}(?![a-z0-9_])", text))
    return normalized_phrase in text


def _english_negated_action_matches(text: str) -> set[DecisionAction]:
    matches: set[DecisionAction] = set()
    negation_prefix = (
        r"(?:not\s+(?:a\s+|an\s+|to\s+)?|"
        r"no\s+(?:need\s+to\s+)?|"
        r"need\s+not\s+|"
        r"cannot\s+|can't\s+|cant\s+|"
        r"do\s+not\s+|don't\s+|dont\s+)"
    )
    for action, terms in _ENGLISH_NEGATED_ACTION_TERMS.items():
        for term in terms:
            if re.search(rf"(?<![a-z0-9_]){negation_prefix}{re.escape(term)}(?![a-z0-9_])", text):
                matches.add(action)
    return matches


def _has_english_avoided_hold_action(text: str) -> bool:
    terms = "|".join(re.escape(term) for term in _ENGLISH_AVOIDED_HOLD_ACTION_TERMS)
    return bool(re.search(rf"(?<![a-z0-9_])avoid\s+(?:{terms})(?![a-z0-9_])", text))


def _has_english_deferred_action(text: str) -> bool:
    terms = "|".join(re.escape(term) for term in _ENGLISH_DEFERRED_ACTION_TERMS)
    if re.search(rf"(?<![a-z0-9_])wait(?:ing)?\s+to\s+(?:{terms})(?![a-z0-9_])", text):
        return True
    return bool(
        re.search(
            rf"(?<![a-z0-9_])waiting\s+(?:for|until)\b.*?(?<![a-z0-9_])(?:{terms})(?![a-z0-9_])",
            text,
        )
    )


def _explicit_action(value: Any) -> Optional[DecisionAction]:
    normalized = _normalize_key(value)
    if not normalized:
        return None
    if normalized in _ACTION_VALUES:
        return normalized  # type: ignore[return-value]
    return _EXPLICIT_ALIASES.get(normalized)


def normalize_decision_action(value: Any) -> Optional[DecisionAction]:
    """Return a unique eight-state action for explicit values or clear text.

    Unknown or ambiguous human-readable advice returns ``None`` rather than
    defaulting to a neutral action.
    """

    explicit = _explicit_action(value)
    if explicit:
        return explicit

    text = _mask_english_financial_compounds(_normalize_key(value))
    if not text:
        return None

    if _has_english_deferred_action(text):
        return None

    negated_matches: set[DecisionAction] = set()
    if _has_english_avoided_hold_action(text):
        negated_matches.add("hold")
    negated_matches.update(_english_negated_action_matches(text))
    for action, phrases in _NEGATED_ACTION_PHRASES.items():
        if any(_word_or_substring_match(text, phrase) for phrase in phrases):
            negated_matches.add(action)
    if len(negated_matches) == 1:
        return next(iter(negated_matches))
    if len(negated_matches) > 1:
        return None

    guard_matches: set[DecisionAction] = set()
    for action in _GUARD_ACTIONS:
        if any(_word_or_substring_match(text, phrase) for phrase in _ACTION_PHRASES[action]):
            guard_matches.add(action)
    if len(guard_matches) == 1:
        return next(iter(guard_matches))
    if len(guard_matches) > 1:
        return None

    matches: set[DecisionAction] = set()
    for action, phrases in _ACTION_PHRASES.items():
        if action in _GUARD_ACTIONS:
            continue
        if any(_word_or_substring_match(text, phrase) for phrase in phrases):
            matches.add(action)

    if len(matches) == 1:
        return next(iter(matches))
    if matches and matches <= {"hold", "watch"}:
        return "watch" if "watch" in matches else "hold"
    return None


def localize_action_label(action: Any, language: Optional[str] = "zh") -> Optional[str]:
    """Return a localized display label for a decision action."""

    normalized = _explicit_action(action)
    if not normalized:
        return None
    return _ACTION_LABELS[normalized][normalize_report_language(language)]


def build_action_fields(
    *,
    operation_advice: Any = None,
    explicit_action: Any = None,
    report_type: Any = None,
    report_language: Optional[str] = "en",
    sentiment_score: Any = None,
    guardrail_reason: Any = None,
    align_with_score: bool = False,
) -> DecisionActionFields:
    """Build optional public action fields without mutating legacy contracts."""

    if str(report_type or "").strip().lower() in _NON_STOCK_REPORT_TYPES:
        return {"action": None, "action_label": None}

    action = normalize_decision_action(explicit_action)
    if action is None:
        advice_text = str(operation_advice or "").strip()
        if advice_text:
            action = normalize_decision_action(advice_text)

    if align_with_score and score_action_conflicts_without_guardrail(
        score=sentiment_score,
        action=action,
        guardrail_reason=guardrail_reason,
    ):
        score_action = action_for_score(sentiment_score)
        if score_action in _ACTION_VALUES:
            action = score_action  # type: ignore[assignment]

    return {
        "action": action,
        "action_label": localize_action_label(action, report_language) if action else None,
    }
