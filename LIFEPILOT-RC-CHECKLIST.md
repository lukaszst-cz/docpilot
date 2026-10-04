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
- [ ] Preview 4.8 po merge: funkcjonalny `DocPilot.exe --self-test` w finalnym pakiecie.
- [ ] Preview 4.8 po merge: funkcjonalny self-test po clean install.
- [ ] Preview 4.8 po merge: funkcjonalny self-test po upgrade.

## B. Pilot rzeczywistych / zanonimizowanych dokumentów

Kanoniczne zadanie: GitHub issue #62.

Minimalny zestaw:
- [ ] faktura / płatność;
- [ ] pismo urzędowe z terminem odpowiedzi;
- [ ] umowa;
- [ ] dokument szkolny / rodzinny;
- [ ] paragon / gwarancja;
- [ ] słaby skan / niski confidence;
- [ ] niejednoznaczne albo wielokrotne daty;
- [ ] sprawa z co najmniej 2 powiązanymi dokumentami;
- [ ] brakujący lokalny oryginał w CasePack;
- [ ] ręczna korekta kluczowych pól i ponowne przeliczenie LifePilot.

Dla każdej próbki należy porównać z oryginałem:
- [ ] typ dokumentu;
- [ ] wystawcę;
- [ ] kwotę i walutę, jeśli występują;
- [ ] datę dokumentu;
- [ ] termin / gwarancję;
- [ ] rekomendację „Co teraz?”;
- [ ] zachowanie po ręcznej korekcie;
- [ ] Decision Trail;
- [ ] Case Readiness;
- [ ] ProofPack / CasePack i jego weryfikację;
- [ ] brak niezamierzonej wysyłki danych do chmury.

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
