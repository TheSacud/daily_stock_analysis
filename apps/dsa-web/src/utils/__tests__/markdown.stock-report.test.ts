import { describe, expect, it } from 'vitest';
import { markdownToPlainText } from '../markdown';

/**
 * Stock report specific tests for markdownToPlainText
 * Tests real-world stock analysis report scenarios
 */
describe('markdownToPlainText - Stock Report Scenarios', () => {
  it('handles typical Chinese stock report with tables and indicators', () => {
    const stockReport = `# \u8d35\u5dde\u8305\u53f0 (600519) \u5206\u6790\u62a5\u544a

## \u6280\u672f\u5206\u6790

| \u6307\u6807 | \u5f53\u524d\u503c | \u4fe1\u53f7 |
|------|--------|------|
| MA5 | 1680.50 | 🟢 |
| MA10 | 1675.30 | 🟢 |
| MA20 | 1665.80 | 🟢 |

**MACD**: \u91d1\u53c9\u4fe1\u53f7，\u4e70\u5165\u53c2\u8003
**RSI**: 56.8，\u5904\u4e8e\u4e2d\u6027\u533a\u57df

## \u57fa\u672c\u9762\u5206\u6790

- **\u5e02\u76c8\u7387**: 28.5
- **\u5e02\u51c0\u7387**: 8.2
- **\u8425\u6536\u589e\u957f**: +15.3% YoY

> \u98ce\u9669\u63d0\u793a：\u77ed\u671f\u6ce2\u52a8\u52a0\u5927，\u5efa\u8bae\u63a7\u5236\u4ed3\u4f4d

## \u64cd\u4f5c\u5efa\u8bae

\`\`\`python
# \u63a8\u8350\u4e70\u5165\u533a\u95f4
entry_zone = [1650, 1680]
stop_loss = 1620
target = 1750
\`\`\`

[\u67e5\u770b\u8be6\u7ec6\u6570\u636e](https://example.com/stock/600519)`;

    const result = markdownToPlainText(stockReport);

    // Verify key content is preserved
    expect(result).toContain('\u8d35\u5dde\u8305\u53f0');
    expect(result).toContain('600519');
    expect(result).toContain('\u6280\u672f\u5206\u6790');
    expect(result).toContain('MACD');
    expect(result).toContain('\u91d1\u53c9\u4fe1\u53f7');
    expect(result).toContain('\u5e02\u76c8\u7387');
    expect(result).toContain('\u98ce\u9669\u63d0\u793a');
    expect(result).toContain('entry_zone');
    expect(result).toContain('\u67e5\u770b\u8be6\u7ec6\u6570\u636e');

    // Verify markdown symbols are removed
    expect(result).not.toMatch(/^#{1,6}\s+/m);
    expect(result).not.toMatch(/\*\*[^*]+\*\*/);
    // Note: remove-markdown preserves table structure with pipe characters
    // This is a known limitation - tables remain pipe-separated
  });

  it('handles Hong Kong stock report with English and Chinese mix', () => {
    const hkReport = `# Tencent (00700.HK) Technical Analysis

## Key Indicators

* **Current Price**: HKD 368.20
* **Change**: +2.5% 📈
* **Volume**: 18.2M

## Support & Resistance

1. **Resistance 1**: HKD 375.00
2. **Resistance 2**: HKD 380.00
3. **Support 1**: HKD 365.00

> \u5efa\u8bae\u5728\u56de\u8c03\u81f3 365-368 \u533a\u95f4\u5173\u6ce8

\`\`\`
MA5 > MA10 > MA20 (\u591a\u5934\u6392\u5217)
RSI(14) = 58.3 (\u4e2d\u6027\u504f\u5f3a)
\`\`\`

[Click for more details](https://finance.qq.com/q/go.php/vInvestConsult/stock/00700)`;

    const result = markdownToPlainText(hkReport);

    expect(result).toContain('Tencent');
    expect(result).toContain('00700.HK');
    expect(result).toContain('368.20');
    expect(result).toContain('Resistance 1');
    expect(result).toContain('Support 1');
    expect(result).toContain('\u5efa\u8bae\u5728\u56de\u8c03');
    expect(result).toContain('MA5 > MA10');
    expect(result).toContain('Click for more details');
  });

  it('handles US stock report with financial data', () => {
    const usReport = `# Apple Inc. (AAPL) Analysis Report

## Financial Metrics

| Metric | Value | Change |
|--------|-------|--------|
| Price | $178.35 | +1.2% |
| Market Cap | $2.8T | - |
| P/E Ratio | 28.5 | - |
| EPS | $6.16 | +8.3% |

## Technical Indicators

- **MA50**: $175.20 (Above)
- **MA200**: $168.80 (Above)
- **RSI**: 62.5 (Slightly Overbought)
- **MACD**: Bullish crossover

## Recommendation

***Strong Buy*** with target price of **$195.00**

> Risk: Trade tensions may impact supply chain

\`\`\`javascript
const entryPrice = 178.35;
const stopLoss = 172.00;
const targetPrice = 195.00;
const riskReward = (targetPrice - entryPrice) / (entryPrice - stopLoss);
// Risk/Reward ratio: 2.1:1
\`\`\`

![AAPL Chart](https://example.com/charts/aapl.png)`;

    const result = markdownToPlainText(usReport);

    expect(result).toContain('Apple Inc.');
    expect(result).toContain('AAPL');
    expect(result).toContain('178.35');
    expect(result).toContain('2.8T');
    expect(result).toContain('Strong Buy');
    expect(result).toContain('195.00');
    expect(result).toContain('Risk/Reward ratio');
  });

  it('handles market review report with multiple stocks', () => {
    const marketReview = `# A\u80a1\u5e02\u573a\u590d\u76d8

## \u6307\u6570\u8868\u73b0

| \u6307\u6570 | \u6536\u76d8 | \u6da8\u8dcc\u5e45 | \u6210\u4ea4\u989d |
|------|------|--------|--------|
| \u4e0a\u8bc1\u6307\u6570 | 3050.32 | +0.85% | 4285\u4ebf |
| \u6df1\u8bc1\u6210\u6307 | 9850.45 | +1.12% | 5250\u4ebf |
| \u521b\u4e1a\u677f\u6307 | 1950.28 | +1.45% | 2180\u4ebf |

## \u70ed\u70b9\u677f\u5757

1. **\u4eba\u5de5\u667a\u80fd** 🤖
   - \u539f\u56e0：\u5927\u6a21\u578b\u6280\u672f\u7a81\u7834
   - \u9f99\u5934：\u79d1\u5927\u8baf\u98de、\u5bd2\u6b66\u7eaa

2. **\u65b0\u80fd\u6e90\u6c7d\u8f66** 🚗
   - \u539f\u56e0：\u9500\u91cf\u6570\u636e\u8d85\u9884\u671f
   - \u9f99\u5934：\u6bd4\u4e9a\u8fea、\u7406\u60f3\u6c7d\u8f66

3. **\u534a\u5bfc\u4f53** 💾
   - \u539f\u56e0：\u56fd\u4ea7\u66ff\u4ee3\u52a0\u901f
   - \u9f99\u5934：\u4e2d\u82af\u56fd\u9645、\u5317\u65b9\u534e\u521b

## \u8d44\u91d1\u6d41\u5411

- **\u5317\u5411\u8d44\u91d1**: +85.5\u4ebf
- **\u878d\u8d44\u878d\u5238**: +32.8\u4ebf
- **\u4e3b\u529b\u8d44\u91d1**: \u51c0\u6d41\u5165 156.8\u4ebf

## \u540e\u5e02\u5c55\u671b

> \u9884\u671f\u660e\u65e5\u9707\u8361\u533a\u95f4：3040-3065

**\u7b56\u7565**：\u5173\u6ce8\u79d1\u6280\u4e3b\u7ebf，\u63a7\u5236\u4ed3\u4f4d`;

    const result = markdownToPlainText(marketReview);

    expect(result).toContain('A\u80a1\u5e02\u573a\u590d\u76d8');
    expect(result).toContain('\u4e0a\u8bc1\u6307\u6570');
    expect(result).toContain('3050.32');
    expect(result).toContain('\u4eba\u5de5\u667a\u80fd');
    expect(result).toContain('\u79d1\u5927\u8baf\u98de');
    expect(result).toContain('\u5317\u5411\u8d44\u91d1');
    expect(result).toContain('85.5\u4ebf');
    expect(result).toContain('3040-3065');
  });

  it('handles report with special characters and formulas', () => {
    const report = `# \u6280\u672f\u6307\u6807\u8ba1\u7b97

## MACD \u8ba1\u7b97

\`\`\`python
# MACD = EMA(12) - EMA(26)
# Signal = EMA(MACD, 9)
# Histogram = MACD - Signal

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    return macd, signal_line
\`\`\`

## RSI \u516c\u5f0f

$$RSI = 100 - \frac{100}{1 + RS}$$

\u5176\u4e2d：
- RS = \u5e73\u5747\u6da8\u5e45 / \u5e73\u5747\u8dcc\u5e45
- \u5468\u671f：\u9ed8\u8ba4 14 \u5929

## \u5e03\u6797\u5e26

- **\u4e2d\u8f68** = MA(20)
- **\u4e0a\u8f68** = MA(20) + 2 × STD(20)
- **\u4e0b\u8f68** = MA(20) - 2 × STD(20)

> \u5f53\u524d\u80a1\u4ef7\u5728\u4e0a\u8f68\u9644\u8fd1，\u6ce8\u610f\u56de\u8c03\u98ce\u9669`;

    const result = markdownToPlainText(report);

    expect(result).toContain('MACD \u8ba1\u7b97');
    expect(result).toContain('EMA(12) - EMA(26)');
    expect(result).toContain('RSI');
    expect(result).toContain('\u5e03\u6797\u5e26');
    expect(result).toContain('MA(20)');
    expect(result).toContain('\u6ce8\u610f\u56de\u8c03\u98ce\u9669');
  });

  it('handles report with code snippets in multiple languages', () => {
    const report = `# \u7b56\u7565\u56de\u6d4b\u4ee3\u7801

## Python \u7b56\u7565

\`\`\`python
import pandas as pd
import numpy as np

def moving_average_strategy(data, short=5, long=20):
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 0

    signals['short_ma'] = data['close'].rolling(window=short).mean()
    signals['long_ma'] = data['close'].rolling(window=long).mean()

    signals.loc[signals['short_ma'] > signals['long_ma'], 'signal'] = 1
    signals.loc[signals['short_ma'] < signals['long_ma'], 'signal'] = -1

    return signals
\`\`\`

\u4ee5\u4e0a\u4ee3\u7801\u53ef\u76f4\u63a5\u7528\u4e8e\u7b56\u7565\u56de\u6d4b。`;

    const result = markdownToPlainText(report);

    // Verify key content is preserved
    expect(result).toContain('\u7b56\u7565\u56de\u6d4b\u4ee3\u7801');
    expect(result).toContain('Python \u7b56\u7565');
    expect(result).toContain('\u4ee5\u4e0a\u4ee3\u7801\u53ef\u76f4\u63a5\u7528\u4e8e\u7b56\u7565\u56de\u6d4b');

    // Verify code content is preserved
    expect(result).toContain('import pandas');
    expect(result).toContain('moving_average_strategy');
  });

  it('handles edge case: very long stock code list', () => {
    const stockList = `# \u80a1\u7968\u6c60\u5217\u8868

## \u6caa\u6df1300\u6210\u5206\u80a1（\u90e8\u5206）

| \u4ee3\u7801 | \u540d\u79f0 | \u73b0\u4ef7 | \u6da8\u8dcc\u5e45 |
|------|------|------|--------|
| 600519 | \u8d35\u5dde\u8305\u53f0 | 1680.50 | +0.85% |
| 000858 | \u4e94\u7cae\u6db2 | 125.30 | +1.20% |
| 600036 | \u62db\u5546\u94f6\u884c | 32.50 | -0.25% |
| 000001 | \u5e73\u5b89\u94f6\u884c | 11.85 | +0.42% |
| 601318 | \u4e2d\u56fd\u5e73\u5b89 | 45.20 | +0.15% |
| 000333 | \u7f8e\u7684\u96c6\u56e2 | 58.80 | +1.80% |
| 600276 | \u6052\u745e\u533b\u836f | 42.50 | +2.10% |
| 300750 | \u5b81\u5fb7\u65f6\u4ee3 | 185.30 | +3.20% |
| 688981 | \u4e2d\u82af\u56fd\u9645 | 52.80 | +4.50% |
| 601012 | \u9686\u57fa\u7eff\u80fd | 25.60 | -1.20% |

## \u7b5b\u9009\u6761\u4ef6

- **\u5e02\u503c**: > 500\u4ebf
- **PE**: 10-50
- **ROE**: > 15%
- **\u8d1f\u503a\u7387**: < 60%`;

    const result = markdownToPlainText(stockList);

    // Verify all stock codes are preserved
    expect(result).toContain('600519');
    expect(result).toContain('000858');
    expect(result).toContain('601012');
    expect(result).toContain('\u8d35\u5dde\u8305\u53f0');
    expect(result).toContain('\u5b81\u5fb7\u65f6\u4ee3');
    expect(result).toContain('\u7b5b\u9009\u6761\u4ef6');
    expect(result).toContain('ROE');
  });

  it('handles mixed Chinese and English punctuation correctly', () => {
    const text = `# \u62a5\u544a\u6458\u8981

**\u4e3b\u8981\u89c2\u70b9**：
1. \u77ed\u671f\u770b\u6da8，\u76ee\u6807\u4ef7 $195.00
2. \u652f\u6491\u4f4d：$168.50-172.00
3. \u538b\u529b\u4f4d：$180.50-185.00

"Risk: Trade war impact"

> \u98ce\u9669\u63d0\u793a：\u4e2d\u7f8e\u8d38\u6613\u6469\u64e6\u53ef\u80fd\u5f71\u54cd\u51fa\u53e3

*\u5173\u6ce8\u70b9*：AI chip business growth`;

    const result = markdownToPlainText(text);

    expect(result).toContain('\u4e3b\u8981\u89c2\u70b9');
    expect(result).toContain('\u77ed\u671f\u770b\u6da8');
    expect(result).toContain('195.00');
    expect(result).toContain('Risk: Trade war impact');
    expect(result).toContain('\u98ce\u9669\u63d0\u793a');
    expect(result).toContain('\u5173\u6ce8\u70b9');
    expect(result).toContain('AI chip business');
  });

  it('preserves numerical data and percentages accurately', () => {
    const report = `# \u6570\u636e\u62a5\u544a

## \u5173\u952e\u6307\u6807

- \u8425\u6536: 1,234.56\u4ebf
- \u51c0\u5229\u6da6: +23.45%
- \u5e02\u5360\u7387: 15.67%
- ROE: 18.9%
- \u8d1f\u503a\u7387: 45.2%

## \u4ef7\u683c\u533a\u95f4

| \u65e5\u671f | \u5f00\u76d8 | \u6700\u9ad8 | \u6700\u4f4e | \u6536\u76d8 |
|------|------|------|------|------|
| 2024-01-15 | 1680.50 | 1695.30 | 1675.20 | 1688.80 |
| 2024-01-16 | 1688.80 | 1702.50 | 1685.30 | 1698.20 |

\u6da8\u8dcc\u5e45: +1.23% (\u4eca\u65e5)`;

    const result = markdownToPlainText(report);

    expect(result).toContain('1,234.56');
    expect(result).toContain('23.45%');
    expect(result).toContain('15.67%');
    expect(result).toContain('1680.50');
    expect(result).toContain('1695.30');
    expect(result).toContain('1.23%');
  });
});
