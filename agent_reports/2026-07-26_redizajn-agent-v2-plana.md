# Redizajn Agent V2 implementacionog plana (v1.0 → v2.0)

## Datum

2026-07-26

## Agent

Claude Opus 5 (Claude Code)

## Scope

- `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` — potpun redizajn
- `docs/CONTEXT.md` — nova sekcija 69 (dokazani uzroci agent routing problema)
- Analiza (bez izmjena): `services/agent/chat/*`, `gui/tabs/agent/services/*`,
  `services/agent/validation/*`, `services/validation/*`, `core/draft/`

## Status izvora

| Izvor | Status |
| --- | --- |
| `AGENT_V2_IMPLEMENTACIONI_PLAN.md` v1.0 (commit `5557949`) | zamijenjen; dostupan kroz `git show` |
| `AGENTS.md`, `docs/CONTEXT.md` | aktivni, korišteni kao ograničenja |
| aktivni izvorni kod | autoritativan — sve tvrdnje u v2.0 §3 provjerene i navedene sa `fajl:linija` |
| GitNexus indeks | **degradiran** — prijavljuje `services/agent/intent_classifier.py` koji ne postoji; potvrđuje `CONTEXT.md §16` |

## GitNexus impact

Zadatak je isključivo dokumentacioni — nijedan simbol nije izmijenjen, pa
`gitnexus_impact` nije primjenjiv. Impact analiza je umjesto toga **ugrađena u
sam plan** kao obaveza po fazi (v2.0 §23), uz eksplicitno upozorenje da je indeks
degradiran i da ga treba dopuniti ručnim `rg` pregledom.

Za buduću Fazu −1.A (`draft.revision`) plan unaprijed traži `gitnexus_impact` i
očekuje HIGH/CRITICAL, jer `DeclarationDraft` koriste svi tabovi i importeri.

## Šta je urađeno

Plan je prepisan od nule (1390 linija, 26 sekcija). Trinaest suštinskih izmjena
u odnosu na v1.0, popisanih u v2.0 §2. Najvažnije:

1. **Nova Faza −1 (blokirajući preduslovi)** — četiri stavke koje su u v1.0 bile
   skrivene unutar kasnijih faza: `draft.revision`, dist_client strategija,
   kill-switch, inventar kolizija imena.
2. **`tool_definitions.py` podignut u primarni scope Faze 1.**
3. **Skup alata se smanjuje 12 → 8** (parametrizovani `prikazi`/`provjeri`)
   umjesto rasta na 19 kako je v1.0 implicitno tražila.
4. **Poslovno stanje modelovano kao kapije**, ne kao enum od 16 stanja.
5. **Faze 7 i 8 označene uslovnim** — obavezni dio je 40–62 dana umjesto 49–79.
6. Dodati izvršni ugovori: worker thread, single-flight brava, injektabilna potvrda.

## Zašto je urađeno

v1.0 je imala tačnu dijagnozu i dobre sigurnosne granice, ali tri sistemska
problema:

- **Preduslovi skriveni u kasnim fazama.** Faza 6 traži fingerprint drafta koji
  ne postoji; Faza 3 traži validaciju nad stotinama stavki bez ijedne riječi o
  threadu; Faza 7 traži da servis vodi pipeline koji je vezan za `QMessageBox`.
  Svaka od tih faza bi u realizaciji "narasla" bez upozorenja.
- **Nepotpuna dijagnoza LLM grane.** v1.0 je `tool_definitions.py` navela kao
  "vjerovatno izmijenjen". Zapravo taj fajl *sam uči model* pogrešno mapiranje,
  pa bi savršen resolver popravio samo lokalnu granu.
- **Rast složenosti umjesto konsolidacije.** v1.0 traži 7 novih alata (19 ukupno,
  6 sa prefiksom `provjeri_`) i istovremeno ≥95% tačnosti izbora alata. To su
  suprotstavljeni ciljevi.

Ekonomski razlog za uslovne faze: dokazani problem (§3) je zamjena prikaza i
provjere i plitke provjere. Ništa u dijagnozi ne dokazuje potrebu za
višekoračnim planerom, a on nosi 13–21 dan.

## Kako je urađeno

Dva prolaza kroz kod prije pisanja:

1. Verifikacija tvrdnji v1.0 — `route_local_tool`, `_application_context_scope`,
   `_handle_message`, `_puna_auto_pipeline`, `_izvezi_xml`, `tool_policy`,
   `tool_result`, `pipeline_stage_result`, `workflow_state`.
2. Traženje onoga što v1.0 nije imala — `tool_definitions.py` (opisi + SYSTEM_PROMPT),
   dostižnost routing grana, inventar validacionih tipova (`Grep` po definicijama
   klasa), postojanje `revision` na draftu, postojeći testovi
   (`test_tool_policy.py` već tvrdi `TOOLS` ↔ `TOOL_EFFECTS` sinhronizaciju).

Svaki nalaz u v2.0 §3 nosi `fajl:linija` da izvršilac ne mora ponovo dokazivati
dijagnozu.

## Šta nije dirano

- **Nijedan red produkcionog koda.** Zadatak je bio analiza i redizajn plana.
- `AGENTS.md`, `CLAUDE.md` — pravila nisu mijenjana.
- `dist_client/` — netaknut.
- Ostali planovi u `docs/agent/` — `AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md`
  i `AGENT_INTELLIGENCE_PLAN.md` zadržavaju status iz v1.0.
- Postojeći `project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md` (tuđa
  neuvezana izmjena, ostavljena netaknuta).

## Verifikacija

