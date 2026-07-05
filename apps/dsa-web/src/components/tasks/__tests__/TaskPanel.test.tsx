import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TaskPanel } from '../TaskPanel';
import type { TaskInfo } from '../../../types/analysis';

const baseTask: TaskInfo = {
  taskId: 'task-1',
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  status: 'processing',
  progress: 40,
  message: '\u6b63\u5728\u6293\u53d6\u6700\u65b0\u884c\u60c5',
  reportType: 'detailed',
  createdAt: '2026-03-21T08:00:00Z',
};

describe('TaskPanel', () => {
  it('renders requested analysis phase badges for active tasks', () => {
    render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            analysisPhase: 'intraday',
          },
          {
            ...baseTask,
            taskId: 'task-2',
            stockCode: 'AAPL',
            stockName: 'Apple',
            status: 'pending',
            analysisPhase: 'auto',
          },
        ]}
      />,
    );

    expect(screen.getByLabelText('\u8bf7\u6c42\u9636\u6bb5: \u76d8\u4e2d')).toBeInTheDocument();
    expect(screen.getByLabelText('\u8bf7\u6c42\u9636\u6bb5: \u81ea\u52a8\u9636\u6bb5')).toBeInTheDocument();
  });

  it('renders active tasks with preserved dashboard panel styling', () => {
    const { container } = render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            traceId: 'trace-task-1',
          },
          {
            ...baseTask,
            taskId: 'task-2',
            stockCode: 'AAPL',
            stockName: 'Apple',
            status: 'pending',
            message: '\u7b49\u5f85\u5206\u6790\u961f\u5217',
          },
        ]}
      />,
    );

    expect(screen.getByText('\u5206\u6790\u4efb\u52a1')).toBeInTheDocument();
    expect(screen.getByText('1 \u8fdb\u884c\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('1 \u7b49\u5f85\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0')).toBeInTheDocument();
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByLabelText('\u4efb\u52a1\u72b6\u6001：\u5206\u6790\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('\u8fd0\u884c\u8bca\u65ad')).toBeInTheDocument();
    expect(screen.getAllByText('trace-task-1')).toHaveLength(2);
    expect(screen.queryByText(/\u8bf7\u6c42\u9636\u6bb5:/)).not.toBeInTheDocument();
    expect(container.querySelector('.home-panel-card')).toBeTruthy();
    expect(container.querySelector('.home-subpanel')).toBeTruthy();
  });

  it('keeps narrow sidebar task metadata in rows instead of squeezing diagnostics vertically', () => {
    render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            stockCode: '601869.SH',
            stockName: '\u957f\u98de\u5149\u7ea4',
            progress: 32,
            message: '\u957f\u98de\u5149\u7ea4: \u8bf7\u6c42\u9636\u6bb5: \u81ea\u52a8\u9636\u6bb5',
            analysisPhase: 'auto',
            traceId: 'c5b9665a64e3b9f42ad9f',
          },
        ]}
        onOpenRunFlow={vi.fn()}
      />,
    );

    const item = screen.getByTestId('task-panel-item');
    expect(item).toHaveClass('grid');
    expect(item).not.toHaveClass('flex');
    expect(screen.getByText('\u957f\u98de\u5149\u7ea4')).toHaveClass('truncate');
    expect(screen.getByText('601869.SH')).toHaveClass('shrink-0');
    expect(screen.getByText('32%')).toBeInTheDocument();

    const diagnosticsSummary = screen.getByTestId('task-panel-diagnostics-summary');
    expect(diagnosticsSummary).toHaveClass('grid-cols-[auto_minmax(0,1fr)_auto]');
    expect(screen.getByText('\u8fd0\u884c\u8bca\u65ad')).toHaveClass('whitespace-nowrap');
    expect(screen.getByText('c5b9665a64...')).toHaveClass('truncate');
    expect(screen.getByRole('button', { name: '\u67e5\u770b \u957f\u98de\u5149\u7ea4 \u8fd0\u884c\u6d41' })).toBeInTheDocument();
  });

  it('opens the run-flow view from an active task icon button', () => {
    const onOpenRunFlow = vi.fn();
    render(
      <TaskPanel
        tasks={[baseTask]}
        onOpenRunFlow={onOpenRunFlow}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 \u8fd0\u884c\u6d41' }));

    expect(onOpenRunFlow).toHaveBeenCalledWith(baseTask);
  });

  it('keeps cancel-requested tasks visible without rendering them as failed', () => {
    render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            status: 'cancel_requested',
            message: '\u6b63\u5728\u8bf7\u6c42\u53d6\u6d88',
          },
        ]}
      />,
    );

    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0')).toBeInTheDocument();
    expect(screen.getByLabelText('\u4efb\u52a1\u72b6\u6001：\u8bf7\u6c42\u53d6\u6d88')).toBeInTheDocument();
    expect(screen.queryByText('\u5931\u8d25')).not.toBeInTheDocument();
  });

  it('does not keep cancelled terminal tasks in the active task panel', () => {
    const { container } = render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            status: 'cancelled',
          },
        ]}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('does not render when there are no active tasks', () => {
    const { container } = render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            status: 'completed',
          },
        ]}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
