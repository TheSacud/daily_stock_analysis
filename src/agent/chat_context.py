# -*- coding: utf-8 -*-
"""Visible conversation history builder for Agent chat requests."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.config import (
    get_agent_context_compression_preset,
    get_effective_agent_primary_model,
    get_effective_agent_models_to_try,
)
from src.agent.litellm_route_resolution import resolve_agent_litellm_route
from src.agent.provider_trace import (
    TRACE_MODEL_KEY,
    TRACE_PROVIDER_KEY,
    TraceDiagnostics,
    resolved_provider_namespace,
    strip_trace_metadata,
    trace_model_matches,
)
from src.llm.usage import should_persist_usage_telemetry
from src.storage import get_db, persist_llm_usage

logger = logging.getLogger(__name__)

VISIBLE_ROLES = {"user", "assistant"}
SUMMARY_USER_PREFIX = "[\u7cfb\u7edf\u751f\u6210\u7684history\u5bf9\u8bddsummary; \u4ec5\u4f9b\u5ef6\u7eed\u672cconversation]"
SUMMARY_LLM_TIMEOUT_SECONDS = 20

SUMMARY_SYSTEM_PROMPT = """\u4f60\u662f\u80a1\u7968ask\u7b54\u7cfb\u7edf\u7684conversation\u538b\u7f29\u5668; \u53ea\u80fd\u603b\u7ed3\u5df2\u7ecf\u51fa\u73b0\u8fc7\u7684user\u53ef\u89c1\u5bf9\u8bdd\u5185\u5bb9.

\u786c\u89c4\u5219:
- \u53ea\u603b\u7ed3\u5df2\u6709\u5bf9\u8bdd; \u4e0d\u65b0\u589e\u884c\u60c5、news、\u8d22\u52a1\u6570\u636eor\u6295\u8d44\u5efa\u8bae.
- \u4e0d\u63a8\u65ad\u672a\u51fa\u73b0\u7684\u4e8b\u5b9e; \u4e0d\u8865\u5145\u65b0\u7684\u4e70\u5356\u5efa\u8bae.
- \u5fc5\u987b\u4fdd\u7559\u6807\u7684、\u6301\u4ed3\u6210\u672c、\u5468\u671f、\u98ce\u9669Slightly \u597d、strategy\u89c6\u89d2、\u5173\u952e\u5224\u65ad、\u64cd\u4f5c\u6761\u4ef6、\u6b62\u635f\u6b62\u76c8、\u6570\u636e\u65f6\u6548、\u5de5\u5177failed\u548c\u672a\u51b3question.
- \u8f93\u51fa\u5fc5\u987b\u4f7f\u7528 Markdown; \u5e76\u4e25\u683c\u5305\u542b\u4ee5\u4e0b 5 \u4e2a\u4e8c\u7ea7\u6807\u9898:
  ## conversationsummary
  ## \u5f53\u524d\u5173\u6ce8\u6807\u7684
  ## userSlightly \u597d\u4e0e\u7ea6\u675f
  ## \u5df2\u6709\u5224\u65ad\u4e0e\u64cd\u4f5c\u6761\u4ef6
  ## \u98ce\u9669、\u6570\u636e\u65f6\u6548\u4e0e\u672a\u51b3question
