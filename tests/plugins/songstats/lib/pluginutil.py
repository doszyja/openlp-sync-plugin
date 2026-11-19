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


def openlp_remote_index_key(openlp_id):
    return 'openlp:{0}'.format(int(openlp_id))


def catalog_title_index_keys(title, number=None, search_title=None):
    """Index keys for server rows without openlpMapping (title + optional number)."""
    keys = []
    normalized_title = (title or '').strip().lower()
    if normalized_title:
        num = ''
        if number is not None:
            num = str(number).strip()
        keys.append('title:{0}|n:{1}'.format(normalized_title, num))
        if num:
            keys.append('title:{0}|n:'.format(normalized_title))
    search_key = (search_title or '').strip().lower()
    if search_key:
        keys.append('search:{0}'.format(search_key))
    return keys


def resolve_remote_mongo_id(comments, openlp_id, remote_index=None, song=None):
    """
    Mongo id for PATCH /songs/:id — comments, title/number index, then openlpMapping if present.
    """
    remote_id = get_remote_id(comments)
    if remote_id:
        return remote_id
    index = remote_index or {}
    if song is not None:
        number = song.alternate_title or song.ccli_number or None
        for key in catalog_title_index_keys(song.title, number, song.search_title):
            item = index.get(key)
            if isinstance(item, dict) and item.get('id'):
                return item['id']
    keyed = index.get(openlp_remote_index_key(openlp_id))
    if isinstance(keyed, dict) and keyed.get('id'):
        return keyed['id']
    for cache_item in index.values():
        if not isinstance(cache_item, dict) or not cache_item.get('id'):
            continue
        mapping = cache_item.get('openlpMapping') or {}
        if mapping.get('openlpId') == openlp_id:
            return cache_item['id']
    return None


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