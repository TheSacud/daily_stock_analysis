import type { DecisionAction } from '../types/analysis';

export type DecisionActionTone = 'success' | 'warning' | 'danger' | 'default';
export type DecisionActionLabelMap = Record<DecisionAction, string>;
export type DecisionActionLabelTextKey =
  | 'history.actionBuy'
  | 'history.actionAdd'
  | 'history.actionHold'
  | 'history.actionReduce'
  | 'history.actionSell'
  | 'history.actionWatch'
  | 'history.actionAvoid'
  | 'history.actionAlert';
export type DecisionActionLabelTranslator = (key: DecisionActionLabelTextKey) => string;

export const DEFAULT_DECISION_ACTION_LABELS: DecisionActionLabelMap = {
  buy: 'Buy',
  add: 'Add',
  hold: 'Hold',
  reduce: 'Reduce',
  sell: 'Sell',
  watch: 'Watch',
  avoid: 'Avoid',
  alert: 'Alert',
};

const resolveActionLabels = (labels?: Partial<DecisionActionLabelMap>): DecisionActionLabelMap => ({
  ...DEFAULT_DECISION_ACTION_LABELS,
  ...labels,
});

export const buildDecisionActionLabelMap = (
  t: DecisionActionLabelTranslator,
): DecisionActionLabelMap => ({
  buy: t('history.actionBuy'),
  add: t('history.actionAdd'),
  hold: t('history.actionHold'),
  reduce: t('history.actionReduce'),
  sell: t('history.actionSell'),
  watch: t('history.actionWatch'),
  avoid: t('history.actionAvoid'),
  alert: t('history.actionAlert'),
});

const toneForAction = (action: DecisionAction): DecisionActionTone => {
  if (action === 'buy' || action === 'add' || action === 'hold') return 'success';
  if (action === 'sell' || action === 'reduce') return 'danger';
  return 'warning';
};

const includesAny = (value: string, phrases: readonly string[]): boolean =>
  phrases.some((phrase) => value.includes(phrase));

const normalizeEnglishAdvice = (value: string): string =>
  value.toLowerCase().replace(/[_-]/g, ' ');

const maskEnglishFinancialCompounds = (value: string): string =>
  value
    .replace(/(^|[^a-z0-9_])buy\s*back(?=$|[^a-z0-9_])/g, '$1financialcompound')
    .replace(/(^|[^a-z0-9_])sell\s*off(?=$|[^a-z0-9_])/g, '$1financialcompound');

const matchesEnglishTerm = (value: string, terms: readonly string[]): boolean =>
  terms.some((term) => new RegExp(`(^|[^a-z0-9_])${term}(?=$|[^a-z0-9_])`).test(value));

const matchesEnglishNegatedAction = (value: string, terms: readonly string[]): boolean => {
  const negationPrefix = String.raw`(?:not\s+(?:a\s+|an\s+|to\s+)?|no\s+(?:need\s+to\s+)?|need\s+not\s+|cannot\s+|can't\s+|cant\s+|do\s+not\s+|don't\s+|dont\s+)`;
  return terms.some((term) =>
    new RegExp(`(^|[^a-z0-9_])${negationPrefix}${term}(?=$|[^a-z0-9_])`).test(value),
  );
};

const hasEnglishAvoidedHoldAction = (value: string): boolean => {
  const terms = String.raw`(?:adding|accumulating|selling|reducing|trimming)`;
  return new RegExp(`(^|[^a-z0-9_])avoid\\s+${terms}(?=$|[^a-z0-9_])`).test(value);
};

const hasEnglishDeferredAction = (value: string): boolean => {
  const terms = String.raw`(?:buy|add|accumulate|sell|reduce|trim)`;
  return (
    new RegExp(`(^|[^a-z0-9_])wait(?:ing)?\\s+to\\s+${terms}(?=$|[^a-z0-9_])`).test(value) ||
    new RegExp(`(^|[^a-z0-9_])waiting\\s+(?:for|until)\\b.*?${terms}(?=$|[^a-z0-9_])`).test(value)
  );
};

export const getLegacyDecisionActionLabel = (
  advice?: string | null,
  labels?: Partial<DecisionActionLabelMap>,
): string | null => {
  const action = getLegacyDecisionAction(advice);
  if (!action) return null;
  return resolveActionLabels(labels)[action];
};

