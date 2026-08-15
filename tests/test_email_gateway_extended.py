"""Additional EmailGateway tests to close coverage gaps (lines 133-390)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.email_gateway import EmailConfig, EmailGateway


# ---------------------------------------------------------------------------
# initialize() error paths (lines 133-135)
# ---------------------------------------------------------------------------

class TestInitializeError:
    def test_initialize_fails_on_connection_error(self):
        """Test initialize() catches _connect_imap failure and raises."""
        gateway = EmailGateway()
        with patch.object(gateway, '_connect_imap', AsyncMock(side_effect=Exception("IMAP down"))):
            with patch.object(gateway, '_poll_loop', AsyncMock()):
                loop = asyncio.new_event_loop()
                try:
                    with pytest.raises(Exception, match="IMAP down"):
                        loop.run_until_complete(gateway.initialize())
                finally:
                    loop.close()

    def test_initialize_sets_running_on_success(self):
        """Test _running becomes True on successful init."""
        gateway = EmailGateway()
        mock_imap = MagicMock()
        with patch.object(gateway, '_connect_imap', AsyncMock(return_value=mock_imap)):
            with patch.object(gateway, '_poll_loop', AsyncMock()):
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(gateway.initialize())
                finally:
                    loop.close()
        assert gateway._running is True
        assert gateway._imap == mock_imap
        assert gateway._poll_task is not None


# ---------------------------------------------------------------------------
# shutdown() imap.logout() except block (lines 151-152)
# ---------------------------------------------------------------------------

class TestShutdownImapError:
    def test_shutdown_handles_imap_logout_error(self):
        """Test shutdown() swallows imap.logout() exceptions."""
        gateway = EmailGateway()
        bad_imap = MagicMock()
        bad_imap.logout.side_effect = Exception("imap error")
        gateway._imap = bad_imap
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gateway.shutdown())
        finally:
            loop.close()
        # Should not raise; _imap cleared
        assert gateway._imap is None


# ---------------------------------------------------------------------------
# poll_inbox() full paths (lines 166-206)
# ---------------------------------------------------------------------------

class TestPollInboxPaths:
    def test_poll_inbox_select_failure(self):
        """Test poll_inbox() when select() fails."""
        gateway = EmailGateway()
        mock_imap = MagicMock()
        mock_imap.select = MagicMock(return_value=("NO", None))
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        assert resp.success is False
        assert "Failed to select mailbox" in resp.error

    def test_poll_inbox_search_no_ids(self):
        """Test poll_inbox() with search returning no results."""
        gateway = EmailGateway()
        mock_imap = MagicMock()
        mock_imap.select = MagicMock(return_value=("OK", None))
        mock_imap.search = MagicMock(return_value=("OK", [b""]))
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        # Empty search result → no emails, success is False (default)
        assert resp.email_count == 0

    def test_poll_inbox_search_failure(self):
        """Test poll_inbox() when search() fails."""
        gateway = EmailGateway()
        mock_imap = MagicMock()
        mock_imap.select = MagicMock(return_value=("OK", None))
        mock_imap.search = MagicMock(return_value=("NO", None))
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        assert resp.success is False

    def test_poll_inbox_fetch_error(self):
        """Test poll_inbox() when fetch() raises."""
        gateway = EmailGateway()
        mock_imap = MagicMock()
        mock_imap.select = MagicMock(return_value=("OK", None))
        mock_imap.search = MagicMock(return_value=("OK", [b"1 2"]))
        mock_imap.fetch = MagicMock(side_effect=Exception("fetch failed"))
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        assert resp.success is False
        assert resp.error is not None

    def test_poll_inbox_search_with_filters(self):
        """Test poll_inbox() uses search filters when configured."""
        gateway = EmailGateway(
            config=EmailConfig(
                search_from="boss@example.com",
                search_subject="urgent",
            )
        )
        mock_imap = MagicMock()
        mock_imap.select = MagicMock(return_value=("OK", None))
        mock_imap.search = MagicMock(return_value=("OK", [b"1"]))
        mock_imap.fetch = MagicMock(return_value=("OK", [(b"1", b"From: x\r\n\r\nBody")]))
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        # Verify search query contains the filters
        search_args = mock_imap.search.call_args
        assert "FROM boss@example.com" in search_args[0][1]
        assert "SUBJECT urgent" in search_args[0][1]
        assert "SUBJECT tektos:" in search_args[0][1]

    def test_poll_inbox_limits_max_emails(self):
        """Test poll_inbox() limits to max_emails_per_poll."""
        gateway = EmailGateway(
            config=EmailConfig(max_emails_per_poll=2)
        )
        mock_imap = MagicMock()
        # Inbox has 100 emails
        mock_imap.select = MagicMock(return_value=("OK", None))
        mock_imap.search = MagicMock(return_value=("OK", [b"1 100"]))
        # Fetch only 2 (ids 99-100)
        mock_imap.fetch = MagicMock(return_value=("OK", [(b"1", b"From: x\r\n\r\nBody")]))
        gateway._imap = mock_imap
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(gateway.poll_inbox())
        finally:
            loop.close()
        # Should only fetch 2 emails
        assert mock_imap.fetch.call_count == 2


# ---------------------------------------------------------------------------
# _poll_loop() (lines 285-296)
# ---------------------------------------------------------------------------

class TestPollLoop:
    async def test_poll_loop_runs_and_polls(self):
        """Test _poll_loop calls poll_inbox and handles emails."""
        gateway = EmailGateway()
        poll_calls = []
        handler_calls = []

        async def fake_poll_inbox():
            poll_calls.append(1)
            from tektos.email_gateway import EmailGatewayResponse, EmailMessage
            return EmailGatewayResponse(success=True, emails=[EmailMessage(body_text="test")])

        async def fake_handler(email_msg):
            handler_calls.append(email_msg)

        gateway._running = True
        gateway.poll_inbox = fake_poll_inbox
        gateway.add_handler(fake_handler)
        gateway._send_auto_reply = AsyncMock()

        # Run poll loop briefly (it loops on sleep)
        task = asyncio.ensure_future(gateway._poll_loop())
        await asyncio.sleep(0.1)
        gateway._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert len(poll_calls) >= 1
        assert len(handler_calls) >= 1

    async def test_poll_loop_handles_poll_error(self):
        """Test _poll_loop handles poll_inbox errors gracefully."""
        gateway = EmailGateway()

        async def failing_poll():
            from tektos.email_gateway import EmailGatewayResponse
            return EmailGatewayResponse(success=False, error="poll failed")

        gateway._running = True
        gateway.poll_inbox = failing_poll
        gateway._handle_email = AsyncMock()
        gateway._send_auto_reply = AsyncMock()

        task = asyncio.ensure_future(gateway._poll_loop())
        await asyncio.sleep(0.1)
        gateway._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Should not have raised


# ---------------------------------------------------------------------------
# _connect_imap() (lines 336-351)
# ---------------------------------------------------------------------------

class TestConnectImap:
    def test_connect_imap_app_password(self):
        """Test _connect_imap uses app password auth."""
        gateway = EmailGateway(
            config=EmailConfig(
                email_address="user@gmail.com",
                password="app-pass",
                use_oauth2=False,
            )
        )
        mock_imap = MagicMock()
        with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(gateway._connect_imap())
            finally:
                loop.close()
        assert result == mock_imap
        mock_imap.login.assert_called_once_with("user@gmail.com", "app-pass")

    async def test_connect_imap_oauth2(self):
        """Test _connect_imap uses OAuth2 auth."""
        gateway = EmailGateway(
            config=EmailConfig(
                email_address="user@gmail.com",
                use_oauth2=True,
                oauth2_client_id="client-id",
                oauth2_client_secret="client-secret",
                oauth2_refresh_token="refresh-token",
            )
        )
        mock_imap = MagicMock()
        with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
            with patch.object(gateway, '_oauth2_login', new_callable=AsyncMock) as mock_login:
                loop = asyncio.new_event_loop()
                try:
                    result = await gateway._connect_imap()
                finally:
                    loop.close()
                assert result == mock_imap
                mock_login.assert_called_once_with(mock_imap)


# ---------------------------------------------------------------------------
# _oauth2_login() (lines 355-390)
# ---------------------------------------------------------------------------

class TestOauth2Login:
    def test_oauth2_login_import_error(self):
        """Test _oauth2_login raises ImportError when google-auth missing."""
        gateway = EmailGateway(
            config=EmailConfig(use_oauth2=True)
        )
        mock_imap = MagicMock()
        with patch('sys.modules', {
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google_auth_oauthlib': None,
        }):
            loop = asyncio.new_event_loop()
            try:
                with pytest.raises(ImportError):
                    loop.run_until_complete(gateway._oauth2_login(mock_imap))
            finally:
                loop.close()

    def test_oauth2_login_fallback_on_error(self):
        """Test _oauth2_login falls back to app password on error (google-auth present but fails)."""
        gateway = EmailGateway(
            config=EmailConfig(
                use_oauth2=True,
                email_address="user@gmail.com",
                password="app-pass",
            )
        )
        mock_imap = MagicMock()
        mock_imap.authenticate.side_effect = Exception("oauth failed")
        # Mock google-auth so the import succeeds but the code fails
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_flow = MagicMock()
        with patch('sys.modules', {'google.oauth2.credentials': MagicMock(Credentials=mock_creds), 'google_auth_oauthlib.flow': MagicMock(InstalledAppFlow=mock_flow)}):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(gateway._oauth2_login(mock_imap))
            finally:
                loop.close()
        mock_imap.login.assert_called_once_with("user@gmail.com", "app-pass")


# ---------------------------------------------------------------------------
# _parse_email() HTML-only body (lines 436-437)
# ---------------------------------------------------------------------------

class TestParseEmailHtmlOnly:
    def test_parse_email_html_only(self):
        """Test _parse_email when body is HTML-only (no text/plain)."""
        gateway = EmailGateway()
        raw = b"From: sender@example.com\r\nTo: receiver@example.com\r\nSubject: HTML Only\r\nContent-Type: text/html\r\n\r\n<html><body><p>HTML only body</p></body></html>"
        msg = gateway._parse_email(raw)
        assert msg.body_text == ""
        assert msg.body_html is not None
        assert "HTML only body" in msg.body_html

    def test_parse_email_html_and_text_both_populated(self):
        """Test _parse_email with both text and HTML parts."""
        gateway = EmailGateway()
        raw = b"""\
