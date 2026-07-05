import { describe, expect, it } from 'vitest';

import { getReportText, normalizeReportLanguage } from '../reportLanguage';
import { getSentimentLabel } from '../../types/analysis';

describe('reportLanguage ko support', () => {
  it('normalizes ko and falls back to English for unknown', () => {
    expect(normalizeReportLanguage('ko')).toBe('en');
    expect(normalizeReportLanguage('en')).toBe('en');
    expect(normalizeReportLanguage('fr')).toBe('en');
    expect(normalizeReportLanguage(undefined)).toBe('en');
  });

  it('returns English report copy for ko compatibility input', () => {
    const ko = getReportText('ko');
    expect(ko.keyInsights).toBe('KEY INSIGHTS');
    expect(ko.actionAdvice).toBe('Action Advice');
    expect(ko.fullReport).toBe('Full Analysis Report');
  });

  it('keeps zh/en report copy in English', () => {
    expect(getReportText('zh').keyInsights).toBe('KEY INSIGHTS');
    expect(getReportText('en').keyInsights).toBe('KEY INSIGHTS');
  });

  it('returns Korean sentiment labels by band', () => {
    expect(getSentimentLabel(90, normalizeReportLanguage('ko'))).toBe('Very Bullish');
    expect(getSentimentLabel(50, normalizeReportLanguage('ko'))).toBe('Neutral');
    expect(getSentimentLabel(10, normalizeReportLanguage('ko'))).toBe('Very Bearish');
    expect(getSentimentLabel(90, 'en')).toBe('Very Bullish');
  });
});
