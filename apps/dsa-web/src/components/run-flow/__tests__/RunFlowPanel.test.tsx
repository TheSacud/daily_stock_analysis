import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi } from '../../../api/analysis';
import { historyApi } from '../../../api/history';
import type { RunFlowSnapshot } from '../../../types/runFlow';
import { RunFlowPanel } from '../RunFlowPanel';

vi.mock('../../../api/analysis', () => ({
  analysisApi: {
    getTaskFlow: vi.fn(),
    getTaskStreamUrl: vi.fn(() => 'http://localhost/api/v1/analysis/tasks/stream'),
  },
}));

vi.mock('../../../api/history', () => ({
  historyApi: {
    getRecordFlow: vi.fn(),
  },
}));

const snapshot: RunFlowSnapshot = {
  taskId: 'task-1',
  traceId: 'trace-1',
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  status: 'degraded',
  generatedAt: '2026-06-08T08:00:00Z',
  summary: {
    elapsedMs: 3250,
    failedAttempts: 1,
    fallbackCount: 1,
    model: 'DeepSeek',
    dataSourceCount: 2,
    eventCount: 3,
  },
  lanes: [
    { id: 'entry', label: '\u5165\u53e3', order: 1 },
    { id: 'data_source', label: '\u6570\u636e\u6765\u6e90', order: 2 },
    { id: 'analysis', label: '\u5206\u6790\u5f15\u64ce', order: 3 },
    { id: 'artifact', label: '\u4ea7\u7269', order: 4 },
  ],
  nodes: [
    {
      id: 'request',
      lane: 'entry',
      kind: 'entry',
      label: '\u7528\u6237\u8bf7\u6c42',
      status: 'success',
      message: '\u4efb\u52a1\u8bf7\u6c42\u5df2\u521b\u5efa',
    },
    {
      id: 'news',
      lane: 'data_source',
      kind: 'data_source',
      label: '\u65b0\u95fb\u8206\u60c5',
      provider: 'AkShare',
      status: 'fallback',
      durationMs: 1200,
      attempts: 2,
      recordCount: 8,
      message: '\u4e3b\u6570\u636e\u6e90\u5931\u8d25\u540e\u964d\u7ea7\u6210\u529f',
      metadata: {
        fallbackFrom: 'Tushare',
        fallbackTo: 'AkShare',
      },
    },
    {
      id: 'llm',
      lane: 'analysis',
      kind: 'model',
      label: 'LLM \u751f\u6210',
      provider: 'DeepSeek',
      status: 'success',
      durationMs: 1800,
    },
  ],
  edges: [
    {
      id: 'request-news',
      from: 'request',
      to: 'news',
      kind: 'control',
      status: 'success',
      label: '\u8c03\u5ea6',
    },
    {
      id: 'news-llm',
      from: 'news',
      to: 'llm',
      kind: 'fallback',
      status: 'fallback',
      label: '\u964d\u7ea7\u8f93\u5165',
    },
  ],
  events: [
    {
      id: 'evt-1',
      timestamp: '2026-06-08T08:00:01Z',
      severity: 'info',
      type: 'task_created',
      nodeId: 'request',
      title: '\u4efb\u52a1\u521b\u5efa',
    },
    {
      id: 'evt-2',
      timestamp: '2026-06-08T08:00:02Z',
      severity: 'warning',
      type: 'provider_fallback',
      nodeId: 'news',
      title: '\u65b0\u95fb\u6570\u636e\u6e90\u964d\u7ea7',
      message: '\u91cd\u8bd5\u540e\u5207\u6362\u6570\u636e\u6e90',
    },
  ],
};

