# -*- coding: utf-8 -*-
"""Helpers for report output language selection and localization."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from src.schemas.decision_scale import signal_key_for_score

SUPPORTED_REPORT_LANGUAGES = ("zh", "en", "ko")

_REPORT_LANGUAGE_ALIASES = {
    "zh-cn": "zh",
    "zh_cn": "zh",
    "zh-hans": "zh",
    "zh_hans": "zh",
    "zh-tw": "zh",
    "zh_tw": "zh",
    "cn": "zh",
    "chinese": "zh",
    "english": "en",
    "en-us": "en",
    "en_us": "en",
    "en-gb": "en",
    "en_gb": "en",
    "korean": "ko",
    "kr": "ko",
    "ko-kr": "ko",
    "ko_kr": "ko",
}

_OPERATION_ADVICE_CANONICAL_MAP = {
    '\u5f3a\u70c8\u4e70\u5165': "strong_buy",
    "strong buy": "strong_buy",
    "strong_buy": "strong_buy",
    '\u4e70\u5165': "buy",
    "buy": "buy",
    '\u52a0\u4ed3': "buy",
    "accumulate": "buy",
    "add position": "buy",
    '\u6301\u6709': "hold",
    '\u6d17\u76d8\u89c2\u5bdf': "hold",
    '\u89c2\u5bdf': "hold",
    "hold": "hold",
    'Watch': "watch",
    "watch": "watch",
    "wait": "watch",
    "wait and see": "watch",
    '\u51cf\u4ed3': "reduce",
    "reduce": "reduce",
    "trim": "reduce",
    '\u5356\u51fa': "sell",
    "sell": "sell",
    '\u5f3a\u70c8\u5356\u51fa': "strong_sell",
    "strong sell": "strong_sell",
    "strong_sell": "strong_sell",
    '\uc801\uadf9 \ub9e4\uc218': "strong_buy",
    '\ub9e4\uc218': "buy",
    '\ubcf4\uc720': "hold",
    '\ubcf4\uc720 \uad00\ucc30': "hold",
    '\uad00\ub9dd': "watch",
    '\ube44\uc911\ucd95\uc18c': "reduce",
    '\ub9e4\ub3c4': "sell",
    '\uc801\uadf9 \ub9e4\ub3c4': "strong_sell",
}

_OPERATION_ADVICE_TRANSLATIONS = {'strong_buy': {'zh': 'Strong Buy', 'en': 'Strong Buy', 'ko': 'Strong Buy'},
 'buy': {'zh': 'Buy', 'en': 'Buy', 'ko': 'Buy'},
 'hold': {'zh': 'Hold', 'en': 'Hold', 'ko': 'Hold'},
 'watch': {'zh': 'Watch', 'en': 'Watch', 'ko': 'Watch'},
 'reduce': {'zh': 'Reduce', 'en': 'Reduce', 'ko': 'Reduce'},
 'sell': {'zh': 'Sell', 'en': 'Sell', 'ko': 'Sell'},
 'strong_sell': {'zh': 'Strong Sell', 'en': 'Strong Sell', 'ko': 'Strong Sell'}}

_TREND_PREDICTION_CANONICAL_MAP = {
    '\u5f3a\u52bf\u7a7a\u5934': "strong_bearish",
    '\u5f3a\u70c8\u770b\u591a': "strong_bullish",
    "strong bullish": "strong_bullish",
    "very bullish": "strong_bullish",
    '\u5f3a\u52bf\u591a\u5934': "strong_bullish",
    '\u591a\u5934\u6392\u5217': "bullish",
    '\u7a7a\u5934\u6392\u5217': "bearish",
    '\u5f31\u52bf\u591a\u5934': "bullish",
    '\u5f31\u52bf\u7a7a\u5934': "bearish",
    '\u770b\u591a': "bullish",
    '\u76d8\u6574': "sideways",
    "bullish": "bullish",
    "uptrend": "bullish",
    '\u9707\u8361': "sideways",
    "neutral": "sideways",
    "sideways": "sideways",
    "range-bound": "sideways",
    '\u770b\u7a7a': "bearish",
    "bearish": "bearish",
    "downtrend": "bearish",
    '\u5f3a\u70c8\u770b\u7a7a': "strong_bearish",
    "strong bearish": "strong_bearish",
    "very bearish": "strong_bearish",
    '\uac15\ud55c \uc0c1\uc2b9': "strong_bullish",
    '\uc0c1\uc2b9': "bullish",
    '\ud6a1\ubcf4': "sideways",
    '\ud558\ub77d': "bearish",
    '\uac15\ud55c \ud558\ub77d': "strong_bearish",
}

_TREND_PREDICTION_TRANSLATIONS = {'strong_bullish': {'zh': 'Strong Bullish', 'en': 'Strong Bullish', 'ko': 'Strong Bullish'},
 'bullish': {'zh': 'Bullish', 'en': 'Bullish', 'ko': 'Bullish'},
 'sideways': {'zh': 'Sideways', 'en': 'Sideways', 'ko': 'Sideways'},
 'bearish': {'zh': 'Bearish', 'en': 'Bearish', 'ko': 'Bearish'},
 'strong_bearish': {'zh': 'Strong Bearish', 'en': 'Strong Bearish', 'ko': 'Strong Bearish'}}

_CONFIDENCE_LEVEL_CANONICAL_MAP = {
    'High': "high",
    "high": "high",
    'Medium': "medium",
    "medium": "medium",
    "med": "medium",
    'Low': "low",
    "low": "low",
    '\ub192\uc74c': "high",
    '\ubcf4\ud1b5': "medium",
    '\ub0ae\uc74c': "low",
}

_CONFIDENCE_LEVEL_TRANSLATIONS = {'high': {'zh': 'High', 'en': 'High', 'ko': 'High'},
 'medium': {'zh': 'Medium', 'en': 'Medium', 'ko': 'Medium'},
 'low': {'zh': 'Low', 'en': 'Low', 'ko': 'Low'}}

_CHIP_HEALTH_CANONICAL_MAP = {
    '\u5065\u5eb7': "healthy",
    "healthy": "healthy",
    '\u4e00\u822c': "average",
    "average": "average",
    '\u8b66\u60d5': "caution",
    "caution": "caution",
    '\uc591\ud638': "healthy",
    '\ubcf4\ud1b5': "average",
    '\uc8fc\uc758': "caution",
}

_CHIP_HEALTH_TRANSLATIONS = {'healthy': {'zh': 'Healthy', 'en': 'Healthy', 'ko': 'Healthy'},
 'average': {'zh': 'Average', 'en': 'Average', 'ko': 'Average'},
 'caution': {'zh': 'Caution', 'en': 'Caution', 'ko': 'Caution'}}

_BIAS_STATUS_CANONICAL_MAP = {
    '\u5b89\u5168': "safe",
    "safe": "safe",
    '\u8b66\u6212': "caution",
    '\u8b66\u60d5': "caution",
    "caution": "caution",
    '\u5371\u9669': "danger",
    "risk": "danger",
    "danger": "danger",
    '\uc548\uc804': "safe",
    '\uacbd\uacc4': "caution",
    '\uc704\ud5d8': "danger",
}

_BIAS_STATUS_TRANSLATIONS = {'safe': {'zh': 'Safe', 'en': 'Safe', 'ko': 'Safe'},
 'caution': {'zh': 'Caution', 'en': 'Caution', 'ko': 'Caution'},
 'danger': {'zh': 'Danger', 'en': 'Danger', 'ko': 'Danger'}}

_PLACEHOLDER_BY_LANGUAGE = {'zh': 'TBD', 'en': 'TBD', 'ko': 'TBD'}

_UNKNOWN_BY_LANGUAGE = {'zh': 'Unknown', 'en': 'Unknown', 'ko': 'Unknown'}

_NO_DATA_BY_LANGUAGE = {'zh': 'Data unavailable', 'en': 'Data unavailable', 'ko': 'Data unavailable'}

_CHIP_UNAVAILABLE_BY_LANGUAGE = {'zh': 'Chip distribution is disabled or temporarily unavailable; chip signals were not used.',
 'en': 'Chip distribution is disabled or temporarily unavailable; chip signals were not used.',
 'ko': 'Chip distribution is disabled or temporarily unavailable; chip signals were not used.'}

_CHIP_PLACEHOLDER_EXACT = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "tbd",
    '\u6570\u636e\u7f3a\u5931',
    '\u672a\u77e5',
    '\u6682\u65e0',
    '\u5f85\u8865\u5145',
}

_CHIP_PLACEHOLDER_HINTS = (
    '\u6570\u636e\u7f3a\u5931',
    '\u65e0\u6cd5\u5224\u65ad',
    "data unavailable",
    "unavailable",
    "not available",
    "missing",
    "not supported",
)

_CHIP_METRIC_KEYS = ("profit_ratio", "avg_cost", "concentration")
_CHIP_UNAVAILABLE_REASON_KEYS = (
    "chip_unavailable_reason",
    "unavailable_reason",
    "chip_unavailable",
)

_GENERIC_STOCK_NAME_BY_LANGUAGE = {'zh': 'Unnamed Stock', 'en': 'Unnamed Stock', 'ko': 'Unnamed Stock'}

_REPORT_LABELS: Dict[str, Dict[str, str]] = {'zh': {'dashboard_title': 'Decision Dashboard',
        'brief_title': 'Decision Brief',
        'analyzed_prefix': 'Analyzed',
        'stock_unit': 'stocks',
        'stock_unit_compact': 'stocks',
        'buy_label': 'Buy',
        'watch_label': 'Watch',
        'sell_label': 'Sell',
        'summary_heading': 'Summary',
        'info_heading': 'Key Updates',
        'sentiment_summary_label': 'Sentiment',
        'earnings_outlook_label': 'Earnings Outlook',
        'risk_alerts_label': 'Risk Alerts',
        'positive_catalysts_label': 'Positive Catalysts',
        'latest_news_label': 'Latest News',
        'core_conclusion_heading': 'Core Conclusion',
        'one_sentence_label': 'One-line Decision',
        'time_sensitivity_label': 'Time Sensitivity',
        'default_time_sensitivity': 'This week',
        'position_status_label': 'Position',
        'action_advice_label': 'Action',
        'no_position_label': 'No Position',
        'has_position_label': 'Holding',
        'continue_holding': 'Continue holding',
        'market_snapshot_heading': 'Market Snapshot',
        'close_label': 'Close',
        'prev_close_label': 'Prev Close',
        'open_label': 'Open',
        'high_label': 'High',
        'low_label': 'Low',
        'change_pct_label': 'Change %',
        'change_amount_label': 'Change',
        'amplitude_label': 'Amplitude',
        'volume_label': 'Volume',
        'amount_label': 'Turnover',
        'current_price_label': 'Price',
        'volume_ratio_label': 'Volume Ratio',
        'turnover_rate_label': 'Turnover Rate',
        'source_label': 'Source',
        'data_perspective_heading': 'Data View',
        'ma_alignment_label': 'MA Alignment',
        'bullish_alignment_label': 'Bullish Alignment',
        'yes_label': 'Yes',
        'no_label': 'No',
        'trend_strength_label': 'Trend Strength',
        'price_metrics_label': 'Price Metrics',
        'ma5_label': 'MA5',
        'ma10_label': 'MA10',
        'ma20_label': 'MA20',
        'bias_ma5_label': 'Bias (MA5)',
        'support_level_label': 'Support',
        'resistance_level_label': 'Resistance',
        'chip_label': 'Chip Structure',
        'phase_decision_heading': 'Phase Decision Guardrail',
        'action_window_label': 'Action Window',
        'immediate_action_label': 'Current Action',
        'watch_conditions_label': 'Watch Conditions',
        'next_check_time_label': 'Next Check',
        'confidence_reason_label': 'Confidence Reason',
        'data_limitations_label': 'Data Limitations',
        'battle_plan_heading': 'Battle Plan',
        'ideal_buy_label': 'Ideal Entry',
        'secondary_buy_label': 'Secondary Entry',
        'stop_loss_label': 'Stop Loss',
        'take_profit_label': 'Target',
        'suggested_position_label': 'Position Size',
        'entry_plan_label': 'Entry Plan',
        'risk_control_label': 'Risk Control',
        'checklist_heading': 'Checklist',
        'failed_checks_heading': 'Failed Checks',
        'history_compare_heading': 'Historical Signal Comparison',
        'time_label': 'Time',
        'score_label': 'Score',
        'advice_label': 'Advice',
        'trend_label': 'Trend',
        'generated_at_label': 'Generated At',
        'report_time_label': 'Generated',
        'no_results': 'No analysis results',
        'report_title': 'Stock Analysis Report',
        'avg_score_label': 'Avg Score',
        'action_points_heading': 'Action Levels',
        'position_advice_heading': 'Position Advice',
        'analysis_model_label': 'Model',
        'not_investment_advice': 'AI-generated content for reference only. Not investment advice.',
        'details_report_hint': 'See detailed report:',
        'financial_summary_heading': 'Financial Summary',
        'report_date_label': 'Report Date',
        'revenue_label': 'Revenue',
        'net_profit_label': 'Net Profit (Parent)',
        'operating_cash_flow_label': 'Operating Cash Flow',
        'roe_label': 'ROE',
        'revenue_yoy_label': 'Revenue YoY',
        'net_profit_yoy_label': 'Net Profit YoY',
        'gross_margin_label': 'Gross Margin',
        'shareholder_return_heading': 'Shareholder Return',
        'ttm_cash_dividend_label': 'TTM Cash Dividend / Share (Pre-tax)',
        'ttm_event_count_label': 'TTM Dividend Events',
        'ttm_dividend_yield_label': 'TTM Dividend Yield',
        'latest_ex_dividend_label': 'Latest Ex-dividend Date',
        'institutional_flow_heading': 'Institutional Flows (3 Majors)',
        'institutional_flow_note': 'Positive = net buy, negative = net sell; unit: shares.',
        'inst_foreign_label': 'Foreign',
        'inst_trust_label': 'Inv. Trust',
        'inst_dealer_label': 'Dealer',
        'inst_total_label': 'Total (3 Majors)',
        'related_boards_heading': 'Related Boards',
        'industry_boards_heading': 'Industry Sectors',
        'concept_boards_heading': 'Concept Themes',
        'board_name_label': 'Board',
        'board_type_label': 'Type',
        'board_status_label': 'Status',
        'board_change_pct_label': 'Change %',
        'leading_board_label': 'Leading',
        'lagging_board_label': 'Lagging',
        'signal_attribution_heading': 'Signal Attribution',
        'attribution_weights_label': 'Attribution Weights',
        'technical_indicators_label': 'Technical Indicators',
        'news_sentiment_label': 'News Sentiment',
        'fundamentals_label': 'Fundamentals',
        'market_conditions_label': 'Market Conditions',
        'strongest_bullish_signal_label': 'Strongest Bullish Signal',
        'strongest_bearish_signal_label': 'Strongest Bearish Signal'},
 'en': {'dashboard_title': 'Decision Dashboard',
        'brief_title': 'Decision Brief',
        'analyzed_prefix': 'Analyzed',
        'stock_unit': 'stocks',
        'stock_unit_compact': 'stocks',
        'buy_label': 'Buy',
        'watch_label': 'Watch',
        'sell_label': 'Sell',
        'summary_heading': 'Summary',
        'info_heading': 'Key Updates',
        'sentiment_summary_label': 'Sentiment',
        'earnings_outlook_label': 'Earnings Outlook',
        'risk_alerts_label': 'Risk Alerts',
        'positive_catalysts_label': 'Positive Catalysts',
        'latest_news_label': 'Latest News',
        'core_conclusion_heading': 'Core Conclusion',
        'one_sentence_label': 'One-line Decision',
        'time_sensitivity_label': 'Time Sensitivity',
        'default_time_sensitivity': 'This week',
        'position_status_label': 'Position',
        'action_advice_label': 'Action',
        'no_position_label': 'No Position',
        'has_position_label': 'Holding',
        'continue_holding': 'Continue holding',
        'market_snapshot_heading': 'Market Snapshot',
        'close_label': 'Close',
        'prev_close_label': 'Prev Close',
        'open_label': 'Open',
        'high_label': 'High',
        'low_label': 'Low',
        'change_pct_label': 'Change %',
        'change_amount_label': 'Change',
        'amplitude_label': 'Amplitude',
        'volume_label': 'Volume',
        'amount_label': 'Turnover',
        'current_price_label': 'Price',
        'volume_ratio_label': 'Volume Ratio',
        'turnover_rate_label': 'Turnover Rate',
        'source_label': 'Source',
        'data_perspective_heading': 'Data View',
        'ma_alignment_label': 'MA Alignment',
        'bullish_alignment_label': 'Bullish Alignment',
        'yes_label': 'Yes',
        'no_label': 'No',
        'trend_strength_label': 'Trend Strength',
        'price_metrics_label': 'Price Metrics',
        'ma5_label': 'MA5',
        'ma10_label': 'MA10',
        'ma20_label': 'MA20',
        'bias_ma5_label': 'Bias (MA5)',
        'support_level_label': 'Support',
        'resistance_level_label': 'Resistance',
        'chip_label': 'Chip Structure',
        'phase_decision_heading': 'Phase Decision Guardrail',
        'action_window_label': 'Action Window',
        'immediate_action_label': 'Current Action',
        'watch_conditions_label': 'Watch Conditions',
        'next_check_time_label': 'Next Check',
        'confidence_reason_label': 'Confidence Reason',
        'data_limitations_label': 'Data Limitations',
        'battle_plan_heading': 'Battle Plan',
        'ideal_buy_label': 'Ideal Entry',
        'secondary_buy_label': 'Secondary Entry',
        'stop_loss_label': 'Stop Loss',
        'take_profit_label': 'Target',
        'suggested_position_label': 'Position Size',
        'entry_plan_label': 'Entry Plan',
        'risk_control_label': 'Risk Control',
        'checklist_heading': 'Checklist',
        'failed_checks_heading': 'Failed Checks',
        'history_compare_heading': 'Historical Signal Comparison',
        'time_label': 'Time',
        'score_label': 'Score',
        'advice_label': 'Advice',
        'trend_label': 'Trend',
        'generated_at_label': 'Generated At',
        'report_time_label': 'Generated',
        'no_results': 'No analysis results',
        'report_title': 'Stock Analysis Report',
        'avg_score_label': 'Avg Score',
        'action_points_heading': 'Action Levels',
        'position_advice_heading': 'Position Advice',
        'analysis_model_label': 'Model',
        'not_investment_advice': 'AI-generated content for reference only. Not investment advice.',
        'details_report_hint': 'See detailed report:',
        'financial_summary_heading': 'Financial Summary',
        'report_date_label': 'Report Date',
        'revenue_label': 'Revenue',
        'net_profit_label': 'Net Profit (Parent)',
        'operating_cash_flow_label': 'Operating Cash Flow',
        'roe_label': 'ROE',
        'revenue_yoy_label': 'Revenue YoY',
        'net_profit_yoy_label': 'Net Profit YoY',
        'gross_margin_label': 'Gross Margin',
        'shareholder_return_heading': 'Shareholder Return',
        'ttm_cash_dividend_label': 'TTM Cash Dividend / Share (Pre-tax)',
        'ttm_event_count_label': 'TTM Dividend Events',
        'ttm_dividend_yield_label': 'TTM Dividend Yield',
        'latest_ex_dividend_label': 'Latest Ex-dividend Date',
        'institutional_flow_heading': 'Institutional Flows (3 Majors)',
        'institutional_flow_note': 'Positive = net buy, negative = net sell; unit: shares.',
        'inst_foreign_label': 'Foreign',
        'inst_trust_label': 'Inv. Trust',
        'inst_dealer_label': 'Dealer',
        'inst_total_label': 'Total (3 Majors)',
        'related_boards_heading': 'Related Boards',
        'industry_boards_heading': 'Industry Sectors',
        'concept_boards_heading': 'Concept Themes',
        'board_name_label': 'Board',
        'board_type_label': 'Type',
        'board_status_label': 'Status',
        'board_change_pct_label': 'Change %',
        'leading_board_label': 'Leading',
        'lagging_board_label': 'Lagging',
        'signal_attribution_heading': 'Signal Attribution',
        'attribution_weights_label': 'Attribution Weights',
        'technical_indicators_label': 'Technical Indicators',
        'news_sentiment_label': 'News Sentiment',
        'fundamentals_label': 'Fundamentals',
        'market_conditions_label': 'Market Conditions',
        'strongest_bullish_signal_label': 'Strongest Bullish Signal',
        'strongest_bearish_signal_label': 'Strongest Bearish Signal'},
 'ko': {'dashboard_title': 'Decision Dashboard',
        'brief_title': 'Decision Brief',
        'analyzed_prefix': 'Analyzed',
        'stock_unit': 'stocks',
        'stock_unit_compact': 'stocks',
        'buy_label': 'Buy',
        'watch_label': 'Watch',
        'sell_label': 'Sell',
        'summary_heading': 'Summary',
        'info_heading': 'Key Updates',
        'sentiment_summary_label': 'Sentiment',
        'earnings_outlook_label': 'Earnings Outlook',
        'risk_alerts_label': 'Risk Alerts',
        'positive_catalysts_label': 'Positive Catalysts',
        'latest_news_label': 'Latest News',
        'core_conclusion_heading': 'Core Conclusion',
        'one_sentence_label': 'One-line Decision',
        'time_sensitivity_label': 'Time Sensitivity',
        'default_time_sensitivity': 'This week',
        'position_status_label': 'Position',
        'action_advice_label': 'Action',
        'no_position_label': 'No Position',
        'has_position_label': 'Holding',
        'continue_holding': 'Continue holding',
        'market_snapshot_heading': 'Market Snapshot',
        'close_label': 'Close',
        'prev_close_label': 'Prev Close',
        'open_label': 'Open',
        'high_label': 'High',
        'low_label': 'Low',
        'change_pct_label': 'Change %',
        'change_amount_label': 'Change',
        'amplitude_label': 'Amplitude',
        'volume_label': 'Volume',
        'amount_label': 'Turnover',
        'current_price_label': 'Price',
        'volume_ratio_label': 'Volume Ratio',
        'turnover_rate_label': 'Turnover Rate',
        'source_label': 'Source',
        'data_perspective_heading': 'Data View',
        'ma_alignment_label': 'MA Alignment',
        'bullish_alignment_label': 'Bullish Alignment',
        'yes_label': 'Yes',
        'no_label': 'No',
        'trend_strength_label': 'Trend Strength',
        'price_metrics_label': 'Price Metrics',
        'ma5_label': 'MA5',
        'ma10_label': 'MA10',
        'ma20_label': 'MA20',
        'bias_ma5_label': 'Bias (MA5)',
        'support_level_label': 'Support',
        'resistance_level_label': 'Resistance',
        'chip_label': 'Chip Structure',
        'phase_decision_heading': 'Phase Decision Guardrail',
        'action_window_label': 'Action Window',
        'immediate_action_label': 'Current Action',
        'watch_conditions_label': 'Watch Conditions',
        'next_check_time_label': 'Next Check',
        'confidence_reason_label': 'Confidence Reason',
        'data_limitations_label': 'Data Limitations',
        'battle_plan_heading': 'Battle Plan',
        'ideal_buy_label': 'Ideal Entry',
        'secondary_buy_label': 'Secondary Entry',
        'stop_loss_label': 'Stop Loss',
        'take_profit_label': 'Target',
        'suggested_position_label': 'Position Size',
        'entry_plan_label': 'Entry Plan',
        'risk_control_label': 'Risk Control',
        'checklist_heading': 'Checklist',
        'failed_checks_heading': 'Failed Checks',
        'history_compare_heading': 'Historical Signal Comparison',
        'time_label': 'Time',
        'score_label': 'Score',
        'advice_label': 'Advice',
        'trend_label': 'Trend',
        'generated_at_label': 'Generated At',
        'report_time_label': 'Generated',
        'no_results': 'No analysis results',
        'report_title': 'Stock Analysis Report',
        'avg_score_label': 'Avg Score',
        'action_points_heading': 'Action Levels',
        'position_advice_heading': 'Position Advice',
        'analysis_model_label': 'Model',
        'not_investment_advice': 'AI-generated content for reference only. Not investment advice.',
        'details_report_hint': 'See detailed report:',
        'financial_summary_heading': 'Financial Summary',
        'report_date_label': 'Report Date',
        'revenue_label': 'Revenue',
        'net_profit_label': 'Net Profit (Parent)',
        'operating_cash_flow_label': 'Operating Cash Flow',
        'roe_label': 'ROE',
        'revenue_yoy_label': 'Revenue YoY',
        'net_profit_yoy_label': 'Net Profit YoY',
        'gross_margin_label': 'Gross Margin',
        'shareholder_return_heading': 'Shareholder Return',
        'ttm_cash_dividend_label': 'TTM Cash Dividend / Share (Pre-tax)',
        'ttm_event_count_label': 'TTM Dividend Events',
        'ttm_dividend_yield_label': 'TTM Dividend Yield',
        'latest_ex_dividend_label': 'Latest Ex-dividend Date',
        'institutional_flow_heading': 'Institutional Flows (3 Majors)',
        'institutional_flow_note': 'Positive = net buy, negative = net sell; unit: shares.',
        'inst_foreign_label': 'Foreign',
        'inst_trust_label': 'Inv. Trust',
        'inst_dealer_label': 'Dealer',
        'inst_total_label': 'Total (3 Majors)',
        'related_boards_heading': 'Related Boards',
        'industry_boards_heading': 'Industry Sectors',
        'concept_boards_heading': 'Concept Themes',
        'board_name_label': 'Board',
        'board_type_label': 'Type',
        'board_status_label': 'Status',
        'board_change_pct_label': 'Change %',
        'leading_board_label': 'Leading',
        'lagging_board_label': 'Lagging',
        'signal_attribution_heading': 'Signal Attribution',
        'attribution_weights_label': 'Attribution Weights',
        'technical_indicators_label': 'Technical Indicators',
        'news_sentiment_label': 'News Sentiment',
        'fundamentals_label': 'Fundamentals',
        'market_conditions_label': 'Market Conditions',
        'strongest_bullish_signal_label': 'Strongest Bullish Signal',
        'strongest_bearish_signal_label': 'Strongest Bearish Signal'}}

_DECISION_INTENT_NEGATIONS = (
    '\u4e0d',
    '\u5e76\u975e',
    '\u5e76\u672a',
    '\u672a',
    '\u6ca1\u6709',
    '\u65e0',
    '\u4e0d\u662f',
    "no ",
    "not ",
    " never",
)

_DECISION_INTENT_NEGATION_SCOPE_BREAK_CHARS = '\uff0c,\u3002\uff1b;:!?\uff01\uff1f'
_DECISION_INTENT_NEGATION_CONNECTORS = (
    '\u5efa\u8bae',
    '\u5e94',
    '\u5e94\u5f53',
    '\u5b9c',
    '\u5148',
    '\u518d',
    '\u6682',
    '\u6682\u65f6',
    '\u53ef',
    '\u53ef\u4ee5',
    '\u9700\u8981',
    '\u9700',
    '\u7ee7\u7eed',
)


def _strip_decision_negation_connectors(text: str) -> str:
    """Remove common advisory connectors between a negation token and decision word."""
    suffix = text.strip()
    changed = True
    while changed:
        changed = False
        for connector in _DECISION_INTENT_NEGATION_CONNECTORS:
            if suffix.startswith(connector):
                suffix = suffix[len(connector):].strip()
                changed = True
                break
    return suffix


def normalize_report_language(value: Optional[str], default: str = "en") -> str:
    """Normalize report language to a supported short code."""
    candidate = (value or default).strip().lower().replace(" ", "_")
    candidate = _REPORT_LANGUAGE_ALIASES.get(candidate, candidate)
    if candidate in SUPPORTED_REPORT_LANGUAGES:
        return candidate
    return default


def is_supported_report_language_value(value: Optional[str]) -> bool:
    """Return whether the raw value is a supported language code or alias."""
    candidate = (value or "").strip().lower().replace(" ", "_")
    if not candidate:
        return False
    return candidate in SUPPORTED_REPORT_LANGUAGES or candidate in _REPORT_LANGUAGE_ALIASES


def get_report_labels(language: Optional[str]) -> Dict[str, str]:
    """Return UI copy for the selected report language."""
    normalized = normalize_report_language(language)
    return _REPORT_LABELS[normalized]


def get_placeholder_text(language: Optional[str]) -> str:
    """Return placeholder text for missing localized content."""
    return _PLACEHOLDER_BY_LANGUAGE[normalize_report_language(language)]


def get_unknown_text(language: Optional[str]) -> str:
    """Return localized unknown text."""
    return _UNKNOWN_BY_LANGUAGE[normalize_report_language(language)]


def get_no_data_text(language: Optional[str]) -> str:
    """Return localized data unavailable text."""
    return _NO_DATA_BY_LANGUAGE[normalize_report_language(language)]


def get_chip_unavailable_text(language: Optional[str]) -> str:
    """Return the localized one-line chip distribution fallback text."""
    return _CHIP_UNAVAILABLE_BY_LANGUAGE[normalize_report_language(language)]


def _normalize_lookup_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _iter_lookup_candidates(value: Any) -> list[str]:
    raw_text = str(value or "").strip()
    if not raw_text:
        return []

    candidates = [raw_text]
    for part in re.split('[/|,\uff0c\u3001]+', raw_text):
        normalized = part.strip()
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _canonicalize_lookup_value(value: Any, canonical_map: Dict[str, str]) -> Optional[str]:
    for candidate in _iter_lookup_candidates(value):
        canonical = canonical_map.get(_normalize_lookup_key(candidate))
        if canonical:
            return canonical
    return None


def _first_non_negated_position(text: str, token: str) -> Optional[int]:
    if not text or not token:
        return None

    normalized_text = text.lower().strip()
    if any(ch in normalized_text for ch in "abcdefghijklmnopqrstuvwxyz"):
        matches = list(re.finditer(rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])", normalized_text))
    else:
        matches = list(re.finditer(re.escape(token), normalized_text))

    for match in matches:
        prefix = normalized_text[: match.start()]
        if any(prefix.rstrip().endswith(neg) for neg in _DECISION_INTENT_NEGATIONS):
            continue
        lookback = prefix[-12:]
        negated = False
        for neg in _DECISION_INTENT_NEGATIONS:
            if not neg:
                continue
            neg_idx = lookback.rfind(neg)
            if neg_idx < 0:
                continue
            suffix = lookback[neg_idx + len(neg):]
            if not suffix:
                negated = True
                break
            if any(ch in suffix for ch in _DECISION_INTENT_NEGATION_SCOPE_BREAK_CHARS):
                continue
            normalized_suffix = _strip_decision_negation_connectors(suffix)
            if not normalized_suffix:
                negated = True
                break
            if any(ch in normalized_suffix for ch in _DECISION_INTENT_NEGATION_SCOPE_BREAK_CHARS):
                continue
            if len(normalized_suffix) > 6 and token not in normalized_suffix:
                continue
            if normalized_suffix.startswith(token):
                negated = True
                break
        if negated:
            continue
        else:
            return match.start()
    return None


def _is_placeholder_stock_name(value: Any, code: Any = None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True

    lowered = text.lower()
    if lowered in {"n/a", "na", "none", "null", "unknown"}:
        return True
    if text in {"-", '\u2014', '\u672a\u77e5', '\u5f85\u8865\u5145'}:
        return True

    code_text = str(code or "").strip()
    if code_text and lowered == code_text.lower():
        return True

    return text.startswith('\u80a1\u7968')


def _translate_from_map(
    value: Any,
    language: Optional[str],
    *,
    canonical_map: Dict[str, str],
    translations: Dict[str, Dict[str, str]],
) -> str:
    normalized_language = normalize_report_language(language)
    raw_text = str(value or "").strip()
    if not raw_text:
        return raw_text

    canonical = _canonicalize_lookup_value(raw_text, canonical_map)
    if canonical:
        return translations[canonical][normalized_language]
    return raw_text


def localize_operation_advice(value: Any, language: Optional[str]) -> str:
    """Translate operation advice between Chinese and English when recognized."""
    return _translate_from_map(
        value,
        language,
        canonical_map=_OPERATION_ADVICE_CANONICAL_MAP,
        translations=_OPERATION_ADVICE_TRANSLATIONS,
    )


def localize_trend_prediction(value: Any, language: Optional[str]) -> str:
    """Translate trend prediction between Chinese and English when recognized."""
    normalized_language = normalize_report_language(language)
    raw_text = str(value or "").strip()
    if not raw_text:
        return raw_text
    if normalized_language == "zh":
        if re.search(r"[\u4e00-\u9fff]", raw_text):
            return raw_text
    return _translate_from_map(
        value,
        normalized_language,
        canonical_map=_TREND_PREDICTION_CANONICAL_MAP,
        translations=_TREND_PREDICTION_TRANSLATIONS,
    )


def localize_confidence_level(value: Any, language: Optional[str]) -> str:
    """Translate confidence level between Chinese and English when recognized."""
    return _translate_from_map(
        value,
        language,
        canonical_map=_CONFIDENCE_LEVEL_CANONICAL_MAP,
        translations=_CONFIDENCE_LEVEL_TRANSLATIONS,
    )


def localize_chip_health(value: Any, language: Optional[str]) -> str:
    """Translate chip health labels between Chinese and English when recognized."""
    return _translate_from_map(
        value,
        language,
        canonical_map=_CHIP_HEALTH_CANONICAL_MAP,
        translations=_CHIP_HEALTH_TRANSLATIONS,
    )


def is_chip_placeholder_value(value: Any) -> bool:
    """Return True for chip fields filled with empty or no-data placeholders."""
    if value is None:
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    text = str(value).strip()
    lowered = text.lower()
    if lowered in _CHIP_PLACEHOLDER_EXACT:
        return True
    return any(hint in lowered for hint in _CHIP_PLACEHOLDER_HINTS)


def is_chip_structure_unavailable(chip_data: Any) -> bool:
    """Detect chip_structure blocks that contain only unavailable placeholders."""
    if not isinstance(chip_data, dict) or not chip_data:
        return False
    for key in _CHIP_UNAVAILABLE_REASON_KEYS:
        raw = chip_data.get(key)
        if isinstance(raw, bool):
            if raw:
                return True
            continue
        if str(raw or "").strip():
            return True
    if any(key in chip_data for key in _CHIP_METRIC_KEYS):
        return all(is_chip_placeholder_value(chip_data.get(key)) for key in _CHIP_METRIC_KEYS)
    return all(is_chip_placeholder_value(value) for value in chip_data.values())


def get_chip_unavailable_reason(value: Any, language: Optional[str]) -> str:
    """Return the explicit or default chip unavailable reason for rendering."""
    if not isinstance(value, dict) or not value:
        return ""
    for key in _CHIP_UNAVAILABLE_REASON_KEYS:
        raw = value.get(key)
        if isinstance(raw, bool):
            if raw:
                return get_chip_unavailable_text(language)
            continue
        text = str(raw or "").strip()
        if text:
            return text
    if is_chip_structure_unavailable(value):
        return get_chip_unavailable_text(language)
    return ""


def localize_bias_status(value: Any, language: Optional[str]) -> str:
    """Translate price bias status labels between Chinese and English when recognized."""
    return _translate_from_map(
        value,
        language,
        canonical_map=_BIAS_STATUS_CANONICAL_MAP,
        translations=_BIAS_STATUS_TRANSLATIONS,
    )


def get_bias_status_emoji(value: Any) -> str:
    """Return the stable alert emoji for a localized or canonical bias status."""
    canonical = _canonicalize_lookup_value(value, _BIAS_STATUS_CANONICAL_MAP)
    if canonical == "safe":
        return '\u2705'
    if canonical == "caution":
        return '\u26a0\ufe0f'
    return '\U0001f6a8'


def infer_decision_type_from_advice(value: Any, default: str = "hold") -> str:
    """Infer buy/hold/sell from human-readable operation advice."""
    canonical = _canonicalize_lookup_value(value, _OPERATION_ADVICE_CANONICAL_MAP)
    if canonical in {"strong_buy", "buy"}:
        return "buy"
    if canonical in {"reduce", "sell", "strong_sell"}:
        return "sell"
    if canonical in {"hold", "watch"}:
        return "hold"

    normalized_text = _normalize_lookup_key(value)
    best_position: Optional[int] = None
    best_canonical: Optional[str] = None
    for option, canonical in _OPERATION_ADVICE_CANONICAL_MAP.items():
        option_norm = _normalize_lookup_key(option)
        pos = _first_non_negated_position(normalized_text, option_norm)
        if pos is None:
            continue
        if best_position is None or pos < best_position:
            best_position = pos
            best_canonical = canonical

    if best_canonical in {"strong_buy", "buy"}:
        return "buy"
    if best_canonical in {"reduce", "sell", "strong_sell"}:
        return "sell"
    if best_canonical in {"hold", "watch"}:
        return "hold"

    return default


def get_signal_level(advice: Any, score: Any, language: Optional[str]) -> tuple[str, str, str]:
    """Return localized signal text, emoji, and stable color tag."""
    normalized_language = normalize_report_language(language)
    canonical = _canonicalize_lookup_value(advice, _OPERATION_ADVICE_CANONICAL_MAP)
    if canonical == "strong_buy":
        return (_OPERATION_ADVICE_TRANSLATIONS["strong_buy"][normalized_language], '\U0001f49a', "strong_buy")
    if canonical == "buy":
        return (_OPERATION_ADVICE_TRANSLATIONS["buy"][normalized_language], '\U0001f7e2', "buy")
    if canonical == "hold":
        return (_OPERATION_ADVICE_TRANSLATIONS["hold"][normalized_language], '\U0001f7e1', "hold")
    if canonical == "watch":
        return (_OPERATION_ADVICE_TRANSLATIONS["watch"][normalized_language], '\u26aa', "watch")
    if canonical == "reduce":
        return (_OPERATION_ADVICE_TRANSLATIONS["reduce"][normalized_language], '\U0001f7e0', "reduce")
    if canonical in {"sell", "strong_sell"}:
        return (_OPERATION_ADVICE_TRANSLATIONS["sell"][normalized_language], '\U0001f534', "sell")

    try:
        numeric_score = int(float(score))
    except (TypeError, ValueError):
        numeric_score = 50

    score_signal = signal_key_for_score(numeric_score)
    if score_signal == "strong_buy":
        return (_OPERATION_ADVICE_TRANSLATIONS["strong_buy"][normalized_language], '\U0001f49a', "strong_buy")
    if score_signal == "buy":
        return (_OPERATION_ADVICE_TRANSLATIONS["buy"][normalized_language], '\U0001f7e2', "buy")
    if score_signal == "watch":
        return (_OPERATION_ADVICE_TRANSLATIONS["watch"][normalized_language], '\u26aa', "watch")
    if score_signal == "reduce":
        return (_OPERATION_ADVICE_TRANSLATIONS["reduce"][normalized_language], '\U0001f7e0', "reduce")
    return (_OPERATION_ADVICE_TRANSLATIONS["sell"][normalized_language], '\U0001f534', "sell")


def get_localized_stock_name(value: Any, code: Any, language: Optional[str]) -> str:
    """Return a localized stock name placeholder when the original name is missing."""
    raw_text = str(value or "").strip()
    if not _is_placeholder_stock_name(raw_text, code):
        return raw_text
    return _GENERIC_STOCK_NAME_BY_LANGUAGE[normalize_report_language(language)]


def get_sentiment_label(score: int, language: Optional[str]) -> str:
    """Return a sentiment label for the configured report language."""
    try:
        score = int(score)
    except Exception:
        score = 50

    if score >= 80:
        return "Very Bullish"
    if score >= 60:
        return "Bullish"
    if score >= 40:
        return "Neutral"
    if score >= 20:
        return "Bearish"
    return "Very Bearish"
