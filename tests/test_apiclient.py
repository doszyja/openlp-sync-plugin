# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from contrib.plugins.songstats.lib.apiclient import SongStatsPostWorker


def _run_worker(worker, post_side_effect=None, post_return=None):
    worker.quit = MagicMock()
    import requests

    patches = [
        patch('openlp.core.common.httputils.get_proxy_settings', return_value={}),
    ]
    if post_side_effect is not None:
        patches.append(
            patch(
                'contrib.plugins.songstats.lib.apiclient.requests.post',
                side_effect=post_side_effect,
            )
        )
    else:
        patches.append(
            patch(
                'contrib.plugins.songstats.lib.apiclient.requests.post',
                return_value=post_return,
            )
        )
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        worker.start()
    worker.quit.emit.assert_called_once()


def test_post_worker_success():
    worker = SongStatsPostWorker(
        'https://example.com/api/presentation-events',
        {'title': 'X'},
        {'Content-Type': 'application/json'},
        (3, 8),
    )
    _run_worker(worker, post_return=MagicMock(status_code=201, text='ok'))


def test_post_worker_network_failure():
    import requests

    worker = SongStatsPostWorker(
        'https://example.com/api/presentation-events',
        {},
        {},
        5,
    )
    _run_worker(worker, post_side_effect=requests.ConnectionError('offline'))


def test_post_worker_http_error_logged_only():
    worker = SongStatsPostWorker('https://example.com/x', {}, {}, 5)
    _run_worker(worker, post_return=MagicMock(status_code=500, text='boom'))