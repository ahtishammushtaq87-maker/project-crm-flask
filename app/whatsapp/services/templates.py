"""Message templates: sync with Meta, describe their variables, and build
the ``template`` object for a send from user-entered values.

Only templates Meta reports as APPROVED can be sent. Creating a template
submits it to Meta for review; it stays PENDING until Meta decides.
"""
import json
import re
from datetime import datetime

from app import db
from app.whatsapp.models import WhatsAppTemplate
from app.whatsapp.services import core

POSITIONAL_RE = re.compile(r'\{\{\s*(\d+)\s*\}\}')
NAMED_RE = re.compile(r'\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}')
MAX_PARAM_LEN = 1024
NAME_RE = re.compile(r'^[a-z0-9_]{1,512}$')


class TemplateError(ValueError):
    pass


def sync_from_meta(settings=None):
    """Fetch every template from the WABA and upsert. Returns (added, updated, removed)."""
    settings = settings or core.get_settings()
    if not settings or not settings.waba_id:
        raise TemplateError('Add the WhatsApp Business Account ID in Settings first.')
    remote = core.api(settings).list_templates()
    now = datetime.utcnow()
    existing = {(t.name, t.language): t for t in WhatsAppTemplate.query.all()}
    added = updated = 0
    seen = set()
    for r in remote:
        key = (r.get('name'), r.get('language'))
        if not all(key):
            continue
        seen.add(key)
        t = existing.get(key)
        if t is None:
            t = WhatsAppTemplate(name=key[0], language=key[1])
            db.session.add(t)
            added += 1
        else:
            updated += 1
        t.meta_id = r.get('id')
        t.category = r.get('category')
        t.status = (r.get('status') or 'PENDING').upper()
        t.parameter_format = (r.get('parameter_format') or 'POSITIONAL').upper()
        t.components_json = json.dumps(r.get('components') or [])
        reason = r.get('rejected_reason')
        t.rejected_reason = reason if reason and reason != 'NONE' else None
        t.synced_at = now
        t.removed_at = None
    removed = 0
    for key, t in existing.items():
        if key not in seen and t.removed_at is None:
            t.removed_at = now
            removed += 1
    settings.templates_synced_at = now
    core.commit_with_retry()
    return added, updated, removed


def apply_status_webhook(value):
    """message_template_status_update webhook: keep the local status current."""
    name, lang = value.get('message_template_name'), value.get('message_template_language')
    event = (value.get('event') or '').upper()
    if not name or not event:
        return
    q = WhatsAppTemplate.query.filter_by(name=name)
    if lang:
        q = q.filter_by(language=lang)
    for t in q.all():
        t.status = event
        reason = value.get('reason')
        t.rejected_reason = reason if reason and reason != 'NONE' else None
        t.synced_at = datetime.utcnow()


def component(t, ctype):
    for c in t.components:
        if (c.get('type') or '').upper() == ctype:
            return c
    return None


def variables(t):
    """Fields the sender has to fill, in order:
    [{key, label, component, kind ('text'|'media'), example}]"""
    fields = []
    named = t.parameter_format == 'NAMED'
    rx = NAMED_RE if named else POSITIONAL_RE

    header = component(t, 'HEADER')
    if header:
        fmt = (header.get('format') or 'TEXT').upper()
        if fmt == 'TEXT':
            for v in _unique(rx.findall(header.get('text') or '')):
                fields.append({'key': f'header.{v}', 'label': f'Header {{{{{v}}}}}', 'component': 'header',
                               'kind': 'text', 'name': v})
        elif fmt in ('IMAGE', 'VIDEO', 'DOCUMENT'):
            fields.append({'key': 'header.media', 'label': f'Header {fmt.lower()} URL (https)', 'component': 'header',
                           'kind': 'media', 'format': fmt.lower()})
    body = component(t, 'BODY')
    if body:
        for v in _unique(rx.findall(body.get('text') or '')):
            fields.append({'key': f'body.{v}', 'label': f'Body {{{{{v}}}}}', 'component': 'body', 'kind': 'text',
                           'name': v})
    buttons = component(t, 'BUTTONS')
    for idx, b in enumerate((buttons or {}).get('buttons') or []):
        if (b.get('type') or '').upper() == 'URL' and rx.search(b.get('url') or ''):
            fields.append({'key': f'button.{idx}', 'label': f'Button "{b.get("text")}" URL suffix',
                           'component': 'button', 'kind': 'text', 'index': idx})
    return fields