export const getLegacyDecisionAction = (advice?: string | null): DecisionAction | null => {
  const normalized = advice?.trim();
  if (!normalized) return null;
  const lower = maskEnglishFinancialCompounds(normalizeEnglishAdvice(normalized));

  if (hasEnglishDeferredAction(lower)) {
    return null;
  }

  if (
    includesAny(normalized, [
      '\u6682\u4e0d\u4e70\u5165',
      '\u4e0d\u8981\u4e70\u5165',
      '\u4e0d\u5b9c\u4e70\u5165',
      '\u5148\u4e0d\u4e70\u5165',
      '\u65e0\u9700\u4e70\u5165',
      '\u65e0\u987b\u4e70\u5165',
      '\u4e0d\u5efa\u8bae\u5efa\u4ed3',
      '\u6682\u4e0d\u5efa\u4ed3',
      '\u4e0d\u8981\u5efa\u4ed3',
      '\u4e0d\u5b9c\u5efa\u4ed3',
      '\u5148\u4e0d\u5efa\u4ed3',
      '\u65e0\u9700\u5efa\u4ed3',
      '\u65e0\u987b\u5efa\u4ed3',
      '\u4e0d\u5efa\u8bae\u5e03\u5c40',
      '\u6682\u4e0d\u5e03\u5c40',
      '\u4e0d\u8981\u5e03\u5c40',
      '\u4e0d\u5b9c\u5e03\u5c40',
      '\u5148\u4e0d\u5e03\u5c40',
      '\u65e0\u9700\u5e03\u5c40',
      '\u65e0\u987b\u5e03\u5c40',
    ]) ||
    matchesEnglishNegatedAction(lower, ['buy'])
  ) {
    return 'avoid';
  }
  if (
    includesAny(normalized, [
      '\u4e0d\u5efa\u8bae\u52a0\u4ed3',
      '\u65e0\u9700\u52a0\u4ed3',
      '\u65e0\u987b\u52a0\u4ed3',
      '\u4e0d\u8981\u52a0\u4ed3',
      '\u4e0d\u5b9c\u52a0\u4ed3',
      '\u6682\u4e0d\u52a0\u4ed3',
      '\u4e0d\u5efa\u8bae\u589e\u6301',
      '\u65e0\u9700\u589e\u6301',
      '\u65e0\u987b\u589e\u6301',
      '\u4e0d\u8981\u589e\u6301',
      '\u4e0d\u5b9c\u589e\u6301',
      '\u6682\u4e0d\u589e\u6301',
      '\u4e0d\u5efa\u8bae\u5356\u51fa',
      '\u65e0\u9700\u5356\u51fa',
      '\u65e0\u987b\u5356\u51fa',
      '\u4e0d\u8981\u5356\u51fa',
      '\u4e0d\u5b9c\u5356\u51fa',
      '\u6682\u4e0d\u5356\u51fa',
      '\u4e0d\u5efa\u8bae\u51cf\u4ed3',
      '\u65e0\u9700\u51cf\u4ed3',
      '\u65e0\u987b\u51cf\u4ed3',
      '\u4e0d\u8981\u51cf\u4ed3',
      '\u4e0d\u5b9c\u51cf\u4ed3',
      '\u6682\u4e0d\u51cf\u4ed3',
      '\u4e0d\u5efa\u8bae\u6e05\u4ed3',
      '\u65e0\u9700\u6e05\u4ed3',
      '\u65e0\u987b\u6e05\u4ed3',
      '\u4e0d\u8981\u6e05\u4ed3',
      '\u4e0d\u5b9c\u6e05\u4ed3',
      '\u6682\u4e0d\u6e05\u4ed3',
    ]) ||
    hasEnglishAvoidedHoldAction(lower) ||
    matchesEnglishNegatedAction(lower, ['add', 'accumulate', 'sell', 'reduce', 'trim'])
  ) {
    return 'hold';
  }
  const guardMatches = new Set<DecisionAction>();
  if (
    normalized.includes('\u4e0d\u5efa\u8bae\u4e70\u5165') ||
    normalized.includes('\u907f\u514d\u4e70\u5165') ||
    normalized.includes('\u56de\u907f') ||
    normalized.includes('\u89c4\u907f') ||
    matchesEnglishTerm(lower, ['avoid'])
  ) {
    guardMatches.add('avoid');
  }
  if (
    normalized.includes('\u98ce\u9669\u9884\u8b66') ||
    normalized.includes('\u89e6\u53d1\u544a\u8b66') ||
    normalized.includes('\u8b66\u60d5') ||
    lower.includes('risk alert') ||
    matchesEnglishTerm(lower, ['alert'])
  ) {
    guardMatches.add('alert');
  }
  if (guardMatches.size === 1) {
    return Array.from(guardMatches)[0];
  }
  if (guardMatches.size > 1) {
    return null;
  }

  const matches = new Set<DecisionAction>();
  if (normalized.includes('\u52a0\u4ed3') || normalized.includes('\u589e\u6301') || matchesEnglishTerm(lower, ['add', 'accumulate'])) {
    matches.add('add');
  }
  if (normalized.includes('\u51cf\u4ed3') || matchesEnglishTerm(lower, ['reduce', 'trim'])) {
    matches.add('reduce');
  }
  if (normalized.includes('\u5f3a\u70c8\u5356\u51fa') || normalized.includes('\u5356\u51fa') || normalized.includes('\u6e05\u4ed3') || matchesEnglishTerm(lower, ['sell'])) {
    matches.add('sell');
  }
  if (normalized.includes('\u6301\u6709') || normalized.includes('\u6d17\u76d8\u89c2\u5bdf') || matchesEnglishTerm(lower, ['hold'])) {
    matches.add('hold');
  }
  if (normalized.includes('\u89c2\u671b') || normalized.includes('\u7b49\u5f85') || matchesEnglishTerm(lower, ['watch', 'wait'])) {
    matches.add('watch');
  }
  if (normalized.includes('\u5f3a\u70c8\u4e70\u5165') || normalized.includes('\u4e70\u5165') || normalized.includes('\u5e03\u5c40') || normalized.includes('\u5efa\u4ed3') || matchesEnglishTerm(lower, ['buy'])) {
    matches.add('buy');
  }

  if (matches.size === 1) {
    return Array.from(matches)[0];
  }
  return null;
};

