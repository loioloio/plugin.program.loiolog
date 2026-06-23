# -*- coding: utf-8 -*-
"""Actions that change state or produce output: export, share, delete, toggles."""
import json
import os
import time

import xbmc
import xbmcgui
import xbmcvfs

from core import ADDON, ADDON_NAME, T, get_filter_term, is_reverse_enabled, is_sanitize_enabled
from io_utils import (copy_to_clipboard, get_log_path, get_old_log_path,
                      read_file_lines, read_log_lines)
from network import SERVE_PORT, UploadError, serve_log, upload_to_paste
from parsing import classify_severity, extract_timestamp
from sanitizer import sanitize_line
from ui import notify, show_qr_code

_BYTES_PER_MB = 1024 * 1024
_LOG_SIZE_WARN_BYTES = 10 * _BYTES_PER_MB
_UPLOAD_MAX_LINES = 15000


def check_log_size_warning():
    """Warn via notification if kodi.log exceeds the size threshold."""
    log_path = get_log_path()
    if not os.path.exists(log_path):
        return
    try:
        size = os.path.getsize(log_path)
    except OSError:
        return
    if size > _LOG_SIZE_WARN_BYTES:
        notify(T(32230).format(size / _BYTES_PER_MB).split('\n')[0],
               xbmcgui.NOTIFICATION_WARNING)


# Export
def export_log():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return

    enabled = is_sanitize_enabled()
    filter_term = get_filter_term()
    filter_label = filter_term if filter_term else "addon"
    opts = [T(32130).format(filter_label), T(32131), T(32132)]
    sel = xbmcgui.Dialog().select(T(32133), opts)
    if sel < 0:
        return

    if sel == 0:
        if filter_term:
            filtered = [sanitize_line(l, enabled) for l in lines if filter_term in l.lower()]
        else:
            filtered = [sanitize_line(l, enabled) for l in lines[-200:]]
        suffix = filter_term if filter_term else "filtered"
    elif sel == 1:
        filtered = [sanitize_line(l, enabled) for l in lines]
        suffix = "full"
    else:
        filtered = [sanitize_line(l, enabled) for l in lines
                    if classify_severity(l) in ('error', 'warning')]
        suffix = "errors"

    if not filtered:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32134))
        return

    dest_dir = xbmcgui.Dialog().browse(3, T(32135), 'files')
    if not dest_dir:
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    fname = f"kodi_log_{suffix}_{ts}.txt"
    if os.path.isdir(dest_dir):
        dest = os.path.join(dest_dir, fname)
    else:
        dest = dest_dir if dest_dir.lower().endswith('.txt') else dest_dir + '.txt'

    try:
        with open(dest, 'w', encoding='utf-8') as fh:
            fh.write(T(32136).format(ADDON_NAME, time.strftime('%d/%m/%Y %H:%M:%S')) + "\n")
            fh.write(T(32137).format(opts[sel]) + "\n")
            fh.write(T(32138).format(len(filtered)) + "\n")
            fh.write("=" * 60 + "\n\n")
            fh.writelines(filtered)
        xbmcgui.Dialog().ok(T(32139), T(32140).format(dest, len(filtered)))
    except OSError as exc:
        xbmcgui.Dialog().ok(T(32222), T(32141).format(exc))


def export_json():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    entries = []
    for line in lines:
        sanitized = sanitize_line(line.rstrip(), enabled)
        ts, body = extract_timestamp(sanitized)
        entries.append({
            "timestamp": ts,
            "severity": classify_severity(sanitized),
            "message": body,
        })
    dest_dir = xbmcgui.Dialog().browse(3, T(32241), 'files')
    if not dest_dir:
        return
    ts_file = time.strftime("%Y%m%d_%H%M%S")
    fname = f"kodi_log_{ts_file}.json"
    if os.path.isdir(dest_dir):
        dest = os.path.join(dest_dir, fname)
    else:
        dest = dest_dir if dest_dir.lower().endswith('.json') else dest_dir + '.json'
    try:
        with open(dest, 'w', encoding='utf-8') as fh:
            json.dump({
                "exported_by": ADDON_NAME,
                "date": time.strftime('%Y-%m-%dT%H:%M:%S'),
                "total_entries": len(entries),
                "entries": entries,
            }, fh, ensure_ascii=False, indent=2)
        xbmcgui.Dialog().ok(T(32242), T(32243).format(dest, len(entries)))
    except OSError as exc:
        xbmcgui.Dialog().ok(T(32222), T(32141).format(exc))


# Share
def upload_log():
    opts = [T(32276), T(32277)]
    sel = xbmcgui.Dialog().select(T(32275), opts)
    if sel < 0:
        return
    path = get_log_path() if sel == 0 else get_old_log_path()
    lines = read_file_lines(path)
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    if len(lines) > _UPLOAD_MAX_LINES:
        lines = lines[-_UPLOAD_MAX_LINES:]
    enabled = is_sanitize_enabled()
    content = "".join(sanitize_line(l, enabled) for l in lines)
    notify(T(32271), xbmcgui.NOTIFICATION_INFO, 2000)

    try:
        url, service = upload_to_paste(content)
    except UploadError as exc:
        xbmcgui.Dialog().ok(T(32222), T(32273).format(exc))
        return
    copy_to_clipboard(url)
    msg = T(32272).format(url) + f"\n\n({service})"
    if xbmcgui.Dialog().yesno(T(32278), msg, nolabel=T(32329), yeslabel=T(32325)):
        show_qr_code(url, T(32326))


