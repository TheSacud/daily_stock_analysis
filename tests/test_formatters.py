# -*- coding: utf-8 -*-
"""
Unit tests for formatters.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.formatters import (
    chunk_content_by_max_words,
    chunk_content_by_max_bytes,
    chunk_markdown_preserving_blocks,
    format_feishu_markdown,
    format_slack_mrkdwn,
    format_telegram_markdown,
    format_wechat_markdown,
    markdown_tables_to_key_value_rows,
    slice_at_max_bytes,
    TRUNCATION_SUFFIX,
    MIN_MAX_WORDS,
    MIN_MAX_BYTES,
    _slice_at_effective_len,
    _chunk_by_max_words,
    utf16_len,
)


class TestChunkContentByMaxWords(unittest.TestCase):
    """Tests for chunk_content_by_max_words."""

    def test_empty_string_returns_single_empty_chunk(self):
        result = chunk_content_by_max_words("", 100)
        self.assertEqual(result, [""])

    def test_short_content_no_separators_returns_single_chunk(self):
        text = "Short message without separators."
        result = chunk_content_by_max_words(text, 100)
        self.assertEqual(result, [text])

    def test_content_with_dash_separator_fits_in_one_chunk(self):
        text = "Part A\n---\nPart B"
        result = chunk_content_by_max_words(text, 500)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_content_with_dash_separator_exceeds_max_splits_into_chunks(self):
        # Use small max_words so the two parts together exceed limit
        part_a = "A" * 50
        part_b = "B" * 50
        text = f"{part_a}\n---\n{part_b}"
        result = chunk_content_by_max_words(text, 60)
        self.assertGreaterEqual(len(result), 2)
        self.assertEqual("".join(result), text)

    def test_long_content_without_separators_gets_force_split_with_suffix(self):
        long_text = "X" * 200
        result = chunk_content_by_max_words(long_text, 50)
        self.assertGreater(len(result), 1)
        # First chunks should end with the truncation suffix
        self.assertIn(TRUNCATION_SUFFIX, result[0])

    def test_content_with_dash_separator_with_long_sections(self):
        part_a = "A" * 80
        part_b = "B" * 80
        text = f"{part_a}\n---\n{part_b}"
        result = chunk_content_by_max_words(text, 40)
        content = ""
        for r in result[:-1]:
            content += r.replace(TRUNCATION_SUFFIX, "")
            self.assertTrue(TRUNCATION_SUFFIX in r or "\n---\n" in r)
            self.assertLessEqual(len(r), 40)
        self.assertEqual(content + result[-1], text)

    def test_chunk_with_emoji(self):
        text = "A" * 79 + "🎯"
        result = chunk_content_by_max_words(text, 80, special_char_len=2)
        self.assertEqual(len(result), 2)

    def test_slice_at_effective_len_with_max_effective_at_least_special_char_len(self):
        chunk, rest = _slice_at_effective_len("🎯", 2, special_char_len=2)
        self.assertEqual(chunk, "🎯")
        self.assertEqual(rest, "")

    def test_chunk_by_max_words_emoji_first_char_makes_progress(self):
        result = _chunk_by_max_words("🎯ab", MIN_MAX_WORDS, special_char_len=2)
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual("".join(r.replace(TRUNCATION_SUFFIX, "") for r in result), "🎯ab")

    def test_chunk_raises_when_max_words_below_min_in_recursion(self):
        # Safe guard\u6d4b\u8bd5，\u907f\u514d\u65e0\u9650\u5faa\u73af，\u629b\u51fa\u9519\u8bef
        with self.assertRaises(ValueError) as ctx:
            chunk_content_by_max_words("\n---\n###\n**\n##\n\n", MIN_MAX_WORDS, special_char_len=2)
        self.assertIn(str(MIN_MAX_WORDS), str(ctx.exception))

    def test_chunk_by_max_words_raises_when_max_words_below_min(self):
        # Safe guard\u6d4b\u8bd5，\u907f\u514d\u65e0\u9650\u5faa\u73af，\u629b\u51fa\u9519\u8bef
        with self.assertRaises(ValueError) as ctx:
            _chunk_by_max_words("🎯ab", 2, special_char_len=2)
        self.assertIn(str(MIN_MAX_WORDS), str(ctx.exception))


class TestChunkContentByMaxBytes(unittest.TestCase):
    """Tests for chunk_content_by_max_bytes."""

    def test_empty_string_returns_single_empty_chunk(self):
        result = chunk_content_by_max_bytes("", 500)
        self.assertEqual(result, [""])

    def test_short_content_fits_in_one_chunk(self):
        text = "Short message."
        result = chunk_content_by_max_bytes(text, 500)
        self.assertEqual(result, [text])

    def test_content_under_max_bytes_returns_single_chunk(self):
        text = "A" * 100
        result = chunk_content_by_max_bytes(text, 500)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_content_with_dash_separator_fits_in_one_chunk(self):
        text = "Part A\n---\nPart B"
        result = chunk_content_by_max_bytes(text, 500)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_content_with_dash_separator_exceeds_max_splits_into_chunks(self):
        part_a = "A" * 150
        part_b = "B" * 150
        text = f"{part_a}\n---\n{part_b}"
        result = chunk_content_by_max_bytes(text, 200)
        self.assertGreaterEqual(len(result), 2)
        joined = "".join(result).replace(TRUNCATION_SUFFIX, "")
        self.assertEqual(joined, text)

    def test_multiple_sections_in_one_chunk_no_double_separator(self):
        # When multiple sections fit in one chunk, they must be concatenated without
        # inserting an extra separator (sections already have separator appended).
        text = "Part A\n---\nPart B\n---\nPart C"
        result = chunk_content_by_max_bytes(text, 500)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)
        self.assertNotIn("\n---\n\n---\n", result[0])

    def test_long_content_without_separators_gets_force_split_with_suffix(self):
        long_text = "X" * 500
        result = chunk_content_by_max_bytes(long_text, 300)
        self.assertGreater(len(result), 1)
        self.assertIn(TRUNCATION_SUFFIX, result[0])

    def test_each_chunk_under_max_bytes(self):
        long_text = "Z" * 800
        max_bytes = 300
        result = chunk_content_by_max_bytes(long_text, max_bytes)
        for chunk in result:
            self.assertLessEqual(len(chunk.encode("utf-8")), max_bytes + 50)

    def test_raises_when_max_bytes_below_min(self):
        with self.assertRaises(ValueError) as ctx:
            chunk_content_by_max_bytes("hello", MIN_MAX_BYTES - 1)
        self.assertIn(str(MIN_MAX_BYTES), str(ctx.exception))

    def test_add_page_marker_appends_marker_to_each_chunk(self):
        text = "A" * 300
        result = chunk_content_by_max_bytes(text, 400, add_page_marker=True)
        self.assertGreaterEqual(len(result), 1)
        for i, chunk in enumerate(result):
            self.assertIn(f"{i + 1}/{len(result)}", chunk)

    def test_utf8_multibyte_boundary_not_split_mid_character(self):
        # Chinese chars are 3 bytes in UTF-8; ensure we don't split in the middle
        text = "\u6d4b" * 100  # 300 bytes in UTF-8
        result = chunk_content_by_max_bytes(text, 150)
        self.assertGreaterEqual(len(result), 2)
        for chunk in result:
            s = chunk.replace(TRUNCATION_SUFFIX, "")
            s.encode("utf-8").decode("utf-8")  # must not raise
        joined = "".join(c.replace(TRUNCATION_SUFFIX, "") for c in result)
        self.assertEqual(joined, text)

    def test_slice_at_max_bytes_returns_truncated_and_remaining_parts(self):
        chunk, remaining = slice_at_max_bytes("\u6d4b\u8bd5ABC", 7)
        self.assertEqual(chunk, "\u6d4b\u8bd5A")
        self.assertEqual(remaining, "BC")


class TestChunkMarkdownPreservingBlocks(unittest.TestCase):
    """Tests for markdown-aware notification chunking."""

    @staticmethod
    def _strip_chunk_suffix(chunk):
        return chunk.rsplit("\n\n(", 1)[0] if "\n\n(" in chunk else chunk

    def test_preserves_fenced_code_boundaries_when_split_inside_block(self):
        text = (
            "## Report\n\n"
            "```python\n"
            + "\n".join(f"print({i})" for i in range(20))
            + "\n```\n\n"
            "Done"
        )

        chunks = chunk_markdown_preserving_blocks(text, 120)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            body = self._strip_chunk_suffix(chunk)
            self.assertEqual(body.count("```") % 2, 0)
        bodies = [self._strip_chunk_suffix(chunk) for chunk in chunks]
        self.assertTrue(any(body.endswith("```") for body in bodies[:-1]))
        self.assertTrue(any(body.startswith("```python\n") for body in bodies[1:]))

    def test_preserves_indentation_when_carrying_fenced_code(self):
        text = (
            "## Report\n\n"
            "```python\n"
            + "\n".join(f"    print({i})" for i in range(20))
            + "\n```\n\n"
            "Done"
        )

        chunks = chunk_markdown_preserving_blocks(text, 120)

        carried_bodies = [
            self._strip_chunk_suffix(chunk)
            for chunk in chunks[1:]
            if self._strip_chunk_suffix(chunk).startswith("```python\n")
        ]
        self.assertTrue(carried_bodies)
        self.assertTrue(
            any(body.startswith("```python\n    print(") for body in carried_bodies)
        )
        self.assertFalse(
            any(body.startswith("```python\nprint(") for body in carried_bodies)
        )

    def test_preserves_space_delimiter_inside_fenced_code(self):
        text = "```python\n" + "value =" + (" item" * 30) + "\n```"

        chunks = chunk_markdown_preserving_blocks(text, 70)

        carried_bodies = [
            self._strip_chunk_suffix(chunk)
            for chunk in chunks[1:]
            if self._strip_chunk_suffix(chunk).startswith("```python\n")
        ]
        self.assertTrue(any(body.startswith("```python\n item") for body in carried_bodies))
        self.assertFalse(any(body.startswith("```python\nitem") for body in carried_bodies))

    def test_preserves_nested_list_indentation_after_split(self):
        text = (
            "- parent with enough words here\n"
            "  - nested child keeps indentation after chunking "
            + ("word " * 20)
        )

        chunks = chunk_markdown_preserving_blocks(text, 70)

        bodies = [self._strip_chunk_suffix(chunk) for chunk in chunks]
        self.assertTrue(any(body.startswith("  - nested child") for body in bodies[1:]))
        self.assertFalse(any(body.startswith("- nested child") for body in bodies[1:]))

    def test_avoids_splitting_inside_inline_code(self):
        text = "Intro " + ("word " * 8) + "`inline code with spaces and (parens)` tail " + ("more " * 20)

        chunks = chunk_markdown_preserving_blocks(text, 70)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            body = self._strip_chunk_suffix(chunk)
            self.assertEqual(body.count("`") % 2, 0)

    def test_avoids_splitting_inside_markdown_links(self):
        link = "[full report](https://example.com/reports/2026/05/30/daily-stock-analysis?channel=feishu)"
        text = (
            "Intro "
            + ("word " * 8)
            + link
            + " tail "
            + ("more " * 20)
        )

        chunks = chunk_markdown_preserving_blocks(text, 130)

        self.assertGreater(len(chunks), 1)
        bodies = [self._strip_chunk_suffix(chunk) for chunk in chunks]
        self.assertTrue(any(link in body for body in bodies))
        self.assertEqual([body for body in bodies if "[full report" in body and link not in body], [])

    def test_supports_utf16_length_function(self):
        text = "😀" * 20

        chunks = chunk_markdown_preserving_blocks(text, 20, len_fn=utf16_len)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(utf16_len(chunk), 20)

    def test_add_page_marker_appends_stable_markers(self):
        text = "A" * 180

        chunks = chunk_markdown_preserving_blocks(text, 80, add_page_marker=True)

        self.assertGreater(len(chunks), 1)
        for i, chunk in enumerate(chunks):
            self.assertIn(f"{i + 1}/{len(chunks)}", chunk)


class TestNotificationMarkdownFormatters(unittest.TestCase):
    """Tests for chat-friendly report Markdown conversions."""

    @staticmethod
    def _first_fenced_code_body(text):
        return text.split("```markdown\n", 1)[1].split("\n```", 1)[0]

    def test_markdown_tables_to_key_value_rows(self):
        text = "| \u80a1\u7968 | \u8bc4\u7ea7 |\n| --- | --- |\n| 600519 | \u4e70\u5165 |\n| AAPL | \u89c2\u671b |"

        result = markdown_tables_to_key_value_rows(text)

        self.assertNotIn("| --- |", result)
        self.assertIn("• 600519：\u4e70\u5165", result)
        self.assertIn("• AAPL：\u89c2\u671b", result)

    def test_markdown_tables_to_key_value_rows_compacts_report_metric_tables(self):
        text = (
            "| \u4ef7\u683c\u6307\u6807 | \u5f53\u524d\u4ef7 |\n"
            "|---------|------|\n"
            "| MA5 | 1292.85 |\n"
            "| \u652f\u6491\u4f4d | 1302.77 |\n\n"
            "| \u677f\u5757 | \u7c7b\u578b |\n"
            "|:-----|:----:|\n"
            "| \u767d\u9152Ⅲ | N/A |"
        )

        result = markdown_tables_to_key_value_rows(text)

        self.assertIn("• MA5：1292.85", result)
        self.assertIn("• \u652f\u6491\u4f4d：1302.77", result)
        self.assertIn("• \u767d\u9152Ⅲ", result)
        self.assertNotIn("\u4ef7\u683c\u6307\u6807：MA5", result)
        self.assertNotIn("\u7c7b\u578b：N/A", result)

    def test_markdown_tables_to_key_value_rows_preserves_empty_cells(self):
        text = (
            "| Header1 | Header2 | Header3 |\n"
            "|---------|---------|---------|\n"
            "| Value1  |         | Value3  |\n"
            "| Tail1   | Tail2   |         |"
        )
        colon = "\uff1a"

        result = markdown_tables_to_key_value_rows(text)

        self.assertIn(f"Header1{colon}Value1 | Header2{colon} | Header3{colon}Value3", result)
        self.assertIn(f"Header1{colon}Tail1 | Header2{colon}Tail2 | Header3{colon}", result)
        self.assertNotIn(f"Header2{colon}Value3", result)

    def test_markdown_tables_to_key_value_rows_keeps_fenced_code_tables(self):
        text = (
            "```markdown\n"
            "| \u80a1\u7968 | \u8bc4\u7ea7 |\n"
            "| --- | --- |\n"
            "| \u793a\u4f8b | \u4e0d\u5e94\u8f6c\u6362 |\n"
            "```\n\n"
            "| \u80a1\u7968 | \u8bc4\u7ea7 |\n"
            "| --- | --- |\n"
            "| 600519 | \u4e70\u5165 |"
        )

        result = markdown_tables_to_key_value_rows(text)

        fenced = self._first_fenced_code_body(result)
        self.assertIn("| --- |", fenced)
        self.assertIn("| \u793a\u4f8b | \u4e0d\u5e94\u8f6c\u6362 |", fenced)
        self.assertIn("• 600519：\u4e70\u5165", result)
        self.assertNotIn("@@DSA_FENCED_CODE_BLOCK_", result)

    def test_feishu_formatter_keeps_legacy_structure_and_converts_table(self):
        text = "# \u65e5\u62a5\n\n> \u98ce\u9669\u63d0\u793a\n\n| \u80a1\u7968 | \u4fe1\u53f7 |\n| --- | --- |\n| 600519 | \u5f3a\u52bf |\n\n- \u5173\u6ce8\u91cf\u80fd"

        result = format_feishu_markdown(text)

        self.assertIn("**\u65e5\u62a5**", result)
        self.assertIn("💬 \u98ce\u9669\u63d0\u793a", result)
        self.assertIn("• \u80a1\u7968：600519 | \u4fe1\u53f7：\u5f3a\u52bf", result)
        self.assertIn("• \u5173\u6ce8\u91cf\u80fd", result)

    def test_feishu_formatter_preserves_empty_table_cells(self):
        text = (
            "| Header1 | Header2 | Header3 |\n"
            "|---------|---------|---------|\n"
            "| Value1  |         | Value3  |"
        )
        colon = "\uff1a"

        result = format_feishu_markdown(text)

        self.assertIn(f"Header1{colon}Value1 | Header2{colon} | Header3{colon}Value3", result)
        self.assertNotIn(f"Header2{colon}Value3", result)

    def test_telegram_formatter_uses_supported_markdown(self):
        text = "## \u65e5\u62a5\n\n| \u80a1\u7968 | \u4fe1\u53f7 |\n| --- | --- |\n| 600519 | \u5f3a\u52bf |\n\n[\u8be6\u60c5](https://example.com/report)"

        result = format_telegram_markdown(text)

        self.assertIn("*\u65e5\u62a5*", result)
        self.assertIn("- 600519：\u5f3a\u52bf", result)
        self.assertIn("[\u8be6\u60c5](https://example.com/report)", result)

    def test_telegram_formatter_escapes_non_link_metacharacters(self):
        text = (
            "## [P4] \u65e5\u62a5\n\n"
            "| \u80a1\u7968 | \u4fe1\u53f7 |\n"
            "| --- | --- |\n"
            "| 600519 | [P4] \u5f3a\u52bf (\u89c2\u5bdf) |\n\n"
            "\u8be6\u89c1 [\u8be6\u60c5](https://example.com/report)"
        )

        result = format_telegram_markdown(text)

        self.assertIn("*\\[P4\\] \u65e5\u62a5*", result)
        self.assertIn("- 600519：\\[P4\\] \u5f3a\u52bf \\(\u89c2\u5bdf\\)", result)
        self.assertIn("[\u8be6\u60c5](https://example.com/report)", result)

    def test_slack_formatter_uses_mrkdwn_links_and_tables(self):
        text = "## \u65e5\u62a5\n\n| \u80a1\u7968 | \u4fe1\u53f7 |\n| --- | --- |\n| 600519 | \u5f3a\u52bf |\n\n[\u8be6\u60c5](https://example.com/report)"

        result = format_slack_mrkdwn(text)

        self.assertIn("*\u65e5\u62a5*", result)
        self.assertIn("• 600519：\u5f3a\u52bf", result)
        self.assertIn("<https://example.com/report|\u8be6\u60c5>", result)

    def test_wechat_formatter_keeps_markdown_but_converts_tables(self):
        text = "## \u65e5\u62a5\n\n| \u80a1\u7968 | \u4fe1\u53f7 |\n| --- | --- |\n| 600519 | \u5f3a\u52bf |"

        result = format_wechat_markdown(text)

        self.assertIn("## \u65e5\u62a5", result)
        self.assertIn("• 600519：\u5f3a\u52bf", result)
        self.assertNotIn("| --- |", result)

    def test_platform_formatters_do_not_rewrite_fenced_code_blocks(self):
        text = (
            "## \u65e5\u62a5\n\n"
            "```markdown\n"
            "| \u80a1\u7968 | \u4fe1\u53f7 |\n"
            "| --- | --- |\n"
            "| \u793a\u4f8b | \u4e0d\u5e94\u8f6c\u6362 |\n"
            "# not heading\n"
            "[\u8be6\u60c5](https://example.com/raw)\n"
            "```\n\n"
            "| \u80a1\u7968 | \u4fe1\u53f7 |\n"
            "| --- | --- |\n"
            "| 600519 | \u5f3a\u52bf |"
        )

        for formatter in (
            format_telegram_markdown,
            format_wechat_markdown,
            format_slack_mrkdwn,
        ):
            with self.subTest(formatter=formatter.__name__):
                result = formatter(text)
                fenced = self._first_fenced_code_body(result)
                self.assertIn("| --- |", fenced)
                self.assertIn("| \u793a\u4f8b | \u4e0d\u5e94\u8f6c\u6362 |", fenced)
                self.assertIn("# not heading", fenced)
                self.assertIn("[\u8be6\u60c5](https://example.com/raw)", fenced)
                self.assertIn("600519：\u5f3a\u52bf", result)
                self.assertNotIn("@@DSA_FENCED_CODE_BLOCK_", result)
