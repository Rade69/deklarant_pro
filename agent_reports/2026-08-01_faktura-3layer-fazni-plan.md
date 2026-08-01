## Datum
2026-08-01

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` (novi fajl) — plan, bez izmjene koda. Analiza je pokrila `gui/tabs/faktura_view.py`, `services/faktura/*.py`, `.worktrees/faktura-3layer/`.

## Status izvora
Osnova: prethodni Codex refaktor (52 commita, spojen u `windows`), sopstvena nezavisna provjera tog refaktora iz iste sesije (179/185 ciljanih testova, pun suite 1414 passed/1 unrelated fail), i `agent_reports/2026-08-01_faktura-zavrsni-e-cleanup-audit.md` (Codex-ov vlastiti audit, aktivan, korišćen kao izvor za "legacy fallback namjerno ostaje"). Memorija `2026-08-01_faktura-3layer-refaktor-nije-zavrsen.md` — aktivna, ažurirana ranije u istoj sesiji.

## Impact analiza
`FakturaView` klasa (upstream, depth 2): LOW, 10 pogođenih, 4 direktna importera. `FakturaItemValidator` (upstream, depth 2): MEDIUM, 30 pogođenih, 14 direktnih (dijeli se sa agent-chat validation adapterima). Ovo je klasni nivo — plan eksplicitno traži da svaki agent koji izvršava Fazu 3+ ponovi impact provjeru na konkretnu metodu/simbol prije izmjene.

## Reprodukcija prije izmjene
N/A — zadatak je izrada plana, ne bugfix.

## Kontekst korišćen
`gui/tabs/faktura_view.py` (cio fajl pročitan preko delegiranog subagenta, 6267 linija), `services/faktura/*.py` (18 fajlova, subagent), `templates/agent-md/project_room_template.md` i `agent_report_template.md` (cio), `.worktrees/faktura-3layer/` git historija i status.

## Šta je urađeno
Napravljen sedmofazni plan ekstrakcije poslovne logike iz `faktura_view.py` u `services/faktura/` sloj, namijenjen DRUGIM agent sesijama (Codex, druge Claude sesije) da ga izvršavaju fazu-po-fazu, uz eksplicitan handoff protokol, scope lock po fazi, i zahtjeve za verifikaciju/nezavisnu provjeru.

## Zašto je urađeno
Korisnik je eksplicitno tražio plan koji može predati drugim agentima da ne troši tokene ove sesije na samu ekstrakciju, dok ova sesija ostaje u ulozi vođe/revizora. Prethodna analiza u istoj sesiji je pokazala da je linijski refaktor tek na početku (6267 vs 6424 linija, -2.4%) uprkos Codex-ovoj tvrdnji o "~65% završeno" — plan operacionalizuje šta konkretno treba uraditi da se ta razlika stvarno zatvori.

## Kako je urađeno
1. Delegiran general-purpose subagent (foreground) da pročita `faktura_view.py` metod-po-metod i kategorizuje svih 119 ne-`_on_*` privatnih metoda (UI / DUPLIKAT / EKSTRAKCIJA / DIREKTAN-POZIV-SERVISA) sa linijskim opsezima, grupisano po funkcionalnoj oblasti.
2. Nezavisno provjereno (grep, ne povjerovano subagentu na riječ) troje otvorenih pitanja koje je subagent flagovao: `ImportService` je aktivan kod (koristi ga `processing_worker.py`) ali NIJE ožičen u `FakturaView`; `_collect_tariff_previews` nema pozivaoca nigdje u repou; `_can_use_unified_manual_import()` vraća False (aktivira legacy granu) kad god je `assembly.master_list_loaded` True — legacy uvoz putevi NISU mrtav kod.
3. Otkriveno da `.worktrees/faktura-3layer/` (grana `refactor/faktura-3layer`) je zastarjela (njen vrh je ancestor od `windows`, ali `windows` je otišao dalje) i ima nepovezan uncommitted WIP — flagovano u planu kao rizik, NIJE dirano.
4. `gitnexus_impact` pokrenut na `FakturaView` i `FakturaItemValidator` (upstream) da se dobije osnovni rizik-nivo za "Pogođeno" sekciju plana.
5. Plan napisan po `templates/agent-md/project_room_template.md` strukturi, proširen na 7 faza rastućeg rizika, sa eksplicitnim "ne ponavljati % završeno" upozorenjem i handoff protokolom.

## Šta nije dirano
Nijedna linija u `gui/tabs/faktura_view.py` ili `services/faktura/*.py` — plan je čisto dokumentacioni, izvršenje faza je namjerno ostavljeno budućim agent sesijama. Nije diran `.worktrees/faktura-3layer/` niti njegov nepovezan WIP (`ui/naimenovanja_tab_OPTIMIZED_ui.py`, `ui/zaglavlje_tab_ui.py`) — samo evidentiran kao rizik. Nije diran pre-postojeći uncommitted WIP u root working tree-u (`dist_client/ui/naimenovanja_tab_OPTIMIZED_ui.py`, `dist_client/ui/zaglavlje_tab_ui.py`, `.worktrees/`, razni `??` fajlovi) — provjeren `git status --short` prije staging-a, dodat u commit samo novi `project_rooms/*.md` fajl.

## Verifikacija
`git status --short` prije/poslije `git add` potvrđuje da je staged tačno 1 fajl. `gitnexus_detect_changes(scope=compare, base_ref=04707cf)` nakon commita potvrđuje da su jedini "touched" simboli iz pre-postojećeg tuđeg WIP-a (`dist_client/ui/*.py`), ne iz ovog commita — plan-fajl kao markdown nije indeksiran kao kod simbol, što je očekivano. Nema testova za ovaj tip promjene (dokumentacija).

## Nezavisna provjera
- Checker korišćen: NE
- Checker agent/model: N/A
- Šta je checker provjerio nezavisno: N/A
- Koje pretpostavke je pokušao oboriti: N/A
- Šta je potvrđeno: N/A
- Šta nije potvrđeno: N/A
- Da li je promjena spremna za prihvatanje: DA (plan je predlog za izvršenje, ne izvršena izmjena koda — nezavisna provjera postaje obavezna PO FAZI kad se faza stvarno izvrši, posebno Faza 3 i Faza 6, kako plan i navodi)

## Pronađeni problemi
Subagent je inicijalno predložio da se DUPLIKAT metode uvoza (`_get_invoice_name`, `_track_file_type`, `_extract_import_result_data`) jednostavno zamijene pozivom na `services/faktura/import_service.py:ImportService` — sopstvenom provjerom (grep) utvrđeno da taj servis NIJE ožičen u `FakturaView` i da ima drugačiji poziv-kontekst (agent pipeline bez GUI), pa je plan eksplicitno upozorio da se ponašanje mora uporediti red-po-red prije spajanja, ne slijepo "obrisati i pozvati servis".

## Odbačene opcije
- Opcija: raditi cijeli refaktor u jednoj velikoj agent sesiji/PR-u.
- Zašto je razmatrana: brže za agenta sa punim kontekstom, bez overhead-a re-orijentacije između faza.
- Zašto je odbačena: 119 metoda / 6267 linija je prevelik, nedovoljno verifikovan korak za jedan potez; onemogućava nezavisnu provjeru po dijelovima; rizik od regresije na aktivnoj produkcionoj funkcionalnosti (carinski dokumenti).
- Kada odluku ponovo otvoriti: ako se pokaže da fazni pristup troši više vremena na re-orijentaciju nego što štedi na riziku.

## Konflikti / kontradiktorni izvori
Codex-ova tvrdnja "~65% Faktura je u troslojnoj arhitekturi" (usmeno korisniku) vs. izmjereno stanje (linije/broj metoda) koje pokazuje da je ekstrakcija tek na početku. Tretirano kao: Codex-ova tvrdnja vjerovatno opisuje workflow-coverage (koliko akcija ima RADAN Controller→Service put), ne udio koda premještenog iz View-a — ovo je već ranije evidentirano u memoriji `2026-08-01_faktura-3layer-refaktor-nije-zavrsen.md`, plan ovdje samo operacionalizuje razliku. Korisnička potvrda nije potrebna — korisnik je već prihvatio ovo tumačenje ranije u sesiji.

## Commitovi
| Hash | Poruka |
| --- | --- |
| e52f368 | docs(faktura): fazni plan ekstrakcije poslovne logike iz faktura_view.py |

## Rizici / ograničenja
Plan se oslanja na subagent-ovu kategorizaciju metoda (UI/DUPLIKAT/EKSTRAKCIJA/DIREKTAN-POZIV) — nije svaka metoda ručno pročitana od strane ove sesije, samo su tri najkritičnija otvorena pitanja nezavisno provjerena. Subagent je sam označio nekoliko stavki kao "NEJASNO — ruč provjeriti" (npr. `_import_multiple_files` preklapanje sa `ImportService.import_multiple_files`) — agent koji izvršava Fazu 2/6 mora to razriješiti prije nego što nastavi, plan to eksplicitno traži ali ne garantuje da će se poštovati.

## Potreban follow-up
Sve — ovo je plan, ne izvršenje. Faze 1-7 su sve PENDING. Faza 6 (legacy uvoz putevi) eksplicitno traži korisničku odluku (PROBE prije implementacije) o tome da li se legacy grana refaktoriše in-place ili unified put proširuje da je zamijeni potpuno.

## Potrebna korisnička potvrda
Da li se `.worktrees/faktura-3layer/` (zastarjela grana `refactor/faktura-3layer` sa nepovezanim uncommitted WIP-om) briše, arhivira, ili ostavlja netaknuta — nije dirana u ovom zadatku jer brisanje worktree-a s uncommitted izmjenama je destruktivna akcija van scope-a ovog plana.
