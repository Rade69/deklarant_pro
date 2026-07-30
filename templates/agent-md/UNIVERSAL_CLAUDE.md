# CLAUDE.md — <<< POPUNI: naziv projekta >>>

> **BOOTSTRAP STATUS: NIJE POKRENUT**
>
> Ovo je JEDAN samostalan fajl — sadrži i PRAVILA rada i UPUTSTVO KAKO
> SEBE POPUNITI. Nema zavisnosti od drugih fajlova. Namijenjen za
> kopiranje u korijen projekta kao `CLAUDE.md`.
>
> **AKO GORNJA LINIJA I DALJE PIŠE "NIJE POKRENUT"**: prije bilo kog
> drugog zadatka u ovoj sesiji, izvrši Sekciju 0 (Bootstrap) ODMAH — ne
> čekati eksplicitnu komandu korisnika, ne pitati "da li da skeniram
> projekat". Projekat je vjerovatno već u poodmakloj fazi razvoja
> (postojeći kod, git istorija, možda i postojeća pravila) — cilj
> bootstrap-a je da SNIMI TRENUTNO STANJE i ovaj fajl prilagodi njemu,
> ne da počne od praznog lista. Kad bootstrap završi, zamijeni gornju
> liniju sa `BOOTSTRAP STATUS: ZAVRŠEN YYYY-MM-DD — vidi
> agent_reports/YYYY-MM-DD_bootstrap.md` i OD TOG TRENUTKA preskoči
> Sekciju 0 u svakoj narednoj sesiji — ne ponavljati bootstrap.

---

## Sekcija 0 — BOOTSTRAP (izvršiti ODMAH ako status nije ZAVRŠEN)

**Prije bilo čega, pokreni `git status --short`.** Ako working tree nije
čist, utvrdi čije su te izmjene prije nastavka — mogu biti tuđi
nekomitovan rad (vidi "Paralelni agenti" u Sekciji 2). Ne pokretati širok
`git add` preko tuđih izmjena.

**Ako u korijenu VEĆ postoji drugi `AGENTS.md`/`CLAUDE.md`** (ne ovaj
fajl) — NE prepisivati ga bez pitanja. Prikazati korisniku predloženu
dopunu/spajanje i tražiti potvrdu.

Zatim, sledećim redom, POTVRDI DOKAZOM (fajl/linija/komanda) prije upisa
— nikad ne pretpostaviti ni izmisliti:

1. **Tech stack** — manifest fajlovi (`package.json`, `pyproject.toml`,
   `go.mod`, `Cargo.toml`, `pom.xml`, `*.csproj`, `Gemfile`,
   `composer.json`...). Izvuci jezik+verziju, package manager, glavne
   dependency-je koje određuju arhitekturu.
2. **Struktura projekta** — top-level i drugi nivo direktorija (isključi
   `.git/`, `.worktrees/`, `node_modules/`, `.venv/`, `venv/`, `dist/`,
   `build/`, `__pycache__/`, `generated/`, `backups/`, i ekvivalente kao
   `target/`, `bin/`, `obj/`). Za svaki sloj otvori 2-3 reprezentativna
   fajla da potvrdiš ulogu — ne pogađaj po imenu foldera.
3. **Konvencije koda** — linter/formatter config fajlovi kao izvor
   istine za stil; za ono što config NE pokriva (docstrings, gustina
   komentara, error handling), uzorkuj 5-10 fajlova i navedi šta je
   DOSLJEDNO. Ako je nekonzistentno, zapiši kao zapažanje i flaguj za
   odluku, ne kao pravilo. **Provjeri specifično**: da li kod već ima
   dosljednu konvenciju komentarisanja različitu od "Kod je
   samoobjašnjavajući" pravila u Sekciji 2 — ako da, flaguj za odluku
   umjesto da tiho nametneš default.
4. **Testovi** — test folder, framework (iz manifest dependency-ja),
   komanda za pokretanje (package.json scripts/Makefile/tox.ini/CI
   config). STVARNO pokreni komandu (read-only) da potvrdiš da radi.
