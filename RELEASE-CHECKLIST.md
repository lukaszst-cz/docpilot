# DocPilot 0.9 → 1.0 — release checklist

Ta lista opisuje warunki, które trzeba zamknąć przed oznaczeniem DocPilot 1.0.0 jako stabilnego wydania. Nowe funkcje nie są celem tej fazy; liczy się przewidywalne działanie obecnych funkcji.

## Automatyczne bramki

- [x] `node --check app.js`
- [x] pełne `pytest -q`
- [x] build aplikacji Windows
- [x] build modułu powiadomień
- [x] obecność DocPilot.exe, DocPilotNotifier.exe i Tesseract OCR w paczce
- [x] self-test spakowanego DocPilot.exe
- [x] build Portable ZIP
- [x] build instalatora Windows
- [x] upgrade smoke test z publicznego v0.5.1 bez utraty danych
- [x] SHA-256 dla instalatora i Portable ZIP

Automatyczne bramki zostały potwierdzone przez GitHub Actions na `main` po scaleniu rozszerzonej macierzy testów przed 1.0.

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

- [x] wybór lokalnego pliku nie zmienia oryginału przed zatwierdzeniem
- [x] rename wymaga potwierdzenia i zapisuje zmianę w historii
- [x] move + rename wymaga potwierdzenia i zapisuje zmianę w historii
- [x] Undo przywraca plik do poprzedniego miejsca
- [x] błąd operacji nie zostawia częściowo przeniesionego pliku
- [x] Exact Duplicate jest rozpoznawany po SHA-256
- [x] Near Duplicate można porównać bez automatycznego kasowania

## Codzienny workflow

- [x] first-run checklist działa na czystej instalacji
- [x] safe demo działa bez wskazywania prywatnych dokumentów
- [x] Deadline Radar pokazuje wykryte terminy
- [x] Review Queue pokazuje dokumenty wymagające decyzji
- [x] Search znajduje dokument po treści
- [x] Q&A pokazuje odpowiedź razem ze źródłami
- [x] Cases & Timeline działa po przypisaniu dokumentów do sprawy
- [x] eksport kalendarza działa
- [x] backup indeksu działa
- [x] full archive backup działa
- [x] restart aplikacji zachowuje indeks i ustawienia

## Windows

- [x] czysta instalacja na Windows 11
- [x] uruchomienie z menu Start
- [x] opcjonalny skrót na pulpicie
- [x] OCR PL/EN działa w instalatorze
- [x] aktualizacja istniejącej instalacji zachowuje dane
- [x] deinstalacja nie usuwa danych użytkownika bez wyraźnej decyzji
- [x] SmartScreen / brak podpisu jest jasno opisany w README

## UX i dostępność

- [x] całą główną nawigację da się obsłużyć klawiaturą
- [x] focus jest widoczny
- [x] aktywny widok ma `aria-current`
- [x] podstawowe pola Search i Q&A mają etykiety dostępności
- [x] komunikaty błędów są czytelne i nie pokazują surowego tracebacku
- [x] długie ścieżki i nazwy plików nie rozwalają layoutu
- [x] interfejs pozostaje używalny przy węższym oknie

## Warunek wydania 1.0

1. Wszystkie automatyczne bramki są zielone.
2. Nie ma błędu powodującego utratę, nadpisanie lub niekontrolowane przeniesienie dokumentu.
3. Nie ma błędu blokującego instalację, start, import dokumentu, wyszukiwanie lub Undo.
4. Pozostałe znane ograniczenia są opisane w README/release notes.
5. Integracje opcjonalne nie blokują 1.0, o ile podstawowy lokalny workflow działa stabilnie.


## Stan 1.0.0 — 28.09.2026

- kod `main` ma wersję **1.0.0**;
- zwykłe CI dla commita 1.0.0 jest zielone;
- pełny Windows Release dla commita 1.0.0 jest zielony;
- artefakt `DocPilot-Windows` zawiera instalator, Portable ZIP i `SHA256SUMS.txt`;
- tag `v1.0.0` został utworzony z commita zweryfikowanego pełnym Windows buildem;
- publiczny GitHub Release **DocPilot v1.0.0** został opublikowany;
- release zawiera instalator Windows, Portable ZIP i `SHA256SUMS.txt`;
- checksumy instalatora i Portable ZIP zostały zweryfikowane przed publikacją.

Wydanie 1.0.0 jest publiczne. Wszystkie pozycje tej checklisty mają potwierdzenie w testach lub zweryfikowanym Windows Release; nie ma już otwartych bramek wydania 1.0.
