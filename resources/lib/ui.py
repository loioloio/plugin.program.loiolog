# -*- coding: utf-8 -*-
"""Kodi UI primitives: notifications, menu items, visual items, QR dialog."""
import xbmcgui
import xbmcplugin

from core import ADDON_NAME, T, build_url, get_icon_path
from parsing import classify_severity, extract_timestamp
from sanitizer import sanitize_line


def notify(msg, level=xbmcgui.NOTIFICATION_INFO, ms=5000):
    xbmcgui.Dialog().notification(ADDON_NAME, msg, level, ms)


def add_menu_item(h, label, action, icon='DefaultIconInfo.png', plot="", is_folder=False, color=None):
    display = f"[B]{label}[/B]"
    if color:
        display = f"[COLOR {color}]{display}[/COLOR]"
    li = xbmcgui.ListItem(label=display)
    li.setArt({'icon': icon})
    if plot:
        li.setInfo('video', {'plot': plot})
    xbmcplugin.addDirectoryItem(handle=h, url=build_url(action=action), listitem=li, isFolder=is_folder)


def add_separator(h, label):
    li = xbmcgui.ListItem(label=f"[COLOR lightgrey][B]{label.upper()}[/B][/COLOR]")
    li.setArt({'icon': get_icon_path("separator.png")})
    li.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(handle=h, url="", listitem=li, isFolder=False)


def format_visual_item(line, enabled):
    """Turn a log line into a (ListItem, sanitized_text) colored by severity."""
    sanitized = sanitize_line(line.rstrip(), enabled)
    sev = classify_severity(sanitized)
    ts, body = extract_timestamp(sanitized)
    label_text = (body[:117] + "...") if len(body) > 120 else body

    if sev == 'error':
        label = "[COLOR red][B]X[/B][/COLOR] "
        if ts:
            label += f"[COLOR grey]{ts}[/COLOR] "
        label += f"[COLOR red]{label_text}[/COLOR]"
        icon = 'DefaultIconError.png'
    elif sev == 'warning':
        label = "[COLOR yellow][B]![/B][/COLOR] "
        if ts:
            label += f"[COLOR grey]{ts}[/COLOR] "
        label += f"[COLOR yellow]{label_text}[/COLOR]"
        icon = 'DefaultIconWarning.png'
    elif sev == 'debug':
        label = "[COLOR grey]- "
        if ts:
            label += f"{ts} "
        label += f"{label_text}[/COLOR]"
        icon = 'DefaultIconInfo.png'
    else:
        label = "[COLOR white]-[/COLOR] "
        if ts:
            label += f"[COLOR grey]{ts}[/COLOR] "
        label += label_text
        icon = 'DefaultIconInfo.png'

    li = xbmcgui.ListItem(label=label)
    li.setArt({'icon': icon})
    li.setInfo('video', {'plot': sanitized})
    return li, sanitized


class QRCodeDialog(xbmcgui.WindowDialog):
    """Full-screen modal showing a QR code image for a URL."""

    def __init__(self, image_path, caption, url):
        super().__init__()
        width, height, qr = 1280, 720, 400
        cx, cy = (width - qr) // 2, (height - qr) // 2
        self.addControl(xbmcgui.ControlImage(
            0, 0, width, height, get_icon_path("qr_bg.png")))
        self.addControl(xbmcgui.ControlLabel(
            0, cy - 60, width, 40, caption, alignment=2, font='font13'))
        # aspectRatio=2 (keep): the QR must stay square on any screen. With the
        # default stretch it distorts into a rectangle when the GUI is not 16:9.
        self.addControl(xbmcgui.ControlImage(cx, cy, qr, qr, image_path, aspectRatio=2))
        self.addControl(xbmcgui.ControlLabel(
            0, cy + qr + 20, width, 40, url, alignment=2, textColor='0xFFe0e0e0'))
        self.addControl(xbmcgui.ControlLabel(
            0, height - 70, width, 40, T(32327), alignment=2,
            font='font12', textColor='0xFFaaaaaa'))

    def onAction(self, action):
        if action.getId() in (10, 92):  # ESC / Back
            self.close()


def show_qr_code(url, caption):
    """Render a QR image for `url` locally and show it full-screen. Returns True on success."""
    import qr_generator  # deferred: only the share actions reach this, not menu open

    img_path = qr_generator.generate(url)
    if not img_path:
        xbmcgui.Dialog().ok(T(32222), T(32331))
        return False
    try:
        QRCodeDialog(img_path, caption, url).doModal()
    finally:
        qr_generator.cleanup(img_path)
    return True
