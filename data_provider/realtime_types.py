# -*- coding: utf-8 -*-
"""
===================================
realtime quote\u7edf\u4e00\u7c7b\u578b\u5b9a\u4e49 & \u7194\u65ad\u673a\u5236
===================================

\u8bbe\u8ba1\u76ee\u6807:
1. \u7edf\u4e00\u5404data source\u7684realtime quote\u8fd4\u56de\u7ed3\u6784
2. \u5b9e\u73b0\u7194\u65ad/\u51b7\u5374\u673a\u5236; \u907f\u514d\u8fde\u7eedfailed\u65f6\u53cd\u590drequest
3. \u652f\u6301\u591adata source\u6545\u969c\u5207\u6362

\u4f7f\u7528\u65b9\u5f0f:
- \u6240\u6709 Fetcher \u7684 get_realtime_quote() \u7edf\u4e00\u8fd4\u56de UnifiedRealtimeQuote
- CircuitBreaker \u7ba1\u7406\u5404data source\u7684\u7194\u65adstatus
"""

import logging
import time
from threading import RLock
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# \u901a\u7528\u7c7b\u578b\u8f6c\u6362\u5de5\u5177\u51fd\u6570
# ============================================
# \u8bbe\u8ba1\u8bf4\u660e:
# \u5404data source\u8fd4\u56de\u7684\u539f\u59cb\u6570\u636e\u7c7b\u578b\u4e0d\u4e00\u81f4 (str/float/int/NaN);
# \u4f7f\u7528\u8fd9\u4e9b\u51fd\u6570\u7edf\u4e00\u8f6c\u6362; \u907f\u514d\u5728\u5404 Fetcher Medium\u91cd\u590d\u5b9a\u4e49.

def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """
    \u5b89\u5168\u8f6c\u6362\u4e3a\u6d6e\u70b9\u6570

    \u5904\u7406\u573a\u666f:
    - None / \u7a7a\u5b57\u7b26\u4e32 → default
    - pandas NaN / numpy NaN → default
    - \u6570\u503c\u5b57\u7b26\u4e32 → float
    - \u5df2\u662f\u6570\u503c → float

    Args:
        val: \u5f85\u8f6c\u6362\u7684\u503c
        default: \u8f6c\u6362failed\u65f6\u7684default\u503c

    Returns:
        \u8f6c\u6362\u540e\u7684\u6d6e\u70b9\u6570; ordefault\u503c
    """
    try:
        if val is None:
            return default

        # \u5904\u7406\u5b57\u7b26\u4e32
        if isinstance(val, str):
            val = val.strip()
            if val == "" or val == "-" or val == "--":
                return default

        # \u5904\u7406 pandas/numpy NaN
        # \u4f7f\u7528 math.isnan \u800c\u4e0d\u662f pd.isna; \u907f\u514d\u5f3a\u5236\u4f9d\u8d56 pandas
        import math
        try:
            if math.isnan(float(val)):
                return default
        except (ValueError, TypeError):
            pass

        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """
    \u5b89\u5168\u8f6c\u6362\u4e3a\u6574\u6570

    \u5148\u8f6c\u6362\u4e3a float; \u518d\u53d6\u6574; \u5904\u7406 "123.0" \u8fd9\u7c7b\u60c5\u51b5

    Args:
        val: \u5f85\u8f6c\u6362\u7684\u503c
        default: \u8f6c\u6362failed\u65f6\u7684default\u503c

    Returns:
        \u8f6c\u6362\u540e\u7684\u6574\u6570; ordefault\u503c
    """
    f_val = safe_float(val, default=None)
    if f_val is not None:
        return int(f_val)
    return default


class RealtimeSource(Enum):
    """realtime quotedata source"""
    EFINANCE = "efinance"           # Eastmoney (efinancelibrary)
    AKSHARE_EM = "akshare_em"       # Eastmoney (aksharelibrary)
    AKSHARE_SINA = "akshare_sina"   # Sina Finance
    AKSHARE_QQ = "akshare_qq"       # Tencent Finance
    TUSHARE = "tushare"             # Tushare Pro
    TICKFLOW = "tickflow"           # TickFlow
    TENCENT = "tencent"             # \u817e\u8baf\u76f4\u8fde
    SINA = "sina"                   # \u65b0\u6d6a\u76f4\u8fde
    STOOQ = "stooq"                 # Stooq US stock\u515c\u5e95
    LONGBRIDGE = "longbridge"       # Longbridge (US stock/HK stock\u515c\u5e95)
    FALLBACK = "fallback"           # \u964d\u7ea7\u515c\u5e95


