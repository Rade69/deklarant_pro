# AGENTS.md — <<< POPUNI: naziv projekta >>> projektni standardi

> **TEMPLATE.** Univerzalni osnov izveden iz `CLAUDE.md`/`AGENTS.md`
> projekta `deklarant_pro`. Kopirati u korijen novog projekta kao
> `AGENTS.md` i popuniti sekcije obilježene `<<< POPUNI: ... >>>`.
>
> Ovaj fajl čitaju SVI agenti koji rade na projektu (Qwen Code, GitHub
> Copilot, Cursor, drugi CLI agenti...). `CLAUDE.md` (isti template folder)
> je dopuna SAMO za Claude Code (memory protokol, detaljnija procedura).
> Ako projekat koristi samo Claude Code, sadržaj ovog fajla se može spojiti
> u `CLAUDE.md` i ovaj fajl izostaviti.

---

## Kontekst projekta — pročitaj prije kodiranja (opcionalno)

<<< POPUNI/UKLONI: ako projekat ima centralni "zajednička memorija za sve
agente" fajl (npr. `docs/CONTEXT.md`) sa ne-trivijalnim odlukama, zabranjenim
paternima i poznatim bugovima koji nisu vidljivi iz koda — referencirati ga
ovdje kao OBAVEZNO štivo prije kodiranja. Ako ne postoji, ukloniti sekciju
(ili je kreirati kad prvi takav slučaj nastane). >>>

**Kad ovaj fajl naraste** (orijentaciono: >500 linija ili >1-2 sedmice
aktivnog dodavanja), podijeliti ga na dva:

```text
docs/CONTEXT.md          ← SAMO evergreen, cross-cutting pravila. Malo,
                            čita se u cijelosti svaki put.
docs/context/history.md  ← dated, append-only log pojedinačnih odluka/
                            bugova/faza. NE čita se u cijelosti — pretražuje
                            se (grep/Grep) po temi ili datumu kad zatreba.
```

Ovo je isti princip kao token budget ispod primijenjen na dokumentaciju:
razdvoji "šta agent MORA znati unaprijed" od "šta agent MOŽE pronaći kad
zatreba". Bez podjele, fajl koji je nekad bio koristan postaje reused input
koji se ponavlja u svaku sesiju bez potrebe.

---

## Token budget i context disciplina

Agent ne prenosi cijeli prethodni razgovor u novi zadatak — prenosi
prihvaćen artefakt (`project_room` fajl, `agent_report`, ili konkretan
plan). Veliki fajlovi (stotine+ linija) se prvo pretraže (grep) po
relevantnom pojmu; cijeli fajl se čita samo kad zadatak to stvarno
zahtijeva. Isto važi za alate: ne povezivati širok skup alata "za svaki
slučaj" — samo one koje zadatak stvarno koristi.

Izuzetak (ne štedjeti kontekst ovdje): HIGH/CRITICAL odluke, sigurnosni
rizik, ili kad agent ne može pouzdano razumjeti zadatak bez šire slike —
tačnost ima prednost nad štednjom tokena.

---

## Paralelni agenti — izolacija working tree-a (ako više agenata radi istovremeno)

<<< POPUNI/UKLONI: relevantno samo ako više agenata (različiti CLI-jevi,
ili više paralelnih instanci istog) mogu raditi na istom repozitorijumu u
isto vrijeme. Ako agent A ostavi nekomitovane izmjene u working tree-u dok
agent B (npr. automatizovan pipeline koji radi `git add -A` na kraju svoje
faze) commituje, B će nesvjesno pokupiti A-ove izmjene u svoj commit —
sadržaj se ne gubi, ali autorstvo/commit poruka postanu netačni i teško je
razdvojiti šta je čije. Rješenje: svaki dugotrajan/automatizovan agent
pipeline radi u zasebnom `git worktree` (npr. `.worktrees/<naziv-toka>/`),
ne direktno na glavnom working tree-u koji dijele interaktivne sesije. >>>

---

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš
uraditi. Čekaj potvrdu korisnika prije implementacije ako zadatak nije
jednoznačan.

---

## Jezik

- Svi odgovori korisniku: <<< POPUNI: jezik + pismo (mora biti isto kao u
  CLAUDE.md "JEZIK I PISMO" sekciji) >>>
