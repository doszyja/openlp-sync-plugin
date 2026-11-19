# -*- coding: utf-8 -*-
"""
Song Stats community plugin — live usage stats and sync with OpenLP Database (master API).
"""
import logging
import uuid
from datetime import datetime, timezone

from PyQt5 import QtCore, QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.common.enum import PluginStatus
from openlp.core.lib.plugin import Plugin, StringContent
from openlp.core.lib.ui import create_action
from openlp.core.state import State
from openlp.core.threading import run_thread
from openlp.core.ui.icons import UiIcons

from contrib.plugins.songstats.lib.constants import PLUGIN_DISPLAY_NAME
from contrib.plugins.songstats.lib.defaults import register_songstats_settings_defaults
from contrib.plugins.songstats.lib.apiutil import (
    SYNC_PULL_SQLITE,
    build_auth_headers,
    build_stats_headers,
    get_stats_request_timeouts,
    is_sqlite_dump_pull,
    persist_auth_profile,
    build_presentation_event_payload,
    ensure_openlp_client_id,
    resolve_full_catalog_pull_url,
    resolve_stats_url,
    resolve_sync_urls,
)
from contrib.plugins.songstats.lib.syncdrift import (
    CHOICE_CANCEL,
    CHOICE_DISCARD,
    CHOICE_PUSH,
    prompt_local_drift_resolution,
)
from contrib.plugins.songstats.lib.authdialog import is_auth_expired_message, offer_session_expired_relogin
from contrib.plugins.songstats.lib.catalogstate import (
    REASON_DELETED_LOCAL,
    REASON_EDIT_NOT_PUSHED,
    REASON_EDIT_NO_TOKEN,
    REASON_PUSH_FAILED,
    apply_catalog_version_from_server,
    clear_drift_for_song,
    clear_local_catalog_drift,
    drift_reason,
    get_drift_song_ids_for_push,
    has_local_drift_deletes,
    is_local_catalog_drifted,
    local_catalog_version_for_display,
    mark_local_catalog_drift,
    remove_drift_songs_pushed,
)
from contrib.plugins.songstats.lib.pluginutil import get_remote_id, get_songs_manager
from contrib.plugins.songstats.lib.syncmessages import explain_sync_error

log = logging.getLogger(__name__)

# Full JSON responses are merged row-by-row — redirect to the SQLite dump instead.
_FULL_CATALOG_SQLITE_THRESHOLD = 50


