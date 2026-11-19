# OpenLP — KWCH Song Stats

Synchronizacja pieśni i statystyki live z [KWCH Świętochłowice](https://piesni.swietochlowicekwch.pl). OpenLP 4+, Windows.

**PowerShell**

```powershell
$f = Join-Path $env:TEMP 'kwch-openlp-install.ps1'; Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue; Invoke-WebRequest -UseBasicParsing -Headers @{ 'Cache-Control' = 'no-cache' } -Uri 'https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1' -OutFile $f; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f
```

**Wiersz polecenia (cmd)** — `curl` jest w Windows 10+; uruchamia ten sam skrypt przez `powershell.exe`:

```bat
del /f /q "%TEMP%\kwch-openlp-install.ps1" 2>nul & curl -fsSL -H "Cache-Control: no-cache" -o "%TEMP%\kwch-openlp-install.ps1" "https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1" & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\kwch-openlp-install.ps1"
```

Z klonu: `powershell -NoProfile -ExecutionPolicy Bypass -File .\install-from-github.ps1`

Po instalacji: zrestartuj OpenLP → **Zarządzaj wtyczkami** → **KWCH Swietochlowice plugin**. Nie używaj `irm | iex` (BOM).

[github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin) · [CONTEXT.md](CONTEXT.md)