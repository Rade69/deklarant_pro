# Sigurnosni pregled aplikacije Deklarant Pro

## 1. Izvršni sažetak

**Datum prvog pregleda:** 2026-07-27

**Datum hardening verifikacije:** 2026-07-27

**Grana:** `feature/agent-v2`

**PostgreSQL server:** `192.168.100.154`, PostgreSQL 16

**Tip pregleda:** statička analiza, ciljani negativni testovi, puni regresioni
testovi, SCA audit zaključanih zavisnosti i kontrolisana provjera runtime DB veze

Nakon realizovanog P0/P1 hardeninga, sigurnosni nivo izvornog i
`dist_client` koda procjenjuje se na **oko 8/10 za kontrolisanu internu
produkciju**. Početna procjena je bila približno 5/10.

Najveći dobitak je uklanjanje lanca „nepotpisan parser → superuser DB nalog“:

- aplikacija sada koristi poseban `deklarant_app` nalog bez administrativnih
  privilegija;
- runtime konekcioni pool odbija netls vezu i privilegovan DB nalog;
- eksterni parseri su podrazumijevano zabranjeni i moraju imati važeći
  RSA-PSS/SHA-256 potpis prije bilo kakvog izvršavanja;
- obavezne XML readiness provjere sada rade fail-closed;
- zaključane produkcijske zavisnosti nemaju poznate ranjivosti prema
  `pip-audit` bazi u trenutku provjere.

Procjena još nije 9/10 ili viša jer ostaju infrastrukturni i release koraci:

1. istorijski nalog `radovan` je i dalje login superuser dok ga administrator
   ne rotira ili onemogući;
2. TLS je obavezan (`require`), ali identitet servera još nije potvrđen kroz
   vlastiti CA i `verify-full`;
3. produkcijski Authenticode certifikat nije instaliran i finalni EXE/installer
   nije potpisan i smoke-testiran;
4. lokalne baze, dokumenti i backup i dalje zavise od Windows/BitLocker zaštite;
5. parser je potpisan i default-deny, ali nije izolovan u zasebnom OS procesu.

## 2. Obuhvat i ograničenja

Pregled i hardening obuhvatili su:

- PostgreSQL TLS, privilegije i startup runtime guard;
- parser instalaciju, validaciju, potpis i učitavanje;
- Agent V2 readiness, XML preflight i zastarjelost rezultata;
- sve direktne XML ulazne tačke u aplikacijskom kodu;
- direktne Groq putanje i centralni `LLMProvider`;
- redakciju tajni i identifikatora u runtime logovima;
- dependency audit, CI gate, Dependabot i Windows code-signing build gate;
- paritet svake sigurnosno izmijenjene root/`dist_client` implementacije;
- puni testni paket u zaključanom `uv` okruženju.

Nisu rađeni:

- penetracioni test servera, firewall-a, `pg_hba.conf` i Windows domena;
- dinamički fuzzing PDF/XLSX parsera;
- pregled sadržaja svih istorijskih Git commitova i svih backup kopija;
- test finalnog instalera na čistoj Windows mašini;
- provjera BitLocker/EDR/backup politike;
- izdavanje i instalacija produkcijskog CA ili Authenticode certifikata.

## 3. Stanje nalaza

| Nalaz | Početni rizik | Novo stanje | Preostali rizik |
| --- | --- | --- | --- |
| SEC-01 DB superuser | Kritičan | Runtime prebačen na `deklarant_app`; kod odbija privilegovanu ulogu | Stari `radovan` login superuser još treba onemogućiti/rotirati |
| SEC-02 proizvoljan parser | Visok | Default-deny; AST provjera i obavezan RSA potpis prije importa | Nema OS sandboxa za odobren parser |
| SEC-03 slaba DB tajna | Visok | Nova slučajna tajna, novi nalog, restriktivan ACL | Stara `radovan` tajna mora biti invalidirana |
| SEC-04 `sslmode=prefer` | Visok | Default i aktivna konfiguracija su `require`; runtime provjera stvarne TLS sesije | Prelazak na CA + `verify-full` |
| SEC-05 XML ulazi | Srednji | Centralna sigurna ulazna funkcija i negativni testovi | PDF/XLSX resource limiti nisu objedinjeni |
| SEC-06 logovi | Srednji | Centralni filter rediguje tajne, JIB i korisničke putanje | Politika roka čuvanja i ACL log direktorijuma |
| SEC-07 direktni Groq | Srednji/visok | Direktni pozivi uklonjeni iz tarifnog i KB toka | Cloud data-minimization treba periodično auditovati |
| SEC-08 podaci na disku | Srednji | Bez aplikacijske promjene | BitLocker, šifrovan backup i retention |
| SEC-09 licencni ključ | Visok operativni | Privatni ključ ostaje gitignored | Premještanje u offline/vault okruženje |
| SEC-10 code signing | Srednji | Build odbija produkcijski EXE bez certifikata i verifikuje potpis | Nabaviti certifikat, potpisati i installer |
| SEC-11 zavisnosti | Srednji | CI `pip-audit`, Dependabot i ažurani lock; trenutni audit čist | Dodati SBOM i redovan review izuzetaka |

