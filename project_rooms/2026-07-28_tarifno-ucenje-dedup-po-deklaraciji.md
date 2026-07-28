# Dedup "knjiga učenja" za tarifni usage_count/confidence — arhiviran prijedlog

## Status

**BLOKIRANO do daljnjeg — čeka `refactor/faktura-3layer` (Pi) da se završi i spoji u `windows`.**

Razlog blokade: svih ~6 mjesta koja poziva `save_mapping()` (vidi GitNexus
impact niže) su u `gui/tabs/faktura_view.py` — TAČNO fajl koji Pi trenutno
razbija na View/Controller/Service ([project_rooms/
2026-07-27_faktura-3layer-refaktor-detaljni-plan.md](2026-07-27_faktura-3layer-refaktor-detaljni-plan.md)).
Rad na ovome sad bi značio direktan sukob/duplirani posao sa tim refaktorom.

**Ne implementirati dok se `refactor/faktura-3layer` ne spoji u `windows`.**
Kad se spoji, ovaj dokument treba PONOVO PROVJERITI protiv novog Controller/
Service koda prije implementacije (imena metoda/fajlova će se promijeniti
prema §7 mapiranju u planu refaktora — npr. `_auto_learn_edits` postaje
Controller metoda, `save_mapping` poziv ide kroz `TariffFacade` iz
Controller-a, ne direktno iz View-a).

## Kontekst — zašto ovo uopšte postoji

Sesija 2026-07-28: istraga "SUSSINA" problema ("Provjeri" ne daje prijedlog)
je otkrila da politika "nikad ne prikaži prijedlog bez potvrđenog izvora"
(docs/CONTEXT.md §65, 26.07) stvara trajan cor-22 za stare zapise bez izvora.
Predložen fix (§88, SHOW_UNCONFIRMED — prikaži ali obilježi kao neprovjereno)
je korisnik **eksplicitno odbacio** (§89, `git revert 8b22281`, commit
`aac9b19`) uz obrazloženje: "Ne možemo korisniku ponuditi prijedlog a da
pritom ne znamo odakle dolazi... greška u tarifiranju može izazvati kazne."

Nastavak razgovora je otkrio DUBLJI problem koji ovaj dokument adresira:
korisnik je precizirao da "izvor istine" = ranije (odobrene) deklaracije
(XML fajlovi) + zvanična tarifa, i da `usage_count`/`confidence` koje
deklarant vidi MORAJU biti stvarno vezani za broj pravih ranijih
deklaracija — "ne može se proizvoljno napisati korišteno 6x ako se za to
nema potvrda."

## Nalaz — usage_count trenutno NIJE pouzdan broj

Provjereno direktno u kodu (ne pretpostavka):

`TariffMappingService.save_mapping()` (`services/tariff/
tariff_mapping_service.py:937`) radi bezuslovno `ON CONFLICT DO UPDATE SET
usage_count = usage_count + 1` — bez ikakve zaštite od dvostrukog brojanja.
Nema ID deklaracije, nema provjere da li je XML stvarno izvezen, ništa što
bi spriječilo da se ISTA deklaracija (ili čak deklaracija koja nikad nije
predata) broji više puta.

GitNexus impact (`save_mapping`, upstream): **HIGH**, 8 direktnih
pozivalaca kroz 3 modula:

1. `FakturaView._auto_learn_edits` — svaka ručna izmjena ćelije u tabeli
   (debounce preko `_flush_pending_validation` → `_pending_learn_rows`)
