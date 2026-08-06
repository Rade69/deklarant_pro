## Datum
2026-08-06

## Agent
Claude Code (Sonnet 5)

## Scope
**Baza podataka** (dmserver, `catalogs.product_tariff_mapping`) — DIREKTNA izmjena produkcijskih
podataka. Nema izmjene koda u ovom zadatku.

## Status izvora
Nastavak dugogodišnjeg, već dokumentovanog "SUSSINA slučaja" — `docs/context/history.md`
§27-29 (2026-07-22), §64 (2026-07-26), §88 (2026-07-28). Korisnik je danas (u realnom
korišćenju aplikacije) prijavio da se dijalog "Automatski ažurirane tarife (ranija potvrda)"
ne pokreće za SUSSINA proizvode, iako smatra da bi trebalo.

## Reprodukcija prije izmjene
Korisnik dostavio screenshot dijaloga (2 stavke auto-ažurirane, SUSSINA nije među njima) +
log fragment sa upozorenjima "Preskačem historijsku tarifu koja nije u zvaničnoj tarifi" za
druge proizvode. Direktnim upitom u `catalogs.product_tariff_mapping` potvrđeno: 4 "čista"
SUSSINA zapisa (imena bez šuma) sa ispravnim tarifama i visokim `usage_count` (43-55), ali BEZ
`source`/`supplier` — `tariff_decision_model.py:77-90` bezuslovno suprimira svaki prijedlog bez
"smislenog izvora" (namjerna politika od 26.7.2026, potvrđena i nakon pokušaja ublažavanja u
§88 koji je eksplicitno vraćen nazad zbog rizika sankcija za pogrešnu carinsku tarifu).

