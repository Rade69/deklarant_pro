# Sigurnosni pregled aplikacije Deklarant Pro

## 1. Sažetak za donošenje odluke

**Datum pregleda:** 2026-07-27  
**Procijenjena verzija:** grana `feature/agent-v2`, commit `c8b31e9`  
**Tip pregleda:** statička analiza koda i konfiguracije, pregled Agent V2 izvještaja i ograničena read-only provjera PostgreSQL servera  
**PostgreSQL server:** `192.168.100.154`, PostgreSQL 16

Ukupni sigurnosni nivo aplikacije procjenjuje se kao **srednji, približno 5/10**.
Deklarant Pro nema veliki udaljeni mrežni napadni prostor jer je desktop aplikacija
bez javnog HTTP servera, a veliki dio SQL pristupa je parametrizovan. Agent V2 je
značajno poboljšao integritet radnog toka kroz stvarne provjere, XML readiness
kapiju i obaveznu potvrdu prije izvoza.

Ipak, aplikacija još nije dovoljno ojačana za sistem koji obrađuje povjerljive
carinske i poslovne podatke. Najveći potvrđeni rizici nisu u samom chat agentu,
nego u kombinaciji:

1. aplikacijski PostgreSQL nalog ima `SUPERUSER` privilegiju;
2. aplikacija može instalirati i izvršiti proizvoljan Python parser;
3. aktivna DB lozinka ima samo 8 znakova i ranije je mogla biti izložena u Git
   historiji;
4. klijent koristi `sslmode=prefer`, pa TLS nije obavezan i identitet servera se
   ne provjerava;
5. poslovni XML/PDF dokumenti i lokalne baze nemaju centralno definisane granice
   resursa i zaštitu podataka na disku.

Zbog kombinacije prve tri stavke, kompromitovan parser ili `.env` ne bi ugrozio
samo jednu deklaraciju. Napadač bi potencijalno dobio ovlaštenja nad cijelim
PostgreSQL serverom.

## 2. Obuhvat i ograničenja

Pregled je obuhvatio:

- `agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md`;
- razlike grane `feature/agent-v2` u odnosu na `windows`;
- Agent V2 routing, tool policy, review servise, workflow orkestrator i XML
  readiness tok;
- PostgreSQL konfiguraciju, aktivni TLS i privilegije aplikacijskog naloga;
- učitavanje eksternih parsera;
- XML/PDF obradu;
- LLM providere i slanje podataka;
- logove i lokalno čuvanje poslovnih podataka;
- licenciranje, build i installer;
- dependency i Git higijenu.

Ovo nije formalni penetracioni test niti sigurnosna certifikacija. Nisu rađeni:

- aktivni napadi na produkcioni server;
- fuzzing stvarnim zlonamjernim XML/PDF/XLSX dokumentima;
- pregled firewall-a, Windows Defender/EDR-a, backup servera i mrežne opreme;
- audit PostgreSQL `pg_hba.conf` i operativnog sistema servera;
- kompletan CVE/SCA audit svih zavisnosti;
- reverzni inženjering finalnog produkcionog EXE/installer paketa.

## 3. Model prijetnji

Za ovu aplikaciju najrealnije prijetnje su:

- zlonamjeran ili kompromitovan parser dostavljen kao `.py` fajl;
- krađa `.env` fajla sa DB i LLM kredencijalima;
- kompromitovan Windows klijent ili korisnički nalog;
- presretanje ili preusmjeravanje DB veze na lokalnoj mreži;
- zlonamjeran, oštećen ili izuzetno veliki XML/PDF/XLSX dokument;
- pogrešna automatizovana carinska odluka bez dovoljno dokaza;
- curenje poslovnih podataka kroz cloud LLM, logove, Git ili backup;
- podmetnut nepotpisan installer ili EXE.

Niski prioritet u trenutnoj arhitekturi imaju klasični internet napadi na web
server, jer aplikacija ne izlaže javni HTTP API niti dolazni mrežni servis.

