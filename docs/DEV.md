# Development

## Checkout layout

| Repo | Zawartość |
|------|-----------|
| **To repozytorium** | Plugin + `install.*` / `package.ps1` |
| **OpenLP** (osobny clone) | `run_openlp_dev.py`, `openlp/`, `.venv` |

## Zmienne środowiskowe

| Zmienna | Znaczenie |
|---------|-----------|
| `OPENLP_SRC` | Ścieżka do katalogu głównego checkoutu OpenLP (z `run_openlp_dev.py`) |
| `OPENLP_DATA` | Nadpisanie katalogu danych (Linux/macOS `install.sh`) |

## Szybki cykl (Windows)

1. Sklonuj OpenLP do np. `C:\dev\ope` i utwórz venv (`contrib\run-dev.ps1` w monorepo lub `py -3 -m venv` + `pip install -e .`).
2. Sklonuj **to** repo obok lub gdzie indziej.
3. Zainstaluj plugin w data dir:

   ```powershell
   cd path\to\kwch-openlp-contrib
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```

4. Uruchom OpenLP z kodu:

   ```powershell
   cd path\to\kwch-openlp-contrib
   powershell -ExecutionPolicy Bypass -File dev\run-with-openlp.ps1
   ```

   Wymaga `OPENLP_SRC` (patrz skrypt).

## Szybki cykl (tylko zainstalowany OpenLP)

Po każdej zmianie:

```powershell
./install.ps1
# restart OpenLP
```

Albo kopiuj tylko `plugins/songstats` do `%APPDATA%\openlp\data\contrib\plugins\songstats`.

## Logi

- Dev: `run_openlp_dev.py -l debug` (konsola + cache OpenLP).
- Stats sieciowe: poziom `debug` — `Song Stats POST skipped (network)`.

## Pakiet release

```powershell
powershell -ExecutionPolicy Bypass -File package.ps1
```

Edytuj `$Version` w `package.ps1` oraz `VERSION`, `openlp-plugin.json`, `SongStatsPlugin` version w `songstatsplugin.py`.

## Testy jednostkowe (bez OpenLP core)

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Stuby w `tests/conftest.py` symulują `DataDir/contrib` i minimalne moduły `openlp.*`. Moduły z pełnym Qt/SQLAlchemy (np. cały `songsync.py`) są testowane pośrednio przez `apiutil`, `pluginutil`, `apiclient`.

Na CI ustawiane jest `QT_QPA_PLATFORM=offscreen` (test pixmapy).

## Test manualny (checklist)

- [ ] Włączenie wtyczki, pasek menu widoczny
- [ ] Sync / sprawdź aktualizacje (z siecią i bez)
- [ ] Logowanie OAuth, avatar w menu, wylogowanie
- [ ] Pieśń na Live → `presentation-events` (zalogowany i nie)
- [ ] Edycja pieśni → push (jeśli włączony i JWT)

## Backend

Repozytorium API KWCH jest **poza** tym projektem. Przy zmianach kontraktu (payload stats, auth) zsynchronizuj `lib/apiutil.py` i dokumentację w `CONTEXT.md`.