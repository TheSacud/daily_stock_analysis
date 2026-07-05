import logging
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

from data_provider.akshare_fetcher import (
    AkshareFetcher,
    SINA_REALTIME_ENDPOINT,
    TENCENT_REALTIME_ENDPOINT,
)


class _DummyCircuitBreaker:
    def __init__(self):
        self.failures = []
        self.successes = []

    def is_available(self, source: str) -> bool:
        return True

    def record_success(self, source: str) -> None:
        self.successes.append(source)

    def record_failure(self, source: str, error=None) -> None:
        self.failures.append((source, error))


class _DummyResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.encoding = None


def _make_sina_payload() -> str:
    fields = [
        "\u5927\u79e6\u94c1\u8def", "5.100", "5.000", "5.190", "5.200", "5.050", "5.180", "5.190",
        "123456", "789012"
    ]
    fields.extend(["0"] * 20)
    fields.extend(["2026-03-08", "15:00:00"])
    return f'var hq_str_sh601006="{",".join(fields)}";'


def _make_tencent_payload(
    *,
    price: str = "5.19",
    volume: str = "1234",
    amount_triplet: str = "",
    amount_wan: str = "640.45",
    turnover_rate: str = "0.69",
    circ_mv_yi: str = "0.93",
    total_mv_yi: str = "1.20",
) -> str:
    fields = ["0"] * 50
    fields[1] = "\u5927\u79e6\u94c1\u8def"
    fields[2] = "601006"
    fields[3] = price
    fields[4] = "5.00"
    fields[5] = "5.10"
    fields[6] = volume
    fields[31] = "0.19"
    fields[32] = "3.80"
    fields[33] = "5.20"
    fields[34] = "5.05"
    if amount_triplet:
        fields[35] = amount_triplet
    fields[37] = amount_wan
    fields[38] = turnover_rate
    fields[39] = "12.3"
    fields[43] = "2.00"
    fields[44] = circ_mv_yi
    fields[45] = total_mv_yi
    fields[46] = "1.20"
    fields[49] = "0.63"
    return f'v_sh601006="{"~".join(fields)}";'


@pytest.fixture
def akshare_fetcher(monkeypatch):
    fetcher = AkshareFetcher()
    monkeypatch.setattr(fetcher, "_enforce_rate_limit", lambda: None)
    return fetcher


def test_sina_realtime_success_logs_endpoint(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(200, _make_sina_payload()),
    )

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_sina("601006")

    assert quote is not None
    assert quote.name == "\u5927\u79e6\u94c1\u8def"
    assert quote.price == 5.19
    assert breaker.successes == ["akshare_sina"]
    assert f"endpoint={SINA_REALTIME_ENDPOINT}" in caplog.text
    assert "[\u5b9e\u65f6\u884c\u60c5-\u65b0\u6d6a] 601006 \u5927\u79e6\u94c1\u8def:" in caplog.text


def test_sina_realtime_remote_disconnect_logs_category(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)

    def _raise_disconnect(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Remote end closed connection without response")

    monkeypatch.setattr("data_provider.akshare_fetcher.requests.get", _raise_disconnect)

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_sina("601006")

    assert quote is None
    assert breaker.failures
    source_key, message = breaker.failures[0]
    assert source_key == "akshare_sina"
    assert "category=remote_disconnect" in message
    assert f"endpoint={SINA_REALTIME_ENDPOINT}" in caplog.text
    assert "\u65b0\u6d6a \u5b9e\u65f6\u884c\u60c5\u63a5\u53e3\u5931\u8d25:" in caplog.text


def test_tencent_realtime_http_status_logs_endpoint(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(503, "service unavailable"),
    )

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_tencent("601006")

    assert quote is None
    assert breaker.failures
    source_key, message = breaker.failures[0]
    assert source_key == "akshare_tencent"
    assert "category=http_status" in message
    assert "detail=HTTP 503" in message
    assert f"endpoint={TENCENT_REALTIME_ENDPOINT}" in caplog.text


def test_tencent_realtime_success_logs_endpoint(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(200, _make_tencent_payload()),
    )

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_tencent("601006")

    assert quote is not None
    assert quote.name == "\u5927\u79e6\u94c1\u8def"
    assert quote.price == 5.19
    assert quote.volume == 123400
    assert quote.amount == 6404500
    assert breaker.successes == ["akshare_tencent"]
    assert f"endpoint={TENCENT_REALTIME_ENDPOINT}" in caplog.text
    assert "[\u5b9e\u65f6\u884c\u60c5-\u817e\u8baf] 601006 \u5927\u79e6\u94c1\u8def:" in caplog.text


def test_tencent_realtime_volume_keeps_share_unit_when_turnover_matches(monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(
            200,
            _make_tencent_payload(
                price="122.70",
                volume="10931723",
                amount_triplet="122.70/10931723/1327404280",
                amount_wan="168369.8131",
                turnover_rate="14.98",
                circ_mv_yi="89.53",
                total_mv_yi="147.24",
            ),
        ),
    )

    quote = akshare_fetcher._get_stock_realtime_quote_tencent("688691")

    assert quote is not None
    assert quote.volume == 10931723
    assert quote.amount == 1327404280


def test_tencent_realtime_volume_falls_back_to_legacy_hand_unit_when_not_cross_checkable(
    monkeypatch, akshare_fetcher
):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(
            200,
            _make_tencent_payload(
                volume="1234",
                turnover_rate="",
                circ_mv_yi="",
            ),
        ),
    )

    quote = akshare_fetcher._get_stock_realtime_quote_tencent("601006")

    assert quote is not None
    assert quote.volume == 123400


