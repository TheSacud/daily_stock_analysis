/**
 * searchStocks unit tests.
 */

import { searchStocks } from '../searchStocks';
import type { StockIndexItem } from '../../types/stockIndex';
import { describe, expect, test } from 'vitest';

const mockIndex: StockIndexItem[] = [
  {
    canonicalCode: "600519.SH",
    displayCode: "600519",
    nameZh: "\u8d35\u5dde\u8305\u53f0",
    pinyinFull: "guizhoumaotai",
    pinyinAbbr: "gzmt",
    aliases: ["\u8305\u53f0"],
    market: "CN",
    assetType: "stock",
    active: true,
    popularity: 100,
  },
  {
    canonicalCode: "000001.SZ",
    displayCode: "000001",
    nameZh: "\u5e73\u5b89\u94f6\u884c",
    pinyinFull: "pinganyinxing",
    pinyinAbbr: "payh",
    aliases: ["\u5e73\u94f6"],
    market: "CN",
    assetType: "stock",
    active: true,
    popularity: 90,
  },
  {
    canonicalCode: "000002.SZ",
    displayCode: "000002",
    nameZh: "\u4e07\u79d1Ａ",
    pinyinFull: "wankeＡ",
    pinyinAbbr: "wkＡ",
    aliases: [],
    market: "CN",
    assetType: "stock",
    active: true,
    popularity: 92,
  },
  {
    canonicalCode: "00700.HK",
    displayCode: "00700",
    nameZh: "\u817e\u8baf\u63a7\u80a1",
    pinyinFull: "tengxunkonggu",
    pinyinAbbr: "txkg",
    aliases: ["\u817e\u8baf"],
    market: "HK",
    assetType: "stock",
    active: true,
    popularity: 95,
  },
  {
    canonicalCode: "AAPL.US",
    displayCode: "AAPL",
    nameZh: "\u82f9\u679c",
    pinyinFull: "pingguo",
    pinyinAbbr: "pg",
    aliases: [],
    market: "US",
    assetType: "stock",
    active: true,
    popularity: 98,
  },
  {
    canonicalCode: "7203.T",
    displayCode: "7203.T",
    nameZh: "\u4e30\u7530\u6c7d\u8f66",
    pinyinFull: "fengtianqiche",
    pinyinAbbr: "ftqc",
    aliases: ["Toyota", "Toyota Motor", "\u4e30\u7530"],
    market: "JP",
    assetType: "stock",
    active: true,
    popularity: 97,
  },
  {
    canonicalCode: "005930.KS",
    displayCode: "005930.KS",
    nameZh: "\u4e09\u661f\u7535\u5b50",
    pinyinFull: "sanxingdianzi",
    pinyinAbbr: "sxdz",
    aliases: ["Samsung", "Samsung Electronics", "\u4e09\u661f"],
    market: "KR",
    assetType: "stock",
    active: true,
    popularity: 97,
  },
  {
    canonicalCode: "035720.KQ",
    displayCode: "035720.KQ",
    nameZh: "Kakao",
    pinyinFull: "Kakao",
    pinyinAbbr: "Kakao",
    aliases: ["Kakao", "\u53ef\u53ef"],
    market: "KR",
    assetType: "stock",
    active: true,
    popularity: 92,
  },
  {
    canonicalCode: "600000.SH",
    displayCode: "600000",
    nameZh: "\u6d66\u53d1\u94f6\u884c",
    pinyinFull: "pufayinxing",
    pinyinAbbr: "pfyh",
    aliases: ["\u6d66\u53d1"],
    market: "CN",
    assetType: "stock",
    active: false,  // Inactive
    popularity: 80,
  },
];

