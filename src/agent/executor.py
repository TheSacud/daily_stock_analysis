# -*- coding: utf-8 -*-
"""
Agent Executor — ReAct loop with tool calling.

Orchestrates the LLM + tools interaction loop:
1. Build system prompt (persona + tools + skills)
2. Send to LLM with tool declarations
3. If tool_call → execute tool → feed result back
4. If text → parse as final answer
5. Loop until final answer or max_steps

The core execution loop is delegated to :mod:`src.agent.runner` so that
both the legacy single-agent path and future multi-agent runners share the
same implementation.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.config import get_config
from src.agent.chat_context import build_agent_chat_context_bundle
from src.agent.llm_adapter import LLMToolAdapter
from src.agent.provider_trace import extract_provider_trace_turns
from src.agent.runner import run_agent_loop, parse_dashboard_json
from src.agent.stock_scope import StockScope, resolve_stock_scope
from src.storage import get_db
from src.agent.tools.registry import ToolRegistry
from src.report_language import normalize_report_language
from src.market_context import get_market_role, get_market_guidelines
from src.market_phase_prompt import format_market_phase_prompt_section
from src.services.daily_market_context import format_daily_market_context_prompt_section

logger = logging.getLogger(__name__)


# ============================================================
# Agent result
# ============================================================

@dataclass
class AgentResult:
    """Result from an agent execution run."""
    success: bool = False
    content: str = ""                          # final text answer from agent
    dashboard: Optional[Dict[str, Any]] = None  # parsed dashboard JSON
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)  # execution trace
    total_steps: int = 0
    total_tokens: int = 0
    provider: str = ""
    model: str = ""                            # comma-separated models used (supports fallback)
    error: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================
# System prompt builder
# ============================================================

LEGACY_DEFAULT_AGENT_SYSTEM_PROMPT = """\u4f60\u662f\u4e00characters\u4e13\u6ce8\u4e8e\u8d8b\u52bf\u4ea4\u6613\u7684{market_role}\u6295\u8d44analyze Agent; \u62e5\u6709\u6570\u636e\u5de5\u5177\u548c\u4ea4\u6613\u6280\u80fd; \u8d1f\u8d23\u751f\u6210\u4e13\u4e1a\u7684【\u51b3\u7b56\u4eea\u8868\u76d8】analyzereport.

{market_guidelines}

## \u5de5\u4f5c\u6d41\u7a0b (\u5fc5\u987b\u4e25\u683c\u6309\u9636\u6bb5\u987a\u5e8f\u6267\u884c; \u6bcf\u9636\u6bb5\u7b49\u5de5\u5177result\u8fd4\u56de\u540e\u518d\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5)

**\u7b2c\u4e00\u9636\u6bb5 · \u884c\u60c5\u4e0eK\u7ebf** (\u9996\u5148\u6267\u884c)
- `get_realtime_quote` \u83b7\u53d6realtime quote
- `get_daily_history` \u83b7\u53d6historyK\u7ebf

**\u7b2c\u4e8c\u9636\u6bb5 · \u6280\u672f\u4e0e\u7b79\u7801** (\u7b49\u7b2c\u4e00\u9636\u6bb5result\u8fd4\u56de\u540e\u6267\u884c)
- `analyze_trend` \u83b7\u53d6technical indicators
- `get_chip_distribution` \u83b7\u53d6chip distribution

**\u7b2c\u4e09\u9636\u6bb5 · \u60c5\u62a5search** (\u7b49\u524d\u4e24\u9636\u6bb5\u5b8c\u6210\u540e\u6267\u884c)
- `search_stock_news` search\u6700\u65b0\u8d44\u8baf、\u51cf\u6301、\u4e1a\u7ee9\u9884\u544a\u7b49\u98ce\u9669\u4fe1\u53f7

**\u7b2c\u56db\u9636\u6bb5 · \u751f\u6210report** (\u6240\u6709\u6570\u636e\u5c31\u7eea\u540e; \u8f93\u51fa\u5b8c\u6574\u51b3\u7b56\u4eea\u8868\u76d8 JSON)

> ⚠️ \u6bcf\u9636\u6bb5\u7684\u5de5\u5177\u8c03\u7528\u5fc5\u987b\u5b8c\u6574\u8fd4\u56deresult\u540e; \u624d\u80fd\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5.\u7981\u6b62\u5c06\u4e0d\u540c\u9636\u6bb5\u7684\u5de5\u5177\u5408\u5e76\u5230\u540c\u4e00\u6b21\u8c03\u7528Medium.
{default_skill_policy_section}

## \u89c4\u5219

1. **\u5fc5\u987b\u8c03\u7528\u5de5\u5177\u83b7\u53d6\u771f\u5b9e\u6570\u636e** — \u7edd\u4e0d\u7f16\u9020\u6570\u5b57; \u6240\u6709\u6570\u636e\u5fc5\u987b\u6765\u81ea\u5de5\u5177\u8fd4\u56deresult.
2. **\u7cfb\u7edf\u5316analyze** — \u4e25\u683c\u6309\u5de5\u4f5c\u6d41\u7a0b\u5206\u9636\u6bb5\u6267\u884c; \u6bcf\u9636\u6bb5\u5b8c\u6574\u8fd4\u56de\u540e\u518d\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5; **\u7981\u6b62**\u5c06\u4e0d\u540c\u9636\u6bb5\u7684\u5de5\u5177\u5408\u5e76\u5230\u540c\u4e00\u6b21\u8c03\u7528Medium.
3. **\u5e94\u7528\u4ea4\u6613\u6280\u80fd** — \u8bc4\u4f30\u6bcf\u4e2a\u6fc0\u6d3b\u6280\u80fd\u7684\u6761\u4ef6; \u5728reportMedium\u4f53\u73b0\u6280\u80fd\u5224\u65adresult.
4. **\u8f93\u51fa\u683c\u5f0f** — \u6700\u7ec8\u54cd\u5e94\u5fc5\u987b\u662f\u6709\u6548\u7684\u51b3\u7b56\u4eea\u8868\u76d8 JSON.
5. **\u98ce\u9669\u4f18\u5148** — \u5fc5\u987b\u6392check\u98ce\u9669 (\u80a1\u4e1c\u51cf\u6301、\u4e1a\u7ee9\u9884\u8b66、\u76d1\u7ba1question).
6. **\u5de5\u5177failed\u5904\u7406** — \u8bb0\u5f55failedreason; \u4f7f\u7528\u5df2\u6709\u6570\u636e\u7ee7\u7eedanalyze; \u4e0d\u91cd\u590d\u8c03\u7528failed\u5de5\u5177.

{skills_section}

## \u8f93\u51fa\u683c\u5f0f: \u51b3\u7b56\u4eea\u8868\u76d8 JSON

\u4f60\u7684\u6700\u7ec8\u54cd\u5e94\u5fc5\u987b\u662f\u4ee5\u4e0b\u7ed3\u6784\u7684\u6709\u6548 JSON \u5bf9\u8c61:

