import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportOverview } from '../ReportOverview';

const baseMeta = {
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  reportType: 'detailed' as const,
  reportLanguage: 'zh' as const,
  createdAt: '2026-03-21T08:00:00Z',
};

const baseSummary = {
  analysisSummary: '\u8d8b\u52bf\u7ef4\u6301\u5f3a\u52bf',
  operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf\u4e70\u70b9',
  trendPrediction: '\u77ed\u7ebf\u9707\u8361\u504f\u5f3a',
  sentimentScore: 78,
};

describe('ReportOverview', () => {
  it('renders final market phase and partial-bar labels from report metadata', () => {
    render(
      <ReportOverview
        meta={{
          ...baseMeta,
          marketPhaseSummary: {
            market: 'cn',
            phase: 'intraday',
            marketLocalTime: '2026-03-21T10:30:00+08:00',
            sessionDate: '2026-03-21',
            effectiveDailyBarDate: '2026-03-20',
            isTradingDay: true,
            isMarketOpenNow: true,
            isPartialBar: true,
            minutesToOpen: null,
            minutesToClose: 150,
            triggerSource: 'api',
            analysisIntent: 'auto',
            warnings: [],
          },
        }}
        summary={baseSummary}
      />,
    );

    expect(screen.getByLabelText('\u5e02\u573a\u9636\u6bb5: CN · \u76d8\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('\u5e02\u573a\u9636\u6bb5: CN · \u76d8\u4e2d')).toBeVisible();
    expect(screen.getByLabelText('\u65e5\u7ebf\u672a\u5b8c\u6210')).toBeInTheDocument();
  });

  it('renders English final market phase and partial-bar labels', () => {
    render(
      <ReportOverview
        meta={{
          ...baseMeta,
          reportLanguage: 'en',
          marketPhaseSummary: {
            market: 'us',
            phase: 'postmarket',
            marketLocalTime: '2026-03-21T16:30:00-04:00',
            sessionDate: '2026-03-21',
            effectiveDailyBarDate: '2026-03-21',
            isTradingDay: true,
            isMarketOpenNow: false,
            isPartialBar: true,
            minutesToOpen: null,
            minutesToClose: null,
            triggerSource: 'api',
            analysisIntent: 'auto',
            warnings: [],
          },
        }}
        summary={baseSummary}
      />,
    );

    expect(screen.getByLabelText('Market phase: US · Post-market')).toBeInTheDocument();
    expect(screen.getByLabelText('Partial bar')).toBeInTheDocument();
  });

  it('renders unknown final phase without partial-bar label', () => {
    render(
      <ReportOverview
        meta={{
          ...baseMeta,
          marketPhaseSummary: {
            market: null,
            phase: 'unknown',
            marketLocalTime: null,
            sessionDate: null,
            effectiveDailyBarDate: null,
            isTradingDay: null,
            isMarketOpenNow: null,
            isPartialBar: false,
            minutesToOpen: null,
            minutesToClose: null,
            triggerSource: 'api',
            analysisIntent: 'auto',
            warnings: ['calendar_unavailable'],
          },
        }}
        summary={baseSummary}
      />,
    );

    expect(screen.getByText('\u5e02\u573a\u9636\u6bb5: \u9636\u6bb5\u672a\u77e5')).toBeVisible();
    expect(screen.queryByText('\u65e5\u7ebf\u672a\u5b8c\u6210')).not.toBeInTheDocument();
  });

  it('does not render a market phase placeholder for legacy reports', () => {
    render(<ReportOverview meta={baseMeta} summary={baseSummary} />);

    expect(screen.queryByText(/\u5e02\u573a\u9636\u6bb5/)).not.toBeInTheDocument();
    expect(screen.queryByText('\u65e5\u7ebf\u672a\u5b8c\u6210')).not.toBeInTheDocument();
  });

  it('renders related boards with leading and lagging markers', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: ' \u767d\u9152 ', type: '\u884c\u4e1a' },
            { name: '\u6d88\u8d39', type: '\u6982\u5ff5' },
            { name: '\u65b0\u80fd\u6e90' },
          ],
          sectorRankings: {
            top: [{ name: '\u767d\u9152', changePct: 2.31 }],
            bottom: [{ name: '\u65b0\u80fd\u6e90', changePct: -1.2 }],
          },
          conceptRankings: {
            top: [{ name: '\u6d88\u8d39', changePct: 4.56 }],
            bottom: [],
          },
        }}
      />,
    );

    expect(screen.getByText('\u5173\u8054\u677f\u5757')).toBeInTheDocument();
    expect(screen.getByText('\u767d\u9152')).toBeInTheDocument();
    expect(screen.getAllByText('\u9886\u6da8')).toHaveLength(2);
    expect(screen.getByText('+2.31%')).toBeInTheDocument();
    expect(screen.getByText('+4.56%')).toBeInTheDocument();
    expect(screen.getByText('\u9886\u8dcc')).toBeInTheDocument();
    expect(screen.getByText('-1.20%')).toBeInTheDocument();
    expect(screen.queryByText('\u4e2d\u6027')).not.toBeInTheDocument();
  });

  it('does not apply industry ranking to a concept board with the same name', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: '\u767d\u9152', type: '\u6982\u5ff5' }],
          sectorRankings: {
            top: [{ name: '\u767d\u9152', changePct: 2.31 }],
            bottom: [],
          },
          conceptRankings: {
            top: [],
            bottom: [{ name: '\u767d\u9152', changePct: -3.2 }],
          },
        }}
      />,
    );

    expect(screen.getByText('\u767d\u9152')).toBeInTheDocument();
    expect(screen.getByText('\u5173\u8054\u677f\u5757')).toBeInTheDocument();
    expect(screen.getByText('\u9886\u8dcc')).toBeInTheDocument();
    expect(screen.getByText('-3.20%')).toBeInTheDocument();
    expect(screen.queryByText('+2.31%')).not.toBeInTheDocument();
  });

  it('renders untyped boards in a single related-board row with ranking matches', () => {
    const conceptRankingBoard = '\u699c\u5355\u6837\u4f8b\u7532';
    const fallbackConceptBoard = '\u672a\u6807\u6ce8\u677f\u5757';
    const sectorRankingBoard = '\u699c\u5355\u6837\u4f8b\u4e59';

    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: conceptRankingBoard },
            { name: fallbackConceptBoard },
            { name: sectorRankingBoard },
          ],
          sectorRankings: {
            top: [{ name: sectorRankingBoard, changePct: 1.11 }],
            bottom: [],
          },
          conceptRankings: {
            top: [{ name: conceptRankingBoard, changePct: 3.21 }],
            bottom: [],
          },
        }}
      />,
    );

    const relatedBoardsRegion = screen.getByRole('region', { name: '\u5173\u8054\u677f\u5757' });

    expect(within(relatedBoardsRegion).getByText(sectorRankingBoard)).toBeInTheDocument();
    expect(within(relatedBoardsRegion).getByText(conceptRankingBoard)).toBeInTheDocument();
    expect(within(relatedBoardsRegion).getByText(fallbackConceptBoard)).toBeInTheDocument();
    expect(within(relatedBoardsRegion).getByText('+3.21%')).toBeInTheDocument();
  });

  it('places related boards below action advice in one horizontal row', () => {
    const { container } = render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: '\u767d\u9152', type: '\u884c\u4e1a' },
            { name: '\u6d88\u8d39', type: '\u6982\u5ff5' },
            { name: '\u9ad8\u7aef\u5236\u9020' },
            { name: '\u6caa\u80a1\u901a' },
          ],
        }}
      />,
    );

    const actionAdviceTitle = screen.getByText('\u64cd\u4f5c\u5efa\u8bae');
    const relatedBoardsRegion = screen.getByRole('region', { name: '\u5173\u8054\u677f\u5757' });
    const boardLists = container.querySelectorAll('.home-related-board-list');

    expect(actionAdviceTitle.compareDocumentPosition(relatedBoardsRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('\u5173\u8054\u677f\u5757')).toBeInTheDocument();
    expect(screen.getByText('\u6caa\u80a1\u901a')).toBeInTheDocument();
    expect(boardLists[0]).toHaveClass(
      'flex-nowrap',
      'overflow-x-auto',
      'w-full',
      'min-w-0',
      'max-w-full',
      'touch-pan-x',
    );
  });

  it('shows board list when rankings are unavailable', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: '\u534a\u5bfc\u4f53', type: '\u884c\u4e1a' }],
        }}
      />,
    );

    expect(screen.getByText('\u5173\u8054\u677f\u5757')).toBeInTheDocument();
    expect(screen.getByText('\u534a\u5bfc\u4f53')).toBeInTheDocument();
    expect(screen.queryByText('\u4e2d\u6027')).not.toBeInTheDocument();
    expect(screen.queryByText('\u9886\u6da8')).not.toBeInTheDocument();
    expect(screen.queryByText('\u9886\u8dcc')).not.toBeInTheDocument();
  });

  it('shows only the board when a matching ranking has no change percent', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: '\u767d\u9152', type: '\u884c\u4e1a' }],
          sectorRankings: {
            top: [{ name: '\u767d\u9152' }],
            bottom: [],
          },
        }}
      />,
    );

    expect(screen.getByText('\u5173\u8054\u677f\u5757')).toBeInTheDocument();
    expect(screen.getByText('\u767d\u9152')).toBeInTheDocument();
    expect(screen.queryByText('\u884c\u4e1a')).not.toBeInTheDocument();
    expect(screen.queryByText('\u9886\u6da8')).not.toBeInTheDocument();
    expect(screen.queryByText('\u9886\u8dcc')).not.toBeInTheDocument();
  });

  it('hides related boards section when no boards are available', () => {
    render(<ReportOverview meta={baseMeta} summary={baseSummary} details={{ belongBoards: [] }} />);

    expect(screen.queryByText('\u677f\u5757\u8054\u52a8')).not.toBeInTheDocument();
  });

  it('fails open on malformed ranking payloads', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: ' \u767d\u9152 ' }],
          sectorRankings: {
            top: {} as unknown as never[],
            bottom: [{ name: '\u767d\u9152', changePct: '-2.5%' as unknown as number }],
          },
        }}
      />,
    );

    expect(screen.getByText('\u5173\u8054\u677f\u5757')).toBeInTheDocument();
    expect(screen.getByText('\u767d\u9152')).toBeInTheDocument();
    expect(screen.getByText('\u9886\u8dcc')).toBeInTheDocument();
    expect(screen.getByText('-2.50%')).toBeInTheDocument();
  });
});
