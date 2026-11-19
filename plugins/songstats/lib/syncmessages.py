# -*- coding: utf-8 -*-
"""User-facing sync error messages (Polish-first via translate source strings)."""
from PyQt5 import QtWidgets

from openlp.core.common.i18n import translate


def prompt_catalog_update_available(parent, remote_version, local_version_label):
    """
    Inform user that the server catalog is newer. Returns True if they chose Synchronizuj.
    """
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Information)
    box.setWindowTitle(translate('SongStatsPlugin', 'Dostępna aktualizacja katalogu'))
    box.setText(
        translate(
            'SongStatsPlugin',
            'Serwer ma wersję {remote}. Lokalnie: {local}.',
        ).format(remote=remote_version, local=local_version_label)
    )
    box.setInformativeText(
        translate(
            'SongStatsPlugin',
            'Pobierz zmiany z serwera KWCH, aby wyrównać katalog pieśni.',
        )
    )
    sync_btn = box.addButton(
        translate('SongStatsPlugin', 'Synchronizuj'),
        QtWidgets.QMessageBox.ActionRole,
    )
    box.addButton(
        translate('SongStatsPlugin', 'Później'),
        QtWidgets.QMessageBox.RejectRole,
    )
    box.exec_()
    return box.clickedButton() is sync_btn


def explain_sync_error(raw_detail):
    """
    Map technical error text to a dialog title and body for operators.
    """
    text = (raw_detail or '').strip()
    lower = text.lower()
    title = translate('SongStatsPlugin', 'Synchronizacja pieśni nie powiodła się')

    if (
        'push requires api token' in lower
        or 'pull requires api token' in lower
        or 'upload skipped (no api token)' in lower
    ):
        body = translate(
            'SongStatsPlugin',
            'Nie jesteś zalogowany na serwer pieśni.\n\n'
            'Zaloguj się kontem z aplikacji webowej KWCH (menu Konto w pasku u góry '
            'lub ustawienia wtyczki).',
        )
    elif '403' in text and ('uprawnie' in lower or 'edit' in lower or 'permission' in lower):
        body = translate(
            'SongStatsPlugin',
            'Konto nie ma uprawnień do edycji pieśni na serwerze.\n\n'
            'Na Discordzie KWCH potrzebna jest rola pozwalająca edytować katalog. '
            'Bez 2xx z PATCH zmiany i wpisy audytu nie trafiają do bazy.',
        )
    elif '401' in text or '403' in text or 'odrzucił' in lower or 'rejected' in lower:
        body = translate(
            'SongStatsPlugin',
            'Sesja wygasła lub serwer odrzucił żądanie dla tego konta.\n\n'
            'Wyloguj i zaloguj ponownie przez stronę KWCH (menu Konto).',
        )
    elif 'timed out' in lower or 'timeout' in lower or 'przekroczono' in lower:
        body = translate(
            'SongStatsPlugin',
            'Przekroczono limit czasu połączenia.\n\n'
            'Sprawdź internet, ustawienia proxy w OpenLP i adres API w wtyczce KWCH.',
        )
    elif any(
        marker in lower
        for marker in (
            'connection',
            'connect',
            'getaddrinfo',
            'network',
            'refused',
            'nodename',
            'name or service not known',
            'max retries',
        )
    ):
        body = translate(
            'SongStatsPlugin',
            'Brak połączenia z serwerem pieśni.\n\n'
            'Sprawdź internet, poprawny adres API (np. https://piesni…/api) i czy strona działa w przeglądarce.',
        )
    elif 'http 5' in lower or '502' in text or '503' in text or '504' in text:
        body = translate(
            'SongStatsPlugin',
            'Serwer pieśni jest chwilowo niedostępny (błąd HTTP).\n\nSpróbuj za chwilę.',
        )
    elif 'unexpected sync response' in lower or 'no version field' in lower:
        body = translate(
            'SongStatsPlugin',
            'Serwer zwrócił nieoczekiwaną odpowiedź.\n\n'
            'Sprawdź adres API (powinien wskazywać na Openlp-database, ścieżka /api).',
        )
    elif 'songs database' in lower or 'songs plugin' in lower:
        body = translate(
            'SongStatsPlugin',
            'Baza pieśni OpenLP nie jest dostępna. Włącz plugin Pieśni i uruchom OpenLP ponownie.',
        )
    elif 'integrityerror' in lower or 'authors_songs' in lower or 'database constraint' in lower:
        body = translate(
            'SongStatsPlugin',
            'Import pieśni napotkał błąd bazy OpenLP (np. autor bez typu).\n\n'
            'To nie jest błąd logowania ani adresu API — katalog z serwera został pobrany. '
            'Spróbuj ponownie po aktualizacji wtyczki; pojedyncze pieśni mogą być pominięte.',
        )
    elif 'import catalog failed' in lower or 'failed to import' in lower:
        body = translate(
            'SongStatsPlugin',
            'Pobrano dane z serwera, ale import do lokalnej bazy się nie powiódł.\n\n'
            'Szczegóły techniczne:\n{detail}',
        ).format(detail=text)
    elif text:
        body = translate('SongStatsPlugin', '{detail}').format(detail=text)
    else:
        body = translate('SongStatsPlugin', 'Nieznany błąd synchronizacji.')

    return title, body