5. **Git istorija** — `git log --oneline -50`: jezik commit poruka,
   format, `Co-Authored-By` konvencija ako postoji. Traži i commit
   poruke tipa `fix: revert X jer...`/`ukloni Y koji je pravio...` —
   to su gotovi kandidati za "Zabrane" tabelu (pravilo + razlog već
   postoje, samo ih izvući).
6. **Postojeća agent-infrastruktura** — provjeri postoji li već
   `agent_reports/`, `docs/CONTEXT.md`-ekvivalent, code-graph/impact
   alat, pre-commit hookovi. Referenciraj nađeno umjesto da predlažeš
   duplikat.
7. **Sjeme za "Evergreen napomene" (Sekcija 2)** — pretraži kod za
   `HACK`, `WARNING`, `IMPORTANT`, `NOTE:`, `workaround`, `don't`/`ne
   diraj`, `zašto`/`why` u komentarima. Za svaki nađen, PRENESI TAČAN
   TEKST komentara sa referencom fajl:linija — ne parafraziraj, ne
   dodaji objašnjenje koje komentar sam ne daje. Ovo je NAJVREDNIJI
   korak na projektu u poodmakloj fazi — tu je najviše tribal-knowledge
   koje niko nije zapisao na jednom mjestu.
8. **Sigurnosno/osjetljivo** — provjeri postoje li `.env`/credentials
   fajlovi, da li su u `.gitignore`, da li kod ima očigledne hardkodovane
   tajne (grep za "password", "api_key", "secret" kao heuristika, ne
   garancija). Flaguj, ne popravljaj sam bez potvrde.

**Obavezan sažetak PRIJE finalizacije** (ne nastavljaj dalje bez ovoga):

| Popunjeno sa dokazom | Treba potvrdu (najbolja pretpostavka) | Nije moglo biti utvrđeno |
| --- | --- | --- |
| ... (fajl/linija referenca) | ... (razlog nesigurnosti) | ... (ostaje `<<< POPUNI >>>`) |

**Housekeeping nakon potvrde korisnika:**

- Popuni `<<< POPUNI >>>` mjesta u Sekciji 2 direktno u ovom fajlu.
- Kreiraj prazan `agent_reports/` folder.
- Ako je Korak 7 našao materijal — kreiraj "Evergreen napomene" odjeljak
  u Sekciji 2 sa tim nalazima (korisnik ih je već potvrdio kroz sažetak
  iznad).
- Ako materijala iz Koraka 5+7 ima MNOGO (orijentaciono >100-150 linija
  već pri bootstrap-u — očekivano na poodmakloj kodnoj bazi) — ne čekati
  organski rast, nego ODMAH primijeniti podjelu iz Sekcije 3 (ovaj fajl
  ostaje kratak/evergreen, novo `docs/context/history.md` nosi opsežnije
  nalaze).
- Napiši `agent_reports/YYYY-MM-DD_bootstrap.md` (koristi šemu iz
  "Agent report" u Sekciji 2) — šta je nađeno, šta je popunjeno sa
  dokazom, šta čeka potvrdu, šta nije utvrđeno.
- Predloži prvi commit, ali NE commituj bez eksplicitne potvrde
  korisnika.
- Ažuriraj STATUS liniju na vrhu fajla.

---

## Sekcija 1 — Zašto ova pravila postoje (kratko; ne preskakati jer djeluje suvišno)

Bez strukture, rad sa AI agentom na dužem projektu ima tri kvara:
kontekst se topi (agent nosi cijelu istoriju pokušaja umjesto prihvaćenog
zaključka), odluke se gube (sljedeći agent ponavlja grešku ili "popravlja"
namjerno pravilo natrag), i rizik se ne skalira sa posljedicom (sitnica i
arhitektonska promjena dobijaju isti tretman). Dolje navedena pravila
rješavaju sva tri kroz jedan princip: **agent ne prenosi razgovor, prenosi
artefakt** — plan prije rizične izmjene, `agent_report` poslije svake.

Deset ideja u pozadini (detalji u Sekciji 2, ovo je samo podsjetnik ZAŠTO
ih ne brisati kad zasmetaju):

1. **Jedan izvor istine** — sva pravila na jednom mjestu, ne duplirano.
2. **Slojevit kontekst** — evergreen (malo, uvijek se čita) odvojeno od
   dated istorije (veliko, pretražuje se po potrebi).
