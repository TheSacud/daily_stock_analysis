import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import { AlertRuleForm } from '../AlertRuleForm';

const { getAccounts } = vi.hoisted(() => ({
  getAccounts: vi.fn(),
}));

vi.mock('../../../api/portfolio', () => ({
  portfolioApi: {
    getAccounts,
  },
}));

describe('AlertRuleForm', () => {
  const onSubmit = vi.fn();

  beforeEach(() => {
    onSubmit.mockReset();
    onSubmit.mockResolvedValue(undefined);
    getAccounts.mockReset();
    window.localStorage.clear();
    getAccounts.mockResolvedValue({ accounts: [{ id: 9, name: 'Main', market: 'us', baseCurrency: 'USD', isActive: true }] });
  });

  function renderEnglishForm() {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    render(
      <UiLanguageProvider>
        <AlertRuleForm onSubmit={onSubmit} />
      </UiLanguageProvider>,
    );
  }

  it('submits a price_cross rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u540d\u79f0'), { target: { value: '\u8305\u53f0\u4ef7\u683c\u7a81\u7834' } });
    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '1800' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: '\u8305\u53f0\u4ef7\u683c\u7a81\u7834',
        targetScope: 'single_symbol',
        target: '600519',
        alertType: 'price_cross',
        parameters: { direction: 'above', price: 1800 },
        severity: 'warning',
        enabled: true,
      });
    });
  });

  it('submits a price_change_percent rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'price_change_percent' } });
    fireEvent.change(screen.getByLabelText('\u65b9\u5411'), { target: { value: 'down' } });
    fireEvent.change(screen.getByLabelText('\u6da8\u8dcc\u5e45\u9608\u503c（%）'), { target: { value: '3.5' } });
    fireEvent.change(screen.getByLabelText('\u4e25\u91cd\u7ea7\u522b'), { target: { value: 'critical' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: 'AAPL',
        alertType: 'price_change_percent',
        parameters: { direction: 'down', changePct: 3.5 },
        severity: 'critical',
      }));
    });
  });

  it('submits a volume_spike rule payload and supports disabled creation', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: 'msft' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'volume_spike' } });
    fireEvent.change(screen.getByLabelText('\u6210\u4ea4\u91cf\u653e\u5927\u500d\u6570'), { target: { value: '2.5' } });
    fireEvent.click(screen.getByLabelText('\u521b\u5efa\u540e\u7acb\u5373\u542f\u7528'));
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: 'MSFT',
        alertType: 'volume_spike',
        parameters: { multiplier: 2.5 },
        enabled: false,
      }));
    });
  });

  it('submits technical indicator rule payloads', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'macd_cross' } });
    fireEvent.change(screen.getByLabelText('\u4ea4\u53c9\u65b9\u5411'), { target: { value: 'bearish_cross' } });
    fireEvent.change(screen.getByLabelText('\u5feb\u7ebf\u5468\u671f'), { target: { value: '6' } });
    fireEvent.change(screen.getByLabelText('\u6162\u7ebf\u5468\u671f'), { target: { value: '13' } });
    fireEvent.change(screen.getByLabelText('\u4fe1\u53f7\u5468\u671f'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: '600519',
        alertType: 'macd_cross',
        parameters: {
          direction: 'bearish_cross',
          fastPeriod: 6,
          slowPeriod: 13,
          signalPeriod: 5,
        },
      }));
    });
  });

  it('rejects invalid technical indicator boundaries before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'rsi_threshold' } });
    fireEvent.change(screen.getByLabelText('RSI \u9608\u503c'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(screen.getByRole('alert')).toHaveTextContent('RSI \u9608\u503c\u5fc5\u987b\u5728 0 \u5230 100 \u4e4b\u95f4');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects indicator period combinations that exceed fetchable history', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'macd_cross' } });
    fireEvent.change(screen.getByLabelText('\u5feb\u7ebf\u5468\u671f'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('\u6162\u7ebf\u5468\u671f'), { target: { value: '250' } });
    fireEvent.change(screen.getByLabelText('\u4fe1\u53f7\u5468\u671f'), { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(screen.getByRole('alert')).toHaveTextContent('MACD \u5468\u671f\u7ec4\u5408\u9700\u8981 501 \u6839\u65e5\u7ebf，\u6700\u591a\u652f\u6301 365 \u6839');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects empty required technical indicator thresholds before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'rsi_threshold' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(screen.getByRole('alert')).toHaveTextContent('RSI \u9608\u503c\u4e0d\u80fd\u4e3a\u7a7a');
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'cci_threshold' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(screen.getByRole('alert')).toHaveTextContent('CCI \u9608\u503c\u4e0d\u80fd\u4e3a\u7a7a');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects invalid numeric thresholds before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(screen.getByRole('alert')).toHaveTextContent('\u4ef7\u683c\u9608\u503c\u5fc5\u987b\u662f\u5927\u4e8e 0 \u7684\u6570\u5b57');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects invalid stock code format before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: 'aapl-2026' } });
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    expect(screen.getByRole('alert')).toHaveTextContent('\u80a1\u7968\u4ee3\u7801\u683c\u5f0f\u4e0d\u6b63\u786e');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('filters alert types and submits a watchlist rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u76ee\u6807\u8303\u56f4'), { target: { value: 'watchlist' } });
    expect(screen.queryByText('\u7ec4\u5408\u6b62\u635f')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        targetScope: 'watchlist',
        target: 'default',
        alertType: 'price_cross',
        parameters: { direction: 'above', price: 10 },
      }));
    });
  });

  it('loads accounts and submits portfolio stop-loss mode', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u76ee\u6807\u8303\u56f4'), { target: { value: 'portfolio_account' } });
    await waitFor(() => expect(getAccounts).toHaveBeenCalledWith(false));
    expect(screen.queryByText('\u4ef7\u683c\u7a81\u7834')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('\u8d26\u6237'), { target: { value: '9' } });
    fireEvent.change(screen.getByLabelText('\u6b62\u635f\u6a21\u5f0f'), { target: { value: 'breach' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        targetScope: 'portfolio_account',
        target: '9',
        alertType: 'portfolio_stop_loss',
        parameters: { mode: 'breach' },
      }));
    });
  });

  it('renders portfolio alert type options in English UI mode', async () => {
    renderEnglishForm();

    fireEvent.change(screen.getByLabelText('Target scope'), { target: { value: 'portfolio_account' } });

    await waitFor(() => expect(getAccounts).toHaveBeenCalledWith(false));
    expect(screen.getByRole('option', { name: 'Portfolio drawdown' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Portfolio stop loss' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Info' })).toBeInTheDocument();
    expect(screen.queryByText('\u7ec4\u5408\u56de\u64a4')).not.toBeInTheDocument();
  });

  it('shows JP/KR options for market region in Chinese UI mode', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u76ee\u6807\u8303\u56f4'), { target: { value: 'market' } });

    expect(screen.getByRole('option', { name: 'A \u80a1（cn）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u6e2f\u80a1（hk）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u7f8e\u80a1（us）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u65e5\u80a1（jp）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u97e9\u80a1（kr）' })).toBeInTheDocument();
  });

  it('submits a market light status rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u76ee\u6807\u8303\u56f4'), { target: { value: 'market' } });
    expect(screen.getByRole('option', { name: 'A \u80a1（cn）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u6e2f\u80a1（hk）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u7f8e\u80a1（us）' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '\u65e5\u80a1（jp）' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '\u97e9\u80a1（kr）' })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('\u5e02\u573a\u533a\u57df'), { target: { value: 'hk' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        targetScope: 'market',
        target: 'hk',
        alertType: 'market_light_status',
        parameters: { statuses: ['red', 'yellow'] },
      }));
    });
  });

  it('keeps JP/KR out of market light options in English UI mode', () => {
    renderEnglishForm();

    fireEvent.change(screen.getByLabelText('Target scope'), { target: { value: 'market' } });

    expect(screen.getByRole('option', { name: 'A-shares (cn)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Hong Kong (hk)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'US (us)' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Japan (jp)' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Korea (kr)' })).not.toBeInTheDocument();
  });

  it('submits a market light score-drop rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u76ee\u6807\u8303\u56f4'), { target: { value: 'market' } });
    fireEvent.change(screen.getByLabelText('\u5e02\u573a\u533a\u57df'), { target: { value: 'us' } });
    fireEvent.change(screen.getByLabelText('\u89c4\u5219\u7c7b\u578b'), { target: { value: 'market_light_score_drop' } });
    fireEvent.change(screen.getByLabelText('Score \u4e0b\u964d\u9608\u503c'), { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        targetScope: 'market',
        target: 'us',
        alertType: 'market_light_score_drop',
        parameters: { minDrop: 12 },
      }));
    });
  });

  it('keeps all account option when account loading fails', async () => {
    getAccounts.mockRejectedValueOnce(new Error('boom'));
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u76ee\u6807\u8303\u56f4'), { target: { value: 'portfolio_holdings' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.getByLabelText('\u8d26\u6237')).toHaveValue('all');
  });

  it('keeps form values when submit reports failure', async () => {
    onSubmit.mockResolvedValueOnce(false);
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('\u6807\u7684\u4ee3\u7801'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('\u4ef7\u683c\u9608\u503c'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '\u521b\u5efa\u89c4\u5219' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(screen.getByLabelText('\u6807\u7684\u4ee3\u7801')).toHaveValue('aapl');
    expect(screen.getByLabelText('\u4ef7\u683c\u9608\u503c')).toHaveValue(200);
  });
});
