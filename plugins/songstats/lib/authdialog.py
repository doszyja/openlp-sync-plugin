# -*- coding: utf-8 -*-
"""Session expiry (401) — clear token and reopen login."""
from PyQt5 import QtWidgets

from openlp.core.common.i18n import translate


def is_auth_expired_message(message):
    text = (message or '').strip().lower()
    return '401' in text or 'sesja wygas' in text or 'rejected (401)' in text


def offer_session_expired_relogin(parent, settings, on_login_callback):
    """On accept: clear_auth_session and call on_login_callback(). Returns True if handled."""
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle(translate('SongStatsPlugin', 'Sesja wygasła'))
    box.setText(
        translate(
            'SongStatsPlugin',
            'Serwer odrzucił żądanie (401) — token jest nieaktualny.',
        )
    )
    box.setInformativeText(
        translate(
            'SongStatsPlugin',
            'Wylogować zapisane dane logowania i otworzyć logowanie KWCH ponownie?',
        )
    )
    reauth_btn = box.addButton(
        translate('SongStatsPlugin', 'Wyloguj i zaloguj ponownie'),
        QtWidgets.QMessageBox.AcceptRole,
    )
    box.addButton(
        translate('SongStatsPlugin', 'Zamknij'),
        QtWidgets.QMessageBox.RejectRole,
    )
    box.exec_()
    if box.clickedButton() is not reauth_btn:
        return True
    from contrib.plugins.songstats.lib.apiutil import clear_auth_session

    clear_auth_session(settings)
    if callable(on_login_callback):
        on_login_callback()
    return True