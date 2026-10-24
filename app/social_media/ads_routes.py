"""Facebook Ads (Meta Marketing API) pages. Separate from organic posting.

Server-side safeguards (the page's dialogs are only a convenience):
  * create: can_manage_ads + typed confirmation; always created PAUSED.
  * activate: can_approve_ad_spend + the exact budget and currency shown to
    the user echoed back + an acknowledgement that Meta bills separately.
  * budget change: can_manage_ads; any increase also needs
    can_approve_ad_spend, and an increase above the configured percentage
    needs a second acknowledgement.
  * every action is audit-logged with user, campaign and amounts.
"""
from decimal import Decimal, InvalidOperation

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.social_media import bp
from app.social_media import permissions as perm
from app.social_media.models import SocialAccount, SocialAdAccount, SocialAdCampaign, SocialPostDestination
from app.social_media.services import ads as ads_svc
from app.social_media.services import core, stats
from app.social_media.services.http import ApiError, label as err_label, next_step


def _commit(msg=None, level='success'):
    try:
        core.commit_with_retry()
        if msg:
            flash(msg, level)
    except Exception:
        db.session.rollback()
        flash('Could not save - the database is busy. Please try again.', 'danger')


def _api_fail(e, action, target=None):
    db.session.rollback()
    core.audit(action, target, f'[{e.kind}] {e.message}', success=False)
    _commit()
    flash(f'{err_label(e.kind)}: {e.message} {next_step(e.kind)}', 'danger')


def _campaign(campaign_id):
    c = db.session.get(SocialAdCampaign, campaign_id)
    if c is None:
        abort(404)
    return c


def _money(minor, currency):
    v = ads_svc.from_minor(minor, currency)
    return None if v is None else f'{v:,.2f} {currency}'


@bp.route('/ads')
@perm.require('can_view_ads')
def ads_overview():
    preset, start, end, label, _, _ = stats.resolve_range(request.args)
    acc = ads_svc.selected_account()
    cred = ads_svc.credential()
    campaigns, insights, summary = [], {}, None
    if acc:
        campaigns = SocialAdCampaign.query.filter_by(ad_account_id=acc.id).order_by(SocialAdCampaign.name).all()
        for c in campaigns:
            for i in c.insights:
                if i.date_start == start and i.date_stop == end:
                    insights[c.id] = i
        summary = ads_svc.summary(acc, start, end)
    return render_template('social_media/ads/index.html', acc=acc, cred=cred, campaigns=campaigns, insights=insights,
                           summary=summary, preset=preset, start=start, end=end, range_label=label,
                           ad_accounts=SocialAdAccount.query.order_by(SocialAdAccount.name).all(),
                           ads_enabled=core.get_bool('ads_enabled'), can_manage_api=ads_svc.can_manage(cred),
                           money=_money, presets=stats.PRESETS,
                           ads_manager=ads_svc.ADS_MANAGER_URL.format(act=acc.account_id) if acc else None)


@bp.route('/ads/sync', methods=['POST'])
@perm.require('can_view_ads')
def ads_sync():
    preset, start, end, *_ = stats.resolve_range(request.form)
    try:
        accounts = ads_svc.sync_ad_accounts()
        acc = ads_svc.selected_account()
        n = 0
        if acc:
            ads_svc.sync_campaigns(acc)
            n = ads_svc.sync_insights(acc, start, end)
        core.audit('ads_synced', acc.name if acc else None, f'{len(accounts)} ad accounts, {n} insight rows '
                   f'{start}..{end}')
        _commit(f'Synchronised {len(accounts)} ad account(s); {n} campaign insight row(s) for {start} – {end}.')
    except ApiError as e:
        _api_fail(e, 'ads_sync_failed')
    args = {'range': preset} if preset != 'custom' else {'range': 'custom', 'start': start, 'end': end}
    return redirect(url_for('social_media.ads_overview', **args))


@bp.route('/ads/select-account', methods=['POST'])
@perm.require('can_view_ads')
def ads_select_account():
    sel = request.form.get('ad_account_id', type=int)
    if not db.session.get(SocialAdAccount, sel or 0):
        abort(400)
    for acc in SocialAdAccount.query.all():
        acc.is_selected = acc.id == sel
    _commit()
    return redirect(url_for('social_media.ads_overview'))


