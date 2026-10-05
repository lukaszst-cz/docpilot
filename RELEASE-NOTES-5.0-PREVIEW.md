# LifePilot Preview 5.0 — RC Hardening

Preview 5.0 nie dodaje nowego modułu użytkowego. Domyka automatyczne ryzyka techniczne przed kontrolowanym pilotem #62.

## Recovery smoke

Finalny `DocPilot.exe --self-test` wykonuje w izolowanym katalogu:
- utworzenie zweryfikowanego checkpointu SQLite;
- kontrolowaną zmianę ustawień i dokumentu;
- restore z checkpointu;
- potwierdzenie powrotu wcześniejszego stanu;
- kontrolę integralności aktywnej bazy po restore.

Ten sam self-test jest uruchamiany:
- na świeżo zbudowanym pakiecie;
- po clean install;
- po upgrade z publicznego stable DocPilot v4.0.0.

## Granice terminów

Self-test sprawdza progi:
- termin minął;
- termin dzisiaj;
- 1–3 dni = urgent;
- 4–14 dni = soon;
- 15+ dni = normal.

## Kalendarz i DST

Eksport .ics:
- używa `DTSTART;VALUE=DATE`;
- dodaje `DTEND;VALUE=DATE` następnego dnia;
- nie używa `TZID`;
- jest testowany na datach zmiany czasu Europe/Warsaw: 29.03.2026 i 25.10.2026;
- nie zapisuje lokalnej ścieżki pliku w DESCRIPTION.

## Privacy smoke

Automatyczna kontrola obejmuje:
- Decision Trail bez lokalnej ścieżki katalogu testowego;
- metadane ProofPack/CasePack bez lokalnych ścieżek i pełnego OCR;
- kalendarz bez lokalnej ścieżki dokumentu.

## Status

Finalny `main` LifePilot Preview 5.0 (`e2091874…`) przeszedł main Test #245 oraz Windows Release #90. Po poprawkach ujawnionych przez pilot (PR #84 i #85) kontrolowany pakiet syntetyczny zakończył się wynikiem **10/10 dokumentów, 0 błędów analizy i 45/45 kontroli merytorycznych/privacy PASS**.

Przed oznaczeniem jako public beta/stable pozostaje wyłącznie **ręczny Windows UX/privacy pass** na autoryzowanym urządzeniu z issue #62.

Stabilnym publicznym wydaniem pozostaje DocPilot v4.0.0.
