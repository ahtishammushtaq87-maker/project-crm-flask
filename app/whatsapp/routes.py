"""WhatsApp module pages. JSON endpoints used by the inbox are in api.py,
the Meta webhook in webhook_routes.py."""
import json
import os
import secrets
from datetime import datetime

from flask import (Response, abort, current_app, flash, redirect, render_template, request, send_file, session,
                   url_for)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from app.whatsapp import bp, media_root
from app.whatsapp import permissions as perm
from app.whatsapp.models import (WhatsAppApiError, WhatsAppAuditLog, WhatsAppAutomation, WhatsAppAutomationLog,
                                 WhatsAppCampaign, WhatsAppCampaignRecipient, WhatsAppContact, WhatsAppConversation,
                                 WhatsAppMessage, WhatsAppSettings, WhatsAppTemplate, WhatsAppUserPermission,
                                 WhatsAppWebhookEvent)
from app.whatsapp.services import automations as auto_svc
from app.whatsapp.services import campaigns as camp_svc
from app.whatsapp.services import connection, core, security, stats
from app.whatsapp.services import contacts as contact_svc
from app.whatsapp.services import messaging
from app.whatsapp.services import templates as tpl_svc
from app.whatsapp.services.cloud_api import ApiError

PER_PAGE = 25


@bp.context_processor
def _inject():
    return {'wa_perms': perm.perms_for() if current_user.is_authenticated else {}}


def _users():
    from app.models import User
    return User.query.filter(User.is_active.is_(True)).order_by(User.username).all()


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _commit(ok_msg=None):
    try:
        core.commit_with_retry()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('WhatsApp: database error')
        flash('Could not save. Please try again.', 'danger')
        return False
    if ok_msg:
        flash(ok_msg, 'success')
    return True


# ── Dashboard ─────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
@perm.require('can_view')
def dashboard():
    preset = request.args.get('range', '7d')
    a, b, label = stats.date_range(preset, request.args.get('start'), request.args.get('end'))
    data = stats.dashboard(a, b)
    recent = (perm.visible_conversations().filter(WhatsAppConversation.last_message_at.isnot(None))
              .order_by(WhatsAppConversation.last_message_at.desc()).limit(8).all())
    activity_q = (WhatsAppMessage.query.join(WhatsAppConversation)
                  .filter(WhatsAppMessage.timestamp >= a, WhatsAppMessage.timestamp < b))
    activity = perm.visible_conversations(activity_q).order_by(WhatsAppMessage.timestamp.desc()).limit(10).all()
    errors = WhatsAppApiError.query.order_by(WhatsAppApiError.created_at.desc()).limit(5).all() \
        if perm.can('can_manage_settings') else []
    return render_template('whatsapp/dashboard.html', data=data, recent=recent, activity=activity, errors=errors,
                           settings=core.get_settings(), preset=preset, range_label=label,
                           series=stats.daily_series(a, b), start=request.args.get('start', ''),
                           end=request.args.get('end', ''))


# ── Inbox page (data comes from api.py) ───────────────────────────────────

@bp.route('/inbox')
@login_required
@perm.require('can_view')
def inbox():
    return render_template('whatsapp/inbox.html', users=_users() if perm.can('can_assign') else [],
                           tags=contact_svc.all_tags(), settings=core.get_settings(),
                           open_id=_int(request.args.get('c')))


@bp.route('/media/<int:message_id>')
@login_required
@perm.require('can_view')
def media(message_id):
    """Protected media: checks the conversation permission, then serves the
    cached copy or fetches it from Meta (short-lived URL, needs the token)."""
    msg = db.session.get(WhatsAppMessage, message_id) or abort(404)
    if not perm.can_see_conversation(msg.conversation):
        abort(403)
    root = media_root()
    if msg.media_local_path:
        path = os.path.normpath(os.path.join(root, msg.media_local_path))
        if path.startswith(os.path.normpath(root)) and os.path.isfile(path):
            return _send_media(path, msg)
    if not msg.media_id:
        abort(404)
    try:
        content, mime = core.api().download_media(msg.media_id)
    except ApiError as e:
        core.record_error('media', e, commit=True)
        return Response(e.label, status=502, mimetype='text/plain')
    ext = {v: k for k, v in messaging.EXT_TO_MIME.items()}.get(mime.split(';')[0].strip(), '.bin')
    rel = os.path.join('in', f'{msg.id}{ext}')
    os.makedirs(os.path.join(root, 'in'), exist_ok=True)
    with open(os.path.join(root, rel), 'wb') as fh:
        fh.write(content)
    msg.media_local_path = rel
    msg.media_mime = msg.media_mime or mime
    msg.media_size = len(content)
    core.commit_with_retry()
    return _send_media(os.path.join(root, rel), msg)


def _send_media(path, msg):
    mime = (msg.media_mime or 'application/octet-stream').split(';')[0]
    inline = mime.startswith(('image/', 'video/', 'audio/')) and request.args.get('download') != '1'
    resp = send_file(path, mimetype=mime, as_attachment=not inline,
                     download_name=msg.media_filename or os.path.basename(path), max_age=0)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Content-Security-Policy'] = "default-src 'none'; img-src 'self'; media-src 'self'; sandbox"
    resp.headers['Cache-Control'] = 'private, no-store'
    return resp


# ── Contacts ──────────────────────────────────────────────────────────────