@bp.route('/ads/campaigns/<int:campaign_id>')
@perm.require('can_view_ads')
def ads_campaign(campaign_id):
    c = _campaign(campaign_id)
    pct = core.get_int('ads_budget_increase_confirm_pct', 20)
    return render_template('social_media/ads/campaign.html', c=c, money=_money, cred=ads_svc.credential(), pct=pct,
                           budget_major=ads_svc.from_minor(c.daily_budget or c.lifetime_budget,
                                                           c.ad_account.currency),
                           ads_manager=ads_svc.ADS_MANAGER_URL.format(act=c.ad_account.account_id))


@bp.route('/ads/campaigns/<int:campaign_id>/sync', methods=['POST'])
@perm.require('can_view_ads')
def ads_campaign_sync(campaign_id):
    c = _campaign(campaign_id)
    try:
        ads_svc.sync_campaigns(c.ad_account)
        ads_svc.sync_campaign_children(c)
        _commit('Campaign, ad sets and ads refreshed from Meta.')
    except ApiError as e:
        _api_fail(e, 'ads_sync_failed', c.name)
    return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))


@bp.route('/ads/campaigns/<int:campaign_id>/status', methods=['POST'])
@perm.require('can_manage_ads')
def ads_campaign_status(campaign_id):
    c = _campaign(campaign_id)
    action = request.form.get('action')
    cur = c.ad_account.currency
    budget = c.daily_budget or c.lifetime_budget
    try:
        if action == 'pause':
            ads_svc.pause(c)
            core.audit('ad_campaign_paused', c.name, f'{c.remote_id}')
            core.notify('ad_status', f'Campaign "{c.name}" paused by {current_user.username}.', link=request.path)
            _commit('Campaign paused.')
        elif action == 'activate':
            if not perm.can('can_approve_ad_spend'):
                abort(403)
            shown = request.form.get('confirm_budget', '')
            if (request.form.get('ack_billing') != '1' or request.form.get('confirm_currency') != cur
                    or shown != str(budget)):
                flash('Activation not confirmed: review the budget and currency and tick the acknowledgement.',
                      'danger')
                return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))
            ads_svc.activate(c, current_user.id)
            core.audit('ad_campaign_activated', c.name, f'{c.remote_id} budget {_money(budget, cur)} '
                       f'({"lifetime" if c.lifetime_budget else "daily"})')
            core.notify('ad_status', f'Campaign "{c.name}" ACTIVATED by {current_user.username} '
                        f'({_money(budget, cur)} {"lifetime" if c.lifetime_budget else "daily"}).', level='warning',
                        link=request.path)
            _commit('Campaign activated. Meta will now deliver ads and bill your ad account.', 'warning')
        else:
            abort(400)
    except ApiError as e:
        _api_fail(e, f'ad_campaign_{action}_failed', c.name)
    return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))


@bp.route('/ads/campaigns/<int:campaign_id>/budget', methods=['POST'])
@perm.require('can_manage_ads')
def ads_campaign_budget(campaign_id):
    c = _campaign(campaign_id)
    cur = c.ad_account.currency
    old_minor = c.daily_budget or c.lifetime_budget
    if not old_minor:
        flash('This campaign uses ad set budgets; change them in Ads Manager.', 'warning')
        return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))
    try:
        amount = Decimal(request.form.get('amount', ''))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash('Enter a positive amount.', 'danger')
        return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))
    new_minor = ads_svc.to_minor(amount, cur)
    if new_minor > old_minor:
        if not perm.can('can_approve_ad_spend'):
            abort(403)
        if request.form.get('ack_increase') != '1':
            flash('Confirm the budget increase.', 'danger')
            return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))
        pct = core.get_int('ads_budget_increase_confirm_pct', 20)
        if new_minor > old_minor * (1 + pct / 100) and request.form.get('ack_large_increase') != '1':
            flash(f'This is an increase of more than {pct}% - tick the second confirmation.', 'danger')
            return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))
    try:
        field, _ = ads_svc.update_budget(c, amount)
        core.audit('ad_budget_changed', c.name, f'{c.remote_id} {field}: {_money(old_minor, cur)} -> '
                   f'{_money(new_minor, cur)}')
        _commit(f'Budget changed from {_money(old_minor, cur)} to {_money(new_minor, cur)}.')
    except ApiError as e:
        _api_fail(e, 'ad_budget_change_failed', c.name)
    return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))


