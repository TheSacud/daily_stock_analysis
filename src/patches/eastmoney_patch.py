import hashlib
import random
import secrets
import threading
import time
import requests
import json
import uuid
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

original_request = requests.Session.request

ua = UserAgent()


class AuthCache:
    def __init__(self):
        self.data = None
        self.expire_at = 0
        self.lock = threading.Lock()
        self.ttl = 20


_cache = AuthCache()


class PatchSign:
    def __init__(self):
        self.patched = False

    def set_patch(self, patched):
        self.patched = patched

    def is_patched(self):
        return self.patched


_patch_sign = PatchSign()


def _get_nid(user_agent):
    """
    \u83b7\u53d6Eastmoney\u7684 NID \u6388\u6743\u4ee4\u724c

    Args:
        user_agent (str): user\u4ee3\u7406\u5b57\u7b26\u4e32; \u7528\u4e8e\u6a21\u62df\u4e0d\u540c\u7684\u6d4f\u89c8\u5668\u8bbfask

    Returns:
        str: \u8fd4\u56de\u83b7\u53d6\u5230\u7684 NID \u6388\u6743\u4ee4\u724c; \u5982\u679cfetch failed\u5219\u8fd4\u56de None

    \u529f\u80fd\u8bf4\u660e:
        \u8be5\u51fd\u6570\u901a\u8fc7\u5411Eastmoney\u7684\u6388\u6743\u63a5\u53e3\u53d1\u9001request\u6765\u83b7\u53d6 NID \u4ee4\u724c;
        \u7528\u4e8e\u540e\u7eeddata\u8bbfask\u6388\u6743.\u51fd\u6570\u5b9e\u73b0\u4e86cache\u673a\u5236\u6765\u907f\u514d\u9891\u7e41request.
    """
    now = time.time()
    # \u68c0checkcache\u662f\u5426\u6709\u6548; \u907f\u514d\u91cd\u590drequest
    if _cache.data and now < _cache.expire_at:
        return _cache.data
    # \u4f7f\u7528\u7ebf\u7a0b\u9501\u786e\u4fdd\u5e76\u53d1\u5b89\u5168
    with _cache.lock:
        try:
            def generate_uuid_md5():
                """
                \u751f\u6210 UUID \u5e76\u5bf9\u5176\u8fdb\u884c MD5 \u54c8\u5e0c\u5904\u7406
                :return: MD5 \u54c8\u5e0c\u503c (32characters\u5341\u516d\u8fdb\u5236\u5b57\u7b26\u4e32)
                """
                # \u751f\u6210 UUID
                unique_id = str(uuid.uuid4())
                # \u5bf9 UUID \u8fdb\u884c MD5 \u54c8\u5e0c
                md5_hash = hashlib.md5(unique_id.encode('utf-8')).hexdigest()
                return md5_hash

            def generate_st_nvi():
                """
                \u751f\u6210 st_nvi \u503c\u7684\u65b9\u6cd5
                :return: \u8fd4\u56de\u751f\u6210\u7684 st_nvi \u503c
                """
                HASH_LENGTH = 4  # \u622a\u53d6\u54c8\u5e0c\u503c\u7684\u524d\u51e0characters

                def generate_random_string(length=21):
                    """
                    \u751f\u6210\u6307\u5b9a\u957f\u5ea6\u7684\u968f\u673a\u5b57\u7b26\u4e32
                    :param length: \u5b57\u7b26\u4e32\u957f\u5ea6; default\u4e3a 21
                    :return: \u968f\u673a\u5b57\u7b26\u4e32
                    """
                    charset = "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict"
                    return ''.join(secrets.choice(charset) for _ in range(length))

                def sha256(input_str):
                    """
                    \u8ba1\u7b97 SHA-256 \u54c8\u5e0c\u503c
                    :param input_str: \u8f93\u5165\u5b57\u7b26\u4e32
                    :return: \u54c8\u5e0c\u503c (\u5341\u516d\u8fdb\u5236)
                    """
                    return hashlib.sha256(input_str.encode('utf-8')).hexdigest()

                random_str = generate_random_string()
                hash_prefix = sha256(random_str)[:HASH_LENGTH]
                return random_str + hash_prefix

            url = "https://anonflow2.eastmoney.com/backend/api/webreport"
            # \u968f\u673a\u9009\u62e9\u5c4f\u5e55\u5206\u8fa8\u7387; \u589e\u52a0request\u7684\u771f\u5b9e
            screen_resolution = random.choice(['1920X1080', '2560X1440', '3840X2160'])
            payload = json.dumps({
                "osPlatform": "Windows",
                "sourceType": "WEB",
                "osversion": "Windows 10.0",
                "language": "zh-CN",
                "timezone": "Asia/Shanghai",
                "webDeviceInfo": {
                    "screenResolution": screen_resolution,
                    "userAgent": user_agent,
                    "canvasKey": generate_uuid_md5(),
                    "webglKey": generate_uuid_md5(),
                    "fontKey": generate_uuid_md5(),
                    "audioKey": generate_uuid_md5()
                }
            })
            headers = {
                'Cookie': f'st_nvi={generate_st_nvi()}',
                'Content-Type': 'application/json'
            }
            # \u589e\u52a0\u8d85\u65f6; \u9632\u6b62\u65e0\u9650waiting
            response = requests.request("POST", url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()  # \u5bf9 4xx/5xx \u54cd\u5e94\u629b\u51fa HTTPError

            data = response.json()
            nid = data['data']['nid']

            _cache.data = nid
            _cache.expire_at = now + _cache.ttl
            return nid
        except requests.exceptions.RequestException as e:
            logger.warning(f"requestEastmoney\u6388\u6743\u63a5\u53e3failed: {e}")
            _cache.data = None
            # \u8be5\u63a5\u53e3requestfailed\u65f6; \u65b9\u6848\u53ef\u80fd\u5df2\u5931\u6548; \u540e\u7eed\u5927\u6982\u7387\u4f1a\u7ee7\u7eedfailed; \u56e0\u65e0\u6cd5success\u83b7\u53d6; \u4e0b\u6b21\u4f1a\u7ee7\u7eedrequest; \u8bbe\u7f6e\u8f83\u957f\u8fc7\u671f\u65f6\u95f4; \u53ef\u907f\u514d\u9891\u7e41request
            _cache.expire_at = now + 5 * 60
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"\u89e3\u6790Eastmoney\u6388\u6743\u63a5\u53e3\u54cd\u5e94failed: {e}")
            _cache.data = None
            # \u8be5\u63a5\u53e3requestfailed\u65f6; \u65b9\u6848\u53ef\u80fd\u5df2\u5931\u6548; \u540e\u7eed\u5927\u6982\u7387\u4f1a\u7ee7\u7eedfailed; \u56e0\u65e0\u6cd5success\u83b7\u53d6; \u4e0b\u6b21\u4f1a\u7ee7\u7eedrequest; \u8bbe\u7f6e\u8f83\u957f\u8fc7\u671f\u65f6\u95f4; \u53ef\u907f\u514d\u9891\u7e41request
            _cache.expire_at = now + 5 * 60
            return None


