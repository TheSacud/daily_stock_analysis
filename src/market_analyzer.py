# -*- coding: utf-8 -*-
"""
===================================
market reviewanalyze\u6a21chunks
===================================

\u804c\u8d23:
1. \u83b7\u53d6\u5927\u76d8index\u6570\u636e (\u4e0a\u8bc1、\u6df1\u8bc1、\u521b\u4e1a\u677f)
2. searchmarketnews\u5f62\u6210\u590d\u76d8\u60c5\u62a5
3. \u4f7f\u7528\u5927\u6a21\u578b\u751f\u6210\u6bcf\u65e5market reviewreport
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from inspect import getattr_static
from typing import Optional, Dict, Any, List

import pandas as pd

from src.config import get_config
from src.report_language import normalize_report_language
from src.search_service import SearchService
from src.core.market_profile import get_profile, MarketProfile
from src.core.market_strategy import get_market_strategy_blueprint
from src.llm.backend_registry import (
    resolve_generation_backend_id,
    resolve_generation_fallback_backend_id,
)
from src.llm.generation_backend import GenerationError
from src.schemas.market_light import MARKET_LIGHT_REGIONS, MarketLightSnapshot
from src.services.run_diagnostics import record_llm_run, record_llm_run_started
from src.services.intelligence_service import IntelligenceService
from data_provider.base import DataFetcherManager

logger = logging.getLogger(__name__)


_ENGLISH_SECTION_PATTERNS = {
    "market_summary": r"###\s*(?:1\.\s*)?Market Summary",
    "index_commentary": r"###\s*(?:2\.\s*)?(?:Index Commentary|Major Indices)",
    "sector_highlights": r"###\s*(?:4\.\s*)?(?:Sector Highlights|Sector/Theme Highlights)",
}

_CHINESE_SECTION_PATTERNS = {
    "market_summary": r"###\s*\u4e00、(?:\u76d8\u9762\u603b\u89c8|market\u603b\u7ed3)",
    "index_commentary": r"###\s*\u4e8c、(?:index\u7ed3\u6784|index\u70b9\u8bc4|\u4e3b\u8981index)",
    "sector_highlights": r"###\s*\u4e09、(?:sector\u4e3b\u7ebf|\u70ed\u70b9\u89e3\u8bfb|sector\u8868\u73b0)",
    "funds_sentiment": r"###\s*\u56db、(?:\u8d44\u91d1\u4e0e\u60c5\u7eea|\u8d44\u91d1\u52a8\u5411)",
    "news_catalysts": r"###\s*\u4e94、(?:\u6d88\u606f\u50ac\u5316|\u540e\u5e02\u5c55\u671b)",
}


@dataclass
class MarketIndex:
    """\u5927\u76d8index\u6570\u636e"""
    code: str                    # indexcode
    name: str                    # indexname
    current: float = 0.0         # \u5f53\u524d\u70b9characters
    change: float = 0.0          # change\u70b9\u6570
    change_pct: float = 0.0      # change\u5e45(%)
    open: float = 0.0            # \u5f00\u76d8\u70b9characters
    high: float = 0.0            # \u6700High\u70b9characters
    low: float = 0.0             # \u6700Low\u70b9characters
    prev_close: float = 0.0      # \u6628\u6536\u70b9characters
    volume: float = 0.0          # volume (\u624b)
    amount: float = 0.0          # amount (\u5143)
    amplitude: float = 0.0       # \u632f\u5e45(%)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'current': self.current,
            'change': self.change,
            'change_pct': self.change_pct,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'amount': self.amount,
            'amplitude': self.amplitude,
        }


@dataclass
class MarketOverview:
    """market\u6982\u89c8\u6570\u636e"""
    date: str                           # date
    indices: List[MarketIndex] = field(default_factory=list)  # \u4e3b\u8981index
    up_count: int = 0                   # \u4e0a\u6da8\u5bb6\u6570
    down_count: int = 0                 # \u4e0b\u8dcc\u5bb6\u6570
    flat_count: int = 0                 # \u5e73\u76d8\u5bb6\u6570
    limit_up_count: int = 0             # \u6da8\u505c\u5bb6\u6570
    limit_down_count: int = 0           # \u8dcc\u505c\u5bb6\u6570
    total_amount: float = 0.0           # \u4e24\u5e02amount (\u4ebf\u5143)
    # north_flow: float = 0.0           # \u5317\u5411\u8d44\u91d1\u51c0\u6d41\u5165 (\u4ebf\u5143)- \u5df2\u5e9f\u5f03; \u63a5\u53e3unavailable

    # sector\u6da8\u5e45\u699c
    top_sectors: List[Dict] = field(default_factory=list)     # \u6da8\u5e45\u524d5sector
    bottom_sectors: List[Dict] = field(default_factory=list)  # \u8dcc\u5e45\u524d5sector
    top_concepts: List[Dict] = field(default_factory=list)    # \u6da8\u5e45\u524d5concept
    bottom_concepts: List[Dict] = field(default_factory=list) # \u8dcc\u5e45\u524d5concept


@dataclass
class MarketLightReviewResult:
    """Internal market-review parts built from one overview fetch."""

    overview: MarketOverview
    report: str
    market_light_snapshot: Optional[Dict[str, Any]]
    structured_payload: Dict[str, Any] = field(default_factory=dict)


class MarketAnalyzer:
    """
    market reviewanalyze\u5668

    \u529f\u80fd:
    1. \u83b7\u53d6\u5927\u76d8indexrealtime quote
    2. \u83b7\u53d6marketchange\u7edf\u8ba1
    3. \u83b7\u53d6sectorchange\u699c
    4. searchmarketnews
    5. \u751f\u6210market reviewreport
    """

    def __init__(
        self,
        search_service: Optional[SearchService] = None,
        analyzer=None,
        region: str = "cn",
        config: Optional[Any] = None,
    ):
        """
        \u521d\u59cb\u5316\u5927\u76d8analyze\u5668

        Args:
            search_service: search\u670d\u52a1\u5b9e\u4f8b
            analyzer: AIanalyze\u5668\u5b9e\u4f8b (\u7528\u4e8e\u8c03\u7528LLM)
            region: market\u533a\u57df cn=A-share hk=HK stock us=US stock jp=\u65e5\u672c kr=\u97e9\u56fd
            config: this run\u590d\u76d8\u4f7f\u7528\u7684config；\u672a\u4f20\u65f6\u8bfb\u53d6\u5168\u5c40config
        """
        self.config = config or get_config()
        self.search_service = search_service
        self.analyzer = analyzer
        self.data_manager = DataFetcherManager()
        self.region = region if region in ("cn", "us", "hk", "jp", "kr") else "cn"
        self.profile: MarketProfile = get_profile(self.region)
        self.strategy = get_market_strategy_blueprint(self.region)

    def _log_context(self) -> str:
        return f"component=market_review region={self.region}"

    def _get_output_language(self) -> str:
        """Return the truthful report language (zh/en/ko) for payload and directives."""
        return normalize_report_language(
            getattr(getattr(self, "config", None), "report_language", "en")
        )

    def _get_review_language(self) -> str:
        # Structural/template language. Korean reuses the English scaffolding;
        # the Korean output directive is applied in the prompt builder.
        language = self._get_output_language()
        return "en" if language == "ko" else language

    def _get_template_review_language(self) -> str:
        return self._get_review_language()

    def _get_market_scope_name(self, review_language: str | None = None) -> str:
        review_language = review_language or self._get_review_language()
        if self.region == "us":
            return "US market" if review_language == "en" else "US stockmarket"
        if self.region == "hk":
            return "Hong Kong market" if review_language == "en" else "HK stockmarket"
        if self.region == "jp":
            return "Japan market" if review_language == "en" else "\u65e5\u672cmarket"
        if self.region == "kr":
            return "Korea market" if review_language == "en" else "\u97e9\u56fdmarket"
        if review_language == "en":
            return "equity market"
        return "A-sharemarket"

    def _get_turnover_unit_label(self) -> str:
        """Return the turnover unit label for the current market/language."""
        if self.region == "us":
            return "USD bn" if self._get_review_language() == "en" else "\u5341\u4ebf\u7f8e\u5143"
        if self.region == "hk":
            return "HKD bn" if self._get_review_language() == "en" else "\u5341\u4ebf\u6e2f\u5143"
        if self.region == "jp":
            return "JPY bn" if self._get_review_language() == "en" else "\u5341\u4ebf\u65e5\u5143"
        if self.region == "kr":
            return "KRW bn" if self._get_review_language() == "en" else "\u5341\u4ebf\u97e9\u5143"
        return "100m units" if self._get_review_language() == "en" else "\u4ebf"

    def _format_turnover_value(self, amount_raw: float) -> str:
        """Format raw turnover according to market-specific units."""
        if amount_raw == 0.0:
            return "N/A"
        if self.region in ("us", "hk", "jp", "kr"):
            return f"{amount_raw / 1e9:.2f}"
        if amount_raw > 1e6:
            return f"{amount_raw / 1e8:.0f}"
        return f"{amount_raw:.0f}"

    def _get_index_change_arrow(self, change_pct: float) -> str:
        if change_pct == 0:
            return "⚪"
        color_scheme = getattr(getattr(self, "config", None), "market_review_color_scheme", "green_up")
        if color_scheme == "red_up":
            return "🔴" if change_pct > 0 else "🟢"
        return "🟢" if change_pct > 0 else "🔴"

    def _get_review_title(self, date: str) -> str:
        if self._get_review_language() == "en":
            market_names = {
                "us": "US Market Recap",
                "hk": "HK Market Recap",
                "jp": "Japan Market Recap",
                "kr": "Korea Market Recap",
            }
            market_name = market_names.get(self.region, "Market Recap")
            return f"## {date} {market_name}"
        return f"## {date} market review"

    def _get_index_hint(self) -> str:
        if self._get_review_language() == "en":
            if self.region == "us":
                return "Analyze the key moves in the S&P 500, Nasdaq, Dow, and other major indices."
            if self.region == "hk":
                return "Analyze the key moves in the HSI, Hang Seng Tech, HSCEI, and other major indices."
            if self.region == "jp":
                return "Analyze the key moves in the Nikkei 225, TOPIX, and other major Japanese indices."
            if self.region == "kr":
                return "Analyze the key moves in the KOSPI, KOSDAQ, and other major Korean indices."
            return "Analyze the price action in the SSE, SZSE, ChiNext, and other major indices."
        return self.profile.prompt_index_hint

    def _get_strategy_prompt_block(self) -> str:
        if self.region == "hk" and self._get_review_language() == "en":
            return """## Strategy Blueprint: Hong Kong Market Regime Strategy
Focus on HSI trend, southbound flow dynamics, and sector rotation to define next-session risk posture.

### Strategy Principles
- Read market regime from HSI, HSTECH, and HSCEI alignment first.
- Track southbound capital flow as a key sentiment driver.
- Translate recap into actionable risk-on/risk-off stance with clear invalidation points.

### Analysis Dimensions
- Trend Regime: Classify the market as momentum, range, or risk-off.
  - Are HSI/HSTECH/HSCEI directionally aligned
  - Did volume confirm the move
  - Are key index levels reclaimed or lost
