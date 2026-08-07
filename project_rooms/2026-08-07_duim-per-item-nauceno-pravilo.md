## Cilj
DUIM (Međunarodni uvozni certifikat za robu dvojne namjene) trenutno se u exportu
piše samo JEDNOM, na Item 1 (header-level, kao N380/DIS/DV1). ASYCUDA World ga
stvarno zahtijeva PO STAVCI, za tarifne brojeve koje njen interni rule engine
označava kao potencijalno dvojne namjene — potvrđeno round-trip poređenjem
(`BLAGIĆ-LOREN-7-8.xml` naš export vs. `BLAGIĆ-LOREN-7-8-asycuda.xml` nakon
ASYCUDA provjere: 11 tarifnih brojeva dobilo je poseban DUIM zapis po stavci,
sa praznom referencom = crveni red). Korisnik je potvrdio (2026-08-08): u
stvarnom poslu se ta rubrika popunjava tekstom "Roba nije dvojne namjene" i
carina to prihvata; jedino praktično rješenje je učiti PO STAVCI koje tarifne
brojeve je ASYCUDA ranije (u stvarnim, uvezenim deklaracijama) tako označila,
i to koristiti kao izvor za automatsko popunjavanje ubuduće — isti princip kao
zvanična BiH Lista robe dvojne namjene NE koristiti direktno (HS kod sam po
sebi nije dovoljan za pravnu klasifikaciju — samo ASYCUDA-ino ponašanje je
pouzdan operativni signal).

## Pogođeno
`gitnexus_impact` na `AsycudaXMLBuilder._add_items` (exporters/asycuda_xml_builder.py):
risk **HIGH**, 1 direktan pozivalac (`build()`), lanac do `export_to_xml()` →
`_izvezi_xml()` (agent workflow) / `_on_export_xml()` (Zaglavlje GUI dugme) —
funkcija kroz koju prolazi SVAKI XML export u aplikaciji.

## Plan
1. `services/agent/learning/exporter_xml_indexer.py` — nova funkcija
   `sync_duim_rule_knowledge_base()` (paralelna `sync_tariff_knowledge_base()`):
   skenira sve indeksirane XML-ove, za svaki `<Item>` traži
   `<Attached_documents>` gdje je `Attached_document_code == "DUIM"` I
   `Attached_document_from_rule == "1"`, upisuje `Commodity_code` u novu
   PostgreSQL tabelu `catalogs.tariff_duim_rules` (isti pattern/schema stil kao
   `product_tariff_mapping`). Pozvati iz `reindex()` pored postojećeg tarifnog sync-a.
2. Nova mala helper funkcija za lookup (npr. `get_duim_tariff_codes() -> set[str]`)
   za čitanje potvrđenih kodova pri exportu.
3. `exporters/asycuda_xml_builder.py::_add_items()` — za svaku stavku, ako je
   njen `tariff_code` u naučenom skupu, dodati NOVI, per-item
   `<Attached_documents>` blok (code=DUIM, name="Međunarodni uvozni certifikat
   za robu dvojne namjene", number="Roba nije dvojne namjene", from_rule=True)
   DIREKTNO na tu `<Item>` — odvojeno od postojeće `header_docs`/item-1-only
   logike, koja ostaje netaknuta za N380/DIS/DV1/PZT/N730/PE.
4. Identična izmjena u `dist_client/` kopijama oba fajla.
5. Seed: sačuvati `BLAGIĆ-LOREN-7-8-asycuda.xml` (i ranije `BLAGIĆ-LOREN-7-8.xml`
   ako zatreba za kontekst) u `docs/NOVA ASIKUDA/` (postojeći learning folder,
   već sadrži realne customer XML-ove — konzistentno sa postojećom praksom),
   pokrenuti `exporter_xml_indexer.py --reindex` da odmah popuni tabelu sa
   potvrđenih 11 tarifnih brojeva iz ove deklaracije.

## Šta NE dirati
- Postojeća `header_docs`/`_PREF_TO_DOC_CODE`/N380-DIS-DV1-PZT-N730 logika u
  `_add_items()` — ostaje potpuno netaknuta.
- `zaglavlje_view.py::get_data()` FROM_RULE_CODES fix iz prethodnog zadatka —
  DUIM se VRAĆA na `False` tamo (header-level DUIM se više ne generiše ni od
  korisnika ručno unesenog reda — per-item mehanizam ga zamjenjuje), ostatak
  skupa (N380/DIS/DV1) se ne dira.
- `services/tariff_controls_service.py` (VET/SAN/FIT/UVK/AGL) — odvojen
  mehanizam, nije dio ovog zadatka.
- Zvanična BiH Lista robe dvojne namjene (Codex-ova SQLite baza) — NIJE
  korišćena za automatsku odluku, samo referentni materijal za budući
  ručni lookup ako se ikad doda kao GUI feature.

## Prihvatljiv ishod (scope lock)
Postojeći N380/DIS/DV1 export (potvrđen ispravan od korisnika na stvarnom
ASYCUDA uvozu) mora ostati bit-za-bit isti. Novi DUIM per-item mehanizam se
dodaje ISKLJUČIVO za tarifne brojeve potvrđene iz stvarnih ASYCUDA XML-ova —
nikad se ne izmišlja/pretpostavlja tarifni broj bez XML dokaza.

## Plan verifikacije
1. `python -m py_compile` na sve izmijenjene fajlove.
2. Postojeći test suite (`test_asycuda_goods_description.py`) i dalje prolazi
   bez regresije.
3. Direktan poziv `sync_duim_rule_knowledge_base()` na test XML-u (LOREN-7-8-asycuda)
   → potvrditi da su tačno ta 3 tarifna broja (uzorak) upisana u
   `catalogs.tariff_duim_rules`.
4. Direktan poziv exportera na test draft-u sa jednom stavkom čiji je
   tariff_code u naučenom skupu → potvrditi da izlazni XML ima
   `<Attached_documents>` sa DUIM/"Roba nije dvojne namjene"/from_rule=1 NA TOJ STAVCI.
5. Ne rušiti postojeći export (regression test na BLAGIĆ-SRECKO ili sličnoj
   poznatoj deklaraciji koja NEMA DUIM stavke — mora ostati bez DUIM bloka).

## Rollback / oporavak
Nova tabela je aditivna (ne mijenja postojeće šeme); ako se pokaže pogrešnom,
brisanje tabele + revert exportera vraća prethodno (poznato ispravno za
N380/DIS/DV1, poznato nepotpuno za DUIM) stanje bez gubitka podataka.

## Nezavisni checker
Nije korišćen za samu implementaciju (LOW/MEDIUM po broju izmijenjenih
simbola van `_add_items`, a `_add_items` samo dobija DODATNU granu logike, ne
mijenja postojeću) — ali korisnik treba ručno potvrditi na stvarnom sledećem
uvozu (isti proces kao za N380/DIS/DV1 fix) da crveni red za DUIM na
potvrđenim tarifama nestaje.

## Odbačene opcije
- Opcija: koristiti zvaničnu BiH Listu robe dvojne namjene (Codex-ova SQLite
  baza) za automatsko HS→DUIM pravilo.
- Zašto je razmatrana: Codex je predložio kao "pravni sloj", nezavisno
  provjerena kao legitimna (362 zapisa, kontrolni brojevi poput 2A001 sa
  preciznim tehničkim kriterijumima, npr. ISO 492 klasa tolerancije za
  ležajeve).
- Zašto je odbačena: lista NIJE HS-kod tabela — kontrola se određuje po
  tehničkim kriterijumima koje ne možemo automatski provjeriti iz tarifnog
  broja. Korisnik eksplicitno potvrdio (2026-08-08) da je jedino praktično
  rješenje učenje iz ASYCUDA-inog stvarnog ponašanja, ne pravna klasifikacija.
- Kada odluku ponovo otvoriti: ako se ikad doda GUI feature za "provjeri da li
  je roba stvarno dvojne namjene" kao pomoć korisniku (ne automatska odluka).

## Konflikti
Nema.
