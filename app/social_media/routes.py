"""Social Media pages. OAuth connect/callback is in oauth_routes.py, Facebook
Ads in ads_routes.py."""
import calendar as pycal
from datetime import date, datetime, timedelta

from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import or_

from app import db
from app.social_media import bp
from app.social_media import permissions as perm
from app.social_media.models import (PERMISSION_FLAGS, PLATFORM_LABELS, POST_STATUSES, SocialAccount,
                                     SocialAccountAccess, SocialAccountSync, SocialAuditLog, SocialNotification,
                                     SocialOAuthCredential, SocialPost, SocialPostDestination, SocialPostMedia,
                                     SocialPublishAttempt, SocialRolePermission, SocialUserPermission)
from app.social_media.services import accounts as acc_svc
from app.social_media.services import core, linkedin, meta, publisher, security, stats, sync
from app.social_media.services import media as media_svc
from app.social_media.services import scheduler as sched_svc
from app.social_media.services.http import ApiError, label as err_label, next_step

PER_PAGE = 25
TABS = [('all', 'All Posts'), ('published', 'Published'), ('scheduled', 'Scheduled'), ('drafts', 'Drafts'),
        ('failed', 'Failed'), ('cancelled', 'Cancelled')]
TAB_STATUSES = {'published': ['published', 'partially_published'], 'scheduled': ['scheduled', 'publishing'],
                'drafts': ['draft'], 'failed': ['failed', 'partially_published'], 'cancelled': ['cancelled']}


@bp.context_processor
def _inject():
    if not current_user.is_authenticated:
        return {}
    try:
        unread = SocialNotification.query.filter(SocialNotification.read_at.is_(None)).count() \
            if perm.can('can_view') else 0
    except Exception:
        unread = 0
    return {'sm_perms': perm.perms_for(), 'sm_unread': unread, 'sm_platform_labels': PLATFORM_LABELS,
            'sm_enabled': core.is_enabled(), 'sm_tz_name': core.get('timezone')}


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _commit(ok_msg=None):
    try:
        core.commit_with_retry()
        if ok_msg:
            flash(ok_msg, 'success')
        return True
    except Exception:
        db.session.rollback()
        flash('Could not save - the database is busy. Please try again.', 'danger')
        return False


def _parse_local(value):
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            return core.local_to_utc(datetime.strptime(value, fmt))
        except ValueError:
            continue
    return None


def _usable_accounts():
    return perm.visible_accounts(SocialAccount.query.filter_by(status='connected')).order_by(
        SocialAccount.platform, SocialAccount.name).all()


def _get_post(post_id):
    post = db.session.get(SocialPost, post_id)
    if post is None:
        abort(404)
    # A user who cannot see one of the post's accounts cannot open it.
    for d in post.destinations:
        if d.account is not None and not perm.can_use_account(d.account):
            abort(403)
    return post


def _editable(post):
    return post.origin == 'crm' and not any(
        d.status in ('published', 'publishing', 'needs_review', 'retry_wait') for d in post.destinations)


# ── Overview ──────────────────────────────────────────────────────────
@bp.route('/')
@perm.require('can_view')
def overview():
    preset, start, end, label, s_utc, e_utc = stats.resolve_range(request.args)
    data = stats.overview(s_utc, e_utc)
    series = stats.daily_series(s_utc, e_utc, start, end)
    from app.social_media.services import ads as ads_svc
    ad_acc = ads_svc.selected_account() if perm.can('can_view_ads') else None
    ad_summary = ads_svc.summary(ad_acc, start, end) if ad_acc else None
    upcoming = SocialPostDestination.query.filter(SocialPostDestination.status == 'scheduled').order_by(
        SocialPostDestination.scheduled_at).limit(8).all()
    recent = SocialPublishAttempt.query.order_by(SocialPublishAttempt.id.desc()).limit(8).all()
    failed = SocialPostDestination.query.filter(SocialPostDestination.status.in_(['failed', 'needs_review'])).order_by(
        SocialPostDestination.updated_at.desc()).limit(6).all()
    accounts = perm.visible_accounts().filter(SocialAccount.status != 'disconnected').order_by(
        SocialAccount.platform).all()
    notes = SocialNotification.query.order_by(SocialNotification.id.desc()).limit(6).all()
    from app.social_media.models import SocialAdCampaign
    campaigns = SocialAdCampaign.query.filter(SocialAdCampaign.effective_status == 'ACTIVE').limit(5).all() \
        if perm.can('can_view_ads') else []
    return render_template('social_media/overview.html', data=data, series=series, preset=preset, start=start,
                           end=end, range_label=label, by_platform=stats.by_platform(s_utc, e_utc),
                           upcoming=upcoming, recent=recent, failed=failed, accounts=accounts, notes=notes,
                           ad_acc=ad_acc, ad_summary=ad_summary, campaigns=campaigns,
                           problems=core.mark_ready_problems(), presets=stats.PRESETS)


@bp.route('/notifications/read', methods=['POST'])
@perm.require('can_view')
def notifications_read():
    SocialNotification.query.filter(SocialNotification.read_at.is_(None)).update(
        {'read_at': datetime.utcnow()}, synchronize_session=False)
    _commit()
    return redirect(request.referrer or url_for('social_media.overview'))


