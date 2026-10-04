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


## Lokalny Pilot Runner

Do kontrolowanego pilota na dokumentach, których nie wolno dodawać do publicznego repo, służy lokalne polecenie:

```powershell
docpilot-pilot "C:\ścieżka\do\folderu-z-próbkami" --output "C:\ścieżka\do\wyników"
```

Domyślnie tworzone są tylko:
- `pilot-public.json` — zredukowane techniczne wyniki bez nazw plików, ścieżek, pełnego OCR, wartości issuerów, kwot i hashy;
- `pilot-report.md` — tabela techniczna + ręczna checklista porównania z oryginałem.

Dokładny lokalny raport można włączyć jawnie:

```powershell
docpilot-pilot "C:\ścieżka\do\folderu-z-próbkami" --output "C:\ścieżka\do\wyników" --include-private
```

Wtedy powstaje dodatkowy `pilot-private.json`. Może zawierać względne nazwy plików, issuerów, kwoty i SHA-256. **Nie publikować go w publicznym repozytorium.**

Katalog `lifepilot-pilot-results/` jest ignorowany przez Git, ale to nie zastępuje ręcznej kontroli raportu przed jakąkolwiek publikacją.
