# -*- coding: utf-8 -*-
"""Read-only log views: text viewers, visual list, search, stats, info."""
import base64
import binascii
import os
import re
import sys

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from analyzer import KNOWN_ISSUE_PATTERNS, analyze_stats, new_errors
from core import (ADDON_NAME, T, build_url, get_filter_term, is_reverse_enabled,
                  is_sanitize_enabled)
from io_utils import get_log_path, get_old_log_path, read_file_lines, read_log_lines
from parsing import classify_severity, extract_timestamp
from sanitizer import sanitize_line
from ui import format_visual_item

_BYTES_PER_KB = 1024
_BYTES_PER_MB = 1024 * 1024


def _line_counts():
    return [T(32103), T(32104), T(32105)], [50, 100, 200]


# Text views
def view_filtered_log():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    term = get_filter_term()
    tail = lines[-100:]
    if term:
        filtered = [sanitize_line(l.rstrip(), enabled) for l in tail if term in l.lower()]
        if not filtered:
            xbmcgui.Dialog().ok(ADDON_NAME, T(32107).format(term))
            return
    else:
        filtered = [sanitize_line(l.rstrip(), enabled) for l in tail[-30:]]
    if is_reverse_enabled():
        filtered.reverse()
    title = T(32010).format(term) if term else T(32011)
    xbmcgui.Dialog().textviewer(title, "\n".join(filtered[-50:]))


def view_full_log():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    ordered = reversed(lines) if is_reverse_enabled() else lines
    text = "".join(sanitize_line(l, enabled) for l in ordered)
    xbmcgui.Dialog().textviewer(T(32013), text)


def view_errors_only():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    error_lines = [
        sanitize_line(l.rstrip(), enabled) for l in lines[-500:]
        if classify_severity(l) in ('error', 'warning')
    ]
    if not error_lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32101))
        return
    if is_reverse_enabled():
        error_lines.reverse()
    xbmcgui.Dialog().textviewer(T(32014), "\n".join(error_lines[-80:]))


def search_log():
    kb = xbmc.Keyboard('', T(32106))
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        return
    raw_term = kb.getText().strip()
    term = raw_term.lower()
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    matches = [sanitize_line(l.rstrip(), enabled) for l in lines if term in l.lower()]
    if not matches:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32107).format(raw_term))
        return
    if is_reverse_enabled():
        matches.reverse()
    xbmcgui.Dialog().textviewer(T(32108).format(len(matches), raw_term), "\n".join(matches[-80:]))


def search_log_regex():
    kb = xbmc.Keyboard('', T(32236))
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        return
    raw_pattern = kb.getText().strip()
    try:
        compiled = re.compile(raw_pattern, re.IGNORECASE)
    except re.error as exc:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32237).format(exc))
        return
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    matches = [sanitize_line(l.rstrip(), enabled) for l in lines if compiled.search(l)]
    if not matches:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32107).format(raw_pattern))
        return
    if is_reverse_enabled():
        matches.reverse()
    xbmcgui.Dialog().textviewer(T(32108).format(len(matches), raw_pattern), "\n".join(matches[-80:]))


def view_old_log():
    lines = read_file_lines(get_old_log_path())
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32150))
        return
    opts, counts = _line_counts()
    sel = xbmcgui.Dialog().select(T(32102), opts)
    if sel < 0:
        return
    tail = lines[-counts[sel]:]
    if is_reverse_enabled():
        tail = list(reversed(tail))
    enabled = is_sanitize_enabled()
    text = "".join(sanitize_line(l, enabled) for l in tail)
    xbmcgui.Dialog().textviewer(T(32151), text)


def view_event_log():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    event_terms = ('notification', 'event', 'signal', 'callback')
    events = []
    for line in lines[-500:]:
        if not any(t in line.lower() for t in event_terms):
            continue
        sanitized = sanitize_line(line.rstrip(), enabled)
        ts, body = extract_timestamp(sanitized)
        label = f"[COLOR grey]{ts}[/COLOR] " if ts else ""
        sev = classify_severity(sanitized)
        if sev == 'error':
            label += f"[COLOR red]{body[:120]}[/COLOR]"
        elif sev == 'warning':
            label += f"[COLOR yellow]{body[:120]}[/COLOR]"
        else:
            label += body[:120]
        events.append(label)
    if not events:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32252))
        return
    if is_reverse_enabled():
        events.reverse()
    xbmcgui.Dialog().textviewer(T(32250), "\n".join(events[-80:]))