@bp.route('/contacts')
@login_required
@perm.require('can_manage_contacts')
def contacts():
    q, tag, consent = request.args.get('q', ''), request.args.get('tag', ''), request.args.get('consent', '')
    page = max(1, _int(request.args.get('page'), 1))
    query = contact_svc.search(q, tag, consent).order_by(WhatsAppContact.last_message_at.desc().nullslast(),
                                                         WhatsAppContact.created_at.desc())
    pager = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('whatsapp/contacts.html', pager=pager, q=q, tag=tag, consent=consent,
                           tags=contact_svc.all_tags(), users=_users())


@bp.route('/contacts/new', methods=['GET', 'POST'])
@bp.route('/contacts/<int:cid>/edit', methods=['GET', 'POST'])
@login_required
@perm.require('can_manage_contacts')
def contact_form(cid=None):
    from app.models import Customer
    contact = db.session.get(WhatsAppContact, cid) if cid else WhatsAppContact(consent_status='unknown')
    if cid and contact is None:
        abort(404)
    errors = []
    if request.method == 'POST':
        errors = contact_svc.apply_form(contact, request.form, (core.get_settings() or WhatsAppSettings(
            default_country_code='92')).default_country_code or '92', cid is None)
        if not errors:
            if cid is None:
                db.session.add(contact)
            try:
                core.commit_with_retry()
            except IntegrityError:
                db.session.rollback()
                errors = ['A contact with this number already exists.']
            else:
                core.audit('contact.create' if cid is None else 'contact.update', f'contact:{contact.id}',
                           '+' + contact.wa_id, commit=True)
                flash('Contact saved.', 'success')
                return redirect(url_for('whatsapp.contacts', q=contact.wa_id))
    customer = db.session.get(Customer, contact.customer_id) if contact.customer_id else None
    return render_template('whatsapp/contact_form.html', contact=contact, errors=errors, users=_users(),
                           customer=customer, form=request.form if request.method == 'POST' else None)


@bp.route('/contacts/<int:cid>/consent', methods=['POST'])
@login_required
@perm.require('can_manage_contacts')
def contact_consent(cid):
    contact = db.session.get(WhatsAppContact, cid) or abort(404)
    status = request.form.get('status')
    try:
        contact_svc.set_consent(contact, status, request.form.get('source') or 'Manual (CRM)')
    except contact_svc.ContactError as e:
        flash(str(e), 'danger')
        return redirect(request.referrer or url_for('whatsapp.contacts'))
    core.audit('contact.consent', f'contact:{cid}', status)
    _commit('Consent updated.')
    return redirect(request.referrer or url_for('whatsapp.contacts'))


@bp.route('/contacts/<int:cid>/delete', methods=['POST'])
@login_required
@perm.require('can_manage_contacts')
def contact_delete(cid):
    contact = db.session.get(WhatsAppContact, cid) or abort(404)
    if not perm.is_admin():
        abort(403)
    label = '+' + contact.wa_id
    db.session.delete(contact)
    core.audit('contact.delete', f'contact:{cid}', label)
    _commit('Contact and its conversation history deleted.')
    return redirect(url_for('whatsapp.contacts'))


@bp.route('/contacts/<int:cid>/start', methods=['POST'])
@login_required
@perm.require('can_reply')
def contact_start(cid):
    contact = db.session.get(WhatsAppContact, cid) or abort(404)
    conv = contact_svc.get_or_create_conversation(contact)
    if not conv.assigned_to_id and not perm.can('can_view_all'):
        conv.assigned_to_id = current_user.id
    _commit()
    if not perm.can_see_conversation(conv):
        flash('This conversation is assigned to someone else.', 'warning')
        return redirect(url_for('whatsapp.contacts'))
    return redirect(url_for('whatsapp.inbox', c=conv.id))


@bp.route('/contacts/import', methods=['GET', 'POST'])
@login_required
@perm.require('can_manage_contacts')
def contact_import():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or not f.filename.lower().endswith('.csv'):
            flash('Choose a .csv file.', 'warning')
            return redirect(url_for('whatsapp.contact_import'))
        settings = core.get_settings()
        try:
            rows = contact_svc.parse_import(f.read(2 * 1024 * 1024 + 1)[:2 * 1024 * 1024],
                                            settings.default_country_code if settings else '92')
        except contact_svc.ContactError as e:
            flash(str(e), 'danger')
            return redirect(url_for('whatsapp.contact_import'))
        token = secrets.token_hex(16)
        path = os.path.join(media_root(), 'tmp')
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, f'import_{token}.json'), 'w', encoding='utf-8') as fh:
            json.dump({'user': current_user.id, 'rows': rows}, fh)
        session['wa_import'] = token
        return render_template('whatsapp/contact_import.html', rows=rows, token=token,
                               summary={k: sum(1 for r in rows if r['action'] == k) for k in ('create', 'update',
                                                                                             'skip')})
    return render_template('whatsapp/contact_import.html', rows=None, fields=contact_svc.CSV_FIELDS)


@bp.route('/contacts/import/confirm', methods=['POST'])
@login_required
@perm.require('can_manage_contacts')
def contact_import_confirm():
    token = request.form.get('token', '')
    if not token or token != session.get('wa_import') or not token.isalnum():
        flash('This import preview has expired. Upload the file again.', 'warning')
        return redirect(url_for('whatsapp.contact_import'))
    path = os.path.join(media_root(), 'tmp', f'import_{token}.json')
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        flash('This import preview has expired. Upload the file again.', 'warning')
        return redirect(url_for('whatsapp.contact_import'))
    if data.get('user') != current_user.id:
        abort(403)
    created, updated = contact_svc.apply_import(data['rows'], current_user.id)
    core.audit('contact.import', None, f'{created} created, {updated} updated')
    if _commit(f'Import finished: {created} created, {updated} updated.'):
        session.pop('wa_import', None)
        try:
            os.remove(path)
        except OSError:
            pass
    return redirect(url_for('whatsapp.contacts'))


