import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import type { DecisionSignalItem } from '../../../types/decisionSignals';
import { DecisionSignalCard, DecisionSignalDetails, PortfolioSignalSummary } from '../DecisionSignalDisplay';

const signal: DecisionSignalItem = {
  id: 7,
  stockCode: '600519',
  stockName: '\u8d35\u5dde\u8305\u53f0',
  market: 'cn',
  sourceType: 'analysis',
  sourceReportId: 3001,
  marketPhase: 'intraday',
  triggerSource: 'web',
  action: 'hold',
  actionLabel: null,
  confidence: 0.72,
  score: 82,
  horizon: '3d',
  entryLow: 1600,
  entryHigh: 1620,
  stopLoss: 1550,
  targetPrice: 1700,
  invalidation: '\u8dcc\u7834 1550',
  watchConditions: '\u89c2\u5bdf\u6210\u4ea4\u91cf',
  reason: '\u8d8b\u52bf\u4fdd\u6301',
  riskSummary: '\u653e\u91cf\u4e0b\u8dcc\u98ce\u9669',
  catalystSummary: '\u4e1a\u7ee9\u7a97\u53e3',
  evidence: { technical: 'ma' },
  dataQualitySummary: { freshness: 'ok' },
  planQuality: 'complete',
  status: 'active',
  expiresAt: '2026-06-18T09:30:00',
  createdAt: '2026-06-17T09:30:00',
  updatedAt: '2026-06-17T09:30:00',
  metadata: { source: 'test' },
};

function renderCard(onSelect?: (item: DecisionSignalItem) => void) {
  window.localStorage.setItem('dsa.uiLanguage', 'zh');
  render(
    <UiLanguageProvider>
      <DecisionSignalCard item={signal} onSelect={onSelect} />
    </UiLanguageProvider>,
  );
}

