# LifePilot Preview 4.5 — CasePack

Preview 4.5 rozszerza warstwę dowodową LifePilot z pojedynczego dokumentu na całą sprawę.

## CasePack ZIP

Dla jednej sprawy LifePilot może utworzyć pakiet zawierający:
- wszystkie dostępne oryginały;
- osobny manifest każdego dokumentu;
- manifest całej sprawy;
- chronologię;
- bezpieczne podsumowanie Markdown;
- sumy SHA-256;
- README.

## Brakujące oryginały

Jeżeli dokument istnieje w indeksie, ale jego lokalnego pliku już nie ma, CasePack nadal uwzględnia go w manifeście i jawnie oznacza brak. Brakujący plik nie jest pomijany po cichu.

## Weryfikacja

Dotychczasowy ekran weryfikacji ProofPack rozpoznaje teraz automatycznie:
- ProofPack — jeden dokument;
- CasePack — cała sprawa.

Dla CasePack sprawdzane są:
- struktura ZIP;
- duplikaty i niebezpieczne ścieżki;
- limity rozmiaru;
- kompletność podstawowych plików;
- SHA-256 wszystkich wpisów wskazanych w checksumach;
- zgodność oryginałów z manifestem;
- zgodność dostępnych oryginałów z wcześniej zapisanym hashem indeksu.

Rozjazd z indeksem jest ostrzeżeniem, o ile sam CasePack jest wewnętrznie spójny.

## Prywatność

CasePack nie zawiera pełnego tekstu OCR ani lokalnych ścieżek systemowych. Tworzenie i weryfikacja odbywają się lokalnie.

## Status

Preview 4.5 nie zmienia schematu SQLite i zachowuje model local-first / human-in-the-loop.
