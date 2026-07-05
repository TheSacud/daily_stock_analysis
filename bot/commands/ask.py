# -*- coding: utf-8 -*-
"""
Ask command - analyze one or more stocks using Agent skills.

Usage:
    /ask 600519                        -> Analyze with default skill
    /ask 600519 \u7528\u7f20\u8bbaanalyze              -> Parse skill from message
    /ask 600519 chan_theory             -> Specify skill id directly
    /ask 600519,000858 \u6ce2\u6d6a\u7406\u8bba         -> Multi-stock comparison with skill overlay
"""

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from data_provider.base import canonical_stock_code
from src.config import get_config
from src.storage import get_db

logger = logging.getLogger(__name__)


class AskCommand(BotCommand):
    """
    Ask command handler - invoke Agent with a specific skill to analyze stocks.
    """

    _MULTI_ANALYZE_TIMEOUT_S = 150.0

    @property
    def name(self) -> str:
        return "ask"

    @property
    def aliases(self) -> List[str]:
        return ["ask-stock"]

    @property
    def description(self) -> str:
        return "analyze stocks with Agent skills"

    @property
    def usage(self) -> str:
        return "/ask <stock code[,code2,...]> [skill name]"

    def _merge_code_args(self, args: List[str]) -> tuple[str, List[str]]:
        """Merge stock code arguments separated by commas or explicit ``vs`` markers."""
        if not args:
            return "", []

        code_like = re.compile(
            r"^,?(\d{6}|hk\d{5}|[A-Za-z]{1,5}(\.[A-Za-z]{1,2})?),?$",
            re.IGNORECASE,
        )
        raw_codes_parts = [args[0]]
        rest_args = list(args[1:])

        while rest_args:
            token = rest_args[0]
            prev = raw_codes_parts[-1].rstrip()

            if token.lower() == "vs" and len(rest_args) > 1 and code_like.match(rest_args[1]):
                raw_codes_parts.append(rest_args[1])
                rest_args = rest_args[2:]
                continue

            has_comma_separator = (
                prev.endswith(",")
                or prev.endswith("; ")
                or token.lstrip().startswith(",")
                or token.lstrip().startswith("; ")
            )
            if code_like.match(token) and has_comma_separator:
                raw_codes_parts.append(token)
                rest_args = rest_args[1:]
                continue

            break

        normalized_parts = [part.strip(",; ") for part in raw_codes_parts]
        raw_code_str = ",".join(normalized_parts)
        return raw_code_str, rest_args

    def _parse_stock_codes(self, raw: str) -> List[str]:
        """Parse one or more stock codes from the first argument."""
        parts = [p.strip().upper() for p in raw.replace("; ", ",").split(",") if p.strip()]
        return [canonical_stock_code(part) for part in parts]

    def _validate_single_code(self, code: str) -> Optional[str]:
        """Validate a single stock code format."""
        normalized = code.upper()
        is_a_stock = re.match(r"^\d{6}$", normalized)
        is_hk_stock = re.match(r"^HK\d{5}$", normalized)
        is_us_stock = re.match(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$", normalized)

        if not (is_a_stock or is_hk_stock or is_us_stock):
            return f"invalid stock code: {normalized} (A-share6 digits / HK stockHK+5 digits / US stock1-5 letters)"
        return None

    def validate_args(self, args: List[str]) -> Optional[str]:
        """Validate arguments."""
        if not args:
            return "enter a stock code.Usage: /ask <stock code[,code2,...]> [skill name]"

        raw_code_str, _ = self._merge_code_args(args)
        codes = self._parse_stock_codes(raw_code_str)
        if not codes:
            return "enter at least one valid stock code"

        for code in codes:
            error = self._validate_single_code(code)
            if error:
                return error

        if len(codes) > 5:
            return "analyze at most 5 stocks at a time"

        return None

    @staticmethod
    def _load_skills() -> List[object]:
        try:
            from src.agent.factory import get_skill_manager

            sm = get_skill_manager()
            return list(sm.list_skills())
        except Exception as e:
            logger.warning("_load_skills failed: Failed to load skills: %s", e, exc_info=True)
            return []

    @classmethod
    def _get_default_skill_id(cls) -> str:
        try:
            from src.agent.skills.defaults import get_primary_default_skill_id

            return get_primary_default_skill_id(cls._load_skills())
        except Exception as e:
            logger.warning("_get_default_skill_id failed: Failed to resolve default skill id: %s", e, exc_info=True)
            return ""

    @classmethod
    def _build_skill_alias_pairs(cls) -> List[tuple[str, str]]:
        alias_pairs: List[tuple[str, str]] = []
        for skill in cls._load_skills():
            skill_id = str(getattr(skill, "name", "")).strip()
            if not skill_id:
                continue
            aliases = [skill_id, getattr(skill, "display_name", "")] + list(getattr(skill, "aliases", []) or [])
            for alias in aliases:
                alias_text = str(alias).strip()
                if alias_text:
                    alias_pairs.append((alias_text, skill_id))

        alias_pairs.sort(key=lambda item: (len(item[0]), item[0]), reverse=True)
        return alias_pairs

    def _parse_skill(self, args: List[str]) -> str:
        """Parse skill from arguments, returning the resolved skill id."""
        default_skill_id = self._get_default_skill_id()
        if len(args) < 2:
            return default_skill_id

        skill_text = " ".join(args[1:]).strip()
        available_ids = {str(getattr(skill, "name", "")).strip() for skill in self._load_skills()}
        if skill_text in available_ids:
            return skill_text

        for alias_text, skill_id in self._build_skill_alias_pairs():
            if alias_text in skill_text:
                return skill_id

        return default_skill_id

    def _resolve_skill_name(self, skill_id: Optional[str]) -> str:
        """Resolve a skill id to a human-readable display name."""
        if not skill_id:
            return "default"
        for skill in self._load_skills():
            if str(getattr(skill, "name", "")).strip() == skill_id:
                display_name = str(getattr(skill, "display_name", "")).strip()
                return display_name or skill_id
        return skill_id

    @staticmethod
    def _build_execution_context(stock_code: str, skill_id: str) -> Dict[str, Any]:
        selected = [skill_id] if skill_id else []
        return {
            "stock_code": stock_code,
            "skills": selected,
            "strategies": selected,
        }

    @staticmethod
    def _build_user_message(stock_code: str, skill_id: str, skill_text: str) -> str:
        user_msg = f"\u8bf7analyze stock {stock_code}"
        if skill_id:
            user_msg = f"please use {skill_id} \u6280\u80fdanalyze stock {stock_code}"
        if skill_text:
            user_msg = f"\u8bf7analyze stock {stock_code}; {skill_text}"
        return user_msg

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute the ask command via Agent pipeline. Supports multi-stock."""
        config = get_config()

        if not config.agent_mode:
            return BotResponse.text_response(
                "⚠️ Agent mode\u672a\u5f00\u542f; \u65e0\u6cd5\u4f7f\u7528ask-stock\u529f\u80fd.\n\u8bf7\u5728configMedium\u8bbe\u7f6e `AGENT_MODE=true`."
            )

        raw_code_str, remaining_args = self._merge_code_args(args)
        codes = self._parse_stock_codes(raw_code_str)
        skill_id = self._parse_skill(["placeholder"] + remaining_args) if remaining_args else self._get_default_skill_id()
        skill_text = " ".join(remaining_args).strip()

        logger.info("[AskCommand] Stocks: %s, Skill: %s, Extra: %s", codes, skill_id, skill_text)

        if len(codes) == 1:
            return self._analyze_single(config, message, codes[0], skill_id, skill_text)

        return self._analyze_multi(config, message, codes, skill_id, skill_text)

    def _analyze_single(
        self,
        config,
        message: BotMessage,
        code: str,
        skill_id: str,
        skill_text: str,
    ) -> BotResponse:
        """Analyze a single stock."""
        try:
            from src.agent.factory import build_agent_executor

            executor = build_agent_executor(config, skills=[skill_id] if skill_id else None)
            user_msg = self._build_user_message(code, skill_id, skill_text)
            session_id = f"{message.platform}_{message.user_id}:ask_{code}_{uuid.uuid4()}"
            result = executor.chat(
                message=user_msg,
                session_id=session_id,
                context=self._build_execution_context(code, skill_id),
            )

            if result.success:
                skill_name = self._resolve_skill_name(skill_id)
                header = f"📊 {code} | \u6280\u80fd: {skill_name}\n{'─' * 30}\n"
                return BotResponse.text_response(header + result.content)
            return BotResponse.text_response(f"⚠️ analyzefailed: {result.error}")

        except Exception as exc:
            logger.error("Ask command failed: %s", exc)
            logger.exception("Ask error details:")
            return BotResponse.text_response(f"⚠️ ask-stock execution error: {str(exc)}")

    def _analyze_multi(
        self,
        config,
        message: BotMessage,
        codes: List[str],
        skill_id: str,
        skill_text: str,
    ) -> BotResponse:
        """Analyze multiple stocks in parallel and produce a comparison summary."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed

        skill_name = self._resolve_skill_name(skill_id)
        results: Dict[str, Dict[str, Any]] = {}
        errors: Dict[str, str] = {}
        started_at = time.monotonic()
        overall_timeout_s = self._MULTI_ANALYZE_TIMEOUT_S

        platform = message.platform
        user_id = message.user_id

        def _run_one(stock_code: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
            try:
                from src.agent.conversation import conversation_manager
                from src.agent.factory import build_agent_executor

                executor = build_agent_executor(config, skills=[skill_id] if skill_id else None)
                user_msg = self._build_user_message(stock_code, skill_id, skill_text)
                session_id = f"{platform}_{user_id}:ask_{stock_code}_{uuid.uuid4()}"
                conversation_manager.add_message(session_id, "user", user_msg)

                result = executor.run(
                    task=user_msg,
                    context=self._build_execution_context(stock_code, skill_id),
                )
                if result.success or self._should_accept_fallback_content(result):
                    dashboard = result.dashboard if isinstance(result.dashboard, dict) else None
                    formatted_analysis = self._format_stock_result(stock_code, dashboard, result.content)
                    conversation_manager.add_message(session_id, "assistant", formatted_analysis)
                    return (
                        stock_code,
                        {
                            "content": result.content,
                            "dashboard": dashboard,
                            "signal": self._extract_signal(dashboard),
                            "confidence": self._extract_confidence(dashboard),
                            "summary": self._extract_summary(stock_code, dashboard, result.content),
                            "markdown": formatted_analysis,
                            "stock_name": self._extract_stock_name(stock_code, dashboard),
                            "risk_flags": self._extract_risk_flags(dashboard),
                        },
                        None,
                    )

                error_note = f"[analyzefailed] {result.error or 'unknown error'}"
                conversation_manager.add_message(session_id, "assistant", error_note)
                return (stock_code, None, result.error or "unknown error")
            except Exception as exc:
                return (stock_code, None, str(exc))

        # Warm up DB connections before parallel history writes.
        get_db()
        pool = ThreadPoolExecutor(max_workers=min(len(codes), 5))
        future_map = {pool.submit(_run_one, code): code for code in codes}
        try:
            for future in as_completed(future_map, timeout=overall_timeout_s):
                try:
                    code, content, error = future.result(timeout=5)
                    if content is not None:
                        results[code] = content
                    else:
                        errors[code] = error or "unknown error"
                except Exception as exc:
                    code = future_map[future]
                    errors[code] = f"\u6267\u884c\u5f02\u5e38: {exc}"
        except FutureTimeoutError:
            logger.warning("[AskCommand] Multi-stock analysis hit overall timeout (%.1fs)", overall_timeout_s)
            for future, code in future_map.items():
                if code in results or code in errors:
                    continue
                if future.done():
                    try:
                        code_done, content, error = future.result(timeout=0)
                        if content is not None:
                            results[code_done] = content
                        else:
                            errors[code] = error or "unknown error"
                    except Exception as exc:
                        errors[code] = f"\u6267\u884c\u5f02\u5e38: {exc}"
                else:
                    errors[code] = "analyze\u8d85\u65f6 (\u672a\u5728 150 \u79d2\u5185\u5b8c\u6210)"
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        for code in codes:
            if code not in results and code not in errors:
                errors[code] = "analyze\u8d85\u65f6"

        parts = [f"📊 **\u591a\u80a1\u5bf9\u6bd4analyze** | \u6280\u80fd: {skill_name}", f"{'─' * 30}", ""]

        remaining_timeout_s = max(0.0, overall_timeout_s - (time.monotonic() - started_at))
        portfolio_section = self._build_portfolio_section(
            config,
            codes,
            results,
            timeout_s=remaining_timeout_s,
        )
        if portfolio_section:
            parts.append(portfolio_section)
            parts.append("")

        if len(results) >= 2:
            parts.append("| \u80a1\u7968 | \u4fe1\u53f7 | \u7f6e\u4fe1\u5ea6 | summary |")
            parts.append("|------|------|--------|------|")
            for code in codes:
                if code in results:
                    item = results[code]
                    signal = item.get("signal") or "unknown"
                    confidence = item.get("confidence")
                    confidence_text = f"{confidence:.0%}" if isinstance(confidence, (int, float)) else "-"
                    summary_line = str(item.get("summary") or "analysis completed").replace("|", "/")[:80]
                    parts.append(f"| {code} | {signal} | {confidence_text} | {summary_line} |")
                elif code in errors:
                    parts.append(f"| {code} | error | - | ⚠️ {errors[code][:40]} |")
            parts.append("")

        for code in codes:
            if code in results:
                parts.append(f"### {code}")
                parts.append(results[code]["markdown"])
                parts.append("")
            elif code in errors:
                parts.append(f"### {code}")
                parts.append(f"⚠️ analyzefailed: {errors[code]}")
                parts.append("")

        return BotResponse.markdown_response("\n".join(parts))

    @staticmethod
    def _should_accept_fallback_content(result: Any) -> bool:
        """Keep usable free-form answers when dashboard JSON parsing fails."""
        if getattr(result, "success", False):
            return True

        content = getattr(result, "content", "")
        error = str(getattr(result, "error", "") or "")
        if not isinstance(content, str) or not content.strip():
            return False

        return error == "Failed to parse dashboard JSON from agent response"

    @staticmethod
    def _extract_stock_name(stock_code: str, dashboard: Optional[Dict[str, Any]]) -> str:
        if isinstance(dashboard, dict):
            stock_name = dashboard.get("stock_name")
            if isinstance(stock_name, str) and stock_name.strip():
                return stock_name.strip()
        return stock_code

    @staticmethod
    def _extract_signal(dashboard: Optional[Dict[str, Any]]) -> str:
        if isinstance(dashboard, dict):
            signal = dashboard.get("decision_type")
            if isinstance(signal, str) and signal.strip():
                return signal.strip()
        return "unknown"

    @staticmethod
    def _extract_confidence(dashboard: Optional[Dict[str, Any]]) -> Optional[float]:
        if not isinstance(dashboard, dict):
            return None

        score = dashboard.get("sentiment_score")
        try:
            return max(0.0, min(1.0, float(score) / 100.0))
        except (TypeError, ValueError):
            pass

        level = str(dashboard.get("confidence_level") or "").strip()
        return {"High": 0.85, "Medium": 0.65, "Low": 0.45}.get(level)

    @staticmethod
    def _extract_summary(stock_code: str, dashboard: Optional[Dict[str, Any]], raw_content: str) -> str:
        if isinstance(dashboard, dict):
            for key in ("analysis_summary", "risk_warning", "trend_prediction"):
                value = dashboard.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            dashboard_block = dashboard.get("dashboard")
            if not isinstance(dashboard_block, dict):
                dashboard_block = {}
            core_conclusion = dashboard_block.get("core_conclusion")
            if not isinstance(core_conclusion, dict):
                core_conclusion = {}
            core = core_conclusion.get("one_sentence")
            if isinstance(core, str) and core.strip():
                return core.strip()

        for line in raw_content.splitlines():
            stripped = line.strip()
            if stripped and len(stripped) > 4 and not stripped.startswith(("{", "}", "\"")):
                return stripped[:120]
        return f"{stock_code} analysis completed"

    @staticmethod
    def _extract_risk_flags(dashboard: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
        if not isinstance(dashboard, dict):
            return []

        flags: List[Dict[str, str]] = []
        dashboard_block = dashboard.get("dashboard")
        if not isinstance(dashboard_block, dict):
            dashboard_block = {}
        intelligence = dashboard_block.get("intelligence")
        if not isinstance(intelligence, dict):
            intelligence = {}
        for alert in intelligence.get("risk_alerts", [])[:5]:
            if isinstance(alert, str) and alert.strip():
                flags.append({"category": "portfolio_input", "description": alert.strip(), "severity": "medium"})

        risk_warning = dashboard.get("risk_warning")
        if isinstance(risk_warning, str) and risk_warning.strip():
            flags.append({"category": "portfolio_input", "description": risk_warning.strip(), "severity": "medium"})
        return flags

    @staticmethod
    def _format_sniper_value(value: Any) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip()
        if not text or text in {"-", "—", "N/A", "None"}:
            return None

        prefixes = (
            "\u7406\u60f3\u4e70\u5165\u70b9: ",
            "\u6b21\u4f18\u4e70\u5165\u70b9: ",
            "\u6b62\u635fcharacters: ",
            "\u76ee\u6807characters: ",
            "\u7406\u60f3\u4e70\u5165\u70b9:",
            "\u6b21\u4f18\u4e70\u5165\u70b9:",
            "\u6b62\u635fcharacters:",
            "\u76ee\u6807characters:",
        )
        for prefix in prefixes:
            if text.startswith(prefix):
                stripped = text[len(prefix):].strip()
                return stripped or None

        return text

    @staticmethod
    def _format_stock_result(stock_code: str, dashboard: Optional[Dict[str, Any]], raw_content: str) -> str:
        if not isinstance(dashboard, dict):
            content = raw_content
            if len(content) > 800:
                content = content[:800] + "\n... (\u5df2\u622a\u65ad; \u5b8c\u6574analyze\u8bf7\u5355\u72ecquery)"
            return content

        lines = []
        stock_name = dashboard.get("stock_name")
        if isinstance(stock_name, str) and stock_name.strip() and stock_name.strip() != stock_code:
            lines.append(f"**name**: {stock_name.strip()}")

        decision = dashboard.get("decision_type")
        confidence = AskCommand._extract_confidence(dashboard)
        trend = dashboard.get("trend_prediction")
        if isinstance(decision, str):
            lines.append(
                f"**\u7ed3\u8bba**: {decision}"
                + (f" | **\u7f6e\u4fe1\u5ea6**: {confidence:.0%}" if isinstance(confidence, (int, float)) else "")
                + (f" | **\u8d8b\u52bf**: {trend}" if isinstance(trend, str) and trend.strip() else "")
            )

        summary = AskCommand._extract_summary(stock_code, dashboard, raw_content)
        if summary:
            lines.append(f"**summary**: {summary}")

        operation = dashboard.get("operation_advice")
        if isinstance(operation, str) and operation.strip():
            lines.append(f"**operation advice**: {operation.strip()}")

        risk_warning = dashboard.get("risk_warning")
        if isinstance(risk_warning, str) and risk_warning.strip():
            lines.append(f"**risk warning**: {risk_warning.strip()}")

        dashboard_block = dashboard.get("dashboard")
        if not isinstance(dashboard_block, dict):
            dashboard_block = {}
        battle_plan = dashboard_block.get("battle_plan")
        if not isinstance(battle_plan, dict):
            battle_plan = {}
        sniper = battle_plan.get("sniper_points")
        if isinstance(sniper, dict):
            price_parts = []
            for key in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit"):
                value = AskCommand._format_sniper_value(sniper.get(key))
                if value:
                    price_parts.append(f"{key}={value}")
            if price_parts:
                lines.append("**\u5173\u952e\u70b9characters**: " + " | ".join(price_parts))

        return "\n\n".join(lines) if lines else raw_content[:800]

    def _build_portfolio_section(
        self,
        config,
        codes: List[str],
        results: Dict[str, Dict[str, Any]],
        timeout_s: Optional[float] = None,
    ) -> str:
        """Generate a portfolio-level overlay for multi-stock ask results."""
        if len(results) < 2:
            return ""

        if timeout_s is not None and timeout_s <= 0:
            logger.info("[AskCommand] Skip portfolio overlay because no timeout budget remains")
            return ""

        def _render_overlay() -> str:
            from src.agent.agents.portfolio_agent import PortfolioAgent
            from src.agent.factory import get_tool_registry
            from src.agent.llm_adapter import LLMToolAdapter
            from src.agent.protocols import AgentContext

            stock_opinions: Dict[str, Dict[str, Any]] = {}
            risk_flags: List[Dict[str, str]] = []
            stock_list: List[str] = []
            for code in codes:
                item = results.get(code)
                if not item:
                    continue
                stock_list.append(code)
                stock_opinions[code] = {
                    "signal": item.get("signal", "unknown"),
                    "confidence": item.get("confidence", 0.5),
                    "summary": item.get("summary", ""),
                    "stock_name": item.get("stock_name", code),
                }
                risk_flags.extend(item.get("risk_flags", []))

            ctx = AgentContext(query=f"Portfolio overlay for {', '.join(stock_list)}")
            ctx.data["stock_opinions"] = stock_opinions
            ctx.data["stock_list"] = stock_list
            ctx.risk_flags.extend(risk_flags[:10])

            agent = PortfolioAgent(
                tool_registry=get_tool_registry(),
                llm_adapter=LLMToolAdapter(config),
            )
            stage_result = agent.run(ctx)
            if not stage_result.success:
                return ""

            assessment = ctx.data.get("portfolio_assessment")
            if not isinstance(assessment, dict):
                return ""

            lines = ["## \u7ec4\u5408\u89c6\u89d2", ""]
            summary = assessment.get("summary")
            if isinstance(summary, str) and summary.strip():
                lines.append(summary.strip())
                lines.append("")

            risk_score = assessment.get("portfolio_risk_score")
            if risk_score is not None:
                lines.append(f"- \u7ec4\u5408\u98ce\u9669\u5206: {risk_score}")
            sector_warnings = assessment.get("sector_warnings") or []
            if sector_warnings:
                lines.append(f"- industry\u96c6Medium: {'；'.join(str(item) for item in sector_warnings[:3])}")
            correlation_warnings = assessment.get("correlation_warnings") or []
            if correlation_warnings:
                lines.append(f"- \u76f8\u5173\u98ce\u9669: {'；'.join(str(item) for item in correlation_warnings[:3])}")
            rebalance = assessment.get("rebalance_suggestions") or []
            if rebalance:
                lines.append(f"- \u8c03\u4ed3\u5efa\u8bae: {'；'.join(str(item) for item in rebalance[:3])}")
            positions = assessment.get("positions") or []
            if positions:
                position_parts = []
                for position in positions[:5]:
                    if not isinstance(position, dict):
                        continue
                    code = position.get("code")
                    weight = position.get("suggested_weight")
                    signal = position.get("signal")
                    if code and weight is not None:
                        try:
                            weight_text = f"{float(weight):.0%}"
                        except (TypeError, ValueError):
                            weight_text = str(weight)
                        suffix = f" ({signal})" if signal else ""
                        position_parts.append(f"{code}: {weight_text}{suffix}")
                if position_parts:
                    lines.append(f"- \u5efa\u8bae\u4ed3characters: {'；'.join(position_parts)}")

            return "\n".join(lines)

        if timeout_s is None:
            try:
                return _render_overlay()
            except Exception as exc:
                logger.warning("[AskCommand] Portfolio overlay failed: %s", exc)
                return ""

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_render_overlay)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeoutError:
            logger.warning("[AskCommand] Portfolio overlay timed out after %.2fs", timeout_s)
            return ""
        except Exception as exc:
            logger.warning("[AskCommand] Portfolio overlay failed: %s", exc)
            return ""
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
