# -*- coding: utf-8 -*-
"""
Import/export song catalog between the Song Stats API and the OpenLP songs database.

Expected API (customise on your server):
  GET  <pull_url>  -> {"songs": [ ... ]}  or a bare JSON array
  POST <push_url>  -> {"songs": [ ... ], "church_id": "..."} 

OpenLP Database (NestJS) pull: GET /api/songs/all-openlp -> { version, songs[] } (lyricsXml = OpenLP DB format)
  or GET /api/songs/export/sqlite (binary; use sqliteimport module).

Each song object (normalized internal / legacy JSON):
  remote_id (str, required for stable matching)
  lyrics_xml (str, optional — preferred from master API)
  openlp_id (int, optional)
  title, alternate_title, copyright, ccli_number, verse_order, comments
  last_modified (ISO-8601 string, optional)
  authors: [{"name": "...", "type": "words"|"music"|"words and music"|"translation"|""}]
  verses: [{"def": "v1", "text": "line1\\nline2", "lang": "en"}]
"""
import logging
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from openlp.core.common import normalize_str
from openlp.core.common.registry import Registry
from openlp.plugins.songs.lib import VerseType, clean_song
from openlp.plugins.songs.lib.db import Author, AuthorType, Song
from openlp.plugins.songs.lib.importers.songimport import SongImport
from openlp.plugins.songs.lib.openlyricsxml import SongXML
from openlp.plugins.songs.lib.ui import SongStrings

log = logging.getLogger(__name__)

REMOTE_ID_LINE = re.compile(r'^songstats:remote_id=(.+)$', re.MULTILINE)

AUTHOR_TYPE_ALIASES = {
    '': AuthorType.NoType,
    'none': AuthorType.NoType,
    'words': AuthorType.Words,
    'music': AuthorType.Music,
    'words+music': AuthorType.WordsAndMusic,
    'words and music': AuthorType.WordsAndMusic,
    'words_and_music': AuthorType.WordsAndMusic,
    'translation': AuthorType.Translation,
}


class ImportStats(object):
    def __init__(self):
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0
        self.deleted = 0
        self.cancelled = False

    def summary(self):
        parts = (
            'created={created}, updated={updated}, skipped={skipped}, errors={errors}'.format(
                created=self.created,
                updated=self.updated,
                skipped=self.skipped,
                errors=self.errors,
            )
        )
        if self.deleted:
            parts += ', deleted={0}'.format(self.deleted)
        if self.cancelled:
            parts += ', cancelled=1'
        return parts


class PushStats(object):
    def __init__(self):
        self.created = 0
        self.updated = 0
        self.errors = 0
        self.skipped = 0

    def summary(self):
        return 'created={created}, updated={updated}, skipped={skipped}, errors={errors}'.format(
            created=self.created,
            updated=self.updated,
            skipped=self.skipped,
            errors=self.errors,
        )


def normalize_master_api_song(item):
    """
    Map Openlp-database GET /songs/all-openlp cache item to the internal import structure.
    """
    if not isinstance(item, dict):
        return None
    remote_id = item.get('id')
    title = item.get('title')
    if not title:
        return None

    verses = []
    for verse in item.get('versesArray') or []:
        label = verse.get('originalLabel') or verse.get('label')
        if not label:
            label = 'v{order}'.format(order=verse.get('order', 1))
        verses.append({
            'def': label,
            'text': verse.get('content') or '',
            'lang': None,
        })

    tags = item.get('tags') or []
    tag_names = []
    for tag in tags:
        if isinstance(tag, dict):
            tag_names.append(tag.get('name') or '')
        else:
            tag_names.append(str(tag))

    number = item.get('number')
    ccli = item.get('ccliNumber') or number
    mapping = item.get('openlpMapping') or {}
    openlp_id = mapping.get('openlpId')
    if openlp_id is None:
        openlp_id = item.get('openlpId')

    return {
        'remote_id': remote_id,
        'openlp_id': openlp_id,
        'title': title,
        'alternate_title': number,
        'ccli_number': ccli or '',
        'copyright': item.get('copyright') or '',
        'comments': item.get('comments') or '',
        'verse_order': item.get('verseOrder') or '',
        'lyrics_xml': item.get('lyricsXml'),
        'verses': verses,
        'language': item.get('language') or 'pl',
        'songbook': item.get('songbook'),
        'tags': [t for t in tag_names if t],
        'search_title': item.get('searchTitle'),
        'search_lyrics': item.get('searchLyrics'),
    }


