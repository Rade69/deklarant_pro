# Plan unapređenja agentskog moda

## Datum

2026-07-19

## Agent

Codex

## Scope

- `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md`
- dokumentacioni handoff za buduću implementaciju agentskog moda

## Status izvora

- `AGENTS.md` - aktivan, kanonska projektna pravila.
- `docs/CONTEXT.md` - aktivan, zajednička projektna memorija.
- `docs/decisions/001-tool-use-refactoring.md` - djelimično zastario u dijelu provider politike.
- `docs/decisions/002-tool-dispatcher-integration.md` - status i dalje navodi implementaciju u toku; korišten kao istorijski izvor.
- Aktivni kod u `gui/tabs/agent/` i `services/agent/` - važeći izvor stvarnog ponašanja.

## GitNexus impact

Nije mijenjan nijedan Python simbol. `gitnexus_detect_changes(scope="unstaged")` prijavio je LOW rizik i nijedan pogođen izvršni proces. Izlaz je sadržao ranije, nepovezane korisničke izmjene; one nisu uključene u commit ovog zadatka.

## Šta je urađeno

Napravljen je detaljan implementacioni plan za drugog agenta. Plan obuhvata sigurnosnu kapiju za mutirajuće alate, jedinstveni LLM provider, pouzdane statuse automatskog pipeline-a, standardizovane rezultate alata, audit događaje, integracione testove i kasnije razlaganje velikog chat handlera.

## Zašto je urađeno

Postojeći agentski mod ima dobru tool-first osnovu, ali direktna LLM mutacija drafta, direktan DeepSeek poziv i nastavak pipeline-a nakon kritične greške predstavljaju najveće rizike. Plan određuje redoslijed koji prvo zatvara sigurnosne i pouzdanosne probleme, a tek zatim radi strukturni refaktor.

## Kako je urađeno

Plan je organizovan u šest implementacionih faza. Za svaku fazu navedeni su namjera, pogođeni fajlovi i simboli, pravila ponašanja, kriterijumi prihvata i ciljane provjere. Dodati su scope lock, dist-client ograničenja, commit redoslijed, verifikaciona matrica, ručni acceptance test, rizici i definition of done.

## Šta nije dirano

- Aplikacioni Python kod.
- Baze podataka i migracije.
- `dist_client/`.
- Postojeće korisničke izmjene u `AGENTS.md`, `CLAUDE.md`, `pyproject.toml`, exporter indexerima i drugim nestageovanim fajlovima.
- `docs/CONTEXT.md`, jer nije donesena nova poslovna odluka; dokumentuje se plan realizacije postojeće analize.

## Verifikacija

- `bash scripts/doc_link_checker.sh .` - završen bez BROKEN ili STALE poruke.
- Pregledan početak i struktura novog dokumenta.
- Potvrđeno 514 linija plana.
- Prethodna analiza agentskog moda imala je 24/24 prolazna ciljana offline testa.
- Pre-commit hook je završio sa statusom OK.

## Pronađeni problemi

GitNexus konceptualna pretraga je ranije bila degradirana zbog nedostajućih FTS indeksa. `detect_changes` radi, ali u ovom zadatku nije prepoznao novi dokument kao simbol, što je očekivano za dokumentacionu izmjenu.

## Konflikti / kontradiktorni izvori

Aktivni kod dozvoljava i direktno koristi providere koji nisu u skladu sa kanonskim `AGENTS.md` pravilom Groq pa Gemini, uz isključen DeepSeek. Plan tretira `AGENTS.md` kao važeći izvor i zahtijeva korisničku potvrdu samo ako budući implementacioni agent želi zadržati OpenRouter ili DeepSeek. Potrebna korisnička potvrda sada: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `2c7bbe1` | `docs(agent): arhiviraj plan unapredjenja agentskog moda` |

## Rizici / ograničenja

Plan nije implementacija. Procjene GitNexus impacta za konkretne simbole moraju se ponoviti neposredno prije svake kodne izmjene. Buduća izmjena aktivnih modula može zahtijevati Windows `dist_client` rebuild.

## Potreban follow-up

Drugi agent treba da realizuje faze redoslijedom iz plana, počevši od sigurnosne kapije za mutirajuće alate. Svaka faza treba da bude zasebno testirana i commitovana.

## Potrebna korisnička potvrda

Nije potrebna za arhiviranje plana. Pri implementaciji je potrebna samo ako se odstupa od kanonske provider politike ili ako se proširuje scope na distribucioni rebuild.
