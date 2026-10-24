"""OAuth connect / callback for Meta and LinkedIn.

* The ``state`` value is random, single-use, bound to the signed-in CRM user
  and expires after 10 minutes. A callback with a missing, wrong, reused or
  expired state is rejected before any code exchange.
* The redirect URI is always built from the configured public base URL, and
  the callback checks it is being served on that same URI.
* Tokens never enter the session cookie or the page: after the callback the
  session only holds the id of the stored (encrypted) credential so the user
  can pick which Pages / organizations to connect.
"""
import hmac
import secrets
import time
import urllib.parse

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app import db
from app.social_media import bp
from app.social_media import permissions as perm
from app.social_media.models import SocialOAuthCredential
from app.social_media.services import accounts as acc_svc
from app.social_media.services import core, linkedin, meta, security
from app.social_media.services.http import ApiError, label as err_label, next_step

STATE_TTL = 600
SESSION_KEY = 'social_media_oauth'
PROVIDERS = ('meta', 'linkedin')


def _fail(message, kind=None):
    core.audit('oauth_failed', None, message, success=False)
    try:
        core.commit_with_retry()
    except Exception:
        db.session.rollback()
    flash(message + (f' {next_step(kind)}' if kind else ''), 'danger')
    return redirect(url_for('social_media.accounts'))


@bp.route('/connect/<provider>', methods=['POST'])
@perm.require('can_manage_accounts')
def oauth_connect(provider):
    if provider not in PROVIDERS:
        abort(404)
    if not security.is_ready():
        return _fail(security.encryption_status()[1])
    redirect_uri = core.redirect_uri(provider)
    state = secrets.token_urlsafe(32)
    try:
        url = (meta if provider == 'meta' else linkedin).authorize_url(state, redirect_uri)
    except ApiError as e:
        return _fail(e.message, e.kind)
    session[SESSION_KEY] = {'provider': provider, 'state': state, 'user_id': current_user.id,
                            'created': int(time.time()), 'redirect_uri': redirect_uri}
    core.audit('oauth_started', provider, None)
    core.commit_with_retry()
    return redirect(url)


@bp.route('/oauth/<provider>/callback')
@perm.require('can_manage_accounts')
def oauth_callback(provider):
    if provider not in PROVIDERS:
        abort(404)
    pending = session.pop(SESSION_KEY, None)  # single use, whatever happens next
    got_state = request.args.get('state', '')
    if (not pending or pending.get('provider') != provider or pending.get('user_id') != current_user.id
            or not got_state or not hmac.compare_digest(str(pending.get('state')), got_state)):
        return _fail('The authorization response could not be verified (invalid or reused state). '
                     'Start the connection again.')
    if time.time() - pending.get('created', 0) > STATE_TTL:
        return _fail('The authorization took too long and expired. Start the connection again.')
    configured = pending.get('redirect_uri') or ''
    if urllib.parse.urlsplit(configured).path != request.path:
        return _fail('The callback URL does not match the configured redirect URI.')
    if request.args.get('error'):
        reason = request.args.get('error_description') or request.args.get('error_reason') or request.args['error']
        return _fail(f'Authorization was not granted: {reason[:200]}')
    code = request.args.get('code')
    if not code:
        return _fail('The provider did not return an authorization code.')
    try:
        if provider == 'meta':
            cred = acc_svc.complete_meta_oauth(code, configured, current_user.id)
        else:
            cred = acc_svc.complete_linkedin_oauth(code, configured, current_user.id)
    except ApiError as e:
        db.session.rollback()
        return _fail(f'{err_label(e.kind)}: {e.message}', e.kind)
    except security.EncryptionNotConfigured as e:
        db.session.rollback()
        return _fail(str(e))
    core.audit('oauth_connected', f'{provider} {cred.external_user_name}', f'scopes: {", ".join(cred.scope_list)}')
    core.commit_with_retry()
    session['social_media_select'] = {'provider': provider, 'cred_id': cred.id, 'user_id': current_user.id}
    return redirect(url_for('social_media.oauth_select', provider=provider))


def _selection_cred(provider):
    sel = session.get('social_media_select') or {}
    cred_id = sel.get('cred_id') if sel.get('provider') == provider and sel.get('user_id') == current_user.id \
        else None
    if cred_id is None and request.args.get('cred') and perm.can('can_manage_accounts'):
        cred_id = int(request.args['cred']) if request.args['cred'].isdigit() else None
    cred = db.session.get(SocialOAuthCredential, cred_id) if cred_id else None
    if cred is None or cred.provider != provider or cred.token_type not in ('user', 'member'):
        return None
    return cred


@bp.route('/connect/<provider>/select', methods=['GET', 'POST'])
@perm.require('can_manage_accounts')
def oauth_select(provider):
    if provider not in PROVIDERS:
        abort(404)
    cred = _selection_cred(provider)
    if cred is None:
        flash('Connect the account first.', 'warning')
        return redirect(url_for('social_media.accounts'))
    try:
        if request.method == 'POST':
            if provider == 'meta':
                chosen = acc_svc.connect_meta_pages(cred, set(request.form.getlist('page_ids')),
                                                    set(request.form.getlist('instagram_ids')), current_user.id)
            else:
                chosen = acc_svc.connect_linkedin(cred, bool(request.form.get('member')),
                                                  set(request.form.getlist('org_urns')), current_user.id)
            core.audit('accounts_connected', provider, ', '.join(a.label for a in chosen) or 'none selected')
            core.commit_with_retry()
            # Import the posts that already exist on the new accounts straight away.
            from app.social_media.services import sync
            for acc in chosen:
                log = sync.sync_posts(acc)
                if log.status == 'error':
                    flash(f'{acc.label}: could not import existing posts - {log.message}', 'warning')
                core.commit_with_retry()
            session.pop('social_media_select', None)
            flash(f'{len(chosen)} account(s) connected.' if chosen else 'No accounts were selected.',
                  'success' if chosen else 'warning')
            return redirect(url_for('social_media.accounts'))
        if provider == 'meta':
            pages = acc_svc.available_meta_pages(cred)
            missing = [p for p in ('pages_show_list', 'pages_manage_posts') if p not in cred.scope_list]
            return render_template('social_media/connect_select.html', provider=provider, cred=cred, pages=pages,
                                   missing=missing)
        member, orgs, org_error = acc_svc.available_linkedin_identities(cred)
        return render_template('social_media/connect_select.html', provider=provider, cred=cred, member=member,
                               orgs=orgs, org_error=org_error)
    except (ApiError, security.SecretUnavailable, security.EncryptionNotConfigured) as e:
        db.session.rollback()
        kind = getattr(e, 'kind', None)
        return _fail(f'{err_label(kind) if kind else "Error"}: {getattr(e, "message", str(e))}', kind)
