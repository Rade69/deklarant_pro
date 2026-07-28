# Normalizacija tarifnih brojeva nakon učitavanja

## Datum

2026-07-28

## Agent

OpenAI Codex

## Scope

`importers/invoice_line_utils.py`, `services/import_service.py`,
`services/naimenovanja/declaration_assembly.py`, njihove `dist_client` kopije i
ciljani unit testovi.

## Status izvora

- `AGENTS.md`: aktivan i kanonski; interni tarifni broj je 8 cifara.
- `docs/CONTEXT.md`: aktivan; pravilo o nedopunjavanju kratkih kodova ostaje.
- Postojeći testovi koji čuvaju 10-cifrenu ex tarifu: zastarjeli u odnosu na
  kanonski interni format.
- Screenshot korisnika: aktivan dokaz da tok glavne liste propušta 10 cifara u
  Faktura tabelu.

## GitNexus impact

`normalize_tariff_number` ima CRITICAL upstream impact: 67 simbola, 12
direktnih pozivalaca, 5 procesnih tokova i 10 modula. `load_master_list` ima LOW
impact: 23 evidentirana simbola i jedan direktni pozivalac. GitNexus
`detect_changes` je izvršen, ali indeks pokazuje glavni `windows` worktree, pa
je konačni scope dodatno potvrđen stvarnim Git diff-om izdvojenog worktree-a.

## Šta je urađeno

- Zajednički normalizator sada svaki tarifni broj duži od 8 cifara skraćuje na
  prvih 8 cifara.
- Glavna Excel lista normalizuje tarifu prije kreiranja `InvoiceLine`.
- Root i `dist_client` runtime kopije su usklađene.
- Dodati su regresioni primjeri sa korisnikovog screenshota i test sa stvarnim
  privremenim Excel fajlom.

## Zašto je urađeno

Stari normalizator čuvao je 10-cifrene kodove ako posljednje dvije cifre nisu
`00`, a `ProductMasterList` je osmocifrenom kodu namjerno dodavao `00` radi
baznog formata. Posebna putanja „Učitaj glavnu listu“ nije pozivala ulaznu
normalizaciju, pa je desetocifrena vrijednost dospijevala u draft i tabelu.

## Kako je urađeno

Normalizacija je ostala centralizovana u
`importers.invoice_line_utils.normalize_tariff_number`. Assembly poziva isti
normalizator na granici Excel zapis → `InvoiceLine`, tako da prikaz, grupisanje
i XML dalje koriste isti model.

## Šta nije dirano

- PostgreSQL i TARIC lookup format od 10 cifara.
- Tarifni šifrarnici i hijerarhija.
- Grupisanje naimenovanja, Rub.31, mase, porijeklo i povlastice.
- Postojeće korisničke izmjene u četiri generisana UI fajla.
- Nevezani Faktura refaktor plan.

## Verifikacija

- Ciljani testovi: `60 passed`.
- Puna suite: `1365 passed, 72 skipped, 5 xfailed`.
- Regresioni Excel test potvrđuje `8516802090` → `85168020` u draftu.
- Primjeri `8421298090`, `8415900090` i `8413608090` takođe završavaju sa 8
  cifara.
- Pre-commit `py_compile`: prošao.

## Pronađeni problemi

GitNexus indeks je vezan za glavni worktree i ne mapira pouzdano necommitovane
izmjene izdvojenog worktree-a. Semantički impact prije izmjene je bio dostupan,
ali je post-change scope zato dodatno provjeren Git diff-om.

## Konflikti / kontradiktorni izvori

Stari kod i testovi dopuštali su 10-cifrenu ex TARIC vrijednost u
`InvoiceLine`. Kanonsko pravilo projekta i korisnikov zahtjev traže interni
osmocifreni format; oni su tretirani kao važeći izvor. Korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `b211777` | `fix(faktura): normalizuj tarife na osam cifara` |

## Rizici / ograničenja

Gubi se TARIC podjela iz devete i desete cifre na ulazima koji je sadrže. To je
namjerno jer poslovni model i ASYCUDA XML koriste osmocifreni CN kod; puni
10-cifreni oblik ostaje u baznom lookup sloju.

## Potreban follow-up

Nema obaveznog kodnog follow-upa.

## Potrebna korisnička potvrda

Ponovo učitati istu glavnu listu i vizuelno potvrditi da kolona „Tarifni broj“
prikazuje samo prvih 8 cifara.
