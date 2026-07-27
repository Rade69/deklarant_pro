# Popravka wiring gapova u Agent V2 implementaciji (feature/agent-v2)

## Datum

2026-07-27

## Agent

Claude (Sonnet 5)

## Scope

- `gui/tabs/agent/services/chat_intent_handler.py` — dispatch za `prikazi`/`provjeri`,
  Tool Use routing za V2 put, VALIDATE/INVOICE/HEADER wiring, kritičan AuditEvent bug
- `gui/tabs/agent/services/xml_workflow_service.py` — `_izvezi_xml` readiness gate
- `services/agent/validation/xml_readiness_service.py` — stvaran `_xml_preflight`
- `services/agent/validation/renderer.py` — `render_xml_readiness_html`, HTML escape
- `services/agent/workflow/declaration_workflow_state.py` — 10 stvarnih kapija
- `services/agent/workflow/declaration_workflow_service.py` — **nov fajl**, orkestrator
- `scripts/sync_dist_client.py` — CRLF/LF normalize bug
- `tests/unit/test_agent_v2_wiring_fixes.py` — **nov fajl**, 23 testa
- `.env` (negitovan) — `DB_HOST` promijenjen na dostupan server (192.168.100.154)
- `dist_client/` mirroring za sve gore navedeno (namjerno ograničen scope — vidi ispod)

Grana: `feature/agent-v2` (worktree `.worktrees/agent-v2`). Nezavisna od `windows`.

## Status izvora

| Izvor | Status |
| --- | --- |
| Moj prethodni review (ova konverzacija) | osnova za Nalaze 1-4 ispod |
| `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` (v2.1) | referentan za sve arhitektonske odluke |
| Faza 1-10 implementacija (drugi agent/sesija) | servisi kvalitetni iznutra, ali nepovezani — potvrđeno u ovoj sesiji |
| GitNexus indeks | ne pokriva `feature/agent-v2` worktree (samo glavna grana i `codex-faktura-toolbar`) — impact analiza rađena protiv glavnog indeksa za dva simbola koja postoje identično na obje grane |

## GitNexus impact

`_puna_auto_pipeline` i `_izvezi_xml` (najveći rizik — najviše korišteni,
najosjetljiviji na regresiju) provjereni PRIJE izmjene, protiv glavnog
indeksa (identičan kod na obje grane u trenutku provjere):

- `_puna_auto_pipeline`: **LOW** (1 direktan pozivalac — `ImportPipelineService.puna_auto_pipeline` wrapper)
- `_izvezi_xml`: **LOW** (1 direktan pozivalac — `XmlWorkflowService.izvezi_xml` wrapper)

Oba su dobila samo DODATNE pozive na početku funkcije (readiness/orkestracija),
bez izmjene postojećeg ponašanja za already-passing putanje — nisam mijenjao
signature na način koji bi slomio jedinog pozivaoca (dodao opcioni
`confirm_fn=None` parametar). `project_room` nije napravljen jer je rizik
ostao LOW i nakon izmjene (plan §23: project_room obavezan samo za HIGH/CRITICAL).

`gitnexus_detect_changes()` nije pokrenut — ovaj worktree nije zaseban
indeksiran repo u GitNexus-u (`list_repos` vraća samo `deklarant_pro` glavnu
putanju i `codex-faktura-toolbar` worktree), pa bi rezultat bio besmislen
(uporedio bi git stanje glavnog repoa, ne ovog worktree-a). Alternativa
(ručna verifikacija): pun test suite (1263 passed) + `py_compile` na svim
izmijenjenim fajlovima + ručno praćenje svakog poziva kroz kod.

## Šta je urađeno

Četiri originalno identifikovana nalaza popravljena, plus jedan kritičan
dodatni bug otkriven pri pisanju testova, plus jedan pred-postojeći bug u
sync skripti:

1. **Nalaz 1 (live regresija)** — `_execute_tool` elif-lanac nije imao granu
   za `"prikazi"`/`"provjeri"`. Dodani `_dispatch_prikazi`/`_dispatch_provjeri`
   koji mapiraju `target` na postojeće snapshot funkcije i nove review servise.