- Provjera pisma: skripta nad cijelim fajlom — **nula ćiriličnih znakova**.
- Struktura: 1390 linija, 26 `##` sekcija.
- Svaka referenca `fajl:linija` u §3 pročitana direktno iz fajla u ovoj sesiji.
- Postojanje/nepostojanje potvrđeno komandom, ne pretpostavkom:
  `services/agent/planning/` i `workflow/` ne postoje; `core/draft/` nema
  `revision`; `tests/unit/test_tool_policy.py` postoji.
- Markdown lint prijavljuje MD024 (ponovljeni naslovi `### Kriterijumi prihvata`
  po fazi) — **namjerno zadržano**, isti obrazac je imala i v1.0 i on je ono što
  čini plan preglednim po fazama.

## Pronađeni problemi

**Potvrđeni (u kodu, ne u planu):**

1. `route_local_tool:71` — `"tab faktura"` bezuslovno u snapshot, bez provjere glagola.
2. `_application_context_scope:767` — `"pregledaj"` tretiran kao želja za prikazom.
3. `_application_context_scope:781` — `faktura` provjerena prije `naimenov`.
4. `_is_naimenovanja_validation_request` — nedostižan za `"pregledaj naimenovanja"`.
5. `tool_definitions.py:172-175, :38` — opisi alata i SYSTEM_PROMPT uče pogrešno mapiranje.
6. `_izvezi_xml` — otkazivanje i uspjeh nerazlučivi; poruka hardkodovana kao
   "Puna automatizacija završena!".
7. `_tariff_usage_stats` — PostgreSQL upiti na UI threadu.
8. `_puna_auto_pipeline` — `processEvents()` bez brave; `QMessageBox` u servisu.
9. Osam konkurentnih reprezentacija ishoda + pet klasa imena `ValidationError`.

**Problemi u samoj v1.0 planu:**

10. `provjeri_usklađenost_tabova` — dijakritika u imenu alata; Groq/OpenAI bi odbili.
11. `ValidationFinding(frozen=True)` sa `evidence: dict` — zamrznutost iluzorna,
    klasa nehashable, a plan traži grupisanje istih nalaza.
12. `IntentAction.MUTATE/PROPOSE` istih imena kao `ToolEffect.MUTATE/PROPOSE`,
    različitog značenja.
13. Kriterijumi prihvata sa hardkodovanim "184 stavki" / "98 naimenovanja".
14. Metrika intent tačnosti mjeri lokalna pravila i LLM zajedno — rezultat bi
    zavisio od dnevnog ponašanja Groq/Gemini modela.

**Lažno pozitivno (provjereno, nije problem):** v1.0 tvrdi da su `tool_policy`,
`tool_result`, `audit_log`, `services/decision/*` i `pipeline_stage_result` već
implementirani — **tačno je**, svi postoje i rade kako je opisano.

## Konflikti / kontradiktorni izvori

| Konflikt | Tretman |
| --- | --- |
| v1.0 §6.2 tvrdi da treba proširiti "postojeći `ValidationItem`" | Nepotpuno: postoji 8 tipova, ne 1. v2.0 §3.7 daje pun inventar. Kod je važeći izvor. |
| v1.0 §3.1 navodi `ValidationResult`, `ValidationItem`, `Issue`, `NaimenovanjeValidation` | Dopunjeno sa `ValidationReport`, `ComplianceResult`, drugi `ValidationResult`, `PipelineStageResult`. |
| GitNexus indeks prijavljuje `services/agent/intent_classifier.py` | Fajl ne postoji. Indeks tretiran kao nepouzdan (`CONTEXT.md §16`), provjera rađena kroz `ls`/`Grep`. |

**Potrebna korisnička potvrda:** DA — vidi zadnju sekciju.

## Commitovi

| Hash | Poruka |
| --- | --- |
| (vidi git log) | `docs(agent): redizajniraj Agent V2 plan na verziju 2.0` |
| (vidi git log) | `docs(report): evidentiraj redizajn Agent V2 plana` |

## Rizici / ograničenja

- **Procjena ostaje procjena.** 40–62 dana za obavezni dio je izvedeno iz obima
  faza, ne iz mjerenja. Faza −1.A (`draft.revision`) je najveća nepoznanica jer
  dira model koji koriste svi tabovi i importeri.
- **Konsolidacija alata 12 → 8 je nedokazana pretpostavka.** Teza da manji skup
  alata daje bolju tačnost LLM izbora je opšte prihvaćena, ali za ovaj konkretan
  skup i ove modele nije izmjerena. Faza 0 fixture je mjesto gdje se to dokazuje
  prije nego što se `TOOLS` prepiše.
- **Uslovne faze 7/8 mogu biti pogrešno otpisane.** Ako korisnik zapravo želi
  "pripremi mi deklaraciju do kraja" kao jednu komandu, planer je potreban i
  procjena raste na 53–83 dana.
- Plan ne rješava nijedan postojeći bug — samo ih dokumentuje. Do realizacije
  Faze 1, `Provjeri tabelu u tabu Faktura` i dalje vraća snapshot.

## Potreban follow-up

- Odluka o dist_client strategiji (tri opcije u v2.0 §10, preporuka: sync skripta).
- Odluka da li se Faze 7 i 8 uopšte planiraju.
- Faza −1 nije započeta.

## Potrebna korisnička potvrda

1. **Da li je preporučeni redoslijed prihvatljiv** — Faza −1 + 0 prvo, planer
   odgođen? Ovo je jedina izmjena koja mijenja *šta se isporučuje*, a ne samo
   *kako je opisano*.
2. **Konsolidacija alata 12 → 8** mijenja postojeći javni skup alata. Aliasi
   čuvaju kompatibilnost, ali je odluka arhitektonska i traži saglasnost.
3. **Kill-switch default `0`** znači da V2 routing u početku NIJE aktivan na
   Windows klijentu — svjesna odluka radi sigurnosti, treba je potvrditi.
