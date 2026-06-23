# -*- coding: utf-8 -*-
"""Local QR PNG generation via the bundled segno. The caller owns cleanup()."""
import os
import struct
import tempfile
import zlib

import xbmc
import xbmcvfs

_QR_SCALE = 8
_QR_BORDER = 2


def generate(url):
    """Build a QR PNG in special://temp and return its path, or None on failure."""
    if not url:
        return None

    try:
        import segno
    except ImportError:
        xbmc.log("loiolog.qr_generator: segno not available", xbmc.LOGWARNING)
        return None

    try:
        qr = segno.make(url, micro=False, error="M")
        png = _encode_png_rgba(qr)
    except (ValueError, TypeError) as exc:
        xbmc.log(f"loiolog.qr_generator: could not build QR: {exc}", xbmc.LOGWARNING)
        return None

    # mkstemp gives a unique name so two QR dialogs can never clobber each other.
    temp_dir = xbmcvfs.translatePath("special://temp/")
    try:
        fd, output_path = tempfile.mkstemp(prefix="loiolog_qr_", suffix=".png", dir=temp_dir)
    except OSError as exc:
        xbmc.log(f"loiolog.qr_generator: mkstemp failed: {exc}", xbmc.LOGWARNING)
        return None

    # fdopen takes ownership of the fd, so the `with` closes it exactly once; the
    # except path must not os.close() it again. After writing we read the file
    # back whole: on Windows an antivirus can briefly lock a freshly written file,
    # and Kodi would then load it as a broken (white) texture. The read-back
    # confirms it is readable before we hand the path to Kodi.
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(png)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass  # best-effort; the read-back below is what decides validity
        with open(output_path, "rb") as rb:
            head = rb.read(8)
            rb.read()  # drain the file: confirms it is fully readable
        if head != b"\x89PNG\r\n\x1a\n":
            raise ValueError("the written file is not a readable PNG")
        return output_path
    except (OSError, ValueError) as exc:
        xbmc.log(f"loiolog.qr_generator: could not write/read QR: {exc}", xbmc.LOGWARNING)
        try:
            os.remove(output_path)
        except OSError:
            pass
        return None


def _encode_png_rgba(qr):
    """Encode the QR matrix as an 8-bit RGBA PNG.

    segno emits 1-bit greyscale PNG, which Kodi's texture loader renders
    intermittently as solid white; every other image in the addon is RGBA8 and
    always loads. Rebuilding the PNG as RGBA8 from the matrix makes Kodi treat it
    like any other asset.
    """
    black = b"\x00\x00\x00\xff"
    white = b"\xff\xff\xff\xff"
    raw = bytearray()
    width = None
    height = 0
    for row in qr.matrix_iter(scale=_QR_SCALE, border=_QR_BORDER):
        raw.append(0)  # PNG filter type for the row: None
        cols = 0
        for module in row:
            raw += black if module else white
            cols += 1
        if width is None:
            width = cols
        height += 1

    def _chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def cleanup(path):
    """Remove the QR PNG. Idempotent: ignores None or a missing file."""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass
