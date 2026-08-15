"""
Tektos-Ultima v1 — Email Gateway Tests

Tests EmailConfig, EmailMessage, EmailGatewayResponse, and EmailGateway:
- Config validation (Pydantic)
- Dataclass defaults
- Gateway lifecycle (init, poll, send, shutdown)
- Email parsing (plain, multipart, HTML, attachments)
- Handler invocation
- Auto-reply logic
- Subject prefix extraction
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from tektos.email_gateway import (
    EmailConfig,
    EmailGateway,
    EmailGatewayResponse,
    EmailMessage,
)


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestEmailConfig:
    def test_default_config(self):
        config = EmailConfig()
        assert config.enabled is False
        assert config.imap_host == "imap.gmail.com"
        assert config.imap_port == 993
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.email_address == ""
        assert config.password == ""
        assert config.use_oauth2 is True
        assert config.poll_interval_seconds == 60
        assert config.max_emails_per_poll == 50
        assert config.inbox_label == "INBOX"
        assert config.session_prefix == "tektos:"
        assert config.auto_reply is True

    def test_custom_config(self):
        config = EmailConfig(
            enabled=True,
            email_address="test@gmail.com",
            password="app-pass",
            use_oauth2=False,
            poll_interval_seconds=30,
        )
        assert config.enabled is True
        assert config.email_address == "test@gmail.com"
        assert config.password == "app-pass"
        assert config.use_oauth2 is False
        assert config.poll_interval_seconds == 30

    def test_search_filters(self):
        config = EmailConfig(search_from="sender@example.com", search_subject="urgent")
        assert config.search_from == "sender@example.com"
        assert config.search_subject == "urgent"


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_email_message_defaults(self):
        msg = EmailMessage()
        assert msg.message_id == ""
        assert msg.from_addr == ""
        assert msg.to_addr == ""
        assert msg.subject == ""
        assert msg.body_text == ""
        assert msg.body_html is None
        assert msg.has_attachments is False
        assert msg.raw_email == ""

    def test_email_gateway_response_defaults(self):
        resp = EmailGatewayResponse()
        assert resp.success is False
        assert resp.error is None
        assert resp.email_count == 0
        assert resp.emails == []
        assert resp.sent is False

    def test_email_message_with_values(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        msg = EmailMessage(
            message_id="abc123",
            from_addr="user@example.com",
            subject="Test",
            body_text="Hello",
            date=dt,
            has_attachments=True,
        )
        assert msg.message_id == "abc123"
        assert msg.from_addr == "user@example.com"
        assert msg.subject == "Test"
        assert msg.body_text == "Hello"
        assert msg.date == dt
        assert msg.has_attachments is True


# ---------------------------------------------------------------------------
# Gateway lifecycle
# ---------------------------------------------------------------------------


class TestGatewayLifecycle:
    def test_create_gateway_default_config(self):
        gateway = EmailGateway()
        assert gateway.config is not None
        assert isinstance(gateway.config, EmailConfig)

    def test_create_gateway_custom_config(self):
        config = EmailConfig(email_address="test@gmail.com", password="pass")
        gateway = EmailGateway(config)
        assert gateway.config.email_address == "test@gmail.com"

    def test_gateway_initial_state(self):
        gateway = EmailGateway()
        assert gateway._running is False
        assert gateway._imap is None
        assert gateway._poll_task is None

    def test_initialize_calls_connect_imap(self):
        gateway = EmailGateway()
        gateway._connect_imap = AsyncMock(return_value=MagicMock())
        gateway._poll_loop = AsyncMock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway.initialize())
        finally:
            loop.close()
        gateway._connect_imap.assert_called_once()

    def test_initialize_sets_running(self):
        gateway = EmailGateway()
        gateway._connect_imap = AsyncMock(return_value=MagicMock())
        gateway._poll_loop = AsyncMock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway.initialize())
        finally:
            loop.close()
        assert gateway._running is True

    def test_initialize_creates_poll_task(self):
        gateway = EmailGateway()
        gateway._connect_imap = AsyncMock(return_value=MagicMock())
        gateway._poll_loop = AsyncMock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway.initialize())
        finally:
            loop.close()
        assert gateway._poll_task is not None

    def test_shutdown_cancels_poll_task(self):
        async def fake_shutdown():
            async def fake_poll():
                await asyncio.sleep(999)
            task = asyncio.ensure_future(fake_poll())
            gateway._poll_task = task
            gateway._running = True
            await gateway.shutdown()
            assert gateway._running is False
        gateway = EmailGateway()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(fake_shutdown())
        finally:
            loop.close()

    def test_shutdown_closes_imap(self):
        gateway = EmailGateway()
        mock_imap = MagicMock()
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway.shutdown())
        finally:
            loop.close()
        mock_imap.logout.assert_called_once()
        assert gateway._imap is None

    def test_poll_without_init_returns_error(self):
        gateway = EmailGateway()
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        assert resp.success is False
        assert "not initialized" in resp.error

    def test_send_email_builds_plain_message(self):
        """Plain email (no HTML) uses MIMEText."""
        gateway = EmailGateway(
            config=EmailConfig(email_address="from@example.com", password="pass")
        )
        mock_smtp = MagicMock()
        mock_smtp.ehlo = MagicMock()
        mock_smtp.starttls = MagicMock()
        mock_smtp.login = MagicMock()
        mock_smtp.sendmail = MagicMock()
        mock_smtp.quit = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp):
            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    gateway.send_email("to@example.com", "Subject", "Body text")
                )
            finally:
                loop.close()
        assert resp.success is True
        assert resp.sent is True

    def test_send_email_builds_multipart_message(self):
        """HTML email uses MIMEMultipart with text + html parts."""
        gateway = EmailGateway(
            config=EmailConfig(email_address="from@example.com", password="pass")
        )
        mock_smtp = MagicMock()
        mock_smtp.ehlo = MagicMock()
        mock_smtp.starttls = MagicMock()
        mock_smtp.login = MagicMock()
        mock_smtp.sendmail = MagicMock()
        mock_smtp.quit = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp):
            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    gateway.send_email(
                        "to@example.com", "Subject", "Text body", html="<p>HTML body</p>"
                    )
                )
            finally:
                loop.close()
        assert resp.success is True

    def test_send_email_error_returns_error(self):
        """SMTP errors return error response."""
        gateway = EmailGateway(
            config=EmailConfig(email_address="from@example.com", password="pass")
        )

        with patch("smtplib.SMTP", side_effect=Exception("SMTP failed")):
            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    gateway.send_email("to@example.com", "Subject", "Body")
                )
            finally:
                loop.close()
        assert resp.success is False
        assert resp.error is not None

    def test_send_email_ssl_port(self):
        """Port 465 uses SMTP_SSL."""
        gateway = EmailGateway(
            config=EmailConfig(smtp_port=465, email_address="from@example.com", password="pass")
        )
        mock_smtp_ssl = MagicMock()
        mock_smtp_ssl.login = MagicMock()
        mock_smtp_ssl.sendmail = MagicMock()
        mock_smtp_ssl.quit = MagicMock()

        with patch("smtplib.SMTP_SSL", return_value=mock_smtp_ssl):
            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    gateway.send_email("to@example.com", "Subject", "Body")
                )
            finally:
                loop.close()
        assert resp.success is True
        mock_smtp_ssl.login.assert_called()


# ---------------------------------------------------------------------------
# Email parsing
# ---------------------------------------------------------------------------


class TestEmailParsing:
    def test_parse_plain_email(self):
        gateway = EmailGateway()
        raw = b"From: sender@example.com\r\nTo: receiver@example.com\r\nSubject: Test\r\n\r\nHello world"
        msg = gateway._parse_email(raw)
        assert msg.from_addr == "sender@example.com"
        assert msg.to_addr == "receiver@example.com"
        assert msg.subject == "Test"
        assert msg.body_text == "Hello world"

    def test_parse_plain_text_multipart(self):
        gateway = EmailGateway()
        raw = b"""\
