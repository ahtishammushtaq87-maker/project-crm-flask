"""Thin client for the WhatsApp Cloud API (Meta Graph API).

Uses only the standard library (urllib + the default TLS context, which
verifies certificates). The access token goes only into the Authorization
header of requests to graph.facebook.com / Meta's media hosts - it is never
returned to callers, logged or put in an error message.

Endpoints used (Graph API, version from settings):
  GET  /{phone-number-id}                         connection test / number details
  POST /{phone-number-id}/messages                send, mark as read
  POST /{phone-number-id}/media                   upload media for sending
  GET  /{media-id}  then GET <media url>          download received media
  GET/POST /{phone-number-id}/whatsapp_business_profile
  GET/POST /{waba-id}/message_templates           list / create templates
  GET/POST /{waba-id}/subscribed_apps             webhook subscription of the app
"""
import json
import mimetypes
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass

from app.whatsapp.services import security

GRAPH_HOST = 'https://graph.facebook.com'
TIMEOUT = 20
MAX_DOWNLOAD = 100 * 1024 * 1024

# Meta error codes -> (kind, retryable). Anything not listed is a permanent
# error for that request. https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
ERROR_KINDS = {
    0: ('invalid_token', False), 190: ('invalid_token', False),
    3: ('missing_permissions', False), 10: ('missing_permissions', False),
    4: ('rate_limited', True), 80007: ('rate_limited', True), 130429: ('rate_limited', True),
    131056: ('rate_limited', True), 131048: ('spam_rate_limited', False),
    1: ('server_error', True), 2: ('server_error', True), 131000: ('server_error', True),
    131016: ('server_error', True), 133004: ('server_error', True),
    131047: ('window_closed', False), 131026: ('undeliverable', False),
    131030: ('recipient_not_allowed', False), 131050: ('user_opted_out_marketing', False),
    131049: ('marketing_limited', False), 131051: ('unsupported_type', False),
    131052: ('media_download_error', False), 131053: ('media_upload_error', False),
    132000: ('template_params', False), 132001: ('template_missing', False),
    132005: ('template_params', False), 132007: ('template_policy', False),
    132012: ('template_params', False), 132015: ('template_paused', False),
    132016: ('template_disabled', False), 133010: ('number_not_registered', False),
    131031: ('account_locked', False), 131042: ('payment_issue', False), 368: ('policy_block', False),
    2500: ('api_version', False), 2635: ('api_version', False),
}

KIND_LABELS = {
    'invalid_token': 'Invalid or expired access token',
    'missing_permissions': 'Missing permissions',
    'invalid_id': 'Invalid Phone Number ID or WABA ID',
    'api_version': 'API version issue',
    'network': 'Network error',
    'rate_limited': 'Rate limited by Meta - try again shortly',
    'window_closed': 'Customer service window closed - send an approved template',
    'not_configured': 'WhatsApp is not configured',
    'unknown': 'Unknown API error',
}


