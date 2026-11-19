# CONTEXT — Song Stats (KWCH) OpenLP plugin

Dokument techniczny (architektura, instalacja dla dev, API). Użytkownikom: [README.md](README.md) i [github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin). Aktualizuj przy większych zmianach API lub UX.

## Repozytorium publiczne

- URL: **https://github.com/doszyja/openlp-sync-plugin**
- Korzeń repo = dawne drzewo `contrib/` z monorepo OpenLP (`__init__.py`, `plugins/`, skrypty).
- Instalacja zdalna (Windows): `install-from-github.ps1` (wywoływany one-linerem z README).

## Układ w OpenLP (DataDir)

Po instalacji:

```text
<DataDir>/contrib/
  __init__.py
  plugins/
    songstats/
      songstatsplugin.py
      openlp-plugin.json
      lib/ ...
```

OpenLP ładuje moduły jako `contrib.plugins.<nazwa>.<pluginfile>` — **pakiet `contrib` musi zostać** w folderze danych (importy `from contrib.plugins.songstats...`, bez zmiany na `songstats.*`).

Mechanizm: `sys.path` wstawia `DataDir`, potem `extension_loader(..., community=True)` importuje `contrib.plugins.songstats.songstatsplugin`.

## Wtyczki w tym repo

| ID | Klasa | Opis |
|----|--------|------|
| `songstats` | `SongStatsPlugin` | Sync katalogu, Discord OAuth, statystyki live, pasek menu |

## Wymagania

- OpenLP **≥ 4.0** z obsługą `DataDir/contrib`
- Zależności OpenLP: m.in. **PyQt5**, **requests**
- API KWCH (domyślnie `https://piesni.swietochlowicekwch.pl/api`)

## Instalacja — skrót

| Sposób | Plik / akcja |
|--------|----------------|
| Windows (użytkownik) | README → pobierz `install-from-github.ps1` do `%TEMP%` i uruchom (`-DataPath` dla portable) |
| Windows (clone repo) | `install.ps1` → `<DataDir>/contrib/` (wykrywa AppData, portable `Data`, rejestr; `-DataPath`) |
| Linux/macOS | `install.sh`, opcjonalnie `OPENLP_DATA` |
| ZIP release | `package.ps1` → `dist/*-import.zip`, `*-contrib.zip` |

Po instalacji: restart OpenLP → Plugin Manager → **KWCH Swietochlowice plugin** → ustawienia / menu konto.

## Funkcje (songstats)

- **Live**: `slidecontroller_live_started` + pieśń → wątek `POST /presentation-events` (także bez JWT; `songstats/openlp client id`).
- **Sync**: wersja katalogu, pull JSON/SQLite; push po edycji gdy API wymaga tokenu.
- **Konto**: OAuth `/auth/openlp`, profil/avatar `GET /auth/me`.

## Struktura repozytorium

```text
.
├── README.md                 ← użytkownik (krótki)
├── CONTEXT.md                ← ten plik
├── AGENTS.md
├── CHANGELOG.md / VERSION / LICENSE
├── install.ps1 / install.sh / install-from-github.ps1
├── package.ps1
├── dev/
├── plugins/songstats/
└── releases/                 ← ZIP (gitignore)
```

Rozwój: [docs/DEV.md](docs/DEV.md) · QSettings: [docs/SETTINGS.md](docs/SETTINGS.md) · wydzielenie z monorepo: [docs/MIGRATION.md](docs/MIGRATION.md).

## Relacja do OpenLP core

OpenLP = osobne repo/instalacja. To repo = wyłącznie community `contrib`. Importy muszą pozostać w przestrzeni nazw `contrib`.

## Licencja

GPL-3.0-or-later — [LICENSE](LICENSE).

## Testy jednostkowe (standalone)

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

- Katalog `tests/` — stub `DataDir/contrib` + minimalne `openlp.*` (`conftest.py`).
- Pokrycie bez pełnego OpenLP: **`apiutil`** (JWT, URL, payload stats, sync), **`syncmessages`**, **`pluginutil`**, **`apiclient`** (mock `requests`), **`syncstatusbar`** (funkcje czyste + opcjonalnie PyQt5).
- **Nie** w tej warstwie: pełny `songsync.py` / `sqliteimport.py` / UI pluginu (SQLAlchemy, Registry, okna) — wymagają OpenLP w dev lub testów integracyjnych.

