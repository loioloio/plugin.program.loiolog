# -*- coding: utf-8 -*-
"""Log file location, reading and clipboard access."""
import os
import sys

import xbmc
import xbmcvfs


def _resolve(name):
    """First existing path for `name` across Kodi's log locations."""
    candidates = [
        xbmcvfs.translatePath("special://logpath/" + name),
        xbmcvfs.translatePath("special://temp/" + name),
        xbmcvfs.translatePath("special://home/" + name),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def get_log_path():
    return _resolve("kodi.log")


def get_old_log_path():
    return _resolve("kodi.old.log")


def read_file_lines(path):
    """All lines from a file, or [] if missing or unreadable."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.readlines()
    except OSError:
        return []


def read_log_lines():
    return read_file_lines(get_log_path())


def copy_to_clipboard(text):
    """Copy text to the system clipboard. Returns True on success."""
    import subprocess  # deferred: only needed for this user action, not on menu open
    data = text.encode('utf-8')
    try:
        if sys.platform == 'win32':
            subprocess.Popen(['clip'], stdin=subprocess.PIPE).communicate(data)
        elif sys.platform == 'darwin':
            subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE).communicate(data)
        else:
            try:
                subprocess.Popen(['xclip', '-selection', 'clipboard'],
                                 stdin=subprocess.PIPE).communicate(data)
            except FileNotFoundError:
                subprocess.Popen(['xsel', '--clipboard', '--input'],
                                 stdin=subprocess.PIPE).communicate(data)
        return True
    except OSError as exc:
        xbmc.log(f"loiolog: clipboard copy failed: {exc}", xbmc.LOGWARNING)
        return False
