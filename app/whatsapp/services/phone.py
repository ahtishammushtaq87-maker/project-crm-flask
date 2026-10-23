"""Phone numbers are stored as WhatsApp IDs: international format, digits
only, no '+' (e.g. 923001234567). One function decides that format so
contacts can't be duplicated by different spellings of the same number."""
import re


class InvalidPhone(ValueError):
    pass


def normalize(raw, default_country_code='92'):
    """'+92 300-1234567', '0092 300 1234567' and '0300 1234567' (with country
    code 92) all become '923001234567'. Raises InvalidPhone."""
    if raw is None:
        raise InvalidPhone('Phone number is required.')
    s = str(raw).strip()
    if not s:
        raise InvalidPhone('Phone number is required.')
    has_plus = s.startswith('+')
    digits = re.sub(r'\D', '', s)
    if not digits:
        raise InvalidPhone('Phone number must contain digits.')
    if not has_plus:
        if digits.startswith('00'):
            digits = digits[2:]
        elif digits.startswith('0'):
            cc = re.sub(r'\D', '', default_country_code or '')
            if not cc:
                raise InvalidPhone('Use international format (e.g. +92 300 1234567).')
            digits = cc + digits[1:]
    if not 8 <= len(digits) <= 15 or digits.startswith('0'):
        raise InvalidPhone('"%s" is not a valid international phone number.' % s[:30])
    return digits


def try_normalize(raw, default_country_code='92'):
    try:
        return normalize(raw, default_country_code)
    except InvalidPhone:
        return None


def pretty(wa_id):
    return '+' + wa_id if wa_id else ''
