## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`templates/agent-md/` — sva 6 fajla (AGENTS.md, CLAUDE.md, METHOD.md, BOOTSTRAP.md, agent_report_template.md, project_room_template.md). Dokumentacija, bez koda.

## Status izvora
Korisnik je podijelio `visi_nivo_agent_potpomognutog_softverskog_inzenjerstva.md` — dokument koji je Codex napravio analizirajući naš `templates/agent-md/` paket (iz prethodna dva zadatka istog dana) i predložio nadogradnju. Ocijenjeno kao aktivan, koristan izvor — dio prijedloga usvojen (identifikovane stvarne rupe), dio namjerno preskočen (restatuje postojeće).

## Impact analiza
Nema — dokumentacija.

## Reprodukcija prije izmjene
N/A — dokumentacioni zadatak, ne bugfix.

## Kontekst korišćen
Pročitan cijeli dopisani dokument (korisnikov paste, ~17 sekcija) i trenutno stanje svih 6 template fajlova prije izmjene (da se izbjegne duplikat i da se novi sadržaj uklopi u postojeću numeraciju/strukturu).

## Šta je urađeno
Iz Codex-ovog dokumenta izabrano 5 stavki ocijenjenih kao stvarna nadogradnja (ne restatement postojećeg), sve implementirane kao dopune postojećih fajlova:
1. **Reprodukcija prije bugfixa** — nova sekcija u `AGENTS.md`, novo polje u `agent_report_template.md`, referenca u `CLAUDE.md` Korak 3 listi.
2. **Definition of Done po tipu promjene** (GUI/parseri/dokumenti/baza/performanse/sigurnost) — nova sekcija u `AGENTS.md`.
3. **Podjela odgovornosti** (agent samostalno / samo predlaže / checker potvrđuje / čovjek odlučuje) — nova tabela u `AGENTS.md`.
4. **Nezavisna provjera (worker≠checker≠čovjek)** — nova sekcija u `AGENTS.md`, novo polje u `agent_report_template.md`, nova polja u `project_room_template.md` (Plan verifikacije, Rollback/oporavak, Nezavisni checker), reference u `CLAUDE.md`.
5. **BOOTSTRAP.md**: obavezan `git status --short` prije skeniranja + eksplicitna ignore-lista generisanih/vendor foldera.

`METHOD.md` dopunjen sa dvije nove komponente (#11 Reprodukuj prije popravke, #12 Worker≠checker≠čovjek) — "Deset komponenti" → "Dvanaest komponenti", sve numeričke reference u fajlu (Kako početi, Kada NE primjenjivati, Šta je univerzalno) ažurirane da odgovaraju.

Ojačano i postojeće pravilo o paralelnim agentima u `AGENTS.md` — eksplicitna zabrana širokog `git add -A`/`git add .` u dijeljenom working tree-u (direktna posljedica sudara sa paralelnim Codex agentom ranije istog dana).

## Zašto je urađeno
Korisnik je tražio da se dokument pregleda i identifikuje šta je stvarno korisno. Najveći nalaz: naš postojeći sistem nije formalno razdvajao "agent tvrdi da je gotovo" od "neko je to nezavisno dokazao" — pravi propust u sistemu čiji je cijeli princip "dokaz prije tvrdnje" (BOOTSTRAP.md evidence-first pristup). `git status` fix u BOOTSTRAP-u je direktna posljedica stvarnog incidenta ranije istog dana (agent_reports/2026-07-30_token-disciplina-context-split.md, "Pronađeni problemi").

## Kako je urađeno
Ručne, ciljane izmjene (Edit tool) na tačnim mjestima u svakom fajlu — bez skripti (fajlovi su reda stotinjak-dvjesto linija). Numeracija komponenti u METHOD.md provjerena grep-om (`^### \d+\.`) da potvrdi kontinuitet 1-12 bez rupa/duplikata nakon svih izmjena.

## Šta nije dirano
Namjerno preskočeno iz Codex-ovog dokumenta (restatuje postojeće ili je lični coaching sadržaj, ne repo artefakt): 10-koračni dnevni workflow (sekcija 8), lično tehničko znanje/debugging-kao-nauka/git vještine (sekcija 10), mjesečno učenje iz agent_reports + metrike (sekcija 12), 90-dnevni plan (sekcija 14), anti-patterni lista (sekcija 15), checklist (sekcija 16) — sve već implicitno pokriveno postojećim `METHOD.md`/`AGENTS.md` ili je van dometa repo-template fajla. `templates/visi_nivo_agent_potpomognutog_softverskog_inzenjerstva.md` (untracked fajl sa originalnim Codex dokumentom, zatečen u working tree-u) nije dirano niti commitovano — nije jasno da li korisnik želi da to bude trajan dio repoa.

## Verifikacija
Grep provjera na Cyrillic raspon karaktera u svih 6 fajlova — 0 pogodaka. Grep provjera numeracije komponenti u METHOD.md — potvrđen kontinuitet 1-12. Ručna provjera da `git status`/`git add` prije commit-a sadrži samo namjeravanih 6 fajlova (HEAD provjeren prije/poslije — pomjeren je paralelnim Codex commit-ima kao i ranije danas, ali bez sudara sa mojim izmjenama).

## Pronađeni problemi
Nema.

## Konflikti / kontradiktorni izvori
Nema — Codex-ov dokument je tretiran kao validan predlog za review, ne kao autoritativan izvor koji se slijepo prihvata; dio je usvojen, dio odbačen sa obrazloženjem iznad.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: dokumentacioni zadatak niskog rizika (LOW — nema koda, nema runtime uticaja), ne zadovoljava kriterijume za obavezni checker iz upravo dodate sekcije "Nezavisna provjera" u `AGENTS.md`.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `198ba12` | docs(templates): dodaj worker/checker razdvajanje, reprodukciju prije bugfixa, DoD po tipu promjene |

## Rizici / ograničenja
- Kao i ranije, cijeli `templates/agent-md/` paket nije testiran na stvarnom bootstrap-u projekta — akumulira se sve više neverifikovanog sadržaja (METHOD.md sad ima 12 komponenti, AGENTS.md znatno duži nego prije tri zadatka). Vrijedi uskoro stvarno isprobati na jednom pravom projektu prije daljeg dodavanja.
- Codex-ov predloženi `<<< POPUNI: agent nije siguran >>>` stil za DoD sekciju je generički (primjeri kategorija, ne konkretna pravila) — svaki novi projekat će morati stvarno popuniti/obrisati kategorije koje mu ne odgovaraju.

## Potreban follow-up
Prva stvarna primjena cijelog paketa (BOOTSTRAP + AGENTS/CLAUDE + template fajlovi) na novom ili postojećem projektu — do sada je sve rađeno "u apstraktnom" na osnovu iskustva sa deklarant_pro, bez provjere da li placeholderi/sekcije stvarno rade kad ih neko prati korak-po-korak.

## Potrebna korisnička potvrda
Da li `templates/visi_nivo_agent_potpomognutog_softverskog_inzenjerstva.md` (originalni Codex dokument, trenutno untracked) treba ostati u repou kao istorijski izvor/referenca, ili obrisati sad kad je sadržaj apsorbovan u template fajlove.
