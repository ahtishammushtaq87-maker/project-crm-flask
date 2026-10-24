"""LinkedIn OAuth 2.0 (3-legged) and the versioned REST APIs. Official docs:
  https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api

Every /rest call sends ``LinkedIn-Version: YYYYMM`` (Settings) and
``X-Restli-Protocol-Version: 2.0.0``.

Endpoints used:
  GET  https://www.linkedin.com/oauth/v2/authorization
  POST https://www.linkedin.com/oauth/v2/accessToken          code / refresh_token grant
  POST https://www.linkedin.com/oauth/v2/introspectToken      token status (connection test)
  GET  https://api.linkedin.com/v2/userinfo                    OpenID member identity
  GET  /rest/organizationAcls?q=roleAssignee                   pages the member administers
  GET  /rest/organizations/{id}                                page name / vanity name
  POST /rest/images?action=initializeUpload, PUT upload URL
  POST /rest/videos?action=initializeUpload / finalizeUpload, PUT parts, GET /rest/videos/{urn}
  POST /rest/posts, DELETE /rest/posts/{urn}, GET /rest/posts?q=author
  GET  /rest/organizationalEntityShareStatistics               organization post statistics
Member post retrieval and member analytics need restricted products; when
they are unavailable LinkedIn answers 403 and the UI says so.
"""
import json
import re
import time
import urllib.parse

from app.social_media.services import core
from app.social_media.services.http import ApiError, send

AUTH_HOST = 'https://www.linkedin.com/oauth/v2'
API_HOST = 'https://api.linkedin.com'


def parse_error(status, payload):
    msg = (payload or {}).get('message') or (payload or {}).get('error_description') or f'HTTP {status}'
    kind, retry = 'api_error', False
    if status == 401:
        kind = 'invalid_token'
    elif status == 403:
        kind = 'app_review' if 'not enough permissions' in msg.lower() or 'scope' in msg.lower() \
            else 'missing_permission'
    elif status == 429:
        kind, retry = 'rate_limited', True
    elif status == 404:
        kind = 'not_found'
    elif status in (400, 409, 422):
        kind = 'validation'
    elif status == 426:
        kind = 'validation'
        msg = f'LinkedIn API version not supported: {msg}. Update the version in API Settings > LinkedIn.'
    elif status >= 500:
        kind, retry = 'unavailable', True
    if (payload or {}).get('error') == 'invalid_grant':
        kind, retry = 'invalid_token', False
    return ApiError(msg, kind=kind, code=(payload or {}).get('serviceErrorCode') or (payload or {}).get('error'),
                    http_status=status, retryable=retry)


def client_credentials():
    cid = core.get('linkedin_client_id')
    secret = core.get_secret('linkedin_client_secret')
    if not cid or not secret:
        raise ApiError('LinkedIn Client ID and Client Secret are not configured.', kind='not_configured')
    return cid, secret


def scopes():
    return [s.strip() for s in core.get('linkedin_scopes').split(',') if s.strip()]


def authorize_url(state, redirect_uri):
    cid, _ = client_credentials()
    return f'{AUTH_HOST}/authorization?' + urllib.parse.urlencode({
        'response_type': 'code', 'client_id': cid, 'redirect_uri': redirect_uri, 'state': state,
        'scope': ' '.join(scopes())})


def _token_request(data):
    resp = send('POST', f'{AUTH_HOST}/accessToken', body=data, is_write=False, error_parser=parse_error)
    out = resp.json()
    if not out.get('access_token'):
        raise ApiError('LinkedIn did not return an access token.', kind='api_error')
    return out


def exchange_code(code, redirect_uri):
    cid, secret = client_credentials()
    return _token_request({'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri,
                           'client_id': cid, 'client_secret': secret})


def refresh(refresh_token):
    """Only for apps LinkedIn enabled programmatic refresh tokens for."""
    cid, secret = client_credentials()
    return _token_request({'grant_type': 'refresh_token', 'refresh_token': refresh_token,
                           'client_id': cid, 'client_secret': secret})