def test_hot_stocks_uses_eastmoney_hot_ranking_when_available(monkeypatch, akshare_fetcher):
    fake_akshare = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    monkeypatch.setattr(
        akshare_fetcher,
        "_get_eastmoney_hot_stocks",
        lambda _ak, n: [
            {
                "rank": 1,
                "code": "SZ000066",
                "name": "\u4e2d\u56fd\u957f\u57ce",
                "price": 21.8,
                "change_pct": 9.99,
                "source": "\u4e1c\u65b9\u8d22\u5bcc\u4eba\u6c14\u699c",
            }
        ],
    )

    result = akshare_fetcher.get_hot_stocks(5)

    assert result[0]["source"] == "\u4e1c\u65b9\u8d22\u5bcc\u4eba\u6c14\u699c"
    assert result[0]["name"] == "\u4e2d\u56fd\u957f\u57ce"


def test_hot_stocks_falls_back_to_xueqiu_when_primary_sources_empty(monkeypatch, akshare_fetcher):
    call_order = []

    def _eastmoney(_ak, _n):
        call_order.append("eastmoney_hot")
        return None

    def _up(_ak, _n):
        call_order.append("eastmoney_hot_up")
        return []

    def _xueqiu(_ak, _n):
        call_order.append("xueqiu")
        return [
            {
                "rank": 1,
                "code": "SH600004",
                "name": "\u534e\u590f\u94f6\u884c",
                "price": 7.21,
                "change_pct": None,
                "source": "\u96ea\u7403\u5173\u6ce8\u699c",
            }
        ]

    monkeypatch.setattr(akshare_fetcher, "_get_eastmoney_hot_stocks", _eastmoney)
    monkeypatch.setattr(akshare_fetcher, "_get_eastmoney_hot_up_stocks", _up)
    monkeypatch.setattr(akshare_fetcher, "_get_xueqiu_hot_stocks", _xueqiu)

    result = akshare_fetcher.get_hot_stocks(5)

    assert call_order == ["eastmoney_hot", "eastmoney_hot_up", "xueqiu"]
    assert result == [
        {
            "rank": 1,
            "code": "SH600004",
            "name": "\u534e\u590f\u94f6\u884c",
            "price": 7.21,
            "change_pct": None,
            "source": "\u96ea\u7403\u5173\u6ce8\u699c",
        }
    ]


def test_limit_up_pool_zero_pads_first_seal_times_before_sorting(monkeypatch, akshare_fetcher):
    df = pd.DataFrame(
        [
            {
                "\u4ee3\u7801": "000002",
                "\u540d\u79f0": "\u5348\u540e\u80a1",
                "\u6da8\u8dcc\u5e45": 10.0,
                "\u6700\u65b0\u4ef7": 12.3,
                "\u6210\u4ea4\u989d": 1,
                "\u6362\u624b\u7387": 2,
                "\u5c01\u677f\u8d44\u91d1": 3,
                "\u9996\u6b21\u5c01\u677f\u65f6\u95f4": 141354,
                "\u6700\u540e\u5c01\u677f\u65f6\u95f4": 141500,
                "\u70b8\u677f\u6b21\u6570": 0,
                "\u6da8\u505c\u7edf\u8ba1": "1/1",
                "\u8fde\u677f\u6570": 1,
                "\u6240\u5c5e\u884c\u4e1a": "\u5730\u4ea7",
            },
            {
                "\u4ee3\u7801": "000001",
                "\u540d\u79f0": "\u7ade\u4ef7\u80a1",
                "\u6da8\u8dcc\u5e45": 10.0,
                "\u6700\u65b0\u4ef7": 10.0,
                "\u6210\u4ea4\u989d": 1,
                "\u6362\u624b\u7387": 2,
                "\u5c01\u677f\u8d44\u91d1": 3,
                "\u9996\u6b21\u5c01\u677f\u65f6\u95f4": 92500,
                "\u6700\u540e\u5c01\u677f\u65f6\u95f4": 93000,
                "\u70b8\u677f\u6b21\u6570": 0,
                "\u6da8\u505c\u7edf\u8ba1": "1/1",
                "\u8fde\u677f\u6570": 1,
                "\u6240\u5c5e\u884c\u4e1a": "\u8ba1\u7b97\u673a",
            },
            {
                "\u4ee3\u7801": "000003",
                "\u540d\u79f0": "\u65e9\u76d8\u80a1",
                "\u6da8\u8dcc\u5e45": 10.0,
                "\u6700\u65b0\u4ef7": 11.0,
                "\u6210\u4ea4\u989d": 1,
                "\u6362\u624b\u7387": 2,
                "\u5c01\u677f\u8d44\u91d1": 3,
                "\u9996\u6b21\u5c01\u677f\u65f6\u95f4": 101500,
                "\u6700\u540e\u5c01\u677f\u65f6\u95f4": 102000,
                "\u70b8\u677f\u6b21\u6570": 0,
                "\u6da8\u505c\u7edf\u8ba1": "1/1",
                "\u8fde\u677f\u6570": 1,
                "\u6240\u5c5e\u884c\u4e1a": "\u7535\u5b50",
            },
        ]
    )
    fake_akshare = SimpleNamespace(stock_zt_pool_em=lambda date: df)
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    result = akshare_fetcher.get_limit_up_pool(date="20260511", n=3)

    assert [row["code"] for row in result] == ["000001", "000003", "000002"]
    assert result[0]["first_limit_time"] == "092500"
    assert result[0]["last_limit_time"] == "093000"