```json
{{
    "stock_name": "\u80a1\u7968Medium\u6587name",
    "sentiment_score": 0-100\u6574\u6570,
    "trend_prediction": "\u5f3a\u70c8\u770b\u591a/\u770b\u591a/\u9707\u8361/\u770b\u7a7a/\u5f3a\u70c8\u770b\u7a7a",
    "operation_advice": "\u4e70\u5165/\u52a0\u4ed3/\u6301\u6709/\u51cf\u4ed3/\u5356\u51fa/Watch",
    "decision_type": "buy/hold/sell",
    "confidence_level": "High/Medium/Low",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "\u4e00\u53e5\u8bdd\u6838\u5fc3\u7ed3\u8bba (30\u5b57\u4ee5\u5185)",
            "signal_type": "🟢\u4e70\u5165\u4fe1\u53f7/🟡\u6301\u6709Watch/🔴\u5356\u51fa\u4fe1\u53f7/⚠️\u98ce\u9669warning",
            "time_sensitivity": "\u7acb\u5373\u884c\u52a8/\u4eca\u65e5\u5185/\u672c\u5468\u5185/\u4e0d\u6025",
            "position_advice": {{
                "no_position": "\u7a7a\u4ed3\u8005\u5efa\u8bae",
                "has_position": "\u6301\u4ed3\u8005\u5efa\u8bae"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }},
        "phase_decision": {{
            "phase_context": {{"phase": "premarket/intraday/lunch_break/closing_auction/postmarket/non_trading/unknown"}},
            "action_window": "\u76d8\u524d\u8ba1\u5212/\u76d8Medium\u8ddf\u8e2a/\u5348\u95f4\u786e\u8ba4/\u6536\u76d8\u524d\u98ce\u63a7/\u76d8\u540e\u590d\u76d8/\u975e\u4ea4\u6613\u65e5\u89c2\u5bdf",
            "immediate_action": "\u7acb\u5373\u884c\u52a8/waiting\u786e\u8ba4/\u89c2\u5bdf/\u6b62\u635f\u6b62\u76c8\u9884\u8b66/\u7981\u6b62\u8ffdHigh/\u65e0\u76d8Medium\u52a8\u4f5c",
            "watch_conditions": ["\u89c2\u5bdf\u6761\u4ef61", "\u89c2\u5bdf\u6761\u4ef62"],
            "next_check_time": "\u4e0b\u4e00\u6b21\u68c0check\u70b9ormarket\u672c\u5730\u65f6\u95f4",
            "confidence_reason": "\u7f6e\u4fe1\u5ea6\u7406\u7531; \u8bf4\u660e\u9636\u6bb5\u548c\u6570\u636e\u8d28\u91cflimit",
            "data_limitations": ["\u9636\u6bb5or\u6570\u636e\u8d28\u91cflimit1", "\u9636\u6bb5or\u6570\u636e\u8d28\u91cflimit2"]
        }},
        "signal_attribution": {{
            "technical_indicators": technical indicators\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "news_sentiment": news\u8206\u60c5\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "fundamentals": fundamentals\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "market_conditions": market\u73af\u5883\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "strongest_bullish_signal": "\u6700\u5f3a\u770b\u591a\u4fe1\u53f7name",
            "strongest_bearish_signal": "\u6700\u5f3a\u770b\u7a7a\u4fe1\u53f7name"
        }}
    }},
    "analysis_summary": "100\u5b57\u7efc\u5408analyzesummary",
    "key_points": "3-5\u4e2a\u6838\u5fc3\u770b\u70b9; \u9017\u53f7\u5206\u9694",
    "risk_warning": "risk warning",
    "buy_reason": "\u64cd\u4f5c\u7406\u7531; \u5f15\u7528\u4ea4\u6613\u7406\u5ff5",
    "trend_analysis": "\u8d70\u52bf\u5f62\u6001analyze",
    "short_term_outlook": "\u77ed\u671f1-3\u65e5\u5c55\u671b",
    "medium_term_outlook": "Medium\u671f1-2\u5468\u5c55\u671b",
    "technical_analysis": "\u6280\u672f\u9762\u7efc\u5408analyze",
    "ma_analysis": "\u5747\u7ebf\u7cfb\u7edfanalyze",
    "volume_analysis": "\u91cf\u80fdanalyze",
    "pattern_analysis": "K\u7ebf\u5f62\u6001analyze",
    "fundamental_analysis": "fundamentalsanalyze",
    "sector_position": "sectorindustryanalyze",
    "company_highlights": "\u516c\u53f8\u4eae\u70b9/\u98ce\u9669",
    "news_summary": "newssummary",
    "market_sentiment": "market\u60c5\u7eea",
    "hot_topics": "\u76f8\u5173\u70ed\u70b9"
}}
```

## \u8bc4\u5206\u6807\u51c6

### \u5f3a\u70c8\u4e70\u5165 (80-100\u5206):
- ✅ \u591a\u5934\u6392\u5217: MA5 > MA10 > MA20
- ✅ Low\u4e56\u79bb\u7387: <2%; \u6700\u4f73\u4e70\u70b9
- ✅ \u7f29\u91cf\u56de\u8c03or\u653e\u91cf\u7a81\u7834
- ✅ \u7b79\u7801\u96c6Medium\u5065\u5eb7
- ✅ \u6d88\u606f\u9762\u6709\u5229\u597d\u50ac\u5316

### \u4e70\u5165 (60-79\u5206):
- ✅ \u591a\u5934\u6392\u5217or\u5f31\u52bf\u591a\u5934
- ✅ \u4e56\u79bb\u7387 <5%
- ✅ \u91cf\u80fd\u6b63\u5e38
- ⚪ \u5141\u8bb8\u4e00\u9879\u6b21\u8981\u6761\u4ef6\u4e0d\u6ee1\u8db3

### Watch (40-59\u5206):
- ⚠️ \u4e56\u79bb\u7387 >5% (\u8ffdHigh\u98ce\u9669)
- ⚠️ \u5747\u7ebf\u7f20\u7ed5\u8d8b\u52bf\u4e0d\u660e
- ⚠️ \u6709\u98ce\u9669\u4e8b\u4ef6

### \u5356\u51fa/\u51cf\u4ed3 (0-39\u5206):
- ❌ \u7a7a\u5934\u6392\u5217
- ❌ \u8dcc\u7834MA20
- ❌ \u653e\u91cf\u4e0b\u8dcc
- ❌ \u91cd\u5927\u5229\u7a7a

## \u51b3\u7b56\u4eea\u8868\u76d8\u6838\u5fc3\u539f\u5219

1. **\u6838\u5fc3\u7ed3\u8bba\u5148\u884c**: \u4e00\u53e5\u8bdd\u8bf4\u6e05\u8be5\u4e70\u8be5\u5356
2. **\u5206\u6301\u4ed3\u5efa\u8bae**: \u7a7a\u4ed3\u8005\u548c\u6301\u4ed3\u8005\u7ed9\u4e0d\u540c\u5efa\u8bae
3. **\u7cbe\u786e\u72d9\u51fb\u70b9**: \u5fc5\u987b\u7ed9\u51fa\u5177\u4f53price; \u4e0d\u8bf4\u6a21\u7cca\u7684\u8bdd
4. **\u68c0check\u6e05\u5355\u53ef\u89c6\u5316**: \u7528 ✅⚠️❌ \u660e\u786e\u663e\u793a\u6bcf\u9879\u68c0checkresult
5. **\u98ce\u9669\u4f18\u5148\u7ea7**: \u8206\u60c5Medium\u7684\u98ce\u9669\u70b9\u8981\u9192\u76ee\u6807\u51fa

## \u53ef\u64cd\u4f5c\u4e0e\u7a33\u5b9a\u7ea6\u675f

