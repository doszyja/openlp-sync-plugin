# Agent notes (Cursor / AI)

1. Read **[CONTEXT.md](CONTEXT.md)** before editing plugin logic.
2. Public repo: **github.com/doszyja/openlp-sync-plugin** — to samo drzewo; install path `DataDir/contrib/`.
3. Keep imports as `contrib.plugins.songstats...` — required by OpenLP community loader.
4. After code changes for local OpenLP testing on Windows, copy to:
   `%APPDATA%\openlp\data\contrib\plugins\songstats\` (or run `install.ps1`).
5. Do not commit `__pycache__`, `dist/`, `releases/*.zip`.
6. User-facing strings: Polish in `translate('SongStatsPlugin', ...)`.
7. Network side effects (sync, stats, avatar) belong in **threads** (`ThreadWorker`, `run_thread`), not UI thread.
8. OAuth token exchange: POST `/auth/openlp/token` body `{code, state}` only (no `redirect_uri` in JSON).
9. Minimal diffs — match existing style in neighboring files.
10. Po zmianach w `lib/apiutil.py` / `apiclient.py` uruchom: `python -m pytest -q` w korzeniu repo.