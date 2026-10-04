# LifePilot Preview 4.7 — Decision Trail

Preview 4.7 dodaje czytelną historię decyzji bez nowej migracji bazy.

## Źródło

Decision Trail korzysta z istniejącej lokalnej tabeli audytu DocPilot/LifePilot.

## Dokument

Dla pojedynczego dokumentu historia może pokazać:
- analizę lub import;
- ręczne korekty;
- nowe wartości przed/po;
- rekomendację LifePilot przed/po;
- oznaczenie jako załatwione;
- ponowne otwarcie;
- eksport ProofPack;
- eksport historii.

## Sprawa

Historia sprawy zbiera:
- zdarzenia aktualnych dokumentów należących do sprawy;
- korekty, w których sprawa występowała jako stan wcześniejszy lub nowy;
- kontrole Case Readiness;
- eksport CasePack;
- eksport podsumowania i historii.

## Prywatność

Decision Trail nie zwraca pełnego OCR ani lokalnych ścieżek plików. Surowy payload audytu jest filtrowany do jawnie dozwolonych pól.

## Zgodność wsteczna

Starsze wpisy audytu są pokazywane tylko z informacjami, które faktycznie były zapisane. Dla nowych korekt LifePilot zapisuje dodatkowo:
- listę zmian pól;
- decyzję przed zmianą;
- decyzję po zmianie.

## Eksport

Historia dokumentu i sprawy może być pobrana jako Markdown.

## Status

Preview 4.7 nie zmienia schematu SQLite i pozostaje local-first.
