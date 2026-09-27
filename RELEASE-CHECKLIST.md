# DocPilot 0.9 → 1.0 — release checklist

Ta lista opisuje warunki, które trzeba zamknąć przed oznaczeniem DocPilot 1.0.0 jako stabilnego wydania. Nowe funkcje nie są celem tej fazy; liczy się przewidywalne działanie obecnych funkcji.

## Automatyczne bramki

- [x] `node --check app.js`
- [x] pełne `pytest -q`
- [ ] build aplikacji Windows
- [ ] build modułu powiadomień
- [ ] obecność DocPilot.exe, DocPilotNotifier.exe i Tesseract OCR w paczce
- [ ] self-test spakowanego DocPilot.exe
- [ ] build Portable ZIP
- [ ] build instalatora Windows
- [ ] upgrade smoke test z publicznego v0.5.1 bez utraty danych
- [ ] SHA-256 dla instalatora i Portable ZIP

## Typowe dokumenty

Każdy przypadek sprawdzamy na kopii testowej, bez prywatnych danych.

- [x] zwykły PDF z warstwą tekstową
- [x] skanowany PDF
- [x] JPG / PNG dokumentu
- [x] faktura z kwotą i terminem
- [x] paragon
- [x] umowa
- [x] pismo urzędowe lub sądowe
- [x] dokument szkolny
- [x] dokument wielostronicowy
- [x] polskie znaki w treści i nazwie pliku
- [x] dokument bez daty lub kwoty
- [x] nieobsługiwany typ pliku
- [x] plik przekraczający limit importu

## Bezpieczna praca na plikach

- [ ] wybór lokalnego pliku nie zmienia oryginału przed zatwierdzeniem
- [ ] rename wymaga potwierdzenia i zapisuje zmianę w historii
- [ ] move + rename wymaga potwierdzenia i zapisuje zmianę w historii
- [x] Undo przywraca plik do poprzedniego miejsca
- [x] błąd operacji nie zostawia częściowo przeniesionego pliku
- [x] Exact Duplicate jest rozpoznawany po SHA-256
- [x] Near Duplicate można porównać bez automatycznego kasowania

## Codzienny workflow

- [x] first-run checklist ma test stanu pierwszego uruchomienia
- [x] safe demo działa bez wskazywania prywatnych dokumentów
- [ ] Deadline Radar pokazuje wykryte terminy
- [ ] Review Queue pokazuje dokumenty wymagające decyzji
- [ ] Search znajduje dokument po treści
- [ ] Q&A pokazuje odpowiedź razem ze źródłami
- [ ] Cases & Timeline działa po przypisaniu dokumentów do sprawy
- [ ] eksport kalendarza działa
- [ ] backup indeksu działa
- [ ] full archive backup działa
- [ ] restart aplikacji zachowuje indeks i ustawienia

## Windows

- [ ] czysta instalacja na Windows 11
- [ ] uruchomienie z menu Start
- [x] opcjonalny skrót na pulpicie
- [x] OCR PL/EN działa w środowisku Windows Release
- [ ] aktualizacja istniejącej instalacji zachowuje dane
- [x] deinstalacja nie usuwa danych użytkownika
- [x] SmartScreen / brak podpisu jest jasno opisany w README

## UX i dostępność

- [x] główna nawigacja ma obsługę klawiatury i test kontraktowy
- [x] focus ma widoczny styl `:focus-visible`
- [x] aktywny widok ma `aria-current`
- [x] pola Search i Q&A mają etykiety dostępności
- [ ] komunikaty błędów są czytelne i nie pokazują surowego tracebacku
- [ ] długie ścieżki i nazwy plików nie rozwalają layoutu
- [ ] interfejs pozostaje używalny przy węższym oknie

## Warunek wydania 1.0

1. Wszystkie automatyczne bramki są zielone.
2. Nie ma błędu powodującego utratę, nadpisanie lub niekontrolowane przeniesienie dokumentu.
3. Nie ma błędu blokującego instalację, start, import dokumentu, wyszukiwanie lub Undo.
4. Pozostałe znane ograniczenia są opisane w README/release notes.
5. Integracje opcjonalne nie blokują 1.0, o ile podstawowy lokalny workflow działa stabilnie.
