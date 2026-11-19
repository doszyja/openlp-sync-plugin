# -*- coding: utf-8 -*-
from contrib.plugins.songstats.lib.syncmessages import explain_sync_error


def test_explain_sync_error_no_token():
    title, body = explain_sync_error('Push requires API token')
    assert 'nie jesteś zalogowany' in body.lower() or 'Zaloguj' in body


def test_explain_sync_error_network():
    title, body = explain_sync_error('Connection refused: getaddrinfo failed')
    assert 'Brak połączenia' in body or 'internet' in body.lower()


def test_explain_sync_error_401():
    _, body = explain_sync_error('HTTP 401 Unauthorized')
    assert 'Sesja' in body or 'wygasła' in body.lower()


def test_explain_sync_error_raw_passthrough():
    _, body = explain_sync_error('Custom operator message')
    assert 'Custom operator message' in body