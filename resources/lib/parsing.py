# -*- coding: utf-8 -*-
"""Severity classification and timestamp extraction for Kodi log lines."""

_SEVERITY_ERROR_TERMS = (' error ', 'exception', 'traceback')
_SEVERITY_WARNING_TERMS = ('warning',)
_SEVERITY_DEBUG_TERMS = (' debug ',)

_KODI_LOG_TAGS = (
    'info <general>:',
    'error <general>:',
    'warning <general>:',
    'debug <general>:',
    'notice <general>:',
)


def classify_severity(line):
    """Return 'error', 'warning', 'debug' or 'info' for a log line."""
    ll = ' ' + line.lower()
    if any(term in ll for term in _SEVERITY_ERROR_TERMS):
        return 'error'
    if any(term in ll for term in _SEVERITY_WARNING_TERMS):
        return 'warning'
    if any(term in ll for term in _SEVERITY_DEBUG_TERMS):
        return 'debug'
    return 'info'


def extract_timestamp(line):
    """Return (HH:MM:SS, body) from a Kodi line, or ('', line) if none."""
    if len(line) > 19 and line[4] == '-' and line[10] == ' ':
        ts = line[11:19]
        rest = line[19:]
        # The fractional seconds (.mmm) are optional: some Kodi forks and older
        # kodi.old.log files omit them. Skip them instead of cutting at a fixed
        # offset, which would slice into the message body when they are absent.
        if rest[:1] == '.':
            i = 1
            while i < len(rest) and rest[i].isdigit():
                i += 1
            rest = rest[i:]
        body = rest.strip()
        if body.startswith("T:"):
            space_idx = body.find(' ')
            if space_idx > 0:
                body = body[space_idx:].strip()
        for tag in _KODI_LOG_TAGS:
            if body.lower().startswith(tag):
                body = body[len(tag):].strip()
                break
        return ts, body
    return "", line
