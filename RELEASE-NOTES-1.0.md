# DocPilot 1.0.0

Pierwsze stabilne wydanie DocPilot przeznaczone do codziennej, lokalnej pracy z dokumentami na Windows.

## Najważniejsze funkcje

- Smart Inbox z analizą dokumentu przed wykonaniem zmiany.
- OCR obrazów i skanowanych PDF-ów w języku polskim i angielskim.
- wykrywanie typu dokumentu, dat, kwot, numerów referencyjnych i terminów;
- Deadline Radar i oznaczanie wymaganych działań;
- Review Queue dla dokumentów wymagających decyzji człowieka;
- lokalne Search & Q&A ze wskazaniem dokumentów źródłowych;
- sprawy i chronologia dokumentów;
- wykrywanie duplikatów SHA-256 i bezpieczne porównanie near-duplicates;
- historia operacji oraz Undo dla rename/move;
- eksport kalendarza, backup indeksu i pełny backup archiwum;
- diagnostyka lokalnych danych i opcjonalne powiadomienia.

## Bezpieczeństwo plików

DocPilot nie wykonuje rename/move przed zatwierdzeniem przez użytkownika. Operacja jest weryfikowana na dysku, a niepotwierdzona zmiana uruchamia rollback. Undo przywraca plik i synchronizuje wpis w lokalnym indeksie SQLite.

Duplicate Finder nie usuwa plików automatycznie.

## Windows

Pakiet wydania zawiera:

- `DocPilot-Setup-Windows-x64.exe`;
- `DocPilot-Portable-Windows-x64.zip`;
- `SHA256SUMS.txt`.

Workflow wydania sprawdza:

- testy Pythona i składnię JavaScript;
- OCR obrazu oraz skanowanego PDF-u;
- build aplikacji i modułu powiadomień;
- obecność wymaganych plików w paczce;
- self-test spakowanego EXE;
- czystą instalację, skrót Start i uninstall z zachowaniem danych;
- upgrade z v0.5.1 po uruchomieniu starej bazy SQLite;
- sumy SHA-256 gotowych artefaktów.

## Prywatność

Podstawowy workflow działa lokalnie. Dokumenty używane przez OCR, indeks, Search, Q&A, Duplicate Finder i Cases nie są wysyłane do usługi chmurowej.

Integracje z pocztą, Notion i Google Calendar są opcjonalne i wymagają osobnej konfiguracji.

## Znane ograniczenia

- instalator nie ma komercyjnego podpisu code-signing, więc Windows może wyświetlić SmartScreen;
- OCR i automatyczne rozpoznawanie danych mogą się pomylić — ważne terminy i kwoty trzeba sprawdzić w oryginale;
- kopię po redakcji danych należy obejrzeć przed udostępnieniem;
- integracje zewnętrzne są dodatkiem i nie są wymagane do podstawowego lokalnego workflow.
