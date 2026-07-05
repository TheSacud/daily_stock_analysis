#!/bin/bash
# ===================================
# A\u80a1/\u6e2f\u80a1/\u7f8e\u80a1 \u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u6d4b\u8bd5\u811a\u672c
# ===================================
#
# \u4f7f\u7528\u65b9\u6cd5：
#   ./scripts/test.sh [\u6d4b\u8bd5\u573a\u666f]
#
# \u6d4b\u8bd5\u573a\u666f：
#   market      - \u4ec5\u5927\u76d8\u590d\u76d8
#   a-stock     - A\u80a1\u4e2a\u80a1\u5206\u6790（\u8305\u53f0、\u5e73\u5b89\u94f6\u884c）
#   etf         - etf\u5206\u6790(\u536b\u661fetf 563230)
#   hk-stock    - \u6e2f\u80a1\u5206\u6790（\u817e\u8baf、\u963f\u91cc）
#   us-stock    - \u7f8e\u80a1\u5206\u6790（\u82f9\u679c、\u7279\u65af\u62c9）
#   mixed       - \u6df7\u5408\u5e02\u573a\u5206\u6790
#   single      - \u5355\u80a1\u6a21\u5f0f\u6d4b\u8bd5
#   dry-run     - \u4ec5\u83b7\u53d6\u6570\u636e\u4e0d\u5206\u6790
#   full        - \u5b8c\u6574\u6d41\u7a0b\u6d4b\u8bd5
#   quick       - \u5feb\u901f\u6d4b\u8bd5（\u5355\u53ea\u80a1\u7968）
#   all         - \u8fd0\u884c\u6240\u6709\u6d4b\u8bd5
#
# \u793a\u4f8b：
#   ./scripts/test.sh market      # \u6d4b\u8bd5\u5927\u76d8\u590d\u76d8
#   ./scripts/test.sh us-stock    # \u6d4b\u8bd5\u7f8e\u80a1\u5206\u6790
#   ./scripts/test.sh quick       # \u5feb\u901f\u6d4b\u8bd5
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

# \u989c\u8272\u5b9a\u4e49
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# \u6253\u5370\u5e26\u989c\u8272\u7684\u4fe1\u606f
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

header() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}$1${NC}"
    echo "=============================================="
    echo ""
}

# \u68c0\u67e5Python\u73af\u5883
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python3 \u672a\u5b89\u88c5"
        exit 1
    fi
    info "Python\u7248\u672c: $(python3 --version)"
}

# \u68c0\u67e5\u4f9d\u8d56
check_deps() {
    info "\u68c0\u67e5\u4f9d\u8d56..."
    python3 -c "import yfinance" 2>/dev/null || { warn "yfinance \u672a\u5b89\u88c5，\u7f8e\u80a1\u6d4b\u8bd5\u53ef\u80fd\u5931\u8d25"; }
    python3 -c "import akshare" 2>/dev/null || { warn "akshare \u672a\u5b89\u88c5，A\u80a1/\u6e2f\u80a1\u6d4b\u8bd5\u53ef\u80fd\u5931\u8d25"; }
    success "\u4f9d\u8d56\u68c0\u67e5\u5b8c\u6210"
}

# ==================== \u6d4b\u8bd5\u573a\u666f ====================