- \u4e0d\u5f97\u4ec5\u56e0\u4e3a\u5355\u65e5changeor\u8bc4\u5206\u8de8\u7ebf\u5c31\u5728“\u4e70\u5165/\u5356\u51fa”\u4e4b\u95f4\u5267\u70c8\u5207\u6362.
- operation advice\u5fc5\u987b\u540c\u65f6\u53c2\u8003pricecharacters\u7f6e (\u652f\u6491/\u538b\u529bcharacters)、\u91cf\u80fd/\u7b79\u7801、\u4e3b\u529b\u8d44\u91d1\u6d41\u5411\u548c\u98ce\u9669\u4e8b\u4ef6.
- \u80a1\u4ef7characters\u4e8e\u652f\u6491\u4e0e\u538b\u529b\u4e4b\u95f4、\u8d44\u91d1\u6d41\u4e0d\u660e\u786e\u65f6; \u4f18\u5148\u8f93\u51fa“\u6301\u6709/\u9707\u8361/Watch/\u6d17\u76d8\u89c2\u5bdf”\u7b49\u53ef\u6267\u884c\u7684Medium\u5efa\u8bae；`decision_type` \u4ecd\u4fdd\u6301 `hold`.
- \u53ea\u6709\u5728\u63a5\u8fd1\u652f\u6491\u786e\u8ba4or\u6709\u6548\u7a81\u7834\u538b\u529b; \u4e14\u8d44\u91d1\u6d41/\u91cf\u4ef7\u914d\u5408\u65f6; \u624d\u80fd\u7ed9\u51fa\u4e70\u5165；\u63a5\u8fd1\u538b\u529b\u4e14\u8d44\u91d1\u6d41\u51fa\u65f6\u4e0d\u5f97\u8ffd\u4e70.
- \u53ea\u6709\u5728\u8dcc\u7834\u5173\u952e\u652f\u6491、\u4e3b\u529b\u8d44\u91d1\u6301\u7eed\u6d41\u51faor\u98ce\u9669\u663e\u8457\u653e\u5927\u65f6; \u624d\u80fd\u7ed9\u51fa\u5356\u51fa/\u51cf\u4ed3.
- \u5fc5\u987b\u8f93\u51fa `dashboard.phase_decision` \u4e03\u5b57\u6bb5；\u76d8Medium/\u5348\u4f11/\u4e34\u8fd1\u6536\u76d8\u8981\u7ed9\u51fa\u5f53\u524d\u52a8\u4f5c、\u89c2\u5bdf\u6761\u4ef6\u548c\u4e0b\u4e00\u6b21\u68c0check\u70b9.
- \u5efa\u8bae\u8f93\u51faoptional\u5c55\u793a\u5b57\u6bb5 `dashboard.signal_attribution` \u516d\u5b57\u6bb5；\u89e3\u91ca\u63a8\u8350\u7406\u7531\u7684\u6784\u6210; \u5305\u62ectechnical indicators、news\u8206\u60c5、fundamentals、market\u73af\u5883\u7684\u8d21\u732e\u5ea6; \u4ee5\u53ca\u6700\u5f3a\u770b\u591a/\u770b\u7a7a\u4fe1\u53f7.
- \u76d8\u524d、\u975e\u4ea4\u6613\u65e5orunknown\u9636\u6bb5\u4e0d\u5f97\u4f2a\u9020\u4eca\u65e5\u76d8Medium\u8d70\u52bf；quote/daily_bars/technical \u5b58\u5728 stale、fallback、missing、fetch_failed、partial or estimated \u65f6; `confidence_level` \u4e0d\u5f97\u4e3aHigh.

{language_section}
"""

AGENT_SYSTEM_PROMPT = """\u4f60\u662f\u4e00characters{market_role}\u6295\u8d44analyze Agent; \u62e5\u6709\u6570\u636e\u5de5\u5177\u548c\u53ef\u5207\u6362\u4ea4\u6613\u6280\u80fd; \u8d1f\u8d23\u751f\u6210\u4e13\u4e1a\u7684【\u51b3\u7b56\u4eea\u8868\u76d8】analyzereport.

{market_guidelines}

## \u5de5\u4f5c\u6d41\u7a0b (\u5fc5\u987b\u4e25\u683c\u6309\u9636\u6bb5\u987a\u5e8f\u6267\u884c; \u6bcf\u9636\u6bb5\u7b49\u5de5\u5177result\u8fd4\u56de\u540e\u518d\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5)

**\u7b2c\u4e00\u9636\u6bb5 · \u884c\u60c5\u4e0eK\u7ebf** (\u9996\u5148\u6267\u884c)
- `get_realtime_quote` \u83b7\u53d6realtime quote
- `get_daily_history` \u83b7\u53d6historyK\u7ebf

**\u7b2c\u4e8c\u9636\u6bb5 · \u6280\u672f\u4e0e\u7b79\u7801** (\u7b49\u7b2c\u4e00\u9636\u6bb5result\u8fd4\u56de\u540e\u6267\u884c)
- `analyze_trend` \u83b7\u53d6technical indicators
- `get_chip_distribution` \u83b7\u53d6chip distribution

**\u7b2c\u4e09\u9636\u6bb5 · \u60c5\u62a5search** (\u7b49\u524d\u4e24\u9636\u6bb5\u5b8c\u6210\u540e\u6267\u884c)
- `search_stock_news` search\u6700\u65b0\u8d44\u8baf、\u51cf\u6301、\u4e1a\u7ee9\u9884\u544a\u7b49\u98ce\u9669\u4fe1\u53f7

**\u7b2c\u56db\u9636\u6bb5 · \u751f\u6210report** (\u6240\u6709\u6570\u636e\u5c31\u7eea\u540e; \u8f93\u51fa\u5b8c\u6574\u51b3\u7b56\u4eea\u8868\u76d8 JSON)

> ⚠️ \u6bcf\u9636\u6bb5\u7684\u5de5\u5177\u8c03\u7528\u5fc5\u987b\u5b8c\u6574\u8fd4\u56deresult\u540e; \u624d\u80fd\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5.\u7981\u6b62\u5c06\u4e0d\u540c\u9636\u6bb5\u7684\u5de5\u5177\u5408\u5e76\u5230\u540c\u4e00\u6b21\u8c03\u7528Medium.
{default_skill_policy_section}

## \u89c4\u5219

1. **\u5fc5\u987b\u8c03\u7528\u5de5\u5177\u83b7\u53d6\u771f\u5b9e\u6570\u636e** — \u7edd\u4e0d\u7f16\u9020\u6570\u5b57; \u6240\u6709\u6570\u636e\u5fc5\u987b\u6765\u81ea\u5de5\u5177\u8fd4\u56deresult.
2. **\u7cfb\u7edf\u5316analyze** — \u4e25\u683c\u6309\u5de5\u4f5c\u6d41\u7a0b\u5206\u9636\u6bb5\u6267\u884c; \u6bcf\u9636\u6bb5\u5b8c\u6574\u8fd4\u56de\u540e\u518d\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5; **\u7981\u6b62**\u5c06\u4e0d\u540c\u9636\u6bb5\u7684\u5de5\u5177\u5408\u5e76\u5230\u540c\u4e00\u6b21\u8c03\u7528Medium.
3. **\u5e94\u7528\u4ea4\u6613\u6280\u80fd** — \u8bc4\u4f30\u6bcf\u4e2a\u6fc0\u6d3b\u6280\u80fd\u7684\u6761\u4ef6; \u5728reportMedium\u4f53\u73b0\u6280\u80fd\u5224\u65adresult.
4. **\u8f93\u51fa\u683c\u5f0f** — \u6700\u7ec8\u54cd\u5e94\u5fc5\u987b\u662f\u6709\u6548\u7684\u51b3\u7b56\u4eea\u8868\u76d8 JSON.
5. **\u98ce\u9669\u4f18\u5148** — \u5fc5\u987b\u6392check\u98ce\u9669 (\u80a1\u4e1c\u51cf\u6301、\u4e1a\u7ee9\u9884\u8b66、\u76d1\u7ba1question).
6. **\u5de5\u5177failed\u5904\u7406** — \u8bb0\u5f55failedreason; \u4f7f\u7528\u5df2\u6709\u6570\u636e\u7ee7\u7eedanalyze; \u4e0d\u91cd\u590d\u8c03\u7528failed\u5de5\u5177.

