# -*- coding: utf-8 -*-
"""
Shared HTTP helpers for the Song Stats plugin (OpenLP Database / NestJS API).
"""
import base64
import json
import re
import uuid
from urllib.parse import urljoin, urlparse

SYNC_PULL_JSON = 'json'
SYNC_PULL_SQLITE = 'sqlite'

DEFAULT_API_BASE = 'https://piesni.swietochlowicekwch.pl/api'


def build_auth_headers(settings, user_agent='OpenLP-SongStats/1.2', accept=None):
    headers = {
        'Accept': accept or 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': user_agent,
    }
    token = settings.value('songstats/api token')
    if token:
        headers['Authorization'] = 'Bearer {token}'.format(token=token)
    return headers


def build_stats_headers(settings, user_agent='OpenLP-SongStats/1.2'):
    """
    POST /presentation-events. Works without login; when JWT is present, send it so the
    server can bind the event to the logged-in app user (like audit logs).
    """
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': user_agent,
    }
    token = settings.value('songstats/api token')
    if token and str(token).strip():
        headers['Authorization'] = 'Bearer {0}'.format(str(token).strip())
    return headers


def get_timeout(settings):
    timeout = settings.value('songstats/timeout')
    return float(timeout) if timeout else 30.0


def get_connect_timeout():
    """TCP connect cap so a bad host/DNS does not block the UI for the full read timeout."""
    return 5.0


def get_request_timeouts(settings):
    """
    ``requests`` timeout tuple: (connect_seconds, read_seconds).
    """
    return get_connect_timeout(), get_timeout(settings)


def get_stats_request_timeouts(settings):
    """
    Background POST /presentation-events only — short cap so a dropped connection
    never ties up a worker thread for the full sync timeout (default 30s).
    """
    _, read = get_request_timeouts(settings)
    read_cap = min(float(read), 10.0)
    return get_connect_timeout(), max(3.0, read_cap)


def get_api_base(settings):
    """
    API base URL e.g. https://example.com/api (Openlp-database Nest global prefix).
    """
    explicit = (settings.value('songstats/api base url') or '').strip().rstrip('/')
    if explicit:
        return explicit
    if settings.value('songstats/use production default', True) is not False:
        return DEFAULT_API_BASE

    stats_url = (settings.value('songstats/api url') or '').strip()
    if not stats_url:
        return ''

    parsed = urlparse(stats_url)
    if not parsed.scheme or not parsed.netloc:
        return ''

    path = parsed.path or ''
    if '/api' in path:
        api_path = path[: path.index('/api') + len('/api')]
        return '{scheme}://{netloc}{path}'.format(
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            path=api_path,
        )
    return '{scheme}://{netloc}/api'.format(scheme=parsed.scheme, netloc=parsed.netloc)


def get_sync_pull_mode(settings):
    mode = (settings.value('songstats/sync pull mode') or SYNC_PULL_JSON).strip().lower()
    if mode not in (SYNC_PULL_JSON, SYNC_PULL_SQLITE):
        return SYNC_PULL_JSON
    return mode


def json_pull_requires_auth(settings):
    """Incremental pull / songs/changes needs JWT from KWCH web login (any app account)."""
    if get_sync_pull_mode(settings) != SYNC_PULL_JSON:
        return False
    pull, _, _ = resolve_sync_urls(settings)
    pull_l = pull or ''
    return 'all-openlp' in pull_l or 'songs/changes' in pull_l