const providerAttemptSnapshot: RunFlowSnapshot = {
  ...snapshot,
  nodes: [
    {
      id: 'task_queue',
      lane: 'entry',
      kind: 'queue',
      label: '\u4efb\u52a1\u961f\u5217',
      status: 'success',
    },
    {
      id: 'provider_news_search_tavily_1',
      lane: 'data_source',
      kind: 'data_source',
      label: '\u65b0\u95fb\u8206\u60c5 · Tavily',
      provider: 'Tavily',
      status: 'failed',
      durationMs: 1200,
      metadata: { data_type: 'news_search', attempt: 1 },
    },
    {
      id: 'provider_news_search_searxng_2',
      lane: 'data_source',
      kind: 'data_source',
      label: '\u65b0\u95fb\u8206\u60c5 · SearXNG',
      provider: 'SearXNG',
      status: 'success',
      durationMs: 800,
      recordCount: 6,
      metadata: { data_type: 'news_search', attempt: 2 },
    },
    {
      id: 'context_pack',
      lane: 'analysis',
      kind: 'analysis',
      label: 'ContextPack',
      status: 'success',
    },
  ],
  edges: [
    {
      id: 'queue-news-1',
      from: 'task_queue',
      to: 'provider_news_search_tavily_1',
      kind: 'control',
      status: 'failed',
    },
    {
      id: 'news-1-news-2',
      from: 'provider_news_search_tavily_1',
      to: 'provider_news_search_searxng_2',
      kind: 'fallback',
      status: 'success',
    },
    {
      id: 'news-context',
      from: 'provider_news_search_searxng_2',
      to: 'context_pack',
      kind: 'data',
      status: 'success',
    },
  ],
  events: [
    {
      id: 'evt-news-1',
      timestamp: '2026-06-08T08:00:02Z',
      severity: 'warning',
      type: 'provider_run',
      nodeId: 'provider_news_search_tavily_1',
      title: '\u65b0\u95fb\u8206\u60c5\u5931\u8d25',
    },
  ],
};

const contextBlockSnapshot: RunFlowSnapshot = {
  ...snapshot,
  status: 'degraded',
  nodes: [
    {
      id: 'context_block_news',
      lane: 'data_source',
      kind: 'data_source',
      label: '\u65b0\u95fb',
      status: 'success',
      recordCount: 6,
      metadata: { block_key: 'news' },
    },
    {
      id: 'context_block_fundamental',
      lane: 'data_source',
      kind: 'data_source',
      label: '\u57fa\u672c\u9762',
      status: 'degraded',
      metadata: { block_key: 'fundamental' },
    },
    {
      id: 'context_pack',
      lane: 'analysis',
      kind: 'analysis',
      label: 'ContextPack',
      status: 'degraded',
    },
  ],
  edges: [
    {
      id: 'news-context',
      from: 'context_block_news',
      to: 'context_pack',
      kind: 'data',
      status: 'success',
    },
    {
      id: 'fundamental-context',
      from: 'context_block_fundamental',
      to: 'context_pack',
      kind: 'data',
      status: 'degraded',
    },
  ],
  events: [],
};

describe('RunFlowPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state while the snapshot request is pending', () => {
    vi.mocked(analysisApi.getTaskFlow).mockReturnValue(new Promise(() => undefined));

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);

    expect(screen.getByTestId('run-flow-panel-loading')).toBeInTheDocument();
    expect(screen.getByText('\u6b63\u5728\u52a0\u8f7d\u8fd0\u884c\u6d41')).toBeInTheDocument();
  });

  it('renders an error state and reload action when the request fails', async () => {
    vi.mocked(analysisApi.getTaskFlow).mockRejectedValue({
      response: {
        status: 404,
        data: { message: '\u8fd0\u884c\u6d41\u4e0d\u5b58\u5728' },
      },
    });

    render(<RunFlowPanel source={{ type: 'task', taskId: 'missing-task' }} />);

    expect(await screen.findByTestId('run-flow-panel-error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u91cd\u65b0\u52a0\u8f7d' })).toBeInTheDocument();
  });

  it('renders an empty snapshot state when there are no nodes or events', async () => {
    vi.mocked(historyApi.getRecordFlow).mockResolvedValue({
      ...snapshot,
      nodes: [],
      edges: [],
      events: [],
      summary: { ...snapshot.summary, eventCount: 0 },
    });

    render(<RunFlowPanel source={{ type: 'history', recordId: 1 }} />);

    expect(await screen.findByText('\u6682\u65e0\u8fd0\u884c\u6d41\u7ec6\u8282')).toBeInTheDocument();
    expect(historyApi.getRecordFlow).toHaveBeenCalledWith(1);
  });

  it('renders a successful graph, event stream, and selectable node details', async () => {
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(snapshot);

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} title="\u8d35\u5dde\u8305\u53f0\u8fd0\u884c\u6d41" />);

    expect(await screen.findByTestId('run-flow-panel')).toBeInTheDocument();
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0\u8fd0\u884c\u6d41')).toBeInTheDocument();
    expect(screen.getByTestId('run-flow-layout')).toHaveClass('xl:grid-cols-[minmax(0,1fr)_19.25rem]');
    expect(screen.getByTestId('run-flow-events-column')).toHaveClass('xl:max-h-[calc(100vh-18rem)]');
    expect(screen.getByTestId('run-flow-graph')).toBeInTheDocument();
    expect(screen.getByTestId('run-flow-events')).toBeInTheDocument();
    expect(await screen.findByTestId('run-flow-node-details')).toHaveTextContent('\u65b0\u95fb\u8206\u60c5');

    fireEvent.click(screen.getByRole('button', { name: 'LLM \u751f\u6210 \u8282\u70b9，\u72b6\u6001 \u6210\u529f' }));

    expect(screen.getByTestId('run-flow-node-details')).toHaveTextContent('LLM \u751f\u6210');
    expect(screen.getByTestId('run-flow-node-details')).toHaveTextContent('DeepSeek');

    fireEvent.click(screen.getByRole('button', { name: '\u65b0\u95fb\u8206\u60c5 \u8282\u70b9，\u72b6\u6001 \u964d\u7ea7\u56de\u9000' }));

    expect(screen.getByTestId('run-flow-node-details')).toHaveTextContent('fallbackFrom');
    expect(screen.getByTestId('run-flow-node-details')).toHaveTextContent('Tushare');
    expect(screen.getByTestId('run-flow-node-details')).toHaveTextContent('fallbackTo');
    expect(screen.getByTestId('run-flow-node-details')).toHaveTextContent('AkShare');
  });

  it('shows default node details without selecting the graph or hiding unrelated edge labels', async () => {
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue({
      ...snapshot,
      nodes: [
        ...snapshot.nodes,
        {
          id: 'artifact',
          lane: 'artifact',
          kind: 'artifact',
          label: '\u4fdd\u5b58\u62a5\u544a',
          status: 'success',
        },
      ],
      edges: [
        ...snapshot.edges,
        {
          id: 'llm-artifact',
          from: 'llm',
          to: 'artifact',
          kind: 'data',
          status: 'success',
          label: '\u4fdd\u5b58',
        },
      ],
    });

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);

    expect(await screen.findByTestId('run-flow-node-details')).toHaveTextContent('\u65b0\u95fb\u8206\u60c5');
    expect(screen.getByText('\u4fdd\u5b58')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u65b0\u95fb\u8206\u60c5 \u8282\u70b9，\u72b6\u6001 \u964d\u7ea7\u56de\u9000' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('expands provider attempt groups from node details', async () => {
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(providerAttemptSnapshot);

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);

    expect(await screen.findByTestId('run-flow-node-topology_data_news_search')).toBeInTheDocument();
    expect(screen.queryByTestId('run-flow-node-provider_news_search_tavily_1')).not.toBeInTheDocument();
    expect(await screen.findByTestId('run-flow-node-details')).toHaveTextContent('\u8fd0\u884c\u5c1d\u8bd5');

    fireEvent.click(screen.getByRole('button', { name: '\u5c55\u5f00\u5c1d\u8bd5' }));

    expect(await screen.findByTestId('run-flow-node-provider_news_search_tavily_1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u6536\u8d77\u5c1d\u8bd5' })).toBeInTheDocument();
  });

  it('renders TickFlow realtime fallback attempts through generic provider groups', async () => {
    const tickFlowProviderAttemptSnapshot: RunFlowSnapshot = {
      ...snapshot,
      nodes: [
        {
          id: 'task_queue',
          lane: 'entry',
          kind: 'queue',
          label: 'Task queue',
          status: 'success',
        },
        {
          id: 'provider_realtime_quote_tickflowfetcher_1',
          lane: 'data_source',
          kind: 'data_source',
          label: '\u5b9e\u65f6\u884c\u60c5 · TickFlowFetcher',
          provider: 'TickFlowFetcher',
          status: 'failed',
          durationMs: 892,
          metadata: { data_type: 'realtime_quote', attempt: 1 },
        },
        {
          id: 'provider_realtime_quote_aksharefetcher_2',
          lane: 'data_source',
          kind: 'data_source',
          label: '\u5b9e\u65f6\u884c\u60c5 · AkshareFetcher',
          provider: 'AkshareFetcher',
          status: 'success',
          durationMs: 8700,
          recordCount: 1,
          metadata: { data_type: 'realtime_quote', attempt: 2 },
        },
        {
          id: 'context_pack',
          lane: 'analysis',
          kind: 'analysis',
          label: 'ContextPack',
          status: 'success',
        },
      ],
      edges: [
        {
          id: 'queue-quote-1',
          from: 'task_queue',
          to: 'provider_realtime_quote_tickflowfetcher_1',
          kind: 'control',
          status: 'failed',
        },
        {
          id: 'quote-1-quote-2',
          from: 'provider_realtime_quote_tickflowfetcher_1',
          to: 'provider_realtime_quote_aksharefetcher_2',
          kind: 'fallback',
          status: 'success',
        },
        {
          id: 'quote-context',
          from: 'provider_realtime_quote_aksharefetcher_2',
          to: 'context_pack',
          kind: 'data',
          status: 'success',
        },
      ],
      events: [],
    };

    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(tickFlowProviderAttemptSnapshot);

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);

    const group = await screen.findByTestId('run-flow-node-topology_data_realtime_quote');
    expect(group).toHaveTextContent('TickFlowFetcher -> AkshareFetcher');
    expect(screen.queryByTestId('run-flow-node-provider_realtime_quote_tickflowfetcher_1')).not.toBeInTheDocument();

    const details = await screen.findByTestId('run-flow-node-details');
    expect(details).toHaveTextContent('TickFlowFetcher -> AkshareFetcher');
    expect(details).toHaveTextContent('TickFlowFetcher');
    expect(details).toHaveTextContent('AkshareFetcher');

    fireEvent.click(screen.getByTestId('run-flow-node-topology_data_realtime_quote-toggle'));

    expect(await screen.findByTestId('run-flow-node-provider_realtime_quote_tickflowfetcher_1')).toBeInTheDocument();
    expect(await screen.findByTestId('run-flow-node-provider_realtime_quote_aksharefetcher_2')).toBeInTheDocument();
    expect(screen.getByTestId('run-flow-node-provider_realtime_quote_tickflowfetcher_1')).toHaveTextContent('TickFlowFetcher');
    expect(screen.getByTestId('run-flow-node-provider_realtime_quote_aksharefetcher_2')).toHaveTextContent('AkshareFetcher');
  });
  it('hides topology summary metadata from aggregated node details', async () => {
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(providerAttemptSnapshot);

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);

    const details = await screen.findByTestId('run-flow-node-details');

    expect(details).toHaveTextContent('\u8fd0\u884c\u5c1d\u8bd5');
    expect(details).not.toHaveTextContent('data_type');
    expect(details).not.toHaveTextContent('provider_chain');
    expect(details).not.toHaveTextContent('success_count');
    expect(details).not.toHaveTextContent('failed_count');
    expect(details).not.toHaveTextContent('fallback_count');
    expect(details).not.toHaveTextContent('retry_count');
  });

  it('hides context-pack topology counts from raw metadata details', async () => {
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(contextBlockSnapshot);

    render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);

    const details = await screen.findByTestId('run-flow-node-details');

    expect(details).toHaveTextContent('ContextPack');
    expect(details).toHaveTextContent('\u4e0a\u4e0b\u6587\u8f93\u5165');
    expect(details).toHaveTextContent('\u65b0\u95fb');
    expect(details).toHaveTextContent('\u57fa\u672c\u9762');
    expect(details).not.toHaveTextContent('context_status_counts');
  });

  it('does not update state after a pending request is cleaned up', async () => {
    let resolveSnapshot: (value: RunFlowSnapshot) => void = () => undefined;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.mocked(analysisApi.getTaskFlow).mockReturnValue(new Promise((resolve) => {
      resolveSnapshot = resolve;
    }));

    try {
      const { unmount } = render(<RunFlowPanel source={{ type: 'task', taskId: 'task-1' }} />);
      unmount();

      await act(async () => {
        resolveSnapshot(snapshot);
      });

      expect(analysisApi.getTaskFlow).toHaveBeenCalledWith('task-1');
      expect(consoleError).not.toHaveBeenCalled();
    } finally {
      consoleError.mockRestore();
    }
  });
});
