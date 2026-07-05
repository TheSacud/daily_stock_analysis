import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IntelligentImport } from '../IntelligentImport';
import { SystemConfigConflictError } from '../../../api/systemConfig';

const { parseImport, update, onMerged } = vi.hoisted(() => ({
  parseImport: vi.fn(),
  update: vi.fn(),
  onMerged: vi.fn(),
}));

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    parseImport,
    extractFromImage: vi.fn(),
  },
}));

vi.mock('../../../api/systemConfig', async () => {
  const actual = await vi.importActual<typeof import('../../../api/systemConfig')>('../../../api/systemConfig');
  return {
    ...actual,
    systemConfigApi: {
      ...actual.systemConfigApi,
      update,
    },
  };
});

describe('IntelligentImport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens the matching hidden file input when the picker buttons are clicked', () => {
    const { container } = render(
      <IntelligentImport
        stockListValue="SH600000"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
      />,
    );

    const inputs = container.querySelectorAll('input[type="file"]');
    expect(inputs).toHaveLength(2);

    const imageClick = vi.fn();
    const dataClick = vi.fn();

    Object.defineProperty(inputs[0], 'click', {
      value: imageClick,
      configurable: true,
    });
    Object.defineProperty(inputs[1], 'click', {
      value: dataClick,
      configurable: true,
    });

    fireEvent.click(screen.getByRole('button', { name: '\u9009\u62e9\u56fe\u7247' }));
    fireEvent.click(screen.getByRole('button', { name: '\u9009\u62e9\u6587\u4ef6' }));

    expect(imageClick).toHaveBeenCalledTimes(1);
    expect(dataClick).toHaveBeenCalledTimes(1);
  });

  it('does not open hidden file inputs when the import actions are disabled', () => {
    const { container } = render(
      <IntelligentImport
        stockListValue="SH600000"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
        disabled
      />,
    );

    const inputs = container.querySelectorAll('input[type="file"]');
    expect(inputs).toHaveLength(2);

    const imageClick = vi.fn();
    const dataClick = vi.fn();

    Object.defineProperty(inputs[0], 'click', {
      value: imageClick,
      configurable: true,
    });
    Object.defineProperty(inputs[1], 'click', {
      value: dataClick,
      configurable: true,
    });

    fireEvent.click(screen.getByRole('button', { name: '\u9009\u62e9\u56fe\u7247' }));
    fireEvent.click(screen.getByRole('button', { name: '\u9009\u62e9\u6587\u4ef6' }));

    expect(imageClick).not.toHaveBeenCalled();
    expect(dataClick).not.toHaveBeenCalled();
  });

  it('refreshes config state after a config version conflict', async () => {
    parseImport.mockResolvedValue({
      items: [{ code: 'SZ000001', name: 'Ping An Bank', confidence: 'high' }],
      codes: [],
    });
    update.mockRejectedValue(
      new SystemConfigConflictError('\u914d\u7f6e\u7248\u672c\u51b2\u7a81', 'v2'),
    );

    render(
      <IntelligentImport
        stockListValue="SH600000"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('\u6216\u7c98\u8d34 CSV/Excel \u590d\u5236\u7684\u6587\u672c...'), {
      target: { value: '000001' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u89e3\u6790' }));

    await screen.findByText('SZ000001');

    fireEvent.click(screen.getByRole('button', { name: '\u5408\u5e76\u5230\u81ea\u9009\u80a1' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(onMerged).toHaveBeenCalledWith('SH600000,SZ000001');
    });
    expect(await screen.findByText('\u914d\u7f6e\u5df2\u66f4\u65b0，\u8bf7\u518d\u6b21\u70b9\u51fb「\u5408\u5e76\u5230\u81ea\u9009\u80a1」')).toBeInTheDocument();
  });

  it('normalizes existing mixed separators when merging into watchlist', async () => {
    parseImport.mockResolvedValue({
      items: [{ code: 'HK00700', name: 'Tencent', confidence: 'high' }],
      codes: [],
    });
    update.mockResolvedValue({ success: true });

    render(
      <IntelligentImport
        stockListValue="SH600000，SH600519 AAPL"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('\u6216\u7c98\u8d34 CSV/Excel \u590d\u5236\u7684\u6587\u672c...'), {
      target: { value: 'HK00700' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u89e3\u6790' }));

    await screen.findByText('HK00700');

    fireEvent.click(screen.getByRole('button', { name: '\u5408\u5e76\u5230\u81ea\u9009\u80a1' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalledWith({
        configVersion: 'v1',
        maskToken: '******',
        reloadNow: true,
        items: [{ key: 'STOCK_LIST', value: 'SH600000,SH600519,AAPL,HK00700' }],
      });
    });
    await waitFor(() => {
      expect(onMerged).toHaveBeenCalledWith('SH600000,SH600519,AAPL,HK00700');
    });
  });
});
