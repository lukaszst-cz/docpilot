# LifePilot — macierz akceptacyjna

Celem tej macierzy jest sprawdzanie zachowania LifePilot na reprezentatywnych klasach dokumentów bez publikowania prywatnych materiałów użytkownika.

## Automatyczny baseline syntetyczny

| Przypadek | Oczekiwane zachowanie |
| --- | --- |
| Faktura | rozpoznanie faktury, terminu i `to-pay` |
| Wezwanie / pismo urzędowe | rozpoznanie pisma, terminu i `to-reply` |
| Polisa | rozpoznanie ubezpieczenia i terminu |
| Gwarancja | wyliczenie końca gwarancji na podstawie daty dokumentu |
| Umowa do podpisu | `to-sign` |
| Dokument szkolny | klasyfikacja `school` |
| Korespondencja szkody | klasyfikacja insurance + sugestia sprawy |
| Słaby skan | niski health/confidence → ręczna weryfikacja |
| Dokument bez terminu | bez fałszywego deadline; zwykłe archiwum |
| Niejednoznaczny „Termin:” | brak zgadywania deadline → ręczna weryfikacja |

Automatyczny zestaw znajduje się w `test_lifepilot_acceptance.py`. Preview 4.9 rozszerza go również o: wiele dat z jawnym terminem, sprawę z 2 dokumentami, CasePack z brakującym oryginałem oraz korektę pól z ponownym przeliczeniem decyzji.

## Zasada bezpieczeństwa

Testy preferują **fałszywy negatyw / ręczne sprawdzenie** zamiast pewnej rekomendacji opartej na niejednoznacznym odczycie. LifePilot nie powinien zgadywać terminu tylko dlatego, że w dokumencie występuje data.

## Co nadal wymaga pilota na realnych dokumentach

Syntetyczne testy nie zastępują kontrolowanego pilota. Przed publiczną betą należy sprawdzić zanonimizowane lub prywatnie przechowywane materiały reprezentujące:
- różne układy faktur;
- pisma urzędowe z terminem liczonym „od dnia doręczenia”;
- skany pod kątem, zdjęcia telefonu i wielostronicowe PDF;
- dokumenty z wieloma datami;
- kwoty ujemne / korekty;
- polisy z różnymi okresami ochrony;
- dokumenty, w których termin nie jest datą kalendarzową;
- dokumenty wielojęzyczne.

Wyniki realnego pilota powinny być zapisywane bez dołączania prywatnych oryginałów do publicznego repozytorium.

## Uruchomienie pilota na Windows

Domyślna ścieżka dla użytkownika po instalacji:
1. otwórz menu Start;
2. uruchom **LifePilot Pilot**;
3. wybierz folder z dokumentami do pilota;
4. poczekaj na zakończenie analizy;
5. otwórz utworzony `pilot-report.md` i porównaj wynik z dokumentami źródłowymi.

Launcher korzysta z tego samego lokalnego silnika co `docpilot-pilot`. Wyniki trafiają lokalnie do `AppData\Local\DocPilot\PilotResults\...`.

Domyślnie tworzone są tylko:
- `pilot-public.json` — zredukowane techniczne wyniki bez nazw plików, ścieżek, pełnego OCR, wartości issuerów, kwot i hashy;
- `pilot-report.md` — tabela techniczna + ręczna checklista porównania z oryginałem.

`pilot-private.json` nie jest tworzony przez zwykły launcher. Dokładny lokalny raport można włączyć wyłącznie jawnie w wersji CLI:

```powershell
docpilot-pilot "C:\ścieżka\do\folderu-z-próbkami" --output "C:\ścieżka\do\wyników" --include-private
```

Wtedy powstaje dodatkowy `pilot-private.json`. Może zawierać względne nazwy plików, issuerów, kwoty i SHA-256. **Nie publikować go w publicznym repozytorium.**

Katalog `lifepilot-pilot-results/` jest ignorowany przez Git, ale to nie zastępuje ręcznej kontroli raportu przed jakąkolwiek publikacją.

## Finalny automatyczny gate przed pilotem ręcznym

PR **#82 — LifePilot: one-click pilot launcher** został scalony do `main`.

Windows Release **#88**, run `37299036015`, dla merge commitu `cdcd5ac3a1eb4e662b66cae193741d28afaac7b5` zakończył się sukcesem i potwierdził:
- pilot na spakowanym EXE;
- clean install + skrót **LifePilot Pilot** + pilot + uninstall;
- zachowanie danych użytkownika po uninstall;
- upgrade z v4.0.0 + skrót + pilot;
- brak `pilot-private.json` bez jawnego opt-in;
- brak nazwy źródłowego pliku i lokalnej ścieżki w publicznym raporcie;
- checksumy i artefakt `DocPilot-Windows`.

Od tego momentu jedynym blockerem akceptacyjnym pozostaje ręczny pilot na realnych lub zanonimizowanych dokumentach oraz ręczny przegląd UX i poprawności wyników.