2. **Nalaz 2** — `_handle_message_v2` je za `ANALYZE`/`REQUEST_CHANGE`/`PROPOSE`/
   `RUN_WORKFLOW`/`EXPORT`/`OTHER` pozivao plain chat bez `tools=`. Izdvojen
   `_dispatch_via_tool_use()` (dijeljen sa starim putem) koji stvarno šalje
   poruku kroz `ToolDispatcherWorker`.
3. **Nalaz 3** — Faza 7 nije imala izvršiv kod-put za "jedna komanda vodi
   cijeli proces". `declaration_workflow_state.py` prošireno na 10 stvarnih
   kapija; nov `declaration_workflow_service.py` orkestrira
   `_puna_auto_pipeline` (ponovo korišten) + preostale provjere + finalni
   izvoz. `RUN_WORKFLOW`/`EXPORT` namjere u `_handle_message_v2` sad direktno
   pozivaju orkestrator odn. `izvezi_xml`.
4. **Nalaz 4** — `_xml_preflight` je samo provjeravao da `items` nije prazan
   (`export_to_xml` uvezen, nikad pozvan). Sad poziva `AsycudaXMLBuilder.build()`
   nad JSON round-trip kopijom drafta. `_izvezi_xml` sad poziva
   `provjeri_spremnost_za_xml()` prije izvoza, odbija na `BLOCKED`, traži
   eksplicitnu potvrdu (injektabilan `confirm_fn`), i razlikuje otkazivanje
   od greške.
5. **Dodatni kritičan bug (otkriven pri testiranju)** —
   `_audit_routing("switch", agent_v2=agent_v2, ...)` i
   `_audit_routing("v2_resolver", action=..., target=..., confidence=...)`
   prosljeđuju kwargs koje `AuditEvent` ne prihvata → `TypeError` na SVAKI
   poziv `_handle_message`, bez obzira na kill-switch. Popravljeno kroz
   `extra={}`.
6. **Pred-postojeći bug u `sync_dist_client.py`** — `normalize()` nije
   normalizovao CRLF/LF, pa je svaki fajl gdje root koristi LF a dist_client
   CRLF bio lažno prijavljen kao "stvarna razlika". Popravljeno.

## Zašto je urađeno

Korisnik je eksplicitno tražio da se poprave svi nalazi iz prethodnog
pregleda te grane. Dodatni AuditEvent bug i sync-skripta bug nisu bili dio
originalnog pregleda — otkriveni su tek pri pisanju testova (AuditEvent) i
pri pokušaju sinhronizacije dist_client-a (normalize) — oba direktno
blokiraju stvari koje sam upravo popravio (AuditEvent bug bi spriječio da
ijedna od popravki 1-4 ikad bude dostignuta u pravoj aplikaciji), pa su
popravljeni u istom zadatku.

## Kako je urađeno

Za svaku popravku: čitanje tačnog postojećeg koda prije izmjene, provjera
signatura servisa koje pozivam (`provjeri_fakturu`, `provjeri_naimenovanja`,
`provjeri_zaglavlje`, `provjeri_usklađenost_tabova`, `provjeri_spremnost_za_xml`),
ručna end-to-end provjera kroz Python REPL prije pisanja formalnih testova
(prazan draft → zaustavlja se na `files_imported`; kompletan draft → prolazi
svih 10 kapija i stiže do izvoza), zatim formalni pytest testovi.

`.env` je izmijenjen (DB_HOST → 192.168.100.154, po korisnikovoj instrukciji
da je server tu dostupan) — potvrđeno konekcijom (`SELECT 1`) prije bilo kakvog
daljeg rada; ovo je riješilo 10 prethodno-neuspješnih DB-connectivity testova
kao nuzgredni efekat (nepovezano sa Agent V2 kodom).

Za `declaration_workflow_service.py`: donesena eksplicitna arhitektonska
odluka da se NE radi puna inverzija zavisnosti `_puna_auto_pipeline`
(uklanjanje `QMessageBox`/`processEvents()`) u ovom zadatku — to je veliki,
rizičan zahvat koji plan §18 opisuje kao "polovina obima Faze 7" i eksplicitno
traži poseban project_room prije diranja. Umjesto toga, orkestrator
PONOVO KORISTI `_puna_auto_pipeline` kao provjerenu "prvu polovinu" i dodaje
nedostajuću "drugu polovinu" (zaglavlje → cross-tab → xml preflight → izvoz).

