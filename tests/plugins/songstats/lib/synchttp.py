# -*- coding: utf-8 -*-
"""
HTTP workers for song catalog sync (network only — DB work runs on the main Qt thread).
"""
import logging
import tempfile
from pathlib import Path

import requests
from PyQt5 import QtCore

from openlp.core.common.httputils import get_proxy_settings
from openlp.core.common.registry import Registry
from openlp.core.threading import ThreadWorker

from contrib.plugins.songstats.lib.apiutil import (
    build_auth_headers,
    get_connect_timeout,
    get_request_timeouts,
    get_timeout,
    resolve_version_url,
)

log = logging.getLogger(__name__)


def describe_push_http_error(response):
    """Short user- and log-friendly message from a failed push response."""
    status = response.status_code
    if status == 403:
        return (
            'Push rejected (403): brak uprawnień do edycji pieśni na serwerze '
            '(wymagana rola edycji na Discordzie KWCH).'
        )
    if status == 404:
        return (
            'Push rejected (404): pieśni nie ma w bazie serwera — '
            'zrób synchronizację lub sprawdź songstats:remote_id w komentarzach.'
        )
    try:
        data = response.json()
        if isinstance(data, dict):
            message = data.get('message')
            if isinstance(message, list):
                detail = '; '.join(str(part) for part in message if part)
                if detail:
                    return 'Push rejected (HTTP {code}): {detail}'.format(code=status, detail=detail)
            if message:
                return 'Push rejected (HTTP {code}): {detail}'.format(
                    code=status, detail=str(message)
                )
    except ValueError:
        pass
    snippet = (response.text or '').strip()
    if snippet:
        snippet = snippet[:400]
        return 'Push rejected (HTTP {code}): {detail}'.format(code=status, detail=snippet)
    return 'Push rejected (HTTP {code})'.format(code=status)


def push_summary_had_upload(summary):
    """True when MasterApiPushWorker summary reports at least one created/updated row."""
    text = (summary or '').strip().lower()
    if not text:
        return False
    parts = {}
    for chunk in text.split(','):
        chunk = chunk.strip()
        if '=' not in chunk:
            continue
        key, _, value = chunk.partition('=')
        parts[key.strip()] = value.strip()
    try:
        if int(parts.get('created', '0') or '0') > 0:
            return True
        if int(parts.get('updated', '0') or '0') > 0:
            return True
    except ValueError:
        pass
    return False


def parse_songs_response(response):
    """
    Returns (songs, version, deleted_song_ids, incremental_full_fallback).
    """
    data = response.json()
    deleted_ids = []
    incremental_full = False
    if isinstance(data, list):
        return data, None, deleted_ids, incremental_full
    if isinstance(data, dict):
        version = data.get('version')
        if data.get('deletedSongIds'):
            deleted_ids = list(data.get('deletedSongIds') or [])
        incremental_full = bool(data.get('full'))
        if 'songs' in data and isinstance(data['songs'], list):
            return data['songs'], version, deleted_ids, incremental_full
        if 'data' in data and isinstance(data['data'], list):
            return data['data'], version, deleted_ids, incremental_full
    raise ValueError(
        'Unexpected sync response (expected {"songs": [...]} from GET /songs/all-openlp or a JSON array)'
    )


class SongVersionWorker(ThreadWorker):
    """GET /songs/version — current master song database revision."""

    version_succeeded = QtCore.pyqtSignal(object)
    version_failed = QtCore.pyqtSignal(str)

    def start(self):
        settings = Registry().get('settings')
        url = resolve_version_url(settings)
        if not url:
            self.version_failed.emit('API base URL is not configured')
            self.quit.emit()
            return
        try:
            response = requests.get(
                url,
                headers=build_auth_headers(settings),
                proxies=get_proxy_settings(),
                timeout=get_request_timeouts(settings),
            )
            if response.status_code >= 400:
                self.version_failed.emit(
                    'Version check HTTP {code}'.format(code=response.status_code)
                )
                return
            data = response.json()
            version = data.get('version') if isinstance(data, dict) else data
            if version is None:
                self.version_failed.emit('No version field in response')
                return
            self.version_succeeded.emit(version)
        except Exception as error:
            log.exception('Song version check failed')
            self.version_failed.emit(str(error))
        finally:
            self.quit.emit()


class SongSyncPullWorker(ThreadWorker):
    pull_succeeded = QtCore.pyqtSignal(list, object, list, bool)
    pull_failed = QtCore.pyqtSignal(str)

    def __init__(self, pull_url):
        super().__init__()
        self._pull_url = pull_url

    def start(self):
        settings = Registry().get('settings')
        try:
            response = requests.get(
                self._pull_url,
                headers=build_auth_headers(settings),
                proxies=get_proxy_settings(),
                timeout=get_request_timeouts(settings),
            )
            if response.status_code >= 400:
                if response.status_code in (401, 403):
                    self.pull_failed.emit(
                        'Pull rejected ({code}): zaloguj ponownie kontem KWCH (menu Konto w OpenLP).'
                        .format(code=response.status_code)
                    )
                else:
                    self.pull_failed.emit(
                        'Pull failed with HTTP {code}: {body}'.format(
                            code=response.status_code,
                            body=response.text[:300],
                        )
                    )
                return
            songs, version, deleted_ids, incremental_full = parse_songs_response(response)
            self.pull_succeeded.emit(songs, version, deleted_ids, incremental_full)
        except requests.exceptions.Timeout as error:
            self.pull_failed.emit('Connection timed out: {0}'.format(error))
        except requests.exceptions.ConnectionError as error:
            self.pull_failed.emit('Connection failed: {0}'.format(error))
        except requests.exceptions.RequestException as error:
            log.exception('Song sync pull failed')
            self.pull_failed.emit(str(error))
        except Exception as error:
            log.exception('Song sync pull failed')
            self.pull_failed.emit(str(error))
        finally:
            self.quit.emit()


