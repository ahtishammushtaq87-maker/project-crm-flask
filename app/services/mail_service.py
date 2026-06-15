import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.models import TaskSettings

def send_task_email(task):
    """Send an email notification for a due task"""
    settings = TaskSettings.query.first()
    if not settings or not settings.is_enabled:
        return False, "Email notifications are disabled."

    if not settings.smtp_server or not settings.smtp_user or not settings.smtp_password:
        return False, "SMTP settings are incomplete."

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = settings.sender_email
        msg['To'] = settings.notification_email
        msg['Subject'] = f"TASK ALERT: {task.title}"

        body = f"""
        TASK ALARM TRIGGERED
        --------------------
        Title: {task.title}
        Priority: {task.priority}
        Description: {task.description or 'No description provided.'}
        Reminder Set For: {task.reminder_at}
        
        Assigned To: {task.assigned_to.username if task.assigned_to else 'Not Assigned'}
        """
        msg.attach(MIMEText(body, 'plain'))

        # Connect and send
        server = smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=15)
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
        server.quit()

        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)
