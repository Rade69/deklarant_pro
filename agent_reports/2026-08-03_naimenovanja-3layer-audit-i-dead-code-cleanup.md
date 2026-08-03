## Datum
2026-08-03

## Agent
Claude Code (Sonnet 5)

## Scope
`gui/tabs/naimenovanja_view.py`, `dist_client/gui/tabs/naimenovanja_view.py` (jedna metoda),
plus audit (bez izmjene) `gui/tabs/naimenovanja_controller.py`, `gui/tabs/naimenovanja_tab.py`.

## Status izvora
- `project_rooms/2026-08-03_naimenovanja-3layer-status-i-nastavak.md` (handoff napisan ranije
  ove sesije) — aktivan, korišćen kao polazna tačka, dopunjen ovim izvještajem.
- `git show f561e55:project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md`
  (Codex, 801 linija, na `feature/agent-v2`, nikad spojen u `windows`) — aktivan, autoritativni
  kriterijum "šta znači završeno" za ovaj tab. Pročitan u cijelosti.
- Zadnji commit na `windows` prije ove sesije (`7d9d6e2`, Codex, "zavrsi tarifni dokument i xml
  tok") — poruka je **djelimično netačna samoprijava**: dokazano da 3 toka (XML→Zaglavlje sync,
  cio-deklaracija save, dropdown DB setup) i dalje nisu migrirani u Controller.

## Impact analiza
`gitnexus_impact` na `_add_history_docs` nije mogao vratiti direktan rezultat (repo
disambiguation greška u MCP alatu — `repo` parametar sa zagradama u nazivu nije prihvaćen).
Nadomješteno nezavisnijim i jačim dokazom za ovaj konkretan slučaj: repo-wide `grep` za
`_add_history_docs` (svi fajlovi, uključujući worktree-ove) potvrđuje **0 poziva** na `windows`
grani (ni u `gui/`, ni u `dist_client/`, ni u testovima) — metoda je bila mrtav kod. Poziv postoji
samo u dva stara worktree-a (`agent-v2`, `codex-faktura-toolbar`) koji nisu spojeni u `windows`.
Rizik izmjene: LOW (brisanje nedostupnog koda, nula pozivalaca).

`gitnexus_detect_changes` (poslije `npx gitnexus analyze` reindex-a) NIJE prikazao izmjenu u
`naimenovanja_view.py` u `changed_symbols` — vjerovatno alat ne hvata čisto brisanje cijele
metode bez izmjene susjednih linija. Ne blokira jer je nezavisan dokaz (grep + testovi) dovoljan
za ovaj obim izmjene.

## Reprodukcija prije izmjene
N/A — ovo nije bugfix nego audit + cleanup mrtvog koda. Dokaz da je kod mrtav: repo-wide grep
(vidi "Impact analiza" gore) i čitanje `_on_tariff_enter`/`_on_tariff_changed` u View-u — ni
jedan živi handler ne poziva `_add_history_docs`.

## Kontekst korišćen
- `f561e55:project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md` — pročitan u
  cijelosti (801 linija), jer je to autoritativni acceptance kriterijum za ovaj refaktor.
- `gui/tabs/naimenovanja_view.py` (3236 linija) — NIJE pročitan u cijelosti, samo ciljani odsjeci
  oko svih 16 `from services.` importa (grep + Read po lokaciji) i svih 16 `_on_*` handlera (grep
  za potpise, zatim Read ključnih).
- `gui/tabs/naimenovanja_controller.py` (313 linija) — pročitan u cijelosti radi poređenja sa
  planom (Faza 5/6 sekcije).
- `services/naimenovanja/naimenovanja_service.py:467` (`add_tariff_documents`) — pročitan da
  potvrdi da je logika `_add_history_docs`-a stvarno duplirana/superseded, ne samo slična.

## Šta je urađeno
1. Pročitan pun Codex plan (`f561e55`) — sadrži ciljnu arhitekturu, mapiranje metoda po slojevima,
   8 faza sa gate-ovima, acceptance kriterijume.
2. Klasifikovano svih 16 `from services.` importa u `naimenovanja_view.py`: 12 legitimnih (čiste
   kalkulacije preko static Service metoda, isti standard kao Faktura), 4 stvarne arhitektonske
   greške (View direktno mutira draft / radi DB setup bez Controllera).
3. Audit svih 16 `_on_*` handlera — potvrđeno da `save_current_item`, `navigate_to`, `add_item`,
   `delete_item`, `on_tariff_changed`, `sync_pe_docs_to_header`, `import_xml` (entry signal),
   `accept_tariff_suggestion`, `prepare_tariff_suggestions` ispravno idu kroz Controller.
   `_on_save` i dio `_on_import_xml`/`_apply_xml_import_to_zaglavlje` NE idu.
4. Istražen prioritetni nalaz (`_add_history_docs`, korisnikov izbor nakon
   `AskUserQuestion`) — otkriveno da NIJE živa arhitektonska greška nego mrtav kod, superseded
   ispravnim Controller-tokom.
