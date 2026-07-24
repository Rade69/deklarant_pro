# Brief: Duboka istraga kodne baze — Deklarant Pro

**Namjena ovog fajla**: brief za drugog agenta koji radi ISKLJUČIVO istraživanje
(bez ispravki, bez commitovanja) i vraća strukturiran izvještaj. Poslije toga
Claude Code primjenjuje ispravke na osnovu tog izvještaja.

---

## OBAVEZNO PRVO PROČITATI

- `AGENTS.md` (kanonska pravila projekta — konvencije, zabrane, arhitektura)
- `docs/CONTEXT.md`, posebno **§43, §44, §45** (2026-07-23) — već urađen posao,
  NE PONAVLJATI

---

## Šta je VEĆ pokriveno (ne trošiti vrijeme na ovo)

- pg_trgm indeksi dodati za: `product_tariff_mapping`, `product_similarity_memory`,
  `zvanicna_tarifa`, `declaration_items` (migracije 007, 011, 012)
- `__file__`-relativni DB_PATH bez `sys.frozen` svijesti — popravljeno u:
  `gui/tabs/sifarnici/tariff_hierarchy.py`, `services/tariff/tariff_tree_service.py`,
  `services/agent/chat/tariff_history_analysis_service.py`
- Duplicirane metode/funkcije unutar iste klase — AST sken cijelog projektnog
  koda (`services/`, `gui/`, `importers/`, `core/`, `database/`, `exporters/`,
  `scripts/`, `config/`, `dist_client/` sopstveni izvor, `app/`, root `.py`) —
  ČIST rezultat, samo `processing_worker.py` je bio stvaran slučaj (već popravljen)
- `dist_client/` vs root drift — DJELIMIČAN sweep (20 od 45 fajlova sa stvarnom
  razlikom detaljno pregledano, 9 popravljeno). NAMJERNO preskočeno i ostavljeno
  za posebnu sesiju: `exporters/asycuda_xml_builder.py` (kompleksan dvosmjerni
  drift), `importers/packing_list_parser.py` (samo reordering, bez razlike)