def serve_log_network():
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    enabled = is_sanitize_enabled()
    content = "".join(sanitize_line(l, enabled) for l in lines)

    try:
        local_ip, server = serve_log(content)
    except OSError:
        xbmcgui.Dialog().ok(T(32222), T(32313).format(SERVE_PORT))
        return

    # The server stays up only while this modal blocks; the QR scan must happen
    # during the dialog. finally guarantees the socket is freed on every path.
    try:
        url = f"http://{local_ip}:{SERVE_PORT}"
        copy_to_clipboard(url)
        if xbmcgui.Dialog().yesno(T(32310), T(32311).format(url), nolabel=T(32329), yeslabel=T(32325)):
            show_qr_code(url, T(32326))
    finally:
        server.shutdown()
        server.server_close()


# Management
def delete_kodi_logs():
    log_path = get_log_path()
    old_path = get_old_log_path()

    targets, labels = [], []
    if os.path.exists(log_path):
        targets.append(log_path)
        labels.append("kodi.log")
    if os.path.exists(old_path):
        targets.append(old_path)
        labels.append("kodi.old.log")

    if not targets:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return

    sel = xbmcgui.Dialog().multiselect(T(32195), labels)
    if not sel:
        return

    deleted, errors = [], []
    active_locked = False
    for idx in sel:
        try:
            os.remove(targets[idx])
            deleted.append(labels[idx])
        except OSError as exc:
            errors.append(f"{labels[idx]}: {exc}")
            # kodi.log is held open by the running Kodi process; on Windows the
            # delete fails with a sharing violation. Flag it to explain why.
            if labels[idx] == "kodi.log":
                active_locked = True

    if deleted:
        notify(T(32198), xbmcgui.NOTIFICATION_INFO)
    if errors:
        detail = "\n".join(errors)
        if active_locked:
            detail += "\n\n" + T(32194)
        xbmcgui.Dialog().ok(T(32222), T(32199).format(detail))
    xbmc.executebuiltin("Container.Refresh")


def toggle_debug():
    current = xbmc.getCondVisibility("System.GetBool(debug.showloginfo)")
    new_state = not current
    response = xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
        "params": {"setting": "debug.showloginfo", "value": new_state},
    }))
    try:
        applied = json.loads(response).get("result") == "OK"
    except ValueError:
        applied = False
    if not applied:
        xbmcgui.Dialog().ok(T(32222), T(32159))
        return
    xbmcgui.Dialog().ok(ADDON_NAME, T(32155) if new_state else T(32156))
    xbmc.executebuiltin("Container.Refresh")


def toggle_reverse():
    ADDON.setSetting("reverse_log", "false" if is_reverse_enabled() else "true")
    xbmc.executebuiltin("Container.Refresh")


def copy_log_path():
    path = get_log_path()
    if copy_to_clipboard(path):
        notify(T(32185), xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32186) + "\n\n" + path)


def pick_addon_filter():
    addons_path = xbmcvfs.translatePath("special://home/addons/")
    if not os.path.isdir(addons_path):
        return
    addon_dirs = sorted(d for d in os.listdir(addons_path)
                        if os.path.isdir(os.path.join(addons_path, d)) and not d.startswith('.'))
    if not addon_dirs:
        return
    sel = xbmcgui.Dialog().select(T(32190), addon_dirs)
    if sel < 0:
        return
    chosen = addon_dirs[sel]
    ADDON.setSetting("filter_term", chosen)
    lines = read_log_lines()
    if not lines:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32100))
        return
    term = chosen.lower()
    enabled = is_sanitize_enabled()
    filtered = [sanitize_line(l.rstrip(), enabled) for l in lines if term in l.lower()]
    if not filtered:
        xbmcgui.Dialog().ok(ADDON_NAME, T(32107).format(chosen))
        return
    if is_reverse_enabled():
        filtered.reverse()
    xbmcgui.Dialog().textviewer(T(32108).format(len(filtered), chosen), "\n".join(filtered[-200:]))


def show_kodi_paths():
    paths = [
        ("Log", xbmcvfs.translatePath("special://logpath/")),
        ("Addons", xbmcvfs.translatePath("special://home/addons/")),
        ("Userdata", xbmcvfs.translatePath("special://userdata/")),
        ("Home", xbmcvfs.translatePath("special://home/")),
        ("Temp", xbmcvfs.translatePath("special://temp/")),
        ("Profile", xbmcvfs.translatePath("special://profile/")),
        ("Thumbnails", xbmcvfs.translatePath("special://thumbnails/")),
        ("Database", xbmcvfs.translatePath("special://database/")),
    ]
    labels = [f"{name}: {path}" for name, path in paths]
    sel = xbmcgui.Dialog().select(T(32290), labels)
    if sel < 0:
        return
    chosen_path = paths[sel][1]
    if copy_to_clipboard(chosen_path):
        notify(T(32185), xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().ok(ADDON_NAME, chosen_path)


def show_api_info():
    msg = (
        "[B]RunScript API[/B]\n\n"
        "xbmc.executebuiltin(\n"
        '  "RunScript(plugin.program.loiolog, show_log)"\n'
        ")\n\n"
        "[B]Commands:[/B]\n"
        "  show_log: Open log viewer\n"
        "  show_errors: Show errors only\n"
        "  show_stats: Show log statistics\n"
        "  show_info: Show system info\n"
        "  toggle_debug: Toggle debug logging\n"
    )
    xbmcgui.Dialog().textviewer(T(32260), msg)
