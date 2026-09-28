# DocPilot 4.0.0

DocPilot 4.0 jest wydaniem dojrzałościowym. Nie zmienia podstawowego sposobu pracy z dokumentami — wzmacnia bezpieczeństwo aktualizacji, odzyskiwanie po awarii, diagnostykę, kompatybilność i zachowanie aplikacji przy większych archiwach.

## Najważniejsze zmiany

- kontrolowane migracje SQLite i blokada otwierania bazy utworzonej przez nowszy, nieobsługiwany schemat;
- automatyczna kopia migracyjna przed zmianą schematu;
- Recovery checkpoints z weryfikacją integralności;
- bezpieczny restore z dodatkową kopią pre-restore;
- automatyczny recovery checkpoint przy realnej zmianie wersji aplikacji;
- diagnostyka integralności bazy, zgodności schematu, recovery i wolnego miejsca;
- bezpieczny raport diagnostyczny bez treści dokumentów i lokalnych ścieżek;
- lepsza wydajność Documents, Dashboard, Search/Q&A, Review Queue, Cases i Duplicate Finder na większych archiwach;
- kontrola spójności wersji Desktop/PWA/backend i możliwość odświeżenia cache PWA;
- dodatkowe testy architektury, kompatybilności wstecznej, migracji, recovery i cyklu aktualizacji;
- praktyczny przewodnik Troubleshooting oraz jasne rozróżnienie Recovery checkpoint i Full Archive Backup.

## Bezpieczeństwo aktualizacji i recovery

DocPilot zachowuje lokalne dane poza katalogiem programu. Standardowy uninstall nie usuwa indeksu ani archiwum.

Przy zmianie wersji aplikacja próbuje utworzyć zweryfikowany punkt recovery bazy. W **Settings → Data & diagnostics** można sprawdzić:
- integralność bazy;
- wersję schematu;
- stan recovery;
- liczbę zweryfikowanych punktów odzyskiwania;
- stan checkpointu utworzonego przy aktualizacji.

Restore dotyczy bazy SQLite — indeksu i ustawień. Nie cofa dokumentów źródłowych na dysku. Do kopii dokumentów służy **Full Archive Backup**.

## Windows

Wydanie zawiera:
- `DocPilot-Setup-Windows-x64.exe`;
- `DocPilot-Portable-Windows-x64.zip`;
- `SHA256SUMS.txt`.

Pipeline wydania wykonuje pełne testy, OCR smoke tests, build Desktop/Notifier, self-test EXE, czystą instalację, uninstall z zachowaniem danych, upgrade ze starszego wydania, checksumy oraz publikację artefaktów.

## Znane ograniczenia

- instalator nadal nie ma komercyjnego podpisu code-signing i Windows może pokazać SmartScreen;
- OCR i automatyczne rozpoznawanie danych wymagają sprawdzenia w oryginalnym dokumencie przy ważnych decyzjach;
- Recovery checkpoint nie zastępuje pełnego backupu plików źródłowych;
- integracje z usługami zewnętrznymi pozostają opcjonalne i powinny być uruchamiane z kontrolowanym zakresem danych.
