# -*- coding: utf-8 -*-
"""
Local catalog drift: OpenLP DB diverged from last synced server state without
changing the stored catalog version counter (used for incremental pull).

Set when e.g. local delete, failed push, or edit without upload. Cleared after a
successful catalog import from the server.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

DRIFT_KEY = 'songstats/local catalog drift'
DRIFT_SINCE_KEY = 'songstats/local drift since'
DRIFT_REASON_KEY = 'songstats/local drift reason'

# Stored version string suffix in UI only (not in QSettings version keys).
DRIFT_DISPLAY_SUFFIX = '⚠'

REASON_DELETED_LOCAL = 'deleted_local'
REASON_EDIT_NO_TOKEN = 'edit_no_token'
REASON_EDIT_NOT_PUSHED = 'edit_not_pushed'
REASON_PUSH_FAILED = 'push_failed'


def is_local_catalog_drifted(settings):
    raw = settings.value(DRIFT_KEY)
    if raw is None or raw == '':
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def mark_local_catalog_drift(settings, reason=''):
    settings.setValue(DRIFT_KEY, True)
    settings.setValue(DRIFT_SINCE_KEY, datetime.now(timezone.utc).isoformat())
    if reason:
        settings.setValue(DRIFT_REASON_KEY, str(reason))
    log.info('KWCH: local catalog drift marked (%s)', reason or 'unspecified')


def clear_local_catalog_drift(settings):
    settings.remove(DRIFT_KEY)
    settings.remove(DRIFT_SINCE_KEY)
    settings.remove(DRIFT_REASON_KEY)
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