def get_remote_id(comments):
    if not comments:
        return None
    match = REMOTE_ID_LINE.search(comments)
    return match.group(1).strip() if match else None


def merge_remote_id(comments, remote_id):
    if not remote_id:
        return comments or ''
    body = comments or ''
    line = 'songstats:remote_id={id}'.format(id=remote_id)
    if REMOTE_ID_LINE.search(body):
        body = REMOTE_ID_LINE.sub(line, body, count=1)
    else:
        body = line + '\n' + body if body else line
    return body.strip()


def _author_type_from_api(value):
    """OpenLP authors_songs.author_type is NOT NULL — never return None."""
    if value is None:
        return AuthorType.Words
    key = str(value).strip().lower()
    resolved = AUTHOR_TYPE_ALIASES.get(key)
    if resolved is None:
        return AuthorType.Words
    return resolved


def song_to_payload(song):
    sxml = SongXML()
    verses = []
    for attrs, text in sxml.get_verses(song.lyrics):
        verse_type = attrs.get('type', 'v')
        label = attrs.get('label', '1')
        verses.append({
            'def': '{type}{label}'.format(type=verse_type, label=label),
            'text': text,
            'lang': attrs.get('lang'),
        })
    authors = []
    for link in song.authors_songs:
        authors.append({
            'name': link.author.display_name,
            'type': link.author_type or '',
        })
    return {
        'remote_id': get_remote_id(song.comments),
        'openlp_id': song.id,
        'title': song.title,
        'alternate_title': song.alternate_title or '',
        'copyright': song.copyright or '',
        'ccli_number': song.ccli_number or '',
        'verse_order': song.verse_order or '',
        'comments': song.comments or '',
        'last_modified': song.last_modified.isoformat() if song.last_modified else None,
        'authors': authors,
        'verses': verses,
    }


def export_local_songs(manager):
    songs = manager.get_all_objects(Song)
    payload = []
    for song in songs:
        if song.temporary:
            continue
        payload.append(song_to_payload(song))
    return payload


def _build_local_song_index(manager):
    """One pass over local songs per sync (not per remote row)."""
    by_remote_id = {}
    by_title = {}
    for song in manager.get_all_objects(Song):
        remote_id = get_remote_id(song.comments)
        if remote_id:
            by_remote_id[remote_id] = song
        title = (song.title or '').strip()
        if title:
            by_title.setdefault(title, []).append(song)
    return by_remote_id, by_title


def find_local_song(manager, remote, local_index=None):
    remote_id = remote.get('remote_id')
    if remote_id and local_index:
        hit = local_index[0].get(remote_id)
        if hit:
            return hit

    openlp_id = remote.get('openlp_id')
    if openlp_id is None:
        openlp_mapping = remote.get('openlpMapping') or {}
        if isinstance(openlp_mapping, dict):
            openlp_id = openlp_mapping.get('openlpId')
    if openlp_id:
        song = manager.get_object(Song, openlp_id)
        if song:
            return song

    ccli = (remote.get('ccli_number') or '').strip()
    title = (remote.get('title') or '').strip()
    if ccli:
        matches = manager.get_all_objects(Song, Song.ccli_number == ccli)
        if len(matches) == 1:
            return matches[0]
    if title:
        matches = manager.get_all_objects(Song, Song.search_title == title.lower())
        if len(matches) != 1:
            matches = manager.get_all_objects(Song, Song.title == title)
        if len(matches) == 1:
            return matches[0]
        if local_index:
            candidates = local_index[1].get(title, [])
            if not candidates:
                return None
            if len(candidates) == 1:
                return candidates[0]
            if remote_id:
                for song in candidates:
                    if get_remote_id(song.comments) == remote_id:
                        return song
            with_remote = [s for s in candidates if get_remote_id(s.comments)]
            if len(with_remote) == 1:
                return with_remote[0]
            without_remote = [s for s in candidates if not get_remote_id(s.comments)]
            if len(without_remote) == 1:
                return without_remote[0]
            return min(candidates, key=lambda s: s.id)
    return None


