## Cilj
Uskladiti Assembly/master-list ručni uvoz (`FakturaView._finish_import_legacy_path`,
`using_assembly=True` grana) sa Agent modom: tražiti EUR.1/PE2/PE3 potvrdu po
fakturi PRIJE nego što se povlastica upiše u draft, umjesto tihog preuzimanja
iz Excel "preferential" kolone master liste. Korisnička odluka (2026-08-02):
"mora raditi identično kao agentski mod, nema druge opcije."

## Dodatak 2026-08-02 (isti dan, korisnik prijavio nastavak problema)
Korisnik je nakon prve popravke prijavio: status "0% (0 faktura)" se
ispravno puni pri POJEDINAČNOM uvozu (popravljeno gore), ali NE i pri
GRUPNOM (batch) uvozu kad je master lista već učitana. Istraga potvrdila
DRUGI, teži, pre-postojeći bug u `_process_batch_records_legacy`: grana
`else: self.draft.invoice_lines.clear(); self.draft.invoice_lines.extend(all_items)`
je (a) potpuno zaobilazila `assembly.add_invoice()` (status ostajao
zamrznut) I (b) **brisala prethodno matchovane stavke** iz ranijih
pojedinačnih uvoza prije nego doda nove — potencijalni gubitak podataka,
ne samo kozmetički bug. Popravljeno u istom commit-u kao ovaj plan:
`_process_batch_records_legacy` sad zove `add_invoice()` PO FAKTURI u
petlji (isto grupisanje kao `final_records`), sa istim EUR.1/PE2/PE3
tokom po fakturi kao pojedinačni uvoz. Stari "jedan dijalog za cijeli
batch" (`_should_show_eur1_dialog`/`_show_eur1_dialog`) ostaje SAMO za
slučaj kad master lista NIJE bila već učitana prije batcha (tj. kad
`load_master_list_from_lines` gradi listu iz samog batcha — taj put
nije mijenjan). 3 nova karakterizaciona testa
(`tests/unit/test_batch_assembly_matching_wiring.py`), uklj. eksplicitan
test da prethodno matchovane stavke PREŽIVE naredni grupni uvoz.

## Dodatak 2 — 2026-08-02 (treći nalaz, korisnik prijavio: "nema kvačice")
Nakon druge popravke, korisnik je prijavio: status "100% (4 faktura)"
sada radi (druga popravka potvrđena), ALI stavke sa potvrđenom
povlasticom (npr. "EUPR"/"EFTA1R" u koloni Povlastica) i dalje nemaju ✅
kvačicu u koloni Zemlja. Provjera `PreferenceValidator` indikatora
("⚠ 1 bez EUR1" od 88 stavki) pokazala da 87/88 stavki VEĆ ima
`eur1_number`/`has_origin_statement` — tj. povlastica JESTE potvrđena.

Uzrok: prva popravka (Dodatak 1 gore) u `update_from_invoice()` je
kopirala `povlastica`/`eur1_number`/`has_origin_statement`/
`is_authorized_exporter` kad postoji potvrđen dokaz, ali **NE i
`country_confidence`/`country_source`/`country_conflict_details`** —
polja koja `_apply_grouped_origin_data()` (`services/import_workflow/
apply_service.py:217-223`) ISPRAVNO postavlja na `items` nakon EUR.1
dijaloga, ali koja su se gubila pri spajanju na master-liste objekat.
`ValidationService.country_confidence_style()` (Faza 5 pravilo) ima
ranu provjeru `if not item.country_confidence: return None` — bez tog
polja NIKAD ne stiže do provjere povlastice, pa se boja/kvačica
uopšte ne primjenjuje, bez obzira što je povlastica stvarno potvrđena.

Popravljeno: `update_from_invoice()` sad kopira i ta tri polja kad je
`has_confirmed_origin` True. 3 nova karakterizaciona testa u istom
fajlu (`TestCountryConfidencePropagacija`), uklj. end-to-end test koji
poziva pravi `ValidationService.country_confidence_style()` i
provjerava da vrati `icon="✅"`.