## 4. Realizovane kontrole

### 4.1 PostgreSQL least privilege i TLS

Na serveru je kreiran/konfigurisan runtime nalog `deklarant_app` sa:

- `NOSUPERUSER`;
- `NOCREATEDB`;
- `NOCREATEROLE`;
- `NOREPLICATION`;
- `NOBYPASSRLS`;
- samo potrebnim `CONNECT`, šemskim i tabelarnim pravima.

Aktivne lokalne konfiguracije koriste novi nalog, slučajnu lozinku i
`DB_SSLMODE=require`. Lozinka se ne nalazi u ovom dokumentu niti u Git
sadržaju. ACL `.env` fajlova ograničen je na aktivnog korisnika, SYSTEM i
Administrators.

`database/db.py` više ne vjeruje samo konfiguraciji. Odmah nakon otvaranja
poola provjerava `pg_stat_ssl` i `pg_roles`; pool se zatvara i startup pada ako
veza nije TLS ili uloga ima bilo koji zabranjeni privilegijski flag.

**Preostalo:** `radovan` je istorijski login superuser. Aplikacija ga više ne
koristi, ali stari kredencijal mora administrator invalidirati. Bez tog koraka
SEC-01/SEC-03 nisu potpuno zatvoreni na nivou cijelog servera.

### 4.2 Potpisani parseri

Instalacija parsera više ne izvršava fajl radi „validacije“. Prvo se radi
statička AST provjera, zatim:

- eksterni plugin mora biti eksplicitno omogućen;
- mora postojati javni ključ iz kontrolisane konfiguracije;
- uz parser mora postojati `.py.sig`;
- RSA-PSS/SHA-256 potpis mora biti važeći;
- tek tada je dozvoljen `exec_module`.

Dodani su alati za generisanje signing ključa i potpis parsera. Privatni
ključevi i potpisi su isključeni iz Gita. Negativni test dokazuje da
zlonamjerni top-level kod nepotpisanog fajla nije izvršen.

### 4.3 Agent V2 i XML izvoz

Svaki tehnički kvar obavezne provjere sada proizvodi blokirajući
`REQUIRED_CHECK_FAILED`; više nema tihog `checks_skipped` puta do READY.
Nedostupan ili neuspješan stvarni XML builder takođe blokira izvoz.

Rezultat readiness provjere vezan je za `draft.revision`. Revision se ponovo
provjerava poslije korisničke potvrde i poslije izbora izlaznog fajla. Izmjena
drafta u međuvremenu prekida izvoz i zahtijeva novu provjeru.

### 4.4 Sigurna XML obrada

Sve pronađene direktne `ElementTree.parse`/`lxml.parse` ulazne tačke
preusmjerene su kroz `services/security/safe_xml.py`. Kontrola:

- odbija DTD i ENTITY deklaracije;
- za `lxml` isključuje entity resolution, DTD loading, mrežu i `huge_tree`;
- ograničava veličinu dokumenta, broj elemenata i dubinu;
- ima testove za DTD/entity, duboko stablo, prevelik fajl i normalan XML.

### 4.5 Centralni LLM put

Tarifni agent i Knowledge Base reranker više ne inicijalizuju Groq direktno.
Koriste centralni `LLMProvider`, pa dijele fallback i konfiguracionu politiku.
Ako lokalni/RAG sloj nema tarifne kandidate, LLM ne smije izmisliti tarifni
broj iz slobodnog odgovora.

### 4.6 Redakcija logova

Runtime handleri imaju centralni `SensitiveDataFilter`. Maskiraju:

- DB i API tajne poznate iz okruženja;
- PostgreSQL URL kredencijale;
- Groq/OpenAI/Gemini obrasce ključeva;
- 13-cifrene JIB vrijednosti;
- korisnički segment Windows putanje.

### 4.7 Supply-chain i release kontrole

- GitHub Actions ima zaključani produkcijski export i `pip-audit` gate.
- Dependabot prati `uv` zavisnosti sedmično.
- Ranjive zaključane verzije su nadograđene.
- Ponovljeni audit vraća `No known vulnerabilities found`.
- Produkcijski Windows build zahtijeva SHA-1 thumbprint signing certifikata,
  potpisuje SHA-256/timestamp postavkama i zatim verifikuje Authenticode.

