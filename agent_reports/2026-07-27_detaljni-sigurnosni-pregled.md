# Detaljni sigurnosni pregled aplikacije

## Datum

2026-07-27

## Agent

Codex (GPT-5)

## Scope

- `docs/SECURITY_AUDIT_2026-07-27.md`
- grana `feature/agent-v2`
- Agent V2 wiring report i sigurnosno relevantni tokovi
- read-only provjera PostgreSQL servera `192.168.100.154`

## Status izvora

| Izvor | Status |
| --- | --- |
| `agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md` | aktivan |
| `docs/CONTEXT.md` | aktivan |
| kod grane `feature/agent-v2` | aktivan za procjenu |
| `windows` grana | produkcijska osnova, ali nema sve Agent V2 izmjene |
| GitNexus FTS indeks | degradiran; dopunjen direktnim pregledom |

## GitNexus impact

Nema izmjene Python simbola. Dodani su samo dokumentacioni fajlovi, pa
pre-change impact nad simbolom nije primjenjiv. GitNexus query je upozorio da
FTS indeksi nedostaju; zato je arhitekturna provjera dopunjena direktnim
pregledom koda, branch diff-a i izvještaja.

## Šta je urađeno

Kreiran je detaljan sigurnosni pregled sa modelom prijetnji, 11 potvrđenih ili
otvorenih nalaza, Agent V2 poboljšanjima, prioritetnim planom sanacije,
kriterijima zatvaranja i predloženim sigurnosnim release gate-om.

Read-only provjera PostgreSQL servera potvrdila je aktivan TLS,
`scram-sha-256` i PostgreSQL 16, ali i kritičan nalaz da aplikacijski nalog
ima `SUPERUSER` privilegiju. Aktivna DB lozinka nije prikazana niti upisana u
izvještaj; evidentirana je samo njena dužina i sigurnosna procjena.

## Zašto je urađeno

Prethodni pregled je napravljen prije čitanja novog Agent V2 wiring izvještaja
i bez dostupnog DB servera. Novi podaci mijenjaju procjenu u oba smjera:
Agent V2 je poboljšao integritet XML workflow-a, ali stvarna DB provjera je
otkrila kritičan infrastrukturni rizik.

## Kako je urađeno

- pročitan kanonski projektni kontekst i Agent V2 wiring report;
- upoređene grane `windows` i `feature/agent-v2`;
- pregledani plugin loader, XML pozivi, LLM putanje, logovi, build i tajne;
- izvršeni samo read-only PostgreSQL upiti o TLS-u i ulozi;
- nalazi razdvojeni na potvrđene, djelimično ublažene i neprovjerene;
- preporuke su dobile prioritet i testabilne kriterije zatvaranja.

## Šta nije dirano

- nijedan Python simbol ili poslovno pravilo;
- DB podaci, uloge, grantovi i konfiguracija servera;
- `.env` i kredencijali;
- `dist_client` drift;
- grana `windows`.

## Verifikacija

- provjereno da dokument ne sadrži DB lozinku ni API ključeve;
- PostgreSQL nalazi dobijeni direktnom read-only sesijom;
- sigurnosni obrasci provjereni `rg` pretragom na `feature/agent-v2`;
- izvještaj ručno strukturisan prema potvrđenim dokazima i ograničenjima.

## Pronađeni problemi

- aplikacijski DB nalog je superuser;
- aktivna DB lozinka ima 8 znakova;
- `sslmode` ostaje podrazumijevani `prefer`;
- proizvoljni Python parseri se izvršavaju kroz `exec_module`;
- GitNexus FTS indeks je degradiran;
- Agent V2 zaštite još nisu nužno u produkcijskoj `windows` isporuci.

## Konflikti / kontradiktorni izvori

Prethodna procjena nije mogla potvrditi DB privilegije jer server nije bio
dostupan. Novi read-only dokaz ima prednost: nalog je potvrđeno superuser.

Agent V2 izvještaj potvrđuje nove sigurnosne kapije, ali te izmjene su na
`feature/agent-v2`, ne na `windows`. Izvještaj zato ne tvrdi da ih trenutni
produkcijski EXE već sadrži.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `633af2d` | `docs(security): dodaj detaljni sigurnosni pregled` |

## Rizici / ograničenja

Ovo je statički pregled sa ograničenom DB provjerom, ne penetracioni test.
Nije izvršen puni dependency CVE audit niti analiza finalnog EXE-a.

## Potreban follow-up

Prvi naredni sigurnosni zadatak treba biti kreiranje least-privilege DB naloga,
rotacija lozinke i regresiono testiranje aplikacije sa tim nalogom.

## Potrebna korisnička potvrda

Potrebno je potvrditi da li se novi sigurnosni hardening radi na
`feature/agent-v2` prije spajanja ili nakon njenog merge-a u `windows`.
