"""Minimal HTTPS client shared by the Meta and LinkedIn services.

Standard library only (urllib + the default TLS context, which verifies
certificates). Tokens travel only in headers/params of requests to the
provider; error messages are redacted before they leave this module.

Every failure is raised as ApiError with:
  kind       short machine label (invalid_token, missing_permission, ...)
  retryable  a later attempt may succeed (rate limit, temporary outage)
  ambiguous  the request may have reached the provider and taken effect
             (timeout after sending, 5xx on a write). The publisher never
             retries those automatically - a person must check first.
"""
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

from app.social_media.services import security

TIMEOUT = 30


class ApiError(Exception):
    def __init__(self, message, kind='api_error', code=None, http_status=None, retryable=False,
                 ambiguous=False, subcode=None):
        super().__init__(message)
        self.message = security.redact(message)
        self.kind = kind
        self.code = code
        self.subcode = subcode
        self.http_status = http_status
        self.retryable = retryable
        self.ambiguous = ambiguous

    def __str__(self):
        return self.message


KIND_LABELS = {
    'not_configured': 'Invalid configuration',
    'invalid_token': 'Token expired or revoked - reconnect the account',
    'missing_permission': 'Missing permission',
    'app_review': 'App Review / product access required',
    'validation': 'Rejected by the platform (content or parameters)',
    'rate_limited': 'Rate limited - will retry',
    'unavailable': 'API temporarily unavailable',
    'network': 'Network error',
    'ambiguous': 'Outcome unknown - check the platform before retrying',
    'processing': 'Media still processing',
    'not_found': 'Not found on the platform',
    'api_error': 'API error',
}

NEXT_STEPS = {
    'not_configured': 'Open API Settings and complete the missing values.',
    'invalid_token': 'Open Connected Accounts and click Reconnect.',
    'missing_permission': 'Reconnect and grant the listed permission; check that your app requests it.',
    'app_review': 'Request the permission/product in your developer app (App Review for Meta, '
                  'product access for LinkedIn).',
    'validation': 'Correct the content (text length, media format or link) and try again.',
    'rate_limited': 'Wait - the scheduler retries automatically.',
    'unavailable': 'Try again in a few minutes.',
    'network': 'Check the server\'s internet access and try again.',
    'ambiguous': 'Open the account on the platform; if the post is not there, use Retry.',
    'not_found': 'The item may have been deleted on the platform.',
}


def label(kind):
    return KIND_LABELS.get(kind, KIND_LABELS['api_error'])


def next_step(kind):
    return NEXT_STEPS.get(kind, 'See the error details and try again.')


def encode_multipart(fields, files):
    """fields: {name: str}; files: {name: (filename, bytes, mime)} -> (body, content_type)."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, (filename, data, mime) in files.items():
        safe = filename.replace('"', '')
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{safe}"\r\n'
                     f'Content-Type: {mime}\r\n\r\n'.encode() + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        if not self.body:
            return {}
        try:
            return json.loads(self.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return {}


def send(method, url, params=None, headers=None, body=None, content_type=None, timeout=TIMEOUT, is_write=None,
         error_parser=None):
    """Perform one request. Returns Response for 2xx; raises ApiError otherwise.
    ``error_parser(status, payload) -> ApiError`` maps provider error bodies."""
    if params:
        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params, doseq=True)
    is_write = method != 'GET' if is_write is None else is_write
    data = body
    hdrs = dict(headers or {})
    if isinstance(body, dict):
        data = urllib.parse.urlencode(body, doseq=True).encode()
        hdrs.setdefault('Content-Type', 'application/x-www-form-urlencoded')
    elif content_type:
        hdrs['Content-Type'] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            return Response(resp.status, dict(resp.headers), resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read() or b''
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            payload = {}
        if error_parser:
            err = error_parser(e.code, payload)
        else:
            err = ApiError(f'HTTP {e.code}', http_status=e.code)
        err.http_status = e.code
        if e.code >= 500 and is_write and not err.retryable:
            # The provider failed while handling a write: it may or may not have applied it.
            err.ambiguous = True
        elif e.code >= 500 and not is_write:
            err.retryable = True
            err.kind = 'unavailable' if err.kind == 'api_error' else err.kind
        raise err
    except (socket.timeout, TimeoutError) as e:
        raise ApiError(f'The request timed out ({e.__class__.__name__}).', kind='ambiguous' if is_write else 'network',
                       retryable=not is_write, ambiguous=is_write)
    except urllib.error.URLError as e:
        reason = getattr(e, 'reason', e)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise ApiError('The request timed out.', kind='ambiguous' if is_write else 'network',
                           retryable=not is_write, ambiguous=is_write)
        # DNS failures / refused connections: nothing reached the provider.
        raise ApiError(f'Could not reach the API: {reason}', kind='network', retryable=True)
    except (ConnectionError, OSError) as e:
        raise ApiError(f'Connection error: {e.__class__.__name__}', kind='ambiguous' if is_write else 'network',
                       retryable=not is_write, ambiguous=is_write)
