"""Email gateway — Gmail IMAP/SMTP integration for Tektos.

Receives and sends emails via Gmail IMAP/SMTP. Designed as a Tektos
provider behind the ProviderPort contract, matching the Telegram gateway
pattern.

Features:
- IMAP inbox polling with configurable interval
- SMTP email sending
- OAuth2 authentication support
- Email-to-event conversion for Tektos sessions
- Threaded connection management
"""

from __future__ import annotations

import asyncio
import email
import email.header
import email.utils
import inspect
import logging
import re
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EmailConfig(BaseModel):
    """Configuration for email gateway."""

    enabled: bool = False
    # Gmail IMAP settings
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    # Gmail SMTP settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    # Credentials (OAuth2 or app password)
    email_address: str = ""
    password: str = ""  # App password or OAuth2 refresh token
    use_oauth2: bool = True
    oauth2_client_id: str = ""
    oauth2_client_secret: str = ""
    oauth2_refresh_token: str = ""
    # Polling settings
    poll_interval_seconds: int = 60
    max_emails_per_poll: int = 50
    # Email filtering
    inbox_label: str = "INBOX"
    search_from: str = ""  # Optional sender filter
    search_subject: str = ""  # Optional subject filter
    # Tektos integration
    session_prefix: str = "tektos:"  # Prefix to identify Tektos emails
    auto_reply: bool = True
    reply_address: str = ""


@dataclass
class EmailMessage:
    """Parsed email message."""

    message_id: str = ""
    from_addr: str = ""
    from_name: str = ""
    to_addr: str = ""
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = None
    date: datetime = field(default_factory=datetime.now)
    has_attachments: bool = False
    raw_email: str = ""


@dataclass
class EmailGatewayResponse:
    """Response from email gateway operations."""

    success: bool = False
    error: Optional[str] = None
    email_count: int = 0
    emails: list[EmailMessage] = field(default_factory=list)
    sent: bool = False


