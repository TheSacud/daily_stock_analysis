import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AlertsPage from '../AlertsPage';

const {
  listRules,
  createRule,
  deleteRule,
  enableRule,
  disableRule,
  testRule,
  listTriggers,
  listNotifications,
} = vi.hoisted(() => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  deleteRule: vi.fn(),
  enableRule: vi.fn(),
  disableRule: vi.fn(),
  testRule: vi.fn(),
  listTriggers: vi.fn(),
  listNotifications: vi.fn(),
}));

vi.mock('../../api/alerts', () => ({
  alertsApi: {
    listRules,
    createRule,
    deleteRule,
    enableRule,
    disableRule,
    testRule,
    listTriggers,
    listNotifications,
  },
}));

vi.mock('../../api/portfolio', () => ({
  portfolioApi: {
    getAccounts: vi.fn().mockResolvedValue({ accounts: [] }),
  },
}));

const parsedError = {
  title: '\u52a0\u8f7d\u5931\u8d25',
  message: '\u544a\u8b66 API \u4e0d\u53ef\u7528',
  rawMessage: '\u544a\u8b66 API \u4e0d\u53ef\u7528',
  category: 'http_error' as const,
  status: 500,
};

const rule = {
  id: 1,
  name: '\u8305\u53f0\u4ef7\u683c\u7a81\u7834',
  targetScope: 'single_symbol' as const,
  target: '600519',
  alertType: 'price_cross' as const,
  parameters: { direction: 'above' as const, price: 1800 },
  severity: 'warning' as const,
  enabled: true,
  source: 'api',
  createdAt: '2026-05-18T09:00:00',
  updatedAt: '2026-05-18T09:30:00',
};

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.clearAllMocks();
  listRules.mockResolvedValue({ items: [rule], total: 1, page: 1, pageSize: 20 });
  listTriggers.mockResolvedValue({
    items: [
      {
        id: 10,
        ruleId: 1,
        target: '600519',
        observedValue: 1801,
        threshold: 1800,
        reason: '600519 price above 1800',
        dataSource: 'realtime_quote',
        dataTimestamp: '2026-05-18T09:30:00',
        triggeredAt: '2026-05-18T09:30:01',
        status: 'triggered',
      },
    ],
    total: 1,
    page: 1,
    pageSize: 20,
  });
  listNotifications.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 });
  testRule.mockResolvedValue({
    ruleId: 1,
    status: 'triggered',
    triggered: true,
    observedValue: 1801,
    message: '600519 price above 1800',
  });
  createRule.mockResolvedValue(rule);
  disableRule.mockResolvedValue({ ...rule, enabled: false });
  enableRule.mockResolvedValue(rule);
  deleteRule.mockResolvedValue({ deleted: 1 });
});

