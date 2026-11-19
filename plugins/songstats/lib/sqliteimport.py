# -*- coding: utf-8 -*-
"""
Import a remote OpenLP SQLite export (GET /songs/export/sqlite) into the local songs DB.
"""
import logging
import shutil
from pathlib import Path

from sqlalchemy.engine.url import make_url

from openlp.plugins.songs.lib.importers.openlp import OpenLPSongImport

log = logging.getLogger(__name__)

# Row-by-row OpenLPSongImport is only used when merge-append is required.
_PROGRESS_ROW_INTERVAL = 25


class _HeadlessImportProgressBar(object):
    def __init__(self):
        self._maximum = 0
        self._value = 0

    def setMaximum(self, value):
        self._maximum = int(value)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = int(value)


class _HeadlessErrorReport(object):
    def isHidden(self):
        return True

    def setText(self, _text):
        pass


class _HeadlessImportWizard(object):
    """
    OpenLPSongImport.do_import() calls import_wizard.increment_progress_bar when no QProgressDialog
    is passed — the file import wizard normally supplies that. KWCH sync runs headless.
    """

    def __init__(self, on_progress=None):
        self.progress_bar = _HeadlessImportProgressBar()
        self.error_report_text_edit = _HeadlessErrorReport()
        self._on_progress = on_progress

    def increment_progress_bar(self, status_text, increment=1):
        if increment > 0:
            self.progress_bar.setValue(self.progress_bar.value() + increment)
        if not self._on_progress:
            return
        total = max(self.progress_bar._maximum, 1)
        current = self.progress_bar.value()
        if current == total or current == 1 or current % _PROGRESS_ROW_INTERVAL == 0:
            self._on_progress(current, total, status_text)


def _local_songs_db_path(manager):
    if not getattr(manager, 'db_url', None):
        return None
    url = make_url(manager.db_url)
    if url.drivername != 'sqlite' or not url.database:
        return None
    return Path(url.database)


def is_kwch_sqlite_bootstrap(settings):
    """First-time KWCH catalog sync (no stored version after success)."""
    from contrib.plugins.songstats.lib.apiutil import _local_catalog_version_for_pull

    _, use_incremental = _local_catalog_version_for_pull(settings)
    return not use_incremental


def replace_local_songs_database(manager, export_path, on_progress=None):
    """
    Copy the server OpenLP SQLite file over the local songs database (fast bootstrap).
    A ``.sqlite.kwch-backup`` sibling file is kept.
    """
    local_path = _local_songs_db_path(manager)
    export = Path(export_path)
    if local_path is None or not export.is_file():
        raise RuntimeError('Cannot replace songs database — invalid paths')

    def _progress(step, title):
        if on_progress:
            on_progress(step, 4, title)

    _progress(0, 'close')
    bind = manager.session.get_bind()
    db_url = manager.db_url
    try:
        manager.session.commit()
    except Exception:
        log.exception('Commit before songs DB replace failed')
    try:
        manager.session.close()
    except Exception:
        pass
    if bind is not None:
        bind.dispose()

    backup = local_path.with_suffix(local_path.suffix + '.kwch-backup')
    _progress(1, 'backup')
    shutil.copy(local_path, backup)
    _progress(2, 'copy')
    shutil.copy(export, local_path)

    from openlp.plugins.songs.lib import upgrade as songs_upgrade
    from openlp.plugins.songs.lib.db import init_schema
    from openlp.core.db.upgrades import upgrade_db

    _progress(3, 'upgrade')
    try:
        upgrade_db(db_url, songs_upgrade)
    except Exception:
        log.exception('OpenLP songs DB upgrade failed after KWCH SQLite replace')

    manager.session = init_schema(db_url)
    _progress(4, 'open')
    log.info(
        'KWCH replaced local songs DB from export (backup: %s)',
        backup,
    )
    return str(backup)


def import_sqlite_export(manager, sqlite_path, on_progress=None, settings=None):
    """
    KWCH server SQLite export always **replaces** the local songs database file.
    Row-by-row OpenLPSongImport duplicates every song if anything already exists locally.
    """
    path = Path(sqlite_path)
    if not path.is_file():
        raise FileNotFoundError(sqlite_path)

    local_db = _local_songs_db_path(manager)
    if local_db is not None:
        backup = replace_local_songs_database(manager, path, on_progress=on_progress)
        log.info('Finished KWCH SQLite import (file replace) from %s', path)
        return 'replaced:{0}'.format(backup)

    # Non-SQLite songs DB (unusual): fall back to legacy importer.
    log.warning('Songs DB is not SQLite — falling back to row-wise OpenLPSongImport')
    importer = OpenLPSongImport(manager, file_path=path)
    importer.import_wizard = _HeadlessImportWizard(on_progress=on_progress)
    importer.do_import()
    return 'row_import'