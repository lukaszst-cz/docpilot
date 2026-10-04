# LifePilot Preview 4.2 — Trust & Decision Provenance

Preview 4.2 koncentruje się na zaufaniu do rekomendacji i czytelności stanu.

## Dlaczego LifePilot tak zaleca?

Każda rekomendacja zawiera teraz:
- źródło danych: automatyczny odczyt albo dane ręcznie sprawdzone;
- poziom pewności automatycznej ekstrakcji;
- czas ręcznej weryfikacji;
- jawne elementy podstawy decyzji, np. typ dokumentu, termin i kod akcji.

UI pokazuje te informacje bez zasłaniania głównego komunikatu „Co teraz?”.

## Semantyczne „załatwione”

Poprzednia wersja używała sygnatury obejmującej techniczny `updated_at`. Preview 4.2 używa sygnatury semantycznej, która obejmuje m.in.:
- hash pliku;
- termin;
- kwotę i walutę;
- typ i wystawcę;
- sprawę;
- akcję;
- status ręcznej weryfikacji.

Dzięki temu czysto techniczna zmiana czasu aktualizacji nie przywraca pozycji do kolejki, ale rzeczywista zmiana danych wpływających na decyzję — tak.

## Historia zamknięcia

Nowe wpisy „załatwione” przechowują również `done_at`, co pozwala pokazać użytkownikowi kiedy sprawa została zamknięta.

Starszy format `document_id -> hash` pozostaje obsługiwany.

## Status

Preview 4.2 nie zmienia schematu SQLite i zachowuje local-first, human-in-the-loop oraz brak automatycznych destrukcyjnych działań.
