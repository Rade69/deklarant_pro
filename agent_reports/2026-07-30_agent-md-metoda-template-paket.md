## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`templates/agent-md/` (AGENTS.md, CLAUDE.md, novi METHOD.md/agent_report_template.md/project_room_template.md). Dokumentacioni zadatak, bez izmjena aplikacijskog koda.

## Status izvora
`templates/agent-md/AGENTS.md`/`CLAUDE.md` su postojali od 2026-06-14 (`agent_reports/2026-06-14_univerzalni-agent-md-template.md`, memorija `2026-06-14_univerzalni-agent-md-template.md`) kao generička osnova izvedena iz root fajlova, sa napomenom "NIJE auto-sinhronizovan — treba ručno ažurirati". Status: **zastario** u odnosu na root (nije imao token-disciplinu ni evergreen/history split uveden u prethodnom zadatku istog dana — vidi `agent_reports/2026-07-30_token-disciplina-context-split.md`). Ovim zadatkom ažuriran.

## Impact analiza
Nema — čista dokumentacija/template fajlovi, nema koda.

## Kontekst korišćen
Pročitana oba postojeća template fajla u cijelosti (177 + 289 linija) da se tačno zna šta već postoji prije dopune (izbjeći duplikat sadržaja).

## Šta je urađeno
Korisnik je tražio da se cjelokupan radni tok iz ove sesije (kanonski fajl pravila, slojevit kontekst, project_room/agent_report artefakti, impact-gejt, git higijena, token disciplina, izolacija paralelnih agenata) pretvori u prenosivu metodu koju može naučiti/predati kolegi za rad sa LLM agentima na softverskim projektima. Umjesto novog dokumenta od nule, nadograđen je postojeći `templates/agent-md/` paket:
1. `templates/agent-md/AGENTS.md` — dodana sekcija "Token budget i context disciplina" i pravilo za evergreen/history split kad `docs/CONTEXT.md`-ekvivalent naraste, plus nova opciona sekcija "Paralelni agenti — izolacija working tree-a".
2. `templates/agent-md/CLAUDE.md` — dodane reference na nove fajlove (METHOD.md, oba template fajla) na dva mjesta (intro napomena, Korak 3, "Plan prije izmjene").
3. Novi `templates/agent-md/METHOD.md` — konceptualni dokument: problem koji metoda rješava, 9 komponenti sa ZAŠTO za svaku, kako početi u novom projektu, kad NE primjenjivati (solo/prototip rad), i eksplicitna podjela šta je univerzalno vs zamjenjivo vs projekt-specifično.
4. Novi `templates/agent-md/agent_report_template.md` i `project_room_template.md` — prazni, `<<< POPUNI >>>` fillable fajlovi za direktno kopiranje (dosad je šema bila opisana samo u prozi unutar CLAUDE.md).

## Zašto je urađeno
Korisnik je eksplicitno rekao da je isključivo vezan za kodiranje/gradnju softvera (ne drugi domeni), i tražio kombinaciju: kratak metoda-dokument (za razumijevanje/predaju) + operativni template paket (za stvarnu primjenu). Iskorišten je postojeći `templates/agent-md/` mehanizam umjesto paralelne strukture, jer već postoji i tačno je namijenjen za ovo (samo je bio zastario).

## Kako je urađeno
Ručno pisanje sadržaja (bez skripti — fajlovi su reda veličine stotinjak linija, ne zahtijeva Python split kao ranije za CONTEXT.md). Provjereno grep-om da nema slučajno unesenih ćiriličnih karaktera (jedan takav artefakt se pojavio u `old_string` parametru jednog Edit poziva i bio odbačen od alata prije upisa na disk — nije dospio u fajl).

## Šta nije dirano
- Root `AGENTS.md`/`CLAUDE.md` — ne diraju se ovim zadatkom (već ažurirani prethodnim zadatkom istog dana).
- `agent_reports/`, `project_rooms/`, `docs/context/history.md` iz glavnog projekta — template fajlovi ih referenciraju kao primjer, ne modifikuju.
- Nepovezane promjene koje se pojavljuju u `git status` (GitNexus auto-generisan footer u root `AGENTS.md`/`CLAUDE.md`, `dist_client/ui/*_ui.py`, paralelni Codex commit-ovi "Faktura 3-layer Faza 9-12") — potvrđeno da HEAD nije pomjeren mojim stage/commit korakom (provjereno `git log --oneline -1` prije i poslije).

## Verifikacija
- Grep provjera na Cyrillic raspon karaktera (`[Ѐ-ӿ]`) u svih 5 izmijenjenih/novih fajlova — 0 pogodaka.
- `git diff --stat templates/` prije commit-a — potvrđen očekivan obim (54 + 320 insertions kroz dva commit-a).
- Ručna provjera da je `git status` prije `git add` pokazivao samo namjeravane fajlove (izbjegnut ponovni sweep tuđih nekomitovanih izmjena, isti rizik kao u prethodnom zadatku istog dana).

## Pronađeni problemi
Nema.

## Konflikti / kontradiktorni izvori
Memorija `2026-06-14_univerzalni-agent-md-template.md` tvrdi da template "NIJE auto-sinhronizovan — treba ručno ažurirati" — potvrđeno tačnim (upravo to je urađeno ovim zadatkom). Memorija treba dopunu da odražava ovo ažuriranje (vidi Follow-up).

## Commitovi
| Hash | Poruka |
| --- | --- |
| `14e39e6` | docs(templates): dopuni agent-md metodu sa token disciplinom i fillable predlošcima |

## Rizici / ograničenja
- METHOD.md i template fajlovi su generalizovani na osnovu JEDNOG projekta (deklarant_pro) — nisu testirani na bootstrap-u stvarnog novog projekta. Prva stvarna upotreba će vjerovatno otkriti sitne nedostatke u placeholderima.
- Sadržaj je isključivo na srpskom latinicom (projektna konvencija) — ako je cilj podijeliti metodu sa nekim ko ne čita srpski, treba prevod (nije rađeno, nije traženo).

## Potreban follow-up
- Ažurirati memoriju `2026-06-14_univerzalni-agent-md-template.md` (ili dodati novu) da odražava ovo ažuriranje — uraditi odmah nakon ovog izvještaja.
- Ako i kad korisnik prvi put primijeni template na novom projektu, vrijedi zabilježiti šta je nedostajalo/bilo pogrešno pretpostavljeno.

## Potrebna korisnička potvrda
- Da li je METHOD.md na pravom nivou detalja za "predaju kolegi" (previše/premalo teorije), ili treba kraća verzija za brzo čitanje.
