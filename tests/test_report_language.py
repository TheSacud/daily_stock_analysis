# -*- coding: utf-8 -*-
"""Unit tests for report language helpers."""

import unittest

from src.report_language import (
    SUPPORTED_REPORT_LANGUAGES,
    get_bias_status_emoji,
    get_localized_stock_name,
    get_report_labels,
    get_sentiment_label,
    get_signal_level,
    infer_decision_type_from_advice,
    localize_operation_advice,
    localize_trend_prediction,
    localize_bias_status,
    normalize_report_language,
)


class ReportLanguageTestCase(unittest.TestCase):
    def test_get_signal_level_handles_compound_sell_advice(self) -> None:
        signal_text, emoji, signal_tag = get_signal_level("\u5356\u51fa/\u89c2\u671b", 60, "zh")

        self.assertEqual(signal_text, "\u5356\u51fa")
        self.assertEqual(emoji, "🔴")
        self.assertEqual(signal_tag, "sell")

    def test_get_signal_level_handles_compound_buy_advice_in_english(self) -> None:
        signal_text, emoji, signal_tag = get_signal_level("Buy / Watch", 40, "en")

        self.assertEqual(signal_text, "Buy")
        self.assertEqual(emoji, "🟢")
        self.assertEqual(signal_tag, "buy")

    def test_get_signal_level_score_fallback_uses_canonical_scale(self) -> None:
        self.assertEqual(get_signal_level("", 28, "zh"), ("\u51cf\u4ed3", "🟠", "reduce"))
        self.assertEqual(get_signal_level("", 38, "zh"), ("\u51cf\u4ed3", "🟠", "reduce"))
        self.assertEqual(get_signal_level("", 42, "zh"), ("\u89c2\u671b", "⚪", "watch"))
        self.assertEqual(get_signal_level("", 55, "zh"), ("\u89c2\u671b", "⚪", "watch"))
        self.assertEqual(get_signal_level("", 60, "zh"), ("\u4e70\u5165", "🟢", "buy"))
        self.assertEqual(get_signal_level("", 66, "zh"), ("\u4e70\u5165", "🟢", "buy"))
        self.assertEqual(get_signal_level("", 72, "zh"), ("\u4e70\u5165", "🟢", "buy"))

    def test_get_localized_stock_name_replaces_placeholder_for_english(self) -> None:
        self.assertEqual(
            get_localized_stock_name("\u80a1\u7968AAPL", "AAPL", "en"),
            "Unnamed Stock",
        )

    def test_get_sentiment_label_preserves_higher_band_thresholds(self) -> None:
        self.assertEqual(get_sentiment_label(80, "en"), "Very Bullish")
        self.assertEqual(get_sentiment_label(60, "en"), "Bullish")
        self.assertEqual(get_sentiment_label(40, "zh"), "\u4e2d\u6027")
        self.assertEqual(get_sentiment_label(20, "zh"), "\u60b2\u89c2")

    def test_localize_trend_prediction_preserves_fine_grain_zh_states(self) -> None:
        self.assertEqual(localize_trend_prediction("\u591a\u5934\u6392\u5217", "zh"), "\u591a\u5934\u6392\u5217")
        self.assertEqual(localize_trend_prediction("\u5f31\u52bf\u7a7a\u5934", "zh"), "\u5f31\u52bf\u7a7a\u5934")

    def test_localize_trend_prediction_still_translates_english_input_for_zh(self) -> None:
        self.assertEqual(localize_trend_prediction("bullish", "zh"), "\u770b\u591a")
        self.assertEqual(localize_trend_prediction("very bearish", "zh"), "\u5f3a\u70c8\u770b\u7a7a")

    def test_bias_status_helpers_support_english_values(self) -> None:
        self.assertEqual(localize_bias_status("Safe", "en"), "Safe")
        self.assertEqual(localize_bias_status("\u8b66\u6212", "en"), "Caution")
        self.assertEqual(get_bias_status_emoji("Safe"), "✅")
        self.assertEqual(get_bias_status_emoji("Caution"), "⚠️")

    def test_infer_decision_type_from_advice_matches_chinese_phrases(self) -> None:
        self.assertEqual(infer_decision_type_from_advice("\u5efa\u8bae\u4e70\u5165"), "buy")
        self.assertEqual(infer_decision_type_from_advice("\u5efa\u8bae\u6301\u6709"), "hold")
        self.assertEqual(infer_decision_type_from_advice("\u5efa\u8bae\u51cf\u4ed3"), "sell")
        self.assertEqual(infer_decision_type_from_advice("\u7ee7\u7eed\u6301\u6709"), "hold")
        self.assertEqual(infer_decision_type_from_advice("\u5efa\u8bae\u6d17\u76d8\u89c2\u5bdf"), "hold")
        self.assertEqual(infer_decision_type_from_advice("\u6d17\u76d8\u89c2\u5bdf", default=""), "hold")
        self.assertEqual(infer_decision_type_from_advice("\u89c2\u5bdf", default=""), "hold")
        self.assertEqual(infer_decision_type_from_advice("\u4e0d\u5efa\u8bae\u4e70\u5165"), "hold")
        self.assertEqual(
            infer_decision_type_from_advice("\u5f53\u524d\u4e0d\u8dcc\u7834\u652f\u6491\u4f4d\u7ee7\u7eed\u6301\u6709"),
            "hold",
        )
        self.assertEqual(
            infer_decision_type_from_advice("\u4e0d\u7834\u652f\u6491\u540e\u4ecd\u53ef\u6301\u6709"),
            "hold",
        )


