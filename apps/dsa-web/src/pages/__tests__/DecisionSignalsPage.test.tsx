import type React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { decisionSignalsApi } from '../../api/decisionSignals';
import { historyApi } from '../../api/history';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type { StockBarResponse } from '../../types/analysis';
import type {
  DecisionSignalFeedbackItem,
  DecisionSignalItem,
  DecisionSignalListResponse,
  DecisionSignalOutcomeListResponse,
  DecisionSignalOutcomeStatsResponse,
  DecisionSignalReassessResponse,
} from '../../types/decisionSignals';
import type { StockIndexItem } from '../../types/stockIndex';
import DecisionSignalsPage from '../DecisionSignalsPage';

let stockIndexState: {
  index: StockIndexItem[];
  loading: boolean;
  error: Error | null;
  fallback: boolean;
  loaded: boolean;
};

vi.mock('../../api/decisionSignals', () => ({
  decisionSignalsApi: {
    list: vi.fn(),
    getLatest: vi.fn(),
    getOutcomeStats: vi.fn(),
    getSignalOutcomes: vi.fn(),
    getFeedback: vi.fn(),
    putFeedback: vi.fn(),
    updateStatus: vi.fn(),
    reassess: vi.fn(),
  },
}));

vi.mock('../../api/history', () => ({
  historyApi: {
    getStockBarList: vi.fn(),
  },
}));

vi.mock('../../hooks/useStockIndex', () => ({
  useStockIndex: () => stockIndexState,
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ScatterChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Scatter: ({
    data,
    onClick,
    shape,
  }: {
    data: Array<{ item: DecisionSignalItem }>;
    onClick: (datum: { item: DecisionSignalItem }) => void;
    shape: (props: unknown) => React.ReactNode;
  }) => (
    <div>
      {data.map((datum, index) => (
        <button
          key={datum.item.id}
          type="button"
          data-testid={`timeline-click-${datum.item.id}`}
          onClick={() => onClick(datum)}
        >
          {shape({ cx: 20 + index * 20, cy: 20, payload: datum })}
          {datum.item.stockCode}
        </button>
      ))}
    </div>
  ),
}));

const signal: DecisionSignalItem = {
  id: 7,
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  market: 'cn',
  sourceType: 'analysis',
  sourceReportId: 3001,
  marketPhase: 'intraday',
  triggerSource: 'web',
  action: 'hold',
  actionLabel: null,
  confidence: 0.72,
  score: 82,
  horizon: '3d',
  entryLow: 1600,
  entryHigh: 1620,
  stopLoss: 1550,
  targetPrice: 1700,
  invalidation: '\u8dcc\u7834 1550',
  watchConditions: '\u89c2\u5bdf\u6210\u4ea4\u91cf',
  reason: '\u8d8b\u52bf\u4fdd\u6301',
  riskSummary: '\u653e\u91cf\u4e0b\u8dcc\u98ce\u9669',
  catalystSummary: '\u4e1a\u7ee9\u7a97\u53e3',
  evidence: { technical: 'ma' },
  dataQualitySummary: { freshness: 'ok' },
  planQuality: 'complete',
  status: 'active',
  expiresAt: '2026-06-18T09:30:00',
  createdAt: '2026-06-17T09:30:00',
  updatedAt: '2026-06-17T09:30:00',
  metadata: { source: 'test' },
};

const stockIndexItems: StockIndexItem[] = [
  {
    canonicalCode: '600519.SH',
    displayCode: '600519',
    nameZh: '\u8d35\u5dde\u8305\u53f0',
    pinyinFull: 'guizhoumaotai',
    pinyinAbbr: 'gzmt',
    aliases: ['\u8305\u53f0'],
    market: 'CN',
    assetType: 'stock',
    active: true,
    popularity: 100,
  },
  {
    canonicalCode: 'AAPL',
    displayCode: 'AAPL',
    nameZh: 'Apple',
    market: 'US',
    assetType: 'stock',
    active: true,
    popularity: 90,
  },
  {
    canonicalCode: '00700.HK',
    displayCode: '00700',
    nameZh: '\u817e\u8baf\u63a7\u80a1',
    market: 'HK',
    assetType: 'stock',
    active: true,
    popularity: 80,
  },
];

const stockBarResponse: StockBarResponse = {
  total: 1,
  items: [
    {
      id: 1,
      stockCode: '600519',
      analysisCount: 2,
      marketPhaseSummary: { market: 'CN', phase: 'unknown', warnings: [] },
    },
  ],
};

function makeSignal(overrides: Partial<DecisionSignalItem> = {}): DecisionSignalItem {
  return {
    ...signal,
    ...overrides,
  };
}

const formattedCreatedAt = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}).format(new Date('2026-06-17T09:30:00Z'));

function listResponse(items: DecisionSignalItem[] = [signal], total = items.length): DecisionSignalListResponse {
  return {
    items,
    total,
    page: 1,
    pageSize: 20,
  };
}

const outcomeStats: DecisionSignalOutcomeStatsResponse = {
  engineVersion: 'decision-signal-v1',
  horizons: null,
  statuses: ['active', 'expired', 'invalidated', 'closed'],
  total: 3,
  completed: 2,
  unable: 1,
  hit: 1,
  miss: 1,
  neutral: 0,
  hitRatePct: 50,
  avgStockReturnPct: 2.5,
  unableReasons: { missing_anchor_price: 1 },
  breakdowns: {},
};

const outcomeList: DecisionSignalOutcomeListResponse = {
  items: [
    {
      id: 31,
      signalId: 7,
      horizon: '3d',
      engineVersion: 'decision-signal-v1',
      evalStatus: 'completed',
      outcome: 'hit',
      directionExpected: 'not_down',
      directionCorrect: true,
      anchorDate: '2024-01-02',
      evalWindowDays: 3,
      startPrice: 100,
      endClose: 105,
      stockReturnPct: 5,
      action: 'hold',
      market: 'cn',
      planQuality: 'complete',
      dataQualityLevel: 'good',
      holdingState: 'holding',
    },
  ],
  total: 1,
  page: 1,
  pageSize: 100,
};

