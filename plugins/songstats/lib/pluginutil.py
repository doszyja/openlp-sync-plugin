# -*- coding: utf-8 -*-
"""Small helpers used at plugin init / live stats (avoid importing songsync at startup)."""
import re

from openlp.core.common.registry import Registry

REMOTE_ID_LINE = re.compile(r'^songstats:remote_id=(.+)$', re.MULTILINE)


def get_remote_id(comments):
    if not comments:
        return None
    match = REMOTE_ID_LINE.search(comments)
    return match.group(1).strip() if match else None


def get_songs_manager():
    manager = Registry().get('songs_manager')
    if manager is not None:
        return manager
    plugin_manager = Registry().get('plugin_manager')
    if not plugin_manager:
        return None
    songs_plugin = plugin_manager.get_plugin_by_name('songs')
    if songs_plugin:
        return songs_plugin.manager
    return None