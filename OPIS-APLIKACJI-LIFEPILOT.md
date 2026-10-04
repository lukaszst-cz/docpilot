# LifePilot — opis aplikacji

> **Wrzuć dokument. LifePilot powie Ci, co to jest, co trzeba zrobić, do kiedy i zachowa wszystko na później.**

**Twórca i właściciel projektu: Łukasz St‑cz.**  
LifePilot jest rozwijany jako warstwa produktowa nad DocPilot.

## Co to jest

LifePilot to local-first asystent dokumentów i codziennych spraw. Jego celem nie jest samo przechowywanie plików, lecz skrócenie drogi od otrzymania dokumentu do decyzji.

Typowy problem wygląda tak: przychodzi faktura, pismo, umowa, dokument szkolny, polisa albo korespondencja. Użytkownik musi ustalić, co to jest, znaleźć termin, zdecydować co zrobić, zapisać plik, a później pamiętać gdzie jest i z czym się łączy.

LifePilot scala te czynności w jeden przepływ:

**dokument → rozpoznanie → następna czynność → termin → sprawa → materiał na później.**

## Najprostsze użycie

1. Dodaj dokument.
2. Sprawdź dane odczytane lokalnie.
3. Zobacz kartę **„Co teraz?”**.
4. Wykonaj lub zaplanuj następną czynność.
5. Zapisz termin do kalendarza, jeśli jest potrzebny.
6. Pobierz ProofPack, jeśli chcesz zachować spójny pakiet materiałów.
7. Oznacz pozycję jako załatwioną. Dokument nadal pozostaje w archiwum.

## Cztery warstwy produktu

### 1. DocPilot — „Co to jest?”

Fundament dokumentowy:
- OCR PL/EN;
- klasyfikacja dokumentu;
- wykrywanie wystawcy, dat, kwot i terminów;
- sprawy i chronologia;
- lokalne wyszukiwanie i Q&A;
- duplikaty;
- bezpieczne przenoszenie i zmiana nazw;
- backup, recovery i historia operacji.

### 2. CoTeraz? — „Co mam zrobić?”

LifePilot tworzy jedną rekomendowaną następną czynność i nadaje jej priorytet:
- **po terminie**;
- **dzisiaj**;
- **pilne** — do 3 dni;
- **do sprawdzenia** — np. niska pewność OCR;
- **wkrótce** — do 14 dni;
- **normalne**.

Centralna kolejka może być filtrowana. Pozycję można oznaczyć jako załatwioną i później przywrócić. Stan „załatwione” nie usuwa dokumentu. Jeśli istotny stan dokumentu się zmieni, np. termin lub wymagana akcja, dokument może ponownie wymagać uwagi.

### 3. ProofPack — „Co zachować?”

ProofPack to lokalnie tworzony ZIP dla jednego dokumentu. Przed pobraniem można zobaczyć, co znajdzie się w pakiecie.

Pakiet zawiera:
- kopię oryginału;
- manifest wybranych metadanych;
- rekomendację „Co teraz?”;
- chronologię dokumentów należących do tej samej sprawy;
- SHA256SUMS;
- README z ograniczeniami.

ProofPack nie wysyła danych do chmury. Manifest nie zawiera pełnego tekstu OCR ani lokalnej ścieżki pliku.

### 4. CzyToŚciema? — „Czy to wygląda podejrzanie?”

CzyToŚciema? pozostaje osobnym produktem do wiadomości, linków, screenshotów i QR.

LifePilot może otworzyć aplikację, ale nie wysyła do niej automatycznie dokumentu ani OCR. To celowa granica prywatności.

## Co działa obecnie

