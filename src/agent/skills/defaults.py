# -*- coding: utf-8 -*-
"""
Shared defaults for trading skills.

This module centralises:
1. The default active skill set used by agent entrypoints
2. The fallback skill subset used by the multi-agent router
3. Common prompt fragments that previously drifted across multiple files
4. Helper utilities for skill-specific agent naming
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional


_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "strategies"

SKILL_AGENT_PREFIX = "skill_"
LEGACY_STRATEGY_AGENT_PREFIX = "strategy_"
SKILL_CONSENSUS_AGENT_NAME = "skill_consensus"
LEGACY_STRATEGY_CONSENSUS_AGENT_NAME = "strategy_consensus"

CORE_TRADING_SKILL_POLICY_ZH = """## default\u6280\u80fd\u57fa\u7ebf (\u5fc5\u987b\u4e25\u683c\u9075\u5b88)

\u5f53\u524d\u6fc0\u6d3b\u7684 skills \u53ef\u4ee5\u8865\u5145\u7ec6\u5316analyze\u89c6\u89d2; \u4f46default\u98ce\u9669\u63a7\u5236\u548c\u4ea4\u6613\u8282\u594f\u5fc5\u987b\u9075\u5b88\u4ee5\u4e0b\u57fa\u7ebf.

### 1. \u4e25\u8fdbstrategy (\u4e0d\u8ffdHigh)
- **\u7edd\u5bf9\u4e0d\u8ffdHigh**: \u5f53\u80a1\u4ef7Slightly \u79bb MA5 \u8d85\u8fc7 5% \u65f6; \u575a\u51b3\u4e0d\u4e70\u5165
- \u4e56\u79bb\u7387 < 2%: \u6700\u4f73\u4e70\u70b9\u533a\u95f4
- \u4e56\u79bb\u7387 2-5%: \u53ef\u5c0f\u4ed3\u4ecb\u5165
- \u4e56\u79bb\u7387 > 5%: \u4e25\u7981\u8ffdHigh！\u76f4\u63a5\u5224\u5b9a\u4e3a"Watch"

### 2. \u8d8b\u52bf\u4ea4\u6613 (\u987a\u52bf\u800c\u4e3a)
- **\u591a\u5934\u6392\u5217\u5fc5\u987b\u6761\u4ef6**: MA5 > MA10 > MA20
- \u53ea\u505a\u591a\u5934\u6392\u5217\u7684\u80a1\u7968; \u7a7a\u5934\u6392\u5217\u575a\u51b3\u4e0d\u78b0
- \u5747\u7ebf\u53d1\u6563\u4e0a\u884c\u4f18\u4e8e\u5747\u7ebf\u7c98\u5408

### 3. \u6548\u7387\u4f18\u5148 (\u7b79\u7801\u7ed3\u6784)
- \u5173\u6ce8\u7b79\u7801\u96c6Medium\u5ea6: 90%\u96c6Medium\u5ea6 < 15% \u8868\u793a\u7b79\u7801\u96c6Medium
- \u83b7\u5229\u6bd4\u4f8banalyze: 70-90% \u83b7\u5229\u76d8\u65f6\u9700\u8b66\u60d5\u83b7\u5229\u56de\u5410
- \u5e73\u5747\u6210\u672c\u4e0e\u73b0\u4ef7\u5173\u7cfb: \u73b0\u4ef7High\u4e8e\u5e73\u5747\u6210\u672c 5-15% \u4e3a\u5065\u5eb7

### 4. \u4e70\u70b9Slightly \u597d (\u56de\u8e29\u652f\u6491)
- **\u6700\u4f73\u4e70\u70b9**: \u7f29\u91cf\u56de\u8e29 MA5 \u83b7\u5f97\u652f\u6491
- **\u6b21\u4f18\u4e70\u70b9**: \u56de\u8e29 MA10 \u83b7\u5f97\u652f\u6491
- **Watch\u60c5\u51b5**: \u8dcc\u7834 MA20 \u65f6Watch

### 5. \u98ce\u9669\u6392check\u91cd\u70b9
- \u51cf\u6301\u516c\u544a、\u4e1a\u7ee9\u9884\u4e8f、\u76d1\u7ba1\u5904\u7f5a、industry\u653f\u7b56\u5229\u7a7a、\u5927\u989d\u89e3\u7981

### 6. \u4f30\u503c\u5173\u6ce8 (PE/PB)
- PE \u660e\u663eSlightly High\u65f6\u9700\u5728\u98ce\u9669\u70b9Medium\u8bf4\u660e

