# feishu_doc.py
# -*- coding: utf-8 -*-
import logging
import json
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *
from typing import List, Dict, Any, Optional
from src.config import get_config

logger = logging.getLogger(__name__)


class FeishuDocManager:
    """Feishu cloud document\u7ba1\u7406\u5668 (\u57fa\u4e8e\u5b98\u65b9 SDK lark-oapi)"""

    def __init__(self):
        self.config = get_config()
        self.app_id = self.config.feishu_app_id
        self.app_secret = self.config.feishu_app_secret
        self.folder_token = self.config.feishu_folder_token

        # \u521d\u59cb\u5316 SDK \u5ba2\u6237\u7aef
        # SDK \u4f1a\u81ea\u52a8\u5904\u7406 tenant_access_token \u7684\u83b7\u53d6\u548c\u5237\u65b0; \u65e0\u9700\u4eba\u5de5\u5e72\u9884
        if self.is_configured():
            self.client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(lark.LogLevel.INFO) \
                .build()
        else:
            self.client = None

    def is_configured(self) -> bool:
        """\u68c0checkconfig\u662f\u5426\u5b8c\u6574"""
        return bool(self.app_id and self.app_secret and self.folder_token)

    def create_daily_doc(self, title: str, content_md: str) -> Optional[str]:
        """
        \u521b\u5efa\u65e5\u62a5docs
        """
        if not self.client or not self.is_configured():
            logger.warning("Feishu SDK not initializedorconfig\u7f3a\u5931; skipping\u521b\u5efa")
            return None

        try:
            # 1. \u521b\u5efadocs
            # \u4f7f\u7528\u5b98\u65b9 SDK \u7684 Builder mode\u6784\u9020request
            create_request = CreateDocumentRequest.builder() \
                .request_body(CreateDocumentRequestBody.builder()
                              .folder_token(self.folder_token)
                              .title(title)
                              .build()) \
                .build()

            response = self.client.docx.v1.document.create(create_request)

            if not response.success():
                logger.error(f"\u521b\u5efadocsfailed: {response.code} - {response.msg} - {response.error}")
                return None

            doc_id = response.data.document.document_id
            # \u8fd9\u91cc\u7684 domain \u53ea\u662f\u4e3a\u4e86\u751f\u6210\u94fe\u63a5; \u5b9e\u9645\u8bbfask\u4f1a\u91cd\u5b9a\u5411
            doc_url = f"https://feishu.cn/docx/{doc_id}"
            logger.info(f"Feishudocscreate succeeded: {title} (ID: {doc_id})")

            # 2. \u89e3\u6790 Markdown \u5e76\u5199\u5165\u5185\u5bb9
            # \u5c06 Markdown \u8f6c\u6362\u4e3a SDK \u9700\u8981\u7684 Block \u5bf9\u8c61\u5217\u8868
            blocks = self._markdown_to_sdk_blocks(content_md)

            # Feishu API limit\u6bcf\u6b21\u5199\u5165 Block count (\u5efa\u8bae 50 \u4e2a\u5de6\u53f3); \u5206\u6279\u5199\u5165
            batch_size = 50
            doc_block_id = doc_id  # docs\u672c\u8eab\u4e5f\u662f\u4e00\u4e2a block

            for i in range(0, len(blocks), batch_size):
                batch_blocks = blocks[i:i + batch_size]

                # \u6784\u9020batch\u6dfb\u52a0chunks\u7684request
                batch_add_request = CreateDocumentBlockChildrenRequest.builder() \
                    .document_id(doc_id) \
                    .block_id(doc_block_id) \
                    .request_body(CreateDocumentBlockChildrenRequestBody.builder()
                                  .children(batch_blocks)  # SDK \u9700\u8981 Block \u5bf9\u8c61\u5217\u8868
                                  .index(-1)  # \u8ffd\u52a0\u5230\u672b\u5c3e
                                  .build()) \
                    .build()

                write_resp = self.client.docx.v1.document_block_children.create(batch_add_request)

                if not write_resp.success():
                    logger.error(f"\u5199\u5165docs\u5185\u5bb9failed(\u6279\u6b21{i}): {write_resp.code} - {write_resp.msg}")

            logger.info(f"docs\u5185\u5bb9\u5199\u5165\u5b8c\u6210")
            return doc_url

        except Exception as e:
            logger.error(f"Feishudocs\u64cd\u4f5c\u5f02\u5e38: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _markdown_to_sdk_blocks(self, md_text: str) -> List[Block]:
        """
        \u5c06\u7b80\u5355\u7684 Markdown \u8f6c\u6362\u4e3aFeishu SDK \u7684 Block \u5bf9\u8c61
        """
        blocks = []
        lines = md_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # default\u666e\u901a\u6587\u672c (Text = 2)
            block_type = 2
            text_content = line

            # \u8bc6\u522b\u6807\u9898
            if line.startswith('# '):
                block_type = 3  # H1
                text_content = line[2:]
            elif line.startswith('## '):
                block_type = 4  # H2
                text_content = line[3:]
            elif line.startswith('### '):
                block_type = 5  # H3
                text_content = line[4:]
            elif line.startswith('---'):
                # \u5206\u5272\u7ebf
                blocks.append(Block.builder()
                              .block_type(22)
                              .divider(Divider.builder().build())
                              .build())
                continue

            # \u6784\u9020 Text \u7c7b\u578b\u7684 Block
            # SDK \u7684\u7ed3\u6784\u5d4c\u5957\u6bd4\u8f83\u6df1: Block -> Text -> elements -> TextElement -> TextRun -> content
            text_run = TextRun.builder() \
                .content(text_content) \
                .text_element_style(TextElementStyle.builder().build()) \
                .build()

            text_element = TextElement.builder() \
                .text_run(text_run) \
                .build()

            text_obj = Text.builder() \
                .elements([text_element]) \
                .style(TextStyle.builder().build()) \
                .build()

            # \u6839\u636e block_type \u653e\u5165\u6b63\u786e\u7684\u5c5e\u5bb9\u5668
            block_builder = Block.builder().block_type(block_type)

            if block_type == 2:
                block_builder.text(text_obj)
            elif block_type == 3:
                block_builder.heading1(text_obj)
            elif block_type == 4:
                block_builder.heading2(text_obj)
            elif block_type == 5:
                block_builder.heading3(text_obj)

            blocks.append(block_builder.build())

        return blocks