def introspect(token):
    cid, secret = client_credentials()
    return send('POST', f'{AUTH_HOST}/introspectToken', is_write=False, error_parser=parse_error,
                body={'client_id': cid, 'client_secret': secret, 'token': token}).json()


class Rest:
    def __init__(self, token):
        self.token = token

    def headers(self, extra=None):
        h = {'Authorization': 'Bearer ' + self.token, 'LinkedIn-Version': core.get('linkedin_version'),
             'X-Restli-Protocol-Version': '2.0.0'}
        h.update(extra or {})
        return h

    def call(self, method, path, params=None, payload=None, is_write=None, raw=None, url=None):
        body = json.dumps(payload).encode() if payload is not None else raw
        hdrs = self.headers({'Content-Type': 'application/json'} if payload is not None else None)
        return send(method, url or f'{API_HOST}{path}', params=params, headers=hdrs, body=body, is_write=is_write,
                    error_parser=parse_error, timeout=120)


def userinfo(token):
    resp = send('GET', f'{API_HOST}/v2/userinfo', headers={'Authorization': 'Bearer ' + token},
                error_parser=parse_error)
    return resp.json()


def admin_organizations(token):
    """[(org_urn, name, vanity)] for approved ADMINISTRATOR roles. Raises
    ApiError(kind missing_permission/app_review) without the scope."""
    r = Rest(token)
    acl = r.call('GET', '/rest/organizationAcls', params={
        'q': 'roleAssignee', 'role': 'ADMINISTRATOR', 'state': 'APPROVED', 'count': 100}).json()
    out = []
    for el in acl.get('elements', []):
        urn = el.get('organization') or el.get('organizationTarget') or ''
        oid = urn.rsplit(':', 1)[-1]
        name, vanity = urn, None
        try:
            org = r.call('GET', f'/rest/organizations/{oid}').json()
            name = org.get('localizedName') or name
            vanity = org.get('vanityName')
        except ApiError:
            pass
        out.append((urn, name, vanity))
    return out


_RESERVED = re.compile(r'([\\|{}@\[\]()<>#*_~])')
_HASHTAG = re.compile(r'(?<![\w#])#(\w+)')


def little_text(text):
    """Posts API 'commentary' uses LinkedIn's little text format: reserved
    characters must be escaped; hashtags use the {hashtag|\\#|tag} template."""
    tags = {}

    def keep(m):
        key = f'\x00{len(tags)}\x00'
        tags[key] = '{hashtag|\\#|' + m.group(1) + '}'
        return key
    out = _HASHTAG.sub(keep, text or '')
    out = _RESERVED.sub(r'\\\1', out)
    for key, val in tags.items():
        out = out.replace(key, val)
    return out


def _upload_image(r, owner, blob):
    init = r.call('POST', '/rest/images', params={'action': 'initializeUpload'}, is_write=False,
                  payload={'initializeUploadRequest': {'owner': owner}}).json()['value']
    send('PUT', init['uploadUrl'], headers={'Authorization': 'Bearer ' + r.token}, body=blob,
         content_type='application/octet-stream', is_write=False, error_parser=parse_error, timeout=300)
    return init['image']


