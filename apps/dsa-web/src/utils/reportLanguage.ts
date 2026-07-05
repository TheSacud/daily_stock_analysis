import type { ReportLanguage } from '../types/analysis';

export const normalizeReportLanguage = (value?: string | null): ReportLanguage => {
  void value;
  return 'en';
};

const REPORT_TEXT = {
  zh: {
    keyInsights: 'Key Insights',
    noAnalysisSummary: 'No analysis summary',
    actionAdvice: 'Action Advice',
    noAdvice: 'No advice',
    trendPrediction: 'Trend Forecast',
    noPrediction: 'No forecast',
    marketSentiment: 'Market Sentiment',
    strategyPoints: 'Strategy Levels',
    sniperLevels: 'Sniper Levels',
    idealBuy: 'Ideal Buy',
    secondaryBuy: 'Secondary Buy',
    stopLoss: 'Stop Loss',
    takeProfit: 'Take Profit',
    noValue: '—',
    newsFeed: 'News Feed',
    relatedNews: 'Related News',
    refresh: 'Refresh',
    retry: 'Retry',
    dismiss: 'Close',
    details: 'View Details',
    loadingNews: 'Loading news...',
    noNews: 'No related news',
    noNewsDescription: 'Refresh later to get the latest news.',
    openLink: 'Open',
    transparency: 'Transparency',
    traceability: 'Data Traceability',
    rawResult: 'Raw Analysis Result',
    analysisSnapshot: 'Analysis Snapshot',
    copy: 'Copy',
    copied: 'Copied',
    recordId: 'Record ID',
    fullReport: 'Full Analysis Report',
    loadingReport: 'Loading report...',
    loadReportFailed: 'Failed to load report',
    copyMarkdownSource: 'Copy Markdown Source',
    copyPlainText: 'Copy Plain Text',
    analysisModel: 'Analysis Model',
    fearGreedIndex: 'Fear And Greed Index',
    boardLinkage: 'Sector Linkage',
    relatedBoards: 'Related Boards',
    leadingBoard: 'Leading',
    laggingBoard: 'Lagging',
    neutralBoard: 'Neutral',
    reanalyze: 'Reanalyze',
  },
  en: {
    keyInsights: 'KEY INSIGHTS',
    noAnalysisSummary: 'No analysis summary yet',
    actionAdvice: 'Action Advice',
    noAdvice: 'No advice yet',
    trendPrediction: 'Trend Outlook',
    noPrediction: 'No forecast yet',
    marketSentiment: 'Market Sentiment',
    strategyPoints: 'STRATEGY POINTS',
    sniperLevels: 'Action Levels',
    idealBuy: 'Ideal Entry',
    secondaryBuy: 'Secondary Entry',
    stopLoss: 'Stop Loss',
    takeProfit: 'Take Profit',
    noValue: '—',
    newsFeed: 'NEWS FEED',
    relatedNews: 'Related News',
    refresh: 'Refresh',
    retry: 'Retry',
    dismiss: 'Close',
    details: 'View details',
    loadingNews: 'Loading news...',
    noNews: 'No related news',
    noNewsDescription: 'Refresh later to check for the latest updates.',
    openLink: 'Open',
    transparency: 'TRANSPARENCY',
    traceability: 'Data Traceability',
    rawResult: 'Raw Analysis Result',
    analysisSnapshot: 'Analysis Snapshot',
    copy: 'Copy',
    copied: 'Copied!',
    recordId: 'Record ID',
    fullReport: 'Full Analysis Report',
    loadingReport: 'Loading report...',
    loadReportFailed: 'Failed to load report',
    copyMarkdownSource: 'Copy Markdown Source',
    copyPlainText: 'Copy Plain Text',
    analysisModel: 'Model',
    fearGreedIndex: 'Fear & Greed Index',
    boardLinkage: 'BOARD LINKAGE',
    relatedBoards: 'Related Boards',
    leadingBoard: 'Leading',
    laggingBoard: 'Lagging',
    neutralBoard: 'Neutral',
    reanalyze: 'Reanalyze',
  },
  ko: {
    keyInsights: '핵심 인사이트',
    noAnalysisSummary: '분석 결론 없음',
    actionAdvice: '대응 전략',
    noAdvice: '제안 없음',
    trendPrediction: '추세 전망',
    noPrediction: '예측 없음',
    marketSentiment: '시장 심리',
    strategyPoints: '전략 가격대',
    sniperLevels: '대응 가격대',
    idealBuy: '이상적 매수가',
    secondaryBuy: '추가 매수가',
    stopLoss: '손절가',
    takeProfit: '목표가',
    noValue: '—',
    newsFeed: '뉴스 피드',
    relatedNews: '관련 뉴스',
    refresh: '새로고침',
    retry: '다시 시도',
    dismiss: '닫기',
    details: '상세 보기',
    loadingNews: '뉴스 불러오는 중...',
    noNews: '관련 뉴스 없음',
    noNewsDescription: '잠시 후 새로고침하여 최신 소식을 확인하세요.',
    openLink: '열기',
    transparency: '투명성',
    traceability: '데이터 추적',
    rawResult: '원본 분석 결과',
    analysisSnapshot: '분석 스냅샷',
    copy: '복사',
    copied: '복사됨!',
    recordId: '레코드 ID',
    fullReport: '전체 분석 리포트',
    loadingReport: '리포트 불러오는 중...',
    loadReportFailed: '리포트 불러오기 실패',
    copyMarkdownSource: 'Markdown 소스 복사',
    copyPlainText: '일반 텍스트 복사',
    analysisModel: '분석 모델',
    fearGreedIndex: '공포·탐욕 지수',
    boardLinkage: '섹터 연동',
    relatedBoards: '관련 섹터',
    leadingBoard: '강세',
    laggingBoard: '약세',
    neutralBoard: '중립',
    reanalyze: '재분석',
  },
} as const;

