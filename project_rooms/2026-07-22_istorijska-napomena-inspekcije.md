# Istorijska napomena za inspekcije (informativni sloj)

## Cilj

Korisnik: statični izvor pravila (`catalogs.inspection_rules`, "BiH UIO Objedinjen spisak
mart 2015") je zastario i nikad nije bio zvanično objedinjen za entitetske inspekcije
(samo veterinarska je na nivou BiH). Ne postoji noviji zvaničan spisak za zamjenu. Umjesto
toga, dodati **čisto informativni** sloj: za dati tarifni broj pokazati koliko puta se u
STVARNIM prošlim deklaracijama pojavio prilog određene vrste (npr. veterinarsko uvjerenje) —
ovo NIKAD ne zamjenjuje niti suprimira postojeće pravno pravilo, samo dodaje kontekst.
Korisnik sam odlučuje na osnovu oba izvora.

## Izvor podataka

`H:\New folder\NOVA ASIKUDA` (5706 XML fajlova, korisnik će uskoro dodati još) — ASYCUDA
XML deklaracije, `<Item><Attached_documents><Attached_document_code>/<...name>`.

Potvrđeno skeniranjem: kodovi dolaze u DVA sistema (stari troslovni + noviji N-prefiksirani),
korisnik potvrdio mapiranje:

| Stari kod | Novi kod | inspection_type (postojeći ključ u `inspection_service.py`) |
|---|---|---|
| SAN | N852 | `sanitary` (Inspekcija za hranu) |
| VET | N853 | `veterinary` |
| FIT | N851 | `phytosanitary` |
| UVK | N003 | `market_inspection` (Tržna — korisnikova ispravka, NE quality_control) |
| AGL | (nema vidljiv N-kod) | `medicines_agency` |

Nema pouzdanog koda za `quality_control` — ta kategorija ostaje bez istorijskog podatka
(pošteno, ne izmišljati).

## Plan

1. `database/migrate_inspection_document_history.py` — standalone skript (isti obrazac kao
   `migrate_inspection_rules_to_pg.py`): kreira `catalogs.inspection_document_history`
   (tariff_code_norm, inspection_type, document_code, document_name, usage_count, first_seen,
   last_seen), UNIQUE (tariff_code_norm, inspection_type). Clear-and-rebuild pattern (ne
   incremental) — jednostavno i uvijek tačno, arhiva se skenira u par desetina sekundi.
   CLI argument za putanju arhive (default `data/knowledge_base/NOVA ASIKUDA`, override
   preko `--xml-dir`) — NE hardkodovati `H:\...` u kod (lična putanja korisnika).
   Pravi XML parsing (`xml.etree.ElementTree`, isti obrazac kao
   `TariffMappingService.import_from_xml_files`), NE regex.
2. `InspectionService.historical_hint(tariff_code) -> list[dict]` — nova metoda, čita iz
   nove tabele, vraća listu {inspection_type, document_name, usage_count} za tačan (8-cifreni)
   tarifni broj. Prazna lista ako nema podatka — bez fallback nagađanja.
3. UI: u "Inspekcijski pregled naimenovanja" dijalogu dodati jasno vizuelno odvojenu
   napomenu (npr. manji font, siva boja, "Istorijski podatak (informativno)") pored
   postojećeg pravnog pravila — nikad ne mijenja boju/status postojećeg reda.

## Šta NE dirati

- `TariffMappingService.import_from_xml_files` — CRITICAL blast radius (Auto-popuni,
  `.pyd`-only u dist_client, ne može se mirror-ovati bez Nuitka rekompilacije). Nova
  funkcionalnost ide u POTPUNO ODVOJEN skript/modul, ne dodaje se u ovu funkciju iako bi
  dijeljenje jednog prolaza kroz XML bilo efikasnije — sigurnost prioritet nad efikasnošću.
- `catalogs.inspection_rules` — pravna pravila ostaju netaknuta, nova tabela je ZASEBNA.
- `InspectionService.check()` — postojeća logika (prefix matching pravnih pravila) se ne
  mijenja, samo se dodaje NOVA metoda pored nje.

## Napomena o dostupnosti baze

Server nedostupan danas (biće sutra) — kod se piše i testira (XML parsing protiv stvarnih
fajlova na H:, jedinični testovi sa mock DB konekcijom za servisni sloj), ali SAMA migracija
(kreiranje tabele + stvarno popunjavanje) se NE pokreće danas. To ostaje kao eksplicitan
sljedeći korak kad baza bude dostupna.

## Konflikti

Nema poznatih.