def resolve_sync_urls(settings):
    """
    Return (pull_url, songs_api_base, pull_mode).

    Default JSON mode:
      - first successful sync path: public GET /songs/export/sqlite (full OpenLP dump)
      - later syncs: GET /songs/changes?sinceVersion= (JWT)
    Explicit SQLite mode always uses the dump (can duplicate songs — not for routine sync).
    """
    pull = (settings.value('songstats/sync pull url') or '').strip()
    songs_base = (settings.value('songstats/sync push url') or '').strip().rstrip('/')
    pull_mode = get_sync_pull_mode(settings)

    api_base = get_api_base(settings)
    if not api_base:
        return pull, songs_base, pull_mode

    if not pull:
        local_version, use_incremental = _local_catalog_version_for_pull(settings)
        if use_incremental:
            pull = urljoin(
                api_base + '/',
                'songs/changes?sinceVersion={0}'.format(local_version),
            )
            pull_mode = SYNC_PULL_JSON
        elif pull_mode == SYNC_PULL_SQLITE:
            pull = urljoin(api_base + '/', 'songs/export/sqlite')
        else:
            # First sync (no stored catalog version): full SQLite dump, no JWT.
            pull = urljoin(api_base + '/', 'songs/export/sqlite')
            pull_mode = SYNC_PULL_SQLITE

    if not songs_base:
        songs_base = api_base

    return pull, songs_base, pull_mode


def resolve_public_catalog_url(settings):
    """GET /songs/all — public index used after SQLite bootstrap (remote ids)."""
    custom = (settings.value('songstats/sync pull url') or '').strip()
    if custom and 'songs/all' in custom:
        return custom
    api_base = get_api_base(settings)
    if not api_base:
        return ''
    return urljoin(api_base + '/', 'songs/all')


def is_sqlite_dump_pull(pull_url, pull_mode):
    return pull_mode == SYNC_PULL_SQLITE and 'export/sqlite' in (pull_url or '')


def _local_catalog_version_for_pull(settings):
    """
    Return (version_int_or_0, use_incremental_pull).
    Incremental pull uses stored local db version from the last successful import;
    a later failed sync does not clear that baseline.
    """
    local_raw = (settings.value('songstats/local db version') or '').strip()
    if not local_raw:
        return 0, False
    try:
        return int(local_raw), True
    except ValueError:
        return 0, False


def get_web_base(settings):
    """
    Public web origin for /auth/openlp (no /api suffix).
    """
    explicit = (settings.value('songstats/web base url') or '').strip().rstrip('/')
    if explicit:
        return explicit

    api_base = get_api_base(settings)
    if not api_base:
        return ''

    if api_base.endswith('/api'):
        return api_base[:-4]
    return api_base


def resolve_version_url(settings):
    """
    GET /songs/version → { \"version\": <int> } (Openlp-database).
    """
    custom = (settings.value('songstats/version url') or '').strip()
    if custom:
        return custom
    api_base = get_api_base(settings)
    if not api_base:
        return ''
    return urljoin(api_base + '/', 'songs/version')


def resolve_stats_url(settings):
    """
    POST target for presentation-events (live stats).
    """
    custom = (settings.value('songstats/api url') or '').strip()
    if custom:
        return custom
    api_base = get_api_base(settings)
    if api_base:
        return urljoin(api_base + '/', 'presentation-events')
    return ''


def _decode_jwt_payload(token):
    token = (token or '').strip()
    parts = token.split('.')
    if len(parts) < 2:
        return None
    segment = parts[1]
    padding = '=' * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + padding)
        return json.loads(raw.decode('utf-8'))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _looks_like_discord_snowflake(value):
    text = str(value).strip()
    return text.isdigit() and 17 <= len(text) <= 20


def _clean_avatar_hash(value):
    text = (value or '').strip()
    if not text or text.lower() in ('null', 'none', 'undefined', '0'):
        return ''
    return text


def build_discord_avatar_url(discord_id, avatar_hash):
    did = (discord_id or '').strip()
    if not did or not _looks_like_discord_snowflake(did):
        return ''
    avatar_hash = _clean_avatar_hash(avatar_hash)
    if not avatar_hash:
        bucket = int(did) % 5
        return 'https://cdn.discordapp.com/embed/avatars/{n}.png'.format(n=bucket)
    ext = 'gif' if avatar_hash.startswith('a_') else 'png'
    return 'https://cdn.discordapp.com/avatars/{uid}/{hash}.{ext}?size=256'.format(
        uid=did,
        hash=avatar_hash,
        ext=ext,
    )