# ── Posts list ────────────────────────────────────────────────────────
@bp.route('/posts')
@perm.require('can_view')
def posts():
    tab = request.args.get('tab', 'all')
    if tab not in dict(TABS):
        tab = 'all'
    q = SocialPost.query
    if tab in TAB_STATUSES:
        q = q.filter(SocialPost.status.in_(TAB_STATUSES[tab]))
        if tab != 'published':
            q = q.filter(SocialPost.origin == 'crm')
    origin = request.args.get('origin', '')
    if origin in ('crm', 'synced'):
        q = q.filter(SocialPost.origin == origin)
    platform = request.args.get('platform', '')
    account_id = _int(request.args.get('account'))
    if platform or account_id:
        sub = SocialPostDestination.query.with_entities(SocialPostDestination.post_id)
        if platform:
            sub = sub.filter(SocialPostDestination.platform == platform)
        if account_id:
            sub = sub.filter(SocialPostDestination.account_id == account_id)
        q = q.filter(SocialPost.id.in_(sub))
    # Hide posts on accounts the user may not see.
    hidden = SocialAccount.query.with_entities(SocialAccount.id).filter(
        ~SocialAccount.id.in_(perm.visible_accounts().with_entities(SocialAccount.id)))
    q = q.filter(~SocialPost.id.in_(SocialPostDestination.query.with_entities(SocialPostDestination.post_id)
                                    .filter(SocialPostDestination.account_id.in_(hidden))))
    status = request.args.get('status', '')
    if status in POST_STATUSES:
        q = q.filter(SocialPost.status == status)
    created_by = _int(request.args.get('created_by'))
    if created_by:
        q = q.filter(SocialPost.created_by == created_by)
    term = (request.args.get('q') or '').strip()
    if term:
        like = f'%{term}%'
        q = q.filter(or_(SocialPost.title.ilike(like), SocialPost.body.ilike(like)))
    start, end = request.args.get('start'), request.args.get('end')
    try:
        if start:
            s = core.local_to_utc(datetime.combine(date.fromisoformat(start), datetime.min.time()))
            q = q.filter(or_(SocialPost.published_at >= s, SocialPost.scheduled_at >= s, SocialPost.created_at >= s))
        if end:
            e = core.local_to_utc(datetime.combine(date.fromisoformat(end) + timedelta(days=1), datetime.min.time()))
            q = q.filter(or_(SocialPost.published_at < e, SocialPost.scheduled_at < e, SocialPost.created_at < e))
    except ValueError:
        flash('Invalid date filter ignored.', 'warning')
    order = SocialPost.scheduled_at.asc() if tab == 'scheduled' else SocialPost.id.desc()
    page = q.order_by(order).paginate(page=_int(request.args.get('page'), 1), per_page=PER_PAGE, error_out=False)
    from app.models import User
    creators = User.query.filter(User.id.in_(SocialPost.query.with_entities(SocialPost.created_by).distinct())).all()
    return render_template('social_media/posts.html', page=page, tab=tab, tabs=TABS,
                           accounts=perm.visible_accounts().order_by(SocialAccount.name).all(), creators=creators,
                           counts=stats.status_counts(), args=request.args)


# ── Create / edit ─────────────────────────────────────────────────────
def _form_context(post=None):
    accounts = _usable_accounts()
    defaults = [int(i) for i in core.get('default_account_ids').split(',') if i.strip().isdigit()]
    selected = {d.account_id for d in post.destinations} if post else set(defaults)
    custom = {d.account_id: d.custom_text or '' for d in post.destinations} if post else {}
    img_types, vid_types = media_svc.allowed_types()
    return {'post': post, 'accounts': accounts, 'selected': selected, 'custom': custom,
            'accept': ','.join(img_types + vid_types), 'max_image_mb': core.get_int('max_image_mb', 8),
            'max_video_mb': core.get_int('max_video_mb', 16), 'tz_name': core.get('timezone'),
            'default_status': core.get('default_status')}


def _save_post_from_form(post):
    """Apply the form to the post. Returns (post, errors)."""
    f = request.form
    errors = []
    body = (f.get('body') or '').strip()
    link = (f.get('link_url') or '').strip()
    if link and not link.startswith(('http://', 'https://')):
        errors.append('The link must start with http:// or https://')
    if len(body) > 63206:
        errors.append('The text is too long.')
    account_ids = {int(i) for i in f.getlist('account_ids') if i.isdigit()}
    accounts = {a.id: a for a in _usable_accounts() if a.id in account_ids}
    if len(accounts) != len(account_ids):
        errors.append('One of the selected accounts is not available to you or is not connected.')
    if errors:
        return post, errors

    is_new = post is None
    if is_new:
        post = SocialPost(created_by=current_user.id, origin='crm', status='draft')
        db.session.add(post)
    post.title = (f.get('title') or '').strip()[:200] or None
    post.body = body
    post.hashtags = (f.get('hashtags') or '').strip()[:1000] or None
    post.link_url = link[:1000] or None
    post.updated_by = current_user.id
    db.session.flush()

    # Media: removals, order, new uploads.
    remove = {int(i) for i in f.getlist('remove_media') if i.isdigit()}
    for m in list(post.media):
        if m.id in remove:
            media_svc.delete_file(m)
            post.media.remove(m)
            db.session.delete(m)
        else:
            m.position = _int(f.get(f'media_order_{m.id}'), m.position)
    pos = max([m.position for m in post.media] + [0]) + 1
    for fs in request.files.getlist('media'):
        if not fs or not fs.filename:
            continue
        try:
            fields = media_svc.save_upload(fs)
        except media_svc.MediaError as e:
            errors.append(str(e))
            continue
        post.media.append(SocialPostMedia(position=pos, **fields))
        pos += 1

    # Destinations: keep, add, remove (only unpublished ones are touched).
    existing = {d.account_id: d for d in post.destinations}
    for acc_id, d in existing.items():
        if acc_id not in accounts and d.status in ('draft', 'scheduled', 'failed', 'cancelled'):
            post.destinations.remove(d)
            db.session.delete(d)
    for acc_id, acc in accounts.items():
        d = existing.get(acc_id)
        if d is None:
            d = SocialPostDestination(account_id=acc_id, platform=acc.platform, status='draft')
            post.destinations.append(d)
        d.custom_text = (f.get(f'custom_text_{acc_id}') or '').strip() or None
    db.session.flush()
    return post, errors


def _validate_destinations(post):
    problems = []
    for d in post.destinations:
        text = post.full_text(d.custom_text)
        for p in media_svc.validate_for_platform(d.platform, post, list(post.media), text):
            problems.append(f'{d.account.label if d.account else d.platform}: {p}')
    return problems