@dataclass
class UnifiedRealtimeQuote:
    """
    \u7edf\u4e00realtime quote\u6570\u636e\u7ed3\u6784

    \u8bbe\u8ba1\u539f\u5219:
    - \u5404data source\u8fd4\u56de\u7684\u5b57\u6bb5\u53ef\u80fd\u4e0d\u540c; \u7f3a\u5931\u5b57\u6bb5\u7528 None \u8868\u793a
    - \u4e3b\u6d41\u7a0b\u4f7f\u7528 getattr(quote, field, None) \u83b7\u53d6; \u4fdd\u8bc1\u517c\u5bb9
    - source \u5b57\u6bb5\u6807\u8bb0\u6570\u636esource; \u4fbf\u4e8e\u8c03\u8bd5
    """
    code: str
    name: str = ""
    source: RealtimeSource = RealtimeSource.FALLBACK

    # === \u6570\u636e\u8d28\u91cf\u5143\u6570\u636e (\u7531 DataFetcherManager \u7edf\u4e00\u8865\u9f50)===
    fetched_at: Optional[str] = None             # \u672c\u7cfb\u7edf\u83b7\u53d6\u65f6\u95f4 (ISO 8601 datetime)
    provider_timestamp: Optional[str] = None     # Provider \u771f\u5b9e\u884c\u60c5\u65f6\u95f4 (ISO 8601 datetime)
    is_stale: Optional[bool] = None              # provider_timestamp \u8d85\u8fc7\u6700\u5c0f TTL \u9608\u503c\u65f6\u4e3a True
    stale_seconds: Optional[int] = None          # provider_timestamp \u8ddd fetched_at \u7684\u79d2\u6570
    fallback_from: Optional[str] = None          # \u6574\u6e90 fallback \u7684failed\u9996\u9009\u6e90 token
    market: Optional[str] = None                 # market\u6807\u7b7e (cn/hk/us/jp/kr/tw)
    currency: Optional[str] = None               # \u62a5\u4ef7\u5e01\u79cd (JPY/KRW/TWD/USD/HKD/CNY \u7b49)
    data_quality: Optional[str] = None           # ok/partial/unavailable
    missing_fields: Optional[list[str]] = None   # provider \u7f3a\u5931\u7684\u5173\u952e\u5b57\u6bb5

    # === \u6838\u5fc3price\u6570\u636e (\u51e0\u4e4e\u6240\u6709\u6e90\u90fd\u6709)===
    price: Optional[float] = None           # \u6700\u65b0\u4ef7
    change_pct: Optional[float] = None      # change\u5e45(%)
    change_amount: Optional[float] = None   # change\u989d

    # === \u91cf\u4ef7\u6307\u6807 (\u90e8\u5206\u6e90\u53ef\u80fd\u7f3a\u5931)===
    volume: Optional[int] = None            # volume (\u80a1; \u4e0ehistorydaily data\u53e3\u5f84\u4e00\u81f4)
    amount: Optional[float] = None          # amount (\u5143)
    volume_ratio: Optional[float] = None    # \u91cf\u6bd4
    turnover_rate: Optional[float] = None   # turnover(%)
    amplitude: Optional[float] = None       # \u632f\u5e45(%)

    # === price\u533a\u95f4 ===
    open_price: Optional[float] = None      # \u5f00\u76d8\u4ef7
    high: Optional[float] = None            # \u6700High\u4ef7
    low: Optional[float] = None             # \u6700Low\u4ef7
    pre_close: Optional[float] = None       # \u6628\u6536\u4ef7

    # === \u4f30\u503c\u6307\u6807 (\u4ec5\u4e1c\u8d22\u7b49\u5168\u91cf\u63a5\u53e3\u6709)===
    pe_ratio: Optional[float] = None        # PE ratio(\u52a8\u6001)
    pb_ratio: Optional[float] = None        # PB ratio
    total_mv: Optional[float] = None        # total market cap(\u5143)
    circ_mv: Optional[float] = None         # float market cap(\u5143)

    # === other\u6307\u6807 ===
    change_60d: Optional[float] = None      # 60\u65e5change\u5e45(%)
    high_52w: Optional[float] = None        # 52\u5468\u6700High
    low_52w: Optional[float] = None         # 52\u5468\u6700Low

    def to_dict(self) -> Dict[str, Any]:
        """\u8f6c\u6362\u4e3a\u5b57\u5178 (\u8fc7\u6ee4 None \u503c)"""
        result = {
            'code': self.code,
            'name': self.name,
            'source': self.source.value,
        }
        # \u53ea\u6dfb\u52a0\u975e None \u7684\u5b57\u6bb5
        optional_fields = [
            'fetched_at', 'provider_timestamp', 'is_stale', 'stale_seconds',
            'fallback_from', 'market', 'currency', 'data_quality', 'missing_fields',
            'price', 'change_pct', 'change_amount', 'volume', 'amount',
            'volume_ratio', 'turnover_rate', 'amplitude',
            'open_price', 'high', 'low', 'pre_close',
            'pe_ratio', 'pb_ratio', 'total_mv', 'circ_mv',
            'change_60d', 'high_52w', 'low_52w'
        ]
        for f in optional_fields:
            val = getattr(self, f, None)
            if val is not None:
                result[f] = val
        return result

    def has_basic_data(self) -> bool:
        """\u68c0check\u662f\u5426\u6709\u57fa\u672c\u7684price\u6570\u636e"""
        return self.price is not None and self.price > 0

    def has_volume_data(self) -> bool:
        """\u68c0check\u662f\u5426\u6709\u91cf\u4ef7\u6570\u636e"""
        return self.volume_ratio is not None or self.turnover_rate is not None


