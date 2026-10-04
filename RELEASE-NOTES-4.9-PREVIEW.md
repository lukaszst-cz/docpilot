# LifePilot Preview 4.9 — Pilot Hardening

Preview 4.9 nie dodaje nowego modułu użytkowego. Domyka narzędzia potrzebne do kontrolowanego pilota #62.

## Lokalny Pilot Runner

Nowe polecenie `docpilot-pilot` analizuje wskazany folder lokalnie.

Domyślnie zapisuje:
- `pilot-public.json`;
- `pilot-report.md`.

Raport publiczny nie zawiera:
- nazw plików;
- lokalnych ścieżek;
- pełnego OCR;
- wartości issuerów;
- wartości kwot;
- SHA-256.

Dokładny `pilot-private.json` wymaga jawnego `--include-private`.

## Macierz akceptacyjna

Dodano scenariusze:
- wiele dat + jawna fraza terminu;
- sprawa z co najmniej dwoma dokumentami;
- CasePack przed i po zniknięciu jednego oryginału;
- Case Readiness = Niekompletna przy brakującym oryginale;
- ręczna korekta kluczowych pól + ponowne przeliczenie rekomendacji.

## Windows Release

Pakowany self-test został rozszerzony o:
- osobny ProofPack + weryfikację;
- brakujący oryginał → Case Readiness = Niekompletna;
- CasePack preview raportujący brakujący oryginał.

Upgrade smoke został skorygowany z historycznego v0.5.1 na **stabilne publiczne v4.0.0**.

## Cel

Po zielonym Windows gate 4.9 automatyczna część przygotowania pilota jest domknięta. Pozostanie wykonanie lokalnego pilota na realnych/zredagowanych próbkach i ręczny przegląd UX.
