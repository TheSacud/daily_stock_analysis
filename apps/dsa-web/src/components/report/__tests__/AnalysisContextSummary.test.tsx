import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import type { AnalysisContextPackOverview, AnalysisReport, AnalysisResult } from '../../../types/analysis';
import { AnalysisContextSummary } from '../AnalysisContextSummary';
import { ReportSummary } from '../ReportSummary';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getDiagnostics: vi.fn(),
    getNews: vi.fn(),
  },
}));

const overview: AnalysisContextPackOverview = {
  packVersion: '1.0',
  createdAt: '2026-04-10T08:30:00+00:00',
  subject: {
    code: '600519',
    stockName: '\u8d35\u5dde\u8305\u53f0',
    market: 'cn',
  },
  blocks: [
    {
      key: 'quote',
      label: '\u884c\u60c5',
      status: 'available',
      source: 'mock_quote',
      warnings: [],
      missingReasons: [],
    },
    {
      key: 'news',
      label: '\u65b0\u95fb',
      status: 'missing',
      source: null,
      warnings: ['news_provider_timeout'],
      missingReasons: ['news_context_missing'],
    },
    {
      key: 'fundamentals',
      label: '\u57fa\u672c\u9762',
      status: 'fetch_failed',
      source: 'fundamental_pipeline',
      warnings: [],
      missingReasons: ['fundamental_pipeline_failed'],
    },
  ],
  counts: {
    available: 1,
    missing: 1,
    notSupported: 0,
    fallback: 0,
    stale: 0,
    estimated: 0,
    partial: 0,
    fetchFailed: 1,
  },
  dataQuality: {
    overallScore: 82,
    level: 'usable',
    blockScores: {
      quote: 100,
      daily_bars: 100,
      technical: 100,
      news: 35,
      fundamentals: 25,
      chip: 100,
    },
    limitations: ['fundamentals: fetch_failed'],
  },
  warnings: ['intraday_realtime_overlay'],
  metadata: {
    triggerSource: 'api',
    newsResultCount: 3,
  },
};