export const getDecisionActionLabel = (
  action?: DecisionAction | null,
  actionLabel?: string | null,
  legacyAdvice?: string | null,
  emptyLabel: string | null = 'Recommendation',
  labels?: Partial<DecisionActionLabelMap>,
): string | null => {
  const actionLabels = resolveActionLabels(labels);
  if (action) return actionLabels[action];
  const explicitLabel = actionLabel?.trim();
  if (explicitLabel) return explicitLabel;
  return getLegacyDecisionActionLabel(legacyAdvice, actionLabels) || emptyLabel;
};

export const getDecisionActionTone = (
  action?: DecisionAction | null,
  actionLabel?: string | null,
  legacyAdvice?: string | null,
): DecisionActionTone => {
  if (action) return toneForAction(action);

  const label = actionLabel?.trim() || '';
  if (label) {
    const lowerLabel = normalizeEnglishAdvice(label);
    if (label.includes('\u4e70') || label.includes('\u52a0\u4ed3') || label.includes('\u6301\u6709')) return 'success';
    if (label.includes('\u5356') || label.includes('\u51cf\u4ed3') || label.includes('\u6e05\u4ed3')) return 'danger';
    if (label.includes('\u89c2\u671b') || label.includes('\u7b49\u5f85') || label.includes('\u56de\u907f') || label.includes('\u9884\u8b66')) {
      return 'warning';
    }
    if (matchesEnglishTerm(lowerLabel, ['buy', 'add', 'hold'])) return 'success';
    if (matchesEnglishTerm(lowerLabel, ['sell', 'reduce', 'trim'])) return 'danger';
    if (matchesEnglishTerm(lowerLabel, ['watch', 'wait', 'avoid', 'alert'])) return 'warning';
    return 'default';
  }

  const legacyAction = getLegacyDecisionAction(legacyAdvice);
  if (legacyAction) return toneForAction(legacyAction);

  return 'default';
};