## Pogođeno
- `FakturaView._finish_import_legacy_path` — GitNexus LOW, 1 pozivalac (`_on_import_finished`)
- `AssemblyItem.update_from_invoice` (`services/naimenovanja/declaration_assembly.py`) —
  GitNexus 0 upstream (dinamički poziv iz `add_invoice()`, poznato ograničenje
  indeksa — potvrđeno ručnim čitanjem koda, ima 1 stvaran pozivalac)
- Reuse (bez izmjene): `determine_origin_dialog()`, `_collect_manual_origin_response()`,
  `_apply_origin_decision()` (iz `services/import_workflow/`) — ISTA infrastruktura
  koju već koriste Agent mod i migrirani pojedinačni ručni uvoz

## Fact (zašto obična dodavanje dijaloga ne bi bilo dovoljno)
`AssemblyItem.update_from_invoice()` ima pravilo "master lista pobjeđuje ako
već ima povlasticu" (`if invoice_line.povlastica and not self.invoice_line.povlastica`).
Pošto Excel master lista već ima popunjenu "preferential" kolonu za skoro sve
stavke, EUR.1 dijalog bez izmjene ovog pravila ne bi imao efekta — potvrda bi
se prikazala ali nikad ne bi ušla u draft.

## Plan
1. U `_finish_import_legacy_path`, `using_assembly` grani, PRIJE
   `self.assembly.add_invoice(items, invoice_name)`: pozvati
   `determine_origin_dialog(items, has_origin_statement, is_authorized_exporter)`,
   i ako `!= NONE`, sagraditi `PreparedInvoice` (pravi dataclass, ne adapter-hack)
   sa `internal_key`/`invoice_number`/`invoice_lines=items`, pozvati
   `self._collect_manual_origin_response(prepared, dialog_type)`, pa primijeniti
   odgovor na `items` preko postojeće `_apply_origin_decision()` funkcije
   (`services/import_workflow/apply_service.py`) — ista logika koju Agent
   mod koristi, ne duplirana.
2. U `AssemblyItem.update_from_invoice()`: ako stavka sa fakture ima POTVRĐEN
   dokaz porijekla (`eur1_number` ili `has_origin_statement`), ta vrijednost
   UVIJEK nadjačava master-liste "predlog" bez dokaza. Bez dokaza, staro
   ponašanje (master lista pobjeđuje ako već ima povlasticu) ostaje
   nepromijenjeno — ovo NE mijenja ponašanje za slučajeve gdje dijalog
   uopšte ne treba (`dialog_type == NONE`).

## Šta NE dirati
- `determine_origin_dialog`, `_collect_manual_origin_response`,
  `_apply_origin_decision` — samo se pozivaju, logika unutra se ne mijenja.
- Sam Excel format master liste / `load_master_list()` — i dalje popunjava
  početni predlog, samo više nije nenadmašiv.
- Non-Assembly grana (`else:`) — već ima svoj EUR.1 mehanizam (`_show_eur1_dialog`),
  van scope-a ove izmjene.
- ~~`_process_batch_records_legacy` van scope-a~~ — ZASTARJELO, vidi
  "Dodatak 2026-08-02" iznad: grupni Assembly uvoz JE popravljen istog
  dana (drugi nalaz), ista logika (`determine_origin_dialog` +
  `_collect_manual_origin_response` + `_apply_origin_decision` po
  fakturi u petlji) primijenjena i tamo.

## Plan verifikacije
- Karakterizacioni testovi za `update_from_invoice()` PRIJE izmjene: potvrditi
  staro ponašanje (master lista pobjeđuje bez dokaza) ostaje isto, NOVO
  ponašanje (dokaz uvijek pobjeđuje) je tačno definisano.
- Karakterizacioni test za novi `_finish_import_legacy_path` dio (dialog
  poziv + primjena) — mockovan `_collect_manual_origin_response` (GUI
  dijalog se ne može testirati headless), provjeriti da se `_apply_origin_decision`
  poziva sa ispravnim argumentima.
- Ponovno pokretanje `tests/integration/test_assembly_master_list_import_e2e.py`
  (5 postojećih testova) — MORAJU i dalje proći bez izmjene (te fakture
  nemaju origin izjavu u PDF-u pa dialog_type vjerovatno NONE za njih,
  provjeriti pretpostavku).
