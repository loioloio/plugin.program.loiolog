# -*- coding: utf-8 -*-
"""Log statistics: severity counts, addon mentions, known-issue detection."""
import re
from collections import Counter

from parsing import classify_severity, extract_timestamp

_ADDON_NAME_RE = re.compile(r'\[([A-Za-z0-9_.\-]+)\]')

# Well-known Kodi failure signatures, surfaced in the stats view.
# (string_id, compiled_pattern); order defines display order.
KNOWN_ISSUE_PATTERNS = [
    (32321, re.compile(r'database is locked', re.IGNORECASE)),
    (32322, re.compile(r'connection timed out|connect timeout|timed out', re.IGNORECASE)),
    (32323, re.compile(r'failed to satisfy dependencies|no module named', re.IGNORECASE)),
    (32324, re.compile(r'playback failed|failed to play', re.IGNORECASE)),
]


def count_known_issues(lines):
    """Count well-known Kodi failure signatures. Returns {string_id: count}."""
    counts = Counter()
    for line in lines:
        for string_id, pattern in KNOWN_ISSUE_PATTERNS:
            if pattern.search(line):
                counts[string_id] += 1
    return counts


def analyze_stats(lines):
    """Single pass over the log. Returns severities, top addons and known issues."""
    severities = Counter()
    addons = Counter()
    known = Counter()
    for line in lines:
        severities[classify_severity(line)] += 1
        for match in _ADDON_NAME_RE.findall(line):
            if '.' in match:
                addons[match] += 1
        for string_id, pattern in KNOWN_ISSUE_PATTERNS:
            if pattern.search(line):
                known[string_id] += 1
    return {
        'total': len(lines),
        'severities': severities,
        'top_addons': addons.most_common(10),
        'known_issues': known,
    }


def new_errors(current_lines, old_lines):
    """Error bodies present in the current log but not in the old one, sorted."""
    def error_bodies(lines):
        bodies = set()
        for line in lines:
            if classify_severity(line) == 'error':
                _, body = extract_timestamp(line)
                bodies.add(body.strip())
        return bodies

    return sorted(error_bodies(current_lines) - error_bodies(old_lines))
