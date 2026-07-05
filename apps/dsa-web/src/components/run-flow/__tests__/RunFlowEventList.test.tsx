import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { RunFlowEvent } from '../../../types/runFlow';
import { RunFlowEventList } from '../RunFlowEventList';

const events: RunFlowEvent[] = [
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
    nodeId: 'daily_data',
    title: '\u65e5\u7ebf\u964d\u7ea7',
    message: 'Tushare \u5931\u8d25\u540e\u5207\u6362 AkShare',
  },
  {
    id: 'evt-3',
    timestamp: '2026-06-08T08:00:03Z',
    severity: 'danger',
    type: 'task_cancelled',
    nodeId: 'queue',
    title: '\u4efb\u52a1\u53d6\u6d88',
  },
];

describe('RunFlowEventList', () => {
  it('filters fallback and cancellation events with visible text labels', () => {
    render(<RunFlowEventList events={events} />);

    expect(screen.getByText('\u4efb\u52a1\u521b\u5efa')).toBeInTheDocument();
    expect(screen.getByText('\u65e5\u7ebf\u964d\u7ea7')).toBeInTheDocument();
    expect(screen.getByText('\u4efb\u52a1\u53d6\u6d88')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u964d\u7ea7\u56de\u9000/\u91cd\u8bd5' }));

    expect(screen.getByText('\u65e5\u7ebf\u964d\u7ea7')).toBeInTheDocument();
    expect(screen.queryByText('\u4efb\u52a1\u521b\u5efa')).not.toBeInTheDocument();
    expect(screen.queryByText('\u4efb\u52a1\u53d6\u6d88')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u53d6\u6d88' }));

    expect(screen.getByText('\u4efb\u52a1\u53d6\u6d88')).toBeInTheDocument();
    expect(screen.queryByText('\u65e5\u7ebf\u964d\u7ea7')).not.toBeInTheDocument();
    expect(screen.getByText('\u5371\u9669')).toBeInTheDocument();
  });

  it('selects the event node when an event row is clicked', () => {
    const onSelectNode = vi.fn();
    render(<RunFlowEventList events={events} onSelectNode={onSelectNode} />);

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b\u4e8b\u4ef6 \u65e5\u7ebf\u964d\u7ea7 \u5173\u8054\u8282\u70b9' }));

    expect(onSelectNode).toHaveBeenCalledWith('daily_data');
  });
});
