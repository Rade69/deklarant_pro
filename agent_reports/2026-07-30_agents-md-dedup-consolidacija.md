## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`AGENTS.md` (root) — 3 domenska pravila u "Ključne konvencije" + Korak 3 (agent_report šema) + "Plan prije izmjene" (project_room šema).

## Impact analiza
Nema — dokumentacija, bez koda.

## Reprodukcija prije izmjene
N/A — dokumentacioni zadatak, ne bugfix.

## Kontekst korišćen
Pročitane u cijelosti relevantne sekcije `AGENTS.md` "Ključne konvencije" i `docs/CONTEXT.md` §1-4 (105 linija) da se PRIJE bilo kakve izmjene tačno utvrdi gdje postoji stvarno preklapanje a gdje samo tematska sličnost — izbjegnuto brisanje jedinstvenog AGENTS.md sadržaja bez pokrića u CONTEXT.md.

## Šta je urađeno
Korisnik je pitao postoji li način da se `AGENTS.md` (698 linija nakon 4 dopune istog dana) smanji. Umjesto direktne implementacije prvobitne pretpostavke ("Ključne konvencije se preklapaju sa CONTEXT.md, svesti na jednu rečenicu"), prvo je urađena provjera grep-om + čitanjem obje strane. Rezultat: preklapanje je UŽE nego prvobitno pretpostavljeno — samo 3 konkretna pravila (`consumed_paths`, Rb.48/`TEMPLATE_FIELDS`, Rb.31 280-znakova) postoje skoro identično na oba mjesta; ostatak "Ključnih konvencija" (incoterm_code, Blagić/IMAMOGLU specifike, Trgovački naziv, Grupiranje po 4 ključa, itd.) je AGENTS.md-only sadržaj bez CONTEXT.md ekvivalenta.

Izmjene:
1. 3 duplirane bullet-tačke svedene na jednu liniju + pointer na `docs/CONTEXT.md` §1/§3, bez brisanja ijedne AGENTS.md-only tačke iz istih sekcija.
2. Korak 3 (agent_report šema, ~35 linija sa objašnjenjem svakog polja) svedeno na kratku listu naziva polja + pointer na `templates/agent-md/agent_report_template.md` kao pun izvor.
3. "Plan prije izmjene" (project_room šema, ~30 linija) svedeno analogno, pointer na `project_room_template.md`.

Rezultat: 698 → 665 linija (-33).

## Zašto je urađeno
Direktan zahtjev korisnika kao follow-up na prethodni izvještaj (`2026-07-30_probe-facts-decisions-adr-dopuna.md`, sekcija "Potreban follow-up"). Korisnik je prihvatio preporuku nakon što sam pokazao konkretan dokaz preklapanja (ne samo tvrdnju da je fajl predugačak).

## Kako je urađeno
Ciljane `Edit` izmjene, po jedna po lokaciji. Prvobitna procjena uštede (~600 linija, tj. ~100 linija manje) je bila zasnovana na pretpostavci da su cijele sekcije duplikat — nakon stvarnog poređenja sadržaja red-po-red, samo pojedinačne rečenice su bile duplikat, ne cijele sekcije. Korisniku je saopštena TAČNA brojka (665, -33), ne prvobitna procjena — primjena iste "Facts vs Decisions"/evidence discipline koju smo istog dana ugradili u metodu.

## Šta nije dirano
Sav AGENTS.md-only sadržaj u istim sekcijama (Parseri: incoterm_code, Blagić/IMAMOGLU; Naimenovanja: Rb.31 auto-opis, Trgovački naziv, Grupiranje po 4 ključa). GitNexus auto-generisani footer. Domenske sekcije koje nemaju CONTEXT.md ekvivalent (Tarifni broj format, Formatiranje težina, Auto-popunjavanje tarifnih brojeva, LLM/Agent integracija, Baza podataka). `docs/CONTEXT.md` sam po sebi — nije mijenjan, ostaje pun izvor za sva 3 konsolidovana pravila.

## Verifikacija
Grep provjera na Cyrillic raspon karaktera — 0 pogodaka. Grep provjera da su sve 3 nove `docs/CONTEXT.md §N` reference stvarno prisutne (linije 277, 298, 305) i da stare pune verzije više ne postoje. Provjera header strukture (`^## `) prije/poslije — inicijalno lažno pozitivan nalaz (4 "duplikata" naslova) ispao je artefakt grep-a koji ne poštuje markdown code fence granice (Facts/Decisions template blok unutar ```markdown ograde) — provjereno ručnim čitanjem, nije stvaran problem. `git diff --stat`: 26 insertions, 59 deletions = neto -33 linija, potvrđuje namjeravan obim.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik, čista dokumentacija, dodatno provjereno mojim sopstvenim evidence-first korakom prije izmjene (grep + čitanje obje strane) što djelimično igra ulogu samo-provjere.

## Pronađeni problemi
Moja prvobitna usmena procjena uštede (u prethodnom odgovoru korisniku, prije ove izmjene) bila je preterana (~600 linija) u odnosu na stvarni rezultat (665 linija) — nisam tada još bio uradio punu provjeru. Ispravljeno u ovom zadatku prije nego je bilo koja izmjena napravljena, i korisniku saopštena tačna brojka, ne ranija procjena.

## Odbačene opcije
- Opcija: Potpuno ukloniti cijele sekcije "Ključne konvencije" koje tematski liče na CONTEXT.md poglavlja i zamijeniti ih samo pointer-om na cijelo poglavlje.
- Zašto je razmatrana: Izgledalo je kao veća, brža ušteda linija.
- Zašto je odbačena: Provjera je pokazala da bi to obrisalo stvaran, jedinstven sadržaj (npr. incoterm_code pravilo, Blagić/IMAMOGLU parser specifike) koji CONTEXT.md uopšte ne pokriva — gubitak informacije radi kozmetičke uštede.
- Kada odluku ponovo otvoriti: Ako CONTEXT.md §1/§3 ikad budu prošireni da eksplicitno pokriju i taj sadržaj, razmotriti dalju konsolidaciju.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `16a8c47` | docs(agents): ukloni potvrdjeno dupliranje izmedju AGENTS.md i CONTEXT.md/predlozaka |

## Rizici / ograničenja
665 linija je i dalje značajan fajl koji se čita u svakoj sesiji svakog agenta. Preostali sadržaj je (nakon ove provjere) uglavnom irreducibilan — domenska pravila specifična za deklarant_pro (Ključne konvencije bez CONTEXT.md ekvivalenta), Zabrane, DoD kategorije, GitNexus auto-footer (~45 linija, van naše kontrole). Dalje smanjenje bi zahtijevalo dublju strukturnu odluku (npr. izdvajanje domenskih pravila u poseban `docs/DOMAIN_RULES.md`, analogno "bounded context" ideji iz Mattovog dokumenta koji smo ranije istog dana svjesno odbacili kao preuranjen) — nije urađeno, van scope-a ovog zadatka.

## Potreban follow-up
Ako AGENTS.md nastavi rasti u budućim sesijama, razmotriti izdvajanje domenskih pravila (Tarifni broj format, Auto-popunjavanje, itd.) u zaseban fajl — ali samo kad/ako stvarno postane problem, ne unaprijed.

## Potrebna korisnička potvrda
Nema neposredno.
