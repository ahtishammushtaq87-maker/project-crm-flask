"""Server-side validation of everything a client can send.

Cell formats and sheet layout ("props") come from the browser as JSON; they
are rebuilt here from a whitelist so nothing unexpected is ever stored. The
browser still escapes everything it renders - this is defence in depth.
"""
import json
import re
from typing import Any, Optional

MAX_ROWS = 50000
MAX_COLS = 260
MAX_CELL_CHARS = 50000
MAX_NAME = 200
MAX_SHEET_NAME = 100
MAX_PROPS_BYTES = 512 * 1024
MAX_LIST_ITEMS = 2000

_COLOR = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
FONTS = ('Arial', 'Calibri', 'Courier New', 'Georgia', 'Roboto', 'Segoe UI', 'Tahoma',
         'Times New Roman', 'Trebuchet MS', 'Verdana')
NUMBER_FORMATS = ('auto', 'number', 'decimal', 'currency', 'percent', 'date', 'time', 'datetime', 'text')
BORDER_STYLES = ('solid', 'dashed', 'dotted', 'double')
SHEET_COLORS_OK = _COLOR


class ValidationError(ValueError):
    """Raised with a message that is safe to show to the user."""


def color(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and _COLOR.match(value) else None


def _int(value: Any, lo: int, hi: int) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None or value == '':
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n and abs(n) < 1e300 else None


def _text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        return None
    return value[:limit]


def clean_name(value: Any, limit: int = MAX_NAME, label: str = 'Name') -> str:
    name = (_text(value, 10000) or '').strip()
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    if not name:
        raise ValidationError(f'{label} is required.')
    if len(name) > limit:
        raise ValidationError(f'{label} must be {limit} characters or fewer.')
    return name


def clean_value(value: Any) -> Optional[str]:
    """A cell's raw input. None/'' clears the cell."""
    if value is None:
        return None
    if isinstance(value, bool):
        value = 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        value = repr(value) if isinstance(value, float) else str(value)
    if not isinstance(value, str):
        raise ValidationError('Invalid cell value.')
    if len(value) > MAX_CELL_CHARS:
        raise ValidationError(f'A cell can hold at most {MAX_CELL_CHARS:,} characters.')
    value = value.replace('\x00', '')
    return value if value != '' else None


def _border(value: Any) -> Optional[dict]:
    if not isinstance(value, dict):
        return None
    w = _int(value.get('w'), 1, 3) or 1
    s = value.get('s') if value.get('s') in BORDER_STYLES else 'solid'
    c = color(value.get('c')) or '#000000'
    return {'w': w, 's': s, 'c': c}


def clean_fmt(fmt: Any) -> Optional[dict]:
    """Whitelisted cell style; None when nothing is set."""
    if not isinstance(fmt, dict):
        return None
    out = {}
    for key in ('b', 'i', 'u', 's'):
        if fmt.get(key) is True:
            out[key] = True
    fs = _int(fmt.get('fs'), 6, 72)
    if fs:
        out['fs'] = fs
    if fmt.get('ff') in FONTS:
        out['ff'] = fmt['ff']
    for key in ('c', 'bg'):
        c = color(fmt.get(key))
        if c:
            out[key] = c
    if fmt.get('ha') in ('left', 'center', 'right'):
        out['ha'] = fmt['ha']
    if fmt.get('va') in ('top', 'middle', 'bottom'):
        out['va'] = fmt['va']
    if fmt.get('wrap') in ('wrap', 'clip', 'overflow'):
        out['wrap'] = fmt['wrap']
    nf = fmt.get('nf')
    if isinstance(nf, dict) and nf.get('t') in NUMBER_FORMATS and nf.get('t') != 'auto':
        clean_nf = {'t': nf['t']}
        d = _int(nf.get('d'), 0, 10)
        if d is not None:
            clean_nf['d'] = d
        cur = _text(nf.get('cur'), 6)
        if cur:
            clean_nf['cur'] = cur
        out['nf'] = clean_nf
    for key in ('bt', 'bb', 'bl', 'br'):
        b = _border(fmt.get(key))
        if b:
            out[key] = b
    return out or None


def _range(obj: Any) -> Optional[dict]:
    if not isinstance(obj, dict):
        return None
    r1, c1 = _int(obj.get('r1'), 0, MAX_ROWS), _int(obj.get('c1'), 0, MAX_COLS)
    r2, c2 = _int(obj.get('r2'), 0, MAX_ROWS), _int(obj.get('c2'), 0, MAX_COLS)
    if None in (r1, c1, r2, c2):
        return None
    return {'r1': min(r1, r2), 'c1': min(c1, c2), 'r2': max(r1, r2), 'c2': max(c1, c2)}


def _size_map(obj: Any, key_max: int, lo: int, hi: int) -> dict:
    out = {}
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:MAX_LIST_ITEMS * 5]:
            ki, vi = _int(k, 0, key_max), _int(v, lo, hi)
            if ki is not None and vi is not None:
                out[str(ki)] = vi
    return out


