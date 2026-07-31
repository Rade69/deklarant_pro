# Metoda: strukturisan rad sa LLM agentima na kodu

> Ovo NIJE template za kopiranje — ovo je objašnjenje ZAŠTO template fajlovi
> u ovom folderu (`AGENTS.md`, `CLAUDE.md`, `agent_report_template.md`,
> `project_room_template.md`) izgledaju kako izgledaju. Namijenjeno za
> učenje: pročitati ovo prvo, pa onda kopirati i prilagoditi ostale fajlove
> u novi projekat.
>
> Izvedeno iz stvarnog, višemjesečnog rada na `deklarant_pro` projektu
> (PySide6 desktop aplikacija, više agenata — Claude Code, Codex, GitHub
> Copilot,agent pi,open router sa masom drugih LLM-ova (GLM5.2,KIMI K3,qwen 3.8,MinMax 2.8...itd) — rade paralelno na istoj kodnoj bazi). Princip je prenosiv na
> bilo koji softverski projekat gdje: (a) rad traje kroz više sesija, (b)
> više agenata/alata dira istu kodnu bazu, (c) greška ima cijenu veću od
> "samo ponovo pokreni".
>
> **Za brzo prenošenje u DRUGI projekat** (gdje ne postoji cijeli ovaj
> folder) — `UNIVERSAL_CLAUDE.md` (isti folder) je sve iz ovog paketa
> stopljeno u JEDAN samostalan fajl, sa ugrađenim bootstrap-om koji se
> sam pokreće pri prvom čitanju (posebno pogodan za kodne baze koje su
> već u poodmakloj fazi, ne prazne projekte).

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

## Trinaest komponenti

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

### 7. Kod je samoobjašnjavajući; komentar linkuje, ne duplira

