import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockScreeningPage from '../StockScreeningPage';

const {
  enableAlphaSift,
  getAlphaSiftStatus,
  getHotspotDetail,
  getHotspots,
  getStrategies,
  getScreenTask,
  navigate,
  resetLastScreenResult,
  screenStocks,
  startScreenTask,
} = vi.hoisted(() => {
  let lastScreenResult: unknown = null;
  const screenStocks = vi.fn();
  const startScreenTask = vi.fn(async (payload: unknown) => {
    lastScreenResult = await screenStocks(payload);
    return {
      taskId: 'screen-task-1',
      traceId: 'screen-task-1',
      status: 'pending',
      message: 'AlphaSift \u9009\u80a1\u4efb\u52a1\u5df2\u63d0\u4ea4',
      strategy: 'dual_low',
      market: 'cn',
      maxResults: 3,
    };
  });
  const getScreenTask = vi.fn(async (taskId: string) => {
    void taskId;
    return {
      taskId: 'screen-task-1',
      traceId: 'screen-task-1',
      status: 'completed',
      progress: 100,
      message: '\u4efb\u52a1\u6267\u884c\u5b8c\u6210',
      result: lastScreenResult,
    };
  });
  return {
    enableAlphaSift: vi.fn(),
    getAlphaSiftStatus: vi.fn(),
    getHotspotDetail: vi.fn(),
    getHotspots: vi.fn(),
    getStrategies: vi.fn(),
    getScreenTask,
    navigate: vi.fn(),
    resetLastScreenResult: () => {
      lastScreenResult = null;
    },
    screenStocks,
    startScreenTask,
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

vi.mock('../../api/alphasift', () => ({
  alphasiftApi: {
    enable: () => enableAlphaSift(),
    getStatus: () => getAlphaSiftStatus(),
    getHotspotDetail: (payload: unknown) => getHotspotDetail(payload),
    getHotspots: (payload: unknown) => getHotspots(payload),
    getStrategies: () => getStrategies(),
    getScreenTask: (taskId: string) => getScreenTask(taskId),
    screen: (payload: unknown) => screenStocks(payload),
    startScreen: (payload: unknown) => startScreenTask(payload),
  },
}));

const mockStrategiesResponse = {
  enabled: true,
  strategies: [
    {
      id: 'dual_low',
      name: 'Dual Low',
      title: 'Dual Low',
      description: 'Low valuation strategy',
      category: 'value',
      tag: 'value',
      tags: ['value'],
      marketScope: ['cn'],
    },
  ],
  strategyCount: 1,
};

function createDeferred<T>() {
  let resolve: (value: T) => void = () => {};
  let reject: (reason?: unknown) => void = () => {};
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe('StockScreeningPage', () => {
  beforeEach(() => {
    enableAlphaSift.mockReset();
    getAlphaSiftStatus.mockReset();
    getHotspotDetail.mockReset();
    getHotspots.mockReset();
    getStrategies.mockReset();
    getScreenTask.mockClear();
    navigate.mockReset();
    resetLastScreenResult();
    screenStocks.mockReset();
    startScreenTask.mockClear();
    getStrategies.mockResolvedValue(mockStrategiesResponse);
    getHotspotDetail.mockResolvedValue({
      enabled: true,
      provider: 'akshare',
      topic: 'AI\u7b97\u529b',
      name: 'AI\u7b97\u529b',
      canonicalTopic: '\u7b97\u529b',
      summary: 'AI\u7b97\u529b \u76d8\u4e2d\u53d1\u9175。',
      qualityStatus: 'stale',
      missingFields: ['live_stocks'],
      fallbackUsed: true,
      stale: true,
      staleAgeHours: 2.5,
      sourceErrors: ['akshare timeout'],
      route: [{ title: '\u76d8\u4e2d\u53d1\u9175', description: '\u51fa\u73b0\u5927\u7b14\u4e70\u5165。', source: 'eastmoney_board_change' }],
      stocks: [{
        code: '300000',
        name: '\u4e2d\u9645\u65ed\u521b',
        role: '\u6838\u5fc3\u9f99\u5934',
        hotStockScore: 88,
        source: 'last_good_cache.leader_stocks',
        sourceConfidence: 0.65,
        fallbackUsed: true,
      }],
      stockCount: 1,
    });
    getHotspots.mockResolvedValue({ enabled: true, provider: 'akshare', hotspots: [], hotspotCount: 0 });
    window.sessionStorage.clear();
  });

  it('re-syncs enabled state when AlphaSift availability check fails after config is enabled', async () => {
    getAlphaSiftStatus
      .mockResolvedValueOnce({
        enabled: false,
        available: false,
        installSpecIsDefault: true,
      })
      .mockResolvedValueOnce({
        enabled: true,
        available: false,
        installSpecIsDefault: true,
      });
    enableAlphaSift.mockRejectedValueOnce(new Error('AlphaSift \u9002\u914d\u5c42\u4e0d\u53ef\u7528。\u8bf7\u6267\u884c pip install -r requirements.txt'));

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u672a\u5f00\u542f')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '\u5f00\u542f AlphaSift' }));

    await waitFor(() => expect(getAlphaSiftStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByText('\u9009\u80a1\u672a\u5f00\u542f')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ })).toBeDisabled();
    expect(screen.getByText(/\u9002\u914d\u5c42\u5f53\u524d\u4e0d\u53ef\u7528/)).toBeInTheDocument();
    expect(screen.getByText('AlphaSift \u9002\u914d\u5c42\u4e0d\u53ef\u7528。\u8bf7\u6267\u884c pip install -r requirements.txt')).toBeInTheDocument();
  });

  it('loads AlphaSift hotspot themes on demand', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        providerUsed: 'akshare',
        hotspots: [],
        hotspotCount: 0,
        cacheUsed: true,
        cachedAt: '2026-06-07T08:00:00Z',
      })
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        providerUsed: 'akshare',
        hotspots: [
          {
            topic: 'AI\u7b97\u529b',
            name: 'AI\u7b97\u529b',
            heatScore: 88,
            trendScore: 12,
            persistenceScore: 66,
            changePct: 4.2,
            stage: '\u52a0\u901f\u4e3b\u5347',
            sampleStockCount: 8,
            leaders: ['\u4e2d\u9645\u65ed\u521b', '\u5de5\u4e1a\u5bcc\u8054'],
          },
        ],
        hotspotCount: 1,
      });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: false }));
    expect(getHotspotDetail).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(screen.getByRole('button', { name: /\u5237\u65b0\u70ed\u70b9\u9898\u6750/ }));

    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: true }));
    fireEvent.click(await screen.findByRole('button', { name: /AI\u7b97\u529b/ }));
    await waitFor(() => expect(getHotspotDetail).toHaveBeenCalledWith({ topic: 'AI\u7b97\u529b', provider: 'akshare', refresh: false }));
    await waitFor(() => expect(screen.getAllByText('AI\u7b97\u529b').length).toBeGreaterThan(0));
    expect(screen.getByText('\u5f3a\u52bf\u9886\u5148')).toBeInTheDocument();
    expect(screen.getByText(/\u4e2d\u9645\u65ed\u521b、\u5de5\u4e1a\u5bcc\u8054/)).toBeInTheDocument();
    expect(screen.getByText(/\u8986\u76d6 8 \u80a1/)).toBeInTheDocument();
    expect(await screen.findByText('\u53d1\u9175\u65f6\u95f4\u7ebf')).toBeInTheDocument();
    expect(screen.getByText('\u6807\u51c6\u9898\u6750：\u7b97\u529b')).toBeInTheDocument();
    expect(screen.getByText('\u8d28\u91cf stale')).toBeInTheDocument();
    expect(screen.getByText('\u7f13\u5b58\u56de\u9000 2.5h')).toBeInTheDocument();
    expect(screen.getByText('\u8be6\u60c5\u6570\u636e\u5df2\u964d\u7ea7，\u5c55\u5f00\u67e5\u770b\u539f\u56e0')).toBeInTheDocument();
    expect(screen.getByText(/\u7f3a\u5931\u5b57\u6bb5：live_stocks/)).toBeInTheDocument();
    expect(screen.getByText('\u76d8\u4e2d\u53d1\u9175')).toBeInTheDocument();
    expect(screen.getByText('\u6982\u5ff5\u80a1')).toBeInTheDocument();
    expect(screen.getByText('\u4e2d\u9645\u65ed\u521b')).toBeInTheDocument();
    expect(screen.getByText(/\u6765\u6e90 last_good_cache\.leader_stocks · \u7f6e\u4fe1 65% · \u56de\u9000/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u5206\u6790 \u4e2d\u9645\u65ed\u521b' }));
    expect(navigate).toHaveBeenCalledWith('/', {
      state: {
        stockCode: '300000',
        stockName: '\u4e2d\u9645\u65ed\u521b',
        autoAnalyze: true,
        selectionSource: 'alphasift_hotspot',
      },
    });
  });

  it('localizes backend hotspot no-cache hint on initial load', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'akshare',
      hotspots: [],
      hotspotCount: 0,
      message: 'No cached AlphaSift hotspot snapshot. Click refresh to fetch live hotspots.',
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u6682\u65e0\u7f13\u5b58\u70ed\u70b9\u9898\u6750，\u5c55\u5f00\u540e\u53ef\u70b9\u51fb\u5237\u65b0\u62c9\u53d6\u5b9e\u65f6\u6570\u636e。')).toBeInTheDocument();
    expect(screen.queryByText(/No cached AlphaSift hotspot snapshot/)).not.toBeInTheDocument();
  });

  it('shows backend hotspot empty message before raw source diagnostics', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'DsaEastMoneyHotspotProvider',
      hotspots: [],
      hotspotCount: 0,
      sourceErrors: ['eastmoney_hotspot_unavailable', "RemoteDisconnected('Remote end closed connection without response')"],
      message: '\u70ed\u70b9\u6e90\u8fde\u63a5\u4e2d\u65ad，\u6682\u65e0\u53ef\u7528\u7f13\u5b58。',
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u70ed\u70b9\u6e90\u8fde\u63a5\u4e2d\u65ad，\u6682\u65e0\u53ef\u7528\u7f13\u5b58。')).toBeInTheDocument();
    expect(screen.queryByText(/RemoteDisconnected/)).not.toBeInTheDocument();
  });

  it('prefers merged hotspot route summaries over raw timeline items', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'akshare',
      hotspots: [{ topic: 'AI\u7b97\u529b', name: 'AI\u7b97\u529b', heatScore: 88, stage: '\u52a0\u901f\u4e3b\u5347' }],
      hotspotCount: 1,
    });
    getHotspotDetail.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      topic: 'AI\u7b97\u529b',
      name: 'AI\u7b97\u529b',
      summary: 'AI\u7b97\u529b \u5f53\u524d\u70ed\u70b9\u8be6\u60c5。',
      route: [{ title: 'route-summary', description: 'compact route summary', source: 'news_search' }],
      timeline: [{ title: 'raw-timeline', description: 'full raw timeline text should stay hidden', source: 'raw_news' }],
      stocks: [],
      stockCount: 0,
    });

    render(<StockScreeningPage />);

    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: false }));
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(await screen.findByRole('button', { name: /AI\u7b97\u529b/ }));

    expect(await screen.findByText('route-summary')).toBeInTheDocument();
    expect(screen.getByText('compact route summary')).toBeInTheDocument();
    expect(screen.queryByText('raw-timeline')).not.toBeInTheDocument();
    expect(screen.queryByText('full raw timeline text should stay hidden')).not.toBeInTheDocument();
  });

  it('uses prefetched hotspot details from the hotspot list response', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'akshare',
      hotspots: [{ topic: 'Moly', name: 'Moly', heatScore: 96, stage: 'warming' }],
      hotspotCount: 1,
      details: {
        Moly: {
          enabled: true,
          provider: 'akshare',
          topic: 'Moly',
          name: 'Moly',
          summary: 'Moly event summary',
          route: [{ title: 'prefetched catalyst', description: 'substitution drove the theme', source: 'news_search' }],
          stocks: [{ code: '603799', name: 'Moly Leader', role: 'leader', hotStockScore: 90 }],
          stockCount: 1,
        },
      },
    });

    render(<StockScreeningPage />);

    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: false }));
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Moly/ }));

    expect(await screen.findByText('prefetched catalyst')).toBeInTheDocument();
    expect(screen.getByText('substitution drove the theme')).toBeInTheDocument();
    expect(screen.getByText('Moly Leader')).toBeInTheDocument();
    expect(getHotspotDetail).not.toHaveBeenCalled();
  });

  it('loads selected hotspot detail once when switching themes', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'akshare',
      hotspots: [
        {
          topic: 'AI\u7b97\u529b',
          name: 'AI\u7b97\u529b',
          heatScore: 88,
          stage: '\u52a0\u901f\u4e3b\u5347',
        },
        {
          topic: '\u673a\u5668\u4eba\u6267\u884c\u5668',
          name: '\u673a\u5668\u4eba\u6267\u884c\u5668',
          heatScore: 80,
          stage: '\u8f6e\u52a8\u6269\u6563',
        },
      ],
      hotspotCount: 2,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: false }));
    expect(getHotspotDetail).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(screen.getByRole('button', { name: /AI\u7b97\u529b/ }));
    await waitFor(() => expect(getHotspotDetail).toHaveBeenCalledWith({ topic: 'AI\u7b97\u529b', provider: 'akshare', refresh: false }));
    expect(getHotspotDetail).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /\u673a\u5668\u4eba\u6267\u884c\u5668/ }));

    await waitFor(() =>
      expect(getHotspotDetail).toHaveBeenLastCalledWith({ topic: '\u673a\u5668\u4eba\u6267\u884c\u5668', provider: 'akshare', refresh: false }),
    );
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(getHotspotDetail).toHaveBeenCalledTimes(2);
  });

  it('clears loaded hotspot detail while loading a different theme', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'akshare',
      hotspots: [
        {
          topic: 'AI\u7b97\u529b',
          name: 'AI\u7b97\u529b',
          heatScore: 88,
          stage: '\u52a0\u901f\u4e3b\u5347',
        },
        {
          topic: '\u673a\u5668\u4eba\u6267\u884c\u5668',
          name: '\u673a\u5668\u4eba\u6267\u884c\u5668',
          heatScore: 80,
          stage: '\u8f6e\u52a8\u6269\u6563',
        },
      ],
      hotspotCount: 2,
    });

    const robotDetail = createDeferred<unknown>();
    getHotspotDetail
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        topic: 'AI\u7b97\u529b',
        name: 'AI\u7b97\u529b',
        summary: 'AI\u7b97\u529b \u76d8\u4e2d\u53d1\u9175。',
        route: [{ title: '\u76d8\u4e2d\u53d1\u9175', description: '\u51fa\u73b0\u5927\u7b14\u4e70\u5165。', source: 'eastmoney_board_change' }],
        stocks: [{ code: '300000', name: '\u4e2d\u9645\u65ed\u521b', role: '\u6838\u5fc3\u9f99\u5934', hotStockScore: 88 }],
        stockCount: 1,
      })
      .mockImplementationOnce(({ topic }: { topic: string }) => {
        if (topic === '\u673a\u5668\u4eba\u6267\u884c\u5668') {
          return robotDetail.promise;
        }
        return Promise.reject(new Error(`unexpected topic: ${topic}`));
      });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(await screen.findByRole('button', { name: /AI\u7b97\u529b/ }));
    expect(await screen.findByText('\u76d8\u4e2d\u53d1\u9175')).toBeInTheDocument();
    expect(screen.getByText('\u4e2d\u9645\u65ed\u521b')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /\u673a\u5668\u4eba\u6267\u884c\u5668/ }));

    await waitFor(() =>
      expect(getHotspotDetail).toHaveBeenLastCalledWith({ topic: '\u673a\u5668\u4eba\u6267\u884c\u5668', provider: 'akshare', refresh: false }),
    );
    expect(screen.getAllByText('\u673a\u5668\u4eba\u6267\u884c\u5668').length).toBeGreaterThan(0);
    expect(screen.getByText('\u6b63\u5728\u8bfb\u53d6\u53d1\u9175\u8def\u7ebf\u4e0e\u6982\u5ff5\u80a1...')).toBeInTheDocument();
    expect(screen.queryByText('\u76d8\u4e2d\u53d1\u9175')).not.toBeInTheDocument();
    expect(screen.queryByText('\u4e2d\u9645\u65ed\u521b')).not.toBeInTheDocument();

    await act(async () => {
      robotDetail.resolve({
        enabled: true,
        provider: 'akshare',
        topic: '\u673a\u5668\u4eba\u6267\u884c\u5668',
        name: '\u673a\u5668\u4eba\u6267\u884c\u5668',
        summary: '\u673a\u5668\u4eba\u6267\u884c\u5668 \u7ee7\u7eed\u53d1\u9175。',
        route: [{ title: '\u673a\u5668\u4eba\u53d1\u9175', description: '\u6267\u884c\u5668\u94fe\u6761\u6269\u6563。', source: 'eastmoney_board_change' }],
        stocks: [{ code: '300111', name: '\u673a\u5668\u4eba\u9f99\u5934', role: '\u6838\u5fc3\u9f99\u5934', hotStockScore: 86 }],
        stockCount: 1,
      });
    });

    expect(await screen.findByText('\u673a\u5668\u4eba\u53d1\u9175')).toBeInTheDocument();
    expect(screen.getByText('\u673a\u5668\u4eba\u9f99\u5934')).toBeInTheDocument();
  });

  it('ignores stale hotspot detail responses when switching themes', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots.mockResolvedValueOnce({
      enabled: true,
      provider: 'akshare',
      providerUsed: 'akshare',
      hotspots: [
        {
          topic: 'AI\u7b97\u529b',
          name: 'AI\u7b97\u529b',
          heatScore: 88,
          stage: '\u52a0\u901f\u4e3b\u5347',
        },
        {
          topic: '\u673a\u5668\u4eba\u6267\u884c\u5668',
          name: '\u673a\u5668\u4eba\u6267\u884c\u5668',
          heatScore: 80,
          stage: '\u8f6e\u52a8\u6269\u6563',
        },
      ],
      hotspotCount: 2,
    });

    const aiDetail = createDeferred<unknown>();
    const robotDetail = createDeferred<unknown>();
    getHotspotDetail.mockImplementation(({ topic }: { topic: string }) => {
      if (topic === 'AI\u7b97\u529b') {
        return aiDetail.promise;
      }
      if (topic === '\u673a\u5668\u4eba\u6267\u884c\u5668') {
        return robotDetail.promise;
      }
      return Promise.reject(new Error(`unexpected topic: ${topic}`));
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(await screen.findByRole('button', { name: /AI\u7b97\u529b/ }));
    await waitFor(() => expect(getHotspotDetail).toHaveBeenCalledWith({ topic: 'AI\u7b97\u529b', provider: 'akshare', refresh: false }));

    fireEvent.click(screen.getByRole('button', { name: /\u673a\u5668\u4eba\u6267\u884c\u5668/ }));

    await waitFor(() =>
      expect(getHotspotDetail).toHaveBeenLastCalledWith({ topic: '\u673a\u5668\u4eba\u6267\u884c\u5668', provider: 'akshare', refresh: false }),
    );
    await act(async () => {
      robotDetail.resolve({
        enabled: true,
        provider: 'akshare',
        topic: '\u673a\u5668\u4eba\u6267\u884c\u5668',
        name: '\u673a\u5668\u4eba\u6267\u884c\u5668',
        summary: '\u673a\u5668\u4eba\u6267\u884c\u5668 \u7ee7\u7eed\u53d1\u9175。',
        route: [{ title: '\u673a\u5668\u4eba\u53d1\u9175', description: '\u6267\u884c\u5668\u94fe\u6761\u6269\u6563。', source: 'eastmoney_board_change' }],
        stocks: [{ code: '300111', name: '\u673a\u5668\u4eba\u9f99\u5934', role: '\u6838\u5fc3\u9f99\u5934', hotStockScore: 86 }],
        stockCount: 1,
      });
    });

    expect(await screen.findByText('\u673a\u5668\u4eba\u53d1\u9175')).toBeInTheDocument();

    await act(async () => {
      aiDetail.resolve({
        enabled: true,
        provider: 'akshare',
        topic: 'AI\u7b97\u529b',
        name: 'AI\u7b97\u529b',
        summary: 'AI\u7b97\u529b \u65e7\u54cd\u5e94。',
        route: [{ title: 'AI\u65e7\u53d1\u9175', description: '\u65e7\u8bf7\u6c42\u665a\u5230。', source: 'eastmoney_board_change' }],
        stocks: [{ code: '300000', name: '\u4e2d\u9645\u65ed\u521b', role: '\u6838\u5fc3\u9f99\u5934', hotStockScore: 88 }],
        stockCount: 1,
      });
    });

    expect(screen.getByText('\u673a\u5668\u4eba\u53d1\u9175')).toBeInTheDocument();
    expect(screen.getByText('\u673a\u5668\u4eba\u9f99\u5934')).toBeInTheDocument();
    expect(screen.queryByText('AI\u65e7\u53d1\u9175')).not.toBeInTheDocument();
    expect(screen.queryByText('\u4e2d\u9645\u65ed\u521b')).not.toBeInTheDocument();
  });

  it('reloads selected hotspot detail when refreshed themes keep the same topic', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        providerUsed: 'akshare',
        hotspots: [
          {
            topic: 'AI\u7b97\u529b',
            name: 'AI\u7b97\u529b',
            heatScore: 88,
            stage: '\u52a0\u901f\u4e3b\u5347',
          },
          {
            topic: '\u673a\u5668\u4eba\u6267\u884c\u5668',
            name: '\u673a\u5668\u4eba\u6267\u884c\u5668',
            heatScore: 80,
            stage: '\u8f6e\u52a8\u6269\u6563',
          },
        ],
        hotspotCount: 2,
      })
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        providerUsed: 'akshare',
        hotspots: [
          {
            topic: 'AI\u7b97\u529b',
            name: 'AI\u7b97\u529b',
            heatScore: 91,
            stage: '\u9ad8\u4f4d\u53d1\u9175',
          },
        ],
        hotspotCount: 1,
      });
    getHotspotDetail
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        topic: 'AI\u7b97\u529b',
        name: 'AI\u7b97\u529b',
        summary: 'AI\u7b97\u529b \u76d8\u4e2d\u53d1\u9175。',
        route: [{ title: '\u76d8\u4e2d\u53d1\u9175', description: '\u51fa\u73b0\u5927\u7b14\u4e70\u5165。', source: 'eastmoney_board_change' }],
        stocks: [{ code: '300000', name: '\u4e2d\u9645\u65ed\u521b', role: '\u6838\u5fc3\u9f99\u5934', hotStockScore: 88 }],
        stockCount: 1,
      })
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        topic: 'AI\u7b97\u529b',
        name: 'AI\u7b97\u529b',
        summary: 'AI\u7b97\u529b \u5237\u65b0\u540e\u7ee7\u7eed\u53d1\u9175。',
        route: [{ title: '\u5237\u65b0\u53d1\u9175', description: '\u5237\u65b0\u540e\u4ecd\u5728\u699c\u5185。', source: 'eastmoney_board_change' }],
        stocks: [{ code: '601138', name: '\u5de5\u4e1a\u5bcc\u8054', role: '\u6838\u5fc3\u9f99\u5934', hotStockScore: 90 }],
        stockCount: 1,
      });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    fireEvent.click(await screen.findByRole('button', { name: /AI\u7b97\u529b/ }));
    await waitFor(() => expect(getHotspotDetail).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /\u5237\u65b0\u70ed\u70b9\u9898\u6750/ }));

    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: true }));
    await waitFor(() => expect(getHotspotDetail).toHaveBeenCalledTimes(2));
    expect(getHotspotDetail).toHaveBeenLastCalledWith({ topic: 'AI\u7b97\u529b', provider: 'akshare', refresh: true });
    expect(await screen.findByText('\u5237\u65b0\u53d1\u9175')).toBeInTheDocument();
    expect(screen.getByText('\u5de5\u4e1a\u5bcc\u8054')).toBeInTheDocument();
  });

  it('keeps existing hotspot cards when manual refresh fails', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    getHotspots
      .mockResolvedValueOnce({
        enabled: true,
        provider: 'akshare',
        providerUsed: 'akshare',
        hotspots: [
          {
            topic: 'AI\u7b97\u529b',
            name: 'AI\u7b97\u529b',
            heatScore: 88,
            trendScore: 12,
            persistenceScore: 66,
            changePct: 4.2,
            stage: '\u52a0\u901f\u4e3b\u5347',
            sampleStockCount: 8,
            leaders: ['\u4e2d\u9645\u65ed\u521b', '\u5de5\u4e1a\u5bcc\u8054'],
          },
        ],
        hotspotCount: 1,
      })
      .mockRejectedValueOnce(new Error('manual refresh failed'));

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u5c55\u5f00\u70ed\u70b9\u9898\u6750/ }));
    expect(await screen.findByText('\u5f3a\u52bf\u9886\u5148')).toBeInTheDocument();
    expect(screen.getByText(/\u4e2d\u9645\u65ed\u521b、\u5de5\u4e1a\u5bcc\u8054/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /\u5237\u65b0\u70ed\u70b9\u9898\u6750/ }));

    await waitFor(() => expect(getHotspots).toHaveBeenCalledWith({ provider: 'akshare', top: 12, refresh: true }));
    expect(await screen.findByText(/manual refresh failed/)).toBeInTheDocument();
    expect(screen.getByText('\u5f3a\u52bf\u9886\u5148')).toBeInTheDocument();
    expect(screen.getByText(/\u4e2d\u9645\u65ed\u521b、\u5de5\u4e1a\u5bcc\u8054/)).toBeInTheDocument();
    expect(screen.queryByText(/\u70b9\u51fb\u5237\u65b0\u540e\u4f1a\u62c9\u53d6\u70ed\u70b9\u6982\u5ff5/)).not.toBeInTheDocument();
  });

  it('shows input strategy when strategy is not in preset list', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValue({
      enabled: true,
      candidates: [],
      candidateCount: 0,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('\u7b56\u7565\u53c2\u6570'), {
      target: { value: 'custom_strategy_alpha' },
    });

    expect(screen.getByDisplayValue('custom_strategy_alpha')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));
    await waitFor(() => expect(screenStocks).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText(/\u81ea\u5b9a\u4e49\u7b56\u7565 \(custom_strategy_alpha\)/)).toBeInTheDocument());
  });

  it('uses supported AlphaSift strategy ids and cn market', async () => {
    getStrategies.mockResolvedValueOnce({
      enabled: true,
      strategies: [
        { id: 'balanced_alpha', name: '\u5e73\u8861\u9009\u80a1', description: 'desc', category: '\u6846\u67b6' },
        { id: 'capital_heat', name: '\u8d44\u91d1\u70ed\u5ea6', description: 'desc', category: '\u52a8\u91cf' },
        { id: 'dual_low', name: '\u53cc\u4f4e', description: 'desc', category: '\u4ef7\u503c' },
        { id: 'oversold_reversal', name: '\u8d85\u8dcc', description: 'desc', category: '\u53cd\u8f6c' },
        { id: 'shrink_pullback', name: '\u7f29\u91cf\u56de\u8e29', description: 'desc', category: '\u8d8b\u52bf' },
      ],
      strategyCount: 5,
    });
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValue({
      enabled: true,
      candidates: [],
      candidateCount: 0,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();

    const marketSelect = screen.getByLabelText('\u5e02\u573a') as HTMLSelectElement;
    expect(Array.from(marketSelect.options).map((option) => option.value)).toEqual(['cn']);

    [
      ['\u5e73\u8861\u9009\u80a1', 'balanced_alpha'],
      ['\u8d44\u91d1\u70ed\u5ea6', 'capital_heat'],
      ['\u8d85\u8dcc', 'oversold_reversal'],
      ['\u7f29\u91cf\u56de\u8e29', 'shrink_pullback'],
    ].forEach(([label, id]) => {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }));
      expect(screen.getByDisplayValue(id)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));
    await waitFor(() => expect(screenStocks).toHaveBeenCalledTimes(1));
    expect(screenStocks).toHaveBeenCalledWith({
      market: 'cn',
      strategy: 'shrink_pullback',
      maxResults: 3,
    });
  });

  it('clears previous screening candidates when strategy changes', async () => {
    getStrategies.mockResolvedValueOnce({
      enabled: true,
      strategies: [
        { id: 'dual_low', name: '\u53cc\u4f4e\u9009\u80a1', description: 'desc', category: '\u4ef7\u503c' },
        { id: 'capital_heat', name: '\u8d44\u91d1\u70ed\u5ea6', description: 'desc', category: '\u52a8\u91cf' },
      ],
      strategyCount: 2,
    });
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '000001',
          name: '\u65e7\u7b56\u7565\u80a1\u7968',
          score: 88.5,
          reason: 'old result',
          raw: {},
        },
      ],
      candidateCount: 1,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));

    expect(await screen.findByText('\u65e7\u7b56\u7565\u80a1\u7968')).toBeInTheDocument();
    expect(screen.getByText('\u9009\u80a1\u5b8c\u6210')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /\u8d44\u91d1\u70ed\u5ea6/ }));

    expect(screen.queryByText('\u65e7\u7b56\u7565\u80a1\u7968')).not.toBeInTheDocument();
    expect(screen.getByText('\u7b49\u5f85\u8fd0\u884c')).toBeInTheDocument();
    expect(screen.getByText('\u5f53\u524d\u7b56\u7565：\u8d44\u91d1\u70ed\u5ea6 · A \u80a1')).toBeInTheDocument();
  });

  it('restores an in-flight screening task after remounting the page', async () => {
    getAlphaSiftStatus.mockResolvedValue({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '000001',
          name: '\u6062\u590d\u540e\u7684\u5019\u9009',
          score: 88.5,
          reason: 'restored result',
          raw: {},
        },
      ],
      candidateCount: 1,
    });
    getScreenTask
      .mockResolvedValueOnce({
        taskId: 'screen-task-1',
        traceId: 'screen-task-1',
        status: 'processing',
        progress: 35,
        message: '\u6b63\u5728\u6267\u884c AlphaSift \u9009\u80a1',
        result: null,
      })
      .mockResolvedValueOnce({
        taskId: 'screen-task-1',
        traceId: 'screen-task-1',
        status: 'completed',
        progress: 100,
        message: '\u4efb\u52a1\u6267\u884c\u5b8c\u6210',
        result: {
          enabled: true,
          candidates: [
            {
              rank: 1,
              code: '000001',
              name: '\u6062\u590d\u540e\u7684\u5019\u9009',
              score: 88.5,
              reason: 'restored result',
              raw: {},
            },
          ],
          candidateCount: 1,
        },
      });

    const firstRender = render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));

    expect(await screen.findByText('\u9009\u80a1\u8fd0\u884c\u4e2d')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('dsa.alphasift.activeScreenTask.v1')).toContain('screen-task-1');

    firstRender.unmount();
    render(<StockScreeningPage />);

    expect(await screen.findByText('\u6062\u590d\u540e\u7684\u5019\u9009')).toBeInTheDocument();
    expect(screen.getByText('\u9009\u80a1\u5b8c\u6210')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('dsa.alphasift.activeScreenTask.v1')).toBeNull();
  });

  it('keeps a restored screening task recoverable when status polling times out', async () => {
    getAlphaSiftStatus.mockResolvedValue({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    window.sessionStorage.setItem('dsa.alphasift.activeScreenTask.v1', JSON.stringify({
      taskId: 'screen-task-1',
      market: 'cn',
      strategy: 'dual_low',
      maxResults: 3,
    }));
    getScreenTask.mockRejectedValueOnce(Object.assign(new Error('timeout of 30000ms exceeded'), {
      code: 'ECONNABORTED',
    }));

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u4efb\u52a1\u8fd0\u884c\u4e2d')).toBeInTheDocument();
    await waitFor(() => expect(getScreenTask).toHaveBeenCalledTimes(1));
    expect(screen.getByText('\u9009\u80a1\u8fd0\u884c\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('\u9009\u80a1\u4efb\u52a1\u4ecd\u5728\u540e\u53f0\u8fd0\u884c，\u72b6\u6001\u8f6e\u8be2\u6682\u65f6\u8d85\u65f6，\u5c06\u81ea\u52a8\u91cd\u8bd5。')).toBeInTheDocument();
    expect(screen.queryByText(/\u8fde\u63a5\u4e0a\u6e38\u670d\u52a1\u8d85\u65f6/)).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem('dsa.alphasift.activeScreenTask.v1')).toContain('screen-task-1');
  });

  it('surfaces AlphaSift LLM fallback instead of showing empty LLM fields as normal', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '000001',
          name: '\u5e73\u5b89\u94f6\u884c',
          score: 88.5,
          reason: '\u672c\u5730\u540e\u7f6e\u8bc4\u5206: value_quality',
          amount: 1042000000,
          factorScores: {
            value: 87.44,
            liquidity: 93.33,
          },
          raw: {},
        },
      ],
      candidateCount: 1,
      snapshotCount: 5193,
      afterFilterCount: 20,
      llmRanked: false,
      warnings: ['LLM ranking failed, falling back to screen_score: Missing gemini_api_key'],
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));

    expect(await screen.findByText('LLM \u5df2\u964d\u7ea7')).toBeInTheDocument();
    expect(screen.getByText(/\u7f3a\u5c11\u53ef\u7528 LLM API Key/)).toBeInTheDocument();
    expect(screen.queryByText(/Missing gemini_api_key/)).not.toBeInTheDocument();
    expect(screen.getByText('\u672a\u91cd\u6392')).toBeInTheDocument();
    expect(screen.getByText('\u672c\u6b21 LLM \u91cd\u6392\u5931\u8d25\u6216\u672a\u8fd4\u56de\u5224\u65ad，\u5f53\u524d\u5c55\u793a\u7684\u662f\u672c\u5730\u56e0\u5b50\u8bc4\u5206\u7ed3\u679c。')).toBeInTheDocument();
    expect(screen.getByText('LLM \u5143\u6570\u636e\u672a\u8fd4\u56de')).toBeInTheDocument();
    expect(screen.getAllByText('\u672a\u8fd4\u56de（LLM \u5df2\u964d\u7ea7）')).toHaveLength(2);
  });

  it('deduplicates AlphaSift snapshot fallback warnings and source errors', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '601919',
          name: '\u4e2d\u8fdc\u6d77\u63a7',
          score: 82.88,
          llmScore: 82,
          riskLevel: 'low',
          raw: {},
        },
      ],
      candidateCount: 1,
      llmRanked: true,
      warnings: ['Snapshot source fallback: tushare: tushare trade_cal returned no open trading days'],
      sourceErrors: ['tushare: tushare trade_cal returned no open trading days'],
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));

    expect(await screen.findByText('AlphaSift \u63d0\u793a')).toBeInTheDocument();
    expect(screen.getAllByText('\u6570\u636e\u6e90\u964d\u7ea7：tushare（\u4ea4\u6613\u65e5\u5386\u6682\u65e0\u53ef\u7528\u5f00\u5e02\u65e5）')).toHaveLength(1);
    expect(screen.queryByText(/trade_cal returned no open trading days/)).not.toBeInTheDocument();
  });

  it('sanitizes long AlphaSift source diagnostics and keeps the alert constrained', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '600016',
          name: '\u6c11\u751f\u94f6\u884c',
          score: 80.12,
          raw: {},
        },
      ],
      candidateCount: 1,
      llmRanked: true,
      warnings: [
        "Snapshot source fallback: efinance: HTTPConnectionPool(host='push2.eastmoney.com', port=80): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=200&po=1&fields=f12%2Cf14%2Cf2%2Cf3 (Caused by ProtocolError('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')))",
        "Snapshot source fallback: akshare_em: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))",
      ],
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));

    const efinanceWarning = await screen.findByText('\u6570\u636e\u6e90\u964d\u7ea7：efinance（\u7f51\u7edc\u8fde\u63a5\u4e2d\u65ad）');
    const alert = efinanceWarning.closest('[role="alert"]');
    expect(alert).toHaveClass('max-w-full');
    expect(efinanceWarning).toBeInTheDocument();
    expect(screen.getByText('\u6570\u636e\u6e90\u964d\u7ea7：akshare_em（\u7f51\u7edc\u8fde\u63a5\u4e2d\u65ad）')).toBeInTheDocument();
    expect(screen.queryByText(/HTTPConnectionPool/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\/api\/qt\/clist\/get/)).not.toBeInTheDocument();
    expect(screen.queryByText(/RemoteDisconnected/)).not.toBeInTheDocument();
  });

  it('shows DSA enrichment summary, news, and enrichment metadata', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '600519',
          name: '\u8d35\u5dde\u8305\u53f0',
          score: 91.2,
          reason: 'AlphaSift pick',
          dsaAnalysisSummary: 'DSA\u884c\u60c5：\u73b0\u4ef7 1688，\u6da8\u8dcc\u5e45 1.2%；DSA\u65b0\u95fb：\u8d35\u5dde\u8305\u53f0\u6700\u65b0\u516c\u544a',
          dsaNews: [{ title: '\u8d35\u5dde\u8305\u53f0\u6700\u65b0\u516c\u544a', source: '\u6d4b\u8bd5\u6e90' }],
          dsaContext: {
            enriched: true,
            warnings: ['stock_news_unavailable'],
          },
          raw: {},
        },
      ],
      candidateCount: 1,
      dsaEnrichment: {
        enabled: true,
        requestedCount: 1,
        enrichedCount: 1,
      },
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('\u9009\u80a1\u5df2\u5f00\u542f')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /\u8fd0\u884c\u9009\u80a1/ }));

    expect(await screen.findByText('DSA\u589e\u5f3a：1 / 1')).toBeInTheDocument();

    expect(screen.getByText('DSA \u589e\u5f3a\u6458\u8981')).toBeInTheDocument();
    expect(screen.getByText(/DSA\u884c\u60c5：\u73b0\u4ef7 1688/)).toBeInTheDocument();
    expect(screen.getByText('DSA \u65b0\u95fb')).toBeInTheDocument();
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0\u6700\u65b0\u516c\u544a')).toBeInTheDocument();
    expect(screen.getByText('DSA \u589e\u5f3a\u63d0\u793a')).toBeInTheDocument();
    expect(screen.getByText('stock_news_unavailable')).toBeInTheDocument();
  });
});
