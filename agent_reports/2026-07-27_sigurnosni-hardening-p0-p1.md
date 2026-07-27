# Sigurnosni hardening P0/P1

## Datum

2026-07-27

## Agent

Codex

## Scope

- Agent V2 XML readiness i export workflow
- PostgreSQL konfiguracija, runtime konekcioni pool i aktivni server
- parser plugin instalacija i učitavanje
- XML ulazne tačke
- LLM provider putanje
- runtime logovi
- Python zavisnosti, CI i Windows build
- odgovarajuće root i `dist_client` implementacije

## Status izvora

| Izvor | Status | Napomena |
| --- | --- | --- |
| `agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md` | aktivan | Polazna slika Agent V2 wiring popravki |
| `docs/SECURITY_AUDIT_2026-07-27.md` prije izmjene | zastario | Opisivao početno stanje prije hardeninga |
| Claude potvrda nalaza SEC-01/02/04/07 | aktivna | Nezavisno potvrđeni nalazi |
| Sekcija 6.5 starog audita | zastarjela | Puni resync je već urađen u `ac49b51` |
| Kod i testovi na `feature/agent-v2` | autoritativan | Korišćeni kao stvarni izvor ponašanja |
| PostgreSQL `192.168.100.154` | autoritativan za runtime | Kontrolisana provjera stvarne TLS sesije i uloge |

## GitNexus impact

- `database/db.py::get_connection_pool`: **CRITICAL**, 522 pogođena simbola,
  33 procesa. Scope i obavezne kapije evidentirani u
  `project_rooms/2026-07-27_db-runtime-security-guard.md`.
- `KnowledgeBaseService._groq_rerank`: **HIGH**, 6 simbola, 2 procesa.
  Scope evidentiran u
  `project_rooms/2026-07-27_kb-rerank-llm-provider.md`.
- Ostali ciljani impact upiti bili su LOW/MEDIUM ili UNKNOWN zbog zastarjelog
  indeksa.
- Obavezni završni `detect_changes(scope=all)` vratio je nula promjena jer je
  GitNexus indeks vezan za glavno radno stablo, a izmjene su u izdvojenom
  `.worktrees/agent-v2`. Rezultat nije tretiran kao dokaz nultog uticaja;
  obim je provjeren diffom, ciljanim testovima, statičkim skenovima i punim
  regresionim paketom.

## Šta je urađeno

1. XML readiness provjere rade fail-closed i tehnički kvar obavezne kapije
   blokira izvoz.
2. XML izvoz ponovo provjerava `draft.revision` poslije potvrde i izbora fajla.
3. Eksterni parseri su default-deny i zahtijevaju važeći RSA-PSS/SHA-256
   potpis prije importa.
4. Parser validacija koristi AST i ne izvršava top-level kod.
5. Aplikacija je prebačena na least-privilege `deklarant_app` DB nalog.
6. TLS je obavezan; konekcioni pool odbija netls i privilegovanu ulogu.
7. XML ulazi koriste centralni sigurni parser sa limitima i zabranom DTD/entity.
8. Tarifni i KB LLM tok koriste centralni `LLMProvider`.
9. LLM ne smije generisati slobodan tarifni broj bez lokalnog/RAG kandidata.
10. Runtime logovi centralno rediguju tajne, JIB i korisničke putanje.
11. Uvedeni su `pip-audit` CI gate, sedmični Dependabot i ažurani lock fajlovi.
12. Windows produkcijski build zahtijeva i verifikuje Authenticode potpis.
13. Sigurnosni audit i `docs/CONTEXT.md` ažurirani su novim kanonskim stanjem.

## Zašto je urađeno

Početni audit je dokazao lanac visokog rizika: aplikacija je mogla izvršiti
izabrani Python parser, a DB kredencijal je pripadao superuser nalogu.
Istovremeno su validator exception putanje mogle završiti kao preskočene
provjere, TLS nije bio obavezan, a dio LLM poziva je zaobilazio centralnu
politiku. Šira automatizacija do XML izvoza nije prihvatljiva dok ti kvarovi
mogu dovesti do kompromitovanja servera ili izvoza nedovoljno provjerene
deklaracije.

## Kako je urađeno

- Uvedeni su mali sigurnosni servisi u `services/security/` za parser trust,
  XML ulaz i log redakciju.
- Postojeće ulazne tačke su preusmjerene na centralne servise bez promjene
  poslovnih modela ili grupisanja naimenovanja.
- DB pool nakon kreiranja izvršava read-only provjeru `pg_stat_ssl` i
  `pg_roles`; na nebezbjedno stanje zatvara pool i prekida startup.
- Server prava su ograničena na potrebne šeme, tabele i sekvence.
- Negativni testovi dokazuju blokiranje nepotpisanog parsera, zlonamjernog XML-a,
  neuspjele readiness provjere i privilegovanog/netls DB stanja.
