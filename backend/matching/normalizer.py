import re
from datetime import datetime
from typing import Optional

PUNCTUATION_PATTERN = re.compile(r'[^\w\s]')
WHITESPACE_PATTERN = re.compile(r'\s+')
PHONE_PATTERN = re.compile(r'\D')


def normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name = name.lower()
    name = PUNCTUATION_PATTERN.sub('', name)
    name = WHITESPACE_PATTERN.sub(' ', name)
    return name.strip()


def normalize_dob(dob: Optional[str]) -> Optional[str]:
    if not dob:
        return None
    dob = str(dob).strip()
    
    # Try parsing common formats (order matters: most specific first)
    formats = [
        "%Y-%m-%d",   # 1988-04-12
        "%Y/%m/%d",   # 1988/04/12
        "%Y/%d/%m",   # 1988/12/04  <-- YYYY/DD/MM
        "%d-%m-%Y",   # 12-04-1988
        "%m-%d-%Y",   # 04-12-1988
        "%d/%m/%Y",   # 12/04/1988
        "%m/%d/%Y",   # 04/12/1988
        "%d.%m.%Y",   # 12.04.1988
        "%Y.%m.%d",   # 1988.04.12
        "%d %b %Y",   # 12 Apr 1988
        "%d %B %Y",   # 12 April 1988
        "%b %d, %Y",  # Apr 12, 1988
        "%B %d, %Y",  # April 12, 1988
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(dob, fmt)
            # Sanity check: year must be realistic (1900–2100)
            if 1900 <= parsed.year <= 2100:
                return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If parsing fails, return original (safely preserve for logging)
    return dob


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    phone_digits = PHONE_PATTERN.sub('', str(phone))
    return phone_digits if phone_digits else None


def normalize_gender(gender: Optional[str]) -> Optional[str]:
    if not gender:
        return None
    g = str(gender).strip().upper()
    if g in ("M", "MALE"):
        return "M"
    if g in ("F", "FEMALE"):
        return "F"
    if g in ("O", "OTHER"):
        return "OTHER"
    return g


def normalize_address(address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    addr = str(address).lower()
    addr = PUNCTUATION_PATTERN.sub('', addr)
    addr = WHITESPACE_PATTERN.sub(' ', addr)
    return addr.strip()
