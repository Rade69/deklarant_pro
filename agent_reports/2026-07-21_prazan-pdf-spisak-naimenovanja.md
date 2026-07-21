## Datum

2026-07-21

## Agent

Codex

## Scope

`exporters/pdf_invoice_exporter.py`, runtime kopija u `dist_client` i ciljani PDF test.

## GitNexus impact

LOW: pet pogođenih simbola za izvorni `_group_by_naimenovanje` i dva za runtime kopiju;
nema pogođenih evidentiranih procesa.

## Šta je urađeno

PDF spisak naimenovanja više ne odbacuje stavke bez dodijeljenog internog ordinala.
Takve stavke se izvoze pod naslovom `STAVKE BEZ NAIMENOVANJA`.

## Zašto je urađeno

Korisnikov PDF je imao jednu stranicu i samo naslov i datum. Analiza stvarnog fajla je
pokazala da izvoz završava uspješno, ali filter `ordinal > 0` uklanja sve redove.

## Kako je urađeno

Grupisanje zadržava postojeće pozitivne ordinale, dok vrijednosti 0 smješta u rezervnu
grupu. Izvoz ne mijenja draft i ne duplira poslovnu logiku formiranja naimenovanja.

## Šta nije dirano

Nisu mijenjani Faktura layout, kreiranje naimenovanja, grupisanje po četiri ključa,
modeli ni drugi PDF pregled po fakturama.

## Verifikacija

Regresioni test generiše pravi PDF i preko `pdfplumber` potvrđuje naslov rezervne grupe i
naziv robe. Rezultat: 13 relevantnih testova prolazi; dva postojeća Linux-font testa su
izuzeta na Windowsu zbog ranije poznate POSIX pretpostavke putanje.

## Pronađeni problemi

Postojeći test otkrivanja fontova koristi `/home/test` i nije prenosiv na Windows; nije
uzrok ove greške i nije mijenjan.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `8082d51` | `fix(faktura): prikaži sve stavke u PDF izvozu` |

## Rizici / ograničenja

Stavke bez ordinala jesu vidljive, ali nisu automatski pridružene postojećem
naimenovanju; to je namjerno kako exporter ne bi preuzeo poslovnu logiku servisa.

## Potreban follow-up

Nije potreban za ovu grešku.

## Potrebna korisnička potvrda

Ponoviti izvoz istog dokumenta i vizuelno potvrditi da tabela sadrži svih 94 stavke.
