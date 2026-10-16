"""Sending system email through the SMTP account saved in Settings > Email.

Every public function returns (ok: bool, message: str) and never raises, so a
mail problem can't break the page that triggered it. Error messages are
translated into plain language (no stack traces or server internals).
"""
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app import db
from app.system_mail.models import MailSettings


def get_settings(create=False):
    settings = MailSettings.query.order_by(MailSettings.id).first()
    if settings is None and create:
        settings = MailSettings()
        db.session.add(settings)
    return settings


class SmtpConfig:
    """Plain values used for one connection (lets the settings page test
    unsaved values without touching the database)."""

    def __init__(self, host, port, security, username, password, from_email, from_name='', reply_to='',
                 timeout=20):
        self.host = (host or '').strip()
        self.port = int(port or 0)
        self.security = security if security in ('starttls', 'ssl', 'none') else 'starttls'
        self.username = (username or '').strip()
        self.password = password or ''
        self.from_email = (from_email or '').strip()
        self.from_name = (from_name or '').strip()
        self.reply_to = (reply_to or '').strip()
        self.timeout = max(5, min(int(timeout or 20), 120))

    @classmethod
    def from_settings(cls, s):
        return cls(s.smtp_host, s.smtp_port, s.security, s.smtp_username, s.smtp_password,
                   s.from_email, s.from_name, s.reply_to, s.timeout_seconds)


def _friendly_error(exc):
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return ('The mail server rejected the username or password. For Gmail/Outlook, use an '
                '"app password" rather than your normal password.')
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return 'The mail server refused the sender address. Use an address that belongs to this SMTP account.'
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return 'The mail server refused the recipient address.'
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return 'The server does not support this security option. Try a different Security setting.'
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return 'The connection timed out. Check the server name, port and your internet/firewall.'
    if isinstance(exc, socket.gaierror):
        return 'The SMTP server name could not be found. Check the server address.'
    if isinstance(exc, ConnectionRefusedError):
        return 'The server refused the connection on this port. Check the port and Security setting.'
    if isinstance(exc, ssl.SSLError):
        return 'Secure connection failed. Check that the Security setting matches the port (587 = STARTTLS, 465 = SSL).'
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return 'The server closed the connection. Check the port and Security setting.'
    if isinstance(exc, smtplib.SMTPException):
        return 'The mail server returned an error. Check the SMTP settings.'
    if isinstance(exc, OSError):
        return 'Could not reach the mail server. Check the server address, port and network connection.'
    return 'Sending failed because of an unexpected error.'


def _connect(cfg):
    if not cfg.host or not cfg.port:
        raise ValueError('Enter the SMTP server and port.')
    context = ssl.create_default_context()
    if cfg.security == 'ssl':
        server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=cfg.timeout, context=context)
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout)
        server.ehlo()
        if cfg.security == 'starttls':
            server.starttls(context=context)
            server.ehlo()
    if cfg.username:
        server.login(cfg.username, cfg.password)
    return server


def test_connection(cfg):
    """Connect and sign in, without sending anything."""
    try:
        server = _connect(cfg)
        try:
            server.noop()
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return True, f'Connected to {cfg.host}:{cfg.port} and signed in successfully.'
    except ValueError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001 - translated, never shown raw
        return False, _friendly_error(e)


def send_email(to, subject, text_body, html_body=None, cfg=None):
    """Send one message. Uses the saved settings unless ``cfg`` is given."""
    if cfg is None:
        settings = get_settings()
        if not settings or not settings.is_configured:
            return False, 'Email sending is not set up. An administrator must configure it in Settings > Email (SMTP).'
        cfg = SmtpConfig.from_settings(settings)
    if not cfg.from_email:
        return False, 'Enter the "From" email address.'

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = formataddr((cfg.from_name, cfg.from_email)) if cfg.from_name else cfg.from_email
    msg['To'] = to
    msg['Message-ID'] = make_msgid()
    if cfg.reply_to:
        msg['Reply-To'] = cfg.reply_to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype='html')

    try:
        server = _connect(cfg)
        try:
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return True, f'Email sent to {to}.'
    except ValueError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, _friendly_error(e)
