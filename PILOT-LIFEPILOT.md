# LifePilot — checklista pilota

Ta checklista określa minimalny poziom przed nazwaniem LifePilot używalną publiczną betą.

## A. Podstawowy przepływ

- [x] Import dokumentu.
- [x] Lokalna analiza.
- [x] „Co teraz?” po analizie.
- [x] Priorytet na podstawie terminu.
- [x] Centralna kolejka działań.
- [x] Filtry kolejki.
- [x] Oznaczanie pozycji jako załatwionej.
- [x] Przywracanie pozycji.
- [x] Ponowne pojawienie się uwagi po zmianie stanu dokumentu.

## B. ProofPack

- [x] ZIP z oryginałem.
- [x] Manifest.
- [x] Next action.
- [x] Timeline sprawy.
- [x] SHA256SUMS.
- [x] README z ograniczeniami.
- [x] Podgląd zawartości przed pobraniem.
- [x] Brak pełnego OCR w manifeście.
- [x] Brak lokalnej ścieżki w manifeście.
- [ ] Smoke test ProofPack z gotowego Windows EXE — dodany do Preview 4.9; zaznaczyć po zielonym Windows gate.
- [ ] Test brakującego/usuniętego oryginału na gotowej instalacji — dodany do Preview 4.9; zaznaczyć po zielonym Windows gate.

## C. Terminy

- [x] Wykryty termin trafia do „Co teraz?”.
- [x] Eksport pojedynczego .ics.
- [x] Rozróżnienie po terminie / dziś / pilne / wkrótce.
- [ ] Test stref czasowych i dat granicznych na gotowej instalacji.
- [ ] Test rzeczywistych pism z różnymi sposobami zapisu terminu.

## D. Prywatność

- [x] Local-first.
- [x] CzyToŚciema? otwiera się osobno.
- [x] Brak automatycznej wysyłki OCR do CzyToŚciema?.
- [x] ProofPack powstaje lokalnie.
- [ ] Ręczny przegląd prywatności finalnego builda.

## E. Niezawodność

- [x] Pełne CI dla linii Preview 4.8.
- [x] Windows build.
- [x] Self-test EXE.
- [x] Clean install.
- [ ] Upgrade z DocPilot v4.0.0 — Preview 4.9 zmienia Windows gate z historycznego v0.5.1 na faktyczne stabilne v4.0.0; zaznaczyć dopiero po zielonym runie.
- [x] Uninstall bez utraty danych użytkownika.
- [x] OCR smoke na obrazie i skanowanym PDF w pełnym Windows gate.
- [ ] Recovery smoke po aktualizacji.

## F. Pilot dokumentów

Do pilota lokalnego użyj `docpilot-pilot`. Domyślny raport jest zredukowany prywatnościowo; dokładny raport lokalny wymaga jawnego `--include-private`.



Przed szerszą publikacją sprawdzić minimum:
- [ ] faktura;
- [ ] pismo urzędowe;
- [ ] wezwanie z terminem odpowiedzi;
- [ ] polisa;
- [ ] gwarancja;
- [ ] umowa;
- [ ] dokument szkolny;
- [ ] korespondencja ubezpieczeniowa;
- [ ] skan słabej jakości;
- [ ] dokument bez terminu;
- [ ] dokument z błędnie odczytanym terminem.

## Warunek publicznej bety

Publiczna beta może być oznaczona dopiero wtedy, gdy:
1. sekcja E przejdzie bez blockerów;
2. pilot dokumentów nie pokaże błędów prowadzących do niebezpiecznej rekomendacji bez ostrzeżenia;
3. ProofPack z gotowej instalacji będzie odtwarzalny i czytelny;
4. opis produktu i ograniczeń będzie zgodny z faktycznym działaniem.

## G. Macierz akceptacyjna

- [x] Automatyczny baseline syntetyczny dla głównych klas dokumentów.
- [x] Słaby skan kierowany do ręcznej kontroli.
- [x] Niejednoznaczny termin nie jest zgadywany.
- [x] Brak prywatnych fixture'ów w publicznym repo.
- [ ] Kontrolowany pilot na realnych, prywatnych lub zanonimizowanych dokumentach.

Szczegóły: [LIFEPILOT-ACCEPTANCE.md](LIFEPILOT-ACCEPTANCE.md).
