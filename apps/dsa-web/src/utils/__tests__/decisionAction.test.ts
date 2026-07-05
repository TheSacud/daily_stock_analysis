import { describe, expect, it } from 'vitest';
import {
  type DecisionActionLabelMap,
  getDecisionActionLabel,
  getLegacyDecisionAction,
  getDecisionActionTone,
  getLegacyDecisionActionLabel,
} from '../decisionAction';

const englishLabels: DecisionActionLabelMap = {
  buy: 'Buy',
  add: 'Add',
  hold: 'Hold',
  reduce: 'Reduce',
  sell: 'Sell',
  watch: 'Watch',
  avoid: 'Avoid',
  alert: 'Alert',
};

describe('decisionAction helpers', () => {
  it('uses structured action taxonomy before server label and legacy advice text', () => {
    expect(getDecisionActionLabel('avoid', '\u56de\u907f', '\u4e70\u5165', '\u5efa\u8bae')).toBe('\u56de\u907f');
    expect(getDecisionActionLabel('sell', '\u4e70\u5165', null, 'Advice', englishLabels)).toBe('Sell');
    expect(getDecisionActionTone('sell', '\u4e70\u5165', null)).toBe('danger');
    expect(getDecisionActionLabel(null, '\u4e70\u5165', null, 'Advice', englishLabels)).toBe('\u4e70\u5165');
  });

  it('falls back to the action taxonomy label when actionLabel is absent', () => {
    expect(getDecisionActionLabel('add', null, '\u6301\u6709', '\u5efa\u8bae')).toBe('\u52a0\u4ed3');
    expect(getDecisionActionLabel('watch', null, '\u6301\u6709', 'Advice', englishLabels)).toBe('Watch');
  });

  it('keeps legacy fallback compatible with negated buy advice', () => {
    expect(getLegacyDecisionActionLabel('\u4e0d\u5efa\u8bae\u4e70\u5165，\u7b49\u5f85\u786e\u8ba4')).toBe('\u56de\u907f');
    expect(getDecisionActionLabel(null, null, '\u907f\u514d\u4e70\u5165', '\u5efa\u8bae')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('\u6682\u4e0d\u4e70\u5165，\u7b49\u5f85\u786e\u8ba4')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('\u5148\u4e0d\u5efa\u4ed3，\u7b49\u5f85\u653e\u91cf')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('\u65e0\u9700\u4e70\u5165，\u7b49\u5f85\u786e\u8ba4')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('\u65e0\u987b\u5efa\u4ed3，\u7ee7\u7eed\u89c2\u5bdf')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('\u65e0\u9700\u5e03\u5c40，\u7b49\u5f85\u7a81\u7834')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('no buy until breakout')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('no need to buy before confirmation')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('cannot buy before confirmation')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel("can't buy before confirmation")).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('not a buy yet')).toBe('\u56de\u907f');
    expect(getLegacyDecisionActionLabel('not a buy yet', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('not to buy', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('avoid buying', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('avoid buying into weakness', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('waiting to buy')).toBeNull();
  });

  it('keeps legacy fallback compatible with negated sell and add advice', () => {
    expect(getLegacyDecisionActionLabel('\u4e0d\u5efa\u8bae\u5356\u51fa，\u7ee7\u7eed\u89c2\u5bdf')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('\u6d17\u76d8\u89c2\u5bdf')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('\u6d17\u76d8\u89c2\u5bdf', englishLabels)).toBe('Hold');
    expect(getLegacyDecisionActionLabel('\u65e0\u9700\u51cf\u4ed3，\u7ef4\u6301\u4ed3\u4f4d')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('\u65e0\u987b\u51cf\u4ed3，\u7ef4\u6301\u4ed3\u4f4d')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('\u4e0d\u5efa\u8bae\u52a0\u4ed3，\u7b49\u5f85\u56de\u8e29')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('\u65e0\u987b\u52a0\u4ed3，\u7b49\u5f85\u56de\u8e29')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('no add before confirmation')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('cannot add before confirmation')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('no need to accumulate here')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel("can't accumulate here")).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('no sell before earnings')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('cannot sell before earnings')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('no need to reduce exposure')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel("can't reduce exposure")).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('no trim while trend holds')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('cannot trim while trend holds')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('not a sell yet')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('not a trim yet')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('not to sell')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('not to trim')).toBe('\u6301\u6709');
    expect(getLegacyDecisionActionLabel('not a trim yet', englishLabels)).toBe('Hold');
    expect(getLegacyDecisionActionLabel('avoid selling into weakness', englishLabels)).toBe('Hold');
    expect(getLegacyDecisionActionLabel('avoid trimming before earnings', englishLabels)).toBe('Hold');
    expect(getLegacyDecisionActionLabel('avoid reducing exposure before earnings', englishLabels)).toBe('Hold');
    expect(getDecisionActionTone(null, null, '\u4e0d\u5efa\u8bae\u5356\u51fa，\u7ee7\u7eed\u89c2\u5bdf')).toBe('success');
  });

  it('does not turn ambiguous English advice into a badge action', () => {
    expect(getLegacyDecisionActionLabel('buy or sell')).toBeNull();
    expect(getDecisionActionLabel(null, null, 'buy or sell', 'Advice', englishLabels)).toBe('Advice');
  });

  it('does not match financial compound words as legacy actions', () => {
    expect(getLegacyDecisionActionLabel('no buyback announced', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('cannot buyback shares now', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('share buy-back announced', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('share buy back announced', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('no selloff risk', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('not selloff yet', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('sell-off risk remains low', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('sell off risk remains low', englishLabels)).toBeNull();
    expect(getLegacyDecisionActionLabel('no sell-off pressure', englishLabels)).toBeNull();
    expect(getDecisionActionLabel(null, null, 'no buyback announced', 'Advice', englishLabels)).toBe('Advice');
    expect(getDecisionActionLabel(null, null, 'no selloff risk', 'Advice', englishLabels)).toBe('Advice');
    expect(getLegacyDecisionActionLabel('no buy until breakout', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('cannot buy before confirmation', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('no sell before earnings', englishLabels)).toBe('Hold');
  });

  it('keeps separate action terms next to financial compounds', () => {
    expect(getLegacyDecisionAction('buy after sell-off')).toBe('buy');
    expect(getLegacyDecisionActionLabel('buy after sell-off', englishLabels)).toBe('Buy');
    expect(getLegacyDecisionAction('sell after buy-back rumor')).toBe('sell');
    expect(getLegacyDecisionActionLabel('sell after buy-back rumor', englishLabels)).toBe('Sell');
  });

  it('does not match Chinese financial context words as legacy actions', () => {
    expect(getLegacyDecisionActionLabel('\u4e70\u76d8\u589e\u5f3a，\u7ee7\u7eed\u89c2\u5bdf')).toBeNull();
    expect(getLegacyDecisionActionLabel('\u5356\u538b\u7f13\u89e3，\u7ee7\u7eed\u89c2\u5bdf')).toBeNull();
    expect(getLegacyDecisionActionLabel('\u5356\u65b9\u8bc4\u7ea7\u5206\u6b67')).toBeNull();
    expect(getDecisionActionLabel(null, null, '\u4e70\u76d8\u589e\u5f3a，\u7ee7\u7eed\u89c2\u5bdf', '\u5efa\u8bae')).toBe('\u5efa\u8bae');
    expect(getDecisionActionLabel(null, null, '\u5356\u538b\u7f13\u89e3，\u7ee7\u7eed\u89c2\u5bdf', '\u5efa\u8bae')).toBe('\u5efa\u8bae');
  });

  it('keeps multi-guard legacy advice empty instead of prioritizing avoid or alert', () => {
    expect(getLegacyDecisionActionLabel('risk alert, avoid buying')).toBeNull();
    expect(getLegacyDecisionActionLabel('\u98ce\u9669\u9884\u8b66，\u907f\u514d\u4e70\u5165')).toBeNull();
    expect(getDecisionActionLabel(null, null, 'risk alert, avoid buying', 'Advice', englishLabels)).toBe('Advice');
    expect(getLegacyDecisionActionLabel('avoid buying', englishLabels)).toBe('Avoid');
    expect(getLegacyDecisionActionLabel('risk alert', englishLabels)).toBe('Alert');
  });

  it('maps action tone without reading legacy text when action is present', () => {
    expect(getDecisionActionTone('buy', null, '\u5356\u51fa')).toBe('success');
    expect(getDecisionActionTone('reduce', null, '\u4e70\u5165')).toBe('danger');
    expect(getDecisionActionTone('alert', null, '\u4e70\u5165')).toBe('warning');
    expect(getDecisionActionTone(null, '\u89c2\u671b', '\u4e70\u5165')).toBe('warning');
    expect(getDecisionActionTone(null, 'Sell', '\u4e70\u5165')).toBe('danger');
    expect(getDecisionActionTone(null, null, 'avoid buying')).toBe('warning');
  });
});
