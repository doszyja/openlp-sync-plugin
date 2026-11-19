# OpenLP — KWCH Song Stats

Synchronizacja pieśni i statystyki live z [KWCH Świętochłowice](https://piesni.swietochlowicekwch.pl). OpenLP 4+, Windows.

**Instalacja (PowerShell, jedna linia):**

```powershell
$f = Join-Path $env:TEMP 'kwch-openlp-install.ps1'; Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue; Invoke-WebRequest -UseBasicParsing -Headers @{ 'Cache-Control' = 'no-cache' } -Uri 'https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1' -OutFile $f; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f
```

Z klonu: `powershell -NoProfile -ExecutionPolicy Bypass -File .\install-from-github.ps1`

Zrestartuj OpenLP i włącz wtyczkę w **Zarządzaj wtyczkami**. Nie używaj `irm | iex` (BOM).

[github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin) · [CONTEXT.md](CONTEXT.md)