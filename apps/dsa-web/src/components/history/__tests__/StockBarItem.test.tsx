import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StockBarItemComponent } from '../StockBarItem';
import type { StockBarItem } from '../../../types/analysis';

const issue1600Item: StockBarItem = {
  id: 1,
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8',
  sentimentScore: 62,
  operationAdvice: '\u89c2\u671b',
  analysisCount: 2,
  lastAnalysisTime: '2026-05-31T04:52:00Z',
  marketPhaseSummary: {
    market: 'CN',
    phase: 'non_trading',
    warnings: [],
  },
};

describe('StockBarItemComponent', () => {
  it('keeps market phase in the meta row instead of the action row', () => {
    render(
      <StockBarItemComponent
        item={issue1600Item}
        isViewing={false}
        onClick={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const actions = screen.getByTestId('history-card-actions');
    const meta = screen.getByTestId('history-card-meta');

    expect(within(actions).getByText('\u89c2\u671b 62')).toBeInTheDocument();
    expect(within(actions).getByRole('button', { name: /\u5220\u9664 \u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8 \u5386\u53f2\u8bb0\u5f55/ })).toBeInTheDocument();
    expect(within(actions).queryByText('CN · \u975e\u4ea4\u6613\u65e5')).not.toBeInTheDocument();
    expect(within(meta).getByText('CN · \u975e\u4ea4\u6613\u65e5')).toBeVisible();

    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd.')).toBeVisible();
    expect(
      screen.getByRole('button', {
        name: /^\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8 600519 \u5386\u53f2\u8bb0\u5f55$/,
      }),
    ).toBeInTheDocument();
  });

  it('uses structured action before legacy operation advice', () => {
    render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: 'avoid',
          actionLabel: '\u56de\u907f',
          operationAdvice: '\u4e70\u5165',
          sentimentScore: 35,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    const actions = screen.getByTestId('history-card-actions');
    expect(within(actions).getByText('\u56de\u907f 35')).toBeInTheDocument();
    expect(within(actions).queryByText('\u4e70\u5165 35')).not.toBeInTheDocument();
  });

  it('uses the unified legacy fallback for negated buy advice without structured action', () => {
    render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: '\u4e0d\u5efa\u8bae\u4e70\u5165，\u7b49\u5f85\u786e\u8ba4',
          sentimentScore: 28,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    const actions = screen.getByTestId('history-card-actions');
    expect(within(actions).getByText('\u56de\u907f 28')).toBeInTheDocument();
    expect(within(actions).queryByText('\u4e70\u5165 28')).not.toBeInTheDocument();
  });

  it('uses the unified legacy fallback for backend-aligned hold advice without structured action', () => {
    render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: '\u6d17\u76d8\u89c2\u5bdf',
          sentimentScore: 48,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    const actions = screen.getByTestId('history-card-actions');
    expect(within(actions).getByText('\u6301\u6709 48')).toBeInTheDocument();
  });

  it('does not render ambiguous English legacy advice as a buy action', () => {
    render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: 'buy or sell',
          sentimentScore: 28,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    const actions = screen.getByTestId('history-card-actions');
    expect(within(actions).queryByText('buy 28')).not.toBeInTheDocument();
    expect(within(actions).getByText(/28/)).toBeInTheDocument();
  });

  it('does not render financial compound English advice as an action badge', () => {
    const { rerender } = render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: 'no selloff risk',
          sentimentScore: 28,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    let actions = screen.getByTestId('history-card-actions');
    expect(within(actions).queryByText('\u6301\u6709 28')).not.toBeInTheDocument();
    expect(within(actions).getByText(/28/)).toBeInTheDocument();

    rerender(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: 'sell-off risk remains low',
          sentimentScore: 31,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    actions = screen.getByTestId('history-card-actions');
    expect(within(actions).queryByText('\u5356\u51fa 31')).not.toBeInTheDocument();
    expect(within(actions).getByText(/31/)).toBeInTheDocument();
  });

  it('does not render Chinese financial context legacy advice as an action badge', () => {
    const { rerender } = render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: '\u4e70\u76d8\u589e\u5f3a，\u7ee7\u7eed\u89c2\u5bdf',
          sentimentScore: 32,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    let actions = screen.getByTestId('history-card-actions');
    expect(within(actions).queryByText('\u4e70\u5165 32')).not.toBeInTheDocument();
    expect(within(actions).getByText(/32/)).toBeInTheDocument();

    rerender(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: '\u5356\u538b\u7f13\u89e3，\u7ee7\u7eed\u89c2\u5bdf',
          sentimentScore: 34,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    actions = screen.getByTestId('history-card-actions');
    expect(within(actions).queryByText('\u5356\u51fa 34')).not.toBeInTheDocument();
    expect(within(actions).getByText(/34/)).toBeInTheDocument();
  });

  it('does not render multi-guard legacy advice as an action badge', () => {
    render(
      <StockBarItemComponent
        item={{
          ...issue1600Item,
          action: null,
          actionLabel: null,
          operationAdvice: 'risk alert, avoid buying',
          sentimentScore: 28,
        }}
        isViewing={false}
        onClick={vi.fn()}
      />,
    );

    const actions = screen.getByTestId('history-card-actions');
    expect(within(actions).queryByText('\u56de\u907f 28')).not.toBeInTheDocument();
    expect(within(actions).queryByText('\u9884\u8b66 28')).not.toBeInTheDocument();
    expect(within(actions).getByText(/28/)).toBeInTheDocument();
  });
});