def _apply_action(post, action):
    """draft | schedule | publish. Returns list of errors (empty = done)."""
    f = request.form
    if action == 'draft':
        for d in post.destinations:
            if d.status in ('scheduled', 'failed', 'cancelled'):
                d.status = 'draft'
        post.scheduled_at = None
        publisher.refresh_post_status(post)
        post.status = 'draft'
        return []
    if not post.destinations:
        return ['Select at least one destination account.']
    problems = _validate_destinations(post)
    if problems:
        return problems
    if f.get('confirmed') != '1':
        return ['Please review and confirm the publishing summary.']
    if action == 'schedule':
        if not perm.can('can_schedule'):
            return ['You do not have permission to schedule posts.']
        when = _parse_local(f.get('scheduled_at'))
        if when is None:
            return ['Choose a valid date and time to schedule the post.']
        if when < datetime.utcnow() + timedelta(minutes=1):
            return ['The scheduled time must be in the future.']
        post.scheduled_at = when
    else:
        if not perm.can('can_publish'):
            return ['You do not have permission to publish posts.']
        when = datetime.utcnow()
        post.scheduled_at = when
    for d in post.destinations:
        if d.status in ('draft', 'scheduled', 'failed', 'cancelled'):
            d.status, d.scheduled_at = 'scheduled', when
            d.failure_count, d.error_kind, d.error_message, d.error_code = 0, None, None, None
    publisher.refresh_post_status(post)
    return []


def _publish_now(post):
    for d in list(post.destinations):
        if d.status == 'scheduled':
            publisher.publish_destination(d.id, triggered_by='user', user_id=current_user.id, wait_seconds=25)
    db.session.refresh(post)


def _handle_post_form(post):
    action = request.form.get('action', 'draft')
    if action not in ('draft', 'schedule', 'publish'):
        abort(400)
    if action == 'publish' and not core.is_enabled():
        flash('Publishing is disabled in API Settings > General.', 'danger')
        return None
    post, errors = _save_post_from_form(post)
    if not errors:
        errors = _apply_action(post, action)
    if errors:
        # Keep the draft (content and uploads are not lost) and show what to fix.
        if post is not None and post.id:
            if action != 'draft':
                for d in post.destinations:
                    if d.status == 'scheduled' and post.status == 'draft':
                        d.status = 'draft'
            _commit()
        for e in errors:
            flash(e, 'danger')
        return post
    verb = {'draft': 'post_draft_saved', 'schedule': 'post_scheduled', 'publish': 'post_publish_now'}[action]
    core.audit(verb, post.display_title, ', '.join(d.account.label for d in post.destinations if d.account)
               + (f' at {post.scheduled_at:%Y-%m-%d %H:%M} UTC' if action == 'schedule' else ''))
    if not _commit():
        return post
    if action == 'publish':
        _publish_now(post)
        ok = [d for d in post.destinations if d.status == 'published']
        bad = [d for d in post.destinations if d.status in ('failed', 'needs_review')]
        pending = [d for d in post.destinations if d.status in ('retry_wait', 'publishing', 'scheduled')]
        if ok:
            flash(f'Published to {len(ok)} of {len(post.destinations)} destinations.', 'success')
        if bad:
            flash(f'{len(bad)} destination(s) failed - see the details below.', 'danger')
        if pending:
            flash(f'{len(pending)} destination(s) are still processing; the scheduler will finish them.', 'warning')
    elif action == 'schedule':
        flash(f'Scheduled for {core.to_local(post.scheduled_at):%d %b %Y, %I:%M %p} ({core.get("timezone")}).',
              'success')
    else:
        flash('Draft saved.', 'success')
    return post


@bp.route('/posts/new', methods=['GET', 'POST'])
@perm.require('can_create_posts')
def post_new():
    if request.method == 'POST':
        post = _handle_post_form(None)
        if post is not None and post.id:
            target = 'social_media.post_detail' if post.status != 'draft' else 'social_media.post_edit'
            return redirect(url_for(target, post_id=post.id))
        return render_template('social_media/post_form.html', **_form_context(None))
    return render_template('social_media/post_form.html', **_form_context(None))


@bp.route('/posts/<int:post_id>/edit', methods=['GET', 'POST'])
@perm.require('can_create_posts')
def post_edit(post_id):
    post = _get_post(post_id)
    if not (perm.can('can_edit_posts') or post.created_by == current_user.id):
        abort(403)
    if not _editable(post):
        flash('This post has already been (or is being) published and cannot be edited. Duplicate it instead.',
              'warning')
        return redirect(url_for('social_media.post_detail', post_id=post.id))
    if request.method == 'POST':
        post = _handle_post_form(post)
        if post is not None and post.status != 'draft':
            return redirect(url_for('social_media.post_detail', post_id=post.id))
        return redirect(url_for('social_media.post_edit', post_id=post_id))
    return render_template('social_media/post_form.html', **_form_context(post))


@bp.route('/posts/<int:post_id>')
@perm.require('can_view')
def post_detail(post_id):
    post = _get_post(post_id)
    return render_template('social_media/post_detail.html', post=post, editable=_editable(post),
                           err_label=err_label, next_step=next_step)


@bp.route('/media/<int:media_id>')
@perm.require('can_view')
def media_file(media_id):
    """Authenticated preview of stored media."""
    m = db.session.get(SocialPostMedia, media_id)
    if m is None:
        abort(404)
    _get_post(m.post_id)
    try:
        return send_file(media_svc.path_for(m), mimetype=m.mime_type, conditional=True)
    except (OSError, media_svc.MediaError):
        abort(404)


@bp.route('/public-media/<token>')
def public_media(token):
    """Signed, expiring, unauthenticated URL for Instagram to fetch media of a
    post being published. See services/media.py."""
    if token == 'probe':
        return 'social-media-public-media-ok', 200, {'Content-Type': 'text/plain', 'Cache-Control': 'no-store'}
    m = media_svc.resolve_token(token)
    if m is None:
        abort(404)
    try:
        resp = send_file(media_svc.path_for(m), mimetype=m.mime_type, conditional=True)
    except (OSError, media_svc.MediaError):
        abort(404)
    resp.headers['X-Robots-Tag'] = 'noindex'
    resp.headers['Cache-Control'] = 'private, max-age=3600'
    return resp