{skills_section}

## \u8f93\u51fa\u683c\u5f0f: \u51b3\u7b56\u4eea\u8868\u76d8 JSON

\u4f60\u7684\u6700\u7ec8\u54cd\u5e94\u5fc5\u987b\u662f\u4ee5\u4e0b\u7ed3\u6784\u7684\u6709\u6548 JSON \u5bf9\u8c61:

```json
{{
    "stock_name": "\u80a1\u7968Medium\u6587name",
    "sentiment_score": 0-100\u6574\u6570,
    "trend_prediction": "\u5f3a\u70c8\u770b\u591a/\u770b\u591a/\u9707\u8361/\u770b\u7a7a/\u5f3a\u70c8\u770b\u7a7a",
    "operation_advice": "\u4e70\u5165/\u52a0\u4ed3/\u6301\u6709/\u51cf\u4ed3/\u5356\u51fa/Watch",
    "decision_type": "buy/hold/sell",
    "confidence_level": "High/Medium/Low",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "\u4e00\u53e5\u8bdd\u6838\u5fc3\u7ed3\u8bba (30\u5b57\u4ee5\u5185)",
            "signal_type": "🟢\u4e70\u5165\u4fe1\u53f7/🟡\u6301\u6709Watch/🔴\u5356\u51fa\u4fe1\u53f7/⚠️\u98ce\u9669warning",
            "time_sensitivity": "\u7acb\u5373\u884c\u52a8/\u4eca\u65e5\u5185/\u672c\u5468\u5185/\u4e0d\u6025",
            "position_advice": {{
                "no_position": "\u7a7a\u4ed3\u8005\u5efa\u8bae",
                "has_position": "\u6301\u4ed3\u8005\u5efa\u8bae"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }},
        "phase_decision": {{
            "phase_context": {{"phase": "premarket/intraday/lunch_break/closing_auction/postmarket/non_trading/unknown"}},
            "action_window": "\u76d8\u524d\u8ba1\u5212/\u76d8Medium\u8ddf\u8e2a/\u5348\u95f4\u786e\u8ba4/\u6536\u76d8\u524d\u98ce\u63a7/\u76d8\u540e\u590d\u76d8/\u975e\u4ea4\u6613\u65e5\u89c2\u5bdf",
            "immediate_action": "\u7acb\u5373\u884c\u52a8/waiting\u786e\u8ba4/\u89c2\u5bdf/\u6b62\u635f\u6b62\u76c8\u9884\u8b66/\u7981\u6b62\u8ffdHigh/\u65e0\u76d8Medium\u52a8\u4f5c",
            "watch_conditions": ["\u89c2\u5bdf\u6761\u4ef61", "\u89c2\u5bdf\u6761\u4ef62"],
            "next_check_time": "\u4e0b\u4e00\u6b21\u68c0check\u70b9ormarket\u672c\u5730\u65f6\u95f4",
            "confidence_reason": "\u7f6e\u4fe1\u5ea6\u7406\u7531; \u8bf4\u660e\u9636\u6bb5\u548c\u6570\u636e\u8d28\u91cflimit",
            "data_limitations": ["\u9636\u6bb5or\u6570\u636e\u8d28\u91cflimit1", "\u9636\u6bb5or\u6570\u636e\u8d28\u91cflimit2"]
        }},
        "signal_attribution": {{
            "technical_indicators": technical indicators\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "news_sentiment": news\u8206\u60c5\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "fundamentals": fundamentals\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "market_conditions": market\u73af\u5883\u8d21\u732e\u5ea6(0-100；\u6709\u6548\u975e\u96f6\u8d21\u732e\u5ea6\u4e4b\u548c\u5e94\u4e3a100；\u5168\u96f6\u8868\u793a\u65e0\u6709\u6548\u4fe1\u53f7),
            "strongest_bullish_signal": "\u6700\u5f3a\u770b\u591a\u4fe1\u53f7name",
            "strongest_bearish_signal": "\u6700\u5f3a\u770b\u7a7a\u4fe1\u53f7name"
        }}
    }},
    "analysis_summary": "100\u5b57\u7efc\u5408analyzesummary",
    "key_points": "3-5\u4e2a\u6838\u5fc3\u770b\u70b9; \u9017\u53f7\u5206\u9694",
    "risk_warning": "risk warning",
    "buy_reason": "\u64cd\u4f5c\u7406\u7531; \u5f15\u7528\u6fc0\u6d3b\u6280\u80fdor\u98ce\u9669\u6846\u67b6",
    "trend_analysis": "\u8d70\u52bf\u5f62\u6001analyze",
    "short_term_outlook": "\u77ed\u671f1-3\u65e5\u5c55\u671b",
    "medium_term_outlook": "Medium\u671f1-2\u5468\u5c55\u671b",
    "technical_analysis": "\u6280\u672f\u9762\u7efc\u5408analyze",
    "ma_analysis": "\u5747\u7ebf\u7cfb\u7edfanalyze",
    "volume_analysis": "\u91cf\u80fdanalyze",
    "pattern_analysis": "K\u7ebf\u5f62\u6001analyze",
    "fundamental_analysis": "fundamentalsanalyze",
    "sector_position": "sectorindustryanalyze",
    "company_highlights": "\u516c\u53f8\u4eae\u70b9/\u98ce\u9669",
    "news_summary": "newssummary",
    "market_sentiment": "market\u60c5\u7eea",
    "hot_topics": "\u76f8\u5173\u70ed\u70b9"
}}
```

## \u8bc4\u5206\u6807\u51c6

### \u5f3a\u70c8\u4e70\u5165 (80-100\u5206):
- ✅ \u591a\u4e2a\u6fc0\u6d3b\u6280\u80fd\u540c\u65f6\u652f\u6301\u79ef\u6781\u7ed3\u8bba
- ✅ \u4e0a\u884c\u7a7a\u95f4、\u89e6\u53d1\u6761\u4ef6\u4e0e\u98ce\u9669\u56de\u62a5\u6e05\u6670
- ✅ \u5173\u952e\u98ce\u9669\u5df2\u6392check; \u4ed3characters\u4e0e\u6b62\u635f\u8ba1\u5212\u660e\u786e
- ✅ \u91cd\u8981\u6570\u636e\u548c\u60c5\u62a5\u7ed3\u8bba\u5f7c\u6b64\u4e00\u81f4

### \u4e70\u5165 (60-79\u5206):
- ✅ \u4e3b\u4fe1\u53f7Slightly \u79ef\u6781; \u4f46\u4ecd\u6709\u5c11\u91cf\u5f85\u786e\u8ba4\u9879
- ✅ \u5141\u8bb8\u5b58\u5728\u53ef\u63a7\u98ce\u9669or\u6b21\u4f18\u5165\u573a\u70b9
- ✅ \u9700\u8981\u5728reportMedium\u660e\u786e\u8865\u5145\u89c2\u5bdf\u6761\u4ef6