def eastmoney_patch():
    if _patch_sign.is_patched():
        return

    def patched_request(self, method, url, **kwargs):
        # \u6392\u9664\u975e\u76ee\u6807\u57df\u540d
        is_target = any(
            d in (url or "")
            for d in [
                "fund.eastmoney.com",
                "push2.eastmoney.com",
                "push2his.eastmoney.com",
            ]
        )
        if not is_target:
            return original_request(self, method, url, **kwargs)
        # \u83b7\u53d6\u4e00\u4e2a\u968f\u673a\u7684 User-Agent
        user_agent = ua.random
        # \u5904\u7406 Headers: \u786e\u4fdd\u4e0d\u7834\u574f\u4e1a\u52a1code\u4f20\u5165\u7684 headers
        headers = kwargs.get("headers", {})
        headers["User-Agent"] = user_agent
        nid = _get_nid(user_agent)
        if nid:
            headers["Cookie"] = f"nid18={nid}"
        kwargs["headers"] = headers
        # \u968f\u673a\u4f11\u7720; \u964dLow\u88ab\u5c01\u98ce\u9669
        sleep_time = random.uniform(1, 4)
        time.sleep(sleep_time)
        return original_request(self, method, url, **kwargs)

    # \u5168\u5c40\u66ff\u6362 Session \u7684 request \u5165\u53e3
    requests.Session.request = patched_request
    _patch_sign.set_patch(True)
