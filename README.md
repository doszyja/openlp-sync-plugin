# Wtyczka KWCH dla OpenLP

OpenLP 4+ (Windows). Synchronizacja pieśni i statystyki: [piesni.swietochlowicekwch.pl](https://piesni.swietochlowicekwch.pl).

## Instalacja

```powershell
$f = Join-Path $env:TEMP 'kwch-openlp-install.ps1'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1' -OutFile $f
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f
```

OpenLP **portable**: po jednym uruchomieniu aplikacji skrypt zwykle sam znajdzie folder `Data`. Jeśli nie — dopisz ścieżkę:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f -DataPath 'D:\TwojOpenLP\Data'
```

Zrestartuj OpenLP → **Zarządzaj wtyczkami** → **KWCH Swietochlowice plugin**.

Kod: [github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin)