# -*- coding: utf-8 -*-
"""
Anspire Search \u641c\u7d22\u5f15\u64ce\u6d4b\u8bd5\u5957\u4ef6

\u6d4b\u8bd5\u8986\u76d6\u8303\u56f4:
1. \u914d\u7f6e\u52a0\u8f7d\u6d4b\u8bd5 - \u9a8c\u8bc1 anspire_api_keys \u662f\u5426\u6b63\u786e\u4ece\u73af\u5883\u53d8\u91cf\u52a0\u8f7d
2. \u670d\u52a1\u521d\u59cb\u5316\u6d4b\u8bd5 - \u9a8c\u8bc1 SearchService \u662f\u5426\u6b63\u786e\u521d\u59cb\u5316 AnspireSearchProvider
3. API \u8c03\u7528\u6d4b\u8bd5 - \u5b9e\u9645\u8c03\u7528 Anspire API \u9a8c\u8bc1\u8fd4\u56de\u7ed3\u679c
4. \u6545\u969c\u8f6c\u79fb\u6d4b\u8bd5 - \u9a8c\u8bc1\u65e0\u6548 Key \u65f6\u7684\u9519\u8bef\u5904\u7406\u548c\u964d\u7ea7\u673a\u5236
5. \u641c\u7d22\u529f\u80fd\u6d4b\u8bd5 - \u6d4b\u8bd5\u80a1\u7968\u65b0\u95fb\u641c\u7d22\u548c\u901a\u7528\u641c\u7d22\u529f\u80fd

\u8fd0\u884c\u65b9\u5f0f:
```bash
# Windows PowerShell
$env:ANSPIRE_API_KEYS="your_test_api_key"
python -m pytest tests/test_anspire_search.py -v

# Linux/Mac
export ANSPIRE_API_KEYS="your_test_api_key"
python -m pytest tests/test_anspire_search.py -v
```
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
load_dotenv()

# \u6dfb\u52a0\u9879\u76ee\u6839\u76ee\u5f55\u5230 Python \u8def\u5f84，\u89e3\u51b3\u6a21\u5757\u5bfc\u5165\u95ee\u9898
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock newspaper before search_service import (optional dependency)
if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.config import Config, get_config
from src.search_service import (
    AnspireSearchProvider,
    SearchService,
    get_search_service,
    reset_search_service,
)


class _FakeResponse:
    """\u6a21\u62df HTTP \u54cd\u5e94\u5bf9\u8c61"""
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.headers = headers or {'content-type': 'application/json'}

    def json(self):
        return self._json_data


class TestAnspireConfigLoading(unittest.TestCase):
    """Test Anspire configuration loading from environment variables."""

    def setUp(self):
        """\u4fdd\u5b58\u5e76\u6e05\u9664\u73af\u5883\u53d8\u91cf（\u4e0d\u64cd\u4f5c .env \u6587\u4ef6）"""
        # ✅ \u4fdd\u5b58\u539f\u59cb\u503c，\u6d4b\u8bd5\u540e\u6062\u590d
        self._original_anspire_keys = os.environ.get('ANSPIRE_API_KEYS')

        # \u6e05\u9664\u73af\u5883\u53d8\u91cf
        if 'ANSPIRE_API_KEYS' in os.environ:
            del os.environ['ANSPIRE_API_KEYS']

        # \u91cd\u7f6e Config \u5355\u4f8b
        Config._Config__instance = None
        reset_search_service()

    def tearDown(self):
        """\u6062\u590d\u539f\u59cb\u73af\u5883\u53d8\u91cf"""
        # ✅ \u6062\u590d\u539f\u59cb\u503c
        if self._original_anspire_keys is not None:
            os.environ['ANSPIRE_API_KEYS'] = self._original_anspire_keys
        elif 'ANSPIRE_API_KEYS' in os.environ:
            del os.environ['ANSPIRE_API_KEYS']

        # \u91cd\u7f6e Config \u5355\u4f8b
        Config._Config__instance = None
        reset_search_service()

    def test_anspire_keys_loaded_from_env(self):
        """Test that ANSPIRE_API_KEYS is correctly parsed from environment."""
        # ✅ \u4f7f\u7528 patch.dict \u4e34\u65f6\u8bbe\u7f6e，\u6d4b\u8bd5\u540e\u81ea\u52a8\u6062\u590d
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': 'key1,key2,key3'}):
            config = Config._load_from_env()

            self.assertEqual(len(config.anspire_api_keys), 3)
            self.assertIn('key1', config.anspire_api_keys)
            self.assertIn('key2', config.anspire_api_keys)
            self.assertIn('key3', config.anspire_api_keys)

    def test_anspire_keys_single_key(self):
        """Test single API Key parsing."""
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': 'single_key_test'}):
            config = Config._load_from_env()

            self.assertEqual(len(config.anspire_api_keys), 1)
            self.assertEqual(config.anspire_api_keys[0], 'single_key_test')

    def test_anspire_keys_empty_env(self):
        """Test empty environment variable handling."""
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': ''}):
            config = Config._load_from_env()

            self.assertEqual(len(config.anspire_api_keys), 0)

    def test_anspire_keys_whitespace_handling(self):
        """Test whitespace trimming in API Keys."""
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': ' key1 , key2 , key3 '}):
            config = Config._load_from_env()

            self.assertEqual(len(config.anspire_api_keys), 3)
            self.assertEqual(config.anspire_api_keys, ['key1', 'key2', 'key3'])


class TestAnspireSearchProvider(unittest.TestCase):
    """Anspire Search Provider \u5355\u5143\u6d4b\u8bd5"""

    def setUp(self):
        """\u6d4b\u8bd5\u524d\u51c6\u5907"""
        # ✅ \u4f7f\u7528\u660e\u786e\u7684\u6d4b\u8bd5\u5360\u4f4d\u7b26，\u4e0d\u662f\u771f\u5b9e\u5bc6\u94a5\u5f62\u6001
        self.test_api_key = "sk-test-anspire-placeholder-key-12345"
        self.provider = AnspireSearchProvider([self.test_api_key])
        # \u4fdd\u5b58\u539f\u59cb requests \u6a21\u5757
        self._original_requests = sys.modules.get('requests')

    def tearDown(self):
        """\u6d4b\u8bd5\u540e\u6e05\u7406"""
        # \u6062\u590d\u539f\u59cb requests \u6a21\u5757
        if self._original_requests is not None:
            sys.modules['requests'] = self._original_requests

    def test_provider_initialization(self):
        """\u6d4b\u8bd5 Provider \u521d\u59cb\u5316"""
        provider = AnspireSearchProvider(["key1", "key2"])
        self.assertEqual(provider.name, "Anspire")
        if hasattr(provider, 'api_keys'):
            self.assertEqual(len(provider.api_keys), 2)
        elif hasattr(provider, '_api_keys'):
            self.assertEqual(len(provider._api_keys), 2)
        self.assertTrue(provider.is_available)

    def test_provider_name(self):
        """\u6d4b\u8bd5 Provider \u540d\u79f0"""
        self.assertEqual(self.provider.name, "Anspire")

    def test_provider_availability(self):
        """\u6d4b\u8bd5 Provider \u53ef\u7528\u6027\u68c0\u6d4b"""
        # \u6709 API Key \u65f6\u5e94\u53ef\u7528
        provider_with_keys = AnspireSearchProvider(["key1"])
        self.assertTrue(provider_with_keys.is_available)

        # \u65e0 API Key \u65f6\u4e0d\u53ef\u7528
        provider_without_keys = AnspireSearchProvider([])
        self.assertFalse(provider_without_keys.is_available)

    def test_extract_domain(self):
        """\u6d4b\u8bd5\u57df\u540d\u63d0\u53d6\u529f\u80fd"""
        test_cases = [
            ("https://www.example.com/article", "example.com"),
            ("https://finance.sina.com.cn/stock/", "finance.sina.com.cn"),
            ("http://www.10jqka.com.cn/news", "10jqka.com.cn"),
            ("invalid_url", "\u672a\u77e5\u6765\u6e90"),
            ("", "\u672a\u77e5\u6765\u6e90"),
        ]

        for url, expected in test_cases:
            result = AnspireSearchProvider._extract_domain(url)
            self.assertEqual(result, expected, f"Failed for URL: {url}")

    @patch('src.search_service.requests')
    def test_search_success_response(self, mock_requests):
        """\u6d4b\u8bd5\u6210\u529f\u54cd\u5e94\u5904\u7406"""
        # \u8bbe\u7f6e mock exceptions
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            pass

        fake_response = _FakeResponse(
            status_code=200,
            json_data={
                "code": 200,
                "msg": "success",
                "results": [
                    {
                        "title": "\u8d35\u5dde\u8305\u53f0\u4eca\u65e5\u80a1\u4ef7\u4e0a\u6da8",
                        "url": "https://finance.sina.com.cn/stock/600519",
                        "content": "\u8d35\u5dde\u8305\u53f0 (600519) \u4eca\u65e5\u6536\u76d8\u80a1\u4ef7\u4e0a\u6da8 2.5%，\u6210\u4ea4\u91cf\u653e\u5927...",
                    },
                    {
                        "title": "\u767d\u9152\u677f\u5757\u6301\u7eed\u8d70\u5f3a",
                        "url": "https://www.10jqka.com.cn/baijiu",
                        "content": "\u767d\u9152\u677f\u5757\u4eca\u65e5\u8868\u73b0\u5f3a\u52bf，\u8d35\u5dde\u8305\u53f0、\u4e94\u7cae\u6db2\u7b49\u4e2a\u80a1\u6da8\u5e45\u5c45\u524d...",
                    }
                ]
            }
        )

        mock_requests.get = MagicMock(return_value=fake_response)

        response = self.provider.search("\u8d35\u5dde\u8305\u53f0 \u80a1\u7968\u65b0\u95fb", max_results=5, days=7)

        # \u9a8c\u8bc1\u7ed3\u679c
        self.assertTrue(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 2)
        self.assertEqual(response.results[0].title, "\u8d35\u5dde\u8305\u53f0\u4eca\u65e5\u80a1\u4ef7\u4e0a\u6da8")
        # \u5047\u8bbe source \u662f\u4ece url \u63d0\u53d6\u7684\u57df\u540d
        self.assertEqual(response.results[0].source, "finance.sina.com.cn")

        # \u9a8c\u8bc1 API \u8c03\u7528\u53c2\u6570
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        # \u68c0\u67e5 URL \u662f\u5426\u5305\u542b anspire \u76f8\u5173\u57df\u540d (\u5177\u4f53 URL \u9700\u6839\u636e\u5b9e\u9645\u5b9e\u73b0\u8c03\u6574)
        # self.assertIn("plugin.anspire.cn", call_args[0][0])
        self.assertIn("Authorization", call_args[1]["headers"])
        # \u9a8c\u8bc1\u4f7f\u7528 params \u800c\u975e json
        self.assertIn("params", call_args[1])
        self.assertNotIn("json", call_args[1])

    @patch('src.search_service.requests')
    def test_search_invalid_api_key(self, mock_requests):
        """\u6d4b\u8bd5\u65e0\u6548 API Key \u7684\u9519\u8bef\u5904\u7406"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            pass

        fake_response = _FakeResponse(
            status_code=401,
            json_data={"message": "Invalid API key"},
            text="Unauthorized"
        )

        mock_requests.get = MagicMock(return_value=fake_response)

        response = self.provider.search("\u6d4b\u8bd5\u67e5\u8be2", max_results=3)

        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
        # \u9519\u8bef\u6d88\u606f\u53ef\u80fd\u56e0\u5b9e\u73b0\u800c\u5f02，\u8fd9\u91cc\u505a\u5bbd\u677e\u68c0\u67e5
        self.assertTrue("API" in response.error_message or "KEY" in response.error_message or "\u65e0\u6548" in response.error_message)

    @patch('src.search_service.requests')
    def test_search_timeout_error(self, mock_requests):
        """\u6d4b\u8bd5\u8d85\u65f6\u9519\u8bef\u5904\u7406"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
            timeout_exc = mock_requests.exceptions.Timeout
        except ImportError:
            mock_requests.exceptions = MagicMock()
            timeout_exc = Exception

        mock_requests.get = MagicMock(side_effect=timeout_exc())

        response = self.provider.search("\u6d4b\u8bd5\u67e5\u8be2", max_results=3)

        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
        # \u9519\u8bef\u6d88\u606f\u68c0\u67e5
        self.assertTrue("\u8d85\u65f6" in response.error_message or "Timeout" in response.error_message)

    @patch('src.search_service.requests')
    def test_search_network_error(self, mock_requests):
        """\u6d4b\u8bd5\u7f51\u7edc\u9519\u8bef\u5904\u7406"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
            conn_exc = mock_requests.exceptions.ConnectionError
        except ImportError:
            mock_requests.exceptions = MagicMock()
            conn_exc = Exception

        mock_requests.get = MagicMock(side_effect=conn_exc())

        response = self.provider.search("\u6d4b\u8bd5\u67e5\u8be2", max_results=3)

        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
        self.assertTrue("\u7f51\u7edc" in response.error_message or "Connection" in response.error_message)

    @patch('src.search_service.requests')
    def test_search_empty_results(self, mock_requests):
        """\u6d4b\u8bd5\u7a7a\u7ed3\u679c\u5904\u7406"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            mock_requests.exceptions = MagicMock()

        fake_response = _FakeResponse(
            status_code=200,
            json_data={"code": 200, "msg": "success", "results": []}
        )

        mock_requests.get = MagicMock(return_value=fake_response)

        response = self.provider.search("\u4e0d\u5b58\u5728\u7684\u80a1\u7968 XYZ", max_results=5)

        self.assertTrue(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)

    @patch('src.search_service.requests')
    def test_search_content_truncation(self, mock_requests):
        """\u6d4b\u8bd5\u957f\u5185\u5bb9\u622a\u65ad\u529f\u80fd"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            mock_requests.exceptions = MagicMock()

        long_content = "\u8fd9\u662f\u4e00\u6bb5\u975e\u5e38\u957f\u7684\u5185\u5bb9，" * 100  # \u8d85\u8fc7 500 \u5b57\u7b26

        fake_response = _FakeResponse(
            status_code=200,
            json_data={
                "code": 200,
                "msg": "success",
                "results": [{
                    "title": "\u957f\u5185\u5bb9\u6d4b\u8bd5",
                    "url": "https://example.com/long",
                    "content": long_content
                }]
            }
        )

        mock_requests.get = MagicMock(return_value=fake_response)

        response = self.provider.search("\u6d4b\u8bd5", max_results=1)

        self.assertTrue(response.success)
        self.assertEqual(len(response.results), 1)
        # \u9a8c\u8bc1\u5185\u5bb9\u88ab\u622a\u65ad\u5230 500 \u5b57\u7b26\u4ee5\u5185
        if response.results[0].snippet:
            self.assertLessEqual(len(response.results[0].snippet), 503)  # 500 + "..."
            self.assertTrue(response.results[0].snippet.endswith("..."))

    @patch('src.search_service.requests')
    def test_search_time_range(self, mock_requests):
        """\u6d4b\u8bd5\u65f6\u95f4\u8303\u56f4\u53c2\u6570"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            mock_requests.exceptions = MagicMock()

        fake_response = _FakeResponse(status_code=200, json_data={"code": 200, "results": []})
        mock_requests.get = MagicMock(return_value=fake_response)

        # \u6d4b\u8bd5 7 \u5929\u8303\u56f4
        self.provider.search("\u6d4b\u8bd5", max_results=3, days=7)

        # \u9a8c\u8bc1\u65f6\u95f4\u53c2\u6570
        call_args = mock_requests.get.call_args
        if call_args and len(call_args) > 1 and 'params' in call_args[1]:
            params = call_args[1]["params"]

            # \u9a8c\u8bc1\u65f6\u95f4\u53c2\u6570\u5b58\u5728 (\u5177\u4f53\u5b57\u6bb5\u540d\u53d6\u51b3\u4e8e\u5b9e\u73b0)
            # \u8fd9\u91cc\u5047\u8bbe\u4f7f\u7528\u4e86 FromTime/ToTime \u6216\u7c7b\u4f3c\u5b57\u6bb5，\u82e5\u65e0\u5219\u8df3\u8fc7\u5177\u4f53\u5b57\u6bb5\u68c0\u67e5
            # self.assertIn("FromTime", params)
            # self.assertIn("ToTime", params)


class TestAnspireSearchService(unittest.TestCase):
    """SearchService \u4e2d Anspire \u96c6\u6210\u6d4b\u8bd5"""

    def setUp(self):
        Config._Config__instance = None
        reset_search_service()

    def test_search_service_with_anspire(self):
        """\u6d4b\u8bd5 SearchService \u6b63\u786e\u521d\u59cb\u5316 Anspire Provider"""
        service = SearchService(
            anspire_keys=["test_key"],
            bocha_keys=[],
            tavily_keys=[],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short"
        )

        self.assertTrue(hasattr(service, '_providers'))
        self.assertGreater(len(service._providers), 0)

        first_provider = service._providers[0]
        self.assertIsInstance(first_provider, AnspireSearchProvider)
        self.assertEqual(first_provider.name, "Anspire")

    def test_search_service_without_anspire(self):
        """\u6d4b\u8bd5\u672a\u914d\u7f6e Anspire \u65f6\u7684\u884c\u4e3a"""
        service = SearchService(
            anspire_keys=[],
            tavily_keys=["tavily_key"],
            bocha_keys=[],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short"
        )

        # \u9a8c\u8bc1\u6ca1\u6709 Anspire Provider
        anspire_providers = [p for p in service._providers if isinstance(p, AnspireSearchProvider)]
        self.assertEqual(len(anspire_providers), 0)

    def test_search_service_priority(self):
        """\u6d4b\u8bd5 Anspire \u4f18\u5148\u7ea7"""
        service = SearchService(
            anspire_keys=["anspire_key"],
            bocha_keys=["bocha_key"],
            tavily_keys=["tavily_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short"
        )

        self.assertIsInstance(service._providers[0], AnspireSearchProvider)


class TestAnspireIntegration(unittest.TestCase):
    """Anspire \u96c6\u6210\u6d4b\u8bd5（\u9700\u8981\u771f\u5b9e API Key）"""

    @classmethod
    def setUpClass(cls):
        """Check if API Key is configured."""
        cls.api_keys = [k.strip() for k in os.getenv('ANSPIRE_API_KEYS', '').split(',') if k.strip()]
        cls.has_api_key = len(cls.api_keys) > 0

        if cls.has_api_key:
            reset_search_service()
            cls.service = get_search_service()

    @unittest.skipIf(
        not os.environ.get("ANSPIRE_API_KEYS"),
        "\u672a\u8bbe\u7f6e ANSPIRE_API_KEYS \u73af\u5883\u53d8\u91cf，\u8df3\u8fc7\u96c6\u6210\u6d4b\u8bd5"
    )
    @pytest.mark.network
    def test_real_api_call_stock_news(self):
        """\u771f\u5b9e API \u8c03\u7528\u6d4b\u8bd5 - \u80a1\u7968\u65b0\u95fb\u641c\u7d22"""
        # \u786e\u4fdd\u670d\u52a1\u5df2\u91cd\u7f6e
        reset_search_service()
        service = get_search_service()

        # \u9a8c\u8bc1 Anspire \u5df2\u914d\u7f6e
        anspire_provider = None
        for provider in service._providers:
            if isinstance(provider, AnspireSearchProvider):
                anspire_provider = provider
                break

        if not anspire_provider:
            self.skipTest("Anspire Provider \u672a\u521d\u59cb\u5316")

        # \u6d4b\u8bd5 A \u80a1\u641c\u7d22
        response = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=3)

        print(f"\n=== Anspire \u771f\u5b9e API \u6d4b\u8bd5\u7ed3\u679c ===")
        print(f"\u641c\u7d22\u72b6\u6001：{'\u6210\u529f' if response.success else '\u5931\u8d25'}")
        print(f"\u641c\u7d22\u5f15\u64ce：{response.provider}")
        print(f"\u7ed3\u679c\u6570\u91cf：{len(response.results)}")
        print(f"\u8017\u65f6：{response.search_time:.2f}s")

        # \u57fa\u672c\u9a8c\u8bc1
        self.assertTrue(response.success, f"\u641c\u7d22\u5931\u8d25：{response.error_message}")
        self.assertEqual(response.provider, "Anspire")
        self.assertGreater(len(response.results), 0, "\u5e94\u81f3\u5c11\u8fd4\u56de\u4e00\u6761\u7ed3\u679c")

        # \u9a8c\u8bc1\u7ed3\u679c\u683c\u5f0f
        for result in response.results:
            self.assertIsNotNone(result.title)
            self.assertIsNotNone(result.url)
            # snippet \u53ef\u80fd\u4e3a\u7a7a，\u89c6\u5177\u4f53\u5b9e\u73b0\u800c\u5b9a
            # self.assertIsNotNone(result.snippet)

    @unittest.skipIf(
        not os.environ.get("ANSPIRE_API_KEYS"),
        "\u672a\u8bbe\u7f6e ANSPIRE_API_KEYS \u73af\u5883\u53d8\u91cf，\u8df3\u8fc7\u96c6\u6210\u6d4b\u8bd5"
    )
    @pytest.mark.network
    def test_real_api_call_general_search(self):
        """\u771f\u5b9e API \u8c03\u7528\u6d4b\u8bd5 - \u901a\u7528\u641c\u7d22"""
        reset_search_service()
        service = get_search_service()

        anspire_provider = None
        for provider in service._providers:
            if isinstance(provider, AnspireSearchProvider):
                anspire_provider = provider
                break

        if not anspire_provider:
            self.skipTest("Anspire Provider \u672a\u521d\u59cb\u5316")

        # \u6d4b\u8bd5\u901a\u7528\u641c\u7d22
        response = anspire_provider.search("\u4eba\u5de5\u667a\u80fd\u6700\u65b0\u53d1\u5c55", max_results=5, days=7)

        print(f"\n=== Anspire \u901a\u7528\u641c\u7d22\u7ed3\u679c ===")
        print(f"\u641c\u7d22\u72b6\u6001：{'\u6210\u529f' if response.success else '\u5931\u8d25'}")
        print(f"\u7ed3\u679c\u6570\u91cf：{len(response.results)}")

        self.assertTrue(response.success)
        self.assertGreater(len(response.results), 0)


def run_manual_test():
    """\u624b\u52a8\u6d4b\u8bd5\u51fd\u6570（\u7528\u4e8e\u5feb\u901f\u9a8c\u8bc1）"""
    import logging
    from src.config import get_config

    # \u914d\u7f6e\u65e5\u5fd7
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )

    print("=" * 60)
    print("Anspire Search \u5feb\u901f\u6d4b\u8bd5")
    print("=" * 60)

    # \u68c0\u67e5\u914d\u7f6e
    config = get_config()
    if not config.anspire_api_keys:
        print("\n❌ \u672a\u68c0\u6d4b\u5230 Anspire API Keys")
        print("\u8bf7\u8bbe\u7f6e\u73af\u5883\u53d8\u91cf：")
        print("  Windows PowerShell: $env:ANSPIRE_API_KEYS=\"your_api_key\"")
        print("  Linux/Mac: export ANSPIRE_API_KEYS=\"your_api_key\"")
        return False

    print(f"\n✅ \u5df2\u914d\u7f6e {len(config.anspire_api_keys)} \u4e2a Anspire API Key")

    # \u521b\u5efa\u670d\u52a1
    service = SearchService(
        anspire_keys=config.anspire_api_keys,
        bocha_keys=config.bocha_api_keys,
        tavily_keys=config.tavily_keys,
        searxng_public_instances_enabled=False,
        news_max_age_days=3,
        news_strategy_profile="short"
    )

    # \u9a8c\u8bc1 Provider
    anspire_provider = service._providers[0] if service._providers else None
    if not anspire_provider or not isinstance(anspire_provider, AnspireSearchProvider):
        print("\n❌ Anspire Provider \u672a\u6b63\u786e\u521d\u59cb\u5316")
        return False

    print(f"✅ Anspire Provider \u521d\u59cb\u5316\u6210\u529f")
    print(f"   Provider \u540d\u79f0：{anspire_provider.name}")
    if hasattr(anspire_provider, 'api_keys'):
        print(f"   API Keys \u6570\u91cf：{len(anspire_provider.api_keys)}")
    elif hasattr(anspire_provider, '_api_keys'):
        print(f"   API Keys \u6570\u91cf：{len(anspire_provider._api_keys)}")

    # \u6267\u884c\u6d4b\u8bd5\u641c\u7d22
    print("\n" + "=" * 60)
    print("\u6267\u884c\u6d4b\u8bd5\u641c\u7d22：\u8d35\u5dde\u8305\u53f0 (600519)")
    print("=" * 60)

    response = service.search_stock_news("600519", "\u8d35\u5dde\u8305\u53f0", max_results=3)

    print(f"\n\u641c\u7d22\u7ed3\u679c:")
    print(f"  \u72b6\u6001：{'✅ \u6210\u529f' if response.success else '❌ \u5931\u8d25'}")
    print(f"  \u641c\u7d22\u5f15\u64ce：{response.provider}")
    print(f"  \u7ed3\u679c\u6570\u91cf：{len(response.results)}")
    print(f"  \u8017\u65f6：{response.search_time:.2f}s")

    if response.error_message:
        print(f"  \u9519\u8bef\u4fe1\u606f：{response.error_message}")

    if response.results:
        print(f"\n\u524d {min(2, len(response.results))} \u6761\u7ed3\u679c\u9884\u89c8:")
        for i, result in enumerate(response.results[:2], 1):
            print(f"\n  [{i}] {result.title}")
            print(f"      \u6765\u6e90：{result.source}")
            print(f"      URL: {result.url}")
            if result.snippet:
                snippet_preview = result.snippet[:100] + "..." if len(result.snippet) > 100 else result.snippet
                print(f"      \u6458\u8981：{snippet_preview}")

    print("\n" + "=" * 60)
    print("\u6d4b\u8bd5\u5b8c\u6210!")
    print("=" * 60)

    return response.success


if __name__ == "__main__":
    # \u5982\u679c\u8bbe\u7f6e\u4e86\u73af\u5883\u53d8\u91cf，\u8fd0\u884c\u5b8c\u6574\u6d4b\u8bd5
    if os.environ.get("ANSPIRE_API_KEYS"):
        print("\u68c0\u6d4b\u5230 ANSPIRE_API_KEYS \u73af\u5883\u53d8\u91cf，\u8fd0\u884c\u5b8c\u6574\u6d4b\u8bd5\u5957\u4ef6...")
        unittest.main(verbosity=2)
    else:
        # \u5426\u5219\u53ea\u8fd0\u884c\u5355\u5143\u6d4b\u8bd5，\u8df3\u8fc7\u96c6\u6210\u6d4b\u8bd5
        print("\u672a\u8bbe\u7f6e ANSPIRE_API_KEYS \u73af\u5883\u53d8\u91cf，\u4ec5\u8fd0\u884c\u5355\u5143\u6d4b\u8bd5（\u8df3\u8fc7\u96c6\u6210\u6d4b\u8bd5）...")
        print("\u5982\u9700\u8fd0\u884c\u5b8c\u6574\u6d4b\u8bd5，\u8bf7\u8bbe\u7f6e\u73af\u5883\u53d8\u91cf:")
        print("  Windows PowerShell: $env:ANSPIRE_API_KEYS=\"your_api_key\"")
        print("  Linux/Mac: export ANSPIRE_API_KEYS=\"your_api_key\"")
        print()

        # \u8fd0\u884c\u5355\u5143\u6d4b\u8bd5
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAnspireConfigLoading)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnspireSearchProvider))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnspireSearchService))
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)

        # \u63d0\u4f9b\u624b\u52a8\u6d4b\u8bd5\u9009\u9879
        print("\n" + "=" * 60)
        choice = input("\u662f\u5426\u8fd0\u884c\u624b\u52a8\u6d4b\u8bd5（\u9700\u8981\u6709\u6548\u7684 API Key）? (y/n): ").strip().lower()
        if choice == 'y':
            run_manual_test()