@dataclass
class ChipDistribution:
    """
    chip distribution\u6570\u636e

    \u53cd\u6620\u6301\u4ed3\u6210\u672c\u5206\u5e03\u548c\u83b7\u5229\u60c5\u51b5
    """
    code: str
    date: str = ""
    source: str = "akshare"

    # \u83b7\u5229\u60c5\u51b5
    profit_ratio: float = 0.0     # \u83b7\u5229\u6bd4\u4f8b(0-1)
    avg_cost: float = 0.0         # \u5e73\u5747\u6210\u672c

    # \u7b79\u7801\u96c6Medium\u5ea6
    cost_90_low: float = 0.0      # 90%\u7b79\u7801\u6210\u672c\u4e0b\u9650
    cost_90_high: float = 0.0     # 90%\u7b79\u7801\u6210\u672c\u4e0a\u9650
    concentration_90: float = 0.0  # 90%\u7b79\u7801\u96c6Medium\u5ea6 (\u8d8a\u5c0f\u8d8a\u96c6Medium)

    cost_70_low: float = 0.0      # 70%\u7b79\u7801\u6210\u672c\u4e0b\u9650
    cost_70_high: float = 0.0     # 70%\u7b79\u7801\u6210\u672c\u4e0a\u9650
    concentration_70: float = 0.0  # 70%\u7b79\u7801\u96c6Medium\u5ea6

    def to_dict(self) -> Dict[str, Any]:
        """\u8f6c\u6362\u4e3a\u5b57\u5178"""
        return {
            'code': self.code,
            'date': self.date,
            'source': self.source,
            'profit_ratio': self.profit_ratio,
            'avg_cost': self.avg_cost,
            'cost_90_low': self.cost_90_low,
            'cost_90_high': self.cost_90_high,
            'concentration_90': self.concentration_90,
            'concentration_70': self.concentration_70,
        }

    def get_chip_status(self, current_price: float) -> str:
        """
        \u83b7\u53d6\u7b79\u7801status\u63cf\u8ff0

        Args:
            current_price: \u5f53\u524d\u80a1\u4ef7

        Returns:
            \u7b79\u7801status\u63cf\u8ff0
        """
        status_parts = []

        # \u83b7\u5229\u6bd4\u4f8banalyze
        if self.profit_ratio >= 0.9:
            status_parts.append("\u83b7\u5229\u76d8\u6781High(\u83b7\u5229\u76d8>90%)")
        elif self.profit_ratio >= 0.7:
            status_parts.append("\u83b7\u5229\u76d8\u8f83High(\u83b7\u5229\u76d870-90%)")
        elif self.profit_ratio >= 0.5:
            status_parts.append("\u83b7\u5229\u76d8Medium\u7b49(\u83b7\u5229\u76d850-70%)")
        elif self.profit_ratio >= 0.3:
            status_parts.append("\u5957\u7262\u76d8Medium\u7b49(\u5957\u7262\u76d850-70%)")
        elif self.profit_ratio >= 0.1:
            status_parts.append("\u5957\u7262\u76d8\u8f83High(\u5957\u7262\u76d870-90%)")
        else:
            status_parts.append("\u5957\u7262\u76d8\u6781High(\u5957\u7262\u76d8>90%)")

        # \u7b79\u7801\u96c6Medium\u5ea6analyze (90%\u96c6Medium\u5ea6 < 10% \u8868\u793a\u96c6Medium)
        if self.concentration_90 < 0.08:
            status_parts.append("\u7b79\u7801High\u5ea6\u96c6Medium")
        elif self.concentration_90 < 0.15:
            status_parts.append("\u7b79\u7801\u8f83\u96c6Medium")
        elif self.concentration_90 < 0.25:
            status_parts.append("\u7b79\u7801\u5206\u6563\u5ea6Medium\u7b49")
        else:
            status_parts.append("\u7b79\u7801\u8f83\u5206\u6563")

        # \u6210\u672c\u4e0e\u73b0\u4ef7\u5173\u7cfb
        if current_price > 0 and self.avg_cost > 0:
            cost_diff = (current_price - self.avg_cost) / self.avg_cost * 100
            if cost_diff > 20:
                status_parts.append(f"\u73b0\u4ef7High\u4e8e\u5e73\u5747\u6210\u672c{cost_diff:.1f}%")
            elif cost_diff > 5:
                status_parts.append(f"\u73b0\u4ef7\u7565High\u4e8e\u6210\u672c{cost_diff:.1f}%")
            elif cost_diff > -5:
                status_parts.append("\u73b0\u4ef7\u63a5\u8fd1\u5e73\u5747\u6210\u672c")
            else:
                status_parts.append(f"\u73b0\u4ef7Low\u4e8e\u5e73\u5747\u6210\u672c{abs(cost_diff):.1f}%")

        return "; ".join(status_parts)