# Visual viewer
def view_visual_log():
    log_path = get_log_path()
    if not os.path.exists(log_path):
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return

    filter_term = get_filter_term()
    opts = [T(32103), T(32104), T(32105)]
    if filter_term:
        opts.append(T(32110).format(filter_term))
    opts.append(T(32111))
    sel = xbmcgui.Dialog().select(T(32109), opts)
    if sel < 0:
        return

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            all_lines = fh.readlines()
    except OSError as exc:
        xbmcgui.Dialog().ok(T(32222), str(exc))
        return

    if sel == 0:
        lines = all_lines[-50:]
    elif sel == 1:
        lines = all_lines[-100:]
    elif sel == 2:
        lines = all_lines[-200:]
    elif filter_term and sel == 3:
        lines = [l for l in all_lines if filter_term in l.lower()][-100:]
    else:
        lines = [l for l in all_lines if classify_severity(l) == 'error'][-100:]

    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32112))
        return

    if is_reverse_enabled():
        lines.reverse()
    enabled = is_sanitize_enabled()
    h = int(sys.argv[1])
    for raw in lines:
        li, sanitized = format_visual_item(raw, enabled)
        encoded = base64.b64encode(sanitized.encode('utf-8')).decode('ascii')
        xbmcplugin.addDirectoryItem(
            handle=h, url=build_url(action="show_line_detail", data=encoded),
            listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(h)


def show_line_detail(data):
    try:
        line = base64.b64decode(data).decode('utf-8')
    except (ValueError, binascii.Error):
        xbmcgui.Dialog().ok(T(32222), T(32114))
        return
    xbmcgui.Dialog().textviewer(T(32113), line)


# Stats, comparison and info
def log_stats():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    stats = analyze_stats(lines)
    sev = stats['severities']

    msg = f"[B]{T(32160)}[/B]\n\n"
    msg += T(32161).format(stats['total']) + "\n"
    msg += "[COLOR red]" + T(32162).format(sev['error']) + "[/COLOR]\n"
    msg += "[COLOR yellow]" + T(32163).format(sev['warning']) + "[/COLOR]\n"
    msg += "[COLOR grey]" + T(32164).format(sev['debug']) + "[/COLOR]\n"
    msg += T(32165).format(sev['info']) + "\n"

    if stats['top_addons']:
        msg += f"\n[B]{T(32166)}[/B]\n"
        for name, count in stats['top_addons']:
            msg += f"  {name}: {count:,}\n"

    known = stats['known_issues']
    if known:
        msg += f"\n[B]{T(32320)}[/B]\n"
        for string_id, _pattern in KNOWN_ISSUE_PATTERNS:
            count = known.get(string_id, 0)
            if count:
                msg += "[COLOR orange]  " + T(string_id).format(count) + "[/COLOR]\n"

    xbmcgui.Dialog().textviewer(T(32160), msg)


def compare_logs():
    log_path = get_log_path()
    old_path = get_old_log_path()
    if not os.path.exists(log_path) or not os.path.exists(old_path):
        xbmcgui.Dialog().ok(ADDON_NAME, T(32170))
        return

    errors = new_errors(read_file_lines(log_path), read_file_lines(old_path))
    enabled = is_sanitize_enabled()

    msg = f"[B]{T(32172)}[/B]\n\n"
    if errors:
        for err in errors[:50]:
            sanitized = sanitize_line(err, enabled)
            truncated = (sanitized[:120] + "...") if len(sanitized) > 120 else sanitized
            msg += f"[COLOR red]- {truncated}[/COLOR]\n"
    else:
        msg += T(32173)

    xbmcgui.Dialog().textviewer(T(32171), msg)


def log_info():
    log_path = get_log_path()
    msg = f"[B]{T(32120)}[/B]\n"
    if os.path.exists(log_path):
        size = os.path.getsize(log_path)
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
                total_lines = sum(1 for _ in fh)
        except OSError:
            total_lines = 0
        if size > _BYTES_PER_MB:
            msg += T(32121).format(size / _BYTES_PER_MB) + "\n"
        else:
            msg += T(32122).format(size / _BYTES_PER_KB) + "\n"
        msg += T(32123).format(total_lines) + "\n"
        msg += T(32124).format(log_path) + "\n"
    else:
        msg += T(32125) + "\n"

    old_path = get_old_log_path()
    if os.path.exists(old_path):
        osize = os.path.getsize(old_path)
        msg += "\n[B]kodi.old.log[/B]\n"
        if osize > _BYTES_PER_MB:
            msg += T(32121).format(osize / _BYTES_PER_MB) + "\n"
        else:
            msg += T(32122).format(osize / _BYTES_PER_KB) + "\n"

    xbmcgui.Dialog().textviewer(T(32128), msg)


def system_info():
    info = xbmc.getInfoLabel
    msg = "[B]Kodi[/B]\n"
    msg += f"Build: {info('System.BuildVersion')}\n"
    msg += f"OS: {info('System.OSVersionInfo')}\n"
    msg += f"Kernel: {info('System.KernelVersion')}\n"
    msg += f"\n[B]{T(32220)}[/B]\n"
    msg += f"CPU: {info('System.CpuUsage')}\n"
    msg += f"RAM: {info('System.FreeMemory')} / {info('System.TotalMemory')}\n"
    msg += f"Screen: {info('System.ScreenResolution')}\n"
    msg += "\n[B]Python[/B]\n"
    msg += f"Version: {sys.version.split()[0]}\n"
    msg += "\n[B]Addons[/B]\n"
    addons_path = xbmcvfs.translatePath("special://home/addons/")
    if os.path.isdir(addons_path):
        addon_dirs = [d for d in os.listdir(addons_path)
                      if os.path.isdir(os.path.join(addons_path, d)) and not d.startswith('.')]
        msg += T(32221).format(len(addon_dirs)) + "\n"
    msg += "\n[B]Log[/B]\n"
    debug_on = xbmc.getCondVisibility("System.GetBool(debug.showloginfo)")
    msg += f"Debug: {'ON' if debug_on else 'OFF'}\n"
    msg += f"Path: {get_log_path()}\n"
    xbmcgui.Dialog().textviewer(T(32180), msg)
