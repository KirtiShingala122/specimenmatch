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
    
    # Try parsing common formats
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y",
        "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(dob, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If parsing fails, just return the original (safely preserve invalid values)
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
