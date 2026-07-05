# -*- coding: utf-8 -*-
"""
===================================
A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u73af\u5883\u9a8c\u8bc1\u6d4b\u8bd5
===================================

\u7528\u4e8e\u9a8c\u8bc1 .env \u914d\u7f6e\u662f\u5426\u6b63\u786e，\u5305\u62ec：
1. \u914d\u7f6e\u52a0\u8f7d\u6d4b\u8bd5
2. \u6570\u636e\u5e93\u67e5\u770b
3. \u6570\u636e\u6e90\u6d4b\u8bd5
4. LLM \u8c03\u7528\u6d4b\u8bd5
5. \u901a\u77e5\u63a8\u9001\u6d4b\u8bd5

\u4f7f\u7528\u65b9\u6cd5：
    python scripts/check_env.py              # \u8fd0\u884c\u6240\u6709\u6d4b\u8bd5
    python scripts/check_env.py --db         # \u4ec5\u67e5\u770b\u6570\u636e\u5e93
    python scripts/check_env.py --llm        # \u4ec5\u6d4b\u8bd5 LLM
    python scripts/check_env.py --fetch      # \u4ec5\u6d4b\u8bd5\u6570\u636e\u83b7\u53d6
    python scripts/check_env.py --notify     # \u4ec5\u6d4b\u8bd5\u901a\u77e5

"""
import os
# Proxy config - controlled by USE_PROXY env var, off by default.
# Set USE_PROXY=true in .env if you need a local proxy (e.g. mainland China).
# GitHub Actions always skips this regardless of USE_PROXY.
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXY_PORT", "10809")
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url

import argparse
import logging
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _reconfigure_output_stream(stream):
    """Avoid UnicodeEncodeError on legacy Windows console code pages."""
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return

    for kwargs in (
        {"encoding": "utf-8", "errors": "replace"},
        {"errors": "replace"},
    ):
        try:
            reconfigure(**kwargs)
            return
        except Exception:
            continue


def configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        _reconfigure_output_stream(stream)


