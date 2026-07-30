## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`templates/agent-md/` — novi `BOOTSTRAP.md`, dopune `CLAUDE.md` i `METHOD.md` (reference). Nastavak istog dana kao `agent_reports/2026-07-30_agent-md-metoda-template-paket.md`.

## Status izvora
`METHOD.md`/predlošci iz prethodnog zadatka istog dana — aktivni, nadograđeni ovim.

## Impact analiza
Nema — dokumentacija, bez koda.

## Kontekst korišćen
Nema — samo pisanje novog sadržaja na osnovu prethodnog konteksta sesije.

## Šta je urađeno
Korisnik je pitao da li `METHOD.md` može biti napisan tako da ga Claude/Codex razumiju kao izvršivu proceduru — da skeniraju kodnu bazu i sami popune `<<< POPUNI >>>` placeholdere. Umjesto pretvaranja `METHOD.md` (pisan za čovjeka) u hibrid, dodat je zaseban `BOOTSTRAP.md`: 9-koračna agent-izvršiva procedura (tech stack, struktura, konvencije, testovi, git istorija, postojeća agent-infrastruktura + "sjeme" za `docs/CONTEXT.md` iz HACK/WARNING komentara, zabrane iz revert-commit-a, obavezan sažetak za čovjeka prije finalizacije, post-popuna housekeeping) sa eksplicitnim zabranama (ne izmišljati "zašto", ne prepisivati postojeći AGENTS.md bez pitanja, ne kreirati praznu infrastrukturu unaprijed). `CLAUDE.md` i `METHOD.md` dopunjeni kratkim referencama na novi fajl.

## Zašto je urađeno
Direktan zahtjev korisnika — razdvojiti "čitaj i razumij" (METHOD.md) od "izvrši" (BOOTSTRAP.md), jer dokument koji pokušava oboje obično loše radi oba posla.

## Kako je urađeno
Ručno pisanje, imperativni stil upućen agentu (ne čovjeku), sa eksplicitnim "dokaz prije upisa" pravilom na svakom koraku.

## Šta nije dirano
`AGENTS.md`/`agent_report_template.md`/`project_room_template.md` iz prethodnog commit-a — nepromijenjeni. Root projekta — ne dira se ovim zadatkom.

## Verifikacija
Grep provjera na Cyrillic raspon karaktera — 0 pogodaka u sva 3 fajla. Ručna provjera da `git status`/`git add` prije commit-a sadrži samo namjeravane fajlove (HEAD provjeren prije/poslije zbog poznatog rizika paralelnog Codex commit-a iz prethodnog zadatka istog dana — nije bilo sudara ovaj put).

## Pronađeni problemi
Nema.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `0109a8b` | docs(templates): dodaj BOOTSTRAP.md - agent-izvrsiva auto-popuna metode |

## Rizici / ograničenja
Nije testirano na stvarnom projektu (ni novom ni postojećem) — prva prava primjena vjerovatno otkriva nedostatke u koracima (npr. dodatni tech stack manifest formati koji nisu pokriveni, ili situacije gdje "sjeme za CONTEXT.md" heuristika hvata previše šuma).

## Potreban follow-up
Isprobati BOOTSTRAP.md na stvarnom projektu (novom ili postojećem) čim prilika nastane, i zabilježiti šta je nedostajalo.

## Potrebna korisnička potvrda
Nema neposredno — follow-up je "probaj kad zatreba", ne nešto što treba potvrditi sada.
