# Popravka pozicionog indeksiranja RealDictCursor rezultata u exporter_xml_indexer

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `services/agent/learning/exporter_xml_indexer.py`
- `dist_client/services/agent/learning/exporter_xml_indexer.py`

Izmijenjene funkcije (identično u oba fajla): `get_stats()`,
`find_xml_for_pair()`, `find_xml_by_consignee()`, `get_all_pairs()`.

## GitNexus impact
Provjereno PRIJE izmjene za svaku funkciju zasebno (`gitnexus_impact`,
`direction: "upstream"`):

- `get_stats()` — LOW risk, pozivan samo iz `_ReindexWorker.run()` u
  `learning_panel.py`.
- `get_all_pairs()` — LOW risk.
- `find_xml_by_consignee()` — LOW/MEDIUM risk.
- `find_xml_for_pair()` — **CRITICAL risk**: 29 simbola, 10 direktnih
  caller-a (Faktura "Učitaj iz prethodne deklaracije" u
  `faktura_view.py`, agent chat `chat_worker.py`, `mcp_facade.py`
  fallback, `xml_workflow_service.py` x2, plus re-export shimovi
  `services/agent/exporter_xml_indexer.py` i `services/agent/__init__.py`).
  Korisniku je prijavljen CRITICAL rizik prije nastavka — korisnik je
  odobrio nastavak ("Naravno" / "Nastavi po planu") nakon procjene da fix
  ne mijenja shape/ključeve vraćenog dict-a i da su svi caller-i već
  defanzivni (`if result: ... else ...` / try-except).

`gitnexus_detect_changes(scope="unstaged")` PRIJE commita: `risk_level:
"low"`, `affected_processes: []`, 15 touched simbola u tačno 2 fajla (svih
4 funkcije u gui/ i dist_client/).

## Šta je urađeno
U svih 4 funkcije, sav pozicioni pristup rezultatima cursor-a
(`row[0]`, `row[3]`, `r[8]`, `best_match[4]`, itd.) zamijenjen je pristupom
po imenu kolone (`row['xml_filepath']`, `row['exporter_original']`, itd.),
prema imenima kolona/aliasa iz odgovarajućeg `SELECT` upita. U
`find_xml_for_pair()` popravljena su sva 4 query bloka: `exact_jib`,
`exact_name`, `exporter_only`, fuzzy match.

## Zašto je urađeno
Korisnik je prijavio: u "Učenje iz XML deklaracija" admin panelu,
reindeksiranje 657 novopreuzetih XML-ova sa ASYCUDA servera staje odmah
nakon "Korak 1/2 — Indeksiram parove izvoznik+uvoznik..." sa porukom
"❌ Greška: 0", statistika ostaje stara.

Root cause: `get_db_connection()` (linije 36-50) postavlja
`cursor_factory=RealDictCursor` — svi `fetchone()`/`fetchall()` rezultati su
`RealDictRow` (OrderedDict podklasa) keyed PO IMENU KOLONE.
`RealDictRow.__getitem__` NIJE override-ovan (verifikovano čitanjem source-a
`psycopg2.extras`), pa `row[0]` nakon konstrukcije baca `KeyError: 0`.
`str(KeyError(0)) == "0"` — tačno poruka "❌ Greška: 0" iz screenshot-a.
`_ReindexWorker.run()` poziva `get_stats()` ODMAH nakon `reindex()` (Korak
1), prije nego što "Korak 2/2" stigne da se loguje — `get_stats()` je
bacao `KeyError(0)`, `except Exception as e: self.error.emit(str(e))` →
"❌ Greška: 0".

Tokom istrage otkriveno da ISTI bug-pattern postoji u još 3 funkcije u istom
fajlu:
- `find_xml_for_pair()` i `find_xml_by_consignee()` su imale
  `try/except Exception` koji je gutao `KeyError` i vraćao `None` — funkcije
  su UVIJEK vraćale "nema rezultata", čak i kad je par postojao u bazi
  (mrtva grana "match found" nikad nije izvršena).
- `get_all_pairs()` nema try/except — bacao bi neuhvaćen `KeyError`.

## Kako je urađeno
Mehanička zamjena `row[N]`/`r[N]`/`best_match[N]` → `row['kolona']` po
svakom `SELECT` bloku, redom:
- `get_stats()`: `total`, `total_uses`, `last_used_any`, `unique_exporters`,
  `unique_jibs`, `unique_consignees`.
- `get_all_pairs()`: `exporter_normalized`, `consignee_normalized`,
  `consignee_jib`, `exporter_original`, `consignee_original`,
  `xml_filepath`, `declaration_date`, `use_count`, `last_used`.
- `find_xml_by_consignee()`: `consignee_jib` / `consignee_name` /
  fuzzy (`consignee_normalized`) blokovi — `xml_filepath`,
  `exporter_original`, `consignee_original`, `consignee_jib`,
  `declaration_date`.
- `find_xml_for_pair()`: sva 4 bloka (`exact_jib`, `exact_name`,
  `exporter_only`, fuzzy) — ista mapa kolona kao gore, plus
  `exporter_normalized` u fuzzy `_similarity_score()` pozivu.