### 7. \u5f3a\u52bf\u8d8b\u52bf\u80a1\u653e\u5bbd
- \u5f3a\u52bf\u8d8b\u52bf\u80a1\u53ef\u9002\u5f53\u653e\u5bbd\u4e56\u79bb\u7387\u8981\u6c42; \u8f7b\u4ed3\u8ffd\u8e2a\u4f46\u9700\u8bbe\u6b62\u635f
"""

TECHNICAL_SKILL_RULES_EN = """## Default Skill Baseline

Treat the currently activated skills as the primary analysis lens, but keep the
following default risk controls as the shared baseline:

- Bullish alignment: MA5 > MA10 > MA20
- Bias from MA5 < 2% -> ideal buy zone; 2-5% -> small position; > 5% -> no chase
- Shrink-pullback to MA5 is the preferred entry rhythm
- Below MA20 -> hold off unless the active skill explicitly proves a better setup
"""


def get_default_trading_skill_policy(*, explicit_skill_selection: bool) -> str:
    """Return the legacy default trading baseline only for implicit/default runs.

    When a caller explicitly chooses a skill (via request payload or config),
    analysis should follow that selected skill alone instead of silently
    layering the old bull-trend baseline on top.
    """
    if explicit_skill_selection:
        return ""
    return CORE_TRADING_SKILL_POLICY_ZH


def get_default_technical_skill_policy(*, explicit_skill_selection: bool) -> str:
    """Return the technical-agent baseline only for implicit/default runs."""
    if explicit_skill_selection:
        return ""
    return TECHNICAL_SKILL_RULES_EN


@lru_cache(maxsize=1)
def _load_builtin_skill_catalog() -> tuple[object, ...]:
    try:
        from src.agent.skills.base import load_skills_from_directory

        return tuple(load_skills_from_directory(_BUILTIN_SKILLS_DIR))
    except Exception:
        return ()


def _coerce_priority(value: object, default: int = 100) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_available_ids(available_skill_ids: Optional[Iterable[str]]) -> List[str]:
    normalized: List[str] = []
    if available_skill_ids is None:
        return normalized
    for skill_id in available_skill_ids:
        if isinstance(skill_id, str):
            cleaned = skill_id.strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
    return normalized


def _normalize_skill_inputs(
    skills: Optional[Iterable[object]],
    available_skill_ids: Optional[Iterable[str]] = None,
) -> tuple[List[object], List[str]]:
    normalized_available = _normalize_available_ids(available_skill_ids)

    if skills is None:
        return list(_load_builtin_skill_catalog()), normalized_available

    skill_pool: List[object] = []
    for item in skills:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned and cleaned not in normalized_available:
                normalized_available.append(cleaned)
            continue
        if item is not None:
            skill_pool.append(item)
    return skill_pool, normalized_available


def _sort_skill_pool(skills: Iterable[object]) -> List[object]:
    return sorted(
        skills,
        key=lambda skill: (
            _coerce_priority(getattr(skill, "default_priority", 100)),
            str(getattr(skill, "display_name", "") or getattr(skill, "name", "")),
            str(getattr(skill, "name", "")),
        ),
    )


def _iter_candidate_skills(
    skills: Optional[Iterable[object]],
    *,
    available_skill_ids: Optional[Iterable[str]] = None,
    user_invocable_only: bool = True,
) -> tuple[List[object], List[str]]:
    skill_pool, normalized_available = _normalize_skill_inputs(skills, available_skill_ids)
    available_lookup = set(normalized_available)

    candidates: List[object] = []
    for skill in _sort_skill_pool(skill_pool):
        skill_id = str(getattr(skill, "name", "")).strip()
        if not skill_id:
            continue
        if user_invocable_only and not bool(getattr(skill, "user_invocable", True)):
            continue
        if available_lookup and skill_id not in available_lookup:
            continue
        candidates.append(skill)

    return candidates, normalized_available


def _slice_skill_ids(skill_ids: List[str], max_count: Optional[int]) -> List[str]:
    if max_count is None:
        return skill_ids
    return skill_ids[:max_count]


def _pick_primary_default_skill_id(candidates: List[object]) -> str:
    preferred = [
        str(getattr(skill, "name", "")).strip()
        for skill in candidates
        if bool(getattr(skill, "default_active", False))
    ]
    if preferred:
        return preferred[0]

    fallback = [str(getattr(skill, "name", "")).strip() for skill in candidates]
    if fallback:
        return fallback[0]

    return ""


def get_default_active_skill_ids(
    skills: Optional[Iterable[object]] = None,
    max_count: Optional[int] = None,
    available_skill_ids: Optional[Iterable[str]] = None,
) -> List[str]:
    candidates, normalized_available = _iter_candidate_skills(
        skills,
        available_skill_ids=available_skill_ids,
    )
    default_skill_id = _pick_primary_default_skill_id(candidates)
    if default_skill_id:
        return _slice_skill_ids([default_skill_id], max_count)

    return _slice_skill_ids(normalized_available[:1], max_count)


def get_default_router_skill_ids(
    skills: Optional[Iterable[object]] = None,
    max_count: Optional[int] = None,
    available_skill_ids: Optional[Iterable[str]] = None,
) -> List[str]:
    candidates, normalized_available = _iter_candidate_skills(
        skills,
        available_skill_ids=available_skill_ids,
    )
    preferred = [
        str(getattr(skill, "name", "")).strip()
        for skill in candidates
        if bool(getattr(skill, "default_router", False))
    ]
    if preferred:
        return _slice_skill_ids(preferred, max_count)

    return get_default_active_skill_ids(
        candidates,
        max_count=max_count,
        available_skill_ids=normalized_available,
    )


def get_regime_skill_ids(
    regime: str,
    skills: Optional[Iterable[object]] = None,
    max_count: Optional[int] = None,
    available_skill_ids: Optional[Iterable[str]] = None,
) -> List[str]:
    candidates, normalized_available = _iter_candidate_skills(
        skills,
        available_skill_ids=available_skill_ids,
    )
    regime_name = (regime or "").strip().lower()
    if regime_name:
        matched = []
        for skill in candidates:
            market_regimes = getattr(skill, "market_regimes", None) or []
            normalized_regimes = {
                str(item).strip().lower()
                for item in market_regimes
                if str(item).strip()
            }
            if regime_name in normalized_regimes:
                matched.append(str(getattr(skill, "name", "")).strip())
        if matched:
            return _slice_skill_ids(matched, max_count)

    return get_default_router_skill_ids(
        candidates,
        max_count=max_count,
        available_skill_ids=normalized_available,
    )


def get_primary_default_skill_id(
    skills: Optional[Iterable[object]] = None,
    available_skill_ids: Optional[Iterable[str]] = None,
) -> str:
    defaults = get_default_active_skill_ids(skills, max_count=1, available_skill_ids=available_skill_ids)
    return defaults[0] if defaults else ""


def _build_regime_skill_ids(skills: Iterable[object]) -> Dict[str, List[str]]:
    regime_map: Dict[str, List[str]] = {}
    for skill in _sort_skill_pool(skills):
        skill_id = str(getattr(skill, "name", "")).strip()
        if not skill_id:
            continue
        for regime in getattr(skill, "market_regimes", None) or []:
            regime_name = str(regime).strip().lower()
            if not regime_name:
                continue
            regime_map.setdefault(regime_name, []).append(skill_id)
    return regime_map


DEFAULT_ACTIVE_SKILL_IDS: tuple[str, ...] = tuple(get_default_active_skill_ids())
DEFAULT_ROUTER_SKILL_IDS: tuple[str, ...] = tuple(get_default_router_skill_ids())
PRIMARY_DEFAULT_SKILL_ID = get_primary_default_skill_id()
REGIME_SKILL_IDS: Dict[str, List[str]] = _build_regime_skill_ids(_load_builtin_skill_catalog())


def build_skill_agent_name(skill_id: str) -> str:
    return f"{SKILL_AGENT_PREFIX}{skill_id}"


def extract_skill_id(agent_name: Optional[str]) -> Optional[str]:
    if not agent_name or not isinstance(agent_name, str):
        return None
    for prefix in (SKILL_AGENT_PREFIX, LEGACY_STRATEGY_AGENT_PREFIX):
        if agent_name.startswith(prefix):
            return agent_name[len(prefix):]
    return None


def is_skill_agent_name(agent_name: Optional[str]) -> bool:
    return extract_skill_id(agent_name) is not None


def is_skill_consensus_name(agent_name: Optional[str]) -> bool:
    return agent_name in {SKILL_CONSENSUS_AGENT_NAME, LEGACY_STRATEGY_CONSENSUS_AGENT_NAME}