- Komentari u kodu: <<< POPUNI: jezik (npr. "engleski, prati stil koji fajl
  već koristi") >>>
- <<< POPUNI: eksplicitne zabrane ako postoje (npr. "nikad ćirilica — nigdje,
  ni u komentarima ni u stringovima koji se prikazuju") >>>
- Commit poruke: <<< POPUNI: jezik, format `tip(scope): opis` >>>

---

## Tech stack

| Sloj | Tehnologija |
| --- | --- |
| <<< GUI/Frontend >>> | <<< POPUNI >>> |
| <<< Baza >>> | <<< POPUNI >>> |
| <<< Jezik/runtime >>> | <<< POPUNI: verzija, package manager >>> |
| <<< Testovi >>> | <<< POPUNI: framework, folder >>> |
| <<< Ostalo (parseri, queue, ...) >>> | <<< POPUNI >>> |

---

## Arhitektura

```text
<<< POPUNI: stablo direktorija sa kratkim opisom svake bitne fascikle, npr.

ime_projekta/
├── core/                 # domenski modeli
├── gui/ ili api/         # ulazna tačka (UI ili HTTP)
├── services/             # business logika
├── database/             # pristup podacima
└── tests/
>>>
```

**<<< POPUNI: arhitektonski pattern, npr. "services/ koristi slobodne
funkcije koje primaju ctrl kao prvi argument, servisna klasa ih omotava kao
public API. Controller metode su tanki 1-liner pozivi servisa." >>>**

---

## Ključne konvencije

### Kod

- **Nema novih komentara** osim za neočigledne workarounds ili skrivene
  invarijante
- **Nema docstrings** na metodama koje slijede jasne naming konvencije
- <<< POPUNI: projekat-specifična pravila, npr. fuzzy matching threshold,
  zabrana f-string u SQL-u, obavezna polja u rezultatima servisa >>>

### <<< POPUNI: modul/sloj 1, npr. "Parseri / importeri" >>>

- <<< POPUNI: pravila specifična za ovaj modul >>>

### <<< POPUNI: modul/sloj 2, npr. "API endpoints" ili "XML/export template" >>>

- <<< POPUNI: pravila specifična za ovaj modul (npr. "polje X se NE
  prepisuje iz historijskih podataka — mijenja se godišnje, mijenjati samo
  whitelist Y") >>>

---

## Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
| --- | --- |
| <<< POPUNI: npr. "Direktni import iz X u Y" >>> | <<< razlog, npr. "kružni import" >>> |
| <<< POPUNI: npr. "Hardkodovati IP/URL u kodu" >>> | <<< razlog, npr. "mora biti u config" >>> |
| <<< POPUNI: npr. "Dodavati UI logiku u servisne klase" >>> | <<< razlog, npr. "narušava razdvajanje slojeva" >>> |
| <<< POPUNI >>> | <<< POPUNI >>> |

---

## Handoff visokog rizika (HIGH/CRITICAL impact)

Kada impact-analiza (npr. `gitnexus_impact()`, ili procjena po kriterijumu
definisanom u `CLAUDE.md` ako alat ne postoji) vrati `HIGH` ili `CRITICAL`
rizik za simbol koji mijenjaš, prijavi korisniku rizik u ovom formatu PRIJE
izmjene (ne nakon):

> "Impact za `<simbol>` je `<risk>`: zavise od njega `<broj>` simbola/procesa
> (`<koji>`). Promjena je mala/velika po obimu ali `<visoka/niska>` po
> sistemskoj važnosti jer `<razlog>`. Scope ostaje ograničen na: `<šta NE
> diraš>`. Obavezni izlaz: `<šta MORA postojati — npr. ciljane izmjene + test
> pokrivenost>`."

Za svaku planiranu izmjenu odredi i navedi:

| Polje | Pitanje na koje odgovara |
| --- | --- |
| **Tip promjene** | bugfix / behavior adjustment / mapping correction / safety patch / refactor? |
| **Prihvatljiv ishod (scope lock)** | šta MORA ostati identično (npr. "validacija ostaje ista osim novog izvora dokaza", "GUI ne mijenja ponašanje osim prikaza") |
| **Nivo dozvole** | draft change only / no auto-merge / mandatory review / test gate required |

Ovo dopunjuje pravilo "upozori korisnika ako impact analiza vrati HIGH ili
CRITICAL" (vidi opcionu sekciju "Code Intelligence" u `CLAUDE.md`) — daje
konkretan format umjesto generičkog upozorenja i tjera agenta da prije
izmjene eksplicitno zapiše granice zadatka.

---

## Format outputa

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: (ako PARCIJALNO/BLOKIRANO)
PITANJA: (ako postoje)
```

---

## Provjera prije predaje

- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] <<< POPUNI: projekat-specifične provjere, npr. "Nisam koristio string
  interpolaciju u SQL-u" >>>
- [ ] Testovi prolaze: `<<< POPUNI: komanda, npr. "python -m pytest tests/ -q" >>>`
- [ ] Output format je popunjen (STATUS, IZMIJENJENI FAJLOVI, itd.)

---

## DOC Guard (opcionalno)

<<< POPUNI/UKLONI: vidi istu sekciju u CLAUDE.md template-u — ako se koristi,
opisati ovdje kratko (BROKEN/STALE reakcija + komanda za ručnu provjeru), ili
samo referencirati CLAUDE.md da se ne duplira. >>>

---

## Code Intelligence (opcionalno — npr. GitNexus)

<<< POPUNI/UKLONI: ako projekat koristi GitNexus ili sličan alat, ovdje ide
auto-generisana sekcija (statistike, Always-Do/Never-Do, resursi/skill
fajlovi) — identična onoj u `CLAUDE.md`. Ako se koristi u oba fajla, provjeriti
da li ih alat sinhronizuje automatski (kao gitnexus marker komentari
`<!-- gitnexus:start -->`/`<!-- gitnexus:end -->`) ili treba ručno održavati
oba mjesta. Ako projekat ne koristi takav alat, ukloniti sekciju. >>>