## 4. Potvrđeni nalazi

### SEC-01 — Aplikacijski DB nalog je PostgreSQL `SUPERUSER`

**Ozbiljnost:** KRITIČNA  
**Status:** potvrđeno direktnom read-only provjerom servera  
**Pogođeno:** povjerljivost, integritet i dostupnost cijelog DB servera

Aktivni aplikacijski nalog nije nazvan `postgres`, ali ima `rolsuper=true`.
Nema `CREATEROLE`, `CREATEDB`, `REPLICATION` ni `BYPASSRLS`, ali `SUPERUSER`
praktično zaobilazi provjere dozvola i čini ostala ograničenja nedovoljnim.

Provjera je pokazala i 132 efektivna write granta i 33 SELECT granta kroz
`information_schema.role_table_grants`. Broj grantova je manje važan od
činjenice da je nalog superuser.

**Scenarij zloupotrebe:** napadač preuzme `.env` ili instalira zlonamjeran
parser, zatim koristi DB kredencijale za čitanje/mijenjanje baza, uloga i
serverskih objekata van funkcionalnog scope-a Deklarant Pro aplikacije.

**Preporuka:**

- kreirati poseban `deklarant_app` login bez `SUPERUSER`, `CREATEDB`,
  `CREATEROLE`, `REPLICATION` i `BYPASSRLS`;
- dati samo potrebni `CONNECT`, `USAGE`, `SELECT`, `INSERT`, `UPDATE` i
  ograničeni `DELETE` nad tačno potrebnim objektima;
- odvojiti migracioni/admin nalog od runtime aplikacijskog naloga;
- ukloniti `CREATE` na `public` šemi ako aplikaciji nije potreban;
- rotirati lozinku odmah nakon prelaska na novi nalog.

**Kriterij zatvaranja:** read-only provjera aktivnog aplikacijskog naloga vraća
svih pet privilegijskih flagova kao `false`, a puni testovi i stvarni uvoz/izvoz
rade sa novim nalogom.

### SEC-02 — Parser plugin dobija proizvoljno izvršavanje koda

**Ozbiljnost:** VISOKA  
**Status:** potvrđeno u kodu  
**Pogođeno:** klijentski računar, `.env`, baze, dokumenti i mrežni resursi

`importers/plugin_loader.py` i `services/admin/plugin_service.py` koriste
`spec_from_file_location()` i `exec_module()`. Modul se izvršava tokom
učitavanja, uključujući top-level kod. „Validacija“ parsera zato nije pasivna
provjera: ona već izvršava sadržaj izabranog `.py` fajla.

Ovo je očekivana sposobnost Python plugin sistema, ali UI instalaciju može
predstaviti kao bezazlen uvoz parsera. Nema potvrđene provjere digitalnog
potpisa, izdavača, hasha, manifest allowliste ili sandboxa.

**Preporuka:**

- u produkciji podrazumijevano zabraniti proizvoljne eksterne `.py` parsere;
- dozvoliti samo interno potpisane parser pakete sa manifestom i hashom;
- provjeriti potpis prije bilo kakvog importa modula;
- instalaciju ograničiti na administratorski režim uz jasno upozorenje;
- parser izvršavati u zasebnom procesu sa ograničenim korisničkim pravima,
  bez direktnog pristupa DB lozinci i LLM ključevima;
- definisati timeout, limit memorije i dozvoljene izlazne podatke.

**Kriterij zatvaranja:** izmijenjen `.py` parser bez važećeg potpisa ne može
biti instaliran niti izvršen, a validacija potpisa ne importuje modul.

### SEC-03 — Slaba i istorijski potencijalno kompromitovana DB lozinka

**Ozbiljnost:** VISOKA  
**Status:** potvrđeno; rotacija nije potvrđena  
**Pogođeno:** PostgreSQL server i svi podaci dostupni aplikacijskom nalogu

Aktivna DB lozinka u lokalnom `.env` ima 8 znakova. Sama dužina ne dokazuje da
je lozinku lako pogoditi, ali je nedovoljna za nalog sa visokim ovlaštenjima.
`docs/CONTEXT.md` dodatno bilježi da je ranija lozinka mogla biti izložena u
Git historiji.

`.env` je običan tekst i njegov ACL sadrži šest lokalnih identiteta/grupa.
Nisu svi identiteti nužno različiti ljudski korisnici, ali površina pristupa
je šira nego što je poželjno za DB i LLM tajne.

**Preporuka:**

- rotirati DB lozinku nakon ukidanja superuser naloga;
- koristiti najmanje 24 slučajna znaka;
- ukloniti stare kredencijale i testirati da više ne rade;
- koristiti Windows Credential Manager ili DPAPI;
- ako `.env` ostaje, ograničiti ACL na aplikacijskog Windows korisnika i
  lokalne administratore;
- nikad ne ispisivati `connection_string`, jer sadrži lozinku.

### SEC-04 — TLS radi, ali nije obavezan niti potvrđuje identitet servera

**Ozbiljnost:** VISOKA  
**Status:** djelimično ublaženo, ali otvoreno  
**Pogođeno:** DB kredencijali i poslovni podaci u tranzitu

Pozitivno je što je server konfigurisan sa `ssl=on`, aktivna sesija koristi
TLS, prijavljeni su TLS verzija i cipher, a `password_encryption` je
`scram-sha-256`.

Klijent ipak koristi podrazumijevani `sslmode=prefer`. Ako TLS nije dostupan,
klijent smije nastaviti bez njega. Takođe se ne provjerava da certifikat
pripada očekivanom serveru. IP adresa otežava pravilnu `verify-full` provjeru
ako certifikat nema odgovarajući IP SAN.

**Preporuka:**

- kratkoročno postaviti `DB_SSLMODE=require`;
- konačno koristiti DNS ime servera, vlastiti CA i `verify-full`;
- dodati `sslrootcert` i certifikat sa odgovarajućim SAN zapisom;
- odbiti startup ako uspostavljena sesija nije TLS.

### SEC-05 — XML parsiranje nije centralno sigurnosno ojačano

**Ozbiljnost:** SREDNJA  
**Status:** potvrđeno  
**Pogođeno:** dostupnost klijenta i obrada dokumenata

U sigurnosno relevantnim folderima pronađeno je najmanje 11 Python fajlova
koji direktno parsiraju XML. Koriste se standardni `ElementTree` i `lxml`
pozivi bez jedinstvene ulazne politike. Nije pronađena eksplicitno uključena
XXE konfiguracija, pa klasični XXE nije potvrđen.

Ipak, nema centralnih limita veličine fajla, dubine stabla, broja elemenata i
vremena parsiranja. To ostavlja prostor za resource-exhaustion/DoS dokumente
i nekonzistentno ponašanje različitih parsera.

**Preporuka:**

- uvesti jednu sigurnu XML ulaznu funkciju;
- za stdlib koristiti `defusedxml`;
- za `lxml` koristiti `resolve_entities=False`, `load_dtd=False`,
  `no_network=True`, `huge_tree=False`;
- ograničiti veličinu, dubinu, broj elemenata i vrijeme parsiranja;
- dodati negativne testove za DTD, entity expansion, duboko stablo i veliki
  dokument.

### SEC-06 — Osjetljivi poslovni podaci mogu završiti u logovima

**Ozbiljnost:** SREDNJA  
**Status:** potvrđeno u kodu  
**Pogođeno:** povjerljivost partnera i deklaracija

Postoje log pozivi koji uključuju putanje faktura, nazive izvoznika/uvoznika,
JIB, nazive robe i XML fajlova. Logovi nisu praćeni Gitom, što je dobro, ali
su obični lokalni fajlovi i nemaju centralnu redakciju.

**Preporuka:**

- napraviti centralni filter koji maskira JIB, DB/LLM tajne i partner podatke;
- u INFO nivou koristiti interne identifikatore i broj obrađenih stavki;
- pune poslovne vrijednosti dozvoliti samo u eksplicitnom debug režimu;
- uvesti rotaciju, maksimalnu veličinu, rok čuvanja i restriktivan ACL.

### SEC-07 — Direktni Groq put zaobilazi centralnu LLM politiku

**Ozbiljnost:** SREDNJA/VISOKA  
**Status:** potvrđeno  
**Pogođeno:** privatnost i integritet tarifnih prijedloga

Većina novog Agent V2 toka koristi centralni `LLMProvider` i tool-first
politiku. Međutim, `services/agent/tariff/hybrid_tariff_agent.py` direktno
inicijalizuje `Groq`. Time se zaobilaze centralizovani fallback, privatnosna
kontrola i jedinstveno auditovanje.

Rizik je dvostruk:

- naziv robe, porijeklo ili RAG kontekst mogu otići cloud provideru drugim
  putem od očekivanog;
- model može generisati tarifni prijedlog bez dovoljno autoritativnog dokaza.

**Preporuka:** ukloniti direktne provider klijente, sve pozive provesti kroz
`LLMProvider`, primijeniti isti data-minimization filter i zabraniti da LLM
popunjava carinski zaključak kada lokalni alat vrati `unknown` ili
`needs_review`.

### SEC-08 — Lokalni podaci i Git dataseti nisu šifrovani

**Ozbiljnost:** SREDNJA  
**Status:** potvrđeno  
**Pogođeno:** povjerljivost poslovnih podataka

Lokalne SQLite baze, XML arhive, logovi i radni dokumenti oslanjaju se na
Windows ACL i zaštitu računara. Nije pronađena aplikacijska enkripcija podataka
na disku. Partner JSON datasetovi se prate Gitom; privatni repozitorij smanjuje
rizik, ali svaki klon i Git historija dobijaju kopiju.

**Preporuka:** BitLocker na klijentima/serveru, šifrovani backup, restriktivni
ACL, definisan rok čuvanja i provjera da li su stvarni partner podaci nužni u
Git repozitoriju.

### SEC-09 — Privatni ključ za licence je visoko vrijedan razvojni sekret

**Ozbiljnost:** VISOKA operativna  
**Status:** djelimično ublaženo  
**Pogođeno:** integritet licenciranja

Privatni ključ nije praćen Gitom i generator upozorava da ne smije ući u
aplikaciju. To je dobro. Ipak, ključ postoji u razvojnom workspace-u. Krađa
ključa omogućila bi izdavanje lažnih licenci.

**Preporuka:** držati ključ van redovnog projekta, na offline mediju ili u
namjenskom secrets vault/HSM rješenju; build i klijentska instalacija smiju
sadržati samo javni ključ.

### SEC-10 — Produkcijski EXE i installer nemaju potvrđeno code signing

**Ozbiljnost:** SREDNJA  
**Status:** potvrđeno odsustvo konfiguracije u pregledanom repou  
**Pogođeno:** supply-chain i povjerenje korisnika

Nije pronađena SignTool/Authenticode konfiguracija u build i installer
fajlovima. Bez potpisa korisnik ne može kriptografski potvrditi ko je izdao
installer i da li je mijenjan.

**Preporuka:** potpisati EXE i installer Authenticode certifikatom, uključiti
timestamp servis i objavljivati SHA-256 hash službene verzije.

### SEC-11 — Dependency audit nije dio potvrđenog release gate-a

**Ozbiljnost:** SREDNJA  
**Status:** nepotpuno provjereno  
**Pogođeno:** cijela aplikacija

Repo ima `uv.lock`, `pyproject.toml` i requirements fajlove, što omogućava
ponovljive verzije. U ovom pregledu nije izvršen kompletan CVE audit i nije
potvrđeno da build/release blokira poznate ranjive verzije.

**Preporuka:** u CI/release uvesti `pip-audit` ili ekvivalentan SCA alat,
SBOM (CycloneDX/SPDX), mjesečni dependency review i blokiranje kritičnih/visokih
CVE nalaza uz dokumentovan izuzetak.

## 5. Agent V2 — sigurnosna poboljšanja

Izvještaj `2026-07-27_popravka-wiring-gapova-agent-v2.md` i pregled koda
potvrđuju nekoliko važnih poboljšanja:

- `prikazi` i `provjeri` sada vode na različite, stvarne servisne tokove;
- LLM tool-use je povezan i u V2 putu, umjesto nekontrolisanog plain chat
  fallbacka;
- workflow ima 10 stvarnih kapija;
- XML preflight sada pokušava izgraditi stvarni XML na kopiji drafta;
- izvoz se blokira na `BLOCKED` rezultatu i traži eksplicitnu potvrdu;
- `AuditEvent` više ne ruši svaku poruku zbog neispravnih kwargs;
- uvedeni su deterministički review servisi i HTML escaping renderer;
- 23 ciljana testa i puni suite od 1263 testa prošli su bez pada na toj grani.

Ovo poboljšava **integritet deklaracije** i smanjuje rizik da agent samo
prikaže snapshot umjesto stvarne provjere. Ne rješava klasične infrastrukturne
rizike iz SEC-01 do SEC-11.

## 6. Otvoreni rizici specifični za Agent V2

### 6.1 Workflow je i dalje vezan za GUI thread

Orkestrator ponovo koristi `_puna_auto_pipeline`, koji sadrži
`QApplication.processEvents()` i inline `QMessageBox`. Proces je re-entrantan:
korisnik potencijalno može pokrenuti drugu radnju dok je pipeline u toku.

Potrebni su workflow lock, onemogućavanje konfliktnih akcija i revision/
fingerprint provjera drafta između kapija.

### 6.2 Kapije mogu biti fail-open

`xml_readiness_service.py` na više mjesta hvata širok `Exception` i bilježi da
je validacija „skipped“. Potrebno je dokazati da svaka preskočena obavezna
provjera završava kao `BLOCKED`, a ne kao upozorenje koje se može potvrditi.
Za carinski XML tehnički kvar validatora treba biti fail-closed.

### 6.3 Rezultat provjere može zastarjeti nakon izmjene drafta

Draft još nema pouzdan revision/fingerprint mehanizam vezan za rezultat
validacije. Ako se podatak promijeni nakon prolaska kapije, raniji rezultat
ne smije ostati važeći.

### 6.4 Indeksiranje `scope="row"` nije potpuno razjašnjeno

Review servisi koriste `ordinals` kao 0-indeksirane pozicije, dok korisnik
prirodno govori 1-indeksirani redni broj. To može provjeriti pogrešnu stavku.
Ovo je prije svega integritetski rizik.

### 6.5 Agent V2 nije još jednako prisutan u svim isporukama

Procijenjeni kod je na `feature/agent-v2`, dok je glavni radni branch
`windows`. Izvještaj navodi više od 330 ranije postojećih razlika u
`dist_client`; samo sedam fajlova iz wiring popravke je ciljano
sinhronizovano. Sigurnosna osobina koja postoji samo u root kodu ili feature
grani ne štiti instalirani EXE.

Prije produkcije mora postojati manifest pariteta root/dist_client/build
artefakta i test baš nad isporučenim paketom.

## 7. Pozitivni nalazi

Tokom pregleda nisu pronađeni potvrđeni primjeri:

- javnog mrežnog listenera ili ugrađenog HTTP servera;
- `shell=True`/`os.system()` za korisničke putanje;
- isključene TLS certifikat provjere kroz `verify=False`;
- aktivnog `.env` ili privatnog licencnog ključa u trenutnom Git sadržaju;
- direktne SQL injekcije u pregledanim dinamičkim upitima.

Dodatne pozitivne kontrole:

- PostgreSQL 16 koristi TLS u aktivnoj sesiji i `scram-sha-256`;
- SQL vrijednosti su u pregledanim mjestima parametrizovane;
- LLM pozivi se obavljaju u worker threadovima;
- postoje ToolPolicy nivoi READ_ONLY/PROPOSE/MUTATE i potvrde za izmjene;
- cloud put ima uvedeno maskiranje dijela partner podataka;
- privatni licencni ključ je gitignored, a javni ključ se koristi za provjeru
  RSA/SHA-256 potpisa;
- poslovni XML izvoz sada prolazi stvarni readiness/preflight tok.

## 8. Prioritetni plan sanacije

### P0 — prije šire produkcione automatizacije

1. Ukinuti `SUPERUSER` aplikacijskom DB nalogu i uvesti least-privilege nalog.
2. Rotirati DB lozinku i onemogućiti stare kredencijale.
3. Onemogućiti proizvoljnu instalaciju nepotpisanih Python parsera.
4. Postaviti najmanje `sslmode=require`; pripremiti `verify-full`.
5. Potvrditi da svaka obavezna Agent V2 kapija radi fail-closed.

### P1 — prije oslanjanja na „jedna komanda do XML-a“

1. Uvesti draft revision/fingerprint i poništavanje zastarjele validacije.
2. Uvesti workflow lock i ukloniti re-entrant GUI ponašanje.
3. Centralizovati sigurnu XML obradu i limite za XML/PDF/XLSX.
4. Sve LLM putanje provesti kroz `LLMProvider`.
5. Uvesti centralnu redakciju logova i politiku čuvanja.
6. Napraviti kontrolisani puni `dist_client` resync i test produkcionog EXE-a.

### P2 — ojačavanje isporuke i zaštite podataka

1. Authenticode potpisivanje EXE-a i installera.
2. Dependency CVE gate i SBOM.
3. BitLocker, šifrovani backup i revizija ACL-ova.
4. Uklanjanje stvarnih partner dataseta iz Gita ako nisu neophodni.
5. Premještanje privatnog licencnog ključa u offline/vault okruženje.

## 9. Predloženi sigurnosni release gate

Nova verzija ne treba biti označena kao produkcijska dok nisu ispunjeni:

- aplikacijski DB nalog nije superuser i prolazi test minimalnih privilegija;
- DB veza se odbija bez TLS-a;
- nepotpisan parser se ne može izvršiti;
- svi Agent V2 obavezni validator kvarovi daju `BLOCKED`;
- izmjena drafta poništava raniji readiness rezultat;
- zlonamjerni XML/PDF/XLSX testovi ne ruše niti zamrzavaju aplikaciju;
- logovi ne sadrže JIB, lozinke, API ključeve ni pune partner podatke;
- root, `dist_client` i produkcijski artefakt imaju potvrđen paritet;
- puni test suite, SCA audit i smoke test finalnog EXE-a prolaze;
- EXE i installer imaju važeći digitalni potpis.

## 10. Zaključak

Agent V2 popravke su stvarno poboljšale sigurnost poslovnog toka: provjera više
nije samo prikaz podataka, XML preflight je izvršiv, a izvoz ima kapiju i
potvrdu. To je važan napredak u zaštiti integriteta deklaracije.

Ukupna aplikacijska sigurnost ipak ostaje srednja zbog kritične DB
konfiguracije i neograničenog plugin modela. Najveći dobitak neće doći iz još
jednog LLM prompta, nego iz ukidanja DB superuser naloga, rotacije tajni,
potpisivanja/sandboxovanja parsera i obaveznog TLS identiteta servera.

Nakon zatvaranja P0 stavki realna procjena može porasti na približno **7/10**.
Nakon P1/P2 kontrola, dinamičkog testa i provjere finalnog instalacionog
paketa, aplikacija bi mogla dostići nivo prikladan za kontrolisanu produkciju
osjetljivih carinskih podataka.