## 5. Verifikacija

### Automatizovani testovi

Kompletan paket u sinhronizovanom zaključanom `uv` okruženju:

```text
1296 passed, 72 skipped, 5 xfailed
```

`xfailed` testovi su ranije definisani očekivani karakterizacioni slučajevi,
ne novi sigurnosni padovi.

Posebno su pokriveni:

- fail-closed readiness i nedostupan XML builder;
- promjena draft revizije nakon potvrde;
- odbijanje nepotpisanog parsera bez izvršavanja top-level koda;
- provjera parser potpisa;
- DB TLS/privilege startup guard;
- bezbjedna XML ograničenja;
- centralni LLM put;
- redakcija logova.

### SCA rezultat

Audit zaključanih produkcijskih zavisnosti:

```text
No known vulnerabilities found
```

Ovo je vremenski ograničen rezultat javne CVE baze, ne garancija da zavisnosti
nemaju nepoznate ranjivosti.

### Runtime DB rezultat

Stvarna konekcija aplikacijskog poola sa `deklarant_app` nalogom prošla je:

- TLS sesija aktivna;
- svih pet zabranjenih privilegijskih flagova su `false`;
- osnovne aplikacijske DB operacije i puni testovi rade.

## 6. Paritet root/`dist_client`

Sekcija 6.5 prvobitnog izvještaja bila je zastarjela nakon punog resync commita
`ac49b51`: tada više nije bilo 330+ stvarnih Python razlika. Sve sigurnosne
izmjene iz ovog hardeninga urađene su i u odgovarajućim `dist_client`
implementacijama. Namjerni izuzetak je kompatibilni stub
`dist_client/services/tariff/tariff_mapping_service.py`, koji uvozi kanonsku
root implementaciju.

Ovaj paritet ne zamjenjuje smoke test finalnog EXE-a. Za produkcijski release
i dalje treba izgraditi, potpisati i testirati stvarni artefakt.

## 7. Preostali prioriteti

### P0 operativno — obavezno prije široke produkcije

1. PostgreSQL administrator treba onemogućiti login ili rotirati lozinku naloga
   `radovan`, pa potvrditi da stari kredencijal više ne radi.
2. Nabaviti produkcijski Authenticode certifikat; potpisati i verifikovati EXE
   i installer.
3. Napraviti server certifikat sa odgovarajućim DNS/IP SAN zapisom, distribuirati
   CA i preći na `DB_SSLMODE=verify-full`.

### P1

1. Izolovati odobrene parsere u zaseban proces bez DB/LLM tajni, sa timeoutom,
   memorijskim limitom i strogo definisanim izlazom.
2. Uvesti centralne resource limite i fuzz testove za PDF/XLSX.
3. Ukloniti GUI re-entrant dio punog workflowa (`processEvents`/inline dijalozi)
   i uvesti workflow lock.
4. Definisati log retention, ACL i automatsko sigurno čišćenje.
5. Dodati SBOM (CycloneDX/SPDX) u release pipeline.

### P2

1. BitLocker na klijentima/serveru i šifrovan, testiran backup.
2. Revizija partner dataseta i rokova čuvanja u Git/backup kopijama.
3. Privatni licencni i parser signing ključ premjestiti u offline/vault/HSM
   okruženje.
4. Periodični eksterni penetracioni test i audit server konfiguracije.

## 8. Release kriterij

Za kontrolisani interni pilot kod je spreman nakon pregleda commitova. Za
široku produkcijsku distribuciju moraju dodatno biti ispunjena prva tri P0
operativna koraka:

- stari superuser kredencijal je invalidiran;
- DB koristi `verify-full`;
- finalni EXE i installer imaju važeći Authenticode potpis;
- potpisani artefakt prolazi smoke test na čistoj Windows mašini;
- puni test suite i SCA audit ponovo prolaze u release jobu.

## 9. Zaključak

Sigurnosni profil je materijalno podignut: kritični runtime DB rizik je
izolovan, parseri su default-deny i potpisani, XML/agent kapije su fail-closed,
LLM pozivi centralizovani, logovi redigovani, a zavisnosti i build imaju
automatizovane sigurnosne kapije.

Najvažniji preostali posao više nije veliki zahvat u aplikacijskom kodu, nego
administratorsko zatvaranje starog superuser naloga i uspostavljanje
produkcijskog PKI/code-signing lanca. Dok to nije završeno, aplikacija je
znatno sigurnija za kontrolisani interni rad, ali nije potpuno produkcijski
ojačana.
