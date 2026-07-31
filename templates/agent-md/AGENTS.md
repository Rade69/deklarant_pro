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

**Bez obzira na worktree izolaciju**, u dijeljenom working tree-u (bilo koji
agent u istoj interaktivnoj sesiji) nikad ne koristiti širok staging
(`git add -A`/`git add .`) — uvijek navesti tačne fajlove koje je TAJ
zadatak izmijenio. Prije svakog `git add`, provjeriti `git status` i
potvrditi da je lista fajlova očekivana; ako ima nepoznatih izmjena, prvo
utvrditi čije su prije nastavka.

---

## Reprodukcija i provjera prije rada (verify before brief)

**Bugfix**: pravi bug se ne popravlja dok nije reprodukovan, osim kad je
jasno dokumentovano zašto reprodukcija nije moguća. Prihvatljivi dokazi:
failing test, minimalna reprodukcijska skripta, konkretan ulaz (fajl,
zahtjev, upit) koji izaziva problem, log sa preciznim podacima i greškom,
screenshot/video stvarnog ponašanja, precizno opisan ručni postupak, ili
stanje baze + upit koji izaziva problem. Ako reprodukcija nije moguća,
zapisati: šta je pokušano, zašto nije reprodukovan, na kojoj pretpostavci
se zasniva izmjena, koji dodatni rizik zbog toga ostaje. Ne mijenjati kod
samo zato što implementacija izgleda sumnjivo — "izgleda sumnjivo" nije
isto što i "dokazano je uzrok problema".

**Feature/enhancement**: prije nego se prihvati kao zadatak, potvrditi da
funkcionalnost već ne postoji (grep/pretraga), i da postoji stvarna
korisnička potreba (ne samo pretpostavka da bi bilo korisno).

**Eksterni/tuđi predlog koda** (patch, PR, kod od drugog agenta bez
nezavisne provjere): prije usvajanja — checkout, pokrenuti testove,
pregledati diff. Tek onda odluka da li se prihvata.

---

## PROBE — kad postoji stvarna nepoznanica

Za zadatke koji zahtijevaju istraživanje, ne implementaciju: nepoznata
biblioteka/API, nejasne performanse, neprovjeren format dokumenta,
nepoznato ponašanje GUI/OS/hardvera, dilema između arhitektura. `PROBE`
NE proizvodi produkcionu funkcionalnost — cilj mu je da odgovori na JEDNO
konkretno pitanje.

Rad na probe-u ide na throwaway granu/worktree (`probe/<pitanje>`) —
NIKAD se ne mergea u glavnu granu. Ako se pokaže vrijednim, prototip se
ili baci i implementira pravilno, ili se zadrži samo dokazani dio iza
novog interfejsa — nikad se ne "očvršćava" na licu mjesta u produkcioni
kod.

Obavezan izlaz (u `agent_report` ili kratkom fajlu vezanom za probe):

```markdown
# Pitanje
# Pretpostavka
# Način provjere
# Rezultat
# Dokaz (test, screenshot, benchmark, primjer izlaza, log, mali prototip)
# Ograničenja rezultata
# Preporuka
# Odluka koju sada možemo donijeti
```

---

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš
uraditi. Čekaj potvrdu korisnika prije implementacije ako zadatak nije
jednoznačan.

**Facts vs Decisions**: agent ne pita korisnika ono što može sam
provjeriti u kodu/repou (to je "fact", ne "decision"). Agent ne smije
sam odlučiti ono što je poslovna/UX/arhitektonska odluka samo zato što
je usput otkrio relevantnu tehničku činjenicu. Kad je pitanje stvarno
za korisnika, format:

```markdown
## Fact found
<<< tehnička činjenica koju si utvrdio (sa referencom) >>>

## Decision required
<<< konkretno pitanje koje samo korisnik može odlučiti >>>

## Recommendation
<<< tvoj predloženi odgovor i zašto >>>

## Consequence
<<< šta se dešava ako se ide suprotnim putem >>>
```

**Confirmation gate za veće/nejasne zadatke** (ne za svaku sitnicu):
prije implementacije, prikazati kratak "Shared Understanding Check" —
cilj, ključne odluke, otvorena pitanja, pretpostavke, predloženi sljedeći
korak — i sačekati potvrdu. Za mali, jednoznačan zadatak dovoljna je
gornja rečenica "šta sam razumio", bez posebnog gate-a.

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
- **Ne miješati refactor i funkcionalnu izmjenu u istom zadatku/commit-u**
  — teško je dokazati šta je promijenilo ponašanje kad su izmiješani.
  Sitno čišćenje nastalo u istom koraku (očigledna duplikacija, ime
  varijable, formatiranje) je OK; veći refactor (pomjeranje granice
  modula, novi apstraktni sloj, uklanjanje starog "smell-a") ide u
  poseban zadatak, čak i ako ga review otkrije usput
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

## Definition of Done po tipu promjene

Promjena nije završena samo zato što se aplikacija pokrenula ili je jedan
test prošao. Obavezan dokaz zavisi od TIPA promjene — popuniti kategorije
koje odgovaraju ovom projektu (obrisati/dodati po potrebi):

<<< POPUNI: primjeri kategorija — zamijeniti/dopuniti stvarnim tipovima
promjena u ovom projektu:

- **GUI/frontend** — screenshot prije/poslije, provjera ciljanog
  ponašanja (fokus, tastaturne prečice, skrol, realan korisnički tok);
  offscreen render NIJE dovoljan dokaz za nešto što zavisi od stvarnog
  prikaza (monitor, skaliranje, fontovi)