- Capital Flows: Map southbound flow and macro narrative into equity risk appetite.
  - Southbound net flow direction and magnitude
  - USD/HKD and China policy implications
  - Breadth and leadership concentration
- Sector Themes: Identify persistent leaders and vulnerable laggards.
  - Tech/internet platform trend persistence
  - Financials/property sensitivity to policy shifts
  - Defensive vs growth factor rotation

### Action Framework
- Risk-on: broad index breakout with expanding southbound participation.
- Neutral: mixed index signals; focus on selective relative strength.
- Risk-off: failed breakouts and rising volatility; prioritize capital preservation."""
        if self.region == "jp" and self._get_review_language() == "en":
            return """## Strategy Blueprint: Japan Market Regime Strategy
Focus on Nikkei 225, TOPIX, currency dynamics, and global risk appetite to define the next-session trading plan.

### Strategy Principles
- Read Nikkei 225 and TOPIX alignment first, then assess yen moves, semiconductor/export chains, and financials.
- Translate index conclusions into position sizing, trading pace, and risk-control actions.
- Base judgments only on available index data, news, and price action without inventing breadth or sector statistics.

### Analysis Dimensions
- Trend Regime: Classify Japan equities as advancing, range-bound, or defensive.
  - Are Nikkei 225 and TOPIX directionally aligned
  - Have key index ranges been reclaimed or lost
  - Are large-cap weights and growth chains moving together
- Macro & FX: Map yen, rates, and global risk appetite into equity impact.
  - Yen direction and implications for exporters
  - Bank of Japan and US Treasury yield narratives
  - Overseas technology and semiconductor read-through
- Theme Signals: Identify durable leadership and crowded areas to avoid.
  - Semiconductor, automation, and auto-chain persistence
  - Rotation between financials and domestic-demand stocks
  - Whether news catalysts confirm price action

### Action Framework
- Risk-on: major indices rise together with improving external risk appetite and stronger leadership.
- Neutral: index divergence or FX disruption; avoid chasing and wait for confirmation.
- Risk-off: major indices weaken or external risk rises; prioritize position control."""
        if self.region == "kr" and self._get_review_language() == "en":
            return """## Strategy Blueprint: Korea Market Regime Strategy
Focus on KOSPI, KOSDAQ, semiconductor heavyweights, and global technology risk appetite to define the next-session trading plan.

### Strategy Principles
- Read KOSPI and KOSDAQ alignment first, then assess heavyweight signals from Samsung Electronics, SK Hynix, and related technology leaders.
- Separate broad index beta, semiconductor cycle exposure, and growth-stock risk appetite.
- Base judgments only on available index data, news, and price action without inventing breadth or sector statistics.

### Analysis Dimensions
- Trend Regime: Classify Korea equities as advancing, range-bound, or defensive.
  - Are KOSPI and KOSDAQ directionally aligned
  - Are heavyweight technology names supporting the indices
  - Have key support or resistance levels been reclaimed or lost
- Technology Cycle: Map semiconductor, AI hardware, and global technology moves into Korea equity risk.
  - Memory and semiconductor-chain catalysts
  - US technology-market read-through
  - Foreign investor risk appetite signals
- Theme Signals: Identify durable leadership and crowded areas to avoid.
  - Rotation across batteries, autos, and internet platforms
  - KOSDAQ growth-stock risk appetite
  - Whether news catalysts confirm price action

### Action Framework
- Risk-on: KOSPI and KOSDAQ rise together with confirmed technology leadership and improving external risk appetite.
- Neutral: index or heavyweight divergence; keep sizing controlled and wait for confirmation.
- Risk-off: technology heavyweights weaken or external risk rises; prioritize drawdown control."""
        if self.region == "us" and self._get_review_language() == "zh":
            return """## US stockmarket\u4e09\u6bb5\u5f0f\u590d\u76d8strategy
\u805a\u7126index\u8d8b\u52bf、\u5b8f\u89c2\u53d9\u4e8b\u4e0esector\u8f6e\u52a8; \u7ed9\u51fa\u6b21\u65e5\u98ce\u63a7\u4e0e\u4ed3characters\u6846\u67b6.

### strategy\u539f\u5219
- \u5148\u770b\u6807\u666e500、\u7eb3\u65af\u8fbe\u514b、\u9053\u743c\u65af\u662f\u5426\u540c\u5411; \u786e\u8ba4\u4e3b\u7ebf\u662f\u5426\u4e00\u81f4.
- \u7ed3\u5408\u5b8f\u89c2\u4e0e\u6d41\u52a8\u6307\u6807; \u8bc6\u522b\u98ce\u9669Slightly \u597d\u662f\u4fee\u590d\u8fd8\u662f\u8f6c\u5f31.
- \u5c06\u590d\u76d8\u8f93\u51fa\u6620\u5c04\u4e3a“\u8fdb\u653b/\u5747\u8861/\u9632\u5b88”\u52a8\u4f5c\u5efa\u8bae; \u5e76\u7ed9\u51fa\u660e\u786e\u89e6\u53d1\u5931\u6548\u6761\u4ef6.

### analyze\u7ef4\u5ea6
- \u8d8b\u52bf\u7ed3\u6784: \u660e\u786emarket\u5904\u4e8e\u4e0a\u51b2、\u9707\u8361\u8fd8\u662f\u9632\u5b88\u8f6c\u5411; \u5224\u65ad\u662f\u5426\u5b58\u5728\u5173\u952e\u652f\u6491characters\u80cc\u79bb.
- \u8d44\u91d1\u4e0e\u60c5\u7eea: \u533a\u5206\u5b8f\u89c2\u653f\u7b56、\u8d27\u5e01\u9762\u4e0e\u6ce2\u52a8\u7387\u5bf9\u6743\u76ca\u98ce\u9669\u7684\u5f71\u54cd.
- \u4e3b\u9898\u7ebf\u7d22: \u8bc6\u522b\u6301\u7eed\u6700\u5f3a\u7684\u4e3b\u9898\u4e0esector\u8f6e\u52a8\u662f\u5426\u5f62\u6210\u53ef\u4ea4\u6613\u4e3b\u7ebf.

### \u884c\u52a8\u6846\u67b6
- \u8fdb\u653b: \u4e3bsector\u8054\u52a8\u4e0a\u884c\u4e14\u91cf\u80fd/\u98ce\u9669characters\u540c\u6b65\u6539\u5584.
- \u5747\u8861: index\u5206\u5316or\u91cf\u80fd\u672a\u660e\u663e\u653e\u5927; \u4ed3characters\u4fdd\u5b88\u6267\u884c.
- \u9632\u5b88: \u7a81\u7834\u5931\u5b88\u4e14\u6ce2\u52a8\u7387\u62ac\u5347\u65f6; \u4f18\u5148\u51cf\u7801\u5e76\u4fdd\u7559\u53cd\u5f39\u53ef\u4ea4\u6613."""
        if not (self.region == "cn" and self._get_review_language() == "en"):
            return self.strategy.to_prompt_block()
        return """## Strategy Blueprint: A-share Three-Phase Recap Strategy
Focus on index trend, liquidity, and sector rotation to shape the next-session trading plan.

### Strategy Principles
- Read index direction first, then confirm liquidity structure, and finally test sector persistence.
- Every conclusion must map to position sizing, trading pace, and risk-control actions.
- Base judgments on today's data and the latest 3-day news flow without inventing unverified information.

### Analysis Dimensions
- Trend Structure: Determine whether the market is in an uptrend, range, or defensive phase.
  - Are the SSE, SZSE, and ChiNext moving in the same direction
  - Is the market advancing on expanding volume or slipping on contracting volume
  - Have key support or resistance levels been reclaimed or broken
- Liquidity & Sentiment: Identify near-term risk appetite and market temperature.
  - Advance/decline breadth and limit-up/limit-down structure
  - Whether turnover is expanding or fading
  - Whether high-beta leaders are showing divergence
- Leading Themes: Distill tradable leadership and areas to avoid.
  - Whether leading sectors have clear event catalysts
  - Whether sector leaders are pulling the group higher
  - Whether weakness is broadening across lagging sectors

### Action Framework
- Offensive: indices rise in sync, turnover expands, and core themes strengthen.
- Balanced: index divergence or low-volume consolidation; keep sizing controlled and wait for confirmation.
- Defensive: indices weaken and laggards broaden; prioritize risk control and de-risking."""

    def _get_strategy_markdown_block(self, review_language: str | None = None) -> str:
        review_language = review_language or self._get_review_language()
        if self.region == "hk" and review_language == "en":
            return """### 6. Strategy Framework
- **Trend Regime**: Classify the market as momentum, range, or risk-off based on HSI/HSTECH/HSCEI alignment.
- **Capital Flows**: Track southbound flow direction and macro narrative for risk appetite signals.
- **Sector Themes**: Focus on tech/internet platform persistence and financials/property policy sensitivity.
"""
        if self.region == "jp" and review_language == "en":
            return """### 6. Strategy Framework
- **Trend Regime**: Classify Japan equities as advancing, range-bound, or defensive based on Nikkei 225/TOPIX alignment.
- **Macro & FX**: Track yen, rates, and global risk appetite for exporter and financial-sector implications.
- **Theme Signals**: Focus on semiconductor, automation, auto-chain, financial, and domestic-demand rotation.
"""
        if self.region == "kr" and review_language == "en":
            return """### 6. Strategy Framework
- **Trend Regime**: Classify Korea equities as advancing, range-bound, or defensive based on KOSPI/KOSDAQ alignment.
- **Technology Cycle**: Track semiconductor, AI hardware, and global technology read-through for market risk appetite.
- **Theme Signals**: Focus on battery, auto, internet-platform, and KOSDAQ growth-stock rotation.
"""
        if self.region == "us" and review_language == "zh":
            return """### \u516d、strategy\u6846\u67b6
- **\u8d8b\u52bf\u7ed3\u6784**: \u5224\u65admarket\u5728\u8fdb\u653b、\u9707\u8361\u4e0e\u9632\u5b88Medium\u7684status\u662f\u5426\u4e00\u81f4.
- **\u8d44\u91d1\u4e0e\u60c5\u7eea**: \u7ed3\u5408\u6ce2\u52a8\u7387、\u5bbd\u5ea6\u548c\u4e3b\u9898\u8f6e\u52a8\u8bc4\u4f30\u98ce\u9669Slightly \u597d.
- **\u4e3b\u9898\u4e3b\u7ebf**: \u8bc6\u522b\u53ef\u5ef6\u7eed\u548c\u53ef\u653e\u5927\u7684industry\u4e3b\u7ebf\u4e0e\u9632\u5b88\u7ebf\u7d22.
"""
        if not (self.region == "cn" and review_language == "en"):
            return self.strategy.to_markdown_block()
        return """### 6. Strategy Framework
