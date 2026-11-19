# -*- coding: utf-8 -*-
"""
Browser login flow: open web /auth/openlp, receive code on localhost, exchange for JWT.
"""
import logging
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from openlp.core.common.httputils import get_proxy_settings

from contrib.plugins.songstats.lib.apiutil import get_api_base, get_request_timeouts, get_web_base

log = logging.getLogger(__name__)

DEFAULT_CALLBACK_PORT = 8765


class _CallbackHandler(BaseHTTPRequestHandler):
    expected_state = ''
    result = None

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        log.debug('OAuth callback: ' + format, *args)

    def do_GET(self):
        parsed = urlparse(self.path)
        if not parsed.path.rstrip('/').endswith('/callback'):
            self.send_error(404)
            return
        params = parse_qs(parsed.query)
        if (params.get('logout') or [''])[0] in ('1', 'true', 'yes'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                '<html><body><p>Wylogowano. Możesz zamknąć tę kartę.</p></body></html>'.encode(
                    'utf-8'
                )
            )
            return
        if _CallbackHandler.result and _CallbackHandler.result.get('code'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                '<html><body><p>Logowanie zakończone. Możesz wrócić do OpenLP.</p></body></html>'.encode(
                    'utf-8'
                )
            )
            return
        code = (params.get('code') or [''])[0]
        state = (params.get('state') or [''])[0]
        if not code or state != _CallbackHandler.expected_state:
            if not _CallbackHandler.result:
                _CallbackHandler.result = {'error': 'invalid_callback'}
            self.send_error(400, 'Invalid callback')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        body = (
            '<html><body><p>Logowanie zakończone. Możesz wrócić do OpenLP.</p>'
            '</body></html>'
        )
        self.wfile.write(body.encode('utf-8'))
        _CallbackHandler.result = {'code': code, 'state': state}


def _exchange_code(settings, code, state):
    api_base = get_api_base(settings)
    if not api_base:
        raise ValueError('API base URL is not configured')
    url = '{base}/auth/openlp/token'.format(base=api_base.rstrip('/'))
    response = requests.post(
        url,
        json={'code': code, 'state': state},
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        proxies=get_proxy_settings(),
        timeout=get_request_timeouts(settings),
    )
    if response.status_code >= 400:
        detail = response.text[:200]
        if response.status_code == 401 and 'authorization code' in detail.lower():
            raise ValueError(
                'Kod logowania wygasł lub został już użyty. '
                'Zamknij stare karty localhost:8765, wyloguj w przeglądarce '
                'i spróbuj zalogować się ponownie (menu Konto).'
            )
        raise ValueError(
            'Token exchange failed (HTTP {code}): {body}'.format(
                code=response.status_code,
                body=detail,
            )
        )
    data = response.json()
    token = data.get('access_token')
    if not token:
        raise ValueError('No access_token in response')
    profile = data.get('user') or data.get('profile') or data.get('discord')
    from contrib.plugins.songstats.lib.apiutil import (
        fetch_identity_from_api,
        persist_auth_profile,
    )

    if isinstance(profile, dict):
        persist_auth_profile(settings, token, profile=profile)
    else:
        persist_auth_profile(settings, token)
    fetch_identity_from_api(settings)
    return token


def login_via_browser(settings):
    """
    Blocking call — run from a background QThread.
    Returns access_token string on success; raises on failure.
    """
    web_base = get_web_base(settings)
    if not web_base:
        raise ValueError('Web base URL could not be determined (set API base URL)')

    state = secrets.token_urlsafe(24)
    _CallbackHandler.expected_state = state
    _CallbackHandler.result = None

    server = HTTPServer(('127.0.0.1', DEFAULT_CALLBACK_PORT), _CallbackHandler)
    server.timeout = 0.5

    def serve():
        deadline = __import__('time').time() + 180
        while _CallbackHandler.result is None and __import__('time').time() < deadline:
            server.handle_request()
        server.server_close()
        pending = _CallbackHandler.result or {}
        if pending.get('code') and not pending.get('token') and not pending.get('error'):
            try:
                token = _exchange_code(
                    settings,
                    pending['code'],
                    pending.get('state') or state,
                )
                _CallbackHandler.result = {'token': token}
            except ValueError as error:
                _CallbackHandler.result = {'error': str(error)}

    thread = Thread(target=serve, daemon=True)
    thread.start()

    query = {
        'port': DEFAULT_CALLBACK_PORT,
        'state': state,
    }
    if settings.value('songstats/force auth prompt'):
        query['prompt'] = 'login'
        query['force_login'] = '1'
        settings.setValue('songstats/force auth prompt', False)
    auth_url = '{web}/auth/openlp?{qs}'.format(
        web=web_base.rstrip('/'),
        qs=urlencode(query),
    )
    if not webbrowser.open(auth_url):
        raise RuntimeError('Could not open the system web browser')

    thread.join(timeout=185)
    if not _CallbackHandler.result:
        raise TimeoutError('Timed out waiting for browser login (3 minutes)')
    if _CallbackHandler.result.get('error'):
        raise ValueError(_CallbackHandler.result['error'])
    if _CallbackHandler.result.get('token'):
        return _CallbackHandler.result['token']
    if _CallbackHandler.result.get('code'):
        return _exchange_code(
            settings,
            _CallbackHandler.result['code'],
            _CallbackHandler.result.get('state') or state,
        )
    raise ValueError('Browser login was rejected')


def logout_openlp_session(settings, open_browser=True):
    """
    End KWCH / Discord SSO for OpenLP: revoke API token, clear local JWT,
    open the web logout page (clears browser session on localhost flow).
    """
    from contrib.plugins.songstats.lib.apiutil import (
        build_auth_headers,
        clear_auth_session,
        get_api_base,
        get_request_timeouts,
        get_web_base,
    )

    token = (settings.value('songstats/api token') or '').strip()
    api_base = get_api_base(settings)
    web_base = get_web_base(settings)
    connect_timeout, read_timeout = get_request_timeouts(settings)

    if token and api_base:
        # NestJS AuthController: POST /auth/logout (JWT, no OpenLP-specific path).
        url = '{base}/auth/logout'.format(base=api_base.rstrip('/'))
        try:
            response = requests.post(
                url,
                json={},
                headers=build_auth_headers(settings),
                proxies=get_proxy_settings(),
                timeout=(connect_timeout, read_timeout),
            )
            if response.status_code >= 400:
                log.debug(
                    'Logout POST /auth/logout HTTP %s: %s',
                    response.status_code,
                    (response.text or '')[:200],
                )
        except requests.RequestException as error:
            log.debug('Logout POST /auth/logout: %s', error)

    clear_auth_session(settings)
    settings.setValue('songstats/force auth prompt', True)

    if open_browser and web_base:
        # SPA route /auth/openlp/logout — not an API path. Do not pass port=:
        # the page would redirect to 127.0.0.1:8765/callback, but OpenLP only
        # listens there during an active login handshake.
        logout_url = '{web}/auth/openlp/logout?{qs}'.format(
            web=web_base.rstrip('/'),
            qs=urlencode({'from': 'openlp'}),
        )
        webbrowser.open(logout_url)