# Image Extract Prompt (Vision LLM)

This document records the complete `EXTRACT_PROMPT` from `src/services/image_stock_extractor.py` so PR reviewers can evaluate instruction changes.

**When modifying `EXTRACT_PROMPT`**: update this file at the same time and include the complete before/after prompt in the PR description so reviewers can evaluate code, name, and confidence extraction behavior.

---

## Current Prompt (Complete)

```
Analyze this stock-market screenshot or image and extract every visible stock code and name.

Important: if the image shows both stock names and stock codes, such as a watchlist or ETF list, extract both values. Each item must include code and name fields.

Output format: return only a valid JSON array. Do not return Markdown or explanations.
Each array item must be an object: {"code":"stock code","name":"stock name","confidence":"high|medium|low"}
- code: required. Stock code, such as a 6-digit A-share code, 5-digit HK code, 1-5 letter US ticker, or ETF code such as 159887/512880.
- name: required when a name is visible in the image, such as Kweichow Moutai, Bank ETF, or Securities ETF; omit only when the image truly has no name.
- confidence: required. Recognition confidence: high=definite, medium=likely, low=uncertain.

Examples when both name and code appear in the image:
- A-shares: 600519 Kweichow Moutai, 300750 CATL
- Hong Kong stocks: 00700 Tencent Holdings, 09988 Alibaba
- US stocks: AAPL Apple, TSLA Tesla
- ETFs: 159887 Bank ETF, 512880 Securities ETF, 512000 Brokerage ETF, 512480 Semiconductor ETF, 515030 New Energy Vehicle ETF

Example output: [{"code":"600519","name":"Kweichow Moutai","confidence":"high"},{"code":"159887","name":"Bank ETF","confidence":"high"}]

Do not return a code-only array such as ["159887","512880"]. Always use the object format. If no stock code is found, return: []
```