@bp.route('/contacts/export')
@login_required
@perm.require('can_export')
def contact_export():
    if not perm.can('can_manage_contacts'):
        abort(403)
    query = contact_svc.search(request.args.get('q'), request.args.get('tag'), request.args.get('consent'))
    data = contact_svc.export_csv(query.order_by(WhatsAppContact.id))
    core.audit('contact.export', None, f'{query.count()} contacts', commit=True)
    return Response(data, mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=whatsapp_contacts_{datetime.utcnow():%Y%m%d}.csv'})


@bp.route('/contacts/duplicates')
@login_required
@perm.require('can_manage_contacts')
def contact_duplicates():
    return render_template('whatsapp/duplicates.html', groups=contact_svc.find_duplicates())


@bp.route('/contacts/merge', methods=['POST'])
@login_required
@perm.require('can_manage_contacts')
def contact_merge():
    primary = db.session.get(WhatsAppContact, _int(request.form.get('primary_id'), 0))
    other = db.session.get(WhatsAppContact, _int(request.form.get('other_id'), 0))
    if not primary or not other:
        abort(404)
    if request.form.get('confirm') != 'MERGE':
        flash('Type MERGE to confirm.', 'warning')
        return redirect(url_for('whatsapp.contact_duplicates'))
    detail = f'+{other.wa_id} merged into +{primary.wa_id}'
    try:
        contact_svc.merge(primary, other)
    except contact_svc.ContactError as e:
        flash(str(e), 'danger')
        return redirect(url_for('whatsapp.contact_duplicates'))
    core.audit('contact.merge', f'contact:{primary.id}', detail)
    _commit('Contacts merged.')
    return redirect(url_for('whatsapp.contact_duplicates'))


# ── Templates ─────────────────────────────────────────────────────────────

@bp.route('/templates')
@login_required
@perm.require('can_view')
def templates():
    q, status = request.args.get('q', '').strip(), request.args.get('status', '')
    query = WhatsAppTemplate.query.filter(WhatsAppTemplate.removed_at.is_(None))
    if q:
        query = query.filter(WhatsAppTemplate.name.ilike(f'%{q}%'))
    if status:
        query = query.filter(WhatsAppTemplate.status == status.upper())
    items = query.order_by(WhatsAppTemplate.name, WhatsAppTemplate.language).all()
    return render_template('whatsapp/templates.html', items=items, q=q, status=status, settings=core.get_settings(),
                           variables=tpl_svc.variables, component=tpl_svc.component)


@bp.route('/templates/sync', methods=['POST'])
@login_required
@perm.require('can_manage_templates')
def templates_sync():
    try:
        added, updated, removed = tpl_svc.sync_from_meta()
    except (ApiError, tpl_svc.TemplateError) as e:
        db.session.rollback()
        if isinstance(e, ApiError):
            core.record_error('templates', e, commit=True)
        flash(f'Could not sync templates: {getattr(e, "message", e)}', 'danger')
    else:
        core.audit('templates.sync', None, f'{added} new, {updated} updated, {removed} removed', commit=True)
        flash(f'Templates synced from Meta: {added} new, {updated} updated, {removed} no longer on Meta.', 'success')
    return redirect(url_for('whatsapp.templates'))


@bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
@perm.require('can_manage_templates')
def template_new():
    error = None
    if request.method == 'POST':
        try:
            t = tpl_svc.create_on_meta(request.form)
            core.audit('templates.create', f'template:{t.name}', t.language)
            core.commit_with_retry()
        except (ApiError, tpl_svc.TemplateError) as e:
            db.session.rollback()
            error = getattr(e, 'message', None) or str(e)
        else:
            flash(f'Template "{t.name}" submitted to Meta. Status: {t.status}. Meta usually reviews within minutes '
                  f'to 24 hours; it can be used once it is APPROVED.', 'success')
            return redirect(url_for('whatsapp.templates'))
    return render_template('whatsapp/template_form.html', error=error, form=request.form)


# ── Campaigns ─────────────────────────────────────────────────────────────

@bp.route('/campaigns')
@login_required
@perm.require('can_manage_campaigns')
def campaigns():
    status = request.args.get('status', '')
    query = WhatsAppCampaign.query
    if status in WhatsAppCampaign.STATUSES:
        query = query.filter_by(status=status)
    pager = query.order_by(WhatsAppCampaign.created_at.desc()).paginate(
        page=max(1, _int(request.args.get('page'), 1)), per_page=PER_PAGE, error_out=False)
    return render_template('whatsapp/campaigns.html', pager=pager, status=status, counts=camp_svc.counts,
                           settings=core.get_settings())


def _campaign_from_form(c):
    c.name = (request.form.get('name') or '').strip()[:150]
    c.description = (request.form.get('description') or '').strip()[:2000] or None
    c.tag_filter = ','.join(t.strip().lower() for t in (request.form.get('tag_filter') or '').split(',')
                            if t.strip())[:255]
    tid = _int(request.form.get('template_id'))
    c.template_id = tid
    t = db.session.get(WhatsAppTemplate, tid) if tid else None
    c.params_json = json.dumps({f['key']: (request.form.get('var_' + f['key']) or '').strip()[:1024]
                                for f in tpl_svc.variables(t)} if t else {})
    c.updated_at = datetime.utcnow()
    return c.name


@bp.route('/campaigns/new', methods=['GET', 'POST'])
@bp.route('/campaigns/<int:cid>/edit', methods=['GET', 'POST'])
@login_required
@perm.require('can_manage_campaigns')
def campaign_form(cid=None):
    c = db.session.get(WhatsAppCampaign, cid) if cid else WhatsAppCampaign(created_by=current_user.id)
    if cid and (c is None):
        abort(404)
    if cid and c.status != 'draft':
        flash('Only draft campaigns can be edited.', 'warning')
        return redirect(url_for('whatsapp.campaign_detail', cid=cid))
    if request.method == 'POST':
        if not _campaign_from_form(c):
            flash('Give the campaign a name.', 'warning')
        else:
            if cid is None:
                db.session.add(c)
                db.session.flush()
            try:
                n = camp_svc.build_recipients(c)
            except camp_svc.CampaignError as e:
                db.session.rollback()
                flash(str(e), 'danger')
            else:
                core.audit('campaign.save', f'campaign:{c.id}', f'{c.name}: {n} recipients')
                if _commit(f'Draft saved with {n} eligible recipients.'):
                    return redirect(url_for('whatsapp.campaign_detail', cid=c.id))
    approved = (WhatsAppTemplate.query.filter_by(status='APPROVED').filter(WhatsAppTemplate.removed_at.is_(None))
                .order_by(WhatsAppTemplate.name).all())
    tpl_vars = {t.id: tpl_svc.variables(t) for t in approved}
    return render_template('whatsapp/campaign_form.html', c=c, approved=approved, tpl_vars=tpl_vars,
                           tags=contact_svc.all_tags(), eligible=camp_svc.eligible_contacts(c.tag_filter).count())


@bp.route('/campaigns/estimate')
@login_required
@perm.require('can_manage_campaigns')
def campaign_estimate():
    tag_filter = request.args.get('tags', '')
    total = WhatsAppContact.query.count()
    eligible = camp_svc.eligible_contacts(tag_filter).count()
    return {'eligible': eligible, 'excluded': total - eligible}


@bp.route('/campaigns/<int:cid>')
@login_required
@perm.require('can_manage_campaigns')
def campaign_detail(cid):
    c = db.session.get(WhatsAppCampaign, cid) or abort(404)
    status = request.args.get('status', '')
    rq = WhatsAppCampaignRecipient.query.filter_by(campaign_id=cid)
    if status:
        rq = rq.filter_by(status=status)
    pager = rq.order_by(WhatsAppCampaignRecipient.id).paginate(
        page=max(1, _int(request.args.get('page'), 1)), per_page=50, error_out=False)
    preview, preview_error = '', None
    if c.template:
        sample = rq.first()
        values = camp_svc.resolve_values(c, sample.contact) if sample else c.params
        preview = tpl_svc.render_preview(c.template, values)
        try:
            camp_svc.validate_draft(c)
        except camp_svc.CampaignError as e:
            preview_error = str(e)
    audit_rows = (WhatsAppAuditLog.query.filter_by(target=f'campaign:{cid}')
                  .order_by(WhatsAppAuditLog.created_at.desc()).limit(30).all())
    return render_template('whatsapp/campaign_detail.html', c=c, counts=camp_svc.counts(c), pager=pager,
                           status=status, preview=preview, preview_error=preview_error, audit_rows=audit_rows,
                           settings=core.get_settings())


@bp.route('/campaigns/<int:cid>/confirm', methods=['POST'])
@login_required
@perm.require('can_manage_campaigns')
def campaign_confirm(cid):
    c = db.session.get(WhatsAppCampaign, cid) or abort(404)
    expected = str(c.recipients.count())
    if request.form.get('confirm_count') != expected:
        flash(f'Type the number of recipients ({expected}) to confirm sending.', 'warning')
        return redirect(url_for('whatsapp.campaign_detail', cid=cid))
    when = None
    if request.form.get('scheduled_at'):
        try:
            local = datetime.strptime(request.form['scheduled_at'], '%Y-%m-%dT%H:%M').replace(tzinfo=stats.CRM_TZ)
            from zoneinfo import ZoneInfo
            when = local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        except ValueError:
            flash('Invalid schedule date.', 'warning')
            return redirect(url_for('whatsapp.campaign_detail', cid=cid))
    try:
        camp_svc.confirm(c, current_user.id, when)
    except camp_svc.CampaignError as e:
        flash(str(e), 'danger')
        return redirect(url_for('whatsapp.campaign_detail', cid=cid))
    core.audit('campaign.confirm', f'campaign:{cid}',
               f'{expected} recipients, ' + (f'scheduled {when:%Y-%m-%d %H:%M} UTC' if when else 'start now'))
    _commit('Campaign confirmed. Messages are sent in the background at the configured rate.'
            if not when else 'Campaign scheduled.')
    return redirect(url_for('whatsapp.campaign_detail', cid=cid))


@bp.route('/campaigns/<int:cid>/<action>', methods=['POST'])
@login_required
@perm.require('can_manage_campaigns')
def campaign_action(cid, action):
    c = db.session.get(WhatsAppCampaign, cid) or abort(404)
    try:
        if action == 'retry':
            n = camp_svc.retry_failed(c)
            msg = f'{n} failed recipient(s) queued again.'
        elif action == 'delete':
            if c.status not in ('draft', 'cancelled', 'completed', 'failed'):
                raise camp_svc.CampaignError('Cancel the campaign before deleting it.')
            db.session.delete(c)
            msg = 'Campaign deleted.'
        else:
            camp_svc.set_status(c, action)
            msg = f'Campaign {c.status}.'
    except camp_svc.CampaignError as e:
        flash(str(e), 'danger')
        return redirect(url_for('whatsapp.campaign_detail', cid=cid))
    core.audit(f'campaign.{action}'[:60], f'campaign:{cid}', c.name)
    _commit(msg)
    if action == 'delete':
        return redirect(url_for('whatsapp.campaigns'))
    return redirect(url_for('whatsapp.campaign_detail', cid=cid))


@bp.route('/campaigns/<int:cid>/export')
@login_required
@perm.require('can_manage_campaigns')
def campaign_export(cid):
    if not perm.can('can_export'):
        abort(403)
    import csv
    import io
    c = db.session.get(WhatsAppCampaign, cid) or abort(404)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['contact', 'phone', 'status', 'attempts', 'error', 'updated_at_utc'])
    for r in c.recipients.order_by(WhatsAppCampaignRecipient.id).yield_per(500):
        w.writerow([contact_svc._csv_safe(r.contact.display_name if r.contact else ''),
                    '+' + r.contact.wa_id if r.contact else '', r.status, r.attempts,
                    contact_svc._csv_safe(r.error or ''), r.updated_at.strftime('%Y-%m-%d %H:%M:%S')])
    core.audit('campaign.export', f'campaign:{cid}', c.name, commit=True)
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=campaign_{cid}_results.csv'})