# \u6d4b\u8bd51: \u5927\u76d8\u590d\u76d8
test_market() {
    header "\u6d4b\u8bd5\u573a\u666f: \u5927\u76d8\u590d\u76d8"
    info "\u8fd0\u884c\u5927\u76d8\u590d\u76d8\u5206\u6790..."
    python3 main.py --market-review "$@"
    success "\u5927\u76d8\u590d\u76d8\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd52: A\u80a1\u5206\u6790
test_a_stock() {
    header "\u6d4b\u8bd5\u573a\u666f: A\u80a1\u5206\u6790"
    info "\u5206\u6790A\u80a1: 600519(\u8305\u53f0), 000001(\u5e73\u5b89\u94f6\u884c)"
    python3 main.py --stocks 600519,000001  --no-market-review "$@"
    success "A\u80a1\u5206\u6790\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd52.5: ETF\u5206\u6790
test_etf() {
    header "\u6d4b\u8bd5\u573a\u666f: ETF\u5206\u6790"
    info "\u5206\u6790ETF: 563230(\u536b\u661fETF)"
    python3 main.py --stocks 563230,512400 --no-market-review "$@"
    success "ETF\u5206\u6790\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd53: \u6e2f\u80a1\u5206\u6790
test_hk_stock() {
    header "\u6d4b\u8bd5\u573a\u666f: \u6e2f\u80a1\u5206\u6790"
    info "\u5206\u6790\u6e2f\u80a1: hk00700(\u817e\u8baf), hk09988(\u963f\u91cc)"
    python3 main.py --stocks hk00700,hk09988 --no-market-review "$@"
    success "\u6e2f\u80a1\u5206\u6790\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd54: \u7f8e\u80a1\u5206\u6790
test_us_stock() {
    header "\u6d4b\u8bd5\u573a\u666f: \u7f8e\u80a1\u5206\u6790"
    info "\u5206\u6790\u7f8e\u80a1: AAPL(\u82f9\u679c), TSLA(\u7279\u65af\u62c9)"
    # \u5141\u8bb8\u900f\u4f20\u53c2\u6570，\u9ed8\u8ba4\u4e0d\u5e26 --no-notify
    python3 main.py --stocks AAPL --no-market-review "$@"
    success "\u7f8e\u80a1\u5206\u6790\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd55: \u6df7\u5408\u5e02\u573a
test_mixed() {
    header "\u6d4b\u8bd5\u573a\u666f: \u6df7\u5408\u5e02\u573a\u5206\u6790"
    info "\u5206\u6790\u6df7\u5408\u5e02\u573a: 600519(A\u80a1), hk00700(\u6e2f\u80a1), AAPL(\u7f8e\u80a1)"
    python3 main.py --stocks 600519,hk00700,AAPL --no-market-review
    success "\u6df7\u5408\u5e02\u573a\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd56: \u5355\u80a1\u63a8\u9001\u6a21\u5f0f
test_single() {
    header "\u6d4b\u8bd5\u573a\u666f: \u5355\u80a1\u63a8\u9001\u6a21\u5f0f"
    info "\u6d4b\u8bd5\u5355\u80a1\u63a8\u9001\u6a21\u5f0f..."
    python3 main.py --stocks 600519 --single-notify --no-market-review
    success "\u5355\u80a1\u63a8\u9001\u6a21\u5f0f\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd57: dry-run\u6a21\u5f0f
test_dry_run() {
    header "\u6d4b\u8bd5\u573a\u666f: Dry-Run \u6a21\u5f0f"
    info "\u4ec5\u83b7\u53d6\u6570\u636e，\u4e0d\u8fdb\u884cAI\u5206\u6790..."
    python3 main.py --stocks 600519,AAPL --dry-run --no-notify
    success "Dry-Run \u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd58: \u5b8c\u6574\u6d41\u7a0b
test_full() {
    header "\u6d4b\u8bd5\u573a\u666f: \u5b8c\u6574\u6d41\u7a0b"
    info "\u8fd0\u884c\u5b8c\u6574\u5206\u6790\u6d41\u7a0b（\u4e2a\u80a1+\u5927\u76d8）..."
    python3 main.py --stocks 600519 --no-notify
    success "\u5b8c\u6574\u6d41\u7a0b\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd59: \u5feb\u901f\u6d4b\u8bd5
test_quick() {
    header "\u6d4b\u8bd5\u573a\u666f: \u5feb\u901f\u6d4b\u8bd5"
    info "\u5355\u53ea\u80a1\u7968\u5feb\u901f\u6d4b\u8bd5..."
    python3 main.py --stocks 600519 --no-market-review --no-notify "$@"
    success "\u5feb\u901f\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd510: \u4ee3\u7801\u8bc6\u522b\u6d4b\u8bd5
test_code_recognition() {
    header "\u6d4b\u8bd5\u573a\u666f: \u4ee3\u7801\u8bc6\u522b"
    info "\u6d4b\u8bd5\u80a1\u7968\u4ee3\u7801\u8bc6\u522b\u903b\u8f91..."

    python3 << 'PYTEST'
import sys
sys.path.insert(0, '.')
from data_provider.akshare_fetcher import _is_hk_code, _is_us_code

test_cases = [
    # (\u4ee3\u7801, \u9884\u671fHK, \u9884\u671fUS, \u63cf\u8ff0)
    ("AAPL", False, True, "\u7f8e\u80a1-\u82f9\u679c"),
    ("TSLA", False, True, "\u7f8e\u80a1-\u7279\u65af\u62c9"),
    ("BRK.B", False, True, "\u7f8e\u80a1-\u4f2f\u514b\u5e0c\u5c14B"),
    ("hk00700", True, False, "\u6e2f\u80a1-\u817e\u8baf"),
    ("HK09988", True, False, "\u6e2f\u80a1-\u963f\u91cc"),
    ("600519", False, False, "A\u80a1-\u8305\u53f0"),
    ("000001", False, False, "A\u80a1-\u5e73\u5b89"),
]

print("\n\u80a1\u7968\u4ee3\u7801\u8bc6\u522b\u6d4b\u8bd5:")
print("-" * 60)
all_pass = True
for code, exp_hk, exp_us, desc in test_cases:
    is_hk = _is_hk_code(code)
    is_us = _is_us_code(code)
    hk_ok = is_hk == exp_hk
    us_ok = is_us == exp_us
    status = "✅" if (hk_ok and us_ok) else "❌"
    all_pass = all_pass and hk_ok and us_ok
    print(f"{status} {code:10} | HK:{is_hk:5} US:{is_us:5} | {desc}")

print("-" * 60)
print(f"{'✅ \u6240\u6709\u6d4b\u8bd5\u901a\u8fc7!' if all_pass else '❌ \u6709\u6d4b\u8bd5\u5931\u8d25!'}")
sys.exit(0 if all_pass else 1)
PYTEST

    success "\u4ee3\u7801\u8bc6\u522b\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd511: YFinance\u4ee3\u7801\u8f6c\u6362\u6d4b\u8bd5
test_yfinance_convert() {
    header "\u6d4b\u8bd5\u573a\u666f: YFinance \u4ee3\u7801\u8f6c\u6362"
    info "\u6d4b\u8bd5YFinance\u4ee3\u7801\u8f6c\u6362\u903b\u8f91..."

    python3 << 'PYTEST'
import sys
sys.path.insert(0, '.')
from data_provider.yfinance_fetcher import YfinanceFetcher

fetcher = YfinanceFetcher()

test_cases = [
    ("AAPL", "AAPL", "\u7f8e\u80a1"),
    ("tsla", "TSLA", "\u7f8e\u80a1\u5c0f\u5199"),
    ("BRK.B", "BRK.B", "\u7f8e\u80a1\u7279\u6b8a"),
    ("hk00700", "0700.HK", "\u6e2f\u80a1"),
    ("HK09988", "9988.HK", "\u6e2f\u80a1\u5927\u5199"),
    ("600519", "600519.SS", "A\u80a1\u6caa\u5e02"),
    ("000001", "000001.SZ", "A\u80a1\u6df1\u5e02"),
    ("300750", "300750.SZ", "A\u80a1\u521b\u4e1a\u677f"),
]

print("\nYFinance \u4ee3\u7801\u8f6c\u6362\u6d4b\u8bd5:")
print("-" * 60)
all_pass = True
for input_code, expected, desc in test_cases:
    result = fetcher._convert_stock_code(input_code)
    status = "✅" if result == expected else "❌"
    all_pass = all_pass and (result == expected)
    print(f"{status} {input_code:10} -> {result:12} (\u671f\u671b: {expected:12}) | {desc}")

print("-" * 60)
print(f"{'✅ \u6240\u6709\u6d4b\u8bd5\u901a\u8fc7!' if all_pass else '❌ \u6709\u6d4b\u8bd5\u5931\u8d25!'}")
sys.exit(0 if all_pass else 1)
PYTEST

    success "YFinance \u4ee3\u7801\u8f6c\u6362\u6d4b\u8bd5\u5b8c\u6210"
}

# \u6d4b\u8bd512: \u8bed\u6cd5\u68c0\u67e5
test_syntax() {
    header "\u6d4b\u8bd5\u573a\u666f: Python \u8bed\u6cd5\u68c0\u67e5"
    info "\u68c0\u67e5\u6240\u6709Python\u6587\u4ef6\u8bed\u6cd5..."

    python3 -m py_compile main.py src/config.py src/notification.py \
        data_provider/akshare_fetcher.py \
        data_provider/yfinance_fetcher.py \
        bot/commands/analyze.py

    success "\u8bed\u6cd5\u68c0\u67e5\u901a\u8fc7"
}

# \u6d4b\u8bd513: Flake8 \u9759\u6001\u68c0\u67e5
test_flake8() {
    header "\u6d4b\u8bd5\u573a\u666f: Flake8 \u9759\u6001\u68c0\u67e5"
    info "\u8fd0\u884c Flake8 \u68c0\u67e5\u4e25\u91cd\u9519\u8bef..."

    if command -v flake8 &> /dev/null; then
        flake8 main.py src/config.py src/notification.py --select=F821,E999 --max-line-length=120
        success "Flake8 \u68c0\u67e5\u901a\u8fc7"
    else
        warn "Flake8 \u672a\u5b89\u88c5，\u8df3\u8fc7\u68c0\u67e5"
    fi
}

# \u8fd0\u884c\u6240\u6709\u6d4b\u8bd5
test_all() {
    header "\u8fd0\u884c\u6240\u6709\u6d4b\u8bd5"

    test_syntax
    test_code_recognition
    test_yfinance_convert
    test_flake8

    echo ""
    info "\u4ee5\u4e0b\u6d4b\u8bd5\u9700\u8981\u7f51\u7edc\u548cAPI\u914d\u7f6e，\u53ef\u80fd\u4f1a\u5931\u8d25:"
    echo ""

    test_dry_run || warn "Dry-Run \u6d4b\u8bd5\u5931\u8d25（\u53ef\u80fd\u662f\u7f51\u7edc\u95ee\u9898）"
    test_quick || warn "\u5feb\u901f\u6d4b\u8bd5\u5931\u8d25（\u53ef\u80fd\u662fAPI\u95ee\u9898）"

    success "\u6240\u6709\u6d4b\u8bd5\u5b8c\u6210!"
}

# ==================== \u4e3b\u7a0b\u5e8f ====================

main() {
    header "A\u80a1/\u6e2f\u80a1/\u7f8e\u80a1 \u667a\u80fd\u5206\u6790\u7cfb\u7edf - \u6d4b\u8bd5"

    check_python
    check_deps

    case "${1:-help}" in
        market)
            shift
            test_market "$@"
            ;;
        a-stock|a_stock|astock)
            shift
            test_a_stock "$@"
            ;;
        etf)
            shift
            test_etf "$@"
            ;;
        hk-stock|hk_stock|hkstock|hk)
            shift
            test_hk_stock "$@"
            ;;
        us-stock|us_stock|usstock|us)
            shift
            test_us_stock "$@"
            ;;
        mixed|mix)
            shift
            test_mixed "$@"
            ;;
        single)
            shift
            test_single "$@"
            ;;
        dry-run|dryrun|dry)
            shift
            test_dry_run "$@"
            ;;
        full)
            shift
            test_full "$@"
            ;;
        quick|q)
            shift
            test_quick "$@"
            ;;
        code|recognition)
            shift
            test_code_recognition "$@"
            ;;
        yfinance|yf)
            shift
            test_yfinance_convert "$@"
            ;;
        syntax)
            shift
            test_syntax "$@"
            ;;
        flake8|lint)
            shift
            test_flake8 "$@"
            ;;
        all)
            shift
            test_all "$@"
            ;;
        help|--help|-h|*)
            echo "\u4f7f\u7528\u65b9\u6cd5: $0 [\u6d4b\u8bd5\u573a\u666f]"
            echo ""
            echo "\u6d4b\u8bd5\u573a\u666f:"
            echo "  market      - \u4ec5\u5927\u76d8\u590d\u76d8"
            echo "  a-stock     - A\u80a1\u4e2a\u80a1\u5206\u6790"
            echo "  etf         - ETF\u5206\u6790"
            echo "  hk-stock    - \u6e2f\u80a1\u5206\u6790"
            echo "  us-stock    - \u7f8e\u80a1\u5206\u6790"
            echo "  mixed       - \u6df7\u5408\u5e02\u573a\u5206\u6790"
            echo "  single      - \u5355\u80a1\u63a8\u9001\u6a21\u5f0f"
            echo "  dry-run     - \u4ec5\u83b7\u53d6\u6570\u636e"
            echo "  full        - \u5b8c\u6574\u6d41\u7a0b"
            echo "  quick       - \u5feb\u901f\u6d4b\u8bd5（\u63a8\u8350）"
            echo "  code        - \u4ee3\u7801\u8bc6\u522b\u6d4b\u8bd5"
            echo "  yfinance    - YFinance\u8f6c\u6362\u6d4b\u8bd5"
            echo "  syntax      - \u8bed\u6cd5\u68c0\u67e5"
            echo "  flake8      - \u9759\u6001\u68c0\u67e5"
            echo "  all         - \u8fd0\u884c\u6240\u6709\u6d4b\u8bd5"
            echo ""
            echo "\u793a\u4f8b:"
            echo "  $0 quick     # \u5feb\u901f\u6d4b\u8bd5"
            echo "  $0 us-stock  # \u6d4b\u8bd5\u7f8e\u80a1"
            echo "  $0 code      # \u6d4b\u8bd5\u4ee3\u7801\u8bc6\u522b"
            echo "  $0 all       # \u8fd0\u884c\u6240\u6709\u6d4b\u8bd5"
            ;;
    esac
}

main "$@"
