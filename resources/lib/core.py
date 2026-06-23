# -*- coding: utf-8 -*-
"""Shared addon singleton: localization, settings and URL building."""
import os
import sys
import urllib.parse

import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")
MEDIA_PATH = os.path.join(ADDON_PATH, "resources", "media")


def T(string_id):
    return ADDON.getLocalizedString(string_id)


def get_icon_path(filename):
    return os.path.join(MEDIA_PATH, filename)


def build_url(**kwargs):
    return sys.argv[0] + "?" + urllib.parse.urlencode(kwargs)


def is_sanitize_enabled():
    return ADDON.getSetting("sanitize_enabled") == "true"


def is_reverse_enabled():
    return ADDON.getSetting("reverse_log") == "true"


def get_filter_term():
    term = ADDON.getSetting("filter_term").strip()
    return term.lower() if term else ""