5. Obrisana mrtva `_add_history_docs` metoda iz `gui/tabs/naimenovanja_view.py` i
   `dist_client/gui/tabs/naimenovanja_view.py` (identičan sadržaj u oba, potvrđeno prije brisanja).
6. `py_compile` na oba fajla — OK. Puna `pytest tests/ -q` — 1684 passed, 4 pre-postojeća fail-a
   nepovezana sa izmjenom (agent tool schema count, XML parser hardkodovana putanja, tarifni
   mapping DB stanje — vidi memory `2026-08-01_product-tariff-mapping-word-overlap-mina-bug`).
7. `npx gitnexus analyze` (indeks je bio stale, `2ed87aa`) — pokrenut prije i poslije commita.
8. Commit `6b20f57` — samo dva izmijenjena fajla staged eksplicitno (ne `git add -A`).
9. Dopunjen `project_rooms/2026-08-03_naimenovanja-3layer-status-i-nastavak.md` sa
   "ZATVARANJE (djelimično)" sekcijom — status i dalje NIJE ZAVRŠENO, sa tačnim file:line
   referencama za preostala 3 nalaza.

## Zašto je urađeno
Prethodna sesija (isti dan) je zatvorila Faktura tab refaktor i ostavila handoff da se
Naimenovanja tab isto provjeri — poznato je bilo da Controller postoji (313 linija) ali bez
zatvarajućeg audita, i da je zadnji Codex commit "zavrsi..." poruka bez nezavisne provjere
(isti obrazac kao ranija netačna "Codex kaže 65%" epizoda). Cilj ove sesije: utvrditi da li je
refaktor stvarno završen, po istom standardu kao Faktura.

Korisnik je, kad je pronađeno da 4 toka zaobilaze Controller, birao između (a) pun nastavak Faza
6+7 odjednom, (b) samo dokumentovati bez diranja koda, (c) uzak fix najrizičnijeg nalaza —
izabrao (c). Pri istrazi se ispostavilo da najrizičniji nalaz (`_add_history_docs`, View direktno
mutira `draft.header_attached_documents`) nije stvarno dostupan kod — mrtav je, jer je
`NaimenovanjaService.add_tariff_documents()` (pozvan iz `Controller.on_tariff_changed`, ožičen
preko `tariff_lookup_requested` signala) već ispravno preuzeo tu odgovornost tokom ranije Faze 5/6.
Brisanje dead koda je i dalje vrijedno — Faza 8 plana eksplicitno traži "obrisati samo dokazano
nepovezane stare metode", i mrtav kod koji izgleda kao aktivna arhitektonska greška zbunjuje
sledeći audit.

## Kako je urađeno
Edit alatom uklonjen cio metod-blok (32 linije uključujući prazan red) u oba fajla, string-for-
string identičan pre brisanja (provjereno Read-om oba fajla prije izmjene).

## Šta nije dirano
- Preostala 3 nalaza (namjerno, po korisnikovoj odluci — follow-up, ne ovaj zadatak):
  - `_apply_xml_import_to_zaglavlje` (`naimenovanja_view.py:2036`) — View direktno instancira
    `ZaglavljeService()` i mutira `self.draft`, bez Controllera.
  - `_on_save` (`naimenovanja_view.py:2317`) — cio izvoz deklaracije u View-u, bez signala ka
    Controlleru.
  - `_setup_package_dropdown` / `_setup_rb40_widgets` (`naimenovanja_view.py:836, 1069`) — View
    sam instancira `NaimenovanjaService()` za DB-backed šifarnike (Faza 3 gate nije ispunjen).
- Zatečen nekomitovan WIP drugog agenta/sesije (`AGENTS.md`, `CLAUDE.md`,
  `dist_client/ui/naimenovanja_tab_OPTIMIZED_ui.py`, `dist_client/ui/zaglavlje_tab_ui.py`,
  `.worktrees/`, više netrackovanih fajlova) — nije diran, nije staged, i dalje prisutan u
  `git status` poslije ovog commita.
- Faktura tab — van scope-a, već zatvoren ranije ove sesije.
- Parser Studio — potpuno odvojen projekat, van scope-a.

## Verifikacija
- `python -m py_compile` na oba izmijenjena fajla — OK.
- `python -m pytest tests/ -q` — 1684 passed, 86 skipped, 5 xfailed, 4 failed (pre-postojeći,
  nepovezani), 1 error (pre-postojeći, nepovezan — `test_model_benchmark.py` fixture problem).
- Repo-wide grep potvrđuje 0 pozivalaca obrisane metode na `windows` prije i nakon brisanja
  (logička provjera da brisanje ništa ne kida).
- Nema namjenskog unit testa za `naimenovanja_view.py` u `tests/` — GUI sloj ovog taba nema
  karakterizacione testove (isto stanje kao što je plan opisao za "Faza 0" koja nikad nije
  urađena na `windows`). Ovo je poznati gap, ne nastao ovom izmjenom.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik (brisanje nedostupnog koda, 0 pozivalaca, puna test svita zelena) — po
  AGENTS.md kriterijumu nezavisna provjera nije obavezna za ovaj obim. Preostala 3 nalaza (koja
  DIRAJU živu draft mutaciju/XML tok) će zahtijevati nezavisnu provjeru kad se budu radila.