class EmailGateway:
    """Email gateway for Tektos — Gmail IMAP/SMTP integration.

    Handles receiving emails from Gmail via IMAP and sending replies
    via SMTP. Integrates with Tektos session management.

    Usage:
        config = EmailConfig(
            email_address="user@gmail.com",
            password="app-password",
        )
        gateway = EmailGateway(config)
        await gateway.initialize()

        emails = await gateway.poll_inbox()
        for email in emails:
            # Process email → create Tektos session
            pass

        await gateway.send_email(
            to="someone@example.com",
            subject="Test",
            body="Hello from Tektos",
        )

        await gateway.shutdown()
    """

    def __init__(self, config: Optional[EmailConfig] = None) -> None:
        self.config = config or EmailConfig()
        self._imap: Optional[Any] = None
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._handlers: list[Any] = []  # Email handlers

    async def initialize(self) -> None:
        """Initialize email gateway — connect to Gmail."""
        try:
            self._imap = await self._connect_imap()
            self._running = True
            self._poll_task = asyncio.create_task(self._poll_loop())
            logger.info("Email gateway initialized: %s", self.config.email_address)
        except Exception as e:
            logger.error("Failed to initialize email gateway: %s", e)
            raise

    async def shutdown(self) -> None:
        """Shutdown email gateway — disconnect from Gmail."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

        logger.info("Email gateway shut down")

    async def poll_inbox(self) -> EmailGatewayResponse:
        """Poll inbox for new emails.

        Returns:
            EmailGatewayResponse with list of new emails.
        """
        if not self._imap:
            return EmailGatewayResponse(error="Email gateway not initialized")

        try:
            # Select inbox
            status, _ = self._imap.select(self.config.inbox_label, readonly=True)
            if status != "OK":
                return EmailGatewayResponse(error=f"Failed to select mailbox: {status}")

            # Search for emails
            search_criteria = []
            if self.config.search_from:
                search_criteria.append(f"FROM {self.config.search_from}")
            if self.config.search_subject:
                search_criteria.append(f"SUBJECT {self.config.search_subject}")
            if self.config.session_prefix:
                search_criteria.append(f"SUBJECT {self.config.session_prefix}")

            search_query = " ".join(search_criteria) if search_criteria else "ALL"
            status, message_ids = self._imap.search(None, search_query)

            if status != "OK" or not message_ids[0]:
                return EmailGatewayResponse(email_count=0)

            # Get messages (limit to max)
            max_ids = int(message_ids[0].split()[-1])
            start_id = max(1, max_ids - self.config.max_emails_per_poll + 1)

            emails: list[EmailMessage] = []
            for msg_id in range(start_id, max_ids + 1):
                status, data = self._imap.fetch(msg_id, "(RFC822)")
                if status == "OK" and data[0]:
                    email_msg = self._parse_email(data[0][1])
                    emails.append(email_msg)

            return EmailGatewayResponse(
                success=True,
                email_count=len(emails),
                emails=emails,
            )

        except Exception as e:
            logger.error("Error polling inbox: %s", e)
            return EmailGatewayResponse(error=str(e))

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: Optional[str] = None,
    ) -> EmailGatewayResponse:
        """Send an email via SMTP.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Plain text body.
            html: Optional HTML body.

        Returns:
            EmailGatewayResponse with success status.
        """
        try:
            # Build message
            if html:
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText

                msg = MIMEMultipart("alternative")
                msg["From"] = self.config.email_address
                msg["To"] = to
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html, "html"))
            else:
                from email.mime.text import MIMEText

                msg = MIMEText(body)
                msg["From"] = self.config.email_address
                msg["To"] = to
                msg["Subject"] = subject

            import smtplib

            # Connect to SMTP
            if self.config.smtp_port == 587:
                smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                await asyncio.to_thread(smtp.ehlo)
                await asyncio.to_thread(smtp.starttls)
            else:
                ctx = ssl.create_default_context()
                smtp = smtplib.SMTP_SSL(
                    self.config.smtp_host, self.config.smtp_port, context=ctx
                )

            try:
                smtp.login(self.config.email_address, self.config.password)
                smtp.sendmail(
                    self.config.email_address,
                    [to],
                    msg.as_string(),
                )
            finally:
                smtp.quit()

            return EmailGatewayResponse(success=True, sent=True)

        except Exception as e:
            logger.error("Error sending email: %s", e)
            return EmailGatewayResponse(error=str(e))

    def add_handler(self, handler: Any) -> None:
        """Add an email handler callback.

        Handlers are called for each new email with the parsed EmailMessage.
        Signature: async def handler(email: EmailMessage) -> None
        """
        self._handlers.append(handler)

    async def _poll_loop(self) -> None:
        """Background loop that polls inbox at configured interval."""
        while self._running:
            try:
                response = await self.poll_inbox()
                if response.success and response.emails:
                    for email_msg in response.emails:
                        await self._handle_email(email_msg)
                if response.error:
                    logger.warning("Email poll error: %s", response.error)
            except Exception as e:
                logger.error("Error in poll loop: %s", e)

            await asyncio.sleep(self.config.poll_interval_seconds)

    async def _handle_email(self, email_msg: EmailMessage) -> None:
        """Handle a received email — invoke handlers."""
        # Extract Tektos session ID from subject
        session_id = None
        if self.config.session_prefix in email_msg.subject:
            parts = email_msg.subject.split(self.config.session_prefix)
            if len(parts) > 1:
                session_id = parts[1].strip()

        # Invoke handlers
        for handler in self._handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(email_msg)
                else:
                    handler(email_msg)
            except Exception as e:
                logger.error("Error in email handler: %s", e)

        # Auto-reply if enabled
        if self.config.auto_reply:
            await self._send_auto_reply(email_msg)

    async def _send_auto_reply(self, email_msg: EmailMessage) -> None:
        """Send an automatic reply to the email."""
        reply_body = (
            f"Thank you for your email. This is an automated response from "
            f"Tektos AI.\n\n"
            f"Your message: {email_msg.body_text[:200]}"
        )
        await self.send_email(
            to=email_msg.from_addr,
            subject="Re: " + email_msg.subject,
            body=reply_body,
        )

    async def _connect_imap(self) -> Any:
        """Connect to Gmail IMAP server."""
        import imaplib

        imap = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)

        if self.config.use_oauth2:
            # OAuth2 authentication
            await self._oauth2_login(imap)
        else:
            # App password authentication
            await asyncio.to_thread(
                imap.login,
                self.config.email_address,
                self.config.password,
            )

        return imap

    async def _oauth2_login(self, imap: Any) -> None:
        """Authenticate using OAuth2."""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            creds = Credentials(
                token=None,
                refresh_token=self.config.oauth2_refresh_token,
                client_id=self.config.oauth2_client_id,
                client_secret=self.config.oauth2_client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://mail.google.com/"],
            )

            # Refresh token if expired
            if not creds.valid:
                await asyncio.to_thread(creds.refresh, None)

            import base64

            # Generate OAuth2 token
            auth_string = f"user={self.config.email_address}\1auth=Bearer {creds.token}\1\1"
            auth_token = base64.b64encode(auth_string.encode()).decode()

            await asyncio.to_thread(
                imap.authenticate,
                "XOAUTH2",
                lambda x: auth_token,
            )

        except ImportError:
            logger.error("google-auth library not installed. Run: pip install google-auth google-auth-oauthlib")
            raise
        except Exception as e:
            logger.error("OAuth2 login failed: %s. Falling back to app password.", e)
            import imaplib
            imap.login(self.config.email_address, self.config.password)

    def _parse_email(self, raw_email: bytes) -> EmailMessage:
        """Parse raw email bytes into EmailMessage."""
        msg = email.message_from_bytes(raw_email)

        # Extract headers
        date_str = msg.get("Date", "")
        date = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now()

        from_addr = msg.get("From", "")
        to_addr = msg.get("To", "")
        subject = msg.get("Subject", "")
        message_id = msg.get("Message-ID", "")

        # Decode subject if needed
        if subject:
            parts = email.header.decode_header(subject)
            decoded_parts = []
            for part, charset in parts:
                if isinstance(part, bytes):
                    charset = charset or "utf-8"
                    decoded_parts.append(part.decode(charset, errors="replace"))
                else:
                    decoded_parts.append(part)
            subject = " ".join(decoded_parts)

        # Extract body
        body_text = ""
        body_html = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain" and not body_text:
                    body_text = self._get_payload(part)
                elif content_type == "text/html" and not body_html:
                    body_html = self._get_payload(part)
        else:
            if msg.get_content_type() == "text/plain":
                body_text = self._get_payload(msg)
            elif msg.get_content_type() == "text/html":
                body_html = self._get_payload(msg)

        return EmailMessage(
            message_id=message_id,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body_text=body_text.strip(),
            body_html=body_html,
            date=date,
            has_attachments=msg.is_multipart(),
            raw_email=raw_email.decode("utf-8", errors="replace"),
        )

    def _get_payload(self, part: Any) -> str:
        """Extract payload from email part."""
        payload = part.get_payload(decode=True)
        if payload:
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        return ""

    async def __aenter__(self) -> "EmailGateway":
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.shutdown()
