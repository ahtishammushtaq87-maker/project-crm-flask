"""Connected accounts: storing OAuth results, choosing Pages / organizations,
connection tests, token expiry checks and disconnecting.

Tokens are fetched again from the provider (server side) whenever a list of
Pages or organizations must be shown, so no token is ever put in the
session cookie or the page.
"""
import json
from datetime import datetime, timedelta

from app import db
from app.social_media.models import SocialAccount, SocialAccountSync, SocialOAuthCredential
from app.social_media.services import core, linkedin, meta, security
from app.social_media.services.http import ApiError


def token_for(account):
    """Decrypted token for an account (Instagram uses its Page's token)."""
    cred = account.credential
    if cred is None:
        raise ApiError('This account has no stored authorization. Reconnect it.', kind='invalid_token')
    if cred.status in ('revoked', 'expired') or cred.is_expired:
        raise ApiError('The authorization for this account has expired or was revoked. Reconnect it.',
                       kind='invalid_token')
    try:
        return security.decrypt(cred.access_token_enc)
    except security.SecretUnavailable as e:
        raise ApiError(str(e), kind='not_configured')


def _ts(value):
    try:
        return datetime.utcfromtimestamp(int(value)) if value else None
    except (TypeError, ValueError, OSError):
        return None


def _upsert_credential(provider, token_type, external_id, name, token, user_id, scopes=None, expires_at=None,
                       expiry_known=False, refresh_token=None, refresh_expires_at=None, parent_id=None,
                       data_access_expires_at=None):
    cred = SocialOAuthCredential.query.filter_by(provider=provider, token_type=token_type,
                                                 external_user_id=str(external_id)).first()
    if cred is None:
        cred = SocialOAuthCredential(provider=provider, token_type=token_type, external_user_id=str(external_id))
        db.session.add(cred)
    cred.external_user_name = (name or '')[:200]
    cred.access_token_enc = security.encrypt(token)
    if refresh_token:
        cred.refresh_token_enc = security.encrypt(refresh_token)
    cred.scopes = json.dumps(sorted(scopes or []))
    cred.expires_at = expires_at
    cred.expiry_known = expiry_known
    cred.refresh_expires_at = refresh_expires_at
    cred.data_access_expires_at = data_access_expires_at
    cred.status = 'active'
    cred.last_error = None
    cred.parent_id = parent_id
    cred.owner_user_id = user_id
    db.session.flush()
    return cred


# ── Meta ──────────────────────────────────────────────────────────────
def complete_meta_oauth(code, redirect_uri, user_id):
    """Code -> long-lived user token, stored. Returns the user credential."""
    short = meta.exchange_code(code, redirect_uri)
    token = short['access_token']
    try:
        token = meta.exchange_long_lived(token).get('access_token') or token
    except ApiError:
        pass  # keep the short-lived token; its real expiry is read below
    info = meta.debug_token(token)
    who = meta.me(token)
    scopes = info.get('scopes') or meta.granted_permissions(token)
    expires = info.get('expires_at')
    return _upsert_credential('meta', 'user', who.get('id'), who.get('name'), token, user_id, scopes=scopes,
                              expires_at=_ts(expires) if expires else None, expiry_known=True,
                              data_access_expires_at=_ts(info.get('data_access_expires_at')))


def available_meta_pages(user_cred):
    token = security.decrypt(user_cred.access_token_enc)
    rows = meta.pages(token)
    out = []
    for p in rows:
        ig = p.get('instagram_business_account') or {}
        out.append({'id': p['id'], 'name': p.get('name'), 'category': p.get('category'),
                    'tasks': p.get('tasks') or [], 'picture': ((p.get('picture') or {}).get('data') or {}).get('url'),
                    'instagram': {'id': ig.get('id'), 'username': ig.get('username'), 'name': ig.get('name'),
                                  'picture': ig.get('profile_picture_url')} if ig.get('id') else None,
                    'can_post': 'CREATE_CONTENT' in (p.get('tasks') or []) or not p.get('tasks')})
    return out


