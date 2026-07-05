import { validateStockCode } from './validation';
import { normalizeStockCode } from './stockCode';

const EXCHANGE_PREFIXES = new Set(['SH', 'SZ', 'BJ', 'HK', 'US', 'SS']);
const LOWERCASE_TICKER_CONTEXT_RE = /\u6362\u6210|\u6539\u770b|\u5206\u6790|\u770b\u770b|\u7814\u7a76|\u8bca\u65ad|\u6bd4\u8f83|\u5bf9\u6bd4|\bvs\b|\u548c[^\uFF0C\u3002,.!?\uFF01\uFF1F]{0,40}\u6bd4|\u5dee\u5f02(?!\u5316)|\u533a\u522b|\u4e0d\u540c|\u76f8\u6bd4|\u5bf9\u7167|\u6bd4\u4e00\u6bd4|\u54ea\u4e2a|\u54ea\u53ea|\u54ea\u4e00\u4e2a|\u8c01\u66f4|\u66f4\u503c\u5f97|\u66f4\u9002\u5408|\u600e\u4e48\u9009|\u9009\u54ea|\u4e8c\u9009\u4e00/i;
const CONTEXTUAL_INDICATOR_TOKENS = new Set(['MA']);
const INDICATOR_CONTEXT_RE = /\u6307\u6807|\u5747\u7ebf|\u79fb\u52a8\u5e73\u5747|\u6392\u5217|\u591a\u5934|\u7a7a\u5934|\u91d1\u53c9|\u6b7b\u53c9|\u652f\u6491|\u538b\u529b|MA\d|SMA|EMA/i;

// Mirrors backend _COMMON_WORDS for #1596 free-text extraction only.
// Explicit validation via validateStockCode() intentionally keeps its original contract.
const FREE_TEXT_TICKER_DENYLIST = new Set([
  'AM', 'AS', 'AT', 'BE', 'BY', 'DO', 'GO', 'HE', 'IF', 'IN',
  'IS', 'IT', 'ME', 'MY', 'NO', 'OF', 'ON', 'OR', 'SO', 'TO',
  'UP', 'US', 'WE',
  'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL',
  'CAN', 'HAD', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'HAS',
  'HIS', 'HOW', 'ITS', 'LET', 'MAY', 'NEW', 'NOW', 'OLD',
  'SEE', 'WAY', 'WHO', 'DID', 'GET', 'HIM', 'USE', 'SAY',
  'SHE', 'TOO', 'ANY', 'WITH', 'FROM', 'THAT', 'THAN',
  'THIS', 'WHAT', 'WHEN', 'WILL', 'JUST', 'ALSO',
  'BEEN', 'EACH', 'HAVE', 'MUCH', 'ONLY', 'OVER',
  'SOME', 'SUCH', 'THEM', 'THEN', 'THEY', 'VERY',
  'WERE', 'YOUR', 'ABOUT', 'AFTER', 'COULD', 'EVERY',
  'OTHER', 'THEIR', 'THERE', 'THESE', 'THOSE', 'WHICH',
  'WOULD', 'BEING', 'STILL', 'WHERE',
  'BUY', 'SELL', 'HOLD', 'LONG', 'PUT', 'CALL',
  'ETF', 'IPO', 'RSI', 'EPS', 'PEG', 'ROE', 'ROA',
  'USA', 'USD', 'CNY', 'HKD', 'EUR', 'GBP',
  'STOCK', 'TRADE', 'PRICE', 'INDEX', 'FUND',
  'HIGH', 'LOW', 'OPEN', 'CLOSE', 'STOP', 'LOSS',
  'TREND', 'BULL', 'BEAR', 'RISK', 'CASH', 'BOND',
  'MACD', 'VWAP', 'BOLL', 'KDJ',
  'TTM', 'LTM', 'NTM', 'FWD', 'YOY', 'QOQ', 'YTD',
  'EBIT', 'EBITDA', 'DCF', 'CAGR', 'FCF', 'NAV', 'AUM',
  'PE', 'PB',
  'HELLO', 'PLEASE', 'THANKS', 'CHECK', 'LOOK', 'THINK',
  'MAYBE', 'GUESS', 'TELL', 'SHOW', 'WHATS',
  'WHY', 'HOWDY', 'HEY', 'HI',
]);

function isDeniedTickerCandidate(value: string, message: string): boolean {
  const token = value.trim().toUpperCase();
  return (
    FREE_TEXT_TICKER_DENYLIST.has(token) ||
    (CONTEXTUAL_INDICATOR_TOKENS.has(token) && INDICATOR_CONTEXT_RE.test(message))
  );
}

export function extractStockCodeFromMessage(message: string): string | null {
  return extractStockCodesFromMessage(message)[0] ?? null;
}

export function extractStockCodesFromMessage(message: string): string[] {
  // More specific patterns first to avoid greedy \d{6} capturing inside .SH/.SZ codes
  const patterns = [
    /\b(30\d{4}\.SZ)\b/gi,
    /\b(68\d{4}\.SH)\b/gi,
    /\b(00\d{4}\.SZ)\b/gi,
    /\b(60\d{4}\.SH)\b/gi,
    /\b(SH\d{6})\b/gi,
    /\b(SZ\d{6})\b/gi,
    /\b(BJ\d{6})\b/gi,
    /\b(hk\d{4,5})\b/gi,
    /\b(\d{1,5}\.HK)\b/gi,
    /\b(\d{5,6})\b/g,
    /\b([A-Z]{2,5}\.[A-Z]{1,2})\b/g,
    /\b([A-Z]{2,5})\b/g,
  ];
  if (LOWERCASE_TICKER_CONTEXT_RE.test(message)) {
    patterns.push(/\b([a-z]{2,5}(?:\.[a-z]{1,2})?)\b/g);
  }

  const matches: Array<{ value: string; index: number; priority: number }> = [];
  patterns.forEach((pattern, priority) => {
    pattern.lastIndex = 0;
    for (const match of message.matchAll(pattern)) {
      const value = match[1] ?? match[0];
      const start = match.index ?? 0;
      const end = start + value.length;
      if (/^[A-Z]{2,5}$/.test(value) && (message[start - 1] === '.' || message[end] === '.')) {
        continue;
      }
      matches.push({
        value,
        index: start,
        priority,
      });
    }
  });

  matches.sort((a, b) => a.index - b.index || a.priority - b.priority);

  const stockCodes: string[] = [];
  const seen = new Set<string>();
  for (const match of matches) {
    if (EXCHANGE_PREFIXES.has(match.value.toUpperCase())) {
      continue;
    }
    if (isDeniedTickerCandidate(match.value, message)) {
      continue;
    }
    const { valid, normalized } = validateStockCode(match.value);
    if (!valid) {
      continue;
    }
    const stockCode = normalizeStockCode(normalized);
    if (!seen.has(stockCode)) {
      seen.add(stockCode);
      stockCodes.push(stockCode);
    }
  }
  return stockCodes;
}
