# -*- coding: utf-8 -*-
"""
Email \u53d1\u9001\u63d0\u9192\u670d\u52a1

\u804c\u8d23:
1. \u901a\u8fc7 SMTP \u53d1\u9001 Email \u6d88\u606f
"""
import logging
from typing import Optional, List
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.header import Header
from email.utils import formataddr
import smtplib

from data_provider.base import normalize_stock_code
from src.config import Config
from src.formatters import markdown_to_html_document


logger = logging.getLogger(__name__)


# SMTP \u670d\u52a1\u5668config (\u81ea\u52a8\u8bc6\u522b)
SMTP_CONFIGS = {
    # QQ\u90ae\u7bb1
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    # \u7f51\u6613\u90ae\u7bb1
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    # Gmail
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    # Outlook
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    # \u65b0\u6d6a
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    # \u641c\u72d0
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    # \u963f\u91cc\u4e91
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    # 139\u90ae\u7bb1
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}


class EmailSender:

    def __init__(self, config: Config):
        """
        \u521d\u59cb\u5316 Email config

        Args:
            config: config\u5bf9\u8c61
        """
        self._email_config = {
            'sender': config.email_sender,
            'sender_name': getattr(config, 'email_sender_name', 'daily_stock_analysis\u80a1\u7968analyze\u52a9\u624b'),
            'password': config.email_password,
            'receivers': config.email_receivers or ([config.email_sender] if config.email_sender else []),
        }
        self._stock_email_groups = getattr(config, 'stock_email_groups', None) or []

    def _is_email_configured(self) -> bool:
        """\u68c0checkEmailconfig\u662f\u5426\u5b8c\u6574 (\u53ea\u9700\u90ae\u7bb1\u548c\u6388\u6743\u7801)"""
        return bool(self._email_config['sender'] and self._email_config['password'])

    def get_receivers_for_stocks(self, stock_codes: List[str]) -> List[str]:
        """
        Look up email receivers for given stock codes based on stock_email_groups.
        Returns union of receivers for all matching groups; falls back to default if none match.
        Stock codes are canonicalized before comparison so that equivalent
        formats (e.g. SH600519 vs 600519) match correctly.
        """
        if not stock_codes or not self._stock_email_groups:
            return self._email_config['receivers']
        normalized_codes = [normalize_stock_code(c) for c in stock_codes]
        seen: set = set()
        result: List[str] = []
        for stocks, emails in self._stock_email_groups:
            for code in normalized_codes:
                if code in stocks:
                    for e in emails:
                        if e not in seen:
                            seen.add(e)
                            result.append(e)
                    break
        return result if result else self._email_config['receivers']

    def get_all_email_receivers(self) -> List[str]:
        """
        Return union of all configured email receivers (all groups + default).
        Used for market review which should go to everyone.
        """
        seen: set = set()
        result: List[str] = []
        for _, emails in self._stock_email_groups:
            for e in emails:
                if e not in seen:
                    seen.add(e)
                    result.append(e)
        for e in self._email_config['receivers']:
            if e not in seen:
                seen.add(e)
                result.append(e)
        return result

    def _format_sender_address(self, sender: str) -> str:
        """Encode display name safely so non-ASCII sender names work across SMTP providers."""
        sender_name = self._email_config.get('sender_name') or '\u80a1\u7968analyze\u52a9\u624b'
        return formataddr((str(Header(str(sender_name), 'utf-8')), sender))

    @staticmethod
    def _close_server(server: Optional[smtplib.SMTP]) -> None:
        """Best-effort SMTP cleanup to avoid leaving sockets open on header/build errors.

        Exceptions from quit()/close() are intentionally silenced — connection may already
        be in a broken state, and there is nothing useful to do at this point.
        """
        if server is None:
            return
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass

    def send_to_email(
        self,
        content: str,
        subject: Optional[str] = None,
        receivers: Optional[List[str]] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        \u901a\u8fc7 SMTP \u53d1\u9001Email (\u81ea\u52a8\u8bc6\u522b SMTP \u670d\u52a1\u5668)

        Args:
            content: Email\u5185\u5bb9 (\u652f\u6301 Markdown; \u4f1a\u8f6c\u6362\u4e3a HTML)
            subject: Email\u4e3b\u9898 (optional; default\u81ea\u52a8\u751f\u6210)
            receivers: \u6536\u4ef6\u4eba\u5217\u8868 (optional; default\u4f7f\u7528config\u7684 receivers)

        Returns:
            \u662f\u5426send succeeded
        """
        if not self._is_email_configured():
            logger.warning("Emailconfig\u4e0d\u5b8c\u6574; skipping\u63a8\u9001")
            return False

        sender = self._email_config['sender']
        password = self._email_config['password']
        receivers = receivers or self._email_config['receivers']
        server: Optional[smtplib.SMTP] = None

        try:
            # \u751f\u6210\u4e3b\u9898
            if subject is None:
                date_str = datetime.now().strftime('%Y-%m-%d')
                subject = f"📈 \u80a1\u7968\u667a\u80fdanalyzereport - {date_str}"

            # \u5c06 Markdown \u8f6c\u6362\u4e3a\u7b80\u5355 HTML
            html_content = markdown_to_html_document(content)

            # \u6784\u5efaEmail
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = self._format_sender_address(sender)
            msg['To'] = ', '.join(receivers)

            # \u6dfb\u52a0\u7eaf\u6587\u672c\u548c HTML \u4e24\u4e2a\u7248\u672c
            text_part = MIMEText(content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(text_part)
            msg.attach(html_part)

            # \u81ea\u52a8\u8bc6\u522b SMTP config
            domain = sender.split('@')[-1].lower()
            smtp_config = SMTP_CONFIGS.get(domain)

            if smtp_config:
                smtp_server = smtp_config['server']
                smtp_port = smtp_config['port']
                use_ssl = smtp_config['ssl']
                logger.info(f"\u81ea\u52a8\u8bc6\u522b\u90ae\u7bb1\u7c7b\u578b: {domain} -> {smtp_server}:{smtp_port}")
            else:
                # unknown\u90ae\u7bb1; \u5c1d\u8bd5\u901a\u7528config
                smtp_server = f"smtp.{domain}"
                smtp_port = 465
                use_ssl = True
                logger.warning(f"unknown\u90ae\u7bb1\u7c7b\u578b {domain}; \u5c1d\u8bd5\u901a\u7528config: {smtp_server}:{smtp_port}")

            # \u6839\u636econfig\u9009\u62e9\u8fde\u63a5\u65b9\u5f0f
            if use_ssl:
                # SSL \u8fde\u63a5 (\u7aef\u53e3 465)
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout_seconds or 30)
            else:
                # TLS \u8fde\u63a5 (\u7aef\u53e3 587)
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout_seconds or 30)
                server.starttls()

            server.login(sender, password)
            server.send_message(msg)

            logger.info(f"Emailsend succeeded; \u6536\u4ef6\u4eba: {receivers}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("Emailsend failed: \u8ba4\u8bc1error; \u8bf7\u68c0check\u90ae\u7bb1\u548c\u6388\u6743\u7801\u662f\u5426\u6b63\u786e")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"Emailsend failed: \u65e0\u6cd5\u8fde\u63a5 SMTP \u670d\u52a1\u5668 - {e}")
            return False
        except Exception as e:
            logger.error(f"\u53d1\u9001Emailfailed: {e}")
            return False
        finally:
            self._close_server(server)

    def _send_email_with_inline_image(
        self, image_bytes: bytes, receivers: Optional[List[str]] = None
    ) -> bool:
        """Send email with inline image attachment (Issue #289)."""
        if not self._is_email_configured():
            return False
        sender = self._email_config['sender']
        password = self._email_config['password']
        receivers = receivers or self._email_config['receivers']
        server: Optional[smtplib.SMTP] = None
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            subject = f"📈 \u80a1\u7968\u667a\u80fdanalyzereport - {date_str}"
            msg = MIMEMultipart('related')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = self._format_sender_address(sender)
            msg['To'] = ', '.join(receivers)

            alt = MIMEMultipart('alternative')
            alt.attach(MIMEText('report\u5df2\u751f\u6210; \u8be6\u89c1\u4e0b\u65b9\u56fe\u7247.', 'plain', 'utf-8'))
            html_body = (
                '<p>report\u5df2\u751f\u6210; \u8be6\u89c1\u4e0b\u65b9\u56fe\u7247 (\u70b9\u51fb\u53efcheck\u770b\u5927\u56fe): </p>'
                '<p><img src="cid:report-image" alt="\u80a1\u7968analyzereport" style="max-width:100%%;" /></p>'
            )
            alt.attach(MIMEText(html_body, 'html', 'utf-8'))
            msg.attach(alt)

            img_part = MIMEImage(image_bytes, _subtype='png')
            img_part.add_header('Content-Disposition', 'inline', filename='report.png')
            img_part.add_header('Content-ID', '<report-image>')
            msg.attach(img_part)

            domain = sender.split('@')[-1].lower()
            smtp_config = SMTP_CONFIGS.get(domain)
            if smtp_config:
                smtp_server, smtp_port = smtp_config['server'], smtp_config['port']
                use_ssl = smtp_config['ssl']
            else:
                smtp_server, smtp_port = f"smtp.{domain}", 465
                use_ssl = True

            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            logger.info("Email (\u5185\u8054\u56fe\u7247)send succeeded; \u6536\u4ef6\u4eba: %s", receivers)
            return True
        except Exception as e:
            logger.error("Email (\u5185\u8054\u56fe\u7247)send failed: %s", e)
            return False
        finally:
            self._close_server(server)
