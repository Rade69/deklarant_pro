# Tab dugmad — zaokruženi uglovi na svim stranama

## Datum

2026-06-14

## Agent

Claude Sonnet 4.6 (Claude Code)

## Scope

- `styles/main_tabs.qss` + `dist_client/styles/main_tabs.qss`
  (`QTabBar::tab`)

## GitNexus impact

QSS fajlovi nisu indeksirani kao kod-simboli (nema poziva/funkcija) —
`gitnexus_impact` nije primjenjiv. `gitnexus_detect_changes(scope="unstaged")`
PRIJE commita: `risk_level: "low"`, `affected_count: 0`,
`affected_processes: []`. Promjena `main_tabs.qss` se ne pojavljuje u
listi promijenjenih simbola (samo nepovezane `AGENTS.md`/`CLAUDE.md`
izmjene).

## Šta je urađeno

Korisnik je na istom screenshotu trake tabova (iz
`2026-06-14_tabovi-donji-rub-izlaz-dugme.md`) primijetio da tab dugmad
(Faktura, Naimenovanja, Zaglavlje, Šifrarnici, Admin, Agent) imaju
zaokružene SAMO gornje uglove, i pitao za mišljenje o tome da izgled bude
konzistentan na svim uglovima.

Ponuđene su dvije opcije (zaokruži sve uglove na svim tabovima uklj.
aktivni — uz prihvatanje gap-a prema panelu; ili samo na neaktivnim
tabovima). Korisnik je izabrao **opciju 1**.

`styles/main_tabs.qss` i `dist_client/styles/main_tabs.qss`
(`QTabBar::tab`): `border-top-left-radius: 8px; border-top-right-radius:
8px;` → `border-radius: 8px;` (sve 4 strane). Pravilo `:selected` nije
mijenjano — automatski nasljeđuje novi `border-radius` iz base pravila.

## Zašto je urađeno

Korisnikov eksplicitan estetski zahtjev nakon diskusije o tradeoff-u:
zaokruživanje donjih uglova kod AKTIVNOG taba stvara mali vizuelni razmak
("notch") gdje se zakrivljen ugao odvaja od ravnog gornjeg ruba panela
(koji od `e5ca8bc`/`d84af78` nema `border-top`, pa je pozadina iza tog
razmaka jednobojna — nema oštrog presjeka). Korisnik je svjesno prihvatio
ovaj mali gap u korist potpune konzistentnosti svih tab dugmadi.

## Kako je urađeno

Jednolinijska izmjena u oba `main_tabs.qss` fajla — zamjena dvije
top-only `border-*-radius` deklaracije jednom `border-radius: 8px;`
shorthand deklaracijom koja pokriva sve 4 strane. Komentar iznad pravila
ažuriran da opisuje novi "floating tab" izgled.

## Šta nije dirano

- `QTabWidget::pane` — nepromijenjeno (border-top: none i radius 0/0 na
  vrhu ostaju iz `e5ca8bc`).
- `QTabBar::tab:selected` `border-bottom: 2px solid #0078d4` — ostaje
  (redundantno sa base border-om, ali bezopasno, minimalan diff —
  konzistentno sa odlukom iz drugog kruga `d84af78`).
- `QTabBar::tab:hover:!selected` — nepromijenjeno.
- Pozicija/boja "Izlaz" dugmeta, Faktura toolbar razmak — nepovezane
  ranije izmjene iz iste sesije, netaknute.

## Verifikacija

- Offscreen render (privremeni `_tmp_diag6.py` / `_tmp_crop6_*.png`,
  obrisani nakon provjere) sa pravim kombinovanim QSS-om (11 fajlova),
  `displayProfile="compact"`, dva stanja (Faktura selektovan / Zaglavlje
  selektovan):
  - Svi tabovi (aktivni i neaktivni) imaju zaokružene uglove na sve 4
    strane.
  - Aktivni tab ima mali, čist gap prema panelu na donjim uglovima — kako
    je i očekivano, bez vizuelnih artefakata (oštrih ivica, preklapanja).

## Pronađeni problemi

Nema novih — vidi poznati offscreen font-fallback artefakt za "Š" u
`2026-06-14_tabovi-donji-rub-izlaz-dugme.md` (nepovezano).

## Commitovi

| Hash      | Poruka                                                             |
|-----------|--------------------------------------------------------------------|
| `b8bd97f` | `fix(gui): zaokruzi sve uglove TAB dugmadi za konzistentan izgled` |

## Rizici / ograničenja

- Čisto kozmetička QSS promjena, nema funkcionalnog rizika.

## Potreban follow-up

- Nema — odluka je donesena uz korisnikovu eksplicitnu potvrdu tradeoff-a.

## Potrebna korisnička potvrda

- Pokrenuti aplikaciju i vizuelno potvrditi da su uglovi svih tab dugmadi
  (uklj. aktivni tab) zaokruženi i da gap kod aktivnog taba prema panelu
  izgleda prihvatljivo na stvarnom ekranu.
