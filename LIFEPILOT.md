# LifePilot — produkt nadrzędny dla codziennych dokumentów i spraw

## Obietnica produktu

> **Wrzuć dokument. LifePilot powie Ci, co to jest, co trzeba zrobić, do kiedy i zachowa wszystko na później.**

LifePilot nie jest osobnym silnikiem od zera. Jest warstwą produktową budowaną nad stabilnym, local-first fundamentem DocPilot.

Celem jest zmniejszenie liczby decyzji, które użytkownik musi podjąć po otrzymaniu dokumentu. Zamiast pytać osobno:
- co to za dokument;
- czy trzeba coś zrobić;
- jaki jest termin;
- gdzie go zapisać;
- co zachować jako materiał źródłowy;
- gdzie później znaleźć kontekst;

LifePilot próbuje przeprowadzić ten przepływ jako jeden proces.

## Moduły

### DocPilot — „Co to jest?”

DocPilot pozostaje warstwą dokumentową:
- OCR i ekstrakcja tekstu;
- klasyfikacja;
- metadane;
- wykrywanie terminów;
- lokalny indeks;
- sprawy i timeline;
- wyszukiwanie i Q&A;
- duplikaty;
- bezpieczne operacje na plikach;
- backup, recovery i audyt.

### CoTeraz? — „Co mam zrobić?”

Po analizie dokumentu LifePilot buduje jedną rekomendowaną następną czynność.

Priorytety:
1. overdue — termin już minął;
2. today — termin przypada dziś;
3. urgent — do 3 dni;
4. review — najpierw ręczna weryfikacja, np. słaby OCR;
5. soon — do 14 dni;
6. normal — brak pilności.

Osobny ekran **LifePilot · Co teraz?** zbiera dokumenty wymagające uwagi i sortuje je zgodnie z tą kolejnością.

### ProofPack — „Co zachować?”

ProofPack v1 jest lokalnym archiwum ZIP tworzonym dla jednego dokumentu.

Zawartość:
- original/<nazwa> — kopia oryginalnego pliku;
- manifest.json — wybrane metadane i informacja o integralności;
- next-action.json — rekomendacja LifePilot;
- timeline.json — bezpieczna chronologia dokumentów w tej samej sprawie;
- SHA256SUMS.txt — sumy kontrolne;
- README.txt — opis i ograniczenia.

ProofPack nie zawiera pełnego tekstu OCR ani lokalnej ścieżki dokumentu w manifeście.

### CzyToŚciema? — „Czy to wygląda podejrzanie?”

CzyToŚciema? pozostaje oddzielną, prostą aplikacją PWA.

LifePilot może otworzyć ją jako opcjonalne narzędzie, ale:
- nie wysyła automatycznie dokumentu;
- nie przekazuje automatycznie tekstu OCR;
- nie zakłada, że brak ostrzeżenia oznacza bezpieczeństwo.

To celowe rozdzielenie granic prywatności i odpowiedzialności.

## Aktualny przepływ użytkownika

1. Użytkownik dodaje dokument do Smart Inbox.
2. DocPilot lokalnie analizuje plik i zapisuje indeks.
3. LifePilot buduje kartę **Co teraz?**.
4. Użytkownik weryfikuje wykryte dane.
5. Może:
   - zatwierdzić organizację pliku;
   - pobrać ProofPack;
   - pobrać termin jako .ics;
   - otworzyć dokument;
   - otworzyć osobno CzyToŚciema?.
6. Dokument może później pojawić się w centralnej kolejce LifePilot.

## Zasady bezpieczeństwa produktu

### Human-in-the-loop

Automatyczna ekstrakcja nie jest traktowana jako źródło prawdy.

Przy niskiej pewności odczytu LifePilot ma najpierw rekomendować ręczne sprawdzenie danych, a nie wykonanie właściwej czynności.

### Brak automatycznych destrukcyjnych decyzji

