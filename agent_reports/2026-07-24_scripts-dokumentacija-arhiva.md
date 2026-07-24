# Scripts dokumentacija — arhiviranje tehnickih zapisa

## Datum

2026-07-24

## Agent

Codex

## Scope

- `scripts/*.md` tehnicki zapisi iz 2026-04-26
- `docs/archive/2026-04-26/`
- `# DOC:` i dokumentacione reference u root i `dist_client` Python fajlovima
- CSV backup fajlovi u `scripts/` samo provjereni, nisu mijenjani

## Status izvora

Koriscen je `agent_reports/2026-07-23_samostalna-istraga-tehnicki-dug.md`.
Nalaz je djelimicno aktivan: sest Markdown fajlova je zaista bilo u pogresnom
folderu, ali backup CSV fajlovi nisu praceni u gitu i ignorisani su pravilom
`*.csv`.

## GitNexus impact

Pre-change simbolski impact nije pokretan jer nije mijenjana funkcija, klasa,
metoda ni runtime logika. Promjena je dokumentacioni rename i azuriranje linkova.

`gitnexus_detect_changes(scope=staged)` je nakon staginga vratio `critical`
zato sto su `# DOC:` komentari unutar indeksiranih simbola mapirani kao
`touched` (`ProcessingWorker.run`, `_find_master_frigo_mapping_xlsx`,
`_INVOICE_PATTERNS`). Rucni diff je potvrdio da je u tim fajlovima promijenjena
samo putanja dokumentacionog linka, bez izmjene tijela funkcija ili podataka.

## Sta je uradjeno

- Premjesteno sest Markdown zapisa iz `scripts/` u `docs/archive/2026-04-26/`.
- Azurirane aktivne reference u root i `dist_client` fajlovima.
- Azurirani raniji agent reporti koji su navodili stare putanje.
- U `master_frigo_agent_import_2026-04-26.md` dodata kratka napomena o arhivskoj
  lokaciji jer taj dokument i dalje ima aktivne `# DOC:` linkove iz koda.

## Zasto je uradjeno

`scripts/` treba da ostane folder za izvrsne alate i setup skripte. Dated
Markdown zapisi su korisni kao istorijski kontekst, ali nisu skripte i smetaju
preglednosti foldera.

## Kako je uradjeno

Fajlovi su premjesteni eksplicitnim `Move-Item` putanjama u
`docs/archive/2026-04-26/`, zatim su reference azurirane kroz root i
`dist_client` kopiju. Nije radjen bulk find/replace po svim fajlovima bez
provjere; prije izmjene su provjerene reference kroz `rg`.

## Sta nije dirano

- CSV backup fajlovi u `scripts/` nisu brisani: ignorisani su pravilom `*.csv`,
  nisu praceni u gitu, i raniji agent reporti ih navode kao lokalne backup-e.
- `AGENTS.md` i `CLAUDE.md` dirty stanje nije dirano jer je postojalo prije ovog
  paketa i vezano je za GitNexus generisane brojace.
- Nije mijenjana runtime logika, parseri, UI ponasanje, SQL ili test logika.

## Verifikacija

- `rg` provjera: nema preostalih referenci na stare `scripts/*.md` putanje.
- `Test-Path`: svih sest novih `docs/archive/2026-04-26/*.md` fajlova postoji.
- Ciljani DOC guard: svi promijenjeni `# DOC:` linkovi su `OK`.
- `python -m py_compile` za sve Python fajlove sa promijenjenim referencama:
  uspjesno.
- `git diff --cached --check`: bez whitespace problema.
- Pre-commit hook: `py_compile` OK.

Puni `scripts/doc_link_checker.sh .` nije zavrsio ni za 120s u ovom Windows
radnom stablu; razlog je prakticna sporost punog skeniranja, uz prisutne velike
runtime/worktree foldere i lokalni `nul` fajl. Zbog toga je uradjena ciljana
ekvivalentna DOC provjera za linkove ovog paketa.

## Pronadjeni problemi

- Pi nalaz je pominjao osam backup CSV fajlova, a trenutno postoji sedam.
- CSV backup fajlovi su ignorisani i nisu kandidati za git commit bez posebne
  odluke korisnika.
- GitNexus je prijavio `critical` za komentar-only promjenu jer ne razlikuje
  dokumentacioni komentar od izmjene logike simbola.

## Konflikti / kontradiktorni izvori

Nema funkcionalnog konflikta. Raniji nalaz "premjestiti u agent_reports ili docs"
tretiran je kao otvorena opcija; izabrano je `docs/archive/2026-04-26/` jer kod
ima aktivne dokumentacione linkove na dio tih zapisa.

## Commitovi

| Hash | Poruka |
|---|---|
| `1391447` | `docs(scripts): arhiviraj stare tehnicke zapise` |

## Rizici / ogranicenja

Rizik runtime regresije je nizak jer nema izmjene izvrsne logike. Preostali rizik
je samo dokumentacioni: ako neki vanjski alat ocekuje stare `scripts/*.md` putanje,
treba ga usmjeriti na `docs/archive/2026-04-26/`.

## Potreban follow-up

- Odvojeno odluciti sta raditi sa ignorisanim lokalnim CSV backup fajlovima u
  `scripts/`: ostaviti lokalno, premjestiti u lokalni backup folder, ili obrisati.

## Potrebna korisnicka potvrda

Ako zelis da se lokalni CSV backup fajlovi uklone sa diska, potrebna je eksplicitna
potvrda jer nisu praceni u gitu i brisanje ne bi bilo oporavljivo kroz commit.