def alternate_discord_avatar_url(url):
    """Some networks resolve media.discordapp.net when cdn.discordapp.com fails."""
    if not url or 'cdn.discordapp.com' not in url:
        return ''
    return url.replace('cdn.discordapp.com', 'media.discordapp.net')


def discord_avatar_ui_fetch_url(url, size=256):
    """Request a larger CDN asset for crisp menubar icons (HiDPI downscale)."""
    text = (url or '').strip()
    if not text:
        return ''
    if is_discord_default_embed_avatar(text):
        return text
    if re.search(r'[?&]size=\d+', text):
        return re.sub(r'(?<=[?&])size=\d+', 'size={0}'.format(int(size)), text, count=1)
    sep = '&' if '?' in text else '?'
    return '{0}{1}size={2}'.format(text, sep, int(size))


def is_discord_default_embed_avatar(url):
    """Placeholder when Discord user id is known but avatar hash was missing."""
    text = (url or '').strip().lower()
    return '/embed/avatars/' in text


def _identity_from_mapping(data):
    """Build identity dict from a flat or nested API / token user object."""
    empty = {'name': '', 'avatar_url': '', 'discord_id': '', 'avatar_hash': ''}
    if not isinstance(data, dict):
        return empty
    nested = []
    for key in ('user', 'discord', 'profile', 'account', 'discordUser'):
        value = data.get(key)
        if isinstance(value, dict):
            nested.append(value)
    sources = nested + [data]

    def first(*keys):
        for src in sources:
            for key in keys:
                value = src.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
        return ''

    name = first(
        'global_name',
        'globalName',
        'discordGlobalName',
        'discord_global_name',
        'displayName',
        'display_name',
        'full_name',
        'fullName',
        'username',
        'userName',
        'discordUsername',
        'discord_username',
        'preferred_username',
        'name',
        'nick',
    )
    discord_id = ''
    for key in (
        'discordId',
        'discord_id',
        'discordUserId',
        'discord_user_id',
        'id',
        'sub',
    ):
        for src in sources:
            value = src.get(key)
            if value is not None and _looks_like_discord_snowflake(value):
                discord_id = str(value).strip()
                break
        if discord_id:
            break
    avatar_hash = _clean_avatar_hash(
        first(
            'avatar',
            'avatarHash',
            'avatar_hash',
            'discordAvatar',
            'discord_avatar',
            'discordAvatarHash',
        )
    )
    avatar_url = ''
    direct = first('avatarUrl', 'avatar_url', 'picture', 'image')
    if direct.startswith('http://') or direct.startswith('https://'):
        avatar_url = direct
    else:
        avatar_url = build_discord_avatar_url(discord_id, avatar_hash or direct)
    return {
        'name': name,
        'avatar_url': avatar_url,
        'discord_id': discord_id,
        'avatar_hash': avatar_hash,
    }


def identity_from_jwt(token):
    """
    Display name + Discord avatar URL from KWCH JWT payload (no signature check).
    """
    payload = _decode_jwt_payload(token)
    if not isinstance(payload, dict):
        return {'name': '', 'avatar_url': '', 'discord_id': '', 'avatar_hash': ''}
    return _identity_from_mapping(payload)


def client_id_from_jwt(token):
    """Extract user / client identifier from KWCH JWT (no signature verification)."""
    payload = _decode_jwt_payload(token)
    if not isinstance(payload, dict):
        return ''
    for key in (
        'sub',
        'userId',
        'user_id',
        'clientId',
        'client_id',
        'id',
        'discordId',
        'discord_id',
    ):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    user = payload.get('user')
    if isinstance(user, dict):
        for key in ('id', '_id', 'userId', 'sub'):
            value = user.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return ''


