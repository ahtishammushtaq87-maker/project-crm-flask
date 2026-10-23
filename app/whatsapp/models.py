"""Tables for the WhatsApp module. All new and prefixed ``whatsapp_``;
existing tables (users, customers, tasks, sales) are only referenced by
foreign key, never altered.

Timestamps are naive UTC (datetime.utcnow), like the rest of the CRM, and are
shown in the CRM's timezone (Asia/Karachi) by the templates.
"""
import json
from datetime import datetime, timedelta

from app import db

SERVICE_WINDOW = timedelta(hours=24)


class WhatsAppSettings(db.Model):
    """One row: the connected WhatsApp Business number. Secrets are stored
    through services.security (encrypted when WHATSAPP_ENCRYPTION_KEY is set)
    and never sent back to the browser."""
    __tablename__ = 'whatsapp_settings'

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(64))
    app_secret_enc = db.Column(db.Text)
    access_token_enc = db.Column(db.Text)
    verify_token_enc = db.Column(db.Text)
    phone_number_id = db.Column(db.String(64))
    waba_id = db.Column(db.String(64))
    graph_version = db.Column(db.String(10), nullable=False, default='v23.0')
    default_country_code = db.Column(db.String(4), nullable=False, default='92')

    # Read from Meta by "Test connection"
    display_phone_number = db.Column(db.String(40))
    verified_name = db.Column(db.String(200))
    quality_rating = db.Column(db.String(20))
    messaging_limit = db.Column(db.String(40))
    connection_status = db.Column(db.String(20), nullable=False, default='unknown')  # unknown|connected|error
    connection_message = db.Column(db.String(500))
    last_test_at = db.Column(db.DateTime)
    connection_verified_at = db.Column(db.DateTime)
    webhook_subscribed = db.Column(db.Boolean)
    last_webhook_at = db.Column(db.DateTime)
    last_webhook_ok_at = db.Column(db.DateTime)
    templates_synced_at = db.Column(db.DateTime)

    # Messaging / media / notifications
    auto_mark_read = db.Column(db.Boolean, nullable=False, default=True)
    optout_keywords = db.Column(db.String(255), nullable=False, default='STOP,UNSUBSCRIBE')
    max_upload_mb = db.Column(db.Integer, nullable=False, default=16)
    media_retention_days = db.Column(db.Integer, nullable=False, default=7)
    log_retention_days = db.Column(db.Integer, nullable=False, default=30)
    campaigns_enabled = db.Column(db.Boolean, nullable=False, default=False)
    campaign_rate_per_minute = db.Column(db.Integer, nullable=False, default=60)
    notify_assigned_by_email = db.Column(db.Boolean, nullable=False, default=False)

    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("connection_status IN ('unknown', 'connected', 'error')",
                           name='ck_whatsapp_settings_conn'),
    )

    @property
    def is_connected(self):
        return self.connection_status == 'connected' and bool(self.phone_number_id)


