# DocPilot — rozwiązywanie problemów

Ten plik opisuje bezpieczne kroki, które warto wykonać przed zgłoszeniem błędu. Nie wymaga usuwania archiwum ani prywatnych dokumentów.

## 1. DocPilot nie uruchamia się

1. Zamknij wszystkie okna DocPilot, także PWA lub kartę przeglądarki otwartą na `127.0.0.1:8765`.
2. Uruchom DocPilot ponownie.
3. Jeżeli nadal nie startuje, otwórz **Settings → Data & diagnostics → Open log**.
4. Nie usuwaj katalogu danych ani pliku bazy tylko po to, żeby „zacząć od nowa”.

Wersja Windows trzyma dane użytkownika poza katalogiem programu, dlatego ponowna instalacja aplikacji nie powinna usuwać archiwum ani indeksu.

## 2. PWA pokazuje inną wersję niż backend

W **Settings → Runtime & PWA** DocPilot pokazuje:
- tryb klienta: Desktop, Installed PWA lub Browser;
- wersję lokalnego backendu;
- wersję cache PWA.

Jeżeli pojawi się komunikat o rozjeździe wersji:

1. użyj przycisku **Update PWA shell** w sekcji **Runtime & PWA**;
2. DocPilot sprawdzi aktualizację service workera i przeładuje klienta;
3. jeżeli problem nadal występuje, zamknij wszystkie okna DocPilot/PWA i uruchom aplikację ponownie.

Nie trzeba usuwać lokalnego archiwum ani bazy danych.

## 3. Recovery readiness — co oznacza

W **Settings → Data & diagnostics** sprawdź pole **Recovery readiness**:

- `ready` — baza jest zdrowa i masz zweryfikowany punkt odzyskiwania;
- `checkpoint-recommended` — baza jest zdrowa, ale nie ma jeszcze zweryfikowanego punktu recovery;
- `database-problem` — najpierw sprawdź integralność bazy i listę Recovery checkpoints.

Jeżeli widzisz `checkpoint-recommended`, użyj **Create checkpoint** przed większą aktualizacją, masowymi operacjami albo konserwacją.

Recovery checkpoint chroni lokalny **indeks i ustawienia SQLite**. Nie zastępuje **Full Archive Backup**, który służy do kopii dokumentów źródłowych.

## 4. Database integrity nie jest OK

Najpierw nie wykonuj masowych zmian ani dużego importu.

1. Otwórz **Settings → Recovery checkpoints**.
2. Sprawdź, czy istnieje punkt z oznaczeniem `integrity: ok`.
3. Przywracanie wymaga ręcznego wpisania `RESTORE`.
4. Przed właściwym restore DocPilot zachowuje dodatkową kopię bezpieczeństwa.

Jeżeli nie ma zweryfikowanego punktu odzyskiwania, zachowaj bieżące dane i zgłoś problem zamiast ręcznie podmieniać pliki SQLite.

## 5. Schema version jest nowsza niż obsługiwana

Taka sytuacja zwykle oznacza próbę otwarcia danych utworzonych przez nowszy DocPilot.

1. Nie wykonuj downgrade bazy ręcznie.
2. Zainstaluj aktualne wydanie DocPilot.
3. Uruchom aplikację ponownie i sprawdź diagnostykę.

## 6. Mało wolnego miejsca

OCR, pełny backup, import seryjny i aktualizacja mogą tworzyć pliki tymczasowe lub kopie bezpieczeństwa.

- poniżej 1 GB DocPilot pokazuje ostrzeżenie;
- poniżej 0,25 GB traktuje sytuację jako wymagającą działania.

Zwolnij miejsce przed dużym backupem, aktualizacją albo masowym importem.

## 7. Aktualizacja nie działa

1. Zamknij działające okna DocPilot.
2. Pobierz aktualny instalator z sekcji **Releases**.
3. Uruchom instalator nad istniejącą instalacją.
4. Po uruchomieniu sprawdź **Settings → Data & diagnostics**.

Instalator jest testowany pod kątem zachowania lokalnych danych podczas aktualizacji. Standardowy uninstall również nie usuwa katalogu danych użytkownika.

Przy pierwszym uruchomieniu po zmianie wersji DocPilot tworzy dodatkowy zweryfikowany recovery checkpoint bazy. Jego stan jest widoczny w **Settings → Data & diagnostics → Upgrade recovery**. Jeżeli widnieje tam `error`, utwórz ręczny checkpoint przed kolejną dużą operacją albo aktualizacją.

## 8. Windows SmartScreen ostrzega przed instalatorem

Instalator nie ma jeszcze komercyjnego podpisu code-signing, dlatego SmartScreen może wyświetlić ostrzeżenie. Przed uruchomieniem można porównać SHA-256 pobranego pliku z `SHA256SUMS.txt` dołączonym do tego samego wydania.

## 9. Jak przygotować zgłoszenie błędu

W **Settings → Data & diagnostics** użyj:
- **Copy safe report** albo
- **Download safe report**.

Bezpieczny raport zawiera informacje o wersji, platformie, stanie bazy, wersji schematu i wolnym miejscu. Celowo nie zawiera:
- treści dokumentów;
- nazw ani ścieżek lokalnych dokumentów;
- katalogu danych;
- haseł, tokenów i danych logowania.

Do publicznego Issue nie dodawaj prywatnych dokumentów, danych osobowych ani pełnego pliku logu bez wcześniejszego sprawdzenia jego zawartości.

## 10. Kiedy użyć Recovery, a kiedy ponownej instalacji

**Recovery checkpoint** służy do problemów z bazą danych.

**Ponowna instalacja** służy do problemów z plikami programu lub nieudaną aktualizacją.

Te czynności rozwiązują inne problemy. Nie zastępuj jednej drugą bez potrzeby.
