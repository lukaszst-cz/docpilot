# LifePilot Preview 4.6 — Case Readiness

Preview 4.6 dodaje techniczny preflight sprawy przed eksportem lub dalszą pracą.

## Bez sztucznego score

LifePilot nie pokazuje procentowego wyniku gotowości. Zamiast tego używa trzech stanów:

- **Gotowa** — nie wykryto problemów kompletności ani integralności;
- **Wymaga sprawdzenia** — materiał istnieje, ale część danych lub integralności wymaga kontroli;
- **Niekompletna** — brakuje co najmniej jednego lokalnego oryginału.

## Co jest sprawdzane

- dostępność lokalnego pliku;
- obecność zapisanego SHA-256;
- bieżący SHA-256 względem indeksu;
- niski confidence bez ręcznej weryfikacji;
- liczba ręcznie sprawdzonych dokumentów;
- otwarte działania;
- terminy po czasie i zbliżające się terminy.

## Stan „załatwione”

Dokument oznaczony jako załatwiony nadal pozostaje w sprawie i w materiale dowodowym, ale nie podbija już liczników otwartych działań ani pilnych terminów.

## Eksport

Case Readiness nie blokuje CasePack. Jeżeli sprawa jest niekompletna, użytkownik może nadal wyeksportować pakiet, a CasePack jawnie zapisze brakujące oryginały w manifeście.

## Granice

Case Readiness nie ocenia zasadności roszczeń, poprawności prawnej, szans procesowych ani treści merytorycznej. To wyłącznie kontrola technicznej kompletności i integralności materiału.

## Status

Preview 4.6 nie zmienia schematu SQLite i pozostaje local-first.
