## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`templates/agent-md/UNIVERSAL_CLAUDE.md` (novo), `templates/agent-md/METHOD.md` (kratka referenca).

## Impact analiza
Nema — dokumentacija.

## Reprodukcija prije izmjene
N/A — novi fajl, ne bugfix.

## Kontekst korišćen
Sadržaj sintetizovan iz svih 8 fajlova napravljenih ranije istog dana u `templates/agent-md/` (AGENTS.md, CLAUDE.md, METHOD.md, BOOTSTRAP.md, agent_report_template.md, project_room_template.md) — pročitani u cijelosti tokom ranijih zadataka istog dana, ne ponovo ovdje.

## Šta je urađeno
Korisnik je tražio JEDAN samostalan fajl (ne folder od 6 fajlova) za primjenu principa na DRUGE aplikacije koje razvija, van deklarant_pro. Kroz dvije `AskUserQuestion` potvrđeno: (1) fajl se sam pokreće pri prvom čitanju bez čekanja komande, (2) počinje kao jedan fajl ali zna kad/kako da se sam podijeli. Korisnikova dopuna: te druge aplikacije su već u poodmaklim fazama razvoja — bootstrap mora "snimiti trenutno stanje i cijeli radni tok prilagoditi", ne početi od praznog projekta.

Napravljen `UNIVERSAL_CLAUDE.md` (365 linija) — stapa METHOD.md (zašto, kondenzovano na 10 stavki), BOOTSTRAP.md (kako sam sebe popuni, prilagođeno za postojeću/poodmaklu kodnu bazu — pojačan Korak 7 "HACK/WARNING komentari" kao najvredniji korak baš zbog te faze) i AGENTS.md pravila (šta, sa `<<< POPUNI >>>` mjestima) u jednu strukturu: Sekcija 0 (bootstrap, sa self-triggering "BOOTSTRAP STATUS" markerom na vrhu fajla), Sekcija 1 (zašto, kratko), Sekcija 2 (pravila), Sekcija 3 (kad/kako se sam podijeliti na više fajlova kasnije).

## Zašto je urađeno
Direktan zahtjev korisnika, sa dvije eksplicitne dizajn-odluke potvrđene kroz pitanja prije pisanja (ne pretpostavljene).

## Kako je urađeno
Ručno pisanje, sintetizovano ne kopirano — svaka sekcija je kondenzovana verzija odgovarajućeg izvornog fajla (npr. METHOD.md 12 komponenti → 10 kratkih stavki bez pune "zašto" proze; BOOTSTRAP.md 9 koraka → 8 koraka bez template-only detalja poput "Korak 0 — obim" koji ovdje nije potreban jer file je uvijek "postojeći projekat" po pretpostavci). "Self-triggering" mehanizam (status marker koji agent ažurira nakon prvog bootstrap-a) je nov element — ne postoji u originalnom BOOTSTRAP.md, dodat specifično da se izbjegne ponavljanje skeniranja svake sesije.

## Šta nije dirano
Preostalih 5 fajlova u `templates/agent-md/` (AGENTS.md, CLAUDE.md, METHOD.md sadržaj osim jedne rečenice, BOOTSTRAP.md, agent_report_template.md, project_room_template.md) — netaknuti, ostaju kao modularna alternativa za projekte gdje folder-pristup ima smisla. Root deklarant_pro fajlovi — nisu dirani ovim zadatkom.

## Verifikacija
Grep provjera na Cyrillic raspon karaktera — 0 pogodaka. Ručna provjera da `git status`/`git add` prije commit-a sadrži samo namjeravana 2 fajla (HEAD provjeren prije/poslije — nepromijenjen, bez sudara sa paralelnim radom ovaj put).

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik (dokumentacija, bez runtime uticaja).

## Pronađeni problemi
Nema.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `5184938` | docs(templates): dodaj UNIVERSAL_CLAUDE.md - jedan samostalan fajl za druge projekte |

## Rizici / ograničenja
**Potpuno neverifikovano** — ovo je prvi put da postoji fajl namijenjen da SAM pokrene bootstrap bez ljudske komande; nije testirano da li Claude Code (ili drugi agent) stvarno prati "AKO PIŠE NIJE POKRENUT, uradi X odmah" instrukciju iz pročitanog fajla bez eksplicitnog user prompta — ovo zavisi od toga koliko snažno CLAUDE.md sadržaj utiče na ponašanje na početku sesije, što nismo testirali u praksi. Takođe neverifikovano: da li je 365 linija previše/premalo za "poodmaklu fazu" projekat da odmah bude produktivan bez dodatnog pojašnjenja.

## Potreban follow-up
Isprobati fajl na stvarnoj "drugoj aplikaciji" korisnika čim prilika nastane — ovo je jedini način da se potvrdi da self-triggering mehanizam stvarno radi kako je zamišljeno.

## Potrebna korisnička potvrda
Kad korisnik prvi put iskoristi ovaj fajl na drugom projektu, vrijedilo bi vratiti nalaz ovdje (šta je radilo, šta nije) — čak i ako je "za drugi projekat", da service ubuduće u ovom repou.
