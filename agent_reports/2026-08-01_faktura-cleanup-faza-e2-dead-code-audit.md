## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py` — read-only audit
- `gui/tabs/faktura_tab.py` — read-only audit
- `gui/tabs/agent/services/import_pipeline_service.py` — read-only potvrda stanja poslije E1
- `tests/unit/test_faktura_controller.py` — read-only audit test pozivalaca
- `tests/unit/test_puna_auto_pipeline.py` — read-only audit E1 stanja
- `dist_client/tests/unit/test_puna_auto_pipeline.py` — read-only audit pariteta testova
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije audita.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e1-agent-private-fallback.md` — aktivan; E2 se nadovezuje na uklanjanje Agent private fallback-a.
- `agent_reports/2026-08-01_faktura-cleanup-stabilizacija-poslije-d3.md` — aktivan; stabilizacioni dokaz prije E faze.

## GitNexus impact

`gitnexus-impact-analysis` skill je korišćen za audit pristup. U trenutnom tool setu nije bio izložen `impact`, pa su korišćeni:

- `gitnexus_context` za `FakturaView._on_validate_all`
- `gitnexus_context` za `FakturaView._on_calculate_masses`
- `gitnexus_context` za `FakturaView._on_auto_fill`
- `gitnexus_context` za `FakturaView._on_create_naimenovanja`
- `rg` inventar pozivalaca za root/dist/test fajlove

Zaključak: nema kandidata za nekontrolisano brisanje. Dva trivial wrappera imaju LOW rizik za kasniji E3, dok su validacija, kreiranje naimenovanja i legacy import i dalje aktivni implementation path.

## Reprodukcija prije izmjene

Ovo nije bugfix nego audit. Reprodukcija nije primjenjiva; dokaz su pozivaoci i GitNexus context.

## Šta je urađeno

- Inventarisani private Faktura View kandidati za cleanup.
- Razdvojeni kandidati u tri grupe: E3 kandidat, ne brisati, kasnije uz dodatnu migraciju.
- Potvrđeno da Agent pipeline poslije E1 više nema private fallback pozive.
- Pronađen test-paritet dug u `dist_client/tests/unit/test_puna_auto_pipeline.py`.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

Faza E je završna cleanup faza, ali brisanje private metoda bez stvarnog inventara može pokvariti ručni toolbar, javne adaptere, PDF export ili import fallback. E2 sprečava "brisanje na osjećaj" i daje sigurnu listu za E3.

## Kako je urađeno

Korišćeni su GitNexus context i `rg` nad root, `dist_client` i testovima. Nije mijenjan produkcioni kod.

## Šta nije dirano

- Nije brisana nijedna metoda.
- Nije mijenjan Agent pipeline.
- Nije mijenjan FakturaTab.
- Nije mijenjan FakturaView.
- Nisu ažurirani `dist_client` testovi; nalaz je samo dokumentovan.
- Nisu dirane tuđe WIP izmjene u working tree-u.

## Verifikacija

- `rg` inventar private Faktura metoda i pozivalaca.
- GitNexus context za četiri glavna private kandidata.
- `git status --short --branch` prije rada: potvrđeni tuđi WIP fajlovi, bez naših produkcionih izmjena.

## Nezavisna provjera

Nije rađena posebna checker sesija jer E2 nije mijenjala produkcioni kod. Za E3 brisanje čak i trivial wrappera preporučujem staged diff review prije commita.

## Pronađeni problemi

| Kandidat | Nalaz | Odluka |
| --- | --- | --- |
| `FakturaView._on_calculate_masses` | Trivial wrapper preko `calculate_masses`; GitNexus vidi samo test pozivaoce. | E3 kandidat za brisanje uz test update. |
| `FakturaView._on_auto_fill` | Trivial wrapper preko `auto_fill`; GitNexus vidi samo test pozivaoce. | E3 kandidat za brisanje uz test update. |
| `FakturaView._on_validate_all` | Core implementacija javnog `validate()`; selekcijski testovi je direktno karakterizuju. | Ne brisati sada. Moguće kasnije preimenovati u internu metodu bez `_on_` obrasca. |
| `FakturaView._on_create_naimenovanja` | Pozivaju ga `create_naimenovanja()`, `_on_export_pdf` i characterization test. | Ne brisati sada. |
| `FakturaView._on_import_finished_legacy` | `_on_import_finished` delegira na njega kad unified import uslovi nisu ispunjeni. | Ne brisati sada. |
| `FakturaTab.validate(auto=True)` | Još zove `self.view._on_validate_all(auto=True)` umjesto `self.view.validate(auto=True)`. | E3/E4 kandidat za prebacivanje na javni adapter prije bilo kakvog preimenovanja validacije. |
| `dist_client/tests/unit/test_puna_auto_pipeline.py` | Još očekuje private fallback pozive iz starog ponašanja. | Test-paritet dug za kasnije; ne dira se u E2. |

## Odbačene opcije

- Odbačeno: odmah brisati sve `_on_*` metode. Razlog: više njih su aktivni implementation path, ne mrtav kod.
- Odbačeno: u E2 popravljati `dist_client` testove. Razlog: E2 je audit faza; produkcioni paritet je već pokriven, a korisnik je ranije naznačio da je odluka oko `dist_client` konačne produkcije posebna tema.

## Konflikti / kontradiktorni izvori

Nema kontradikcija u produkcionom kodu. Postoji paritetni raskorak između root i `dist_client` testova poslije E1; tretiran je kao dokumentovan dug, ne runtime gap.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 9f9687e | `docs(faktura): dokumentuj cleanup faza e2 audit` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; ažuriran je append-only na kraju.
- `faktura_view.py` nije čitan cijeli; korišćeni su ciljano grep i kratki isječci.
- `faktura_tab.py` pročitan u relevantnom dijelu adaptera/signala.

## Rizici / ograničenja

Audit je statički i testno orijentisan; ne zamjenjuje ručni GUI E2E. Zaključak "E3 kandidat" ne znači "brisati bez testova", nego "nema vidljivog produkcionog pozivaoca sada".

## Potreban follow-up

Predloženi E3:

1. Ukloniti samo trivial wrapper metode `FakturaView._on_calculate_masses` i `FakturaView._on_auto_fill`.
2. Ažurirati root testove koji ih direktno karakterizuju.
3. Odvojeno odlučiti da li ažurirati `dist_client/tests` ili ih ostaviti van trenutne produkcione test kapije.

Kasnije, ne u E3:

- prebaciti `FakturaTab.validate(auto=True)` sa `self.view._on_validate_all(auto=True)` na `self.view.validate(auto=True)`;
- tek onda razmotriti preimenovanje `_on_validate_all` u neutralnije interno ime;
- `_on_create_naimenovanja` i `_on_import_finished_legacy` ostaviti dok imaju stvarne pozivaoce.

## Potrebna korisnička potvrda

Prije agresivnijeg brisanja korisnik treba potvrditi da prihvata uski E3 scope: samo dva trivial wrappera, bez diranja validacije, kreiranja naimenovanja i import legacy puta.
