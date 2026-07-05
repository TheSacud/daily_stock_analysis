import { StrictMode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import type { RunDiagnosticSummary } from '../../../types/analysis';
import { ReportDiagnostics } from '../ReportDiagnostics';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getDiagnostics: vi.fn(),
  },
}));

const diagnosticSummary: RunDiagnosticSummary = {
  traceId: 'trace-1234567890abcdef',
  taskId: 'task-1',
  queryId: 'query-1',
  stockCode: '600519',
  triggerSource: 'web',
  status: 'degraded',
  statusLabel: '\u90e8\u5206\u964d\u7ea7',
  reason: '\u5b9e\u65f6\u884c\u60c5 baostock \u6210\u529f，\u524d\u7f6e\u6570\u636e\u6e90\u5931\u8d25\u540e\u5df2\u7ee7\u7eed',
  copyText: 'trace_id: trace-1234567890abcdef\ndata_status: degraded',
  components: {
    realtimeQuote: {
      key: 'realtime_quote',
      label: '\u5b9e\u65f6\u884c\u60c5',
      status: 'degraded',
      message: '\u5b9e\u65f6\u884c\u60c5 baostock \u6210\u529f，\u524d\u7f6e\u6570\u636e\u6e90\u5931\u8d25\u540e\u5df2\u7ee7\u7eed',
      details: {
        provider: 'baostock',
        attempts: 2,
      },
    },
    notification: {
      key: 'notification',
      label: '\u901a\u77e5',
      status: 'not_configured',
      message: '\u901a\u77e5\u672a\u914d\u7f6e\u6216\u672c\u6b21\u8df3\u8fc7',
    },
  },
};

describe('ReportDiagnostics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it('loads historical diagnostics in a collapsed panel and copies sanitized text', async () => {
    vi.mocked(historyApi.getDiagnostics).mockResolvedValue(diagnosticSummary);

    render(<ReportDiagnostics recordId={1} />);

    expect(historyApi.getDiagnostics).toHaveBeenCalledWith(1);
    expect(await screen.findByText('\u8fd0\u884c\u72b6\u6001')).toBeInTheDocument();
    const panel = screen.getByTestId('run-diagnostics');
    expect(panel).not.toHaveAttribute('open');
    expect(screen.getByText('\u90e8\u5206\u964d\u7ea7')).toBeInTheDocument();

    fireEvent.click(screen.getByText('\u8fd0\u884c\u72b6\u6001'));

    expect(panel).toHaveAttribute('open');
    expect(screen.getByText('\u6700\u8fd1\u5931\u8d25\u540e\u5df2\u964d\u7ea7')).toBeInTheDocument();
    expect(screen.getByText('\u672a\u914d\u7f6e')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u590d\u5236\u6392\u969c\u4fe1\u606f' }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(diagnosticSummary.copyText);
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '\u5df2\u590d\u5236' })).toBeInTheDocument();
    });
  });

  it('uses the provided summary without fetching history diagnostics', () => {
    render(<ReportDiagnostics summary={diagnosticSummary} language="en" />);

    expect(historyApi.getDiagnostics).not.toHaveBeenCalled();
    expect(screen.getByText('Run Status')).toBeInTheDocument();
    expect(screen.getByText('Degraded')).toBeInTheDocument();
    expect(screen.getByText('Fetch / LLM / save / notification path')).toBeInTheDocument();
  });

  it('opens historical run flow from the diagnostics body', async () => {
    const onOpenRunFlow = vi.fn();
    vi.mocked(historyApi.getDiagnostics).mockResolvedValue(diagnosticSummary);

    render(<ReportDiagnostics recordId={1} onOpenRunFlow={onOpenRunFlow} />);

    fireEvent.click(await screen.findByText('\u8fd0\u884c\u72b6\u6001'));
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b\u5386\u53f2\u8bb0\u5f55 1 \u8fd0\u884c\u6d41' }));

    expect(onOpenRunFlow).toHaveBeenCalledWith(1);
  });

  it('refetches diagnostics after StrictMode cleans up the first effect run', async () => {
    vi.mocked(historyApi.getDiagnostics).mockResolvedValue(diagnosticSummary);

    render(
      <StrictMode>
        <ReportDiagnostics recordId={1} />
      </StrictMode>,
    );

    await waitFor(() => {
      expect(historyApi.getDiagnostics).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText('\u8fd0\u884c\u72b6\u6001')).toBeInTheDocument();
  });
});