3. **Strukturisan intake** — hipoteza se potvrđuje dokazom prije izmjene.
4. **Gejt provjere uticaja** — nikad ne pretpostaviti blast radius.
5. **Rizik-stepenovana ceremonija** — LOW direktno, HIGH/CRITICAL sa
   planom i scope lock-om.
6. **Fiksna šema izvještaja** — ništa se tiho ne preskače.
7. **Samoobjašnjavajući kod** — ime nosi "šta", komentar (kratak) nosi
   neočigledno "zašto", dugo objašnjenje ide u `agent_report` uz link.
8. **Artefakt umjesto razgovora** — prelaz između faza nosi zaključak,
   ne cijeli chat.
9. **Git higijena** — atomski commit, nikad širok `git add` u dijeljenom
   working tree-u.
10. **Reprodukcija prije popravke + nezavisna provjera** — "agent kaže da
    je gotovo" i "dokazano je da radi" su dvije različite tvrdnje.

---

## Sekcija 2 — Pravila

### Jezik

- Svi odgovori korisniku: <<< POPUNI: jezik + pismo >>>
- Komentari u kodu: <<< POPUNI: jezik (prati postojeći stil fajla) >>>
- Commit poruke: <<< POPUNI: jezik, format `tip(scope): opis` >>>

### Token budget i context disciplina

Agent ne prenosi cijeli prethodni razgovor u novi zadatak — prenosi
prihvaćen artefakt (plan, `agent_report`). Veliki fajlovi (stotine+
linija) se prvo pretraže (grep) po pojmu; cijeli se čitaju samo kad
zadatak to stvarno zahtijeva. Izuzetak: HIGH/CRITICAL odluke i sigurnosni
rizik — tačnost ima prednost nad štednjom konteksta.

### Paralelni agenti — izolacija working tree-a

Relevantno čim više od jednog agenta (ili automatizovan pipeline) može
raditi na istom kodu u isto vrijeme. Pravila: nikad `git add -A`/`git add
.` — uvijek navesti tačne fajlove; prije svakog `git add`/`commit`
provjeriti `git status --short`; ako ima nepoznatih izmjena, utvrditi
čije su prije nastavka. Dugotrajni/automatizovani pipeline-ovi rade u
zasebnom `git worktree` gdje je to moguće.

### Evergreen napomene

<<< POPUNI (BOOTSTRAP Korak 7): ne-trivijalne odluke, zabranjeni patterni
i poznati bugovi koji nisu vidljivi iz koda — svaki sa fajl/linija
referencom ili "N/A" ako projekat nema još ovakvih napomena. Kad ovaj
odjeljak naraste (vidi Sekciju 3), premjestiti u zaseban fajl. >>>

### Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš
uraditi. Čekaj potvrdu korisnika ako zadatak nije jednoznačan.

### Reprodukcija prije bugfixa

Bug se ne popravlja dok nije reprodukovan (failing test, konkretan ulaz,
log, screenshot/video, precizan ručni postupak), osim kad je zapisano
zašto reprodukcija nije moguća i na kojoj se pretpostavci izmjena
zasniva. Ne mijenjati kod samo zato što implementacija izgleda sumnjivo —
to nije isto što i dokazan uzrok.

### Tech stack

<<< POPUNI (BOOTSTRAP Korak 1) — jezik/runtime, package manager, glavni
framework(i), baza, testovi >>>

### Arhitektura

```text
<<< POPUNI (BOOTSTRAP Korak 2): stablo direktorija sa kratkim opisom
svake bitne fascikle >>>
```

<<< POPUNI: arhitektonski pattern ako je vidljiv iz stvarnog koda (samo
ako potvrđeno u 2+ primjera, ne pretpostavka) >>>

### Ključne konvencije

- Default: bez komentara — imena nose "šta". Komentar samo za
  neočigledno "zašto", kratak (jedna linija). Dugo objašnjenje ide u
  `agent_report`, komentar u kodu je samo link:
  ```text
  # Vidi agent_reports/YYYY-MM-DD_naziv.md — objašnjenje odluke
  ```
  (Razlog: inline objašnjenje i `agent_report` lako divergiraju kad se
  kod promijeni a komentar ne — kratak link ne zastarjeva na isti način.)
