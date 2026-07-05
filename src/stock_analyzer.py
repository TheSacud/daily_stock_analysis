# -*- coding: utf-8 -*-
"""
===================================
\u8d8b\u52bf\u4ea4\u6613analyze\u5668 - \u57fa\u4e8euser\u4ea4\u6613\u7406\u5ff5
===================================

\u4ea4\u6613\u7406\u5ff5\u6838\u5fc3\u539f\u5219:
1. \u4e25\u8fdbstrategy - \u4e0d\u8ffdHigh; \u8ffd\u6c42\u6bcf\u7b14\u4ea4\u6613success\u7387
2. \u8d8b\u52bf\u4ea4\u6613 - MA5>MA10>MA20 \u591a\u5934\u6392\u5217; \u987a\u52bf\u800c\u4e3a
3. \u6548\u7387\u4f18\u5148 - \u5173\u6ce8\u7b79\u7801\u7ed3\u6784\u597d\u7684\u80a1\u7968
4. \u4e70\u70b9Slightly \u597d - \u5728 MA5/MA10 \u9644\u8fd1\u56de\u8e29\u4e70\u5165

\u6280\u672f\u6807\u51c6:
- \u591a\u5934\u6392\u5217: MA5 > MA10 > MA20
- \u4e56\u79bb\u7387: (Close - MA5) / MA5 < 5% (\u4e0d\u8ffdHigh)
- \u91cf\u80fd\u5f62\u6001: \u7f29\u91cf\u56de\u8c03\u4f18\u5148
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum

import pandas as pd
import numpy as np

from src.config import get_config
from src.schemas.decision_scale import signal_key_for_score

logger = logging.getLogger(__name__)


class TrendStatus(Enum):
    """\u8d8b\u52bfstatus\u679a\u4e3e"""
    STRONG_BULL = "\u5f3a\u52bf\u591a\u5934"      # MA5 > MA10 > MA20; \u4e14\u95f4\u8ddd\u6269\u5927
    BULL = "\u591a\u5934\u6392\u5217"             # MA5 > MA10 > MA20
    WEAK_BULL = "\u5f31\u52bf\u591a\u5934"        # MA5 > MA10; \u4f46 MA10 < MA20
    CONSOLIDATION = "\u76d8\u6574"        # \u5747\u7ebf\u7f20\u7ed5
    WEAK_BEAR = "\u5f31\u52bf\u7a7a\u5934"        # MA5 < MA10; \u4f46 MA10 > MA20
    BEAR = "\u7a7a\u5934\u6392\u5217"             # MA5 < MA10 < MA20
    STRONG_BEAR = "\u5f3a\u52bf\u7a7a\u5934"      # MA5 < MA10 < MA20; \u4e14\u95f4\u8ddd\u6269\u5927


class VolumeStatus(Enum):
    """\u91cf\u80fdstatus\u679a\u4e3e"""
    HEAVY_VOLUME_UP = "\u653e\u91cf\u4e0a\u6da8"       # \u91cf\u4ef7\u9f50\u5347
    HEAVY_VOLUME_DOWN = "\u653e\u91cf\u4e0b\u8dcc"     # \u653e\u91cf\u6740\u8dcc
    SHRINK_VOLUME_UP = "\u7f29\u91cf\u4e0a\u6da8"      # \u65e0\u91cf\u4e0a\u6da8
    SHRINK_VOLUME_DOWN = "\u7f29\u91cf\u56de\u8c03"    # \u7f29\u91cf\u56de\u8c03 (\u597d)
    NORMAL = "\u91cf\u80fd\u6b63\u5e38"


class BuySignal(Enum):
    """\u4e70\u5165\u4fe1\u53f7\u679a\u4e3e"""
    STRONG_BUY = "\u5f3a\u70c8\u4e70\u5165"       # \u591a\u6761\u4ef6\u6ee1\u8db3
    BUY = "\u4e70\u5165"                  # \u57fa\u672c\u6761\u4ef6\u6ee1\u8db3
    HOLD = "\u6301\u6709"                 # \u5df2\u6301\u6709\u53ef\u7ee7\u7eed
    WAIT = "Watch"                 # waiting\u66f4\u597d\u65f6\u673a
    SELL = "\u5356\u51fa"                 # \u8d8b\u52bf\u8f6c\u5f31
    STRONG_SELL = "\u5f3a\u70c8\u5356\u51fa"      # \u8d8b\u52bf\u7834\u574f


class MACDStatus(Enum):
    """MACDstatus\u679a\u4e3e"""
    GOLDEN_CROSS_ZERO = "\u96f6\u8f74\u4e0a\u91d1\u53c9"      # DIF\u4e0a\u7a7fDEA; \u4e14\u5728\u96f6\u8f74\u4e0a\u65b9
    GOLDEN_CROSS = "\u91d1\u53c9"                # DIF\u4e0a\u7a7fDEA
    BULLISH = "\u591a\u5934"                    # DIF>DEA>0
    CROSSING_UP = "\u4e0a\u7a7f\u96f6\u8f74"             # DIF\u4e0a\u7a7f\u96f6\u8f74
    CROSSING_DOWN = "\u4e0b\u7a7f\u96f6\u8f74"           # DIF\u4e0b\u7a7f\u96f6\u8f74
    BEARISH = "\u7a7a\u5934"                    # DIF<DEA<0
    DEATH_CROSS = "\u6b7b\u53c9"                # DIF\u4e0b\u7a7fDEA


class RSIStatus(Enum):
    """RSIstatus\u679a\u4e3e"""
    OVERBOUGHT = "Overbought"        # RSI > 70
    STRONG_BUY = "\u5f3a\u52bf\u4e70\u5165"    # 50 < RSI < 70
    NEUTRAL = "Medium"          # 40 <= RSI <= 60
    WEAK = "\u5f31\u52bf"             # 30 < RSI < 40
    OVERSOLD = "Oversold"         # RSI < 30


@dataclass
class TrendAnalysisResult:
    """\u8d8b\u52bfanalysis result"""
    code: str

    # \u8d8b\u52bf\u5224\u65ad
    trend_status: TrendStatus = TrendStatus.CONSOLIDATION
    ma_alignment: str = ""           # \u5747\u7ebf\u6392\u5217\u63cf\u8ff0
    trend_strength: float = 0.0      # \u8d8b\u52bf\u5f3a\u5ea6 0-100

    # \u5747\u7ebf\u6570\u636e
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    current_price: float = 0.0

    # \u4e56\u79bb\u7387 (\u4e0e MA5 \u7684Slightly \u79bb\u5ea6)
    bias_ma5: float = 0.0            # (Close - MA5) / MA5 * 100
    bias_ma10: float = 0.0
    bias_ma20: float = 0.0

    # \u91cf\u80fdanalyze
    volume_status: VolumeStatus = VolumeStatus.NORMAL
    volume_ratio_5d: float = 0.0     # \u5f53\u65e5volume/5\u65e5\u5747\u91cf
    volume_trend: str = ""           # \u91cf\u80fd\u8d8b\u52bf\u63cf\u8ff0

    # \u652f\u6491\u538b\u529b
    support_ma5: bool = False        # MA5 \u662f\u5426\u6784\u6210\u652f\u6491
    support_ma10: bool = False       # MA10 \u662f\u5426\u6784\u6210\u652f\u6491
    resistance_levels: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)

    # MACD \u6307\u6807
    macd_dif: float = 0.0          # DIF \u5feb\u7ebf
    macd_dea: float = 0.0          # DEA \u6162\u7ebf
    macd_bar: float = 0.0           # MACD \u67f1\u72b6\u56fe
    macd_status: MACDStatus = MACDStatus.BULLISH
    macd_signal: str = ""            # MACD \u4fe1\u53f7\u63cf\u8ff0

    # RSI \u6307\u6807
    rsi_6: float = 0.0              # RSI(6) \u77ed\u671f
    rsi_12: float = 0.0             # RSI(12) Medium\u671f
    rsi_24: float = 0.0             # RSI(24) \u957f\u671f
    rsi_status: RSIStatus = RSIStatus.NEUTRAL
    rsi_signal: str = ""              # RSI \u4fe1\u53f7\u63cf\u8ff0

    # \u4e70\u5165\u4fe1\u53f7
    buy_signal: BuySignal = BuySignal.WAIT
    signal_score: int = 0            # \u7efc\u5408\u8bc4\u5206 0-100
    signal_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'trend_status': self.trend_status.value,
            'ma_alignment': self.ma_alignment,
            'trend_strength': self.trend_strength,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'ma60': self.ma60,
            'current_price': self.current_price,
            'bias_ma5': self.bias_ma5,
            'bias_ma10': self.bias_ma10,
            'bias_ma20': self.bias_ma20,
            'volume_status': self.volume_status.value,
            'volume_ratio_5d': self.volume_ratio_5d,
            'volume_trend': self.volume_trend,
            'support_ma5': self.support_ma5,
            'support_ma10': self.support_ma10,
            'buy_signal': self.buy_signal.value,
            'signal_score': self.signal_score,
            'signal_reasons': self.signal_reasons,
            'risk_factors': self.risk_factors,
            'macd_dif': self.macd_dif,
            'macd_dea': self.macd_dea,
            'macd_bar': self.macd_bar,
            'macd_status': self.macd_status.value,
            'macd_signal': self.macd_signal,
            'rsi_6': self.rsi_6,
            'rsi_12': self.rsi_12,
            'rsi_24': self.rsi_24,
            'rsi_status': self.rsi_status.value,
            'rsi_signal': self.rsi_signal,
        }


class StockTrendAnalyzer:
    """
    \u80a1\u7968\u8d8b\u52bfanalyze\u5668

    \u57fa\u4e8euser\u4ea4\u6613\u7406\u5ff5\u5b9e\u73b0:
    1. \u8d8b\u52bf\u5224\u65ad - MA5>MA10>MA20 \u591a\u5934\u6392\u5217
    2. \u4e56\u79bb\u7387\u68c0\u6d4b - \u4e0d\u8ffdHigh; Slightly \u79bb MA5 \u8d85\u8fc7 5% \u4e0d\u4e70
    3. \u91cf\u80fdanalyze - Slightly \u597d\u7f29\u91cf\u56de\u8c03
    4. \u4e70\u70b9\u8bc6\u522b - \u56de\u8e29 MA5/MA10 \u652f\u6491
    5. MACD \u6307\u6807 - \u8d8b\u52bf\u786e\u8ba4\u548c\u91d1\u53c9\u6b7b\u53c9\u4fe1\u53f7
    6. RSI \u6307\u6807 - OverboughtOversold\u5224\u65ad
    """

    # \u4ea4\u6613parameterconfig (BIAS_THRESHOLD \u4ece Config \u8bfb\u53d6; \u89c1 _generate_signal)
    VOLUME_SHRINK_RATIO = 0.7   # \u7f29\u91cf\u5224\u65ad\u9608\u503c (\u5f53\u65e5\u91cf/5\u65e5\u5747\u91cf)
    VOLUME_HEAVY_RATIO = 1.5    # \u653e\u91cf\u5224\u65ad\u9608\u503c
    MA_SUPPORT_TOLERANCE = 0.02  # MA \u652f\u6491\u5224\u65ad\u5bb9\u5fcd\u5ea6 (2%)

    # MACD parameter (\u6807\u51c612/26/9)
    MACD_FAST = 12              # \u5feb\u7ebf\u5468\u671f
    MACD_SLOW = 26             # \u6162\u7ebf\u5468\u671f
    MACD_SIGNAL = 9             # \u4fe1\u53f7\u7ebf\u5468\u671f

    # RSI parameter
    RSI_SHORT = 6               # \u77ed\u671fRSI\u5468\u671f
    RSI_MID = 12               # Medium\u671fRSI\u5468\u671f
    RSI_LONG = 24              # \u957f\u671fRSI\u5468\u671f
    RSI_OVERBOUGHT = 70        # Overbought\u9608\u503c
    RSI_OVERSOLD = 30          # Oversold\u9608\u503c

    def __init__(self):
        """\u521d\u59cb\u5316analyze\u5668"""
        pass

    def analyze(self, df: pd.DataFrame, code: str) -> TrendAnalysisResult:
        """
        analyze stock\u8d8b\u52bf

        Args:
            df: \u5305\u542b OHLCV \u6570\u636e\u7684 DataFrame
            code: stock code

        Returns:
            TrendAnalysisResult analysis result
        """
        result = TrendAnalysisResult(code=code)

        if df is None or df.empty or len(df) < 20:
            logger.warning(f"{code} \u6570\u636e\u4e0d\u8db3; \u65e0\u6cd5\u8fdb\u884c\u8d8b\u52bfanalyze")
            result.risk_factors.append("\u6570\u636e\u4e0d\u8db3; \u65e0\u6cd5\u5b8c\u6210analyze")
            return result

        # \u786e\u4fdd\u6570\u636e\u6309date\u6392\u5e8f
        df = df.sort_values('date').reset_index(drop=True)

        # \u8ba1\u7b97\u5747\u7ebf
        df = self._calculate_mas(df)

        # \u8ba1\u7b97 MACD \u548c RSI
        df = self._calculate_macd(df)
        df = self._calculate_rsi(df)

        # \u83b7\u53d6\u6700\u65b0\u6570\u636e
        latest = df.iloc[-1]
        result.current_price = float(latest['close'])
        result.ma5 = float(latest['MA5'])
        result.ma10 = float(latest['MA10'])
        result.ma20 = float(latest['MA20'])
        result.ma60 = float(latest.get('MA60', 0))

        # 1. \u8d8b\u52bf\u5224\u65ad
        self._analyze_trend(df, result)

        # 2. \u4e56\u79bb\u7387\u8ba1\u7b97
        self._calculate_bias(result)

        # 3. \u91cf\u80fdanalyze
        self._analyze_volume(df, result)

        # 4. \u652f\u6491\u538b\u529banalyze
        self._analyze_support_resistance(df, result)

        # 5. MACD analyze
        self._analyze_macd(df, result)

        # 6. RSI analyze
        self._analyze_rsi(df, result)

        # 7. \u751f\u6210\u4e70\u5165\u4fe1\u53f7
        self._generate_signal(result)

        return result

    def _calculate_mas(self, df: pd.DataFrame) -> pd.DataFrame:
        """\u8ba1\u7b97\u5747\u7ebf"""
        df = df.copy()
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA10'] = df['close'].rolling(window=10).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        if len(df) >= 60:
            df['MA60'] = df['close'].rolling(window=60).mean()
        else:
            df['MA60'] = df['MA20']  # \u6570\u636e\u4e0d\u8db3\u65f6\u4f7f\u7528 MA20 \u66ff\u4ee3
        return df

    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        \u8ba1\u7b97 MACD \u6307\u6807

        \u516c\u5f0f:
        - EMA(12): 12\u65e5index\u79fb\u52a8\u5e73\u5747
        - EMA(26): 26\u65e5index\u79fb\u52a8\u5e73\u5747
        - DIF = EMA(12) - EMA(26)
        - DEA = EMA(DIF, 9)
        - MACD = (DIF - DEA) * 2
        """
        df = df.copy()

        # \u8ba1\u7b97\u5feb\u6162\u7ebf EMA
        ema_fast = df['close'].ewm(span=self.MACD_FAST, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.MACD_SLOW, adjust=False).mean()

        # \u8ba1\u7b97\u5feb\u7ebf DIF
        df['MACD_DIF'] = ema_fast - ema_slow

        # \u8ba1\u7b97\u4fe1\u53f7\u7ebf DEA
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=self.MACD_SIGNAL, adjust=False).mean()

        # \u8ba1\u7b97\u67f1\u72b6\u56fe
        df['MACD_BAR'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2

        return df

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        \u8ba1\u7b97 RSI \u6307\u6807 (Wilder's EMA / SMMA \u53e3\u5f84)

        \u516c\u5f0f:
        - avg_gain / avg_loss \u4f7f\u7528 ewm(alpha=1/period, adjust=False)
        - RS = avg_gain / avg_loss
        - RSI = 100 - (100 / (1 + RS))
        """
        df = df.copy()

        for period in [self.RSI_SHORT, self.RSI_MID, self.RSI_LONG]:
            # \u8ba1\u7b97price\u53d8\u5316
            delta = df['close'].diff()

            # \u5206\u79bb\u4e0a\u6da8\u548c\u4e0b\u8dcc
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # \u4f7f\u7528 Wilder's EMA / SMMA \u53e3\u5f84; \u4e0e\u5e38\u89c1 RSI \u56fe\u8868\u5de5\u5177\u4fdd\u6301\u4e00\u81f4.
            avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

            # \u8ba1\u7b97 RS \u548c RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # \u586b\u5145 NaN \u503c
            rsi = rsi.fillna(50)  # defaultMedium\u503c

            # \u6dfb\u52a0\u5230 DataFrame
            col_name = f'RSI_{period}'
            df[col_name] = rsi

        return df

    def _analyze_trend(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analyze\u8d8b\u52bfstatus

        \u6838\u5fc3\u903b\u8f91: \u5224\u65ad\u5747\u7ebf\u6392\u5217\u548c\u8d8b\u52bf\u5f3a\u5ea6
        """
        ma5, ma10, ma20 = result.ma5, result.ma10, result.ma20

        # \u5224\u65ad\u5747\u7ebf\u6392\u5217
        if ma5 > ma10 > ma20:
            # \u68c0check\u95f4\u8ddd\u662f\u5426\u5728\u6269\u5927 (\u5f3a\u52bf)
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev['MA5'] - prev['MA20']) / prev['MA20'] * 100 if prev['MA20'] > 0 else 0
            curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0

            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BULL
                result.ma_alignment = "\u5f3a\u52bf\u591a\u5934\u6392\u5217; \u5747\u7ebf\u53d1\u6563\u4e0a\u884c"
                result.trend_strength = 90
            else:
                result.trend_status = TrendStatus.BULL
                result.ma_alignment = "\u591a\u5934\u6392\u5217 MA5>MA10>MA20"
                result.trend_strength = 75

        elif ma5 > ma10 and ma10 <= ma20:
            result.trend_status = TrendStatus.WEAK_BULL
            result.ma_alignment = "\u5f31\u52bf\u591a\u5934; MA5>MA10 \u4f46 MA10≤MA20"
            result.trend_strength = 55

        elif ma5 < ma10 < ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev['MA20'] - prev['MA5']) / prev['MA5'] * 100 if prev['MA5'] > 0 else 0
            curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0

            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BEAR
                result.ma_alignment = "\u5f3a\u52bf\u7a7a\u5934\u6392\u5217; \u5747\u7ebf\u53d1\u6563\u4e0b\u884c"
                result.trend_strength = 10
            else:
                result.trend_status = TrendStatus.BEAR
                result.ma_alignment = "\u7a7a\u5934\u6392\u5217 MA5<MA10<MA20"
                result.trend_strength = 25

        elif ma5 < ma10 and ma10 >= ma20:
            result.trend_status = TrendStatus.WEAK_BEAR
            result.ma_alignment = "\u5f31\u52bf\u7a7a\u5934; MA5<MA10 \u4f46 MA10≥MA20"
            result.trend_strength = 40

        else:
            result.trend_status = TrendStatus.CONSOLIDATION
            result.ma_alignment = "\u5747\u7ebf\u7f20\u7ed5; \u8d8b\u52bf\u4e0d\u660e"
            result.trend_strength = 50

    def _calculate_bias(self, result: TrendAnalysisResult) -> None:
        """
        \u8ba1\u7b97\u4e56\u79bb\u7387

        \u4e56\u79bb\u7387 = (\u73b0\u4ef7 - \u5747\u7ebf) / \u5747\u7ebf * 100%

        \u4e25\u8fdbstrategy: \u4e56\u79bb\u7387\u8d85\u8fc7 5% \u4e0d\u8ffdHigh
        """
        price = result.current_price

        if result.ma5 > 0:
            result.bias_ma5 = (price - result.ma5) / result.ma5 * 100
        if result.ma10 > 0:
            result.bias_ma10 = (price - result.ma10) / result.ma10 * 100
        if result.ma20 > 0:
            result.bias_ma20 = (price - result.ma20) / result.ma20 * 100

    def _analyze_volume(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analyze\u91cf\u80fd

        Slightly \u597d: \u7f29\u91cf\u56de\u8c03 > \u653e\u91cf\u4e0a\u6da8 > \u7f29\u91cf\u4e0a\u6da8 > \u653e\u91cf\u4e0b\u8dcc
        """
        if len(df) < 5:
            return

        latest = df.iloc[-1]
        vol_5d_avg = df['volume'].iloc[-6:-1].mean()

        if vol_5d_avg > 0:
            result.volume_ratio_5d = float(latest['volume']) / vol_5d_avg

        # \u5224\u65adprice\u53d8\u5316
        prev_close = df.iloc[-2]['close']
        price_change = (latest['close'] - prev_close) / prev_close * 100

        # \u91cf\u80fdstatus\u5224\u65ad
        if result.volume_ratio_5d >= self.VOLUME_HEAVY_RATIO:
            if price_change > 0:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_UP
                result.volume_trend = "\u653e\u91cf\u4e0a\u6da8; \u591a\u5934\u529b\u91cf\u5f3a\u52b2"
            else:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_DOWN
                result.volume_trend = "\u653e\u91cf\u4e0b\u8dcc; \u6ce8\u610f\u98ce\u9669"
        elif result.volume_ratio_5d <= self.VOLUME_SHRINK_RATIO:
            if price_change > 0:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_UP
                result.volume_trend = "\u7f29\u91cf\u4e0a\u6da8; \u4e0a\u653b\u52a8\u80fd\u4e0d\u8db3"
            else:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_DOWN
                result.volume_trend = "\u7f29\u91cf\u56de\u8c03; \u6d17\u76d8\u7279\u5f81\u660e\u663e (\u597d)"
        else:
            result.volume_status = VolumeStatus.NORMAL
            result.volume_trend = "\u91cf\u80fd\u6b63\u5e38"

    def _analyze_support_resistance(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analyze\u652f\u6491\u538b\u529bcharacters

        \u4e70\u70b9Slightly \u597d: \u56de\u8e29 MA5/MA10 \u83b7\u5f97\u652f\u6491
        """
        price = result.current_price

        # \u68c0check\u662f\u5426\u5728 MA5 \u9644\u8fd1\u83b7\u5f97\u652f\u6491
        if result.ma5 > 0:
            ma5_distance = abs(price - result.ma5) / result.ma5
            if ma5_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma5:
                result.support_ma5 = True
                result.support_levels.append(result.ma5)

        # \u68c0check\u662f\u5426\u5728 MA10 \u9644\u8fd1\u83b7\u5f97\u652f\u6491
        if result.ma10 > 0:
            ma10_distance = abs(price - result.ma10) / result.ma10
            if ma10_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma10:
                result.support_ma10 = True
                if result.ma10 not in result.support_levels:
                    result.support_levels.append(result.ma10)

        # MA20 \u4f5c\u4e3a\u91cd\u8981\u652f\u6491
        if result.ma20 > 0 and price >= result.ma20:
            result.support_levels.append(result.ma20)

        # \u8fd1\u671fHigh\u70b9\u4f5c\u4e3a\u538b\u529b
        if len(df) >= 20:
            recent_high = df['high'].iloc[-20:].max()
            if recent_high > price:
                result.resistance_levels.append(recent_high)

    def _analyze_macd(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analyze MACD \u6307\u6807

        \u6838\u5fc3\u4fe1\u53f7:
        - \u96f6\u8f74\u4e0a\u91d1\u53c9: \u6700\u5f3a\u4e70\u5165\u4fe1\u53f7
        - \u91d1\u53c9: DIF \u4e0a\u7a7f DEA
        - \u6b7b\u53c9: DIF \u4e0b\u7a7f DEA
        """
        if len(df) < self.MACD_SLOW:
            result.macd_signal = "\u6570\u636e\u4e0d\u8db3"
            return

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # \u83b7\u53d6 MACD \u6570\u636e
        result.macd_dif = float(latest['MACD_DIF'])
        result.macd_dea = float(latest['MACD_DEA'])
        result.macd_bar = float(latest['MACD_BAR'])

        # \u5224\u65ad\u91d1\u53c9\u6b7b\u53c9
        prev_dif_dea = prev['MACD_DIF'] - prev['MACD_DEA']
        curr_dif_dea = result.macd_dif - result.macd_dea

        # \u91d1\u53c9: DIF \u4e0a\u7a7f DEA
        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0

        # \u6b7b\u53c9: DIF \u4e0b\u7a7f DEA
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0

        # \u96f6\u8f74\u7a7f\u8d8a
        prev_zero = prev['MACD_DIF']
        curr_zero = result.macd_dif
        is_crossing_up = prev_zero <= 0 and curr_zero > 0
        is_crossing_down = prev_zero >= 0 and curr_zero < 0

        # \u5224\u65ad MACD status
        if is_golden_cross and curr_zero > 0:
            result.macd_status = MACDStatus.GOLDEN_CROSS_ZERO
            result.macd_signal = "⭐ \u96f6\u8f74\u4e0a\u91d1\u53c9; \u5f3a\u70c8\u4e70\u5165\u4fe1\u53f7！"
        elif is_crossing_up:
            result.macd_status = MACDStatus.CROSSING_UP
            result.macd_signal = "⚡ DIF\u4e0a\u7a7f\u96f6\u8f74; \u8d8b\u52bf\u8f6c\u5f3a"
        elif is_golden_cross:
            result.macd_status = MACDStatus.GOLDEN_CROSS
            result.macd_signal = "✅ \u91d1\u53c9; \u8d8b\u52bf\u5411\u4e0a"
        elif is_death_cross:
            result.macd_status = MACDStatus.DEATH_CROSS
            result.macd_signal = "❌ \u6b7b\u53c9; \u8d8b\u52bf\u5411\u4e0b"
        elif is_crossing_down:
            result.macd_status = MACDStatus.CROSSING_DOWN
            result.macd_signal = "⚠️ DIF\u4e0b\u7a7f\u96f6\u8f74; \u8d8b\u52bf\u8f6c\u5f31"
        elif result.macd_dif > 0 and result.macd_dea > 0:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "✓ \u591a\u5934\u6392\u5217; \u6301\u7eed\u4e0a\u6da8"
        elif result.macd_dif < 0 and result.macd_dea < 0:
            result.macd_status = MACDStatus.BEARISH
            result.macd_signal = "⚠ \u7a7a\u5934\u6392\u5217; \u6301\u7eed\u4e0b\u8dcc"
        else:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = " MACD Medium\u533a\u57df"

    def _analyze_rsi(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        analyze RSI \u6307\u6807

        \u6838\u5fc3\u5224\u65ad:
        - RSI > 70: Overbought; \u8c28\u614e\u8ffdHigh
        - RSI < 30: Oversold; \u5173\u6ce8\u53cd\u5f39
        - 40-60: Medium\u533a\u57df
        """
        if len(df) < self.RSI_LONG:
            result.rsi_signal = "\u6570\u636e\u4e0d\u8db3"
            return

        latest = df.iloc[-1]

        # \u83b7\u53d6 RSI \u6570\u636e
        result.rsi_6 = float(latest[f'RSI_{self.RSI_SHORT}'])
        result.rsi_12 = float(latest[f'RSI_{self.RSI_MID}'])
        result.rsi_24 = float(latest[f'RSI_{self.RSI_LONG}'])

        # \u4ee5Medium\u671f RSI(12) \u4e3a\u4e3b\u8fdb\u884c\u5224\u65ad
        rsi_mid = result.rsi_12

        # \u5224\u65ad RSI status
        if rsi_mid > self.RSI_OVERBOUGHT:
            result.rsi_status = RSIStatus.OVERBOUGHT
            result.rsi_signal = f"⚠️ RSIOverbought({rsi_mid:.1f}>70); \u77ed\u671f\u56de\u8c03\u98ce\u9669High"
        elif rsi_mid > 60:
            result.rsi_status = RSIStatus.STRONG_BUY
            result.rsi_signal = f"✅ RSI\u5f3a\u52bf({rsi_mid:.1f}); \u591a\u5934\u529b\u91cf\u5145\u8db3"
        elif rsi_mid >= 40:
            result.rsi_status = RSIStatus.NEUTRAL
            result.rsi_signal = f" RSIMedium({rsi_mid:.1f}); \u9707\u8361\u6574\u7406Medium"
        elif rsi_mid >= self.RSI_OVERSOLD:
            result.rsi_status = RSIStatus.WEAK
            result.rsi_signal = f"⚡ RSI\u5f31\u52bf({rsi_mid:.1f}); \u5173\u6ce8\u53cd\u5f39"
        else:
            result.rsi_status = RSIStatus.OVERSOLD
            result.rsi_signal = f"⭐ RSIOversold({rsi_mid:.1f}<30); \u53cd\u5f39\u673a\u4f1a\u5927"

    def _generate_signal(self, result: TrendAnalysisResult) -> None:
        """
        \u751f\u6210\u4e70\u5165\u4fe1\u53f7

        \u7efc\u5408\u8bc4\u5206\u7cfb\u7edf:
        - \u8d8b\u52bf (30\u5206): \u591a\u5934\u6392\u5217\u5f97\u5206High
        - \u4e56\u79bb\u7387 (20\u5206): \u63a5\u8fd1 MA5 \u5f97\u5206High
        - \u91cf\u80fd (15\u5206): \u7f29\u91cf\u56de\u8c03\u5f97\u5206High
        - \u652f\u6491 (10\u5206): \u83b7\u5f97\u5747\u7ebf\u652f\u6491\u5f97\u5206High
        - MACD (15\u5206): \u91d1\u53c9\u548c\u591a\u5934\u5f97\u5206High
        - RSI (10\u5206): Oversold\u548c\u5f3a\u52bf\u5f97\u5206High
        """
        score = 0
        reasons = []
        risks = []

        # === \u8d8b\u52bf\u8bc4\u5206 (30\u5206)===
        trend_scores = {
            TrendStatus.STRONG_BULL: 30,
            TrendStatus.BULL: 26,
            TrendStatus.WEAK_BULL: 18,
            TrendStatus.CONSOLIDATION: 12,
            TrendStatus.WEAK_BEAR: 8,
            TrendStatus.BEAR: 4,
            TrendStatus.STRONG_BEAR: 0,
        }
        trend_score = trend_scores.get(result.trend_status, 12)
        score += trend_score

        if result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            reasons.append(f"✅ {result.trend_status.value}; \u987a\u52bf\u505a\u591a")
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            risks.append(f"⚠️ {result.trend_status.value}; \u4e0d\u5b9c\u505a\u591a")

        # === \u4e56\u79bb\u7387\u8bc4\u5206 (20\u5206; \u5f3a\u52bf\u8d8b\u52bf\u8865\u507f)===
        bias = result.bias_ma5
        if bias != bias or bias is None:  # NaN or None defense
            bias = 0.0
        base_threshold = get_config().bias_threshold

        # Strong trend compensation: relax threshold for STRONG_BULL with high strength
        trend_strength = result.trend_strength if result.trend_strength == result.trend_strength else 0.0
        if result.trend_status == TrendStatus.STRONG_BULL and (trend_strength or 0) >= 70:
            effective_threshold = base_threshold * 1.5
            is_strong_trend = True
        else:
            effective_threshold = base_threshold
            is_strong_trend = False

        if bias < 0:
            # Price below MA5 (pullback)
            if bias > -3:
                score += 20
                reasons.append(f"✅ price\u7565Low\u4e8eMA5({bias:.1f}%); \u56de\u8e29\u4e70\u70b9")
            elif bias > -5:
                score += 16
                reasons.append(f"✅ price\u56de\u8e29MA5({bias:.1f}%); \u89c2\u5bdf\u652f\u6491")
            else:
                score += 8
                risks.append(f"⚠️ \u4e56\u79bb\u7387\u8fc7\u5927({bias:.1f}%); \u53ef\u80fd\u7834characters")
        elif bias < 2:
            score += 18
            reasons.append(f"✅ price\u8d34\u8fd1MA5({bias:.1f}%); \u4ecb\u5165\u597d\u65f6\u673a")
        elif bias < base_threshold:
            score += 14
            reasons.append(f"⚡ price\u7565High\u4e8eMA5({bias:.1f}%); \u53ef\u5c0f\u4ed3\u4ecb\u5165")
        elif bias > effective_threshold:
            score += 4
            risks.append(
                f"❌ \u4e56\u79bb\u7387\u8fc7High({bias:.1f}%>{effective_threshold:.1f}%); \u4e25\u7981\u8ffdHigh！"
            )
        elif bias > base_threshold and is_strong_trend:
            score += 10
            reasons.append(
                f"⚡ \u5f3a\u52bf\u8d8b\u52bfMedium\u4e56\u79bb\u7387Slightly High({bias:.1f}%); \u53ef\u8f7b\u4ed3\u8ffd\u8e2a"
            )
        else:
            score += 4
            risks.append(
                f"❌ \u4e56\u79bb\u7387\u8fc7High({bias:.1f}%>{base_threshold:.1f}%); \u4e25\u7981\u8ffdHigh！"
            )

        # === \u91cf\u80fd\u8bc4\u5206 (15\u5206)===
        volume_scores = {
            VolumeStatus.SHRINK_VOLUME_DOWN: 15,  # \u7f29\u91cf\u56de\u8c03\u6700\u4f73
            VolumeStatus.HEAVY_VOLUME_UP: 12,     # \u653e\u91cf\u4e0a\u6da8\u6b21\u4e4b
            VolumeStatus.NORMAL: 10,
            VolumeStatus.SHRINK_VOLUME_UP: 6,     # \u65e0\u91cf\u4e0a\u6da8\u8f83\u5dee
            VolumeStatus.HEAVY_VOLUME_DOWN: 0,    # \u653e\u91cf\u4e0b\u8dcc\u6700\u5dee
        }
        vol_score = volume_scores.get(result.volume_status, 8)
        score += vol_score

        if result.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            reasons.append("✅ \u7f29\u91cf\u56de\u8c03; \u4e3b\u529b\u6d17\u76d8")
        elif result.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("⚠️ \u653e\u91cf\u4e0b\u8dcc; \u6ce8\u610f\u98ce\u9669")

        # === \u652f\u6491\u8bc4\u5206 (10\u5206)===
        if result.support_ma5:
            score += 5
            reasons.append("✅ MA5\u652f\u6491\u6709\u6548")
        if result.support_ma10:
            score += 5
            reasons.append("✅ MA10\u652f\u6491\u6709\u6548")

        # === MACD \u8bc4\u5206 (15\u5206)===
        macd_scores = {
            MACDStatus.GOLDEN_CROSS_ZERO: 15,  # \u96f6\u8f74\u4e0a\u91d1\u53c9\u6700\u5f3a
            MACDStatus.GOLDEN_CROSS: 12,      # \u91d1\u53c9
            MACDStatus.CROSSING_UP: 10,       # \u4e0a\u7a7f\u96f6\u8f74
            MACDStatus.BULLISH: 8,            # \u591a\u5934
            MACDStatus.BEARISH: 2,            # \u7a7a\u5934
            MACDStatus.CROSSING_DOWN: 0,       # \u4e0b\u7a7f\u96f6\u8f74
            MACDStatus.DEATH_CROSS: 0,        # \u6b7b\u53c9
        }
        macd_score = macd_scores.get(result.macd_status, 5)
        score += macd_score

        if result.macd_status in [MACDStatus.GOLDEN_CROSS_ZERO, MACDStatus.GOLDEN_CROSS]:
            reasons.append(f"✅ {result.macd_signal}")
        elif result.macd_status in [MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN]:
            risks.append(f"⚠️ {result.macd_signal}")
        else:
            reasons.append(result.macd_signal)

        # === RSI \u8bc4\u5206 (10\u5206)===
        rsi_scores = {
            RSIStatus.OVERSOLD: 10,       # Oversold\u6700\u4f73
            RSIStatus.STRONG_BUY: 8,     # \u5f3a\u52bf
            RSIStatus.NEUTRAL: 5,        # Medium
            RSIStatus.WEAK: 3,            # \u5f31\u52bf
            RSIStatus.OVERBOUGHT: 0,       # Overbought\u6700\u5dee
        }
        rsi_score = rsi_scores.get(result.rsi_status, 5)
        score += rsi_score

        if result.rsi_status in [RSIStatus.OVERSOLD, RSIStatus.STRONG_BUY]:
            reasons.append(f"✅ {result.rsi_signal}")
        elif result.rsi_status == RSIStatus.OVERBOUGHT:
            risks.append(f"⚠️ {result.rsi_signal}")
        else:
            reasons.append(result.rsi_signal)

        # === \u7efc\u5408\u5224\u65ad ===
        result.signal_score = score
        result.signal_reasons = reasons
        result.risk_factors = risks

        # \u751f\u6210\u4e70\u5165\u4fe1\u53f7 (\u4e0e canonical decision scale \u4fdd\u6301\u4e00\u81f4)
        score_signal = signal_key_for_score(score)
        if score_signal == "strong_buy" and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            result.buy_signal = BuySignal.STRONG_BUY
        elif score_signal in {"strong_buy", "buy"} and result.trend_status in [
            TrendStatus.STRONG_BULL,
            TrendStatus.BULL,
            TrendStatus.WEAK_BULL,
        ]:
            result.buy_signal = BuySignal.BUY
        elif score_signal in {"strong_buy", "buy"} and result.trend_status in [
            TrendStatus.CONSOLIDATION,
            TrendStatus.WEAK_BEAR,
        ]:
            result.buy_signal = BuySignal.WAIT
        elif score_signal == "watch":
            result.buy_signal = BuySignal.WAIT
        elif score_signal == "sell" or result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            result.buy_signal = BuySignal.STRONG_SELL
        else:
            result.buy_signal = BuySignal.SELL

    def format_analysis(self, result: TrendAnalysisResult) -> str:
        """
        \u683c\u5f0f\u5316analysis result\u4e3a\u6587\u672c

        Args:
            result: analysis result

        Returns:
            \u683c\u5f0f\u5316\u7684analyze\u6587\u672c
        """
        lines = [
            f"=== {result.code} \u8d8b\u52bfanalyze ===",
            f"",
            f"📊 \u8d8b\u52bf\u5224\u65ad: {result.trend_status.value}",
            f"   \u5747\u7ebf\u6392\u5217: {result.ma_alignment}",
            f"   \u8d8b\u52bf\u5f3a\u5ea6: {result.trend_strength}/100",
            f"",
            f"📈 \u5747\u7ebf\u6570\u636e:",
            f"   \u73b0\u4ef7: {result.current_price:.2f}",
            f"   MA5:  {result.ma5:.2f} (\u4e56\u79bb {result.bias_ma5:+.2f}%)",
            f"   MA10: {result.ma10:.2f} (\u4e56\u79bb {result.bias_ma10:+.2f}%)",
            f"   MA20: {result.ma20:.2f} (\u4e56\u79bb {result.bias_ma20:+.2f}%)",
            f"",
            f"📊 \u91cf\u80fdanalyze: {result.volume_status.value}",
            f"   \u91cf\u6bd4(vs5\u65e5): {result.volume_ratio_5d:.2f}",
            f"   \u91cf\u80fd\u8d8b\u52bf: {result.volume_trend}",
            f"",
            f"📈 MACD\u6307\u6807: {result.macd_status.value}",
            f"   DIF: {result.macd_dif:.4f}",
            f"   DEA: {result.macd_dea:.4f}",
            f"   MACD: {result.macd_bar:.4f}",
            f"   \u4fe1\u53f7: {result.macd_signal}",
            f"",
            f"📊 RSI\u6307\u6807: {result.rsi_status.value}",
            f"   RSI(6): {result.rsi_6:.1f}",
            f"   RSI(12): {result.rsi_12:.1f}",
            f"   RSI(24): {result.rsi_24:.1f}",
            f"   \u4fe1\u53f7: {result.rsi_signal}",
            f"",
            f"🎯 operation advice: {result.buy_signal.value}",
            f"   \u7efc\u5408\u8bc4\u5206: {result.signal_score}/100",
        ]

        if result.signal_reasons:
            lines.append(f"")
            lines.append(f"✅ \u4e70\u5165\u7406\u7531:")
            for reason in result.signal_reasons:
                lines.append(f"   {reason}")

        if result.risk_factors:
            lines.append(f"")
            lines.append(f"⚠️ \u98ce\u9669\u56e0\u7d20:")
            for risk in result.risk_factors:
                lines.append(f"   {risk}")

        return "\n".join(lines)


def analyze_stock(df: pd.DataFrame, code: str) -> TrendAnalysisResult:
    """
    \u4fbf\u6377\u51fd\u6570: analyze\u5355stocks

    Args:
        df: \u5305\u542b OHLCV \u6570\u636e\u7684 DataFrame
        code: stock code

    Returns:
        TrendAnalysisResult analysis result
    """
    analyzer = StockTrendAnalyzer()
    return analyzer.analyze(df, code)


if __name__ == "__main__":
    # \u6d4b\u8bd5code
    logging.basicConfig(level=logging.INFO)

    # \u6a21\u62df\u6570\u636e\u6d4b\u8bd5
    import numpy as np

    dates = pd.date_range(start='2025-01-01', periods=60, freq='D')
    np.random.seed(42)

    # \u6a21\u62df\u591a\u5934\u6392\u5217data
    base_price = 10.0
    prices = [base_price]
    for i in range(59):
        change = np.random.randn() * 0.02 + 0.003  # \u8f7b\u5fae\u4e0a\u6da8\u8d8b\u52bf
        prices.append(prices[-1] * (1 + change))

    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + np.random.uniform(0, 0.02)) for p in prices],
        'low': [p * (1 - np.random.uniform(0, 0.02)) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in prices],
    })

    analyzer = StockTrendAnalyzer()
    result = analyzer.analyze(df, '000001')
    print(analyzer.format_analysis(result))