Identične izmjene primijenjene redom u `services/agent/learning/
exporter_xml_indexer.py` i `dist_client/services/agent/learning/
exporter_xml_indexer.py` (potpuno identičan kod u oba stabla).

## Šta nije dirano
- `get_db_connection()` (linije 36-50) — `cursor_factory=RealDictCursor`
  je ISPRAVAN, ostaje netaknut; bug je bio u POZIVAOCIMA, ne u konekciji.
- `_ReindexWorker` / `learning_panel.py` — nije bilo potrebe mijenjati,
  greška je nestala čistim fix-om `get_stats()`.
- Re-export shimovi (`services/agent/exporter_xml_indexer.py`,
  `services/agent/__init__.py`) — nisu dirani, samo re-eksportuju funkcije
  bez vlastite logike.
- Caller-i (`faktura_view.py`, `chat_worker.py`, `mcp_facade.py`,
  `xml_workflow_service.py`) — nisu dirani; svi su već defanzivni i
  ostaju kompatibilni jer ključevi vraćenog dict-a nisu promijenjeni.
- `client.log.lck` (untracked) — nepovezan, nije dodat u commit.

## Verifikacija
- `python -m py_compile` na oba izmijenjena fajla — OK.
- Real-DB test (Postgres, `catalogs.exporter_xml_index`, 313 redova):
  - `get_stats()` → `{'total_pairs': 313, 'total_uses': 313,
    'last_used_any': ..., 'unique_exporters': 303, 'unique_jibs': 136,
    'unique_consignees': 143}`
  - `get_all_pairs()` → 313 dict-ova sa svim očekivanim ključevima.
  - `find_xml_for_pair(exporter, consignee_jib=..., consignee_hint=...)` →
    `match_type: 'exact_jib'`, popunjen `xml_filepath` itd.
  - `find_xml_for_pair(exporter)` (bez jib/hint) → `match_type:
    'exporter_only'`.
  - `find_xml_for_pair('PIP FOOD GROOP')` (namjerni typo, score 92.9% >=
    threshold 92%) → `match_type: 'fuzzy (93%)'`, ispravan `xml_filepath`.
  - `find_xml_by_consignee(consignee_jib=..., consignee_hint=...)` →
    `match_type: 'consignee_jib'`.

Prije fixa, sva 4 poziva bi vratila `None`/`KeyError`.

## Pronađeni problemi
Nema lažno pozitivnih nalaza — diagnoza (KeyError(0) == "0") se poklopila
sa screenshot-om na prvi pokušaj, a real-DB test je potvrdio sve 4
funkcije rade ispravno (uključujući fuzzy granu, koja zahtijeva da
similarity score >= 0.92 — prvi pokušaj sa truncated imenom (0.903) je
ispravno vratio `None`, drugi pokušaj sa typo-om (0.929) je vratio fuzzy
match).

## Commitovi
| Hash | Poruka |
|------|--------|
| `7d87606` | `fix(agent): popravi pozicioni indeksing RealDictCursor rezultata u exporter_xml_indexer` |

## Rizici / ograničenja
- `find_xml_for_pair()`/`find_xml_by_consignee()` su prije ovog fixa UVIJEK
  vraćale `None` (zbog gutanog `KeyError`-a) — sada PRVI PUT mogu vratiti
  popunjen dict ("match found"). Ova grana koda je do sada bila MRTVA u
  produkciji (nikad testirana end-to-end kroz GUI), pa postoji rizik da
  neki caller ima latentnu pretpostavku koja se nije do sada manifestovala
  (npr. format `declaration_date` kao `None` vs string — provjereno da
  `None` je legitimna vrijednost i u staroj i u novoj verziji).
- `find_xml_for_pair` ima CRITICAL GitNexus impact (10 caller-a) — fix je
  mehanički i ne mijenja shape dict-a, ali se preporučuje funkcionalni test
  (vidi "Potrebna korisnička potvrda").

## Potreban follow-up
- Pokrenuti reindeksiranje u "Učenje iz XML deklaracija" panelu nad 657
  novih XML-ova sa ASYCUDA servera i potvrditi da "Korak 2/2" sada izvršava
  i da statistika (2,451 deklaracija, itd.) raste.
- Pretražiti `services/agent/` za eventualne druge `cursor.fetchone()[N]`
  pozive nakon `get_db_connection()` (RealDictCursor) — nije rađen
  exhaustive grep van ovog fajla, mogući isti bug-pattern negdje drugo
  (vidi memory fajl "How to apply").

## Potrebna korisnička potvrda
1. Pokrenuti reindeksiranje XML-ova u admin panelu i potvrditi da "Korak
   2/2 — Ekstraktujem tarifne veze..." stvarno izvrši (umjesto "❌ Greška:
   0").
2. U Faktura tabu, na fakturi sa exporterom koji već ima zapis u
   `catalogs.exporter_xml_index`, testirati "Učitaj iz prethodne
   deklaracije" — prvi put kad `find_xml_for_pair` stvarno vraća match,
   provjeriti da se XML predložak korektno učita.
3. U agent chatu, testirati prijedlog XML predloška za poznatog
   exportera/consignee-a — provjeriti da `mcp_facade`/`xml_workflow_service`
   integracije rade sa novim populated rezultatom.
