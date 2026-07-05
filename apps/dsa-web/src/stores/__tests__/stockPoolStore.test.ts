import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { historyApi } from '../../api/history';
import type { AnalysisReport, HistoryListResponse, TaskInfo, TaskListResponse } from '../../types/analysis';
import { getRecentStartDate, getTodayInShanghai } from '../../utils/format';
import { useStockPoolStore } from '../stockPoolStore';

vi.mock('../../api/history', () => ({
  historyApi: {
    getList: vi.fn(),
    getDetail: vi.fn(),
    deleteRecords: vi.fn(),
    getStockBarList: vi.fn(),
  },
}));

vi.mock('../../api/analysis', async () => {
  const actual = await vi.importActual<typeof import('../../api/analysis')>('../../api/analysis');
  return {
    ...actual,
    analysisApi: {
      analyzeAsync: vi.fn(),
      getTasks: vi.fn(),
    },
  };
});

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
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf',
    operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf\u4e70\u70b9',
    trendPrediction: '\u77ed\u7ebf\u9707\u8361\u504f\u5f3a',
    sentimentScore: 78,
  },
};

const marketReviewHistoryReport = {
  ...historyReport,
  meta: {
    ...historyReport.meta,
    id: 10,
    queryId: 'q-10',
    stockCode: '',
    stockName: '\u5927\u76d8\u590d\u76d8',
    reportType: 'market_review' as const,
  },
};

function createTask(overrides: Partial<TaskInfo> = {}): TaskInfo {
  return {
    taskId: 'task-1',
    stockCode: '600519',
    stockName: '\u8d35\u5dde\u8305\u53f0',
    status: 'processing',
    progress: 50,
    reportType: 'detailed',
    createdAt: '2026-03-18T08:00:00Z',
    ...overrides,
  };
}

