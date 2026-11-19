# -*- coding: utf-8 -*-
from contrib.plugins.songstats.lib import apiutil
from contrib.plugins.songstats.lib.apiutil import (
    DEFAULT_API_BASE,
    build_discord_avatar_url,
    build_presentation_event_payload,
    build_stats_headers,
    clear_plugin_cache,
    discord_avatar_ui_fetch_url,
    ensure_openlp_client_id,
    get_api_base,
    get_stats_request_timeouts,
    get_sync_pull_mode,
    is_discord_default_embed_avatar,
    json_pull_requires_auth,
    needs_account_profile_from_api,
    persist_auth_profile,
    resolve_account_identity,
    resolve_stats_url,
    resolve_sync_urls,
    _identity_from_mapping,
)

from .fakes import FakeSettings, fake_jwt_payload


def test_get_api_base_production_default():
    s = FakeSettings({'songstats/use production default': True})
    assert get_api_base(s) == DEFAULT_API_BASE


def test_resolve_stats_url_default():
    s = FakeSettings({'songstats/use production default': True})
    assert resolve_stats_url(s).endswith('/presentation-events')


def test_build_stats_headers_without_token():
    s = FakeSettings()
    headers = build_stats_headers(s)
    assert 'Authorization' not in headers
    assert headers['Content-Type'] == 'application/json'


def test_build_stats_headers_with_token():
    s = FakeSettings({'songstats/api token': 'tok'})
    headers = build_stats_headers(s)
    assert headers['Authorization'] == 'Bearer tok'


def test_discord_avatar_real_hash():
    url = build_discord_avatar_url(
        '238746528372621312',
        'ee2ba36591150b90475fcf8e9f951f26',
    )
    assert 'avatars/238746528372621312/' in url
    assert 'ee2ba365' in url
    assert 'size=256' in url


def test_discord_embed_placeholder_when_no_hash():
    url = build_discord_avatar_url('238746528372621312', '')
    assert '/embed/avatars/' in url


def test_is_discord_default_embed_avatar():
    assert is_discord_default_embed_avatar('https://cdn.discordapp.com/embed/avatars/2.png')
    assert not is_discord_default_embed_avatar(
        'https://cdn.discordapp.com/avatars/1/a.png?size=128'
    )


def test_discord_avatar_ui_fetch_url_bumps_size():
    src = 'https://cdn.discordapp.com/avatars/1/a.png?size=128'
    out = discord_avatar_ui_fetch_url(src, size=512)
    assert 'size=512' in out


def test_identity_from_mapping_auth_me_shape():
    data = {
        'discordId': '238746528372621312',
        'username': 'Dominik Szyja',
        'avatar': 'ee2ba36591150b90475fcf8e9f951f26',
    }
    identity = _identity_from_mapping(data)
    assert identity['name'] == 'Dominik Szyja'
    assert identity['avatar_hash'] == 'ee2ba36591150b90475fcf8e9f951f26'
    assert 'avatars/238746528372621312' in identity['avatar_url']


def test_resolve_account_identity_strips_embed_url():
    s = FakeSettings(
        {
            'songstats/api token': fake_jwt_payload(
                {'discordId': '238746528372621312', 'sub': 'mongo-id'}
            ),
            'songstats/auth profile': (
                '{"name": "X", "avatar_url": '
                '"https://cdn.discordapp.com/embed/avatars/2.png", '
                '"discord_id": "238746528372621312"}'
            ),
        }
    )
    identity = resolve_account_identity(s)
    assert identity['avatar_url'] == '' or 'avatars/238746528372621312' in identity['avatar_url']


def test_needs_account_profile_from_api():
    assert needs_account_profile_from_api({'avatar_url': '', 'discord_id': '1'})
    assert needs_account_profile_from_api(
        {'avatar_url': 'https://cdn.discordapp.com/embed/avatars/1.png'}
    )
    assert not needs_account_profile_from_api(
        {
            'avatar_url': 'https://cdn.discordapp.com/avatars/1/h.png',
            'avatar_hash': 'h',
            'discord_id': '238746528372621312',
        }
    )


def test_ensure_openlp_client_id_persists():
    s = FakeSettings()
    a = ensure_openlp_client_id(s)
    b = ensure_openlp_client_id(s)
    assert a == b
    assert a.startswith('openlp-')