def _build_lyrics_from_verses(verse_rows):
    sxml = SongXML()
    verse_counts = {}
    for item in verse_rows:
        verse_def = (item.get('def') or 'v1').strip()
        text = item.get('text') or ''
        lang = item.get('lang')
        if not verse_def:
            verse_def = 'v1'
        tag = verse_def[0].lower()
        if tag not in VerseType.tags:
            tag = VerseType.tags[VerseType.Other]
        if len(verse_def) == 1:
            verse_counts[tag] = verse_counts.get(tag, 0) + 1
            number = str(verse_counts[tag])
        else:
            number = verse_def[1:]
        sxml.add_verse_to_lyrics(tag, number, normalize_str(text), lang)
    return str(sxml.extract_xml(), 'utf-8')


def _ensure_default_author(manager, song):
    """clean_song() calls add_author() without type — pre-empt with a valid author_type."""
    if song.authors_songs:
        return
    name = SongStrings().AuthorUnknown
    author = manager.get_object_filtered(Author, Author.display_name == name)
    if author is None:
        author = Author(display_name=name, last_name='', first_name='')
    song.add_author(author, AuthorType.NoType)


def _coerce_lyrics_xml(lyrics_xml):
    """
    Openlp-database may return bare <verse> fragments; OpenLP expects a full OpenLyrics document.
    """
    if not lyrics_xml or not str(lyrics_xml).strip():
        return None
    text = str(lyrics_xml).strip()
    if '<lyrics' not in text and text.startswith('<'):
        text = (
            "<?xml version='1.0' encoding='UTF-8'?>\n"
            '<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.8">'
            '<lyrics>{body}</lyrics></song>'
        ).format(body=text)
    try:
        SongXML().get_verses(text)
        return text
    except Exception:
        log.debug('lyricsXml not parseable as OpenLyrics, falling back to versesArray')
        return None


def _apply_authors(manager, song, authors_data):
    if not authors_data:
        return
    song.authors_songs.clear()
    for row in authors_data:
        name = (row.get('name') or '').strip()
        if not name:
            continue
        author_type = _author_type_from_api(row.get('type'))
        author = manager.get_object_filtered(Author, Author.display_name == name)
        if not author:
            parts = name.split(' ')
            author = Author(
                display_name=name,
                last_name=parts[-1] if parts else name,
                first_name=' '.join(parts[:-1]) if len(parts) > 1 else '',
            )
        if author_type is None:
            author_type = AuthorType.NoType
        song.add_author(author, author_type)


def _has_song_body(remote):
    if _coerce_lyrics_xml(remote.get('lyrics_xml')):
        return True
    return bool(remote.get('verses'))


def _apply_lyrics_and_order(song, remote):
    lyrics = _coerce_lyrics_xml(remote.get('lyrics_xml'))
    if lyrics:
        song.lyrics = lyrics
    elif remote.get('verses'):
        song.lyrics = _build_lyrics_from_verses(remote['verses'])
    else:
        return False
    if remote.get('verse_order'):
        song.verse_order = remote['verse_order']
    return True


def _update_existing_song(manager, song, remote):
    if not _has_song_body(remote):
        return False
    song.title = remote.get('title') or song.title
    song.alternate_title = remote.get('alternate_title') or song.alternate_title
    song.copyright = remote.get('copyright') or song.copyright
    song.ccli_number = remote.get('ccli_number') or song.ccli_number
    if not _apply_lyrics_and_order(song, remote):
        return False
    comments = remote.get('comments') or song.comments
    song.comments = merge_remote_id(comments, remote.get('remote_id'))
    _apply_authors(manager, song, remote.get('authors'))
    _ensure_default_author(manager, song)
    if remote.get('last_modified'):
        try:
            song.last_modified = datetime.fromisoformat(remote['last_modified'].replace('Z', '+00:00'))
        except ValueError:
            pass
    clean_song(manager, song)
    manager.save_object(song)
    return True