LifePilot nie powinien sam:
- usuwać dokumentów;
- wykonywać płatności;
- wysyłać odpowiedzi;
- przenosić oryginalnych plików bez zatwierdzenia;
- wysyłać prywatnej treści do zewnętrznej usługi.

### Integralność nie oznacza kwalifikowanego dowodu czasu

SHA-256 pozwala sprawdzić, czy bajty dokumentu odpowiadają zapisanej sumie.

ProofPack:
- nie jest kwalifikowanym podpisem elektronicznym;
- nie jest kwalifikowaną pieczęcią;
- nie jest zaufanym znacznikiem czasu;
- nie dowodzi samodzielnie, kiedy dokument powstał.

W sprawach formalnych oryginały i źródłowe kanały doręczenia nadal należy zachować.

## Prywatność

Podstawowy przepływ LifePilot korzysta z lokalnego modelu DocPilot:
- OCR lokalnie;
- indeks lokalnie;
- baza SQLite lokalnie;
- wyszukiwanie lokalnie;
- ProofPack lokalnie.

Zewnętrzne integracje DocPilot pozostają opcjonalne i są uruchamiane jawnie.

Manifest ProofPack v1 nie zawiera:
- pełnego tekstu OCR;
- lokalnej ścieżki pliku;
- danych logowania;
- tokenów integracji.

## Kontrakt API preview

### Widok pojedynczego dokumentu

GET /api/lifepilot/{document_id}

Zwraca:
- next_action;
- bezpieczny manifest proof_pack.

### Kolejka „Co teraz?”

GET /api/lifepilot/queue?limit=200

Zwraca priorytetyzowane dokumenty wymagające uwagi.

### ProofPack ZIP

GET /api/lifepilot/{document_id}/proofpack

Tworzy lokalny ZIP i zwraca go do pobrania.

### Termin kalendarza

GET /api/lifepilot/{document_id}/calendar

Eksportuje pojedynczy wykryty termin jako iCalendar.

## Status

### Działa w kodzie preview

- karta Co teraz? po analizie;
- centralna kolejka LifePilot;
- priorytety terminów;
- ręczna weryfikacja przy niskiej pewności;
- ProofPack ZIP;
- podgląd zawartości ProofPack przed pobraniem;
- oznaczanie pozycji kolejki jako załatwionej i przywracanie;
- filtry Aktywne / Dzisiaj / Pilne / Do sprawdzenia / Wkrótce / Załatwione;
- SHA-256 oryginału i plików metadanych;
- timeline sprawy;
- pojedynczy .ics;
- pełna strona „O LifePilot”;
- testy modułu, API i frontendu.

### Stabilny kanał wydania

Ostatnim stabilnym publicznym wydaniem Windows pozostaje **DocPilot v4.0.0**.

LifePilot powinien wejść do kolejnego publicznego wydania dopiero po:
1. pełnym CI;
2. Windows build;
3. self-test gotowego EXE;
4. clean install;
5. upgrade z poprzedniej stabilnej wersji;
6. sprawdzeniu OCR;
7. testach ProofPack na zainstalowanej aplikacji;
8. smoke testach na realnych urządzeniach.

## Kolejne etapy

### Następny rozsądny zakres

- ręczne poprawianie kluczowych pól bez opuszczania karty;
- bezpieczny eksport streszczenia sprawy;
- dalsze testy rzeczywistych klas dokumentów;
- powiadomienia o najważniejszych akcjach;
- ręczne poprawianie kluczowych pól bez opuszczania karty;
- bezpieczny eksport streszczenia sprawy;
- testy na większej liczbie rzeczywistych klas dokumentów.

### Później

- wersja mobilna / wygodniejszy import ze zdjęcia;
- rozszerzony przepływ rodzinny;
- opcjonalne szablony odpowiedzi tworzone na podstawie zweryfikowanych danych;
- węższe kontrakty integracyjne między produktami;
- wielojęzyczność warstwy LifePilot.

## Kryterium sukcesu

LifePilot ma być dobry wtedy, gdy użytkownik po wrzuceniu dokumentu **nie musi rozumieć struktury DocPilot ani znać nazw modułów**.