@bp.route('/posts/<int:post_id>/duplicate', methods=['POST'])
@perm.require('can_create_posts')
def post_duplicate(post_id):
    src = _get_post(post_id)
    import os
    import shutil
    import uuid
    from app.social_media import media_root
    dup = SocialPost(title=((src.title or src.display_title) + ' (copy)')[:200], body=src.body, hashtags=src.hashtags,
                     link_url=src.link_url, status='draft', origin='crm', created_by=current_user.id,
                     duplicated_from_id=src.id)
    db.session.add(dup)
    db.session.flush()
    for m in src.media:
        new_name = uuid.uuid4().hex + os.path.splitext(m.stored_name)[1]
        try:
            shutil.copyfile(media_svc.path_for(m), os.path.join(media_root(), new_name))
        except (OSError, media_svc.MediaError):
            continue
        dup.media.append(SocialPostMedia(kind=m.kind, stored_name=new_name, original_name=m.original_name,
                                         mime_type=m.mime_type, size_bytes=m.size_bytes, width=m.width,
                                         height=m.height, position=m.position))
    for d in src.destinations:
        if d.account and d.account.status == 'connected' and perm.can_use_account(d.account):
            dup.destinations.append(SocialPostDestination(account_id=d.account_id, platform=d.platform,
                                                          custom_text=d.custom_text, status='draft'))
    core.audit('post_duplicated', src.display_title, f'new draft #{dup.id}')
    if _commit('Copied to a new draft.'):
        return redirect(url_for('social_media.post_edit', post_id=dup.id))
    return redirect(url_for('social_media.post_detail', post_id=post_id))


@bp.route('/posts/<int:post_id>/cancel', methods=['POST'])
@perm.require('can_delete_posts')
def post_cancel(post_id):
    post = _get_post(post_id)
    n = 0
    for d in post.destinations:
        if d.status in ('scheduled', 'retry_wait'):
            d.status, n = 'cancelled', n + 1
    publisher.refresh_post_status(post)
    core.audit('post_cancelled', post.display_title, f'{n} destination(s) cancelled')
    _commit(f'Cancelled {n} scheduled destination(s).' if n else 'Nothing was waiting to be published.')
    return redirect(url_for('social_media.post_detail', post_id=post.id))


@bp.route('/posts/<int:post_id>/reschedule', methods=['POST'])
@perm.require('can_schedule')
def post_reschedule(post_id):
    post = _get_post(post_id)
    when = _parse_local(request.form.get('scheduled_at'))
    if when is None or when < datetime.utcnow() + timedelta(minutes=1):
        flash('Choose a valid future date and time.', 'danger')
        return redirect(request.referrer or url_for('social_media.post_detail', post_id=post.id))
    n = 0
    for d in post.destinations:
        if d.status in ('scheduled', 'cancelled', 'draft', 'failed') and not d.remote_id and d.account and \
                d.account.status == 'connected':
            d.status, d.scheduled_at, d.failure_count = 'scheduled', when, 0
            d.error_message = d.error_kind = None
            n += 1
    post.scheduled_at = when
    publisher.refresh_post_status(post)
    core.audit('post_rescheduled', post.display_title, f'{n} destination(s) to {when:%Y-%m-%d %H:%M} UTC')
    _commit(f'Rescheduled {n} destination(s) for {core.to_local(when):%d %b %Y, %I:%M %p}.')
    return redirect(request.referrer or url_for('social_media.post_detail', post_id=post.id))


@bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@perm.require('can_delete_posts')
def post_delete(post_id):
    """Delete the CRM record only. Remote posts are never deleted here."""
    post = _get_post(post_id)
    if any(d.status in ('publishing', 'retry_wait') for d in post.destinations):
        flash('This post is being published right now; cancel it first.', 'warning')
        return redirect(url_for('social_media.post_detail', post_id=post.id))
    title = post.display_title
    for m in post.media:
        media_svc.delete_file(m)
    db.session.delete(post)
    core.audit('post_deleted_local', title, 'CRM record removed; posts on the platforms were not touched')
    _commit('Removed from the CRM. Nothing was deleted on the social platforms.')
    return redirect(url_for('social_media.posts'))


@bp.route('/destinations/<int:dest_id>/retry', methods=['POST'])
@perm.require('can_publish')
def destination_retry(dest_id):
    d = db.session.get(SocialPostDestination, dest_id) or abort(404)
    _get_post(d.post_id)
    if d.status == 'needs_review' and request.form.get('confirm_checked') != '1':
        flash('Confirm that you checked the platform and the post is not already live.', 'danger')
        return redirect(url_for('social_media.post_detail', post_id=d.post_id))
    if publisher.manual_retry(d, current_user.id):
        publisher.publish_destination(d.id, triggered_by='user', user_id=current_user.id, wait_seconds=25)
        d = db.session.get(SocialPostDestination, dest_id)
        flash(f'Retry result: {d.status.replace("_", " ")}.', 'success' if d.status == 'published' else 'warning')
    else:
        flash('This destination cannot be retried.', 'warning')
    return redirect(url_for('social_media.post_detail', post_id=d.post_id))


@bp.route('/destinations/<int:dest_id>/delete-remote', methods=['POST'])
@perm.require('can_delete_posts', 'can_publish')
def destination_delete_remote(dest_id):
    d = db.session.get(SocialPostDestination, dest_id) or abort(404)
    _get_post(d.post_id)
    if request.form.get('confirm_text') != 'DELETE':
        flash('Type DELETE to confirm removing the post from the platform.', 'danger')
        return redirect(url_for('social_media.post_detail', post_id=d.post_id))
    if not d.remote_id or d.platform == 'instagram' or d.account is None:
        flash('Deleting this post through the API is not supported. Delete it in the platform app.', 'warning')
        return redirect(url_for('social_media.post_detail', post_id=d.post_id))
    try:
        token = acc_svc.token_for(d.account)
        if d.platform == 'facebook':
            meta.delete_facebook(d.remote_id, token)
        else:
            linkedin.delete(d.remote_id, token)
        core.audit('remote_post_deleted', d.post.display_title, f'{d.account.label} {d.remote_id}')
        d.status, d.error_message = 'cancelled', 'Deleted from the platform by a CRM user.'
        publisher.refresh_post_status(d.post)
        _commit('Deleted from the platform.')
    except ApiError as e:
        core.audit('remote_post_delete_failed', d.post.display_title, e.message, success=False)
        _commit()
        flash(f'The platform refused: {e.message}', 'danger')
    return redirect(url_for('social_media.post_detail', post_id=d.post_id))


