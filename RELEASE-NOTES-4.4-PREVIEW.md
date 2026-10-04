# LifePilot Preview 4.4 — ProofPack Verifier

Preview 4.4 dodaje lokalną weryfikację pakietów ProofPack.

## Co sprawdza verifier

- czy plik jest poprawnym ZIP;
- czy archiwum nie ma duplikatów nazw;
- czy nie zawiera ścieżek typu `../` albo absolutnych ścieżek;
- czy mieści się w limitach bezpieczeństwa;
- czy zawiera wymagane pliki ProofPack;
- czy dokładnie jeden plik znajduje się w `original/`;
- czy `SHA256SUMS.txt` ma prawidłowy format;
- czy wszystkie zapisane SHA-256 odpowiadają faktycznej zawartości;
- czy oryginał zgadza się z `computed_digest` manifestu;
- czy oryginał zgadza się z hashem zapisanym wcześniej w indeksie DocPilot.

## Dwa poziomy wyniku

**Integralność pakietu** odpowiada na pytanie: „czy zawartość ProofPack została zmieniona?”.

**Zgodność z indeksem** odpowiada na inne pytanie: „czy oryginał pakowany do ProofPack był tym samym plikiem, który wcześniej zindeksował DocPilot?”.

Rozjazd z indeksem jest ostrzeżeniem nawet wtedy, gdy sam ZIP jest wewnętrznie spójny.

## Bezpieczeństwo

Verifier czyta ZIP bez wypakowywania go do katalogu użytkownika. Stosuje limity liczby wpisów i sumarycznego rozmiaru, a hashe dużych elementów liczy strumieniowo.

## Status

Preview 4.4 nie zmienia schematu SQLite ani granic local-first.