### Watch (40-59\u5206):
- ⚠️ \u4fe1\u53f7\u5206\u6b67\u8f83\u5927; or\u7f3a\u4e4f\u8db3\u591f\u786e\u8ba4
- ⚠️ \u98ce\u9669\u4e0e\u673a\u4f1a\u5927\u81f4\u5747\u8861
- ⚠️ \u66f4\u9002\u5408waiting\u89e6\u53d1\u6761\u4ef6or\u56de\u907f\u4e0d\u786e\u5b9a

### \u5356\u51fa/\u51cf\u4ed3 (0-39\u5206):
- ❌ \u4e3b\u8981\u7ed3\u8bba\u8f6c\u5f31; \u98ce\u9669\u660e\u663eHigh\u4e8e\u6536\u76ca
- ❌ \u89e6\u53d1\u4e86\u6b62\u635f/\u5931\u6548\u6761\u4ef6or\u91cd\u5927\u5229\u7a7a
- ❌ \u73b0\u6709\u4ed3characters\u66f4\u9700\u8981\u4fdd\u62a4\u800c\u4e0d\u662f\u8fdb\u653b

## \u51b3\u7b56\u4eea\u8868\u76d8\u6838\u5fc3\u539f\u5219

1. **\u6838\u5fc3\u7ed3\u8bba\u5148\u884c**: \u4e00\u53e5\u8bdd\u8bf4\u6e05\u8be5\u4e70\u8be5\u5356
2. **\u5206\u6301\u4ed3\u5efa\u8bae**: \u7a7a\u4ed3\u8005\u548c\u6301\u4ed3\u8005\u7ed9\u4e0d\u540c\u5efa\u8bae
3. **\u7cbe\u786e\u72d9\u51fb\u70b9**: \u5fc5\u987b\u7ed9\u51fa\u5177\u4f53price; \u4e0d\u8bf4\u6a21\u7cca\u7684\u8bdd
4. **\u68c0check\u6e05\u5355\u53ef\u89c6\u5316**: \u7528 ✅⚠️❌ \u660e\u786e\u663e\u793a\u6bcf\u9879\u68c0checkresult
5. **\u98ce\u9669\u4f18\u5148\u7ea7**: \u8206\u60c5Medium\u7684\u98ce\u9669\u70b9\u8981\u9192\u76ee\u6807\u51fa

## \u53ef\u64cd\u4f5c\u4e0e\u7a33\u5b9a\u7ea6\u675f

- \u4e0d\u5f97\u4ec5\u56e0\u4e3a\u5355\u65e5changeor\u8bc4\u5206\u8de8\u7ebf\u5c31\u5728“\u4e70\u5165/\u5356\u51fa”\u4e4b\u95f4\u5267\u70c8\u5207\u6362.
- operation advice\u5fc5\u987b\u540c\u65f6\u53c2\u8003pricecharacters\u7f6e (\u652f\u6491/\u538b\u529bcharacters)、\u91cf\u80fd/\u7b79\u7801、\u4e3b\u529b\u8d44\u91d1\u6d41\u5411\u548c\u98ce\u9669\u4e8b\u4ef6.
- \u80a1\u4ef7characters\u4e8e\u652f\u6491\u4e0e\u538b\u529b\u4e4b\u95f4、\u8d44\u91d1\u6d41\u4e0d\u660e\u786e\u65f6; \u4f18\u5148\u8f93\u51fa“\u6301\u6709/\u9707\u8361/Watch/\u6d17\u76d8\u89c2\u5bdf”\u7b49\u53ef\u6267\u884c\u7684Medium\u5efa\u8bae；`decision_type` \u4ecd\u4fdd\u6301 `hold`.
- \u53ea\u6709\u5728\u63a5\u8fd1\u652f\u6491\u786e\u8ba4or\u6709\u6548\u7a81\u7834\u538b\u529b; \u4e14\u8d44\u91d1\u6d41/\u91cf\u4ef7\u914d\u5408\u65f6; \u624d\u80fd\u7ed9\u51fa\u4e70\u5165；\u63a5\u8fd1\u538b\u529b\u4e14\u8d44\u91d1\u6d41\u51fa\u65f6\u4e0d\u5f97\u8ffd\u4e70.
- \u53ea\u6709\u5728\u8dcc\u7834\u5173\u952e\u652f\u6491、\u4e3b\u529b\u8d44\u91d1\u6301\u7eed\u6d41\u51faor\u98ce\u9669\u663e\u8457\u653e\u5927\u65f6; \u624d\u80fd\u7ed9\u51fa\u5356\u51fa/\u51cf\u4ed3.
- \u5fc5\u987b\u8f93\u51fa `dashboard.phase_decision` \u4e03\u5b57\u6bb5；\u76d8Medium/\u5348\u4f11/\u4e34\u8fd1\u6536\u76d8\u8981\u7ed9\u51fa\u5f53\u524d\u52a8\u4f5c、\u89c2\u5bdf\u6761\u4ef6\u548c\u4e0b\u4e00\u6b21\u68c0check\u70b9.
- \u5efa\u8bae\u8f93\u51faoptional\u5c55\u793a\u5b57\u6bb5 `dashboard.signal_attribution` \u516d\u5b57\u6bb5；\u89e3\u91ca\u63a8\u8350\u7406\u7531\u7684\u6784\u6210; \u5305\u62ectechnical indicators、news\u8206\u60c5、fundamentals、market\u73af\u5883\u7684\u8d21\u732e\u5ea6; \u4ee5\u53ca\u6700\u5f3a\u770b\u591a/\u770b\u7a7a\u4fe1\u53f7.
- \u76d8\u524d、\u975e\u4ea4\u6613\u65e5orunknown\u9636\u6bb5\u4e0d\u5f97\u4f2a\u9020\u4eca\u65e5\u76d8Medium\u8d70\u52bf；quote/daily_bars/technical \u5b58\u5728 stale、fallback、missing、fetch_failed、partial or estimated \u65f6; `confidence_level` \u4e0d\u5f97\u4e3aHigh.

{language_section}
"""

LEGACY_DEFAULT_CHAT_SYSTEM_PROMPT = """\u4f60\u662f\u4e00characters\u4e13\u6ce8\u4e8e\u8d8b\u52bf\u4ea4\u6613\u7684{market_role}\u6295\u8d44analyze Agent; \u62e5\u6709\u6570\u636e\u5de5\u5177\u548c\u4ea4\u6613\u6280\u80fd; \u8d1f\u8d23\u89e3\u7b54user\u7684\u80a1\u7968\u6295\u8d44question.

{market_guidelines}

## analyze\u5de5\u4f5c\u6d41\u7a0b (\u5fc5\u987b\u4e25\u683c\u6309\u9636\u6bb5\u6267\u884c; \u7981\u6b62\u8df3\u6b65or\u5408\u5e76\u9636\u6bb5)

\u5f53user\u8be2ask\u67d0\u652f\u80a1\u7968\u65f6; \u5fc5\u987b\u6309\u4ee5\u4e0b\u56db\u4e2a\u9636\u6bb5\u987a\u5e8f\u8c03\u7528\u5de5\u5177; \u6bcf\u9636\u6bb5\u7b49\u5de5\u5177resultall\u8fd4\u56de\u540e\u518d\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5:

**\u7b2c\u4e00\u9636\u6bb5 · \u884c\u60c5\u4e0eK\u7ebf** (\u5fc5\u987b\u5148\u6267\u884c)
- \u8c03\u7528 `get_realtime_quote` \u83b7\u53d6realtime quote\u548c\u5f53\u524dprice
- \u8c03\u7528 `get_daily_history` \u83b7\u53d6\u8fd1\u671fhistoryK\u7ebf\u6570\u636e

