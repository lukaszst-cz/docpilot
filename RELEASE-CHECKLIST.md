# DocPilot 0.9 → 1.0 — release checklist

Ta lista opisuje warunki, które trzeba zamknąć przed oznaczeniem DocPilot 1.0.0 jako stabilnego wydania. Nowe funkcje nie są celem tej fazy; liczy się przewidywalne działanie obecnych funkcji.

## Automatyczne bramki

- [ ] `node --check app.js`
- [ ] pełne `pytest -q`
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

- [ ] zwykły PDF z warstwą tekstową
- [ ] skanowany PDF
- [ ] JPG / PNG dokumentu
- [ ] faktura z kwotą i terminem
- [ ] paragon
- [ ] umowa
- [ ] pismo urzędowe lub sądowe
- [ ] dokument szkolny
- [ ] dokument wielostronicowy
- [ ] polskie znaki w treści i nazwie pliku
- [ ] dokument bez daty lub kwoty
- [ ] nieobsługiwany typ pliku
- [ ] plik przekraczający limit importu

## Bezpieczna praca na plikach

- [ ] wybór lokalnego pliku nie zmienia oryginału przed zatwierdzeniem
- [ ] rename wymaga potwierdzenia i zapisuje zmianę w historii
- [ ] move + rename wymaga potwierdzenia i zapisuje zmianę w historii
- [ ] Undo przywraca plik do poprzedniego miejsca
- [ ] błąd operacji nie zostawia częściowo przeniesionego pliku
- [ ] Exact Duplicate jest rozpoznawany po SHA-256
- [ ] Near Duplicate można porównać bez automatycznego kasowania

## Codzienny workflow

- [ ] first-run checklist działa na czystej instalacji
- [ ] safe demo działa bez wskazywania prywatnych dokumentów
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
- [ ] opcjonalny skrót na pulpicie
- [ ] OCR PL/EN działa w instalatorze
- [ ] aktualizacja istniejącej instalacji zachowuje dane
- [ ] deinstalacja nie usuwa danych użytkownika bez wyraźnej decyzji
- [ ] SmartScreen / brak podpisu jest jasno opisany w README

## UX i dostępność

- [ ] całą główną nawigację da się obsłużyć klawiaturą
- [ ] focus jest widoczny
- [ ] aktywny widok ma `aria-current`
- [ ] podstawowe pola Search i Q&A mają etykiety dostępności
- [ ] komunikaty błędów są czytelne i nie pokazują surowego tracebacku
- [ ] długie ścieżki i nazwy plików nie rozwalają layoutu
- [ ] interfejs pozostaje używalny przy węższym oknie

## Warunek wydania 1.0

1. Wszystkie automatyczne bramki są zielone.
2. Nie ma błędu powodującego utratę, nadpisanie lub niekontrolowane przeniesienie dokumentu.
3. Nie ma błędu blokującego instalację, start, import dokumentu, wyszukiwanie lub Undo.
4. Pozostałe znane ograniczenia są opisane w README/release notes.
5. Integracje opcjonalne nie blokują 1.0, o ile podstawowy lokalny workflow działa stabilnie.