Powinien zobaczyć:
1. co to jest;
2. co zrobić;
3. do kiedy;
4. gdzie jest oryginał;
5. jak zachować materiał.

To jest główna miara produktu — nie liczba funkcji.

## LifePilot Preview 4.2 — przejrzystość decyzji

### Przejrzystość rekomendacji

Każde `next_action` zwraca teraz:
- źródło danych: `automatic` albo `manual`;
- poziom pewności automatycznej ekstrakcji;
- czas ręcznej weryfikacji, jeśli istnieje;
- listę `decision_basis` wyjaśniającą podstawę zalecenia.

Interfejs pokazuje te informacje pod rozwijanym „Dlaczego LifePilot tak zaleca?”.

### Historia „załatwione”

Nowe wpisy przechowują:
- wersję formatu;
- semantyczną sygnaturę stanu dokumentu;
- czas oznaczenia jako załatwione.

Sygnatura v2 reaguje na realne zmiany danych wpływających na decyzję, a nie na sam techniczny `updated_at`. Starsze wpisy zapisane jako pojedynczy hash pozostają zgodne wstecznie.

## LifePilot Preview 4.3 — powiadomienia

Powiadomienia Windows korzystają teraz z tej samej kolejki i priorytetów co ekran **Co teraz?**.

Zasady:
- pozycje oznaczone jako załatwione nie generują powiadomień;
- powiadamiane są tylko pozycje z wykrytym terminem w wybranym horyzoncie;
- pozycje bez daty pozostają w kolejce LifePilot, ale nie generują powiadomień tylko dlatego, że wymagają ręcznej kontroli;
- ta sama wersja stanu dokumentu jest pokazywana najwyżej raz dziennie;
- jeżeli zmieni się istotny stan dokumentu, np. termin lub akcja, nowa sygnatura może wygenerować nowe powiadomienie;
- treść powiadomienia używa rekomendacji LifePilot, a nie wyłącznie surowej daty.

Status API powiadomień pokazuje również liczbę pozycji pasujących do aktualnego horyzontu.

## LifePilot Preview 4.4 — weryfikacja ProofPack

LifePilot potrafi lokalnie sprawdzić wcześniej utworzony ProofPack ZIP.

Weryfikator:
- nie rozpakowuje archiwum do folderu użytkownika;
- odrzuca duplikaty nazw i niebezpieczne ścieżki ZIP;
- kontroluje limit liczby wpisów i łącznego rozmiaru po rozpakowaniu;
- sprawdza `SHA256SUMS.txt` strumieniowo;
- weryfikuje wymagane pliki oraz format manifestu;
- porównuje hash oryginału z `computed_digest` w manifeście;
- osobno raportuje zgodność z hashem zapisanym wcześniej w indeksie.

**Ważne:** poprawna integralność ProofPack oznacza, że pakiet jest wewnętrznie spójny. Nie oznacza kwalifikowanego podpisu ani zaufanego znacznika czasu.

## LifePilot Preview 4.5 — CasePack

CasePack rozszerza ProofPack z pojedynczego dokumentu na **całą sprawę**.

Pakiet zawiera:
- wszystkie dostępne lokalnie oryginały należące do sprawy;
- osobny manifest dla każdego dokumentu;
- `case-manifest.json` opisujący zakres pakietu;
- uporządkowaną chronologię `timeline.json`;
- bezpieczne podsumowanie `case-summary.md` bez pełnego OCR i lokalnych ścieżek;
- `SHA256SUMS.txt` dla elementów pakietu;
- README z ograniczeniami.

Jeżeli oryginału brakuje na dysku, CasePack **nie ukrywa tego faktu**. Dokument pozostaje w manifeście jako brakujący, a podgląd pokazuje liczbę brakujących oryginałów przed pobraniem.