describe('AnalysisContextSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a collapsed summary and expands overview details on demand', () => {
    render(<AnalysisContextSummary overview={overview} />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(panel).not.toHaveAttribute('open');
    expect(within(panel).getAllByText('\u8f93\u5165\u6570\u636e\u5757')[0]).toBeVisible();
    expect(screen.getAllByText('\u53ef\u7528 1')[0]).toBeVisible();
    expect(screen.getAllByText('\u7f3a\u5931 1')[0]).toBeVisible();
    expect(screen.getAllByText('\u6293\u53d6\u5931\u8d25 1')[0]).toBeVisible();
    expect(screen.getAllByText('\u8d28\u91cf\u5206 82/100 \u53ef\u7528')[0]).toBeVisible();
    expect(screen.getByText('\u89e6\u53d1\u6765\u6e90: api')).toBeVisible();
    expect(screen.getByText('\u6765\u6e90: mock_quote')).not.toBeVisible();

    fireEvent.click(within(panel).getAllByText('\u8f93\u5165\u6570\u636e\u5757')[0]);

    expect(panel).toHaveAttribute('open');
    expect(screen.getByText('\u884c\u60c5')).toBeInTheDocument();
    expect(screen.getByText('\u6765\u6e90: mock_quote')).toBeVisible();
    expect(screen.getByText('\u544a\u8b66:')).toBeInTheDocument();
    expect(screen.getByText(/intraday_realtime_overlay/)).toBeInTheDocument();
    expect(screen.getByText('\u6570\u636e\u9650\u5236:')).toBeInTheDocument();
    expect(screen.getByText(/\u57fa\u672c\u9762：\u6293\u53d6\u5931\u8d25/)).toBeInTheDocument();
    expect(screen.getByText(/news_provider_timeout/)).toBeInTheDocument();
    expect(screen.getByText(/\u672a\u8fdb\u5165\u5206\u6790\u8f93\u5165 \(news_context_missing\)/)).toBeInTheDocument();
    expect(screen.getByText(/fundamental_pipeline_failed/)).toBeInTheDocument();
    expect(screen.getAllByText('\u65b0\u95fb\u7ed3\u679c\u6570: 3').some((item) => item.textContent === '\u65b0\u95fb\u7ed3\u679c\u6570: 3')).toBe(true);
    expect(screen.getAllByText('\u672c\u6b21\u5206\u6790\u8f93\u5165')[0]).toBeVisible();
  });

  it('localizes the collapsed summary for english reports', () => {
    render(<AnalysisContextSummary overview={overview} language="en" />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(panel).not.toHaveAttribute('open');
    expect(screen.getAllByText('Input Blocks')[0]).toBeVisible();
    expect(screen.getByText('Shows inputs included in this LLM run, not provider run success')).toBeVisible();
    expect(screen.getAllByText('Available 1')[0]).toBeVisible();
    expect(screen.getAllByText('Missing 1')[0]).toBeVisible();
    expect(screen.getAllByText('Fetch failed 1')[0]).toBeVisible();
    expect(screen.getAllByText('Quality 82/100 Usable')[0]).toBeVisible();
    expect(screen.getByText('Trigger: api')).toBeVisible();

    fireEvent.click(within(panel).getAllByText('Input Blocks')[0]);

    expect(screen.getByText('Data Limitations:')).toBeInTheDocument();
    expect(screen.getByText(/fundamentals: Fetch failed/)).toBeInTheDocument();
  });

  it('surfaces degraded non-zero states in the collapsed summary', () => {
    const degradedOverview: AnalysisContextPackOverview = {
      ...overview,
      blocks: [
        {
          key: 'quote',
          label: '\u884c\u60c5',
          status: 'fallback',
          source: 'cached_quote',
          warnings: ['quote_fallback'],
          missingReasons: [],
        },
        {
          key: 'fundamental',
          label: '\u57fa\u672c\u9762',
          status: 'stale',
          source: 'fundamental_cache',
          warnings: ['stale_fundamental'],
          missingReasons: [],
        },
      ],
      counts: {
        available: 0,
        missing: 0,
        notSupported: 0,
        fallback: 1,
        stale: 1,
        estimated: 0,
        partial: 0,
        fetchFailed: 0,
      },
    };

    render(<AnalysisContextSummary overview={degradedOverview} />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(panel).not.toHaveAttribute('open');
    expect(within(panel).getByText('\u53ef\u7528 0')).toBeVisible();
    expect(within(panel).getByText('\u7f3a\u5931 0')).toBeVisible();
    expect(within(panel).getAllByText('\u964d\u7ea7 1')[0]).toBeVisible();
    expect(within(panel).getAllByText('\u8fc7\u671f 1')[0]).toBeVisible();
  });

  it('does not render without an overview', () => {
    const { container } = render(<AnalysisContextSummary overview={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('does not render raw values or unexpected sensitive fields', () => {
    const unsafeOverview = {
      ...overview,
      value: 'raw trend payload',
      content: '\u5b8c\u6574\u65b0\u95fb\u6b63\u6587\u4e0d\u5e94\u51fa\u73b0',
      apiKey: 'secret-key',
      blocks: [
        {
          ...overview.blocks[0],
          items: {
            price: {
              value: 1880,
              apiKey: 'secret-key',
            },
          },
        },
      ],
    } as unknown as AnalysisContextPackOverview;

    render(<AnalysisContextSummary overview={unsafeOverview} />);

    fireEvent.click(screen.getAllByText('\u8f93\u5165\u6570\u636e\u5757')[0]);

    expect(screen.queryByText('raw trend payload')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5b8c\u6574\u65b0\u95fb\u6b63\u6587\u4e0d\u5e94\u51fa\u73b0')).not.toBeInTheDocument();
    expect(screen.queryByText('secret-key')).not.toBeInTheDocument();
  });
});

describe('ReportSummary analysis context placement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders strategy and news before context, diagnostics and traceability', async () => {
    vi.mocked(historyApi.getNews).mockResolvedValue({
      total: 0,
      items: [],
    });

    const report: AnalysisReport = {
      meta: {
        id: 1,
        queryId: 'q1',
        stockCode: '600519',
        stockName: '\u8d35\u5dde\u8305\u53f0',
        reportType: 'detailed',
        reportLanguage: 'zh',
        createdAt: '2026-04-10T12:00:00',
        marketPhaseSummary: {
          market: 'cn',
          phase: 'intraday',
          marketLocalTime: '2026-04-10T10:30:00+08:00',
          sessionDate: '2026-04-10',
          effectiveDailyBarDate: '2026-04-09',
          isTradingDay: true,
          isMarketOpenNow: true,
          isPartialBar: true,
          minutesToOpen: null,
          minutesToClose: 150,
          triggerSource: 'api',
          analysisIntent: 'auto',
          warnings: [],
        },
      },
      summary: {
        analysisSummary: 'summary',
        operationAdvice: '\u6301\u6709',
        trendPrediction: '\u9707\u8361',
        sentimentScore: 70,
      },
      strategy: {
        idealBuy: '120',
      },
      details: {
        analysisContextPackOverview: overview,
      },
    };
    const result: AnalysisResult = {
      queryId: 'q1',
      stockCode: '600519',
      stockName: '\u8d35\u5dde\u8305\u53f0',
      report,
      diagnosticSummary: {
        status: 'normal',
        statusLabel: '\u6b63\u5e38',
        reason: '\u8fd0\u884c\u6b63\u5e38',
        components: {},
        copyText: '',
      },
      createdAt: '2026-04-10T12:00:00',
    };

    render(<ReportSummary data={result} />);

    await waitFor(() => {
      expect(screen.getByText('\u6682\u65e0\u76f8\u5173\u8d44\u8baf')).toBeInTheDocument();
    });

    expect(screen.getByText('\u5e02\u573a\u9636\u6bb5: CN · \u76d8\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('\u65e5\u7ebf\u672a\u5b8c\u6210')).toBeInTheDocument();
    expect(screen.getAllByText('\u8d28\u91cf\u5206 82/100 \u53ef\u7528')[0]).toBeInTheDocument();

    const strategy = screen.getByText('\u72d9\u51fb\u70b9\u4f4d');
    const news = screen.getByText('\u76f8\u5173\u8d44\u8baf');
    const diagnostics = screen.getByTestId('run-diagnostics');
    const contextSummary = screen.getByTestId('analysis-context-summary');
    expect(contextSummary).not.toHaveAttribute('open');
    expect(diagnostics).not.toHaveAttribute('open');
    const traceability = screen.getByText('\u6570\u636e\u8ffd\u6eaf');

    expect(strategy.compareDocumentPosition(news) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(news.compareDocumentPosition(contextSummary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(contextSummary.compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(diagnostics.compareDocumentPosition(traceability) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText('AI \u5efa\u8bae / \u51b3\u7b56\u4fe1\u53f7')).not.toBeInTheDocument();
  });
});
