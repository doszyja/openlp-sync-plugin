# -*- coding: utf-8 -*-
"""
Settings tab for the KWCH Swietochlowice plugin.
"""
import uuid

from PyQt5 import QtCore, QtWidgets

from openlp.core.common.enum import PluginStatus
from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.lib.settingstab import SettingsTab
from openlp.core.threading import run_thread, ThreadWorker

from contrib.plugins.songstats.lib.apiutil import (
    DEFAULT_API_BASE,
    SYNC_PULL_JSON,
    SYNC_PULL_SQLITE,
    clear_auth_session,
    persist_auth_profile,
)
from contrib.plugins.songstats.lib.constants import PLUGIN_DISPLAY_NAME


class SongStatsTab(SettingsTab):
    """
    Configure OpenLP Database master API, stats, and song sync.
    """

    def _setup(self):
        """Defer heavy UI until the user opens Configure OpenLP (faster application startup)."""
        self._ui_ready = False
        # SettingsTab.resizeEvent needs left_column / right_column even before tab_visible.
        SettingsTab.setup_ui(self)
        self.right_column.hide()

    def _ensure_ui(self):
        if self._ui_ready:
            return
        self.setup_ui()
        self.retranslate_ui()
        self.initialise()
        self._ui_ready = True

    def tab_visible(self):
        self._ensure_ui()
        self.load()

    def setup_ui(self):
        if getattr(self, '_content', None) is not None:
            return
        self.setObjectName('SongStatsTab')
        self.right_column.hide()

        scroll = QtWidgets.QScrollArea(self.left_column)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setToolTip('')
        self.left_layout.addWidget(scroll)

        self._content = QtWidgets.QWidget()
        scroll.setWidget(self._content)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(6, 6, 8, 8)
        content_layout.setAlignment(QtCore.Qt.AlignTop)

        self.power_group_box = QtWidgets.QGroupBox(self._content)
        content_layout.addWidget(self.power_group_box)
        power_v = QtWidgets.QVBoxLayout(self.power_group_box)
        power_form = QtWidgets.QFormLayout()
        power_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        power_form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.plugin_status_label = QtWidgets.QLabel(self.power_group_box)
        self.plugin_status_combo = QtWidgets.QComboBox(self.power_group_box)
        self.plugin_status_combo.setMinimumWidth(220)
        self.plugin_status_combo.addItem('Nieaktywny', PluginStatus.Inactive)
        self.plugin_status_combo.addItem('Aktywny', PluginStatus.Active)
        power_form.addRow(self.plugin_status_label, self.plugin_status_combo)
        power_v.addLayout(power_form)

        self.api_group_box = QtWidgets.QGroupBox(self._content)
        content_layout.addWidget(self.api_group_box)
        api_v = QtWidgets.QVBoxLayout(self.api_group_box)

        self.api_layout = QtWidgets.QFormLayout()
        self.api_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.api_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.api_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        self.api_base_url_label = QtWidgets.QLabel(self.api_group_box)
        self.api_base_url_line_edit = QtWidgets.QLineEdit(self.api_group_box)
        self.api_base_url_line_edit.setPlaceholderText('https://piesni.example.pl/api')
        self.api_layout.addRow(self.api_base_url_label, self.api_base_url_line_edit)

        self.api_token_label = QtWidgets.QLabel(self.api_group_box)
        self.api_token_line_edit = QtWidgets.QLineEdit(self.api_group_box)
        self.api_token_line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.api_token_line_edit.setPlaceholderText('Wypełni się po zalogowaniu')
        self.api_layout.addRow(self.api_token_label, self.api_token_line_edit)

        self.default_language_label = QtWidgets.QLabel(self.api_group_box)
        self.default_language_line_edit = QtWidgets.QLineEdit(self.api_group_box)
        self.default_language_line_edit.setMaxLength(8)
        self.default_language_line_edit.setMaximumWidth(80)
        self.api_layout.addRow(self.default_language_label, self.default_language_line_edit)

        self.timeout_label = QtWidgets.QLabel(self.api_group_box)
        self.timeout_spin_box = QtWidgets.QSpinBox(self.api_group_box)
        self.timeout_spin_box.setRange(1, 300)
        self.timeout_spin_box.setSuffix(' s')
        self.timeout_spin_box.setMaximumWidth(100)
        self.api_layout.addRow(self.timeout_label, self.timeout_spin_box)
        api_v.addLayout(self.api_layout)

        login_row = QtWidgets.QHBoxLayout()
        self.login_button = QtWidgets.QPushButton(self.api_group_box)
        self.login_button.clicked.connect(self.on_browser_login)
        self.logout_button = QtWidgets.QPushButton(self.api_group_box)
        self.logout_button.clicked.connect(self.on_logout)
        self.clear_cache_button = QtWidgets.QPushButton(self.api_group_box)
        self.clear_cache_button.clicked.connect(self.on_clear_cache)
        login_row.addWidget(self.login_button, 0)
        login_row.addWidget(self.logout_button, 0)
        login_row.addWidget(self.clear_cache_button, 0)
        login_row.addStretch(1)
        api_v.addLayout(login_row)
        self.login_status_label = QtWidgets.QLabel(self.api_group_box)
        self.login_status_label.setWordWrap(True)
        self.login_status_label.setStyleSheet('color: palette(mid); margin: 0;')
        api_v.addWidget(self.login_status_label)

        self.sync_group_box = QtWidgets.QGroupBox(self._content)
        content_layout.addWidget(self.sync_group_box)
        sync_v = QtWidgets.QVBoxLayout(self.sync_group_box)
        self.push_on_edit_check_box = QtWidgets.QCheckBox(self.sync_group_box)
        sync_v.addWidget(self.push_on_edit_check_box)
        self.delete_hint_label = QtWidgets.QLabel(self.sync_group_box)
        self.delete_hint_label.setWordWrap(True)
        self.delete_hint_label.setStyleSheet('color: palette(mid); margin: 0;')
        sync_v.addWidget(self.delete_hint_label)

        self.sync_layout = QtWidgets.QFormLayout()
        self.sync_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.sync_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.sync_pull_mode_label = QtWidgets.QLabel(self.sync_group_box)
        self.sync_pull_mode_combo = QtWidgets.QComboBox(self.sync_group_box)
        self.sync_pull_mode_combo.addItem('JSON — scalanie (zalecane)', SYNC_PULL_JSON)
        self.sync_pull_mode_combo.addItem('SQLite — pełny eksport', SYNC_PULL_SQLITE)
        self.sync_layout.addRow(self.sync_pull_mode_label, self.sync_pull_mode_combo)
        sync_v.addLayout(self.sync_layout)

        content_layout.addStretch(1)

    def resizeEvent(self, event=None):
        if not hasattr(self, 'right_column'):
            return QtWidgets.QWidget.resizeEvent(self, event)
        if self.right_column.isHidden():
            if event:
                QtWidgets.QWidget.resizeEvent(self, event)
            width = self.width() - self.tab_layout.spacing() - (
                self.tab_layout.contentsMargins().left()
                + self.tab_layout.contentsMargins().right()
            )
            self.left_column.setFixedWidth(max(width, 0))
            return
        super().resizeEvent(event)

    def retranslate_ui(self):
        title = translate('SongStatsPlugin.SongStatsTab', 'Wtyczka {name}').format(name=PLUGIN_DISPLAY_NAME)
        self.power_group_box.setTitle(title)
        self.plugin_status_label.setText(translate('SongStatsPlugin.SongStatsTab', 'Status:'))

        self.api_group_box.setTitle(
            translate('SongStatsPlugin.SongStatsTab', 'Serwer pieśni KWCH')
        )
        self.api_base_url_label.setText(translate('SongStatsPlugin.SongStatsTab', 'Adres API:'))
        self.api_token_label.setText(translate('SongStatsPlugin.SongStatsTab', 'Token (JWT):'))
        self.default_language_label.setText(translate('SongStatsPlugin.SongStatsTab', 'Język pieśni:'))
        self.timeout_label.setText(translate('SongStatsPlugin.SongStatsTab', 'Limit czasu:'))
        self.login_button.setText(
            translate('SongStatsPlugin.SongStatsTab', 'Zaloguj (Discord)')
        )
        self.logout_button.setText(
            translate('SongStatsPlugin.SongStatsTab', 'Wyloguj')
        )
        self.clear_cache_button.setText(
            translate('SongStatsPlugin.SongStatsTab', 'Wyczyść cache')
        )
        self.clear_cache_button.setToolTip(
            translate(
                'SongStatsPlugin.SongStatsTab',
                'Usuwa zapamiętane wersje katalogu, datę synchronizacji i profil '
                '(nazwa, avatar). Nie wylogowuje i nie kasuje pieśni.',
            )
        )

        self.sync_group_box.setTitle(translate('SongStatsPlugin.SongStatsTab', 'Synchronizacja pieśni'))
        self.push_on_edit_check_box.setText(
            translate(
                'SongStatsPlugin.SongStatsTab',
                'Od razu po zapisie pieśni wyślij edycję na serwer KWCH',
            )
        )
        self.push_on_edit_check_box.setToolTip(
            translate(
                'SongStatsPlugin.SongStatsTab',
                'Włączone (zalecane): po Zapisz w edytorze pieśni natychmiast PATCH/POST '
                'na API (wymaga logowania). Wyłączone: tylko OpenLP + ⚠.',
            )
        )
        self.delete_hint_label.setText(
            translate(
                'SongStatsPlugin.SongStatsTab',
                'Usunięcie pieśni w OpenLP nie usuwa jej na serwerze — tylko administrator '
                'może skasować pieśń w panelu KWCH. Lokalne zmiany bez wysyłki: ⚠ przy wersji lokalnej.',
            )
        )
        self.sync_pull_mode_label.setText(translate('SongStatsPlugin.SongStatsTab', 'Tryb pobierania:'))

    def _update_login_buttons(self, token):
        logged_in = bool((token or '').strip())
        self.logout_button.setEnabled(logged_in)
        self.login_button.setEnabled(True)
        if logged_in:
            self.login_status_label.setText(
                translate('SongStatsPlugin.SongStatsTab', 'Zalogowano.')
            )
        else:
            self.login_status_label.setText(
                translate(
                    'SongStatsPlugin.SongStatsTab',
                    'Nie zalogowano — synchronizacja przyrostowa i wysyłka pieśni wymagają '
                    'konta z logowania na stronie KWCH.',
                )
            )

    def load(self):
        self._ensure_ui()
        api_base = (self.settings.value('songstats/api base url') or '').strip()
        if not api_base:
            api_base = DEFAULT_API_BASE
        self.api_base_url_line_edit.setText(api_base)
        plugin = Registry().get('song_stats_plugin')
        self.plugin_status_combo.blockSignals(True)
        self.plugin_status_combo.clear()
        self.plugin_status_combo.addItem('Nieaktywny', PluginStatus.Inactive)
        self.plugin_status_combo.addItem('Aktywny', PluginStatus.Active)
        if plugin and plugin.status == PluginStatus.Disabled:
            self.plugin_status_combo.addItem('Wyłączony (włącz Pieśni)', PluginStatus.Disabled)
            self.plugin_status_combo.setCurrentIndex(2)
            self.plugin_status_combo.setEnabled(False)
        else:
            self.plugin_status_combo.setEnabled(True)
            if plugin and plugin.status == PluginStatus.Active:
                self.plugin_status_combo.setCurrentIndex(1)
            else:
                self.plugin_status_combo.setCurrentIndex(0)
        self.plugin_status_combo.blockSignals(False)

        token = (self.settings.value('songstats/api token') or '').strip()
        self.api_token_line_edit.setText(token)
        self._update_login_buttons(token)
        lang = self.settings.value('songstats/default language')
        self.default_language_line_edit.setText(lang if lang else 'pl')
        timeout = self.settings.value('songstats/timeout')
        self.timeout_spin_box.setValue(int(timeout) if timeout else 30)

        push_on_edit = self.settings.value('songstats/push on edit')
        if push_on_edit is None:
            push_on_edit = True
        self.push_on_edit_check_box.setChecked(bool(push_on_edit))
        pull_mode = (self.settings.value('songstats/sync pull mode') or SYNC_PULL_JSON).lower()
        self.sync_pull_mode_combo.setCurrentIndex(1 if pull_mode == SYNC_PULL_SQLITE else 0)

    def on_logout(self):
        self._ensure_ui()
        from contrib.plugins.songstats.lib.openlpauth import logout_openlp_session

        logout_openlp_session(self.settings, open_browser=True)
        self.api_token_line_edit.clear()
        self._update_login_buttons('')
        plugin = Registry().get('song_stats_plugin')
        if plugin and hasattr(plugin, '_refresh_sync_header_display'):
            plugin._refresh_sync_header_display()

    def on_clear_cache(self):
        self._ensure_ui()
        plugin = Registry().get('song_stats_plugin')
        if plugin and hasattr(plugin, '_on_kwch_clear_cache'):
            if plugin._on_kwch_clear_cache(parent=self):
                token = (self.settings.value('songstats/api token') or '').strip()
                self._update_login_buttons(token)
            return
        from contrib.plugins.songstats.lib.apiutil import clear_plugin_cache

        reply = QtWidgets.QMessageBox.question(
            self,
            translate('SongStatsPlugin.SongStatsTab', 'Wyczyść cache'),
            translate(
                'SongStatsPlugin.SongStatsTab',
                'Zostaną usunięte zapamiętane wersje katalogu, data ostatniej '
                'synchronizacji oraz zapisany profil (nazwa, avatar).\n\n'
                'Logowanie, ustawienia i pieśni w OpenLP zostaną.\n\n'
                'Kontynuować?',
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        clear_plugin_cache(self.settings)
        token = (self.settings.value('songstats/api token') or '').strip()
        self._update_login_buttons(token)

    def on_browser_login(self):
        from contrib.plugins.songstats.lib.openlpauth import login_via_browser

        self._ensure_ui()
        self.login_button.setEnabled(False)
        self.login_status_label.setText(
            translate('SongStatsPlugin.SongStatsTab', 'Otwieranie przeglądarki… (max. 3 min)')
        )

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
        worker.succeeded.connect(self._on_login_succeeded)
        worker.failed.connect(self._on_login_failed)
        run_thread(worker, 'songstats-login-{uid}'.format(uid=uuid.uuid4().hex[:8]), can_start=True)

    def _on_login_succeeded(self, token):
        self.api_token_line_edit.setText(token)
        self.settings.setValue('songstats/api token', token)
        persist_auth_profile(self.settings, token)
        self._update_login_buttons(token)
        self.login_button.setEnabled(True)
        plugin = Registry().get('song_stats_plugin')
        if plugin and hasattr(plugin, '_refresh_sync_header_display'):
            plugin._refresh_sync_header_display()

    def _on_login_failed(self, message):
        self.login_status_label.setText(
            translate('SongStatsPlugin.SongStatsTab', 'Logowanie nie powiodło się: {err}').format(err=message)
        )
        token = (self.settings.value('songstats/api token') or '').strip()
        self._update_login_buttons(token)
        self.login_button.setEnabled(True)

    def save(self):
        self._ensure_ui()
        plugin = Registry().get('song_stats_plugin')
        if plugin and self.plugin_status_combo.isEnabled():
            desired = self.plugin_status_combo.currentData()
            if desired in (PluginStatus.Active, PluginStatus.Inactive) and plugin.status != desired:
                if desired == PluginStatus.Active and not Registry().get('songs_manager'):
                    self.login_status_label.setText(
                        translate('SongStatsPlugin.SongStatsTab', 'Nie można włączyć: plugin Pieśni jest wyłączony.')
                    )
                else:
                    plugin.toggle_status(desired)

        self.settings.setValue('songstats/api base url', self.api_base_url_line_edit.text().strip())
        token = self.api_token_line_edit.text()
        self.settings.setValue('songstats/api token', token)
        if token.strip():
            persist_auth_profile(self.settings, token)
        else:
            clear_auth_session(self.settings)
        self.settings.setValue(
            'songstats/default language',
            self.default_language_line_edit.text().strip() or 'pl',
        )
        self.settings.setValue('songstats/timeout', self.timeout_spin_box.value())

        self.settings.setValue('songstats/enabled', True)

        self.settings.setValue(
            'songstats/push on edit',
            self.push_on_edit_check_box.isChecked(),
        )
        self.settings.setValue(
            'songstats/sync pull mode',
            self.sync_pull_mode_combo.currentData(),
        )

        self._update_login_buttons(token)

        if plugin and hasattr(plugin, '_refresh_sync_header_display'):
            plugin._refresh_sync_header_display()