class KoreanReportLanguageTestCase(unittest.TestCase):
    def test_korean_is_supported(self) -> None:
        self.assertIn("ko", SUPPORTED_REPORT_LANGUAGES)

    def test_normalize_korean_aliases(self) -> None:
        self.assertEqual(normalize_report_language("ko"), "ko")
        self.assertEqual(normalize_report_language("korean"), "ko")
        self.assertEqual(normalize_report_language("ko-KR"), "ko")
        self.assertEqual(normalize_report_language("kr"), "ko")

    def test_unknown_language_falls_back_to_default(self) -> None:
        self.assertEqual(normalize_report_language("fr"), "zh")
        self.assertEqual(normalize_report_language(None), "zh")

    def test_korean_labels_cover_full_english_key_set(self) -> None:
        ko_labels = get_report_labels("ko")
        en_labels = get_report_labels("en")
        self.assertEqual(set(ko_labels.keys()), set(en_labels.keys()))
        self.assertEqual(ko_labels["dashboard_title"], "결정 대시보드")
        self.assertEqual(ko_labels["risk_alerts_label"], "리스크 경보")

    def test_korean_sentiment_label_bands(self) -> None:
        self.assertEqual(get_sentiment_label(80, "ko"), "매우 낙관")
        self.assertEqual(get_sentiment_label(40, "ko"), "중립")
        self.assertEqual(get_sentiment_label(0, "ko"), "매우 비관")

    def test_korean_operation_advice_and_trend(self) -> None:
        self.assertEqual(localize_operation_advice("\u4e70\u5165", "ko"), "매수")
        self.assertEqual(localize_operation_advice("strong sell", "ko"), "적극 매도")
        self.assertEqual(localize_trend_prediction("bullish", "ko"), "상승")

    def test_korean_localized_stock_name_placeholder(self) -> None:
        self.assertEqual(
            get_localized_stock_name("\u80a1\u7968AAPL", "AAPL", "ko"),
            "미확인 종목",
        )

    def test_existing_languages_unchanged(self) -> None:
        self.assertEqual(get_sentiment_label(80, "en"), "Very Bullish")
        self.assertEqual(get_sentiment_label(40, "zh"), "\u4e2d\u6027")

    def test_korean_advice_canonicalizes_to_decision_type(self) -> None:
        self.assertEqual(infer_decision_type_from_advice("매수"), "buy")
        self.assertEqual(infer_decision_type_from_advice("매도"), "sell")
        self.assertEqual(infer_decision_type_from_advice("보유"), "hold")
        self.assertEqual(infer_decision_type_from_advice("관망"), "hold")

    def test_korean_advice_resolves_signal_level(self) -> None:
        self.assertEqual(get_signal_level("매수", 72, "ko"), ("매수", "🟢", "buy"))
        self.assertEqual(get_signal_level("매도", 30, "ko"), ("매도", "🔴", "sell"))

    def test_korean_values_canonicalize_back_for_other_languages(self) -> None:
        self.assertEqual(localize_trend_prediction("상승", "en"), "Bullish")
        self.assertEqual(localize_operation_advice("적극 매도", "zh"), "\u5f3a\u70c8\u5356\u51fa")


if __name__ == "__main__":
    unittest.main()