**VAŽNO**: `C:\Users\38765\Desktop\deklarant_pro\dist\DeklarantPro\` je STVARAN,
aktuelan izbildani `.exe` (PyInstaller output sa `_internal/` zavisnostima) —
NIJE zaostatak, ne dirati, ne komentarisati kao "staro"/"leftover". Isključiti iz
grep/AST skeniranja (šum, ne projektni kod), ali ne brisati niti predlagati brisanje.

---

## Metodologija koja je do sad davala rezultate (koristiti isti pristup)

1. Nađi JEDAN konkretan primjer problema (grep/read)
2. DOKAŽI da je stvaran problem — pokreni kod, `EXPLAIN ANALYZE` za SQL, `diff`
   za drift, direktan poziv funkcije koji pokazuje netačan rezultat
3. Provjeri da li ista klasa problema postoji NA DRUGIM MJESTIMA (grep šire)
4. Provjeri da li je kod zaista aktivan (ima realnog pozivaoca), ne mrtav kod

Ne prijavljivati nalaz bez dokaza iz koraka 2. Bolje 5 potvrđenih nalaza nego
30 nagađanja — svaki neprovjeren nalaz u izvještaju je trošak tokena unazad.

---

## Predložene oblasti za istragu (prioritet opadajući)

1. **`except Exception: pass` / bare `except:`** koji tiho gutaju greške u
   servisnom sloju (`services/`) — posebno mjesta gdje bi tiha greška značila
   da korisnik dobije netačan/prazan rezultat bez ikakve poruke (isti obrazac
   kao `tariff_tree_service.py` bug iz §45 — funkcija je bila slomljena
   mjesecima jer je exception hvatan i gutan bez traga).

2. **Qt threading van LLM poziva** — sinhroni network/DB pozivi ili teški
   proračuni direktno u slot metodama (`_on_*_clicked`) bez `QThread` workera,
   van onoga što je već pokriveno (`system_panel.py::_on_ai_health_clicked`,
   §43). Fokus: `gui/tabs/*.py`, `gui/dialogs/*.py`.

3. **Bulk operacije nad `QTableWidget` bez `blockSignals(True/False)`** —
   AGENTS.md eksplicitno traži ovaj pattern za bulk operacije (vidi CONTEXT.md
   §5), provjeriti da li je dosljedno primijenjen svugdje gdje se tabela puni
   petljom od >20-30 redova.

4. **f-string ili `.format()` direktno u SQL upitu** (zaobilazi parametrizaciju,
   potencijalni SQL injection) — AGENTS.md eksplicitno zabranjuje, treba
   potvrditi da nema izuzetaka. `grep -rn "f\"\"\".*SELECT\|f'.*SELECT\|\.format(.*SELECT"`.

5. **`mock` korišten za SQLite/PostgreSQL konekciju u testovima** — AGENTS.md
   zabranjuje ("maskira realne greške"). Provjeriti `tests/` za `unittest.mock`/
   `MagicMock` patch-ovan direktno na `get_db_connection`/`sqlite3.connect`.

6. **Nedostajući `consumed_paths` u kombinovanim importerima** — AGENTS.md
   dokumentuje ovo kao OBAVEZNO za svaki importer koji interno koristi drugi
   fajl (Excel+PDF par i sl.), sa napomenom da bez toga dolazi do duplikata
   stavki. Provjeriti sve fajlove u `importers/vendors/` koji rade kombinovani
   import (traže "combine"/"pair" u imenu/logici) da li ISPRAVNO postavljaju
   `consumed_paths` na `ImportResult`.

7. **Preostali `dist_client` drift** — `exporters/asycuda_xml_builder.py`
   (namjerno preskočen, kompleksan) i još 25 fajlova od originalnih 45 koji
   NISU detaljno pregledani u §43 (traži listu u agent_reports/
   2026-07-23_skeniranje-uskih-grla-i-dist-client-drift.md, sekcija sa svih 45
   fajlova po veličini razlike) — sistematski proći kroz preostale i
   klasifikovati namjerno/slučajno kao u §43.

8. **QThread lifecycle / cleanup** — provjeriti da li se worker thread-ovi
   (`QThread` podklase) pravilno gase pri zatvaranju aplikacije ili prelasku na
   drugi tab (mogući "QThread: Destroyed while thread is still running" crash
   ili memory leak). Fokus na `gui/tabs/agent/widgets/*_worker.py`.

---

## Format izvještaja (OBAVEZNO — jedan nalaz = jedan blok)

Za SVAKI nalaz:

```
### [Oblast] Kratak naslov nalaza

- **Fajl:Linija**: putanja i tačan broj linije
- **Opis**: jedna rečenica šta je problem
- **Dokaz**: konkretan repro (EXPLAIN ANALYZE output, diff, poziv funkcije i
  njen stvaran rezultat, citat koda koji potvrđuje) — NE pretpostavka
- **Da li je aktivan kod**: potvrda da postoji stvaran pozivalac (grep/import
  chain), ne mrtav kod
- **Predlog fixa**: 1-2 rečenice, BEZ implementacije
- **Procijenjen scope**: koje GUI tabove/funkcije/agent chat komande pogađa
```

Na kraju izvještaja: kratak sažetak (broj potvrđenih nalaza po oblasti,
prioritet za Claude Code da počne popravljati).

---

## Šta NE raditi

- NE mijenjati nijedan fajl u repozitorijumu
- NE commitovati ništa
- NE ažurirati `docs/CONTEXT.md` niti pisati u `agent_reports/` — samo
  dostaviti izvještaj (kao poruku ili kao jedan markdown fajl u `project_rooms/`)
- NE predlagati preimenovanje srpskih naziva polja (`tarifni_broj`, `naziv_robe`,
  itd. — namjerno, vidi AGENTS.md) niti brisanje `dist/DeklarantPro/`

---

## Izlaz

Jedan markdown fajl (predlog imena): `project_rooms/2026-07-23_nalazi-duboke-istrage.md`