const emptyFeedback: DecisionSignalFeedbackItem = {
  signalId: 7,
  feedbackValue: null,
  reasonCode: null,
  note: null,
  source: null,
};

const reassessResponse: DecisionSignalReassessResponse = {
  preview: {
    action: 'watch',
    score: 72,
    confidence: null,
    horizon: '3d',
    entryLow: 1680,
    stopLoss: 1600,
    reason: 'preview reason',
    metadata: {
      decision_profile: 'balanced',
      data_quality_level: 'medium',
      scoring_breakdown: { raw_action: 'buy' },
      guardrail_result: {
        raw_action: 'buy',
        final_action: 'watch',
        passed: false,
        violations: ['missing_confidence'],
        adjustments: ['action_downgraded_by_guardrail'],
        adjusted: true,
      },
    },
  },
  item: null,
  created: false,
  warnings: [{ code: 'action_blocked_by_guardrail' }],
  blockedReason: 'actionable_signal_blocked_by_guardrail',
};

function renderPage() {
  return render(
    <UiLanguageProvider>
      <DecisionSignalsPage />
    </UiLanguageProvider>,
  );
}

function deferredPromise<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function submitCurrentStock(value: string) {
  const input = screen.getByLabelText('\u5f53\u524d\u80a1\u7968');
  fireEvent.change(input, { target: { value } });
  fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b\u80a1\u7968' }));
}

beforeEach(() => {
  window.history.pushState({}, '', '/');
  window.localStorage.clear();
  window.localStorage.setItem('dsa.uiLanguage', 'zh');
  vi.clearAllMocks();
  stockIndexState = {
    index: stockIndexItems,
    loading: false,
    error: null,
    fallback: false,
    loaded: true,
  };
  vi.mocked(historyApi.getStockBarList).mockResolvedValue(stockBarResponse);
  vi.mocked(decisionSignalsApi.list).mockResolvedValue(listResponse());
  vi.mocked(decisionSignalsApi.getLatest).mockResolvedValue(listResponse([signal]));
  vi.mocked(decisionSignalsApi.getOutcomeStats).mockResolvedValue(outcomeStats);
  vi.mocked(decisionSignalsApi.getSignalOutcomes).mockResolvedValue(outcomeList);
  vi.mocked(decisionSignalsApi.getFeedback).mockResolvedValue(emptyFeedback);
  vi.mocked(decisionSignalsApi.putFeedback).mockResolvedValue({
    ...emptyFeedback,
    feedbackValue: 'useful',
    source: 'web',
  });
  vi.mocked(decisionSignalsApi.updateStatus).mockResolvedValue({ ...signal, status: 'invalidated' });
  vi.mocked(decisionSignalsApi.reassess).mockResolvedValue(reassessResponse);
});

