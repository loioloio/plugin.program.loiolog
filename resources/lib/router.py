# -*- coding: utf-8 -*-
"""Main menu, action routing and the RunScript API for other addons."""
import sys
import urllib.parse

import xbmc
import xbmcplugin

import actions
import views
from core import T, get_filter_term, get_icon_path, is_reverse_enabled, is_sanitize_enabled
from ui import add_menu_item, add_separator

# action -> handler. Keep in sync with the menu items below.
_ROUTES = {
    "view_filtered_log": views.view_filtered_log,
    "view_full_log": views.view_full_log,
    "view_errors_only": views.view_errors_only,
    "view_visual_log": views.view_visual_log,
    "view_old_log": views.view_old_log,
    "view_event_log": views.view_event_log,
    "search_log": views.search_log,
    "search_log_regex": views.search_log_regex,
    "log_stats": views.log_stats,
    "compare_logs": views.compare_logs,
    "log_info": views.log_info,
    "system_info": views.system_info,
    "export_log": actions.export_log,
    "export_json": actions.export_json,
    "upload_log": actions.upload_log,
    "serve_log_network": actions.serve_log_network,
    "toggle_debug": actions.toggle_debug,
    "toggle_reverse": actions.toggle_reverse,
    "copy_log_path": actions.copy_log_path,
    "pick_addon_filter": actions.pick_addon_filter,
    "show_kodi_paths": actions.show_kodi_paths,
    "show_api_info": actions.show_api_info,
    "delete_kodi_logs": actions.delete_kodi_logs,
}

# RunScript command -> handler, for other addons calling us via executebuiltin.
_RUNSCRIPT = {
    "show_log": views.view_filtered_log,
    "show_errors": views.view_errors_only,
    "show_stats": views.log_stats,
    "show_info": views.system_info,
    "toggle_debug": actions.toggle_debug,
}


def main_menu():
    h = int(sys.argv[1])
    filter_term = get_filter_term()

    actions.check_log_size_warning()

    _add_views_section(h, filter_term)
    _add_search_section(h)
    _add_analysis_section(h)
    _add_export_section(h)
    _add_tools_section(h)

    add_separator(h, T(32305))
    add_menu_item(h, T(32027), "delete_kodi_logs",
                  icon=get_icon_path("delete_logs.png"), color="red", plot=T(32218))

    xbmcplugin.endOfDirectory(h)


def _add_views_section(h, filter_term):
    add_separator(h, T(32300))
    label = T(32010).format(filter_term) if filter_term else T(32011)
    plot = T(32200)
    if filter_term:
        plot += T(32201).format(filter_term)
    if is_sanitize_enabled():
        plot += "\n" + T(32202)
    add_menu_item(h, label, "view_filtered_log", icon=get_icon_path("log_filtered.png"), plot=plot)
    add_menu_item(h, T(32013), "view_full_log", icon=get_icon_path("log_full.png"), plot=T(32204))
    add_menu_item(h, T(32014), "view_errors_only", icon=get_icon_path("log_errors.png"), plot=T(32205))
    add_menu_item(h, T(32012), "view_visual_log", icon=get_icon_path("log_visual.png"),
                  plot=T(32203), is_folder=True)
    add_menu_item(h, T(32020), "view_old_log", icon=get_icon_path("log_old.png"), plot=T(32211))
    add_menu_item(h, T(32250), "view_event_log", icon=get_icon_path("log_events.png"), plot=T(32251))


def _add_search_section(h):
    add_separator(h, T(32301))
    add_menu_item(h, T(32016), "search_log", icon=get_icon_path("search.png"), plot=T(32207))
    add_menu_item(h, T(32235), "search_log_regex", icon=get_icon_path("search_regex.png"), plot=T(32238))


def _add_analysis_section(h):
    add_separator(h, T(32302))
    add_menu_item(h, T(32022), "log_stats", icon=get_icon_path("stats.png"), plot=T(32213))
    add_menu_item(h, T(32023), "compare_logs", icon=get_icon_path("compare.png"), plot=T(32214))
    add_menu_item(h, T(32018), "log_info", icon=get_icon_path("info.png"), plot=T(32209))


def _add_export_section(h):
    add_separator(h, T(32303))
    add_menu_item(h, T(32017), "export_log", icon=get_icon_path("export.png"), plot=T(32208))
    add_menu_item(h, T(32240), "export_json", icon=get_icon_path("export_json.png"), plot=T(32244))
    add_menu_item(h, T(32270), "upload_log", icon=get_icon_path("upload.png"), plot=T(32274))
    add_menu_item(h, T(32310), "serve_log_network",
                  icon=get_icon_path("serve_network.png"), plot=T(32312))


def _add_tools_section(h):
    add_separator(h, T(32304))
    add_menu_item(h, T(32024), "system_info", icon=get_icon_path("system_info.png"), plot=T(32215))
    debug_on = xbmc.getCondVisibility("System.GetBool(debug.showloginfo)")
    add_menu_item(h, T(32157) if debug_on else T(32158), "toggle_debug",
                  icon=get_icon_path("debug.png"), plot=T(32212))
    add_menu_item(h, T(32315) if is_reverse_enabled() else T(32314), "toggle_reverse",
                  icon=get_icon_path("reverse.png"), plot=T(32316))
    add_menu_item(h, T(32025), "copy_log_path", icon=get_icon_path("copy_path.png"), plot=T(32216))
    add_menu_item(h, T(32026), "pick_addon_filter", icon=get_icon_path("pick_filter.png"), plot=T(32217))
    add_menu_item(h, T(32290), "show_kodi_paths", icon=get_icon_path("kodi_paths.png"), plot=T(32291))
    add_menu_item(h, T(32260), "show_api_info", icon=get_icon_path("api_info.png"), plot=T(32261))


def route():
    params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip('?')))
    action = params.get("action", "")
    if not action:
        main_menu()
    elif action == "show_line_detail":
        views.show_line_detail(params.get("data", ""))
    else:
        handler = _ROUTES.get(action)
        if handler:
            handler()


def handle_runscript():
    """Run a RunScript command from another addon. Returns True if handled."""
    if len(sys.argv) < 2 or sys.argv[1].isdigit():
        return False
    handler = _RUNSCRIPT.get(sys.argv[1].strip().lower())
    if handler:
        handler()
        return True
    return False