describe('AlertsPage', () => {
  it('loads rules, trigger history, and notification empty state', async () => {
    render(<AlertsPage />);

    expect(screen.getByText('\u7ba1\u7406\u4e8b\u4ef6\u544a\u8b66、\u65e5\u7ebf\u6280\u672f\u6307\u6807、\u81ea\u9009\u80a1、\u6301\u4ed3/\u8d26\u6237\u8054\u52a8\u548c\u5927\u76d8\u7ea2\u7eff\u706f\u89c4\u5219，\u6267\u884c\u4e00\u6b21\u6027\u6d4b\u8bd5，\u5e76\u67e5\u770b\u540e\u53f0\u8bc4\u4f30\u4efb\u52a1\u8bb0\u5f55\u7684\u89e6\u53d1\u5386\u53f2。')).toBeInTheDocument();
    expect(await screen.findByText('\u8305\u53f0\u4ef7\u683c\u7a81\u7834')).toBeInTheDocument();
    expect(await screen.findByText('600519 price above 1800')).toBeInTheDocument();
    expect(await screen.findByText('\u6682\u65e0\u901a\u77e5\u5c1d\u8bd5\u8bb0\u5f55')).toBeInTheDocument();
    expect(listRules).toHaveBeenCalledWith({
      enabled: undefined,
      alertType: undefined,
      page: 1,
      pageSize: 20,
    });
    expect(listTriggers).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(listNotifications).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
  });

  it('runs a dry-run test and renders only declared response fields', async () => {
    listTriggers.mockResolvedValueOnce({ items: [], total: 0, page: 1, pageSize: 20 });
    render(<AlertsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '\u6d4b\u8bd5' }));

    await waitFor(() => expect(testRule).toHaveBeenCalledWith(1));
    expect(await screen.findByText('\u6d4b\u8bd5\u7ed3\u679c')).toBeInTheDocument();
    expect(screen.getByText(/600519 price above 1800/)).toBeInTheDocument();
    expect(screen.getByText(/\u89c2\u5bdf\u503c：1801/)).toBeInTheDocument();
    expect(screen.queryByText(/realtime_quote/)).not.toBeInTheDocument();
  });

  it('renders batch dry-run summary and target results', async () => {
    testRule.mockResolvedValueOnce({
      ruleId: 1,
      targetScope: 'watchlist',
      status: 'triggered',
      triggered: true,
      observedValue: 11,
      message: 'Evaluated 2 targets',
      evaluatedCount: 2,
      triggeredCount: 1,
      degradedCount: 1,
      skippedCount: 0,
      targetResults: [
        {
          target: '600519',
          displayTarget: '\u81ea\u9009\u80a1 - 600519',
          status: 'triggered',
          recordStatus: 'triggered',
          triggered: true,
          observedValue: 11,
          message: 'triggered',
        },
        {
          target: '000001',
          displayTarget: '\u81ea\u9009\u80a1 - 000001',
          status: 'not_triggered',
          recordStatus: 'degraded',
          triggered: false,
          observedValue: null,
          message: 'degraded',
        },
      ],
    });
    render(<AlertsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '\u6d4b\u8bd5' }));

    expect(await screen.findByText(/\u8bc4\u4f30 2 · \u89e6\u53d1 1 · \u964d\u7ea7 1 · \u8df3\u8fc7 0/)).toBeInTheDocument();
    expect(screen.getByText('\u81ea\u9009\u80a1 - 600519')).toBeInTheDocument();
    expect(screen.getByText(/not_triggered \/ degraded/)).toBeInTheDocument();
  });

  it('creates a rule through the page form and reloads rules', async () => {
    render(<AlertsPage />);

    await screen.findByText('\u8305\u53f0\u4ef7\u683c\u7a81\u7834');
    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(createRule).toHaveBeenCalledWith(expect.objectContaining({
        target: 'AAPL',
        alertType: 'price_cross',
        parameters: { direction: 'above', price: 200 },
      }));
    });
    expect(await screen.findByText(/\u5df2\u521b\u5efa\u544a\u8b66\u89c4\u5219/)).toBeInTheDocument();
  });

  it('keeps create form values when create API fails', async () => {
    createRule.mockRejectedValueOnce({ parsedError });
    render(<AlertsPage />);

    await screen.findByText('\u8305\u53f0\u4ef7\u683c\u7a81\u7834');
    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(await screen.findByText('\u52a0\u8f7d\u5931\u8d25')).toBeInTheDocument();
    expect(screen.getByLabelText('\u6807\u7684\u4ee3\u7801')).toHaveValue('aapl');
    expect(screen.getByLabelText('\u4ef7\u683c\u9608\u503c')).toHaveValue(200);
  });

  it('clamps rules pagination when a mutation leaves the current page empty', async () => {
    const page2Rule = { ...rule, id: 2, name: '\u7b2c\u4e8c\u9875\u89c4\u5219', target: 'AAPL' };
    listRules
      .mockResolvedValueOnce({ items: [rule], total: 21, page: 1, pageSize: 20 })
      .mockResolvedValueOnce({ items: [page2Rule], total: 21, page: 2, pageSize: 20 })
      .mockResolvedValueOnce({ items: [], total: 20, page: 2, pageSize: 20 })
      .mockResolvedValue({ items: [rule], total: 20, page: 1, pageSize: 20 });

    render(<AlertsPage />);

    expect(await screen.findByText('\u8305\u53f0\u4ef7\u683c\u7a81\u7834')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    expect(await screen.findByText('\u7b2c\u4e8c\u9875\u89c4\u5219')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('\u5220\u9664 \u7b2c\u4e8c\u9875\u89c4\u5219'));
    fireEvent.click(await screen.findByRole('button', { name: '\u5220\u9664' }));

    await waitFor(() => expect(deleteRule).toHaveBeenCalledWith(2));
    await waitFor(() => {
      expect(listRules).toHaveBeenCalledWith({
        enabled: undefined,
        alertType: undefined,
        page: 1,
        pageSize: 20,
      });
    });
    expect(await screen.findByText('\u8305\u53f0\u4ef7\u683c\u7a81\u7834')).toBeInTheDocument();
  });

  it('keeps the latest rules response when filter requests resolve out of order', async () => {
    const initialRequest = createDeferred<{ items: Array<typeof rule>; total: number; page: number; pageSize: number }>();
    const filteredRequest = createDeferred<{ items: Array<typeof rule>; total: number; page: number; pageSize: number }>();
    const staleRule = { ...rule, id: 3, name: '\u65e7\u7b5b\u9009\u89c4\u5219', enabled: true };
    const filteredRule = { ...rule, id: 4, name: '\u505c\u7528\u89c4\u5219', enabled: false };
    listRules
      .mockReset()
      .mockReturnValueOnce(initialRequest.promise)
      .mockReturnValueOnce(filteredRequest.promise);

    render(<AlertsPage />);

    fireEvent.change(screen.getByLabelText('\u542f\u505c\u72b6\u6001'), { target: { value: 'disabled' } });
    await waitFor(() => expect(listRules).toHaveBeenCalledTimes(2));

    filteredRequest.resolve({ items: [filteredRule], total: 1, page: 1, pageSize: 20 });
    expect(await screen.findByText('\u505c\u7528\u89c4\u5219')).toBeInTheDocument();

    initialRequest.resolve({ items: [staleRule], total: 1, page: 1, pageSize: 20 });
    await waitFor(() => expect(screen.queryByText('\u65e7\u7b5b\u9009\u89c4\u5219')).not.toBeInTheDocument());
    expect(screen.getByText('\u505c\u7528\u89c4\u5219')).toBeInTheDocument();
  });

  it('renders API errors through ApiErrorAlert', async () => {
    listRules.mockRejectedValueOnce({ parsedError });

    render(<AlertsPage />);

    expect(await screen.findByText('\u52a0\u8f7d\u5931\u8d25')).toBeInTheDocument();
    expect(screen.getByText('\u544a\u8b66 API \u4e0d\u53ef\u7528')).toBeInTheDocument();
  });
});
