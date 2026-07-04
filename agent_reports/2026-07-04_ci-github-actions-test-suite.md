# CI: automatsko pokretanje test suite-a (GitHub Actions)

**Datum:** 2026-07-04
**Grana:** windows
**Scope:** `.github/workflows/tests.yml` (nov fajl)

---

## Šta je urađeno

Dodat GitHub Actions workflow (`.github/workflows/tests.yml`) koji na svaki push i pull request ka `main`/`windows` granama automatski pokreće test suite.

## Zašto

Test suite je jučer (2026-07-03) bio potpuno neupotrebljiv — 18 grešaka pri kolekciji je blokiralo i samo pokretanje pytest-a (vidi [2026-07-03_test-suite-oporavak-i-zaglavlje-bugfix.md](2026-07-03_test-suite-oporavak-i-zaglavlje-bugfix.md)). Nakon oporavka, suite je danas pouzdan (589+ testova, 0 palo). Bez automatskog pokretanja, ovakva regresija (test suite koji se tiho pokvari i niko ne primijeti) mogla bi se ponoviti neopaženo — CI je zaštita da se to ne desi.

## Kako je urađeno

- **Runner: `windows-latest`**, ne `ubuntu-latest`. Aplikacija je isključivo Windows produkcija (PySide6 desktop app za Windows terminale), i današnja sesija je otkrila više pravih bugova koji su specifično Windows-vezani (backslash/forward-slash path nesklad u `consumed_paths`, `cp1252` encoding pucanje na `č`/`Ć` u testovima). Linux runner bi te probleme ili sakrio (drugačiji path separator, UTF-8 default) ili ih drugačije manifestovao — `windows-latest` je vjerniji stvarnom okruženju.
- **Dependency management: `uv`** (`astral-sh/setup-uv` akcija sa keš-om), isto kao dokumentovan lokalni dev workflow (`docs/INSTALACIJA.md`: `uv sync`). `.python-version` (3.13) u repou automatski određuje verziju Python-a koju `uv` instalira — nije potreban zaseban `actions/setup-python` korak.
- **Komanda:** `uv run pytest -m "not integration" -q` — isključuje testove koji zahtijevaju pravi PostgreSQL (marker `integration` već postoji u `pyproject.toml`), isto kao svi ručni test run-ovi tokom ove sesije.

## Verifikacija

Nije moguće lokalno simulirati GitHub Actions runner, ali logika se oslanja na već potvrđeno ponašanje: isti `pytest -m "not integration"` komanda je danas više puta pokrenuta u ovom repou (bez `.env` fajla, tačno kao što će biti u svježem CI checkout-u koji nikad neće imati `.env` — zaštićen `.gitignore`-om) i dala **589 prošlo, 0 palo, 3 preskočena**. Preskočeni testovi (Gemini opciona zavisnost + 2 fajla bez privatnih fixture faktura) će ostati preskočeni i u CI-ju na isti način (`skipif`/`importorskip`), ne blokiraju workflow.

`gitnexus_detect_changes` (unstaged): risk LOW, 0 affected processes (očekivano — `.yml` fajl nije indeksiran kao izvorni kod).

## Šta nije dirano

- Nema build/packaging automatizacije (PyInstaller/Nuitka exe build) — samo test suite. Packaging CI bi bio zaseban, veći zadatak.
- Nema badge-a u README-u niti branch protection pravila na GitHub-u (zahtijeva podešavanje na GitHub strani, van scope-a ovog fajla).

## Commitovi

| Hash | Poruka |
|------|--------|
| `cbaa1e3` | ci(github-actions): dodaj automatsko pokretanje test suite-a |

## Rizici / ograničenja

Prvi stvarni run na GitHub-u nije mogao biti posmatran iz ove sesije (nema pristup GitHub Actions logovima odavde) — vrijedi da korisnik provjeri Actions tab na GitHub-u nakon push-a da potvrdi da workflow prolazi zeleno, i da po potrebi javi ako nešto specifično za GitHub-ov Windows runner (npr. Qt offscreen platforma) ne radi isto kao lokalno.

## Potreban follow-up

- Korisnik da provjeri prvi CI run na GitHub-u (Actions tab) nakon push-a.
- Razmisliti o `branch protection` pravilu (zahtijevaj zeleni CI prije merge-a) kad bude više saradnika ili PR-ova.
