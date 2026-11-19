# -*- coding: utf-8 -*-
"""Modal when syncing with unsynchronized local catalog changes (⚠)."""
from PyQt5 import QtWidgets

from openlp.core.common.i18n import translate

from contrib.plugins.songstats.lib.catalogstate import drift_reason

CHOICE_PUSH = 'push'
CHOICE_DISCARD = 'discard'
CHOICE_CANCEL = None  # cancelled dialog


def prompt_local_drift_resolution(parent, settings, has_token):
    """
    Ask operator: push local to server, discard local (pull from server), or cancel.
    Returns CHOICE_PUSH, CHOICE_DISCARD, or CHOICE_CANCEL.
    """
    reason = drift_reason(settings)
    reason_note = ''
    if reason == 'deleted_local':
        reason_note = translate(
            'SongStatsPlugin',
            'Usunąłeś pieśń lokalnie — na serwerze nadal może być.',
        )
    elif reason in ('edit_no_token', 'edit_not_pushed', 'push_failed'):
        reason_note = translate(
            'SongStatsPlugin',
            'Masz edycje zapisane tylko w OpenLP.',
        )

    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle(
        translate('SongStatsPlugin', 'Lokalne zmiany poza synchronizacją')
    )
    box.setText(
        translate(
            'SongStatsPlugin',
            'Lokalna baza ma zmiany (⚠), które nie są zgodne z serwerem KWCH.\n\n'
            'Co chcesz zrobić?',
        )
    )
    detail_parts = [
        reason_note,
        translate(
            'SongStatsPlugin',
            'Wyślij lokalne — PATCH/POST na serwer (wymaga logowania i uprawnień edycji).\n'
            'Pobierz z serwera — nadpisuje lokalne zmiany danymi z serwera (usunięte '
            'lokalnie pieśni mogą wrócić).',
        ),
    ]
    box.setDetailedText('\n\n'.join(part for part in detail_parts if part))

    push_btn = box.addButton(
        translate('SongStatsPlugin', 'Wyślij lokalne na serwer'),
        QtWidgets.QMessageBox.ActionRole,
    )
    pull_btn = box.addButton(
        translate('SongStatsPlugin', 'Odrzuć lokalne i pobierz z serwera'),
        QtWidgets.QMessageBox.DestructiveRole,
    )
    cancel_btn = box.addButton(
        translate('SongStatsPlugin', 'Anuluj'),
        QtWidgets.QMessageBox.RejectRole,
    )
    if not has_token:
        push_btn.setEnabled(False)
        push_btn.setToolTip(
            translate(
                'SongStatsPlugin',
                'Zaloguj się przez menu Konto, aby wysyłać zmiany.',
            )
        )

    box.exec_()
    clicked = box.clickedButton()
    if clicked is cancel_btn:
        return CHOICE_CANCEL
    if clicked is push_btn:
        if not has_token:
            QtWidgets.QMessageBox.warning(
                parent,
                translate('SongStatsPlugin', 'Brak logowania'),
                translate(
                    'SongStatsPlugin',
                    'Wysyłka na serwer wymaga zalogowania kontem KWCH (Discord).',
                ),
            )
            return CHOICE_CANCEL
        return CHOICE_PUSH
    if clicked is pull_btn:
        return CHOICE_DISCARD
    return CHOICE_CANCEL