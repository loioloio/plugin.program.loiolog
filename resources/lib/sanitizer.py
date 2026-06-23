# -*- coding: utf-8 -*-
"""Masking of sensitive data in log lines."""
import re

_SENSITIVE_PATTERNS = [
    re.compile(r'(access_token=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(bearer=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(hdnts=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(token=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(api_key=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(password=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(client_secret=)[^&\s]+', re.IGNORECASE),
    re.compile(r'(Authorization:\s*Bearer\s+)\S+', re.IGNORECASE),
]

_EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b')
_MAC_RE = re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b')
# Bounded octets (0-255) so version strings like 1.2.340.5 are left intact.
_IP_RE = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b'
)
# Non-identifying addresses we never mask: localhost, wildcard, public Google DNS.
_IP_EXCEPTIONS = {'127.0.0.1', '0.0.0.0', '8.8.8.8'}


def sanitize_line(line, enabled):
    """Mask tokens, emails, MACs and IPs in a log line when `enabled`."""
    if not enabled:
        return line
    for pattern in _SENSITIVE_PATTERNS:
        line = pattern.sub(r'\1***', line)
    line = _EMAIL_RE.sub('***@***.***', line)
    line = _MAC_RE.sub('XX:XX:XX:XX:XX:XX', line)
    line = _IP_RE.sub(
        lambda m: m.group(0) if m.group(0) in _IP_EXCEPTIONS else '***.***.***.***',
        line,
    )
    return line