From: sender@example.com
To: receiver@example.com
Subject: Both parts
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="BOUND"

--BOUND
Content-Type: text/plain

Plain text here
--BOUND
Content-Type: text/html

<html><body>HTML here</body></html>
--BOUND--
"""
        msg = gateway._parse_email(raw)
        assert "Plain text here" in msg.body_text
        assert "HTML here" in msg.body_html


# ---------------------------------------------------------------------------
# _get_payload() fallback (line 457)
# ---------------------------------------------------------------------------

class TestGetPayload:
    def test_get_payload_no_decode(self):
        """Test _get_payload when payload is None (fallback returns "")."""
        gateway = EmailGateway()
        mock_part = MagicMock()
        mock_part.get_payload.return_value = None
        result = gateway._get_payload(mock_part)
        assert result == ""

    def test_get_payload_with_charset(self):
        """Test _get_payload with charset decoding."""
        gateway = EmailGateway()
        mock_part = MagicMock()
        mock_part.get_payload.return_value = b"\xc3\xa9\xc3\xa0"  # UTF-8: éà
        mock_part.get_content_charset.return_value = "utf-8"
        result = gateway._get_payload(mock_part)
        assert result == "éà"

    def test_get_payload_default_charset(self):
        """Test _get_payload falls back to utf-8 when charset missing."""
        gateway = EmailGateway()
        mock_part = MagicMock()
        mock_part.get_payload.return_value = b"hello"
        mock_part.get_content_charset.return_value = None
        result = gateway._get_payload(mock_part)
        assert result == "hello"