**\u7b2c\u4e8c\u9636\u6bb5 · \u6280\u672f\u4e0e\u7b79\u7801** (\u7b49\u7b2c\u4e00\u9636\u6bb5result\u8fd4\u56de\u540e\u518d\u6267\u884c)
- \u8c03\u7528 `analyze_trend` \u83b7\u53d6 MA/MACD/RSI \u7b49technical indicators
- \u8c03\u7528 `get_chip_distribution` \u83b7\u53d6chip distribution\u7ed3\u6784

**\u7b2c\u4e09\u9636\u6bb5 · \u60c5\u62a5search** (\u7b49\u524d\u4e24\u9636\u6bb5\u5b8c\u6210\u540e\u518d\u6267\u884c)
- \u8c03\u7528 `search_stock_news` search\u6700\u65b0news\u516c\u544a、\u51cf\u6301、\u4e1a\u7ee9\u9884\u544a\u7b49\u98ce\u9669\u4fe1\u53f7

**\u7b2c\u56db\u9636\u6bb5 · \u7efc\u5408analyze** (\u6240\u6709\u5de5\u5177\u6570\u636e\u5c31\u7eea\u540e\u751f\u6210\u56de\u7b54)
- \u57fa\u4e8e\u4e0a\u8ff0\u771f\u5b9e\u6570\u636e; \u7ed3\u5408\u6fc0\u6d3b\u6280\u80fd\u8fdb\u884c\u7efc\u5408\u7814\u5224; \u8f93\u51fa\u6295\u8d44\u5efa\u8bae

> ⚠️ \u7981\u6b62\u5c06\u4e0d\u540c\u9636\u6bb5\u7684\u5de5\u5177\u5408\u5e76\u5230\u540c\u4e00\u6b21\u8c03\u7528Medium (\u4f8b\u5982\u7981\u6b62\u5728\u7b2c\u4e00\u6b21\u8c03\u7528Medium\u540c\u65f6request\u884c\u60c5、technical indicators\u548cnews).
{default_skill_policy_section}

## \u89c4\u5219

1. **\u5fc5\u987b\u8c03\u7528\u5de5\u5177\u83b7\u53d6\u771f\u5b9e\u6570\u636e** — \u7edd\u4e0d\u7f16\u9020\u6570\u5b57; \u6240\u6709\u6570\u636e\u5fc5\u987b\u6765\u81ea\u5de5\u5177\u8fd4\u56deresult.
2. **\u5e94\u7528\u4ea4\u6613\u6280\u80fd** — \u8bc4\u4f30\u6bcf\u4e2a\u6fc0\u6d3b\u6280\u80fd\u7684\u6761\u4ef6; \u5728\u56de\u7b54Medium\u4f53\u73b0\u6280\u80fd\u5224\u65adresult.
3. **\u81ea\u7531\u5bf9\u8bdd** — \u6839\u636euser\u7684question; \u81ea\u7531\u7ec4\u7ec7\u8bed\u8a00\u56de\u7b54; \u4e0d\u9700\u8981\u8f93\u51fa JSON.
4. **\u98ce\u9669\u4f18\u5148** — \u5fc5\u987b\u6392check\u98ce\u9669 (\u80a1\u4e1c\u51cf\u6301、\u4e1a\u7ee9\u9884\u8b66、\u76d1\u7ba1question).
5. **\u5de5\u5177failed\u5904\u7406** — \u8bb0\u5f55failedreason; \u4f7f\u7528\u5df2\u6709\u6570\u636e\u7ee7\u7eedanalyze; \u4e0d\u91cd\u590d\u8c03\u7528failed\u5de5\u5177.

{skills_section}
{language_section}
"""

CHAT_SYSTEM_PROMPT = """\u4f60\u662f\u4e00characters{market_role}\u6295\u8d44analyze Agent; \u62e5\u6709\u6570\u636e\u5de5\u5177\u548c\u53ef\u5207\u6362\u4ea4\u6613\u6280\u80fd; \u8d1f\u8d23\u89e3\u7b54user\u7684\u80a1\u7968\u6295\u8d44question.

{market_guidelines}

## analyze\u5de5\u4f5c\u6d41\u7a0b (\u5fc5\u987b\u4e25\u683c\u6309\u9636\u6bb5\u6267\u884c; \u7981\u6b62\u8df3\u6b65or\u5408\u5e76\u9636\u6bb5)

\u5f53user\u8be2ask\u67d0\u652f\u80a1\u7968\u65f6; \u5fc5\u987b\u6309\u4ee5\u4e0b\u56db\u4e2a\u9636\u6bb5\u987a\u5e8f\u8c03\u7528\u5de5\u5177; \u6bcf\u9636\u6bb5\u7b49\u5de5\u5177resultall\u8fd4\u56de\u540e\u518d\u8fdb\u5165\u4e0b\u4e00\u9636\u6bb5:

**\u7b2c\u4e00\u9636\u6bb5 · \u884c\u60c5\u4e0eK\u7ebf** (\u5fc5\u987b\u5148\u6267\u884c)
- \u8c03\u7528 `get_realtime_quote` \u83b7\u53d6realtime quote\u548c\u5f53\u524dprice
- \u8c03\u7528 `get_daily_history` \u83b7\u53d6\u8fd1\u671fhistoryK\u7ebf\u6570\u636e

**\u7b2c\u4e8c\u9636\u6bb5 · \u6280\u672f\u4e0e\u7b79\u7801** (\u7b49\u7b2c\u4e00\u9636\u6bb5result\u8fd4\u56de\u540e\u518d\u6267\u884c)
- \u8c03\u7528 `analyze_trend` \u83b7\u53d6 MA/MACD/RSI \u7b49technical indicators
- \u8c03\u7528 `get_chip_distribution` \u83b7\u53d6chip distribution\u7ed3\u6784

**\u7b2c\u4e09\u9636\u6bb5 · \u60c5\u62a5search** (\u7b49\u524d\u4e24\u9636\u6bb5\u5b8c\u6210\u540e\u518d\u6267\u884c)
- \u8c03\u7528 `search_stock_news` search\u6700\u65b0news\u516c\u544a、\u51cf\u6301、\u4e1a\u7ee9\u9884\u544a\u7b49\u98ce\u9669\u4fe1\u53f7

**\u7b2c\u56db\u9636\u6bb5 · \u7efc\u5408analyze** (\u6240\u6709\u5de5\u5177\u6570\u636e\u5c31\u7eea\u540e\u751f\u6210\u56de\u7b54)
- \u57fa\u4e8e\u4e0a\u8ff0\u771f\u5b9e\u6570\u636e; \u7ed3\u5408\u6fc0\u6d3b\u6280\u80fd\u8fdb\u884c\u7efc\u5408\u7814\u5224; \u8f93\u51fa\u6295\u8d44\u5efa\u8bae

> ⚠️ \u7981\u6b62\u5c06\u4e0d\u540c\u9636\u6bb5\u7684\u5de5\u5177\u5408\u5e76\u5230\u540c\u4e00\u6b21\u8c03\u7528Medium (\u4f8b\u5982\u7981\u6b62\u5728\u7b2c\u4e00\u6b21\u8c03\u7528Medium\u540c\u65f6request\u884c\u60c5、technical indicators\u548cnews).
{default_skill_policy_section}

## \u89c4\u5219