# ── Automations ───────────────────────────────────────────────────────────

@bp.route('/automations')
@login_required
@perm.require('can_manage_automations')
def automations():
    items = WhatsAppAutomation.query.order_by(WhatsAppAutomation.created_at.desc()).all()
    logs = (WhatsAppAutomationLog.query.order_by(WhatsAppAutomationLog.created_at.desc()).limit(50).all())
    return render_template('whatsapp/automations.html', items=items, logs=logs, triggers=auto_svc.TRIGGERS,
                           actions=auto_svc.ACTIONS, describe=auto_svc.describe)


@bp.route('/automations/new', methods=['GET', 'POST'])
@bp.route('/automations/<int:aid>/edit', methods=['GET', 'POST'])
@login_required
@perm.require('can_manage_automations')
def automation_form(aid=None):
    a = db.session.get(WhatsAppAutomation, aid) if aid else None
    if aid and a is None:
        abort(404)
    error = None
    if request.method == 'POST':
        try:
            fields = auto_svc.validate(request.form)
        except auto_svc.AutomationError as e:
            error = str(e)
        else:
            if a is None:
                # New automations always start disabled and in test (dry-run) mode.
                a = WhatsAppAutomation(created_by=current_user.id, is_enabled=False, dry_run=True)
                db.session.add(a)
            for k, v in fields.items():
                setattr(a, k, v)
            a.updated_at = datetime.utcnow()
            db.session.flush()
            core.audit('automation.save', f'automation:{a.id}', a.name)
            if _commit('Automation saved.' + (' It is disabled and in test mode until you turn it on.'
                                              if aid is None else '')):
                return redirect(url_for('whatsapp.automations'))
    approved = (WhatsAppTemplate.query.filter_by(status='APPROVED').filter(WhatsAppTemplate.removed_at.is_(None))
                .order_by(WhatsAppTemplate.name).all())
    return render_template('whatsapp/automation_form.html', a=a, error=error, triggers=auto_svc.TRIGGERS,
                           actions=auto_svc.ACTIONS, users=_users(), approved=approved,
                           tpl_vars={t.id: tpl_svc.variables(t) for t in approved},
                           placeholders=auto_svc.PLACEHOLDERS, form=request.form if request.method == 'POST' else None)


