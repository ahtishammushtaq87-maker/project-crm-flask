"""Meta Marketing API (Facebook / Instagram ads). Official docs:
  https://developers.facebook.com/docs/marketing-apis/

Financial safeguards enforced here (routes add confirmation and permissions):
  * Everything the CRM creates is created PAUSED. Nothing is activated
    except by activate(), which routes only call after an explicit,
    confirmed action by a user with can_approve_ad_spend.
  * Budgets are converted with the ad account's currency offset (Meta
    stores amounts in the currency's minor unit; zero-decimal currencies
    such as JPY or KRW have offset 1).
  * Publishing an organic post never touches this module.

Endpoints used:
  GET  /me/adaccounts
  GET  /act_{id}/campaigns, /{campaign}/adsets, /{campaign}/ads
  GET  /act_{id}/insights?level=campaign
  POST /act_{id}/campaigns  (status=PAUSED; execution_options=["validate_only"] for the review step)
  POST /act_{id}/adsets, /act_{id}/adcreatives (object_story_id of an existing Page post), /act_{id}/ads
  POST /{campaign-id}       (status / budget changes)
"""
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app import db
from app.social_media.models import (SocialAd, SocialAdAccount, SocialAdCampaign, SocialAdInsight, SocialAdSet,
                                     SocialOAuthCredential)
from app.social_media.services import core, meta, security
from app.social_media.services.http import ApiError

# Currencies Meta bills without a minor unit (offset 1). Others use 100.
ZERO_DECIMAL = {'CLP', 'COP', 'CRC', 'HUF', 'ISK', 'IDR', 'JPY', 'KRW', 'PYG', 'TWD', 'VND'}

# Objectives the guided wizard supports end-to-end with a Page-post creative.
WIZARD_OBJECTIVES = {
    'OUTCOME_AWARENESS': {'label': 'Awareness (reach people)', 'optimization_goal': 'REACH'},
    'OUTCOME_ENGAGEMENT': {'label': 'Engagement (post engagement)', 'optimization_goal': 'POST_ENGAGEMENT'},
    'OUTCOME_TRAFFIC': {'label': 'Traffic (link clicks; the post must contain a link)',
                        'optimization_goal': 'LINK_CLICKS'},
}
OTHER_OBJECTIVES = {
    'OUTCOME_LEADS': 'Needs a lead form or pixel/conversion setup',
    'OUTCOME_SALES': 'Needs a pixel or catalog and conversion events',
    'OUTCOME_APP_PROMOTION': 'Needs a registered app',
}
ADS_MANAGER_URL = 'https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act}'


def offset(currency):
    return 1 if (currency or '').upper() in ZERO_DECIMAL else 100