@bp.route('/destinations/<int:dest_id>/metrics', methods=['POST'])
@perm.require('can_view_analytics')
def destination_metrics(dest_id):
    d = db.session.get(SocialPostDestination, dest_id) or abort(404)
    _get_post(d.post_id)
    if d.status != 'published' or not d.account:
        abort(400)
    try:
        publisher.store_metrics(d, sync.metrics_for(d, d.account, acc_svc.token_for(d.account)))
        _commit('Metrics updated.')
    except ApiError as e:
        acc_svc.mark_auth_problem(d.account, e)
        _commit()
        flash(f'Could not read metrics: {e.message}', 'danger')
    return redirect(url_for('social_media.post_detail', post_id=d.post_id))


# ── Calendar ──────────────────────────────────────────────────────────
@bp.route('/calendar')
@perm.require('can_view')
def calendar():
    view = request.args.get('view', 'month')
    if view not in ('month', 'week', 'day', 'list'):
        view = 'month'
    try:
        anchor = date.fromisoformat(request.args.get('date'))
    except (TypeError, ValueError):
        anchor = core.local_now().date()
    if view == 'month':
        first = anchor.replace(day=1)
        start = first - timedelta(days=first.weekday())
        last = first.replace(day=pycal.monthrange(first.year, first.month)[1])
        end = last + timedelta(days=6 - last.weekday())
        prev_d, next_d = (first - timedelta(days=1)).replace(day=1), last + timedelta(days=1)
        title = first.strftime('%B %Y')
    elif view == 'week':
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        prev_d, next_d = start - timedelta(days=7), start + timedelta(days=7)
        title = f'{start:%d %b} – {end:%d %b %Y}'
    elif view == 'day':
        start = end = anchor
        prev_d, next_d = anchor - timedelta(days=1), anchor + timedelta(days=1)
        title = anchor.strftime('%A, %d %B %Y')
    else:
        start, end = anchor, anchor + timedelta(days=30)
        prev_d, next_d = anchor - timedelta(days=30), anchor + timedelta(days=30)
        title = f'{start:%d %b} – {end:%d %b %Y}'
    s_utc = core.local_to_utc(datetime.combine(start, datetime.min.time()))
    e_utc = core.local_to_utc(datetime.combine(end + timedelta(days=1), datetime.min.time()))
    D = SocialPostDestination
    when = db.func.coalesce(D.published_at, D.scheduled_at, D.created_at)
    q = D.query.join(SocialPost).filter(when >= s_utc, when < e_utc,
                                        D.account_id.in_(perm.visible_accounts().with_entities(SocialAccount.id)))
    platform, account_id, status = request.args.get('platform'), _int(request.args.get('account')), \
        request.args.get('status')
    if platform:
        q = q.filter(D.platform == platform)
    if account_id:
        q = q.filter(D.account_id == account_id)
    if status:
        q = q.filter(SocialPost.status == status)
    if request.args.get('origin') != 'all':
        q = q.filter(SocialPost.origin == 'crm')
    items = {}
    for d in q.order_by(when).all():
        key = core.to_local(d.published_at or d.scheduled_at or d.created_at).date()
        items.setdefault(key, []).append(d)
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return render_template('social_media/calendar.html', view=view, anchor=anchor, days=days, items=items,
                           title=title, prev_d=prev_d, next_d=next_d, today=core.local_now().date(),
                           accounts=perm.visible_accounts().order_by(SocialAccount.name).all(), args=request.args,
                           statuses=POST_STATUSES)


# ── Analytics ─────────────────────────────────────────────────────────
@bp.route('/analytics')
@perm.require('can_view_analytics')
def analytics():
    preset, start, end, label, s_utc, e_utc = stats.resolve_range(request.args)
    D = SocialPostDestination
    top = D.query.filter(D.status == 'published', D.published_at >= s_utc, D.published_at < e_utc,
                         D.account_id.in_(perm.visible_accounts().with_entities(SocialAccount.id))).order_by(
        D.engagements.desc().nullslast(), D.published_at.desc()).limit(25).all()
    syncs = SocialAccountSync.query.filter(SocialAccountSync.kind != 'test').order_by(
        SocialAccountSync.id.desc()).limit(10).all()
    return render_template('social_media/analytics.html', preset=preset, start=start, end=end, range_label=label,
                           by_platform=stats.by_platform(s_utc, e_utc), data=stats.overview(s_utc, e_utc),
                           series=stats.daily_series(s_utc, e_utc, start, end), top=top, syncs=syncs,
                           presets=stats.PRESETS)


@bp.route('/analytics/sync', methods=['POST'])
@perm.require('can_view_analytics')
def analytics_sync():
    kind = request.form.get('kind', 'insights')
    if kind not in ('insights', 'posts'):
        abort(400)
    n_ok = n_err = 0
    for a in perm.visible_accounts(SocialAccount.query.filter_by(status='connected')).all():
        log = (sync.sync_insights if kind == 'insights' else sync.sync_posts)(a)
        n_ok, n_err = n_ok + (log.status != 'error'), n_err + (log.status == 'error')
        if not _commit():
            break
    core.audit(f'sync_{kind}', None, f'{n_ok} ok, {n_err} errors', success=not n_err)
    _commit()
    flash(f'Synchronisation finished: {n_ok} account(s) OK, {n_err} with errors (see the sync log).',
          'success' if not n_err else 'warning')
    return redirect(request.referrer or url_for('social_media.analytics'))


# ── Accounts ──────────────────────────────────────────────────────────
@bp.route('/accounts')
@perm.require('can_view_accounts')
def accounts():
    from app.models import User
    rows = perm.visible_accounts().order_by(SocialAccount.platform, SocialAccount.name).all()
    by_platform = {p: [a for a in rows if a.platform == p] for p in ('facebook', 'instagram', 'linkedin')}
    access = {}
    for r in SocialAccountAccess.query.all():
        access.setdefault(r.account_id, set()).add(r.user_id)
    meta_ready = bool(core.get('meta_app_id') and core.has_secret('meta_app_secret'))
    li_ready = bool(core.get('linkedin_client_id') and core.has_secret('linkedin_client_secret'))
    return render_template('social_media/accounts.html', by_platform=by_platform, access=access,
                           users=User.query.filter(User.is_active.is_(True)).order_by(User.username).all(),
                           meta_ready=meta_ready, li_ready=li_ready, enc_ok=security.is_ready(),
                           meta_user=SocialOAuthCredential.query.filter_by(provider='meta', token_type='user')
                           .order_by(SocialOAuthCredential.updated_at.desc()).first())