def connect_meta_pages(user_cred, page_ids, instagram_ids, user_id):
    """Fetch Pages again (server side, with their Page tokens) and store the
    selected Pages and linked Instagram accounts. Returns created/updated accounts."""
    token = security.decrypt(user_cred.access_token_enc)
    scopes = user_cred.scope_list
    selected = []
    for p in meta.pages(token):
        ig = p.get('instagram_business_account') or {}
        want_page = p['id'] in page_ids
        want_ig = ig.get('id') and ig['id'] in instagram_ids
        if not (want_page or want_ig):
            continue
        page_token = p.get('access_token')
        if not page_token:
            continue
        info = {}
        try:
            info = meta.debug_token(page_token)
        except ApiError:
            pass
        exp = info.get('expires_at')
        cred = _upsert_credential('meta', 'page', p['id'], p.get('name'), page_token, user_id, scopes=scopes,
                                  # Meta reports expires_at=0 for Page tokens that do not expire.
                                  expires_at=_ts(exp) if exp else None, expiry_known='expires_at' in info,
                                  parent_id=user_cred.id,
                                  data_access_expires_at=_ts(info.get('data_access_expires_at')))
        page_acc = _upsert_account('facebook', 'page', p['id'], p.get('name'), None,
                                   ((p.get('picture') or {}).get('data') or {}).get('url'), cred, scopes, user_id,
                                   active=want_page)
        if want_page:
            selected.append(page_acc)
        if want_ig:
            ig_acc = _upsert_account('instagram', 'professional', ig['id'], ig.get('name') or ig.get('username'),
                                     ig.get('username'), ig.get('profile_picture_url'), cred, scopes, user_id,
                                     parent=page_acc)
            selected.append(ig_acc)
    return selected


def _upsert_account(platform, account_type, remote_id, name, username, picture, cred, scopes, user_id, parent=None,
                    active=True):
    acc = SocialAccount.query.filter_by(platform=platform, remote_id=str(remote_id)).first()
    if acc is None:
        acc = SocialAccount(platform=platform, remote_id=str(remote_id), connected_by=user_id,
                            status='connected' if active else 'disconnected')
        db.session.add(acc)
    elif active or acc.status != 'disconnected':
        acc.status = 'connected'
    acc.account_type = account_type
    acc.name = (name or str(remote_id))[:200]
    acc.username = username
    acc.picture_url = (picture or '')[:1000] or None
    acc.credential_id = cred.id
    acc.granted_permissions = json.dumps(sorted(scopes or []))
    acc.last_error = None
    if active:
        acc.connected_at = datetime.utcnow()
    if parent is not None:
        db.session.flush()
        acc.parent_account_id = parent.id
    db.session.flush()
    return acc


# ── LinkedIn ──────────────────────────────────────────────────────────
def complete_linkedin_oauth(code, redirect_uri, user_id):
    data = linkedin.exchange_code(code, redirect_uri)
    token = data['access_token']
    who = linkedin.userinfo(token)
    now = datetime.utcnow()
    exp = now + timedelta(seconds=int(data['expires_in'])) if data.get('expires_in') else None
    rexp = now + timedelta(seconds=int(data['refresh_token_expires_in'])) \
        if data.get('refresh_token_expires_in') else None
    scopes = (data.get('scope') or '').replace(',', ' ').split()
    cred = _upsert_credential('linkedin', 'member', who.get('sub'), who.get('name'), token, user_id, scopes=scopes,
                              expires_at=exp, expiry_known=bool(exp), refresh_token=data.get('refresh_token'),
                              refresh_expires_at=rexp)
    cred._member = who
    return cred


def available_linkedin_identities(cred):
    """Member identity plus administered organizations (if permitted)."""
    token = security.decrypt(cred.access_token_enc)
    member = {'urn': f'urn:li:person:{cred.external_user_id}', 'name': cred.external_user_name,
              'can_post': 'w_member_social' in cred.scope_list}
    orgs, org_error = [], None
    try:
        orgs = [{'urn': u, 'name': n, 'vanity': v, 'can_post': 'w_organization_social' in cred.scope_list}
                for u, n, v in linkedin.admin_organizations(token)]
    except ApiError as e:
        org_error = (f'{e.message} - listing company pages needs the Community Management API '
                     f'(scope rw_organization_admin or r_organization_admin), which LinkedIn must approve.')
    return member, orgs, org_error


def connect_linkedin(cred, member_selected, org_urns, user_id):
    out = []
    member, orgs, _ = available_linkedin_identities(cred)
    if member_selected:
        picture = None
        try:
            picture = linkedin.userinfo(security.decrypt(cred.access_token_enc)).get('picture')
        except ApiError:
            pass
        out.append(_upsert_account('linkedin', 'member', member['urn'], member['name'], None, picture, cred,
                                   cred.scope_list, user_id))
    for o in orgs:
        if o['urn'] in org_urns:
            out.append(_upsert_account('linkedin', 'organization', o['urn'], o['name'], o['vanity'], None, cred,
                                       cred.scope_list, user_id))
    return out