- **Parseri/import** — realni ili anonimizovani fixture fajlovi,
  očekivani strukturisan rezultat, edge case-ovi (nedostajuća polja,
  prazni/skriveni redovi, različit encoding/format), dokaz da stari
  izvori/formati nisu pokvareni ponovnim testom
- **Generisani dokumenti (XML/PDF/Excel/Word...)** — golden fajlovi,
  semantičko poređenje ključnih polja (ne slijepo binarno poređenje),
  schema validacija gdje postoji, otvaranje/provjera da rezultat nije
  korumpiran
- **Baza i migracije** — test na disposable bazi, backup prije
  produkcijske migracije, transakcija gdje je moguća, provjera broja
  redova prije/poslije, idempotentnost, NIKAD prvi put testirati na
  produkcionim podacima
- **Performanse** — mjerenje PRIJE, identifikovano usko grlo, ciljana
  izmjena, isto mjerenje POSLIJE, provjera funkcionalne jednakosti (brže
  ALI i dalje tačno)
- **Sigurnost/osjetljivi podaci** — agent nema pristup originalnim
  osjetljivim dokumentima/podacima mimo allowlist-ovanih polja,
  osjetljivi podaci ne završavaju u promptu/logovima/agent_report-u >>>

**Hijerarhija dokaza** (od najjačeg prema najslabijem — koristiti
najjači koji je razumno dostupan):

```text
1. deterministički test
2. integration test
3. reproducibilan benchmark
4. build/package rezultat
5. golden file (semantičko poređenje)
6. screenshot ili video
7. ručna QA kontrolna lista
8. agentovo objašnjenje ("radi jer sam tako napisao")
```

Agentova tvrdnja da nešto radi je NAJSLABIJI mogući dokaz — prihvatljiva
samo kad ništa jače nije razumno dostupno, i tada eksplicitno navesti
zašto.

---

## Podjela odgovornosti

| Ko | Šta |
| --- | --- |
| **Agent radi samostalno** | pretraga koda, pronalaženje pozivalaca, sažimanje postojećeg ponašanja, priprema failing testa, mala lokalna izmjena, pokretanje testova, `agent_report` |
| **Agent samo predlaže** (čovjek odlučuje) | arhitektonska promjena, promjena domenskog modela/centralne poslovne logike, bazna migracija, nova sigurnosna politika, širi refactor, promjena javnog interfejsa |
| **Nezavisan checker potvrđuje** (vidi "Nezavisna provjera" ispod) | da diff odgovara scope-u, da testovi provjeravaju pravi problem, da nisu promijenjena sporedna ponašanja, da nema očigledne regresije |
| **Čovjek odlučuje** | da li poslovna logika ima smisla, da li je UX prihvatljiv, da li se prihvata HIGH/CRITICAL rizik, da li se pušta migracija/mijenja produkcijsko stanje |

---

## Nezavisna provjera (checker)

Nezavisan pregled (drugi agent, drugi model, ili čovjek — bilo ko OSIM
onoga ko je pisao izmjenu) je obavezan ili snažno preporučen kada
promjena: ima HIGH/CRITICAL impact; dira bazu/migracije; dira centralnu
poslovnu logiku ili sigurnost; mijenja generisani finansijski/pravni/
carinski dokument; nije bila pouzdano reprodukovana; ima kontradiktorne
izvore; ima veliku cijenu greške.

Checker nezavisno: pregleda diff, potvrdi scope, provjeri pozivaoce i
zavisnosti, pokrene relevantne testove, POKUŠA OBORITI hipotezu workera
(ne samo potvrditi je), provjeri edge case-ove, i jasno navede šta NIJE
provjerio. `agent_report` (worker) tvrdi da je zadatak završen;
`agent_report`-ovo polje "Nezavisna provjera" tvrdi da je to i DOKAZANO —
to su dvije različite stvari, ne miješati ih.

**Dvije odvojene ose pregleda** (kod može biti lijepo napisan a rješavati
pogrešan problem, ili tačno riješiti problem a biti arhitekturno loše —
jedan opšti pregled često pomiješa ova dva kriterija):

- **Standards review** — da li je kod u skladu sa konvencijama i
  arhitekturom (naming, stil, modularnost, error handling, zavisnosti,
  testna praksa, sigurnost, performanse).
- **Spec review** — da li kod zaista rješava zadati problem (acceptance
  kriteriji, izostavljeni slučajevi, scope creep, kontradikcije sa
  zadatkom, van-opsežne promjene).

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

**Napomena**: `project_room`/trajni zapis odluke ima smisla i ISPOD
HIGH/CRITICAL praga kad je odluku teško vratiti, iznenađujuća je bez
konteksta, ili je rezultat stvarnog kompromisa — vidi filter u
`CLAUDE.md` "Plan prije izmjene".

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

- [ ] Bug je reprodukovan prije popravke (ili je zapisano zašto nije mogao biti)
- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] <<< POPUNI: projekat-specifične provjere, npr. "Nisam koristio string
  interpolaciju u SQL-u" >>>
- [ ] Testovi prolaze: `<<< POPUNI: komanda, npr. "python -m pytest tests/ -q" >>>`
- [ ] Dokaz odgovara "Definition of Done" za tip promjene (GUI/parser/dokument/baza/...)
- [ ] Za HIGH/CRITICAL: nezavisna provjera je urađena i navedena u `agent_report`
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