- Ranjive zaključane verzije nadograđene su preko `uv lock`; root i
  `dist_client/uv.lock` imaju isti hash.

## Šta nije dirano

- Nepovezane korisničke izmjene:
  `ui/naimenovanja_tab_OPTIMIZED_ui.py` i `ui/zaglavlje_tab_ui.py`.
- Poslovna pravila grupisanja naimenovanja i format ASYCUDA XML-a.
- SQL šeme i aplikacijske migracije.
- `pg_hba.conf`, firewall, OS servera i Windows domenska politika.
- Istorijski superuser nalog `radovan`, jer aktivni runtime `.env` više ne
  sadrži administratorski kredencijal potreban za njegovu rotaciju/NOLOGIN.
- Produkcijski certifikati i finalni installer artefakt.

## Verifikacija

- `uv run pytest tests -q`:
  **1296 passed, 72 skipped, 5 xfailed**.
- `pip-audit` nad `uv export --frozen --no-dev --no-emit-project`:
  **No known vulnerabilities found**.
- `uv run python -m compileall -q ...`: prolazi.
- Statički sken:
  - direktni `Groq` ostaje samo unutar kanonskog `LLMProvider`;
  - nema direktnog `ET.parse`/`ElementTree.parse`/`etree.parse` ulaza u
    pregledanim aplikacijskim folderima.
- Root i `dist_client/uv.lock`: identičan SHA-256 hash.
- Stvarna aplikacijska DB konekcija:
  - TLS aktivan;
  - `deklarant_app` nema nijedan zabranjeni privilegijski flag;
  - runtime security guard prolazi.
- Git pre-commit `py_compile` gate: prolazi.

## Pronađeni problemi

1. Istorijski `radovan` nalog je i dalje login superuser. Aplikacija ga više ne
   koristi, ali krađa starog kredencijala i dalje predstavlja serverski rizik.
2. TLS `require` šifruje vezu, ali ne potvrđuje identitet servera.
3. `uv sync` je pri prvom zajedničkom pozivu prekoračio timeout tokom
   preuzimanja; odvojena sinhronizacija je završila, a zatim puni testovi prošli.
4. GitNexus završni diff sken ne vidi izdvojeni worktree.
5. `scripts/sync_dist_client.py` nije pokretan jer je sigurnosni sandbox odbio
   široku mutirajuću komandu; paritet je provjeren ciljanim read-only skenovima
   i testovima.
6. Produkcijski installer skripta nije prisutna na ovoj feature grani, pa build
   gate pokriva EXE, ali potpis finalnog installera ostaje operativni korak.

## Konflikti / kontradiktorni izvori

Stari audit i dio `docs/CONTEXT.md` tvrdili su da postoji 330+ stvarnih razlika
u `dist_client`. Važeći izvor je noviji puni resync commit `ac49b51` i Claudeova
potvrda da je Python drift tada nula. Novi sigurnosni zahvat zato je preslikan
u obje implementacije. Korisnička potvrda za izbor važećeg izvora nije
potrebna jer je korisnik eksplicitno naveo da je sekcija 6.5 popravljena.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `35d2004` | `fix(security): ojačaj runtime i ulazne kapije` |
| `21dae95` | `docs(security): ažuriraj audit nakon hardeninga` |

## Rizici / ograničenja

- Potpisani Python parser i dalje radi sa pravima aplikacijskog procesa; potpis
  uspostavlja povjerenje u izdavača, ali nije sandbox.
- `sslmode=require` ne štiti od lažnog servera sa drugim certifikatom.
- `pip-audit` vidi samo trenutno poznate i mapirane CVE nalaze.
- Log redakcija smanjuje rizik, ali ne može prepoznati svaki mogući poslovni
  identifikator ili slobodni tekst.
- Ocjena 8/10 važi za pregledani kod i kontrolisani interni runtime, ne za
  neprovjeren finalni instalacioni paket.

## Potreban follow-up

1. PostgreSQL administrator: invalidirati stari `radovan` login/lozinku.
2. Infrastruktura: vlastiti CA, server SAN i `DB_SSLMODE=verify-full`.
3. Release: produkcijski Authenticode certifikat, potpis EXE-a i installera,
   smoke test na čistoj Windows mašini.
4. Parser: zaseban ograničen proces bez pristupa DB/LLM tajnama.
5. Dodati PDF/XLSX resource limite, fuzz testove i SBOM.

## Potrebna korisnička potvrda

- Potvrditi da istorijski `radovan` nalog nije potreban drugim aplikacijama
  prije nego PostgreSQL administrator primijeni `NOLOGIN` ili rotira lozinku.
- Nakon produkcijskog builda ručno potvrditi Authenticode izdavača i osnovni
  uvoz/provjeru/izvoz na čistoj Windows mašini.