- Tri slične linije > prerana apstrakcija.
- Bez error handling/validacije za scenarije koji se ne mogu desiti —
  validacija samo na granicama sistema.
- <<< POPUNI (BOOTSTRAP Korak 3): projekat-specifične konvencije koda,
  imenovanja, formatiranja >>>

### Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
| --- | --- |
| <<< POPUNI (BOOTSTRAP Korak 5 — revert-commit-ovi su gotov izvor) >>> | <<< >>> |

### Definition of Done po tipu promjene

Promjena nije završena samo zato što se pokrenula. Dokaz zavisi od tipa —
popuniti kategorije koje odgovaraju ovom projektu, obrisati nepotrebne:

<<< POPUNI: primjeri — GUI/frontend (screenshot prije/poslije, offscreen
render nije dovoljan za nešto što zavisi od stvarnog prikaza); parseri/
import (fixture fajlovi, edge case-ovi, dokaz da stari izvori nisu
pokvareni); generisani dokumenti (golden fajlovi, semantičko poređenje,
schema validacija); baza/migracije (izolovana test baza, backup prije
produkcijske migracije, NIKAD prvi put na produkcionim podacima);
performanse (mjerenje prije/poslije, funkcionalna jednakost); sigurnost
(osjetljivi podaci ne završavaju u promptu/logovima/agent_report-u) >>>

### Podjela odgovornosti

| Ko | Šta |
| --- | --- |
| **Agent radi samostalno** | pretraga koda, pozivaoci, sažimanje ponašanja, failing test, mala lokalna izmjena, testovi, `agent_report` |
| **Agent samo predlaže** (korisnik odlučuje) | arhitektonska promjena, domenski model, centralna poslovna logika, bazna migracija, širi refactor, javni interfejs |
| **Nezavisan checker potvrđuje** | da diff odgovara scope-u, da testovi provjeravaju pravi problem, da nema regresije |
| **Korisnik odlučuje** | poslovna ispravnost, UX, HIGH/CRITICAL rizik, produkcijsko stanje |

### Nezavisna provjera (checker)

Obavezna ili snažno preporučena za: HIGH/CRITICAL impact, promjene baze/
migracija, centralnu poslovnu logiku, sigurnost, nereprodukovane bugove,
kontradiktorne izvore, veliku cijenu greške. Checker (drugi agent, drugi
model, ili korisnik) nezavisno: pregleda diff, potvrdi scope, provjeri
pozivaoce, pokrene testove, POKUŠA OBORITI hipotezu (ne samo potvrditi),
i jasno kaže šta NIJE provjerio. "Agent kaže da je gotovo" i "checker je
dokazao da radi" su dvije različite tvrdnje — ne miješati ih u
`agent_report`-u.

<<< POPUNI: konkretan mehanizam na ovom projektu — dostupni review
skillovi, druga agent sesija, ili ljudski review >>>

### Format zadatka za agenta (preporučeno)

Za netrivijalne zadatke: **Zadatak** (šta), **Moja radna pretpostavka**
(hipoteza), **Provjeri hipotezu** (agent potvrđuje/odbacuje dokazom prije
izmjene), **Granice** (šta se NE dira), **Šta je dobar ishod**,
**Obavezno** (impact/rizik + `agent_report`). Za sitne ispravke format je
nepotreban overhead.

### Plan prije izmjene — HIGH/CRITICAL impact

Ako je impact HIGH/CRITICAL (alat za impact-analizu ako postoji, inače
<<< POPUNI: zamjenski kriterijum, npr. "simbol ima >10 pozivalaca" >>>),
PRIJE izmjene napraviti kratak fajl `project_rooms/YYYY-MM-DD_naziv.md`
(ili odjeljak u `agent_report`-u ako `project_rooms/` folder još ne
postoji) sa: **Cilj**, **Pogođeno**, **Plan**, **Šta NE dirati** (scope
lock), **Plan verifikacije** (koji dokaz mora postojati — vidi Definition
of Done), **Rollback/oporavak**, **Nezavisni checker**, **Konflikti**
(ako postoje kontradiktorni izvori). Za MEDIUM ili niže se preskače.

### Handoff visokog rizika