class ApiError(Exception):
    def __init__(self, message, code=None, kind='unknown', retryable=False, http_status=None,
                 uncertain=False, title=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.kind = kind
        self.retryable = retryable
        self.http_status = http_status
        self.uncertain = uncertain   # the request may have reached Meta (timeout after sending)
        self.title = title

    @property
    def label(self):
        return KIND_LABELS.get(self.kind, self.title or KIND_LABELS['unknown'])


@dataclass
class Credentials:
    phone_number_id: str
    waba_id: str
    access_token: str
    graph_version: str = 'v23.0'

    @classmethod
    def from_settings(cls, s):
        if s is None or not s.phone_number_id or not s.access_token_enc:
            raise ApiError('WhatsApp is not configured. Add the Phone Number ID and access token in Settings.',
                           kind='not_configured')
        try:
            token = security.decrypt(s.access_token_enc)
        except security.SecretUnavailable as e:
            raise ApiError(str(e), kind='not_configured')
        return cls(s.phone_number_id, s.waba_id or '', token, s.graph_version or 'v23.0')


def _classify(status, err):
    code = err.get('code')
    sub = err.get('error_subcode')
    msg = (err.get('error_user_msg') or err.get('message') or 'Unknown error')
    details = (err.get('error_data') or {}).get('details')
    if details and details not in msg:
        msg = f'{msg} ({details})'
    kind, retryable = ERROR_KINDS.get(code, ('unknown', False))
    if code == 100 and (sub == 33 or 'does not exist' in msg or 'Unsupported get request' in msg
                        or 'Unsupported post request' in msg):
        kind = 'invalid_id'
    elif kind == 'unknown' and ('version' in msg.lower() and 'graph' in msg.lower()):
        kind = 'api_version'
    elif kind == 'unknown' and status == 401:
        kind = 'invalid_token'
    elif kind == 'unknown' and status >= 500:
        kind, retryable = 'server_error', True
    if 200 <= (code or 0) <= 299:
        kind = 'missing_permissions'
    return kind, retryable, msg, err.get('title') or err.get('type')


class CloudAPI:
    def __init__(self, creds: Credentials, timeout=TIMEOUT):
        self.creds = creds
        self.timeout = timeout
        self._ctx = ssl.create_default_context()

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _url(self, path):
        return f'{GRAPH_HOST}/{self.creds.graph_version}/{path.lstrip("/")}'

    def _open(self, req):
        return urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx)

    def request(self, method, path, params=None, body=None, data=None, content_type=None, is_send=False):
        url = self._url(path)
        if params:
            url += '?' + urllib.parse.urlencode(params)
        headers = {'Authorization': f'Bearer {self.creds.access_token}', 'Accept': 'application/json'}
        if body is not None:
            data = json.dumps(body).encode()
            content_type = 'application/json'
        if content_type:
            headers['Content-Type'] = content_type
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._open(req) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode('utf-8', 'replace'))
                err = payload.get('error') or {}
            except Exception:
                err = {}
            if not err:
                raise ApiError(f'HTTP {e.code} from Meta.', kind='server_error' if e.code >= 500 else 'unknown',
                               retryable=e.code >= 500, http_status=e.code)
            kind, retryable, msg, title = _classify(e.code, err)
            raise ApiError(security.redact(msg, self.creds.access_token), code=err.get('code'), kind=kind,
                           retryable=retryable, http_status=e.code, title=title)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, 'reason', e)
            # A send that timed out may still have reached Meta.
            raise ApiError(f'Could not reach Meta: {security.redact(reason, self.creds.access_token)}',
                           kind='network', retryable=True, uncertain=is_send)
        try:
            return json.loads(raw.decode('utf-8')) if raw else {}
        except ValueError:
            raise ApiError('Meta returned an unreadable response.', kind='unknown')

    # ── Account ───────────────────────────────────────────────────────────
    def get_phone_number(self):
        return self.request('GET', self.creds.phone_number_id, params={
            'fields': 'display_phone_number,verified_name,quality_rating,code_verification_status,'
                      'messaging_limit_tier,name_status'})

    def get_waba(self):
        return self.request('GET', self.creds.waba_id, params={'fields': 'id,name,currency,timezone_id'})

    def subscribed_apps(self):
        return self.request('GET', f'{self.creds.waba_id}/subscribed_apps').get('data', [])

    def subscribe_app(self):
        return self.request('POST', f'{self.creds.waba_id}/subscribed_apps')

    def get_business_profile(self):
        data = self.request('GET', f'{self.creds.phone_number_id}/whatsapp_business_profile', params={
            'fields': 'about,address,description,email,websites,vertical,profile_picture_url'}).get('data', [])
        return data[0] if data else {}

    def update_business_profile(self, fields):
        body = {'messaging_product': 'whatsapp'}
        body.update(fields)
        return self.request('POST', f'{self.creds.phone_number_id}/whatsapp_business_profile', body=body)

    # ── Messages ──────────────────────────────────────────────────────────
    def send_message(self, to, msg_type, content, context_wamid=None):
        body = {'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': to, 'type': msg_type,
                msg_type: content}
        if context_wamid:
            body['context'] = {'message_id': context_wamid}
        resp = self.request('POST', f'{self.creds.phone_number_id}/messages', body=body, is_send=True)
        msgs = resp.get('messages') or []
        if not msgs or not msgs[0].get('id'):
            raise ApiError('Meta did not return a message id.', kind='unknown', uncertain=True)
        return msgs[0]['id']

    def mark_read(self, wamid):
        return self.request('POST', f'{self.creds.phone_number_id}/messages',
                            body={'messaging_product': 'whatsapp', 'status': 'read', 'message_id': wamid})

    # ── Media ─────────────────────────────────────────────────────────────
    def upload_media(self, content, mime, filename):
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (('messaging_product', 'whatsapp'), ('type', mime)):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        safe_name = filename.replace('"', '')
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
                     f'Content-Type: {mime}\r\n\r\n'.encode() + content + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        resp = self.request('POST', f'{self.creds.phone_number_id}/media', data=b''.join(parts),
                            content_type=f'multipart/form-data; boundary={boundary}')
        if not resp.get('id'):
            raise ApiError('Meta did not return a media id.', kind='media_upload_error')
        return resp['id']

    def download_media(self, media_id):
        """Returns (bytes, mime). The media URL is short-lived and needs the token."""
        info = self.request('GET', media_id)
        url = info.get('url')
        if not url or not url.startswith('https://'):
            raise ApiError('Media is no longer available from Meta.', kind='media_download_error')
        if int(info.get('file_size') or 0) > MAX_DOWNLOAD:
            raise ApiError('Media file is too large to preview.', kind='media_download_error')
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {self.creds.access_token}'})
        try:
            with self._open(req) as resp:
                content = resp.read(MAX_DOWNLOAD + 1)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ApiError('Could not download media from Meta.', kind='network', retryable=True)
        if len(content) > MAX_DOWNLOAD:
            raise ApiError('Media file is too large to preview.', kind='media_download_error')
        return content, info.get('mime_type') or mimetypes.guess_type(url)[0] or 'application/octet-stream'

    # ── Templates ─────────────────────────────────────────────────────────
    def list_templates(self, max_pages=20):
        out, params = [], {'fields': 'id,name,language,status,category,components,parameter_format,rejected_reason',
                           'limit': 100}
        path = f'{self.creds.waba_id}/message_templates'
        for _ in range(max_pages):
            resp = self.request('GET', path, params=params)
            out.extend(resp.get('data') or [])
            after = ((resp.get('paging') or {}).get('cursors') or {}).get('after')
            if not after or not (resp.get('paging') or {}).get('next'):
                break
            params = dict(params, after=after)
        return out

    def create_template(self, payload):
        return self.request('POST', f'{self.creds.waba_id}/message_templates', body=payload)
