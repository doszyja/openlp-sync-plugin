# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock

from contrib.plugins.songstats.lib.apiutil import resolve_openlp_save_url
from contrib.plugins.songstats.lib.pluginutil import (
    catalog_title_index_keys,
    resolve_remote_mongo_id,
)
from contrib.plugins.songstats.lib.songsync import build_openlp_save_operation
from contrib.plugins.songstats.lib.synchttp import push_summary_had_upload


class _Settings(dict):
    def value(self, key, default=None):
        return self.get(key, default)


def test_resolve_openlp_save_url_default():
    settings = _Settings({'songstats/api base url': 'https://example.com/api'})
    assert (
        resolve_openlp_save_url(settings)
        == 'https://example.com/api/songs/openlp/save'
    )


def test_resolve_remote_mongo_id_by_title_index():
    index = {
        'title:amazing grace|n:123': {'id': 'mongoabc', 'title': 'Amazing Grace'},
    }
    song = SimpleNamespace(
        title='Amazing Grace',
        alternate_title='123',
        ccli_number='',
        search_title='amazing grace',
        comments='',
    )
    assert (
        resolve_remote_mongo_id('', 99, index, song=song) == 'mongoabc'
    )


def test_build_openlp_save_operation_puts_method():
    settings = _Settings({
        'songstats/api base url': 'https://x/api',
        'songstats/default language': 'pl',
        'songstats/openlp client id': 'openlp-test-client',
    })
    song = SimpleNamespace(
        id=7,
        temporary=False,
        title='Test',
        alternate_title='',
        ccli_number='',
        search_title='test',
        comments='',
        lyrics='<?xml version="1.0"?><song xmlns="http://openlyrics.info/namespace/2009/song" version="0.8"><lyrics><verse name="v1"><lines><line>Hi</line></lines></verse></lyrics></song>',
        verse_order='',
        copyright='',
        theme_name='',
        search_lyrics='',
    )
    song.authors_songs = []
    op = build_openlp_save_operation(song, settings, 'https://x/api', {})
    assert op is not None
    assert op['method'] == 'PUT'
    assert op['url'] == 'https://x/api/songs/openlp/save'
    assert op['body']['title'] == 'Test'
    assert op['local_id'] == 7
    mapping = op['body']['openlpMapping']
    assert mapping['openlpId'] == 7
    assert mapping['clientId'] == 'openlp-test-client'
    assert mapping['lastSyncedAt']


def test_push_summary_had_upload_after_put():
    assert push_summary_had_upload('created=0, updated=1, errors=0, skipped=0') is True


def test_catalog_title_index_keys_search():
    keys = catalog_title_index_keys('Foo', '1', 'foo')
    assert 'title:foo|n:1' in keys
    assert 'search:foo' in keys