"""


@dataclass(frozen=True)
class VisibleMessage:
    """A persisted user-visible chat message."""

    id: int
    role: str
    content: str
    created_at: Any = None


@dataclass(frozen=True)
class VisibleHistoryState:
    """Id-aware visible history state used for summary and trace splicing."""

    messages: List[Dict[str, Any]]
    visible_ids: set[int]
    visible_tokens: int


@dataclass(frozen=True)
class AgentChatContextBundle:
    """Prepared context messages for a single-agent chat request."""

    context_messages: List[Dict[str, Any]]
    diagnostics: Dict[str, Any]


def build_summary_message(summary_text: str) -> Dict[str, str]:
    """Build the synthetic summary message injected into chat history."""
    return {
        "role": "user",
        "content": f"{SUMMARY_USER_PREFIX}\n{summary_text.strip()}",
    }


def estimate_text_tokens(text: str, config: Any) -> int:
    """Estimate tokens deterministically enough for compression decisions."""
    normalized_text = text or ""
    try:
        import litellm  # type: ignore

        model = get_effective_agent_primary_model(config)
        count = litellm.token_counter(model=model, text=normalized_text)
        return max(0, int(count or 0))
    except Exception as exc:
        logger.debug("Token counter failed; using character heuristic: %s", exc)
        return int(math.ceil(len(normalized_text) / 3))


def estimate_messages_tokens(messages: Sequence[Dict[str, Any]], config: Any) -> int:
    """Estimate tokens for a list of role/content messages."""
    return estimate_text_tokens(_render_messages(messages), config)


def build_summary_messages(
    previous_summary: str,
    messages: Sequence[VisibleMessage],
) -> List[Dict[str, str]]:
    """Build the text-only summary request messages."""
    sections: List[str] = []
    if previous_summary.strip():
        sections.append("\u5df2\u6709\u6eda\u52a8summary: \n" + previous_summary.strip())
    sections.append("this run\u9700\u8981\u7eb3\u5165summary\u7684\u65b0\u589e\u5bf9\u8bdd: ")
    sections.append(_render_visible_messages(messages))
    user_payload = "\n\n".join(sections).strip()
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]


def build_visible_chat_history(
    session_id: str,
    llm_adapter: Any,
    config: Any,
) -> List[Dict[str, str]]:
    """Return visible chat history according to the compression state table."""
    state = _build_visible_history_state(session_id, llm_adapter, config)
    return _strip_internal_message_ids(state.messages)


def build_agent_chat_context_bundle(
    session_id: str,
    llm_adapter: Any,
    config: Any,
) -> AgentChatContextBundle:
    """Return id-spliced visible history plus provider trace messages.

    The bundle excludes the current user turn.  ``AgentExecutor.chat`` appends
    factual context and the current user after these messages, preserving the
    existing request assembly order.
    """
    state = _build_visible_history_state(session_id, llm_adapter, config)
    diagnostics = TraceDiagnostics(visible_tokens=state.visible_tokens)
    db = get_db()
    resolution = resolve_agent_litellm_route(config)
    candidate_models = resolution.models_to_try if resolution.available else []
    if not candidate_models and not resolution.reason:
        candidate_models = get_effective_agent_models_to_try(config)
    if not candidate_models and not resolution.reason:
        candidate_models = [get_effective_agent_primary_model(config)]
    candidate_trace_targets = _build_trace_match_targets(candidate_models, config)
    turns = db.get_agent_provider_turns(session_id, must_roundtrip_only=True)
    traces_by_anchor: Dict[int, List[Dict[str, Any]]] = {}
    pending_trace_tokens = 0
    pending_trace_count = 0

    for turn in turns:
        if not any(
            trace_model_matches(
                turn.get("provider"),
                turn.get("model"),
                model,
                current_provider=provider,
            )
            for model, provider in candidate_trace_targets
        ):
            diagnostics.model_mismatch += 1
            diagnostics.dropped_trace_count += 1
            diagnostics.trace_dropped_reason = diagnostics.trace_dropped_reason or "model_mismatch"
            continue
        anchor_id = _coerce_int(turn.get("anchor_assistant_message_id"), default=0)
        if anchor_id <= 0 or anchor_id not in state.visible_ids:
            diagnostics.anchor_summarized += 1
            diagnostics.dropped_trace_count += 1
            diagnostics.trace_dropped_reason = diagnostics.trace_dropped_reason or "anchor_summarized"
            continue
        trace_messages = _restore_trace_metadata(
            turn.get("messages") or [],
            provider=turn.get("provider"),
            model=turn.get("model"),
        )
        if not trace_messages:
            continue
        pending_trace_count += 1
        pending_trace_tokens += _coerce_int(
            turn.get("estimated_tokens"),
            default=estimate_messages_tokens(trace_messages, config),
        )
        traces_by_anchor.setdefault(anchor_id, []).extend(trace_messages)

    if traces_by_anchor:
        preset = get_agent_context_compression_preset(
            getattr(config, "agent_context_compression_profile", None)
        )
        history_budget = _coerce_int(
            getattr(config, "agent_context_history_budget_tokens", preset.history_budget_tokens),
            default=preset.history_budget_tokens,
        )
        remaining_budget = history_budget - state.visible_tokens
        if remaining_budget < pending_trace_tokens:
            diagnostics.budget_exceeded = True
            diagnostics.trace_dropped_reason = "budget_exceeded"
            diagnostics.dropped_trace_count += pending_trace_count
            traces_by_anchor = {}
        else:
            diagnostics.trace_injected = True
            diagnostics.trace_tokens = pending_trace_tokens

    merged: List[Dict[str, Any]] = []
    for msg in state.messages:
        msg_id = _coerce_int(msg.get("_message_id"), default=0)
        if msg_id and msg_id in traces_by_anchor:
            merged.extend(traces_by_anchor[msg_id])
        merged.append(msg)

    return AgentChatContextBundle(
        context_messages=_strip_internal_message_ids(merged),
        diagnostics=diagnostics.to_dict(),
    )


def _build_visible_history_state(
    session_id: str,
    llm_adapter: Any,
    config: Any,
) -> VisibleHistoryState:
    """Return visible history with private ``_message_id`` anchors."""
    db = get_db()
    if not getattr(config, "agent_context_compression_enabled", False):
        selected = _load_visible_messages(session_id, limit=20)
        messages = _to_chat_messages(selected, include_ids=True)
        return VisibleHistoryState(
            messages=messages,
            visible_ids={msg.id for msg in selected},
            visible_tokens=estimate_messages_tokens(_strip_internal_message_ids(messages), config),
        )

    visible_messages = _load_visible_messages(session_id)
    if not visible_messages:
        return VisibleHistoryState(messages=[], visible_ids=set(), visible_tokens=0)

    summary_record = db.get_conversation_summary(session_id)
    previous_summary = (summary_record or {}).get("summary") or ""
    covered_message_id = _coerce_int((summary_record or {}).get("covered_message_id"), default=0)
    preset = get_agent_context_compression_preset(
        getattr(config, "agent_context_compression_profile", None)
    )
    trigger_tokens = _coerce_int(
        getattr(config, "agent_context_compression_trigger_tokens", preset.trigger_tokens),
        default=preset.trigger_tokens,
    )
    protected_turns = _coerce_int(
        getattr(config, "agent_context_protected_turns", preset.protected_turns),
        default=preset.protected_turns,
    )

    protected_tail = _split_protected_tail(visible_messages, protected_turns)
    protected_ids = {msg.id for msg in protected_tail}
    uncovered_messages = [msg for msg in visible_messages if msg.id > covered_message_id]
    candidate = (
        [build_summary_message(previous_summary)] + _to_chat_messages(uncovered_messages, include_ids=True)
        if previous_summary
        else _to_chat_messages(visible_messages, include_ids=True)
    )
    candidate_tokens = estimate_messages_tokens(_strip_internal_message_ids(candidate), config)

    if candidate_tokens <= trigger_tokens:
        return VisibleHistoryState(
            messages=candidate,
            visible_ids={msg.id for msg in visible_messages if msg.id > covered_message_id or not previous_summary},
            visible_tokens=candidate_tokens,
        )

    to_summarize = [
        msg
        for msg in visible_messages
        if msg.id > covered_message_id and msg.id not in protected_ids
    ]
    if not to_summarize:
        if previous_summary:
            logger.warning(
                "Conversation context compression skipped for session %s: protected tail exceeds trigger",
                session_id,
            )
            messages = [build_summary_message(previous_summary)] + _to_chat_messages(protected_tail, include_ids=True)
            return VisibleHistoryState(
                messages=messages,
                visible_ids={msg.id for msg in protected_tail},
                visible_tokens=estimate_messages_tokens(_strip_internal_message_ids(messages), config),
            )
        logger.warning(
            "Conversation context compression skipped for session %s: all visible history is protected",
            session_id,
        )
        messages = _to_chat_messages(visible_messages, include_ids=True)
        return VisibleHistoryState(
            messages=messages,
            visible_ids={msg.id for msg in visible_messages},
            visible_tokens=estimate_messages_tokens(_strip_internal_message_ids(messages), config),
        )

    logger.info(
        "Conversation context compression summarizing session %s: %d messages, candidate_tokens=%d, trigger=%d",
        session_id,
        len(to_summarize),
        candidate_tokens,
        trigger_tokens,
    )
    summary_text, response = _generate_summary(
        llm_adapter=llm_adapter,
        config=config,
        previous_summary=previous_summary,
        to_summarize=to_summarize,
        max_tokens=preset.summary_target_tokens,
    )
    if summary_text:
        new_covered_message_id = max(msg.id for msg in to_summarize)
        estimated_tokens = estimate_text_tokens(summary_text, config)
        db.upsert_conversation_summary(
            session_id=session_id,
            summary=summary_text,
            covered_message_id=new_covered_message_id,
            source_message_count=len(to_summarize),
            estimated_tokens=estimated_tokens,
        )
        usage = getattr(response, "usage", {}) or {}
        if should_persist_usage_telemetry(usage):
            persist_llm_usage(
                usage,
                getattr(response, "model", "") or get_effective_agent_primary_model(config) or "unknown",
                call_type="agent",
            )
        messages = [build_summary_message(summary_text)] + _to_chat_messages(protected_tail, include_ids=True)
        return VisibleHistoryState(
            messages=messages,
            visible_ids={msg.id for msg in protected_tail},
            visible_tokens=estimate_messages_tokens(_strip_internal_message_ids(messages), config),
        )

    logger.warning(
        "Conversation context compression failed for session %s; using state-table fallback",
        session_id,
    )
    if previous_summary:
        return VisibleHistoryState(
            messages=candidate,
            visible_ids={msg.id for msg in visible_messages if msg.id > covered_message_id},
            visible_tokens=candidate_tokens,
        )
    selected = visible_messages[-20:]
    messages = _to_chat_messages(selected, include_ids=True)
    return VisibleHistoryState(
        messages=messages,
        visible_ids={msg.id for msg in selected},
        visible_tokens=estimate_messages_tokens(_strip_internal_message_ids(messages), config),
    )


def _load_visible_messages(session_id: str, *, limit: Optional[int] = None) -> List[VisibleMessage]:
    rows = get_db().get_visible_conversation_messages(session_id, limit=limit)
    messages = []
    for row in rows:
        role = str(row.get("role") or "")
        content = str(row.get("content") or "")
        if role not in VISIBLE_ROLES or not content:
            continue
        messages.append(
            VisibleMessage(
                id=_coerce_int(row.get("id"), default=0),
                role=role,
                content=content,
                created_at=row.get("created_at"),
            )
        )
    return [msg for msg in messages if msg.id > 0]


def _split_protected_tail(messages: Sequence[VisibleMessage], protected_turns: int) -> List[VisibleMessage]:
    if not messages:
        return []
    if protected_turns <= 0:
        return []

    user_count = 0
    # If fewer user turns exist than requested, keep start_index=0 and protect
    # the entire visible history. The caller handles over-trigger protected-only
    # sessions without forcing a magic truncate.
    start_index = 0
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            user_count += 1
            if user_count >= protected_turns:
                start_index = index
                break
    return list(messages[start_index:])


def _generate_summary(
    *,
    llm_adapter: Any,
    config: Any,
    previous_summary: str,
    to_summarize: Sequence[VisibleMessage],
    max_tokens: int,
) -> Tuple[Optional[str], Any]:
    try:
        response = llm_adapter.call_text(
            build_summary_messages(previous_summary, to_summarize),
            temperature=0,
            max_tokens=max_tokens,
            timeout=SUMMARY_LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Conversation summary LLM call raised: %s", exc)
        return None, None

    content = (getattr(response, "content", None) or "").strip()
    if getattr(response, "provider", "") == "error" or not content:
        return None, response
    return content, response


def _to_chat_messages(
    messages: Iterable[VisibleMessage],
    *,
    include_ids: bool = False,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for msg in messages:
        row: Dict[str, Any] = {"role": msg.role, "content": msg.content}
        if include_ids:
            row["_message_id"] = msg.id
        result.append(row)
    return result


def _strip_internal_message_ids(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {key: value for key, value in msg.items() if key != "_message_id"}
        for msg in messages
    ]


def _restore_trace_metadata(
    messages: Sequence[Any],
    *,
    provider: Any,
    model: Any,
) -> List[Dict[str, Any]]:
    restored: List[Dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        clean = strip_trace_metadata(msg)
        if clean.get("role") in {"assistant", "tool"}:
            clean[TRACE_PROVIDER_KEY] = provider
            clean[TRACE_MODEL_KEY] = model
        restored.append(clean)
    return restored


def _build_trace_match_targets(
    models: Sequence[str],
    config: Any,
) -> List[Tuple[str, str]]:
    model_list = getattr(config, "llm_model_list", []) or []
    targets: List[Tuple[str, str]] = []
    for model in models:
        normalized = str(model or "").strip()
        if not normalized:
            continue
        targets.append((normalized, resolved_provider_namespace(normalized, model_list)))
    return targets


def _render_messages(messages: Sequence[Dict[str, Any]]) -> str:
    return "\n\n".join(
        f"{msg.get('role', '')}:\n{msg.get('content', '')}"
        for msg in messages
    )


def _render_visible_messages(messages: Sequence[VisibleMessage]) -> str:
    return "\n\n".join(f"{msg.role}:\n{msg.content}" for msg in messages)


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