def test_presentation_payload_anonymous():
    s = FakeSettings()
    ensure_openlp_client_id(s)
    payload = build_presentation_event_payload(
        s,
        openlp_song_id=42,
        mongo_song_id='507f1f77bcf86cd799439011',
        title='Test song',
        service_item_title='Service',
        presented_at='2026-01-01T12:00:00+00:00',
        song_metadata={'authors': 'A'},
    )
    allowed = {
        'clientId',
        'openlpSongId',
        'mongoSongId',
        'title',
        'serviceItemTitle',
        'presentedAt',
        'metadata',
    }
    assert set(payload.keys()) <= allowed
    assert 'source' not in payload
    assert payload['metadata']['loggedIn'] is False
    assert payload['metadata']['anonymousClient'] is True
    assert payload['clientId'].startswith('openlp-')
    assert payload['title'] == 'Test song'


def test_presentation_payload_logged_in():
    token = fake_jwt_payload(
        {
            'sub': 'user-mongo-id',
            'discordId': '238746528372621312',
            'name': 'Dominik',
        }
    )
    s = FakeSettings({'songstats/api token': token})
    persist_auth_profile(
        s,
        token,
        profile={
            'username': 'Dominik Szyja',
            'avatar': 'ee2ba36591150b90475fcf8e9f951f26',
            'discordId': '238746528372621312',
        },
    )
    payload = build_presentation_event_payload(
        s,
        openlp_song_id=1,
        mongo_song_id='abc',
        title='Pieśń',
        service_item_title='Niedziela',
        presented_at='2026-01-01T12:00:00+00:00',
        song_metadata={},
    )
    assert payload['metadata']['loggedIn'] is True
    assert 'anonymousClient' not in payload['metadata']
    assert payload['clientId'] == 'user-mongo-id'
    assert payload['metadata']['performerName']


def test_get_stats_request_timeouts_capped():
    s = FakeSettings({'songstats/timeout': 60})
    connect, read = get_stats_request_timeouts(s)
    assert connect == apiutil.get_connect_timeout()
    assert read <= 10.0


def test_resolve_sync_urls_first_sync_sqlite():
    s = FakeSettings({'songstats/use production default': True})
    pull, base, mode = resolve_sync_urls(s)
    assert 'export/sqlite' in pull
    assert mode == apiutil.SYNC_PULL_SQLITE


def test_resolve_sync_urls_incremental_with_local_version():
    s = FakeSettings(
        {
            'songstats/use production default': True,
            'songstats/local db version': '100',
            'songstats/sync pull mode': apiutil.SYNC_PULL_JSON,
        }
    )
    pull, _, mode = resolve_sync_urls(s)
    assert 'songs/changes' in pull
    assert 'sinceVersion=100' in pull
    assert mode == apiutil.SYNC_PULL_JSON


def test_json_pull_requires_auth_on_changes_url():
    s = FakeSettings(
        {
            'songstats/sync pull url': 'https://x/api/songs/changes?sinceVersion=1',
            'songstats/sync pull mode': apiutil.SYNC_PULL_JSON,
        }
    )
    assert json_pull_requires_auth(s) is True


def test_get_sync_pull_mode_invalid_falls_back():
    s = FakeSettings({'songstats/sync pull mode': 'nonsense'})
    assert get_sync_pull_mode(s) == apiutil.SYNC_PULL_JSON


def test_clear_plugin_cache_keeps_login_and_settings():
    s = FakeSettings(
        {
            'songstats/api token': 'tok',
            'songstats/api base url': DEFAULT_API_BASE,
            'songstats/auth profile': '{"name":"X"}',
            'songstats/logged in user id': 'abc',
            'songstats/local db version': '12',
            'songstats/master db version': '12',
            'songstats/last sync at': '2026-11-19T10:00:00+00:00',
            'songstats/last sync status': 'ok',
            'songstats/local catalog drift': True,
            'songstats/openlp client id': 'client-1',
        }
    )
    clear_plugin_cache(s)
    assert s.value('songstats/api token') == 'tok'
    assert s.value('songstats/api base url') == DEFAULT_API_BASE
    assert s.value('songstats/openlp client id') == 'client-1'
    assert s.value('songstats/local catalog drift') is True
    assert s.value('songstats/auth profile') is None
    assert s.value('songstats/logged in user id') is None
    assert s.value('songstats/local db version') is None
    assert s.value('songstats/master db version') is None
    assert s.value('songstats/last sync at') is None
    assert s.value('songstats/last sync status') is None