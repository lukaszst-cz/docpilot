# DocPilot — architektura i kontrakty kompatybilności

Ten dokument opisuje granice, których kolejne wersje DocPilot nie powinny naruszać przypadkiem.

## Warstwy

### 1. Core / domena

Moduły odpowiedzialne za analizę, OCR, reguły, wyszukiwanie, bazę, backup i operacje na plikach nie zależą od FastAPI, pywebview ani interfejsu użytkownika.

Do tej warstwy należą m.in.:
- `analyze.py`;
- `db.py`;
- `db_maintenance.py`;
- `storage.py`;
- `rules.py`;
- `semantic.py`;
- `review.py`;
- `qa.py`;
- `portable_config.py`;
- `exporters.py`;
- `update_safety.py`.

### 2. Integracje

`integrations.py` i `integration_registry.py` są granicą między lokalnym indeksem a usługami zewnętrznymi.

Integracje:
- są opcjonalne;
- nie blokują podstawowego lokalnego workflow;
- nie powinny omijać registry adapterów przy nowych typach synchronizacji;
- zapisują historię i błędy operacji.

### 3. API lokalne

`app.py` składa moduły niższych warstw i wystawia lokalne API na `127.0.0.1`.

API jest interfejsem aplikacji, nie publiczną usługą sieciową. Żądania modyfikujące dane są chronione przed obcym Origin.

### 4. Desktop i PWA

`desktop.py` uruchamia lokalny backend i osadza ten sam frontend, którego używa przeglądarka/PWA.

Desktop, Browser i Installed PWA powinny:
- korzystać z tego samego lokalnego backendu;
- raportować tryb klienta;
- wykrywać rozjazd wersji PWA shell ↔ backend;
- zachowywać te same podstawowe zasady pracy na dokumentach.

## Stabilne formaty danych

| Format | Obecna wersja | Zasada kompatybilności |
| --- | ---: | --- |
| SQLite schema | v1 | nieversionowane starsze bazy są migrowane z kopią bezpieczeństwa; baza z nowszym schema jest odrzucana |
| Portable Configuration | v1 | import obsługuje tylko jawnie wspierane wersje; przyszły nieznany format jest odrzucany |
| Recovery checkpoint | schema SQLite zapisane w pliku | przywracany jest tylko punkt z poprawnym integrity i schema nie nowszym niż wspierane |
| Archive layout | Home legacy + Profiles | Home zachowuje historyczny układ; inne profile mogą używać `archive/Profiles/<profile>` |
| PWA shell | zgodny z wersją aplikacji | frontend ostrzega, jeśli cache shell i backend mają różne wersje |

## Zasady migracji SQLite

1. Migracja nie modyfikuje bazy o schema nowszym niż wspierane.
2. Przed migracją starszej istniejącej bazy tworzona jest kopia w `migration-backups`.
3. Migracja jest idempotentna.
4. Po migracji sprawdzana jest zgodność schema i integrity.
5. Restore z recovery point przechodzi przez tę samą walidację schema.

## Zasady Portable Configuration

Portable Configuration może przenosić reguły, własne typy dokumentów i bezpieczne preferencje.

Nie przenosi automatycznie:
- haseł;
- tokenów;
- plików OAuth;
- lokalnych ścieżek;
- folderu watch;
- historii integracji;
- startup registration.

Import nowszego, nieznanego formatu ma zostać odrzucony zamiast częściowo zastosowany.

## Aktualizacja i recovery

Przy pierwszym uruchomieniu po zmianie wersji aplikacji DocPilot tworzy zweryfikowany checkpoint bieżącej bazy. Dla migracji schematu dodatkowo zachowuje osobny backup przed migracją. Zwykły restart tej samej wersji nie tworzy kolejnego checkpointu.

Jeżeli automatyczny checkpoint wersji się nie powiedzie, aplikacja może się uruchomić, ale diagnostyka oznacza stan upgrade recovery jako wymagający uwagi. Wersja nie jest wtedy zapisywana jako bezpiecznie przepracowana, dzięki czemu następny start ponowi próbę.

## Kompatybilność wydania

Przed stabilnym wydaniem wymagane są:
- zwykłe CI;
- pełny Windows build;
- self-test gotowego EXE;
- clean install;
- uninstall bez utraty danych użytkownika;
- upgrade smoke test ze starszej publicznej wersji;
- test migracji legacy SQLite;
- test Portable Configuration;
- test PWA/backend version sync.

## Czego nie traktujemy jako stabilnego publicznego API

Wewnętrzne endpointy `/api/*` są kontraktem między frontendem DocPilot a lokalnym backendem. Mogą ewoluować razem z aplikacją, o ile testy aplikacji i kompatybilność danych pozostają zachowane.

## Reguła dla 4.0

Zmiana architektury jest uzasadniona tylko wtedy, gdy poprawia bezpieczeństwo, możliwość testowania, kompatybilność lub utrzymanie. Samo przenoszenie kodu między plikami nie jest celem.