def _index_list(obj: Any, key_max: int) -> list:
    if not isinstance(obj, list):
        return []
    return sorted({i for i in (_int(x, 0, key_max) for x in obj[:MAX_ROWS]) if i is not None})


_FILTER_OPS = ('contains', 'not_contains', 'eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between',
               'empty', 'not_empty', 'date_before', 'date_after', 'date_eq')
_CF_TYPES = ('gt', 'gte', 'lt', 'lte', 'eq', 'neq', 'between', 'contains', 'not_contains',
             'empty', 'not_empty', 'duplicate')
_DV_TYPES = ('list', 'number', 'text_length', 'text_contains', 'date')


def _filter(obj: Any) -> Optional[dict]:
    rng = _range(obj)
    if not rng:
        return None
    crit = {}
    if isinstance(obj.get('crit'), dict):
        for k, v in list(obj['crit'].items())[:MAX_COLS]:
            col = _int(k, 0, MAX_COLS)
            if col is None or not isinstance(v, dict):
                continue
            entry = {}
            if isinstance(v.get('values'), list):
                entry['values'] = [t for t in (_text(x, 500) for x in v['values'][:MAX_LIST_ITEMS]) if t is not None]
            if v.get('op') in _FILTER_OPS:
                entry['op'] = v['op']
                entry['v1'] = _text(v.get('v1'), 500) or ''
                entry['v2'] = _text(v.get('v2'), 500) or ''
            if entry:
                crit[str(col)] = entry
    rng['crit'] = crit
    return rng


def _style(obj: Any) -> dict:
    obj = obj if isinstance(obj, dict) else {}
    out = {}
    for key in ('bg', 'c'):
        c = color(obj.get(key))
        if c:
            out[key] = c
    if obj.get('b') is True:
        out['b'] = True
    return out


def _cond_formats(obj: Any) -> list:
    out = []
    for item in (obj if isinstance(obj, list) else [])[:200]:
        rng = _range(item)
        if not rng or item.get('type') not in _CF_TYPES:
            continue
        rng.update(type=item['type'], v1=_text(item.get('v1'), 500) or '',
                   v2=_text(item.get('v2'), 500) or '', style=_style(item.get('style')))
        out.append(rng)
    return out


def _validations(obj: Any) -> list:
    out = []
    for item in (obj if isinstance(obj, list) else [])[:200]:
        rng = _range(item)
        if not rng or item.get('type') not in _DV_TYPES:
            continue
        values = item.get('values') if isinstance(item.get('values'), list) else []
        rng.update(
            type=item['type'],
            values=[t for t in (_text(x, 200) for x in values[:500]) if t],
            min=_num(item.get('min')), max=_num(item.get('max')),
            text=_text(item.get('text'), 200) or '',
            strict=item.get('strict') is not False,
            msg=_text(item.get('msg'), 300) or '',
        )
        out.append(rng)
    return out


def _merges(obj: Any) -> list:
    out = []
    for item in (obj if isinstance(obj, list) else [])[:5000]:
        rng = _range(item)
        if rng and (rng['r2'] > rng['r1'] or rng['c2'] > rng['c1']):
            out.append({k: rng[k] for k in ('r1', 'c1', 'r2', 'c2')})
    return out


def clean_props(props: Any) -> dict:
    """Sheet layout that isn't stored per cell."""
    if not isinstance(props, dict):
        props = {}
    out = {
        'cw': _size_map(props.get('cw'), MAX_COLS, 20, 2000),
        'rh': _size_map(props.get('rh'), MAX_ROWS, 12, 1000),
        'hr': _index_list(props.get('hr'), MAX_ROWS),
        'hc': _index_list(props.get('hc'), MAX_COLS),
        'merges': _merges(props.get('merges')),
        'filter': _filter(props.get('filter')),
        'cf': _cond_formats(props.get('cf')),
        'dv': _validations(props.get('dv')),
    }
    if len(json.dumps(out)) > MAX_PROPS_BYTES:
        raise ValidationError('This sheet has too many layout settings to save.')
    return out


def dump(obj: Any) -> Optional[str]:
    return json.dumps(obj, separators=(',', ':')) if obj else None


def load(text: Optional[str], default=None):
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default