def _import_as_new_direct(manager, remote):
    song = Song()
    song.title = remote.get('title') or ''
    song.alternate_title = remote.get('alternate_title') or ''
    song.copyright = remote.get('copyright') or ''
    song.ccli_number = remote.get('ccli_number') or ''
    song.comments = merge_remote_id(remote.get('comments') or '', remote.get('remote_id'))
    if remote.get('tags'):
        song.theme_name = ', '.join(remote['tags'])
    if not _apply_lyrics_and_order(song, remote):
        return None
    _ensure_default_author(manager, song)
    clean_song(manager, song)
    manager.save_object(song)
    return song.id


def _import_as_new(manager, remote):
    if _coerce_lyrics_xml(remote.get('lyrics_xml')):
        return _import_as_new_direct(manager, remote)

    importer = SongImport(manager, file_path='songstats-sync')
    importer.set_defaults()
    importer.title = remote.get('title') or ''
    if not importer.title or not remote.get('verses'):
        return None
    importer.alternate_title = remote.get('alternate_title') or ''
    importer.copyright = remote.get('copyright') or ''
    importer.ccli_number = remote.get('ccli_number') or ''
    importer.comments = merge_remote_id(remote.get('comments') or '', remote.get('remote_id'))
    if remote.get('verse_order'):
        importer.verse_order_list = remote['verse_order'].split()
    for author in remote.get('authors') or []:
        name = (author.get('name') or '').strip()
        if name:
            importer.add_author(name, _author_type_from_api(author.get('type')))
    for verse in remote['verses']:
        importer.add_verse(
            verse.get('text') or '',
            verse.get('def') or 'v',
            verse.get('lang'),
        )
    song_id = importer.finish()
    if song_id and remote.get('last_modified'):
        song = manager.get_object(Song, song_id)
        if song:
            try:
                song.last_modified = datetime.fromisoformat(remote['last_modified'].replace('Z', '+00:00'))
                manager.save_object(song)
            except ValueError:
                pass
    return song_id


def stamp_remote_ids_after_sqlite_bootstrap(manager, settings, on_progress=None):
    """
    After a full SQLite import, link local rows to Mongo ids via public GET /songs/all.
    """
    from contrib.plugins.songstats.lib.apiutil import (
        build_stats_headers,
        get_request_timeouts,
        resolve_public_catalog_url,
    )

    import requests
    from openlp.core.common.httputils import get_proxy_settings

    url = resolve_public_catalog_url(settings)
    if not url:
        return 0
    try:
        response = requests.get(
            url,
            headers=build_stats_headers(settings),
            proxies=get_proxy_settings(),
            timeout=get_request_timeouts(settings),
        )
        if response.status_code >= 400:
            log.warning('Public catalog index HTTP %s', response.status_code)
            return 0
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get('songs'), list):
            remote_items = payload['songs']
        elif isinstance(payload, list):
            remote_items = payload
        else:
            return 0
    except Exception:
        log.exception('Failed to fetch public catalog for remote_id stamping')
        return 0

    stamped = 0
    local_index = _build_local_song_index(manager)
    total = len(remote_items)
    for index, item in enumerate(remote_items):
        if not isinstance(item, dict) or not item.get('id'):
            continue
        remote_id = item['id']
        existing = find_local_song(manager, normalize_master_api_song(item), local_index)
        if not existing:
            existing = find_local_song(manager, {'remote_id': remote_id, 'title': item.get('title')}, local_index)
        if existing and get_remote_id(existing.comments) != remote_id:
            existing.comments = merge_remote_id(existing.comments, remote_id)
            manager.save_object(existing)
            stamped += 1
        if on_progress and (index == 0 or (index + 1) % 25 == 0 or index + 1 == total):
            on_progress(index + 1, total)
    return stamped