def _account_or_404(account_id):
    a = db.session.get(SocialAccount, account_id)
    if a is None or not perm.can_use_account(a):
        abort(404)
    return a


@bp.route('/accounts/<int:account_id>/test', methods=['POST'])
@perm.require('can_view_accounts')
def account_test(account_id):
    a = _account_or_404(account_id)
    ok, kind, msg = acc_svc.test_account(a)
    core.audit('account_test', a.label, msg, success=ok)
    _commit()
    flash(('Connection successful. ' if ok else f'{err_label(kind)}: ') + msg + ('' if ok else ' ' + next_step(kind)),
          'success' if ok else 'danger')
    return redirect(url_for('social_media.accounts'))


@bp.route('/accounts/<int:account_id>/refresh', methods=['POST'])
@perm.require('can_view_accounts')
def account_refresh(account_id):
    a = _account_or_404(account_id)
    logs = [sync.sync_posts(a), sync.sync_insights(a)]
    _commit()
    flash(' '.join(f'{l.kind.title()}: {l.message}' for l in logs),
          'success' if all(l.status != 'error' for l in logs) else 'warning')
    return redirect(url_for('social_media.accounts'))


@bp.route('/accounts/<int:account_id>/disconnect', methods=['POST'])
@perm.require('can_manage_accounts')
def account_disconnect(account_id):
    a = _account_or_404(account_id)
    affected = {d.post for d in SocialPostDestination.query.filter(
        SocialPostDestination.account_id == a.id, SocialPostDestination.status.in_(['scheduled', 'retry_wait']))}
    acc_svc.disconnect(a)
    for p in affected:
        publisher.refresh_post_status(p)
    core.audit('account_disconnected', a.label, f'{len(affected)} scheduled post(s) cancelled for this account')
    _commit(f'{a.label} disconnected. Posts already on the platform were not changed.')
    return redirect(url_for('social_media.accounts'))


@bp.route('/accounts/<int:account_id>/access', methods=['POST'])
@perm.require('can_manage_accounts')
def account_access(account_id):
    a = _account_or_404(account_id)
    SocialAccountAccess.query.filter_by(account_id=a.id).delete()
    ids = {int(i) for i in request.form.getlist('user_ids') if i.isdigit()}
    for uid in ids:
        db.session.add(SocialAccountAccess(account_id=a.id, user_id=uid))
    core.audit('account_access_changed', a.label, f'restricted to {len(ids)} user(s)' if ids else 'unrestricted')
    _commit('Access updated.')
    return redirect(url_for('social_media.accounts'))


# ── Settings ──────────────────────────────────────────────────────────
SETTINGS_TABS = [('general', 'General'), ('meta', 'Meta / Facebook'), ('instagram', 'Instagram'),
                 ('linkedin', 'LinkedIn'), ('ads', 'Facebook Ads'), ('media', 'Media Storage'),
                 ('scheduler', 'Scheduler'), ('notifications', 'Notifications'), ('security', 'Security & Logs'),
                 ('permissions', 'Permissions')]
TEXT_FIELDS = {
    'general': ['timezone', 'default_status', 'max_retries', 'retry_base_seconds'],
    'meta': ['meta_app_id', 'meta_graph_version', 'meta_login_config_id', 'meta_app_mode', 'meta_app_review_status',
             'meta_business_verification'],
    'instagram': ['meta_instagram_mode'],
    'linkedin': ['linkedin_client_id', 'linkedin_version', 'linkedin_member_posting', 'linkedin_org_posting'],
    'ads': ['ads_budget_increase_confirm_pct'],
    'media': ['max_image_mb', 'max_video_mb', 'allowed_image_types', 'allowed_video_types', 'public_base_url',
              'public_media_hours', 'media_cleanup_days'],
    'notifications': ['notify_email_to'],
}
BOOL_FIELDS = {'general': ['enabled'], 'ads': ['ads_enabled'],
               'notifications': ['notify_success', 'notify_failure', 'notify_email_failures']}
SECRET_FIELDS = {'meta': ['meta_app_secret'], 'linkedin': ['linkedin_client_secret']}
INT_FIELDS = {'max_retries': (0, 10), 'retry_base_seconds': (30, 3600), 'max_image_mb': (1, 8),
              'max_video_mb': (1, 1024), 'public_media_hours': (1, 168), 'media_cleanup_days': (0, 3650),
              'ads_budget_increase_confirm_pct': (1, 500)}
ENUMS = {'default_status': ('draft', 'scheduled'), 'meta_app_mode': ('development', 'live'),
         'meta_app_review_status': ('not_started', 'submitted', 'approved', 'rejected', 'not_required'),
         'meta_business_verification': ('not_started', 'pending', 'verified', 'not_required'),
         'meta_instagram_mode': ('facebook_login',),
         'linkedin_member_posting': ('unknown', 'approved', 'not_requested'),
         'linkedin_org_posting': ('unknown', 'requested', 'approved', 'not_requested')}


