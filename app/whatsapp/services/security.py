"""Secrets at rest, webhook signatures, masking and log redaction.

Encryption uses Fernet (AES-128-CBC + HMAC-SHA256, from the ``cryptography``
package) with a key read from the WHATSAPP_ENCRYPTION_KEY environment
variable - never from the database or the repository. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Without a key, secrets are stored as entered (prefix ``plain:``), the same as
the CRM's existing SMTP settings, and the Settings page shows a warning.
Values saved in plain text are re-encrypted the next time they are saved
once a key is configured.
"""
import hashlib
import hmac
import os
import re

PLAIN = 'plain:'
FERNET = 'fernet:'


class SecretUnavailable(Exception):
    """A stored secret can't be decrypted (key missing or changed)."""


def _fernet():
    key = os.environ.get('WHATSAPP_ENCRYPTION_KEY', '').strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception:  # bad key format or package missing
        return None


def encryption_status():
    """('ok' | 'missing' | 'invalid', message) for the Settings page."""
    key = os.environ.get('WHATSAPP_ENCRYPTION_KEY', '').strip()
    if not key:
        return 'missing', ('WHATSAPP_ENCRYPTION_KEY is not set, so credentials are stored unencrypted '
                           'in the database. Set it on the server to encrypt them.')
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return 'invalid', 'The "cryptography" package is not installed (pip install -r requirements.txt).'
    if _fernet() is None:
        return 'invalid', 'WHATSAPP_ENCRYPTION_KEY is not a valid Fernet key.'
    return 'ok', 'Credentials are encrypted at rest.'


def encrypt(value):
    if not value:
        return None
    f = _fernet()
    if f is None:
        return PLAIN + value
    return FERNET + f.encrypt(value.encode()).decode()


def decrypt(stored):
    if not stored:
        return ''
    if stored.startswith(PLAIN):
        return stored[len(PLAIN):]
    if stored.startswith(FERNET):
        f = _fernet()
        if f is None:
            raise SecretUnavailable('WHATSAPP_ENCRYPTION_KEY is missing or invalid.')
        try:
            return f.decrypt(stored[len(FERNET):].encode()).decode()
        except Exception:
            raise SecretUnavailable('Stored credential can no longer be decrypted (encryption key changed?).')
    return stored


def is_encrypted(stored):
    return bool(stored) and stored.startswith(FERNET)


def mask(value, keep=4):
    """'EAAG••••••••3xQ1' - never more than the last few characters."""
    if not value:
        return ''
    if len(value) <= keep * 2:
        return '•' * 8
    return value[:2] + '•' * 8 + value[-keep:]


def verify_signature(raw_body, header_value, app_secret):
    """X-Hub-Signature-256: 'sha256=<hex HMAC of the raw body with the app secret>'."""
    if not app_secret or not header_value or not header_value.startswith('sha256='):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value[len('sha256='):].strip().lower())


_TOKEN_RE = re.compile(r'(EAA[A-Za-z0-9]{10,}|access_token=[^&\s]+|Bearer\s+[A-Za-z0-9._\-]+)')


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
