# LifePilot Preview 4.8 — Functional Release Self-Test

Preview 4.8 koncentruje się na jakości gotowego wydania Windows.

## Co było wcześniej

`DocPilot.exe --self-test` sprawdzał:
- obecność zasobów aplikacji;
- zgodność wersji;
- obecność dokumentu demo.

## Co sprawdza teraz

W izolowanym katalogu tymczasowym wykonywany jest również przepływ LifePilot:
- analiza dokumentu;
- korekta kluczowych pól;
- Decision Trail;
- Case Readiness;
- CasePack;
- weryfikacja CasePack;
- stan „załatwione”;
- aktywna kolejka;
- historia całej sprawy.

## Izolacja

Self-test:
- nie korzysta z dokumentów użytkownika;
- nie pozostawia testowej bazy ani plików po zakończeniu;
- przywraca pierwotny obiekt ustawień aplikacji;
- nie wymaga developerskiego `httpx` ani `TestClient`.

## Windows gate

Pipeline Windows uruchamia `--self-test` na:
1. świeżo zbudowanym pakiecie;
2. czystej instalacji;
3. aplikacji po upgrade ze starej wersji.

Dzięki temu zielony Windows Release potwierdza nie tylko start EXE, ale także podstawowy funkcjonalny przepływ LifePilot w finalnym artefakcie.

## Status

Preview 4.8 nie zmienia schematu SQLite ani zachowania danych użytkownika.
