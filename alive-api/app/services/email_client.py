"""
Email client abstraction for sending notifications.
Supports SMTP (Gmail, etc.) with easy extension for SendGrid/SES.
"""
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents an email to be sent."""
    to: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    reply_to: Optional[str] = None


@dataclass
class SendResult:
    """Result of an email send attempt."""
    success: bool
    error: Optional[str] = None


class EmailClient(ABC):
    """Abstract base class for email clients."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> SendResult:
        """Send an email message."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up any resources."""
        pass


class SMTPEmailClient(EmailClient):
    """
    SMTP-based email client.
    Works with Gmail (App Password), AWS SES SMTP, SendGrid SMTP, etc.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        from_name: str = "Alive App",
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.from_name = from_name
        self.use_tls = use_tls
        self._connection: Optional[smtplib.SMTP] = None

    def _get_connection(self) -> smtplib.SMTP:
        """Get or create SMTP connection."""
        if self._connection is not None:
            try:
                # Test if connection is still alive
                self._connection.noop()
                return self._connection
            except Exception:
                self._connection = None

        # Create new connection
        if self.port == 465:
            # SSL from the start
            context = ssl.create_default_context()
            self._connection = smtplib.SMTP_SSL(self.host, self.port, context=context)
        else:
            # STARTTLS
            self._connection = smtplib.SMTP(self.host, self.port)
            if self.use_tls:
                context = ssl.create_default_context()
                self._connection.starttls(context=context)

        self._connection.login(self.username, self.password)
        return self._connection

    async def send(self, message: EmailMessage) -> SendResult:
        """
        Send an email via SMTP.
        Note: smtplib is blocking, but email sends are fast enough
        that running in the main thread is acceptable for our use case.
        For high-volume, consider running in a thread pool.
        """
        try:
            conn = self._get_connection()

            # Build the email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{self.from_name} <{self.from_address}>"
            msg["To"] = message.to

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            # Attach text part
            part_text = MIMEText(message.body_text, "plain", "utf-8")
            msg.attach(part_text)

            # Attach HTML part if provided
            if message.body_html:
                part_html = MIMEText(message.body_html, "html", "utf-8")
                msg.attach(part_html)

            # Send
            conn.sendmail(self.from_address, [message.to], msg.as_string())

            logger.info(f"Email sent successfully to {message.to}")
            return SendResult(success=True)

        except smtplib.SMTPRecipientsRefused as e:
            error = f"Recipient refused: {e}"
            logger.error(error)
            return SendResult(success=False, error=error)

        except smtplib.SMTPAuthenticationError as e:
            error = f"SMTP authentication failed: {e}"
            logger.error(error)
            # Reset connection on auth error
            self._connection = None
            return SendResult(success=False, error=error)

        except smtplib.SMTPException as e:
            error = f"SMTP error: {e}"
            logger.error(error)
            self._connection = None
            return SendResult(success=False, error=error)

        except Exception as e:
            error = f"Unexpected error sending email: {e}"
            logger.exception(error)
            self._connection = None
            return SendResult(success=False, error=error)

    def close(self) -> None:
        """Close the SMTP connection."""
        if self._connection:
            try:
                self._connection.quit()
            except Exception:
                pass
            self._connection = None


class ConsoleEmailClient(EmailClient):
    """
    Dummy email client that prints to console.
    Useful for development/testing.
    """

    async def send(self, message: EmailMessage) -> SendResult:
        print("=" * 60)
        print(f"EMAIL TO: {message.to}")
        print(f"SUBJECT: {message.subject}")
        print("-" * 60)
        print(message.body_text)
        print("=" * 60)
        return SendResult(success=True)

    def close(self) -> None:
        pass


def create_email_client(
    host: str,
    port: int,
    username: str,
    password: str,
    from_address: str,
    from_name: str = "Alive App",
    use_console: bool = False,
) -> EmailClient:
    """
    Factory function to create an email client.

    Args:
        host: SMTP host
        port: SMTP port (587 for TLS, 465 for SSL)
        username: SMTP username
        password: SMTP password
        from_address: Sender email address
        from_name: Sender display name
        use_console: If True, use ConsoleEmailClient for testing

    Returns:
        EmailClient instance
    """
    if use_console or not host:
        logger.info("Using ConsoleEmailClient (emails will be printed, not sent)")
        return ConsoleEmailClient()

    logger.info(f"Using SMTPEmailClient with host={host}:{port}")
    return SMTPEmailClient(
        host=host,
        port=port,
        username=username,
        password=password,
        from_address=from_address,
        from_name=from_name,
    )
