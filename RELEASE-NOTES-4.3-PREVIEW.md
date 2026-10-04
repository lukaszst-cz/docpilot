# LifePilot Preview 4.3 — Priority Notifications

Preview 4.3 przenosi powiadomienia Windows z prostego „deadline notifier” na logikę LifePilot.

## Co się zmienia

Powiadomienia korzystają z:
- tej samej kolejki `Co teraz?`;
- priorytetu LifePilot;
- tytułu rekomendowanej czynności;
- semantycznej sygnatury dokumentu;
- statusu `załatwione`.

## Mniej spamu

LifePilot:
- nie powiadamia o pozycjach oznaczonych jako załatwione;
- nie powiadamia o dokumentach bez terminu tylko dlatego, że mają niski confidence;
- nie powtarza tej samej pozycji w tym samym stanie wielokrotnie tego samego dnia;
- pozwala ponownie powiadomić, jeśli realnie zmienił się termin lub inny stan wpływający na decyzję.

## Horyzont

Użytkownik nadal wybiera liczbę dni naprzód. Pozycje z terminem poza horyzontem pozostają w LifePilot, ale nie trafiają do background toastów.

## Prywatność

Powiadomienia korzystają wyłącznie z lokalnej bazy i lokalnego procesu notifiera. Nie wymagają chmury i nie wysyłają zawartości dokumentu do zewnętrznej usługi.

## Status

Preview 4.3 nie zmienia schematu SQLite. Publicznym stabilnym wydaniem pozostaje DocPilot 4.0.0 do czasu osobnego procesu stabilnego release.