def _upload_video(r, owner, blob, wait_seconds):
    init = r.call('POST', '/rest/videos', params={'action': 'initializeUpload'}, is_write=False, payload={
        'initializeUploadRequest': {'owner': owner, 'fileSizeBytes': len(blob), 'uploadCaptions': False,
                                    'uploadThumbnail': False}}).json()['value']
    etags = []
    for part in init['uploadInstructions']:
        chunk = blob[part['firstByte']:part['lastByte'] + 1]
        resp = send('PUT', part['uploadUrl'], body=chunk, content_type='application/octet-stream',
                    is_write=False, error_parser=parse_error, timeout=300)
        etags.append(resp.headers.get('ETag') or resp.headers.get('etag'))
    r.call('POST', '/rest/videos', params={'action': 'finalizeUpload'}, is_write=False, payload={
        'finalizeUploadRequest': {'video': init['video'], 'uploadToken': init.get('uploadToken', ''),
                                  'uploadedPartIds': etags}})
    deadline = time.monotonic() + wait_seconds
    vid = urllib.parse.quote(init['video'], safe='')
    while True:
        st = r.call('GET', f'/rest/videos/{vid}').json().get('status')
        if st == 'AVAILABLE':
            return init['video']
        if st == 'PROCESSING_FAILED':
            raise ApiError('LinkedIn could not process the video.', kind='validation')
        if time.monotonic() >= deadline:
            raise ApiError('LinkedIn is still processing the video.', kind='processing', retryable=True)
        time.sleep(4)


def publish(author_urn, token, text, link, media, link_title=None, wait_seconds=90):
    """media: list of (SocialPostMedia, bytes). Returns (post_urn, url)."""
    r = Rest(token)
    body = {
        'author': author_urn, 'commentary': little_text(text), 'visibility': 'PUBLIC',
        'distribution': {'feedDistribution': 'MAIN_FEED', 'targetEntities': [], 'thirdPartyDistributionChannels': []},
        'lifecycleState': 'PUBLISHED', 'isReshareDisabledByAuthor': False,
    }
    videos = [b for m, b in media if m.kind == 'video']
    images = [b for m, b in media if m.kind == 'image']
    if videos:
        body['content'] = {'media': {'id': _upload_video(r, author_urn, videos[0], wait_seconds)}}
    elif len(images) == 1:
        body['content'] = {'media': {'id': _upload_image(r, author_urn, images[0])}}
    elif images:
        body['content'] = {'multiImage': {'images': [{'id': _upload_image(r, author_urn, b)} for b in images]}}
    elif link:
        body['content'] = {'article': {'source': link, 'title': (link_title or link)[:400]}}
    resp = r.call('POST', '/rest/posts', payload=body)
    urn = resp.headers.get('x-restli-id') or resp.headers.get('X-RestLi-Id') or resp.json().get('id')
    if not urn:
        raise ApiError('LinkedIn accepted the post but returned no id.', kind='ambiguous', ambiguous=True)
    return urn, f'https://www.linkedin.com/feed/update/{urn}/'


def delete(post_urn, token):
    Rest(token).call('DELETE', '/rest/posts/' + urllib.parse.quote(post_urn, safe=''))


def recent_posts(author_urn, token, limit=50):
    r = Rest(token)
    data = r.call('GET', '/rest/posts', params={'q': 'author', 'author': author_urn, 'count': min(limit, 100),
                                                 'sortBy': 'LAST_MODIFIED'},
                  ).json()
    return data.get('elements', [])[:limit]


def organization_post_stats(org_urn, post_urn, token):
    key = 'ugcPosts' if ':ugcPost:' in post_urn else 'shares'
    r = Rest(token)
    url = (f'{API_HOST}/rest/organizationalEntityShareStatistics?q=organizationalEntity'
           f'&organizationalEntity={urllib.parse.quote(org_urn, safe="")}'
           f'&{key}=List({urllib.parse.quote(post_urn, safe="")})')
    data = r.call('GET', None, url=url).json()
    stats = ((data.get('elements') or [{}])[0]).get('totalShareStatistics') or {}
    if not stats:
        return {}
    return {'impressions': stats.get('impressionCount'), 'reach': stats.get('uniqueImpressionsCount'),
            'likes': stats.get('likeCount'), 'comments': stats.get('commentCount'),
            'shares': stats.get('shareCount'), 'clicks': stats.get('clickCount'),
            'engagements': sum(stats.get(k) or 0 for k in ('likeCount', 'commentCount', 'shareCount', 'clickCount'))}
