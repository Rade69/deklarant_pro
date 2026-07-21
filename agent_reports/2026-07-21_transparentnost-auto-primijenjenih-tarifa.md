# Agent Report — 2026-07-21: Transparentnost auto-primijenjenih tarifa

## Datum
2026-07-21

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + dist_client
- `tests/unit/test_faktura_view_auto_applied_notice.py` (novo)
- `docs/CONTEXT.md` (dopuna §27)

## Status izvora

Direktan nastavak `project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md` i
`agent_reports/2026-07-21_preciznost-tarifnih-prijedloga.md` — korisnik je nakon
testiranja rebuildovanog `.exe`-a postavio konkretno pitanje o Rb.11 stavci
("Korišten 9x" ali "Sigurnost preporuke: slab (62%)" — da li prihvatiti prijedlog).

## GitNexus impact

`FakturaView._run_historical_tariff_validation` — LOW, 1 direktan pozivalac
(`_on_validate_all`), 0 affected_processes.

**Napomena o paralelnom radu**: tokom rada otkriven drugi, necommitovan skup izmjena
(`gui/delegates/validation_delegate.py`, `project_rooms/2026-07-21_faktura-segment-5-validacioni-prikaz.md`)
— drugi agent (izgleda Codex, po ranijim "GUI QSS nacrt" commitovima u 12:19-12:20)
radi paralelno na VIZUELNOM segmentu (monospace font, blaže boje), potpuno odvojenom
scope-u. Njihov project_room fajl eksplicitno navodi da moje tarifne izmjene u
`faktura_view.py` ostaju izvan njihovog commita. Nisam dirao niti stageovao njihove
fajlove.

## Šta je urađeno

Korisnik je ispravno primijetio da "korišten Nx u deklaracijama" ne dokazuje da je
tarifa ispravna — carina radi selektivnu kontrolu, ne pregledava svaku stavku svake
deklaracije, pa "nije odbijeno" ≠ "verifikovano tačno". Ovo je isti obrazac kao već
poznat bug (GREJAC SPIRALA, Plamenik — "jedna ručna greška postaje 'naučen' trajni bug").

Provjerom koda otkriveno: sistem VEĆ ima jači signal od "usage_count u XML-u" —
tabela `catalogs.user_feedback` pamti kad je ČOVJEK eksplicitno kliknuo Prihvati/Odbij
na baš taj par (naziv robe → tarifa) kroz "Provjeri" dijalog. Ali taj signal se
koristio SAMO da (`HistoricalTariffSearchService._feedback_action` → "accept" grana)
**tiho** auto-primijeni promjenu u tabeli — bez ijedne poruke korisniku šta se
promijenilo ili zašto. Stavke sa ranijim "accept" feedbackom NIKAD ne stižu do
`TariffValidationDialog`-a (bajpasuju ga prije `results.append`), pa se izvorno
predložen fix ("prikaži u dijalogu 'ranije potvrđeno'") nije mogao doslovno
implementirati — prilagođen je stvarnoj arhitekturi.

Dodata `FakturaView._notify_auto_applied_tariffs(auto_applied)` — poziva se iz
`_run_historical_tariff_validation` odmah nakon što se `auto_applied` promjene upišu
u tabelu, SAMO u interaktivnom modu (`auto=False`). Prikazuje `_show_scrollable_info_dialog`
sa jasnom porukom: koje stavke (Rb., naziv, nova tarifa) su automatski ažurirane, i
eksplicitno navodi da je razlog ranija RUČNA potvrda (jača evidencija od pukog
korištenja u deklaracijama), uz poziv da se ponovo provjeri. U auto modu (puna
automatizacija) samo se loguje — ne prekida pipeline dijalogom (isto pravilo kao
ostatak Faze C/§7 plana).

## Zašto je urađeno

Bez ove izmjene, jedna ranija ljudska odluka (ispravna ili pogrešna) bi se tiho
ponavljala zauvijek, bez ikad ponovnog pregleda — potpuno isti mehanizam entrenchmenta
kao GREJAC SPIRALA/Plamenik bug, samo kroz drugi kod-put (`user_feedback` umjesto
`product_tariff_mapping` exact-match).

## Kako je urađeno

Minimalna, izolovana izmjena — nova metoda poziva postojeći `_show_scrollable_info_dialog`
(već korišten obrazac u ovom fajlu za slične rezultate), ne mijenja ništa u
`HistoricalTariffSearchService`. `auto_applied` tuple format (`(idx, tarif)`) je ostao
nepromijenjen — naziv robe se dohvata na licu mjesta iz `self.draft.invoice_lines`.

## Šta nije dirano

- `HistoricalTariffSearchService`/`_feedback_action`/`user_feedback` tabela — sama
  logika auto-primjene nije mijenjana, samo dodata vidljivost u GUI sloju.
- Reject-grana (`feedback_action == "reject"`) — ostaje tiho suprimirana (korisnik
  nije izrazio zabrinutost za taj slučaj).
- `gui/delegates/validation_delegate.py` — tuđe, necommitovano, netaknuto.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_auto_applied_notice.py -v → 2 passed (novo)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 830 passed, 58 skipped, 3 failed, 1 error (sve pretpostojeće/nepovezano)
python -m py_compile gui/tabs/faktura_view.py dist_client/... → OK
diff (bez BOM) root/dist_client faktura_view.py → IDENTIČNI
mcp__gitnexus__detect_changes() → risk_level: low, 0 affected_processes
  (širok changed_symbols spisak je posljedica pomjeranja linija u ogromnom fajlu
  (5100+ linija) nakon umetanja ~30 novih linija — nepovezani simboli fizički
  nisu mijenjani, samo pomjereni; potvrđeno git diff-om da je stvaran diff
  ograničen na tačno dva mjesta u FakturaView)
```

## Pronađeni problemi

Nema novih, van onoga što je već dokumentovano u prethodnom izvještaju.

## Konflikti / kontradiktorni izvori

Paralelni necommitovani rad drugog agenta na `validation_delegate.py` — nije u
konfliktu (odvojen fajl/scope), nije diran, dokumentovan gore radi transparentnosti.

## Commitovi

| Hash | Poruka |
|------|--------|
| `302df71` | fix(faktura): obavijesti korisnika kad se tarifa auto-primijeni po ranijoj potvrdi |

## Rizici / ograničenja

- Poruka se prikazuje kao modalni/scrollabilni dijalog svaki put kad postoji
  auto-primijenjena stavka u interaktivnom modu — ako se ovo dešava često na istoj
  fakturi (npr. pri ponovljenim klikovima na "Provjeri"), može postati zamorno.
  Nije optimizovano (npr. "ne prikazuj ponovo za ovu sesiju") — moguć follow-up ako
  se pokaže smetajućim u praksi.
- Reject-grana i dalje ostaje potpuno tiha — ako korisnik želi istu transparentnost
  i za odbijene prijedloge, to je zaseban follow-up.

## Potreban follow-up

- Ručni test na rebuildovanom `.exe`-u: potvrditi da se poruka pojavljuje ispravno
  kad postoji ranije prihvaćen par.
- Razmotriti da li reject-grana treba istu transparentnost.
- Pratiti da li je dijalog za auto-primijenjene stavke prečest/dosadan u praksi.

## Potrebna korisnička potvrda

- Da li je poruka dovoljno jasna i ne suviše nametljiva u praksi.