export const getReportText = (language?: string | null) => REPORT_TEXT[normalizeReportLanguage(language)];
const CJK_TEXT_PATTERN = /[\u3400-\u9fff]/;

const LEGACY_REPORT_EXACT_TRANSLATIONS: Record<string, string> = {
  '\u89c2\u671b': 'Watch',
  '\u89c2\u5bdf': 'Watch',
  '\u7b49\u5f85': 'Wait',
  '\u6301\u6709': 'Hold',
  '\u4e70\u5165': 'Buy',
  '\u52a0\u4ed3': 'Add',
  '\u51cf\u4ed3': 'Reduce',
  '\u5356\u51fa': 'Sell',
  '\u770b\u591a': 'Bullish',
  '\u770b\u7a7a': 'Bearish',
  '\u9707\u8361': 'Sideways',
  '\u591a\u5934\u6392\u5217': 'Bullish alignment',
  '\u7a7a\u5934\u6392\u5217': 'Bearish alignment',
  '\u770b\u591a\u4f46\u4e56\u79bb\u7387\u8fc7\u9ad8': 'Bullish, but price is overextended',
};

const LEGACY_REPORT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\u7406\u60f3\u4e70\u5165\u70b9[:\uff1a]/g, 'Ideal entry:'],
  [/\u6b21\u4f18\u4e70\u5165\u70b9[:\uff1a]/g, 'Secondary entry:'],
  [/\u6b62\u635f\u4f4d[:\uff1a]/g, 'Stop loss:'],
  [/\u76ee\u6807\u4f4d[:\uff1a]/g, 'Take profit:'],
  [/\u7b2c\u4e00\u76ee\u6807/g, 'first target '],
  [/\u7b2c\u4e8c\u76ee\u6807/g, 'second target '],
  [/\u6574\u6570\u5173\u53e3/g, 'round-number level'],
  [/\u524d\u9ad8\u53c2\u8003/g, 'prior high reference'],
  [/\u8dcc\u7834/g, 'breaks below '],
  [/\u4e14\u653e\u91cf\u65f6\u6b62\u635f/g, 'on rising volume'],
  [/\u9644\u8fd1/g, ' area'],
  [/\u7b49\u5f85\u7f29\u91cf\u56de\u8e29\u786e\u8ba4/g, 'wait for a lower-volume pullback confirmation'],
  [/\u4e0e/g, ' and '],
  [/\u4e4b\u95f4/g, 'between'],
  [/\u5143/g, ''],
  [/\uff08/g, ' ('],
  [/\uff09/g, ')'],
  [/\uff0c/g, ', '],
  [/\u3002/g, '.'],
  [/\uff1b/g, '; '],
  [/\s{2,}/g, ' '],
];

export const containsCjkText = (value?: string | null): boolean =>
  CJK_TEXT_PATTERN.test(value || '');