describe('DecisionSignalCard', () => {
  it('uses a dedicated details button for interactive cards', () => {
    const onSelect = vi.fn();
    renderCard(onSelect);

    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0').closest('button')).toBeNull();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('1600 - 1620')).toBeInTheDocument();
    expect(screen.getByText('\u4e1a\u7ee9\u7a97\u53e3')).toBeInTheDocument();
    expect(screen.getByText('\u8dcc\u7834 1550')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' }));

    expect(onSelect).toHaveBeenCalledWith(signal);
    expect(screen.getByText('3 \u65e5')).toBeInTheDocument();
    expect(screen.getByText('\u8ba1\u5212\u8d28\u91cf: \u5b8c\u6574')).toBeInTheDocument();
    expect(screen.getByText('\u9636\u6bb5: \u76d8\u4e2d')).toBeInTheDocument();
    expect(screen.queryByText('3d')).not.toBeInTheDocument();
    expect(screen.queryByText('complete')).not.toBeInTheDocument();
    expect(screen.queryByText('intraday')).not.toBeInTheDocument();
  });

  it('renders non-interactive cards without a details button', () => {
    renderCard();

    expect(screen.getByText('\u8d35\u5dde\u8305\u53f0')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u67e5\u770b \u8d35\u5dde\u8305\u53f0 AI \u5efa\u8bae\u8be6\u60c5' })).not.toBeInTheDocument();
  });

  it('hides missing optional plan text for sparse legacy signals', () => {
    window.localStorage.setItem('dsa.uiLanguage', 'zh');
    render(
      <UiLanguageProvider>
        <DecisionSignalCard
          item={{
            ...signal,
            score: null,
            confidence: null,
            horizon: null,
            entryLow: null,
            entryHigh: null,
            stopLoss: null,
            targetPrice: null,
            invalidation: null,
            watchConditions: null,
            catalystSummary: null,
          }}
        />
      </UiLanguageProvider>,
    );

    expect(screen.getByText('\u8bc4\u5206')).toBeInTheDocument();
    expect(screen.getByText('\u7f6e\u4fe1\u5ea6')).toBeInTheDocument();
    expect(screen.getByText('\u5468\u671f')).toBeInTheDocument();
    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText('\u5165\u573a\u533a\u95f4')).not.toBeInTheDocument();
    expect(screen.queryByText('\u6b62\u635f')).not.toBeInTheDocument();
    expect(screen.queryByText('\u76ee\u6807\u4ef7')).not.toBeInTheDocument();
    expect(screen.queryByText('\u50ac\u5316')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5931\u6548\u6761\u4ef6')).not.toBeInTheDocument();
  });
});

describe('DecisionSignalDetails', () => {
  it('renders secondary-only entry_high as a valid entry range', () => {
    window.localStorage.setItem('dsa.uiLanguage', 'zh');
    render(
      <UiLanguageProvider>
        <DecisionSignalDetails item={{ ...signal, entryLow: null, entryHigh: 1680 }} />
      </UiLanguageProvider>,
    );

    const entryRange = screen.getByText('\u5165\u573a\u533a\u95f4').closest('div');
    expect(entryRange).not.toBeNull();
    expect(entryRange as HTMLElement).toHaveTextContent('1680');
    expect(screen.getByText('3 \u65e5')).toBeInTheDocument();
    expect(screen.getByText('\u5b8c\u6574')).toBeInTheDocument();
    expect(screen.getByText('\u76d8\u4e2d')).toBeInTheDocument();
    expect(screen.queryByText('3d')).not.toBeInTheDocument();
  });

  it('renders opaque JSON fields without creating html nodes from their string values', () => {
    window.localStorage.setItem('dsa.uiLanguage', 'zh');
    const { container } = render(
      <UiLanguageProvider>
        <DecisionSignalDetails
          item={{
            ...signal,
            evidence: { headline: '<img src=x onerror="window.__signalEvidenceXss = true">' },
            dataQualitySummary: { note: '<script>window.__signalQualityXss = true</script>' },
            metadata: { raw: '<svg onload="window.__signalMetadataXss = true"></svg>' },
          }}
        />
      </UiLanguageProvider>,
    );

    expect(container.textContent).toContain('<img src=x onerror=\\"window.__signalEvidenceXss = true\\">');
    expect(container.textContent).toContain('<script>window.__signalQualityXss = true</script>');
    expect(container.textContent).toContain('<svg onload=\\"window.__signalMetadataXss = true\\"></svg>');
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('svg')).toBeNull();
    expect(container.querySelector('[onerror]')).toBeNull();
    expect(container.querySelector('[onload]')).toBeNull();
  });

  it('renders outcome results and feedback controls', () => {
    const onFeedbackSubmit = vi.fn();
    window.localStorage.setItem('dsa.uiLanguage', 'zh');
    render(
      <UiLanguageProvider>
        <DecisionSignalDetails
          item={signal}
          outcomes={[
            {
              id: 31,
              signalId: 7,
              horizon: '3d',
              engineVersion: 'decision-signal-v1',
              evalStatus: 'completed',
              outcome: 'hit',
              directionExpected: 'not_down',
              directionCorrect: true,
              anchorDate: '2024-01-02',
              evalWindowDays: 3,
              startPrice: 100,
              endClose: 105,
              stockReturnPct: 5,
              action: 'hold',
              market: 'cn',
              planQuality: 'complete',
              dataQualityLevel: 'good',
              holdingState: 'holding',
            },
          ]}
          feedback={{
            signalId: 7,
            feedbackValue: 'useful',
            reasonCode: null,
            note: null,
            source: 'web',
          }}
          onFeedbackSubmit={onFeedbackSubmit}
        />
      </UiLanguageProvider>,
    );

    expect(screen.getByText('\u540e\u9a8c\u7ed3\u679c')).toBeInTheDocument();
    expect(screen.getAllByText('3 \u65e5').length).toBeGreaterThan(1);
    expect(screen.getByText('\u547d\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('5%')).toBeInTheDocument();
    expect(screen.getByText('\u50ac\u5316')).toBeInTheDocument();
    expect(screen.getByText('\u4e1a\u7ee9\u7a97\u53e3')).toBeInTheDocument();
    expect(screen.getByText('\u5931\u6548\u6761\u4ef6')).toBeInTheDocument();
    expect(screen.getByText('\u8dcc\u7834 1550')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u65e0\u7528' }));
    expect(onFeedbackSubmit).toHaveBeenCalledWith('not_useful');
  });

  it('renders portfolio signal horizon using the current UI language', () => {
    window.localStorage.setItem('dsa.uiLanguage', 'en');
    render(
      <UiLanguageProvider>
        <PortfolioSignalSummary item={{ ...signal, horizon: '10d', action: 'sell', actionLabel: null }} />
      </UiLanguageProvider>,
    );

    expect(screen.getByText('10 days')).toBeInTheDocument();
    expect(screen.queryByText('10d')).not.toBeInTheDocument();
  });
});
