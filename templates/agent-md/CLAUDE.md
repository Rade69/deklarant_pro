# CLAUDE.md - Projektne instrukcije za AI asistenta

> **TEMPLATE.** Ovo je univerzalni osnov izveden iz `CLAUDE.md`/`AGENTS.md`
> projekta `deklarant_pro`. Kopirati u korijen novog projekta kao `CLAUDE.md`
> i popuniti sekcije obilježene `<<< POPUNI: ... >>>`. Sekcije BEZ tog
> obilježivača su opšta pravila koja vrijede nezavisno od projekta — po
> potrebi prilagoditi formulaciju, ali ne brisati bez razloga (predstavljaju
> naučene lekcije: spriječavaju ponavljanje istih grešaka/diskusija).
>
> Ovaj fajl rade u paru sa `AGENTS.md` (isti template folder) — `CLAUDE.md`
> je za Claude Code, `AGENTS.md` za sve ostale agente (Qwen, Copilot,
> Cursor...). Ako projekat koristi SAMO Claude Code, sadržaj `AGENTS.md`
> templejta (tech stack, arhitektura, zabrane) se može spojiti ovdje i
> `AGENTS.md` izostaviti.

---

## ⚠️ JEZIK I PISMO: <<< POPUNI npr. "ISKLJUČIVO SRPSKI LATINICA" >>>

**OVA INSTRUKCIJA JE OBAVEZNA I PRIMARNA** — staviti je na vrh fajla jer
agent čita CLAUDE.md prije svega ostalog, i jezik/pismo utiče na SVAKI
odgovor.

- Pišem isključivo na <<< POPUNI: jezik + pismo >>>
- Svi odgovori, objašnjenja, komentari su na <<< pismo >>>
- Nikada ne pišem <<< POPUNI: zabranjeno pismo/jezik, ako relevantno (npr.
  "nikad ćirilica", "nikad engleski osim ako korisnik eksplicitno traži") >>>
- Kod komentari mogu biti na engleskom ako već postoje u kodu (ne prepisivati
  postojeći stil bez razloga)

---

## ⚠️ OBAVEZNO: Čitanje memorije na početku SVAKE sesije

Claude Code ima fajl-baziran memorijski sistem u
`~/.claude/projects/<slug-projekta>/memory/` (slug se generiše iz putanje
projekta). Protokol na početku sesije:

1. `MEMORY.md` (indeks svih memorija za ovaj projekat) je automatski učitan
   u kontekst na početku razgovora — pregledati ga prvo.
2. Ako je trenutni zadatak vezan za neku temu iz indeksa, otvoriti
   odgovarajući memorijski fajl (`Read`) za detalje (Šta/Zašto/Kako se
   primjenjuje).
3. Memorija ima prioritet nad starim `agent_reports/`/dokumentacijom AKO su
   u konfliktu — ali PRIJE oslanjanja na nju, provjeriti da je još tačna
   (fajl/funkcija/red mogu biti promijenjeni ili obrisani od kad je memorija
   napisana). Ako memorija tvrdi da nešto postoji, provjeriti `grep`/`Read`
   pre nego što se na to osloni preporuka korisniku.
4. Memorija se NE koristi za: kod konvencije/arhitekturu (to se vidi iz
   koda), git historiju (`git log`/`git blame` su autoritativni), privremeno
   stanje zadatka.

<<< POPUNI: ako projekat koristi DRUGAČIJI/DODATNI memory mehanizam (npr.
namjenski MCP memory server sa alatima poput `get_project_context` /
`search_project_memory`, ili vector store), opisati ovdje kako se on
kombinuje sa fajl-baziranom memorijom — koji ima prioritet i zašto. >>>

---

## Projektne konvencije

<<< POPUNI: ovo je SRCE projektno-specifičnog dijela. Svako pravilo treba
imati ŠTA (konkretno pravilo), ZAŠTO (background/bug koji je riješio — bez
toga agent će "popraviti" pravilo natrag jer mu izgleda kao greška), i GDJE
u kodu (fajl/funkcija). Primjeri kategorija (iz deklarant_pro — zamijeniti
stvarnim pravilima ovog projekta):

- Formatiranje podataka (npr. brojevi, datumi, valute) — gdje je tačno
  pravilo implementirano (npr. `_format_weight()` u `faktura_tab_v2.py`)
- Parsiranje/import specifičnih formata po izvoru (npr. različiti dobavljači
  imaju različite formate fajlova — koji importer pokriva koji format i koje
  su mu posebnosti)
- GUI konvencije (koji widget za koju vrstu prikaza, read-only polja, debug
  ispisi)
