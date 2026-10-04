# LifePilot Preview 4.1 — release notes

LifePilot Preview 4.1 rozwija warstwę produktową DocPilot 4.0 bez zmiany schematu SQLite.

## Najważniejsze zmiany

### Zweryfikowane dane użytkownika

Po analizie dokumentu użytkownik może poprawić i jawnie zatwierdzić:
- typ dokumentu;
- wystawcę;
- kwotę i walutę;
- datę dokumentu;
- termin;
- koniec gwarancji;
- sprawę;
- wymaganą akcję.

Po zapisaniu LifePilot natychmiast przelicza „Co teraz?”. Ręcznie sprawdzone dane nie są później ponownie traktowane jak niezweryfikowany, niskiej pewności OCR.

Poprawki są zachowywane także po operacji Apply / przeniesieniu dokumentu.

### Bezpieczne podsumowanie sprawy

Dla sprawy można:
- zobaczyć lokalny podgląd chronologii;
- pobrać podsumowanie Markdown;
- zobaczyć dokumenty, daty, terminy, działania i SHA-256.

Eksport domyślnie nie zawiera:
- pełnego tekstu OCR;
- lokalnych ścieżek;
- tokenów ani danych logowania;
- dokumentów spoza wybranej sprawy.

### Macierz akceptacyjna

Dodano syntetyczne testy dla:
- faktury;
- wezwania / pisma urzędowego;
- polisy;
- gwarancji;
- umowy;
- dokumentu szkolnego;
- szkody ubezpieczeniowej;
- słabego skanu;
- dokumentu bez terminu;
- niejednoznacznego terminu.

Celem jest preferowanie ręcznej weryfikacji zamiast pewnej rekomendacji przy niejednoznacznych danych.

## Bezpieczeństwo

Preview 4.1 nadal zachowuje zasady:
- local-first;
- brak automatycznych płatności i wysyłki odpowiedzi;
- brak automatycznego przekazywania dokumentów do CzyToŚciema?;
- brak destrukcyjnych decyzji bez użytkownika;
- ProofPack i case summary nie są kwalifikowanym podpisem ani zaufanym znacznikiem czasu.

## Status wydania

To są release notes warstwy preview. Stabilnym publicznym wydaniem pozostaje DocPilot 4.0.0 do czasu przejścia pełnego release gate dla kolejnej wersji.
