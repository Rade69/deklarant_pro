<!--
OVAJ FAJL JE ZA AGENTA, NE ZA ČOVJEKA.
METHOD.md objašnjava ZAŠTO metoda postoji (čita čovjek). Ovaj fajl je
korak-po-korak procedura koju agent (Claude Code, Codex, Cursor, bilo koji
CLI agent) IZVRŠAVA da bi popunio AGENTS.md/CLAUDE.md za konkretan projekat.

Kako se pokreće: korisnik kopira cijeli templates/agent-md/ folder u
korijen ciljanog projekta (novog ili postojećeg sa kodom) i kaže agentu
"pročitaj BOOTSTRAP.md i primijeni ga na ovaj projekat".
-->

# BOOTSTRAP — agent-izvršiva procedura za popunu agent-md metode

## Prije nego počneš — dva glavna pravila

1. **Nikad ne izmišljaj poslovna pravila.** Ako kod ne kaže EKSPLICITNO
   zašto nešto radi na određen način (komentar, docstring, commit poruka,
   test koji to provjerava), to polje ostaje `<<< POPUNI: NUŽNA POTVRDA
   — [tvoja najbolja pretpostavka], razlog nesigurnosti: ... >>>` — nikad
   se ne piše kao da je činjenica.
2. **Kopiraj tačne vrijednosti iz koda, ne generičke.** Ako nađeš
   `min_similarity = 0.85` ili sličan konkretan broj/konstantu, upiši
   TU vrijednost sa referencom na fajl/liniju — ne pisati okvirno
   "neki prag sličnosti".

Cilj ovog koraka NIJE da agent zvuči kao da sve zna o projektu. Cilj je da
razdvoji ono što je STVARNO utvrđeno dokazom od onoga što čovjek mora
potvrditi — isti princip kao "Provjeri hipotezu" u formatu zadatka (vidi
`CLAUDE.md`).

---

## Korak 0 — obim

Utvrdi da li je ovo:
- **(a) Prazan/novi projekat** (nema koda ili samo skeleton) → većina
  koraka ispod se preskače, samo popuni ono što je korisnik VEĆ rekao
  (tech stack odluku, jezik) i ostavi ostalo za popunu kako projekat raste.
- **(b) Postojeća kodna baza** bez ove metode do sada → puna procedura
  ispod.
- **(c) Postojeća kodna baza koja VEĆ ima `AGENTS.md`/`CLAUDE.md`** (ne iz
  ovog templejta) → NE prepisivati postojeći fajl bez pitanja. Prikazati
  korisniku predloženi diff/dopunu i tražiti potvrdu prije bilo kakve
  izmjene.

Ako je (c), stani ovdje i pitaj korisnika kako želi da se postojeći fajl i
ovaj template pomire (spoji ručno, zamijeni, ili odustani).

**Prije bilo čega drugog, pokreni `git status --short`.** Ako working
tree nije čist (ima nekomitovanih izmjena koje ti nisi napravio), utvrdi
čije su prije nego što nastaviš — mogu biti WIP drugog agenta koji radi
paralelno u istom working tree-u (vidi `AGENTS.md` "Paralelni agenti").
Nikad ne pokretati široki `git add`/commit preko tuđih nekomitovanih
izmjena kao dio ovog bootstrap-a.

Tokom cijelog skeniranja (Koraci 1-7), isključi iz pretrage/čitanja:

```text
.git/  .worktrees/  node_modules/  .venv/  venv/  dist/  build/
__pycache__/  generated/  backups/
```

<<< POPUNI: dopuniti listom generisanih/vendor foldera specifičnih za
ovaj projekat (npr. `target/` za Rust/Java, `bin/`/`obj/` za .NET) >>>

Ovi folderi su ili tuđi kod (vendor/dependency) ili generisan sadržaj —
skeniranje bez izuzimanja troši vrijeme/kontekst bez koristi i može
dovesti do pogrešnih zaključaka (npr. konvencija iz `node_modules/`
pogrešno pripisana projektu).

---

## Korak 1 — tech stack (dokaz: manifest fajlovi)

Potraži (redom, prvi pogodak određuje primarni stack; može ih biti više
u monorepo situaciji — navesti sve):

```text
package.json, pnpm-lock.yaml, yarn.lock   → Node/JS/TS
pyproject.toml, requirements.txt, setup.py → Python
go.mod                                      → Go
Cargo.toml                                  → Rust
pom.xml, build.gradle                       → Java/Kotlin
*.csproj, *.sln                             → .NET
Gemfile                                     → Ruby
composer.json                               → PHP
```

