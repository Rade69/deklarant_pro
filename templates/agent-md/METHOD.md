# Metoda: strukturisan rad sa LLM agentima na kodu

> Ovo NIJE template za kopiranje — ovo je objašnjenje ZAŠTO template fajlovi
> u ovom folderu (`AGENTS.md`, `CLAUDE.md`, `agent_report_template.md`,
> `project_room_template.md`) izgledaju kako izgledaju. Namijenjeno za
> učenje: pročitati ovo prvo, pa onda kopirati i prilagoditi ostale fajlove
> u novi projekat.
>
> Izvedeno iz stvarnog, višemjesečnog rada na `deklarant_pro` projektu
> (PySide6 desktop aplikacija, više agenata — Claude Code, Codex, GitHub
> Copilot — rade paralelno na istoj kodnoj bazi). Princip je prenosiv na
> bilo koji softverski projekat gdje: (a) rad traje kroz više sesija, (b)
> više agenata/alata dira istu kodnu bazu, (c) greška ima cijenu veću od
> "samo ponovo pokreni".

---

## Problem koji ova metoda rješava

Bez strukture, rad sa LLM agentom na dužem projektu ima tri karakteristična
kvara:

1. **Kontekst se topi.** Agent u dugom razgovoru nosi cijelu istoriju
   pokušaja, uključujući greške i odbačene ideje — svaki novi zahtjev je
   skuplji i konfuzniji od prethodnog, a relevantan signal se gubi u šumu.
2. **Odluke se gube.** Bez pisanog traga, "zašto smo ovo uradili ovako"
   postoji samo u glavi osobe koja je bila prisutna tog dana. Sljedeći
   agent (ili ista osoba za mjesec dana) ili ponavlja istu grešku, ili
   "popravlja" namjerno pravilo natrag jer mu izgleda kao bug.
3. **Rizik se ne skalira sa posljedicom.** Jednolinijska ispravka i
   arhitektonska promjena dobijaju isti (pre)tretman — ili je sve
   prezahtjevno za sitnice, ili je sve preplitko za rizične izmjene.

Metoda ispod rješava sva tri kroz jedan princip: **agent ne prenosi
razgovor, prenosi artefakt** — i taj artefakt ima fiksnu, predvidivu formu.

---

## Devet komponenti

### 1. Kanonski fajl pravila — jedan izvor istine

Sva pravila na JEDNOM mjestu (`AGENTS.md`), koje čitaju svi agenti/alati.
Alat-specifični fajlovi (`CLAUDE.md` za Claude Code, itd.) samo importuju
ili dopunjuju — nikad ne dupliraju. Bez ovoga, pravila drift-uju: Codex
zna nešto što Claude ne zna, i obrnuto, i niko ne zna koja je verzija
tačna.

### 2. Slojevit kontekst — nije sva memorija ista

- **Evergreen pravila** (malo, čita se UVIJEK, prije svakog zadatka) —
  ono što ne zavisi od datuma ili konkretnog taska.
- **Dated istorija** (može biti veliko, pretražuje se PO POTREBI, ne čita
  cijelo) — hronologija odluka, bugova, faza.
- **Radna/sesijska memorija** (po agentu, po sesiji) — specifično za alat
  (npr. Claude Code fajl-memorija ili MCP memory server).

Kad se evergreen fajl napuni dated zapisima, on prestaje biti "malo i
uvijek se čita" — treba ga podijeliti (vidi `AGENTS.md` sekciju "Kontekst
projekta"). Znak da je vrijeme za podjelu: fajl prelazi nekoliko stotina
linija ili agent počinje da "preskače" dijelove pri čitanju.

### 3. Strukturisan intake zadatka

Prije netrivijalnog zadatka, čovjek popuni kratak obrazac (vidi `CLAUDE.md`
"Format zadatka"): šta treba uraditi, KOJA JE MOJA HIPOTEZA o uzroku/
rješenju, šta agent NE SMIJE dirati, i kako izgleda dobar ishod. Agent onda
PRIJE izmjene potvrđuje ili odbacuje hipotezu dokazima — ne izvršava
slijepo ono što je čovjek pretpostavio. Ovo hvata slučajeve gdje je čovjek
pogrešno dijagnostikovao uzrok, prije nego što agent potroši vrijeme
"rješavajući" pogrešan problem.

### 4. Gejt provjere uticaja PRIJE izmjene

Prije nego što se dirne simbol/funkcija/modul, agent mora znati ko sve od
njega zavisi. Alat je zamjenjiv (code-graph alat, IDE "find references",
`grep`, ili prosto pažljivo čitanje pozivalaca) — princip nije: **nikad
ne pretpostavljati blast radius, uvijek ga provjeriti**.

### 5. Rizik-stepenovana ceremonija

Ne tretirati svaku izmjenu isto:

- **LOW/MEDIUM** — direktno, agent_report na kraju je dovoljan.
- **HIGH/CRITICAL** (širok blast radius, dodiruje produkcione podatke,
  sigurnosno osjetljivo, arhitektonska odluka) — PRIJE izmjene, kratak
  plan fajl (`project_room_template.md`) sa eksplicitnim scope lock-om
  ("šta MORA ostati identično") i, ako je potrebno, korisnička potvrda.

