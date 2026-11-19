# OpenLP — wtyczka KWCH (sync pieśni + statystyki live)

Wtyczka community łączy [OpenLP](https://openlp.org/) 4+ z katalogiem pieśni [KWCH Świętochłowice](https://piesni.swietochlowicekwch.pl): synchronizacja bazy, logowanie Discord, zliczanie prezentacji na żywo.

Kod i aktualizacje: **[github.com/doszyja/openlp-sync-plugin](https://github.com/doszyja/openlp-sync-plugin)**

## Instalacja (Windows, jedna komenda)

W **PowerShell** (wystarczy raz; wymaga internetu):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1 | iex"
```

Skrypt pobierze najnowsze pliki z GitHub i skopiuje wtyczkę do folderu danych OpenLP.

Potem **uruchom ponownie OpenLP** → **Ustawienia → Zarządzaj wtyczkami** → włącz **KWCH Swietochlowice plugin**.

## Po instalacji

- W pasku menu (u góry): synchronizacja, wersja bazy, konto Discord (opcjonalnie).
- Pieśń na **Live** wysyła statystykę na serwer KWCH (działa też bez logowania).

---

Dokumentacja techniczna, API, rozwój: [CONTEXT.md](CONTEXT.md)