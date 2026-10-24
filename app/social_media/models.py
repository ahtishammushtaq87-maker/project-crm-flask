"""Tables for the Social Media module. All new and prefixed ``social_``;
existing tables (users) are only referenced by foreign key, never altered.

Timestamps are naive UTC (datetime.utcnow), like the rest of the CRM, and are
shown in the module's configured timezone by the templates.

Credentials live only in social_oauth_credentials (encrypted, see
services/security.py). Posts, destinations and accounts reference them by id
and never hold a token themselves.
"""
import json
from datetime import datetime

from app import db

PLATFORMS = ('facebook', 'instagram', 'linkedin')
PLATFORM_LABELS = {'facebook': 'Facebook', 'instagram': 'Instagram', 'linkedin': 'LinkedIn'}


def _json_load(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


class SocialSetting(db.Model):
    """Key/value settings. Secret values are stored encrypted (``is_secret``)
    and never rendered back into a page. Keys starting with ``state.`` hold
    scheduler/health state, not configuration."""
    __tablename__ = 'social_settings'

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)
    is_secret = db.Column(db.Boolean, nullable=False, default=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


PERMISSION_FLAGS = (
    ('can_view', 'View the social media dashboard'),
    ('can_view_accounts', 'View connected accounts'),
    ('can_manage_accounts', 'Connect / disconnect accounts'),
    ('can_create_posts', 'Create posts and drafts'),
    ('can_edit_posts', 'Edit posts'),
    ('can_publish', 'Publish posts'),
    ('can_schedule', 'Schedule posts'),
    ('can_delete_posts', 'Delete or cancel posts'),
    ('can_view_analytics', 'View analytics'),
    ('can_view_ads', 'View advertising reports'),
    ('can_manage_ads', 'Create or modify ad campaigns (always paused)'),
    ('can_approve_ad_spend', 'Approve ad spend (activate / raise budgets)'),
    ('can_manage_settings', 'Manage API settings and permissions'),
    ('can_view_logs', 'View activity logs'),
)


class _PermissionFlags:
    can_view = db.Column(db.Boolean, nullable=False, default=False)
    can_view_accounts = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_accounts = db.Column(db.Boolean, nullable=False, default=False)
    can_create_posts = db.Column(db.Boolean, nullable=False, default=False)
    can_edit_posts = db.Column(db.Boolean, nullable=False, default=False)
    can_publish = db.Column(db.Boolean, nullable=False, default=False)
    can_schedule = db.Column(db.Boolean, nullable=False, default=False)
    can_delete_posts = db.Column(db.Boolean, nullable=False, default=False)
    can_view_analytics = db.Column(db.Boolean, nullable=False, default=False)
    can_view_ads = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_ads = db.Column(db.Boolean, nullable=False, default=False)
    can_approve_ad_spend = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_settings = db.Column(db.Boolean, nullable=False, default=False)
    can_view_logs = db.Column(db.Boolean, nullable=False, default=False)


class SocialRolePermission(_PermissionFlags, db.Model):
    """Permissions granted to every CRM user with this role (users.role)."""
    __tablename__ = 'social_role_permissions'

    role = db.Column(db.String(20), primary_key=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SocialUserPermission(_PermissionFlags, db.Model):
    """Extra permissions for one CRM user (added to the role's grants)."""
    __tablename__ = 'social_user_permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SocialOAuthCredential(db.Model):
    """One OAuth token: a Meta user token, a Facebook Page token, or a
    LinkedIn member token. Encrypted at rest; never sent to the browser."""
    __tablename__ = 'social_oauth_credentials'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False)          # meta | linkedin
    token_type = db.Column(db.String(20), nullable=False)        # user | page | member
    external_user_id = db.Column(db.String(120))
    external_user_name = db.Column(db.String(200))
    access_token_enc = db.Column(db.Text, nullable=False)
    refresh_token_enc = db.Column(db.Text)
    scopes = db.Column(db.Text)                                   # JSON list actually granted
    expires_at = db.Column(db.DateTime)                           # None = provider reports no expiry / unknown
    refresh_expires_at = db.Column(db.DateTime)
    data_access_expires_at = db.Column(db.DateTime)
    expiry_known = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default='active')  # active|expired|revoked|error
    last_error = db.Column(db.String(500))
    parent_id = db.Column(db.Integer, db.ForeignKey('social_oauth_credentials.id', ondelete='SET NULL'))
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_social_cred_provider_ext', 'provider', 'token_type', 'external_user_id'),
    )

    @property
    def scope_list(self):
        return _json_load(self.scopes, [])

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= datetime.utcnow())