def persist_auth_profile(settings, token, profile=None):
    """Save Discord display fields from login response or JWT for UI / stats."""
    jwt_identity = identity_from_jwt(token)
    if profile:
        mapped = _identity_from_mapping(profile)
        identity = {
            'name': mapped.get('name') or jwt_identity.get('name'),
            'avatar_url': mapped.get('avatar_url') or jwt_identity.get('avatar_url'),
            'discord_id': mapped.get('discord_id') or jwt_identity.get('discord_id'),
            'avatar_hash': mapped.get('avatar_hash') or jwt_identity.get('avatar_hash'),
        }
    else:
        identity = jwt_identity
    avatar_url = (identity.get('avatar_url') or '').strip()
    avatar_hash = (identity.get('avatar_hash') or '').strip()
    discord_id = (identity.get('discord_id') or '').strip()
    if is_discord_default_embed_avatar(avatar_url):
        if avatar_hash and discord_id:
            identity['avatar_url'] = build_discord_avatar_url(discord_id, avatar_hash)
        else:
            identity['avatar_url'] = ''
    if identity.get('name') or identity.get('avatar_url') or identity.get('discord_id'):
        settings.setValue('songstats/auth profile', json.dumps(identity, ensure_ascii=False))
    persist_logged_in_client_id(settings, token)
    return identity


def _load_persisted_identity(settings):
    raw = settings.value('songstats/auth profile') or ''
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return _identity_from_mapping(data)
    return {}


def resolve_account_identity(settings):
    """Name + avatar URL for the menubar account control."""
    token = (settings.value('songstats/api token') or '').strip()
    if not token:
        return {'name': '', 'avatar_url': '', 'discord_id': '', 'avatar_hash': ''}
    jwt_identity = identity_from_jwt(token)
    stored = _load_persisted_identity(settings)
    name = jwt_identity.get('name') or stored.get('name') or ''
    discord_id = jwt_identity.get('discord_id') or stored.get('discord_id') or ''
    avatar_url = jwt_identity.get('avatar_url') or stored.get('avatar_url') or ''
    avatar_hash = jwt_identity.get('avatar_hash') or stored.get('avatar_hash') or ''
    if not avatar_url and discord_id:
        avatar_url = build_discord_avatar_url(discord_id, avatar_hash)
    if is_discord_default_embed_avatar(avatar_url):
        if avatar_hash and discord_id:
            avatar_url = build_discord_avatar_url(discord_id, avatar_hash)
        else:
            avatar_url = ''
    return {
        'name': name,
        'avatar_url': avatar_url,
        'discord_id': discord_id,
        'avatar_hash': avatar_hash,
    }


def needs_account_profile_from_api(identity):
    """
    True when we should call GET /auth/me (same source as the KWCH web UI).
    """
    if not identity:
        return True
    url = (identity.get('avatar_url') or '').strip()
    if not url:
        return bool(identity.get('discord_id') or identity.get('name'))
    if is_discord_default_embed_avatar(url):
        return True
    return bool(identity.get('discord_id') and not identity.get('avatar_hash'))


def fetch_identity_from_api(settings):
    """
    Fallback GET (JWT) when login/JWT payload lacks Discord avatar hash.
    Returns empty dict on failure.
    """
    import requests

    from openlp.core.common.httputils import get_proxy_settings

    api_base = get_api_base(settings)
    if not api_base:
        return {}
    connect_timeout, read_timeout = get_request_timeouts(settings)
    headers = build_auth_headers(settings)
    token = (settings.value('songstats/api token') or '').strip()
    if not token:
        return {}
    for path in ('auth/me',):
        url = urljoin(api_base + '/', path)
        try:
            response = requests.get(
                url,
                headers=headers,
                proxies=get_proxy_settings(),
                timeout=(connect_timeout, read_timeout),
            )
            if response.status_code != 200:
                continue
            data = response.json()
            if not isinstance(data, dict):
                continue
            user = data.get('user') if isinstance(data.get('user'), dict) else data
            identity = _identity_from_mapping(user)
            if identity.get('name') or identity.get('avatar_url') or identity.get('discord_id'):
                persist_auth_profile(settings, token, profile=identity)
                return identity
        except requests.RequestException:
            continue
    return {}


