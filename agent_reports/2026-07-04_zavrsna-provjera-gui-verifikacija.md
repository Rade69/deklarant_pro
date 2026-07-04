# Verifikacija "Završna provjera" kroz stvarni GUI kod put

**Datum:** 2026-07-04
**Grana:** windows
**Scope:** verifikacija (bez izmjene produkcijskog koda), nov test fajl `tests/unit/test_zavrsna_provjera_kompletnost_tab.py`

---

## Status izvora

Tri ranija izvještaja (2026-06-15) implementirala su i djelimično verifikovala "Završna provjera" dugme:
- `2026-06-15_compliance-check-broken-import-fix.md` — popravljen mrtav import
- `2026-06-15_zavrsna-provjera-dugme.md` — implementirano dugme + tab "Kompletnost"
- `2026-06-15_compliance-check-bez-atb-fakture.md` — fix da provjera nastavlja bez ATB stavki

Sva tri izričito ostavljaju otvorenim **"Potrebna korisnička potvrda: pokrenuti aplikaciju i kliknuti Završna provjera na pravom GUI-ju"** — ovo nikad nije urađeno. Ovaj izvještaj to zatvara, u granicama alata dostupnih agentu (nema mišem-klik/screenshot automatizacije za pravi Windows prozor).

## Šta je urađeno

Umjesto ponovnog testiranja na nivou servisa (kao ranija tri izvještaja), napravljena je skripta koja vozi **stvarni kod put** dugmeta od nule:

1. `ZaglavljeController._get_naimenovanja_data()` i `_get_invoice_lines(draft)` — **nikad ranije testirano** (raniji izvještaji su ručno konstruisali `naimenovanja_data`/`invoice_lines` dict-ove, zaobilazeći ove dvije metode).
2. `validate_declaration_full(...)` — sa podacima iz koraka 1 (ne ručno napisanim).
3. `EnhancedValidationDialog(report, config, None)` — stvarna konstrukcija dijaloga (bez `.exec()` da ne blokira, isti pristup kao raniji izvještaj), sa čitanjem **stvarnog renderovanog teksta** unutar taba "Kompletnost" (QLabel/QTextEdit sadržaj), ne samo brojanjem stavki na `report` objektu.

Scenario: "XML uvoz direktno u Naimenovanja, bez ATB Faktura" (draft sa praznim `invoice_lines`, jednim naimenovanjem bez tarife/šifre postupka, bez priloženih dokumenata) — isti scenario koji je treći izvještaj identifikovao kao slučaj koji stari kod nije ispravno obrađivao.

## Rezultat

```
Broj tabova: 3
  Tab 0: 📋 Zaglavlje
  Tab 1: 📦 Naimenovanja
  Tab 2: 📄 Kompletnost

Sadržaj 'Kompletnost' taba (stvaran renderovan tekst):
  ❌ <b>Kompletnost</b> - naim_no_tariff — 1 naimenovanja bez tarifnog broja.
  ⚠️ <b>Kompletnost</b> - naim_no_procedure — 1 naimenovanja bez šifre postupka (Rub.37).
  ⚠️ <b>Kompletnost</b> - no_docs — Nije priložen nijedan dokument (Rubrika 44)...
  ℹ️ <b>Kompletnost</b> - no_invoice_lines — Nema uvezenih stavki fakture (ATB)...

Dugmad u dijalogu: ['❌ Zatvori', '💾 Sačuvaj izvještaj']  (BEZ export dugmeta — potvrđeno)
```

Sve se poklapa sa očekivanjima iz sva tri ranija izvještaja — dugme, tabovi, sadržaj i odsustvo export dugmeta (poslovno pravilo korisnika: "Nema nikakve automatizacije, tu odluku uvijek donosi deklarant") rade ispravno kroz **stvarni** kod put, ne samo kroz ručno sastavljene test podatke.

Usput potvrđeno da AI chat put (`_compliance_check` u `chat_intent_handler.py`) i dalje ispravno importuje `ComplianceCheckService` iz `services.agent.validation.declaration_validator_service` — fix iz prvog izvještaja nije regresirao.

## Šta NIJE verifikovano (ograničenje alata)

- **Vizuelni izgled na pravom, vidljivom Windows prozoru** (boje, layout, čitljivost) — agent nema alat za miš-klik/screenshot automatizaciju stvarnog GUI prozora. Sva verifikacija je urađena offscreen (`QT_QPA_PLATFORM=offscreen`), čitanjem stvarnog teksta widget-a, ne piksela.
- Interaktivni AI chat scenario ("provjeri sve" komanda kroz punu chat sesiju) — provjeren samo import/dostupnost klase, ne puna chat interakcija.

## Kako je urađeno

Iskorišten postojeći obrazac iz `tests/unit/test_zaglavlje_controller_import_docs.py` — `ZaglavljeController.__new__(ZaglavljeController)` bez punog `View`-a, jer `_get_naimenovanja_data`/`_get_invoice_lines` rade isključivo sa `draft` objektom (`self._get_draft_fn()`), bez zavisnosti od `self.view`.

## Verifikacija

- Pun test suite nakon dodavanja regresionog testa: **594 prošlo, 0 palo, 3 preskočena**.
- `gitnexus_detect_changes` (unstaged): risk LOW, 0 affected processes (dodat samo test fajl).

## Šta nije dirano

Nema izmjena produkcijskog koda — čista verifikacija + dodavanje testa. `ComplianceCheckService`, `EnhancedValidationDialog`, `ZaglavljeController` logika — netaknuti.

## Commitovi

| Hash | Poruka |
|------|--------|
| (test) | test(zaglavlje): regresioni test za Zavrsnu provjeru kroz stvarni GUI kod put |

## Rizici / ograničenja

Nema novih rizika (samo test dodat). Preostaje da korisnik jednom klikne dugme u stvarnoj, vidljivoj aplikaciji da potvrdi vizuelni izgled (boje/layout) — ovo je van dometa agentovih alata u ovoj sesiji.

## Potreban follow-up

- Korisnik da jednom pokrene aplikaciju i vizuelno potvrdi izgled taba "Kompletnost" i dugmeta "Završna provjera" na stvarnom ekranu.
- AI chat "provjeri sve" komanda — puna interaktivna verifikacija ostaje otvorena (niska prioritet, import je potvrđen ispravan).