## Pronađeni problemi
- Prvobitna pretpostavka (iz handoff-a) da je `_add_history_docs` "stvarna arhitektonska greška"
  bila je netačna nakon dubljeg audita — bio je to lažno pozitivan nalaz na prvi pogled (View
  direktno mutira draft = izgleda kao bug), koji se pri provjeri pokazao kao neopasan mrtav kod.
  Vrijedna pouka: i dalje potvrditi da je "sumnjiv" kod stvarno DOSTIŽAN prije nego se tretira kao
  aktivan bug.
- `gitnexus_impact`/`detect_changes` MCP alati imali su dvije manje smetnje ove sesije: (1) `repo`
  parametar sa zagradama u nazivu ("deklarant_pro (C:\...)") je odbijen iako je tačno taj string
  vraćen kao "Available" — rješenje: koristiti goli path bez naziva; (2) `detect_changes` nije
  prikazao čisto brisanje metode ni poslije reindexa — nije blokiralo jer je nezavisan dokaz
  postojao, ali vrijedi zapamtiti za buduće provjere sličnog obima.

## Odbačene opcije
- Opcija: pun nastavak Faza 6+7 (migracija sva 4 nalaza) u ovoj sesiji.
- Zašto je razmatrana: to je bio jedan od ponuđenih odgovora korisniku, i najbliže "stvarnom
  završetku" refaktora.
- Zašto je odbačena: korisnik je eksplicitno izabrao uži obim (samo najrizičniji nalaz); plan
  procjenjuje Faza 6+7 na 8-13h, veliki obim za jednu turu bez checkpointa.
- Kada odluku ponovo otvoriti: sledeća sesija na Naimenovanja, kad korisnik odluči prioritet
  između preostala 3 nalaza.

## Konflikti / kontradiktorni izvori
Zadnji Codex commit poruka ("zavrsi tarifni dokument i xml tok", `7d9d6e2`) tvrdi da je dokument i
XML tok završen. Kod pokazuje da JE završeno za tarifni-dokument-suggestion tok (preko
`add_tariff_documents`), ali NIJE za XML→Zaglavlje sync (`_apply_xml_import_to_zaglavlje`) niti za
cio-deklaracija save (`_on_save`). Tretirano kao: commit poruka je djelimično tačna — sadrži i
stvarno gotov posao i precijenjen obim. Korisnička potvrda nije potrebna za ovaj zaključak (dokaz
je direktno u kodu), ali JE potrebna za redoslijed/prioritet preostalog rada (vidi "Potreban
follow-up").

## Commitovi
| Hash | Poruka |
| --- | --- |
| `6b20f57` | `refactor(naimenovanja): ukloni mrtvu _add_history_docs metodu iz View-a` |

## Rizici / ograničenja
- Nijedan poznat rizik od ove konkretne izmjene (mrtav kod, 0 pozivalaca, testovi zeleni).
- Preostala 3 nalaza NISU rizik SADA (postojeće ponašanje nepromijenjeno), ali predstavljaju
  postojeći arhitektonski dug koji čini sledeći audit/izmjenu tih tokova rizičnijom nego što bi
  bila da su ranije migrirani (npr. `_on_save` i `_apply_xml_import_to_zaglavlje` diraju draft
  mutaciju i XML sadržaj — carinski osjetljivo kad se na njih bude radilo).
- Nema karakterizacionih testova za `naimenovanja_view.py` (Faza 0 plana nikad urađena na
  `windows`) — svaka buduća izmjena preostalih tokova nosi veći rizik regresije bez njih.

## Potreban follow-up
1. `_apply_xml_import_to_zaglavlje` — migrirati u Controller (Faza 7 plana).
2. `_on_save` — migrirati u Controller (Faza 7/8 plana, eksplicitno navedeno u §7.2).
3. `_setup_package_dropdown` / `_setup_rb40_widgets` — Controller treba dobavljati kataloge
   umjesto da View sam instancira Service (Faza 3 plana).
4. Razmotriti karakterizacione testove (Faza 0 plana) prije nego se bilo koji od gornja 3 toka
   dira — trenutno nema automatizovane zaštite od regresije za `naimenovanja_view.py`.
Sve gore zapisano i u `project_rooms/2026-08-03_naimenovanja-3layer-status-i-nastavak.md`
("ZATVARANJE (djelimično)" sekcija) sa tačnim file:line referencama.

## Potrebna korisnička potvrda
- Odluka o prioritetu/redoslijedu preostala 3 nalaza za sledeću sesiju (nije hitno, tab i dalje
  radi identično kao prije — ovi tokovi rade, samo arhitekturno nisu na trosloj standardu).
- Nema potrebe za ručnom GUI provjerom ove specifične izmjene — brisanje nedostupnog koda ne
  mijenja nijedno vidljivo ponašanje.