def dedupe_songs_after_kwch_sync(manager, on_progress=None):
    """
    Remove duplicate non-temporary songs with the same title (legacy row-wise imports).
    Keeps one row: prefer songstats remote_id, else lowest OpenLP id.
    """
    songs = manager.get_all_objects(Song)
    total = max(len(songs), 1)
    if on_progress:
        on_progress(0, total)
    by_title = {}
    for index, song in enumerate(songs):
        if song.temporary:
            continue
        key = (song.title or '').strip().casefold()
        if not key:
            continue
        by_title.setdefault(key, []).append(song)
        if on_progress and (index == 0 or (index + 1) % 50 == 0 or index + 1 == len(songs)):
            on_progress(index + 1, total)

    removed = 0
    groups = list(by_title.values())
    group_total = max(len(groups), 1)
    for index, group in enumerate(groups):
        if len(group) < 2:
            continue
        with_remote = [s for s in group if get_remote_id(s.comments)]
        if with_remote:
            keep = min(with_remote, key=lambda s: s.id)
        else:
            keep = min(group, key=lambda s: s.id)
        for song in group:
            if song.id == keep.id:
                continue
            manager.delete_object(Song, song.id)
            removed += 1
        if on_progress and (index == 0 or (index + 1) % 25 == 0 or index + 1 == len(groups)):
            on_progress(index + 1, group_total)
    return removed


def apply_remote_deletions(manager, deleted_remote_ids):
    """Remove local songs whose Mongo id was deleted on the master since last sync."""
    if not deleted_remote_ids:
        return 0
    remote_set = set(deleted_remote_ids)
    removed = 0
    for song in manager.get_all_objects(Song):
        if song.temporary:
            continue
        remote_id = get_remote_id(song.comments)
        if remote_id and remote_id in remote_set:
            manager.delete_object(Song, song.id)
            removed += 1
    return removed


def import_remote_catalog(manager, remote_songs, on_progress=None, cancel_check=None):
    stats = ImportStats()
    if remote_songs is None:
        stats.errors += 1
        return stats

    items = [item for item in (remote_songs or []) if isinstance(item, dict)]
    total = len(items)
    local_index = _build_local_song_index(manager)
    for index, item in enumerate(items):
        if cancel_check and cancel_check():
            stats.cancelled = True
            break
        if item.get('lyricsXml') or item.get('versesArray') is not None:
            remote = normalize_master_api_song(item)
        else:
            remote = item
        if not remote or not remote.get('title') or not _has_song_body(remote):
            stats.skipped += 1
            continue
        try:
            existing = find_local_song(manager, remote, local_index)
            if existing:
                if _update_existing_song(manager, existing, remote):
                    stats.updated += 1
                else:
                    stats.skipped += 1
            elif _import_as_new(manager, remote):
                stats.created += 1
            else:
                stats.errors += 1
        except IntegrityError:
            log.exception('Failed to import song %s (database constraint)', remote.get('title'))
            try:
                manager.session.rollback()
            except Exception:
                log.exception('Rollback after import error failed')
            stats.errors += 1
        except Exception:
            log.exception('Failed to import song %s', remote.get('title'))
            try:
                manager.session.rollback()
            except Exception:
                log.exception('Rollback after import error failed')
            stats.errors += 1
        if on_progress:
            on_progress(index + 1, total)
    return stats


def _tags_from_song(song):
    theme = (song.theme_name or '').strip()
    if not theme:
        return None
    return [part.strip() for part in theme.split(',') if part.strip()]


