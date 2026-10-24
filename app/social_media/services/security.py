"""Secrets at rest, masking and log redaction.

Encryption uses Fernet (AES-128-CBC + HMAC-SHA256, from the ``cryptography``
package) with a key read from the SOCIAL_MEDIA_ENCRYPTION_KEY environment
variable - never from the database or the repository. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Unlike the WhatsApp module there is no plain-text fallback: without a valid
key, saving an app secret or connecting an account is refused and the
Settings page explains how to configure the key.
"""
import os
import re

FERNET = 'fernet:'


class EncryptionNotConfigured(Exception):
    """SOCIAL_MEDIA_ENCRYPTION_KEY is missing or invalid."""


class SecretUnavailable(Exception):
    """A stored secret can't be decrypted (key missing or changed)."""


def _fernet():
    key = os.environ.get('SOCIAL_MEDIA_ENCRYPTION_KEY', '').strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception:  # bad key format or package missing
        return None


def encryption_status():
    """('ok' | 'missing' | 'invalid', message) for the Settings page."""
    key = os.environ.get('SOCIAL_MEDIA_ENCRYPTION_KEY', '').strip()
    if not key:
        return 'missing', ('SOCIAL_MEDIA_ENCRYPTION_KEY is not set. Credentials cannot be saved and accounts cannot '
                           'be connected until it is configured on the server.')
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return 'invalid', 'The "cryptography" package is not installed (pip install -r requirements.txt).'
    if _fernet() is None:
        return 'invalid', 'SOCIAL_MEDIA_ENCRYPTION_KEY is not a valid Fernet key.'
    return 'ok', 'Credentials are encrypted at rest.'


def is_ready():
    return encryption_status()[0] == 'ok'


def encrypt(value):
    if not value:
        return None
    f = _fernet()
    if f is None:
        raise EncryptionNotConfigured(encryption_status()[1])
    return FERNET + f.encrypt(value.encode()).decode()


def decrypt(stored):
    if not stored:
        return ''
    if not stored.startswith(FERNET):
        raise SecretUnavailable('Stored credential is not in the expected encrypted format.')
    f = _fernet()
    if f is None:
        raise SecretUnavailable('SOCIAL_MEDIA_ENCRYPTION_KEY is missing or invalid.')
    try:
        return f.decrypt(stored[len(FERNET):].encode()).decode()
    except Exception:
        raise SecretUnavailable('Stored credential can no longer be decrypted (encryption key changed?).')


def mask(value, keep=4):
    """'EAAG••••••••3xQ1' - never more than the last few characters."""
    if not value:
        return ''
    if len(value) <= keep * 2:
        return '•' * 8
    return value[:2] + '•' * 8 + value[-keep:]


_TOKEN_RE = re.compile(r'(EAA[A-Za-z0-9]{10,}|AQ[A-Za-z0-9_\-]{30,}|'
                       r'(access_token|client_secret|fb_exchange_token|refresh_token|code)=[^&\s"]+|'
                       r'Bearer\s+[A-Za-z0-9._\-]+)')


def redact(text, *secrets):
    """Remove tokens and the given secret values from text before it is
    logged, stored or shown."""
    if not text:
        return text
    text = str(text)
    for s in secrets:
        if s and len(s) >= 6:
            text = text.replace(s, '[redacted]')
    return _TOKEN_RE.sub('[redacted]', text)
