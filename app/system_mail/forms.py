from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField
from wtforms.widgets import PasswordInput
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional

from app.system_mail.models import MailSettings


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current password', validators=[Optional()])
    new_password = PasswordField('New password', validators=[
        DataRequired(message='Enter a new password.'),
        Length(min=8, max=128, message='Use at least 8 characters.')])
    confirm_password = PasswordField('Confirm new password', validators=[
        DataRequired(message='Re-enter the new password.'),
        EqualTo('new_password', message='The two passwords do not match.')])


class MailSettingsForm(FlaskForm):
    is_enabled = BooleanField('Enable system email')
    smtp_host = StringField('SMTP server', validators=[DataRequired(message='Enter the SMTP server.'), Length(max=255)])
    smtp_port = IntegerField('Port', validators=[DataRequired(message='Enter the port.'),
                                                 NumberRange(min=1, max=65535, message='Enter a valid port (1-65535).')])
    security = SelectField('Security', choices=list(MailSettings.SECURITY_CHOICES))
    smtp_username = StringField('Username', validators=[Optional(), Length(max=255)])
    # Re-shows what was just typed after a Test (the saved password itself is
    # never sent to the browser: the GET handler blanks this field).
    smtp_password = PasswordField('Password', widget=PasswordInput(hide_value=False),
                                  validators=[Optional(), Length(max=255)])
    from_email = StringField('From email', validators=[DataRequired(message='Enter the sender email.'),
                                                       Email(message='Enter a valid email address.'), Length(max=255)])
    from_name = StringField('From name', validators=[Optional(), Length(max=120)])
    reply_to = StringField('Reply-to email', validators=[Optional(), Email(message='Enter a valid email address.'),
                                                         Length(max=255)])
    timeout_seconds = IntegerField('Timeout (seconds)', default=20,
                                   validators=[Optional(), NumberRange(min=5, max=120, message='Use 5-120 seconds.')])
    test_to = StringField('Send test email to', validators=[Optional(), Email(message='Enter a valid email address.'),
                                                            Length(max=255)])
