# Import workflow faze 2-4 — korekcije

## Cilj

Ispraviti greske u neutralnom import workflow sloju prije nastavka na UI integraciju:
odluke korisnika moraju stvarno filtrirati fakture, invoice key mora koristiti kanonsku
normalizaciju, priprema ne smije mutirati izvorne parser linije, a neuspjeli/dupli fajlovi
moraju sacuvati dovoljno informacija za kasniju primjenu i prikaz.

## Pogodjeno

GitNexus impact za nove simbole `prepare_import` i `invoices_to_apply` vraca `UNKNOWN`
jer indeks ne pronalazi simbole. Posto je u `docs/CONTEXT.md` evidentirano da je indeks
degradiran za nove Python simbole, rizik se rucno tretira kao HIGH: ovo je buduci zajednicki
put za rucni, batch i Agent import.

## Plan

1. Ispraviti modele konflikata/odluka da nose `invoice_key` i vise valutnih konflikata.
2. Ispraviti pripremu: kanonski invoice key, bez mutiranja source linija, bez spajanja
   nepovezanih fajlova samo zato sto imaju isti broj fakture, uz propagaciju warnings/errors.
3. Ispraviti decision servis da postuje `ABORT`, `SKIP_INVOICE`, `DraftOperation.SKIP` i
   per-invoice konfliktne odluke.
4. Dodati regresione testove za kontra-primjere iz revizije.
5. Mirrovati izmjene u `dist_client/services/import_workflow`.

## Sta NE dirati

Ne dirati postojeci `FakturaView`, Agent controller, parser API, `ImportService`, niti
servis primjene drafta koji jos nije uveden. Ovo zatvara samo Faze 2-4 prije Faze 5.

## Konflikti

Pi agent test `test_isti_invoice_broj_grupise` enshrine-uje ponasanje koje je revizijom
oznaceno kao rizicno. Vazeca odluka: `consumed_paths` i parserov `is_combined` su
autoritativni za spajanje; isti broj fakture sam po sebi nije dokaz da treba sabrati
stavke i tezine.