# \u914d\u7f6e\u65e5\u5fd7
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """\u6253\u5370\u6807\u9898"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str):
    """\u6253\u5370\u5c0f\u8282"""
    print(f"\n--- {title} ---")


def check_config():
    """\u6d4b\u8bd5\u914d\u7f6e\u52a0\u8f7d"""
    print_header("1. \u914d\u7f6e\u52a0\u8f7d\u6d4b\u8bd5")

    from src.config import get_config
    config = get_config()

    print_section("\u57fa\u7840\u914d\u7f6e")
    print(f"  \u80a1\u7968\u5217\u8868: {config.stock_list}")
    print(f"  \u6570\u636e\u5e93\u8def\u5f84: {config.database_path}")
    print(f"  \u6700\u5927\u5e76\u53d1\u6570: {config.max_workers}")
    print(f"  \u8c03\u8bd5\u6a21\u5f0f: {config.debug}")

    print_section("API \u914d\u7f6e")
    print(f"  Tushare Token: {'\u5df2\u914d\u7f6e ✓' if config.tushare_token else '\u672a\u914d\u7f6e ✗'}")
    if config.tushare_token:
        print(f"    Token \u524d8\u4f4d: {config.tushare_token[:8]}...")

    print(f"  Gemini API Key: {'\u5df2\u914d\u7f6e ✓' if config.gemini_api_key else '\u672a\u914d\u7f6e ✗'}")
    if config.gemini_api_key:
        print(f"    Key \u524d8\u4f4d: {config.gemini_api_key[:8]}...")
    print(f"  Gemini \u4e3b\u6a21\u578b: {config.gemini_model}")
    print(f"  Gemini \u5907\u9009\u6a21\u578b: {config.gemini_model_fallback}")

    print(f"  \u4f01\u4e1a\u5fae\u4fe1 Webhook: {'\u5df2\u914d\u7f6e ✓' if config.wechat_webhook_url else '\u672a\u914d\u7f6e ✗'}")

    print_section("\u914d\u7f6e\u9a8c\u8bc1")
    issues = config.validate_structured()
    _prefix = {"error": "  ✗", "warning": "  ⚠", "info": "  ·"}
    for issue in issues:
        print(f"{_prefix.get(issue.severity, '  ?')} [{issue.severity.upper()}] {issue.message}")
    if not any(i.severity in ("error", "warning") for i in issues):
        print("  ✓ \u5173\u952e\u914d\u7f6e\u9879\u9a8c\u8bc1\u901a\u8fc7")

    return True


def view_database():
    """\u67e5\u770b\u6570\u636e\u5e93\u5185\u5bb9"""
    print_header("2. \u6570\u636e\u5e93\u5185\u5bb9\u67e5\u770b")

    from src.storage import get_db
    from sqlalchemy import text

    db = get_db()

    print_section("\u6570\u636e\u5e93\u8fde\u63a5")
    print(f"  ✓ \u8fde\u63a5\u6210\u529f")

    # \u4f7f\u7528\u72ec\u7acb\u7684 session \u67e5\u8be2
    session = db.get_session()
    try:
        # \u7edf\u8ba1\u4fe1\u606f
        result = session.execute(text("""
            SELECT
                code,
                COUNT(*) as count,
                MIN(date) as min_date,
                MAX(date) as max_date,
                data_source
            FROM stock_daily
            GROUP BY code
            ORDER BY code
        """))
        stocks = result.fetchall()

        print_section(f"\u5df2\u5b58\u50a8\u80a1\u7968\u6570\u636e (\u5171 {len(stocks)} \u53ea)")
        if stocks:
            print(f"  {'\u4ee3\u7801':<10} {'\u8bb0\u5f55\u6570':<8} {'\u8d77\u59cb\u65e5\u671f':<12} {'\u6700\u65b0\u65e5\u671f':<12} {'\u6570\u636e\u6e90'}")
            print("  " + "-" * 60)
            for row in stocks:
                print(f"  {row[0]:<10} {row[1]:<8} {row[2]!s:<12} {row[3]!s:<12} {row[4] or 'Unknown'}")
        else:
            print("  \u6682\u65e0\u6570\u636e")

        # \u67e5\u8be2\u4eca\u65e5\u6570\u636e
        today = date.today()
        result = session.execute(text("""
            SELECT code, date, open, high, low, close, pct_chg, volume, ma5, ma10, ma20, volume_ratio
            FROM stock_daily
            WHERE date = :today
            ORDER BY code
        """), {"today": today})
        today_data = result.fetchall()

        print_section(f"\u4eca\u65e5\u6570\u636e ({today})")
        if today_data:
            for row in today_data:
                code, dt, open_, high, low, close, pct_chg, volume, ma5, ma10, ma20, vol_ratio = row
                print(f"\n  【{code}】")
                print(f"    \u5f00\u76d8: {open_:.2f}  \u6700\u9ad8: {high:.2f}  \u6700\u4f4e: {low:.2f}  \u6536\u76d8: {close:.2f}")
                print(f"    \u6da8\u8dcc\u5e45: {pct_chg:.2f}%  \u6210\u4ea4\u91cf: {volume/10000:.2f}\u4e07\u80a1")
                print(f"    MA5: {ma5:.2f}  MA10: {ma10:.2f}  MA20: {ma20:.2f}  \u91cf\u6bd4: {vol_ratio:.2f}")
        else:
            print("  \u4eca\u65e5\u6682\u65e0\u6570\u636e")

        # \u67e5\u8be2\u6700\u8fd110\u6761\u6570\u636e
        result = session.execute(text("""
            SELECT code, date, close, pct_chg, volume, data_source
            FROM stock_daily
            ORDER BY date DESC, code
            LIMIT 10
        """))
        recent = result.fetchall()

        print_section("\u6700\u8fd110\u6761\u8bb0\u5f55")
        if recent:
            print(f"  {'\u4ee3\u7801':<10} {'\u65e5\u671f':<12} {'\u6536\u76d8':<10} {'\u6da8\u8dcc%':<8} {'\u6210\u4ea4\u91cf':<15} {'\u6765\u6e90'}")
            print("  " + "-" * 70)
            for row in recent:
                vol_str = f"{row[4]/10000:.2f}\u4e07" if row[4] else "N/A"
                print(f"  {row[0]:<10} {row[1]!s:<12} {row[2]:<10.2f} {row[3]:<8.2f} {vol_str:<15} {row[5] or 'Unknown'}")
    finally:
        session.close()

    return True


def check_data_fetch(stock_code: str = "600519"):
    """\u6d4b\u8bd5\u6570\u636e\u83b7\u53d6"""
    print_header("3. \u6570\u636e\u83b7\u53d6\u6d4b\u8bd5")

    from data_provider import DataFetcherManager

    manager = DataFetcherManager()

    print_section("\u6570\u636e\u6e90\u5217\u8868")
    for i, name in enumerate(manager.available_fetchers, 1):
        print(f"  {i}. {name}")

    print_section(f"\u83b7\u53d6 {stock_code} \u6570\u636e")
    print(f"  \u6b63\u5728\u83b7\u53d6（\u53ef\u80fd\u9700\u8981\u51e0\u79d2\u949f）...")

    try:
        df, source = manager.get_daily_data(stock_code, days=5)

        print(f"  ✓ \u83b7\u53d6\u6210\u529f")
        print(f"    \u6570\u636e\u6e90: {source}")
        print(f"    \u8bb0\u5f55\u6570: {len(df)}")

        print_section("\u6570\u636e\u9884\u89c8（\u6700\u8fd15\u6761）")
        if not df.empty:
            preview_cols = ['date', 'open', 'high', 'low', 'close', 'pct_chg', 'volume']
            existing_cols = [c for c in preview_cols if c in df.columns]
            print(df[existing_cols].tail().to_string(index=False))

        return True

    except Exception as e:
        print(f"  ✗ \u83b7\u53d6\u5931\u8d25: {e}")
        return False


def check_llm():
    """\u6d4b\u8bd5 LLM \u8c03\u7528"""
    print_header("4. LLM (Gemini) \u8c03\u7528\u6d4b\u8bd5")

    from src.analyzer import GeminiAnalyzer
    from src.config import get_config
    import time

    config = get_config()

    print_section("\u6a21\u578b\u914d\u7f6e")
    print(f"  \u4e3b\u6a21\u578b: {config.gemini_model}")
    print(f"  \u5907\u9009\u6a21\u578b: {config.gemini_model_fallback}")

    # \u68c0\u67e5\u7f51\u7edc\u8fde\u63a5
    print_section("\u7f51\u7edc\u8fde\u63a5\u68c0\u67e5")
    try:
        import socket
        socket.setdefaulttimeout(10)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("generativelanguage.googleapis.com", 443))
        print(f"  ✓ \u53ef\u4ee5\u8fde\u63a5\u5230 Google API \u670d\u52a1\u5668")
    except Exception as e:
        print(f"  ✗ \u65e0\u6cd5\u8fde\u63a5\u5230 Google API \u670d\u52a1\u5668: {e}")
        print(f"  \u63d0\u793a: \u8bf7\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5\u6216\u914d\u7f6e\u4ee3\u7406")
        print(f"  \u63d0\u793a: \u53ef\u4ee5\u8bbe\u7f6e\u73af\u5883\u53d8\u91cf HTTPS_PROXY=http://your-proxy:port")
        return False

    analyzer = GeminiAnalyzer()

    print_section("\u6a21\u578b\u521d\u59cb\u5316")
    if analyzer.is_available():
        print(f"  ✓ \u6a21\u578b\u521d\u59cb\u5316\u6210\u529f")
    else:
        print(f"  ✗ \u6a21\u578b\u521d\u59cb\u5316\u5931\u8d25（\u8bf7\u68c0\u67e5 API Key）")
        return False

    # \u6784\u9020\u6d4b\u8bd5\u4e0a\u4e0b\u6587
    test_context = {
        'code': '600519',
        'date': date.today().isoformat(),
        'today': {
            'open': 1420.0,
            'high': 1435.0,
            'low': 1415.0,
            'close': 1428.0,
            'volume': 5000000,
            'amount': 7140000000,
            'pct_chg': 0.56,
            'ma5': 1425.0,
            'ma10': 1418.0,
            'ma20': 1410.0,
            'volume_ratio': 1.1,
        },
        'ma_status': '\u591a\u5934\u6392\u5217 📈',
        'volume_change_ratio': 1.05,
        'price_change_ratio': 0.56,
    }

    print_section("\u53d1\u9001\u6d4b\u8bd5\u8bf7\u6c42")
    print(f"  \u6d4b\u8bd5\u80a1\u7968: \u8d35\u5dde\u8305\u53f0 (600519)")
    print(f"  \u6b63\u5728\u8c03\u7528 Gemini API（\u8d85\u65f6: 60\u79d2）...")

    start_time = time.time()

    try:
        result = analyzer.analyze(test_context)

        elapsed = time.time() - start_time
        print(f"\n  ✓ API \u8c03\u7528\u6210\u529f (\u8017\u65f6: {elapsed:.2f}\u79d2)")

        print_section("\u5206\u6790\u7ed3\u679c")
        print(f"  \u60c5\u7eea\u8bc4\u5206: {result.sentiment_score}/100")
        print(f"  \u8d8b\u52bf\u9884\u6d4b: {result.trend_prediction}")
        print(f"  \u64cd\u4f5c\u5efa\u8bae: {result.operation_advice}")
        print(f"  \u6280\u672f\u5206\u6790: {result.technical_analysis[:80]}..." if len(result.technical_analysis) > 80 else f"  \u6280\u672f\u5206\u6790: {result.technical_analysis}")
        print(f"  \u6d88\u606f\u9762: {result.news_summary[:80]}..." if len(result.news_summary) > 80 else f"  \u6d88\u606f\u9762: {result.news_summary}")
        print(f"  \u7efc\u5408\u6458\u8981: {result.analysis_summary}")

        if not result.success:
            print(f"\n  ⚠ \u6ce8\u610f: {result.error_message}")

        return result.success

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n  ✗ API \u8c03\u7528\u5931\u8d25 (\u8017\u65f6: {elapsed:.2f}\u79d2)")
        print(f"  \u9519\u8bef: {e}")

        # \u63d0\u4f9b\u66f4\u8be6\u7ec6\u7684\u9519\u8bef\u63d0\u793a
        error_str = str(e).lower()
        if 'timeout' in error_str or 'unavailable' in error_str:
            print(f"\n  \u8bca\u65ad: \u7f51\u7edc\u8d85\u65f6，\u53ef\u80fd\u539f\u56e0:")
            print(f"    1. \u7f51\u7edc\u4e0d\u901a（\u9700\u8981\u4ee3\u7406\u8bbf\u95ee Google）")
            print(f"    2. API \u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528")
            print(f"    3. \u8bf7\u6c42\u91cf\u8fc7\u5927\u88ab\u9650\u6d41")
        elif 'invalid' in error_str or 'api key' in error_str:
            print(f"\n  \u8bca\u65ad: API Key \u53ef\u80fd\u65e0\u6548")
        elif 'model' in error_str:
            print(f"\n  \u8bca\u65ad: \u6a21\u578b\u540d\u79f0\u53ef\u80fd\u4e0d\u6b63\u786e，\u5c1d\u8bd5\u4fee\u6539 .env \u4e2d\u7684 GEMINI_MODEL")

        return False


def check_notification():
    """\u6d4b\u8bd5\u901a\u77e5\u63a8\u9001"""
    print_header("5. \u901a\u77e5\u63a8\u9001\u6d4b\u8bd5")

    from src.notification import NotificationService
    from src.config import get_config

    config = get_config()
    service = NotificationService()

    print_section("\u914d\u7f6e\u68c0\u67e5")
    if service.is_available():
        print(f"  ✓ \u4f01\u4e1a\u5fae\u4fe1 Webhook \u5df2\u914d\u7f6e")
        webhook_preview = config.wechat_webhook_url[:50] + "..." if len(config.wechat_webhook_url) > 50 else config.wechat_webhook_url
        print(f"    URL: {webhook_preview}")
    else:
        print(f"  ✗ \u4f01\u4e1a\u5fae\u4fe1 Webhook \u672a\u914d\u7f6e")
        return False

    print_section("\u53d1\u9001\u6d4b\u8bd5\u6d88\u606f")

    test_message = f"""## 🧪 \u7cfb\u7edf\u6d4b\u8bd5\u6d88\u606f