def persist_logged_in_client_id(settings, token):
    """Cache presentation-events clientId after browser login."""
    client_id = client_id_from_jwt(token)
    if client_id:
        settings.setValue('songstats/logged in user id', client_id)
    return client_id


def ensure_openlp_client_id(settings):
    """
    Persistent install id so POST /presentation-events works without Discord login.
    Not cleared on logout.
    """
    key = 'songstats/openlp client id'
    existing = (settings.value(key) or '').strip()
    if existing:
        return existing
    client_id = 'openlp-{0}'.format(uuid.uuid4().hex)
    settings.setValue(key, client_id)
    return client_id


def resolve_presentation_client_id(settings):
    """
    Stable app user id for stats / audit (JWT sub or cached id), else legacy church id,
    else anonymous OpenLP install id.
    """
    token = (settings.value('songstats/api token') or '').strip()
    if token:
        client_id = client_id_from_jwt(token)
        if client_id:
            return client_id
        cached = (settings.value('songstats/logged in user id') or '').strip()
        if cached:
            return cached
    church_id = (settings.value('songstats/church id') or '').strip()
    if church_id:
        return church_id
    return ensure_openlp_client_id(settings)


def build_presentation_event_payload(
    settings,
    *,
    openlp_song_id,
    mongo_song_id,
    title,
    service_item_title,
    presented_at,
    song_metadata,
):
    """
    Body for POST /presentation-events — aligned with KWCH audit entries:
    who (performedBy / userId), what (entity), when (presentedAt).
    """
    token = (settings.value('songstats/api token') or '').strip()
    identity = resolve_account_identity(settings) if token else {}
    user_id = resolve_presentation_client_id(settings)
    display_name = (identity.get('name') or '').strip()
    discord_id = (identity.get('discord_id') or '').strip()

    performed_by = {}
    if user_id:
        performed_by['userId'] = user_id
        performed_by['clientId'] = user_id
    if display_name:
        performed_by['name'] = display_name
        performed_by['displayName'] = display_name
    elif not token:
        performed_by['displayName'] = 'OpenLP'
        performed_by['anonymous'] = True
    if discord_id:
        performed_by['discordId'] = discord_id

    entity_id = mongo_song_id or (str(openlp_song_id) if openlp_song_id is not None else None)
    entity = {
        'type': 'song',
        'title': title,
    }
    if entity_id:
        entity['id'] = entity_id
    if mongo_song_id:
        entity['mongoSongId'] = mongo_song_id
    if openlp_song_id is not None:
        entity['openlpSongId'] = openlp_song_id

    metadata = dict(song_metadata or {})
    metadata['loggedIn'] = bool(token)
    if not token:
        metadata['anonymousClient'] = True

    payload = {
        'source': 'openlp',
        'eventType': 'song_presentation',
        'action': 'present',
        'clientId': user_id,
        'userId': user_id,
        'performedBy': performed_by or None,
        'actor': performed_by or None,
        'entity': entity,
        'openlpSongId': openlp_song_id,
        'mongoSongId': mongo_song_id,
        'title': title,
        'serviceItemTitle': service_item_title,
        'presentedAt': presented_at,
        'metadata': metadata,
    }
    return {key: value for key, value in payload.items() if value is not None}


def clear_auth_session(settings):
    """Remove JWT and cached user id (Discord logout from OpenLP)."""
    settings.remove('songstats/api token')
    settings.remove('songstats/logged in user id')
    settings.remove('songstats/auth profile')