W kodzie projektu działa już:
- karta „LifePilot · Co teraz?” po analizie;
- centralna kolejka działań;
- filtry Aktywne / Dzisiaj / Pilne / Do sprawdzenia / Wkrótce / Załatwione;
- oznaczanie pozycji jako załatwionej i przywracanie jej;
- automatyczny powrót uwagi po zmianie istotnego stanu dokumentu;
- ProofPack ZIP;
- podgląd zawartości ProofPack przed pobraniem;
- ręczna korekta typu, wystawcy, kwoty, waluty, daty dokumentu, terminu i gwarancji;
- ponowne przeliczenie „Co teraz?” po zatwierdzeniu sprawdzonych danych;
- jawne źródło rekomendacji: automatyczny odczyt albo dane sprawdzone ręcznie;
- rozwijane „Dlaczego LifePilot tak zaleca?” z podstawą decyzji;
- czas oznaczenia pozycji jako załatwionej oraz zgodność ze starszym formatem historii;
- powiadomienia Windows oparte na tej samej logice LifePilot „Co teraz?”, respektujące status załatwione i wybrany horyzont;
- antyspamowe deduplikowanie powiadomień według semantycznego stanu dokumentu;
- lokalny weryfikator ProofPack sprawdzający sumy SHA-256, manifest, oryginał oraz bezpieczną strukturę ZIP;
- CasePack ZIP dla całej sprawy: wszystkie dostępne oryginały, manifesty dokumentów, chronologia, bezpieczne podsumowanie i SHA-256;
- jawne raportowanie brakujących oryginałów w CasePack zamiast cichego pomijania;
- wspólny lokalny weryfikator ProofPack / CasePack;
- Case Readiness: preflight kompletności i integralności sprawy przed eksportem, bez sztucznego punktowego score;
- rozróżnienie stanów „Gotowa / Wymaga sprawdzenia / Niekompletna” oraz osobne raportowanie terminów i otwartych działań;
- Decision Trail dla dokumentu i całej sprawy: historia korekt, zmian rekomendacji, oznaczeń „załatwione”, eksportów ProofPack/CasePack i kontroli gotowości;
- eksport historii do Markdown bez pełnego OCR i lokalnych ścieżek plików;
- funkcjonalny self-test gotowego EXE: analiza → korekta → Decision Trail → Case Readiness → CasePack → weryfikacja → „załatwione” → kolejka;
- izolowany self-test w katalogu tymczasowym, bez używania danych użytkownika i bez zależności developerskich;
- lokalny Pilot Runner (`docpilot-pilot`) do kontrolowanego pilota na prywatnym folderze dokumentów;
- public-safe raport pilota domyślnie bez nazw plików, ścieżek, pełnego OCR, wartości issuerów, kwot i SHA-256;
- dokładny raport prywatny wyłącznie po jawnym `--include-private`;
- packaged self-test ProofPack oraz scenariusza brakującego oryginału;
- Windows upgrade smoke z faktycznie stabilnego publicznego DocPilot v4.0.0;
- recovery smoke w finalnym runtime: checkpoint → kontrolowana zmiana → restore → ponowna kontrola integralności bazy;
- testy granic priorytetu terminów oraz eksportu .ics na datach zmiany czasu Europe/Warsaw;
- eksport .ics bez lokalnej ścieżki pliku, jako całodniowe zdarzenie `VALUE=DATE` z jawnym `DTEND` następnego dnia;
- automatyczny privacy smoke Decision Trail oraz metadanych ProofPack/CasePack;
- rozróżnienie między integralnością samego pakietu a zgodnością oryginału z hashem zapisanym wcześniej w indeksie;
- bezpieczny podgląd i eksport podsumowania całej sprawy bez pełnego OCR i ścieżek lokalnych;
- kontrola integralności SHA-256;
- chronologia sprawy w ProofPack;
- eksport pojedynczego terminu jako .ics;
- przycisk otwierający oryginał;
- oddzielne przejście do CzyToŚciema?;
- strona informacyjna LifePilot;
- testy modułu, API i architektury.

## Dla kogo

### Dom i rodzina
Faktury, szkoła, gwarancje, polisy, umowy, korespondencja, sprawy urzędowe i terminy.

### Freelancer i mała firma
Umowy, koszty, dokumenty klientów, odpowiedzi, płatności i archiwum spraw.

### Osoba prowadząca wiele spraw
Dokumenty są grupowane w sprawy, a ProofPack pozwala zachować spójny materiał.

### Użytkownik nietechniczny
Docelowo najważniejsze ma być jedno pytanie: **„Co teraz?”**, a nie znajomość struktury aplikacji.

## Prywatność

Podstawowe działanie jest local-first:
- plik pozostaje na komputerze;
- OCR działa lokalnie;
- indeks działa lokalnie;
- baza SQLite jest lokalna;
- ProofPack powstaje lokalnie;
- rekomendacja LifePilot jest wyliczana lokalnie.

Integracje z usługami zewnętrznymi są opcjonalne i jawne.

## Bezpieczeństwo decyzji

LifePilot stosuje human-in-the-loop. Nie powinien automatycznie:
- płacić;
- wysyłać odpowiedzi;
- usuwać dokumentów;
- wykonywać nieodwracalnych operacji;
- wysyłać prywatnej treści do innych usług.

Przy słabej jakości ekstrakcji pierwszym zaleceniem jest ręczna kontrola danych.

## Ważne ograniczenia

OCR i heurystyki mogą się mylić. Termin, kwotę, rachunek bankowy, dane osoby i inne informacje mające znaczenie prawne lub finansowe należy porównać z oryginałem.

ProofPack wykorzystuje SHA-256 do kontroli integralności, ale **nie jest kwalifikowanym podpisem elektronicznym, kwalifikowaną pieczęcią ani zaufanym znacznikiem czasu**.

## Platformy

Fundament DocPilot jest przygotowany przede wszystkim dla Windows jako aplikacja lokalna z backendem FastAPI i interfejsem desktop/PWA.

Ten sam frontend może działać w:
- aplikacji desktopowej;
- przeglądarce na tym samym komputerze;
- zainstalowanej PWA podłączonej do lokalnego backendu.

Operacje na dokumentach wymagają działającego lokalnego backendu.

## Status produktu

LifePilot jest obecnie **preview/pilot (linia 5.0 preview)**, rozwijanym nad stabilnym DocPilot v4.0.0.

Nie oznaczamy go jeszcze jako stabilnego publicznego wydania Windows. Przed takim oznaczeniem wymagane są:
- pełne CI;
- Windows build;
- self-test EXE;
- clean install;
- upgrade ze stabilnej wersji;
- OCR smoke;
- testy ProofPack w gotowej instalacji;
- testy na rzeczywistych klasach dokumentów;
- kontrola UX na Windows.

## Kryterium sukcesu

LifePilot nie ma wygrywać liczbą funkcji.

Ma wygrać tym, że po wrzuceniu dokumentu użytkownik szybko widzi:
1. **co to jest**;
2. **co zrobić**;
3. **do kiedy**;
4. **gdzie jest oryginał**;
5. **jak zachować materiał**.

Jeżeli do odpowiedzi na te pytania potrzebne jest przekopywanie wielu ekranów, produkt wymaga dalszego uproszczenia.

## Linki

- Repozytorium: https://github.com/lukaszst-cz/docpilot
- CzyToŚciema?: https://github.com/lukaszst-cz/czy-to-sciema
- Dobrowolne wsparcie: https://buymeacoffee.com/nalesnik_plus_plus
- Strony i proste systemy: https://zielona-marka.pl