@bp.route('/ads/campaigns/<int:campaign_id>/rename', methods=['POST'])
@perm.require('can_manage_ads')
def ads_campaign_rename(campaign_id):
    c = _campaign(campaign_id)
    name = (request.form.get('name') or '').strip()[:200]
    if not name:
        abort(400)
    try:
        old = c.name
        ads_svc.rename(c, name)
        core.audit('ad_campaign_renamed', name, f'{c.remote_id} was "{old}"')
        _commit('Campaign renamed.')
    except ApiError as e:
        _api_fail(e, 'ad_campaign_rename_failed', c.name)
    return redirect(url_for('social_media.ads_campaign', campaign_id=c.id))


def _promotable_posts():
    D = SocialPostDestination
    return D.query.join(SocialAccount, SocialAccount.id == D.account_id).filter(
        D.platform == 'facebook', D.status == 'published', D.remote_id.isnot(None),
        D.account_id.in_(perm.visible_accounts().with_entities(SocialAccount.id))).order_by(
        D.published_at.desc()).limit(100).all()


@bp.route('/ads/new', methods=['GET', 'POST'])
@perm.require('can_manage_ads')
def ads_wizard():
    acc = ads_svc.selected_account()
    cred = ads_svc.credential()
    if acc is None:
        flash('Synchronise your ad accounts first (Facebook Ads > Refresh from Meta).', 'warning')
        return redirect(url_for('social_media.ads_overview'))
    ctx = dict(acc=acc, cred=cred, objectives=ads_svc.WIZARD_OBJECTIVES, others=ads_svc.OTHER_OBJECTIVES,
               posts=_promotable_posts(), can_manage_api=ads_svc.can_manage(cred), form=request.form,
               ads_manager=ads_svc.ADS_MANAGER_URL.format(act=acc.account_id), review=None, errors=[])
    if request.method == 'GET':
        return render_template('social_media/ads/wizard.html', **ctx)
    spec, errors = ads_svc.build_spec(request.form, acc)
    ctx['spec'] = spec
    if errors:
        ctx['errors'] = errors
        return render_template('social_media/ads/wizard.html', **ctx)
    step = request.form.get('step')
    if step == 'review':
        try:
            ads_svc.validate(acc, spec)
            ctx['review'] = {'ok': True, 'message': 'Meta validated the campaign settings (nothing was created).'}
        except ApiError as e:
            ctx['review'] = {'ok': False, 'message': f'{err_label(e.kind)}: {e.message}'}
        return render_template('social_media/ads/wizard.html', **ctx)
    if step != 'create':
        abort(400)
    if (request.form.get('confirm_text') != 'CREATE' or request.form.get('ack_billing') != '1'
            or request.form.get('confirm_currency') != acc.currency):
        ctx['errors'] = ['Type CREATE, confirm the currency and tick the billing acknowledgement.']
        return render_template('social_media/ads/wizard.html', **ctx)
    try:
        camp = ads_svc.create_paused(acc, spec, current_user.id)
        core.notify('ad_status', f'Campaign "{camp.name}" created PAUSED - needs approval to activate.',
                    level='info', link=url_for('social_media.ads_campaign', campaign_id=camp.id))
        _commit('Campaign created and PAUSED. Nothing will be spent until someone with approval rights activates it.')
        return redirect(url_for('social_media.ads_campaign', campaign_id=camp.id))
    except ApiError as e:
        camp = getattr(e, 'campaign', None)
        _api_fail(e, 'ad_campaign_create_failed', spec['name'])
        if camp is not None:
            return redirect(url_for('social_media.ads_campaign', campaign_id=camp.id))
        ctx['errors'] = [e.message]
        return render_template('social_media/ads/wizard.html', **ctx)

