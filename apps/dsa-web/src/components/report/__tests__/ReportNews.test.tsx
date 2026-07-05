import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import { ReportNews } from '../ReportNews';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getNews: vi.fn(),
  },
}));

describe('ReportNews', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders news items and refreshes with preserved subpanel styling', async () => {
    vi.mocked(historyApi.getNews).mockResolvedValue({
      total: 1,
      items: [
        {
          title: '\u8305\u53f0\u53d1\u5e03\u6700\u65b0\u7ecf\u8425\u6570\u636e',
          snippet: '\u516c\u53f8\u62ab\u9732\u5b63\u5ea6\u7ecf\u8425\u60c5\u51b5，\u5e02\u573a\u5173\u6ce8\u5ea6\u63d0\u5347。',
          url: 'https://example.com/news',
        },
      ],
    });

    const { container } = render(<ReportNews recordId={1} />);

    expect(await screen.findByText('\u8305\u53f0\u53d1\u5e03\u6700\u65b0\u7ecf\u8425\u6570\u636e')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '\u8df3\u8f6c' })).toHaveAttribute('href', 'https://example.com/news');
    expect(screen.getByText('\u76f8\u5173\u8d44\u8baf/\u540e\u7eed\u68c0\u7d22')).toBeVisible();
    expect(screen.getByText('\u6765\u6e90：\u62a5\u544a\u9875\u8865\u5145\u8d44\u8baf；\u662f\u5426\u7528\u4e8e\u5206\u6790\u4ee5\u8f93\u5165\u6570\u636e\u5757\u4e3a\u51c6。')).toBeVisible();
    expect(container.querySelector('.home-panel-card')).toBeTruthy();
    expect(container.querySelector('.home-subpanel')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '\u5237\u65b0' }));

    await waitFor(() => {
      expect(historyApi.getNews).toHaveBeenCalledTimes(2);
    });
  });

  it('renders the empty state when no news exists', async () => {
    vi.mocked(historyApi.getNews).mockResolvedValue({
      total: 0,
      items: [],
    });

    render(<ReportNews recordId={1} />);

    expect(await screen.findByText('\u6682\u65e0\u76f8\u5173\u8d44\u8baf')).toBeInTheDocument();
    expect(screen.getByText('\u53ef\u7a0d\u540e\u5237\u65b0\u4ee5\u83b7\u53d6\u6700\u65b0\u8d44\u8baf。')).toBeInTheDocument();
  });

  it('localizes the empty state description for english reports', async () => {
    vi.mocked(historyApi.getNews).mockResolvedValue({
      total: 0,
      items: [],
    });

    render(<ReportNews recordId={1} language="en" />);

    expect(await screen.findByText('No related news')).toBeInTheDocument();
    expect(screen.getByText('Refresh later to check for the latest updates.')).toBeInTheDocument();
    expect(screen.getByText('Related news / follow-up retrieval')).toBeVisible();
  });

  it('renders the error state and supports retry', async () => {
    vi.mocked(historyApi.getNews)
      .mockRejectedValueOnce(new Error('network failed'))
      .mockResolvedValueOnce({
        total: 1,
        items: [
          {
            title: '\u91cd\u8bd5\u6210\u529f',
            snippet: '\u7b2c\u4e8c\u6b21\u8bf7\u6c42\u6210\u529f\u8fd4\u56de。',
            url: 'https://example.com/retry',
          },
        ],
      });

    render(<ReportNews recordId={1} />);

    expect(await screen.findByRole('alert')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u91cd\u8bd5' }));

    expect(await screen.findByText('\u91cd\u8bd5\u6210\u529f')).toBeInTheDocument();
  });
});
