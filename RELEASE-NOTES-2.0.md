# DocPilot 2.0.0

DocPilot 2.0 rozwija codzienną pracę z dokumentami bez odchodzenia od lokalnego, bezpiecznego modelu z wersji 1.0.

## Reguły seryjnych dokumentów

- reguły można edytować, wstrzymywać, ponownie włączać i usuwać;
- warunki mogą uwzględniać wystawcę, fragment tekstu i typ dokumentu;
- reguły mogą ustawiać kategorię, profil i tagi;
- analiza pokazuje listę reguł, które zadziałały;
- nowsza pasująca reguła może jawnie nadpisać kategorię lub profil ustawiony przez starszą.

## Documents i operacje masowe

- lista dokumentów ma zaznaczanie pojedynczych rekordów i całej widocznej strony;
- można grupowo przypisać sprawę, profil albo wymaganą akcję;
- masowa zmiana działa w jednej transakcji SQLite i jest zapisywana w audycie;
- pojedyncza operacja jest ograniczona do 500 dokumentów;
- operacje masowe zmieniają metadane indeksu i nie wykonują ukrytych ruchów plików.

## Cases & Timeline

Sprawy pokazują teraz:

- liczbę dokumentów;
- liczbę otwartych działań;
- używane profile;
- najbliższy przyszły termin;
- liczbę terminów przeterminowanych;
- rozszerzoną chronologię z kategorią, profilem, typem dokumentu i możliwością otwarcia źródła.

## Duże archiwa

- Documents używa paginowanych, lekkich rekordów zamiast pobierania pełnej treści setek dokumentów do UI;
- filtrowanie listy odbywa się w SQLite;
- sortowanie po aktualizacji ma osobny indeks;
- Duplicate Finder może ponownie wykorzystać już załadowaną listę dokumentów zamiast wykonywać kolejny pełny odczyt;
- regresje są sprawdzane na syntetycznym archiwum ponad 1000 dokumentów.

## Profile i przestrzenie

- `Home` zachowuje dotychczasowy układ archiwum dla kompatybilności;
- inne profile podczas operacji `organize` trafiają do `archive/Profiles/<profile>/...`;
- nazwa profilu jest sanitizowana przed użyciem jako element ścieżki;
- dwa profile mogą przechowywać plik o tej samej nazwie bez wzajemnego konfliktu;
- Undo działa również dla plików przeniesionych do przestrzeni profilu.

Zmiana profilu w samych metadanych nie przenosi istniejącego pliku między przestrzeniami. Fizyczny ruch pozostaje osobną, świadomą operacją na pliku.

## Bezpieczeństwo i kompatybilność

DocPilot 2.0 zachowuje mechanizmy 1.0:

- zatwierdzenie przed rename/move;
- weryfikację operacji i rollback;
- Undo;
- lokalny OCR, Search i Q&A;
- clean-install i upgrade smoke tests Windows;
- uninstall bez kasowania danych użytkownika;
- instalator, Portable ZIP i SHA-256 generowane przez Windows Release workflow.

## Znane ograniczenia

- instalator nadal nie ma komercyjnego podpisu code-signing;
- OCR i automatyczna ekstrakcja danych wymagają weryfikacji przy ważnych terminach i kwotach;
- operacje masowe nie przenoszą fizycznie istniejących plików między przestrzeniami profili;
- integracje zewnętrzne pozostają etapem 3.0.
