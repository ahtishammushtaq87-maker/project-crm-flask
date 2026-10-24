"""Meta Graph API: Facebook Login OAuth, Pages, Facebook Page publishing,
Instagram content publishing (Instagram API with Facebook Login) and
insights. Official docs:
  https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow
  https://developers.facebook.com/docs/pages-api/
  https://developers.facebook.com/docs/instagram-platform/content-publishing

Endpoints used ({v} = Graph API version from Settings):
  dialog  https://www.facebook.com/{v}/dialog/oauth
  POST    /oauth/access_token                         code -> user token; fb_exchange_token -> long-lived
  GET     /debug_token                                expiry and granted scopes
  GET     /me, /me/permissions, /me/accounts          user, scopes, Pages (+ Page tokens, linked IG account)
  POST    /{page-id}/feed | /photos | /videos         Facebook posts
  GET     /{post-id}?fields=permalink_url,...         permalink and engagement
  GET     /{post-id}/insights                         post insights (metrics vary by API version)
  GET     /{page-id}/published_posts                  existing Page posts
  DELETE  /{post-id}                                  delete a Page post
  POST    /{ig-user-id}/media, /media_publish         Instagram containers and publishing
  GET     /{container-id}?fields=status_code          container processing status
  GET     /{ig-user-id}/media, /content_publishing_limit
  GET     /{ig-media-id}/insights
"""
import hashlib
import hmac
import json
import time
import urllib.parse

from app.social_media.services import core
from app.social_media.services.http import ApiError, encode_multipart, send

GRAPH_HOST = 'https://graph.facebook.com'
VIDEO_HOST = 'https://graph-video.facebook.com'
WWW = 'https://www.facebook.com'

RATE_CODES = {4, 17, 32, 341, 613} | set(range(80001, 80015))
TOKEN_CODES = {102, 190, 463, 467}
PERMISSION_CODES = {10} | set(range(200, 300))


def parse_error(status, payload):
    err = (payload or {}).get('error') or {}
    code = err.get('code')
    sub = err.get('error_subcode')
    msg = err.get('error_user_msg') or err.get('message') or f'HTTP {status}'
    kind, retry = 'api_error', bool(err.get('is_transient'))
    if code in TOKEN_CODES:
        kind = 'invalid_token'
    elif code in PERMISSION_CODES:
        kind = 'app_review' if 'review' in msg.lower() or 'advanced access' in msg.lower() else 'missing_permission'
    elif code in RATE_CODES or (code == 9 and sub == 2207042):
        kind, retry = 'rate_limited', True
    elif code in (1, 2):
        kind, retry = 'unavailable', True
    elif code == 9007 or sub == 2207027:
        kind, retry = 'processing', True
    elif code == 100 and sub == 33:
        kind = 'not_found'
    elif code in (100, 368, 9004, 36003, 36000, 36001, 2207026) or status == 400:
        kind = 'validation'
    elif status == 404:
        kind = 'not_found'
    if retry and kind == 'api_error':
        kind = 'unavailable'
    return ApiError(msg, kind=kind, code=code, subcode=sub, http_status=status, retryable=retry)


def version():
    return core.get('meta_graph_version') or 'v24.0'


def app_credentials():
    app_id = core.get('meta_app_id')
    secret = core.get_secret('meta_app_secret')
    if not app_id or not secret:
        raise ApiError('Meta App ID and App Secret are not configured.', kind='not_configured')
    return app_id, secret


class Graph:
    def __init__(self, token=None, app_secret=None):
        self.token = token
        self.app_secret = app_secret

    def call(self, method, path, params=None, data=None, files=None, host=GRAPH_HOST, is_write=None, timeout=60):
        url = f'{host}/{version()}/{path.lstrip("/")}'
        headers = {}
        params = dict(params or {})
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
            if self.app_secret:
                params['appsecret_proof'] = hmac.new(self.app_secret.encode(), self.token.encode(),
                                                     hashlib.sha256).hexdigest()
        body, ctype = None, None
        if files:
            body, ctype = encode_multipart({k: str(v) for k, v in (data or {}).items()}, files)
        elif data is not None:
            body = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
        resp = send(method, url, params=params, headers=headers, body=body, content_type=ctype, timeout=timeout,
                    is_write=is_write, error_parser=parse_error)
        return resp.json()

    def get(self, path, **params):
        return self.call('GET', path, params=params)

    def paged(self, path, limit_items=200, **params):
        out, data = [], self.get(path, **params)
        while True:
            out.extend(data.get('data', []))
            nxt = (data.get('paging') or {}).get('cursors', {}).get('after')
            if len(out) >= limit_items or not nxt or not (data.get('paging') or {}).get('next'):
                return out[:limit_items]
            data = self.get(path, after=nxt, **params)


def graph_for_token(token):
    try:
        secret = core.get_secret('meta_app_secret') or None
    except Exception:
        secret = None
    return Graph(token, secret)


# ── OAuth ─────────────────────────────────────────────────────────────
def scopes():
    chosen = [s.strip() for s in core.get('meta_scopes').split(',') if s.strip()]
    if core.get_bool('ads_enabled'):
        for s in ('ads_read', 'ads_management'):
            if s not in chosen:
                chosen.append(s)
    return chosen


