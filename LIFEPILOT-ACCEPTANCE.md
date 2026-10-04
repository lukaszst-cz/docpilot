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

Automatyczny zestaw znajduje się w `test_lifepilot_acceptance.py`.

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
