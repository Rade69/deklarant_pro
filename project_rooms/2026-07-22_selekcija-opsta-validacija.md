# Selekcijsko skopiranje opšte validacije (_on_validate_all)

## Cilj

Dodati selekcijsko skopiranje sažetka/brojača u `_on_validate_all` (dugme "Provjeri"),
konzistentno sa `_run_historical_tariff_validation` (već ima selekciju) i `_on_auto_fill`
(već ima selekciju). Trenutno "Provjeri" scopira SAMO istorijsku tarifnu provjeru — opšta
validacija (greške/upozorenja/brojevi) uvijek prijavljuje stanje SVIH stavki, čak i kad je
korisnik selektovao konkretne redove.

## Pogođeno

- `_validation_issue_counts` — HIGH (27 impactedCount, transitivno kroz `_update_status_bar`
  pozvan sa ~15 mjesta). Izmjena: dodaje se OPCIONI `row_indexes: list[int] | None = None`
  parametar sa default vrijednošću koja ZADRŽAVA identično ponašanje za SVE postojeće
  pozivaoce (svi pozivaju bez argumenata) — funkcionalno nulti rizik za postojeći kod.
- `_on_validate_all` — LOW (potpis nepromijenjen, samo interna logika).

## Plan

1. `_validation_issue_counts(self, row_indexes=None)` — ako je `row_indexes` zadan, iterira
   SAMO te redove; inače (default) identično kao prije.
2. `_on_validate_all`: dodati isti selekcijski obrazac kao `_run_historical_tariff_validation`
   (selection.selectedRows() kad `not auto`). Loop za `_validate_and_color_row` i dalje boji
   SVE vidljive redove (jeftino, korisno da tabela uvijek izgleda ažurno) — ali brojevi u
   sažetku (`error_count`/`warning_count`/`valid_count`/`total_count`) i poruka se računaju
   SAMO za selektovane redove kad selekcija postoji (ručno preko `validation_cache.get(row)`
   po indeksu, ne globalni `get_error_count()`).
3. Poruka mora eksplicitno navesti da je sažetak scoped ("N selektovanih stavki") da ne
   zbuni korisnika zašto brojevi ne odgovaraju ukupnom broju stavki na fakturi.

## Šta NE dirati

- `ValidationCache` klasa sama (`services/faktura/validation_cache.py`) — koristi se
  postojeći `.get(row)` API, ne dodaje se nova metoda.
- Bojenje redova (`_validate_and_color_row`) — ostaje na SVIM redovima, ne samo selektovanim
  (vizuelna ažurnost tabele nije razlog za brigu, boji se uvijek sve).
- `_run_historical_tariff_validation` — već ima svoju selekcijsku logiku, ne dirati.
- Svi OSTALI pozivaoci `_validation_issue_counts()` (`_update_status_bar` itd.) — pozivaju
  BEZ argumenata, ostaju netaknuti.

## Konflikti

Nema poznatih. Nema paralelnog rada drugog agenta na ovim tačnim linijama (Codexov merge je
već integrisan, ne dira validaciju/brojače).