- **Trend Structure**: Determine whether the market is in an uptrend, range, or defensive phase.
- **Liquidity & Sentiment**: Track breadth, turnover expansion, and whether leaders are diverging.
- **Leading Themes**: Focus on sectors with catalysts and sustained leadership while avoiding broadening weakness.
"""

    def _get_market_mood_text(self, mood_key: str, review_language: str | None = None) -> str:
        review_language = review_language or self._get_review_language()
        if review_language == "en":
            mapping = {
                "strong_up": "strong gains",
                "mild_up": "moderate gains",
                "mild_down": "mild losses",
                "strong_down": "clear weakness",
                "range": "range-bound trading",
            }
        else:
            mapping = {
                "strong_up": "\u5f3a\u52bf\u4e0a\u6da8",
                "mild_up": "\u5c0f\u5e45\u4e0a\u6da8",
                "mild_down": "\u5c0f\u5e45\u4e0b\u8dcc",
                "strong_down": "\u660e\u663e\u4e0b\u8dcc",
                "range": "\u9707\u8361\u6574\u7406",
            }
        return mapping[mood_key]

    def get_market_overview(self) -> MarketOverview:
        """
        \u83b7\u53d6market\u6982\u89c8\u6570\u636e

        Returns:
            MarketOverview: market\u6982\u89c8\u6570\u636e\u5bf9\u8c61
        """
        today = datetime.now().strftime('%Y-%m-%d')
        overview = MarketOverview(date=today)

        # 1. \u83b7\u53d6\u4e3b\u8981index\u884c\u60c5 (\u6309 region \u5207\u6362 A \u80a1/US stock)
        overview.indices = self._get_main_indices()

        # 2. \u83b7\u53d6change\u7edf\u8ba1 (A \u80a1\u6709; US stock\u65e0\u7b49\u6548\u6570\u636e)
        if self.profile.has_market_stats:
            self._get_market_statistics(overview)

        # 3. \u83b7\u53d6sectorchange\u699c (A \u80a1\u6709; US stock\u6682\u65e0)
        if self.profile.has_sector_rankings:
            self._get_sector_rankings(overview)
            self._get_concept_rankings(overview)

        # 4. \u83b7\u53d6\u5317\u5411\u8d44\u91d1 (optional)
        # self._get_north_flow(overview)

        return overview


    def _get_main_indices(self) -> List[MarketIndex]:
        """\u83b7\u53d6\u4e3b\u8981indexrealtime quote"""
        indices = []

        try:
            logger.info("[\u5927\u76d8] %s action=get_main_indices status=start", self._log_context())

            # \u4f7f\u7528 DataFetcherManager \u83b7\u53d6index\u884c\u60c5 (\u6309 region \u5207\u6362)
            data_list = self.data_manager.get_main_indices(region=self.region)

            if data_list:
                for item in data_list:
                    index = MarketIndex(
                        code=item['code'],
                        name=item['name'],
                        current=item['current'],
                        change=item['change'],
                        change_pct=item['change_pct'],
                        open=item['open'],
                        high=item['high'],
                        low=item['low'],
                        prev_close=item['prev_close'],
                        volume=item['volume'],
                        amount=item['amount'],
                        amplitude=item['amplitude']
                    )
                    indices.append(index)

            if not indices:
                logger.warning("[\u5927\u76d8] %s action=get_main_indices status=empty", self._log_context())
            else:
                logger.info(
                    "[\u5927\u76d8] %s action=get_main_indices status=success count=%d",
                    self._log_context(),
                    len(indices),
                )

        except Exception as e:
            logger.error("[\u5927\u76d8] %s action=get_main_indices status=failed error=%s", self._log_context(), e)

        return indices

    def _get_market_statistics(self, overview: MarketOverview):
        """\u83b7\u53d6marketchange\u7edf\u8ba1"""
        try:
            logger.info("[\u5927\u76d8] %s action=get_market_stats status=start", self._log_context())

            stats = self.data_manager.get_market_stats(purpose=f"market_review:{self.region}")

            if stats:
                overview.up_count = stats.get('up_count', 0)
                overview.down_count = stats.get('down_count', 0)
                overview.flat_count = stats.get('flat_count', 0)
                overview.limit_up_count = stats.get('limit_up_count', 0)
                overview.limit_down_count = stats.get('limit_down_count', 0)
                overview.total_amount = stats.get('total_amount', 0.0)

                logger.info(
                    "[\u5927\u76d8] %s action=get_market_stats status=success up=%s down=%s flat=%s "
                    "limit_up=%s limit_down=%s amount=%.0f\u4ebf",
                    self._log_context(),
                    overview.up_count,
                    overview.down_count,
                    overview.flat_count,
                    overview.limit_up_count,
                    overview.limit_down_count,
                    overview.total_amount,
                )
            else:
                logger.warning("[\u5927\u76d8] %s action=get_market_stats status=empty", self._log_context())

        except Exception as e:
            logger.error("[\u5927\u76d8] %s action=get_market_stats status=failed error=%s", self._log_context(), e)

    def _get_sector_rankings(self, overview: MarketOverview):
        """\u83b7\u53d6sectorchange\u699c"""
        try:
            logger.info("[\u5927\u76d8] %s action=get_sector_rankings status=start", self._log_context())

            top_sectors, bottom_sectors = self.data_manager.get_sector_rankings(5)

            if top_sectors or bottom_sectors:
                overview.top_sectors = top_sectors
                overview.bottom_sectors = bottom_sectors

                logger.info(
                    "[\u5927\u76d8] %s action=get_sector_rankings status=success top=%s bottom=%s",
                    self._log_context(),
                    [s['name'] for s in overview.top_sectors],
                    [s['name'] for s in overview.bottom_sectors],
                )
            else:
                logger.warning("[\u5927\u76d8] %s action=get_sector_rankings status=empty", self._log_context())

        except Exception as e:
            logger.error("[\u5927\u76d8] %s action=get_sector_rankings status=failed error=%s", self._log_context(), e)

    def _get_concept_rankings(self, overview: MarketOverview):
        """\u83b7\u53d6concept/\u9898\u6750change\u699c (fail-open)."""
        try:
            logger.info("[\u5927\u76d8] %s action=get_concept_rankings status=start", self._log_context())

            top_concepts, bottom_concepts = self.data_manager.get_concept_rankings(5)

            if top_concepts or bottom_concepts:
                overview.top_concepts = top_concepts
                overview.bottom_concepts = bottom_concepts

                logger.info(
                    "[\u5927\u76d8] %s action=get_concept_rankings status=success top=%s bottom=%s",
                    self._log_context(),
                    [s.get('name') for s in overview.top_concepts],
                    [s.get('name') for s in overview.bottom_concepts],
                )
            else:
                logger.warning("[\u5927\u76d8] %s action=get_concept_rankings status=empty", self._log_context())

        except Exception as e:
            logger.warning("[\u5927\u76d8] %s action=get_concept_rankings status=failed error=%s", self._log_context(), e)

    # def _get_north_flow(self, overview: MarketOverview):
    #     """\u83b7\u53d6\u5317\u5411\u8d44\u91d1\u6d41\u5165"""
    #     try:
    #         logger.info("[\u5927\u76d8] \u83b7\u53d6\u5317\u5411\u8d44\u91d1...")
    #
    #         # \u83b7\u53d6\u5317\u5411\u8d44\u91d1\u6570\u636e
    #         df = ak.stock_hsgt_north_net_flow_in_em(symbol="\u5317\u4e0a")
    #
    #         if df is not None and not df.empty:
    #             # \u53d6\u6700\u65b0\u4e00\u6761\u6570\u636e
    #             latest = df.iloc[-1]
    #             if '\u5f53\u65e5\u51c0\u6d41\u5165' in df.columns:
    #                 overview.north_flow = float(latest['\u5f53\u65e5\u51c0\u6d41\u5165']) / 1e8  # \u8f6c\u4e3a\u4ebf\u5143
    #             elif '\u51c0\u6d41\u5165' in df.columns:
    #                 overview.north_flow = float(latest['\u51c0\u6d41\u5165']) / 1e8
    #
    #             logger.info(f"[\u5927\u76d8] \u5317\u5411\u8d44\u91d1\u51c0\u6d41\u5165: {overview.north_flow:.2f}\u4ebf")
    #
    #     except Exception as e:
    #         logger.warning(f"[\u5927\u76d8] \u83b7\u53d6\u5317\u5411\u8d44\u91d1failed: {e}")

    def search_market_news(self) -> List[Dict]:
        """
        searchmarketnews

        Returns:
            news\u5217\u8868
        """
        if not self.search_service:
            logger.warning(
                "[\u5927\u76d8] %s action=search_market_news status=skipped reason=no_search_service",
                self._log_context(),
            )
            return []

        all_news = []

        # \u6309 region \u4f7f\u7528\u4e0d\u540c\u7684newssearch\u8bcd
        search_queries = self.profile.news_queries
        review_language = self._get_review_language()
        market_names = {
            "cn": "\u5927\u76d8" if review_language == "zh" else "equity market",
            "us": "US stockmarket" if review_language == "zh" else "US market",
            "hk": "HK stockmarket" if review_language == "zh" else "HK market",
            "jp": "\u65e5\u672c\u80a1\u5e02" if review_language == "zh" else "Japan stock market",
            "kr": "\u97e9\u56fd\u80a1\u5e02" if review_language == "zh" else "Korea stock market",
        }

        try:
            logger.info("[\u5927\u76d8] %s action=search_market_news status=start", self._log_context())

            # \u6839\u636e region \u8bbe\u7f6esearch\u4e0a\u4e0b\u6587name; \u907f\u514dUS stocksearch\u88ab\u89e3\u8bfb\u4e3a A \u80a1\u8bed\u5883
            market_name = market_names.get(self.region, "\u5927\u76d8")
            for query in search_queries:
                response = self.search_service.search_stock_news(
                    stock_code="market",
                    stock_name=market_name,
                    max_results=3,
                    focus_keywords=query.split()
                )
                if response and response.results:
                    all_news.extend(response.results)
                    logger.info(
                        "[\u5927\u76d8] %s action=search_market_news status=query_success count=%d",
                        self._log_context(),
                        len(response.results),
                    )

            logger.info(
                "[\u5927\u76d8] %s action=search_market_news status=success count=%d",
                self._log_context(),
                len(all_news),
            )

        except Exception as e:
            logger.error("[\u5927\u76d8] %s action=search_market_news status=failed error=%s", self._log_context(), e)

        return all_news

    def generate_market_review(self, overview: MarketOverview, news: List) -> str:
        """
        \u4f7f\u7528\u5927\u6a21\u578b\u751f\u6210market reviewreport

        Args:
            overview: market\u6982\u89c8\u6570\u636e
            news: marketnews\u5217\u8868 (SearchResult \u5bf9\u8c61\u5217\u8868)

        Returns:
            market reviewreport\u6587\u672c
        """
        backend_error = self._get_analyzer_generation_backend_config_error()
        if backend_error is not None:
            logger.error(
                "[\u5927\u76d8] %s action=generate_review status=failed error_type=%s error=%s",
                self._log_context(),
                type(backend_error).__name__,
                backend_error,
            )
            record_llm_run(
                success=False,
                provider="litellm",
                model=getattr(self.config, "litellm_model", None),
                call_type="market_review",
                error_type=type(backend_error).__name__,
                error_message=backend_error,
            )
            raise backend_error

        if not self.analyzer or not self.analyzer.is_available():
            logger.warning(
                "[\u5927\u76d8] %s action=generate_review status=fallback_template reason=no_analyzer",
                self._log_context(),
            )
            return self._sanitize_default_english_market_report(self._generate_template_review(overview, news))

        # \u6784\u5efa Prompt
        prompt = self._build_review_prompt(overview, news)

        logger.info("[\u5927\u76d8] %s action=generate_review status=start", self._log_context())
        # Use the public generate_text() entry point - never access private analyzer attributes.
        llm_started_at = time.perf_counter()
        try:
            record_llm_run_started(
                provider="litellm",
                model=getattr(self.config, "litellm_model", None),
                call_type="market_review",
            )
            review = self.analyzer.generate_text(prompt, max_tokens=8192, temperature=0.7)
        except Exception as exc:
            record_llm_run(
                success=False,
                provider="litellm",
                model=getattr(self.config, "litellm_model", None),
                call_type="market_review",
                duration_ms=int((time.perf_counter() - llm_started_at) * 1000),
                error_type=type(exc).__name__,
                error_message=exc,
            )
            raise

        record_llm_run(
            success=bool(review),
            provider="litellm",
            model=getattr(self.config, "litellm_model", None),
            call_type="market_review",
            duration_ms=int((time.perf_counter() - llm_started_at) * 1000),
            error_type=None if review else "EmptyResponse",
            error_message=None if review else "empty market review response",
        )

        if review:
            logger.info(
                "[\u5927\u76d8] %s action=generate_review status=success length=%d",
                self._log_context(),
                len(review),
            )
            # Inject structured data tables into LLM prose sections
            return self._sanitize_default_english_market_report(self._inject_data_into_review(review, overview, news))

        logger.warning(
            "[\u5927\u76d8] %s action=generate_review status=fallback_template reason=empty_llm_response",
            self._log_context(),
        )
        return self._sanitize_default_english_market_report(self._generate_template_review(overview, news))

    def _get_analyzer_generation_backend_config_error(self) -> Optional[GenerationError]:
        """Return analyzer backend config errors without relying on dynamic mock attributes."""
        if self.analyzer is None:
            try:
                resolve_generation_backend_id(self.config)
                resolve_generation_fallback_backend_id(self.config)
            except GenerationError as exc:
                return exc
            return None
        missing = object()
        if getattr_static(self.analyzer, "get_generation_backend_config_error", missing) is missing:
            return None
        method = getattr(self.analyzer, "get_generation_backend_config_error", None)
        if not callable(method):
            return None
        error = method()
        return error if isinstance(error, GenerationError) else None

    def build_market_review_payload(
        self,
        overview: MarketOverview,
        news: List,
        report: str,
        market_light_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the structured market-review contract consumed by API, Web, and notifications."""
        language = self._get_output_language()
        sections = self._split_report_sections(report)
        title = self._extract_report_title(report) or self._get_review_title(overview.date).lstrip("# ").strip()
        light = (
            market_light_snapshot or self.build_market_light_snapshot(overview)
            if self._supports_market_light()
            else None
        )
        breadth_dimensions = None
        if isinstance(light, dict):
            dimensions = light.get("dimensions")
            if isinstance(dimensions, dict):
                breadth_dimensions = dimensions.get("breadth")

        breadth_supported = bool(self.profile.has_market_stats)
        if breadth_supported and isinstance(breadth_dimensions, dict) and "available" in breadth_dimensions:
            breadth_supported = bool(breadth_dimensions.get("available"))

        has_breadth_data = False
        if breadth_supported:
            if isinstance(breadth_dimensions, dict) and "available" in breadth_dimensions:
                has_breadth_data = bool(breadth_dimensions.get("available"))
            else:
                breadth_available = overview.up_count + overview.down_count + overview.flat_count > 0
                limit_available = overview.limit_up_count + overview.limit_down_count > 0
                has_breadth_data = bool(breadth_available or limit_available)

        payload = {
            "version": 1,
            "kind": "market_review",
            "region": self.region,
            "language": language,
            "title": title,
            "generated_at": datetime.now().isoformat(),
            "date": overview.date,
            "market_scope": self._get_market_scope_name(language),
            "indices": [idx.to_dict() for idx in overview.indices],
            "sectors": {
                "top": list(overview.top_sectors or []),
                "bottom": list(overview.bottom_sectors or []),
            },
            "concepts": {
                "top": list(overview.top_concepts or []),
                "bottom": list(overview.bottom_concepts or []),
            },
            "news": [self._normalize_news_item(item) for item in (news or [])[:8]],
            "sections": sections,
            "markdown_report": report,
        }

        if light is not None:
            payload["market_light"] = light

        if has_breadth_data:
            payload["breadth"] = {
                "up_count": overview.up_count,
                "down_count": overview.down_count,
                "flat_count": overview.flat_count,
                "limit_up_count": overview.limit_up_count,
                "limit_down_count": overview.limit_down_count,
                "total_amount": overview.total_amount,
                "turnover_unit": self._get_turnover_unit_label(),
            }

        return payload

    def _supports_market_light(self) -> bool:
        return self.region in MARKET_LIGHT_REGIONS

    @staticmethod
    def _extract_report_title(report: str) -> str:
        for line in (report or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""

    @classmethod
    def _split_report_sections(cls, report: str) -> List[Dict[str, str]]:
        text = (report or "").strip()
        if not text:
            return []
        matches = list(re.finditer(r"^(#{2,3})\s+(.+?)\s*$", text, flags=re.MULTILINE))
        if not matches:
            return [{"key": "full_review", "title": "Review", "markdown": text}]

        sections: List[Dict[str, str]] = []
        first_match = matches[0]
        starts_with_report_title = first_match.start() == 0 and first_match.group(1) == "##"
        content_start_index = 1 if starts_with_report_title else 0
        intro_start = first_match.end() if starts_with_report_title else 0
        intro_end = (
            matches[1].start()
            if starts_with_report_title and len(matches) > 1
            else (len(text) if starts_with_report_title else matches[0].start())
        )
        intro = text[intro_start:intro_end].strip()
        if intro:
            sections.append({"key": "overview", "title": "Overview", "markdown": intro})

        for index, match in enumerate(matches[content_start_index:], start=content_start_index):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            title = match.group(2).strip()
            markdown = text[start:end].strip()
            if not markdown:
                continue
            key = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", title).strip("_").lower()
            sections.append({
                "key": key or f"section_{index + 1}",
                "title": title,
                "markdown": markdown,
            })
        return sections

    @classmethod
    def _normalize_news_item(cls, item: Any) -> Dict[str, str]:
        return {
            "title": cls._compact_news_text(cls._get_news_field(item, "title"), limit=120),
            "snippet": cls._compact_news_text(cls._get_news_field(item, "snippet"), limit=260),
            "source": cls._compact_news_text(cls._get_news_field(item, "source"), limit=80),
            "published_date": cls._compact_news_text(cls._get_news_field(item, "published_date"), limit=40),
            "url": cls._compact_news_text(cls._get_news_field(item, "url"), limit=240),
        }

    def _inject_data_into_review(
        self,
        review: str,
        overview: MarketOverview,
        news: Optional[List] = None,
    ) -> str:
        """Inject structured data tables into the corresponding LLM prose sections."""
        # Build data blocks
        stats_block = self._build_stats_block(overview)
        indices_block = self._build_indices_block(overview)
        sector_block = self._build_sector_block(overview)
        patterns = (
            _ENGLISH_SECTION_PATTERNS
            if self._get_review_language() == "en"
            else _CHINESE_SECTION_PATTERNS
        )

        if stats_block:
            review = self._insert_after_section(
                review,
                patterns["market_summary"],
                stats_block,
            )

        if indices_block:
            review = self._insert_after_section(
                review,
                patterns["index_commentary"],
                indices_block,
            )

        if sector_block:
            original_review = review
            review = self._insert_after_section(
                review,
                patterns["sector_highlights"],
                sector_block,
            )
            if review == original_review and sector_block not in review:
                fallback_heading = (
                    "### 4. Sector Highlights"
                    if self._get_review_language() == "en"
                    else "### \u4e09、sector\u4e3b\u7ebf"
                )
                review = f"{review.rstrip()}\n\n{fallback_heading}\n{sector_block}\n"

        return review

    @staticmethod
    def _insert_after_section(text: str, heading_pattern: str, block: str) -> str:
        """Insert a data block at the end of a markdown section (before the next ### heading)."""
        import re
        # Find the heading
        match = re.search(heading_pattern, text)
        if not match:
            return text
        start = match.end()
        # Find the next ### heading after this one
        next_heading = re.search(r'\n###\s', text[start:])
        if next_heading:
            insert_pos = start + next_heading.start()
        else:
            # No next heading — append at end
            insert_pos = len(text)
        # Insert the block before the next heading, with spacing
        return text[:insert_pos].rstrip() + '\n\n' + block + '\n\n' + text[insert_pos:].lstrip('\n')

    def _build_stats_block(self, overview: MarketOverview) -> str:
        """Build market statistics block."""
        has_stats = overview.up_count or overview.down_count or overview.total_amount
        if not has_stats:
            return ""
        if self._get_review_language() == "en":
            light = self.build_market_light_snapshot(overview)
            return "\n".join(
                [
                    f"- **Market Signal**: {light['score']}/100 "
                    f"({light['temperature_label']}, {light['label']})",
                    f"- **Drivers**: {'; '.join(light['reasons'])}",
                    f"- **Guidance**: {light['guidance']}",
                    "",
                    f"- **Breadth**: Advancers {overview.up_count} / Decliners {overview.down_count} / "
                    f"Flat {overview.flat_count}; "
                    f"Limit-up {overview.limit_up_count} / Limit-down {overview.limit_down_count}; "
                    f"Turnover {overview.total_amount:.0f} ({self._get_turnover_unit_label()})",
                ]
            )
        light = self.build_market_light_snapshot(overview)
        score, label = light["score"], light["temperature_label"]
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else 0.0
        limit_spread = overview.limit_up_count - overview.limit_down_count
        lines = [
            f"- **\u76d8\u9762\u4fe1\u53f7**: {score}/100 ({label}; {light['label']})",
            f"- **\u4fe1\u53f7\u4f9d\u636e**: {'；'.join(light['reasons'])}",
            f"- **operation advice**: {light['guidance']}",
            "",
            "| \u6307\u6807 | \u6570\u503c | \u89c2\u5bdf |",
            "|------|------|------|",
            f"| \u4e0a\u6da8/\u4e0b\u8dcc/\u5e73\u76d8 | {overview.up_count} / {overview.down_count} / {overview.flat_count} | \u4e0a\u6da8\u5360\u6bd4(\u4e0d\u542b\u5e73\u76d8) {up_ratio:.1%} |",
            f"| \u6da8\u505c/\u8dcc\u505c | {overview.limit_up_count} / {overview.limit_down_count} | change\u505c\u5dee {limit_spread:+d} |",
            f"| \u4e24\u5e02amount | {overview.total_amount:.0f} \u4ebf | {self._describe_turnover(overview.total_amount)} |",
        ]
        return "\n".join(lines)

    def build_market_light_snapshot(self, overview: MarketOverview) -> Dict[str, Any]:
        """Build a deterministic market-light snapshot from structured breadth data."""
        scores = self._build_market_light_scores(overview)
        score = int(scores["score"])
        temperature_label = str(scores["temperature_label"])
        if score >= 60:
            status = "green"
        elif score >= 40:
            status = "yellow"
        else:
            status = "red"

        if self._get_review_language() == "en":
            label_map = {
                "green": "risk-on",
                "yellow": "balanced",
                "red": "risk-off",
            }
            guidance_map = {
                "green": "Risk appetite is acceptable; focus on leading themes and position discipline.",
                "yellow": "Signals are mixed; keep position sizing moderate and wait for confirmation.",
                "red": "Risk is elevated; prioritize drawdown control and avoid chasing weak rebounds.",
            }
            reasons = self._build_market_light_reasons_en(overview, score)
        else:
            label_map = {
                "green": "\u53ef\u8fdb\u653b",
                "yellow": "\u9700\u89c2\u5bdf",
                "red": "Slightly \u9632\u5b88",
            }
            guidance_map = {
                "green": "\u98ce\u9669Slightly \u597d\u5c1a\u53ef; \u5173\u6ce8\u4e3b\u7ebf\u5ef6\u7eed\u4e0e\u4ed3characters\u7eaa\u5f8b.",
                "yellow": "\u4fe1\u53f7\u5206\u5316; Control position size\u5e76waiting\u91cf\u4ef7\u786e\u8ba4.",
                "red": "\u98ce\u9669Slightly High; \u4f18\u5148\u63a7\u5236\u56de\u64a4; \u907f\u514d\u8ffdHigh\u5f31\u53cd\u5f39.",
            }
            reasons = self._build_market_light_reasons_zh(overview, score)

        snapshot = MarketLightSnapshot(
            region=self.region,
            trade_date=overview.date,
            status=status,
            label=label_map[status],
            score=score,
            temperature_label=temperature_label,
            reasons=reasons,
            guidance=guidance_map[status],
            dimensions=scores["dimensions"],
            data_quality=str(scores["data_quality"]),
        )
        return snapshot.model_dump()

    def _build_market_light_reasons_zh(self, overview: MarketOverview, score: int) -> List[str]:
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else None
        reasons: List[str] = []
        if up_ratio is not None:
            if up_ratio >= 0.6:
                reasons.append(f"\u4e0a\u6da8\u5bb6\u6570\u5360\u6bd4 {up_ratio:.0%}; \u8d5a\u94b1\u6548\u5e94\u6269\u6563")
            elif up_ratio <= 0.4:
                reasons.append(f"\u4e0a\u6da8\u5bb6\u6570\u5360\u6bd4 {up_ratio:.0%}; \u4e8f\u94b1\u6548\u5e94\u8f83\u5f3a")
            else:
                reasons.append(f"\u4e0a\u6da8\u5bb6\u6570\u5360\u6bd4 {up_ratio:.0%}; market\u5206\u5316")
        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        if index_changes:
            avg_change = sum(index_changes) / len(index_changes)
            reasons.append(f"\u4e3b\u8981index\u5e73\u5747change\u5e45 {avg_change:+.2f}%")
        if overview.limit_up_count or overview.limit_down_count:
            reasons.append(f"change\u505c\u5dee {overview.limit_up_count - overview.limit_down_count:+d}")
        if not reasons and overview.total_amount:
            reasons.append(f"amount {overview.total_amount:.0f} \u4ebf; {self._describe_turnover(overview.total_amount)}")
        if not reasons:
            reasons.append("\u7ed3\u6784\u5316change\u6570\u636e\u6709\u9650; \u6309\u53ef\u7528\u884c\u60c5\u7efc\u5408\u5224\u65ad")
        return reasons[:4]

    def _build_market_light_reasons_en(self, overview: MarketOverview, score: int) -> List[str]:
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else None
        reasons: List[str] = []
        if up_ratio is not None:
            if up_ratio >= 0.6:
                reasons.append(f"advancers ratio {up_ratio:.0%}, breadth is expanding")
            elif up_ratio <= 0.4:
                reasons.append(f"advancers ratio {up_ratio:.0%}, downside pressure dominates")
            else:
                reasons.append(f"advancers ratio {up_ratio:.0%}, breadth is mixed")
        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        if index_changes:
            avg_change = sum(index_changes) / len(index_changes)
            reasons.append(f"average major-index change {avg_change:+.2f}%")
        if overview.limit_up_count or overview.limit_down_count:
            reasons.append(f"limit-up/down spread {overview.limit_up_count - overview.limit_down_count:+d}")
        if not reasons and overview.total_amount:
            reasons.append(f"turnover {overview.total_amount:.0f} ({self._get_turnover_unit_label()})")
        if not reasons:
            reasons.append("limited structured breadth data; using available market inputs")
        return reasons[:4]

    def _build_indices_block(self, overview: MarketOverview) -> str:
        """\u6784\u5efaindex\u884c\u60c5\u8868\u683c"""
        if not overview.indices:
            return ""
        if self._get_review_language() == "en":
            lines = [
                f"| Index | Last | Change % | Open | High | Low | Amplitude | Turnover ({self._get_turnover_unit_label()}) |",
                "|-------|------|----------|------|------|-----|-----------|-----------------|",
            ]
        else:
            lines = [
                "| index | \u6700\u65b0 | change\u5e45 | \u5f00\u76d8 | \u6700High | \u6700Low | \u632f\u5e45 | amount(\u4ebf) |",
                "|------|------|--------|------|------|------|------|-----------|",
            ]
        for idx in overview.indices:
            arrow = self._get_index_change_arrow(idx.change_pct)
            amount_raw = idx.amount or 0.0
            amount_str = self._format_turnover_value(amount_raw)
            lines.append(
                f"| {idx.name} | {idx.current:.2f} | {arrow} {idx.change_pct:+.2f}% | "
                f"{self._format_optional_number(idx.open)} | {self._format_optional_number(idx.high)} | "
                f"{self._format_optional_number(idx.low)} | {self._format_optional_pct(idx.amplitude)} | {amount_str} |"
            )
        return "\n".join(lines)

    def _build_sector_block(self, overview: MarketOverview) -> str:
        """Build industry and concept ranking blocks."""
        if (
            not overview.top_sectors
            and not overview.bottom_sectors
            and not overview.top_concepts
            and not overview.bottom_concepts
        ):
            return ""
        lines = []
        language = self._get_review_language()

        def append_ranking(title: str, name_label: str, rows: List[Dict]) -> None:
            if not rows:
                return
            if lines:
                lines.append("")
            rank_label = 'Rank' if language == 'en' else '\u6392\u540d'
            change_label = 'Change' if language == 'en' else 'change\u5e45'
            lines.extend([
                title,
                f"| {rank_label} | {name_label} | {change_label} |",
                "|------|------|--------|",
            ])
            for rank, item in enumerate(rows[:5], 1):
                lines.append(
                    f"| {rank} | {item.get('name', '-')} | {self._format_signed_pct(item.get('change_pct'))} |"
                )

        if language == "en":
            append_ranking("#### Leading Industry Sectors", "Sector", overview.top_sectors)
            append_ranking("#### Lagging Industry Sectors", "Sector", overview.bottom_sectors)
            append_ranking("#### Leading Concept Themes", "Concept", overview.top_concepts)
            append_ranking("#### Lagging Concept Themes", "Concept", overview.bottom_concepts)
        else:
            append_ranking("#### industrysector\u9886\u6da8 Top 5", "industrysector", overview.top_sectors)
            append_ranking("#### industrysector\u9886\u8dcc Top 5", "industrysector", overview.bottom_sectors)
            append_ranking("#### conceptsector\u9886\u6da8 Top 5", "conceptsector", overview.top_concepts)
            append_ranking("#### conceptsector\u9886\u8dcc Top 5", "conceptsector", overview.bottom_concepts)
        return "\n".join(lines)

    def _build_news_block(self, news: List) -> str:
        """Build a compact source-aware news catalyst list for the rendered report."""
        if not news:
            return ""
        language = self._get_review_language()
        if language == "en":
            lines = [
                "#### News Catalysts",
            ]
        else:
            lines = [
                "#### \u8fd1\u4e09\u65e5market\u7ebf\u7d22",
            ]

        for idx, item in enumerate(news[:5], 1):
            lines.append(self._format_news_catalyst_line(idx, item, language=language))
        return "\n".join(lines)

    @staticmethod
    def _get_news_field(item: Any, field: str) -> str:
        if hasattr(item, field):
            value = getattr(item, field, "") or ""
        elif isinstance(item, dict):
            value = item.get(field, "") or ""
        else:
            value = ""
        return str(value).strip()

    @classmethod
    def _format_news_catalyst_line(cls, idx: int, item: Any, *, language: str = "zh") -> str:
        fallback_title = "Untitled catalyst" if language == "en" else "\u672a\u547d\u540d\u7ebf\u7d22"
        title = cls._compact_news_text(cls._get_news_field(item, "title"), limit=90) or fallback_title
        source = cls._compact_news_text(cls._get_news_field(item, "source"), limit=40)
        date_text = cls._compact_news_text(cls._get_news_field(item, "published_date"), limit=24)
        url = cls._compact_news_text(cls._get_news_field(item, "url"), limit=0)
        title_text = cls._escape_markdown_link_label(title)
        if url:
            title_text = f"[{title_text}]({url})"
        meta_parts = [part for part in (source, date_text) if part]
        if language == "en":
            meta = f" ({' / '.join(meta_parts)})" if meta_parts else ""
        else:
            meta = f" ({' / '.join(meta_parts)})" if meta_parts else ""
        return f"- {idx}. {title_text}{meta}"

    @staticmethod
    def _compact_news_text(value: str, *, limit: int) -> str:
        text = " ".join(str(value or "").split())
        if limit <= 0 or len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _format_optional_number(value: float) -> str:
        return "N/A" if value in (None, 0, 0.0) else f"{value:.2f}"

    @staticmethod
    def _format_optional_pct(value: float) -> str:
        return "N/A" if value in (None, 0, 0.0) else f"{value:.2f}%"

    @staticmethod
    def _format_signed_pct(value: Any) -> str:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "N/A"
        return f"{numeric_value:+.2f}%"

    @classmethod
    def _format_ranking_summary(cls, rows: List[Dict], limit: int = 3) -> str:
        parts = []
        for item in (rows or [])[:limit]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            parts.append(f"{name}({cls._format_signed_pct(item.get('change_pct'))})")
        return ", ".join(parts)

    @staticmethod
    def _escape_markdown_link_label(value: str) -> str:
        return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")

    @staticmethod
    def _describe_turnover(total_amount: float) -> str:
        if total_amount >= 15000:
            return "High\u6d3b\u8dc3\u5ea6"
        if total_amount >= 9000:
            return "Medium\u7b49\u6d3b\u8dc3"
        if total_amount > 0:
            return "\u7f29\u91cfWatch"
        return "\u6682no data"

    def _build_market_light_scores(self, overview: MarketOverview) -> Dict[str, Any]:
        """Build the canonical Market Light scores used by reports and alerts."""

        participants = overview.up_count + overview.down_count
        breadth_available = bool(self.profile.has_market_stats and participants > 0)
        breadth_score = 50
        if breadth_available:
            breadth_score = int(overview.up_count / participants * 100)

        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        index_available = bool(overview.indices and index_changes)
        index_score = 50
        if index_available:
            avg_change = sum(index_changes) / len(index_changes)
            index_score = int(max(0, min(100, 50 + avg_change * 12)))

        limit_total = overview.limit_up_count + overview.limit_down_count
        limit_available = bool(self.profile.has_market_stats and limit_total > 0)
        limit_score = 50
        if limit_available:
            limit_score = int(overview.limit_up_count / limit_total * 100)

        dimensions = {
            "breadth": {"score": breadth_score, "available": breadth_available},
            "index": {"score": index_score, "available": index_available},
            "limit": {"score": limit_score, "available": limit_available},
        }

        if not index_available:
            data_quality = "unavailable"
        elif all(dimension["available"] for dimension in dimensions.values()):
            data_quality = "ok"
        else:
            data_quality = "partial"

        score = int(round(breadth_score * 0.45 + index_score * 0.35 + limit_score * 0.20))
        if self._get_review_language() == "en":
            if score >= 70:
                label = "risk-on"
            elif score >= 55:
                label = "constructive"
            elif score >= 40:
                label = "mixed"
            else:
                label = "defensive"
        else:
            if score >= 70:
                label = "\u5f3a\u52bf"
            elif score >= 55:
                label = "Slightly \u6696"
            elif score >= 40:
                label = "\u9707\u8361"
            else:
                label = "Slightly \u5f31"
        return {
            "score": score,
            "temperature_label": label,
            "dimensions": dimensions,
            "data_quality": data_quality,
        }

    def _build_market_temperature(self, overview: MarketOverview) -> tuple[int, str]:
        scores = self._build_market_light_scores(overview)
        score = int(scores["score"])
        label = str(scores["temperature_label"])
        return score, label

    def _build_output_template_sections(self, review_language: str) -> str:
        """Build LLM output sections according to market data capabilities."""
        if review_language == "en":
            if self.profile.has_market_stats and self.profile.has_sector_rankings:
                return """### 3. Fund Flows
(Interpret what turnover, participation, and flow signals imply.)

### 4. Sector Highlights
(Distinguish industry-sector moves from concept/theme moves, then analyze drivers and persistence.)

### 5. Outlook
(Provide the near-term outlook based on price action and news.)

### 6. Risk Alerts
(List the main risks to monitor.)

### 7. Strategy Plan
(Provide an offensive/balanced/defensive stance, a position-sizing guideline, one invalidation trigger, and end with "For reference only, not investment advice.")"""

            section_number = 3
            sections: List[str] = []
            if self.profile.has_market_stats:
                sections.append(f"""### {section_number}. Fund Flows
(Interpret only the provided turnover, participation, breadth, and flow signals.)""")
                section_number += 1
            if self.profile.has_sector_rankings:
                sections.append(f"""### {section_number}. Sector Highlights
(Analyze only the provided industry-sector and concept/theme rankings.)""")
                section_number += 1
            sections.extend([
                f"""### {section_number}. News Catalysts
(Connect recent news to index price action and macro/external-market clues. Do not infer unsupported breadth, fund-flow, or sector-ranking data.)""",
                f"""### {section_number + 1}. Outlook
(Provide the near-term outlook based on index price action and the available news.)""",
                f"""### {section_number + 2}. Risk Alerts
(List the main risks to monitor.)""",
                f"""### {section_number + 3}. Strategy Plan
(Provide an offensive/balanced/defensive stance, a position-sizing guideline, one invalidation trigger, and end with "For reference only, not investment advice.")""",
            ])
            return "\n\n".join(sections)

        if self.profile.has_market_stats and self.profile.has_sector_rankings:
            return """### \u4e09、sector\u4e3b\u7ebf
 (\u533a\u5206industrysector\u4e0econcept\u9898\u6750; analyze\u9886\u6da8/\u9886\u8dcc\u80cc\u540e\u7684\u903b\u8f91、\u6301\u7eed\u548c\u662f\u5426\u5f62\u6210\u4e3b\u7ebf)

### \u56db、\u8d44\u91d1\u4e0e\u60c5\u7eea
 (\u89e3\u8bfbamount、change\u505c\u7ed3\u6784、market\u5bbd\u5ea6\u548c\u98ce\u9669Slightly \u597d)

### \u4e94、\u6d88\u606f\u50ac\u5316
 (\u7ed3\u5408\u8fd1\u4e09\u65e5news; \u63d0\u70bc\u771f\u6b63\u5f71\u54cd\u660e\u65e5\u4ea4\u6613\u7684\u50ac\u5316or\u6270\u52a8)

### \u516d、\u660e\u65e5\u4ea4\u6613\u8ba1\u5212
 (\u7ed9\u51fa\u8fdb\u653b/\u5747\u8861/\u9632\u5b88\u7ed3\u8bba、\u4ed3characters\u533a\u95f4、\u5173\u6ce8\u65b9\u5411、\u56de\u907f\u65b9\u5411\u548c\u4e00\u4e2a\u89e6\u53d1\u5931\u6548\u6761\u4ef6)

### \u4e03、risk warning
 (\u5217\u51fa\u9700\u8981\u5173\u6ce8\u7684\u98ce\u9669\u70b9；\u6700\u540e\u8865\u5145“\u5efa\u8bae\u4ec5\u4f9b\u53c2\u8003; \u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae”.)"""

        numerals = ["\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94", "\u516d", "\u4e03", "\u516b"]
        section_number = 3
        sections: List[str] = []

        def add_section(title: str, hint: str) -> None:
            nonlocal section_number
            sections.append(f"### {numerals[section_number - 1]}、{title}\n{hint}")
            section_number += 1

        if self.profile.has_sector_rankings:
            add_section("sector\u4e3b\u7ebf", " (\u4ec5analyze\u5df2\u63d0\u4f9b\u7684industrysector\u4e0econcept\u9898\u6750\u699c\u5355; \u4e0d\u6269\u5c55\u672a\u63d0\u4f9bdata)")
        if self.profile.has_market_stats:
            add_section("\u8d44\u91d1\u4e0e\u60c5\u7eea", " (\u4ec5\u89e3\u8bfb\u5df2\u63d0\u4f9b\u7684amount、change\u505c\u7ed3\u6784、market\u5bbd\u5ea6\u548c\u98ce\u9669Slightly \u597d\u6570\u636e)")
        add_section(
            "\u6d88\u606f\u50ac\u5316",
            " (\u7ed3\u5408\u8fd1\u4e09\u65e5news\u548cindex\u8868\u73b0; \u63d0\u70bc\u771f\u6b63\u5f71\u54cd\u660e\u65e5\u4ea4\u6613\u7684\u50ac\u5316or\u6270\u52a8；\u4e0d\u8981\u63a8\u65ad\u672a\u63d0\u4f9b\u7684\u8d44\u91d1\u6d41、market\u5bbd\u5ea6orsector\u699c)",
        )
        add_section("\u660e\u65e5\u4ea4\u6613\u8ba1\u5212", " (\u7ed9\u51fa\u8fdb\u653b/\u5747\u8861/\u9632\u5b88\u7ed3\u8bba、\u4ed3characters\u533a\u95f4、\u5173\u6ce8\u65b9\u5411、\u56de\u907f\u65b9\u5411\u548c\u4e00\u4e2a\u89e6\u53d1\u5931\u6548\u6761\u4ef6)")
        add_section("risk warning", " (\u5217\u51fa\u9700\u8981\u5173\u6ce8\u7684\u98ce\u9669\u70b9；\u6700\u540e\u8865\u5145“\u5efa\u8bae\u4ec5\u4f9b\u53c2\u8003; \u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae”.)")
        return "\n\n".join(sections)

    def _sanitize_default_english_market_report(self, report: str) -> str:
        """Remove CN-specific country/currency labels from English market-review output."""
        if self.region != "cn" or self._get_output_language() != "en" or not report:
            return report

        sanitized = report
        replacements = (
            (r"\bA[- ]shares?\s+Market Recap\b", "Market Recap"),
            (r"\bA[- ]shares?\s+market\b", "equity market"),
            (r"\bA[- ]shares\b", "equities"),
            (r"\bA[- ]share\b", "equity"),
            ("\u0041\u80a1", "equities"),
            (r"\bCNY\s*100m\b", "100m units"),
            (r"\bCNY\b", "units"),
            (r"\bRMB\b", "units"),
            (r"\brenminbi\b", "units"),
            (r"\byuan\b", "units"),
            ("\u4eba\u6c11\u5e01", "units"),
            ("\u4ebf\u5143", "100m units"),
            ("\u5143", "units"),
            (r"\bMainland\s+China\b", "the market"),
            (r"\bChina's\b", "the market's"),
            (r"\bChina\b", "the market"),
            ("\u4e2d\u56fd", "the market"),
            (r"\bChinese\s+", ""),
            (r"\bChinese\b", "market"),
        )
        for pattern, replacement in replacements:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
        sanitized = re.sub(r" +\n", "\n", sanitized)
        return sanitized

    def _build_review_prompt(self, overview: MarketOverview, news: List) -> str:
        """\u6784\u5efa\u590d\u76d8report Prompt"""
        review_language = self._get_review_language()
        # Korean reuses the English structural template but the model is told to
        # write the entire shell, headings, guidance and conclusion in Korean.
        shell_language_label = "Korean (한국어)" if self._get_output_language() == "ko" else "English"

        # index\u884c\u60c5info (\u7b80\u6d01\u683c\u5f0f; \u4e0d\u7528emoji)
        indices_text = ""
        for idx in overview.indices:
            direction = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "-"
            indices_text += f"- {idx.name}: {idx.current:.2f} ({direction}{abs(idx.change_pct):.2f}%)\n"

        # sectorinfo
        top_sectors_text = self._format_ranking_summary(overview.top_sectors)
        bottom_sectors_text = self._format_ranking_summary(overview.bottom_sectors)
        top_concepts_text = self._format_ranking_summary(overview.top_concepts)
        bottom_concepts_text = self._format_ranking_summary(overview.bottom_concepts)

        # newsinfo - \u652f\u6301 SearchResult \u5bf9\u8c61or\u5b57\u5178
        news_text = ""
        for i, n in enumerate(news[:6], 1):
            # \u517c\u5bb9 SearchResult \u5bf9\u8c61\u548c\u5b57\u5178
            title = self._compact_news_text(self._get_news_field(n, "title"), limit=90)
            snippet = self._compact_news_text(self._get_news_field(n, "snippet"), limit=220)
            source = self._compact_news_text(self._get_news_field(n, "source"), limit=60)
            published_date = self._compact_news_text(self._get_news_field(n, "published_date"), limit=30)
            url = self._compact_news_text(self._get_news_field(n, "url"), limit=180)
            meta_parts = [part for part in (source, published_date) if part]
            meta = f" ({' / '.join(meta_parts)})" if meta_parts else ""
            url_line = f"\n   URL: {url}" if url else ""
            news_text += f"{i}. {title}{meta}\n   {snippet or '-'}{url_line}\n"

        # \u6309 region \u7ec4\u88c5market\u6982\u51b5\u4e0esector\u533achunks (US stock/HK stock/\u65e5\u97e9\u65e0change\u5bb6\u6570、sector\u6570\u636e)
        stats_block = ""
        sector_block = ""
        data_limits_block = ""
        if review_language == "en":
            if self.profile.has_market_stats:
                stats_block = f"""## Market Breadth
- Advancers: {overview.up_count} | Decliners: {overview.down_count} | Flat: {overview.flat_count}
- Limit-up: {overview.limit_up_count} | Limit-down: {overview.limit_down_count}
- Turnover: {overview.total_amount:.0f} ({self._get_turnover_unit_label()})"""

            if self.profile.has_sector_rankings:
                sector_block = f"""## Sector / Theme Performance
Industry leading: {top_sectors_text if top_sectors_text else "N/A"}
Industry lagging: {bottom_sectors_text if bottom_sectors_text else "N/A"}
Concept leading: {top_concepts_text if top_concepts_text else "N/A"}
Concept lagging: {bottom_concepts_text if bottom_concepts_text else "N/A"}"""

            data_limit_lines = []
            if not self.profile.has_market_stats:
                data_limit_lines.append(
                    "- Market breadth, aggregate turnover, participation, and fund-flow signals are not available for this market."
                )
            if not self.profile.has_sector_rankings:
                data_limit_lines.append("- Sector/theme ranking data is not available for this market.")
            if data_limit_lines:
                data_limits_block = "## Data Limits\n" + "\n".join(data_limit_lines)
        else:
            if self.profile.has_market_stats:
                stats_block = f"""## market\u6982\u51b5
- \u4e0a\u6da8: {overview.up_count} \u5bb6 | \u4e0b\u8dcc: {overview.down_count} \u5bb6 | \u5e73\u76d8: {overview.flat_count} \u5bb6
- \u6da8\u505c: {overview.limit_up_count} \u5bb6 | \u8dcc\u505c: {overview.limit_down_count} \u5bb6
- \u4e24\u5e02amount: {overview.total_amount:.0f} \u4ebf\u5143"""

            if self.profile.has_sector_rankings:
                no_data_text = '\u6682no data'
                sector_block = f"""## sector\u8868\u73b0
industry\u9886\u6da8: {top_sectors_text if top_sectors_text else no_data_text}
industry\u9886\u8dcc: {bottom_sectors_text if bottom_sectors_text else no_data_text}
concept\u9886\u6da8: {top_concepts_text if top_concepts_text else no_data_text}
concept\u9886\u8dcc: {bottom_concepts_text if bottom_concepts_text else no_data_text}"""

            data_limit_lines = []
            if not self.profile.has_market_stats:
                data_limit_lines.append("- \u8be5market\u6682\u65e0change\u5bb6\u6570、change\u505c、amount\u6c47\u603b、\u53c2\u4e0e\u5ea6or\u8d44\u91d1\u6d41\u4fe1\u53f7.")
            if not self.profile.has_sector_rankings:
                data_limit_lines.append("- \u8be5market\u6682\u65e0industrysector/concept\u9898\u6750change\u699c.")
            if data_limit_lines:
                data_limits_block = "## \u6570\u636e\u8fb9\u754c\n" + "\n".join(data_limit_lines)

        data_no_indices_hint = (
            "\u6ce8\u610f: \u7531\u4e8e\u884c\u60c5\u6570\u636efetch failed; \u8bf7\u4e3b\u8981\u6839\u636e【marketnews】\u8fdb\u884c\u5b9aanalyze\u548c\u603b\u7ed3; \u4e0d\u8981\u7f16\u9020\u5177\u4f53\u7684index\u70b9characters."
            if not indices_text
            else ""
        )
        if review_language == "en":
            data_no_indices_hint = (
                "Note: Market data fetch failed. Rely mainly on [Market News] for qualitative analysis. Do not invent index levels."
                if not indices_text
                else ""
            )
            indices_placeholder = indices_text if indices_text else "No index data (API error)"
            news_placeholder = news_text if news_text else "No relevant news"
            data_boundary_requirement = (
                "- Respect Data Limits: do not invent or over-interpret unsupported breadth, fund-flow, turnover, participation, or sector-ranking data.\n"
                if data_limits_block
                else ""
            )
            neutral_market_requirement = (
                "- For the default equity-market report, do not write country or currency labels such as yuan, CNY, RMB, renminbi, China, Chinese, or A-share; use market/equities and 100m units instead.\n"
                if self.region == "cn" and self._get_output_language() == "en"
                else ""
            )
            market_summary_hint = (
                "2-3 sentences summarizing overall market tone, index moves, and liquidity."
                if self.profile.has_market_stats
                else "2-3 sentences summarizing overall market tone, index moves, and available news context."
            )
        else:
            indices_placeholder = indices_text if indices_text else "\u6682\u65e0index\u6570\u636e (\u63a5\u53e3\u5f02\u5e38)"
            news_placeholder = news_text if news_text else "\u6682\u65e0\u76f8\u5173news"
            data_boundary_requirement = (
                "- \u4e25\u683c\u9075\u5b88\u6570\u636e\u8fb9\u754c: \u672a\u63d0\u4f9bchange\u5bb6\u6570、\u8d44\u91d1\u6d41、amount\u6c47\u603borsector\u699c\u65f6; \u4e0d\u8981\u7f16\u9020or\u8fc7\u5ea6\u89e3\u8bfb.\n"
                if data_limits_block
                else ""
            )
            market_summary_hint = (
                "2-3\u53e5\u8bdd\u6982\u62ecindex、change\u5bb6\u6570、amount\u548c\u60c5\u7eea\u6e29\u5ea6; \u660e\u786e“\u5f3a\u52bf/Slightly \u6696/\u9707\u8361/Slightly \u5f31”\u5224\u65ad"
                if self.profile.has_market_stats
                else "2-3\u53e5\u8bdd\u6982\u62ecindex\u8868\u73b0、news\u7ebf\u7d22\u548c\u6574\u4f53\u98ce\u9669status; \u4e0d\u8981\u8865\u5199\u672a\u63d0\u4f9b\u7684market\u5bbd\u5ea6or\u8d44\u91d1\u6d41\u6570\u636e"
            )

        output_template_sections = self._build_output_template_sections(review_language)
        zh_market_scope_name = self._get_market_scope_name("zh")
        zh_report_title = f"{overview.date} market review"
        if self.region in ("jp", "kr"):
            zh_report_title = f"{overview.date} {zh_market_scope_name}market review"
        workflow_hint = (
            "report\u8981\u50cf\u4ea4\u6613\u5458\u76d8\u540e\u5de5\u4f5c\u53f0: \u5148\u7ed9\u7ed3\u8bba; \u518d\u6309\u6570\u636e\u8868、\u4e3b\u7ebf、\u50ac\u5316、\u8ba1\u5212\u5c55\u5f00"
            if self.profile.has_market_stats or self.profile.has_sector_rankings
            else "report\u8981\u50cf\u4ea4\u6613\u5458\u76d8\u540e\u5de5\u4f5c\u53f0: \u5148\u7ed9\u7ed3\u8bba; \u518d\u6309index、news\u50ac\u5316\u548c\u8ba1\u5212\u5c55\u5f00"
        )

        if review_language == "en":
            report_title = self._get_review_title(overview.date).removeprefix("## ").strip()
            return f"""You are a professional {self._get_market_scope_name('en')} analyst. Please produce a concise market recap report based on the data below.

[Requirements]
- Output pure Markdown only
- No JSON
- No code blocks
- Use emoji sparingly in headings (at most one per heading)
- The entire fixed shell, headings, guidance, and conclusion must be in {shell_language_label}
{data_boundary_requirement}{neutral_market_requirement}

---

# Today's Market Data

## Date
{overview.date}

## Major Indices
{indices_placeholder}

{stats_block}

{sector_block}

{data_limits_block}

## Market News
{news_placeholder}

{data_no_indices_hint}

{self._get_strategy_prompt_block()}

---

# Output Template (follow this structure)

## {report_title}

### 1. Market Summary
({market_summary_hint})

### 2. Index Commentary
({self._get_index_hint()})

{output_template_sections}

---

Output the report content directly, no extra commentary.
"""

        # A \u80a1\u573a\u666f\u4f7f\u7528Medium\u6587\u63d0\u793a\u8bed
        return f"""\u4f60\u662f\u4e00characters\u4e13\u4e1a\u7684{self._get_market_scope_name('zh')}analyze\u5e08; \u8bf7\u6839\u636e\u4ee5\u4e0b\u6570\u636e\u751f\u6210\u4e00\u4efd\u7ed3\u6784\u5316\u7684{self._get_market_scope_name('zh')}market reviewreport.

【\u91cd\u8981】\u8f93\u51fa\u8981\u6c42:
- \u5fc5\u987b\u8f93\u51fa\u7eaf Markdown \u6587\u672c\u683c\u5f0f
- \u7981\u6b62\u8f93\u51fa JSON \u683c\u5f0f
- \u7981\u6b62\u8f93\u51facodechunks
- emoji \u4ec5\u5728\u6807\u9898\u5904\u5c11\u91cf\u4f7f\u7528 (\u6bcf\u4e2a\u6807\u9898\u6700\u591a1\u4e2a)
- {workflow_hint}
- \u4e0d\u8981\u91cd\u590d\u5217\u51fa\u5df2\u7531\u7cfb\u7edf\u6ce8\u5165\u7684\u8868\u683c\u6570\u636e；\u6b63\u6587\u8d1f\u8d23\u89e3\u91ca\u8868\u683c\u80cc\u540e\u7684\u542b\u4e49
{data_boundary_requirement}

---

# \u4eca\u65e5market\u6570\u636e

## date
{overview.date}

## \u4e3b\u8981index
{indices_placeholder}

{stats_block}

{sector_block}

{data_limits_block}

## marketnews
{news_placeholder}

{data_no_indices_hint}

{self._get_strategy_prompt_block()}

---

# \u8f93\u51fa\u683c\u5f0f\u6a21\u677f (\u8bf7\u4e25\u683c\u6309\u6b64\u683c\u5f0f\u8f93\u51fa)

## {zh_report_title}

> \u4e00\u53e5\u8bdd\u7ed9\u51fa\u4eca\u65e5marketstatus、\u6838\u5fc3\u77db\u76fe\u548c\u660e\u65e5\u4f18\u5148\u89c2\u5bdf\u65b9\u5411.

### \u4e00、\u76d8\u9762\u603b\u89c8
 ({market_summary_hint})

### \u4e8c、index\u7ed3\u6784
 ({self._get_index_hint()}; \u8bf4\u660e\u8c01\u5728\u62a4\u76d8、\u8c01\u5728\u62d6\u7d2f; \u4ee5\u53ca\u5173\u952e\u652f\u6491/\u538b\u529b)

{output_template_sections}

---

\u8bf7\u76f4\u63a5\u8f93\u51fa\u590d\u76d8report\u5185\u5bb9; \u4e0d\u8981\u8f93\u51faother\u8bf4\u660e\u6587\u5b57.
"""

    def _generate_template_review(self, overview: MarketOverview, news: List) -> str:
        """\u4f7f\u7528\u6a21\u677f\u751f\u6210\u590d\u76d8report (\u65e0\u5927\u6a21\u578b\u65f6\u7684\u5907\u9009\u65b9\u6848)"""
        template_language = self._get_template_review_language()
        mood_code = self.profile.mood_index_code
        # \u6839\u636e mood_index_code check\u627e\u5bf9\u5e94index
        # cn: mood_code="000001"; idx.code \u53ef\u80fd\u4e3a "sh000001" (\u4ee5 mood_code \u7ed3\u5c3e)
        # us: mood_code="SPX"; idx.code \u76f4\u63a5\u4e3a "SPX"
        mood_index = next(
            (
                idx
                for idx in overview.indices
                if idx.code == mood_code or idx.code.endswith(mood_code)
            ),
            None,
        )
        if mood_index:
            if mood_index.change_pct > 1:
                market_mood = self._get_market_mood_text("strong_up", template_language)
            elif mood_index.change_pct > 0:
                market_mood = self._get_market_mood_text("mild_up", template_language)
            elif mood_index.change_pct > -1:
                market_mood = self._get_market_mood_text("mild_down", template_language)
            else:
                market_mood = self._get_market_mood_text("strong_down", template_language)
        else:
            market_mood = self._get_market_mood_text("range", template_language)

        # index\u884c\u60c5 (\u7b80\u6d01\u683c\u5f0f)
        indices_text = ""
        for idx in overview.indices[:4]:
            direction = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "-"
            indices_text += f"- **{idx.name}**: {idx.current:.2f} ({direction}{abs(idx.change_pct):.2f}%)\n"

        # sectorinfo
        separator = ", " if template_language == "en" else "、"
        top_text = separator.join([s['name'] for s in overview.top_sectors[:3]])
        bottom_text = separator.join([s['name'] for s in overview.bottom_sectors[:3]])
        top_concept_text = separator.join([s['name'] for s in overview.top_concepts[:3]])
        bottom_concept_text = separator.join([s['name'] for s in overview.bottom_concepts[:3]])

        if template_language == "en":
            stats_section = ""
            if self.profile.has_market_stats:
                stats_section = f"""
### 3. Breadth & Liquidity
| Metric | Value |
|--------|-------|
| Advancers | {overview.up_count} |
| Decliners | {overview.down_count} |
| Limit-up | {overview.limit_up_count} |
| Limit-down | {overview.limit_down_count} |
| Turnover ({self._get_turnover_unit_label()}) | {overview.total_amount:.0f} |
"""
            sector_section = ""
            if self.profile.has_sector_rankings and (top_text or bottom_text or top_concept_text or bottom_concept_text):
                sector_section = f"""
### 4. Sector / Theme Highlights
- **Industry Leaders**: {top_text or "N/A"}
- **Industry Laggards**: {bottom_text or "N/A"}
- **Concept Leaders**: {top_concept_text or "N/A"}
- **Concept Laggards**: {bottom_concept_text or "N/A"}
"""
            market_names = {
                "us": "US Market Recap",
                "hk": "HK Market Recap",
                "jp": "Japan Market Recap",
                "kr": "Korea Market Recap",
            }
            market_name = market_names.get(self.region, "Market Recap")
            report = f"""## {overview.date} {market_name}

### 1. Market Summary
Today's {self._get_market_scope_name(template_language)} showed **{market_mood}**.

### 2. Major Indices
{indices_text or "- No index data available"}
{stats_section}
{sector_section}
### 5. Risk Alerts
Market conditions can change quickly. The data above is for reference only and does not constitute investment advice.

{self._get_strategy_markdown_block(template_language)}

---
*Review Time: {datetime.now().strftime('%H:%M')}*
"""
            return report

        market_labels = {"cn": "A-share", "us": "US stock", "hk": "HK stock", "jp": "JP stock", "kr": "KR stock"}
        market_label = market_labels.get(self.region, "A-share")
        dashboard_block = self._build_stats_block(overview) if self.profile.has_market_stats else ""
        indices_block = self._build_indices_block(overview)
        sector_block = self._build_sector_block(overview) if self.profile.has_sector_rankings else ""
        summary_focus = (
            "index\u627f\u63a5、amount\u53d8\u5316\u548csector\u6301\u7eed"
            if self.profile.has_market_stats and self.profile.has_sector_rankings
            else "index\u627f\u63a5、\u6d88\u606f\u50ac\u5316\u548c\u6574\u4f53\u98ce\u9669status"
        )
        market_summary_block = (
            dashboard_block
            if dashboard_block
            else (
                "\u6682\u65e0market\u5bbd\u5ea6\u6570\u636e."
                if self.profile.has_market_stats
                else "- \u5f53\u524d\u4ee5\u4e3b\u8981index\u4e0e\u53ef\u7528news\u7ebf\u7d22\u8bc4\u4f30\u6574\u4f53\u98ce\u9669status."
            )
        )
        sector_fallback = '- \u6682\u65e0sectorchange\u699c\u6570\u636e.'
        sector_section = (
            f"""
### \u4e09ã€sector\u4e3b\u7ebf
{sector_block or sector_fallback}
"""
            if self.profile.has_sector_rankings
            else ""
        )
        funds_section = (
            """
### \u56db、\u8d44\u91d1\u4e0e\u60c5\u7eea
- \u7ed3\u5408amount\u548cchange\u5bb6\u6570\u770b; \u5f53\u524d\u66f4\u9002\u5408waiting\u786e\u8ba4; \u907f\u514d\u4ec5\u51ed\u5355\u4e00\u70ed\u70b9\u8ffdHigh.
"""
            if self.profile.has_market_stats
            else ""
        )
        indices_display = indices_block or indices_text or '\u6682\u65e0index\u6570\u636e.'
        return f"""## {overview.date} market review

> \u4eca\u65e5{market_label}market\u6574\u4f53\u5448\u73b0**{market_mood}**\u6001\u52bf; \u4f18\u5148\u89c2\u5bdf{summary_focus}.

### \u4e00、\u76d8\u9762\u603b\u89c8
{market_summary_block}

### \u4e8c、index\u7ed3\u6784
{indices_display}
{sector_section}
{funds_section}

### \u4e94、\u6d88\u606f\u50ac\u5316
- \u6682\u65e0\u53ef\u7528news\u65f6; \u5e94\u964dLow\u5bf9\u9898\u6750\u6301\u7eed\u7684\u786e\u5b9a\u5224\u65ad.

{self._get_strategy_markdown_block(template_language)}

### \u4e03、risk warning
- market\u6709\u98ce\u9669; \u6295\u8d44\u9700\u8c28\u614e.\u4ee5\u4e0a\u6570\u636e\u4ec5\u4f9b\u53c2\u8003; \u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae.

---
*\u590d\u76d8\u65f6\u95f4: {datetime.now().strftime('%H:%M')}*
"""

    def _run_daily_review_parts(self) -> MarketLightReviewResult:
        """Run market review once and keep report/snapshot on the same overview."""
        logger.info("========== \u5f00\u59cbmarket reviewanalyze ==========")

        # 1. \u83b7\u53d6market\u6982\u89c8
        overview = self.get_market_overview()

        # 2. searchmarketnews
        news = self.search_market_news()
        news = self._merge_persisted_market_intelligence(news)

        # 3. \u751f\u6210\u590d\u76d8report
        report = self.generate_market_review(overview, news)
        snapshot = self.build_market_light_snapshot(overview) if self._supports_market_light() else None
        structured_payload = self.build_market_review_payload(
            overview,
            news,
            report,
            snapshot,
        )

        logger.info("========== market reviewanalysis completed ==========")

        return MarketLightReviewResult(
            overview=overview,
            report=report,
            market_light_snapshot=snapshot,
            structured_payload=structured_payload,
        )

    def _merge_persisted_market_intelligence(self, news: List) -> List:
        """Merge local persisted market intelligence and search news with bounded prompt/payload slot preservation."""
        search_news = list(news or [])
        merged_local = []
        seen_urls = {
            self._get_news_field(item, "url")
            for item in search_news
            if self._get_news_field(item, "url")
        }
        try:
            service = IntelligenceService(config=self.config)
            service.refresh_auto_sources()
            payload = service.list_items(
                scope_type="market",
                market=self.region,
                published_days=max(1, int(self.config.get_effective_news_window_days() or 1)),
                page=1,
                page_size=6,
            )
            for item in payload.get("items", []):
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "")
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)
                merged_local.append({
                    "title": item.get("title") or "\u672a\u547d\u540d\u8d44\u8baf",
                    "snippet": item.get("summary") or "",
                    "source": item.get("source") or item.get("source_name") or "local-intel",
                    "published_date": item.get("published_at") or "",
                    "url": "" if url.startswith("no-url:intel:") else url,
                })
        except Exception as exc:
            logger.debug("[\u5927\u76d8] %s action=load_local_intelligence status=failed error=%s", self._log_context(), exc)
        merged_news = []
        merged_local_index = 0
        merged_search_index = 0
        while merged_local_index < len(merged_local) or merged_search_index < len(search_news):
            if merged_local_index < len(merged_local):
                merged_news.append(merged_local[merged_local_index])
                merged_local_index += 1
            if merged_search_index < len(search_news):
                merged_news.append(search_news[merged_search_index])
                merged_search_index += 1
        return merged_news

    def run_daily_review(self) -> str:
        """
        \u6267\u884c\u6bcf\u65e5market review\u6d41\u7a0b

        Returns:
            \u590d\u76d8report\u6587\u672c
        """
        return self.run_daily_review_with_snapshot().report

    def run_daily_review_with_snapshot(self) -> MarketLightReviewResult:
        """Run daily review and return the report plus its structured Market Light snapshot."""
        return self._run_daily_review_parts()


# \u6d4b\u8bd5\u5165\u53e3
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    )

    analyzer = MarketAnalyzer()

    # \u6d4b\u8bd5\u83b7\u53d6market\u6982\u89c8
    overview = analyzer.get_market_overview()
    print(f"\n=== market\u6982\u89c8 ===")
    print(f"date: {overview.date}")
    print(f"indexcount: {len(overview.indices)}")
    for idx in overview.indices:
        print(f"  {idx.name}: {idx.current:.2f} ({idx.change_pct:+.2f}%)")
    print(f"\u4e0a\u6da8: {overview.up_count} | \u4e0b\u8dcc: {overview.down_count}")
    print(f"amount: {overview.total_amount:.0f}\u4ebf")

    # \u6d4b\u8bd5\u751f\u6210\u6a21\u677freport
    report = analyzer._generate_template_review(overview, [])
    print(f"\n=== \u590d\u76d8report ===")
    print(report)