describe('searchStocks', () => {
  test('\u7cbe\u786e\u5339\u914d\u4ee3\u7801', () => {
    const results = searchStocks('600519', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
    expect(results[0].matchField).toBe('code');
  });

  test('\u7cbe\u786e\u5339\u914d\u4e2d\u6587\u540d\u79f0', () => {
    const results = searchStocks('\u8d35\u5dde\u8305\u53f0', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
    expect(results[0].matchField).toBe('name');
  });

  test('\u62fc\u97f3\u9996\u5b57\u6bcd\u5339\u914d', () => {
    const results = searchStocks('gzmt', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
  });

  test('\u522b\u540d\u5339\u914d', () => {
    const results = searchStocks('\u8305\u53f0', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
  });

  test('\u524d\u7f00\u5339\u914d\u4ee3\u7801', () => {
    const results = searchStocks('600', mockIndex);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].matchType).toBe('prefix');
    expect(results[0].matchField).toBe('code');
  });

  test('\u524d\u7f00\u5339\u914d\u540d\u79f0', () => {
    const results = searchStocks('\u8d35\u5dde', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].matchType).toBe('prefix');
    expect(results[0].matchField).toBe('name');
  });

  test('\u5305\u542b\u5339\u914d\u62fc\u97f3', () => {
    const results = searchStocks('maotai', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('contains');
  });

  test('active \u4f18\u5148\u4e8e inactive', () => {
    // 600000 \u662f\u4e0d\u6d3b\u8dc3\u7684，600519 \u662f\u6d3b\u8dc3\u7684
    const results = searchStocks('600', mockIndex);
    const activeResults = results.filter(r => {
      const item = mockIndex.find(i => i.canonicalCode === r.canonicalCode);
      return item?.active;
    });
    // \u6d3b\u8dc3\u80a1\u7968\u5e94\u8be5\u6392\u5728\u524d\u9762
    if (results.length > 1) {
      expect(activeResults.length).toBeGreaterThan(0);
    }
  });

  test('activeOnly \u9009\u9879\u8fc7\u6ee4\u4e0d\u6d3b\u8dc3\u80a1\u7968', () => {
    const results = searchStocks('600', mockIndex, { activeOnly: true });
    for (const result of results) {
      const item = mockIndex.find(i => i.canonicalCode === result.canonicalCode);
      expect(item?.active).toBe(true);
    }
  });

  test('limit \u9009\u9879\u9650\u5236\u8fd4\u56de\u6570\u91cf', () => {
    const results = searchStocks('600', mockIndex, { limit: 1 });
    expect(results.length).toBeLessThanOrEqual(1);
  });

  test('\u65e0\u7ed3\u679c\u65f6\u8fd4\u56de\u7a7a\u6570\u7ec4', () => {
    const results = searchStocks('NOTFOUND', mockIndex);
    expect(results).toHaveLength(0);
  });

  test('\u7a7a\u67e5\u8be2\u8fd4\u56de\u7a7a\u6570\u7ec4', () => {
    const results = searchStocks('', mockIndex);
    expect(results).toHaveLength(0);
  });

  test('\u5927\u5c0f\u5199\u4e0d\u654f\u611f', () => {
    const results1 = searchStocks('aapl', mockIndex);
    const results2 = searchStocks('AAPL', mockIndex);
    expect(results1).toHaveLength(1);
    expect(results2).toHaveLength(1);
    expect(results1[0].canonicalCode).toBe(results2[0].canonicalCode);
  });

  test('sorts by popularity when scores are tied', () => {
    const results = searchStocks('600', mockIndex);
    // When scores tie, popularity should decide the order.
    if (results.length > 1) {
      for (let index = 0; index < results.length - 1; index++) {
        const currentItem = mockIndex.find((item) => item.canonicalCode === results[index].canonicalCode);
        const nextItem = mockIndex.find((item) => item.canonicalCode === results[index + 1].canonicalCode);
        if (results[index].score === results[index + 1].score) {
          expect((currentItem?.popularity || 0)).toBeGreaterThanOrEqual(nextItem?.popularity || 0);
        }
      }
    }
  });

  test('\u7f8e\u80a1\u4ee3\u7801\u5339\u914d', () => {
    const results = searchStocks('AAPL', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('AAPL.US');
    expect(results[0].market).toBe('US');
  });

  test('supports half-width queries for full-width A-share suffix names', () => {
    const byName = searchStocks('\u4e07\u79d1A', mockIndex);
    const byPinyin = searchStocks('wka', mockIndex);

    expect(byName[0].canonicalCode).toBe('000002.SZ');
    expect(byPinyin[0].canonicalCode).toBe('000002.SZ');
  });

  test('\u6e2f\u80a1\u4ee3\u7801\u5339\u914d', () => {
    const results = searchStocks('00700', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('00700.HK');
    expect(results[0].market).toBe('HK');
  });

  test('\u65e5\u80a1 Yahoo \u540e\u7f00\u4ee3\u7801\u5339\u914d', () => {
    const results = searchStocks('7203.T', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('7203.T');
    expect(results[0].market).toBe('JP');
  });

  test('\u65e5\u80a1\u82f1\u6587\u522b\u540d\u5339\u914d', () => {
    const results = searchStocks('Toyota', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('7203.T');
    expect(results[0].matchField).toBe('alias');
  });

  test('\u97e9\u80a1 KOSPI Yahoo \u540e\u7f00\u4ee3\u7801\u5339\u914d', () => {
    const results = searchStocks('005930.KS', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('005930.KS');
    expect(results[0].market).toBe('KR');
  });

  test('\u97e9\u80a1 KOSDAQ Yahoo \u540e\u7f00\u4ee3\u7801\u5339\u914d', () => {
    const results = searchStocks('035720.KQ', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('035720.KQ');
    expect(results[0].market).toBe('KR');
  });

  test('\u97e9\u80a1\u4e2d\u6587\u522b\u540d\u5339\u914d', () => {
    const results = searchStocks('\u4e09\u661f', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('005930.KS');
  });

  describe('Edge case tests', () => {
    test('special character query', () => {
      const results = searchStocks('@#$%', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('pure space query', () => {
      const results = searchStocks('   ', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('Unicode character query', () => {
      const results = searchStocks('\u80a1\u7968🚀', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('extra long query string', () => {
      const longQuery = 'a'.repeat(1000);
      const results = searchStocks(longQuery, mockIndex);
      expect(results).toHaveLength(0);
    });

    test('partial pinyin match', () => {
      const results = searchStocks('mao', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      const hasMaoTai = results.some(r => r.canonicalCode === '600519.SH');
      expect(hasMaoTai).toBe(true);
    });

    test('abbreviation prefix match', () => {
      const results = searchStocks('gz', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].matchType).toBe('prefix');
    });

    test('alias match', () => {
      const results = searchStocks('\u94f6', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      // Should match \u5e73\u5b89\u94f6\u884c and \u6d66\u53d1\u94f6\u884c
      const banks = results.filter(r => r.nameZh.includes('\u94f6\u884c'));
      expect(banks.length).toBeGreaterThan(0);
    });
  });

  describe('Scoring system tests', () => {
    test('exact match has highest score', () => {
      const exactResults = searchStocks('600519', mockIndex);
      const prefixResults = searchStocks('600', mockIndex);

      expect(exactResults[0].score).toBeGreaterThan(prefixResults[0].score);
    });

    test('code match prioritized over name match', () => {
      const codeResults = searchStocks('600519', mockIndex);
      const nameResults = searchStocks('\u8d35\u5dde', mockIndex);

      // Code exact match should be 99 points (displayCode match)
      expect(codeResults[0].score).toBe(99);
      // Name prefix match should be less than 99 points
      expect(nameResults[0].score).toBeLessThan(99);
    });

    test('sorts by popularity when scores are equal', () => {
      // Add two stocks with same score
      const tieIndex: StockIndexItem[] = [
        {
          canonicalCode: 'TEST1.SH',
          displayCode: 'TEST1',
          nameZh: '\u6d4b\u8bd51',
          pinyinFull: 'test1',
          pinyinAbbr: 'ts1',
          aliases: [],
          market: 'CN',
          assetType: 'stock',
          active: true,
          popularity: 50,
        },
        {
          canonicalCode: 'TEST2.SH',
          displayCode: 'TEST2',
          nameZh: '\u6d4b\u8bd52',
          pinyinFull: 'test2',
          pinyinAbbr: 'ts2',
          aliases: [],
          market: 'CN',
          assetType: 'stock',
          active: true,
          popularity: 100,
        },
      ];

      const results = searchStocks('TEST', tieIndex);
      if (results.length > 1) {
        // TEST2 should rank first due to higher popularity
        expect(results[0].canonicalCode).toBe('TEST2.SH');
      }
    });
  });

  describe('Inactive stock tests', () => {
    test('filters out inactive stocks by default', () => {
      const results = searchStocks('600000', mockIndex);
      // 600000 is inactive, should not appear by default
      expect(results).toHaveLength(0);
    });

    test('shows inactive stocks when activeOnly=false', () => {
      const results = searchStocks('600000', mockIndex, { activeOnly: false });
      expect(results).toHaveLength(1);
      expect(results[0].canonicalCode).toBe('600000.SH');
    });

    test('active stocks prioritized over inactive stocks', () => {
      const results = searchStocks('600', mockIndex, { activeOnly: false });
      if (results.length > 1) {
        // First result should be active
        const firstItem = mockIndex.find(i => i.canonicalCode === results[0].canonicalCode);
        expect(firstItem?.active).toBe(true);
      }
    });
  });

  describe('Performance tests', () => {
    test('large index search performance', () => {
      // Create a large index
      const largeIndex: StockIndexItem[] = Array.from({ length: 5000 }, (_, i) => ({
        canonicalCode: `${i}.SH`,
        displayCode: `${i}`,
        nameZh: `\u80a1\u7968${i}`,
        pinyinFull: `stock${i}`,
        pinyinAbbr: `s${i}`,
        aliases: [],
        market: 'CN',
        assetType: 'stock',
        active: true,
        popularity: i % 100,
      }));

      const startTime = Date.now();
      const results = searchStocks('1', largeIndex);
      const endTime = Date.now();

      // Should complete in reasonable time (< 100ms)
      expect(endTime - startTime).toBeLessThan(100);
      expect(results.length).toBeGreaterThan(0);
    });

    test('multiple search performance', () => {
      const iterations = 100;
      const startTime = Date.now();

      for (let i = 0; i < iterations; i++) {
        searchStocks('600', mockIndex);
      }

      const endTime = Date.now();
      const avgTime = (endTime - startTime) / iterations;

      // Average search should be fast (< 10ms)
      expect(avgTime).toBeLessThan(10);
    });
  });

  describe('Match type tests', () => {
    test('exact match type', () => {
      const results = searchStocks('600519', mockIndex);
      expect(results[0].matchType).toBe('exact');
    });

    test('prefix match type', () => {
      const results = searchStocks('600', mockIndex);
      expect(results[0].matchType).toBe('prefix');
    });

    test('contains match type', () => {
      const results = searchStocks('maotai', mockIndex);
      expect(results[0].matchType).toBe('contains');
    });
  });

  describe('Match field tests', () => {
    test('code field match', () => {
      const results = searchStocks('600519', mockIndex);
      expect(results[0].matchField).toBe('code');
    });

    test('name field match', () => {
      const results = searchStocks('\u8d35\u5dde', mockIndex);
      expect(results[0].matchField).toBe('name');
    });

    test('pinyin field match', () => {
      const results = searchStocks('gzmt', mockIndex);
      expect(results[0].matchField).toBe('pinyin');
    });

    test('alias field match', () => {
      const results = searchStocks('\u8305\u53f0', mockIndex);
      // Should match \u8d35\u5dde\u8305\u53f0
      expect(results.length).toBeGreaterThan(0);
    });
  });
});
