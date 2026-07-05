# -*- coding: utf-8 -*-
"""Contract checks for the alert-center documentation."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "alerts.md"


def _read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_alerts_doc_exists_and_links_p0_scope() -> None:
    doc = _read_doc()

    assert "Issue #1202" in doc
    assert "AGENT_EVENT_ALERT_RULES_JSON" in doc
    assert "EventMonitor" in doc
    assert "P1 Alert API MVP" in doc
    assert "P0 \u4e0d\u505a" in doc


def test_alerts_doc_covers_legacy_runtime_rules() -> None:
    doc = _read_doc()

    for token in ("price_cross", "price_change_percent", "volume_spike"):
        assert token in doc
    for token in ("sentiment_shift", "risk_flag", "custom"):
        assert token in doc


def test_alerts_doc_defines_required_contract_entities() -> None:
    doc = _read_doc()

    required_sections = (
        "### `alert_rule`",
        "### `alert_trigger`",
        "### `alert_notification`",
        "### `alert_cooldown`",
    )
    for section in required_sections:
        assert section in doc

    required_fields = (
        "target_scope",
        "parameters",
        "cooldown_policy",
        "notification_policy",
        "observed_value",
        "data_timestamp",
        "trigger_id",
        "latency_ms",
        "cooldown_until",
    )
    for field_name in required_fields:
        assert field_name in doc


def test_alerts_doc_covers_storage_evaluation_and_rollback() -> None:
    doc = _read_doc()

    assert (PROJECT_ROOT / "src" / "storage.py").is_file()

    for token in (
        "## \u5b58\u50a8\u65b9\u6848\u8bc4\u4f30",
        "src/storage.py",
        "src/repositories/",
        "src/services/",
        "data/stock_analysis.db",
        "\u5e42\u7b49\u521d\u59cb\u5316",
        "\u56de\u6eda\u8bf4\u660e",
    ):
        assert token in doc


def test_alerts_doc_keeps_p0_non_goals_explicit() -> None:
    doc = _read_doc()

    for token in (
        "P0 \u9636\u6bb5\u4e0d\u65b0\u589e `api/v1/schemas/alerts.py`",
        "P0 \u9636\u6bb5\u4e0d\u65b0\u589e Web \u544a\u8b66\u4e2d\u5fc3\u9875\u9762",
        "P0 \u9636\u6bb5\u4e0d\u65b0\u589e\u6570\u636e\u5e93\u8868",
        "P0 \u9636\u6bb5\u4e0d\u5b9e\u73b0\u89e6\u53d1\u5386\u53f2",
        "P0 \u9636\u6bb5\u4e0d\u81ea\u52a8\u8fc1\u79fb、\u5220\u9664\u6216\u8986\u76d6 `AGENT_EVENT_ALERT_RULES_JSON`",
        "P0 \u9636\u6bb5\u4e0d\u91cd\u5199 `NotificationService`",
    ):
        assert token in doc


def test_alerts_doc_defines_p1_api_mvp_scope() -> None:
    doc = _read_doc()

    for token in (
        "api/v1/endpoints/alerts.py",
        "api/v1/schemas/alerts.py",
        "GET /api/v1/alerts/rules",
        "POST /api/v1/alerts/rules",
        "GET /api/v1/alerts/rules/{rule_id}",
        "PATCH /api/v1/alerts/rules/{rule_id}",
        "DELETE /api/v1/alerts/rules/{rule_id}",
        "POST /api/v1/alerts/rules/{rule_id}/enable",
        "POST /api/v1/alerts/rules/{rule_id}/disable",
        "POST /api/v1/alerts/rules/{rule_id}/test",
        "GET /api/v1/alerts/triggers",
        "GET /api/v1/alerts/notifications",
        "price_cross",
        "price_change_percent",
        "volume_spike",
        "unsupported",
        "\u8131\u654f",
        "\u4fdd\u7559\u5b57\u6bb5",
        "\u4e0d\u6267\u884c\u51b7\u5374\u6216\u81ea\u5b9a\u4e49\u901a\u77e5\u8bed\u4e49",
    ):
        assert token in doc


def test_alerts_doc_keeps_p1_non_goals_explicit() -> None:
    doc = _read_doc()

    for token in (
        "\u4e0d\u65b0\u589e Web \u544a\u8b66\u4e2d\u5fc3\u9875\u9762",
        "\u4e0d\u8ba9 schedule worker \u52a0\u8f7d\u6301\u4e45\u5316 active rules",
        "\u4e0d\u5b9e\u73b0\u771f\u5b9e `alert_trigger` / `alert_notification` \u5199\u5165",
        "\u4e0d\u5b9e\u73b0 `alert_cooldown` \u6267\u884c\u8bed\u4e49",
        "\u4e0d\u5b9e\u73b0 MACD、KDJ、CCI、RSI",
        "\u4e0d\u81ea\u52a8\u8fc1\u79fb、\u5220\u9664、\u8986\u76d6\u6216\u6539\u5199 legacy \u914d\u7f6e",
    ):
        assert token in doc


def test_alerts_doc_defines_p2_worker_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P2 \u544a\u8b66\u8bc4\u4f30 Worker",
        "src/services/alert_worker.py",
        "agent_event_monitor",
        "\u6301\u4e45\u5316 active rules",
        "legacy JSON",
        "`triggered`、`skipped`、`degraded`、`failed`",
        "\u4e0d\u5199 `alert_notifications`",
        "\u4e0d\u6267\u884c `cooldown_policy`",
    ):
        assert token in doc


def test_alerts_doc_describes_p1_rollback_for_created_tables() -> None:
    doc = _read_doc()

    for token in (
        "P1 \u65b0\u589e Alert API \u4ee3\u7801",
        "`alert_rules` / `alert_triggers` / `alert_notifications` SQLite \u8868",
        "Base.metadata.create_all()",
        "SQLite \u8868\u4e0e\u6570\u636e\u4e0d\u4f1a\u81ea\u52a8\u5220\u9664",
        "\u624b\u52a8\u5220\u9664\u76f8\u5173\u8868",
    ):
        assert token in doc


def test_alerts_doc_defines_p4_notification_and_cooldown_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P4 \u901a\u77e5\u7ed3\u679c\u4e0e\u6301\u4e45\u5316\u51b7\u5374",
        "`alert_cooldowns`",
        "`alert_notifications`",
        "`rule_id + target + data_source + data_timestamp`",
        "\u540c\u4e00\u6570\u636e\u70b9\u53bb\u91cd",
        "`data_timestamp` \u7f3a\u5931\u65f6\u4e0d\u505a\u53bb\u91cd",
        "`__cooldown__`",
        "`__cooldown_read_failed__`",
        "`__noise_suppressed__`",
        "notification_noise.py",
        "DB \u6301\u4e45\u5316\u89c4\u5219\u6b63\u5e38\u8def\u5f84\u4f7f\u7528 `alert_cooldowns`",
        "\u8bfb\u53d6\u6301\u4e45\u5316\u51b7\u5374\u72b6\u6001\u5931\u8d25",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON` \u89c4\u5219\u7ee7\u7eed\u4f7f\u7528 worker \u8fdb\u7a0b\u5185 fingerprint",
        "\u4e0d\u4f1a\u5199\u5165\u6216\u5ef6\u957f `alert_cooldowns`",
        "\u6700\u5c0f\u56de\u6eda\u65b9\u5f0f\u662f revert P4 PR",
    ):
        assert token in doc


def test_alerts_doc_defines_p5_indicator_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P5 \u6280\u672f\u6307\u6807\u89c4\u5219",
        "ma_price_cross",
        "rsi_threshold",
        "macd_cross",
        "kdj_cross",
        "cci_threshold",
        "compute_required_bars",
        "requested_days",
        "required_bars > 365",
        "\u6700\u8fd1\u4e24\u6839\u5df2\u6536\u76d8\u65e5\u7ebf",
        "prev <= threshold < current",
        "Wilder",
        "SMMA",
        "alpha=1/period",
        "EMA(fast_period)",
        "alpha=1/k_period",
        "0.015 * mean_deviation",
        "\u670d\u52a1\u5668\u672c\u5730\u65f6\u533a\u542f\u53d1\u5f0f",
        "16:00",
        "\u65e5\u671f\u4e0d\u53ef\u5224\u5b9a\u90fd\u4f1a\u4fdd\u5b88\u4e22\u5f03",
        "legacy JSON \u8def\u5f84",
        "\u4e0d\u6269\u5c55 `src/agent/events.py`",
        "HTTP 400 + `validation_error`",
        "HTTP 400 + `unsupported_alert_type`",
        "\u4e0d\u652f\u6301 MACD \u67f1\u4f53\u653e\u5927/\u6536\u7f29",
        "\u4e0d\u652f\u6301 KDJ \u8d85\u4e70/\u8d85\u5356\u533a\u89c4\u5219",
        "\u4e0d\u652f\u6301 MA \u4e0e MA \u53cc\u5747\u7ebf\u4ea4\u53c9",
        "\u4e0d\u652f\u6301\u5206\u949f\u7ebf",
        "revert P5 PR",
        "skip unsupported `alert_type`",
    ):
        assert token in doc


def test_alerts_doc_defines_p6_portfolio_and_watchlist_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P6 \u6301\u4ed3\u4e0e\u81ea\u9009\u80a1\u8054\u52a8",
        "P6 scope/type \u77e9\u9635",
        "`watchlist`",
        "`portfolio_holdings`",
        "`portfolio_account`",
        "`portfolio_stop_loss`",
        "`portfolio_concentration`",
        "`portfolio_drawdown`",
        "`portfolio_price_stale`",
        "Target Identity Contract",
        "`effective_target`",
        "`RuntimeAlertRule.key`",
        "`{parent_key}|{effective_target}`",
        "dry-run",
        "`degraded_count`",
        "soft cap",
        "cooldown_active",
        "\u7236\u89c4\u5219\u6458\u8981",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON` \u4e0d\u652f\u6301 watchlist、portfolio",
        "sector \u7ea7\u96c6\u4e2d\u5ea6",
        "P6 PR",
    ):
        assert token in doc


def test_alerts_doc_defines_p7_market_light_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P7 \u5927\u76d8\u7ea2\u7eff\u706f\u7ed3\u6784\u5316\u544a\u8b66",
        "MarketLightSnapshot",
        "`target_scope=market`",
        "`market_light_status`",
        "`market_light_score_drop`",
        "`statuses=[\"red\",\"yellow\"]`",
        "`min_drop > 0`",
        "`cn` / `hk` / `us`",
        "\u53cc\u5411\u7ea6\u675f",
        "`context_snapshot.market_light_snapshots`",
        "`data_quality=unavailable`",
        "`partial_comparison=true`",
        "`missing_dimensions`",
        "canonical scorer",
        "thin wrapper",
        "`load_previous_snapshot(region, before_trade_date)`",
        "\u6700\u5927 `snapshot.trade_date`",
        "\u65e7\u4ea4\u6613\u65e5 backfill",
        "`TRADING_DAY_CHECK_ENABLED`",
        "`data_source=market_light`",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON` \u4e0d\u652f\u6301 market \u89c4\u5219",
        "revert P7 PR",
    ):
        assert token in doc


def test_alerts_doc_covers_issue_1386_p7_user_visibility_boundary() -> None:
    doc = _read_doc()
    p7_section = doc.split("#1386 P7 \u7684\u7528\u6237\u8fb9\u754c：", 1)[1].split(
        "\n\n\u56de\u6eda\u672c\u8054\u52a8",
        1,
    )[0]

    for token in (
        "\u89e6\u53d1\u65f6\u5df2\u7ecf\u53ef\u516c\u5f00\u7684\u9636\u6bb5\u548c\u6570\u636e\u8d28\u91cf\u6458\u8981",
        "\u4e0d\u4f1a\u81ea\u52a8\u53d1\u8d77\u8f7b\u91cf LLM \u76d8\u4e2d\u5206\u6790",
        "\u4e0d\u4f1a\u65b0\u589e\u544a\u8b66\u8868、\u89c4\u5219\u7c7b\u578b、\u73af\u5883\u53d8\u91cf\u6216 migration",
        "\u5206\u6790 API / Web \u624b\u52a8\u5206\u6790\u5165\u53e3",
        "\u544a\u8b66\u901a\u77e5\u53ea\u4fdd\u7559\u9636\u6bb5\u6807\u7b7e、trigger source、partial-bar warning、\u6570\u636e\u8d28\u91cf\u7b49\u7ea7\u548c\u524d\u4e24\u6761 limitations",
    ):
        assert token in p7_section


def test_alerts_doc_defines_p8_user_and_deployment_boundaries() -> None:
    doc = _read_doc()

    for token in (
        "## P8 \u7528\u6237\u914d\u7f6e\u4e0e\u90e8\u7f72\u8fb9\u754c",
        "`AGENT_EVENT_MONITOR_ENABLED`",
        "`AGENT_EVENT_MONITOR_INTERVAL_MINUTES`",
        "`NOTIFICATION_ALERT_CHANNELS`",
        "`route_type=alert`",
        "Alert API / Web \u544a\u8b66\u4e2d\u5fc3\u6301\u4e45\u5316\u89c4\u5219",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON`",
        "\u53ea\u517c\u5bb9 `single_symbol`",
        "P5 \u6280\u672f\u6307\u6807、P6 watchlist/portfolio \u6216 P7 market light",
        "docker/Dockerfile",
        "`python main.py --schedule`",
        "\u4fdd\u7559 `data/` \u6570\u636e\u5e93\u5377",
        ".github/workflows/00-daily-analysis.yml",
        "\u4e00\u6b21\u6027\u5206\u6790 workflow",
        "\u4e0d\u8fd0\u884c `--schedule` \u540e\u53f0 alert worker",
        "\u6ca1\u6709\u6620\u5c04 `AGENT_EVENT_*`",
        "`/alerts`",
        "Desktop \u4e0d\u65b0\u589e\u539f\u751f\u544a\u8b66\u7ba1\u7406\u754c\u9762",
        "`triggered`、`skipped`、`degraded`、`failed`",
        "`rule_id + target + data_source + data_timestamp`",
        "\u56de\u6eda P8 \u53ea\u9700 revert \u6587\u6863、\u914d\u7f6e\u8bf4\u660e\u548c Web \u6587\u6848\u6539\u52a8",
    ):
        assert token in doc


def test_changelog_mentions_alert_p6_release_note() -> None:
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "P6" in changelog
    assert "\u81ea\u9009\u80a1" in changelog
    assert "\u6301\u4ed3" in changelog
    assert "\u8d26\u6237\u8054\u52a8\u89c4\u5219" in changelog


def test_changelog_mentions_alert_p8_docs_closeout() -> None:
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "\u8865\u9f50\u544a\u8b66\u4e2d\u5fc3 P8 \u6587\u6863\u4e0e\u914d\u7f6e\u6536\u53e3\u8bf4\u660e" in changelog
    assert "GitHub Actions \u4e0e Desktop \u8fb9\u754c" in changelog


def test_changelog_unreleased_keeps_flat_entries() -> None:
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]

    assert "\n### " not in unreleased
