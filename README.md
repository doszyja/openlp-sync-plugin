# OpenLP — wtyczka KWCH (sync pieśni + statystyki live)

Wtyczka community łączy [OpenLP](https://openlp.org/) 4+ z katalogiem pieśni [KWCH Świętochłowice](https://piesni.swietochlowicekwch.pl): synchronizacja bazy, logowanie Discord, zliczanie prezentacji na żywo.

Kod i aktualizacje: **[github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin)**

## Instalacja (Windows)

W **PowerShell** wklej **cały blok** (wymaga internetu; działa w oknie PS — nie owijaj w drugie `powershell -Command`):

```powershell
$f = Join-Path $env:TEMP 'kwch-openlp-install.ps1'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1' -OutFile $f
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f
```

Z katalogu sklonowanego repo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-from-github.ps1
```

(Opcjonalnie tylko lokalne pliki: `.\install.ps1`.)

Nie używaj `irm … | iex` — BOM z GitHub psuje pierwszą linię skryptu.

Potem **zrestartuj OpenLP** → **Ustawienia → Zarządzaj wtyczkami** → włącz **KWCH Swietochlowice plugin**.

## Po instalacji

- W pasku menu (u góry): synchronizacja, wersja bazy, konto Discord (opcjonalnie).
- Pieśń na **Live** wysyła statystykę na serwer KWCH (działa też bez logowania).

---

Dokumentacja techniczna: [CONTEXT.md](CONTEXT.md)