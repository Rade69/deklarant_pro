## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Pregled `docs/admin/ADMIN_TAB_CODE_AUDIT.md` (audit drugog agenta, "pi", 2026-08-03) i minimalna
akcija po korisnikovom izboru — korisnik je eksplicitno tražio da se ne troše tokeni na puni
nezavisni re-audit svih 23 nalaza, nego da se odabere najmanje rizičan/najisplativiji potez.

## Šta je urađeno
1. Pročitan cijeli `ADMIN_TAB_CODE_AUDIT.md` — sumira 23 stavke mrtvog koda, 4 grupe duplikata
   (~300 linija CSS), 4 arhitekturna kršenja (2 od njih krše eksplicitna AGENTS.md pravila: direktna
   `psycopg2.connect()` u `learning_panel.py`, direktan `LLMProvider()` poziv u `analytics_panel.py`),
   7 sitnijih nedostataka.
2. Korisnik odabrao (nakon AskUserQuestion): najbezbolniji potez, uz eksplicitnu napomenu da ne
   želi trošiti tokene na dublju provjeru.
3. Odabrana najniže-rizična, potpuno zatvorena stavka: duplikat `gui/styles/admin_tab.qss`.
   Nezavisno provjereno (ne slijepo prihvaćeno iz tuđeg audita):
   - `gui/tabs/admin/admin_view.py:51` učitava stylesheet isključivo preko
     `get_path_settings().styles_dir / "admin_tab.qss"` → `styles_dir` = `BUNDLE_ROOT/styles`
     (`config/settings.py:108`) — dakle `styles/admin_tab.qss`, NIKAD `gui/styles/admin_tab.qss`.
   - Grep za `gui/styles` putanju u cijelom repou (van `.worktrees/`) — nula referenci.
   - `diff` potvrdio bajt-identičnost `gui/styles/admin_tab.qss` ↔ `styles/admin_tab.qss` (i
     dist_client parovi).
   - Postojeći test `tests/unit/test_admin_stylesheet_palette.py` (već u repou, netaknut)
     eksplicitno provjerava da se stylesheet učitava preko `styles_dir` puta — prošao i prije i
     poslije brisanja (2 passed).
4. Uočena i zabilježena (ne popravljena sada, u napomeni ispod), razlika u linijskim brojevima
   između `ADMIN_TAB_CODE_AUDIT.md` i trenutnog stanja fajlova (npr. `analytics_service.py` —
   `get_declaration_statistics` sada na liniji 222, audit navodi 291) — fajl je mijenjan nakon
   audita 2026-08-03, pa se preostalim 22 stavkama NE smije vjerovati na riječ bez ponovne
   provjere prije bilo koje buduće akcije.
5. Obrisan `gui/styles/admin_tab.qss` i `dist_client/gui/styles/admin_tab.qss` (472 linije ukupno).
6. `pytest tests/unit/test_admin_stylesheet_palette.py -q` — 2 passed.
7. Commit `651e059`.

## Zašto je urađeno
Korisnik traži smanjenje nepotrebnog koda u produkciji, ali eksplicitno ograničio obim ove runde
na najniže-rizičan potez zbog token budžeta. QSS duplikat je jedina stavka iz audita koja je (a)
statički resurs, ne Python simbol — nema call-chain rizik, (b) potpuno samostalna (ne zavisi od
drugih stavki na listi), (c) već pokrivena postojećim testom.

## Kako je urađeno
Brisanje dva bajt-identična fajla, bez izmjene ijedne linije Python koda.

## Šta nije dirano
Preostalih 22 stavke iz `ADMIN_TAB_CODE_AUDIT.md` (prazni controller handleri, `BackupService`,
`SettingsService`/`AnalyticsService` mrtve metode, CSS duplikati u panelima, direktna DB konekcija
u `learning_panel.py`, direktan `LLMProvider()` poziv u `analytics_panel.py`, neiskorišćeni
importi) — NIJESU dirane. Ove stavke imaju međusobne pozivne lance (npr. `AnalyticsService.
get_summary()` interno poziva `get_declaration_statistics()`) i zahtijevaju provjeru caller-a
prije bilo kakvog brisanja/izmjene — ne mogu se sigurno riješiti "u prolazu" bez provjere kakva je
urađena za Šifrarnici Controller.

## Verifikacija
Ciljani grep (potvrđena nula referenci na `gui/styles` putanju), `diff` (bajt-identičnost),
postojeći automatizovani test (2 passed prije i poslije). Nema py_compile potrebe (nije Python
fajl).

## Nezavisna provjera
- Checker korišćen: NE.
- Razlog: promjena je brisanje statičkog, dokazano neučitanog resursa, pokrivena postojećim
  testom; nema izvršnog koda koji bi mogao biti pogrešno protumačen.

## Pronađeni problemi
Linijski brojevi u `ADMIN_TAB_CODE_AUDIT.md` su zastarjeli za dio fajlova (npr.
`analytics_service.py`) — fajl se mijenjao nakon 2026-08-03 revizije. Bilo koja buduća akcija na
preostalim stavkama iz tog audita mora ponovo pročitati trenutno stanje fajla, ne osloniti se na
navedene brojeve linija.

## Odbačene opcije
- Pun nezavisan re-audit svih 23 stavke prije bilo koje akcije — odbačeno eksplicitno po
  korisnikovom zahtjevu (token budžet).
- Direktno popravljanje 2 stvarna kršenja pravila (DB konekcija, LLM poziv) — odbačeno za ovu
  rundu jer mijenjaju runtime ponašanje (ne čisto brisanje) i zahtijevaju testiranje da se
  Learning/Analytics paneli i dalje ponašaju ispravno — veći trošak od onoga što je korisnik
  tražio ovom rundom.
- Brisanje cijelog `BackupService`/`SettingsService`/`AnalyticsService` mrtvog koda u istoj rundi
  — odbačeno jer postoje interni pozivni lanci između metoda (vidi "Pronađeni problemi") koje
  treba raspetljati prije sigurnog brisanja.

## Konflikti / kontradiktorni izvori
Nema — audit drugog agenta je u ovom slučaju potvrđen kao tačan za QSS stavku.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `651e059` | `chore(admin): ukloni duplikat admin_tab.qss koji se nikad ne učitava` |

## Rizici / ograničenja
Nema za ovu izmjenu. Preostalih 22 stavki iz Admin audita ostaje otvoreno — vidi "Potreban
follow-up".

## Potreban follow-up
Ako korisnik želi nastaviti čišćenje Admin taba: preporučen redoslijed po riziku —
(1) prazni controller handleri i CSS duplikati u panelima (nizak rizik, slično Šifrarnici
Controlleru), (2) `BackupService`/`SettingsService`/`AnalyticsService` mrtve metode (srednji rizik,
zahtijeva raspetljavanje internih poziva), (3) DB konekcija i LLM poziv kršenja (zahtijeva
funkcionalno testiranje Learning/Analytics panela, ne samo brisanje).

## Potrebna korisnička potvrda
Da li nastaviti na preostale stavke iz `ADMIN_TAB_CODE_AUDIT.md`, i kojim redoslijedom (vidi
"Potreban follow-up").