describe('DecisionSignalsPage', () => {
  it('loads active signals by default', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'AI \u5efa\u8bae' })).toBeInTheDocument();
    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenCalledWith(expect.objectContaining({
        status: 'active',
        page: 1,
        pageSize: 20,
      }));
    });
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0')).toBeInTheDocument();
    expect(await screen.findByText('\u4fe1\u53f7\u8868\u73b0\u7edf\u8ba1')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' })).toBeInTheDocument();
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0').closest('button')).toBeNull();
    expect(screen.getByText('\u653e\u91cf\u4e0b\u8dcc\u98ce\u9669')).toBeInTheDocument();
    expect(screen.getByText(formattedCreatedAt)).toBeInTheDocument();
    expect(screen.getByText('\u5f53\u524d\u7edf\u8ba1\u4e3a\u5168\u5c40\u5df2\u590d\u76d8 outcome \u53e3\u5f84，\u4e0d\u7b49\u4e8e\u5f53\u524d\u53ef\u89c1\u4fe1\u53f7\u6570\u91cf，\u4e5f\u4e0d\u968f\u5f53\u524d\u80a1\u7968\u8fc7\u6ee4。')).toBeInTheDocument();
  });

  it('shows a zero-sample outcome stats state instead of misleading zero metrics', async () => {
    vi.mocked(decisionSignalsApi.getOutcomeStats).mockResolvedValueOnce({
      ...outcomeStats,
      total: 0,
      completed: 0,
      unable: 0,
      hit: 0,
      miss: 0,
      neutral: 0,
      hitRatePct: null,
      avgStockReturnPct: null,
    });

    renderPage();

    expect(await screen.findByText('\u6682\u65e0\u5df2\u590d\u76d8\u6837\u672c')).toBeInTheDocument();
    expect(screen.getByText('\u5f53\u524d\u7edf\u8ba1\u4e3a\u5168\u5c40\u5df2\u590d\u76d8 outcome \u53e3\u5f84，\u4e0d\u7b49\u4e8e\u5f53\u524d\u53ef\u89c1\u4fe1\u53f7\u6570\u91cf，\u4e5f\u4e0d\u968f\u5f53\u524d\u80a1\u7968\u8fc7\u6ee4。')).toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
  });

  it('uses a source report id query parameter as an exact analysis lookup on load', async () => {
    window.history.pushState({}, '', '/decision-signals?sourceReportId=3001&status=closed&market=cn');

    renderPage();

    expect(await screen.findByRole('heading', { name: 'AI \u5efa\u8bae' })).toBeInTheDocument();
    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenCalledWith({
        sourceReportId: 3001,
        sourceType: 'analysis',
        page: 1,
        pageSize: 20,
      });
    });
    expect(screen.getByLabelText('\u6765\u6e90\u62a5\u544a ID')).toHaveValue(3001);
  });

  it('renders decision signal enum filter labels in Chinese', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    expect(within(screen.getByLabelText('\u5e02\u573a')).getByRole('option', { name: '\u65e5\u80a1' })).toHaveValue('jp');
    expect(within(screen.getByLabelText('\u5e02\u573a')).getByRole('option', { name: '\u97e9\u80a1' })).toHaveValue('kr');
    expect(within(screen.getByLabelText('\u9636\u6bb5')).getByRole('option', { name: '\u5348\u95f4\u4f11\u5e02' })).toHaveValue('lunch_break');
    expect(within(screen.getByLabelText('\u9636\u6bb5')).getByRole('option', { name: '\u96c6\u5408\u7ade\u4ef7' })).toHaveValue('closing_auction');
    expect(within(screen.getByLabelText('\u6765\u6e90')).getByRole('option', { name: '\u5927\u76d8\u590d\u76d8' })).toHaveValue('market_review');
    expect(screen.getByLabelText('\u6765\u6e90\u62a5\u544a ID')).toBeInTheDocument();
  });

  it('renders decision signal filters and card value labels in English', async () => {
    window.localStorage.setItem('dsa.uiLanguage', 'en');
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([
      makeSignal({
        market: 'jp',
        marketPhase: 'closing_auction',
        horizon: '10d',
        planQuality: 'partial',
      }),
    ]));

    renderPage();

    expect(await screen.findByRole('heading', { name: 'AI signals' })).toBeInTheDocument();
    expect(within(screen.getByLabelText('Market')).getByRole('option', { name: 'Japan' })).toHaveValue('jp');
    expect(within(screen.getByLabelText('Market')).getByRole('option', { name: 'Korea' })).toHaveValue('kr');
    expect(within(screen.getByLabelText('Phase')).getByRole('option', { name: 'Closing auction' })).toHaveValue('closing_auction');
    expect(within(screen.getByLabelText('Source')).getByRole('option', { name: 'Market review' })).toHaveValue('market_review');
    expect(screen.getByLabelText('Source report ID')).toBeInTheDocument();
    expect(screen.getAllByText('Japan').length).toBeGreaterThan(1);
    expect(screen.getByText('Horizon')).toBeInTheDocument();
    expect(screen.getByText('10 days')).toBeInTheDocument();
    expect(screen.getByText('Plan quality: Partial')).toBeInTheDocument();
    expect(screen.getByText('Phase: Closing auction')).toBeInTheDocument();
    expect(screen.queryByText('10d')).not.toBeInTheDocument();
    expect(screen.queryByText('closing_auction')).not.toBeInTheDocument();
  });

  it('passes filter parameters when applying filters', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.change(screen.getByLabelText('\u5e02\u573a'), { target: { value: 'cn' } });
    fireEvent.change(screen.getByLabelText('\u80a1\u7968\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u52a8\u4f5c'), { target: { value: 'hold' } });
    fireEvent.click(screen.getByRole('button', { name: '\u7b5b\u9009' }));

    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        market: 'cn',
        stockCode: '600519',
        action: 'hold',
        status: 'active',
        page: 1,
        pageSize: 20,
      }));
    });
  });

  it('uses an exact analysis source report lookup when a report id filter is applied', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.change(screen.getByLabelText('\u5e02\u573a'), { target: { value: 'cn' } });
    fireEvent.change(screen.getByLabelText('\u80a1\u7968\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u52a8\u4f5c'), { target: { value: 'hold' } });
    fireEvent.change(screen.getByLabelText('\u6765\u6e90'), { target: { value: 'alert' } });
    fireEvent.change(screen.getByLabelText('\u72b6\u6001'), { target: { value: 'closed' } });
    fireEvent.change(screen.getByLabelText('\u6765\u6e90\u62a5\u544a ID'), { target: { value: '3001' } });
    fireEvent.click(screen.getByRole('button', { name: '\u7b5b\u9009' }));

    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith({
        sourceReportId: 3001,
        sourceType: 'analysis',
        page: 1,
        pageSize: 20,
      });
    });
  });

  it('reassesses from the selected signal source report without triggering list lookup', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(await screen.findByText('\u51b3\u7b56\u98ce\u683c\u91cd\u8bc4\u4f30\u9884\u89c8')).toBeInTheDocument();
    vi.mocked(decisionSignalsApi.list).mockClear();

    fireEvent.click(screen.getByRole('button', { name: '\u751f\u6210\u9884\u89c8' }));

    await waitFor(() => {
      expect(decisionSignalsApi.reassess).toHaveBeenCalledWith({
        sourceReportId: 3001,
        decisionProfile: 'balanced',
        persist: false,
      });
    });
    expect(decisionSignalsApi.list).not.toHaveBeenCalled();
    expect(await screen.findByText('actionable_signal_blocked_by_guardrail')).toBeInTheDocument();
    expect(screen.getByText('buy -> watch')).toBeInTheDocument();
    expect(screen.getByText('action_blocked_by_guardrail')).toBeInTheDocument();
  });

  it('reassesses from an existing source report id filter without a selected signal', async () => {
    window.history.pushState({}, '', '/decision-signals?sourceReportId=3001');
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([], 0));

    renderPage();
    expect(await screen.findByText('\u51b3\u7b56\u98ce\u683c\u91cd\u8bc4\u4f30\u9884\u89c8')).toBeInTheDocument();
    vi.mocked(decisionSignalsApi.list).mockClear();

    fireEvent.click(screen.getByRole('button', { name: '\u751f\u6210\u9884\u89c8' }));

    await waitFor(() => {
      expect(decisionSignalsApi.reassess).toHaveBeenCalledWith({
        sourceReportId: 3001,
        decisionProfile: 'balanced',
        persist: false,
      });
    });
    expect(decisionSignalsApi.list).not.toHaveBeenCalled();
  });

  it('disables reassess when no source report id is available', async () => {
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([
      makeSignal({ sourceReportId: null }),
    ]));

    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));

    await waitFor(() => {
      expect(screen.getAllByText('\u8be5\u4fe1\u53f7\u4e0d\u652f\u6301\u91cd\u8bc4\u4f30').length).toBeGreaterThan(0);
    });
    expect(screen.getByRole('button', { name: '\u751f\u6210\u9884\u89c8' })).toBeDisabled();
  });

  it('does not fallback to page source report id for a selected signal without source report id', async () => {
    window.history.pushState({}, '', '/decision-signals?sourceReportId=3001');
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([
      makeSignal({ sourceReportId: null }),
    ]));

    renderPage();
    await screen.findByText('\u51b3\u7b56\u98ce\u683c\u91cd\u8bc4\u4f30\u9884\u89c8');
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));

    await waitFor(() => {
      expect(screen.getAllByText('\u8be5\u4fe1\u53f7\u4e0d\u652f\u6301\u91cd\u8bc4\u4f30').length).toBeGreaterThan(0);
    });
    expect(screen.getByRole('button', { name: '\u751f\u6210\u9884\u89c8' })).toBeDisabled();
    expect(decisionSignalsApi.reassess).not.toHaveBeenCalled();
  });

  it('ignores stale reassess responses after switching the selected signal', async () => {
    const nextSignal = makeSignal({
      id: 8,
      stockCode: '000001',
      stockName: '\u5e73\u5b89\u94f6\u884c',
      sourceReportId: 3002,
    });
    const pending = deferredPromise<DecisionSignalReassessResponse>();
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([signal, nextSignal], 2));
    vi.mocked(decisionSignalsApi.reassess).mockReturnValueOnce(pending.promise);

    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    fireEvent.click(await screen.findByRole('button', { name: '\u751f\u6210\u9884\u89c8' }));
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u5e73\u5b89\u94f6\u884c AI \u5efa\u8bae\u8be6\u60c5' }));

    await act(async () => {
      pending.resolve({
        ...reassessResponse,
        preview: { ...reassessResponse.preview, reason: 'stale A preview' },
      });
    });

    expect(screen.queryByText('stale A preview')).not.toBeInTheDocument();
  });

  it('queries latest active signals by stock code', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('600519');

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenCalledWith('600519', {
        market: undefined,
        limit: 5,
      });
    });
  });

  it('submits the main stock context once and keeps the applied context separate from the draft', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    vi.mocked(decisionSignalsApi.getLatest).mockClear();
    vi.mocked(decisionSignalsApi.list).mockClear();

    submitCurrentStock('AAPL');

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenCalledTimes(1);
      expect(decisionSignalsApi.list).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText('\u5f53\u524d\u67e5\u770b：AAPL')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('\u5f53\u524d\u80a1\u7968'), { target: { value: 'MSFT' } });

    expect(screen.getByText('\u5f53\u524d\u67e5\u770b：AAPL')).toBeInTheDocument();
    expect(decisionSignalsApi.getLatest).toHaveBeenCalledTimes(1);
    expect(decisionSignalsApi.list).toHaveBeenCalledTimes(1);
  });

  it('uses autocomplete metadata for the active context instead of the old draft value', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.change(screen.getByLabelText('\u5f53\u524d\u80a1\u7968'), { target: { value: '6005' } });
    const listbox = await screen.findByRole('listbox');
    fireEvent.click(within(listbox).getByRole('option', { name: /\u8d35\u5dde\u8305\u53f0.*600519/ }));

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenCalledWith('600519.SH', {
        market: 'cn',
        limit: 5,
      });
    });
    expect(screen.getByText('\u5f53\u524d\u67e5\u770b：600519 / \u8d35\u5dde\u8305\u53f0 / cn')).toBeInTheDocument();
    expect(screen.getByLabelText('\u5f53\u524d\u80a1\u7968')).toHaveValue('600519');
  });

  it('shows recent history candidates and passes normalized market when a candidate is selected', async () => {
    renderPage();

    expect(await screen.findByText('\u6700\u8fd1\u5206\u6790')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /600519/ }));

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenCalledWith('600519', {
        market: 'cn',
        limit: 5,
      });
    });
    expect(screen.getByText('\u5f53\u524d\u67e5\u770b：600519 / cn')).toBeInTheDocument();
  });

  it('preserves the applied stock context metadata when the unchanged draft is submitted again', async () => {
    renderPage();

    expect(await screen.findByText('\u6700\u8fd1\u5206\u6790')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /600519/ }));

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenLastCalledWith('600519', {
        market: 'cn',
        limit: 5,
      });
    });
    expect(screen.getByLabelText('\u5f53\u524d\u80a1\u7968')).toHaveValue('600519');

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b\u80a1\u7968' }));

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenLastCalledWith('600519', {
        market: 'cn',
        limit: 5,
      });
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: '600519',
        market: 'cn',
      }));
    });
  });

  it('does not pass market for a history candidate when market cannot be inferred', async () => {
    vi.mocked(historyApi.getStockBarList).mockResolvedValueOnce({
      total: 1,
      items: [
        {
          id: 1,
          stockCode: '600519',
          analysisCount: 1,
          marketPhaseSummary: null,
        },
      ],
    });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /^600519$/ }));

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenCalledWith('600519', {
        market: undefined,
        limit: 5,
      });
    });
  });

  it('falls back to popular stock index candidates when history is empty or fails', async () => {
    vi.mocked(historyApi.getStockBarList).mockResolvedValueOnce({ total: 0, items: [] });
    const { unmount } = renderPage();

    expect(await screen.findByText('\u70ed\u95e8\u5019\u9009')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /AAPL.*Apple.*us/ })).toBeInTheDocument();
    expect(decisionSignalsApi.getLatest).not.toHaveBeenCalled();

    unmount();
    vi.clearAllMocks();
    vi.mocked(historyApi.getStockBarList).mockRejectedValueOnce(new Error('history down'));
    vi.mocked(decisionSignalsApi.list).mockResolvedValue(listResponse());
    vi.mocked(decisionSignalsApi.getLatest).mockResolvedValue(listResponse([signal]));
    vi.mocked(decisionSignalsApi.getOutcomeStats).mockResolvedValue(outcomeStats);
    renderPage();

    expect(await screen.findByText('\u70ed\u95e8\u5019\u9009')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /AAPL.*Apple.*us/ })).toBeInTheDocument();
  });

  it('renders no candidate fallback without crashing when history and stock index are unavailable', async () => {
    stockIndexState = {
      index: [],
      loading: false,
      error: new Error('index down'),
      fallback: true,
      loaded: false,
    };
    vi.mocked(historyApi.getStockBarList).mockRejectedValueOnce(new Error('history down'));

    renderPage();

    expect(await screen.findByText('\u6682\u65e0\u53ef\u7528\u5019\u9009，\u53ef\u76f4\u63a5\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0。')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'AI \u5efa\u8bae' })).toBeInTheDocument();
  });

  it('deduplicates history candidates with market-aware keys and falls back to stock code without market', async () => {
    vi.mocked(historyApi.getStockBarList).mockResolvedValueOnce({
      total: 4,
      items: [
        { id: 1, stockCode: '600519', analysisCount: 1, marketPhaseSummary: { market: 'CN', phase: 'unknown', warnings: [] } },
        { id: 2, stockCode: '600519', analysisCount: 1, marketPhaseSummary: { market: 'HK', phase: 'unknown', warnings: [] } },
        { id: 3, stockCode: 'AAPL', analysisCount: 1, marketPhaseSummary: null },
        { id: 4, stockCode: 'AAPL', analysisCount: 1, marketPhaseSummary: null },
      ],
    });
    renderPage();

    expect(await screen.findByText('\u6700\u8fd1\u5206\u6790')).toBeInTheDocument();
    const candidateButtons = screen.getAllByRole('button').filter((button) => (
      button.textContent?.includes('600519') || button.textContent?.includes('AAPL')
    ));

    expect(candidateButtons.filter((button) => button.textContent?.includes('600519'))).toHaveLength(2);
    expect(candidateButtons.filter((button) => button.textContent?.includes('AAPL'))).toHaveLength(1);
  });

  it('does not use the advanced list market filter for latest lookup', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    const marketSelect = screen.getByLabelText('\u5e02\u573a');
    fireEvent.change(marketSelect, { target: { value: 'cn' } });
    fireEvent.click(screen.getByRole('button', { name: '\u7b5b\u9009' }));
    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        market: 'cn',
      }));
    });

    fireEvent.change(marketSelect, { target: { value: 'hk' } });
    submitCurrentStock('600519');

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenCalledWith('600519', {
        market: undefined,
        limit: 5,
      });
    });
  });

  it('ignores stale latest-search responses', async () => {
    const firstSearch = deferredPromise<DecisionSignalListResponse>();
    const secondSignal = {
      ...signal,
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us' as const,
      riskSummary: '\u7b2c\u4e8c\u6b21\u67e5\u8be2\u7ed3\u679c',
    };
    vi.mocked(decisionSignalsApi.getLatest)
      .mockReturnValueOnce(firstSearch.promise)
      .mockResolvedValueOnce(listResponse([secondSignal]));
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('600519');

    submitCurrentStock('AAPL');

    expect(await screen.findByText('\u7b2c\u4e8c\u6b21\u67e5\u8be2\u7ed3\u679c')).toBeInTheDocument();

    await act(async () => {
      firstSearch.resolve(listResponse([{ ...signal, riskSummary: '\u7b2c\u4e00\u6b21\u665a\u8fd4\u56de\u7ed3\u679c' }]));
      await firstSearch.promise;
    });

    await waitFor(() => {
      expect(screen.queryByText('\u7b2c\u4e00\u6b21\u665a\u8fd4\u56de\u7ed3\u679c')).not.toBeInTheDocument();
    });
    expect(screen.getByText('\u7b2c\u4e8c\u6b21\u67e5\u8be2\u7ed3\u679c')).toBeInTheDocument();
  });

  it('renders latest empty and error states', async () => {
    vi.mocked(decisionSignalsApi.getLatest).mockResolvedValueOnce(listResponse([], 0));
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('600519');

    expect(await screen.findByText('\u6682\u65e0\u6700\u65b0\u6709\u6548\u4fe1\u53f7')).toBeInTheDocument();

    vi.mocked(decisionSignalsApi.getLatest).mockRejectedValueOnce(new Error('latest down'));
    submitCurrentStock('600519');

    expect(await screen.findByRole('alert')).toHaveTextContent('latest down');
  });

  it('does not request the timeline before a current stock is selected', async () => {
    renderPage();

    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    expect(screen.getAllByText('\u9009\u62e9\u80a1\u7968\u67e5\u770b AI \u5efa\u8bae').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '\u67e5\u8be2\u65f6\u95f4\u7ebf' })).toBeDisabled();
    expect(decisionSignalsApi.list).toHaveBeenCalledTimes(1);
    expect(within(screen.getByLabelText('\u65f6\u95f4\u7ebf\u72b6\u6001')).queryByRole('option', { name: '\u5df2\u5173\u95ed' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('profile')).not.toBeInTheDocument();
  });

  it('queries timeline with independent filters and no default status', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('600519');
    await waitFor(() => expect(decisionSignalsApi.list).toHaveBeenCalledTimes(2));

    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a'), { target: { value: 'cn' } });
    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u8303\u56f4'), { target: { value: '30d' } });
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u8be2\u65f6\u95f4\u7ebf' }));

    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenCalledTimes(3);
    });
    expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
      market: 'cn',
      stockCode: '600519',
      page: 1,
      pageSize: 100,
      status: undefined,
    }));
    const params = vi.mocked(decisionSignalsApi.list).mock.calls.at(-1)?.[0] as Record<string, string>;
    expect(params.createdFrom).toEqual(expect.any(String));
    expect(params.createdTo).toEqual(expect.any(String));
  });

  it('initializes timeline market from a new stock context once and preserves later user overrides', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    const getHistoryCandidateButton = () => screen.getAllByRole('button').find((button) => (
      button.textContent?.includes('600519') && button.textContent.includes('/ cn')
    ));
    fireEvent.click(await waitFor(() => {
      const button = getHistoryCandidateButton();
      expect(button).toBeTruthy();
      return button as HTMLButtonElement;
    }));

    await waitFor(() => {
      expect(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a')).toHaveValue('cn');
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: '600519',
        market: 'cn',
      }));
    });

    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a'), { target: { value: 'hk' } });
    const sameCandidateButton = getHistoryCandidateButton();
    expect(sameCandidateButton).toBeTruthy();
    fireEvent.click(sameCandidateButton as HTMLButtonElement);

    await waitFor(() => {
      expect(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a')).toHaveValue('hk');
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: '600519',
        market: 'hk',
      }));
    });
  });

  it('clears timeline market from a previous stock context before a later manual stock submit without metadata', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    const historyCandidateButton = await waitFor(() => {
      const button = screen.getAllByRole('button').find((candidateButton) => (
        candidateButton.textContent?.includes('600519') && candidateButton.textContent.includes('/ cn')
      ));
      expect(button).toBeTruthy();
      return button as HTMLButtonElement;
    });
    fireEvent.click(historyCandidateButton);

    await waitFor(() => {
      expect(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a')).toHaveValue('cn');
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: '600519',
        market: 'cn',
      }));
    });

    fireEvent.click(screen.getByRole('button', { name: '\u6e05\u7a7a\u5f53\u524d\u80a1\u7968' }));
    await waitFor(() => {
      expect(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a')).toHaveValue('');
    });

    submitCurrentStock('AAPL');

    await waitFor(() => {
      expect(decisionSignalsApi.getLatest).toHaveBeenLastCalledWith('AAPL', {
        market: undefined,
        limit: 5,
      });
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: 'AAPL',
        market: undefined,
      }));
    });
  });

  it('preserves a user-selected timeline market when a later manual stock submit has no metadata', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a'), { target: { value: 'us' } });
    submitCurrentStock('AAPL');

    await waitFor(() => {
      expect(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a')).toHaveValue('us');
      expect(decisionSignalsApi.getLatest).toHaveBeenLastCalledWith('AAPL', {
        market: undefined,
        limit: 5,
      });
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: 'AAPL',
        market: 'us',
      }));
    });
  });

  it('applies timeline draft filters only after the query button is clicked', async () => {
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('AAPL');
    await waitFor(() => expect(decisionSignalsApi.list).toHaveBeenCalledTimes(2));

    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u5e02\u573a'), { target: { value: 'us' } });
    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u8303\u56f4'), { target: { value: '30d' } });
    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u72b6\u6001'), { target: { value: 'active' } });

    expect(decisionSignalsApi.list).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u8be2\u65f6\u95f4\u7ebf' }));

    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenCalledTimes(3);
    });
    expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
      stockCode: 'AAPL',
      market: 'us',
      status: 'active',
    }));
  });

  it('passes active timeline status, shows truncation, and opens details from a point', async () => {
    const timelineSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      action: 'alert',
      riskSummary: 'Timeline risk',
    });
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([timelineSignal], 150));
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u72b6\u6001'), { target: { value: 'active' } });
    submitCurrentStock('AAPL');

    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        stockCode: 'AAPL',
        status: 'active',
        pageSize: 100,
      }));
    });
    expect(await screen.findByText('\u4ec5\u5c55\u793a\u6700\u8fd1 100 \u6761\u4fe1\u53f7，\u8bf7\u7f29\u5c0f\u65f6\u95f4\u8303\u56f4。')).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId('timeline-click-8'));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Timeline risk')).toBeInTheDocument();
  });

  it('returns to the timeline guide when stock code is cleared after a search', async () => {
    const timelineSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Timeline stale risk',
    });
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([timelineSignal], 1));
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('AAPL');
    fireEvent.click(await screen.findByTestId('timeline-click-8'));
    expect(within(await screen.findByRole('dialog')).getByText('Timeline stale risk')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u6e05\u7a7a\u5f53\u524d\u80a1\u7968' }));

    expect(screen.getAllByText('\u9009\u62e9\u80a1\u7968\u67e5\u770b AI \u5efa\u8bae').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '\u67e5\u8be2\u65f6\u95f4\u7ebf' })).toBeDisabled();
    expect(screen.queryByTestId('timeline-click-8')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(decisionSignalsApi.list).toHaveBeenCalledTimes(2);
  });

  it('clears current stock derived state without closing a list-sourced drawer', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(within(await screen.findByRole('dialog')).getByText('\u8d8b\u52bf\u4fdd\u6301')).toBeInTheDocument();

    submitCurrentStock('AAPL');
    expect(await screen.findByText('\u5f53\u524d\u67e5\u770b：AAPL')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u6e05\u7a7a\u5f53\u524d\u80a1\u7968' }));

    expect(screen.getByLabelText('\u5f53\u524d\u80a1\u7968')).toHaveValue('');
    expect(screen.getAllByText('\u9009\u62e9\u80a1\u7968\u67e5\u770b AI \u5efa\u8bae').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '\u67e5\u8be2\u65f6\u95f4\u7ebf' })).toBeDisabled();
    expect(within(screen.getByRole('dialog')).getByText('\u8d8b\u52bf\u4fdd\u6301')).toBeInTheDocument();
  });

  it('closes a timeline-sourced drawer when an active timeline status update removes it', async () => {
    const timelineSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Timeline active risk',
    });
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([timelineSignal], 1))
      .mockResolvedValueOnce(listResponse());
    vi.mocked(decisionSignalsApi.updateStatus).mockResolvedValueOnce({ ...timelineSignal, status: 'invalidated' });
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u72b6\u6001'), { target: { value: 'active' } });
    submitCurrentStock('AAPL');
    fireEvent.click(await screen.findByTestId('timeline-click-8'));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' }));
    fireEvent.click(await screen.findByRole('button', { name: '\u786e\u5b9a' }));

    await waitFor(() => {
      expect(decisionSignalsApi.updateStatus).toHaveBeenCalledWith(8, { status: 'invalidated' });
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('\u6682\u65e0\u65f6\u95f4\u7ebf\u4fe1\u53f7')).toBeInTheDocument();
  });

  it('uses applied timeline filters instead of draft filters after status updates', async () => {
    const timelineSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Timeline all risk',
    });
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([timelineSignal], 1))
      .mockResolvedValueOnce(listResponse());
    vi.mocked(decisionSignalsApi.updateStatus).mockResolvedValueOnce({ ...timelineSignal, status: 'invalidated' });
    renderPage();
    await screen.findByText('\u8d35\u5dde\u8305\u53f0');

    submitCurrentStock('AAPL');
    fireEvent.change(screen.getByLabelText('\u65f6\u95f4\u7ebf\u72b6\u6001'), { target: { value: 'active' } });
    fireEvent.click(await screen.findByTestId('timeline-click-8'));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' }));
    fireEvent.click(await screen.findByRole('button', { name: '\u786e\u5b9a' }));

    await waitFor(() => {
      expect(decisionSignalsApi.updateStatus).toHaveBeenCalledWith(8, { status: 'invalidated' });
    });
    await waitFor(() => {
      expect(within(screen.getByRole('dialog')).getByText('\u5df2\u5931\u6548')).toBeInTheDocument();
    });
    expect(screen.queryByText('\u6682\u65e0\u65f6\u95f4\u7ebf\u4fe1\u53f7')).not.toBeInTheDocument();
  });

  it('renders empty and error states', async () => {
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([], 0));

    renderPage();

    expect(await screen.findByText('\u6682\u65e0\u51b3\u7b56\u4fe1\u53f7')).toBeInTheDocument();
    vi.mocked(decisionSignalsApi.list).mockRejectedValueOnce(new Error('boom'));
    fireEvent.click(screen.getByRole('button', { name: '\u5237\u65b0' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
  });

  it('clears stale list data and closes a list drawer when refresh fails', async () => {
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockRejectedValueOnce(new Error('filter failed'));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('\u80a1\u7968\u4ee3\u7801'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '\u7b5b\u9009' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('filter failed');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' })).not.toBeInTheDocument();
    expect(screen.getByText('\u5171 0 \u6761\u4fe1\u53f7')).toBeInTheDocument();
  });

  it('opens details and confirms terminal status updates', async () => {
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([], 0));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getAllByText('\u8d35\u5dde\u8305\u53f0')).toHaveLength(2);
    expect(within(dialog).getByText('\u8d8b\u52bf\u4fdd\u6301')).toBeInTheDocument();
    expect(within(dialog).getByText('#3001')).toBeInTheDocument();
    expect(await within(dialog).findByText('\u547d\u4e2d')).toBeInTheDocument();
    expect(within(dialog).getByText('\u6682\u65e0\u53cd\u9988')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' }));
    expect(await screen.findByRole('heading', { name: '\u66f4\u65b0\u4fe1\u53f7\u72b6\u6001' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u786e\u5b9a' }));

    await waitFor(() => {
      expect(decisionSignalsApi.updateStatus).toHaveBeenCalledWith(7, { status: 'invalidated' });
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('\u5171 0 \u6761\u4fe1\u53f7')).toBeInTheDocument();
    expect(screen.getByText('\u6682\u65e0\u51b3\u7b56\u4fe1\u53f7')).toBeInTheDocument();
  });

  it('submits useful feedback from the details drawer', async () => {
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(await within(dialog).findByRole('button', { name: '\u6709\u7528' }));

    await waitFor(() => {
      expect(decisionSignalsApi.putFeedback).toHaveBeenCalledWith(7, {
        feedbackValue: 'useful',
        source: 'web',
      });
    });
    await waitFor(() => {
      expect(within(dialog).getAllByText('\u6709\u7528').length).toBeGreaterThan(1);
    });
  });

  it('ignores stale feedback submit responses after selecting another signal', async () => {
    const feedbackSave = deferredPromise<DecisionSignalFeedbackItem>();
    const nextSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      reason: 'Second signal reason',
    });
    vi.mocked(decisionSignalsApi.list).mockResolvedValueOnce(listResponse([signal, nextSignal], 2));
    vi.mocked(decisionSignalsApi.getFeedback).mockImplementation(async (signalId: number) => ({
      ...emptyFeedback,
      signalId,
    }));
    vi.mocked(decisionSignalsApi.putFeedback).mockReturnValueOnce(feedbackSave.promise);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    let dialog = await screen.findByRole('dialog');
    fireEvent.click(await within(dialog).findByRole('button', { name: '\u6709\u7528' }));
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b Apple AI \u5efa\u8bae\u8be6\u60c5' }));
    dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('Second signal reason')).toBeInTheDocument();

    await act(async () => {
      feedbackSave.resolve({
        ...emptyFeedback,
        feedbackValue: 'useful',
        source: 'web',
      });
      await feedbackSave.promise;
    });

    await waitFor(() => {
      expect(within(dialog).getByText('\u6682\u65e0\u53cd\u9988')).toBeInTheDocument();
      expect(within(dialog).getAllByText('\u6709\u7528')).toHaveLength(1);
    });
  });

  it('closes a list-sourced drawer when filters remove the selected signal', async () => {
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([], 0));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('\u80a1\u7968\u4ee3\u7801'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '\u7b5b\u9009' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('\u6682\u65e0\u51b3\u7b56\u4fe1\u53f7')).toBeInTheDocument();
  });

  it('keeps a latest-sourced drawer open when the main list refreshes', async () => {
    const latestSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Latest risk',
    });
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(listResponse([], 0));
    vi.mocked(decisionSignalsApi.getLatest).mockResolvedValueOnce(listResponse([latestSignal]));
    renderPage();

    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    submitCurrentStock('AAPL');
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b Apple AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Latest risk')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('\u80a1\u7968\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '\u7b5b\u9009' }));

    await waitFor(() => {
      expect(within(screen.getByRole('dialog')).getByText('Latest risk')).toBeInTheDocument();
    });
  });

  it('closes a latest-sourced drawer when the next latest search excludes the selected signal', async () => {
    const firstLatestSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Latest A risk',
    });
    const nextLatestSignal = makeSignal({
      id: 9,
      stockCode: 'MSFT',
      stockName: 'Microsoft',
      market: 'us',
      riskSummary: 'Latest B risk',
    });
    vi.mocked(decisionSignalsApi.getLatest)
      .mockResolvedValueOnce(listResponse([firstLatestSignal]))
      .mockResolvedValueOnce(listResponse([nextLatestSignal]));
    renderPage();

    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    submitCurrentStock('AAPL');
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b Apple AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(within(await screen.findByRole('dialog')).getByText('Latest A risk')).toBeInTheDocument();

    submitCurrentStock('MSFT');

    expect(await screen.findByText('Latest B risk')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('closes a latest-sourced drawer when latest search fails', async () => {
    const latestSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Latest risk before failure',
    });
    vi.mocked(decisionSignalsApi.getLatest)
      .mockResolvedValueOnce(listResponse([latestSignal]))
      .mockRejectedValueOnce(new Error('latest failed'));
    renderPage();

    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    submitCurrentStock('AAPL');
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b Apple AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(within(await screen.findByRole('dialog')).getByText('Latest risk before failure')).toBeInTheDocument();

    submitCurrentStock('MSFT');

    expect(await screen.findByRole('alert')).toHaveTextContent('latest failed');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('keeps a list-sourced drawer open when latest search results change', async () => {
    const latestSignal = makeSignal({
      id: 8,
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      riskSummary: 'Latest lookup risk',
    });
    vi.mocked(decisionSignalsApi.getLatest).mockResolvedValueOnce(listResponse([latestSignal]));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    expect(within(await screen.findByRole('dialog')).getByText('\u8d8b\u52bf\u4fdd\u6301')).toBeInTheDocument();

    submitCurrentStock('AAPL');

    expect(await screen.findByText('Latest lookup risk')).toBeInTheDocument();
    expect(within(screen.getByRole('dialog')).getByText('\u8d8b\u52bf\u4fdd\u6301')).toBeInTheDocument();
  });

  it('ignores duplicate status confirmation clicks and disables confirmation controls', async () => {
    const statusUpdate = deferredPromise<DecisionSignalItem>();
    vi.mocked(decisionSignalsApi.updateStatus).mockReturnValueOnce(statusUpdate.promise);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' }));
    const confirmButton = await screen.findByRole('button', { name: '\u786e\u5b9a' });

    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    expect(decisionSignalsApi.updateStatus).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(confirmButton).toBeDisabled());

    await act(async () => {
      statusUpdate.resolve({ ...signal, status: 'invalidated' });
      await statusUpdate.promise;
    });
  });

  it('clamps to a valid page after status update removes the only item on the last page', async () => {
    const pageTwoSignal = makeSignal({ id: 8, stockCode: 'AAPL', stockName: 'Apple', market: 'us' });
    vi.mocked(decisionSignalsApi.list)
      .mockResolvedValueOnce(listResponse([signal], 21))
      .mockResolvedValueOnce(listResponse([pageTwoSignal], 21))
      .mockResolvedValueOnce(listResponse([], 20))
      .mockResolvedValueOnce(listResponse([signal], 20));
    vi.mocked(decisionSignalsApi.updateStatus).mockResolvedValueOnce({ ...pageTwoSignal, status: 'invalidated' });
    renderPage();

    await screen.findByText('\u8d35\u5dde\u8305\u53f0');
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b Apple AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' }));
    fireEvent.click(await screen.findByRole('button', { name: '\u786e\u5b9a' }));

    await waitFor(() => {
      expect(decisionSignalsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        page: 1,
        pageSize: 20,
      }));
    });
    expect(screen.getByText('\u5171 20 \u6761\u4fe1\u53f7')).toBeInTheDocument();
    expect(screen.queryByText('\u6682\u65e0\u51b3\u7b56\u4fe1\u53f7')).not.toBeInTheDocument();
  });

  it('closes the status confirmation dialog and shows an error when status update fails', async () => {
    vi.mocked(decisionSignalsApi.updateStatus).mockRejectedValueOnce(new Error('status update failed'));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' }));
    expect(await screen.findByRole('heading', { name: '\u66f4\u65b0\u4fe1\u53f7\u72b6\u6001' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u786e\u5b9a' }));

    const errorMessage = await screen.findByText('status update failed');
    expect(errorMessage.closest('[role="alert"]')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: '\u66f4\u65b0\u4fe1\u53f7\u72b6\u6001' })).not.toBeInTheDocument();
    });
    expect(within(dialog).getByText('\u6709\u6548')).toBeInTheDocument();
  });

  it.each([
    ['\u5173\u95ed\u4fe1\u53f7', 'closed'],
    ['\u5f52\u6863', 'archived'],
  ] as const)('confirms %s without exposing active recovery', async (buttonName, status) => {
    vi.mocked(decisionSignalsApi.updateStatus).mockResolvedValueOnce({ ...signal, status });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));
    const dialog = await screen.findByRole('dialog');

    expect(within(dialog).getByRole('button', { name: '\u5173\u95ed\u4fe1\u53f7' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '\u6807\u8bb0\u5931\u6548' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '\u5f52\u6863' })).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: '\u6709\u6548' })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: '\u5df2\u8fc7\u671f' })).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: buttonName }));
    fireEvent.click(await screen.findByRole('button', { name: '\u786e\u5b9a' }));

    await waitFor(() => {
      expect(decisionSignalsApi.updateStatus).toHaveBeenCalledWith(7, { status });
    });
  });
});
