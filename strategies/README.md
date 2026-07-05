# Trading Strategy Directory

This directory stores natural-language trading strategy files in YAML format. At startup, the system automatically loads every `.yaml` file in this directory.

For users and documentation, these capabilities are called strategies. In code, configuration, and API fields, they are named `skill`; treat a skill as a reusable strategy capability package.

## How To Write A Custom Strategy Skill

Create a `.yaml` file and describe the trading strategy in natural language. No code is required.

### Minimal Template

```yaml
name: my_strategy          # Unique identifier, English with underscores
display_name: My Strategy  # Display name
description: Briefly describe what the strategy is for

instructions: |
  Describe your strategy here.
  Write the decision criteria, entry conditions, exit conditions, and risk controls in natural language.
  You can reference tool names such as get_daily_history and analyze_trend to guide which data the AI should use.
```

### Full Template

```yaml
name: my_strategy
display_name: My Strategy
description: Briefly describe the market scenario where the strategy applies

# Strategy category: trend, pattern, reversal, or framework
category: trend

# Optional linked core trading rule numbers, 1-7
core_rules: [1, 2]

# Optional tools required by the strategy
# Available tools: get_daily_history, analyze_trend, get_realtime_quote,
#                  get_sector_rankings, search_stock_news, get_stock_info
required_tools:
  - get_daily_history
  - analyze_trend

# Optional aliases for natural-language strategy selection, such as /ask routing
aliases: [my setup, my model]

# Optional metadata for default behavior
# default_active: whether the strategy belongs to the default active skill set
# default_router: whether the strategy belongs to the router fallback skill set
# default_priority: display/sort priority, lower values appear earlier
# market_regimes: market-state tags where this skill is preferred
default_active: true
default_router: false
default_priority: 100
market_regimes: [trending_up]

# Detailed strategy instructions in natural language; Markdown is supported
instructions: |
  **My Strategy Name**

  Decision criteria:

  1. **Condition one**:
     - Use `analyze_trend` to inspect moving-average alignment.
     - Describe the trend features you expect to see.

  2. **Condition two**:
     - Describe volume requirements.

  Score adjustments:
  - Suggested sentiment_score adjustment when conditions are met
  - Mention the strategy name in `buy_reason`
```

### Core Trading Rule Reference

| Number | Rule |
| --- | --- |
| 1 | Strict entry: only consider entry when bias is below 5%. |
| 2 | Trend trading: MA5 > MA10 > MA20 bullish alignment. |
| 3 | Efficiency first: volume confirms trend validity. |
| 4 | Entry preference: prioritize pullbacks to moving-average support. |
| 5 | Risk filter: major negative news can veto the setup. |
| 6 | Volume-price alignment: volume should validate price movement. |
| 7 | Strong trend exception: sector leaders may allow slightly wider standards. |

## Custom Strategy Directory

In addition to this built-in directory, you can specify an extra custom strategy directory with an environment variable:

```env
AGENT_SKILL_DIR=./my_skills
```

The system loads both built-in and custom strategies. If names conflict, the custom strategy overrides the built-in one.

The environment variable is still named `AGENT_SKILL_DIR` because of the internal naming convention; in product terms, it means custom strategy directory.