- Poslovna pravila koja NISU očigledna iz koda (npr. "polje X prikazuje
  agregat iz tabele Y, ali export mora biti skraćen na N karaktera")
- Konvencije za "kombinovane" operacije (npr. kad jedan proces konzumira
  više fajlova/izvora, kako se to obilježava da se ne dupliraju rezultati)
- Auto-popunjavanje/učenje (ako sistem ima komponentu koja "uči" mapiranja —
  opisati prioritet matching pravila i gdje se pamte naučena mapiranja) >>>

---

## Stil koda

- Docstrings: <<< POPUNI: jezik/da li su obavezni za nove metode >>>
- Komentari: <<< POPUNI: jezik za nove komentare; postojeći stil se ne
  prepisuje bez razloga >>>
- Log/print poruke: <<< POPUNI: konvencija (npr. emoji prefiksi za vizuelnu
  identifikaciju, structured logging, itd.) >>>
- Error handling: <<< POPUNI: stil poruka, da li se greške prevode za
  korisnika >>>
- Opšta pravila (vrijede nezavisno od projekta):
  - Tri slične linije > prerana apstrakcija
  - Ne dodavati error handling/validaciju za scenarije koji se ne mogu
    desiti — validacija samo na granicama sistema (korisnički unos, eksterni
    API)
  - Default: bez komentara. Komentar samo kad objašnjava NEOČIGLEDAN "zašto"
    (workaround, invarijanta, podmukli bug) — ne "šta" (to vide imena)

---

## Struktura projekta

```text
<<< POPUNI: stablo direktorija projekta sa kratkim opisom svake bitne
fascikle, npr.

ime_projekta/
├── core/                 # ...
├── gui/ ili api/         # ...
├── services/             # business logika
├── database/             # ...
└── tests/                # ...
>>>
```

---

## Testiranje

- <<< POPUNI: gdje su test podaci (npr. folder sa realnim primjerima), kako
  se pokreću testovi (komanda), šta su poznati edge case-ovi koje treba
  provjeriti >>>
- Debug ispisi moraju biti informativni i pregledni (ako se koriste umjesto
  ili uz formalne testove)

---

## Git konvencije

- Commit poruke: <<< POPUNI: jezik (npr. srpski latinica) >>>
- Format: `tip(oblast): kratki opis` (`fix`, `feat`, `refactor`, `docs`,
  `chore`, ...)
- Uvijek dodati: `Co-Authored-By: <<< POPUNI: ime AI asistenta >>>
  <noreply@anthropic.com>`
- Opisati ŠTA je promijenjeno i ZAŠTO (ne samo šta)

---

## Format zadatka za agenta (preporučeno)

Za netrivijalne i debug zadatke, korisnik formuliše zadatak po ovom obrascu.
Agent ga prepoznaje i direktno mapira na sekcije iz "OBAVEZNA PROCEDURA →
Agent report":

- **Zadatak** — šta treba popraviti/promijeniti
- **Moja radna pretpostavka** — korisnikova hipoteza o uzroku/rješenju
- **Provjeri hipotezu** — agent PRIJE izmjene potvrđuje ili odbacuje
  hipotezu dokazima (baza, kod, logovi) → puni "Zašto je urađeno" i
  "Verifikacija" u izvještaju
- **Granice** — šta agent NE smije dirati (van scope-a) → puni
  "Šta nije dirano"
- **Šta je dobar ishod** — opis vidljivog/testabilnog rezultata
- **Obavezno** — agent prikazuje impact/rizik i ostavlja agent_report
  → puni "GitNexus impact" (ili ekvivalent — vidi sekciju ispod) i
  "Rizici / ograničenja"

Ovaj format je preporuka, ne zamjena za "OBAVEZNA PROCEDURA": za sitne,
jednolinijske ispravke (npr. jedan red u bazi, jedna konstanta) format je
nepotreban overhead — koristiti procjenu.

---

## Plan prije izmjene — HIGH/CRITICAL impact

Ako alat za impact-analizu (npr. `gitnexus_impact` — vidi opcionu sekciju
"Code Intelligence" na kraju fajla, ili ekvivalentan alat) za simbol koji se
mijenja vrati **HIGH** ili **CRITICAL**, agent PRIJE izmjene napravi JEDAN
kratki fajl (ne cijeli "project room" sa više fajlova):

```text
project_rooms/YYYY-MM-DD_kratak-naziv-zadatka.md
```

sa sekcijama:

- **Cilj** — šta se mijenja i zašto
- **Pogođeno** — simboli/procesi iz impact-analize (broj, koji, rizik)
- **Plan** — fajlovi i redoslijed izmjena
- **Šta NE dirati** — eksplicitne granice (scope lock — vidi `AGENTS.md`
  "Handoff visokog rizika" za format prijave rizika korisniku)
- **Konflikti** — ako postoje kontradiktorni izvori (stari agent_report,
  memorija, kod), navesti oba, koji se tretira kao važeći i zašto, i da li
  je potrebna korisnička potvrda (DA/NE)

Fajl se na kraju može spojiti u `agent_report` (Korak 3 ispod) ili obrisati —
nije trajna dokumentacija. Za MEDIUM ili niži impact ovaj korak se
preskače — dovoljan je "Format zadatka" iznad i `agent_report` na kraju.

<<< POPUNI: ako projekat NEMA alat za impact-analizu, definisati ovdje
zamjenski kriterijum za "HIGH/CRITICAL" (npr. "simbol ima >10 pozivača",
"dio je core/shared modula", "dodiruje bazu/produkcione podatke") >>>

---

## ⚠️ OBAVEZNA PROCEDURA: Nakon završenog zadatka

Svaki agent koji radi na ovom projektu MORA slijediti ovaj redosljed nakon
što završi zadatak:

### Korak 1 — Git commit

- Staged promjene grupisati po logičkim cjelinama (ne sve u jedan commit)
- Format poruke: `tip(oblast): kratki opis`
- Uvijek dodati: `Co-Authored-By: <<< ime AI asistenta >>>
  <noreply@anthropic.com>`

### Korak 2 — Memorija

- Upisati u memorijski fajl sve što je **ne-očigledno** i korisno za buduće
  sesije
- Lokacija: `~/.claude/projects/<slug-projekta>/memory/`
- Format fajla: `YYYY-MM-DD_kratki-opis.md` sa YAML frontmatterom (`name`,
  `description`, `metadata.type`)
- Ažurirati `MEMORY.md` index — jedna linija po memorijskom fajlu
- **Šta upisivati**: poslovne odluke, pravila koja nisu u kodu, bug uzroci,
  fiksevi koji se mogu ponoviti
- **Šta NE upisivati**: šta kod radi (to se vidi iz koda), git historija,
  privremeno stanje

### Korak 3 — Agent report

- Kreirati izvještaj u `agent_reports/YYYY-MM-DD_naziv-zadatka.md`
- Izvještaj mora pratiti ovu strukturu (sekcije kao `##`):
  - **Datum**, **Agent**, **Scope** — fajlovi/moduli na koje se zadatak
    odnosi
  - **Status izvora** (samo za kompleksne/rizične zadatke) — koji raniji
    agent_reports/memory/kod fajlovi su korišćeni kao osnova i njihov
    status: aktivan / zastario / duplikat / treba potvrdu
  - **Impact analiza** — rezultat provjere prije izmjene (rizik, broj
    pogođenih simbola/procesa) — vidi opcionu sekciju "Code Intelligence"
  - **Šta je urađeno** — kratki pregled promjena
  - **Zašto je urađeno** — poslovni razlog, bug uzrok, odluka i alternativa
  - **Kako je urađeno** — tehnički pristup, koje funkcije/fajlovi
  - **Šta nije dirano** — eksplicitno navesti šta je OSTAVLJENO netaknuto
    (npr. nepovezan WIP), da se spriječi širenje scope-a
  - **Verifikacija** — kako je agent dokazao da promjena radi (testovi,
    offscreen provjere, py_compile...)
  - **Pronađeni problemi** — uključujući lažno pozitivne zaključke (npr.
    verifikacija koja je krivo pokazala uspjeh)
  - **Konflikti / kontradiktorni izvori** (ako postoje) — dva izvora koja se
    ne slažu (stari report vs. kod, dvije memorije...), koji je tretiran kao
    važeći i zašto, i da li treba korisnička potvrda (DA/NE)
  - **Commitovi** — tabela hash/poruka
  - **Rizici / ograničenja**
  - **Potreban follow-up** — šta NIJE zatvoreno
  - **Potrebna korisnička potvrda** — šta korisnik treba ručno provjeriti
    (npr. vizuelni izgled na stvarnom hardveru)
- Commitovati izvještaj odmah nakon pisanja

### Korak 4 — Link u kodu (opcionalno, za kompleksne odluke)

- Kada je odluka netrivijalna (npr. zašto je odabran ovaj algoritam, zašto je
  nešto preskočeno), dodati komentar u kodu koji referiše na izvještaj:

  ```text
  # Vidi agent_reports/YYYY-MM-DD_naziv.md — objašnjenje odluke
  ```

- Koristiti samo gdje je stvarno potrebno, ne na svakoj promjeni

### Korak 5 — Code intelligence ažuriranje (opcionalno)

<<< POPUNI/UKLONI: ako projekat koristi alat za code intelligence (npr.
GitNexus), nakon commita provjeriti je li index zastario i pokrenuti
odgovarajuću analize-komandu. Ako projekat NEMA takav alat, ovaj korak
ukloniti. >>>

---

## DOC Guard (opcionalno)

<<< POPUNI/UKLONI: ako projekat ima hook koji provjerava linkove na MD
fajlove (DOC-GUARD), opisati ovdje kako agent reaguje na BROKEN/STALE status
i komandu za ručnu provjeru. Ako ne postoji, ukloniti sekciju. >>>

---

## Code Intelligence (opcionalno — npr. GitNexus)

<<< POPUNI/UKLONI: ako projekat koristi GitNexus (ili sličan alat za
analizu kodne baze), ovdje ide auto-generisana sekcija sa statistikama
(simboli/relacije/flows), Always-Do / Never-Do pravilima (impact analiza
prije izmjene, detect_changes prije commita, rename umjesto find-replace),
i tabelom resursa/skill fajlova. Pokrenuti inicijalnu analizu (npr.
`npx gitnexus analyze` / `npx gitnexus init`) da se ova sekcija generiše.
Ako projekat ne koristi takav alat, ukloniti cijelu sekciju i sve referencije
na nju iznad (Korak 5, "Plan prije izmjene"). >>>