def to_minor(amount, currency):
    return int((Decimal(str(amount)) * offset(currency)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def from_minor(minor, currency):
    if minor is None:
        return None
    return Decimal(int(minor)) / offset(currency)


def credential():
    """The Meta user credential that granted ads_read/ads_management."""
    for cred in SocialOAuthCredential.query.filter_by(provider='meta', token_type='user', status='active').order_by(
            SocialOAuthCredential.updated_at.desc()):
        if {'ads_read', 'ads_management'} & set(cred.scope_list):
            return cred
    return None


def graph(cred=None):
    cred = cred or credential()
    if cred is None:
        raise ApiError('No connected Meta login has ads_read or ads_management. Enable Facebook Ads in API '
                       'Settings and reconnect Facebook.', kind='missing_permission')
    try:
        return meta.graph_for_token(security.decrypt(cred.access_token_enc)), cred
    except security.SecretUnavailable as e:
        raise ApiError(str(e), kind='not_configured')


def can_manage(cred):
    return cred is not None and 'ads_management' in cred.scope_list


def selected_account():
    return SocialAdAccount.query.filter_by(is_selected=True).first() or SocialAdAccount.query.first()


def sync_ad_accounts():
    g, cred = graph()
    rows = g.paged('me/adaccounts', limit_items=200, limit=50,
                   fields='id,account_id,name,currency,account_status,timezone_name')
    seen = []
    for r in rows:
        acc = SocialAdAccount.query.filter_by(remote_id=r['id']).first()
        if acc is None:
            acc = SocialAdAccount(remote_id=r['id'])
            db.session.add(acc)
        acc.name, acc.currency = r.get('name'), r.get('currency')
        acc.timezone_name, acc.account_status = r.get('timezone_name'), r.get('account_status')
        acc.credential_id, acc.synced_at = cred.id, datetime.utcnow()
        seen.append(acc)
    if seen and not any(a.is_selected for a in seen):
        seen[0].is_selected = True
    db.session.flush()
    return seen


def _upsert(model, remote_id, **fields):
    row = model.query.filter_by(remote_id=remote_id).first()
    if row is None:
        row = model(remote_id=remote_id)
        db.session.add(row)
    for k, v in fields.items():
        setattr(row, k, v)
    row.synced_at = datetime.utcnow()
    db.session.flush()
    return row


def _int(v):
    try:
        return int(v) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


def sync_campaigns(ad_account):
    g, _ = graph(ad_account.credential)
    for c in g.paged(f'{ad_account.remote_id}/campaigns', limit_items=500, limit=100,
                     fields='id,name,objective,status,effective_status,daily_budget,lifetime_budget,'
                            'start_time,stop_time'):
        _upsert(SocialAdCampaign, c['id'], ad_account_id=ad_account.id, name=c.get('name'),
                objective=c.get('objective'), status=c.get('status'), effective_status=c.get('effective_status'),
                daily_budget=_int(c.get('daily_budget')), lifetime_budget=_int(c.get('lifetime_budget')),
                start_time=c.get('start_time'), stop_time=c.get('stop_time'))


def sync_campaign_children(campaign):
    g, _ = graph(campaign.ad_account.credential)
    for s in g.paged(f'{campaign.remote_id}/adsets', limit_items=200, limit=100,
                     fields='id,name,status,effective_status,daily_budget,lifetime_budget,optimization_goal,'
                            'billing_event,targeting'):
        adset = _upsert(SocialAdSet, s['id'], campaign_id=campaign.id, name=s.get('name'), status=s.get('status'),
                        effective_status=s.get('effective_status'), daily_budget=_int(s.get('daily_budget')),
                        lifetime_budget=_int(s.get('lifetime_budget')), optimization_goal=s.get('optimization_goal'),
                        billing_event=s.get('billing_event'), targeting=json.dumps(s.get('targeting') or {}))
        for a in g.paged(f'{adset.remote_id}/ads', limit_items=200, limit=100,
                         fields='id,name,status,effective_status,creative{id}'):
            _upsert(SocialAd, a['id'], adset_id=adset.id, name=a.get('name'), status=a.get('status'),
                    effective_status=a.get('effective_status'), creative_id=(a.get('creative') or {}).get('id'))


def sync_insights(ad_account, since, until):
    """Campaign-level insights for the range, stored as returned."""
    g, _ = graph(ad_account.credential)
    rows = g.paged(f'{ad_account.remote_id}/insights', limit_items=1000, limit=100, level='campaign',
                   time_range=json.dumps({'since': since.isoformat(), 'until': until.isoformat()}),
                   fields='campaign_id,campaign_name,spend,impressions,reach,clicks,inline_link_clicks,ctr,cpc,cpm,'
                          'actions,cost_per_action_type')
    for r in rows:
        camp = SocialAdCampaign.query.filter_by(remote_id=r.get('campaign_id')).first()
        if camp is None:
            continue
        ins = SocialAdInsight.query.filter_by(campaign_id=camp.id, date_start=since, date_stop=until).first()
        if ins is None:
            ins = SocialAdInsight(campaign_id=camp.id, date_start=since, date_stop=until)
            db.session.add(ins)
        ins.spend, ins.ctr, ins.cpc, ins.cpm = r.get('spend'), r.get('ctr'), r.get('cpc'), r.get('cpm')
        ins.impressions, ins.reach = _int(r.get('impressions')), _int(r.get('reach'))
        ins.clicks, ins.link_clicks = _int(r.get('clicks')), _int(r.get('inline_link_clicks'))
        ins.results = json.dumps({'actions': r.get('actions') or [],
                                  'cost_per_action_type': r.get('cost_per_action_type') or []})
        ins.captured_at = datetime.utcnow()
    db.session.flush()
    return len(rows)


# ── wizard ────────────────────────────────────────────────────────────
def build_spec(form, ad_account):
    """Validate wizard input. Returns (spec, errors)."""
    errors = []
    spec = {'name': (form.get('name') or '').strip()[:200], 'objective': form.get('objective'),
            'budget_type': form.get('budget_type'), 'post_id': (form.get('post_id') or '').strip(),
            'page_id': (form.get('page_id') or '').strip(),
            'countries': [c.strip().upper() for c in (form.get('countries') or '').split(',') if c.strip()],
            'placements': form.get('placements') or 'automatic'}
    if not spec['name']:
        errors.append('Enter a campaign name.')
    if spec['objective'] not in WIZARD_OBJECTIVES:
        errors.append('Choose a supported objective.')
    try:
        spec['amount'] = Decimal(form.get('budget') or '0')
        if spec['amount'] <= 0:
            raise ValueError
    except Exception:
        errors.append('Enter a positive budget.')
        spec['amount'] = Decimal('0')
    if spec['budget_type'] not in ('daily', 'lifetime'):
        errors.append('Choose a daily or lifetime budget.')
    for key in ('start', 'end'):
        raw = form.get(key) or ''
        spec[key] = None
        if raw:
            try:
                spec[key] = core.local_to_utc(datetime.strptime(raw, '%Y-%m-%dT%H:%M'))
            except ValueError:
                errors.append(f'Invalid {key} date.')
    if spec['budget_type'] == 'lifetime' and not spec['end']:
        errors.append('A lifetime budget needs an end date.')
    if spec['start'] and spec['end'] and spec['end'] <= spec['start']:
        errors.append('The end date must be after the start date.')
    if not spec['countries'] or any(len(c) != 2 or not c.isalpha() for c in spec['countries']):
        errors.append('Enter target countries as 2-letter codes, e.g. PK, AE.')
    try:
        spec['age_min'] = max(18, min(65, int(form.get('age_min') or 18)))
        spec['age_max'] = max(spec['age_min'], min(65, int(form.get('age_max') or 65)))
    except ValueError:
        errors.append('Ages must be numbers.')
    spec['genders'] = [int(g) for g in form.getlist('genders') if g in ('1', '2')] if hasattr(form, 'getlist') else []
    if spec['placements'] not in ('automatic', 'facebook_feed'):
        errors.append('Choose a placement option.')
    if not spec['post_id'] or not spec['page_id']:
        errors.append('Choose a published Facebook Page post to promote.')
    spec['currency'] = ad_account.currency
    spec['minor'] = to_minor(spec['amount'], ad_account.currency) if spec['amount'] > 0 else 0
    return spec, errors


def _campaign_payload(spec, validate_only=False):
    data = {'name': spec['name'], 'objective': spec['objective'], 'status': 'PAUSED',
            'special_ad_categories': [], 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP',
            f'{spec["budget_type"]}_budget': spec['minor']}
    if validate_only:
        data['execution_options'] = ['validate_only']
    return data


def validate(ad_account, spec):
    """Meta's own validation of the campaign (nothing is created)."""
    g, _ = graph(ad_account.credential)
    return g.call('POST', f'{ad_account.remote_id}/campaigns', data=_campaign_payload(spec, True), is_write=False)


def create_paused(ad_account, spec, user_id):
    """Campaign -> ad set -> creative -> ad, all PAUSED. Returns the local
    campaign; on a later failure the partial (paused) objects remain and the
    error says which step failed."""
    g, cred = graph(ad_account.credential)
    if not can_manage(cred):
        raise ApiError('The connected Meta login does not have ads_management.', kind='missing_permission')
    c = g.call('POST', f'{ad_account.remote_id}/campaigns', data=_campaign_payload(spec))
    camp = _upsert(SocialAdCampaign, c['id'], ad_account_id=ad_account.id, name=spec['name'],
                   objective=spec['objective'], status='PAUSED', effective_status='PAUSED', created_via_crm=True,
                   created_by=user_id, **{f'{spec["budget_type"]}_budget': spec['minor']})
    core.audit('ad_campaign_created', spec['name'], f'{ad_account.remote_id} {c["id"]} PAUSED '
               f'{spec["budget_type"]} budget {spec["amount"]} {ad_account.currency}', user_id=user_id)
    core.commit_with_retry()
    step = 'ad set'
    try:
        targeting = {'geo_locations': {'countries': spec['countries']}, 'age_min': spec['age_min'],
                     'age_max': spec['age_max'], 'targeting_automation': {'advantage_audience': 0}}
        if spec['genders']:
            targeting['genders'] = spec['genders']
        if spec['placements'] == 'facebook_feed':
            targeting.update(publisher_platforms=['facebook'], facebook_positions=['feed'])
        adset_data = {'name': spec['name'] + ' - Ad set', 'campaign_id': c['id'], 'status': 'PAUSED',
                      'billing_event': 'IMPRESSIONS',
                      'optimization_goal': WIZARD_OBJECTIVES[spec['objective']]['optimization_goal'],
                      'targeting': targeting, 'promoted_object': {'page_id': spec['page_id']}}
        if spec['start']:
            adset_data['start_time'] = spec['start'].strftime('%Y-%m-%dT%H:%M:%S+0000')
        if spec['end']:
            adset_data['end_time'] = spec['end'].strftime('%Y-%m-%dT%H:%M:%S+0000')
        s = g.call('POST', f'{ad_account.remote_id}/adsets', data=adset_data)
        adset = _upsert(SocialAdSet, s['id'], campaign_id=camp.id, name=adset_data['name'], status='PAUSED',
                        optimization_goal=adset_data['optimization_goal'], billing_event='IMPRESSIONS',
                        targeting=json.dumps(targeting))
        step = 'creative'
        story = spec['post_id'] if '_' in spec['post_id'] else f'{spec["page_id"]}_{spec["post_id"]}'
        cr = g.call('POST', f'{ad_account.remote_id}/adcreatives',
                    data={'name': spec['name'] + ' - Creative', 'object_story_id': story})
        step = 'ad'
        a = g.call('POST', f'{ad_account.remote_id}/ads', data={
            'name': spec['name'] + ' - Ad', 'adset_id': s['id'], 'status': 'PAUSED',
            'creative': {'creative_id': cr['id']}})
        _upsert(SocialAd, a['id'], adset_id=adset.id, name=spec['name'] + ' - Ad', status='PAUSED',
                creative_id=cr['id'])
    except ApiError as e:
        e.message = (f'The campaign was created (paused) but creating the {step} failed: {e.message} '
                     f'Finish it in Ads Manager or delete it there.')
        e.campaign = camp
        raise
    return camp


def activate(campaign, user_id):
    """Set the campaign and its CRM-known ad sets/ads ACTIVE. Callers must
    have obtained explicit confirmation and can_approve_ad_spend."""
    g, _ = graph(campaign.ad_account.credential)
    for adset in campaign.adsets:
        for ad in adset.ads:
            if ad.status == 'PAUSED':
                g.call('POST', ad.remote_id, data={'status': 'ACTIVE'})
                ad.status = 'ACTIVE'
        if adset.status == 'PAUSED':
            g.call('POST', adset.remote_id, data={'status': 'ACTIVE'})
            adset.status = 'ACTIVE'
    g.call('POST', campaign.remote_id, data={'status': 'ACTIVE'})
    campaign.status = 'ACTIVE'


def pause(campaign):
    g, _ = graph(campaign.ad_account.credential)
    g.call('POST', campaign.remote_id, data={'status': 'PAUSED'})
    campaign.status = 'PAUSED'


def update_budget(campaign, amount):
    """amount in major units of the account currency."""
    g, _ = graph(campaign.ad_account.credential)
    field = 'lifetime_budget' if campaign.lifetime_budget else 'daily_budget'
    minor = to_minor(amount, campaign.ad_account.currency)
    g.call('POST', campaign.remote_id, data={field: minor})
    setattr(campaign, field, minor)
    return field, minor


def rename(campaign, name):
    g, _ = graph(campaign.ad_account.credential)
    g.call('POST', campaign.remote_id, data={'name': name})
    campaign.name = name


def summary(ad_account, since, until):
    """Totals from stored insights for exactly this range (None = no data)."""
    rows = SocialAdInsight.query.join(SocialAdCampaign).filter(
        SocialAdCampaign.ad_account_id == ad_account.id, SocialAdInsight.date_start == since,
        SocialAdInsight.date_stop == until).all()
    if not rows:
        return None
    spend = sum((Decimal(r.spend) for r in rows if r.spend), Decimal('0'))
    impressions = sum(r.impressions or 0 for r in rows)
    clicks = sum(r.link_clicks or 0 for r in rows)
    results = {}
    for r in rows:
        for a in r.results_data.get('actions', []):
            results[a.get('action_type')] = results.get(a.get('action_type'), 0) + float(a.get('value') or 0)
    conversions = sum(v for k, v in results.items() if k in ('lead', 'purchase', 'complete_registration') or
                      k.startswith('offsite_conversion') or k.startswith('onsite_conversion.lead'))
    return {'spend': spend, 'impressions': impressions, 'reach': sum(r.reach or 0 for r in rows),
            'link_clicks': clicks, 'conversions': conversions if results else None,
            'ctr': (Decimal(clicks) / impressions * 100) if impressions else None,
            'cpc': (spend / clicks) if clicks else None,
            'cpm': (spend / impressions * 1000) if impressions else None,
            'currency': ad_account.currency, 'campaigns': len(rows)}


def today_local():
    return core.local_now().date() if core.local_now() else date.today()
