# Faktura — vizuelno unapređenje po segmentima

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- `gui/tabs/faktura_view.py`
- `docs/design/GUI_VIZUELNO_UNAPREDJENJE.md`
- `styles/gui_visual_refresh_proposal.qss`
- `project_rooms/2026-07-21_faktura-segment-5-validacioni-prikaz.md`

## Status izvora

- Snimci svih glavnih tabova koje je dostavio korisnik — aktivan vizuelni izvor.
- `docs/CONTEXT.md` i `AGENTS.md` — aktivni projektni standardi.
- Postojeći source kod Faktura taba — aktivan izvor za layout i ponašanje.
- `dist_client` — može zaostajati za source kodom i nije tretiran kao izvor za izmjene.

## GitNexus impact

Izmjene su provjeravane prije svakog segmenta. Većina stilskih i layout izmjena
imala je LOW ili MEDIUM rizik. Segment validacionog prikaza za
`_validate_and_color_row` imao je HIGH impact: 28 povezanih simbola, 8 direktnih
zavisnosti i 0 pogođenih izvršnih procesa, pa je prije izmjene napravljen poseban
scope dokument. Završna QSS korekcija imala je LOW rizik i 0 pogođenih procesa.

GitNexus povremeno mapira isti simbol i na `dist_client` kopiju, iako Git diff
potvrđuje da je mijenjan samo source fajl.

## Šta je urađeno

- Napisan je prijedlog unapređenja cijelog GUI-ja i pripremljen neaktivni QSS prototip.
- Tabela Faktura taba dobila je neutralnije zaglavlje, blažu mrežu i jasniju selekciju.
- Toolbar zone su ujednačene neutralnom pozadinom i diskretnim razdvajanjem.
- Dugmad su dobila jasniju hijerarhiju: standardne, primarne, AI i destruktivne akcije.
- Bruto, neto i dugme `Provjeri` grupisani su u jednu kompaktnu cjelinu.
- Validaciona stanja koriste blaže boje, a tarifni broj monospace font.
- Statusna traka ima manje separatora i kraći sažetak zemalja porijekla.
- QSS selektor toolbar pozadine ograničen je na kontejner da ne prekriva boje dugmadi.

## Zašto je urađeno

Faktura tab je funkcionalno bogat, ali je veliki broj jakih boja i jednako naglašenih
akcija otežavao vizuelno skeniranje. Izmjene smanjuju vizuelni šum i jasnije odvajaju
primarne, pomoćne i opasne akcije, bez rekonstrukcije dugo građenog rasporeda.

## Kako je urađeno

Rad je podijeljen u šest malih commitovanih segmenata. Zadržani su postojeći widgeti,
signali, redoslijed sekcija i poslovna logika. Promijenjene su lokalne QSS vrijednosti,
jedan mali kontejner za mase, prikaz validacionih boja i tekst statusnog sažetka.

## Šta nije dirano

- Poslovna logika, uvoz, parseri, baza i modeli.
- Redoslijed glavnih toolbar sekcija i struktura tabele.
- Validaciona pravila i kriterijumi ispravnosti.
- `dist_client` kopija i postojeći PyInstaller build.
- Ostali tabovi aplikacije.
- Paralelne lokalne izmjene drugih autora.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py` — prolazi.
- `python -m pytest tests/unit/test_faktura_manual_import_sort.py tests/unit/test_historical_tariff_validation.py tests/unit/test_faktura_view_auto_applied_notice.py -q` — 33 passed.
- Offscreen provjere potvrdile su validacione role, kompaktnu grupu masa i render taba.
- Završni GitNexus detect changes — LOW rizik, 0 pogođenih procesa za QSS korekciju.
- Pre-commit `py_compile` provjera prošla je za svaki Python commit.

## Pronađeni problemi

Generički `QWidget` selektor toolbar kontejnera nasljeđivao se na dugmad i prekrivao
njihove nove boje. Selektor je sužen na `QWidget#toolbarSection`. Nije pronađeno
pomjeranje osnovnog layouta niti funkcionalna regresija u ciljanim testovima.

## Konflikti / kontradiktorni izvori

Nije bilo kontradiktornih poslovnih izvora. Tokom rada su postojale paralelne izmjene
u istom source fajlu; sačuvane su i nisu uključene u stilske commitove.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `892050e` | `docs(gui): dodaj prijedlog vizuelnog unapređenja` |
| `dfe4fa2` | `style(faktura): ublaži boju validnih redova` |
| `fb6bd70` | `style(faktura): neutralizuj izgled tabele` |
| `e7339ef` | `style(faktura): ujednači toolbar zone` |
| `f2d9ffa` | `style(faktura): pojasni hijerarhiju akcija` |
| `247b71a` | `style(faktura): grupiši kontrolne mase` |
| `244c794` | `style(faktura): unaprijedi validacioni prikaz` |
| `735400a` | `style(faktura): sažmi statusnu traku` |
| `2d4f5e6` | `fix(faktura): ograniči pozadinu toolbar sekcija` |

## Rizici / ograničenja

Promjene su trenutno vidljive samo pri pokretanju aplikacije iz source-a. Frozen
aplikacija neće ih prikazati bez novog builda. Vizuelna procjena u stvarnom Windows
okruženju i na korisnikovoj rezoluciji ostaje važna jer offscreen Qt render ne daje
potpuno identičan prikaz fontova i sistemskih stilova.

## Potreban follow-up

Nakon korisničke potvrde može se selektivno prenijeti source u `dist_client` i napraviti
novi build. Ostali tabovi mogu se uređivati istim segmentnim pristupom.

## Potrebna korisnička potvrda

Pokrenuti aplikaciju iz `dist_client` virtualnog okruženja nad source `run.py` i potvrditi
da su dugmad jasno obojena, panel masa poravnat i tabela dovoljno kontrastna.