export const localizeLegacyReportValue = (
  value?: string | null,
  language?: string | null,
  fallback = '',
): string => {
  const raw = (value || '').trim();
  if (!raw) return fallback;
  if (normalizeReportLanguage(language) !== 'en') return raw;

  const exact = LEGACY_REPORT_EXACT_TRANSLATIONS[raw];
  if (exact) return exact;

  const normalized = LEGACY_REPORT_REPLACEMENTS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    raw,
  ).trim();

  if (!containsCjkText(normalized)) return normalized;
  return fallback || 'Reanalyze this saved report to refresh it in English.';
};

const LEGACY_DIAGNOSTIC_EXACT_TRANSLATIONS: Record<string, string> = {
  '\u90e8\u5206\u964d\u7ea7': 'Degraded',
  '\u6b63\u5e38': 'Normal',
  '\u672a\u77e5': 'Unknown',
  '\u5b9e\u65f6\u884c\u60c5': 'realtime quote',
  '\u901a\u77e5': 'notification',
  '\u4fdd\u5b58': 'save',
};

const LEGACY_DIAGNOSTIC_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\u90e8\u5206\u964d\u7ea7/g, 'Degraded'],
  [/\u6b63\u5e38/g, 'Normal'],
  [/\u672a\u77e5/g, 'Unknown'],
  [/\u5b9e\u65f6\u884c\u60c5/g, 'realtime quote'],
  [/\u524d\u7f6e(?:data source|\u6570\u636e\u6e90)(?:failed|\u5931\u8d25)\u540e\s*\u5df2\u7ee7\u7eed/g, 'continued after an earlier data source failed'],
  [/\u6210\u529f/g, 'succeeded'],
  [/\u5931\u8d25/g, 'failed'],
  [/\u6700\u8fd1\u5931\u8d25\u540e\u5df2\u964d\u7ea7/g, 'Recent failure'],
  [/\u672a\u914d\u7f6e\u6216\u672c\u6b21\u8df3\u8fc7/g, 'not configured or skipped for this run'],
  [/\u672a\u914d\u7f6e/g, 'not configured'],
  [/\u672c\u6b21/g, 'this run'],
  [/\u8df3\u8fc7/g, 'skipped'],
  [/\u901a\u77e5/g, 'notification'],
  [/\u5df2\u4fdd\u5b58/g, 'saved'],
  [/\u4fdd\u5b58/g, 'save'],
  [/\u65e0result/g, 'returned no results'],
  [/\u6570\u636e/g, 'data'],
  [/\u65e5\u7ebf/g, 'daily bars'],
  [/\u65b0\u95fb/g, 'news'],
  [/\u68c0\u7d22/g, 'search'],
  [/\u8fd4\u56de/g, 'returned'],
  [/\u6761result/g, 'results'],
  [/\uff0c/g, ', '],
  [/\uff1b/g, '; '],
  [/\u3002/g, '.'],
];

const LEGACY_DIAGNOSTIC_TEXT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/data sourcefailed/g, 'data source failed'],
  [/not configuredorthis runskipping/gi, 'not configured or skipped for this run'],
  [/reporthistory/g, 'report history '],
  [/historysave/g, 'history save'],
  [/newssearch/g, 'news search'],
  [/daily data data/g, 'daily data'],
  [/notificationnot configured/gi, 'notification not configured'],
  [/searchreturned/g, 'search returned'],
  [/\bsuccess\b/g, 'succeeded'],
  [/\s*;\s*continued after an earlier data source failed/g, ' after an earlier data source failed'],
  [/([a-z])([A-Z])/g, '$1 $2'],
  [/\s{2,}/g, ' '],
];

export const localizeLegacyDiagnosticText = (
  value?: string | null,
  fallback = '',
): string => {
  const raw = (value || '').trim();
  if (!raw) return fallback;

  const exact = LEGACY_DIAGNOSTIC_EXACT_TRANSLATIONS[raw];
  if (exact) return exact;

  const withTranslatedCjk = LEGACY_DIAGNOSTIC_REPLACEMENTS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    raw,
  );
  const normalized = LEGACY_DIAGNOSTIC_TEXT_REPLACEMENTS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    withTranslatedCjk,
  ).trim();

  if (!containsCjkText(normalized)) return normalized;
  return fallback || 'Legacy diagnostic text was generated before English localization.';
};
