# Wydzielenie z monorepo OpenLP

## Co przenosisz

Cały katalog `contrib/` (ten repozytorium = jego zawartość w korzeniu):

- `__init__.py`
- `plugins/`
- `install.ps1`, `install.sh`, `package.ps1`
- `run-dev.*`, `dev/`

## Czego **nie** kopiujesz do nowego repo

- `__pycache__/`, `releases/*.zip` (odbuduj `package.ps1`)
- `openlp/`, `run_openlp_dev.py` — zostają w repo OpenLP

## Po sklonowaniu nowego repo

```bash
git init
git add .
git commit -m "Initial import: KWCH OpenLP songstats contrib"
```

Opcjonalnie w starym monorepo: usuń `contrib/` albo dodaj git submodule wskazujący na nowe repo.

## Git submodule (monorepo)

```bash
cd openlp-checkout
git rm -r contrib   # jeśli było w głównym repo
git submodule add <url-nowego-repo> contrib
```

Dev z monorepo nadal działa: `contrib/run-dev.ps1` wykrywa `../run_openlp_dev.py`.

## CI (opcjonalnie)

Minimum: lint `python -m compileall plugins` w workflow. Pełne testy OpenLP — w repo OpenLP.