class WhatsAppUserPermission(db.Model):
    """WhatsApp permissions per CRM user. CRM admins always have all of them;
    other users have none until an admin ticks them in Settings > Staff."""
    __tablename__ = 'whatsapp_user_permissions'

    FLAGS = (
        ('can_view', 'View WhatsApp (assigned conversations)'),
        ('can_view_all', 'View all conversations'),
        ('can_reply', 'Reply to conversations'),
        ('can_assign', 'Assign conversations'),
        ('can_manage_contacts', 'Manage contacts'),
        ('can_export', 'Export contacts / reports (CSV)'),
        ('can_manage_templates', 'Manage templates'),
        ('can_manage_campaigns', 'Manage campaigns'),
        ('can_manage_automations', 'Manage automations'),
        ('can_view_reports', 'View reports'),
        ('can_manage_settings', 'Manage WhatsApp settings'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    can_view = db.Column(db.Boolean, nullable=False, default=False)
    can_view_all = db.Column(db.Boolean, nullable=False, default=False)
    can_reply = db.Column(db.Boolean, nullable=False, default=False)
    can_assign = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_contacts = db.Column(db.Boolean, nullable=False, default=False)
    can_export = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_templates = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_campaigns = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_automations = db.Column(db.Boolean, nullable=False, default=False)
    can_view_reports = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_settings = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


class WhatsAppContact(db.Model):
    __tablename__ = 'whatsapp_contacts'

    CONSENT = ('unknown', 'opted_in', 'opted_out')

    id = db.Column(db.Integer, primary_key=True)
    wa_id = db.Column(db.String(20), nullable=False, unique=True)   # E.164 digits, no '+'
    name = db.Column(db.String(150))
    profile_name = db.Column(db.String(150))                         # name the customer set in WhatsApp
    email = db.Column(db.String(120))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    tags = db.Column(db.String(500), nullable=False, default='')     # ",vip,wholesale," for exact LIKE matching
    consent_status = db.Column(db.String(12), nullable=False, default='unknown')
    consent_source = db.Column(db.String(120))
    consent_at = db.Column(db.DateTime)
    opted_out_at = db.Column(db.DateTime)
    last_message_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("consent_status IN ('unknown', 'opted_in', 'opted_out')",
                           name='ck_whatsapp_contacts_consent'),
        db.Index('ix_whatsapp_contacts_customer', 'customer_id'),
        db.Index('ix_whatsapp_contacts_assigned', 'assigned_to_id'),
        db.Index('ix_whatsapp_contacts_consent', 'consent_status'),
        db.Index('ix_whatsapp_contacts_created', 'created_at'),
    )

    customer = db.relationship('Customer', foreign_keys=[customer_id])
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])

    @property
    def display_name(self):
        return self.name or self.profile_name or ('+' + self.wa_id)

    @property
    def tag_list(self):
        return [t for t in (self.tags or '').split(',') if t]

    def set_tags(self, values):
        clean = []
        for v in values:
            v = ''.join(ch for ch in str(v).strip().lower() if ch.isalnum() or ch in '-_ ')[:30].strip()
            if v and v not in clean:
                clean.append(v)
        self.tags = (',' + ','.join(clean) + ',') if clean else ''

    @property
    def is_opted_out(self):
        return self.consent_status == 'opted_out'


class WhatsAppConversation(db.Model):
    """One thread per contact (WhatsApp has no separate threads per number)."""
    __tablename__ = 'whatsapp_conversations'

    STATUSES = ('open', 'pending', 'resolved')

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('whatsapp_contacts.id', ondelete='CASCADE'),
                           nullable=False, unique=True)
    status = db.Column(db.String(10), nullable=False, default='open')
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    is_starred = db.Column(db.Boolean, nullable=False, default=False)
    unread_count = db.Column(db.Integer, nullable=False, default=0)
    last_message_at = db.Column(db.DateTime)
    last_message_preview = db.Column(db.String(200))
    last_message_direction = db.Column(db.String(3))
    last_inbound_at = db.Column(db.DateTime)
    first_response_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("status IN ('open', 'pending', 'resolved')", name='ck_whatsapp_conv_status'),
        db.Index('ix_whatsapp_conv_activity', 'last_message_at'),
        db.Index('ix_whatsapp_conv_assigned', 'assigned_to_id', 'status'),
        db.Index('ix_whatsapp_conv_updated', 'updated_at'),
    )

    contact = db.relationship('WhatsAppContact', backref=db.backref('conversation', uselist=False))
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])

    @property
    def window_open(self):
        return bool(self.last_inbound_at and datetime.utcnow() - self.last_inbound_at < SERVICE_WINDOW)

    @property
    def window_expires_at(self):
        return self.last_inbound_at + SERVICE_WINDOW if self.last_inbound_at else None