Ten sam lokalny ekran weryfikacji rozpoznaje teraz automatycznie ProofPack albo CasePack. Dla CasePack raportuje m.in. liczbę zweryfikowanych dokumentów, zgodność z wcześniejszym SHA-256 indeksu oraz brakujące oryginały.

CasePack jest narzędziem porządkującym i integralnościowym. Nie jest kwalifikowanym podpisem elektronicznym, pieczęcią ani zaufanym znacznikiem czasu.

## LifePilot Preview 4.6 — Case Readiness

Case Readiness to lokalny preflight sprawy przed dalszą pracą lub eksportem CasePack.

LifePilot nie wylicza sztucznego procentowego „score”. Używa trzech czytelnych stanów:
- **Gotowa** — nie wykryto problemów kompletności ani integralności;
- **Wymaga sprawdzenia** — np. niski confidence bez ręcznej weryfikacji, brak SHA-256 albo rozjazd aktualnego pliku z indeksem;
- **Niekompletna** — co najmniej jeden lokalny oryginał jest niedostępny.

Preflight sprawdza m.in.:
- dostępność lokalnych oryginałów;
- obecność SHA-256;
- zgodność aktualnego pliku z wcześniej zapisanym hashem;
- niską pewność OCR bez ręcznej weryfikacji;
- liczbę ręcznie sprawdzonych dokumentów;
- otwarte działania;
- terminy po czasie i zbliżające się terminy.

Pozycje oznaczone jako **załatwione** nie są ponownie liczone jako otwarte działania ani pilne terminy.

Terminy i otwarte działania są warstwą uwagi, ale same nie zmieniają sprawy na „Niekompletną”. Eksport CasePack pozostaje decyzją użytkownika.

**Case Readiness nie jest oceną prawną ani merytoryczną sprawy.** Dotyczy wyłącznie kompletności, integralności i jakości technicznego przygotowania materiału.

## LifePilot Preview 4.7 — Decision Trail

Decision Trail wykorzystuje istniejący lokalny audyt DocPilot zamiast tworzyć drugi system historii.

Dla dokumentu LifePilot pokazuje m.in.:
- analizę/import dokumentu;
- ręczne korekty pól wpływających na decyzję;
- zmiany wartości **przed → po** dla nowych korekt;
- zmianę rekomendacji **przed → po** dla nowych korekt;
- oznaczenie jako załatwione i ponowne otwarcie;
- eksport ProofPack;
- eksport historii.

Dla całej sprawy Decision Trail łączy zdarzenia aktualnych dokumentów oraz wpisy, w których dana sprawa występowała jako `case_before` albo `case_after`. Obejmuje też Case Readiness, CasePack i eksport podsumowania sprawy.

### Prywatność historii

Warstwa historii jawnie filtruje payload audytu. Do Decision Trail nie trafiają:
- pełny tekst OCR;
- lokalne ścieżki plików;
- dowolne nieznane pola z surowego audytu.

Starsze wpisy pozostają widoczne w zakresie danych, które były wtedy rzeczywiście zapisane. LifePilot nie rekonstruuje ani nie dopisuje historycznych wartości, których audyt wcześniej nie przechowywał.

Historia dokumentu i sprawy może być eksportowana do Markdown.

## LifePilot Preview 4.8 — release self-test

Preview 4.8 wzmacnia proces wydania Windows zamiast dodawać kolejną funkcję użytkową.

Polecenie `DocPilot.exe --self-test` sprawdza teraz nie tylko obecność plików i zgodność wersji, ale również izolowany przepływ LifePilot:
1. analizę dokumentu testowego;
2. ręczną korektę danych i przypisanie do sprawy;
3. zapis i odczyt Decision Trail;
4. Case Readiness;
5. utworzenie CasePack;
6. lokalną weryfikację CasePack;
7. oznaczenie dokumentu jako załatwionego;
8. potwierdzenie, że załatwiony dokument znika z aktywnej kolejki;
9. historię sprawy z wpisem o załatwieniu.

Self-test używa osobnego katalogu tymczasowego, po czym przywraca wcześniejsze ustawienia aplikacji. Nie korzysta z dokumentów użytkownika.

