# GUI vizuelno unapređenje — dokument i QSS nacrt

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- `docs/design/GUI_VIZUELNO_UNAPREDJENJE.md`
- `styles/gui_visual_refresh_proposal.qss`

## GitNexus impact

Pre-change simbol impact nije primjenjiv jer nisu mijenjane postojeće funkcije,
klase ili metode. `gitnexus_detect_changes(scope="staged")` prijavio je LOW
rizik, 0 promijenjenih simbola i 0 pogođenih procesa za dva nova fajla.

## Šta je urađeno

Napravljen je dokument sa vizuelnom analizom, paletom, preporukama po ekranima,
redoslijedom implementacije, granicama i kriterijima prihvatanja. Napravljen je
i samostalan QSS nacrt koji pokriva glavne tabove, dugmad, forme, tabele,
statusna stanja, skrolbare, Admin, Šifrarnike, Agent i display profile varijante.

## Zašto je urađeno

Postojeći GUI koristi više konkurentnih centralnih i lokalnih stilskih sistema.
Cilj nacrta je dati jednu provjerljivu referencu za ujednačavanje izgleda bez
neposredne promjene produkcionog interfejsa ili poslovnog toka.

## Kako je urađeno

QSS koristi postojeće Qt tipove widgeta, poznate object name selektore i
dinamička svojstva. Paleta je svedena na plavu primarnu akciju, neutralne
sekundarne akcije, crvenu destruktivnu akciju, zelene statuse i ljubičastu AI
podršku. Fajl nije dodat u listu stilova u `MainWindow.load_stylesheet()`.

## Šta nije dirano

- Postojeći QSS fajlovi i njihov redoslijed učitavanja.
- `MainWindow`, View, Controller i Service kod.
- Poslovna logika, signali, modeli, baze i XML tokovi.
- `dist_client` i PyInstaller artefakti.
- Zatečene korisničke izmjene u `AGENTS.md`, `CLAUDE.md` i neversionisani fajlovi.

## Verifikacija

- `git diff --check` — bez grešaka.
- Encoding skeniranje za tipične mojibake sekvence — bez nalaza.
- QSS zagrade — 88 otvorenih i 88 zatvorenih blokova.
- GitNexus staged provjera — LOW, 0 simbola, 0 procesa.
- Potvrđeno da QSS nije naveden u `MainWindow.load_stylesheet()`.

## Pronađeni problemi

GitNexus unstaged provjera je prijavila ranije korisnikove izmjene u
`AGENTS.md` i `CLAUDE.md`, ali ne i nova untracked fajla. Nakon staginga samo
ciljanih fajlova, staged provjera je dala očekivani rezultat bez pogođenih
simbola i procesa.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `892050e` | `docs(gui): dodaj prijedlog vizuelnog unapređenja` |

## Rizici / ograničenja

QSS nije vizuelno testiran kao aktivni završni sloj. Postojeći inline stilovi i
selektori veće specifičnosti mogu nadjačati pojedine dijelove nacrta. Aktiviranje
bez ekran-po-ekran provjere moglo bi promijeniti dimenzije ili kontrast widgeta.

## Potreban follow-up

Na posebnoj grani privremeno uključiti QSS na kraj liste stilova, pokrenuti
aplikaciju na podržanim rezolucijama i prvo usaglasiti Faktura tab kao
referentni ekran. Tek nakon korisničkog odobrenja širiti aktivaciju na ostale
tabove i uklanjati duplirane legacy stilove.

## Potrebna korisnička potvrda

Korisnik treba potvrditi vizuelni pravac iz dokumenta i odobriti zasebnu fazu
aktiviranja QSS-a u aplikaciji.

