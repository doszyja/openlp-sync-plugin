# OpenLP — wtyczka KWCH Świętochłowice

Synchronizacja pieśni i statystyki live z [katalogiem KWCH](https://piesni.swietochlowicekwch.pl). Wymaga OpenLP 4+.

Repozytorium: [github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin)

## Instalacja (Windows)

**PowerShell** — wklej cały blok:

```powershell
$f = Join-Path $env:TEMP 'kwch-openlp-install.ps1'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1' -OutFile $f
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f
```

Z klonu repozytorium: `powershell -NoProfile -ExecutionPolicy Bypass -File .\install-from-github.ps1`

### OpenLP portable

Portable trzyma dane w folderze `Data` obok programu (nie w `%APPDATA%`). Uruchom portable raz, potem doinstaluj wtyczkę:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f -DataPath 'D:\sciezka\do\OpenLPPortable\Data'
```

(albo `.\install.ps1 -DataPath '…'` z katalogu repozytorium)

Po instalacji: zrestartuj OpenLP → **Zarządzaj wtyczkami** → włącz **KWCH Swietochlowice plugin**.

Dokumentacja techniczna: [CONTEXT.md](CONTEXT.md)