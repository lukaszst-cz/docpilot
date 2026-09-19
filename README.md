# DocPilot

DocPilot powstał z prostego problemu: po pewnym czasie folder z dokumentami przestaje być archiwum, a zaczyna być miejscem, w którym trzeba wszystkiego szukać ręcznie.

Program pomaga uporządkować skany, PDF-y, faktury, umowy i pisma. Odczytuje dokument, wyciąga z niego najważniejsze informacje, potrafi znaleźć termin, zaproponować nazwę i miejsce w archiwum, a później pozwala wrócić do dokumentu przez wyszukiwarkę.

Najważniejsza zasada jest prosta: **DocPilot najpierw pokazuje propozycję, a dopiero później wykonuje zmianę.**

![DocPilot demo](assets/demo.gif)

## Pobierz

Strona projektu:

https://lukaszst-cz.github.io/operations-office-portfolio/docpilot/

Instalator Windows:

https://github.com/lukaszst-cz/docpilot/releases/download/v0.5.1/DocPilot-Setup-Windows-x64.exe

Pełne wydanie v0.5.1:

https://github.com/lukaszst-cz/docpilot/releases/tag/v0.5.1

Do wyboru są:
- **Setup EXE** — zwykły instalator dla Windows;
- **Portable ZIP** — wersja bez instalacji;
- **SHA256SUMS.txt** — sumy kontrolne plików.

Instalator nie jest jeszcze podpisany komercyjnym certyfikatem code-signing, dlatego Windows może wyświetlić ostrzeżenie SmartScreen.

## Jak zacząć

Po uruchomieniu możesz od razu użyć **Try safe demo**. Program wczyta przykładową, sztuczną fakturę. Dzięki temu można zobaczyć sposób działania bez wskazywania własnych dokumentów.

Przy normalnej pracy wybierasz plik, DocPilot go analizuje i pokazuje m.in. rozpoznany typ dokumentu, datę, kwotę, termin, kategorię oraz proponowaną nazwę. Dopiero po sprawdzeniu tych informacji decydujesz, co zrobić dalej.

## Co potrafi

DocPilot czyta zwykłe PDF-y, obrazy i skany. Dla dokumentów obrazowych korzysta z OCR. W wydaniu Windows dołączony jest Tesseract z obsługą języka polskiego i angielskiego.

Potrafi wykrywać terminy płatności, odpowiedzi, gwarancji i ważności dokumentów. Dokument można oznaczyć np. jako wymagający zapłaty, odpowiedzi, podpisu albo ręcznego sprawdzenia.

Wyszukiwarka działa lokalnie. Można szukać nie tylko po nazwie pliku, ale także po treści i znaczeniu. Jest też proste Q&A, które odpowiada na podstawie lokalnie zindeksowanych dokumentów.

Program wykrywa duplikaty, porównuje dwie wersje dokumentu, grupuje dokumenty w sprawy i buduje ich chronologię.

Operacje na plikach są zapisywane w historii. Te, które da się odwrócić, można cofnąć.

## Prywatność

Podstawowe działanie programu jest lokalne: OCR, indeksowanie, wyszukiwanie, Q&A i praca na plikach odbywają się na komputerze użytkownika.

Połączenia z Notion, Google Calendar czy pocztą są opcjonalne i wymagają osobnej konfiguracji.

DocPilot nie powinien być traktowany jako źródło prawdy o ważnym terminie, kwocie albo danych z dokumentu. OCR i automatyczne rozpoznawanie mogą się pomylić, dlatego ważne informacje trzeba porównać z oryginałem.

## Funkcje, które nadal wymagają ostrożności

Redakcja danych w skanach i PDF-ach działa, ale przed wysłaniem takiego pliku trzeba go obejrzeć ręcznie.

Integracje z Gmail/Outlook, Notion i Google Calendar są opcjonalne i nadal traktuję je jako funkcje dodatkowe.

MCP jest przeznaczone dla osób, które wiedzą, po co chcą go użyć. Do zwykłego korzystania z DocPilot nie jest potrzebne.

## Dla bardziej technicznych

DocPilot działa jako lokalna aplikacja z backendem FastAPI i bazą SQLite. Interfejs może działać jako aplikacja Windows lub PWA połączona z lokalnym serwisem.

Najważniejsze elementy:
- Python + FastAPI;
- SQLite;
- Tesseract OCR;
- OpenCV do poprawy skanów;
- lokalne wyszukiwanie TF-IDF + LSA;
- PyInstaller + Inno Setup dla wydania Windows;
- testy uruchamiane w GitHub Actions.

Wersję źródłową można uruchomić przez:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[full]"
docpilot
```

Aplikacja działa lokalnie pod:

```text
http://127.0.0.1:8765
```

Testy:

```bash
pip install -e ".[full,dev]"
pytest -q
```

## Status wydania

Aktualna wersja: **v0.5.1**

Wydanie Windows przechodzi automatyczne testy, budowę aplikacji, budowę modułu powiadomień, dołączenie OCR, self-test gotowego pakietu, utworzenie instalatora i ZIP-a oraz wygenerowanie sum SHA-256.

## Zgłaszanie problemów

Jeżeli coś nie działa, najlepiej otworzyć Issue i krótko opisać:
- co zostało zrobione;
- co miało się wydarzyć;
- co wydarzyło się faktycznie;
- jaka wersja Windows i DocPilot była używana.

Nie dodawaj do publicznego zgłoszenia prywatnych dokumentów, danych osobowych ani danych logowania.

## Licencja

MIT — szczegóły w pliku `LICENSE`.
