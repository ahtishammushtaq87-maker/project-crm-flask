"""Tables for the system email (SMTP) settings and password resets.

Both are new and self-contained; existing tables (users, task_settings ...)
are only referenced by foreign key, never altered. The Task Notifications
SMTP settings (task_settings) are separate and keep working as before.

* ``mail_settings``    one row: the SMTP account the CRM sends system email from.
* ``password_resets``  one row per "Forgot password" request. Only a hash of
                       the temporary password is stored. The user's real
                       password is NOT changed by a request, so nobody can lock
                       a user out just by knowing their username.
"""
from datetime import datetime

from app import db


class MailSettings(db.Model):
    __tablename__ = 'mail_settings'

    SECURITY_CHOICES = (
        ('starttls', 'STARTTLS'),
        ('ssl', 'SSL/TLS'),
        ('none', 'None'),
    )

    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=False)
    smtp_host = db.Column(db.String(255))
    smtp_port = db.Column(db.Integer, nullable=False, default=587)
    security = db.Column(db.String(10), nullable=False, default='starttls')
    smtp_username = db.Column(db.String(255))
    # Stored as entered (like the existing Task Notification settings) and
    # never sent back to the browser; only admins can open this page.
    smtp_password = db.Column(db.String(255))
    from_email = db.Column(db.String(255))
    from_name = db.Column(db.String(120))
    reply_to = db.Column(db.String(255))
    timeout_seconds = db.Column(db.Integer, nullable=False, default=20)
    last_test_at = db.Column(db.DateTime)
    last_test_ok = db.Column(db.Boolean)
    last_test_message = db.Column(db.String(500))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("security IN ('starttls', 'ssl', 'none')", name='ck_mail_settings_security'),
        db.CheckConstraint('smtp_port > 0 AND smtp_port < 65536', name='ck_mail_settings_port'),
    )

    @property
    def is_configured(self):
        return bool(self.is_enabled and self.smtp_host and self.from_email)


class PasswordReset(db.Model):
    __tablename__ = 'password_resets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    temp_password_hash = db.Column(db.String(256), nullable=False)
    sent_to = db.Column(db.String(255), nullable=False)
    requested_ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)          # signed in with it
    revoked_at = db.Column(db.DateTime)       # replaced by a newer request, or real password used

    __table_args__ = (
        db.Index('ix_password_resets_user', 'user_id'),
        db.Index('ix_password_resets_created', 'created_at'),
        db.Index('ix_password_resets_ip', 'requested_ip', 'created_at'),
    )

    user = db.relationship('User', foreign_keys=[user_id])


ALL_MODELS = (MailSettings, PasswordReset)
