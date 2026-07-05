# -*- coding: utf-8 -*-
"""Market strategy blueprints for CN/HK/US daily market recap."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class StrategyDimension:
    """Single strategy dimension used by market recap prompts."""

    name: str
    objective: str
    checkpoints: List[str]


@dataclass(frozen=True)
class MarketStrategyBlueprint:
    """Region specific market strategy blueprint."""

    region: str
    title: str
    positioning: str
    principles: List[str]
    dimensions: List[StrategyDimension]
    action_framework: List[str]

    def to_prompt_block(self) -> str:
        """Render blueprint as prompt instructions."""
        principles_text = "\n".join([f"- {item}" for item in self.principles])
        action_text = "\n".join([f"- {item}" for item in self.action_framework])

        dims = []
        for dim in self.dimensions:
            checkpoints = "\n".join([f"  - {cp}" for cp in dim.checkpoints])
            dims.append(f"- {dim.name}: {dim.objective}\n{checkpoints}")
        dimensions_text = "\n".join(dims)

        return (
            f"## Strategy Blueprint: {self.title}\n"
            f"{self.positioning}\n\n"
            f"### Strategy Principles\n{principles_text}\n\n"
            f"### Analysis Dimensions\n{dimensions_text}\n\n"
            f"### Action Framework\n{action_text}"
        )

    def to_markdown_block(self) -> str:
        """Render blueprint as markdown section for template fallback report."""
        dims = "\n".join([f"- **{dim.name}**: {dim.objective}" for dim in self.dimensions])
        section_title = "### VI. Strategy Framework" if self.region == "us" else "### \u516d、strategy\u6846\u67b6"
        return f"{section_title}\n{dims}\n"


CN_BLUEPRINT = MarketStrategyBlueprint(
    region="cn",
    title="A-sharemarket\u4e09\u6bb5\u5f0f\u590d\u76d8strategy",
    positioning="\u805a\u7126index\u8d8b\u52bf、\u8d44\u91d1\u535a\u5f08\u4e0esector\u8f6e\u52a8; \u5f62\u6210\u6b21\u65e5\u4ea4\u6613\u8ba1\u5212.",
    principles=[
        "\u5148\u770bindex\u65b9\u5411; \u518d\u770b\u91cf\u80fd\u7ed3\u6784; \u6700\u540e\u770bsector\u6301\u7eed.",
        "\u7ed3\u8bba\u5fc5\u987b\u6620\u5c04\u5230\u4ed3characters、\u8282\u594f\u4e0e\u98ce\u9669\u63a7\u5236\u52a8\u4f5c.",
        "\u5224\u65ad\u4f7f\u7528\u5f53\u65e5\u6570\u636e\u4e0e\u8fd13\u65e5news; \u4e0d\u81c6\u6d4b\u672a\u9a8c\u8bc1info.",
    ],
    dimensions=[
        StrategyDimension(
            name="\u8d8b\u52bf\u7ed3\u6784",
            objective="\u5224\u65admarket\u5904\u4e8e\u4e0a\u5347、\u9707\u8361\u8fd8\u662f\u9632\u5b88\u9636\u6bb5.",
            checkpoints=["\u4e0a\u8bc1/\u6df1\u8bc1/\u521b\u4e1a\u677f\u662f\u5426\u540c\u5411", "\u653e\u91cf\u4e0a\u6da8or\u7f29\u91cf\u4e0b\u8dcc\u662f\u5426\u6210\u7acb", "\u5173\u952e\u652f\u6491\u963b\u529b\u662f\u5426\u88ab\u7a81\u7834"],
        ),
        StrategyDimension(
            name="\u8d44\u91d1\u60c5\u7eea",
            objective="\u8bc6\u522b\u77ed\u7ebf\u98ce\u9669Slightly \u597d\u4e0e\u60c5\u7eea\u6e29\u5ea6.",
            checkpoints=["change\u5bb6\u6570\u4e0echange\u505c\u7ed3\u6784", "amount\u662f\u5426\u6269\u5f20", "Highcharacters\u80a1\u662f\u5426\u51fa\u73b0\u5206\u6b67"],
        ),
        StrategyDimension(
            name="\u4e3b\u7ebfsector",
            objective="\u63d0\u70bc\u53ef\u4ea4\u6613\u4e3b\u7ebf\u4e0e\u89c4\u907f\u65b9\u5411.",
            checkpoints=["\u9886\u6da8sector\u662f\u5426\u5177\u5907\u4e8b\u4ef6\u50ac\u5316", "sector\u5185\u90e8\u662f\u5426\u6709\u9f99\u5934\u5e26\u52a8", "\u9886\u8dccsector\u662f\u5426\u6269\u6563"],
        ),
    ],
    action_framework=[
        "\u8fdb\u653b: index\u5171\u632f\u4e0a\u884c + amount\u653e\u5927 + \u4e3b\u7ebf\u5f3a\u5316.",
        "\u5747\u8861: index\u5206\u5316or\u7f29\u91cf\u9707\u8361; Control position size\u5e76waiting\u786e\u8ba4.",
        "\u9632\u5b88: index\u8f6c\u5f31 + \u9886\u8dcc\u6269\u6563; \u4f18\u5148\u98ce\u63a7\u4e0e\u51cf\u4ed3.",
    ],
)

US_BLUEPRINT = MarketStrategyBlueprint(
    region="us",
    title="US Market Regime Strategy",
    positioning="Focus on index trend, macro narrative, and sector rotation to define next-session risk posture.",
    principles=[
        "Read market regime from S&P 500, Nasdaq, and Dow alignment first.",
        "Separate beta move from theme-driven alpha rotation.",
        "Translate recap into actionable risk-on/risk-off stance with clear invalidation points.",
    ],
    dimensions=[
        StrategyDimension(
            name="Trend Regime",
            objective="Classify the market as momentum, range, or risk-off.",
            checkpoints=[
                "Are SPX/NDX/DJI directionally aligned",
                "Did volume confirm the move",
                "Are key index levels reclaimed or lost",
            ],
        ),
        StrategyDimension(
            name="Macro & Flows",
            objective="Map policy/rates narrative into equity risk appetite.",
            checkpoints=[
                "Treasury yield and USD implications",
                "Breadth and leadership concentration",
                "Defensive vs growth factor rotation",
            ],
        ),
        StrategyDimension(
            name="Sector Themes",
            objective="Identify persistent leaders and vulnerable laggards.",
            checkpoints=[
                "AI/semiconductor/software trend persistence",
                "Energy/financials sensitivity to macro data",
                "Volatility signals from VIX and large-cap earnings",
            ],
        ),
    ],
    action_framework=[
        "Risk-on: broad index breakout with expanding participation.",
        "Neutral: mixed index signals; focus on selective relative strength.",
        "Risk-off: failed breakouts and rising volatility; prioritize capital preservation.",
    ],
)

HK_BLUEPRINT = MarketStrategyBlueprint(
    region="hk",
    title="HK stockmarket\u4e09\u6bb5\u5f0f\u590d\u76d8strategy",
    positioning="\u805a\u7126\u6052\u751findex\u8d8b\u52bf、\u5357\u5411\u8d44\u91d1\u535a\u5f08\u4e0esector\u8f6e\u52a8; \u5f62\u6210\u6b21\u65e5\u4ea4\u6613\u8ba1\u5212.",
    principles=[
        "\u5148\u770b\u6052\u6307/\u6052\u79d1/\u56fd\u4f01index\u65b9\u5411; \u518d\u770b\u5357\u5411\u8d44\u91d1\u60c5\u7eea; \u6700\u540e\u770bsector\u6301\u7eed.",
        "\u7ed3\u8bba\u5fc5\u987b\u6620\u5c04\u5230\u4ed3characters、\u8282\u594f\u4e0e\u98ce\u9669\u63a7\u5236\u52a8\u4f5c.",
        "\u5224\u65ad\u4f7f\u7528\u5f53\u65e5\u6570\u636e\u4e0e\u8fd13\u65e5news; \u4e0d\u81c6\u6d4b\u672a\u9a8c\u8bc1info.",
    ],
    dimensions=[
        StrategyDimension(
            name="\u8d8b\u52bf\u7ed3\u6784",
            objective="\u5224\u65admarket\u5904\u4e8e\u4e0a\u5347、\u9707\u8361\u8fd8\u662f\u9632\u5b88\u9636\u6bb5.",
            checkpoints=["\u6052\u6307/\u6052\u79d1/\u56fd\u4f01index\u662f\u5426\u540c\u5411", "\u653e\u91cf\u4e0a\u6da8or\u7f29\u91cf\u4e0b\u8dcc\u662f\u5426\u6210\u7acb", "\u5173\u952e\u652f\u6491\u963b\u529b\u662f\u5426\u88ab\u7a81\u7834"],
        ),
        StrategyDimension(
            name="\u8d44\u91d1\u60c5\u7eea",
            objective="\u8bc6\u522b\u5357\u5411\u8d44\u91d1\u98ce\u9669Slightly \u597d\u4e0e\u60c5\u7eea\u6e29\u5ea6.",
            checkpoints=["\u5357\u5411\u8d44\u91d1\u51c0\u6d41\u5165\u65b9\u5411\u4e0e\u89c4\u6a21", "\u6e2f\u5143\u6c47\u7387\u4e0e\u5185\u5730\u653f\u7b56\u542b\u4e49", "market\u5e7f\u5ea6\u4e0e\u9f99\u5934\u96c6Medium\u5ea6"],
        ),
        StrategyDimension(
            name="\u4e3b\u7ebfsector",
            objective="\u63d0\u70bc\u53ef\u4ea4\u6613\u4e3b\u7ebf\u4e0e\u89c4\u907f\u65b9\u5411.",
            checkpoints=["\u79d1\u6280/\u4e92\u8054\u7f51\u5e73\u53f0\u8d8b\u52bf\u6301\u7eed", "\u91d1\u878d/\u5730\u4ea7\u5bf9\u653f\u7b56\u8f6c\u5411\u7684\u654f\u611f\u5ea6", "\u9632\u5fa1\u4e0e\u6210\u957f\u56e0\u5b50\u8f6e\u52a8"],
        ),
    ],
    action_framework=[
        "\u8fdb\u653b: \u6052\u6307\u5171\u632f\u4e0a\u884c + \u5357\u5411\u8d44\u91d1\u6301\u7eed\u6d41\u5165 + \u4e3b\u7ebf\u5f3a\u5316.",
        "\u5747\u8861: index\u5206\u5316or\u7f29\u91cf\u9707\u8361; Control position size\u5e76waiting\u786e\u8ba4.",
        "\u9632\u5b88: index\u8f6c\u5f31 + \u6ce2\u52a8\u7387\u4e0a\u5347; \u4f18\u5148\u98ce\u63a7\u4e0e\u51cf\u4ed3.",
    ],
)


JP_BLUEPRINT = MarketStrategyBlueprint(
    region="jp",
    title="\u65e5\u672cmarket\u4e09\u6bb5\u5f0f\u590d\u76d8strategy",
    positioning="\u805a\u7126\u65e5\u7ecf225、\u4e1c\u8bc1index、\u6c47\u7387\u4e0e\u5168\u7403\u98ce\u9669Slightly \u597d; \u5f62\u6210\u6b21\u65e5\u4ea4\u6613\u8ba1\u5212.",
    principles=[
        "\u5148\u770b\u65e5\u7ecf225\u4e0eTOPIX\u662f\u5426\u540c\u5411; \u518d\u770b\u65e5\u5143、\u534a\u5bfc\u4f53/\u51fa\u53e3\u94fe\u4e0e\u91d1\u878d\u80a1\u8868\u73b0.",
        "\u628aindex\u7ed3\u8bba\u6620\u5c04\u5230\u4ed3characters、\u8282\u594f\u4e0e\u98ce\u9669\u63a7\u5236\u52a8\u4f5c.",
        "\u53ea\u57fa\u4e8e\u53ef\u5f97index、news\u548cprice\u884c\u4e3a\u5224\u65ad; \u4e0d\u81c6\u9020market\u5e7f\u5ea6orsector\u7edf\u8ba1.",
    ],
    dimensions=[
        StrategyDimension(
            name="\u8d8b\u52bf\u7ed3\u6784",
            objective="\u5224\u65ad\u65e5\u672cmarket\u5904\u4e8e\u4e0a\u653b、\u9707\u8361\u8fd8\u662f\u9632\u5b88\u9636\u6bb5.",
            checkpoints=["\u65e5\u7ecf225/TOPIX\u662f\u5426\u540c\u5411", "index\u662f\u5426\u7a81\u7834or\u8dcc\u7834\u5173\u952e\u533a\u95f4", "\u5927\u76d8\u6743\u91cd\u4e0e\u6210\u957f\u94fe\u662f\u5426\u5171\u632f"],
        ),
        StrategyDimension(
            name="\u5b8f\u89c2\u4e0e\u6c47\u7387",
            objective="\u8bc6\u522b\u65e5\u5143、\u5229\u7387\u548c\u5168\u7403\u98ce\u9669Slightly \u597d\u5bf9\u6743\u76camarket\u7684\u5f71\u54cd.",
            checkpoints=["\u65e5\u5143\u65b9\u5411\u5bf9\u51fa\u53e3\u94fe\u7684\u5f71\u54cd", "\u65e5\u672c\u592e\u884c\u548c\u7f8e\u503a\u5229\u7387\u53d9\u4e8b", "\u6d77\u5916\u79d1\u6280\u80a1\u4e0e\u534a\u5bfc\u4f53\u94fe\u6620\u5c04"],
        ),
        StrategyDimension(
            name="\u4e3b\u9898\u7ebf\u7d22",
            objective="\u63d0\u70bc\u53ef\u5ef6\u7eed\u4e3b\u7ebf\u4e0e\u9700\u8981\u89c4\u907f\u7684\u62e5\u6324\u65b9\u5411.",
            checkpoints=["\u534a\u5bfc\u4f53/\u81ea\u52a8\u5316/\u6c7d\u8f66\u94fe\u6301\u7eed", "\u91d1\u878d\u4e0e\u5185\u9700\u80a1\u662f\u5426\u8f6e\u52a8", "news\u50ac\u5316\u662f\u5426\u652f\u6491price\u884c\u4e3a"],
        ),
    ],
    action_framework=[
        "\u8fdb\u653b: \u4e3b\u8981index\u5171\u632f\u4e0a\u884c + \u5916\u90e8\u98ce\u9669Slightly \u597d\u6539\u5584 + \u4e3b\u7ebf\u5f3a\u5316.",
        "\u5747\u8861: index\u5206\u5316or\u6c47\u7387\u6270\u52a8; \u964dLow\u8ffd\u6da8\u5e76waiting\u786e\u8ba4.",
        "\u9632\u5b88: \u4e3b\u8981index\u8f6c\u5f31or\u5916\u90e8\u98ce\u9669\u5347\u6e29; \u4f18\u5148Control position size.",
    ],
)

KR_BLUEPRINT = MarketStrategyBlueprint(
    region="kr",
    title="\u97e9\u56fdmarket\u4e09\u6bb5\u5f0f\u590d\u76d8strategy",
    positioning="\u805a\u7126 KOSPI、KOSDAQ、\u534a\u5bfc\u4f53\u6743\u91cd\u4e0e\u5168\u7403\u79d1\u6280\u98ce\u9669Slightly \u597d; \u5f62\u6210\u6b21\u65e5\u4ea4\u6613\u8ba1\u5212.",
    principles=[
        "\u5148\u770b KOSPI/KOSDAQ \u662f\u5426\u540c\u5411; \u518d\u770b\u4e09\u661f\u7535\u5b50、SK \u6d77\u529b\u58eb\u7b49\u6743\u91cd\u7ebf\u7d22.",
        "\u533a\u5206index beta、\u534a\u5bfc\u4f53\u5468\u671f\u548c\u6210\u957f\u80a1\u98ce\u9669Slightly \u597d\u7684\u8d21\u732e.",
        "\u53ea\u57fa\u4e8e\u53ef\u5f97index、news\u548cprice\u884c\u4e3a\u5224\u65ad; \u4e0d\u81c6\u9020market\u5e7f\u5ea6orsector\u7edf\u8ba1.",
    ],
    dimensions=[
        StrategyDimension(
            name="\u8d8b\u52bf\u7ed3\u6784",
            objective="\u5224\u65ad\u97e9\u56fdmarket\u5904\u4e8e\u4e0a\u653b、\u9707\u8361\u8fd8\u662f\u9632\u5b88\u9636\u6bb5.",
            checkpoints=["KOSPI/KOSDAQ \u662f\u5426\u540c\u5411", "\u6743\u91cd\u80a1\u662f\u5426\u652f\u6491index", "\u5173\u952e\u652f\u6491\u963b\u529b\u662f\u5426\u88ab\u7a81\u7834"],
        ),
        StrategyDimension(
            name="\u79d1\u6280\u5468\u671f",
            objective="\u8bc6\u522b\u534a\u5bfc\u4f53、AI \u786c\u4ef6\u548c\u5168\u7403\u79d1\u6280\u80a1\u5bf9\u97e9\u56fdmarket\u7684\u6620\u5c04.",
            checkpoints=["\u5b58\u50a8/\u534a\u5bfc\u4f53\u94fenews\u50ac\u5316", "US stock\u79d1\u6280\u65b9\u5411\u8054\u52a8", "\u5916\u8d44\u98ce\u9669Slightly \u597d\u53d8\u5316"],
        ),
        StrategyDimension(
            name="\u4e3b\u9898\u7ebf\u7d22",
            objective="\u63d0\u70bc\u53ef\u5ef6\u7eed\u4e3b\u7ebf\u4e0e\u9700\u8981\u89c4\u907f\u7684\u62e5\u6324\u65b9\u5411.",
            checkpoints=["\u7535\u6c60/\u6c7d\u8f66/\u4e92\u8054\u7f51\u662f\u5426\u8f6e\u52a8", "KOSDAQ \u6210\u957f\u80a1\u98ce\u9669Slightly \u597d", "news\u50ac\u5316\u662f\u5426\u652f\u6491price\u884c\u4e3a"],
        ),
    ],
    action_framework=[
        "\u8fdb\u653b: KOSPI/KOSDAQ \u5171\u632f\u4e0a\u884c + \u79d1\u6280\u6743\u91cd\u786e\u8ba4 + \u5916\u90e8\u98ce\u9669Slightly \u597d\u6539\u5584.",
        "\u5747\u8861: indexor\u6743\u91cd\u80a1\u5206\u5316; Control position size\u5e76waiting\u786e\u8ba4.",
        "\u9632\u5b88: \u79d1\u6280\u6743\u91cd\u8f6c\u5f31or\u5916\u90e8\u98ce\u9669\u5347\u6e29; \u4f18\u5148\u63a7\u5236\u56de\u64a4.",
    ],
)

def get_market_strategy_blueprint(region: str) -> MarketStrategyBlueprint:
    """Return strategy blueprint by market region."""
    if region == "us":
        return US_BLUEPRINT
    if region == "hk":
        return HK_BLUEPRINT
    if region == "jp":
        return JP_BLUEPRINT
    if region == "kr":
        return KR_BLUEPRINT
    return CN_BLUEPRINT
