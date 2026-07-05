import { fireEvent, render, screen } from '@testing-library/react';
import type React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertRuleList } from '../AlertRuleList';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import type { AlertRuleItem } from '../../../types/alerts';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';

const rules: AlertRuleItem[] = [
  {
    id: 1,
    name: '\u8305\u53f0\u4ef7\u683c\u7a81\u7834',
    targetScope: 'single_symbol',
    target: '600519',
    alertType: 'price_cross',
    parameters: { direction: 'above', price: 1800 },
    severity: 'warning',
    enabled: true,
    source: 'api',
    cooldownUntil: '2099-05-18T10:30:00',
    cooldownActive: true,
    createdAt: '2026-05-18T09:00:00',
    updatedAt: '2026-05-18T09:30:00',
  },
  {
    id: 2,
    name: 'MACD \u91d1\u53c9',
    targetScope: 'single_symbol',
    target: '300750',
    alertType: 'macd_cross',
    parameters: { direction: 'bullish_cross', fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
    severity: 'info',
    enabled: true,
    source: 'api',
    cooldownActive: false,
    createdAt: '2026-05-18T09:00:00',
    updatedAt: '2026-05-18T09:30:00',
  },
  {
    id: 3,
    name: 'KDJ \u6b7b\u53c9',
    targetScope: 'single_symbol',
    target: '000001',
    alertType: 'kdj_cross',
    parameters: { direction: 'bearish_cross', period: 9, kPeriod: 3, dPeriod: 3 },
    severity: 'warning',
    enabled: true,
    source: 'api',
    cooldownActive: false,
    createdAt: '2026-05-18T09:00:00',
    updatedAt: '2026-05-18T09:30:00',
  },
];

describe('AlertRuleList', () => {
  const onEnabledFilterChange = vi.fn();
  const onAlertTypeFilterChange = vi.fn();
  const onPageChange = vi.fn();
  const onToggleEnabled = vi.fn();
  const onDelete = vi.fn();
  const onTest = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  function renderList(overrides: Partial<React.ComponentProps<typeof AlertRuleList>> = {}) {
    render(
      <AlertRuleList
        rules={rules}
        total={40}
        page={1}
        pageSize={20}
        enabledFilter="all"
        alertTypeFilter="all"
        onEnabledFilterChange={onEnabledFilterChange}
        onAlertTypeFilterChange={onAlertTypeFilterChange}
        onPageChange={onPageChange}
        onToggleEnabled={onToggleEnabled}
        onDelete={onDelete}
        onTest={onTest}
        {...overrides}
      />,
    );
  }

  function renderEnglishList(overrides: Partial<React.ComponentProps<typeof AlertRuleList>> = {}) {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    render(
      <UiLanguageProvider>
        <AlertRuleList
          rules={rules}
          total={40}
          page={1}
          pageSize={20}
          enabledFilter="all"
          alertTypeFilter="all"
          onEnabledFilterChange={onEnabledFilterChange}
          onAlertTypeFilterChange={onAlertTypeFilterChange}
          onPageChange={onPageChange}
          onToggleEnabled={onToggleEnabled}
          onDelete={onDelete}
          onTest={onTest}
          {...overrides}
        />
      </UiLanguageProvider>,
    );
  }

  it('renders rules, filters, and pagination', () => {
    renderList();

    expect(screen.getByText('\u8305\u53f0\u4ef7\u683c\u7a81\u7834')).toBeInTheDocument();
    expect(screen.getByText('600519')).toBeInTheDocument();
    expect(screen.getAllByText('\u4ef7\u683c\u7a81\u7834').length).toBeGreaterThan(0);
    expect(screen.getByText('\u4e0a\u7834 1800')).toBeInTheDocument();
    expect(screen.getAllByText('MACD \u91d1\u53c9/\u6b7b\u53c9').length).toBeGreaterThan(0);
    expect(screen.getByText('MACD(12,26,9) \u91d1\u53c9')).toBeInTheDocument();
    expect(screen.getByText('KDJ(9,3,3) \u6b7b\u53c9')).toBeInTheDocument();
    expect(screen.getByText('\u51b7\u5374\u4e2d')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('\u542f\u505c\u72b6\u6001'), { target: { value: 'enabled' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'price_cross' } });
    fireEvent.click(screen.getByRole('button', { name: '2' }));

    expect(onEnabledFilterChange).toHaveBeenCalledWith('enabled');
    expect(onAlertTypeFilterChange).toHaveBeenCalledWith('price_cross');
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('uses backend cooldownActive instead of parsing cooldownUntil locally', () => {
    renderList({
      rules: [
        {
          ...rules[0],
          cooldownUntil: '2099-05-18T10:30:00',
          cooldownActive: false,
        },
      ],
    });

    expect(screen.getByText('\u672a\u51b7\u5374')).toBeInTheDocument();
  });

  it('renders portfolio scope labels and child-target cooldown hint', () => {
    renderList({
      rules: [
        {
          id: 4,
          name: '\u6301\u4ed3 RSI',
          targetScope: 'portfolio_holdings',
          target: 'all',
          alertType: 'rsi_threshold',
          parameters: { direction: 'below', period: 12, threshold: 30 },
          severity: 'warning',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
        {
          id: 5,
          name: '\u7ec4\u5408\u6b62\u635f',
          targetScope: 'portfolio_account',
          target: '9',
          alertType: 'portfolio_stop_loss',
          parameters: { mode: 'breach' },
          severity: 'critical',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
      ],
    });

    expect(screen.getByText('\u6301\u4ed3\u6807\u7684')).toBeInTheDocument();
    expect(screen.getByText('\u5b50\u76ee\u6807\u89c1\u89e6\u53d1\u5386\u53f2')).toBeInTheDocument();
    expect(screen.getByText('\u8d26\u6237 9')).toBeInTheDocument();
    expect(screen.getAllByText('\u7ec4\u5408\u6b62\u635f').length).toBeGreaterThan(0);
    expect(screen.getByText('\u5df2\u89e6\u53d1\u6b62\u635f')).toBeInTheDocument();
  });

  it('renders portfolio drawdown alert labels in English UI mode', () => {
    renderEnglishList({
      rules: [
        {
          id: 8,
          name: 'Drawdown rule',
          targetScope: 'portfolio_account',
          target: 'all',
          alertType: 'portfolio_drawdown',
          parameters: {},
          severity: 'warning',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
      ],
    });

    expect(screen.getByText('Alert rules')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'All statuses' })).toBeInTheDocument();
    expect(screen.getAllByText('Portfolio drawdown').length).toBeGreaterThan(0);
    expect(screen.getByText('Portfolio account')).toBeInTheDocument();
    expect(screen.getAllByText('Enabled').length).toBeGreaterThan(0);
    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.queryByText('\u7ec4\u5408\u56de\u64a4')).not.toBeInTheDocument();
  });

  it('renders market scope labels, filters, and parameters', () => {
    renderList({
      rules: [
        {
          id: 6,
          name: 'A \u80a1\u7ea2\u9ec4\u706f',
          targetScope: 'market',
          target: 'cn',
          alertType: 'market_light_status',
          parameters: { statuses: ['red', 'yellow'] },
          severity: 'critical',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
        {
          id: 7,
          name: '\u7f8e\u80a1\u5206\u6570\u4e0b\u964d',
          targetScope: 'market',
          target: 'us',
          alertType: 'market_light_score_drop',
          parameters: { minDrop: 15 },
          severity: 'warning',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
      ],
    });

    expect(screen.getByText('A \u80a1')).toBeInTheDocument();
    expect(screen.getByText('\u7f8e\u80a1')).toBeInTheDocument();
    expect(screen.getAllByText('\u5927\u76d8\u5e02\u573a').length).toBeGreaterThan(0);
    expect(screen.getAllByText('\u5927\u76d8\u7ea2\u7eff\u706f\u72b6\u6001').length).toBeGreaterThan(0);
    expect(screen.getByText('\u7ea2\u706f / \u9ec4\u706f')).toBeInTheDocument();
    expect(screen.getByText('Score \u4e0b\u964d >= 15')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'market_light_score_drop' } });

    expect(onAlertTypeFilterChange).toHaveBeenCalledWith('market_light_score_drop');
  });

  it('runs test and toggles enabled state', () => {
    renderList();

    fireEvent.click(screen.getAllByRole('button', { name: '\u6d4b\u8bd5' })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: '\u505c\u7528' })[0]);

    expect(onTest).toHaveBeenCalledWith(rules[0]);
    expect(onToggleEnabled).toHaveBeenCalledWith(rules[0]);
  });

  it('shows loading text only for the active rule operation', () => {
    renderList({ busyRule: { id: 1, action: 'toggle' } });

    expect(screen.getAllByRole('button', { name: '\u6d4b\u8bd5' })[0]).toBeDisabled();
    expect(screen.getByRole('button', { name: '\u505c\u7528\u4e2d' })).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByRole('button', { name: '\u6d4b\u8bd5\u4e2d' })).not.toBeInTheDocument();
  });

  it('confirms deletion before calling onDelete', async () => {
    renderList();

    fireEvent.click(screen.getByLabelText('\u5220\u9664 \u8305\u53f0\u4ef7\u683c\u7a81\u7834'));
    expect(await screen.findByRole('heading', { name: '\u5220\u9664\u544a\u8b66\u89c4\u5219' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u5220\u9664' }));

    expect(onDelete).toHaveBeenCalledWith(rules[0]);
  });

  it('shows an empty state for no rules', () => {
    renderList({ rules: [], total: 0 });

    expect(screen.getByText('\u6682\u65e0\u544a\u8b66\u89c4\u5219')).toBeInTheDocument();
  });
});