class WhatsAppMessage(db.Model):
    __tablename__ = 'whatsapp_messages'

    # Outbound lifecycle: sending -> accepted (Meta took it) -> sent -> delivered -> read,
    # or failed. "unknown" = the API call timed out, so we can't tell whether Meta has it;
    # such messages are never resent automatically. Inbound messages are "received".
    STATUS_RANK = {'sending': 0, 'unknown': 0, 'accepted': 1, 'sent': 2, 'delivered': 3, 'read': 4}

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('whatsapp_conversations.id', ondelete='CASCADE'),
                                nullable=False)
    direction = db.Column(db.String(3), nullable=False)          # in | out
    wamid = db.Column(db.String(128), unique=True)               # Meta message id
    client_ref = db.Column(db.String(36), unique=True)           # our idempotency key for sends
    msg_type = db.Column(db.String(20), nullable=False, default='text')
    body = db.Column(db.Text)
    media_id = db.Column(db.String(64))
    media_mime = db.Column(db.String(100))
    media_filename = db.Column(db.String(255))
    media_size = db.Column(db.Integer)
    media_local_path = db.Column(db.String(255))                 # relative to the module's private media dir
    template_name = db.Column(db.String(512))
    template_language = db.Column(db.String(15))
    template_params = db.Column(db.Text)                         # JSON
    context_wamid = db.Column(db.String(128))                    # the message this one replies to
    extra_json = db.Column(db.Text)                              # interactive / location / reaction details
    status = db.Column(db.String(10), nullable=False, default='sending')
    error_code = db.Column(db.String(20))
    error_title = db.Column(db.String(200))
    error_detail = db.Column(db.String(500))
    sent_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    automation_id = db.Column(db.Integer, db.ForeignKey('whatsapp_automations.id', ondelete='SET NULL'))
    campaign_recipient_id = db.Column(db.Integer, db.ForeignKey('whatsapp_campaign_recipients.id',
                                                                ondelete='SET NULL'))
    retry_of_id = db.Column(db.Integer, db.ForeignKey('whatsapp_messages.id', ondelete='SET NULL'))
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)   # Meta's time for inbound
    status_updated_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("direction IN ('in', 'out')", name='ck_whatsapp_msg_direction'),
        db.Index('ix_whatsapp_msg_conv', 'conversation_id', 'id'),
        db.Index('ix_whatsapp_msg_ts', 'timestamp'),
        db.Index('ix_whatsapp_msg_status', 'direction', 'status'),
        db.Index('ix_whatsapp_msg_status_upd', 'status_updated_at'),
    )

    conversation = db.relationship('WhatsAppConversation', backref=db.backref('messages', lazy='dynamic',
                                                                              passive_deletes=True))
    sent_by = db.relationship('User', foreign_keys=[sent_by_id])

    @property
    def params(self):
        try:
            return json.loads(self.template_params) if self.template_params else []
        except ValueError:
            return []

    @property
    def extra(self):
        try:
            return json.loads(self.extra_json) if self.extra_json else {}
        except ValueError:
            return {}


class WhatsAppStatusEvent(db.Model):
    """Every delivery/read/failed webhook status, deduplicated, so the
    message history can be audited; the message row holds the latest."""
    __tablename__ = 'whatsapp_message_status_events'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('whatsapp_messages.id', ondelete='CASCADE'))
    wamid = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(12), nullable=False)
    status_at = db.Column(db.DateTime, nullable=False)
    error_code = db.Column(db.String(20))
    error_title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('wamid', 'status', 'status_at', name='uq_whatsapp_status_event'),
        db.Index('ix_whatsapp_status_msg', 'message_id'),
    )


class WhatsAppTemplate(db.Model):
    __tablename__ = 'whatsapp_templates'

    id = db.Column(db.Integer, primary_key=True)
    meta_id = db.Column(db.String(64))
    name = db.Column(db.String(512), nullable=False)
    language = db.Column(db.String(15), nullable=False)
    category = db.Column(db.String(20))
    status = db.Column(db.String(20), nullable=False, default='PENDING')
    parameter_format = db.Column(db.String(12), nullable=False, default='POSITIONAL')
    components_json = db.Column(db.Text, nullable=False, default='[]')
    rejected_reason = db.Column(db.String(255))
    synced_at = db.Column(db.DateTime)
    removed_at = db.Column(db.DateTime)    # no longer returned by Meta

    __table_args__ = (
        db.UniqueConstraint('name', 'language', name='uq_whatsapp_template_name_lang'),
        db.Index('ix_whatsapp_templates_status', 'status'),
    )

    @property
    def components(self):
        try:
            return json.loads(self.components_json or '[]')
        except ValueError:
            return []

    @property
    def is_approved(self):
        return self.status == 'APPROVED' and self.removed_at is None


class WhatsAppCampaign(db.Model):
    __tablename__ = 'whatsapp_campaigns'

    STATUSES = ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled', 'failed')

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    template_id = db.Column(db.Integer, db.ForeignKey('whatsapp_templates.id', ondelete='SET NULL'))
    params_json = db.Column(db.Text, nullable=False, default='{}')
    tag_filter = db.Column(db.String(255), nullable=False, default='')
    status = db.Column(db.String(10), nullable=False, default='draft')
    scheduled_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    status_message = db.Column(db.String(500))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("status IN ('draft', 'scheduled', 'running', 'paused', 'completed', "
                           "'cancelled', 'failed')", name='ck_whatsapp_campaign_status'),
        db.Index('ix_whatsapp_campaign_status', 'status', 'scheduled_at'),
    )

    template = db.relationship('WhatsAppTemplate')
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def params(self):
        try:
            return json.loads(self.params_json or '{}')
        except ValueError:
            return {}