class SocialAccount(db.Model):
    """A publishing destination: a Facebook Page, an Instagram professional
    account (linked to a Page), a LinkedIn member or a LinkedIn organization."""
    __tablename__ = 'social_accounts'

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(20), nullable=False)           # facebook | instagram | linkedin
    account_type = db.Column(db.String(20), nullable=False)       # page | business | creator | member | organization
    remote_id = db.Column(db.String(120), nullable=False)         # page id / ig user id / person or org URN
    name = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(200))
    picture_url = db.Column(db.String(1000))
    credential_id = db.Column(db.Integer, db.ForeignKey('social_oauth_credentials.id', ondelete='SET NULL'))
    parent_account_id = db.Column(db.Integer, db.ForeignKey('social_accounts.id', ondelete='SET NULL'))
    status = db.Column(db.String(20), nullable=False, default='connected')  # connected|reauth_required|error|disconnected
    granted_permissions = db.Column(db.Text)                      # JSON list
    last_sync_at = db.Column(db.DateTime)
    last_test_at = db.Column(db.DateTime)
    last_error = db.Column(db.String(500))
    connected_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    credential = db.relationship('SocialOAuthCredential', foreign_keys=[credential_id])
    parent = db.relationship('SocialAccount', remote_side=[id])

    __table_args__ = (
        db.UniqueConstraint('platform', 'remote_id', name='uq_social_accounts_platform_remote'),
        db.CheckConstraint("platform IN ('facebook', 'instagram', 'linkedin')", name='ck_social_accounts_platform'),
    )

    @property
    def permission_list(self):
        return _json_load(self.granted_permissions, [])

    @property
    def is_usable(self):
        return self.status == 'connected' and self.credential_id is not None

    @property
    def label(self):
        return f'{PLATFORM_LABELS.get(self.platform, self.platform)} · {self.name}'


class SocialAccountAccess(db.Model):
    """Optional restriction: if an account has any rows here, only these
    users (and CRM admins) may see it or publish to it."""
    __tablename__ = 'social_account_access'

    account_id = db.Column(db.Integer, db.ForeignKey('social_accounts.id', ondelete='CASCADE'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)


POST_STATUSES = ('draft', 'scheduled', 'publishing', 'published', 'partially_published', 'failed', 'cancelled')


class SocialPost(db.Model):
    """A piece of content and its destinations. ``origin='synced'`` rows were
    imported from a platform (not published by the CRM)."""
    __tablename__ = 'social_posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False, default='')
    hashtags = db.Column(db.String(1000))
    link_url = db.Column(db.String(1000))
    status = db.Column(db.String(30), nullable=False, default='draft')
    origin = db.Column(db.String(10), nullable=False, default='crm')  # crm | synced
    scheduled_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    duplicated_from_id = db.Column(db.Integer, db.ForeignKey('social_posts.id', ondelete='SET NULL'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    media = db.relationship('SocialPostMedia', backref='post', order_by='SocialPostMedia.position',
                            cascade='all, delete-orphan')
    destinations = db.relationship('SocialPostDestination', backref='post', cascade='all, delete-orphan',
                                   order_by='SocialPostDestination.id')
    creator = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.Index('ix_social_posts_status', 'status'),
        db.Index('ix_social_posts_scheduled', 'scheduled_at'),
        db.Index('ix_social_posts_origin', 'origin'),
    )

    def full_text(self, override=None):
        text = (override if override else self.body or '').strip()
        if self.hashtags and not override:
            tags = ' '.join(t if t.startswith('#') else '#' + t for t in self.hashtags.replace(',', ' ').split())
            text = (text + '\n\n' + tags).strip()
        return text

    @property
    def display_title(self):
        if self.title:
            return self.title
        body = (self.body or '').strip().splitlines()
        return (body[0][:80] if body else '') or f'Post #{self.id}'


class SocialPostMedia(db.Model):
    """An uploaded image or video, stored privately under instance/. It is
    only reachable without login through a signed, expiring URL that the
    publisher creates for Instagram (which fetches media from a URL)."""
    __tablename__ = 'social_post_media'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('social_posts.id', ondelete='CASCADE'), nullable=False)
    kind = db.Column(db.String(10), nullable=False)               # image | video
    stored_name = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(255))
    mime_type = db.Column(db.String(80), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    position = db.Column(db.Integer, nullable=False, default=0)
    public_enabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index('ix_social_media_post', 'post_id'),)


DEST_STATUSES = ('draft', 'scheduled', 'publishing', 'retry_wait', 'published', 'failed', 'needs_review',
                 'cancelled')


class SocialPostDestination(db.Model):
    """One post on one account. This is also the persistent scheduler job:
    the background worker claims a row with an atomic UPDATE (status
    scheduled/retry_wait -> publishing), so one destination is never
    published twice, even with several workers or after a restart."""
    __tablename__ = 'social_post_destinations'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('social_posts.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('social_accounts.id', ondelete='SET NULL'))
    platform = db.Column(db.String(20), nullable=False)
    custom_text = db.Column(db.Text)
    ig_media_type = db.Column(db.String(20))                      # FEED | REELS (Instagram video choice)
    status = db.Column(db.String(20), nullable=False, default='draft')
    scheduled_at = db.Column(db.DateTime)
    next_attempt_at = db.Column(db.DateTime)
    failure_count = db.Column(db.Integer, nullable=False, default=0)
    lock_token = db.Column(db.String(40))
    locked_at = db.Column(db.DateTime)
    remote_id = db.Column(db.String(200))
    remote_container_id = db.Column(db.String(200))               # Instagram media container in progress
    remote_url = db.Column(db.String(1000))
    published_at = db.Column(db.DateTime)
    error_code = db.Column(db.String(40))
    error_kind = db.Column(db.String(40))
    error_message = db.Column(db.String(500))
    # Latest insight snapshot (history in social_post_insights). None = not available.
    impressions = db.Column(db.Integer)
    reach = db.Column(db.Integer)
    engagements = db.Column(db.Integer)
    insights_synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = db.relationship('SocialAccount')
    attempts = db.relationship('SocialPublishAttempt', backref='destination', cascade='all, delete-orphan',
                               order_by='SocialPublishAttempt.id')

    __table_args__ = (
        db.UniqueConstraint('post_id', 'account_id', name='uq_social_dest_post_account'),
        db.UniqueConstraint('account_id', 'remote_id', name='uq_social_dest_account_remote'),
        db.Index('ix_social_dest_due', 'status', 'scheduled_at'),
        db.Index('ix_social_dest_retry', 'status', 'next_attempt_at'),
    )


class SocialPublishAttempt(db.Model):
    """Every publishing attempt and its real outcome."""
    __tablename__ = 'social_publish_attempts'

    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(db.Integer, db.ForeignKey('social_post_destinations.id', ondelete='CASCADE'),
                               nullable=False)
    triggered_by = db.Column(db.String(20), nullable=False)       # scheduler | user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    outcome = db.Column(db.String(20), nullable=False, default='started')  # started|success|retry|failed|unknown|pending
    remote_id = db.Column(db.String(200))
    http_status = db.Column(db.Integer)
    error_code = db.Column(db.String(40))
    error_message = db.Column(db.String(500))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

    __table_args__ = (db.Index('ix_social_attempt_dest', 'destination_id'),)


class SocialPostInsight(db.Model):
    """A metrics snapshot for a published destination. A NULL metric means
    the platform did not provide it (shown as "Not available")."""
    __tablename__ = 'social_post_insights'

    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(db.Integer, db.ForeignKey('social_post_destinations.id', ondelete='CASCADE'),
                               nullable=False)
    captured_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    impressions = db.Column(db.Integer)
    reach = db.Column(db.Integer)
    engagements = db.Column(db.Integer)
    likes = db.Column(db.Integer)
    comments = db.Column(db.Integer)
    shares = db.Column(db.Integer)
    saves = db.Column(db.Integer)
    clicks = db.Column(db.Integer)
    video_views = db.Column(db.Integer)

    __table_args__ = (db.Index('ix_social_insight_dest', 'destination_id', 'captured_at'),)


class SocialAccountSync(db.Model):
    __tablename__ = 'social_account_syncs'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('social_accounts.id', ondelete='CASCADE'), nullable=False)
    kind = db.Column(db.String(20), nullable=False)               # posts | insights | test
    status = db.Column(db.String(20), nullable=False)             # success | partial | error
    items = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.String(500))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

    __table_args__ = (db.Index('ix_social_sync_account', 'account_id', 'started_at'),)


class SocialAdAccount(db.Model):
    __tablename__ = 'social_ad_accounts'

    id = db.Column(db.Integer, primary_key=True)
    credential_id = db.Column(db.Integer, db.ForeignKey('social_oauth_credentials.id', ondelete='SET NULL'))
    remote_id = db.Column(db.String(60), nullable=False, unique=True)   # act_123
    name = db.Column(db.String(200))
    currency = db.Column(db.String(10))
    timezone_name = db.Column(db.String(80))
    account_status = db.Column(db.Integer)
    is_selected = db.Column(db.Boolean, nullable=False, default=False)
    synced_at = db.Column(db.DateTime)

    credential = db.relationship('SocialOAuthCredential')

    @property
    def account_id(self):
        return self.remote_id.replace('act_', '')