Za `dist_client` sync: prvi `--apply` je (prije nego što sam to shvatio)
sinhronizovao **preko 330 fajlova nepovezanih sa Agent V2** (pred-postojeći
drift akumuliran tokom istorije projekta — dist_client je kasnio za root-om
za stotine fajlova i prije ovog zadatka). To je namjerno vraćeno
(`git checkout --` za modifikovane, `rm` za novokreirane) da bi commit ostao
skoncentrisan na stvarni scope zadatka — sinhronizovano je samo 7 fajlova
koja sam ja mijenjao/kreirao. Širi drift ostaje, dokumentovan u
`docs/CONTEXT.md` §71, kao odluka za korisnika.

## Šta nije dirano

- `_puna_auto_pipeline` sam kod (samo pozvan iznova, ne izmijenjen) —
  namjerna odluka, vidi gore.
- `AgentPlan`/`PlanValidator`/`KANONSKI_WORKFLOW` (`agent_plan.py`,
  `plan_validator.py`) — validiraju se ispravno (provjereno), ali ostaju
  nepovezani na generički izvršilac; orkestrator ih ne koristi (pragmatičan
  direktan pristup umjesto generičkog plan-interpretera — vidi "Rizici" ispod).
- `automation_levels.py` — i dalje orphaned (nijedan pozivalac van sopstvenih
  testova); nije bio dio moja četiri nalaza, nisam ga povezivao.
- Preko 330 nepovezanih `dist_client` fajlova sa pred-postojećim drift-om —
  namjerno vraćeno na prethodno stanje, vidi gore.
- `ui/naimenovanja_tab_OPTIMIZED_ui.py`, `ui/zaglavlje_tab_ui.py` — tuđe
  neuvezane izmjene затечене na početku sesije, ostavljene netaknute.
- Nijedna poslovna validaciona pravila (tarifni format, Rub.31 limit,
  grupisanje po 4 ključa...) — sve popravke su isključivo wiring/integracija.

## Verifikacija

- `py_compile` na svim izmijenjenim fajlovima — čist.
- Ručna end-to-end provjera kroz Python (bez pytest) prije formalnih
  testova, za `declaration_workflow_state`/`declaration_workflow_service`
  i `_xml_preflight`/`_izvezi_xml` (prazan draft, kompletan draft, odbijena
  potvrda) — svi ishodi kako je očekivano.
- **23 nova testa** u `test_agent_v2_wiring_fixes.py` — svi zeleni.
- **Pun test suite: 1263 passed, 72 skipped, 5 xfailed, 0 failed** (prije
  popravki: 1230 passed + 10 failed zbog DB nedostupnosti — .env fix + moje
  popravke zajedno daju čist rezultat, nema regresija).
- `dist_client` sync dry-run nakon svih popravki: **0 stvarnih razlika** za
  7 fajlova u scope-u ovog zadatka (preostale 3 razlike su pred-postojeći,
  nepovezan drift — `importers/packing_list_parser.py`,
  `importers/vendors/sumaprom/sumaprom_excel_parser.py`,
  `services/agent/chat/tool_policy.py` — namjerno ostavljene).

## Pronađeni problemi

Svi navedeni u "Šta je urađeno" (1-6). Dodatno, **lažno pozitivan zaključak
koji sam izbjegao**: prvi `sync_dist_client.py --apply` je izgledao kao da
je "sve popravio" (539 fajlova kopirano), ali bi bez pažljivog pregleda
git statusa rezultovao ogromnim, nepreglednim commitom koji dira stotine
nepovezanih modula. Provjereno prije commit-a, scope svjesno ograničen.

## Konflikti / kontradiktorni izvori

| Konflikt | Tretman |
| --- | --- |
| Project room za `_puna_auto_pipeline`/`declaration_workflow_service` nije zahtijevan jer je impact LOW | Provjereno protiv glavnog GitNexus indeksa (identičan kod u trenutku provjere) — nije retroaktivno nevažeće ako se `_puna_auto_pipeline` kasnije mijenja u punoj inverziji zavisnosti (tada bi impact vjerovatno bio HIGH/CRITICAL i project_room bi bio obavezan) |
| Moj prethodni review nije predvidio AuditEvent bug niti sync-skripta bug | Oba popravljena u istom zadatku jer direktno blokiraju/potkopavaju stvari koje sam upravo radio; dokumentovano zasebno u CONTEXT.md §71 |

