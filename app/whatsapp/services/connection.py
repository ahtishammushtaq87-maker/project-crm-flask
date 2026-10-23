"""The "Test connection" check: real calls to Meta with the saved credentials."""
from datetime import datetime

from app.whatsapp.services import core
from app.whatsapp.services.cloud_api import ApiError, KIND_LABELS

RESULT_LABELS = {
    'connected': 'Connected',
    'invalid_token': 'Invalid token',
    'missing_permissions': 'Missing permissions',
    'invalid_id': 'Invalid Phone Number ID',
    'api_version': 'API version issue',
    'network': 'Network error',
    'not_configured': 'Not configured',
    'unknown': 'Unknown API error',
}

HINTS = {
    'invalid_token': 'Generate a new permanent token for the System User in Meta Business Settings and paste it here.',
    'missing_permissions': 'The System User needs whatsapp_business_messaging and whatsapp_business_management, '
                           'and must be assigned to the WhatsApp Business Account and the app.',
    'invalid_id': 'Copy the Phone Number ID and WhatsApp Business Account ID from WhatsApp Manager > '
                  'API Setup (they are numbers, not the phone number itself).',
    'api_version': 'Use a supported Graph API version such as v23.0.',
    'network': 'The server could not reach graph.facebook.com. Check internet access, DNS and firewall.',
}


def test(settings):
    """Calls GET /{phone-number-id}, GET /{waba-id} and GET /{waba-id}/subscribed_apps.
    Updates the settings row (caller commits). Returns a result dict."""
    now = datetime.utcnow()
    settings.last_test_at = now
    result = {'ok': False, 'status': 'unknown', 'label': '', 'detail': '', 'hint': '', 'checks': []}
    try:
        client = core.api(settings)
        number = client.get_phone_number()
        result['checks'].append(('Phone number', True, f"{number.get('display_phone_number', '')} — "
                                                       f"{number.get('verified_name', '')}"))
        settings.display_phone_number = (number.get('display_phone_number') or '')[:40] or None
        settings.verified_name = (number.get('verified_name') or '')[:200] or None
        settings.quality_rating = (number.get('quality_rating') or '')[:20] or None
        settings.messaging_limit = (number.get('messaging_limit_tier') or '')[:40] or None
        if settings.waba_id:
            waba = client.get_waba()
            result['checks'].append(('Business account', True, waba.get('name') or waba.get('id')))
            apps = client.subscribed_apps()
            settings.webhook_subscribed = bool(apps)
            result['checks'].append(('App subscribed to webhooks', bool(apps),
                                     ', '.join((a.get('whatsapp_business_api_data') or {}).get('name', '')
                                               or a.get('name', 'app') for a in apps) or 'Not subscribed'))
        else:
            result['checks'].append(('Business account', False, 'WABA ID not set - templates and campaigns '
                                                                'need it'))
    except ApiError as e:
        settings.connection_status = 'error'
        status = e.kind if e.kind in RESULT_LABELS else 'unknown'
        settings.connection_message = f'{RESULT_LABELS[status]}: {e.message}'[:500]
        core.record_error('test', e)
        result.update(status=status, label=RESULT_LABELS[status], detail=e.message,
                      hint=HINTS.get(status, KIND_LABELS.get(e.kind, '')))
        return result
    settings.connection_status = 'connected'
    settings.connection_verified_at = now
    settings.connection_message = 'Connected'
    result.update(ok=True, status='connected', label='Connected')
    return result