Iz nađenog manifesta izvuci: jezik + verziju (ako je pinovana), package
manager, glavne dependency-je koje određuju arhitekturu (web framework,
GUI framework, ORM, test framework). Upiši u "Tech stack" tabelu sa
referencom (npr. "iz `pyproject.toml`, linija N").

Ako nema manifest fajla ili je dvosmislen (npr. i `requirements.txt` i
`package.json` u istom repou bez jasne granice) → flag za potvrdu, ne
pogađaj koji je primarni.

---

## Korak 2 — struktura projekta (dokaz: stvarno stablo direktorija)

Napravi listing top-level i drugog nivoa direktorija (isključi
`node_modules/`, `.venv/`, `dist/`, `build/`, `.git/` i slično generisano).
Za svaki direktorij koji izgleda kao arhitektonski sloj (ne utility folder
kao `scripts/` ili `docs/`), **otvori 2-3 reprezentativna fajla** da
potvrdiš ulogu prije nego je upišeš — ne pogađaj po samom imenu foldera
(npr. `core/` može biti bilo šta ovisno o projektu).

Upiši u "Arhitektura" sekciju kao stablo sa kratkim opisom svakog foldera
(1 red po folderu), plus arhitektonski pattern AKO je vidljiv iz stvarnog
koda (npr. "controller pozivi su 1-linijski wrapperi oko servisa" — ovo
piši SAMO ako si to stvarno vidio u 2+ primjera, ne pretpostavi).

---

## Korak 3 — konvencije koda (dokaz: linter/formatter config + sample fajlovi)

Potraži config fajlove: `.eslintrc*`, `.prettierrc*`, `ruff.toml`,
`pyproject.toml [tool.black]/[tool.ruff]`, `.editorconfig`, `rustfmt.toml`,
`.golangci.yml`. Ako postoje, navedi ih kao izvor istine za code style —
ne izmišljati dodatna pravila mimo njih.