Kad je impact HIGH/CRITICAL, prijaviti korisniku PRIJE izmjene: koliko
zavisi od simbola, da li je promjena mala/velika po obimu ali visoka/
niska po sistemskoj važnosti i zašto, šta scope NE uključuje, i šta MORA
postojati kao izlaz (tip promjene, prihvatljiv ishod/scope lock, nivo
dozvole).

### Obavezna procedura nakon zadatka

**Korak 1 — Git commit**: staged promjene grupisati po logičkim
cjelinama, format `tip(oblast): opis`, `Co-Authored-By:` linija. Nikad
širok `git add -A`/`.` (vidi "Paralelni agenti").

**Korak 2 — Memorija/napomene**: ne-očigledno i korisno za buduće sesije
ide u "Evergreen napomene" iznad (dok je fajl jedan) ili u
`docs/context/history.md` (nakon podjele — vidi Sekciju 3). Šta NE
upisivati: šta kod radi (vidi se iz koda), git istorija, privremeno
stanje.

**Korak 3 — Agent report**: `agent_reports/YYYY-MM-DD_naziv-zadatka.md`
sa sekcijama: **Datum/Agent/Scope**, **Impact analiza**, **Reprodukcija
prije izmjene** (za bugfix — dokaz ili razlog zašto nije moguće), **Šta
je urađeno**, **Zašto je urađeno**, **Kako je urađeno**, **Šta nije
dirano**, **Verifikacija** (mora odgovarati Definition of Done),
**Nezavisna provjera** (obavezno za HIGH/CRITICAL), **Pronađeni
problemi**, **Konflikti/kontradiktorni izvori**, **Commitovi**, **Rizici/
ograničenja**, **Potreban follow-up**, **Potrebna korisnička potvrda**.
Commitovati odmah nakon pisanja.

**Korak 4 — Link u kodu** (opcionalno): za netrivijalne odluke, kratak
komentar koji referiše `agent_report` (vidi "Ključne konvencije").

**Korak 5 — Code intelligence** (opcionalno): <<< POPUNI/UKLONI: ako
projekat koristi alat za analizu kodne baze, ovdje ide provjera
zastarjelosti indeksa >>>

### Testiranje

<<< POPUNI (BOOTSTRAP Korak 4): komanda, gdje su test podaci, poznati
edge case-ovi >>>

### Format outputa

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: (ako PARCIJALNO/BLOKIRANO)
PITANJA: (ako postoje)
```

### Provjera prije predaje

- [ ] Bug je reprodukovan prije popravke (ili zapisano zašto nije mogao biti)
- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] Testovi prolaze
- [ ] Dokaz odgovara Definition of Done za tip promjene
- [ ] Za HIGH/CRITICAL: nezavisna provjera je urađena i navedena
- [ ] Provjerio sam `git status --short` prije staging-a
- [ ] Output format je popunjen

---

## Sekcija 3 — Kad ovaj JEDAN fajl podijeliti na više

Znak da je vrijeme: "Evergreen napomene" odjeljak prelazi nekoliko
stotina linija, ili agent počinje "preskakati" dijelove pri čitanju, ili
`agent_reports/` ima desetine fajlova bez pregledne istorije.

Podjela (isti princip kao svugdje u ovom fajlu — evergreen odvojeno od
dated):

```text
CLAUDE.md                — ostaje ovaj fajl, SAMO Sekcija 2 (pravila),
                            skraćen (Evergreen napomene svedene na
                            trajno relevantno), bez Sekcije 0 (bootstrap
                            se više ne ponavlja) i bez Sekcije 1 (princip
                            je već usvojen, ne treba podsjetnik svaki put)
docs/CONTEXT.md           — evergreen napomene koje ostaju, kratko
docs/context/history.md   — dated, append-only log; NE čita se cijeli,
                            pretražuje se (grep) po temi/datumu
agent_reports/            — već postoji od bootstrap-a
project_rooms/            — kreirati kad prva HIGH/CRITICAL izmjena
                            zatreba plan fajl
```

Ne raditi ovu podjelu unaprijed "za svaki slučaj" — isti bloat koji ovaj
fajl pokušava spriječiti. Uvesti je kad prvi put stvarno nedostaje.
