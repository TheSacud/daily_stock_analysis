import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { agentApi } from '../../api/agent';
import { historyApi } from '../../api/history';
import { systemConfigApi } from '../../api/systemConfig';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { useStockPoolStore } from '../../stores';
import type { RunFlowSnapshot } from '../../types/runFlow';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import HomePage from '../HomePage';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../../api/history', () => ({
  historyApi: {
    getList: vi.fn(),
    getDetail: vi.fn(),
    getNews: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    getMarkdown: vi.fn().mockResolvedValue('# report'),
    getDiagnostics: vi.fn(),
    getRecordFlow: vi.fn(),
    getStockBarList: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    deleteByCode: vi.fn(),
  },
}));

vi.mock('../../api/analysis', async () => {
  const actual = await vi.importActual<typeof import('../../api/analysis')>('../../api/analysis');
  return {
    ...actual,
    analysisApi: {
      analyzeAsync: vi.fn(),
      triggerMarketReview: vi.fn(),
      getStatus: vi.fn(),
      getTasks: vi.fn(),
      getTaskFlow: vi.fn(),
    },
  };
});

vi.mock('../../api/systemConfig', () => ({
  systemConfigApi: {
    getSetupStatus: vi.fn(),
    getWatchlist: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../../api/agent', () => ({
  agentApi: {
    getSkills: vi.fn(),
  },
}));

vi.mock('../../hooks/useTaskStream', () => ({
  useTaskStream: vi.fn(),
}));

const historyItem = {
  id: 1,
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  sentimentScore: 82,
  operationAdvice: '\u4e70\u5165',
  createdAt: '2026-03-18T08:00:00Z',
};

const historyReport = {
  meta: {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '\u8d35\u5dde\u8305\u53f0',
    reportType: 'detailed' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf',
    operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf\u4e70\u70b9',
    trendPrediction: '\u77ed\u7ebf\u9707\u8361\u504f\u5f3a',
    sentimentScore: 78,
  },
};

const marketReviewHistoryItem = {
  id: 2,
  queryId: 'market-review-q-1',
  stockCode: 'MARKET',
  stockName: '\u5927\u76d8\u590d\u76d8',
  reportType: 'market_review' as const,
  createdAt: '2026-03-18T08:00:00Z',
};

const marketReviewHistoryReport = {
  meta: {
    id: 2,
    queryId: 'market-review-q-1',
    stockCode: 'MARKET',
    stockName: '\u5927\u76d8\u590d\u76d8',
    reportType: 'market_review' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '\u5927\u76d8\u590d\u76d8\u6458\u8981',
    operationAdvice: '\u67e5\u770b\u590d\u76d8',
    trendPrediction: '\u5927\u76d8\u590d\u76d8',
    sentimentScore: 50,
  },
};

const runFlowSnapshot: RunFlowSnapshot = {
  taskId: 'task-1',
  traceId: 'trace-1',
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  status: 'running',
  generatedAt: '2026-06-08T08:00:00Z',
  summary: {
    elapsedMs: 1200,
    failedAttempts: 0,
    fallbackCount: 0,
    dataSourceCount: 1,
    eventCount: 1,
  },
  lanes: [
    { id: 'entry', label: '\u5165\u53e3', order: 1 },
    { id: 'analysis', label: '\u5206\u6790\u5f15\u64ce', order: 2 },
  ],
  nodes: [
    {
      id: 'request',
      lane: 'entry',
      kind: 'entry',
      label: '\u7528\u6237\u8bf7\u6c42',
      status: 'success',
    },
    {
      id: 'analysis',
      lane: 'analysis',
      kind: 'analysis',
      label: '\u5206\u6790\u6d41\u7a0b',
      status: 'running',
    },
  ],
  edges: [
    {
      id: 'request-analysis',
      from: 'request',
      to: 'analysis',
      kind: 'control',
      status: 'running',
      label: '\u8c03\u5ea6',
    },
  ],
  events: [
    {
      id: 'evt-1',
      timestamp: '2026-06-08T08:00:00Z',
      severity: 'info',
      type: 'task_started',
      nodeId: 'analysis',
      title: '\u4efb\u52a1\u5f00\u59cb',
    },
  ],
};

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    window.localStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 0,
      pending: 0,
      processing: 0,
      tasks: [],
    });
    vi.mocked(agentApi.getSkills).mockResolvedValue({ skills: [], default_skill_id: '' });
    vi.mocked(historyApi.getDiagnostics).mockResolvedValue({
      status: 'unknown',
      statusLabel: '\u672a\u77e5',
      reason: '\u65e7\u62a5\u544a\u6216\u8bca\u65ad\u8bc1\u636e\u4e0d\u8db3，\u65e0\u6cd5\u5224\u65ad\u672c\u6b21\u8fd0\u884c\u72b6\u6001',
      components: {},
      copyText: 'data_status: unknown',
    });
    vi.mocked(historyApi.getRecordFlow).mockResolvedValue(runFlowSnapshot);
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(runFlowSnapshot);
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [],
    });
  });

  it('renders the dashboard workspace and auto-loads the first report', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const dashboard = await screen.findByTestId('home-dashboard');
    expect(dashboard).toBeInTheDocument();
    expect(dashboard.className).toContain('h-[calc(100vh-5rem)]');
    expect(dashboard.className).toContain('lg:h-[calc(100vh-2rem)]');
    expect(dashboard.firstElementChild?.className).toContain('min-h-0');
    expect(dashboard.querySelector('.flex-1.flex.min-h-0.overflow-hidden')).toBeTruthy();
    expect(screen.getByTestId('home-dashboard-scroll')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0，\u5982 600519、\u8d35\u5dde\u8305\u53f0、AAPL')).toBeInTheDocument();
    expect(await screen.findByText('\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf')).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: getReportText(normalizeReportLanguage(historyReport.meta.reportLanguage)).fullReport,
      }),
    ).toBeInTheDocument();
    expect(historyApi.getMarkdown).not.toHaveBeenCalled();
  });

  it('loads markdown only after opening the full report drawer', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full Markdown Report');

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const fullReportButton = await screen.findByRole('button', {
      name: getReportText(normalizeReportLanguage(historyReport.meta.reportLanguage)).fullReport,
    });
    expect(historyApi.getMarkdown).not.toHaveBeenCalled();

    fireEvent.click(fullReportButton);

    await waitFor(() => {
      expect(historyApi.getMarkdown).toHaveBeenCalledWith(historyReport.meta.id);
    });
    expect(await screen.findByRole('heading', { name: 'Full Markdown Report' })).toBeInTheDocument();
  });

  it('shows the empty report workspace when history is empty', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('\u5f00\u59cb\u5206\u6790')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\u5f00\u59cb\u5206\u6790', level: 3 })).toBeInTheDocument();
    expect(screen.getByText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u8fdb\u884c\u5206\u6790，\u6216\u4ece\u5de6\u4fa7\u9009\u62e9\u5386\u53f2\u62a5\u544a\u67e5\u770b。')).toBeInTheDocument();
    expect(screen.getByText('\u6682\u65e0\u4e2a\u80a1\u8bb0\u5f55')).toBeInTheDocument();
  });

  it('opens the run-flow drawer from an active task in TaskPanel', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 1,
      pending: 0,
      processing: 1,
      tasks: [
        {
          taskId: 'task-1',
          traceId: 'trace-1',
          stockCode: '600519',
          stockName: '\u8d35\u5dde\u8305\u53f0',
          status: 'processing',
          progress: 35,
          message: '\u5206\u6790\u4e2d',
          reportType: 'detailed',
          createdAt: '2026-06-08T08:00:00Z',
        },
      ],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 \u8fd0\u884c\u6d41' }));

    await waitFor(() => {
      expect(analysisApi.getTaskFlow).toHaveBeenCalledWith('task-1');
    });
    expect(await screen.findByTestId('run-flow-panel')).toBeInTheDocument();
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0 \u8fd0\u884c\u6d41')).toBeInTheDocument();
  });

  it('opens the run-flow drawer from completed report diagnostics', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText('\u8fd0\u884c\u72b6\u6001'));
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b\u5386\u53f2\u8bb0\u5f55 1 \u8fd0\u884c\u6d41' }));

    await waitFor(() => {
      expect(historyApi.getRecordFlow).toHaveBeenCalledWith(1);
    });
    expect(await screen.findByTestId('run-flow-panel')).toBeInTheDocument();
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0 \u5386\u53f2\u8fd0\u884c\u6d41')).toBeInTheDocument();
  });

  it('shows market review history in the stock bar', async () => {
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [{
        id: 11,
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        sentimentScore: 72,
        operationAdvice: '\u89c2\u5bdf',
        analysisCount: 2,
        lastAnalysisTime: '2026-03-19T08:00:00Z',
      }],
    });
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 1,
          page: 1,
          limit: 10,
          items: [marketReviewHistoryItem],
        });
      }
      return Promise.resolve({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(marketReviewHistoryReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: /MARKET/ })).toBeInTheDocument();
    const newerStockButton = await screen.findByRole('button', { name: /AAPL/ });
    const marketButton = await screen.findByRole('button', { name: /MARKET/ });
    expect(newerStockButton.compareDocumentPosition(marketButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText('\u5927\u76d8\u590d\u76d8\u5386\u53f2')).not.toBeInTheDocument();
    expect(historyApi.getList).toHaveBeenCalledWith({
      stockCode: 'MARKET',
      reportType: 'market_review',
      page: 1,
      limit: 10,
    });

    fireEvent.click(await screen.findByRole('button', { name: /MARKET/ }));

    expect(await screen.findByText('\u5927\u76d8\u590d\u76d8\u6458\u8981')).toBeInTheDocument();
  });

  it('removes the MARKET stock bar item after deleting market review history', async () => {
    let isMarketReviewDeleted = false;
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 0,
      items: [],
    });
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: isMarketReviewDeleted ? 0 : 1,
          page: 1,
          limit: 10,
          items: isMarketReviewDeleted ? [] : [marketReviewHistoryItem],
        });
      }
      return Promise.resolve({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
    });
    vi.mocked(historyApi.deleteByCode).mockImplementation(async () => {
      isMarketReviewDeleted = true;
      return { deleted: 1 };
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: /MARKET/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u5220\u9664 \u5927\u76d8\u590d\u76d8 \u5386\u53f2\u8bb0\u5f55' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /MARKET/ })).not.toBeInTheDocument();
    });
    expect(historyApi.deleteByCode).toHaveBeenCalledWith('MARKET');
  });

  it('surfaces duplicate task warnings from dashboard submission', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(
      new DuplicateTaskError('600519', 'task-1', '\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d'),
    );

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0，\u5982 600519、\u8d35\u5dde\u8305\u53f0、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '\u5206\u6790' }));

    await waitFor(() => {
      expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).toBeInTheDocument();
    });
    expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/).closest('[role="alert"]')).toBeInTheDocument();
  });

  it('dismisses the duplicate task banner when its close button is clicked', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByPlaceholderText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0，\u5982 600519、\u8d35\u5dde\u8305\u53f0、AAPL');

    act(() => {
      useStockPoolStore.setState({ duplicateError: '\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d，\u8bf7\u7b49\u5f85\u5b8c\u6210' });
    });

    expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u5173\u95ed' }));

    expect(screen.queryByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).not.toBeInTheDocument();
  });

  it('auto-dismisses the duplicate task banner after 5 seconds', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(historyApi.getList).mockResolvedValue({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });

      render(
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>,
      );

      await act(async () => {
        await Promise.resolve();
      });

      act(() => {
        useStockPoolStore.setState({ duplicateError: '\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d，\u8bf7\u7b49\u5f85\u5b8c\u6210' });
      });

      expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(4999);
      });
      expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(screen.queryByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).not.toBeInTheDocument();
    } finally {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    }
  });

  it('restarts the auto-dismiss countdown when a duplicate task is triggered again', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(historyApi.getList).mockResolvedValue({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });

      render(
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>,
      );

      await act(async () => {
        await Promise.resolve();
      });

      act(() => {
        useStockPoolStore.setState({ duplicateError: '\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d，\u8bf7\u7b49\u5f85\u5b8c\u6210' });
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(4000);
      });
      expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).toBeInTheDocument();

      // Trigger the duplicate prompt again (the store clears then re-sets the message).
      act(() => {
        useStockPoolStore.setState({ duplicateError: null });
      });
      act(() => {
        useStockPoolStore.setState({ duplicateError: '\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d，\u8bf7\u7b49\u5f85\u5b8c\u6210' });
      });

      // 4s after the restart: still within the fresh 5s window because the countdown reset.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4000);
      });
      expect(screen.getByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).toBeInTheDocument();

      // Crossing the fresh 5s threshold finally closes the banner.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(screen.queryByText(/\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d/)).not.toBeInTheDocument();
    } finally {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    }
  });

  it('submits market review from the home toolbar', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\u5927\u76d8\u590d\u76d8\u4efb\u52a1\u5df2\u63d0\u4ea4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '\u5e02\u573a\u590d\u76d8\u62a5\u544a\u793a\u4f8b\u6587\u672c',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u5927\u76d8\u590d\u76d8' }));

    await waitFor(() => {
      expect(analysisApi.triggerMarketReview).toHaveBeenCalledWith({ sendNotification: true });
    });
    expect(await screen.findByText('\u5927\u76d8\u590d\u76d8\u5df2\u5b8c\u6210')).toBeInTheDocument();
    expect(await screen.findByText('\u5e02\u573a\u590d\u76d8\u62a5\u544a\u793a\u4f8b\u6587\u672c')).toBeInTheDocument();
    expect(analysisApi.getStatus).toHaveBeenCalledWith('task-1');
  });

  it('keeps report language unset when only the UI language is English', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-1',
      status: 'pending',
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: 'Market review task submitted',
      taskId: 'market-task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'market-task-1',
      status: 'completed',
      marketReviewReport: 'Market review report',
      marketReviewPayload: {
        kind: 'market_review',
        language: 'en',
        title: 'Market review',
        sections: [],
      },
    });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    fireEvent.change(await screen.findByPlaceholderText('Enter a stock code or name, e.g. 600519, Kweichow Moutai, AAPL'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }));
    fireEvent.click(screen.getByRole('button', { name: 'Market review' }));

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalled();
      expect(analysisApi.triggerMarketReview).toHaveBeenCalledWith({ sendNotification: true });
    });
    expect(vi.mocked(analysisApi.analyzeAsync).mock.calls[0]?.[0]).not.toHaveProperty('reportLanguage');
  });

  it('uses the payload language for live market review controls', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: 'Market review task submitted',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '# US Market Recap\n\n## Summary\n\nUS market review body',
      marketReviewPayload: {
        kind: 'market_review',
        region: 'us',
        language: 'en',
        title: 'US Market Recap',
        sections: [
          {
            key: 'summary',
            title: 'Summary',
            markdown: 'US market review body',
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u5927\u76d8\u590d\u76d8' }));

    expect(await screen.findByRole('button', { name: 'Copy Markdown Source' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy Plain Text' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u590d\u5236 Markdown \u6e90\u7801' })).not.toBeInTheDocument();
  });

  it('scrolls the dashboard to market review feedback after toolbar clicks', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\u5927\u76d8\u590d\u76d8\u4efb\u52a1\u5df2\u63d0\u4ea4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '\u5e02\u573a\u590d\u76d8\u62a5\u544a\u793a\u4f8b\u6587\u672c',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf');
    const dashboardScroll = screen.getByTestId('home-dashboard-scroll');
    const scrollToMock = vi.fn(function scrollTo(this: HTMLElement, options?: ScrollToOptions) {
      if (typeof options?.top === 'number') {
        this.scrollTop = options.top;
      }
    });
    Object.defineProperty(dashboardScroll, 'scrollTo', {
      configurable: true,
      value: scrollToMock,
    });
    dashboardScroll.scrollTop = 480;

    fireEvent.click(screen.getByRole('button', { name: '\u5927\u76d8\u590d\u76d8' }));

    await waitFor(() => {
      expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
    });
    expect(dashboardScroll.scrollTop).toBe(0);
    expect(await screen.findByText('\u5927\u76d8\u590d\u76d8\u5df2\u5b8c\u6210')).toBeInTheDocument();
  });

  it('keeps market review results in the main dashboard scroll area', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\u5927\u76d8\u590d\u76d8\u4efb\u52a1\u5df2\u63d0\u4ea4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: [
        '# A\u80a1\u5e02\u573a\u590d\u76d8',
        '',
        '> \u5e02\u573a\u60c5\u7eea\u4fee\u590d',
        '',
        '## \u6307\u6570\u6982\u89c8',
        '',
        '| \u6307\u6570 | \u8868\u73b0 |',
        '| --- | --- |',
        '| \u4e0a\u8bc1\u6307\u6570 | \u9707\u8361\u8d70\u5f3a |',
        '',
        '## \u98ce\u9669\u63d0\u793a',
        '',
        '- \u8d44\u91d1\u56de\u6d41\u6838\u5fc3\u8d44\u4ea7',
      ].join('\n'),
      marketReviewPayload: {
        kind: 'market_review',
        region: 'cn',
        title: 'A\u80a1\u5e02\u573a\u590d\u76d8',
        breadth: {
          upCount: 3200,
          downCount: 1700,
          limitUpCount: 60,
          limitDownCount: 8,
          totalAmount: 9800,
          turnoverUnit: '\u4ebf',
        },
        indices: [
          {
            code: '000001',
            name: '\u4e0a\u8bc1\u6307\u6570',
            current: 3150.2,
            changePct: 0.62,
            high: 3168.4,
            low: 3120.8,
          },
        ],
        sections: [
          {
            key: 'index_overview',
            title: '\u6307\u6570\u6982\u89c8',
            markdown: '| \u6307\u6570 | \u8868\u73b0 |\n| --- | --- |\n| \u4e0a\u8bc1\u6307\u6570 | \u9707\u8361\u8d70\u5f3a |',
          },
          {
            key: 'risk',
            title: '\u98ce\u9669\u63d0\u793a',
            markdown: '- \u8d44\u91d1\u56de\u6d41\u6838\u5fc3\u8d44\u4ea7',
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u5927\u76d8\u590d\u76d8' }));

    const dashboardScroll = screen.getByTestId('home-dashboard-scroll');
    const marketReviewReport = await screen.findByTestId('market-review-report');
    expect(dashboardScroll).toContainElement(marketReviewReport);
    expect(marketReviewReport.className).not.toContain('max-h-64');
    expect(marketReviewReport.className).not.toContain('overflow-y-auto');
    expect(screen.getByRole('heading', { name: '\u7ed3\u6784\u5316\u5927\u76d8\u6570\u636e' })).toBeInTheDocument();
    expect(screen.getByText('3200')).toBeInTheDocument();
    expect(screen.getByText('3150.20')).toBeInTheDocument();
    expect(marketReviewReport.querySelector('h2, h3')?.textContent).not.toBe('A\u80a1\u5e02\u573a\u590d\u76d8');
    expect(screen.getByRole('heading', { name: '\u6307\u6570\u6982\u89c8' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\u98ce\u9669\u63d0\u793a' })).toBeInTheDocument();
    expect(screen.getAllByRole('table').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('# A\u80a1\u5e02\u573a\u590d\u76d8')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5f00\u59cb\u5206\u6790')).not.toBeInTheDocument();
  });

  it('shows first-run setup gaps and links to settings', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: false,
      readyForSmoke: false,
      requiredMissingKeys: ['llm_primary', 'stock_list'],
      nextStepKey: 'llm_primary',
      checks: [
        {
          key: 'llm_primary',
          title: 'LLM \u4e3b\u6e20\u9053',
          category: 'ai_model',
          required: true,
          status: 'needs_action',
          message: '\u7f3a\u5c11\u4e3b\u6a21\u578b\u914d\u7f6e',
        },
        {
          key: 'stock_list',
          title: '\u81ea\u9009\u80a1',
          category: 'base',
          required: true,
          status: 'needs_action',
          message: '\u7f3a\u5c11\u81ea\u9009\u80a1',
        },
      ],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('\u57fa\u7840\u914d\u7f6e\u672a\u5b8c\u6210')).toBeInTheDocument();
    expect(screen.getByText(/LLM \u4e3b\u6e20\u9053、\u81ea\u9009\u80a1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u53bb\u914d\u7f6e' }));
    expect(navigateMock).toHaveBeenCalledWith('/settings');
  });

  it('navigates to chat with report context when asking a follow-up question', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const followUpButton = await screen.findByRole('button', { name: '\u8ffd\u95ee AI' });
    fireEvent.click(followUpButton);

    expect(navigateMock).toHaveBeenCalledWith(
      '/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1',
    );
  });

  it('opens and closes the mobile history drawer without changing dashboard styles', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const trigger = await screen.findByRole('button', { name: '\u5386\u53f2\u8bb0\u5f55' });
    fireEvent.click(trigger);

    expect(container.querySelector('.page-drawer-overlay')).toBeTruthy();
    expect(container.querySelector('.dashboard-card')).toBeTruthy();

    fireEvent.click(container.querySelector('.fixed.inset-0.z-40') as HTMLElement);

    await waitFor(() => {
      expect(container.querySelector('.page-drawer-overlay')).toBeFalsy();
    });
  });

  it('keeps same-stock history range controls in empty result state and allows switching back', async () => {
    const staleReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        createdAt: '2020-01-01T08:00:00Z',
      },
    };

    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [
        {
          id: 1,
          stockCode: '600519',
          stockName: '\u8d35\u5dde\u8305\u53f0',
          reportType: 'detailed',
          sentimentScore: 58,
          operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf\u4e70\u70b9',
          analysisCount: 2,
          lastAnalysisTime: '2026-03-21T08:00:00Z',
        },
      ],
    });

    vi.mocked(historyApi.getList).mockImplementation((params: { stockCode?: string; startDate?: string } = {}) => {
      if (!Object.prototype.hasOwnProperty.call(params, 'stockCode')) {
        return Promise.resolve({
          total: 1,
          page: 1,
          limit: 20,
          items: [historyItem],
        });
      }

      return Promise.resolve({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(staleReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const historyTrendButton = await screen.findByRole('button', { name: '\u5386\u53f2\u8d8b\u52bf' });
    fireEvent.click(historyTrendButton);

    const range30Button = await screen.findByRole('button', { name: '\u8fd130\u5929' });
    fireEvent.click(range30Button);

    await waitFor(() => {
      expect(screen.getByText('\u6682\u65e0\u66f4\u591a\u540c\u80a1\u5386\u53f2\u5206\u6790')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '\u5168\u90e8\u5386\u53f2' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '\u5168\u90e8\u5386\u53f2' }));

    await waitFor(() => {
      expect(screen.queryByText('\u6682\u65e0\u66f4\u591a\u540c\u80a1\u5386\u53f2\u5206\u6790')).not.toBeInTheDocument();
    });
    expect(screen.getAllByRole('button', { name: /\u8d35\u5dde\u8305\u53f0/ }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/2\u6b21/)).toBeInTheDocument();

    const historyCalls = vi.mocked(historyApi.getList).mock.calls.filter((call) => call[0]?.stockCode === '600519');
    expect(historyCalls).toHaveLength(3);
    expect(historyCalls[1][0]).toHaveProperty('startDate');
    expect(historyCalls[2][0]).not.toHaveProperty('startDate');
  });

  it('renders active task panel content from dashboard state', async () => {
    const activeTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '\u8d35\u5dde\u8305\u53f0',
      status: 'processing' as const,
      progress: 45,
      message: '\u6b63\u5728\u6293\u53d6\u6700\u65b0\u884c\u60c5',
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 1,
      pending: 0,
      processing: 1,
      tasks: [activeTask],
    });

    useStockPoolStore.setState({
      activeTasks: [activeTask],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('\u5206\u6790\u4efb\u52a1')).toBeInTheDocument();
    expect(screen.getByText('\u6b63\u5728\u6293\u53d6\u6700\u65b0\u884c\u60c5')).toBeInTheDocument();
  });

  it('triggers reanalyze for the current report even if the search input has other text', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-re-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    // Wait for the report to load
    await screen.findByText('\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf');

    // Type something else in the search box
    const input = screen.getByPlaceholderText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0，\u5982 600519、\u8d35\u5dde\u8305\u53f0、AAPL');
    fireEvent.change(input, { target: { value: 'AAPL' } });

    // Click "Reanalyze"
    const reanalyzeButton = screen.getByRole('button', { name: '\u91cd\u65b0\u5206\u6790' });
    fireEvent.click(reanalyzeButton);

    // Verify that analyzeAsync is called with the report's stock code, not the search box text
    expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: '600519',
      originalQuery: '600519',
      forceRefresh: true,
    }));
    expect(vi.mocked(analysisApi.analyzeAsync).mock.calls[0]?.[0]).not.toHaveProperty('reportLanguage');
  });

  it('passes the selected strategy when submitting stock analysis', async () => {
    vi.mocked(agentApi.getSkills).mockResolvedValue({
      default_skill_id: 'bull_trend',
      skills: [
        { id: 'bull_trend', name: '\u9ed8\u8ba4\u591a\u5934\u8d8b\u52bf', description: '\u8d8b\u52bf\u5206\u6790' },
        { id: 'growth_quality', name: '\u6210\u957f\u8d28\u91cf', description: '\u6210\u957f\u80a1\u5206\u6790' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-strategy-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u7b56\u7565' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: /\u6210\u957f\u8d28\u91cf/ }));

    const input = screen.getByPlaceholderText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0，\u5982 600519、\u8d35\u5dde\u8305\u53f0、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '\u5206\u6790' }));

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: '600519',
        skills: ['growth_quality'],
      }));
    });
  });

  it('supports keyboard navigation in the strategy menu', async () => {
    vi.mocked(agentApi.getSkills).mockResolvedValue({
      default_skill_id: 'bull_trend',
      skills: [
        { id: 'bull_trend', name: '\u9ed8\u8ba4\u591a\u5934\u8d8b\u52bf', description: '\u8d8b\u52bf\u5206\u6790' },
        { id: 'growth_quality', name: '\u6210\u957f\u8d28\u91cf', description: '\u6210\u957f\u80a1\u5206\u6790' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const trigger = await screen.findByRole('button', { name: '\u7b56\u7565' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });

    const defaultOption = await screen.findByRole('menuitemradio', { name: /\u9ed8\u8ba4\u7b56\u7565/ });
    await waitFor(() => {
      expect(defaultOption).toHaveFocus();
    });

    const menu = screen.getByRole('menu');
    fireEvent.keyDown(menu, { key: 'ArrowDown' });
    expect(screen.getByRole('menuitemradio', { name: /\u9ed8\u8ba4\u591a\u5934\u8d8b\u52bf/ })).toHaveFocus();

    fireEvent.keyDown(menu, { key: 'End' });
    expect(screen.getByRole('menuitemradio', { name: /\u6210\u957f\u8d28\u91cf/ })).toHaveFocus();

    fireEvent.keyDown(menu, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
    expect(trigger).toHaveFocus();
  });

  it('renders market review history reports with a dedicated markdown view', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [marketReviewHistoryItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(marketReviewHistoryReport);
    vi.mocked(historyApi.getMarkdown).mockResolvedValue([
      '# \u5927\u76d8\u590d\u76d8\u8be6\u60c5',
      '',
      '## \u5e02\u573a\u60c5\u7eea\u4e0e\u8d5a\u94b1\u6548\u5e94',
      '',
      '**\u8d5a\u94b1\u6548\u5e94** \u6539\u5584',
      '',
      '## \u884c\u4e1a/\u4e3b\u9898\u8f6e\u52a8',
      '',
      '| \u65b9\u5411 | \u72b6\u6001 |',
      '| --- | --- |',
      '| \u534a\u5bfc\u4f53 | \u8f6e\u52a8\u589e\u5f3a |',
    ].join('\n'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('\u5927\u76d8\u590d\u76d8\u6458\u8981');
    expect(screen.queryByRole('heading', { name: '\u5927\u76d8\u590d\u76d8\u8be6\u60c5' })).not.toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: '\u5e02\u573a\u60c5\u7eea\u4e0e\u8d5a\u94b1\u6548\u5e94' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\u884c\u4e1a/\u4e3b\u9898\u8f6e\u52a8' })).toBeInTheDocument();
    expect(screen.getByText('\u8d5a\u94b1\u6548\u5e94')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u91cd\u65b0\u5206\u6790' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u8ffd\u95ee AI' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u91cd\u65b0\u590d\u76d8' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u5386\u53f2\u8d8b\u52bf' })).toBeInTheDocument();
    expect(historyApi.getMarkdown).toHaveBeenCalledWith(marketReviewHistoryReport.meta.id);

    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('clears live market review output when switching to a history report', async () => {
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 1,
          page: 1,
          limit: 10,
          items: [marketReviewHistoryItem],
        });
      }
      return Promise.resolve({
        total: 1,
        page: 1,
        limit: 20,
        items: [historyItem],
      });
    });
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [
        {
          id: 1,
          stockCode: '600519',
          stockName: '\u8d35\u5dde\u8305\u53f0',
          sentimentScore: 82,
          operationAdvice: '\u4e70\u5165',
          analysisCount: 1,
          lastAnalysisTime: '2026-03-18T08:00:00Z',
          reportType: 'detailed',
        },
      ],
    });
    vi.mocked(historyApi.getDetail).mockImplementation((recordId: number) => {
      if (recordId === 2) {
        return Promise.resolve(marketReviewHistoryReport);
      }
      return Promise.resolve(historyReport);
    });
    vi.mocked(historyApi.getMarkdown).mockResolvedValue([
      '# \u5927\u76d8\u590d\u76d8\u8be6\u60c5',
      '',
      '## \u5e02\u573a\u60c5\u7eea\u4e0e\u8d5a\u94b1\u6548\u5e94',
      '',
      '**\u8d5a\u94b1\u6548\u5e94** \u6539\u5584',
      '',
      '## \u884c\u4e1a/\u4e3b\u9898\u8f6e\u52a8',
      '',
      '| \u65b9\u5411 | \u72b6\u6001 |',
      '| --- | --- |',
      '| \u534a\u5bfc\u4f53 | \u8f6e\u52a8\u589e\u5f3a |',
    ].join('\n'));
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\u5927\u76d8\u590d\u76d8\u4efb\u52a1\u5df2\u63d0\u4ea4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '\u5e02\u573a\u590d\u76d8\u62a5\u544a\u793a\u4f8b\u6587\u672c',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf');

    fireEvent.click(screen.getByRole('button', { name: '\u5927\u76d8\u590d\u76d8' }));

    await waitFor(() => {
      expect(screen.getByText('\u5927\u76d8\u590d\u76d8\u5df2\u5b8c\u6210')).toBeInTheDocument();
      expect(screen.getByText('\u5e02\u573a\u590d\u76d8\u62a5\u544a\u793a\u4f8b\u6587\u672c')).toBeInTheDocument();
    });

    const marketHistoryButton = await screen.findByRole('button', { name: /MARKET/ });
    fireEvent.click(marketHistoryButton);

    await waitFor(() => {
      expect(screen.queryByText('\u5e02\u573a\u590d\u76d8\u62a5\u544a\u793a\u4f8b\u6587\u672c')).not.toBeInTheDocument();
      expect(screen.queryByText('\u5927\u76d8\u590d\u76d8\u5df2\u5b8c\u6210')).not.toBeInTheDocument();
    });
    expect(await screen.findByText('\u5927\u76d8\u590d\u76d8\u6458\u8981')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\u5e02\u573a\u60c5\u7eea\u4e0e\u8d5a\u94b1\u6548\u5e94' })).toBeInTheDocument();
    expect(vi.mocked(historyApi.getDetail)).toHaveBeenCalledWith(2);
  });
});