Self-test nie zależy od `pytest`, `httpx` ani `FastAPI TestClient`. Korzysta wyłącznie z modułów dostępnych w runtime aplikacji.

Ten sam `--self-test` jest wykonywany w pipeline Windows dla:
- świeżo zbudowanego pakietu;
- czystej instalacji;
- instalacji po upgrade ze starszej wersji.


## LifePilot Preview 4.9 — pilot hardening

Preview 4.9 przygotowuje kontrolowany pilot #62 bez dokładania kolejnego modułu użytkowego.

### Lokalny Pilot Runner

Polecenie `docpilot-pilot` analizuje wskazany folder lokalnie. Domyślnie tworzy:
- `pilot-public.json`;
- `pilot-report.md`.

Raport publiczny nie zawiera nazw plików, lokalnych ścieżek, pełnego OCR, wartości issuerów, kwot ani hashy. Dokładny `pilot-private.json` powstaje dopiero po jawnym `--include-private` i powinien pozostać lokalny.

### Macierz pilota

Automatyczny baseline obejmuje dodatkowo:
- dokument z wieloma datami i jawną frazą terminu;
- sprawę z co najmniej 2 dokumentami;
- CasePack przed i po utracie jednego lokalnego oryginału;
- Case Readiness = Niekompletna dla brakującego oryginału;
- ręczną korektę kluczowych pól i ponowne przeliczenie decyzji.

### Windows hardening

Pakowany `DocPilot.exe --self-test` sprawdza dodatkowo osobny ProofPack oraz scenariusz brakującego oryginału. Upgrade smoke rozpoczyna się od faktycznie stabilnego publicznego **DocPilot v4.0.0**, a nie od historycznej wersji 0.x.

Po automatycznym Windows gate 4.9 pozostają już tylko: kontrolowany lokalny pilot na realnych/zredagowanych próbkach i ręczny przegląd UX Windows.


## LifePilot Preview 5.0 — RC hardening

Preview 5.0 nie dodaje kolejnego modułu użytkowego. Domyka automatyczne ryzyka przed pilotem #62.

### Recovery w finalnym runtime

`DocPilot.exe --self-test` wykonuje teraz na izolowanej bazie:
1. utworzenie zweryfikowanego checkpointu SQLite;
2. kontrolowaną zmianę danych;
3. restore z checkpointu;
4. potwierdzenie powrotu wcześniejszego stanu dokumentu i ustawień;
5. ponowną kontrolę integralności aktywnej bazy.

Ponieważ ten sam self-test działa na świeżo zbudowanym pakiecie, po clean install oraz po upgrade z v4.0.0, recovery jest testowane również w tych ścieżkach wydania.

### Granice terminów i kalendarz

Self-test sprawdza granice priorytetów:
- po terminie;
- dzisiaj;
- 1–3 dni = pilne;
- 4–14 dni = wkrótce;
- 15+ dni = normalne.

Eksport iCalendar został dodatkowo utwardzony:
- termin jest zdarzeniem całodniowym `VALUE=DATE`;
- `DTEND` wskazuje następny dzień zgodnie z semantyką iCalendar;
- eksport nie używa `TZID`, więc data nie przesuwa się przez zmianę strefy lub DST;
- test obejmuje przejścia Europe/Warsaw 29.03.2026 i 25.10.2026;
- `.ics` nie zawiera lokalnej ścieżki dokumentu.

### Privacy smoke

Finalny self-test sprawdza, że:
- Decision Trail nie ujawnia katalogu danych testowych;
- metadane ProofPack/CasePack nie ujawniają lokalnych ścieżek ani pełnego OCR;
- eksport kalendarza nie ujawnia lokalnej ścieżki źródła.

Preview 5.0 nadal pozostaje **Preview / Pilot**. Automatyczne bramki techniczne nie zastępują kontrolowanego pilota na realnych lub zanonimizowanych dokumentach ani ręcznego przeglądu UX/prywatności.