@bp.route('/settings')
@perm.require('can_manage_settings')
def settings():
    tab = request.args.get('tab', 'general')
    if tab not in dict(SETTINGS_TABS):
        tab = 'general'
    from app.models import User
    from app.social_media.services import ads as ads_svc
    values = {k: core.get(k) for k in core.DEFAULTS}
    values['linkedin_version'] = core.get('linkedin_version')
    secrets_set = {k: core.has_secret(k) for k in core.SECRET_KEYS}
    meta_cred = SocialOAuthCredential.query.filter_by(provider='meta', token_type='user').order_by(
        SocialOAuthCredential.updated_at.desc()).first()
    li_cred = SocialOAuthCredential.query.filter_by(provider='linkedin').order_by(
        SocialOAuthCredential.updated_at.desc()).first()
    try:
        meta_redirect = core.redirect_uri('meta')
        li_redirect = core.redirect_uri('linkedin')
    except Exception:
        meta_redirect = li_redirect = ''
    roles = sorted({u.role or 'user' for u in User.query.all()} | {'manager', 'user'} - {'admin'})
    from app.social_media.models import SocialAdAccount
    return render_template(
        'social_media/settings.html', tab=tab, tabs=SETTINGS_TABS, v=values, secrets_set=secrets_set,
        enc=security.encryption_status(), meta_perms=core.META_PERMISSIONS, li_scopes=core.LINKEDIN_SCOPES,
        chosen_meta=set(values['meta_scopes'].split(',')), chosen_li=set(values['linkedin_scopes'].split(',')),
        meta_cred=meta_cred, li_cred=li_cred, meta_redirect=meta_redirect, li_redirect=li_redirect,
        health=sched_svc.health(), flags=PERMISSION_FLAGS, roles=roles,
        role_perms={r.role: r for r in SocialRolePermission.query.all()},
        user_perms={p.user_id: p for p in SocialUserPermission.query.all()},
        users=User.query.filter(User.is_active.is_(True)).order_by(User.username).all(),
        accounts=SocialAccount.query.filter_by(status='connected').order_by(SocialAccount.name).all(),
        default_ids={int(i) for i in values['default_account_ids'].split(',') if i.strip().isdigit()},
        ad_accounts=SocialAdAccount.query.order_by(SocialAdAccount.name).all(), ads_cred=ads_svc.credential(),
        enums=ENUMS, public_base=core.public_base_url(), mask=security.mask,
        default_li_version=core._linkedin_default_version())


@bp.route('/settings/<section>', methods=['POST'])
@perm.require('can_manage_settings')
def settings_save(section):
    if section not in dict(SETTINGS_TABS):
        abort(404)
    f = request.form
    errors = []
    if section == 'permissions':
        return _save_permissions()
    for key in TEXT_FIELDS.get(section, []):
        val = (f.get(key) or '').strip()
        if key in INT_FIELDS:
            lo, hi = INT_FIELDS[key]
            n = _int(val)
            if n is None or not lo <= n <= hi:
                errors.append(f'{key.replace("_", " ").title()} must be between {lo} and {hi}.')
                continue
            val = str(n)
        if key in ENUMS and val not in ENUMS[key]:
            errors.append(f'Invalid value for {key}.')
            continue
        if key == 'timezone':
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(val)
            except Exception:
                errors.append(f'Unknown timezone "{val}". Use an IANA name such as Asia/Karachi.')
                continue
        if key == 'meta_graph_version' and not (val.startswith('v') and val[1:].replace('.', '').isdigit()):
            errors.append('Graph API version must look like v24.0.')
            continue
        if key == 'linkedin_version' and val and not (len(val) == 6 and val.isdigit()):
            errors.append('LinkedIn version must be YYYYMM, e.g. 202607 (or empty for automatic).')
            continue
        if key == 'public_base_url' and val and not val.startswith('https://'):
            errors.append('The public base URL must start with https:// (Meta only fetches HTTPS media).')
            continue
        if key in ('allowed_image_types', 'allowed_video_types'):
            allowed = set(media_svc.EXT_FOR_MIME)
            parts = [p.strip() for p in val.split(',') if p.strip()]
            if not parts or not set(parts) <= allowed:
                errors.append(f'File types must be a subset of: {", ".join(sorted(allowed))}.')
                continue
            val = ','.join(parts)
        core.set_value(key, val.rstrip('/') if key == 'public_base_url' else val, current_user.id)
    for key in BOOL_FIELDS.get(section, []):
        core.set_value(key, '1' if f.get(key) else '0', current_user.id)
    if section == 'general':
        ids = [i for i in f.getlist('default_account_ids') if i.isdigit()]
        core.set_value('default_account_ids', ','.join(ids), current_user.id)
    if section == 'meta':
        known = {p for p, _ in core.META_PERMISSIONS} - {'ads_read', 'ads_management'}
        core.set_value('meta_scopes', ','.join(p for p in f.getlist('meta_scopes') if p in known), current_user.id)
    if section == 'linkedin':
        known = {p for p, _ in core.LINKEDIN_SCOPES}
        core.set_value('linkedin_scopes', ','.join(p for p in f.getlist('linkedin_scopes') if p in known),
                       current_user.id)
    if section == 'ads':
        sel = _int(f.get('selected_ad_account'))
        if sel:
            from app.social_media.models import SocialAdAccount
            for acc in SocialAdAccount.query.all():
                acc.is_selected = acc.id == sel
    for key in SECRET_FIELDS.get(section, []):
        val = (f.get(key) or '').strip()
        if f.get(f'clear_{key}'):
            core.set_secret(key, None, current_user.id)
        elif val:
            try:
                core.set_secret(key, val, current_user.id)
            except security.EncryptionNotConfigured as e:
                errors.append(str(e))
    for e in errors:
        flash(e, 'danger')
    core.audit('settings_saved', dict(SETTINGS_TABS)[section], 'errors: ' + '; '.join(errors) if errors else None,
               success=not errors)
    _commit(None if errors else 'Settings saved.')
    return redirect(url_for('social_media.settings', tab=section))


def _save_permissions():
    f = request.form
    roles = [r for r in f.getlist('roles') if r and r != 'admin']
    for role in roles:
        row = db.session.get(SocialRolePermission, role) or SocialRolePermission(role=role)
        db.session.add(row)
        for flag, _ in PERMISSION_FLAGS:
            setattr(row, flag, bool(f.get(f'role_{role}_{flag}')))
    from app.models import User
    for u in User.query.filter(User.is_active.is_(True)).all():
        if u.role == 'admin':
            continue
        flags = {flag: bool(f.get(f'user_{u.id}_{flag}')) for flag, _ in PERMISSION_FLAGS}
        row = SocialUserPermission.query.filter_by(user_id=u.id).first()
        if row is None and not any(flags.values()):
            continue
        if row is None:
            row = SocialUserPermission(user_id=u.id)
            db.session.add(row)
        for flag, val in flags.items():
            setattr(row, flag, val)
    core.audit('permissions_changed', 'Social Media permissions', f'roles: {", ".join(roles)}')
    _commit('Permissions saved.')
    return redirect(url_for('social_media.settings', tab='permissions'))