function createTaskListResponse(
  tasks: TaskInfo[],
  counts: Partial<Pick<TaskListResponse, 'pending' | 'processing' | 'total'>> = {},
): TaskListResponse {
  const pending = counts.pending ?? tasks.filter((task) => task.status === 'pending').length;
  const processing = counts.processing ?? tasks.filter((task) => task.status === 'processing').length;
  return {
    total: counts.total ?? tasks.length,
    pending,
    processing,
    tasks,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('stockPoolStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useStockPoolStore.getState().resetDashboardState();
    vi.mocked(analysisApi.getTasks).mockResolvedValue(createTaskListResponse([]));
  });

  it('loads initial history and auto-selects the first report', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    await useStockPoolStore.getState().loadInitialHistory();

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(1);
    expect(state.selectedReport?.meta.stockCode).toBe('600519');
    expect(state.isLoadingHistory).toBe(false);
    expect(state.isLoadingReport).toBe(false);
  });

  it('opens same-stock history trend and loads more records', async () => {
    const olderItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      modelUsed: 'gemini/gemini-2.5-pro',
    };

    useStockPoolStore.setState({ selectedReport: historyReport });
    vi.mocked(historyApi.getList)
      .mockResolvedValueOnce({
        total: 2,
        page: 1,
        limit: 20,
        items: [historyItem],
      })
      .mockResolvedValueOnce({
        total: 2,
        page: 2,
        limit: 20,
        items: [olderItem],
      });

    await useStockPoolStore.getState().openHistoryTrend();

    let state = useStockPoolStore.getState();
    expect(state.isHistoryTrendOpen).toBe(true);
    expect(state.stockHistoryItems).toEqual([historyItem]);
    expect(state.stockHistoryHasMore).toBe(true);
    expect(historyApi.getList).toHaveBeenLastCalledWith({
      stockCode: '600519',
      page: 1,
      limit: 20,
    });

    await useStockPoolStore.getState().loadMoreStockHistory();

    state = useStockPoolStore.getState();
    expect(state.stockHistoryItems.map((item) => item.id)).toEqual([1, 2]);
    expect(state.stockHistoryHasMore).toBe(false);
    expect(historyApi.getList).toHaveBeenLastCalledWith({
      stockCode: '600519',
      page: 2,
      limit: 20,
    });
  });

  it('deduplicates same-stock trend records when loading more pages', async () => {
    const duplicateCurrentItem = {
      ...historyItem,
      id: 1,
      queryId: 'q-1',
    };
    const olderPageItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      modelUsed: 'gemini/gemini-2.5-pro',
    };
    const thirdItem = {
      ...historyItem,
      id: 3,
      queryId: 'q-3',
      modelUsed: 'gemini/gemini-2.5-flash',
    };

    useStockPoolStore.setState({ selectedReport: historyReport });
    vi.mocked(historyApi.getList)
      .mockResolvedValueOnce({
        total: 3,
        page: 1,
        limit: 20,
        items: [olderPageItem],
      })
      .mockResolvedValueOnce({
        total: 3,
        page: 2,
        limit: 20,
        items: [duplicateCurrentItem, thirdItem],
      });

    await useStockPoolStore.getState().openHistoryTrend();
    await useStockPoolStore.getState().loadMoreStockHistory();

    const state = useStockPoolStore.getState();
    expect(state.stockHistoryItems.map((item) => item.id)).toEqual([1, 2, 3]);
  });

  it('does not inject the current report when it is outside the selected history time range', async () => {
    const oldSelectedReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 5,
        queryId: 'q-old',
        createdAt: '2020-01-01T08:00:00Z',
      },
    };

    useStockPoolStore.setState({
      selectedReport: oldSelectedReport,
      stockHistoryFilters: {
        range: '30d',
        model: 'all',
        sort: 'desc',
      },
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [
        {
          ...historyItem,
          id: 6,
          queryId: 'q-in-range',
          createdAt: '2026-03-18T08:00:00Z',
        },
      ],
    });

    await useStockPoolStore.getState().openHistoryTrend();

    const state = useStockPoolStore.getState();
    expect(state.stockHistoryItems).toHaveLength(1);
    expect(state.stockHistoryItems[0].id).toBe(6);
    expect(state.stockHistoryItems[0].id).not.toBe(5);
    expect(historyApi.getList).toHaveBeenCalledWith({
      stockCode: '600519',
      startDate: getRecentStartDate(30),
      endDate: getTodayInShanghai(),
      page: 1,
      limit: 20,
    });
  });

  it('loads market-review trend history when selecting a market-review report', async () => {
    const marketItem = {
      ...historyItem,
      id: 10,
      queryId: 'market-review-q-10',
      stockCode: 'MARKET',
      stockName: '\u5927\u76d8\u590d\u76d8',
      reportType: 'market_review' as const,
    };
    useStockPoolStore.setState({
      selectedReport: historyReport,
      isHistoryTrendOpen: true,
      stockHistoryItems: [{ ...historyItem, modelUsed: 'gemini/gemini-2.5-pro' }],
      stockHistoryTotal: 12,
      stockHistoryPage: 3,
      stockHistoryHasMore: true,
    });

    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [marketItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(marketReviewHistoryReport);

    await useStockPoolStore.getState().selectHistoryItem(1);

    const state = useStockPoolStore.getState();
    expect(state.selectedReport?.meta.reportType).toBe('market_review');
    expect(state.isHistoryTrendOpen).toBe(true);
    expect(state.stockHistoryItems).toEqual([marketItem]);
    expect(state.stockHistoryTotal).toBe(1);
    expect(state.stockHistoryPage).toBe(1);
    expect(state.stockHistoryHasMore).toBe(false);
    expect(state.isLoadingStockHistory).toBe(false);
    expect(state.isLoadingMoreStockHistory).toBe(false);
    expect(historyApi.getList).toHaveBeenCalledWith({
      stockCode: 'MARKET',
      reportType: 'market_review',
      page: 1,
      limit: 20,
    });
  });

  it('loads market review history through the dedicated MARKET filter', async () => {
    const marketItem = {
      ...historyItem,
      id: 10,
      queryId: 'market-review-q-10',
      stockCode: 'MARKET',
      stockName: '\u5927\u76d8\u590d\u76d8',
      reportType: 'market_review' as const,
      operationAdvice: '\u67e5\u770b\u590d\u76d8',
      sentimentScore: 50,
    };
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [marketItem],
    });

    await useStockPoolStore.getState().loadMarketReviewHistory();

    const state = useStockPoolStore.getState();
    expect(state.marketReviewHistoryItems).toEqual([marketItem]);
    expect(state.marketReviewHistoryHasMore).toBe(false);
    expect(historyApi.getList).toHaveBeenCalledWith({
      stockCode: 'MARKET',
      reportType: 'market_review',
      page: 1,
      limit: 10,
    });
  });

  it('deduplicates market review history after silent refresh shifts pagination', async () => {
    const createMarketReviewItem = (id: number) => ({
      ...historyItem,
      id,
      queryId: `market-review-q-${id}`,
      stockCode: 'MARKET',
      stockName: '\u5927\u76d8\u590d\u76d8',
      reportType: 'market_review' as const,
    });
    const loadedItems = Array.from({ length: 20 }, (_, index) => createMarketReviewItem(index + 1));
    const newlyCompletedItem = createMarketReviewItem(21);

    useStockPoolStore.setState({
      marketReviewHistoryItems: loadedItems,
      marketReviewHistoryPage: 2,
      marketReviewHistoryHasMore: true,
    });
    vi.mocked(historyApi.getList)
      .mockResolvedValueOnce({
        total: 21,
        page: 1,
        limit: 10,
        items: [newlyCompletedItem, ...loadedItems.slice(0, 9)],
      })
      .mockResolvedValueOnce({
        total: 21,
        page: 3,
        limit: 10,
        items: [loadedItems[19]],
      });

    await useStockPoolStore.getState().refreshMarketReviewHistory(true);
    await useStockPoolStore.getState().loadMoreMarketReviewHistory();

    const state = useStockPoolStore.getState();
    expect(state.marketReviewHistoryItems.map((item) => item.id)).toEqual([
      21,
      ...Array.from({ length: 20 }, (_, index) => index + 1),
    ]);
    expect(state.marketReviewHistoryHasMore).toBe(false);
    expect(historyApi.getList).toHaveBeenLastCalledWith({
      stockCode: 'MARKET',
      reportType: 'market_review',
      page: 3,
      limit: 10,
    });
  });

  it('deletes the selected market review history record and clears the open market report', async () => {
    const marketItem = {
      ...historyItem,
      id: 10,
      queryId: 'market-review-q-10',
      stockCode: 'MARKET',
      stockName: '\u5927\u76d8\u590d\u76d8',
      reportType: 'market_review' as const,
    };
    useStockPoolStore.setState({
      marketReviewHistoryItems: [marketItem],
      selectedMarketReviewHistoryIds: [10],
      selectedReport: marketReviewHistoryReport,
    });

    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 10,
      items: [],
    });

    await useStockPoolStore.getState().deleteSelectedMarketReviewHistory();

    const state = useStockPoolStore.getState();
    expect(historyApi.deleteRecords).toHaveBeenCalledWith([10]);
    expect(state.marketReviewHistoryItems).toEqual([]);
    expect(state.selectedMarketReviewHistoryIds).toEqual([]);
    expect(state.selectedReport).toBeNull();
  });

  it('deletes selected history and clears the selected report when nothing remains', async () => {
    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedHistoryIds: [1],
      selectedReport: historyReport,
    });

    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    await useStockPoolStore.getState().deleteSelectedHistory();

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(0);
    expect(state.selectedHistoryIds).toHaveLength(0);
    expect(state.selectedReport).toBeNull();
    expect(historyApi.getList).toHaveBeenCalledTimes(1);
  });

  it('falls back to the next history report after deleting the currently selected item', async () => {
    const nextHistoryItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      stockCode: 'AAPL',
      stockName: 'Apple',
    };
    const nextHistoryReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        stockCode: 'AAPL',
        stockName: 'Apple',
      },
    };

    useStockPoolStore.setState({
      historyItems: [historyItem, nextHistoryItem],
      selectedHistoryIds: [1],
      selectedReport: historyReport,
    });

    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [nextHistoryItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(nextHistoryReport);

    await useStockPoolStore.getState().deleteSelectedHistory();

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(1);
    expect(state.historyItems[0].id).toBe(2);
    expect(state.selectedReport?.meta.id).toBe(2);
    expect(state.selectedReport?.meta.stockCode).toBe('AAPL');
  });

  it('surfaces duplicate task errors without replacing the dashboard error state', async () => {
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(
      new DuplicateTaskError('600519', 'task-1', '\u80a1\u7968 600519 \u6b63\u5728\u5206\u6790\u4e2d'),
    );

    useStockPoolStore.getState().setQuery('600519');
    await useStockPoolStore.getState().submitAnalysis();

    const state = useStockPoolStore.getState();
    expect(state.duplicateError).toContain('600519');
    expect(state.error).toBeNull();
    expect(state.isAnalyzing).toBe(false);
  });

  it('rejects obviously invalid mixed alphanumeric input before calling the API', async () => {
    useStockPoolStore.getState().setQuery('00aaaaa');

    await useStockPoolStore.getState().submitAnalysis();

    const state = useStockPoolStore.getState();
    expect(state.inputError).toBe('\u8bf7\u8f93\u5165\u6709\u6548\u7684\u80a1\u7968\u4ee3\u7801\u6216\u80a1\u7968\u540d\u79f0');
    expect(state.isAnalyzing).toBe(false);
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('accepts HK suffix codes from autocomplete without local validation errors', async () => {
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-hk-1',
      stockCode: '00700.HK',
      status: 'pending',
      message: 'accepted',
    } as never);

    await useStockPoolStore.getState().submitAnalysis({
      stockCode: '00700.HK',
      stockName: '\u817e\u8baf\u63a7\u80a1',
      originalQuery: '00700',
      selectionSource: 'autocomplete',
    });

    const state = useStockPoolStore.getState();
    expect(state.inputError).toBeUndefined();
    expect(state.isAnalyzing).toBe(false);
    expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: '00700.HK',
      reportType: 'detailed',
      stockName: '\u817e\u8baf\u63a7\u80a1',
      originalQuery: '00700',
      selectionSource: 'autocomplete',
      notify: true,
    }));
  });

  it('merges newly discovered history items during silent refresh', async () => {
    useStockPoolStore.setState({
      historyItems: [historyItem],
      currentPage: 1,
      hasMore: true,
    });

    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 2,
      page: 1,
      limit: 20,
      items: [
        { ...historyItem, id: 2, queryId: 'q-2', stockCode: 'AAPL', stockName: 'Apple' },
        historyItem,
      ],
    });

    await useStockPoolStore.getState().refreshHistory(true);

    const state = useStockPoolStore.getState();
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1]);
    expect(state.currentPage).toBe(1);
  });

  it('selects the newest report for the completed task stock during silent refresh', async () => {
    const latestItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      createdAt: '2026-03-18T09:00:00Z',
    };
    const latestReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        createdAt: '2026-03-18T09:00:00Z',
      },
    };

    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedReport: historyReport,
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestItem, historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(latestReport);

    await useStockPoolStore.getState().refreshHistoryForCompletedTask(createTask({
      status: 'completed',
      progress: 100,
    }));

    const state = useStockPoolStore.getState();
    expect(historyApi.getDetail).toHaveBeenCalledWith(2);
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1]);
    expect(state.selectedReport?.meta.id).toBe(2);
  });

  it('selects the completed-task report after an overlapping refresh supersedes the original request', async () => {
    const latestItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      createdAt: '2026-03-18T09:00:00Z',
    };
    const latestReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        createdAt: '2026-03-18T09:00:00Z',
      },
    };
    const completedRefresh = createDeferred<HistoryListResponse>();
    const overlappingRefresh = createDeferred<HistoryListResponse>();

    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedReport: historyReport,
    });
    vi.mocked(historyApi.getList)
      .mockReturnValueOnce(completedRefresh.promise)
      .mockReturnValueOnce(overlappingRefresh.promise);
    vi.mocked(historyApi.getDetail).mockResolvedValue(latestReport);

    const completedRefreshPromise = useStockPoolStore.getState().refreshHistoryForCompletedTask(createTask({
      status: 'completed',
      progress: 100,
    }));
    const overlappingRefreshPromise = useStockPoolStore.getState().refreshHistory(true);

    overlappingRefresh.resolve({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestItem, historyItem],
    });
    await overlappingRefreshPromise;

    completedRefresh.resolve({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestItem, historyItem],
    });
    await completedRefreshPromise;

    const state = useStockPoolStore.getState();
    expect(historyApi.getDetail).toHaveBeenCalledTimes(1);
    expect(historyApi.getDetail).toHaveBeenCalledWith(2);
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1]);
    expect(state.selectedReport?.meta.id).toBe(2);
  });

  it('selects the newest completed-task report when stock codes use equivalent aliases', async () => {
    const olderTencentItem = {
      ...historyItem,
      id: 10,
      queryId: 'q-10',
      stockCode: 'HK00700',
      stockName: '\u817e\u8baf\u63a7\u80a1',
    };
    const olderTencentReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 10,
        queryId: 'q-10',
        stockCode: 'HK00700',
        stockName: '\u817e\u8baf\u63a7\u80a1',
      },
    };
    const latestTencentItem = {
      ...olderTencentItem,
      id: 11,
      queryId: 'q-11',
      stockCode: '00700.HK',
      createdAt: '2026-03-18T09:00:00Z',
    };
    const latestTencentReport = {
      ...olderTencentReport,
      meta: {
        ...olderTencentReport.meta,
        id: 11,
        queryId: 'q-11',
        stockCode: '00700.HK',
        createdAt: '2026-03-18T09:00:00Z',
      },
    };

    useStockPoolStore.setState({
      historyItems: [olderTencentItem],
      selectedReport: olderTencentReport,
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestTencentItem, olderTencentItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(latestTencentReport);

    await useStockPoolStore.getState().refreshHistoryForCompletedTask(createTask({
      stockCode: '00700.HK',
      stockName: '\u817e\u8baf\u63a7\u80a1',
      status: 'completed',
      progress: 100,
    }));

    const state = useStockPoolStore.getState();
    expect(historyApi.getDetail).toHaveBeenCalledWith(11);
    expect(state.historyItems.map((item) => item.id)).toEqual([11, 10]);
    expect(state.selectedReport?.meta.id).toBe(11);
  });

  it('does not replace the selected report when another stock task completes', async () => {
    const otherReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 3,
        queryId: 'q-3',
        stockCode: 'AAPL',
        stockName: 'Apple',
      },
    };
    const latestItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      createdAt: '2026-03-18T09:00:00Z',
    };

    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedReport: otherReport,
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestItem, historyItem],
    });

    await useStockPoolStore.getState().refreshHistoryForCompletedTask(createTask({
      status: 'completed',
      progress: 100,
    }));

    const state = useStockPoolStore.getState();
    expect(historyApi.getDetail).not.toHaveBeenCalled();
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1]);
    expect(state.selectedReport?.meta.stockCode).toBe('AAPL');
  });

  it('does not auto-switch to completed-task latest when the selected report changed before the refresh response returns', async () => {
    const latestItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      createdAt: '2026-03-18T09:00:00Z',
    };
    const latestCompletedReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        createdAt: '2026-03-18T09:00:00Z',
      },
    };
    const switchedReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 3,
        queryId: 'q-3',
      },
    };
    const completedRefreshResponse = createDeferred<HistoryListResponse>();

    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedReport: historyReport,
    });
    vi.mocked(historyApi.getList).mockReturnValue(completedRefreshResponse.promise);
    vi.mocked(historyApi.getDetail).mockResolvedValue(latestCompletedReport);

    const completedRefreshPromise = useStockPoolStore.getState().refreshHistoryForCompletedTask(createTask({
      status: 'completed',
      progress: 100,
    }));

    useStockPoolStore.setState({
      selectedReport: switchedReport,
    });

    completedRefreshResponse.resolve({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestItem, historyItem],
    });
    await completedRefreshPromise;

    const state = useStockPoolStore.getState();
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1]);
    expect(state.selectedReport?.meta.id).toBe(3);
    expect(historyApi.getDetail).not.toHaveBeenCalled();
  });

  it('does not auto-switch report when user selection is pending during completed-task refresh', async () => {
    const latestItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      createdAt: '2026-03-18T09:00:00Z',
    };
    const completedRefreshResponse = createDeferred<HistoryListResponse>();
    const userSelectionDetail = createDeferred<AnalysisReport>();
    const userSelectionReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 3,
        queryId: 'q-3',
        stockCode: 'AAPL',
        stockName: 'Apple',
        createdAt: '2026-03-18T07:00:00Z',
      },
    };
    const latestCompletedReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        createdAt: '2026-03-18T09:00:00Z',
      },
    };

    useStockPoolStore.setState({
      historyItems: [
        historyItem,
        {
          ...historyItem,
          id: 3,
          queryId: 'q-3',
          stockCode: 'AAPL',
          stockName: 'Apple',
          createdAt: '2026-03-18T07:00:00Z',
        },
      ],
      selectedReport: historyReport,
    });
    vi.mocked(historyApi.getList).mockReturnValueOnce(completedRefreshResponse.promise);
    vi.mocked(historyApi.getDetail)
      .mockReturnValueOnce(userSelectionDetail.promise)
      .mockResolvedValue(latestCompletedReport);

    const completedRefreshPromise = useStockPoolStore.getState().refreshHistoryForCompletedTask(
      createTask({
        status: 'completed',
        progress: 100,
      }),
    );
    const manualSelectionPromise = useStockPoolStore.getState().selectHistoryItem(3);

    completedRefreshResponse.resolve({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestItem, historyItem],
    });
    await completedRefreshPromise;

    const midState = useStockPoolStore.getState();
    expect(midState.selectedReport?.meta.id).toBe(historyReport.meta.id);
    expect(historyApi.getDetail).toHaveBeenCalledWith(3);
    expect(historyApi.getDetail).toHaveBeenCalledTimes(1);

    userSelectionDetail.resolve(userSelectionReport);
    await manualSelectionPromise;

    const state = useStockPoolStore.getState();
    expect(state.selectedReport?.meta.id).toBe(3);
    expect(state.selectedReport?.meta.stockCode).toBe('AAPL');
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1, 3]);
  });

  it('ignores late history responses after dashboard reset', async () => {
    const deferred = createDeferred<{
      total: number;
      page: number;
      limit: number;
      items: typeof historyItem[];
    }>();

    vi.mocked(historyApi.getList).mockImplementation(() => deferred.promise);

    const loadPromise = useStockPoolStore.getState().loadInitialHistory();
    useStockPoolStore.getState().resetDashboardState();

    deferred.resolve({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });

    await loadPromise;

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(0);
    expect(state.isLoadingHistory).toBe(false);
    expect(state.currentPage).toBe(1);
  });

  it('tracks task lifecycle updates and resets all dashboard state', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '\u8d35\u5dde\u8305\u53f0',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'processing',
      progress: 60,
    });

    let state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(1);
    expect(state.activeTasks[0].status).toBe('processing');

    useStockPoolStore.getState().removeTask('task-1');
    state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);

    useStockPoolStore.setState({
      query: 'AAPL',
      selectedHistoryIds: [1],
      selectedReport: historyReport,
      markdownDrawerOpen: true,
      activeTasks: [
        {
          ...pendingTask,
          taskId: 'task-2',
          status: 'processing',
          progress: 80,
        },
      ],
    });

    useStockPoolStore.getState().resetDashboardState();
    state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);
    expect(state.query).toBe('');
    expect(state.selectedHistoryIds).toHaveLength(0);
    expect(state.selectedReport).toBeNull();
    expect(state.markdownDrawerOpen).toBe(false);
  });

  it('ignores late task updates after a task has been removed', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '\u8d35\u5dde\u8305\u53f0',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().removeTask('task-1');
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'processing',
      progress: 35,
    });
    useStockPoolStore.getState().syncTaskCreated(pendingTask);

    expect(useStockPoolStore.getState().activeTasks).toHaveLength(0);
  });

  it('ignores unknown task updates after dashboard reset', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '\u8d35\u5dde\u8305\u53f0',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().resetDashboardState();
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'processing',
      progress: 35,
    });

    const state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);
  });

  it('does not backfill unknown failed tasks from SSE updates', () => {
    useStockPoolStore.getState().syncTaskFailed({
      taskId: 'task-404',
      stockCode: 'AAPL',
      stockName: 'Apple',
      status: 'failed',
      progress: 100,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
      error: '\u5206\u6790\u5931\u8d25',
    });

    const state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);
    expect(state.error).toBeTruthy();
  });

  it('reconciles active tasks from a complete empty backend snapshot without dismissing them', async () => {
    const staleTask = createTask();
    useStockPoolStore.getState().syncTaskCreated(staleTask);
    vi.mocked(analysisApi.getTasks).mockResolvedValue(createTaskListResponse([]));

    await useStockPoolStore.getState().refreshActiveTasks();

    expect(analysisApi.getTasks).toHaveBeenCalledWith({
      status: 'pending,processing,cancel_requested',
      limit: 100,
    });
    expect(useStockPoolStore.getState().activeTasks).toHaveLength(0);

    useStockPoolStore.getState().syncTaskCreated(staleTask);
    expect(useStockPoolStore.getState().activeTasks).toEqual([staleTask]);
  });

  it('does not prune tasks created after an active-task refresh request started', async () => {
    const emptySnapshot = createDeferred<TaskListResponse>();
    const createdTask = createTask({
      taskId: 'task-created-after-request',
      status: 'pending',
      progress: 0,
    });
    const updatedTask = {
      ...createdTask,
      status: 'processing' as const,
      progress: 35,
    };
    vi.mocked(analysisApi.getTasks).mockReturnValue(emptySnapshot.promise);

    const refreshPromise = useStockPoolStore.getState().refreshActiveTasks();
    useStockPoolStore.getState().syncTaskCreated(createdTask);

    emptySnapshot.resolve(createTaskListResponse([]));
    await refreshPromise;

    expect(useStockPoolStore.getState().activeTasks).toEqual([createdTask]);

    useStockPoolStore.getState().syncTaskUpdated(updatedTask);
    expect(useStockPoolStore.getState().activeTasks).toEqual([updatedTask]);
  });

  it('upserts pending and processing tasks from the backend snapshot', async () => {
    const existingTask = createTask({ taskId: 'task-existing', progress: 30 });
    const updatedTask = createTask({ taskId: 'task-existing', progress: 80, message: 'LLM \u6b63\u5728\u751f\u6210\u5206\u6790\u7ed3\u679c' });
    const newTask = createTask({
      taskId: 'task-new',
      stockCode: '000001',
      stockName: '\u5e73\u5b89\u94f6\u884c',
      status: 'pending',
      progress: 0,
    });
    useStockPoolStore.getState().syncTaskCreated(existingTask);
    vi.mocked(analysisApi.getTasks).mockResolvedValue(
      createTaskListResponse([updatedTask, newTask]),
    );

    await useStockPoolStore.getState().refreshActiveTasks();

    expect(useStockPoolStore.getState().activeTasks).toEqual([updatedTask, newTask]);
  });

  it('does not re-add dismissed tasks from backend reconciliation', async () => {
    const dismissedTask = createTask();
    useStockPoolStore.getState().syncTaskCreated(dismissedTask);
    useStockPoolStore.getState().removeTask(dismissedTask.taskId);
    vi.mocked(analysisApi.getTasks).mockResolvedValue(
      createTaskListResponse([dismissedTask]),
    );

    await useStockPoolStore.getState().refreshActiveTasks();

    expect(useStockPoolStore.getState().activeTasks).toHaveLength(0);
  });

  it('ignores late active-task snapshots from older refreshes', async () => {
    const staleSnapshot = createDeferred<TaskListResponse>();
    const freshSnapshot = createDeferred<TaskListResponse>();
    const staleTask = createTask({ taskId: 'task-stale' });
    const freshTask = createTask({ taskId: 'task-fresh', stockCode: '000001', stockName: '\u5e73\u5b89\u94f6\u884c' });
    vi.mocked(analysisApi.getTasks)
      .mockReturnValueOnce(staleSnapshot.promise)
      .mockReturnValueOnce(freshSnapshot.promise);

    const staleRefresh = useStockPoolStore.getState().refreshActiveTasks();
    const freshRefresh = useStockPoolStore.getState().refreshActiveTasks();

    freshSnapshot.resolve(createTaskListResponse([freshTask]));
    await freshRefresh;
    expect(useStockPoolStore.getState().activeTasks).toEqual([freshTask]);

    staleSnapshot.resolve(createTaskListResponse([staleTask]));
    await staleRefresh;
    expect(useStockPoolStore.getState().activeTasks).toEqual([freshTask]);
  });

  it('does not prune local tasks when the backend active-task snapshot is incomplete', async () => {
    const localTask = createTask({ taskId: 'task-local' });
    const remoteTask = createTask({ taskId: 'task-remote', stockCode: '000001', stockName: '\u5e73\u5b89\u94f6\u884c' });
    useStockPoolStore.getState().syncTaskCreated(localTask);
    vi.mocked(analysisApi.getTasks).mockResolvedValue(
      createTaskListResponse([remoteTask], { processing: 2, total: 2 }),
    );

    await useStockPoolStore.getState().refreshActiveTasks();

    expect(useStockPoolStore.getState().activeTasks).toEqual([localTask, remoteTask]);
  });

  it('prunes stale local tasks when a complete backend snapshot contains cancel-requested tasks', async () => {
    const staleTask = createTask({ taskId: 'task-stale', status: 'processing' });
    const cancelRequestedTask = createTask({
      taskId: 'task-cancel-requested',
      status: 'cancel_requested',
      progress: 60,
      message: '\u6b63\u5728\u53d6\u6d88\u4efb\u52a1',
    });
    useStockPoolStore.getState().syncTaskCreated(staleTask);
    vi.mocked(analysisApi.getTasks).mockResolvedValue(
      createTaskListResponse([cancelRequestedTask]),
    );

    await useStockPoolStore.getState().refreshActiveTasks();

    expect(useStockPoolStore.getState().activeTasks).toEqual([cancelRequestedTask]);
  });

  it('keeps active tasks unchanged when backend reconciliation fails', async () => {
    const activeTask = createTask();
    useStockPoolStore.getState().syncTaskCreated(activeTask);
    vi.mocked(analysisApi.getTasks).mockRejectedValue(new Error('network failed'));

    await useStockPoolStore.getState().refreshActiveTasks();

    expect(useStockPoolStore.getState().activeTasks).toEqual([activeTask]);
  });

  it('triggers an analysis with the forceRefresh flag', async () => {
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-force-1',
      status: 'pending',
    } as never);

    await useStockPoolStore.getState().submitAnalysis({
      stockCode: '600519',
      forceRefresh: true,
    });

    expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: '600519',
      forceRefresh: true,
    }));
  });
});