\u8fd9\u662f\u4e00\u6761\u6765\u81ea **A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf** \u7684\u6d4b\u8bd5\u6d88\u606f。

- \u6d4b\u8bd5\u65f6\u95f4: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- \u6d4b\u8bd5\u76ee\u7684: \u9a8c\u8bc1\u4f01\u4e1a\u5fae\u4fe1 Webhook \u914d\u7f6e

\u5982\u679c\u60a8\u6536\u5230\u6b64\u6d88\u606f，\u8bf4\u660e\u901a\u77e5\u529f\u80fd\u914d\u7f6e\u6b63\u786e ✓"""

    print(f"  \u6b63\u5728\u53d1\u9001...")

    try:
        success = service.send_to_wechat(test_message)

        if success:
            print(f"  ✓ \u6d88\u606f\u53d1\u9001\u6210\u529f，\u8bf7\u68c0\u67e5\u4f01\u4e1a\u5fae\u4fe1")
        else:
            print(f"  ✗ \u6d88\u606f\u53d1\u9001\u5931\u8d25")

        return success

    except Exception as e:
        print(f"  ✗ \u53d1\u9001\u5f02\u5e38: {e}")
        return False


def run_all_tests():
    """\u8fd0\u884c\u6240\u6709\u6d4b\u8bd5"""
    print("\n" + "🚀" * 20)
    print("  A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u73af\u5883\u9a8c\u8bc1")
    print("  " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚀" * 20)

    results = {}

    # 1. \u914d\u7f6e\u6d4b\u8bd5
    try:
        results['\u914d\u7f6e\u52a0\u8f7d'] = check_config()
    except Exception as e:
        print(f"  ✗ \u914d\u7f6e\u6d4b\u8bd5\u5931\u8d25: {e}")
        results['\u914d\u7f6e\u52a0\u8f7d'] = False

    # 2. \u6570\u636e\u5e93\u67e5\u770b
    try:
        results['\u6570\u636e\u5e93'] = view_database()
    except Exception as e:
        print(f"  ✗ \u6570\u636e\u5e93\u6d4b\u8bd5\u5931\u8d25: {e}")
        results['\u6570\u636e\u5e93'] = False

    # 3. \u6570\u636e\u83b7\u53d6（\u8df3\u8fc7，\u907f\u514d\u592a\u6162）
    # results['\u6570\u636e\u83b7\u53d6'] = check_data_fetch()

    # 4. LLM \u6d4b\u8bd5（\u53ef\u9009）
    # results['LLM\u8c03\u7528'] = check_llm()

    # \u6c47\u603b
    print_header("\u6d4b\u8bd5\u7ed3\u679c\u6c47\u603b")
    for name, passed in results.items():
        status = "✓ \u901a\u8fc7" if passed else "✗ \u5931\u8d25"
        print(f"  {status}: {name}")

    print(f"\n\u63d0\u793a: \u4f7f\u7528 --llm \u53c2\u6570\u5355\u72ec\u6d4b\u8bd5 LLM \u8c03\u7528")
    print(f"\u63d0\u793a: \u4f7f\u7528 --fetch \u53c2\u6570\u5355\u72ec\u6d4b\u8bd5\u6570\u636e\u83b7\u53d6")
    print(f"\u63d0\u793a: \u4f7f\u7528 --notify \u53c2\u6570\u5355\u72ec\u6d4b\u8bd5\u901a\u77e5\u63a8\u9001")


def query_stock_data(stock_code: str, days: int = 10):
    """\u67e5\u8be2\u6307\u5b9a\u80a1\u7968\u7684\u6570\u636e"""
    print_header(f"\u67e5\u8be2\u80a1\u7968\u6570\u636e: {stock_code}")

    from src.storage import get_db
    from sqlalchemy import text

    db = get_db()

    session = db.get_session()
    try:
        result = session.execute(text("""
            SELECT date, open, high, low, close, pct_chg, volume, amount, ma5, ma10, ma20, volume_ratio
            FROM stock_daily
            WHERE code = :code
            ORDER BY date DESC
            LIMIT :limit
        """), {"code": stock_code, "limit": days})

        rows = result.fetchall()

        if rows:
            print(f"\n  \u6700\u8fd1 {len(rows)} \u6761\u8bb0\u5f55:\n")
            print(f"  {'\u65e5\u671f':<12} {'\u5f00\u76d8':<10} {'\u6700\u9ad8':<10} {'\u6700\u4f4e':<10} {'\u6536\u76d8':<10} {'\u6da8\u8dcc%':<8} {'MA5':<10} {'MA10':<10} {'\u91cf\u6bd4':<8}")
            print("  " + "-" * 100)
            for row in rows:
                dt, open_, high, low, close, pct_chg, vol, amt, ma5, ma10, ma20, vol_ratio = row
                print(f"  {dt!s:<12} {open_:<10.2f} {high:<10.2f} {low:<10.2f} {close:<10.2f} {pct_chg:<8.2f} {ma5:<10.2f} {ma10:<10.2f} {vol_ratio:<8.2f}")
        else:
            print(f"  \u672a\u627e\u5230 {stock_code} \u7684\u6570\u636e")
    finally:
        session.close()


def main():
    configure_console_encoding()

    parser = argparse.ArgumentParser(
        description='A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u73af\u5883\u9a8c\u8bc1\u6d4b\u8bd5',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--db', action='store_true', help='\u67e5\u770b\u6570\u636e\u5e93\u5185\u5bb9')
    parser.add_argument('--llm', action='store_true', help='\u6d4b\u8bd5 LLM \u8c03\u7528')
    parser.add_argument('--fetch', action='store_true', help='\u6d4b\u8bd5\u6570\u636e\u83b7\u53d6')
    parser.add_argument('--notify', action='store_true', help='\u6d4b\u8bd5\u901a\u77e5\u63a8\u9001')
    parser.add_argument('--config', action='store_true', help='\u67e5\u770b\u914d\u7f6e')
    parser.add_argument('--stock', type=str, help='\u67e5\u8be2\u6307\u5b9a\u80a1\u7968\u6570\u636e，\u5982 --stock 600519')
    parser.add_argument('--all', action='store_true', help='\u8fd0\u884c\u6240\u6709\u6d4b\u8bd5（\u5305\u62ec LLM）')

    args = parser.parse_args()

    # \u5982\u679c\u6ca1\u6709\u6307\u5b9a\u4efb\u4f55\u53c2\u6570，\u8fd0\u884c\u57fa\u7840\u6d4b\u8bd5
    if not any([args.db, args.llm, args.fetch, args.notify, args.config, args.stock, args.all]):
        run_all_tests()
        return 0

    # \u6839\u636e\u53c2\u6570\u8fd0\u884c\u6307\u5b9a\u6d4b\u8bd5
    if args.config:
        check_config()

    if args.db:
        view_database()

    if args.stock:
        query_stock_data(args.stock)

    if args.fetch:
        check_data_fetch()

    if args.llm:
        check_llm()

    if args.notify:
        check_notification()

    if args.all:
        check_config()
        view_database()
        check_data_fetch()
        check_llm()
        check_notification()

    return 0


if __name__ == "__main__":
    sys.exit(main())