def _unique(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def render_preview(t, values):
    """Plain-text preview with values substituted (for the UI and the stored message body)."""
    rx = NAMED_RE if t.parameter_format == 'NAMED' else POSITIONAL_RE
    parts = []
    for ctype, prefix in (('HEADER', 'header'), ('BODY', 'body'), ('FOOTER', None)):
        c = component(t, ctype)
        if not c or not c.get('text'):
            continue
        text = c['text']
        if prefix:
            text = rx.sub(lambda m: values.get(f'{prefix}.{m.group(1)}') or m.group(0), text)
        parts.append(f'*{text}*' if ctype == 'HEADER' else text)
    return '\n\n'.join(parts)


def build_payload(t, values):
    """Validate values and build the Cloud API ``template`` object."""
    if not t.is_approved:
        raise TemplateError(f'Template "{t.name}" is {t.status.lower()} - only approved templates can be sent.')
    fields = variables(t)
    named = t.parameter_format == 'NAMED'
    clean = {}
    for f in fields:
        v = (values.get(f['key']) or '').strip()
        if not v:
            raise TemplateError(f'Fill in {f["label"]}.')
        if len(v) > MAX_PARAM_LEN:
            raise TemplateError(f'{f["label"]} is too long.')
        if f['kind'] == 'media' and not v.lower().startswith('https://'):
            raise TemplateError('Header media must be a public https:// link.')
        if f['kind'] == 'text' and ('\n' in v or '\t' in v or '    ' in v) and f['component'] == 'body':
            raise TemplateError(f'{f["label"]} cannot contain new lines, tabs or 4+ spaces (Meta rule).')
        clean[f['key']] = v

    def param(f, v):
        p = {'type': 'text', 'text': v}
        if named and f.get('name'):
            p['parameter_name'] = f['name']
        return p

    components = []
    header = [f for f in fields if f['component'] == 'header']
    if header:
        if header[0]['kind'] == 'media':
            fmt = header[0]['format']
            components.append({'type': 'header', 'parameters': [{'type': fmt, fmt: {'link': clean['header.media']}}]})
        else:
            components.append({'type': 'header', 'parameters': [param(f, clean[f['key']]) for f in header]})
    body = [f for f in fields if f['component'] == 'body']
    if body:
        components.append({'type': 'body', 'parameters': [param(f, clean[f['key']]) for f in body]})
    for f in fields:
        if f['component'] == 'button':
            components.append({'type': 'button', 'sub_type': 'url', 'index': str(f['index']),
                               'parameters': [{'type': 'text', 'text': clean[f['key']]}]})
    payload = {'name': t.name, 'language': {'code': t.language}}
    if components:
        payload['components'] = components
    return payload, clean


def create_on_meta(form, settings=None):
    """Submit a new template for Meta review (WhatsApp Manager does the same)."""
    name = (form.get('name') or '').strip().lower()
    if not NAME_RE.match(name):
        raise TemplateError('Name: lowercase letters, numbers and underscores only.')
    language = (form.get('language') or '').strip()
    if not re.match(r'^[a-z]{2,3}(_[A-Z]{2})?$', language):
        raise TemplateError('Language code like en, en_US or ur.')
    category = (form.get('category') or '').upper()
    if category not in ('MARKETING', 'UTILITY'):
        raise TemplateError('Category must be Marketing or Utility.')
    body = (form.get('body') or '').strip()
    if not body or len(body) > 1024:
        raise TemplateError('Body is required (max 1024 characters).')
    nums = [int(n) for n in POSITIONAL_RE.findall(body)]
    if nums and sorted(set(nums)) != list(range(1, max(nums) + 1)):
        raise TemplateError('Body variables must be numbered {{1}}, {{2}}, ... without gaps.')
    examples = [e.strip() for e in (form.get('examples') or '').split('|') if e.strip()]
    if nums and len(examples) != max(nums):
        raise TemplateError(f'Give {max(nums)} example value(s), separated by |, for Meta review.')
    components = []
    header = (form.get('header') or '').strip()
    if header:
        if len(header) > 60 or POSITIONAL_RE.search(header):
            raise TemplateError('Header: plain text up to 60 characters (no variables).')
        components.append({'type': 'HEADER', 'format': 'TEXT', 'text': header})
    b = {'type': 'BODY', 'text': body}
    if nums:
        b['example'] = {'body_text': [examples]}
    components.append(b)
    footer = (form.get('footer') or '').strip()
    if footer:
        if len(footer) > 60:
            raise TemplateError('Footer: up to 60 characters.')
        components.append({'type': 'FOOTER', 'text': footer})
    if category == 'MARKETING' and (form.get('add_stop_button') == '1'):
        components.append({'type': 'BUTTONS', 'buttons': [{'type': 'QUICK_REPLY', 'text': 'Stop promotions'}]})
    payload = {'name': name, 'language': language, 'category': category, 'components': components}
    resp = core.api(settings).create_template(payload)
    t = WhatsAppTemplate.query.filter_by(name=name, language=language).first() or WhatsAppTemplate(
        name=name, language=language)
    t.meta_id = resp.get('id')
    t.status = (resp.get('status') or 'PENDING').upper()
    t.category = resp.get('category') or category
    t.components_json = json.dumps(components)
    t.synced_at = datetime.utcnow()
    t.removed_at = None
    db.session.add(t)
    return t
