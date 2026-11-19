# QSettings keys (`songstats/`)

Zarejestrowane w `lib/defaults.py` via `register_songstats_settings_defaults()`.

| Klucz | Opis |
|-------|------|
| `songstats/status` | `PluginStatus` |
| `songstats/enabled` | Wtyczka włączona |
| `songstats/api base url` | Np. `https://piesni…/api` |
| `songstats/api token` | JWT po OAuth |
| `songstats/auth profile` | JSON: name, avatar_url, discord_id, avatar_hash |
| `songstats/openlp client id` | Anonimowy ID instalacji (stats bez loginu) |
| `songstats/logged in user id` | Cache `sub` z JWT |
| `songstats/master db version` | Wersja serwera (wyświetlanie) |
| `songstats/local db version` | Wersja po udanym imporcie |
| `songstats/last sync at`, `last sync status` | UI paska |
| `songstats/sync pull mode` | `json` \| `sqlite` |
| `songstats/push on edit` | Push po `song_changed` |
| `songstats/timeout` | Domyślny read timeout HTTP (sync) |
| `songstats/force auth prompt` | Wymuś ponowne logowanie Discord |

`clear_auth_session()` usuwa token, `logged in user id`, `auth profile` — **nie** usuwa `openlp client id`.