# ── health ────────────────────────────────────────────────────────────
def mark_auth_problem(account, err):
    """Record a token/permission problem on the account and notify once."""
    if err.kind == 'invalid_token':
        new = 'reauth_required'
    elif err.kind in ('missing_permission', 'app_review'):
        new = 'error'
    else:
        return
    if account.status != new:
        account.status = new
        core.notify('account_auth', f'{account.label}: {err.message}', level='danger',
                    link='/social-media/accounts', email=True)
    account.last_error = err.message[:500]


def test_account(account):
    """Real API call with the stored token. Returns (ok, kind, message)."""
    started = datetime.utcnow()
    try:
        token = token_for(account)
        if account.platform == 'facebook':
            meta.graph_for_token(token).get(account.remote_id, fields='id,name')
            msg = 'Page reachable with the stored Page token.'
        elif account.platform == 'instagram':
            prof = meta.instagram_profile(account.remote_id, token)
            limit = meta.instagram_publishing_limit(account.remote_id, token)
            msg = f'Instagram account @{prof.get("username")} reachable.'
            if limit.get('config'):
                msg += (f' Publishing quota: {limit.get("quota_usage", 0)} of '
                        f'{limit["config"].get("quota_total")} posts in the last 24 hours.')
        else:
            info = linkedin.introspect(token)
            if not info.get('active'):
                raise ApiError('LinkedIn reports the token is not active.', kind='invalid_token')
            msg = f'LinkedIn token active (scopes: {info.get("scope") or "unknown"}).'
        account.status = 'connected'
        account.last_error = None
        ok, kind = True, 'ok'
    except ApiError as e:
        mark_auth_problem(account, e)
        account.last_error = e.message[:500]
        ok, kind, msg = False, e.kind, e.message
    account.last_test_at = datetime.utcnow()
    db.session.add(SocialAccountSync(account_id=account.id, kind='test', status='success' if ok else 'error',
                                     message=msg[:500], started_at=started, finished_at=datetime.utcnow()))
    return ok, kind, msg


def check_token_expiry():
    """Daily: flag expired credentials, warn 7 days ahead, refresh LinkedIn
    tokens where LinkedIn issued a refresh token."""
    now = datetime.utcnow()
    for cred in SocialOAuthCredential.query.filter(SocialOAuthCredential.status == 'active',
                                                   SocialOAuthCredential.expires_at.isnot(None)).all():
        if cred.provider == 'linkedin' and cred.refresh_token_enc and cred.expires_at <= now + timedelta(days=7):
            try:
                data = linkedin.refresh(security.decrypt(cred.refresh_token_enc))
                cred.access_token_enc = security.encrypt(data['access_token'])
                if data.get('refresh_token'):
                    cred.refresh_token_enc = security.encrypt(data['refresh_token'])
                cred.expires_at = now + timedelta(seconds=int(data.get('expires_in') or 0)) \
                    if data.get('expires_in') else None
                core.audit('token_refreshed', f'LinkedIn {cred.external_user_name}', user_id=None)
                continue
            except (ApiError, security.SecretUnavailable) as e:
                cred.last_error = str(e)[:500]
        accounts = SocialAccount.query.filter_by(credential_id=cred.id).all()
        if cred.expires_at <= now:
            cred.status = 'expired'
            for a in accounts:
                if a.status == 'connected':
                    a.status = 'reauth_required'
                    core.notify('account_auth', f'{a.label}: authorization expired - reconnect the account.',
                                level='danger', link='/social-media/accounts', email=True)
        elif cred.expires_at <= now + timedelta(days=7):
            key = f'expiry_warned.{cred.id}'
            if core.state_get(key) != cred.expires_at.isoformat():
                core.state_set(key, cred.expires_at.isoformat())
                names = ', '.join(a.name for a in accounts) or cred.external_user_name
                core.notify('token_expiring', f'Authorization for {names} expires on '
                            f'{core.to_local(cred.expires_at):%d %b %Y}. Reconnect before then.',
                            level='warning', link='/social-media/accounts')


def disconnect(account):
    """Stop using the account locally. Remote posts are never touched.
    Pending scheduled destinations are cancelled. The credential is deleted
    when no other account uses it."""
    from app.social_media.models import SocialPostDestination
    account.status = 'disconnected'
    cred_id = account.credential_id
    account.credential_id = None
    for d in SocialPostDestination.query.filter(SocialPostDestination.account_id == account.id,
                                                SocialPostDestination.status.in_(['scheduled', 'retry_wait'])):
        d.status = 'cancelled'
        d.error_message = 'Account disconnected before publication.'
    db.session.flush()
    if cred_id and not SocialAccount.query.filter_by(credential_id=cred_id).count():
        cred = db.session.get(SocialOAuthCredential, cred_id)
        if cred is not None:
            db.session.delete(cred)