class WhatsAppCampaignRecipient(db.Model):
    __tablename__ = 'whatsapp_campaign_recipients'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('whatsapp_campaigns.id', ondelete='CASCADE'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('whatsapp_contacts.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')
    message_id = db.Column(db.Integer, db.ForeignKey('whatsapp_messages.id', ondelete='SET NULL'))
    attempts = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'contact_id', name='uq_whatsapp_campaign_recipient'),
        db.Index('ix_whatsapp_cr_status', 'campaign_id', 'status'),
    )

    contact = db.relationship('WhatsAppContact')
    campaign = db.relationship('WhatsAppCampaign', backref=db.backref('recipients', lazy='dynamic',
                                                                      passive_deletes=True))


class WhatsAppAutomation(db.Model):
    __tablename__ = 'whatsapp_automations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    trigger = db.Column(db.String(30), nullable=False)
    conditions_json = db.Column(db.Text, nullable=False, default='{}')
    action = db.Column(db.String(30), nullable=False)
    action_config_json = db.Column(db.Text, nullable=False, default='{}')
    is_enabled = db.Column(db.Boolean, nullable=False, default=False)
    dry_run = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_run_at = db.Column(db.DateTime)

    __table_args__ = (db.Index('ix_whatsapp_automation_trigger', 'trigger', 'is_enabled'),)

    @property
    def conditions(self):
        try:
            return json.loads(self.conditions_json or '{}')
        except ValueError:
            return {}

    @property
    def config(self):
        try:
            return json.loads(self.action_config_json or '{}')
        except ValueError:
            return {}


class WhatsAppAutomationLog(db.Model):
    __tablename__ = 'whatsapp_automation_logs'

    id = db.Column(db.Integer, primary_key=True)
    automation_id = db.Column(db.Integer, db.ForeignKey('whatsapp_automations.id', ondelete='CASCADE'),
                              nullable=False)
    event_key = db.Column(db.String(120), nullable=False)
    result = db.Column(db.String(10), nullable=False)     # done | dry_run | skipped | error
    detail = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('automation_id', 'event_key', name='uq_whatsapp_automation_event'),
        db.Index('ix_whatsapp_automation_logs_created', 'created_at'),
    )

    automation = db.relationship('WhatsAppAutomation', backref=db.backref('logs', lazy='dynamic',
                                                                          passive_deletes=True))


class WhatsAppWebhookEvent(db.Model):
    """A summary (never the full payload) of each webhook POST, for
    deduplication of Meta's retries and the Diagnostics page."""
    __tablename__ = 'whatsapp_webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    dedupe_key = db.Column(db.String(64), nullable=False, unique=True)   # sha256 of the raw body
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    signature_ok = db.Column(db.Boolean, nullable=False, default=False)
    processed_ok = db.Column(db.Boolean, nullable=False, default=False)
    summary = db.Column(db.String(300))
    error = db.Column(db.String(300))

    __table_args__ = (db.Index('ix_whatsapp_webhook_received', 'received_at'),)


class WhatsAppApiError(db.Model):
    """Sanitized API / webhook errors for Diagnostics and Reports."""
    __tablename__ = 'whatsapp_api_errors'

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(20), nullable=False)      # send | test | webhook | templates | media | campaign
    code = db.Column(db.String(20))
    kind = db.Column(db.String(30))
    message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.Index('ix_whatsapp_api_errors_created', 'created_at'),)


class WhatsAppNote(db.Model):
    __tablename__ = 'whatsapp_internal_notes'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('whatsapp_contacts.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.Index('ix_whatsapp_notes_contact', 'contact_id'),)

    user = db.relationship('User')


class WhatsAppAuditLog(db.Model):
    __tablename__ = 'whatsapp_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    action = db.Column(db.String(60), nullable=False)
    target = db.Column(db.String(120))
    detail = db.Column(db.String(500))
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.Index('ix_whatsapp_audit_created', 'created_at'),)

    user = db.relationship('User')


class WhatsAppState(db.Model):
    """Small key/value store for background-job cursors (e.g. the last
    invoice id the automation scan has seen)."""
    __tablename__ = 'whatsapp_state'

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


# Creation order matters for foreign keys.
ALL_MODELS = (
    WhatsAppSettings, WhatsAppUserPermission, WhatsAppContact, WhatsAppConversation,
    WhatsAppTemplate, WhatsAppCampaign, WhatsAppAutomation, WhatsAppCampaignRecipient,
    WhatsAppMessage, WhatsAppStatusEvent, WhatsAppAutomationLog, WhatsAppWebhookEvent,
    WhatsAppApiError, WhatsAppNote, WhatsAppAuditLog, WhatsAppState,
)
