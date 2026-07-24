# Runtime logging i `.env` dokumentacija

## Datum

2026-07-24

## Agent

Codex

## Scope

- `services/carinski_dokumenti_service.py`
- `services/knowledge_base/kb_service.py`
- odgovarajuće `dist_client` kopije
- `AGENTS.md`, `CLAUDE.md` i root/dist instalaciona uputstva
- ciljani fallback testovi

## Status izvora

`agent_reports/2026-07-23_samostalna-istraga-tehnicki-dug.md` je aktivan izvor.
Pi nalaz o produkcionim emoji ispisima potvrđen je djelimično: servisni ispisi su
runtime problem, dok su ispisi u dva dijaloga samo `__main__` demo helperi.
Nalaz o zastarjelom `config.ini` je potvrđen i u `AGENTS.md` i u instalacionom
uputstvu.

## GitNexus impact

`pretrazi_dokumente`: LOW, 7 simbola i 2 chat procesa.

Početni impact za `KnowledgeBaseService`: MEDIUM, 17 zavisnosti. Završni
`detect_changes`: HIGH i 10 procesa zbog konzervativnog mapiranja pomjerenih
linija na neizmijenjene metode. HIGH je prihvaćen kao commit gate; plan je u
`project_rooms/2026-07-24_kb-runtime-logging.md`.

Dokumentacione promjene: LOW, bez pogođenih procesa.

## Šta je urađeno

- Svi potvrđeni produkcioni emoji `print()` pozivi u dva servisa zamijenjeni su
  strukturisanim loggerom.
- Dodati su testovi koji potvrđuju DB-error i Groq rerank fallback.
- Kanonska pravila sada upućuju na `.env` i `config/settings.py`.
- Instalaciona uputstva koriste `.env.example`, upozoravaju na zaseban
  `dist_client/.env` i pokreću stvarni `run.py`.
- Root i `dist_client` kopije su usklađene.

## Zašto je urađeno

Direktan emoji ispis može pasti u Windows cp1252 konzoli, dok logger bezbjedno
obrađuje encoding i čuva dijagnostiku. Nepostojeći `config.ini` i `main.py`
usmjeravali su administratore na postupak koji ne može raditi.

## Kako je urađeno

Promijenjen je samo izlazni kanal dijagnostike; poslovna logika, SQL, povratne
vrijednosti i fallbackovi ostali su isti. Dokumentacija je usklađena sa
`.env.example`, `config/settings.py` i postojećim ulaznim fajlom `run.py`.

## Šta nije dirano

- `__main__` demo ispisi u dijalozima i servisnim test helperima
- SQL i Knowledge Base rangiranje
- Groq provider logika
- stvarne `.env` vrijednosti i tajne
- preostali Pi nalazi o shimovima, arhivi `scripts/`, velikim klasama i MCP alatima

## Verifikacija

- ciljani testovi: 17/17 prolazi
- puni testovi: 930 passed, 58 skipped, 5 xfailed
- postojeći neuspjesi: 3 fail + 1 error, isti infrastrukturni problemi van scope-a
- `py_compile` prolazi
- root/dist fajlovi su identični
- `git diff --check` prolazi

## Pronađeni problemi

`docs/INSTALACIJA.md` je pored `config.ini` navodio i nepostojeći `main.py`.
Puni suite i dalje ima benchmark kolekciju bez fixture-a, generisani `dist/torch`
scan, cp1252 čitanje i hardkodovanu Linux XML putanju.

## Konflikti / kontradiktorni izvori

GitNexus je prije izmjene dao MEDIUM, a završnom diff-u HIGH. Završni HIGH je
tretiran kao važeći zbog procedure, iako sadržaj diff-a potvrđuje da su
funkcionalne metode samo pomjerene dodavanjem loggera.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `08631f4` | `fix(logging): ukloni runtime emoji ispise` |
| `f9feb97` | `docs(config): uskladi uputstva sa env konfiguracijom` |

## Rizici / ograničenja

Log poruke na INFO nivou zavise od aktivne logging konfiguracije i možda neće biti
vidljive u svakom režimu, ali više ne ugrožavaju proces direktnim konzolnim ispisom.

## Potreban follow-up

Sljedeći praktični Pi paket je organizacija šest Markdown izvještaja i osam backup
CSV fajlova u `scripts/`, nakon provjere git historije i da ih ništa ne koristi.

## Potrebna korisnička potvrda

Nije potrebna za ovaj paket.