@bp.route('/settings/test/<what>', methods=['POST'])
@perm.require('can_manage_settings')
def settings_test(what):
    """Every test makes a real server-side check. Returns JSON for the page."""
    result = {'ok': False, 'kind': 'not_configured', 'message': '', 'next': ''}
    try:
        if what == 'meta_app':
            info = meta.app_info()
            result.update(ok=True, kind='ok', message=f'App credentials valid: "{info.get("name")}" (id {info.get("id")}).')
        elif what == 'meta_oauth':
            meta.app_credentials()
            redirect_uri = core.redirect_uri('meta')
            if not redirect_uri.startswith('https://'):
                raise ApiError(f'The callback URL {redirect_uri} is not HTTPS; Meta requires HTTPS redirect URIs '
                               f'outside localhost. Set the Public base URL.', kind='not_configured')
            cred = SocialOAuthCredential.query.filter_by(provider='meta', token_type='user').order_by(
                SocialOAuthCredential.updated_at.desc()).first()
            if cred is None:
                raise ApiError('No Facebook login connected yet - use Connected Accounts > Connect Facebook.',
                               kind='invalid_token')
            info = meta.debug_token(security.decrypt(cred.access_token_enc))
            if not info.get('is_valid'):
                raise ApiError('Meta reports the stored login token is not valid.', kind='invalid_token')
            missing = sorted(set(meta.scopes()) - set(info.get('scopes') or []))
            if missing:
                raise ApiError('Token valid, but these permissions were not granted: ' + ', '.join(missing),
                               kind='missing_permission')
            exp = info.get('expires_at')
            result.update(ok=True, kind='ok', message='Login token valid with all requested permissions'
                          + (f'; expires {core.to_local(datetime.utcfromtimestamp(exp)):%d %b %Y}.' if exp else '.'))
        elif what == 'linkedin':
            linkedin.client_credentials()
            cred = SocialOAuthCredential.query.filter_by(provider='linkedin').order_by(
                SocialOAuthCredential.updated_at.desc()).first()
            if cred is None:
                raise ApiError('Client ID and Secret are saved. Connect a LinkedIn member to complete the test '
                               '(LinkedIn can only validate them with a token).', kind='invalid_token')
            info = linkedin.introspect(security.decrypt(cred.access_token_enc))
            if not info.get('active'):
                raise ApiError('LinkedIn reports the stored token is not active.', kind='invalid_token')
            result.update(ok=True, kind='ok', message=f'Client credentials and member token valid. Scopes: '
                                                      f'{info.get("scope")}.')
        elif what == 'ads':
            from app.social_media.services import ads as ads_svc
            g, cred = ads_svc.graph()
            rows = g.get('me/adaccounts', fields='id,name,currency', limit=5).get('data', [])
            result.update(ok=True, kind='ok', message=f'Marketing API reachable: {len(rows)} ad account(s) visible'
                          + (f', e.g. {rows[0]["name"]} ({rows[0]["currency"]})' if rows else '')
                          + ('. ads_management granted.' if ads_svc.can_manage(cred) else
                             '. ads_management NOT granted - reporting only.'))
        elif what == 'media':
            from app.social_media.services.http import send
            base = core.public_base_url()
            url = core.external_url('social_media.public_media', token='probe')
            if not url.startswith('https://'):
                raise ApiError(f'Public base URL is "{base or "not set"}". Instagram needs a public HTTPS URL.',
                               kind='not_configured')
            body = send('GET', url, timeout=15).body
            if b'social-media-public-media-ok' not in body:
                raise ApiError(f'{url} answered, but not with this CRM\'s probe response.', kind='not_configured')
            result.update(ok=True, kind='ok', message=f'{url} is publicly reachable from this server.')
        elif what == 'scheduler':
            h = sched_svc.health()
            summary = sched_svc.tick(current_app_obj())
            ok = not summary['error']
            result.update(ok=ok, kind='ok' if ok else 'api_error',
                          message=('Scheduler pass completed: ' if ok else 'Scheduler pass failed: ')
                          + (summary['error'] or f'{summary["published"]} published, {summary["failed"]} failed. '
                             f'Background job running in this process: {"yes" if h["in_process"] else "no"}.'))
        else:
            abort(404)
    except ApiError as e:
        result.update(ok=False, kind=e.kind, message=e.message, next=next_step(e.kind))
    except security.SecretUnavailable as e:
        result.update(ok=False, kind='not_configured', message=str(e), next=next_step('not_configured'))
    result['label'] = 'Connection successful' if result['ok'] else err_label(result['kind'])
    core.audit(f'test_{what}', None, result['message'], success=result['ok'])
    _commit()
    return jsonify(result)


def current_app_obj():
    from flask import current_app
    return current_app._get_current_object()


# ── Logs ──────────────────────────────────────────────────────────────
@bp.route('/logs')
@perm.require('can_view_logs')
def logs():
    view = request.args.get('view', 'activity')
    page_no = _int(request.args.get('page'), 1)
    if view == 'attempts':
        page = SocialPublishAttempt.query.order_by(SocialPublishAttempt.id.desc()).paginate(
            page=page_no, per_page=50, error_out=False)
    elif view == 'syncs':
        page = SocialAccountSync.query.order_by(SocialAccountSync.id.desc()).paginate(
            page=page_no, per_page=50, error_out=False)
    elif view == 'notifications':
        page = SocialNotification.query.order_by(SocialNotification.id.desc()).paginate(
            page=page_no, per_page=50, error_out=False)
    else:
        view = 'activity'
        q = SocialAuditLog.query
        if request.args.get('failed'):
            q = q.filter(SocialAuditLog.success.is_(False))
        page = q.order_by(SocialAuditLog.id.desc()).paginate(page=page_no, per_page=50, error_out=False)
    return render_template('social_media/logs.html', view=view, page=page)
