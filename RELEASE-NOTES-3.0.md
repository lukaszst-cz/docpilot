# DocPilot 3.0.0

DocPilot 3.0 porządkuje integracje zewnętrzne. Celem tego wydania jest przewidywalny przepływ danych: użytkownik może sprawdzić zakres synchronizacji, zobaczyć jej wynik, uniknąć duplikowania tych samych rekordów i przenieść bezpieczną konfigurację na inną instalację.

## Kontrola zakresu synchronizacji

Przed synchronizacją z Notion lub Google Calendar można ograniczyć dokumenty po:

- profilu;
- sprawie;
- wymaganej akcji;
- prefiksie kategorii;
- maksymalnej liczbie rekordów.

Preview pokazuje liczbę pasujących i kwalifikujących się dokumentów oraz próbkę rekordów przed wysłaniem danych.

## Historia integracji

DocPilot zapisuje osobny wynik każdego uruchomienia Notion, Google Calendar i importu załączników z poczty:

- użyty zakres;
- liczbę prób;
- liczbę zakończonych sukcesem;
- liczbę pominiętych;
- liczbę błędów;
- skrócone informacje o błędach.

Hasła i tokeny nie są zapisywane w historii.

## Idempotentny Notion i Google Calendar

DocPilot pamięta lokalne powiązanie dokumentu z obiektem utworzonym po stronie integracji.

Google Calendar:
- pierwszy sync tworzy wydarzenie;
- niezmieniony dokument jest pomijany;
- zmiana danych używanych w wydarzeniu aktualizuje istniejący event zamiast tworzyć kolejny.

Notion:
- pierwszy sync tworzy stronę;
- niezmieniony dokument jest pomijany;
- zmieniony dokument tworzy nową wersję strony, archiwizuje poprzednią i aktualizuje lokalne powiązanie;
- jeśli archiwizacja poprzedniej strony się nie powiedzie, nowa strona jest wycofywana w miarę możliwości i lokalne powiązanie nie jest podmieniane.

## Portable Configuration

Nowy eksport konfiguracji JSON pozwala przenieść między instalacjami:

- reguły;
- własne typy dokumentów;
- bezpieczne preferencje;
- niesekretne identyfikatory potrzebne do ponownego skonfigurowania integracji.

Eksport celowo nie zawiera:

- haseł i app-passwordów;
- tokenu Notion;
- tokenu Google OAuth;
- lokalnej ścieżki watch foldera;
- ścieżki do pliku Google OAuth client;
- rejestracji autostartu powiadomień;
- historii synchronizacji i mapowań obiektów zewnętrznych.

Import ma osobny preview i dopiero potem świadome Apply. Reguły i custom types są scalane po nazwie, więc ponowne użycie tego samego pliku nie mnoży wpisów.

## Registry adapterów integracji

Notion, Google Calendar i Email mają wspólny rejestr adapterów opisujący m.in.:

- kierunek integracji;
- status;
- obsługę zakresu;
- obsługę document sync;
- idempotencję;
- filtr kwalifikujących się dokumentów.

Preview w UI pobiera listę obsługiwanych document-sync adapterów z katalogu API zamiast z listy wpisanej na sztywno w frontendzie. Nowy adapter może zostać zarejestrowany bez dokładania provider-specific warunków do głównego kodu aplikacji.

## Bezpieczeństwo i model danych

Podstawowy workflow DocPilota nadal jest lokalny. Integracje są opcjonalne i uruchamiane jawnie.

DocPilot 3.0 nie wysyła automatycznie całego archiwum tylko dlatego, że konektor został skonfigurowany. Zakres syncu jest ustalany przy operacji, a użytkownik może go wcześniej podejrzeć.

## Znane ograniczenia

- instalator nadal nie ma komercyjnego podpisu code-signing;
- pierwszą synchronizację z usługą zewnętrzną warto wykonać na małym zakresie i sprawdzić rezultat;
- Notion nie ma prostego odpowiednika pełnego update istniejącej strony z dziećmi, dlatego zmieniony dokument jest bezpiecznie zastępowany nową stroną, a poprzednia jest archiwizowana;
- import IMAP wymaga konfiguracji poświadczeń na danym komputerze;
- Portable Configuration nie przenosi sekretów ani rejestracji zależnych od systemu operacyjnego.
