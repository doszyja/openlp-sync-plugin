# -*- coding: utf-8 -*-
"""
Non-blocking HTTP client for the Song Stats plugin.
"""
import logging

import requests

from openlp.core.common.httputils import get_proxy_settings
from openlp.core.threading import ThreadWorker

log = logging.getLogger(__name__)


class SongStatsPostWorker(ThreadWorker):
    """
    POST JSON payload to the configured stats API in a background thread.
    """

    def __init__(self, url, payload, headers, timeout):
        super().__init__()
        self._url = url
        self._payload = payload
        self._headers = headers
        self._timeout = timeout

    def start(self):
        try:
            timeout = self._timeout
            if not isinstance(timeout, (tuple, list)):
                timeout = float(timeout)
            response = requests.post(
                self._url,
                json=self._payload,
                headers=self._headers,
                proxies=get_proxy_settings(),
                timeout=timeout,
            )
            if response.status_code >= 400:
                log.warning(
                    'KWCH presentation-events HTTP %s: %s',
                    response.status_code,
                    (response.text or '')[:300],
                )
        except requests.RequestException as err:
            # Offline, timeout, DNS — expected; must not affect Live / UI.
            log.debug('Song Stats POST skipped (network): %s — %s', self._url, err)
        except Exception:
            log.exception('Unexpected error posting song stats to %s', self._url)
        finally:
            self.quit.emit()