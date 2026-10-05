# LifePilot — Release Candidate Checklist

Ten dokument określa, co musi być spełnione przed oznaczeniem LifePilot jako stabilnego publicznego wydania Windows.

## A. Automatyczne bramki techniczne

- [x] Zwykłe CI: składnia frontendu + pełny pytest.
- [x] Syntetyczna matryca akceptacyjna reprezentatywnych klas dokumentów.
- [x] ProofPack: generowanie, SHA-256, bezpieczny verifier i test manipulacji.
- [x] CasePack: generowanie całej sprawy, jawne braki, verifier i test manipulacji.
- [x] Case Readiness: Gotowa / Wymaga sprawdzenia / Niekompletna.
- [x] Decision Trail: dokument + sprawa, prywatnościowy allow-list, eksport Markdown.
- [x] Windows build: DocPilot.exe.
- [x] Windows build: DocPilotNotifier.exe.
- [x] Bundled OCR.
- [x] Portable ZIP.
- [x] Installer.
- [x] Clean install + uninstall smoke test w linii preview przed 4.8.
- [x] Upgrade smoke test ze stabilnej starszej wersji w linii preview przed 4.8.
- [x] Checksumy artefaktów.
- [x] Preview 4.8: funkcjonalny self-test uruchamiany w zwykłym pytest przed pakowaniem.
- [x] Preview 4.8 po merge: funkcjonalny `DocPilot.exe --self-test` w finalnym pakiecie.
- [x] Preview 4.8 po merge: funkcjonalny self-test po clean install.
- [x] Preview 4.8 po merge: funkcjonalny self-test po upgrade.

Potwierdzenie automatycznych bramek 4.8: GitHub Actions `Windows Release` run **37206846769** — pełny `success` (packaged self-test, clean install/uninstall, upgrade, checksumy i artefakty).

### Preview 4.9 — pilot hardening

- [x] Lokalny `docpilot-pilot` z public-safe raportem domyślnym.
- [x] Dokładny raport pilota wyłącznie po jawnym `--include-private`.
- [x] Rozszerzona macierz: wiele dat, 2-dokumentowa sprawa, missing-original CasePack, korekta + ponowne przeliczenie.
- [x] Funkcjonalny ProofPack + verifier w finalnym `DocPilot.exe --self-test`.
- [x] Missing-original → Case Readiness = Niekompletna w finalnym self-teście.
- [x] Missing-original widoczny w CasePack preview w finalnym self-teście.
- [x] Clean install/uninstall po Preview 4.9.
- [x] Upgrade smoke z faktycznie stabilnego publicznego **DocPilot v4.0.0**.
- [x] Funkcjonalny self-test po upgrade z v4.0.0.
- [x] Checksumy i workflow artifacts.

Potwierdzenie bramek 4.9: GitHub Actions `Windows Release` run **37209580044** — pełny `success`.


### Preview 5.0 — RC hardening

- [x] Recovery smoke w runtime: zweryfikowany checkpoint → kontrolowana zmiana → restore → ponowna kontrola integralności SQLite.
- [x] Recovery smoke jest częścią tego samego `--self-test`, który działa na pakiecie, clean install i po upgrade.
- [x] Granice priorytetu terminów: po terminie / dziś / 1–3 dni / 4–14 dni / 15+ dni.
- [x] ProofPack i CasePack: automatyczny privacy smoke metadanych bez lokalnych ścieżek i pełnego OCR.
- [x] Eksport .ics nie zawiera lokalnej ścieżki pliku.
- [x] Eksport .ics używa całodniowych `VALUE=DATE` i jest sprawdzany na datach przejścia DST Europe/Warsaw (29.03.2026 i 25.10.2026).
- [x] Packaged calendar self-test działa w finalnym EXE, po clean install i po upgrade.
- [x] Zwykłe CI, Windows build, installer, clean install/uninstall, upgrade z v4.0.0, checksumy i artifacts.

Finalne potwierdzenie bramek 5.0 po poprawkach pilota: main Test **#245 / 37304245537** = `success`, Windows Release **#90 / 37304245485** = `success` dla `main` `e20918743cc084bb04f5466cabb86c6f4141abb9`.


## B. Kontrolowany pilot dokumentów

Kanoniczne zadanie: GitHub issue #62.

Kontrolowany pakiet syntetyczny finalnej logiki jest zakończony:
- [x] 10/10 dokumentów przetworzonych;
- [x] 0 błędów analizy;
- [x] 45/45 kontroli merytorycznych/privacy PASS;
- [x] faktura / płatność;
- [x] pismo urzędowe z terminem względnym;
- [x] umowa;
- [x] dokument szkolny / rodzinny;
- [x] paragon / gwarancja;
- [x] słaby skan / niski confidence;
- [x] niejednoznaczne albo wielokrotne daty;
- [x] sprawa i referencje ubezpieczeniowe;
- [x] brakujący lokalny oryginał w CasePack w testach runtime;
- [x] ręczna korekta kluczowych pól i ponowne przeliczenie LifePilot w testach akceptacyjnych;
- [x] public-safe raport bez nazw plików, ścieżek, issuerów, kwot, hashy i pełnego OCR.

## C. UX Windows — ręczny przegląd

- [ ] pierwszy start aplikacji jest zrozumiały bez dokumentacji;
- [ ] wrzucenie dokumentu prowadzi do „Co teraz?” bez zbędnego klikania;
- [ ] korekta kluczowych danych jest czytelna;
- [ ] „Dlaczego LifePilot tak zaleca?” jest zrozumiałe;
- [ ] kolejka Aktywne / Dzisiaj / Pilne / Do sprawdzenia / Wkrótce / Załatwione jest czytelna;
- [ ] Case Readiness nie jest mylone z oceną prawną;
- [ ] ProofPack / CasePack i verifier są zrozumiałe dla użytkownika nietechnicznego;
- [ ] Decision Trail jest czytelny i nie ujawnia ścieżek lokalnych;
- [ ] komunikaty błędów wskazują następny krok;
- [ ] installer / uninstall / upgrade zachowują dane użytkownika.

## D. Granice bezpieczeństwa produktu

- [x] brak automatycznych płatności;
- [x] brak automatycznego wysyłania odpowiedzi;
- [x] brak automatycznego usuwania oryginałów przez LifePilot;
- [x] niski confidence wymusza review-first;
- [x] CzyToŚciema? pozostaje oddzielone i nie dostaje automatycznie OCR dokumentu;
- [x] ProofPack/CasePack nie są przedstawiane jako kwalifikowany podpis lub zaufany timestamp;
- [x] Case Readiness nie jest przedstawiane jako ocena prawna lub merytoryczna.

## Decyzja o stabilnym wydaniu

Stabilne publiczne wydanie LifePilot powinno zostać oznaczone dopiero, gdy:
1. wszystkie automatyczne bramki sekcji A są zielone;
2. kontrolowany pilot sekcji B jest zakończony bez nierozwiązanych błędów krytycznych;
3. ręczny przegląd UX sekcji C nie ma nierozwiązanych problemów blokujących;
4. granice bezpieczeństwa sekcji D pozostają zachowane.

Do tego momentu właściwą etykietą jest **Preview / Pilot**, nie „stable”.