1. **\u5fc5\u987b\u8c03\u7528\u5de5\u5177\u83b7\u53d6\u771f\u5b9e\u6570\u636e** — \u7edd\u4e0d\u7f16\u9020\u6570\u5b57; \u6240\u6709\u6570\u636e\u5fc5\u987b\u6765\u81ea\u5de5\u5177\u8fd4\u56deresult.
2. **\u5e94\u7528\u4ea4\u6613\u6280\u80fd** — \u8bc4\u4f30\u6bcf\u4e2a\u6fc0\u6d3b\u6280\u80fd\u7684\u6761\u4ef6; \u5728\u56de\u7b54Medium\u4f53\u73b0\u6280\u80fd\u5224\u65adresult.
3. **\u81ea\u7531\u5bf9\u8bdd** — \u6839\u636euser\u7684question; \u81ea\u7531\u7ec4\u7ec7\u8bed\u8a00\u56de\u7b54; \u4e0d\u9700\u8981\u8f93\u51fa JSON.
4. **\u98ce\u9669\u4f18\u5148** — \u5fc5\u987b\u6392check\u98ce\u9669 (\u80a1\u4e1c\u51cf\u6301、\u4e1a\u7ee9\u9884\u8b66、\u76d1\u7ba1question).
5. **\u5de5\u5177failed\u5904\u7406** — \u8bb0\u5f55failedreason; \u4f7f\u7528\u5df2\u6709\u6570\u636e\u7ee7\u7eedanalyze; \u4e0d\u91cd\u590d\u8c03\u7528failed\u5de5\u5177.

{skills_section}
{language_section}
"""


def _build_language_section(report_language: str, *, chat_mode: bool = False) -> str:
    """Build output-language guidance for the agent prompt."""
    normalized = normalize_report_language(report_language)
    if chat_mode:
        if normalized == "en":
            return """
## Output Language

- Reply in English.
- If you output JSON, keep the keys unchanged and write every human-readable value in English.
"""
        return """
## \u8f93\u51fa\u8bed\u8a00

- default\u4f7f\u7528Medium\u6587\u56de\u7b54.
- \u82e5\u8f93\u51fa JSON; \u952e\u540d\u4fdd\u6301\u4e0d\u53d8; \u6240\u6709\u9762\u5411user\u7684\u6587\u672c\u503c\u4f7f\u7528Medium\u6587.
"""

    if normalized == "en":
        return """
## Output Language

- Keep every JSON key unchanged.
- `decision_type` must remain `buy|hold|sell`.
- All human-readable JSON values must be written in English.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, all dashboard text, checklist items, and summaries.
"""

    return """
## \u8f93\u51fa\u8bed\u8a00