class SocialAdCampaign(db.Model):
    __tablename__ = 'social_ad_campaigns'

    id = db.Column(db.Integer, primary_key=True)
    ad_account_id = db.Column(db.Integer, db.ForeignKey('social_ad_accounts.id', ondelete='CASCADE'), nullable=False)
    remote_id = db.Column(db.String(60), nullable=False, unique=True)
    name = db.Column(db.String(400))
    objective = db.Column(db.String(60))
    status = db.Column(db.String(30))
    effective_status = db.Column(db.String(40))
    daily_budget = db.Column(db.BigInteger)                       # minor units, as returned by Meta
    lifetime_budget = db.Column(db.BigInteger)
    start_time = db.Column(db.String(40))
    stop_time = db.Column(db.String(40))
    created_via_crm = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    synced_at = db.Column(db.DateTime)

    ad_account = db.relationship('SocialAdAccount', backref=db.backref('campaigns', cascade='all, delete-orphan'))


class SocialAdSet(db.Model):
    __tablename__ = 'social_ad_sets'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('social_ad_campaigns.id', ondelete='CASCADE'), nullable=False)
    remote_id = db.Column(db.String(60), nullable=False, unique=True)
    name = db.Column(db.String(400))
    status = db.Column(db.String(30))
    effective_status = db.Column(db.String(40))
    daily_budget = db.Column(db.BigInteger)
    lifetime_budget = db.Column(db.BigInteger)
    optimization_goal = db.Column(db.String(60))
    billing_event = db.Column(db.String(40))
    targeting = db.Column(db.Text)
    synced_at = db.Column(db.DateTime)

    campaign = db.relationship('SocialAdCampaign', backref=db.backref('adsets', cascade='all, delete-orphan'))


class SocialAd(db.Model):
    __tablename__ = 'social_ads'

    id = db.Column(db.Integer, primary_key=True)
    adset_id = db.Column(db.Integer, db.ForeignKey('social_ad_sets.id', ondelete='CASCADE'), nullable=False)
    remote_id = db.Column(db.String(60), nullable=False, unique=True)
    name = db.Column(db.String(400))
    status = db.Column(db.String(30))
    effective_status = db.Column(db.String(40))
    creative_id = db.Column(db.String(60))
    synced_at = db.Column(db.DateTime)

    adset = db.relationship('SocialAdSet', backref=db.backref('ads', cascade='all, delete-orphan'))


class SocialAdInsight(db.Model):
    """Campaign insights for a date range, exactly as returned by Meta
    (amounts in the ad account's currency, as decimal strings)."""
    __tablename__ = 'social_ad_insights'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('social_ad_campaigns.id', ondelete='CASCADE'), nullable=False)
    date_start = db.Column(db.Date, nullable=False)
    date_stop = db.Column(db.Date, nullable=False)
    spend = db.Column(db.String(30))
    impressions = db.Column(db.BigInteger)
    reach = db.Column(db.BigInteger)
    clicks = db.Column(db.BigInteger)
    link_clicks = db.Column(db.BigInteger)
    ctr = db.Column(db.String(30))
    cpc = db.Column(db.String(30))
    cpm = db.Column(db.String(30))
    results = db.Column(db.Text)                                  # JSON: actions / cost_per_action_type
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaign = db.relationship('SocialAdCampaign', backref=db.backref('insights', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'date_start', 'date_stop', name='uq_social_ad_insight_range'),
    )

    @property
    def results_data(self):
        return _json_load(self.results, {})


class SocialAuditLog(db.Model):
    __tablename__ = 'social_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    action = db.Column(db.String(60), nullable=False)
    target = db.Column(db.String(200))
    detail = db.Column(db.String(1000))
    success = db.Column(db.Boolean, nullable=False, default=True)
    ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')

    __table_args__ = (db.Index('ix_social_audit_created', 'created_at'),)


class SocialNotification(db.Model):
    __tablename__ = 'social_notifications'

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(40), nullable=False)
    level = db.Column(db.String(10), nullable=False, default='info')   # info | success | warning | danger
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

    __table_args__ = (db.Index('ix_social_notif_created', 'created_at'),)


ALL_MODELS = [
    SocialSetting, SocialRolePermission, SocialUserPermission, SocialOAuthCredential, SocialAccount,
    SocialAccountAccess, SocialPost, SocialPostMedia, SocialPostDestination, SocialPublishAttempt,
    SocialPostInsight, SocialAccountSync, SocialAdAccount, SocialAdCampaign, SocialAdSet, SocialAd,
    SocialAdInsight, SocialAuditLog, SocialNotification,
]
