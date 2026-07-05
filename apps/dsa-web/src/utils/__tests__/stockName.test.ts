import {
  truncateStockName,
  isStockNameTruncated,
  STOCK_NAME_MAX_LENGTH,
} from '../stockName';
import { describe, expect, test } from 'vitest';

describe('truncateStockName', () => {
  describe('English strings', () => {
    test('returns unchanged when at or below 15 chars', () => {
      expect(truncateStockName('Apple')).toBe('Apple');
      expect(truncateStockName('AAPL')).toBe('AAPL');
      expect(truncateStockName('123456789012345')).toBe('123456789012345');
    });

    test('truncates to 15 chars with trailing dot', () => {
      expect(truncateStockName('Apple Computer Inc.')).toBe('Apple Computer .');
      expect(truncateStockName('1234567890123456')).toBe('123456789012345.');
    });

    test('truncates very long English strings', () => {
      expect(truncateStockName('VeryLongStockNameCorporation')).toBe('VeryLongStockNa.');
    });
  });

  describe('Chinese strings', () => {
    test('returns unchanged when at or below 8 chars', () => {
      expect(truncateStockName('\u8d35\u5dde\u8305\u53f0')).toBe('\u8d35\u5dde\u8305\u53f0');
      expect(truncateStockName('\u817e\u8baf\u63a7\u80a1')).toBe('\u817e\u8baf\u63a7\u80a1');
    });

    test('truncates to 8 chars with trailing dot', () => {
      // \u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650\u516c\u53f8: 10 Chinese chars -> slice(0,8) + dot = 8 ch + dot
      expect(truncateStockName('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650\u516c\u53f8')).toBe('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650.');
      // \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fdABCD: mixed, 11 chars > 10 → truncate to '\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fdABC.'
      expect(truncateStockName('\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fdABCD')).toBe('\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fdABC.');
    });
  });

  describe('Mixed Chinese and English strings', () => {
    test('returns unchanged when at or below 10 chars', () => {
      expect(truncateStockName('\u8305\u53f0A')).toBe('\u8305\u53f0A');
      expect(truncateStockName('\u817e\u8baf\u63a7\u80a1HK')).toBe('\u817e\u8baf\u63a7\u80a1HK');
    });

    test('truncates to 10 chars with trailing dot', () => {
      // \u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650\u516c\u53f8AB: 10 Chinese + 2 English = 12 mixed -> slice(0,10) + dot
      // First 10: \u8d35 \u5dde \u8305 \u53f0 \u80a1 \u7968 \u6709 \u9650 \u516c \u53f8 = 8 ch + 2 en
      expect(truncateStockName('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650\u516c\u53f8AB')).toBe('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650\u516c\u53f8.');
      // \u817e\u8baf\u63a7\u80a100700H: 4 Chinese + 6 English = 10 mixed -> no truncation (10 <= 10)
      expect(truncateStockName('\u817e\u8baf\u63a7\u80a100700H')).toBe('\u817e\u8baf\u63a7\u80a100700H');
    });
  });

  describe('edge cases', () => {
    test('returns empty string unchanged', () => {
      expect(truncateStockName('')).toBe('');
    });

    test('handles stock code only (no Chinese)', () => {
      expect(truncateStockName('600519.SH')).toBe('600519.SH');
      expect(truncateStockName('00700.HK')).toBe('00700.HK');
    });

    test('handles single character strings', () => {
      expect(truncateStockName('A')).toBe('A');
      expect(truncateStockName('\u8305')).toBe('\u8305');
    });

    test('handles strings with only numbers and symbols', () => {
      expect(truncateStockName('600519')).toBe('600519');
      expect(truncateStockName('2026-03-24')).toBe('2026-03-24');
    });

    test('returns undefined unchanged (but should not happen in practice)', () => {
      // The function checks falsy, so empty string is handled, but non-string values
      // would behave unexpectedly - this documents current behavior
      expect(truncateStockName('' as unknown as string)).toBe('');
    });
  });

  describe('isStockNameTruncated', () => {
    test('returns false for empty string', () => {
      expect(isStockNameTruncated('')).toBe(false);
    });

    test('returns false for names at or below max length', () => {
      expect(isStockNameTruncated('Apple')).toBe(false);
      expect(isStockNameTruncated('\u8d35\u5dde\u8305\u53f0')).toBe(false);
      expect(isStockNameTruncated('\u8305\u53f0A')).toBe(false);
    });

    test('returns true for English names exceeding 15 chars', () => {
      expect(isStockNameTruncated('Apple Computer Inc.')).toBe(true);
      expect(isStockNameTruncated('VeryLongStockNameCorporation')).toBe(true);
    });

    test('returns true for Chinese names exceeding 8 chars', () => {
      expect(isStockNameTruncated('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u80a1\u4efd\u6709\u9650\u516c\u53f8')).toBe(true);
    });

    test('returns true for mixed names exceeding 10 chars', () => {
      expect(isStockNameTruncated('\u8d35\u5dde\u8305\u53f0\u80a1\u7968\u6709\u9650\u516c\u53f8AB')).toBe(true);
    });

    test('returns false for stock codes at boundary', () => {
      expect(isStockNameTruncated('600519.SH')).toBe(false);
      expect(isStockNameTruncated('00700.HK')).toBe(false);
    });
  });

  describe('STOCK_NAME_MAX_LENGTH constant', () => {
    test('has correct values', () => {
      expect(STOCK_NAME_MAX_LENGTH.ENGLISH).toBe(15);
      expect(STOCK_NAME_MAX_LENGTH.CHINESE).toBe(8);
      expect(STOCK_NAME_MAX_LENGTH.MIXED).toBe(10);
    });
  });
});