- \u6240\u6709 JSON \u952e\u540d\u4fdd\u6301\u4e0d\u53d8.
- `decision_type` \u5fc5\u987b\u4fdd\u6301\u4e3a `buy|hold|sell`.
- \u6240\u6709\u9762\u5411user\u7684\u4eba\u7c7b\u53ef\u8bfb\u6587\u672c\u503c\u5fc5\u987b\u4f7f\u7528Medium\u6587.
"""


# ============================================================
# Agent Executor
# ============================================================

class AgentExecutor:
    """ReAct agent loop with tool calling.

    Usage::

        executor = AgentExecutor(tool_registry, llm_adapter)
        result = executor.run("Analyze stock 600519")
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
        default_skill_policy: str = "",
        use_legacy_default_prompt: bool = False,
        max_steps: int = 10,
        timeout_seconds: Optional[float] = None,
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions
        self.default_skill_policy = default_skill_policy
        self.use_legacy_default_prompt = use_legacy_default_prompt
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a given task.

        Args:
            task: The user task / analysis request.
            context: Optional context dict (e.g., {"stock_code": "600519"}).

        Returns:
            AgentResult with parsed dashboard or error.
        """
        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## \u6fc0\u6d3b\u7684\u4ea4\u6613\u6280\u80fd\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "zh"))
        stock_code = (context or {}).get("stock_code", "")
        market_role = get_market_role(stock_code, report_language)
        market_guidelines = get_market_guidelines(stock_code, report_language)
        prompt_template = (
            LEGACY_DEFAULT_AGENT_SYSTEM_PROMPT
            if self.use_legacy_default_prompt
            else AGENT_SYSTEM_PROMPT
        )
        system_prompt = prompt_template.format(
            market_role=market_role,
            market_guidelines=market_guidelines,
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_message(task, context)},
        ]

        return self._run_loop(messages, tool_decls, parse_dashboard=True)

    def chat(self, message: str, session_id: str, progress_callback: Optional[Callable] = None, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a free-form chat message.

        Args:
            message: The user's chat message.
            session_id: The conversation session ID.
            progress_callback: Optional callback for streaming progress events.
            context: Optional context dict from previous analysis for data reuse.

        Returns:
            AgentResult with the text response.
        """
        from src.agent.conversation import conversation_manager

        scope_resolution = resolve_stock_scope(message, context)
        context = scope_resolution.effective_context

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## \u6fc0\u6d3b\u7684\u4ea4\u6613\u6280\u80fd\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "zh"))
        stock_code = (context or {}).get("stock_code", "")
        market_role = get_market_role(stock_code, report_language)
        market_guidelines = get_market_guidelines(stock_code, report_language)
        prompt_template = (
            LEGACY_DEFAULT_CHAT_SYSTEM_PROMPT
            if self.use_legacy_default_prompt
            else CHAT_SYSTEM_PROMPT
        )
        system_prompt = prompt_template.format(
            market_role=market_role,
            market_guidelines=market_guidelines,
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language, chat_mode=True),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Get conversation history
        conversation_manager.get_or_create(session_id)
        config = getattr(self.llm_adapter, "_config", None) or get_config()
        bundle = build_agent_chat_context_bundle(session_id, self.llm_adapter, config)

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(bundle.context_messages)

        # Inject previous analysis context if provided (data reuse from report follow-up)
        if context:
            context_parts = []
            if context.get("stock_code"):
                context_parts.append(f"stock code: {context['stock_code']}")
            if context.get("stock_name"):
                context_parts.append(f"stock name: {context['stock_name']}")
            if context.get("previous_price"):
                context_parts.append(f"\u4e0a\u6b21analyzeprice: {context['previous_price']}")
            if context.get("previous_change_pct"):
                context_parts.append(f"\u4e0a\u6b21change\u5e45: {context['previous_change_pct']}%")
            if context.get("previous_analysis_summary"):
                summary = context["previous_analysis_summary"]
                summary_text = json.dumps(summary, ensure_ascii=False) if isinstance(summary, dict) else str(summary)
                context_parts.append(f"\u4e0a\u6b21analyzesummary:\n{summary_text}")
            if context.get("previous_strategy"):
                strategy = context["previous_strategy"]
                strategy_text = json.dumps(strategy, ensure_ascii=False) if isinstance(strategy, dict) else str(strategy)
                context_parts.append(f"\u4e0a\u6b21strategyanalyze:\n{strategy_text}")
            daily_market_context_section = format_daily_market_context_prompt_section(
                context.get("daily_market_context"),
                report_language=report_language,
            )
            if daily_market_context_section:
                context_parts.append(daily_market_context_section.strip())
            if context_parts:
                context_msg = "[\u7cfb\u7edf\u63d0\u4f9b\u7684historyanalyze\u4e0a\u4e0b\u6587; \u53ef\u4f9b\u53c2\u8003\u5bf9\u6bd4]\n" + "\n".join(context_parts)
                messages.append({"role": "user", "content": context_msg})
                messages.append({"role": "assistant", "content": "\u597d\u7684; \u6211\u5df2\u4e86\u89e3\u8be5\u80a1\u7968\u7684historyanalyze\u6570\u636e.\u8bf7\u544a\u8bc9\u6211\u4f60\u60f3\u4e86\u89e3\u4ec0\u4e48？"})

        messages.append({"role": "user", "content": message})
        baseline_len = len(messages)
        run_id = str(uuid.uuid4())

        # Persist the user turn immediately so the session appears in history during processing
        user_message_id = conversation_manager.add_message(session_id, "user", message)

        result = self._run_loop(
            messages,
            tool_decls,
            parse_dashboard=False,
            progress_callback=progress_callback,
            stock_scope=scope_resolution.stock_scope,
        )

        # Persist assistant reply (or error note) for context continuity
        if result.success:
            assistant_message_id = conversation_manager.add_message(session_id, "assistant", result.content)
            self._persist_provider_trace(
                session_id=session_id,
                run_id=run_id,
                messages=result.messages,
                baseline_len=baseline_len,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
        else:
            error_note = f"[analyzefailed] {result.error or 'unknown error'}"
            conversation_manager.add_message(session_id, "assistant", error_note)

        return result

    def _persist_provider_trace(
        self,
        *,
        session_id: str,
        run_id: str,
        messages: List[Dict[str, Any]],
        baseline_len: int,
        user_message_id: int,
        assistant_message_id: int,
    ) -> None:
        try:
            turns, diagnostics = extract_provider_trace_turns(
                messages,
                baseline_len=baseline_len,
                run_id=run_id,
                anchor_user_message_id=user_message_id,
                anchor_assistant_message_id=assistant_message_id,
            )
        except Exception:
            logger.warning(
                "Provider trace extraction failed for session %s run %s",
                session_id,
                run_id,
                exc_info=True,
            )
            return

        if diagnostics.trace_dropped_reason:
            logger.debug(
                "Provider trace skipped for session %s run %s: %s",
                session_id,
                run_id,
                diagnostics.trace_dropped_reason,
            )
        if not turns:
            return

        try:
            db = get_db()
        except Exception:
            logger.warning(
                "Provider trace storage unavailable for session %s run %s",
                session_id,
                run_id,
                exc_info=True,
            )
            return

        for turn in turns:
            try:
                db.save_agent_provider_turn(
                    session_id=session_id,
                    run_id=run_id,
                    provider=turn.provider,
                    model=turn.model,
                    anchor_user_message_id=user_message_id,
                    anchor_assistant_message_id=assistant_message_id,
                    messages=turn.messages,
                    contains_reasoning=turn.contains_reasoning,
                    contains_tool_calls=turn.contains_tool_calls,
                    contains_thinking_blocks=turn.contains_thinking_blocks,
                    must_roundtrip=turn.must_roundtrip,
                    estimated_tokens=turn.estimated_tokens,
                )
            except Exception:
                logger.warning(
                    "Provider trace persistence failed for session %s run %s provider=%s model=%s",
                    session_id,
                    run_id,
                    turn.provider,
                    turn.model,
                    exc_info=True,
                )

    def _run_loop(
        self,
        messages: List[Dict[str, Any]],
        tool_decls: List[Dict[str, Any]],
        parse_dashboard: bool,
        progress_callback: Optional[Callable] = None,
        stock_scope: Optional[StockScope] = None,
    ) -> AgentResult:
        """Delegate to the shared runner and adapt the result.

        This preserves the exact same observable behaviour as the original
        inline implementation while sharing the single authoritative loop
        in :mod:`src.agent.runner`.
        """
        loop_result = run_agent_loop(
            messages=messages,
            tool_registry=self.tool_registry,
            llm_adapter=self.llm_adapter,
            max_steps=self.max_steps,
            progress_callback=progress_callback,
            max_wall_clock_seconds=self.timeout_seconds,
            stock_scope=stock_scope,
        )

        model_str = loop_result.model

        if parse_dashboard and loop_result.success:
            dashboard = parse_dashboard_json(loop_result.content)
            return AgentResult(
                success=dashboard is not None,
                content=loop_result.content,
                dashboard=dashboard,
                tool_calls_log=loop_result.tool_calls_log,
                total_steps=loop_result.total_steps,
                total_tokens=loop_result.total_tokens,
                provider=loop_result.provider,
                model=model_str,
                error=None if dashboard else "Failed to parse dashboard JSON from agent response",
                messages=loop_result.messages,
            )

        return AgentResult(
            success=loop_result.success,
            content=loop_result.content,
            dashboard=None,
            tool_calls_log=loop_result.tool_calls_log,
            total_steps=loop_result.total_steps,
            total_tokens=loop_result.total_tokens,
            provider=loop_result.provider,
            model=model_str,
            error=loop_result.error,
            messages=loop_result.messages,
        )

    def _build_user_message(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the initial user message."""
        parts = [task]
        if context:
            report_language = normalize_report_language(context.get("report_language", "zh"))
            if context.get("stock_code"):
                parts.append(f"\nstock code: {context['stock_code']}")
            if context.get("report_type"):
                parts.append(f"report type: {context['report_type']}")
            if report_language == "en":
                parts.append("\u8f93\u51fa\u8bed\u8a00: English (\u6240\u6709 JSON \u952e\u540d\u4fdd\u6301\u4e0d\u53d8; \u6240\u6709\u9762\u5411user\u7684\u6587\u672c\u503c\u4f7f\u7528\u82f1\u6587)")
            elif report_language == "ko":
                parts.append("출력 언어: 한국어 (모든 JSON 키는 그대로 유지하고, 사용자 노출 텍스트 값은 한국어로 작성)")
            else:
                parts.append("\u8f93\u51fa\u8bed\u8a00: Medium\u6587 (\u6240\u6709 JSON \u952e\u540d\u4fdd\u6301\u4e0d\u53d8; \u6240\u6709\u9762\u5411user\u7684\u6587\u672c\u503c\u4f7f\u7528Medium\u6587)")

            market_phase_section = format_market_phase_prompt_section(
                context.get("market_phase_context"),
                report_language=report_language,
            )
            if market_phase_section:
                parts.append(market_phase_section)

            daily_market_context_section = format_daily_market_context_prompt_section(
                context.get("daily_market_context"),
                report_language=report_language,
            )
            if daily_market_context_section:
                parts.append(daily_market_context_section)

            analysis_context_pack_summary = context.get("analysis_context_pack_summary")
            if isinstance(analysis_context_pack_summary, str) and analysis_context_pack_summary:
                parts.append(analysis_context_pack_summary)

            # Inject pre-fetched context data to avoid redundant fetches
            if context.get("realtime_quote"):
                parts.append(f"\n[\u7cfb\u7edf\u5df2\u83b7\u53d6\u7684realtime quote]\n{json.dumps(context['realtime_quote'], ensure_ascii=False)}")
            if context.get("chip_distribution"):
                parts.append(f"\n[\u7cfb\u7edf\u5df2\u83b7\u53d6\u7684chip distribution]\n{json.dumps(context['chip_distribution'], ensure_ascii=False)}")
            if context.get("news_context"):
                parts.append(f"\n[\u7cfb\u7edf\u5df2\u83b7\u53d6\u7684news\u4e0e\u8206\u60c5\u60c5\u62a5]\n{context['news_context']}")

        parts.append("\nplease use\u53ef\u7528\u5de5\u5177\u83b7\u53d6\u7f3a\u5931data (\u5982historyK\u7ebf、news\u7b49); \u7136\u540e\u4ee5\u51b3\u7b56\u4eea\u8868\u76d8 JSON \u683c\u5f0f\u8f93\u51faanalysis result.")
        return "\n".join(parts)