def authorize_url(state, redirect_uri):
    app_id, _ = app_credentials()
    q = {'client_id': app_id, 'redirect_uri': redirect_uri, 'state': state, 'response_type': 'code'}
    config_id = core.get('meta_login_config_id')
    if config_id:
        q['config_id'] = config_id  # Facebook Login for Business: permissions come from the configuration
    else:
        q['scope'] = ','.join(scopes())
    return f'{WWW}/{version()}/dialog/oauth?' + urllib.parse.urlencode(q)


def exchange_code(code, redirect_uri):
    app_id, secret = app_credentials()
    data = Graph().call('POST', 'oauth/access_token', data={
        'client_id': app_id, 'client_secret': secret, 'redirect_uri': redirect_uri, 'code': code}, is_write=False)
    if not data.get('access_token'):
        raise ApiError('Meta did not return an access token.', kind='api_error')
    return data


def exchange_long_lived(token):
    """Long-lived user token (Meta documents ~60 days). If Meta refuses,
    the caller keeps the short-lived token and shows its real expiry."""
    app_id, secret = app_credentials()
    return Graph().call('POST', 'oauth/access_token', data={
        'grant_type': 'fb_exchange_token', 'client_id': app_id, 'client_secret': secret,
        'fb_exchange_token': token}, is_write=False)


def debug_token(token):
    app_id, secret = app_credentials()
    data = Graph(f'{app_id}|{secret}').get('debug_token', input_token=token)
    return data.get('data') or {}


def app_info():
    """Validates App ID + Secret with an app access token."""
    app_id, secret = app_credentials()
    return Graph(f'{app_id}|{secret}').get(app_id, fields='id,name,link')


def me(token):
    return graph_for_token(token).get('me', fields='id,name')


def granted_permissions(token):
    rows = graph_for_token(token).get('me/permissions').get('data', [])
    return sorted(r['permission'] for r in rows if r.get('status') == 'granted')


def pages(token):
    return graph_for_token(token).paged(
        'me/accounts', limit_items=500, limit=100,
        fields='id,name,access_token,category,tasks,picture{url},'
               'instagram_business_account{id,username,name,profile_picture_url}')


# ── Facebook publishing ───────────────────────────────────────────────
def _fb_permalink(g, object_id):
    try:
        url = g.get(object_id, fields='permalink_url').get('permalink_url') or ''
    except ApiError:
        return ''
    if url.startswith('/'):
        url = WWW + url
    return url


def publish_facebook(page_id, token, text, link, media):
    """media: list of (SocialPostMedia, bytes). Returns (remote_id, url)."""
    g = graph_for_token(token)
    videos = [(m, b) for m, b in media if m.kind == 'video']
    images = [(m, b) for m, b in media if m.kind == 'image']
    if videos:
        m, blob = videos[0]
        data = g.call('POST', f'{page_id}/videos', host=VIDEO_HOST, timeout=300,
                      data={'description': text}, files={'source': (m.original_name or 'video.mp4', blob, m.mime_type)})
        vid = data.get('id')
        if not vid:
            raise ApiError('Facebook accepted the upload but returned no video id.', kind='ambiguous', ambiguous=True)
        return vid, _fb_permalink(g, vid) or f'{WWW}/{vid}'
    if len(images) == 1:
        m, blob = images[0]
        data = g.call('POST', f'{page_id}/photos', data={'message': text, 'published': 'true'},
                      files={'source': (m.original_name or 'image.jpg', blob, m.mime_type)})
        pid = data.get('post_id') or data.get('id')
    elif images:
        ids = []
        for m, blob in images:
            up = g.call('POST', f'{page_id}/photos', data={'published': 'false'},
                        files={'source': (m.original_name or 'image.jpg', blob, m.mime_type)}, is_write=False)
            ids.append(up['id'])  # unpublished photos are not visible; safe to re-upload on retry
        data = {'message': text}
        for i, fbid in enumerate(ids):
            data[f'attached_media[{i}]'] = {'media_fbid': fbid}
        pid = g.call('POST', f'{page_id}/feed', data=data).get('id')
    else:
        data = {'message': text}
        if link:
            data['link'] = link
        pid = g.call('POST', f'{page_id}/feed', data=data).get('id')
    if not pid:
        raise ApiError('Facebook returned no post id.', kind='ambiguous', ambiguous=True)
    return pid, _fb_permalink(g, pid)


def delete_facebook(post_id, token):
    return graph_for_token(token).call('DELETE', post_id)


