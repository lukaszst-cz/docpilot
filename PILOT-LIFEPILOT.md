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
- [x] Smoke test ProofPack z gotowego Windows EXE — Preview 4.9 Windows run 37209580044.
- [x] Test brakującego/usuniętego oryginału w funkcjonalnym self-teście gotowego EXE / clean install / upgrade — Preview 4.9.

## C. Terminy

- [x] Wykryty termin trafia do „Co teraz?”.
- [x] Eksport pojedynczego .ics.
- [x] Rozróżnienie po terminie / dziś / pilne / wkrótce.
- [x] Test dat granicznych priorytetu oraz eksportu .ics na dniach zmiany czasu w finalnym self-teście — Preview 5.0, finalny Windows Release run 37299036015 (#88).
- [x] Eksport .ics używa całodniowego `VALUE=DATE`, jawnego `DTEND` następnego dnia i nie zapisuje lokalnej ścieżki pliku.
- [ ] Test rzeczywistych pism z różnymi sposobami zapisu terminu.

## D. Prywatność

- [x] Local-first.
- [x] CzyToŚciema? otwiera się osobno.
- [x] Brak automatycznej wysyłki OCR do CzyToŚciema?.
- [x] ProofPack powstaje lokalnie.
- [x] Automatyczny privacy smoke finalnego builda: Decision Trail, ProofPack/CasePack i .ics bez ujawniania lokalnych ścieżek; metadane pakietów bez pełnego OCR.
- [x] Pilot public-safe nie zapisuje nazwy pliku ani lokalnej ścieżki źródłowej; `pilot-private.json` nie powstaje bez jawnego opt-in — Windows Release #88.
- [ ] Ręczny przegląd prywatności finalnego builda.

## E. Niezawodność

- [x] Pełne CI dla linii Preview 5.0.
- [x] Windows build.
- [x] Self-test EXE.
- [x] LifePilot Pilot na gotowym, spakowanym EXE.
- [x] Clean install.
- [x] LifePilot Pilot po clean install.
- [x] Upgrade z DocPilot v4.0.0 — finalny Preview 5.0 Windows Release run 37299036015 (#88).
- [x] LifePilot Pilot po upgrade z v4.0.0.
- [x] Uninstall bez utraty danych użytkownika.
- [x] OCR smoke na obrazie i skanowanym PDF w pełnym Windows gate.
- [x] Recovery smoke checkpoint → zmiana → restore w finalnym EXE, clean install i po upgrade — Preview 5.0.
- [x] Artefakt `DocPilot-Windows` z instalatorem, Portable ZIP i SHA256SUMS został utworzony w runie #88.

## F. Pilot dokumentów

Na zainstalowanym Windows uruchom z menu Start **LifePilot Pilot**, wybierz folder dokumentów i poczekaj na raport. Launcher korzysta z tego samego lokalnego silnika co `docpilot-pilot`.

Domyślne wyniki są zapisywane lokalnie w `AppData\Local\DocPilot\PilotResults\...` i obejmują tylko:
- `pilot-public.json`;
- `pilot-report.md`.

Dokładny `pilot-private.json` nie jest tworzony przez zwykły launcher. Wymaga jawnego `--include-private` w wersji CLI i nie powinien być publikowany.

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