class SongSyncSqlitePullWorker(ThreadWorker):
    """Download GET /songs/export/sqlite to a temporary file."""
    pull_succeeded = QtCore.pyqtSignal(object)
    pull_failed = QtCore.pyqtSignal(str)

    def __init__(self, pull_url):
        super().__init__()
        self._pull_url = pull_url

    def start(self):
        settings = Registry().get('settings')
        headers = build_auth_headers(settings, accept='application/x-sqlite3')
        headers.pop('Content-Type', None)
        try:
            response = requests.get(
                self._pull_url,
                headers=headers,
                proxies=get_proxy_settings(),
                timeout=(get_connect_timeout(), max(get_timeout(settings), 120.0)),
                stream=True,
            )
            if response.status_code >= 400:
                self.pull_failed.emit(
                    'SQLite pull failed with HTTP {code}'.format(code=response.status_code)
                )
                return
            temp_dir = Path(tempfile.gettempdir()) / 'openlp'
            temp_dir.mkdir(parents=True, exist_ok=True)
            dest = temp_dir / 'songstats-master-export.sqlite'
            with dest.open('wb') as handle:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        handle.write(chunk)
            self.pull_succeeded.emit(dest)
        except Exception as error:
            log.exception('SQLite export download failed')
            self.pull_failed.emit(str(error))
        finally:
            self.quit.emit()


class MasterApiPushWorker(ThreadWorker):
    push_succeeded = QtCore.pyqtSignal(object, str)
    push_failed = QtCore.pyqtSignal(str)
    push_progress = QtCore.pyqtSignal(int, int)

    def __init__(self, operations):
        super().__init__()
        self._operations = operations

    def start(self):
        settings = Registry().get('settings')
        headers = build_auth_headers(settings)
        created = updated = errors = skipped = 0
        post_results = []

        if not self.settings_has_token(settings):
            self.push_failed.emit(
                'Push requires API token (log in via KWCH web). Upload skipped (no API token).'
            )
            self.quit.emit()
            return

        total = len(self._operations)
        last_error = None
        try:
            for position, op in enumerate(self._operations, start=1):
                self.push_progress.emit(position, total)
                method = op['method']
                try:
                    if method == 'PATCH':
                        response = requests.patch(
                            op['url'],
                            json=op['body'],
                            headers=headers,
                            proxies=get_proxy_settings(),
                            timeout=get_request_timeouts(settings),
                        )
                    elif method == 'POST':
                        response = requests.post(
                            op['url'],
                            json=op['body'],
                            headers=headers,
                            proxies=get_proxy_settings(),
                            timeout=get_request_timeouts(settings),
                        )
                    elif method == 'PUT':
                        response = requests.put(
                            op['url'],
                            json=op['body'],
                            headers=headers,
                            proxies=get_proxy_settings(),
                            timeout=get_request_timeouts(settings),
                        )
                    elif method == 'DELETE':
                        log.warning(
                            'KWCH: ignoring DELETE %s (server delete is admin-only on web)',
                            op['url'],
                        )
                        skipped += 1
                        continue
                    else:
                        skipped += 1
                        continue

                    if response.status_code == 401:
                        self.push_failed.emit(
                            'Push rejected (401): zaloguj ponownie (KWCH Swietochlowice plugin → Połącz z kontem).'
                        )
                        return
                    if response.status_code >= 400:
                        errors += 1
                        last_error = describe_push_http_error(response)
                        log.warning(
                            'Push %s %s -> %s: %s',
                            method,
                            op['url'],
                            response.status_code,
                            last_error,
                        )
                        continue

                    log.info(
                        'KWCH: push %s %s -> HTTP %s (local openlp id=%s)',
                        method,
                        op['url'],
                        response.status_code,
                        op.get('local_id'),
                    )

                    if method == 'POST':
                        created += 1
                    elif method == 'PUT':
                        updated += 1
                    else:
                        updated += 1
                    if method in ('POST', 'PUT'):
                        try:
                            body = response.json()
                            remote_id = body.get('id') or body.get('_id')
                            if isinstance(remote_id, dict) and remote_id.get('$oid'):
                                remote_id = remote_id['$oid']
                            if remote_id:
                                remote_id = str(remote_id)
                                post_results.append({
                                    'method': method,
                                    'local_id': op['local_id'],
                                    'remote_id': remote_id,
                                })
                        except ValueError:
                            pass
                except OSError:
                    errors += 1
                    log.exception('Push request failed for %s', op['url'])

            if errors > 0 and created + updated == 0:
                self.push_failed.emit(
                    last_error
                    or 'Push failed: {e} error(s), nothing uploaded.'.format(e=errors)
                )
                return

            summary = 'created={c}, updated={u}, errors={e}, skipped={s}'.format(
                c=created, u=updated, e=errors, s=skipped
            )
            self.push_succeeded.emit(post_results, summary)
        except Exception as error:
            log.exception('Master API push failed')
            self.push_failed.emit(str(error))
        finally:
            self.quit.emit()

    @staticmethod
    def settings_has_token(settings):
        from contrib.plugins.songstats.lib.apiutil import has_api_token

        return has_api_token(settings)