2. `FakturaView._correct_tariff_in_db` — desni-klik kontekstni meni
3. `FakturaView._on_bulk_change_tariff` — grupna promjena tarife
4. `FakturaView._on_table_context_menu` (indirektno, poziva #2)
5. `TariffMappingService.correct_mapping` — ispravka mapiranja
6. `TariffMappingService.learn_from_draft` — poziva se iz
   `_on_create_naimenovanja` (`gui/tabs/faktura_view.py:4455`), NE iz XML
   izvoza — znači "učenje" se dešava u trenutku kreiranja naimenovanja,
   koje se u velikim deklaracijama može ponoviti više puta
7. `TariffIntentService.learn_tariff` — agent chat "nauči tarifu" alat

Svih 6-7 dijeli ISTI nezaštićen increment. Praktična posljedica: deklarant
koji 3x ispravi istu ćeliju dok ne pogodi tačnu tarifu, ili 2x klikne
"Kreiraj naimenovanja" u velikoj deklaraciji, ili deklaracija koja se
naknadno odbaci/nikad ne izveze — sve to ostavlja trag u `usage_count` kao
da se radi o stvarnim, odvojenim, odobrenim deklaracijama.

## Korisnikova smjernica za rješenje (2026-07-28)

Doslovno: "Ne mora izvoz xml-a biti okidač učenja, to može biti trenutak
kad deklarant vidi grešku u tabeli u tabu faktura, može biti nakon
kreiranja naimenovanja, jer se u velikim deklaracijama takva greška
podkrade, to su dva ključna mjesta. Aplikacija može u toku izvoza uraditi
neku vrstu provjere da vidi da li ima dupliranja i u tom trenutku to
spriječiti ili već nešto slično."

Znači: NE premještati okidač učenja na XML izvoz (gubi se rani signal kad
deklarant uhvati grešku). Umjesto toga: učenje ostaje na postojećim
mjestima (Faktura ispravka + nakon kreiranja naimenovanja), ALI se dodaje
mehanizam koji SPRJEČAVA dupliranje, sa provjerom/usklađivanjem u trenutku
XML izvoza kao završnom sigurnosnom mrežom.

## Predloženo rješenje (arhitektura, nije implementirano)

### 1. Stabilan identitet deklaracije

`DeclarationDraft` trenutno NEMA trajan UUID koji preživljava snimanje/
učitavanje nacrta (`core/draft/draft.py` provjeren — ima `item_id` po
stavci, `revision` je in-memory brojač dirty-stanja, ali nema draft-level
ID). Treba dodati npr. `draft_uid: str` (generisan jednom pri kreiranju
drafta, upisan u nacrt XML pri `DeclarationDraftService.save()`, čitan pri
`load()` — ako fajl ne postoji, generisati i sačuvati).

### 2. "Knjiga učenja" po deklaraciji (nova tabela)

```sql
CREATE TABLE catalogs.tariff_learning_ledger (
    draft_uid      TEXT NOT NULL,
    line_key       TEXT NOT NULL,  -- stabilan identifikator stavke unutar drafta
    naziv_robe     TEXT NOT NULL,
    product_code   TEXT NOT NULL DEFAULT '',
    tarifni_broj   TEXT NOT NULL,
    learned_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (draft_uid, line_key)
);
```

Logika (zamjenjuje direktan `save_mapping()` poziv iz svih 6-7 mjesta):

- Pročitaj postojeći red za `(draft_uid, line_key)`.
- Ako ne postoji → INSERT u ledger + `save_mapping()` (pravi +1 usage_count).
- Ako postoji sa ISTOM tarifom → ništa (već zabilježeno, nema duplog brojanja).
- Ako postoji sa DRUGAČIJOM tarifom (ispravka) → UPDATE ledger na novu
  tarifu + **skini** 1 sa stare tarife u `product_tariff_mapping` (ili bar
  ne dodavaj joj više, po odluci — "skidanje" je preciznije) + `save_mapping()`
  na novu (pravi +1 tamo).

Ovo automatski rješava: ponovljene izmjene iste ćelije (idempotentno),
ponovljeno kreiranje naimenovanja (idempotentno), i baza znanja ostaje
iskrena čak i kad se deklarant predomisli.

### 3. Provjera/usklađivanje pri XML izvozu (korisnikov predlog)

U `_izvezi_xml` (`gui/tabs/agent/services/xml_workflow_service.py`, nakon
uspješnog `export_to_xml`) — završni prolaz kroz TRENUTNO stanje
`draft.invoice_lines`, uporediti sa ledger-om za taj `draft_uid`, uhvatiti
i uskladiti bilo šta što je promijenjeno mimo ona dva glavna mjesta (npr.
direktna izmjena u Naimenovanja tabu koja ne prolazi kroz Faktura auto-learn).
Ovo je sigurnosna mreža, ne primarni mehanizam učenja.

## Šta NIJE riješeno ovim prijedlogom (van scope-a)

- Postojećih 129 SUSSINA zapisa (i sličnih) sa praznim `source` — ledger
  rješava BUDUĆE tačnosti brojanja, ne popravlja retroaktivno već naučene
  podatke.
- `source`/`supplier` i dalje se ne piše za ručne potvrde (odvojen nalaz,
  "Sloj 1" iz §88 istrage) — ledger rješava TAČNOST BROJA (usage_count),
  ne POTVRDU IZVORA (source). Ovo su dva različita, ali povezana problema;
  vrijedi razmotriti oba zajedno kad se ovo implementira.

## Sljedeći koraci (kad se blokada skine)

1. Provjeriti da je `refactor/faktura-3layer` spojen u `windows`.
2. Ponovo pročitati novi `faktura_view.py`/`faktura_controller.py`/
   `services/faktura/` — imena/lokacije metoda će se promijeniti.
3. GitNexus impact ponovo pokrenuti na `save_mapping` (ili šta god je
   njegov ekvivalent nakon refaktora) protiv NOVOG stanja koda.
4. Predložiti `project_rooms/` plan fajl (HIGH impact kapija po AGENTS.md)
   prije implementacije, sa ažuriranim referencama na fajlove.
5. Korisnička potvrda dizajna (posebno: da li "skidanje" boda sa stare
   tarife pri ispravci ide na `usage_count - 1` ili nekim drugim
   mehanizmom) prije pisanja koda.
