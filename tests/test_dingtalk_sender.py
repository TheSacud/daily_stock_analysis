import unittest
import json
from unittest.mock import patch, MagicMock
from src.notification_sender.dingtalk_sender import DingtalkSender
from src.config import Config

class TestDingtalkSender(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.dingtalk_webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=test_token"
        self.config.dingtalk_secret = "test_secret"
        self.sender = DingtalkSender(self.config)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        result = self.sender.send_to_dingtalk("Test content", "Test Title")
        self.assertTrue(result)
        mock_post.assert_called_once()

        called_url = mock_post.call_args[0][0]
        self.assertIn("timestamp=", called_url)
        self.assertIn("sign=", called_url)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_chunked_long_chinese_message_payload_size(self, mock_post):
        """\u6d4b\u8bd5\u8d85\u8fc7 20KB \u9650\u5236\u7684\u591a\u5b57\u8282\u4e2d\u6587\u957f\u6587\u672c\u4e0e\u957f\u6807\u9898，\u9a8c\u8bc1\u5b9e\u9645\u53d1\u9001\u7684 JSON payload \u5b57\u8282\u6570\u4e25\u683c\u9075\u5b88\u9650\u5236"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # \u751f\u6210\u8d85\u957f\u4e2d\u6587\u5185\u5bb9 (\u6bcf\u4e2a\u6c49\u5b57 3 bytes，\u751f\u6210\u7ea6 30,000 bytes \u7684\u6587\u672c)
        long_chinese_content = "\u80a1\u7968\u590d\u76d8" * 2500
        # \u751f\u6210\u6781\u7aef\u957f\u6807\u9898
        long_title = "\u8fd9\u662f\u4e00\u4e2a\u7528\u6765\u6d4b\u8bd5\u9489\u9489\u673a\u5668\u4eba\u6781\u7aef\u8fb9\u754c\u60c5\u51b5\u7684\u8d85\u957f\u8d85\u957f\u8d85\u957f\u8d85\u957f\u6807\u9898" * 10

        result = self.sender.send_to_dingtalk(long_chinese_content, long_title)

        self.assertTrue(result)
        # \u5e94\u8be5\u88ab\u5207\u5206\u6210\u81f3\u5c11 2 \u4e2a\u8bf7\u6c42
        self.assertGreaterEqual(mock_post.call_count, 2)

        # \u9a8c\u8bc1\u6bcf\u6b21\u8bf7\u6c42\u7684 JSON \u5b9e\u9645\u5e8f\u5217\u5316\u5b57\u8282\u6570\u7edd\u5bf9\u4e0d\u8d85\u8fc7 DingTalk \u7684 20000 \u5b57\u8282\u9650\u5236
        for call in mock_post.call_args_list:
            payload = call.kwargs['json']
            # \u6a21\u62df\u5b9e\u9645\u7f51\u7edc\u4f20\u8f93\u65f6\u7684 JSON \u5e8f\u5217\u5316 (\u65e0\u7a7a\u683c，UTF-8\u7f16\u7801)
            payload_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))

            # \u65ad\u8a00：\u6700\u7ec8\u53d1\u9001\u7684\u6574\u4e2a JSON \u8bf7\u6c42\u4f53 <= 20000 \u5b57\u8282
            self.assertLessEqual(payload_bytes, 20000, f"Payload \u5b57\u8282\u6570\u4e3a {payload_bytes}，\u8d85\u8fc7\u9489\u9489 20KB \u9650\u5236！")

            # \u786e\u4fdd\u6807\u9898\u88ab\u6210\u529f\u622a\u65ad\u5e76\u6ca1\u6709\u4e22\u5931\u5206\u9875\u4fe1\u606f
            self.assertLessEqual(len(payload['markdown']['title']), 120)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_api_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 310000, "errmsg": "invalid token"}
        mock_post.return_value = mock_response

        result = self.sender.send_to_dingtalk("Test content")
        self.assertFalse(result)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_exception(self, mock_post):
        mock_post.side_effect = Exception("Network Error")
        result = self.sender.send_to_dingtalk("Test content")
        self.assertFalse(result)