def openlp_song_to_master_dto(song, settings):
    sxml = SongXML()
    verses = []
    for index, (attrs, text) in enumerate(sxml.get_verses(song.lyrics)):
        verse_type = attrs.get('type', 'v')
        label = attrs.get('label', '1')
        original = '{type}{label}'.format(type=verse_type, label=label)
        verses.append({
            'order': index + 1,
            'content': text,
            'label': original,
            'originalLabel': original,
        })
    language = (settings.value('songstats/default language') or 'pl').strip() or 'pl'
    client_id = (settings.value('songstats/church id') or '').strip() or None
    dto = {
        'title': song.title,
        'number': song.alternate_title or song.ccli_number or None,
        'language': language,
        'verses': verses,
        'verseOrder': song.verse_order or None,
        'lyricsXml': song.lyrics,
        'copyright': song.copyright or None,
        'comments': song.comments or None,
        'ccliNumber': song.ccli_number or None,
        'searchLyrics': song.search_lyrics or None,
        'tags': _tags_from_song(song),
        'openlpMapping': {
            'openlpId': song.id,
            'clientId': client_id,
        },
    }
    songbook = (settings.value('songstats/default songbook') or '').strip()
    if songbook:
        # API expects slug string ('pielgrzym', 'zielony', …), not {name: …}
        dto['songbook'] = songbook
    return dto


def build_push_operations(manager, settings, songs_api_base, remote_index):
    """
    Build HTTP operations for Openlp-database: PATCH /songs/:id or POST /songs.

    Never DELETE — removing a song from the master catalog is admin-only on KWCH web.
    remote_index: dict remote_id -> cache item from last pull (optional).
    """
    operations = []
    remote_by_id = remote_index or {}
    local_songs = manager.get_all_objects(Song)
    for song in local_songs:
        if song.temporary:
            continue
        dto = openlp_song_to_master_dto(song, settings)
        remote_id = get_remote_id(song.comments)
        if not remote_id:
            for cache_item in remote_by_id.values():
                if not isinstance(cache_item, dict):
                    continue
                mapping = cache_item.get('openlpMapping') or {}
                if mapping.get('openlpId') == song.id:
                    remote_id = cache_item.get('id')
                    break
        if remote_id and remote_id in remote_by_id:
            url = '{base}/songs/{id}'.format(base=songs_api_base.rstrip('/'), id=remote_id)
            operations.append({'method': 'PATCH', 'url': url, 'body': dto, 'local_id': song.id})
        elif remote_id:
            url = '{base}/songs/{id}'.format(base=songs_api_base.rstrip('/'), id=remote_id)
            operations.append({'method': 'PATCH', 'url': url, 'body': dto, 'local_id': song.id})
        else:
            url = '{base}/songs'.format(base=songs_api_base.rstrip('/'))
            body = dict(dto)
            body.pop('id', None)
            operations.append({'method': 'POST', 'url': url, 'body': body, 'local_id': song.id})
    return operations


def build_push_operation_for_song(manager, settings, songs_api_base, song_id, remote_index=None):
    """Single-song upload after OpenLP edit (POST or PATCH /songs). No DELETE."""
    song = manager.get_object(Song, song_id)
    if not song or song.temporary:
        return None
    remote_by_id = remote_index or {}
    dto = openlp_song_to_master_dto(song, settings)
    remote_id = get_remote_id(song.comments)
    if not remote_id:
        for cache_item in remote_by_id.values():
            if not isinstance(cache_item, dict):
                continue
            mapping = cache_item.get('openlpMapping') or {}
            if mapping.get('openlpId') == song.id:
                remote_id = cache_item.get('id')
                break
    if remote_id:
        url = '{base}/songs/{id}'.format(base=songs_api_base.rstrip('/'), id=remote_id)
        return {'method': 'PATCH', 'url': url, 'body': dto, 'local_id': song.id}
    url = '{base}/songs'.format(base=songs_api_base.rstrip('/'))
    body = dict(dto)
    body.pop('id', None)
    return {'method': 'POST', 'url': url, 'body': body, 'local_id': song.id}


def apply_push_response_ids(manager, results):
    """
    Store MongoDB id in comments after successful POST (results: list of dicts).
    """
    for row in results:
        if row.get('method') != 'POST' or not row.get('remote_id'):
            continue
        song = manager.get_object(Song, row['local_id'])
        if song:
            song.comments = merge_remote_id(song.comments, row['remote_id'])
            manager.save_object(song)


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