Za konvencije koje config fajlovi NE pokrivaju (npr. da li se koriste
docstrings, gustina komentara, jezik komentara, error handling stil),
uzorkuj 5-10 fajlova iz različitih dijelova koda i navedi ono što je
DOSLJEDNO u većini njih. Ako je nekonzistentno (pola fajlova ima
docstrings, pola nema) → napiši to kao zapažanje, ne kao pravilo, i
flag za odluku ("projekat nema dosljednu konvenciju za X — predložiti
korisniku da odluči").

**Provjera specifično za "Stil koda" default (bez komentara + link ka
agent_report umjesto inline objašnjenja, vidi `CLAUDE.md`)**: ako
uzorkovani fajlovi pokazuju DOSLJEDNU, drugačiju postojeću konvenciju
(npr. obavezan JSDoc/Javadoc na svakoj public funkciji, ili opsežni
inline komentari koji su očigledno namjeran standard tima, ne zapušten
kod) — NE prepisuj template default preko toga. Flaguj za odluku
("postojeći kod dosljedno koristi X stil komentarisanja, template
default je Y — koji zadržati?"). Ako je postojeći kod nekonzistentan bez
jasnog standarda, template default (minimalni komentari + link ka
`agent_report` za netrivijalne odluke) ostaje kao predloženo pravilo
ubuduće, bez potrebe za potvrdom.

---

## Korak 4 — testovi (dokaz: test config + CI + postojeći testovi)

Potraži: test folder (`tests/`, `test/`, `__tests__/`, `spec/`), test
framework iz manifest dependency-ja (pytest, jest, vitest, go test,
cargo test...), komandu za pokretanje (u `package.json` scripts,
`Makefile`, `tox.ini`, CI config fajlu poput `.github/workflows/*.yml`).
Pokušaj STVARNO pokrenuti test komandu (read-only, ne mijenjaj ništa) da
potvrdiš da radi prije nego je upišeš kao "Testovi" komandu u template.

---

## Korak 5 — git konvencije (dokaz: `git log`)

Pregledaj zadnjih ~30 commit poruka (`git log --oneline -30`). Utvrdi:
jezik poruka, da li prate `tip(scope): opis` format ili nešto drugo,
da li postoji `Co-Authored-By:` konvencija. Upiši ono što je STVARNO
dosljedno korišteno — ne nameći `AGENTS.md` template-ov default format
ako repo već ima svoj ustaljen stil.

---

## Korak 6 — postojeća agent-infrastruktura (dokaz: fajlovi/folderi)

Provjeri da li već postoje: `docs/CONTEXT.md`-ekvivalent (bilo koji fajl
sa "za AI agente" ili "napomene za razvoj" u nazivu/sadržaju),
`agent_reports/`, `project_rooms/`, code-graph/impact-analiza alat
(GitNexus, Sourcegraph, ctags setup, itd.), pre-commit hookovi. Za svaki
nađeni — referenciraj ga u odgovarajućoj `AGENTS.md`/`CLAUDE.md` sekciji
umjesto da predlažeš da se pravi novi. Za svaki NENAĐEN — ostavi
placeholder kao opcion (ne kreiraj prazan folder/fajl dok stvarno ne
zatreba — vidi METHOD.md "Kako početi").

**Sjeme za `docs/CONTEXT.md`** (samo ako se prvi put kreira): pretraži kod
za komentare koji signaliziraju skrivenu odluku ili zamku — ključne riječi
`HACK`, `WARNING`, `IMPORTANT`, `NOTE:`, `workaround`, `don't`/`ne diraj`,
`zašto`/`why` u komentarima. Za svaki nađen, PRENESI TAČAN TEKST komentara
kao kandidat za prvi zapis u `docs/CONTEXT.md`, sa referencom fajl:linija
— ne parafraziraj i ne dodaji objašnjenje koje komentar sam ne daje. Sve
ovako sakupljeno predstavlja korisniku kao prijedlog PRIJE upisa — komentar
u kodu može biti zastario ili pogrešan, treba ljudska potvrda.

---

## Korak 7 — zabrane (dokaz: PRIJEĐENI istorijski bugovi/revertovani commit-i)

Ako `git log` sadrži commit poruke tipa `fix: revert X jer...` ili
`fix: ukloni Y koji je pravio...`, to su jaki kandidati za "Zabrane
specifične za ovaj projekat" tabelu — pravilo + razlog već postoje u
istoriji, samo ih treba izvući. Ne izmišljaj zabrane koje nemaju ovakav
istorijski trag ili eksplicitan komentar u kodu.

---

## Korak 8 — sažetak za čovjeka (OBAVEZNO prije nego što se bilo šta finalizuje)

Prikaži tabelu sa tri kolone prije nego što predložiš da je `AGENTS.md`/
`CLAUDE.md` gotov:

| Popunjeno sa dokazom | Treba potvrdu (najbolja pretpostavka) | Nije moglo biti utvrđeno |
| --- | --- | --- |
| ... (svako sa fajl/linija referencom) | ... (svako sa razlogom nesigurnosti) | ... (ostaje `<<< POPUNI >>>`) |

Ne nastavljaj na Korak 9 dok korisnik ne pregleda srednju kolonu.

---

## Korak 9 — post-popuna housekeeping

- Kreiraj prazan `agent_reports/` folder (ako ne postoji).
- `project_rooms/` i `docs/context/history.md` split NE kreiraj unaprijed
  — samo ako je Korak 6 već našao materijal za `docs/CONTEXT.md`, kreiraj
  taj jedan fajl (bez history split-a — split dolazi tek kad naraste,
  vidi METHOD.md #2).
- Predloži prvi commit (`docs: bootstrapuj agent-md metodu za <projekat>`),
  ali NE commituj bez eksplicitne potvrde korisnika — ovo je novi fajl u
  tuđem/novom repou, ne rutinska izmjena.

---

## Zabrane za ovaj bootstrap (važe za agenta koji izvršava proceduru)

| Zabrana | Razlog |
| --- | --- |
| Popuniti "Zašto" polje bez eksplicitnog dokaza u kodu/commit istoriji | Izmišljeno objašnjenje je gore od praznog placeholdera — vodi na pogrešnu odluku kasnije |
| Prepisati postojeći `AGENTS.md`/`CLAUDE.md` bez pitanja | Može biti tuđ rad u toku ili namjerna odluka koju bootstrap ne vidi |
| Kreirati `docs/CONTEXT.md`/`project_rooms/`/`agent_reports/` sadržaj "za svaki slučaj" | Isti bloat koji metoda pokušava spriječiti (METHOD.md "Kako početi") |
| Zaokružiti/generalizovati konkretne vrijednosti (thresholds, verzije, limite) | Tačna vrijednost iz koda je provjerljiva, generička nije |
| Preskočiti Korak 8 (sažetak za čovjeka) | Bootstrap bez ljudske provjere je isto što i izmišljanje pravila |
