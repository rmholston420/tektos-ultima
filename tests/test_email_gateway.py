"""Tests for EmailGateway — Gmail IMAP/SMTP integration."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tektos.email_gateway import (
    EmailConfig,
    EmailGateway,
    EmailGatewayResponse,
    EmailMessage,
)


class TestEmailConfig:
    """Tests for EmailConfig defaults."""

    def test_config_defaults(self):
        config = EmailConfig()
        assert config.enabled is False
        assert config.imap_host == "imap.gmail.com"
        assert config.imap_port == 993
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.email_address == ""
        assert config.poll_interval_seconds == 60
        assert config.max_emails_per_poll == 50
        assert config.session_prefix == "tektos:"
        assert config.auto_reply is True

    def test_config_custom(self):
        config = EmailConfig(
            enabled=True,
            imap_host="custom.imap.com",
            smtp_port=465,
            session_prefix="custom:",
            auto_reply=False,
        )
        assert config.enabled is True
        assert config.imap_host == "custom.imap.com"
        assert config.smtp_port == 465
        assert config.session_prefix == "custom:"
        assert config.auto_reply is False


class TestEmailMessage:
    """Tests for EmailMessage dataclass."""

    def test_message_defaults(self):
        msg = EmailMessage()
        assert msg.message_id == ""
        assert msg.from_addr == ""
        assert msg.to_addr == ""
        assert msg.subject == ""
        assert msg.body_text == ""
        assert msg.body_html is None
        assert msg.has_attachments is False
        assert msg.raw_email == ""

    def test_message_with_data(self):
        msg = EmailMessage(
            message_id="abc123",
            from_addr="sender@example.com",
            from_name="Test Sender",
            to_addr="recipient@example.com",
            subject="Test Subject",
            body_text="Test body content",
            date=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert msg.message_id == "abc123"
        assert msg.from_addr == "sender@example.com"
        assert msg.subject == "Test Subject"
        assert msg.body_text == "Test body content"


class TestEmailGatewayResponse:
    """Tests for EmailGatewayResponse."""

    def test_response_defaults(self):
        resp = EmailGatewayResponse()
        assert resp.success is False
        assert resp.error is None
        assert resp.email_count == 0
        assert resp.emails == []
        assert resp.sent is False

    def test_response_with_data(self):
        msg = EmailMessage(
            message_id="test123",
            subject="Test Email",
            body_text="Body content",
        )
        resp = EmailGatewayResponse(
            success=True,
            email_count=1,
            emails=[msg],
            sent=True,
        )
        assert resp.success is True
        assert resp.email_count == 1
        assert len(resp.emails) == 1
        assert resp.emails[0].message_id == "test123"
        assert resp.sent is True


class TestEmailGateway:
    """Tests for EmailGateway initialization and lifecycle."""

    def test_gateway_initialization(self):
        config = EmailConfig(
            enabled=True,
            email_address="test@gmail.com",
            password="app-password",
        )
        gateway = EmailGateway(config)
        assert gateway.config.email_address == "test@gmail.com"
        assert gateway._imap is None
        assert gateway._running is False

    @pytest.mark.asyncio
    async def test_shutdown_without_initialize(self):
        """Test shutdown without prior initialization is safe."""
        gateway = EmailGateway()
        await gateway.shutdown()  # Should not raise

    @pytest.mark.asyncio
    async def test_poll_inbox_without_init(self):
        """Test polling without initialization returns error."""
        gateway = EmailGateway()
        response = await gateway.poll_inbox()
        assert response.success is False
        assert "not initialized" in response.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_without_init(self):
        """Test sending without initialization returns error."""
        gateway = EmailGateway()
        response = await gateway.send_email(
            to="recipient@example.com",
            subject="Test",
            body="Hello",
        )
        assert response.success is False

    @pytest.mark.asyncio
    async def test_add_handler(self):
        """Test adding email handlers."""
        gateway = EmailGateway()

        async def handler(email_msg):
            pass

        gateway.add_handler(handler)
        assert len(gateway._handlers) == 1

    @pytest.mark.asyncio
    async def test_handle_email_with_handler(self):
        """Test email handler invocation."""
        gateway = EmailGateway()

        handler_called = False

        async def mock_handler(email_msg):
            nonlocal handler_called
            handler_called = True

        gateway.add_handler(mock_handler)

        email_msg = EmailMessage(
            from_addr="sender@example.com",
            subject="tektos:session123",
            body_text="Test message",
        )
        await gateway._handle_email(email_msg)
        assert handler_called is True

    @pytest.mark.asyncio
    async def test_handle_email_auto_reply(self):
        """Test auto-reply when enabled."""
        config = EmailConfig(
            email_address="test@gmail.com",
            password="app-password",
            auto_reply=True,
        )
        gateway = EmailGateway(config)

        with patch.object(gateway, "send_email") as mock_send:
            email_msg = EmailMessage(
                from_addr="sender@example.com",
                subject="Test Subject",
                body_text="Hello Karl",
            )
            await gateway._handle_email(email_msg)
            assert mock_send.call_count == 1
            call_args = mock_send.call_args
            assert call_args.kwargs["to"] == "sender@example.com"
            assert "Karl" in call_args.kwargs["body"]

    @pytest.mark.asyncio
    async def test_handle_email_no_auto_reply(self):
        """Test no auto-reply when disabled."""
        config = EmailConfig(
            email_address="test@gmail.com",
            password="app-password",
            auto_reply=False,
        )
        gateway = EmailGateway(config)

        with patch.object(gateway, "send_email") as mock_send:
            email_msg = EmailMessage(
                from_addr="sender@example.com",
                subject="Test Subject",
                body_text="Hello",
            )
            await gateway._handle_email(email_msg)
            assert mock_send.call_count == 0

    def test_parse_email_simple(self):
        """Test parsing a simple email."""
        gateway = EmailGateway()

        raw_email = (
            "From: sender@example.com\r\n"
            "To: recipient@example.com\r\n"
            "Subject: Test Email\r\n"
            "Date: Mon, 15 Jan 2024 10:30:00 +0000\r\n"
            "Message-ID: <test123@example.com>\r\n"
            "\r\n"
            "This is the body"
        )

        msg = gateway._parse_email(raw_email.encode())
        assert msg.from_addr == "sender@example.com"
        assert msg.to_addr == "recipient@example.com"
        assert msg.subject == "Test Email"
        assert msg.body_text == "This is the body"
        assert msg.message_id == "<test123@example.com>"

    def test_parse_email_with_attachments(self):
        """Test parsing email with attachments."""
        gateway = EmailGateway()

        raw_email = (
            "From: sender@example.com\r\n"
            "To: recipient@example.com\r\n"
            "Subject: Email with Attachment\r\n"
            "Date: Mon, 15 Jan 2024 10:30:00 +0000\r\n"
            "Content-Type: multipart/mixed; boundary=\"boundary123\"\r\n"
            "\r\n"
            "--boundary123\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "Body content\r\n"
            "--boundary123\r\n"
            "Content-Type: application/pdf\r\n"
            "Content-Disposition: attachment; filename=\"file.pdf\"\r\n"
            "\r\n"
            "PDF content\r\n"
            "--boundary123--"
        )

        msg = gateway._parse_email(raw_email.encode())
        assert msg.body_text == "Body content"
        assert msg.has_attachments is True

    def test_parse_email_multipart_html(self):
        """Test parsing multipart email with HTML."""
        gateway = EmailGateway()

        raw_email = (
            "From: sender@example.com\r\n"
            "To: recipient@example.com\r\n"
            "Subject: HTML Email\r\n"
            "Date: Mon, 15 Jan 2024 10:30:00 +0000\r\n"
            "Content-Type: multipart/alternative; boundary=\"boundary123\"\r\n"
            "\r\n"
            "--boundary123\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "Plain text body\r\n"
            "--boundary123\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<html><body>HTML body</body></html>\r\n"
            "--boundary123--"
        )

        msg = gateway._parse_email(raw_email.encode())
        assert msg.body_text == "Plain text body"
        assert msg.body_html is not None
        assert "HTML body" in msg.body_html

    def test_parse_email_encoded_subject(self):
        """Test parsing email with encoded subject."""
        gateway = EmailGateway()

        raw_email = (
            "From: sender@example.com\r\n"
            "To: recipient@example.com\r\n"
            "Subject: =?UTF-8?B?VGVzdCBTdWJqZWN0?=\r\n"
            "Date: Mon, 15 Jan 2024 10:30:00 +0000\r\n"
            "\r\n"
            "Body"
        )

        msg = gateway._parse_email(raw_email.encode())
        assert msg.subject == "Test Subject"

    def test_context_manager(self):
        """Test async context manager pattern."""
        config = EmailConfig(email_address="test@gmail.com", password="pass")
        gateway = EmailGateway(config)
        assert gateway._running is False

    @pytest.mark.asyncio
    async def test_poll_loop_stops_on_shutdown(self):
        """Test poll loop stops when _running is False."""
        gateway = EmailGateway()
        gateway._running = False

        # Poll loop should exit immediately
        await gateway._poll_loop()
