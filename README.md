# Wtyczka KWCH dla OpenLP

OpenLP 4+ (Windows). Synchronizacja pieśni i statystyki: [piesni.swietochlowicekwch.pl](https://piesni.swietochlowicekwch.pl).

## Gdzie są wtyczki (portable)

| Folder | Co tam jest |
|--------|-------------|
| `App\OpenLP\plugins\` | Wbudowane wtyczki OpenLP (Pieśni, Biblia…) — **nie** KWCH |
| `Data\contrib\plugins\songstats\` | Kopia wtyczki KWCH przy danych portable |
| `%APPDATA%\openlp\data\contrib\` | **Stąd OpenLP na Windows ładuje wtyczki community** (w tym przy portable) |

Instalator kopiuje w odpowiednie miejsca sam.

## Instalacja

```powershell
$f = Join-Path $env:TEMP 'kwch-openlp-install.ps1'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1' -OutFile $f
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f
```

Portable — jeśli nie wykryje folderu `Data`, podaj go (nie `App\OpenLP`):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f -DataPath 'D:\OpenLPPortable\Data'
```

Po instalacji: zrestartuj OpenLP → **Zarządzaj wtyczkami** → **włącz** **KWCH Swietochlowice plugin**.

Kod: [github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin)