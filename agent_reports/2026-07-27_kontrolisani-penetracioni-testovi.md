# Kontrolisani penetracioni testovi

## Datum

2026-07-27

## Agent

Codex

## Scope

- Deklarant Pro izvorni i `dist_client` kod
- parser plugin trust granica
- XML ulazne tačke
- redakcija logova
- SQL konstrukcija
- Git sadržaj i ograničena provjera historije
- PostgreSQL runtime veza prema `192.168.100.154:5432`

Testovi su bili nedestruktivni. Nisu rađeni brute-force, DoS, široko skeniranje
portova, izmjena produkcijskih podataka ni pokušaj eksploatacije drugih uređaja.

## Status izvora

| Izvor | Status |
| --- | --- |
| Trenutni kod `feature/agent-v2` | autoritativan |
| `docs/SECURITY_AUDIT_2026-07-27.md` | aktivan |
| Aktivna PostgreSQL sesija `deklarant_app` | autoritativna za runtime nalaz |
| Git historija | provjerena samo po obrascima i metapodacima, bez ispisa tajni |

## GitNexus impact

Nije mijenjan aplikacijski simbol. Penetracioni testovi su read-only; impact
analiza nije potrebna za izmjenu koda.

## Šta je urađeno

1. Statički sken praćenog sadržaja za privatne ključeve, API ključeve,
   PostgreSQL URL kredencijale i DB lozinke.
2. Sken za `shell=True`, `os.system`, Python `eval/exec`, direktni XML parse
   i f-string SQL.
3. Negativni testovi nepotpisanog/zlonamjernog parsera.
4. XXE/DTD, dubina, broj elemenata i veličina XML payload testovi.
5. Test redakcije DB URL-a, API tajni, JIB-a i korisničke putanje.
6. Test konfiguracionog i runtime DB TLS/privilege guarda.
7. Mrežna provjera ciljanog PostgreSQL porta.
8. Stvarna read-only SQL provjera TLS protokola, ciphera, runtime privilegija,
   naslijeđenih rola i statusa `radovan` naloga.
9. Ograničena Git-history pretraga commit metapodataka za `DB_PASSWORD` i
   privatne ključeve.

## Zašto je urađeno

Cilj je bio provjeriti da li se nove sigurnosne kontrole mogu zaobići kroz
najrealnije desktop napadne površine: zlonamjerni dokument/plugin, curenje
tajne, SQL konstrukciju i kompromitovan DB kredencijal.

## Kako je urađeno

- Korišćeni su `git grep`, `rg`, postojeći sigurnosni pytest payloadi,
  `Test-NetConnection` i parametrizovani read-only PostgreSQL upiti.
- Stvarna lozinka i API ključevi nisu ispisani.
- Testovi koji namjerno očekuju odbijanje payload-a izvršeni su u testnom
  okruženju, ne nad produkcijskim podacima.

## Nalazi

### PEN-01 — `radovan` je i dalje login superuser

**Ozbiljnost:** VISOKA

**Status:** potvrđeno na serveru

```text
rolname=radovan
rolcanlogin=true
rolsuper=true
```

Aplikacija koristi `deklarant_app`, ali stari kredencijal i dalje može dati
potpunu kontrolu nad PostgreSQL serverom. Ovo ostaje najvažniji otvoreni rizik.

**Preporuka:** nakon provjere da ga drugi sistem ne koristi, administrator
primjenjuje `NOLOGIN`, prekida postojeće sesije i postavlja `PASSWORD NULL`.

### PEN-02 — tri migracione skripte zaobilaze sigurni XML gateway

**Ozbiljnost:** SREDNJA ako primaju nepouzdan XML, inače NISKA

**Status:** potvrđeno u kodu

Direktni `ElementTree.parse` ostaje u:

- `database/migrate_inspection_document_history.py`
- `database/ingest_tariff_kb.py`
- `database/import_partners_from_xml.py`

Glavni aplikacijski import tok koristi `safe_xml`, ali ručno pokretanje ovih
skripti nad zlonamjernim ili ekstremno velikim XML fajlom zaobilazi centralne
limite.

**Preporuka:** migrirati ih na `services.security.safe_xml.safe_parse` prije
sljedećeg korišćenja sa spoljnim fajlovima.

### PEN-03 — f-string SQL postoji, ali injection nije potvrđen

**Ozbiljnost:** NISKA / hardening dug

**Status:** pregledano

Pronađeni f-string SQL upiti interpoliraju interno generisane liste `%s`/`?`
placeholdera, fiksne whitelist kolone ili uslovne konstante. Vrijednosti
korisnika se i dalje šalju kao DB parametri. Nije potvrđen put kojim korisnik
može ubrizgati proizvoljan SQL.

Ipak, obrazac krši strogu projektnu konvenciju i otežava automatsko razlikovanje
bezbjednog od opasnog SQL-a.

**Preporuka:** postepeno zamijeniti dinamičke identifikatore
`psycopg2.sql` kompozicijom ili centralnim helperom i dodati statički CI rule.

### PEN-04 — PostgreSQL port je mrežno dostupan klijentu

**Ozbiljnost:** INFORMATIVNA

**Status:** očekivano

`192.168.100.154:5432` je dostupan sa testnog računara. To je potrebno za rad
aplikacije, ali test nije mogao potvrditi da firewall/`pg_hba.conf` dozvoljava
samo odobrenu LAN/VPN grupu.

**Preporuka:** na serveru ograničiti 5432 na tačno potrebne klijentske
IP/subnet opsege; ne izlagati port internetu.

### PEN-05 — Git historija sadrži reference na DB_PASSWORD

**Ozbiljnost:** INFORMATIVNA uz postojeću rotaciju

**Status:** djelimično potvrđeno

Trenutno nema praćenog `.env`, `.pem` ili `.key` fajla i nisu pronađeni stvarni
ključevi u trenutnom sadržaju. Više istorijskih commitova mijenjalo je tekst
koji sadrži `DB_PASSWORD`; provjera metapodataka namjerno nije ispisivala stare
vrijednosti, pa ne dokazuje da je svaki pogodak stvarna tajna.

Pošto postoji ranija sumnja na izložen kredencijal, rotacija/invalidacija
`radovan` naloga ostaje obavezna bez obzira na sadržaj starih commitova.

## Pozitivni rezultati

### Parser granica

- nepotpisan parser je odbijen;
- zlonamjerni top-level kod nije izvršen;
- potpis se provjerava prije importa.

### XML granica glavne aplikacije

- DTD i ENTITY payloadi su odbijeni;
- prevelik XML je odbijen;
- prekoračenje dubine i broja elemenata je odbijeno;
- nije pronađen direktni nesigurni XML parse u glavnom GUI/service/import toku.

### Logovi

- DB URL lozinka, API ključ, JIB i korisnički dio Windows putanje su redigovani.

### PostgreSQL runtime

```text
current_user=deklarant_app
ssl=true
TLSv1.3
TLS_AES_256_GCM_SHA384
```

Svi flagovi su `false`:

- `rolsuper`
- `rolcreatedb`
- `rolcreaterole`
- `rolreplication`
- `rolbypassrls`

Dodatno:

- nema CREATE pravo nad bazom;
- nema CREATE pravo nad `public` šemom;
- nije član `radovan` uloge;
- nema naslijeđenu opasnu `pg_*` sistemsku rolu.

### Tajne i command execution

- nije pronađen stvarni privatni ključ ili aktivni API ključ u praćenom kodu;
- `shell=True` i `os.system()` nisu pronađeni;
- `exec()` pogodci su Qt event-loop/dijalozi, ne Python izvršavanje stringa.

## Verifikacija

Sigurnosni testni skup:

```text
37 passed
```

Obuhvata:

- 14 parser testova;
- 6 sigurnih XML testova;
- 3 redaction testa;
- 7 DB runtime guard testova;
- 7 DB settings/TLS testova.

Mreža:

```text
192.168.100.154:5432 TcpTestSucceeded=True
```

## Šta nije dirano

- Nije mijenjan aplikacijski kod.
- Nisu mijenjani DB podaci, role ili server konfiguracija.
- Nisu dirane postojeće izmjene u `docs/CONTEXT.md`, `admin_view.py` i
  generisanim `ui/` fajlovima.
- Nisu testirani drugi uređaji, portovi ni servisi na mreži.

## Konflikti / kontradiktorni izvori

Raniji sigurnosni audit navodi da aplikacija koristi least-privilege nalog, što
je potvrđeno. To ne znači da je stari superuser uklonjen: stvarni server
potvrđuje da `radovan` još ima `LOGIN`. Nema konflikta; radi se o odvojenom
runtime i istorijskom nalogu.

## Commitovi

Izvještaj se commitije kao dokumentaciona promjena; aplikacijski kod nije
mijenjan.

## Rizici / ograničenja

- Ovo nije formalni eksterni penetracioni test.
- Nije pregledan `pg_hba.conf`, firewall, OS, EDR ni backup.
- Nije rađen PDF/XLSX fuzzing.
- Nije testirana otpornost na DoS velikim brojem paralelnih konekcija.
- Git-history sken po obrascu može dati lažno pozitivne i lažno negativne
  rezultate.

## Potreban follow-up

1. P0: onemogućiti `radovan` login i staru lozinku.
2. P1: tri migracione XML skripte prebaciti na `safe_parse`.
3. P1: pregledati `pg_hba.conf` i firewall allowlist.
4. P2: dodati PDF/XLSX fuzzing i CI statički SQL rule.
5. P2: nezavisan test finalnog potpisanog EXE/installer artefakta.

## Potrebna korisnička potvrda

Potvrditi da `radovan` ne koristi nijedan drugi posao ili aplikacija prije
primjene `NOLOGIN`.