Default je BEZ komentara — imena funkcija/metoda/varijabli nose "šta".
Komentar u kodu se piše SAMO kad postoji neočigledan "zašto" (workaround,
skrivena invarijanta, podmukao bug) koje ime samo ne može prenijeti — i
tada je komentar KRATAK (jedna linija), ne objašnjenje u prozi. Ako je
odluka dovoljno netrivijalna da zaslužuje pravo objašnjenje (alternative
koje su razmotrene i odbačene, poslovni razlog, veza sa bugom), to
objašnjenje ide u `agent_report` (komponenta #6), a komentar u kodu je
samo pokazivač na njega:

```python
# Vidi agent_reports/2026-07-19_evidence-adapter-exact-match-fix.md
```

Razlog za razdvajanje: inline objašnjenje u komentaru i objašnjenje u
`agent_report`-u lako divergiraju kad se kod kasnije mijenja — neko
ažurira kod, zaboravi ažurirati dugačak komentar iznad njega, i sad
komentar aktivno laže. Kratak link ne može zastarjeti na isti način
(fajl ostaje istorijski tačan za trenutak kad je pisan), a jedini izvor
istine za "zašto" je jedan fajl, ne razbacan po desetinama komentara.
Kolateralna korist: kod ostaje kratak i čitljiv, umjesto da svaka
netrivijalna odluka nabubri funkciju sa pasusom komentara.

### 8. Artefakt umjesto razgovora — prelaz između faza

Kad se faza rada promijeni (istraživanje → plan → implementacija →
verifikacija), sljedeća faza dobija PRETHODNI ARTEFAKT (plan fajl,
report), ne cijeli chat. Ovo je isti princip kao #2, primijenjen na tok
rada unutar jedne sesije/zadatka, ne samo na dugoročnu memoriju.

### 9. Git higijena vezana za sve gore

Atomski commit po logičkoj cjelini (ne "sve u jedan commit"), konvencija
poruke (`tip(oblast): opis`), i po mogućnosti automatska provjera
(pre-commit hook) koja podsjeća na proceduru — ne da bi blokirala rad, nego
da bi bila spoljna memorija za korake koje je lako preskočiti pod pritiskom.

### 10. Izolacija paralelnih agenata

Čim više od jednog agenta (ili automatizovanog pipeline-a) može raditi na
istom kodu u isto vrijeme, dijeljeni working tree postaje rizik: agent A
ostavi nekomitovane izmjene, agent B (npr. automatizovan tok koji na kraju
svoje faze radi široki `git add`) ih nesvjesno pokupi u svoj commit.
Sadržaj se ne gubi, ali autorstvo i istorija postaju netačni i teško ih je
razdvojiti. Rješenje: svaki dugotrajan/automatizovan agent tok radi u
zasebnom `git worktree`, ne na glavnom working tree-u koji dijele
interaktivne sesije.

### 11. Reprodukuj prije popravke

Bug se ne popravlja dok nije reprodukovan (failing test, konkretan ulaz,
log, screenshot, precizan ručni postupak) — osim kad je eksplicitno
zapisano zašto reprodukcija nije bila moguća i na kojoj se pretpostavci
izmjena onda zasniva. Razlog: bez reprodukcije, "popravka" lako gađa
simptom koji je agent primijetio, ne stvarni uzrok — kod koji IZGLEDA
sumnjivo nije isto što i kod koji je DOKAZANO uzrok. Agent koji promijeni
kod prije reprodukcije često napiše test POSLIJE koji potvrđuje njegovu
vlastitu izmjenu, ne stvarni problem — lažno pozitivan osjećaj da je
zatvoreno.

### 12. Worker ≠ checker ≠ čovjek — razdvojena verifikacija

Isti agent koji je pisao izmjenu, pisao test, pokrenuo test i protumačio
rezultat je u suštini provjeravao sam sebe. `agent_report` (komponenta
#6) dokazuje da je PROCEDURA praćena — ne dokazuje sam po sebi da je
RJEŠENJE ispravno. Za HIGH/CRITICAL (komponenta #5) i slične visoko-
rizične promjene, treći, nezavisan pregled (drugi agent, drugi model,
ili čovjek) mora aktivno pokušati OBORITI hipotezu workera, ne samo
potvrditi je — i mora jasno reći šta NIJE provjerio, ne samo šta jeste.
Tri različite tvrdnje se ne smiju miješati: "worker kaže da je gotovo"
(agent_report), "checker je dokazao da radi" (nezavisna provjera), i
"čovjek prihvata poslovni/rizični ishod" (ljudska potvrda) — vidi
`AGENTS.md` "Podjela odgovornosti".

### 13. PROBE — istraživanje je poseban tip zadatka, ne implementacija

Kad postoji stvarna nepoznanica (nepoznata biblioteka, neprovjerene
performanse, nejasno GUI/OS ponašanje, dilema arhitekture), miješanje
istraživanja i implementacije u isti zadatak proizvodi kod koji je
napola dokaz, napola produkcija — ni dovoljno rigorozan da bude pouzdan
odgovor, ni dovoljno čist da uđe u glavnu granu. `PROBE` (vidi
`AGENTS.md`) razdvaja ih eksplicitno: rad ide na throwaway granu koja se
nikad ne mergea, izlaz je fiksnog oblika (pitanje → dokaz → odluka), a
odluka koju probe donese preživljava i kad se kod baci. Ovo je
komponenta #11 (reprodukuj prije popravke) primijenjena na NEPOZNANICE
umjesto na BUGOVE — isti princip "dokaz prije zaključka", drugi okidač.

---

## Kako početi u novom projektu

1. Kopirati `AGENTS.md` i `CLAUDE.md` (ili samo `CLAUDE.md` ako je jedini
   agent Claude Code) u korijen novog projekta, popuniti sve
   `<<< POPUNI: ... >>>` placeholdere. **Za postojeću kodnu bazu**, ovaj
   korak ne mora biti ručan — `BOOTSTRAP.md` (isti folder) je striktna
   procedura koju agent (Claude, Codex, bilo koji CLI agent) izvršava sam:
   skenira tech stack, strukturu, konvencije i istoriju, popunjava
   placeholdere sa dokazom (fajl/linija) gdje je siguran, i eksplicitno
   flaguje za ljudsku potvrdu sve što je poslovna odluka a ne vidljiva
   činjenica iz koda.
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
  dirati ovaj kod — komponente #1, #3, #6, #7, #11, #13 i dalje vrijede u
  minimalnoj formi (par rečenica prije/poslije; #7, #11 i #13 su posebno
  jeftine navike bez obzira na veličinu tima ili tima od jednog), ali #5
  (project_room), #10 (worktree izolacija) i formalni `docs/CONTEXT.md`
  split su suvišni dok ne zatrebaju. #12 (nezavisan checker) formalno
  zahtijeva drugu stranu — u solo radu se aproksimira "vrati se sutra i
  pročitaj diff kao da je tuđi", nije potpuna zamjena.
- Pravilo palca: uvedi komponentu kad je PRVI PUT stvarno nedostajala
  (agent je "popravio" namjerno pravilo natrag, izgubljena je odluka, dva
  agenta su se sudarila) — ne unaprijed "za svaki slučaj".

---

## Šta je univerzalno, šta je zamjenjivo

**Univerzalno** (prenosi se skoro 1:1 na bilo koji softverski projekat, a
komponente #1, #2, #3, #5, #6, #8, #10, #11, #12, #13 vjerovatno i na
drugi rad sa jasnim "artefaktima" i verzijama — pravni dokumenti, data
pipeline konfiguracije, content sistemi): komponente #1, #2, #3, #5, #6,
#7, #8, #10, #11, #12, #13. Komponenta #7 (samoobjašnjavajući kod) je
specifično za rad SA KODOM — ne prenosi se 1:1 na ne-kodni rad, ali
analogija postoji (kratka bilješka koja linkuje na detaljan zapis,
umjesto dugog inline objašnjenja u samom dokumentu). Komponenta #11
(reprodukuj prije popravke) se na ne-kodni rad prenosi kao "potvrdi da
problem stvarno postoji i razumij ga prije nego predložiš rješenje".
Komponenta #13 (PROBE) se prenosi kao "istraženo nešto nepoznato" —
throwaway istraživanje sa fiksnim zapisnikom odluke, van glavnog
artefakta.

**Zamjenjivo** (princip ostaje, alat/implementacija se mijenja po
projektu): komponenta #4 (code-graph alat vs grep vs IDE), tačan format
memorije u komponenti #2 (fajl-baziran vs vector store vs MCP server),
git hook mehanizam u komponenti #9.

**Projekt-specifično** (ne prenosi se — ovo su primjeri, ne šablon): sva
konkretna poslovna pravila, tech stack, zabrane specifične za jedan
projekat. Ta idu u `<<< POPUNI >>>` sekcije, ne u ovaj METHOD.md.