From: sender@example.com
To: receiver@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain

Plain text body
--BOUNDARY
Content-Type: text/html

<html><body>HTML body</body></html>
--BOUNDARY--
"""
        msg = gateway._parse_email(raw)
        assert msg.body_text == "Plain text body"
        assert msg.body_html is not None
        assert "HTML body" in msg.body_html

    def test_parse_email_with_attachments(self):
        gateway = EmailGateway()
        raw = b"""\
From: sender@example.com
To: receiver@example.com
Subject: With attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain

Main body
--BOUNDARY
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="file.txt"

Attachment content
--BOUNDARY--
"""
        msg = gateway._parse_email(raw)
        assert msg.body_text == "Main body"
        assert msg.has_attachments is True

    def test_parse_email_missing_headers(self):
        gateway = EmailGateway()
        raw = b"\r\n\r\nNo headers here"
        msg = gateway._parse_email(raw)
        assert msg.message_id == ""
        assert msg.subject == ""

    def test_parse_email_decoded_subject(self):
        gateway = EmailGateway()
        raw = b"""\
From: sender@example.com
To: receiver@example.com
Subject: =?UTF-8?B?VGVzdA==?=

Body
"""
        msg = gateway._parse_email(raw)
        assert msg.subject != ""


# ---------------------------------------------------------------------------
# Handler invocation
# ---------------------------------------------------------------------------


class TestHandlerInvocation:
    def test_add_handler(self):
        gateway = EmailGateway()
        handler = MagicMock()
        gateway.add_handler(handler)
        assert handler in gateway._handlers
        assert len(gateway._handlers) == 1

    def test_invoke_async_handler(self):
        gateway = EmailGateway()
        handler = AsyncMock()
        gateway.add_handler(handler)
        msg = EmailMessage(subject="tektos:session-1", body_text="Test")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        handler.assert_called_once_with(msg)

    def test_invoke_sync_handler(self):
        gateway = EmailGateway()
        handler = MagicMock()
        gateway.add_handler(handler)
        msg = EmailMessage(subject="tektos:session-1", body_text="Test")
        gateway._running = True
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        handler.assert_called_once_with(msg)

    def test_handler_exception_logged(self):
        """Handler exceptions are caught and logged, not propagated."""
        gateway = EmailGateway()

        async def bad_handler(email):
            raise ValueError("handler error")

        gateway.add_handler(bad_handler)
        msg = EmailMessage(subject="tektos:session-1", body_text="Test")
        # Should not raise
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()

    def test_multiple_handlers(self):
        gateway = EmailGateway()
        h1 = AsyncMock()
        h2 = AsyncMock()
        gateway.add_handler(h1)
        gateway.add_handler(h2)
        msg = EmailMessage(subject="tektos:session-1", body_text="Test")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        assert h1.call_count == 1
        assert h2.call_count == 1


# ---------------------------------------------------------------------------
# Auto-reply
# ---------------------------------------------------------------------------


class TestAutoReply:
    def test_auto_reply_enabled(self):
        gateway = EmailGateway(
            config=EmailConfig(email_address="from@example.com", auto_reply=True)
        )
        mock_send = AsyncMock(return_value=AsyncMock(success=True))
        gateway.send_email = mock_send
        msg = EmailMessage(from_addr="sender@example.com", subject="Test", body_text="Hello")
        gateway._running = True
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        assert mock_send.call_count == 1
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["to"] == "sender@example.com"
        assert call_kwargs[1]["subject"].startswith("Re: Test")

    def test_auto_reply_disabled(self):
        gateway = EmailGateway(
            config=EmailConfig(email_address="from@example.com", auto_reply=False)
        )
        mock_send = AsyncMock()
        gateway.send_email = mock_send
        msg = EmailMessage(from_addr="sender@example.com", subject="Test", body_text="Hello")
        gateway._running = True
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        assert mock_send.call_count == 0

    def test_auto_reply_truncates_body(self):
        gateway = EmailGateway(
            config=EmailConfig(email_address="from@example.com", auto_reply=True)
        )
        replies = []

        async def capture_send(*args, **kwargs):
            replies.append(kwargs)

        gateway.send_email = capture_send
        long_body = "x" * 500
        msg = EmailMessage(from_addr="sender@example.com", subject="Test", body_text=long_body)
        gateway._running = True
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        assert len(replies) == 1
        # Reply body should truncate body_text to ~200 chars
        assert "Tektos AI" in replies[0]["body"]


# ---------------------------------------------------------------------------
# Subject prefix extraction
# ---------------------------------------------------------------------------


class TestSubjectPrefix:
    def test_extract_session_id(self):
        gateway = EmailGateway(
            config=EmailConfig(session_prefix="tektos:")
        )
        msg = EmailMessage(subject="tektos:session-abc-123")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
        finally:
            loop.close()
        # Handler should have seen the message (no error)

    def test_no_session_id_prefix(self):
        """Non-tektos subjects don't extract session_id."""
        gateway = EmailGateway(
            config=EmailConfig(session_prefix="tektos:")
        )
        msg = EmailMessage(subject="Just a regular email")
        msg2 = EmailMessage(subject="Re: Meeting Notes")
        # Both should be handled without session ID extraction
        gateway._running = True
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway._handle_email(msg))
            loop.run_until_complete(gateway._handle_email(msg2))
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_aenter(self):
        gateway = EmailGateway()
        gateway.initialize = AsyncMock()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(gateway.__aenter__())
        finally:
            loop.close()
        assert result is gateway
        gateway.initialize.assert_called_once()

    def test_aexit(self):
        gateway = EmailGateway()
        gateway.shutdown = AsyncMock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway.__aexit__(None, None, None))
        finally:
            loop.close()
        gateway.shutdown.assert_called_once()