- Pun test suite + `gitnexus_detect_changes`.

## Rollback / oporavak
Svaka izmjena zaseban commit — revert `update_from_invoice` izmjene vraća
staro (rizičnije, ali poznato) ponašanje; revert `_finish_import_legacy_path`
izmjene vraća "bez dijaloga uopšte" (trenutno stanje).

## Nezavisni checker
Preporučen prije nego korisnik počne stvarno raditi deklaracije kroz ovaj
put — carinski-osjetljiva izmjena (povlastica u ASYCUDA deklaraciji).

**Urađeno 2026-08-02** (general-purpose subagent, read-only pregled +
pokušaj obaranja hipoteze). Rezultat:

**Potvrđeno ispravno**: sve tri popravke rade ono što tvrde, pun skup
polja iz `_apply_grouped_origin_data()` je pokrivet (nema dodatnog
propuštenog polja), 17 relevantnih testova + širi skup od 106 povezanih
testova prolazi bez regresije. Za **unmatched** stavke (nova, bez match-a
u master listi) `add_invoice()` ne prolazi kroz `update_from_invoice()`
uopšte — merge-prioritet pravilo nije ni relevantno za taj slučaj.

**Novi nalaz #1 (nije popravljen, dijeljena infrastruktura van scope-a)**:
Otkazivanje/Reject EUR.1/PE2/PE3 dijaloga ne čisti per-line
`has_origin_statement` koje neki PARSERI (potvrđeno:
`importers/proton_system_importer.py:205,222`) postavljaju DIREKTNO iz
teksta fakture, prije nego dijalog uopšte otvori. Kad korisnik otkaže,
`_apply_origin_decision()` se rano vraća bez izmjene — flag ostaje
`True` sa parsera, pa `has_confirmed_origin` u `update_from_invoice()`
i dalje evaluira `True` i upisuje `has_origin_statement=True` na
master-liste stavku BEZ obzira na otkazivanje. Vizuelna kvačica se NE
pojavljuje (jer `country_confidence` ostaje prazan — ta provjera
"spašava" situaciju), ali sam flag se ipak upisuje u draft. **Ovo NIJE
uvedeno sa tri popravke** — isto se dešava u Agent modu i migriranom
pojedinačnom uvozu jer dijele istu `_apply_origin_decision()` (svjesno
neizmijenjenu, "Šta NE dirati" iznad). Dijeljena infrastruktura, van
scope-a Assembly-specifičnog rada — zahtijeva korisničku odluku i
zaseban zadatak ako se popravlja (dira 3 uvoz-toka odjednom).

**Novi nalaz #2 (POPRAVLJEN)**: `is_authorized_exporter` se kopirao SAMO
kad `True` (`if invoice_line.is_authorized_exporter:`), za razliku od
`has_origin_statement` koje se kopira bezuslovno. Posljedica: PE3→PE2
korekcija na istoj stavci (True→False) se ne bi primijenila. Popravljeno
— bezuslovno kopiranje, isto kao `has_origin_statement`. 2 nova testa
(`TestIsAuthorizedExporterSimetricnoKopiranje`).

**Novi nalaz #3 (POPRAVLJEN)**: netačan komentar u
`test_batch_assembly_matching_wiring.py` (tvrdio "dialog_type==NONE" dok
fixture-i stvarno daju `EUR1` preko `determine_origin_dialog()`
"has_pending" grane) — test je i dalje ispravno testirao wiring (mock
sprječava pravi dijalog), samo je dokumentacija bila netačna. Ispravljen
komentar, bez izmjene test logike.

## Odbačene opcije
- Opcija: Excel kolona ostaje autoritativna, dijalog samo evidentira dokaz
  bez izmjene `povlastica` polja.
- Zašto je razmatrana: manje rizično, ne dira `update_from_invoice`.
- Zašto je odbačena: korisnik je eksplicitno tražio "identično kao agentski
  mod" — Agent mod uopšte ne čita Excel "preferential" kolonu, povlastica
  mu dolazi isključivo iz dijaloga. Zadržavanje Excel-a kao autoritativnog
  bi i dalje bilo drugačije ponašanje od Agent moda.