**Potrebna korisnička potvrda:** DA — vidi zadnju sekciju.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `e4be596` | `fix(agent-v2): povezi prikazi/provjeri/RUN_WORKFLOW/EXPORT i popravi AuditEvent pad` |
| `cd4faee` | `feat(agent-v2): kapije pozivaju stvarne review servise + orkestrator za RUN_WORKFLOW` |
| `fa06acd` | `fix(agent-v2): xml_preflight stvarno gradi XML, izvezi_xml provjerava readiness` |
| `3bf577b` | `fix(scripts): sync_dist_client normalize() ne prepoznaje CRLF/LF kao istovjetno` |
| `8abf3bb` | `test(agent-v2): testovi za popravke wiring gapova` |
| (ovaj) | `docs(report): evidentiraj popravku wiring gapova` |

## Rizici / ograničenja

- **`declaration_workflow_service.py` NE radi punu inverziju zavisnosti
  `_puna_auto_pipeline`** — i dalje koristi `QMessageBox`/`processEvents()`
  iznutra. Orkestrator radi ispravno, ali dio "prve polovine" ostaje vezan
  za GUI thread na isti način kao prije. Ovo je svjesna, dokumentovana
  odluka (vidi "Kako je urađeno"), ne previd.
- **`AgentPlan`/`PlanValidator` ostaju nepovezani na generički izvršilac** —
  orkestrator koristi direktan, pragmatičan pristup umjesto generičkog
  plan-interpretera. Ako se kasnije poželi generički PlanStep executor
  (za dinamičke, ne samo "prepare declaration" ciljeve), taj rad tek treba
  uraditi.
- **Redoslijed ordinala u `items_review_service`/`invoice_review_service`
  za `scope="row"`** — koriste `ordinals` kao 0-indeksirane pozicije u listi
  (`items[i]`), dok korisnik vjerovatno misli na 1-indeksiran Rb. broj.
  Nijedan postojeći test ne pokriva ovaj put — nisam ga mijenjao (van scope-a
  četiri nalaza), ali vrijedi provjeriti prije oslanjanja na "provjeri
  naimenovanje 5" kroz chat.
- **`automation_levels.py` (Faza 8, 3 režima) ostaje orphaned** — nije bio
  dio mojih nalaza, nisam ga povezivao. Trenutno postoji samo Režim C
  ("Priprema do XML-a") implicitno kroz orkestrator, bez formalnog
  razlikovanja režima.
- Preko 330 nepovezanih `dist_client` fajlova i dalje kasne za root-om —
  namjerno ostavljeno, dokumentovano u CONTEXT.md §71.

## Potreban follow-up

- Odluka korisnika: da li raditi širi `dist_client` resync (330+ fajlova)
  kao zaseban zadatak.
- Ako se ikad zatraži puna inverzija zavisnosti `_puna_auto_pipeline`:
  obavezan project_room prije izmjene (očekivan HIGH/CRITICAL impact).
- `automation_levels.py` — odlučiti da li ostaje neiskorišten ili se
  eksplicitno povezuje kao Faza 8 rad.
- Provjeriti ordinal indeksiranje u review servisima za `scope="row"` prije
  oslanjanja na taj put u produkciji.

## Potrebna korisnička potvrda

1. **`.env` DB_HOST je promijenjen lokalno** (negitovan fajl) — potvrdi da
   je 192.168.100.154 trajno ispravna adresa, ne privremena.
2. **Odluka o širem `dist_client` drift-u** (330+ fajlova) — riješiti sada
   kao poseban zadatak, ili ostaviti za kasnije?
3. **Da li je prihvatljivo da `declaration_workflow_service.py` i dalje
   zavisi od `_puna_auto_pipeline`-ovog postojećeg `QMessageBox`/
   `processEvents()` ponašanja** za prvu polovinu procesa, umjesto pune
   inverzije zavisnosti — ili se to sada želi uraditi kao poseban,
   veći zadatak?