@bp.route('/automations/<int:aid>/<action>', methods=['POST'])
@login_required
@perm.require('can_manage_automations')
def automation_action(aid, action):
    a = db.session.get(WhatsAppAutomation, aid) or abort(404)
    if action == 'enable':
        a.is_enabled = True
    elif action == 'disable':
        a.is_enabled = False
    elif action == 'live':
        if request.form.get('confirm') != '1':
            flash('Confirm that this automation may act for real.', 'warning')
            return redirect(url_for('whatsapp.automations'))
        a.dry_run = False
    elif action == 'test_mode':
        a.dry_run = True
    elif action == 'delete':
        db.session.delete(a)
    else:
        abort(404)
    core.audit(f'automation.{action}', f'automation:{aid}', a.name)
    _commit('Automation updated.' if action != 'delete' else 'Automation deleted.')
    return redirect(url_for('whatsapp.automations'))


# ── Reports ───────────────────────────────────────────────────────────────

@bp.route('/reports')
@login_required
@perm.require('can_view_reports')
def reports():
    preset = request.args.get('range', '30d')
    a, b, label = stats.date_range(preset, request.args.get('start'), request.args.get('end'))
    user_id = _int(request.args.get('user_id'))
    campaign_id = _int(request.args.get('campaign_id'))
    status = request.args.get('status') if request.args.get('status') in (
        'accepted', 'sent', 'delivered', 'read', 'failed', 'unknown') else None
    data = stats.report(a, b, user_id, campaign_id, status)
    if request.args.get('export') == 'csv':
        if not perm.can('can_export'):
            abort(403)
        import csv
        import io
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['metric', 'value'])
        for k, v in data['messages'].items():
            w.writerow([k, '' if v is None else v])
        w.writerow(['new_contacts', data['growth']])
        w.writerow(['opt_ins', data['opt_ins']])
        w.writerow(['opt_outs', data['opt_outs']])
        w.writerow(['median_first_response_seconds', data['median_response'] or ''])
        for s, n in data['by_status'].items():
            w.writerow([f'conversations_{s}', n])
        for uid, uname, total, active in data['workload']:
            w.writerow([f'workload_{uname}', f'{total} total / {active or 0} active'])
        for t in data['templates']:
            w.writerow([f'template_{t["name"]}', f'sent {t["sent"]}, delivered {t["delivered"]}, read {t["read"]}, '
                                                 f'failed {t["failed"]}'])
        core.audit('reports.export', None, label, commit=True)
        return Response(out.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=whatsapp_report.csv'})
    return render_template('whatsapp/reports.html', data=data, preset=preset, range_label=label, users=_users(),
                           user_id=user_id, campaign_id=campaign_id, status=status,
                           all_campaigns=WhatsAppCampaign.query.order_by(WhatsAppCampaign.created_at.desc()).all(),
                           start=request.args.get('start', ''), end=request.args.get('end', ''))


# ── Settings ──────────────────────────────────────────────────────────────

SECRET_FIELDS = {'app_secret': 'app_secret_enc', 'access_token': 'access_token_enc',
                 'verify_token': 'verify_token_enc'}


def _secret_view(s):
    out = {}
    for name, col in SECRET_FIELDS.items():
        stored = getattr(s, col) if s else None
        try:
            value = security.decrypt(stored) if stored else ''
            out[name] = {'set': bool(stored), 'masked': security.mask(value), 'encrypted': security.is_encrypted(stored),
                         'error': None}
        except security.SecretUnavailable as e:
            out[name] = {'set': True, 'masked': '••••••••', 'encrypted': True, 'error': str(e)}
    return out


@bp.route('/settings')
@login_required
@perm.require('can_manage_settings')
def settings():
    s = core.get_settings()
    tab = request.args.get('tab', 'connection')
    profile, profile_error = None, None
    if tab == 'profile' and s and s.access_token_enc:
        try:
            profile = core.api(s).get_business_profile()
        except ApiError as e:
            profile_error = e.message
    from app.models import User
    staff = User.query.filter(User.is_active.is_(True), User.role != 'admin').order_by(User.username).all()
    perms = {p.user_id: p for p in WhatsAppUserPermission.query.all()}
    enc_status, enc_message = security.encryption_status()
    callback = core.external_url('whatsapp_webhook.receive')
    return render_template(
        'whatsapp/settings.html', s=s or WhatsAppSettings(graph_version='v23.0', default_country_code='92'),
        saved=s is not None, tab=tab, secrets=_secret_view(s), callback_url=callback,
        callback_https=callback.startswith('https://'), enc_status=enc_status, enc_message=enc_message,
        profile=profile, profile_error=profile_error, staff=staff, perms=perms,
        flags=WhatsAppUserPermission.FLAGS,
        webhook_events=WhatsAppWebhookEvent.query.order_by(WhatsAppWebhookEvent.received_at.desc()).limit(20).all(),
        api_errors=WhatsAppApiError.query.order_by(WhatsAppApiError.created_at.desc()).limit(30).all(),
        audit_rows=WhatsAppAuditLog.query.order_by(WhatsAppAuditLog.created_at.desc()).limit(40).all(),
        test_result=session.pop('wa_test_result', None))


@bp.route('/settings/connection', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_connection():
    import re
    s = core.get_settings(create=True)
    f = request.form
    errors = []
    for field, label in (('phone_number_id', 'Phone Number ID'), ('waba_id', 'WhatsApp Business Account ID'),
                         ('app_id', 'Meta App ID')):
        v = (f.get(field) or '').strip()
        if v and not v.isdigit():
            errors.append(f'{label} must contain digits only.')
        setattr(s, field, v[:64] or None)
    gv = (f.get('graph_version') or 'v23.0').strip()
    if not re.match(r'^v\d{1,2}\.\d$', gv):
        errors.append('Graph API version looks like v23.0.')
    s.graph_version = gv[:10]
    cc = ''.join(ch for ch in (f.get('default_country_code') or '') if ch.isdigit())[:4]
    s.default_country_code = cc or '92'
    changed = []
    for name, col in SECRET_FIELDS.items():
        value = (f.get(name) or '').strip()
        if value:                       # blank = keep the saved value
            if len(value) > 2000 or any(ch.isspace() for ch in value):
                errors.append(f'{name.replace("_", " ").title()} is not valid.')
                continue
            setattr(s, col, security.encrypt(value))
            changed.append(name)
    if errors:
        db.session.rollback()
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('whatsapp.settings', tab='connection'))
    if changed or 'phone_number_id' in f:
        s.connection_status = 'unknown'    # new credentials must be tested again
    s.updated_by, s.updated_at = current_user.id, datetime.utcnow()
    core.audit('settings.connection', None, 'Changed: ' + (', '.join(changed) if changed else 'IDs/version only'))
    _commit('Connection settings saved. Run "Test connection" to verify them.')
    return redirect(url_for('whatsapp.settings', tab='connection'))


@bp.route('/settings/generate-verify-token', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_generate_verify_token():
    s = core.get_settings(create=True)
    token = secrets.token_urlsafe(24)
    s.verify_token_enc = security.encrypt(token)
    core.audit('settings.verify_token', None, 'Generated a new verify token')
    if _commit():
        # Shown once so it can be pasted into Meta; afterwards only masked.
        flash(f'New verify token: {token} — paste it into the Meta App dashboard now; it will be masked after '
              f'you leave this page.', 'success')
    return redirect(url_for('whatsapp.settings', tab='webhook'))


@bp.route('/settings/clear', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_clear():
    if not perm.is_admin():
        abort(403)
    if request.form.get('confirm') != 'CLEAR':
        flash('Type CLEAR to confirm.', 'warning')
        return redirect(url_for('whatsapp.settings', tab='connection'))
    s = core.get_settings()
    if s:
        s.app_secret_enc = s.access_token_enc = s.verify_token_enc = None
        s.connection_status, s.connection_message = 'unknown', 'Credentials cleared'
        s.campaigns_enabled = False
    core.audit('settings.clear', None, 'All WhatsApp credentials cleared')
    _commit('Credentials cleared. Sending and webhooks stop until new credentials are saved.')
    return redirect(url_for('whatsapp.settings', tab='connection'))


@bp.route('/settings/test', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_test():
    s = core.get_settings()
    if s is None:
        flash('Save the connection settings first.', 'warning')
        return redirect(url_for('whatsapp.settings'))
    result = connection.test(s)
    core.audit('settings.test', None, result['label'])
    _commit()
    session['wa_test_result'] = result
    return redirect(url_for('whatsapp.settings', tab=request.form.get('tab') or 'connection'))


@bp.route('/settings/subscribe', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_subscribe():
    s = core.get_settings()
    try:
        core.api(s).subscribe_app()
    except ApiError as e:
        core.record_error('test', e)
        flash(f'Could not subscribe the app: {e.message}', 'danger')
    else:
        s.webhook_subscribed = True
        core.audit('settings.subscribe', None, 'Subscribed app to WABA webhooks')
        flash('App subscribed to this WhatsApp Business Account’s webhooks.', 'success')
    _commit()
    return redirect(url_for('whatsapp.settings', tab='webhook'))


@bp.route('/settings/options', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_options():
    s = core.get_settings(create=True)
    f = request.form
    tab = f.get('tab', 'messaging')
    if tab == 'messaging':
        s.auto_mark_read = f.get('auto_mark_read') == '1'
        kws = [k.strip().upper()[:20] for k in (f.get('optout_keywords') or '').split(',') if k.strip()]
        s.optout_keywords = ','.join(kws)[:255] or 'STOP'
        want = f.get('campaigns_enabled') == '1'
        if want and not s.is_connected:
            flash('Campaign sending can be enabled after a successful connection test.', 'warning')
            want = False
        s.campaigns_enabled = want
        s.campaign_rate_per_minute = max(1, min(1000, _int(f.get('campaign_rate_per_minute'), 60)))
    elif tab == 'media':
        s.max_upload_mb = max(1, min(16, _int(f.get('max_upload_mb'), 16)))
        s.media_retention_days = max(1, min(365, _int(f.get('media_retention_days'), 7)))
        s.log_retention_days = max(7, min(365, _int(f.get('log_retention_days'), 30)))
    elif tab == 'notifications':
        s.notify_assigned_by_email = f.get('notify_assigned_by_email') == '1'
    s.updated_by, s.updated_at = current_user.id, datetime.utcnow()
    core.audit(f'settings.{tab}'[:60], None, 'Options saved')
    _commit('Settings saved.')
    return redirect(url_for('whatsapp.settings', tab=tab))


@bp.route('/settings/profile', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_profile():
    f = request.form
    fields = {'about': (f.get('about') or '').strip()[:139], 'address': (f.get('address') or '').strip()[:256],
              'description': (f.get('description') or '').strip()[:512], 'email': (f.get('email') or '').strip()[:128],
              'websites': [w.strip() for w in (f.get('websites') or '').split('\n') if w.strip()][:2]}
    if any(not w.startswith(('http://', 'https://')) for w in fields['websites']):
        flash('Websites must start with http:// or https://', 'warning')
        return redirect(url_for('whatsapp.settings', tab='profile'))
    try:
        core.api().update_business_profile({k: v for k, v in fields.items() if v})
    except ApiError as e:
        core.record_error('test', e, commit=True)
        flash(f'Meta rejected the update: {e.message}', 'danger')
    else:
        core.audit('settings.profile', None, 'Business profile updated', commit=True)
        flash('Business profile updated on WhatsApp.', 'success')
    return redirect(url_for('whatsapp.settings', tab='profile'))


@bp.route('/settings/permissions', methods=['POST'])
@login_required
@perm.require('can_manage_settings')
def settings_permissions():
    if not perm.is_admin():
        abort(403)    # only CRM admins hand out WhatsApp access
    from app.models import User
    changes = []
    for user in User.query.filter(User.role != 'admin').all():
        row = WhatsAppUserPermission.query.filter_by(user_id=user.id).first()
        new = {flag: request.form.get(f'p_{user.id}_{flag}') == '1' for flag in perm.FLAG_NAMES}
        if row is None and not any(new.values()):
            continue
        if row is None:
            row = WhatsAppUserPermission(user_id=user.id)
            db.session.add(row)
        diff = [k for k, v in new.items() if bool(getattr(row, k)) != v]
        for k, v in new.items():
            setattr(row, k, v)
        if diff:
            row.updated_at = datetime.utcnow()
            changes.append(f'{user.username}: ' + ', '.join(f'{k}={"on" if new[k] else "off"}' for k in diff))
    for c in changes:
        core.audit('permissions.change', None, c)
    _commit(f'Permissions saved ({len(changes)} user(s) changed).')
    return redirect(url_for('whatsapp.settings', tab='staff'))


# ── CRM customer / invoice integration ────────────────────────────────────

@bp.route('/customer/<int:customer_id>')
@login_required
@perm.require('can_view')
def customer(customer_id):
    from app.models import Customer
    cust = db.session.get(Customer, customer_id) or abort(404)
    linked = WhatsAppContact.query.filter_by(customer_id=customer_id).all()
    s = core.get_settings()
    suggested_wa = None
    if cust.phone:
        from app.whatsapp.services import phone
        suggested_wa = phone.try_normalize(cust.phone, s.default_country_code if s else '92')
    suggested = contact_svc.find_by_wa_id(suggested_wa) if suggested_wa else None
    history = []
    for c in linked:
        if c.conversation and perm.can_see_conversation(c.conversation):
            history.extend(c.conversation.messages.order_by(WhatsAppMessage.id.desc()).limit(20).all())
    history.sort(key=lambda m: m.timestamp)
    from app.models import Sale
    invoices = (Sale.query.filter_by(customer_id=customer_id).filter(Sale.is_draft.isnot(True))
                .order_by(Sale.date.desc()).limit(10).all())
    return render_template('whatsapp/customer.html', cust=cust, linked=linked, suggested=suggested,
                           suggested_wa=suggested_wa, history=history, invoices=invoices)


@bp.route('/customer/<int:customer_id>/link', methods=['POST'])
@login_required
@perm.require('can_manage_contacts')
def customer_link(customer_id):
    from app.models import Customer
    cust = db.session.get(Customer, customer_id) or abort(404)
    action = request.form.get('action')
    if action == 'unlink':
        c = db.session.get(WhatsAppContact, _int(request.form.get('contact_id'), 0)) or abort(404)
        if c.customer_id == customer_id:
            c.customer_id = None
            core.audit('contact.unlink', f'contact:{c.id}', f'customer:{customer_id}')
            _commit('Contact unlinked from this customer.')
        return redirect(url_for('whatsapp.customer', customer_id=customer_id))
    s = core.get_settings()
    from app.whatsapp.services import phone
    try:
        wa_id = phone.normalize(request.form.get('phone') or cust.phone, s.default_country_code if s else '92')
    except phone.InvalidPhone as e:
        flash(str(e), 'danger')
        return redirect(url_for('whatsapp.customer', customer_id=customer_id))
    c = contact_svc.find_by_wa_id(wa_id)
    if c and c.customer_id and c.customer_id != customer_id:
        flash(f'+{wa_id} is already linked to another customer. Unlink it there first.', 'warning')
        return redirect(url_for('whatsapp.customer', customer_id=customer_id))
    if c is None:
        c = WhatsAppContact(wa_id=wa_id, name=cust.name, email=cust.email)
        db.session.add(c)
    c.customer_id = customer_id
    c.updated_at = datetime.utcnow()
    db.session.flush()
    core.audit('contact.link', f'contact:{c.id}', f'customer:{customer_id}')
    _commit(f'+{wa_id} linked to {cust.name}.')
    return redirect(url_for('whatsapp.customer', customer_id=customer_id))


@bp.route('/invoice/<int:sale_id>/notify', methods=['GET', 'POST'])
@login_required
@perm.require('can_reply')
def invoice_notify(sale_id):
    """Send an invoice notification with an approved template, by hand."""
    from app.models import Sale
    sale = db.session.get(Sale, sale_id) or abort(404)
    if not (perm.is_admin() or getattr(current_user, 'can_view_sales', False)):
        abort(403)
    contacts = WhatsAppContact.query.filter_by(customer_id=sale.customer_id).all() if sale.customer_id else []
    approved = (WhatsAppTemplate.query.filter_by(status='APPROVED').filter(WhatsAppTemplate.removed_at.is_(None))
                .order_by(WhatsAppTemplate.name).all())
    values = auto_svc._vars(contacts[0] if contacts else None, {'sale_id': sale.id})
    if request.method == 'POST':
        contact = db.session.get(WhatsAppContact, _int(request.form.get('contact_id'), 0))
        t = db.session.get(WhatsAppTemplate, _int(request.form.get('template_id'), 0))
        if not contact or contact.customer_id != sale.customer_id or not t:
            flash('Choose a linked WhatsApp contact and a template.', 'warning')
            return redirect(url_for('whatsapp.invoice_notify', sale_id=sale_id))
        conv = contact_svc.get_or_create_conversation(contact)
        if not conv.assigned_to_id:
            conv.assigned_to_id = current_user.id
        core.commit_with_retry()
        vals = {f['key']: request.form.get('var_' + f['key'], '') for f in tpl_svc.variables(t)}
        try:
            msg = messaging.send_template(conv, t, vals, user_id=current_user.id)
        except messaging.SendError as e:
            flash(e.message, 'danger')
            return redirect(url_for('whatsapp.invoice_notify', sale_id=sale_id))
        core.audit('message.invoice', f'conversation:{conv.id}', f'{sale.invoice_number} via {t.name}: {msg.status}',
                   commit=True)
        flash(f'Invoice notification {"sent" if msg.status == "accepted" else msg.status}.',
              'success' if msg.status == 'accepted' else 'warning')
        return redirect(url_for('whatsapp.inbox', c=conv.id))
    return render_template('whatsapp/invoice_notify.html', sale=sale, contacts=contacts, approved=approved,
                           tpl_vars={t.id: tpl_svc.variables(t) for t in approved}, values=values)
