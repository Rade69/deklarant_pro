## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`AGENTS.md` (root), `templates/agent-md/{AGENTS,CLAUDE,METHOD,UNIVERSAL_CLAUDE,agent_report_template,project_room_template}.md`, `docs/context/history.md` (§117).

## Status izvora
`MATT_AI_ENGINEERING_RADNI_TOK_ARHIVA_V2.md` — korisnikova lična arhiva (55 sekcija), prilagođena Mattovom AI Engineering predavanju i njegovom aihero.dev sistemu (skills, Wayfinder, SPEC/tickets). Tretiran kao vrijedan izvor za review, ne kao autoritativan — dio usvojen sa obrazloženjem, dio odbačen sa obrazloženjem.

## Impact analiza
Nema — dokumentacija, bez koda.

## Reprodukcija prije izmjene
N/A — dokumentacioni zadatak, ne bugfix.

## Kontekst korišćen
Pročitan cijeli eksterni dokument (dostavljen u chat-u). Pročitani u cijelosti svi agent-md fajlovi prije izmjene (isti kao u prethodna 3 zadatka istog dana) da se izbjegne duplikat i tačno se pronađu anchor tačke za umetanje.

## Šta je urađeno
Korisnik je tražio da pročitam dokument i dam mišljenje da li nešto vrijedi uzeti. Kategorisao sam 55 sekcija u tri grupe: (a) već imamo (fresh context, worker≠checker, reprodukcija, risk-tiering, worktree izolacija), (b) zanimljivo ali zahtijeva infrastrukturu koju nemamo (Wayfinder/FlowOS/ticket-DAG, model routing, bounded-context docs), (c) vrijedno uzeti odmah — 9 stavki koje su niskog koštanja i uklapaju se u postojeći fajl-bazirani sistem bez nove infrastrukture. Korisnik je potvrdio "sve 9 odjednom".

Implementirano na sva tri sloja (root AGENTS.md, generički templates/agent-md/ paket, UNIVERSAL_CLAUDE.md single-file varijanta):
1. PROBE — nov tip zadatka, throwaway grana, fiksni izlaz format — nova komponenta #13 u METHOD.md.
2. Facts vs Decisions format za pitanja agenta korisniku.
3. Confirmation gate (Shared Understanding Check) za veće zadatke.
4. Reprodukcija preimenovana u "Reprodukcija i provjera prije rada" — prošireno na feature/enhancement zahtjeve i eksterne predloge koda.
5. Hijerarhija dokaza (8 nivoa, agentovo objašnjenje najslabije) u Definition of Done.
6. Standards review + Spec review kao dvije odvojene ose u Nezavisnoj provjeri.
7. Odbačene opcije — strukturisano polje u agent_report_template.md i project_room_template.md (fizički dodano) + u prozi root AGENTS.md/CLAUDE.md.
8. Zabrana miješanja refactor-a i funkcionalne izmjene u istom zadatku — dodano u Ključne konvencije.
9. ADR/project_room filter od tri pitanja — omogućava project_room i ispod HIGH/CRITICAL praga.

## Zašto je urađeno
Direktan zahtjev korisnika, sa eksplicitnom potvrdom obima (sve 9 stavki odjednom) prije implementacije.

## Kako je urađeno
Ručne, ciljane Edit izmjene na svakom od 7 fajlova (root AGENTS.md + 6 template fajlova), redom: rename/proširenje "Reprodukcija" sekcije, nova PROBE sekcija, Facts/Decisions+Confirmation gate u "Obavezno prije kodiranja", Evidence hijerarhija u DoD, Standards+Spec split u Nezavisnoj provjeri, refactor-separacija u Ključnim konvencijama, ADR filter + Odbačene opcije u Plan prije izmjene / project_room_template.md / agent_report_template.md, nova METHOD.md komponenta #13 sa ažuriranjem sve numeričke reference (10→11 ideja, 12→13 komponenti).

## Šta nije dirano
Wayfinder/decision-DAG/FlowOS, model routing po tipu zadatka, bounded-context `context.md` po domenu — svjesno preskočeno (obrazloženje u "Pronađeni problemi"/ranijem tekstu razgovora, ne u ovom fajlu). `docs/CONTEXT.md` (evergreen sekcije 1-14) — netaknuto, ovaj zadatak je isključivo o agent-md procesu.

## Verifikacija
Grep provjera na Cyrillic raspon karaktera u svih 7 fajlova — 0 pogodaka. Grep provjera da je stara referenca "Reprodukcija prije bugfixa" (preimenovana) uklonjena iz svih mjesta koja su je citirala (0 preostalih pogodaka u root AGENTS.md). Provjera numeracije METHOD.md komponenti (1-13, bez rupa/duplikata). **Bitno**: pri `git add`/`git status` prije commit-a otkriven tuđi (Codex) WIP fajl već stažovan u indexu (`agent_reports/2026-07-30_faktura-cleanup-faza-d3-...md`) — nije dirano; commit izveden eksplicitnim pathspec-om (`git commit -- <fajlovi>`) da se izbjegne povlačenje tog sadržaja u ovaj commit. HEAD provjeren prije/poslije, bez sudara.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik, čista dokumentacija.

## Pronađeni problemi
Otkriven tuđi staged (ne samo nekomitovan) fajl u indexu — malo drugačiji oblik istog rizika od ranijeg sudara istog dana (tada je bio nekomitovan WIP u working tree-u, sad je bio VEĆ stažovan). Rješenje (`git commit -- <pathspec>`) je čistije od prethodnog pristupa (koji je zahtijevao provjeru diff-a i selektivan `git add`) — vrijedi ovo zapamtiti kao standardni alat za ovaj scenario.

## Odbačene opcije
- Opcija: Unstage-ovati Codex-ov fajl (`git restore --staged`) prije svog `git add`-a.
- Zašto je razmatrana: Jednostavnije mentalno pratiti "index sadrži samo moje stvari".
- Zašto je odbačena: Rizik da to poremeti Codex-ov tok ako je usred pripreme svog commit-a — unstage tuđeg rada bez razloga je destruktivna akcija po duhu "Paralelni agenti" pravila, čak i ako je tehnički reverzibilna.
- Kada odluku ponovo otvoriti: Ako se pokaže da eksplicitni pathspec commit ima neki nedostatak (npr. ne radi dobro sa pre-commit hookovima koji očekuju pun staged snapshot).

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `496416f` | docs(agents): dodaj PROBE, Facts/Decisions, evidence hijerarhiju, ADR filter |

## Rizici / ograničenja
Root `AGENTS.md` je sada 698 linija (bio 438 prije četiri zadatka danas) — nastavlja rasti ka istom bloat-problemu identifikovanom ranije istog dana za `docs/CONTEXT.md`. Sadržaj je i dalje evergreen (nema dated materijala za izdvajanje), ali dužina fajla samo po sebi postaje relevantan faktor za token trošak svake sesije. Vrijedi razmotriti da li root AGENTS.md treba svoju "Sekcija 3"-ekvivalentnu podjelu (npr. izdvajanje GitNexus auto-generisanog footera, ili konsolidacija sličnih sekcija) prije sljedeće runde dopuna.

## Potreban follow-up
- Isprobati novododane sekcije (posebno PROBE i Facts/Decisions format) na stvarnom sljedećem zadatku.
- Razmotriti da li root AGENTS.md treba redukciju/reorganizaciju prije daljeg rasta.

## Potrebna korisnička potvrda
Nema neposredno.
