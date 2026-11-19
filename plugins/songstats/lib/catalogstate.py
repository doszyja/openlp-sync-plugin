# -*- coding: utf-8 -*-
"""
Local catalog drift: OpenLP DB diverged from last synced server state without
changing the stored catalog version counter (used for incremental pull).

Set when e.g. local delete, failed push, or edit without upload. Cleared after a
successful catalog import from the server.
"""
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

DRIFT_KEY = 'songstats/local catalog drift'
DRIFT_SINCE_KEY = 'songstats/local drift since'
DRIFT_REASON_KEY = 'songstats/local drift reason'
DRIFT_SONG_IDS_KEY = 'songstats/drift song ids'
DRIFT_HAS_DELETES_KEY = 'songstats/local drift has deletes'

# Stored version string suffix in UI only (not in QSettings version keys).
DRIFT_DISPLAY_SUFFIX = '⚠'

REASON_DELETED_LOCAL = 'deleted_local'
REASON_EDIT_NO_TOKEN = 'edit_no_token'
REASON_EDIT_NOT_PUSHED = 'edit_not_pushed'
REASON_PUSH_FAILED = 'push_failed'


def _read_int_list(settings, key):
    raw = settings.value(key)
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        items = raw
    else:
        text = str(raw).strip()
        if not text:
            return []
        try:
            items = json.loads(text)
        except ValueError:
            items = []
    result = []
    for item in items:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _write_int_list(settings, key, values):
    unique = sorted(set(int(v) for v in values))
    settings.setValue(key, json.dumps(unique))


def is_local_catalog_drifted(settings):
    raw = settings.value(DRIFT_KEY)
    if raw is None or raw == '':
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def has_local_drift_deletes(settings):
    raw = settings.value(DRIFT_HAS_DELETES_KEY)
    if raw is None or raw == '':
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def get_drift_song_ids(settings):
    return _read_int_list(settings, DRIFT_SONG_IDS_KEY)


def get_drift_song_ids_for_push(settings, manager):
    """OpenLP song ids that still exist locally and should be bulk-pushed."""
    if manager is None:
        return []
    from openlp.plugins.songs.lib.db import Song

    ids = []
    for song_id in get_drift_song_ids(settings):
        if manager.get_object(Song, song_id):
            ids.append(song_id)
    return ids


def mark_local_catalog_drift(settings, reason='', song_id=None):
    settings.setValue(DRIFT_KEY, True)
    settings.setValue(DRIFT_SINCE_KEY, datetime.now(timezone.utc).isoformat())
    if reason:
        settings.setValue(DRIFT_REASON_KEY, str(reason))
    if reason == REASON_DELETED_LOCAL:
        settings.setValue(DRIFT_HAS_DELETES_KEY, True)
    elif song_id is not None:
        try:
            sid = int(song_id)
        except (TypeError, ValueError):
            sid = None
        if sid is not None:
            ids = get_drift_song_ids(settings)
            if sid not in ids:
                ids.append(sid)
                _write_int_list(settings, DRIFT_SONG_IDS_KEY, ids)
    log.info('KWCH: local catalog drift marked (%s)', reason or 'unspecified')


def clear_drift_for_song(settings, song_id):
    try:
        sid = int(song_id)
    except (TypeError, ValueError):
        return
    ids = [i for i in get_drift_song_ids(settings) if i != sid]
    if ids:
        _write_int_list(settings, DRIFT_SONG_IDS_KEY, ids)
    else:
        settings.remove(DRIFT_SONG_IDS_KEY)
    _reconcile_drift_flag(settings)


def remove_drift_songs_pushed(settings, local_ids):
    if not local_ids:
        return
    remove = set(int(i) for i in local_ids)
    ids = [i for i in get_drift_song_ids(settings) if i not in remove]
    if ids:
        _write_int_list(settings, DRIFT_SONG_IDS_KEY, ids)
    else:
        settings.remove(DRIFT_SONG_IDS_KEY)
    _reconcile_drift_flag(settings)


def _reconcile_drift_flag(settings):
    if get_drift_song_ids(settings) or has_local_drift_deletes(settings):
        return
    settings.remove(DRIFT_KEY)
    settings.remove(DRIFT_SINCE_KEY)
    settings.remove(DRIFT_REASON_KEY)


def clear_local_catalog_drift(settings):
    settings.remove(DRIFT_KEY)
    settings.remove(DRIFT_SINCE_KEY)
    settings.remove(DRIFT_REASON_KEY)
    settings.remove(DRIFT_SONG_IDS_KEY)
    settings.remove(DRIFT_HAS_DELETES_KEY)
    log.debug('KWCH: local catalog drift cleared')


def local_catalog_version_for_display(settings):
    """Catalog version for UI; appends ⚠ when locally drifted (counter unchanged)."""
    raw = (settings.value('songstats/local db version') or '').strip()
    if not raw:
        return ''
    if is_local_catalog_drifted(settings):
        if raw.endswith(DRIFT_DISPLAY_SUFFIX):
            return raw
        return '{0}{1}'.format(raw, DRIFT_DISPLAY_SUFFIX)
    return raw


def strip_drift_suffix(version_display):
    text = (version_display or '').strip()
    for suffix in (DRIFT_DISPLAY_SUFFIX, '†'):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def drift_reason(settings):
    return (settings.value(DRIFT_REASON_KEY) or '').strip()


def apply_catalog_version_from_server(settings, version):
    """Align local/master catalog counters after server bumped version (e.g. PATCH push)."""
    if version is None:
        return
    text = str(version).strip()
    if not text:
        return
    settings.setValue('songstats/local db version', text)
    settings.setValue('songstats/master db version', text)
    log.info('KWCH: catalog version synced from server -> %s', text)