Šira pretraga (`ILIKE '%SUSSINA%'`, ne samo tačno ime) otkrila je DODATNIH 38 zapisa —
uključujući **3 zapisa sa pogrešnom tarifom 38249993** (id 128370/128371/128398, po jedan za
svaku varijantu imena — 650/200/1200 tbl), `usage_count=21` svaki, BEZ izvora. Ovo je ISTI bug
koji je §37 (22.7.2026) već jednom "očistio" (obrisano 7 tadašnjih pogrešnih zapisa,
`usage_count` tada bio 2) — sad je narastao na 21, potvrđujući da se poznati obrazac ("jedna
ručna greška postaje trajno naučen bug", AGENTS.md) aktivno ponavlja.

## GitNexus impact
N/A — ovo je izmjena podataka u PostgreSQL bazi, ne koda. Nijedan `.py` fajl nije mijenjan.

## Uzročni lanac (zašto se pogrešna mapa 38249993 stalno vraća)
Radna hipoteza, potkrijepljena postojećom dokumentacijom, NIJE nezavisno dokazana kroz kod
`learn_from_draft()` u ovom zadatku (van scope-a): suzbijanje ispravnog istorijskog prijedloga
(nema izvora) → korisnikova faktura zadržava originalno pogrešno parsiranu tarifu 38249993 →
ako se deklaracija potvrdi bez ručne ispravke → `learn_from_draft()` (uči samo iz CONFIRMED
odluka) ponovo učvršćuje POGREŠNU tarifu kao "naučenu" → `usage_count` raste. Ako je ova
hipoteza tačna, brisanje pogrešne mape BEZ paralelnog rješavanja suzbijanja ispravne mape bi
bio samo privremen predah (isto što se desilo između jula i danas) — zato je korisnik
eksplicitno tražio OBA koraka zajedno.

## Šta je urađeno
1. Nezavisno provjereno u stvarnim XML fajlovima (`data/knowledge_base/NOVA ASIKUDA/*.xml`,
   25 fajlova sa SUSSINA stavkama) da je pravi izvoznik **"MEDICO PHARM SERVIS"** (Beograd,
   Srbija) — NE "Medicopharm" (to je domaći uvoznik/primalac "MEDICOPHARM DOO", Bijeljina).
   Svih 25 provjerenih fajlova konzistentno potvrđuje tarifu 21069098 za "SUSSINA ... tbl"
   grupu. Ovo je urađeno da se u bazu ne upiše pogrešan/pretpostavljen naziv izvoznika.
2. Korisnik odlučio (AskUserQuestion, nakon što sam prijavio širu sliku od originalno
   odobrenih "4 zapisa"): prvo obrisati pogrešnu mapu, zatim dodati izvor ispravnim redovima.
3. Jedna transakcija (`with get_db_connection() as conn:`, auto-commit/rollback):
   - `DELETE FROM catalogs.product_tariff_mapping WHERE id = ANY(%s)` za `[128370, 128371,
     128398]` (SUSSINA 650/200/1200 tbl → 38249993, usage 21 svaki) — **3 reda obrisana**,
     potvrđeno `RETURNING`.
   - `UPDATE catalogs.product_tariff_mapping SET supplier = 'MEDICO PHARM SERVIS', source =
     'MANUAL_VERIFIED_NOVA_ASIKUDA_XML_2026-08-06' WHERE id = ANY(%s)` za `[63200, 65199,
     65350, 65351]` (STEVIA→21069092 usage 55; 650/200/1200 tbl→21069098 usage 49/43/43) —
     **4 reda ažurirana**, potvrđeno `RETURNING`.
4. Verifikacija poslije: ponovni `SELECT ... WHERE naziv_robe ILIKE 'SUSSINA%'` potvrđuje
   tačno očekivano stanje (3 obrisana reda više ne postoje, 4 ažurirana reda imaju
   supplier/source popunjen).
5. Direktan poziv `decide_tariff_match()` sa simuliranim SUSSINA matchom (usage=49,
   source='MEDICO PHARM SERVIS', trenutna tarifa='38249993') — rezultat: **`outcome:
   show_strong, should_show: True`** — potvrđuje da bi "Provjeri"/auto-apply sada ispravno
   ponudio korekciju.
6. Namjerno NEDIRANO: dva niske-pouzdanosti "šumna" zapisa (`id=65927` "SUSSINA 200 tbl." →
   pogrešno 21069092, usage=1; `id=65889` "SUSSINA STEVIA a200 tbl" → pogrešno 21069098,
   usage=29) — oba imaju niži `usage_count` od sad-popravljenih ispravnih zapisa iste imenske
   grupe, pa gube po `ORDER BY usage_count DESC` u `_search_one()` bez potrebe da se dirају.
   Takođe nedirano: 25+ "šumnih" zapisa iz sirovog `Commercial_Description` teksta koji VEĆ
   imaju izvor (`supplier=MEDIKO/MED/M`, `source=<ime_xml_fajla>`) — ti rade ispravno, van
   scope-a.

## Zašto je urađeno
Korisnik je direktno pogođen greškom u produkciji (stvarna deklaracija, stvarna faktura) i
eksplicitno odobrio ovaj tačno ograničen, dvokorak popravak nakon što sam prijavio širu sliku
od originalno pretpostavljene.

## Kako je urađeno
Jedna transakcija, dva `RETURNING`-praćena upita, potpuna snimka stanja PRIJE (sačuvana u
ovom izvještaju) i PROVJERA POSLIJE — u skladu sa AGENTS.md "Baza i migracije" zahtjevom
(broj redova prije/poslije, transakcija). Nijedan drugi red u `product_tariff_mapping` nije
dirnut.

## Šta nije dirano
- Opšta politika "nikad ne prikazuj prijedlog bez izvora" (`tariff_decision_model.py`) —
  ostaje netaknuta, korisnik je EKSPLICITNO odbio opciju da se ta politika ponovo otvori.
- `sync_tariff_knowledge_base()` (Admin "Učenje iz XML-ova") — i dalje ne upisuje `source`
  kolonu; ovaj tehnički gap NIJE popravljen (otkriven usput, dokumentovan kao follow-up).
- Uzročni lanac (da li `learn_from_draft()` stvarno re-uči pogrešnu tarifu iz nepopravljenih
  faktura) — NIJE nezavisno dokazan kroz kod u ovom zadatku, samo naveden kao radna hipoteza
  potkrijepljena istorijom rasta `usage_count` (2→21).
- Preostalih 25+ "šumnih" zapisa i 2 niske-pouzdanosti duplikata — nedirano (vidi gore).

## Verifikacija
`RETURNING` na oba upita (3 obrisana, 4 ažurirana, tačni id-jevi potvrđeni). Naknadni SELECT
potvrđuje finalno stanje. Direktan poziv `decide_tariff_match()` potvrđuje da bi ishod sad bio
SHOW_STRONG umjesto SUPPRESS za identičan scenario kao na korisnikovom screenshotu. **Nije
end-to-end testirano kroz stvarnu GUI "Provjeri" akciju** (agent nema pristup pokrenutoj GUI
instanci) — vidi "Potrebna korisnička potvrda".

## Nezavisna provjera
- Checker korišćen: NE.
- Razlog: DB izmjena je mala, precizno ciljana (7 redova od 55598+ u tabeli), potpuno
  reverzibilna (imam pun snapshot PRIJE stanja u ovom izvještaju), i korisnik je aktivno
  učestvovao u odluci na svakom koraku (dva odvojena AskUserQuestion checkpointa). Preporučuje
  se da korisnik potvrdi u stvarnom GUI-ju (vidi ispod) kao finalna provjera.

## Pronađeni problemi
1. **Aktivan, rastući recidiv poznatog bug obrasca** — SUSSINA→38249993 mapa je narasla sa
   usage_count=2 (jul) na 21 (danas) uprkos ranijem "čišćenju". Radna hipoteza (vidi "Uzročni
   lanac") je da suzbijanje ispravnog prijedloga (nema izvora) tjera korisnike da nesvjesno
   potvrđuju pogrešnu tarifu, koja se onda re-uči. Ako je hipoteza tačna, ovaj popravak
   (dodavanje izvora ispravnim redovima) bi trebalo da PREKINE taj ciklus — ali to zahtijeva
   praćenje kroz vrijeme, ne može se potvrditi odmah.
2. `sync_tariff_knowledge_base()` (services/agent/learning/exporter_xml_indexer.py:455-502)
   ne upisuje `source`/`supplier` kolonu pri insertu — čak i kad bi se jutrošnji permission
   denied bug (`catalogs.exporter_xml_index`, nepovezan sa ovim zadatkom) popravio, taj
   specifičan reindex put ne bi rješavao "nema izvora" problem za NOVE proizvode. Van scope-a
   ovog zadatka, potencijalan budući fix ako se pojavi sličan slučaj za drugi proizvod.
3. Dvije duplikatne, konfliktne, niske-pouzdanosti mape i dalje postoje u bazi (`id=65927`,
   `id=65889`, vidi "Šta nije dirano") — trenutno bezopasne (gube po usage_count), ali
   vrijedi ih očistiti u budućem "database cleanup" zadatku ako se prostor za to otvori.

## Odbačene opcije
- Ponovno otvaranje opšte "nikad bez izvora" politike (SHOW_UNCONFIRMED) — korisnik eksplicitno
  odbio, uz razumijevanje da je to već probano i namjerno povučeno 28.7. zbog rizika.
- Popraviti (umjesto obrisati) 3 pogrešna 38249993 reda tako da pokazuju na 21069098 — odbačeno
  jer bi to duplirati/konfliktovati sa već postojećim ispravnim redovima (65199/65350/65351)
  za iste nazive; brisanje je čistije i tačno prati precedent iz §37 (22.7.).

## Konflikti / kontradiktorni izvori
Nema — nalaz je potvrđen kroz tri nezavisna izvora (DB upit, 25 stvarnih XML fajlova, i
`docs/context/history.md` istorijski zapisi §27-29/§64/§88 koji se potpuno slažu).

## Commitovi
Nema — ovo je čista izmjena podataka u produkcijskoj PostgreSQL bazi (dmserver), ne git commit.
Ovaj `agent_report` (i pratećа `docs/context/history.md`/memorija stavka) su commitovani
odvojeno kao dokumentacija.

## Rizici / ograničenja
Izmjena utiče na ponašanje "Provjeri"/auto-apply dijaloga za SVE buduće fakture koje sadrže
SUSSINA proizvode (pozitivan efekat po korisnikovoj ocjeni), ali kako `usage_count`-bazirano
rangiranje sad favorizuje ove redove, treba pratiti da se ne pojavi neki NOVI, drugačiji
proizvod čije ime slučajno sadrži "SUSSINA" kao podniz i pogrešno se poklopi (nije primijećeno
u 25 provjerenih XML fajlova, ali nije ni iscrpno isključeno za buduće, još neviđene fakture).

## Potreban follow-up
1. Vrijedi periodično (npr. za mjesec dana) provjeriti da li se `usage_count` na obrisanoj
   38249993 kombinaciji ponovo pojavljuje (potvrdilo bi ili oborilo hipotezu o uzročnom lancu).
2. Razmotriti da li `sync_tariff_knowledge_base()` treba popraviti da upisuje `source` (nalaz
   #2 gore) — samo ako se pojavi sličan slučaj za drugi proizvod.
3. Očistiti dvije preostale niske-pouzdanosti konfliktne mape (`id=65927`, `id=65889`) u
   budućem DB cleanup zadatku.

## Potrebna korisnička potvrda
**Isprobati u stvarnoj aplikaciji**: uvezi/otvori fakturu sa SUSSINA proizvodom koji ima
tarifu 38249993 (ili bilo koju pogrešnu), klikni "Provjeri" ili sačekaj automatsku provjeru
nakon uvoza — potvrditi da se sada nudi ispravna tarifa (21069098/21069092) sa jasnim izvorom
umjesto "nema boljeg prijedloga".
