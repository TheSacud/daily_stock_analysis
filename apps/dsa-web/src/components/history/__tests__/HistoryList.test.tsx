import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HistoryList } from '../HistoryList';
import type { HistoryItem } from '../../../types/analysis';

const baseProps = {
  isLoading: false,
  isLoadingMore: false,
  hasMore: false,
  selectedIds: new Set<number>(),
  onItemClick: vi.fn(),
  onLoadMore: vi.fn(),
  onToggleItemSelection: vi.fn(),
  onToggleSelectAll: vi.fn(),
  onDeleteSelected: vi.fn(),
};

const items: HistoryItem[] = [
  {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '\u8d35\u5dde\u8305\u53f0',
    sentimentScore: 82,
    operationAdvice: '\u4e70\u5165',
    createdAt: '2026-03-15T08:00:00Z',
  },
];

const longChineseNameItem: HistoryItem = {
  id: 2,
  queryId: 'q-2',
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8',
  sentimentScore: 75,
  operationAdvice: '\u6301\u6709',
  createdAt: '2026-03-16T08:00:00Z',
  marketPhaseSummary: {
    market: 'CN',
    phase: 'non_trading',
    warnings: [],
  },
};

describe('HistoryList', () => {
  it('shows the empty state copy when no history exists', () => {
    const { container } = render(<HistoryList {...baseProps} items={[]} />);

    expect(screen.getByText('\u6682\u65e0\u5386\u53f2\u5206\u6790\u8bb0\u5f55')).toBeInTheDocument();
    expect(screen.getByText('\u5b8c\u6210\u9996\u6b21\u5206\u6790\u540e，\u8fd9\u91cc\u4f1a\u4fdd\u7559\u6700\u8fd1\u7ed3\u679c。')).toBeInTheDocument();
    expect(screen.getByText('\u5386\u53f2\u5206\u6790')).toBeInTheDocument();
    expect(container.querySelector('.glass-card')).toBeTruthy();
  });

  it('renders selected count and forwards item interactions', () => {
    const onItemClick = vi.fn();
    const onToggleItemSelection = vi.fn();

    render(
      <HistoryList
        {...baseProps}
        items={items}
        selectedIds={new Set([1])}
        selectedId={1}
        onItemClick={onItemClick}
        onToggleItemSelection={onToggleItemSelection}
      />,
    );

    expect(screen.getByText('\u5df2\u9009 1')).toBeInTheDocument();
    expect(screen.getByText('\u4e70\u5165 82')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /\u8d35\u5dde\u8305\u53f0/i }));
    expect(onItemClick).toHaveBeenCalledWith(1);

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    expect(onToggleItemSelection).toHaveBeenCalledWith(1);
  });

  it('uses structured action before legacy operation advice', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: 'avoid',
            actionLabel: '\u56de\u907f',
            operationAdvice: '\u4e70\u5165',
            sentimentScore: 35,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u56de\u907f 35')).toBeInTheDocument();
    expect(screen.queryByText('\u4e70\u5165 35')).not.toBeInTheDocument();
  });

  it('uses the unified legacy fallback for negated buy advice without structured action', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: null,
            actionLabel: null,
            operationAdvice: '\u4e0d\u5efa\u8bae\u4e70\u5165，\u7b49\u5f85\u786e\u8ba4',
            sentimentScore: 28,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u56de\u907f 28')).toBeInTheDocument();
    expect(screen.queryByText('\u4e70\u5165 28')).not.toBeInTheDocument();
  });

  it('uses the unified legacy fallback for backend-aligned hold advice without structured action', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: null,
            actionLabel: null,
            operationAdvice: '\u6d17\u76d8\u89c2\u5bdf',
            sentimentScore: 48,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u6301\u6709 48')).toBeInTheDocument();
    expect(screen.queryByText('\u60c5\u7eea 48')).not.toBeInTheDocument();
  });

  it('does not render ambiguous English legacy advice as a buy action', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: null,
            actionLabel: null,
            operationAdvice: 'buy or sell',
            sentimentScore: 28,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u60c5\u7eea 28')).toBeInTheDocument();
    expect(screen.queryByText('buy 28')).not.toBeInTheDocument();
  });

  it('does not render financial compound English advice as an action badge', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: null,
            actionLabel: null,
            operationAdvice: 'no buyback announced',
            sentimentScore: 28,
          },
          {
            ...items[0],
            id: 2,
            queryId: 'q-2',
            action: null,
            actionLabel: null,
            operationAdvice: 'no selloff risk',
            sentimentScore: 31,
          },
          {
            ...items[0],
            id: 3,
            queryId: 'q-3',
            action: null,
            actionLabel: null,
            operationAdvice: 'sell-off risk remains low',
            sentimentScore: 33,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u60c5\u7eea 28')).toBeInTheDocument();
    expect(screen.getByText('\u60c5\u7eea 31')).toBeInTheDocument();
    expect(screen.getByText('\u60c5\u7eea 33')).toBeInTheDocument();
    expect(screen.queryByText('\u56de\u907f 28')).not.toBeInTheDocument();
    expect(screen.queryByText('\u6301\u6709 31')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5356\u51fa 33')).not.toBeInTheDocument();
  });

  it('does not render Chinese financial context legacy advice as an action badge', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: null,
            actionLabel: null,
            operationAdvice: '\u4e70\u76d8\u589e\u5f3a，\u7ee7\u7eed\u89c2\u5bdf',
            sentimentScore: 32,
          },
          {
            ...items[0],
            id: 2,
            queryId: 'q-2',
            action: null,
            actionLabel: null,
            operationAdvice: '\u5356\u538b\u7f13\u89e3，\u7ee7\u7eed\u89c2\u5bdf',
            sentimentScore: 34,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u60c5\u7eea 32')).toBeInTheDocument();
    expect(screen.getByText('\u60c5\u7eea 34')).toBeInTheDocument();
    expect(screen.queryByText('\u4e70\u5165 32')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5356\u51fa 34')).not.toBeInTheDocument();
  });

  it('does not render multi-guard legacy advice as an avoid or alert action', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[
          {
            ...items[0],
            action: null,
            actionLabel: null,
            operationAdvice: 'risk alert, avoid buying',
            sentimentScore: 28,
          },
        ]}
      />,
    );

    expect(screen.getByText('\u60c5\u7eea 28')).toBeInTheDocument();
    expect(screen.queryByText('\u56de\u907f 28')).not.toBeInTheDocument();
    expect(screen.queryByText('\u9884\u8b66 28')).not.toBeInTheDocument();
  });

  it('toggles select-all when clicking the label text', () => {
    const onToggleSelectAll = vi.fn();

    render(
      <HistoryList
        {...baseProps}
        items={items}
        onToggleSelectAll={onToggleSelectAll}
      />,
    );

    fireEvent.click(screen.getByText('\u5168\u9009\u5f53\u524d'));

    expect(onToggleSelectAll).toHaveBeenCalledTimes(1);
  });

  it('disables delete when nothing is selected', () => {
    render(<HistoryList {...baseProps} items={items} />);

    expect(screen.getByRole('button', { name: '\u5220\u9664' })).toBeDisabled();
  });

  it('truncates long stock names with trailing dot', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[longChineseNameItem]}
      />,
    );

    // '\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8' (12 Chinese chars) should be truncated to '\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd.' (8 chars + dot)
    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd.')).toBeInTheDocument();
    expect(screen.queryByText('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: /^\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8 600519 \u5386\u53f2\u8bb0\u5f55$/,
      }),
    ).toBeInTheDocument();

    const actions = screen.getByTestId('history-card-actions');
    const meta = screen.getByTestId('history-card-meta');
    expect(within(actions).queryByText('CN · \u975e\u4ea4\u6613\u65e5')).not.toBeInTheDocument();
    expect(within(meta).getByText('CN · \u975e\u4ea4\u6613\u65e5')).toBeVisible();
  });

  it('generates unique select-all ids across multiple instances', () => {
    const { container } = render(
      <>
        <HistoryList {...baseProps} items={items} />
        <HistoryList {...baseProps} items={items} />
      </>,
    );

    const labels = container.querySelectorAll('label[for]');
    const ids = Array.from(labels).map((label) => label.getAttribute('for'));

    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
