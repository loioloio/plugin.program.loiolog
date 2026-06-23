# -*- coding: utf-8 -*-
"""Sharing the log: paste services and a local HTTP server.

socket / json / urllib.request / http.server / threading are imported lazily
inside the functions that use them: they pull in http.client, _socket and
ipaddress (~65ms total), and only the rarely used share actions need them, so
the menu must not pay that cost on every open.
"""
import xbmc

SERVE_PORT = 8989

_PAGE_PREFIX = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>Kodi Log</title>'
    '<style>'
    'body{background:#1a1a2e;color:#e0e0e0;font-family:monospace;'
    'font-size:13px;padding:12px;margin:0}'
    'h1{color:#e94560;font-size:18px;margin:0 0 12px}'
    'pre{white-space:pre-wrap;word-wrap:break-word;line-height:1.5}'
    '</style></head><body>'
    '<h1>Kodi Log &mdash; loiolog</h1><pre>'
)
_PAGE_SUFFIX = '</pre></body></html>'


class UploadError(Exception):
    """No paste service accepted the upload."""


def upload_to_paste(content):
    """Try several paste services in order. Returns (url, service_name)."""
    import json
    import socket
    import urllib.error
    import urllib.parse
    import urllib.request

    payload = content.encode('utf-8')

    # Termbin (raw TCP on port 9999)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(15)
            sock.connect(("termbin.com", 9999))
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            url = sock.recv(1024).decode('utf-8').replace('\x00', '').strip()
        if url.startswith("http"):
            return url, "Termbin"
    except OSError as exc:
        xbmc.log(f"loiolog: Termbin upload failed: {exc}", xbmc.LOGWARNING)

    # dpaste.com (HTTPS POST)
    try:
        data = urllib.parse.urlencode({'content': content, 'expiry_days': 7}).encode('utf-8')
        req = urllib.request.Request(
            "https://dpaste.com/api/v2/", data=data,
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            url = response.read().decode('utf-8').strip()
            if url.startswith("http"):
                return url, "dpaste"
    except (OSError, urllib.error.URLError) as exc:
        xbmc.log(f"loiolog: dpaste upload failed: {exc}", xbmc.LOGWARNING)

    # paste.osmc.tv (HTTPS POST, JSON response)
    try:
        req = urllib.request.Request(
            "https://paste.osmc.tv/documents", data=payload,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "text/plain"})
        with urllib.request.urlopen(req, timeout=15) as response:
            key = json.loads(response.read().decode('utf-8')).get("key")
            if key:
                return f"https://paste.osmc.tv/{key}", "OSMC Paste"
    except (OSError, urllib.error.URLError, ValueError) as exc:
        xbmc.log(f"loiolog: OSMC paste upload failed: {exc}", xbmc.LOGWARNING)

    raise UploadError("All paste services failed or timed out.")


def _local_ip():
    """Best-effort LAN IP, or 127.0.0.1 if it cannot be determined."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def serve_log(content):
    """Serve `content` as an HTML page on the LAN. Returns (ip, server).

    Raises OSError if SERVE_PORT is already in use. The caller owns the server
    and must call server.shutdown() and server.server_close() when done.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    page = (_PAGE_PREFIX + escaped + _PAGE_SUFFIX).encode('utf-8')

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, fmt, *args):
            pass

    server = HTTPServer(("0.0.0.0", SERVE_PORT), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return _local_ip(), server
