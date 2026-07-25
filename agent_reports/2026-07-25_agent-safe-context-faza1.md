# Faza 1: AgentSafeContext schema + AgentContextAdapter

## Datum
2026-07-25

## Agent
Claude (Sonnet 5)

## Scope
- `services/agent/chat/safe_context_schema.py` (novo) + `dist_client/` mirror
- `services/agent/chat/context_adapter.py` (novo) + `dist_client/` mirror
- `tests/unit/test_agent_context_adapter.py` (novo, 8 testova)
- `docs/CONTEXT.md` (§62)
- `project_rooms/2026-07-25_agent-safe-input-schema-plan.md` (ažuriran ranije, §7 odgovor)

## Status izvora
Prva faza plana iz `project_rooms/2026-07-25_agent-safe-input-schema-plan.md`
(napisan u prethodnom koraku iste sesije, nakon poređenja korisnikovog
dokumenta "Kontrolisana podatkovna granica za AI agente" sa stvarnim stanjem
aplikacije — vidi `docs/CONTEXT.md` §61). Korisnik eksplicitno odabrao
"Faza 1" preko AskUserQuestion (opcija "Da, počni Fazu 1") nad alternativama
"samo plan" i "prvo odgovori na preostala pitanja".

## GitNexus impact
- Nove datoteke, nemaju postojećih pozivalaca — `detect_changes(scope=staged)`
  prije commita: risk **LOW**, 0 affected. Tačno kako plan §6 Faza 1
  predviđa ("BEZ dirat postojeći chat_worker.py... nula rizika za postojeći
  kod").

## Šta je urađeno
1. `safe_context_schema.py` — Pydantic modeli: `DraftSummary` (agregati,
   `Field(ge=0)` validacija), `PartnerInfo` (`name: str | None`, `masked: bool`),
   `AttachedDocument`, `DeclarationHeaderSummary`, `AgentSafeContext`
   (kompozitni model koji spaja sve zone).
2. `context_adapter.py` — `AgentContextAdapter`:
   - `build_partner_info()` — JEDINA tačka maskiranja partner imena
     (izvoznik/primalac/deklarant), `name=None` ako `allow_sensitive=False`.
   - `build_draft_summary(invoice_lines)` — staticmethod, preslikava TAČNU
     formulu iz `ChatWorker._build_context()` (bez_tarife/bez_zemlje/
     sa_povlasticom/ceka_eur1/zemlja_distribucija).
   - `build_header()` — preslikava preostala (ne-partner) polja iz
     `ChatWorker._build_zaglavlje_zone()`, uključujući `prilozene_isprave`
     (Rb.44) BEZ maskiranja (korisnička potvrda).
3. 8 testova pokrivaju: maskiranje uključeno/isključeno/prazna imena,
   tačnost agregatnih brojeva (uključujući "ceka_eur1" edge case — stavka
   sa izjavom o porijeklu se NE računa kao "čeka EUR1"), `None` draft,
   priložene isprave bez maskiranja, Pydantic shema validacija (negativan
   broj stavki odbijen sa `ValidationError`).

## Zašto je urađeno
Korisnik je eksplicitno odabrao da počne implementaciju plana, ograničeno
na Fazu 1 (izolovani novi fajlovi, bez dirat postojeći `ChatWorker`) —
ostala pitanja o obimu (Faza 4 vs 5, TariffLLMWorker migracija, prioritet
u odnosu na druge otvorene stavke) ostaju otvorena za kasniju odluku.

## Kako je urađeno
- Formule u `build_draft_summary`/`build_header` prepisane RIJEČ PO RIJEČ
  iz postojećeg `chat_worker.py` koda (linije 200-221 za Zone A, 481-519
  za ne-partner Zone B2 polja) da bi Faza 2 mogla direktno zamijeniti bez
  promjene ponašanja — nije "reizmišljena" logika, čist prepis u novi oblik.
- `prilozene_isprave` polje dodano SAD (plan ga je ostavio otvorenim u §7)
  jer je korisnik potvrdio da brojevi dokumenata nisu osjetljivi — uključeno
  bez ikakvog maskiranja, za razliku od partner imena.
- Testovi pisani PRIJE provjere GitNexus impact-a pošto su nove datoteke —
  impact provjeren na `scope=staged` (ne `scope=all`) jer `scope=all` na
  potpuno novim, još necommitovanim fajlovima vraća "No changes detected"
  (GitNexus prati git diff, ne fajlove van staging area-e).

## Šta nije dirano
- `ChatWorker` (`_build_context`, `_build_session_zone`, `_build_zaglavlje_
  zone` i ostale zone) — POTPUNO netaknut. Postojeći masking fix iz §61
  (commit `223d543`) ostaje jedini aktivni mehanizam maskiranja u produkciji;
  novi adapter se NIGDJE još ne poziva.
- `TariffLLMWorker` — nije migriran, nije bilo u opsegu Faze 1.
- `knowledge`/`tariff_val`/`declarations` zone — ostaju van scope-a i
  budućih faza po planu (§6 Faza 5, najveći posao, najmanja hitnost).

## Verifikacija
- `python -m py_compile` na sva 4 fajla (root + dist_client × 2) — OK.
- 8 novih testova: svi prolaze.
- Pun test suite: 1139 passed (bilo 1131 prije ovog koraka, +8 novih).
  10 DB-backed testova (`test_decision_characterization.py`) i dalje failed
  — PostgreSQL server (192.168.100.154) nedostupan, korisnik potvrdio da
  će biti dostupan sutra ujutru — POZNATO stanje, nije regres izazvan ovim
  zadatkom (ovi fajlovi nemaju nikakve veze sa tariff_mapping_service DB
  testovima).
- `gitnexus_detect_changes(scope=staged)`: risk LOW, 0 affected.
- Root vs dist_client diff nakon mirroringa: prazan (identični fajlovi).

## Pronađeni problemi
Nema novih.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `4eb88d0` | feat(agent): Faza 1 AgentSafeContext schema + AgentContextAdapter |

## Rizici / ograničenja
- Novi kod trenutno NEMA efekat na produkciono ponašanje (ništa ga još ne
  poziva) — ovo je namjerno (Faza 1 = priprema, ne migracija), ali znači
  da propust popravljen u §61 i dalje zavisi ISKLJUČIVO od ručnog fixa u
  `ChatWorker`, ne od ovog novog sloja, dok se Faza 2 ne izvrši.
- `build_draft_summary`/`build_header` su ručni prepisi postojeće logike —
  ako se original u `ChatWorker` promijeni prije Faze 2 migracije, ova
  dva mjesta mogu se razići (duplicirana logika dok migracija ne završi).

## Potreban follow-up
- Faza 2 (migracija `_build_session_zone`/`_build_zaglavlje_zone` da
  koriste `AgentContextAdapter`) — zaseban zadatak, čeka odluku o obimu.
- Otvorena pitanja iz plana §7 (Faza 4 vs 5, TariffLLMWorker migracija,
  prioritet) i dalje neodgovorena.

## Potrebna korisnička potvrda
- Da li i kada nastaviti na Fazu 2, ili sačekati odgovore na preostala
  pitanja iz plana prvo.