Ovo sprečava dvije suprotne greške: preveliki overhead na sitnice, i
nedovoljna pažnja na rizične promjene.

### 6. Fiksna šema izvještaja poslije zadatka

Svaki netrivijalan zadatak se zatvara sa `agent_report` po fiksnoj šemi
(vidi `agent_report_template.md`): šta je urađeno, ZAŠTO (poslovni razlog/
uzrok buga), KAKO (tehnički pristup), šta NIJE dirano (eksplicitno —
sprečava širenje scope-a i lažni utisak da je nešto provjereno), kako je
VERIFIKOVANO, koji su rizici, i šta je otvoreno za sljedeći put. Fiksna
šema garantuje da se ništa tiho ne preskoči — čak i kad je odgovor "nema".

### 7. Artefakt umjesto razgovora — prelaz između faza

Kad se faza rada promijeni (istraživanje → plan → implementacija →
verifikacija), sljedeća faza dobija PRETHODNI ARTEFAKT (plan fajl,
report), ne cijeli chat. Ovo je isti princip kao #2, primijenjen na tok
rada unutar jedne sesije/zadatka, ne samo na dugoročnu memoriju.

### 8. Git higijena vezana za sve gore

Atomski commit po logičkoj cjelini (ne "sve u jedan commit"), konvencija
poruke (`tip(oblast): opis`), i po mogućnosti automatska provjera
(pre-commit hook) koja podsjeća na proceduru — ne da bi blokirala rad, nego
da bi bila spoljna memorija za korake koje je lako preskočiti pod pritiskom.

### 9. Izolacija paralelnih agenata

Čim više od jednog agenta (ili automatizovanog pipeline-a) može raditi na
istom kodu u isto vrijeme, dijeljeni working tree postaje rizik: agent A
ostavi nekomitovane izmjene, agent B (npr. automatizovan tok koji na kraju
svoje faze radi široki `git add`) ih nesvjesno pokupi u svoj commit.
Sadržaj se ne gubi, ali autorstvo i istorija postaju netačni i teško ih je
razdvojiti. Rješenje: svaki dugotrajan/automatizovan agent tok radi u
zasebnom `git worktree`, ne na glavnom working tree-u koji dijele
interaktivne sesije.

---

## Kako početi u novom projektu

1. Kopirati `AGENTS.md` i `CLAUDE.md` (ili samo `CLAUDE.md` ako je jedini
   agent Claude Code) u korijen novog projekta, popuniti sve
   `<<< POPUNI: ... >>>` placeholdere.
2. Napraviti prazne foldere `agent_reports/` i (opciono, dok ne zatreba)
   `project_rooms/`.
3. NE praviti `docs/CONTEXT.md`/`docs/context/history.md` unaprijed — tek
   kad se pojavi prvo ne-trivijalno pravilo koje nije vidljivo iz koda.
   Prerano kreiranje prazne infrastrukture je isti bloat koji metoda
   pokušava spriječiti.
4. Za komponentu #4 (impact analiza) — ako projekat nema code-graph alat,
   definisati eksplicitan zamjenski kriterijum za "HIGH/CRITICAL" (npr.
   "simbol ima >10 pozivalaca", "dio je shared/core modula") — vidi
   placeholder u `CLAUDE.md`.
5. Prvi put kad `docs/CONTEXT.md`-ekvivalent naraste (vidi komponentu #2),
   podijeliti ga — ne čekati da postane 3000+ linija.

---

## Kada NE primjenjivati (ili primijeniti u olakšanoj formi)

- Jednokratan skript, eksperiment, prototip bez budućnosti — sva ova
  ceremonija je čist overhead.
- Solo rad, kratak vijek projekta, nema drugih agenata koji će ikad
  dirati ovaj kod — komponente #1, #3, #6 i dalje vrijede u minimalnoj
  formi (par rečenica prije/poslije), ali #5 (project_room), #9
  (worktree izolacija) i formalni `docs/CONTEXT.md` split su suvišni dok
  ne zatrebaju.
- Pravilo palca: uvedi komponentu kad je PRVI PUT stvarno nedostajala
  (agent je "popravio" namjerno pravilo natrag, izgubljena je odluka, dva
  agenta su se sudarila) — ne unaprijed "za svaki slučaj".

---

## Šta je univerzalno, šta je zamjenjivo

**Univerzalno** (prenosi se skoro 1:1 na bilo koji softverski projekat, a
vjerovatno i na drugi rad sa jasnim "artefaktima" i verzijama — pravni
dokumenti, data pipeline konfiguracije, content sistemi): komponente #1,
#2, #3, #5, #6, #7, #9.

**Zamjenjivo** (princip ostaje, alat/implementacija se mijenja po
projektu): komponenta #4 (code-graph alat vs grep vs IDE), tačan format
memorije u komponenti #2 (fajl-baziran vs vector store vs MCP server),
git hook mehanizam u komponenti #8.

**Projekt-specifično** (ne prenosi se — ovo su primjeri, ne šablon): sva
konkretna poslovna pravila, tech stack, zabrane specifične za jedan
projekat. Ta idu u `<<< POPUNI >>>` sekcije, ne u ovaj METHOD.md.