def facebook_post_metrics(post_id, token):
    g = graph_for_token(token)
    out = {}
    data = g.get(post_id, fields='reactions.summary(total_count).limit(0),'
                                 'comments.summary(total_count).limit(0),shares')
    out['likes'] = ((data.get('reactions') or {}).get('summary') or {}).get('total_count')
    out['comments'] = ((data.get('comments') or {}).get('summary') or {}).get('total_count')
    out['shares'] = (data.get('shares') or {}).get('count', 0 if 'reactions' in data else None)
    # Post insight metric names change between Graph versions; each is optional.
    for metric, key in (('post_impressions', 'impressions'), ('post_impressions_unique', 'reach'),
                        ('post_clicks', 'clicks')):
        try:
            rows = g.get(f'{post_id}/insights', metric=metric).get('data', [])
            if rows and rows[0].get('values'):
                out[key] = rows[0]['values'][0].get('value')
        except ApiError:
            pass
    parts = [out.get(k) for k in ('likes', 'comments', 'shares')]
    out['engagements'] = sum(p for p in parts if isinstance(p, int)) if any(p is not None for p in parts) else None
    return out


def facebook_recent_posts(page_id, token, limit=100):
    return graph_for_token(token).paged(f'{page_id}/published_posts', limit_items=limit, limit=50,
                                        fields='id,message,created_time,permalink_url,full_picture')


# ── Instagram publishing ──────────────────────────────────────────────
def _wait_container(g, container_id, budget_seconds):
    deadline = time.monotonic() + budget_seconds
    while True:
        st = g.get(container_id, fields='status_code,status')
        code = st.get('status_code')
        if code in ('FINISHED', 'PUBLISHED'):
            return code
        if code in ('ERROR', 'EXPIRED'):
            raise ApiError(f'Instagram could not process the media: {st.get("status") or code}', kind='validation')
        if time.monotonic() >= deadline:
            raise ApiError('Instagram is still processing the media.', kind='processing', retryable=True)
        time.sleep(3)


def publish_instagram(ig_id, token, caption, media_urls, container_id=None, save_container=None, wait_seconds=60):
    """media_urls: list of (kind, public_url). Container creation is safe to
    repeat; ``save_container`` persists the id before publishing so a restart
    resumes with the same container instead of creating a second post."""
    g = graph_for_token(token)
    if not container_id:
        if len(media_urls) == 1:
            kind, url = media_urls[0]
            data = {'caption': caption}
            if kind == 'video':
                data.update(media_type='REELS', video_url=url, share_to_feed='true')
            else:
                data['image_url'] = url
            container_id = g.call('POST', f'{ig_id}/media', data=data, is_write=False)['id']
        else:
            children = []
            for kind, url in media_urls:
                d = {'is_carousel_item': 'true'}
                d.update({'media_type': 'VIDEO', 'video_url': url} if kind == 'video' else {'image_url': url})
                children.append(g.call('POST', f'{ig_id}/media', data=d, is_write=False)['id'])
            for c in children:
                _wait_container(g, c, wait_seconds)
            container_id = g.call('POST', f'{ig_id}/media', is_write=False, data={
                'media_type': 'CAROUSEL', 'children': ','.join(children), 'caption': caption})['id']
        if save_container:
            save_container(container_id)
    status = _wait_container(g, container_id, wait_seconds)
    if status == 'PUBLISHED':
        raise ApiError('This Instagram container was already published. Check the account before retrying.',
                       kind='ambiguous', ambiguous=True)
    media_id = g.call('POST', f'{ig_id}/media_publish', data={'creation_id': container_id}).get('id')
    if not media_id:
        raise ApiError('Instagram returned no media id.', kind='ambiguous', ambiguous=True)
    try:
        url = g.get(media_id, fields='permalink').get('permalink', '')
    except ApiError:
        url = ''
    return media_id, url


def instagram_profile(ig_id, token):
    return graph_for_token(token).get(ig_id, fields='id,username,name,profile_picture_url')


def instagram_publishing_limit(ig_id, token):
    try:
        rows = graph_for_token(token).get(f'{ig_id}/content_publishing_limit', fields='quota_usage,config')
        return (rows.get('data') or [{}])[0]
    except ApiError:
        return {}


def instagram_media_metrics(media_id, token):
    g = graph_for_token(token)
    data = g.get(media_id, fields='like_count,comments_count')
    out = {'likes': data.get('like_count'), 'comments': data.get('comments_count')}
    for metric, key in (('reach', 'reach'), ('saved', 'saves'), ('shares', 'shares'), ('views', 'video_views')):
        try:
            rows = g.get(f'{media_id}/insights', metric=metric).get('data', [])
            if rows and rows[0].get('values'):
                out[key] = rows[0]['values'][0].get('value')
            elif rows and 'total_value' in rows[0]:
                out[key] = rows[0]['total_value'].get('value')
        except ApiError:
            pass
    parts = [out.get(k) for k in ('likes', 'comments', 'saves', 'shares')]
    out['engagements'] = sum(p for p in parts if isinstance(p, int)) if any(p is not None for p in parts) else None
    return out


def instagram_recent_media(ig_id, token, limit=100):
    return graph_for_token(token).paged(f'{ig_id}/media', limit_items=limit, limit=50,
                                        fields='id,caption,timestamp,permalink,media_type,thumbnail_url,media_url')


# ── Marketing API helpers shared with ads.py ──────────────────────────
def ad_accounts(token):
    return graph_for_token(token).paged('me/adaccounts', limit_items=200, limit=50,
                                        fields='id,account_id,name,currency,account_status,timezone_name')