class SongStatsPlugin(Plugin):
    """
    Live song stats plus download sync and per-song upload on OpenLP save.
    """

    def __init__(self):
        super(SongStatsPlugin, self).__init__(
            'songstats',
            settings_tab_class=None,
            version='1.2.0',
        )
        register_songstats_settings_defaults()
        self.weight = 10
        self.icon = UiIcons().song_usage
        self.icon_path = self.icon
        self.sync_songs_action = None
        self.sync_header_widget = None
        self._sync_in_progress = False
        self._sync_cancelled = False
        self._suppress_song_push = False
        self._suppress_live_stats = False
        self._push_in_progress = False
        self._bulk_push_in_progress = False
        self._bulk_push_local_ids = []
        self._pending_edit_push_ids = []
        self._last_edit_push_song_id = None
        self._version_check_in_progress = False
        self._account_profile_fetch_done = False
        self._last_import_summary = ''
        self._remote_index = {}
        self._songs_api_base = ''
        # State module id must match Registry key from class name: SongStatsPlugin → song_stats_plugin
        self._state_name = 'song_stats'
        State().add_service(self._state_name, self.weight, is_plugin=True, requires='songs')
        # Do not call update_pre_conditions here: community plugins may load before Songs → permanent Disabled.
        self.set_status()

    def create_settings_tab(self, parent):
        """Load the settings UI only when OpenLP builds the configure dialog (faster startup)."""
        from contrib.plugins.songstats.lib.songstatstab import SongStatsTab

        self.settings_tab = SongStatsTab(
            parent,
            self.name,
            self.get_string(StringContent.VisibleName)['title'],
            self.icon_path,
        )

    def bootstrap_post_set_up(self):
        """Restore status after Songs registers songs_manager (OpenLP bootstrap order)."""
        if Registry().get('songs_manager') and self.status == PluginStatus.Disabled:
            self.set_status()
        if self.is_active():
            self._ensure_sync_header()
            QtCore.QTimer.singleShot(500, self._refresh_sync_header_display)
            self._prune_stale_version_settings()
            if self.settings.value('songstats/push on edit') is None:
                self.settings.setValue('songstats/push on edit', True)

    def check_pre_conditions(self):
        return Registry().get('songs_manager') is not None

    def add_tools_menu_item(self, tools_menu):
        self.sync_songs_action = create_action(
            tools_menu,
            'songstatsSyncSongs',
            text=translate('SongStatsPlugin', 'Synchronize songs with API'),
            statustip=translate(
                'SongStatsPlugin',
                'Pobierz katalog lub przyrostowe zmiany z serwera KWCH (bez wysyłki lokalnych edycji).',
            ),
            visible=False,
            triggers=self.on_synchronize_songs,
        )
        tools_menu.addAction(self.sync_songs_action)

    def _ensure_sync_header(self):
        if self.sync_header_widget:
            return
        from contrib.plugins.songstats.lib.syncstatusbar import SyncHeaderWidget

        self.sync_header_widget = SyncHeaderWidget(self.main_window)
        self.sync_header_widget.sync_clicked.connect(self.on_synchronize_songs)
        self.sync_header_widget.check_updates_clicked.connect(self.on_check_catalog_updates)
        self.sync_header_widget.cancel_sync_clicked.connect(self.on_cancel_sync)
        self.sync_header_widget.configure_requested.connect(self._on_kwch_configure)
        self.sync_header_widget.login_requested.connect(self._on_kwch_login)
        self.sync_header_widget.logout_requested.connect(self._on_kwch_logout)
        self.sync_header_widget.open_web_requested.connect(self._on_kwch_open_web)
        self.sync_header_widget.about_requested.connect(self._on_kwch_about)
        self._refresh_sync_header_display()

    def _on_kwch_configure(self):
        title = self.get_string(StringContent.VisibleName)['title']
        settings_form = Registry().get('settings_form')
        if settings_form:
            settings_form.exec(starting_tab_name=title)

    def _on_kwch_login(self):
        from contrib.plugins.songstats.lib.openlpauth import login_via_browser
        from openlp.core.threading import ThreadWorker, run_thread

        class LoginWorker(ThreadWorker):
            succeeded = QtCore.pyqtSignal(str)
            failed = QtCore.pyqtSignal(str)

            def __init__(self, settings):
                super().__init__()
                self._settings = settings

            def start(self):
                try:
                    token = login_via_browser(self._settings)
                    self.succeeded.emit(token)
                except Exception as error:
                    self.failed.emit(str(error))
                finally:
                    self.quit.emit()

        worker = LoginWorker(self.settings)
        worker.succeeded.connect(self._on_kwch_login_ok)
        worker.failed.connect(self._on_kwch_login_failed)
        run_thread(worker, 'songstats-header-login-{uid}'.format(uid=uuid.uuid4().hex[:8]), can_start=True)

    def _on_kwch_login_ok(self, token):
        self._account_profile_fetch_done = False
        self.settings.setValue('songstats/api token', token)
        self.settings.setValue('songstats/push on edit', True)
        persist_auth_profile(self.settings, token)
        self._refresh_sync_header_display()
        self.main_window.information_message(
            translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME),
            translate('SongStatsPlugin', 'Zalogowano — token zapisany.'),
        )

    def _on_kwch_login_failed(self, message):
        self.main_window.error_message(
            translate('SongStatsPlugin', 'Logowanie nie powiodło się'),
            message,
        )

    def _on_kwch_logout(self):
        from contrib.plugins.songstats.lib.openlpauth import logout_openlp_session

        logout_openlp_session(self.settings, open_browser=True)
        self._account_profile_fetch_done = False
        self._refresh_sync_header_display()
        self.main_window.information_message(
            translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME),
            translate(
                'SongStatsPlugin',
                'Wylogowano w OpenLP. Sesja JWT usunięta — w przeglądarce otwarto stronę '
                'wylogowania KWCH (bez przekierowania na localhost).',
            ),
        )

    def _on_kwch_open_web(self):
        import webbrowser

        from contrib.plugins.songstats.lib.apiutil import get_web_base

        url = get_web_base(self.settings)
        if url:
            webbrowser.open(url)
        else:
            self.main_window.warning_message(
                translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME),
                translate('SongStatsPlugin', 'Ustaw adres API lub strony w konfiguracji wtyczki.'),
            )

    def _on_kwch_about(self):
        self.main_window.information_message(
            translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME),
            self.about(),
        )

    def toggle_status(self, new_status):
        was_active = self.is_active()
        super(SongStatsPlugin, self).toggle_status(new_status)
        if self.is_active() and not was_active:
            self._ensure_sync_header()
            self._refresh_sync_header_display()
    def initialise(self):
        log.info('Song Stats initialising')
        super(SongStatsPlugin, self).initialise()
        Registry().register_function('slidecontroller_live_started', self.on_live_started)
        Registry().register_function('song_changed', self.on_local_song_saved)
        Registry().register_function('song_deleted', self.on_local_song_deleted)
        if self.sync_songs_action:
            self.sync_songs_action.setVisible(True)
        self._ensure_sync_header()
        self._prune_stale_version_settings()
        ensure_openlp_client_id(self.settings)
        self._refresh_sync_header_display()

    def finalise(self):
        Registry().remove_function('slidecontroller_live_started', self.on_live_started)
        Registry().remove_function('song_changed', self.on_local_song_saved)
        Registry().remove_function('song_deleted', self.on_local_song_deleted)
        if self.sync_songs_action:
            self.sync_songs_action.setVisible(False)
        if self.sync_header_widget:
            self.sync_header_widget.detach()
            self.sync_header_widget = None
        super(SongStatsPlugin, self).finalise()

    def _prune_stale_version_settings(self):
        """
        GET /songs/version is an internal server counter, not a catalog label.
        Do not show master until local db version was stored by a successful import.
        Failed sync must not clear a previously stored local version.
        """
        local = (self.settings.value('songstats/local db version') or '').strip()
        if not local:
            self.settings.remove('songstats/master db version')
            self.settings.remove('songstats/local db version')

    def _parse_catalog_version(self, raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _local_catalog_version(self):
        return self._parse_catalog_version(self.settings.value('songstats/local db version'))

    def _master_catalog_version(self):
        return self._parse_catalog_version(self.settings.value('songstats/master db version'))

    def _catalog_update_available(self):
        master = self._master_catalog_version()
        if master is None:
            return False
        local = self._local_catalog_version()
        if local is None:
            return True
        return master > local

    def _catalog_versions_for_display(self):
        master_raw = (self.settings.value('songstats/master db version') or '').strip()
        local_display = local_catalog_version_for_display(self.settings)
        return master_raw or '', local_display

    def _mark_sync_started(self, message=None):
        self._sync_cancelled = False
        if self.sync_header_widget:
            self.sync_header_widget.show_indeterminate_progress(
                message or translate('SongStatsPlugin', 'Synchronizacja pieśni…')
            )

    def _mark_sync_finished(self, success, version=None):
        self._sync_in_progress = False
        self._sync_cancelled = False
        self._suppress_song_push = False
        self.settings.setValue(
            'songstats/last sync at',
            datetime.now(timezone.utc).isoformat(),
        )
        self.settings.setValue('songstats/last sync status', 'ok' if success else 'error')
        if success and version is not None:
            self.settings.setValue('songstats/local db version', str(version))
            self.settings.setValue('songstats/master db version', str(version))
            clear_local_catalog_drift(self.settings)
        if self.sync_header_widget:
            self.sync_header_widget.hide_progress()
        self._refresh_sync_header_display()
        QtCore.QTimer.singleShot(0, self._flush_pending_edit_push)

    def on_cancel_sync(self):
        if not self._sync_in_progress:
            return
        self._sync_cancelled = True
        if self.sync_header_widget:
            self.sync_header_widget.set_status_text(
                translate('SongStatsPlugin', 'Anulowanie po bieżącym kroku…')
            )

    @staticmethod
    def _push_on_edit_enabled(settings):
        value = settings.value('songstats/push on edit', True)
        if value is False or value == 0:
            return False
        if isinstance(value, str) and value.strip().lower() in ('false', '0', 'no', 'off'):
            return False
        return True

    def _run_after_edit_dialog_closed(self, callback):
        """Edit song form is modal; defer dialogs until after QDialog.accept()."""
        QtCore.QTimer.singleShot(50, callback)

    def _show_save_push_disabled_dialog(self):
        window = self.main_window or Registry().get('main_window')
        if not window:
            return
        window.warning_message(
            translate('SongStatsPlugin', 'Pieśń nie trafi na serwer KWCH'),
            translate(
                'SongStatsPlugin',
                'Pieśń zapisano w OpenLP, ale opcja „Po zapisie wyślij na serwer” jest wyłączona.\n\n'
                'W ustawieniach wtyczki KWCH włącz wysyłkę albo użyj Synchronizuj → Wyślij lokalne.\n\n'
                'Wersja lokalna: ⚠ (poza sync).',
            ),
        )

    def _show_local_delete_dialog(self):
        window = self.main_window or Registry().get('main_window')
        if not window:
            return
        window.warning_message(
            translate('SongStatsPlugin', 'Usunięto tylko lokalnie w OpenLP'),
            translate(
                'SongStatsPlugin',
                'Ta pieśń zniknęła z bazy na tym komputerze.\n\n'
                'Na stronie KWCH nadal może być w katalogu — usunięcie na serwerze '
                'wykonuje wyłącznie administrator w panelu webowym.\n\n'
                'Synchronizacja z serwera może przywrócić tę pieśń do OpenLP.',
            ),
        )

    def _handle_http_auth_failure(self, message):
        if not is_auth_expired_message(message):
            return False
        parent = self._main_window_for_dialog()
        if not parent:
            return True
        offer_session_expired_relogin(parent, self.settings, self._on_kwch_login)
        self._refresh_sync_header_display()
        return True

    def _show_save_skipped_not_logged_in_dialog(self):
        window = self.main_window or Registry().get('main_window')
        if not window:
            log.warning('KWCH: not-logged-in save dialog skipped (main_window unavailable)')
            return
        window.warning_message(
            translate('SongStatsPlugin', 'Pieśń nie zostanie zapisana na stronie KWCH'),
            translate(
                'SongStatsPlugin',
                'Pieśń została zapisana w OpenLP na tym komputerze.\n\n'
                'Na stronie internetowej KWCH (serwerze) nie została zapisana, '
                'ponieważ nie jesteś zalogowany.\n\n'
                'Aby wysyłać zmiany na serwer: menu u góry → Konto → '
                'Zaloguj przez przeglądarkę (Discord).\n\n'
                'Lokalny katalog oznaczono jako poza synchronizacją (⚠ przy wersji lokalnej).',
            ),
        )

    def on_local_song_deleted(self, song_id):
        """Usunięcie w OpenLP jest tylko lokalne — DELETE na serwerze tylko dla admina KWCH."""
        if not self.is_active():
            return
        log.debug(
            'KWCH: pieśń %s usunięta lokalnie w OpenLP — bez żądania DELETE na serwerze',
            song_id,
        )
        mark_local_catalog_drift(self.settings, REASON_DELETED_LOCAL, song_id=song_id)
        self._refresh_sync_header_display()
        self._run_after_edit_dialog_closed(self._show_local_delete_dialog)

    def _enqueue_or_push_song(self, song_id):
        if self._sync_in_progress or self._suppress_song_push:
            log.debug(
                'KWCH: odłożono push pieśni %s (sync=%s suppress=%s)',
                song_id,
                self._sync_in_progress,
                self._suppress_song_push,
            )
            if song_id not in self._pending_edit_push_ids:
                self._pending_edit_push_ids.append(song_id)
            return
        if self._push_in_progress or self._bulk_push_in_progress:
            if song_id not in self._pending_edit_push_ids:
                self._pending_edit_push_ids.append(song_id)
            return
        _, songs_api_base, _ = resolve_sync_urls(self.settings)
        if not songs_api_base:
            window = self._main_window_for_dialog()
            if window:
                window.warning_message(
                    translate('SongStatsPlugin', 'Wysyłka pieśni'),
                    translate(
                        'SongStatsPlugin',
                        'Brak adresu API w ustawieniach KWCH — edycja nie trafi na serwer.',
                    ),
                )
            return
        log.info('KWCH: wysyłam pieśń %s na serwer po zapisie w OpenLP', song_id)
        self._push_song_to_server(song_id, songs_api_base)

    def _flush_pending_edit_push(self):
        if (
            self._push_in_progress
            or self._bulk_push_in_progress
            or self._sync_in_progress
            or self._suppress_song_push
        ):
            return
        if not self._pending_edit_push_ids:
            return
        if not self._has_api_token():
            return
        song_id = self._pending_edit_push_ids.pop(0)
        self._enqueue_or_push_song(song_id)

    def on_local_song_saved(self, song_id):
        if not self.is_active():
            return
        from openlp.plugins.songs.lib.db import Song

        manager = get_songs_manager()
        if not manager or not manager.get_object(Song, song_id):
            log.debug('KWCH: pomijam wysyłkę — pieśń %s już nie istnieje lokalnie', song_id)
            return
        from contrib.plugins.songstats.lib.synchttp import MasterApiPushWorker

        if not self._has_api_token():
            log.debug('KWCH: skip upload — no API token')
            mark_local_catalog_drift(self.settings, REASON_EDIT_NO_TOKEN, song_id=song_id)
            self._refresh_sync_header_display()
            self._run_after_edit_dialog_closed(self._show_save_skipped_not_logged_in_dialog)
            return
        if not self._push_on_edit_enabled(self.settings):
            self.settings.setValue('songstats/push on edit', True)
        self._enqueue_or_push_song(song_id)

    def _push_song_to_server(self, song_id, songs_api_base):
        from openlp.plugins.songs.lib.db import Song

        from contrib.plugins.songstats.lib.songsync import build_push_operation_for_song
        from contrib.plugins.songstats.lib.synchttp import MasterApiPushWorker

        manager = get_songs_manager()
        if not manager:
            return
        try:
            song = manager.get_object(Song, song_id)
            from contrib.plugins.songstats.lib.songsync import ensure_remote_index_for_song

            self._remote_index = ensure_remote_index_for_song(
                self.settings, self._remote_index, song
            )
            operation = build_push_operation_for_song(
                manager, self.settings, songs_api_base, song_id, self._remote_index
            )
        except Exception:
            log.exception('KWCH: could not build push for song %s', song_id)
            return
        if not operation:
            return
        self._last_edit_push_song_id = song_id
        self._push_in_progress = True
        worker = MasterApiPushWorker([operation])
        worker.push_succeeded.connect(self._on_edit_push_succeeded)
        worker.push_failed.connect(self._on_edit_push_failed)
        run_thread(worker, 'songstats-edit-push-{uid}'.format(uid=uuid.uuid4().hex[:8]), can_start=True)

    def _on_edit_push_succeeded(self, post_results, summary):
        from contrib.plugins.songstats.lib.songsync import apply_push_response_ids
        from contrib.plugins.songstats.lib.synchttp import push_summary_had_upload

        self._push_in_progress = False
        manager = get_songs_manager()
        if manager and post_results:
            self._suppress_song_push = True
            try:
                apply_push_response_ids(manager, post_results)
            finally:
                self._suppress_song_push = False
        summary_lower = (summary or '').lower()
        if 'updated=0' in summary_lower and 'created=0' in summary_lower and 'errors=' in summary_lower:
            err_part = summary.split('errors=', 1)[-1].split(',')[0].strip()
            if err_part and err_part != '0':
                self._on_edit_push_failed(
                    translate(
                        'SongStatsPlugin',
                        'Wysyłka po zapisie: nic nie zaktualizowano ({summary}).',
                    ).format(summary=summary)
                )
                return
        if push_summary_had_upload(summary):
            log.info('KWCH: song pushed after local edit (%s)', summary)
            if self._last_edit_push_song_id is not None:
                clear_drift_for_song(self.settings, self._last_edit_push_song_id)
                self._refresh_sync_header_display()
            self._fetch_catalog_version_after_push()
        self._flush_pending_edit_push()

    def _fetch_catalog_version_after_push(self):
        """GET /songs/version after successful PATCH/POST — server bumps catalog version."""
        from contrib.plugins.songstats.lib.synchttp import SongVersionWorker

        worker = SongVersionWorker()
        worker.version_succeeded.connect(self._on_catalog_version_after_push)
        worker.version_failed.connect(self._on_catalog_version_after_push_failed)
        run_thread(
            worker,
            'songstats-post-push-version-{uid}'.format(uid=uuid.uuid4().hex[:8]),
            can_start=True,
        )

    def _on_catalog_version_after_push(self, version):
        apply_catalog_version_from_server(self.settings, version)
        self._refresh_sync_header_display()

    def _on_catalog_version_after_push_failed(self, message):
        log.warning('KWCH: catalog version not refreshed after push: %s', message)

    def _on_edit_push_failed(self, message):
        self._push_in_progress = False
        song_id = self._last_edit_push_song_id
        mark_local_catalog_drift(
            self.settings, REASON_PUSH_FAILED, song_id=song_id
        )
        self._refresh_sync_header_display()
        log.warning('KWCH upload after edit failed: %s', message)
        if self._handle_http_auth_failure(message):
            self._pending_edit_push_ids.clear()
            return
        title, body = explain_sync_error(message)
        self.main_window.warning_message(
            translate('SongStatsPlugin', 'Wysyłka pieśni na serwer nie powiodła się'),
            body or title,
        )
        self._flush_pending_edit_push()

    def _on_import_progress(self, current, total):
        if not self.sync_header_widget:
            return
        self.sync_header_widget.show_progress(
            current,
            total,
            translate('SongStatsPlugin', 'Import pieśni {current}/{total}').format(
                current=current, total=total
            ),
        )
        if self.application:
            self.application.process_events()

    def _format_sync_time(self, iso_ts):
        if not iso_ts:
            return ''
        try:
            parsed = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
            local = parsed.astimezone()
            return local.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return iso_ts[:16]

    def _refresh_sync_header_display(self):
        if not self.sync_header_widget:
            return
        if self._sync_in_progress:
            return
        if self._version_check_in_progress:
            self.sync_header_widget.set_version_checking(True)
            return
        self.sync_header_widget.set_version_checking(False)
        self.sync_header_widget.hide_progress()

        remote_version, local_version = self._catalog_versions_for_display()
        last_at = self.settings.value('songstats/last sync at') or ''
        last_status = self.settings.value('songstats/last sync status') or ''
        from contrib.plugins.songstats.lib.apiutil import has_api_token, read_api_token

        token = read_api_token(self.settings)
        has_token = has_api_token(self.settings)
        identity = {}
        if has_token:
            from contrib.plugins.songstats.lib.apiutil import resolve_account_identity
            identity = resolve_account_identity(self.settings)
        update_available = self._catalog_update_available()

        self.sync_header_widget.set_primary_catalog_action(update_available)
        self.sync_header_widget.update_status_panel(
            remote_version=remote_version,
            local_version=local_version,
            has_token=has_token,
            last_sync_status=last_status or '',
            last_sync_time=self._format_sync_time(last_at) if last_at else '',
            version_checking=self._version_check_in_progress,
            account_name=identity.get('name') or '',
            account_avatar_url=identity.get('avatar_url') or '',
            local_catalog_drift=is_local_catalog_drifted(self.settings),
            local_drift_reason=drift_reason(self.settings),
        )
        if has_token:
            from contrib.plugins.songstats.lib.apiutil import needs_account_profile_from_api

            if needs_account_profile_from_api(identity):
                self._maybe_fetch_account_profile(force=bool(identity.get('avatar_url')))

    def _maybe_fetch_account_profile(self, force=False):
        if self._account_profile_fetch_done and not force:
            return
        self._account_profile_fetch_done = True
        from openlp.core.threading import ThreadWorker, run_thread

        plugin_settings = self.settings

        class ProfileWorker(ThreadWorker):
            done = QtCore.pyqtSignal(dict)

            def __init__(self, settings):
                super().__init__()
                self._settings = settings

            def start(self):
                from contrib.plugins.songstats.lib.apiutil import fetch_identity_from_api
                self.done.emit(fetch_identity_from_api(self._settings) or {})
                self.quit.emit()

        worker = ProfileWorker(plugin_settings)
        worker.done.connect(self._on_account_profile_fetched)
        run_thread(
            worker,
            'songstats-profile-{uid}'.format(uid=uuid.uuid4().hex[:8]),
            can_start=True,
        )

    def _on_account_profile_fetched(self, identity):
        if not identity.get('name') and not identity.get('avatar_url'):
            return
        token = (self.settings.value('songstats/api token') or '').strip()
        if not token:
            return
        persist_auth_profile(self.settings, token, profile=identity)
        self._refresh_sync_header_display()

    def _main_window_for_dialog(self):
        return self.main_window or Registry().get('main_window')

    def _has_api_token(self):
        from contrib.plugins.songstats.lib.apiutil import has_api_token

        return has_api_token(self.settings)

    def _ask_drift_resolution_if_needed(self):
        if not is_local_catalog_drifted(self.settings):
            return True
        parent = self._main_window_for_dialog()
        if not parent:
            return False
        choice = prompt_local_drift_resolution(
            parent, self.settings, self._has_api_token()
        )
        if choice is CHOICE_CANCEL:
            return False
        if choice is CHOICE_PUSH:
            self._push_all_local_songs(self._run_catalog_version_check)
            return False
        if choice is CHOICE_DISCARD:
            self._start_catalog_pull(discard_local=True)
            return False
        return False

    def _push_all_local_songs(self, continuation):
        if (
            self._bulk_push_in_progress
            or self._push_in_progress
            or self._sync_in_progress
        ):
            return
        if not self._has_api_token():
            window = self._main_window_for_dialog()
            if window:
                window.warning_message(
                    translate('SongStatsPlugin', 'Brak logowania'),
                    translate(
                        'SongStatsPlugin',
                        'Wysyłka wymaga zalogowania kontem KWCH (menu Konto).',
                    ),
                )
            return
        manager = get_songs_manager()
        _, songs_api_base, _ = resolve_sync_urls(self.settings)
        if not manager or not songs_api_base:
            return
        from contrib.plugins.songstats.lib.songsync import build_push_operations
        from contrib.plugins.songstats.lib.synchttp import MasterApiPushWorker

        drift_ids = get_drift_song_ids_for_push(self.settings, manager)
        if not drift_ids:
            window = self._main_window_for_dialog()
            if window:
                if has_local_drift_deletes(self.settings):
                    window.information_message(
                        translate('SongStatsPlugin', 'Brak pieśni do wysłania'),
                        translate(
                            'SongStatsPlugin',
                            'Do wysłania nie ma zapisanych edycji — zostały tylko lokalne '
                            'usunięcia (nie idą na serwer). Użyj „Pobierz z serwera”, aby '
                            'wyrównać katalog, albo przywróć pieśni w OpenLP.',
                        ),
                    )
                else:
                    window.information_message(
                        translate('SongStatsPlugin', 'Brak pieśni do wysłania'),
                        translate(
                            'SongStatsPlugin',
                            'Nie ma oznaczonych lokalnych edycji do wysłania.',
                        ),
                    )
            continuation()
            return
        try:
            operations = build_push_operations(
                manager,
                self.settings,
                songs_api_base,
                self._remote_index,
                only_local_ids=drift_ids,
            )
        except Exception:
            log.exception('KWCH: build_push_operations failed')
            return
        if not operations:
            continuation()
            return
        self._bulk_push_local_ids = list(drift_ids)
        self._bulk_push_in_progress = True
        if self.sync_header_widget:
            self.sync_header_widget.set_sync_busy(True)
            self._mark_sync_started(
                translate('SongStatsPlugin', 'Wysyłanie lokalnych pieśni na serwer…')
            )
        worker = MasterApiPushWorker(operations)

        def on_ok(results, summary):
            self._on_bulk_push_finished(results, summary, continuation, failed=False)

        def on_fail(message):
            self._on_bulk_push_finished(None, message, continuation, failed=True)

        worker.push_succeeded.connect(on_ok)
        worker.push_failed.connect(on_fail)
        run_thread(
            worker,
            'songstats-bulk-push-{uid}'.format(uid=uuid.uuid4().hex[:8]),
            can_start=True,
        )

    def _on_bulk_push_finished(self, post_results, summary_or_error, continuation, failed):
        from contrib.plugins.songstats.lib.songsync import apply_push_response_ids
        from contrib.plugins.songstats.lib.synchttp import push_summary_had_upload

        self._bulk_push_in_progress = False
        if self.sync_header_widget:
            self.sync_header_widget.set_sync_busy(False)
            self.sync_header_widget.hide_progress()
        manager = get_songs_manager()
        if failed:
            mark_local_catalog_drift(self.settings, REASON_PUSH_FAILED)
            self._refresh_sync_header_display()
            if self._handle_http_auth_failure(str(summary_or_error)):
                return
            title, body = explain_sync_error(str(summary_or_error))
            window = self._main_window_for_dialog()
            if window:
                window.warning_message(
                    translate('SongStatsPlugin', 'Wysyłka katalogu nie powiodła się'),
                    body or title,
                )
            return
        if manager and post_results:
            apply_push_response_ids(manager, post_results)
        summary = summary_or_error or ''
        if push_summary_had_upload(summary):
            self._fetch_catalog_version_after_push()
        summary_lower = summary.lower()
        if 'errors=' in summary_lower:
            err = summary.split('errors=', 1)[-1].split(',')[0].strip()
            try:
                if int(err) > 0:
                    mark_local_catalog_drift(self.settings, REASON_PUSH_FAILED)
                    self._refresh_sync_header_display()
                    window = self._main_window_for_dialog()
                    if window:
                        window.warning_message(
                            translate('SongStatsPlugin', 'Wysyłka katalogu częściowo nieudana'),
                            translate(
                                'SongStatsPlugin',
                                'Niektóre pieśni nie trafiły na serwer ({summary}).',
                            ).format(summary=summary),
                        )
                    return
            except ValueError:
                pass
        if self._bulk_push_local_ids:
            remove_drift_songs_pushed(self.settings, self._bulk_push_local_ids)
            self._bulk_push_local_ids = []
            self._refresh_sync_header_display()
        window = self._main_window_for_dialog()
        if window and has_local_drift_deletes(self.settings):
            window.information_message(
                translate('SongStatsPlugin', 'Wysłano edycje pieśni'),
                translate(
                    'SongStatsPlugin',
                    'Zmiany tekstów trafiły na serwer (jeśli serwer je przyjął).\n\n'
                    'Lokalne usunięcia pieśni nadal obowiązują tylko w OpenLP — na '
                    'stronie KWCH te pozycje mogły zostać bez zmian. ⚠ przy wersji '
                    'lokalnej może dalej być widoczne.',
                ),
            )
        continuation()

    def _run_catalog_version_check(self):
        if self._sync_in_progress or self._version_check_in_progress:
            return
        from contrib.plugins.songstats.lib.apiutil import resolve_version_url
        from contrib.plugins.songstats.lib.synchttp import SongVersionWorker

        if not resolve_version_url(self.settings):
            window = self._main_window_for_dialog()
            if window:
                window.warning_message(
                    translate('SongStatsPlugin', 'Synchronizacja pieśni nie powiodła się'),
                    translate('SongStatsPlugin', 'Ustaw adres API w konfiguracji wtyczki KWCH.'),
                )
            return

        self._version_check_in_progress = True
        if self.sync_header_widget:
            self.sync_header_widget.set_version_checking(True)
        worker = SongVersionWorker()
        worker.version_succeeded.connect(self._on_version_check_succeeded)
        worker.version_failed.connect(self._on_version_check_failed)
        run_thread(
            worker,
            'songstats-version-check-{uid}'.format(uid=uuid.uuid4().hex[:8]),
            can_start=True,
        )

    def on_check_catalog_updates(self):
        if self._sync_in_progress or self._version_check_in_progress:
            return
        if is_local_catalog_drifted(self.settings):
            if not self._ask_drift_resolution_if_needed():
                return
        self._run_catalog_version_check()

    def _on_version_check_succeeded(self, version):
        self._version_check_in_progress = False
        if self.sync_header_widget:
            self.sync_header_widget.set_version_checking(False)
        if version is not None:
            self.settings.setValue('songstats/master db version', str(version))
        self._refresh_sync_header_display()
        if self._catalog_update_available():
            self.main_window.information_message(
                translate('SongStatsPlugin', 'Dostępna aktualizacja katalogu'),
                translate(
                    'SongStatsPlugin',
                    'Serwer ma wersję {remote}. Lokalnie: {local}.\n\n'
                    'Użyj przycisku Synchronizuj, aby pobrać zmiany.',
                ).format(
                    remote=version,
                    local=self.settings.value('songstats/local db version') or translate(
                        'SongStatsPlugin', 'brak'
                    ),
                ),
            )
        else:
            self.main_window.information_message(
                translate('SongStatsPlugin', 'Katalog aktualny'),
                translate(
                    'SongStatsPlugin',
                    'Lokalna baza ma tę samą wersję katalogu co serwer (v{version}).',
                ).format(version=version),
            )

    def _on_version_check_failed(self, message):
        self._version_check_in_progress = False
        if self.sync_header_widget:
            self.sync_header_widget.set_version_checking(False)
        self._refresh_sync_header_display()
        if self._handle_http_auth_failure(message):
            return
        title, body = explain_sync_error(message)
        self.main_window.warning_message(title, body or message)

    def on_synchronize_songs(self):
        if self._sync_in_progress:
            return
        if is_local_catalog_drifted(self.settings):
            parent = self._main_window_for_dialog()
            if not parent:
                return
            choice = prompt_local_drift_resolution(
                parent, self.settings, self._has_api_token()
            )
            if choice is CHOICE_CANCEL:
                return
            if choice is CHOICE_PUSH:
                self._push_all_local_songs(self._continue_sync_after_bulk_push)
                return
            if choice is CHOICE_DISCARD:
                self._start_catalog_pull(discard_local=True)
                return
        if not self._catalog_update_available():
            self.on_check_catalog_updates()
            return
        self._start_catalog_pull(discard_local=False)

    def _continue_sync_after_bulk_push(self):
        if self._catalog_update_available():
            self._start_catalog_pull(discard_local=False)
        else:
            self._run_catalog_version_check()
            window = self._main_window_for_dialog()
            if window:
                window.information_message(
                    translate('SongStatsPlugin', 'Wysyłka zakończona'),
                    translate(
                        'SongStatsPlugin',
                        'Lokalne pieśni wysłano na serwer. Wersja katalogu została odświeżona.',
                    ),
                )

    def _start_catalog_pull(self, discard_local=False):
        manager = get_songs_manager()
        if manager is None:
            self.main_window.warning_message(
                translate('SongStatsPlugin', 'Songs plugin unavailable'),
                translate('SongStatsPlugin', 'Enable the Songs plugin before synchronizing.'),
            )
            return

        from contrib.plugins.songstats.lib.apiutil import json_pull_requires_auth
        from contrib.plugins.songstats.lib.synchttp import MasterApiPushWorker

        pull_url, songs_api_base, pull_mode = resolve_sync_urls(self.settings)
        if discard_local:
            pull_url, pull_mode = resolve_full_catalog_pull_url(self.settings)
        if json_pull_requires_auth(self.settings) and not MasterApiPushWorker.settings_has_token(
            self.settings
        ):
            self.main_window.warning_message(
                translate('SongStatsPlugin', 'Synchronizacja pieśni nie powiodła się'),
                translate(
                    'SongStatsPlugin',
                    'Przyrostowa synchronizacja wymaga zalogowania kontem na stronie KWCH '
                    '(to samo konto co w przeglądarce).\n\n'
                    'Menu Konto → Zaloguj przez przeglądarkę… lub ustawienia wtyczki KWCH.',
                ),
            )
            return
        if not pull_url:
            self.main_window.warning_message(
                translate('SongStatsPlugin', 'Sync not configured'),
                translate(
                    'SongStatsPlugin',
                    'Set the API base URL in Song Stats settings (e.g. https://your-server/api).',
                ),
            )
            return

        from contrib.plugins.songstats.lib.synchttp import (
            SongSyncPullWorker,
            SongSyncSqlitePullWorker,
        )

        self._sync_in_progress = True
        self._last_import_summary = ''
        self._remote_index = {}
        self._songs_api_base = songs_api_base
        if is_sqlite_dump_pull(pull_url, pull_mode):
            start_msg = translate(
                'SongStatsPlugin',
                'Pobieranie pełnej bazy SQLite (pierwsza synchronizacja)…',
            )
        elif discard_local:
            start_msg = translate(
                'SongStatsPlugin',
                'Pobieranie pełnego katalogu z serwera (odrzucenie lokalnych zmian)…',
            )
        else:
            start_msg = translate('SongStatsPlugin', 'Pobieranie katalogu z serwera…')
        self._mark_sync_started(start_msg)

        if pull_mode == SYNC_PULL_SQLITE:
            worker = SongSyncSqlitePullWorker(pull_url)
            worker.pull_succeeded.connect(self._on_sqlite_pull_succeeded)
            worker.pull_failed.connect(self._on_pull_failed)
        else:
            worker = SongSyncPullWorker(pull_url)
            worker.pull_succeeded.connect(self._on_json_pull_succeeded)
            worker.pull_failed.connect(self._on_pull_failed)

        run_thread(worker, 'songstats-sync-pull-{uid}'.format(uid=uuid.uuid4().hex[:8]), can_start=True)

    def _on_pull_failed(self, message):
        self._mark_sync_finished(False)
        if self._handle_http_auth_failure(message):
            return
        title, body = explain_sync_error(message)
        self.main_window.error_message(title, body)

    def _on_sync_error(self, message):
        """Show operator-friendly error and mark sync state failed."""
        self._on_pull_failed(message)

    def _pull_sqlite_dump_instead(self):
        """Download GET /songs/export/sqlite when a JSON pull would import thousands of rows."""
        from urllib.parse import urljoin

        from contrib.plugins.songstats.lib.apiutil import get_api_base
        from contrib.plugins.songstats.lib.synchttp import SongSyncSqlitePullWorker

        api_base = get_api_base(self.settings)
        if not api_base:
            self._on_pull_failed(translate('SongStatsPlugin', 'API base URL is not configured'))
            return
        pull_url = urljoin(api_base + '/', 'songs/export/sqlite')
        if self.sync_header_widget:
            self.sync_header_widget.show_indeterminate_progress(
                translate(
                    'SongStatsPlugin',
                    'Pełny katalog — pobieranie bazy SQLite z serwera…',
                )
            )
        worker = SongSyncSqlitePullWorker(pull_url)
        worker.pull_succeeded.connect(self._on_sqlite_pull_succeeded)
        worker.pull_failed.connect(self._on_pull_failed)
        run_thread(worker, 'songstats-sync-sqlite-{uid}'.format(uid=uuid.uuid4().hex[:8]), can_start=True)

    def _on_sqlite_pull_succeeded(self, sqlite_path):
        from contrib.plugins.songstats.lib.sqliteimport import import_sqlite_export
        from contrib.plugins.songstats.lib.songsync import stamp_remote_ids_after_sqlite_bootstrap
        from contrib.plugins.songstats.lib.synchttp import SongVersionWorker

        manager = get_songs_manager()
        if manager is None:
            self._on_pull_failed(translate('SongStatsPlugin', 'Songs database is not available.'))
            return
        if self._sync_cancelled:
            self._mark_sync_finished(False)
            return
        def on_sqlite_import_progress(current, total, title=None):
            stage = {
                'close': translate('SongStatsPlugin', 'Zamykanie lokalnej bazy pieśni…'),
                'backup': translate('SongStatsPlugin', 'Kopia zapasowa bazy pieśni…'),
                'copy': translate('SongStatsPlugin', 'Kopiowanie katalogu z serwera…'),
                'upgrade': translate('SongStatsPlugin', 'Aktualizacja schematu bazy…'),
                'open': translate('SongStatsPlugin', 'Otwieranie nowej bazy pieśni…'),
                'replace': translate('SongStatsPlugin', 'Zastępowanie lokalnej bazy pieśni…'),
            }.get(title)
            if stage:
                label = stage
            elif total and total > 1:
                label = translate(
                    'SongStatsPlugin',
                    'Import pieśni {current}/{total}',
                ).format(current=current, total=total)
            else:
                label = translate('SongStatsPlugin', 'Import bazy pieśni…')
            if self.sync_header_widget:
                self.sync_header_widget.show_progress(current, total or 0, label)
            if self.application:
                self.application.process_events()

        if self.sync_header_widget:
            self.sync_header_widget.show_progress(
                0,
                4,
                translate('SongStatsPlugin', 'Import dużej bazy pieśni…'),
            )
        if self.application:
            self.application.process_events()

        try:
            mode = import_sqlite_export(
                manager,
                sqlite_path,
                on_progress=on_sqlite_import_progress,
                settings=self.settings,
            )
        except Exception as error:
            log.exception('SQLite import failed')
            self._on_pull_failed(str(error))
            return
        if self._sync_cancelled:
            self._mark_sync_finished(False)
            return

        def on_post_import_progress(current, total, label):
            if self.sync_header_widget:
                self.sync_header_widget.show_progress(current, total, label)
            if self.application:
                self.application.process_events()

        from contrib.plugins.songstats.lib.songsync import dedupe_songs_after_kwch_sync

        deduped = 0
        try:
            on_post_import_progress(
                0,
                1,
                translate('SongStatsPlugin', 'Usuwanie duplikatów pieśni…'),
            )
            deduped = dedupe_songs_after_kwch_sync(
                manager,
                on_progress=lambda current, total: on_post_import_progress(
                    current,
                    total,
                    translate(
                        'SongStatsPlugin',
                        'Usuwanie duplikatów {current}/{total}',
                    ).format(current=current, total=total),
                ),
            )
        except Exception:
            log.exception('Duplicate song cleanup after SQLite import failed')
        stamped = 0
        try:
            on_post_import_progress(
                0,
                1,
                translate('SongStatsPlugin', 'Pobieranie indeksu katalogu serwera…'),
            )
            stamped, link_index = stamp_remote_ids_after_sqlite_bootstrap(
                manager,
                self.settings,
                on_progress=lambda current, total: on_post_import_progress(
                    current,
                    total,
                    translate(
                        'SongStatsPlugin',
                        'Powiązanie pieśni {current}/{total}',
                    ).format(current=current, total=total),
                ),
            )
            if link_index:
                self._remote_index.update(link_index)
        except Exception:
            log.exception('Remote id stamping after SQLite import failed')
        self._last_import_summary = (
            '{mode}, deduped={deduped}, remote_ids={stamped}'.format(
                mode=mode if mode else 'sqlite_import',
                deduped=deduped,
                stamped=stamped,
            )
        )
        on_post_import_progress(
            0,
            0,
            translate('SongStatsPlugin', 'Odświeżanie listy pieśni…'),
        )
        Registry().execute('songs_load_list')
        self._reload_displayed_songs()

        version_worker = SongVersionWorker()
        version_worker.version_succeeded.connect(self._complete_sqlite_sync)
        version_worker.version_failed.connect(self._complete_sqlite_sync_version_failed)
        run_thread(
            version_worker,
            'songstats-sqlite-version-{uid}'.format(uid=uuid.uuid4().hex[:8]),
            can_start=True,
        )

    def _complete_sqlite_sync_version_failed(self, _message):
        self._complete_sqlite_sync(None)

    def _complete_sqlite_sync(self, version):
        self._mark_sync_finished(True, version=version)
        extra = ''
        if version is None:
            extra = '\n\n' + translate(
                'SongStatsPlugin',
                'Nie udało się odczytać wersji katalogu (GET /songs/version). '
                'Kolejna synchronizacja może pobrać pełny katalog.',
            )
        self.main_window.information_message(
            translate('SongStatsPlugin', 'Song sync complete'),
            translate(
                'SongStatsPlugin',
                'Import bazy SQLite z serwera KWCH.\n\n{summary}{extra}'.format(
                    summary=self._last_import_summary,
                    extra=extra,
                ),
            ),
        )

    def _on_json_pull_succeeded(self, remote_songs, version, deleted_ids=None, incremental_full=False):
        from contrib.plugins.songstats.lib.songsync import (
            apply_remote_deletions,
            import_remote_catalog,
        )

        if self._sync_cancelled:
            self._mark_sync_finished(False)
            return

        song_count = len(remote_songs or [])
        if incremental_full or song_count >= _FULL_CATALOG_SQLITE_THRESHOLD:
            log.info(
                'KWCH sync: %s songs in JSON response — switching to SQLite dump',
                song_count,
            )
            self._pull_sqlite_dump_instead()
            return

        manager = get_songs_manager()
        if manager is None:
            self._on_pull_failed(translate('SongStatsPlugin', 'Songs database is not available.'))
            return

        self._remote_index = {}
        for item in remote_songs or []:
            if isinstance(item, dict) and item.get('id'):
                self._remote_index[item['id']] = item
                mapping = item.get('openlpMapping') or {}
                openlp_id = mapping.get('openlpId')
                if openlp_id is not None:
                    self._remote_index['openlp:{0}'.format(openlp_id)] = item

        self._suppress_song_push = True
        deleted_ids = deleted_ids or []
        removed = 0
        if deleted_ids:
            try:
                removed = apply_remote_deletions(manager, deleted_ids)
            except Exception as error:
                log.exception('Remote deletions failed')
                self._on_sync_error(
                    translate('SongStatsPlugin', 'Usuwanie pieśni nie powiodło się: {err}').format(err=error)
                )
                return

        total = len(remote_songs or [])
        if self.sync_header_widget:
            mode_note = ''
            if incremental_full:
                mode_note = translate('SongStatsPlugin', ' (pełny katalog — brak dziennika zmian)')
            self.sync_header_widget.show_progress(
                0,
                total,
                translate('SongStatsPlugin', 'Import pieśni 0/{total}{note}').format(
                    total=total, note=mode_note
                ),
            )
        try:
            stats = import_remote_catalog(
                manager,
                remote_songs,
                on_progress=self._on_import_progress,
                cancel_check=lambda: self._sync_cancelled,
            )
            if deleted_ids:
                stats.deleted = removed
        except Exception as error:
            log.exception('Song catalog import failed after pull')
            self._on_sync_error(
                translate('SongStatsPlugin', 'Import catalog failed: {err}').format(err=error)
            )
            return
        from contrib.plugins.songstats.lib.songsync import dedupe_songs_after_kwch_sync

        deduped = 0
        try:
            deduped = dedupe_songs_after_kwch_sync(manager)
        except Exception:
            log.exception('Duplicate song cleanup after JSON import failed')

        version_note = ''
        if version is not None:
            version_note = ', server_version={v}'.format(v=version)
        dedupe_note = ', deduped={0}'.format(deduped) if deduped else ''
        self._last_import_summary = stats.summary() + version_note + dedupe_note
        Registry().execute('songs_load_list')
        self._reload_displayed_songs()

        if stats.cancelled or self._sync_cancelled:
            self._mark_sync_finished(False)
            self.main_window.information_message(
                translate('SongStatsPlugin', 'Synchronizacja przerwana'),
                translate(
                    'SongStatsPlugin',
                    'Import zatrzymany przez użytkownika.\n\n{summary}'.format(
                        summary=self._last_import_summary
                    ),
                ),
            )
            return

        self._mark_sync_finished(True, version=version)
        self.main_window.information_message(
            translate('SongStatsPlugin', 'Song sync complete'),
            translate('SongStatsPlugin', 'Import: {summary}').format(summary=self._last_import_summary),
        )

    def _songs_media_item(self):
        plugin_manager = Registry().get('plugin_manager')
        if not plugin_manager:
            return None
        songs_plugin = plugin_manager.get_plugin_by_name('songs')
        if not songs_plugin:
            return None
        return getattr(songs_plugin, 'media_item', None)

    def _find_song_for_service_item(self, manager, service_item):
        from openlp.plugins.songs.lib.db import Song

        song_id = getattr(service_item, 'edit_id', None)
        if song_id:
            song = manager.get_object(Song, song_id)
            if song and not getattr(song, 'temporary', False):
                return song
        title = (getattr(service_item, 'title', None) or '').strip()
        if not title:
            audit = getattr(service_item, 'audit', None) or []
            if audit:
                title = (audit[0] or '').strip()
        if not title:
            return None
        matches = manager.get_all_objects(Song, Song.title == title) or []
        matches = [song for song in matches if not getattr(song, 'temporary', False)]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        remote_id = get_remote_id(getattr(service_item, 'notes', None) or '')
        if remote_id:
            for song in matches:
                if get_remote_id(getattr(song, 'comments', None) or '') == remote_id:
                    return song
        return min(matches, key=lambda song: song.id or 0)

    def _reload_controller_song(self, controller, media_item, manager):
        if not controller:
            return
        service_item = getattr(controller, 'service_item', None)
        if not service_item or getattr(service_item, 'name', None) != 'songs':
            return
        song = self._find_song_for_service_item(manager, service_item)
        if not song:
            log.debug(
                'Song Stats: no matching song to reload on %s',
                getattr(controller, 'type_prefix', ''),
            )
            return
        from openlp.core.lib import ServiceItemContext

        list_item = media_item.create_item_from_id(song.id)
        context = ServiceItemContext.Live if getattr(controller, 'is_live', False) else ServiceItemContext.Preview
        new_item = media_item.build_service_item(list_item, context=context)
        if not new_item:
            log.warning(
                'Song Stats: failed to rebuild song %s for %s',
                song.id,
                getattr(controller, 'type_prefix', ''),
            )
            return
        slide_no = getattr(controller, 'selected_row', 0) or 0
        preview_widget = getattr(controller, 'preview_widget', None)
        if preview_widget is not None:
            try:
                slide_no = preview_widget.current_slide_number()
            except Exception:
                pass
        controller.selected_row = max(0, slide_no)
        controller.refresh_service_item(new_item)

    def _reload_displayed_songs(self):
        """Rebuild the song currently on Preview and Live so catalog changes show immediately."""
        media_item = self._songs_media_item()
        manager = get_songs_manager()
        if not media_item or not manager:
            return
        self._suppress_live_stats = True
        try:
            self._reload_controller_song(self.preview_controller, media_item, manager)
            self._reload_controller_song(self.live_controller, media_item, manager)
        except Exception:
            log.exception('Song Stats: failed to reload preview/live songs after sync')
        finally:
            self._suppress_live_stats = False

    def on_live_started(self, items):
        """Fire-and-forget POST /presentation-events; never blocks Live or shows errors."""
        try:
            self._enqueue_presentation_event(items)
        except Exception:
            log.debug('Song Stats: could not enqueue presentation event', exc_info=True)

    def _enqueue_presentation_event(self, items):
        if not self.is_active() or self._suppress_live_stats:
            return
        if not items:
            return
        service_item = items[0]
        if service_item.name != 'songs':
            return

        url = resolve_stats_url(self.settings)
        if not url:
            log.debug('Song Stats: stats URL is empty (configure API base)')
            return

        ensure_openlp_client_id(self.settings)

        from contrib.plugins.songstats.lib.apiclient import SongStatsPostWorker

        audit = service_item.audit or []
        title = audit[0] if audit else service_item.title
        mongo_id = None
        from openlp.plugins.songs.lib.db import Song

        manager = get_songs_manager()
        if manager:
            song = manager.get_object(Song, service_item.edit_id)
            if song:
                mongo_id = get_remote_id(song.comments)

        presented_at = datetime.now(timezone.utc).isoformat()
        song_metadata = {
            'authors': audit[1] if len(audit) > 1 else '',
            'copyright': audit[2] if len(audit) > 2 else '',
            'ccli': audit[3] if len(audit) > 3 else '',
        }
        payload = build_presentation_event_payload(
            self.settings,
            openlp_song_id=service_item.edit_id,
            mongo_song_id=mongo_id,
            title=title,
            service_item_title=service_item.title,
            presented_at=presented_at,
            song_metadata=song_metadata,
        )

        headers = build_stats_headers(self.settings)
        worker = SongStatsPostWorker(
            url,
            payload,
            headers,
            get_stats_request_timeouts(self.settings),
        )
        thread_name = 'songstats-live-{uid}'.format(uid=uuid.uuid4().hex[:12])
        try:
            run_thread(worker, thread_name, can_start=True)
        except KeyError:
            log.debug('Song Stats: stats thread name collision, skipping duplicate POST')

    @staticmethod
    def about():
        return translate(
            'SongStatsPlugin',
            '<strong>{name}</strong><br />'
            'Syncs with OpenLP Database (GET /songs/all-openlp, POST/PATCH /songs) and optional live stats POST.',
        ).format(name=PLUGIN_DISPLAY_NAME)

    def set_plugin_text_strings(self):
        self.text_strings[StringContent.Name] = {
            'singular': translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME, 'name singular'),
            'plural': translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME, 'name plural'),
        }
        self.text_strings[StringContent.VisibleName] = {
            'title': translate('SongStatsPlugin', PLUGIN_DISPLAY_NAME, 'container title'),
        }