class CircuitBreaker:
    """
    \u7194\u65ad\u5668 - \u7ba1\u7406data source\u7684\u7194\u65ad/\u51b7\u5374status

    strategy:
    - \u8fde\u7eedfailed N \u6b21\u540e\u8fdb\u5165\u7194\u65adstatus
    - \u7194\u65ad\u671f\u95f4skipping\u8be5data source
    - \u51b7\u5374\u65f6\u95f4\u540e\u81ea\u52a8\u6062\u590d\u534a\u5f00status
    - \u534a\u5f00status\u4e0b\u5355\u6b21success\u5219\u5b8c\u5168\u6062\u590d; failed\u5219\u7ee7\u7eed\u7194\u65ad

    status\u673a:
    CLOSED (\u6b63\u5e38) --failedN\u6b21--> OPEN (\u7194\u65ad)--\u51b7\u5374\u65f6\u95f4\u5230--> HALF_OPEN (\u534a\u5f00)
    HALF_OPEN --success--> CLOSED
    HALF_OPEN --failed--> OPEN
    """

    # status\u5e38\u91cf
    CLOSED = "closed"      # \u6b63\u5e38status
    OPEN = "open"          # \u7194\u65adstatus (unavailable)
    HALF_OPEN = "half_open"  # \u534a\u5f00status (\u8bd5\u63a2request)

    def __init__(
        self,
        failure_threshold: int = 3,       # \u8fde\u7eedfailed\u6b21\u6570\u9608\u503c
        cooldown_seconds: float = 300.0,  # \u51b7\u5374\u65f6\u95f4 (\u79d2); default5\u5206\u949f
        half_open_max_calls: int = 1      # \u534a\u5f00status\u6700\u5927\u5c1d\u8bd5\u6b21\u6570
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_calls = half_open_max_calls

        # \u5404data sourcestatus {source_name: {state, failures, last_failure_time, half_open_calls}}
        self._states: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def _get_state_locked(self, source: str) -> Dict[str, Any]:
        """\u83b7\u53d6or\u521d\u59cb\u5316data sourcestatus (\u8c03\u7528\u65b9\u9700\u6301\u6709\u9501)."""
        if source not in self._states:
            self._states[source] = {
                'state': self.CLOSED,
                'failures': 0,
                'last_failure_time': 0.0,
                'half_open_calls': 0
            }
        return self._states[source]

    def is_available(self, source: str) -> bool:
        """
        \u68c0checkdata source\u662f\u5426\u53ef\u7528

        \u8fd4\u56de True \u8868\u793a\u53ef\u4ee5\u5c1d\u8bd5request
        \u8fd4\u56de False \u8868\u793a\u5e94skipping\u8be5data source
        """
        with self._lock:
            state = self._get_state_locked(source)
            current_time = time.time()

            if state['state'] == self.CLOSED:
                return True

            if state['state'] == self.OPEN:
                # \u68c0check\u51b7\u5374\u65f6\u95f4
                time_since_failure = current_time - state['last_failure_time']
                if time_since_failure >= self.cooldown_seconds:
                    # \u51b7\u5374\u5b8c\u6210; \u8fdb\u5165\u534a\u5f00status (\u4e0d\u9884\u5360\u540d\u989d; \u7531 HALF_OPEN \u5206\u652f\u7edf\u4e00\u7ba1\u7406)
                    state['state'] = self.HALF_OPEN
                    state['half_open_calls'] = 0
                    state['last_failure_time'] = current_time
                    logger.info(f"[\u7194\u65ad\u5668] {source} \u51b7\u5374\u5b8c\u6210; \u8fdb\u5165\u534a\u5f00status")
                    # Fall through to HALF_OPEN check below
                else:
                    remaining = self.cooldown_seconds - time_since_failure
                    logger.debug(f"[\u7194\u65ad\u5668] {source} \u5904\u4e8e\u7194\u65adstatus; \u5269\u4f59\u51b7\u5374\u65f6\u95f4: {remaining:.0f}s")
                    return False

            if state['state'] == self.HALF_OPEN:
                if state['half_open_calls'] < self.half_open_max_calls:
                    state['half_open_calls'] += 1
                    return True
                # \u6240\u6709\u63a2\u6d4b\u540d\u989d\u5df2\u7528\u5b8c；\u82e5\u51b7\u5374\u65f6\u95f4\u518d\u6b21\u5230\u671f\u4ecd\u672areceived
                # record_success/record_failure \u56de\u8c03; \u91cd\u7f6e\u540d\u989d\u5141\u8bb8\u91cd\u65b0\u63a2\u6d4b;
                # \u907f\u514d\u6c38\u4e45\u5361\u5728 HALF_OPEN.
                time_since_failure = current_time - state['last_failure_time']
                if time_since_failure >= self.cooldown_seconds:
                    state['half_open_calls'] = 1
                    state['last_failure_time'] = current_time
                    logger.info(f"[\u7194\u65ad\u5668] {source} \u534a\u5f00status\u63a2\u6d4b\u8d85\u65f6; \u91cd\u65b0\u63a2\u6d4b")
                    return True
                return False

            return True

    def record_inconclusive(self, source: str) -> None:
        """\u8bb0\u5f55\u4e0d\u786e\u5b9a\u7684\u63a2\u6d4bresult (\u5982\u8fd4\u56de None).

        \u4ec5\u5f71\u54cd HALF_OPEN status: \u5c06\u5176\u8f6c\u56de OPEN \u4ee5\u4fbf\u51b7\u5374\u540e\u91cd\u65b0\u63a2\u6d4b.
        CLOSED status\u4e0b\u4e3a\u7a7a\u64cd\u4f5c; \u4e0d\u5f71\u54cdfailed\u8ba1\u6570.
        """
        with self._lock:
            state = self._get_state_locked(source)
            if state['state'] == self.HALF_OPEN:
                state['state'] = self.OPEN
                state['half_open_calls'] = 0
                state['last_failure_time'] = time.time()
                logger.info(f"[\u7194\u65ad\u5668] {source} \u534a\u5f00\u63a2\u6d4bresult\u4e0d\u786e\u5b9a; \u91cd\u65b0\u8fdb\u5165\u51b7\u5374")

    def record_success(self, source: str) -> None:
        """\u8bb0\u5f55successrequest"""
        with self._lock:
            state = self._get_state_locked(source)

            if state['state'] == self.HALF_OPEN:
                # \u534a\u5f00status\u4e0bsuccess; \u5b8c\u5168\u6062\u590d
                logger.info(f"[\u7194\u65ad\u5668] {source} \u534a\u5f00statusrequestsuccess; \u6062\u590d\u6b63\u5e38")

            # \u91cd\u7f6estatus
            state['state'] = self.CLOSED
            state['failures'] = 0
            state['half_open_calls'] = 0

    def record_failure(self, source: str, error: Optional[str] = None) -> None:
        """\u8bb0\u5f55failedrequest"""
        with self._lock:
            state = self._get_state_locked(source)
            current_time = time.time()

            state['failures'] += 1
            state['last_failure_time'] = current_time

            if state['state'] == self.HALF_OPEN:
                # \u534a\u5f00status\u4e0bfailed; \u7ee7\u7eed\u7194\u65ad
                state['state'] = self.OPEN
                state['half_open_calls'] = 0
                logger.warning(f"[\u7194\u65ad\u5668] {source} \u534a\u5f00statusrequestfailed; \u7ee7\u7eed\u7194\u65ad {self.cooldown_seconds}s")
            elif state['failures'] >= self.failure_threshold:
                # \u8fbe\u5230\u9608\u503c; \u8fdb\u5165\u7194\u65ad
                state['state'] = self.OPEN
                logger.warning(f"[\u7194\u65ad\u5668] {source} \u8fde\u7eedfailed {state['failures']} \u6b21; \u8fdb\u5165\u7194\u65adstatus "
                              f"(\u51b7\u5374 {self.cooldown_seconds}s)")
                if error:
                    logger.warning(f"[\u7194\u65ad\u5668] \u6700\u540eerror: {error}")

    def get_status(self) -> Dict[str, str]:
        """\u83b7\u53d6\u6240\u6709data sourcestatus"""
        with self._lock:
            return {source: info['state'] for source, info in self._states.items()}

    def reset(self, source: Optional[str] = None) -> None:
        """\u91cd\u7f6e\u7194\u65ad\u5668status"""
        with self._lock:
            if source:
                if source in self._states:
                    del self._states[source]
            else:
                self._states.clear()


# \u5168\u5c40\u7194\u65ad\u5668\u5b9e\u4f8b (realtime quote\u4e13\u7528)
_realtime_circuit_breaker = CircuitBreaker(
    failure_threshold=3,      # \u8fde\u7eedfailed3\u6b21\u7194\u65ad
    cooldown_seconds=300.0,   # \u51b7\u53745\u5206\u949f
    half_open_max_calls=1
)

# \u7b79\u7801\u63a5\u53e3\u7194\u65ad\u5668 (\u66f4\u4fdd\u5b88\u7684strategy; \u56e0\u4e3a\u8be5\u63a5\u53e3\u66f4\u4e0d\u7a33\u5b9a)
_chip_circuit_breaker = CircuitBreaker(
    failure_threshold=2,      # \u8fde\u7eedfailed2\u6b21\u7194\u65ad
    cooldown_seconds=600.0,   # \u51b7\u537410\u5206\u949f
    half_open_max_calls=1
)


def get_realtime_circuit_breaker() -> CircuitBreaker:
    """\u83b7\u53d6realtime quote\u7194\u65ad\u5668"""
    return _realtime_circuit_breaker


def get_chip_circuit_breaker() -> CircuitBreaker:
    """\u83b7\u53d6\u7b79\u7801\u63a5\u53e3\u7194\u65ad\u5668"""
    return _chip_circuit_breaker