CI: `.github/workflows/validate.yml` uruchamia `pytest` z `QT_QPA_PLATFORM=offscreen`.

## Cel

Community plugin **songstats** dla OpenLP 4+:

1. Synchronizacja lokalnej bazy pieśni z API NestJS KWCH (`/songs/...`, wersje, pull JSON/SQLite).
2. Statystyki prezentacji na żywo (`POST /presentation-events`).
3. Logowanie użytkownika Discord/KWCH (OAuth `auth/openlp`) — audit i pull wymagające JWT.
4. Pasek w menu głównym: sync, wersje, konto + dropdown.

**Nie** jest częścią core OpenLP — ładowany z `AppLocation.DataDir/contrib` jako pakiet Python `contrib`.

## Backend (produkcja)

| Ustawienie | Domyślnie |
|------------|-----------|
| API base | `https://piesni.swietochlowicekwch.pl/api` |
| Web (OAuth) | wynika z `songstats/web base url` lub API base bez `/api` |

Kluczowe endpointy używane przez wtyczkę:

| Metoda | Ścieżka | Użycie |
|--------|---------|--------|
| GET | `/songs/version` | Wersja katalogu na serwerze |
| GET | `/songs/changes` … | Pull przyrostowy (JWT) |
| GET/POST | `/songs/...` | Push/pull, SQLite dump |
| POST | `/auth/openlp/token` | Wymiana kodu OAuth → JWT |
| GET | `/auth/me` | Avatar Discord, username (nie w JWT) |
| POST | `/presentation-events` | Statystyka live (JWT opcjonalny) |

JWT często ma `discordId` bez hash avatara → UI woła **`/auth/me`** jak strona web.

## OpenLP — punkty zaczepienia

- `Registry().register_function('slidecontroller_live_started', ...)` — tylko wejście pieśni na **Live** (nie sam podgląd).
- `Registry().register_function('song_changed', ...)` — push po lokalnej edycji.
- `Settings` (QSettings): prefiks `songstats/...` (zob. `lib/defaults.py`).

## Pliki (songstats)

| Plik | Rola |
|------|------|
| `songstatsplugin.py` | Plugin, sync, live stats, nagłówek |
| `lib/apiutil.py` | URL, JWT, tożsamość, payload stats, timeouty |
| `lib/apiclient.py` | `SongStatsPostWorker` — wątek POST stats |
| `lib/openlpauth.py` | OAuth localhost:8765, logout |
| `lib/syncstatusbar.py` | UI paska menu |
| `lib/synchttp.py` | Wątki HTTP sync/push/pull |
| `lib/songsync.py` | Mapowanie pieśni, import zdalny, `songstats:remote_id=` |
| `lib/sqliteimport.py` | Zamiana DB z exportu SQLite |
| `lib/songstatstab.py` | Zakładka ustawień |
| `lib/syncmessages.py` | Komunikaty błędów (PL) |

## Zachowania ważne (regresje)

- **Po błędzie sync** nie czyścić `songstats/local db version`.
- **Stats offline**: krótki timeout (`get_stats_request_timeouts`), `RequestException` → `log.debug`, brak dialogów UI.
- **Stats bez loginu**: `ensure_openlp_client_id`, `metadata.anonymousClient`.
- **Avatar**: nie traktować `cdn.../embed/avatars/` jako prawdziwego zdjęcia; przebudować z `/auth/me`.
- **Deploy dev**: często kopiować do `%APPDATA%\openlp\data\contrib\plugins\songstats\` — OpenLP nie czyta drzewa git bezpośrednio.

## Instalacja / moduł Python

Ścieżka docelowa:

```text
DataDir/contrib/__init__.py
DataDir/contrib/plugins/songstats/songstatsplugin.py
```

Loader OpenLP: `extension_loader(..., community=True)` → `import contrib.plugins.songstats.songstatsplugin`.

## Wersja

Numer w `VERSION`, `songstatsplugin.Plugin.version`, `openlp-plugin.json`, `package.ps1` ($Version) — utrzymuj spójnie przy release.