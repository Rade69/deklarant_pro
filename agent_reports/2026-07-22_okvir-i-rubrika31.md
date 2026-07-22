## Datum

2026-07-22

## Agent

Codex

## Scope

Spoljašnje poravnanje kartice Naimenovanja i vizuelno uređenje Rub.31.

## GitNexus impact

LOW. Konstruktor prikaza nema evidentirane uzvodne zavisnosti ni pogođene poslovne procese.

## Šta je urađeno

Cijeli sadržaj kartice dobio je simetričnu marginu od 1 px lijevo i desno. Rub.31 dobio je diskretniju podlogu, istaknutu oznaku rubrike, jasniji naslov i konzistentne okvire/fokus za tri ručna ulazna polja.

## Zašto je urađeno

Na bočnim snimcima okvir nije djelovao jednako vidljivo. Rub.31 je sljedeći planirani segment i ranije se vizuelno stapao s ostatkom velikog zelenog formulara.

## Kako je urađeno

Spoljašnja margina promijenjena je u glavnom layoutu `NaimenovanjaView`, a Rub.31 kroz selektore `group_31`, `lbl_rubrika31`, `lbl_r31_oznake` i tri konkretna QLineEdit polja. Izvorna i `dist_client` kopija su usklađene.

## Šta nije dirano

Nisu mijenjani generisani `.ui` fajlovi, apsolutna geometrija, podaci, signali, poslovna logika ni prethodno podešena dugmad.

## Verifikacija

Offscreen provjera sa stvarnim QSS redoslijedom potvrdila je margine `(1, 1)` i vidljivost svih ciljnih kontrola. Prošlo je 9 ciljnih testova, `py_compile` i `git diff --check`.

## Pronađeni problemi

GitNexus `detect_changes` prikazuje nepovezane izmjene drugog radnog stabla; staged diff potvrđuje ciljani scope.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `64e28db` | `style(naimenovanja): poravnaj okvir i izdvoji rubriku 31` |

## Rizici / ograničenja

Promjena Rub.31 je namjerno diskretna; konačan kontrast treba potvrditi u stvarnoj aplikaciji.

## Potreban follow-up

Nakon potvrde nastaviti na blok Rub.32–39 kao sljedeći odvojeni segment.

## Potrebna korisnička potvrda

Provjeriti bočne ivice cijele kartice i čitljivost Rub.31 bez promjene rasporeda polja.
