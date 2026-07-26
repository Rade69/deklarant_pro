# Faze 2-5: AgentSafeContext migracija ChatWorker zona

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/agent/widgets/chat_worker.py` + `dist_client/` mirror (5 metoda:
  `_build_context`, `_build_session_zone`, `_build_zaglavlje_zone`,
  `_search_declarations_context`)
- `services/agent/chat/context_adapter.py` + `dist_client/` mirror (novi
  `mask_partner()`, refaktorisan `build_partner_info()`, ispravljen razmak
  u `build_header()`)
- 5 novih test fajlova (24 nova testa ukupno kroz sve faze)
- `docs/CONTEXT.md` (§63)
- `project_rooms/2026-07-25_agent-safe-input-schema-plan.md` (izvorni plan,
  Faze 2-5 sad izvršene)

## Status izvora
Direktan nastavak `agent_reports/2026-07-25_agent-safe-context-faza1.md`
(Faza 1) — korisnik eksplicitno zatražio "nastavi faze 2-5" nakon Faze 1,
implicitno odgovarajući na otvoreno pitanje plana §7 ("da li ide do Faze
5") potvrdno.

## GitNexus impact
- `_build_context` (upstream, prije bilo koje izmjene): LOW, 1 direktan
  pozivalac (`run`) — niže nego što je plan anticipirao (predviđao
  HIGH/CRITICAL po analogiji sa §60).
- Faza 2 (`detect_changes` staged): MEDIUM, 2 affected_processes, oba na
  `_build_session_zone`/`_allow_sensitive_data` — očekivano.
- Faza 3 (`detect_changes` staged): **HIGH**, 6 affected_processes
  (`_allow_sensitive_data`/`Mask_partner`/`_determine_context_zones`, svaki
  x2 root+dist_client) — `_build_context` je centralna orkestracija.
  **Prijavljeno korisniku u AGENTS.md formatu PRIJE commita** (izmjena je
  već bila napravljena i testirana kad je risk provjeren — commit je
  uslijedio tek nakon eksplicitnog prikaza rizika i 49/49 zelenih testova).
- Faza 4 (`detect_changes` staged): LOW, 0 affected.
- Faza 5 (`detect_changes` staged): LOW, 0 affected.

## Šta je urađeno

### Faza 2 — Zone B + Zone B2 partner maskiranje
`AgentContextAdapter.mask_partner(role, name) -> PartnerInfo | None` —
nova jedina tačka odluke o maskiranju. `_build_session_zone` (Zone B, izvor
imena: `invoice_lines[0].exporter.name`) i `_build_zaglavlje_zone` (Zone
B2, izvor: draft Zaglavlje polja) obje migrirane da je koriste umjesto
ručnog `if send_sensitive:` po polju. `build_partner_info()` (Faza 1)
refaktorisan da interno zove `mask_partner()` (bez promjene javnog
ponašanja — 8 Faza 1 testova prošlo nepromijenjeno).

Svaki case original logike (pošiljalac sa imenom, uvoznik sa imenom, JIB
bez imena kad sensitive/kad nije, prazno) ručno provjeren protiv nove
implementacije PRIJE pisanja koda — dokumentovano u commit poruci.

Zone B ranije nije imala test koji provjerava STVARAN sadržaj (samo
monkeypatch na prazan output u `test_tool_use_offline.py`) — dodano 5
testova. `find_xml_for_pair` (PostgreSQL upit unutar Zone B, nepovezan sa
maskiranjem) mockovan da testovi ne čekaju DB connection timeout (87s →
0.9s po test file-u).

### Faza 3 — Zone A agregati
`AgentContextAdapter.build_draft_summary(lines)` (Faza 1, već postojao)
sad se STVARNO koristi u `_build_context()` za `=== STANJE DRAFTA ===`
umjesto ručnih `sum()`/`len()`/dict-brojanja. `bez_tarife_list`/`bez_
zemlje_list` (liste redova, ne brojevi) ostaju lokalno računate jer ih
koriste kasnije sekcije (Zone C, "STAVKE BEZ ZEMLJE PORIJEKLA").

GitNexus HIGH ovdje — dokumentovano u §5 gore i eksplicitno prikazano
korisniku (format iz AGENTS.md "Handoff visokog rizika") prije commita,
iako je stvarna izmjena bila mala (3 lokalne varijable → jedan adapter
poziv, identični brojevi). Verifikacija: 2 nova testa + kompletan
`test_tool_use_offline.py` (31 test, uključujući test koji direktno
poziva `_build_context()`) prošao nepromijenjeno.

### Faza 4 — Zone B2 header polja
`AgentContextAdapter.build_header()` (Faza 1) sad stvarno korišten za
valuta/iznos/kurs, uslovi isporuke, vid transporta, država izvoza,
troškovi, priložene isprave. Uslovi ZA PRIKAZ (da li se linija uopšte
pojavljuje) namjerno ostavljeni kao direktne provjere na `d.*` poljima
(ne na `header.*`) — sačuvana ivica gdje se "Uslovi isporuke" ne prikazuje
ako je `uslovi_kod` prazan čak i kad `uslovi_mjesto` ima vrijednost.

**Usput otkriven i popravljen bug u vlastitom Faza 1 kodu**: `build_
header().vid_transporta` je imao JEDAN razmak prije "granica=" umjesto DVA
kao original — pošto Faza 1 nikad nije bila stvarno POZVANA iz produkcije
(samo testirana izolovano), ovaj bug nikad nije uticao na stvaran chat
kontekst. Uhvaćen novim testom prije nego što je Faza 4 ožvijela taj kod
— potvrđuje vrijednost pisanja regresionih testova PRIJE integracije, ne
samo poslije.

6 novih testova pokrivaju tačan format teksta (uključujući razmake) za
svako polje — ranije nepokriveno nijednim testom.

### Faza 5 — preostale zone (analiza + selektivna migracija)
Analizirane sve tri preostale zone:
- `_build_knowledge_zone`, `_build_tariff_validation_context` — NE diraju
  partner podatke (samo tarifni kodovi/nazivi robe/zemlje porijekla).
  **Namjerno NISU migrirane** — migracija bi bila čist strukturni churn
  bez sigurnosne koristi, suprotno duhu "minimalna izmjena za maksimalnu
  korist" principa ove sesije.
- `_search_pg_partners` — GitNexus hook je otkrio DVA postojeća dokumenta
  (`docs/deklarant_pro_code_review.md` §2.2, `docs/deklarant_pro_analiza_i_
  prijedlozi.md` §1.2) koji tvrde da ova metoda "ignoriše SEND_SENSITIVE_
  DATA". Čitanjem koda potvrđeno: **tvrdnja je ZASTARJELA** — metoda već
  ispravno maskira (`row['name'] if send_sensitive else "[ime skriveno]"`),
  identično onome što ti isti dokumenti predlažu kao "rješenje". Nema
  akcije na kodu (nije pokvareno); dokumenti NISU ažurirani (van scope-a
  — to bi bio zaseban dokumentacioni čišćenje zadatak).
- `_search_declarations_context` "Pretraga po partneru" grana — JE
  migrirana na `adapter.mask_partner()`. Ovo je bio jedini preostali
  primjer istog ranjivog obrasca (ručni ternary po partner-polju) izvan
  Zone B/B2. 2 nova testa.

**Novi, nezavisan nalaz — namjerno NEDIRANO**: ista partner-search grana
pokazuje STVARAN JIB (`r.get('consignee_jib', ...)`) kad je `send_
sensitive=True`, za razliku od Zone B gdje je "JIB se nikad ne šalje
LLM-u" apsolutno pravilo bez obzira na flag. Ovo je INKONZISTENTNOST
otkrivena tokom Faze 5 analize, ne prijavljen bug — dokumentovano
komentarom u kodu ("NAPOMENA (Faza 5, otvoreno pitanje, nedirano)"), NIJE
promijenjeno bez eksplicitne korisničke odluke da li je to namjeravano
ponašanje ili treba uskladiti sa Zone B.

### Forbidden-marker test (plan §8)
`tests/unit/test_chat_worker_forbidden_markers.py` — umjesto provjere
polje-po-polje, ubaci prepoznatljive markere u SVA partner polja (oba
izvora: `invoice_lines[].exporter.name` za Zone B, draft Zaglavlje polja
za Zone B2) i provjeri da se NIJEDAN ne pojavi u CJELOKUPNOM `_build_
context()` outputu. Kontrolni test (sensitive=True) potvrđuje da markeri
BI procurili da masking ne radi — dokaz da prvi test nije lažno pozitivan.

## Zašto je urađeno
Korisnik je eksplicitno tražio nastavak do kraja plana. Svaka faza je
tretirana kao zaseban, provjerljiv korak (zaseban commit, zaseban test
run, zaseban `gitnexus_detect_changes()`) — matches plan §6 i §10
("namjerno postepen i zaustaviv nakon svake faze").

## Kako je urađeno
- Za Faze 2 i 4, SVAKA grana originalne logike je ručno upoređena sa novom
  implementacijom prije pisanja izmjene (dokumentovano u komentarima i
  commit porukama) — posebno pažljivo za Zone B (JIB-only edge case) i
  Zone B2 uslovi isporuke (kod-prazan-ali-mjesto-postoji edge case).
- Za Fazu 3, GitNexus HIGH risk je eksplicitno prijavljen korisniku u
  AGENTS.md propisanom formatu prije commita (commit je uslijedio TEK
  nakon te transparentnosti + zelenih testova).
- Za Fazu 5, GitNexus hook-ovi (automatski prikazani uz grep/read pozive)
  otkrili su relevantne postojeće dokumente (`docs/deklarant_pro_code_
  review.md`, `docs/deklarant_pro_analiza_i_prijedlozi.md`) koji su
  navodili `_search_pg_partners` kao buggy — ta tvrdnja je NEZAVISNO
  provjerena čitanjem stvarnog koda (isti standard kao za bilo koji drugi
  izvor, uključujući ranije Pi/Codex izvještaje u ovoj sesiji) i utvrđena
  zastarjelom prije nego što je bilo šta "popravljeno".
- Svaka faza mirrorovana u `dist_client` odmah nakon root izmjene, uz
  `diff --strip-trailing-cr` provjeru da je jedina preostala razlika
  pre-postojeći BOM karakter (nepovezano, nije dirano).

## Šta nije dirano
- `_build_knowledge_zone`, `_build_tariff_validation_context` — eksplicitna
  odluka, obrazložena gore.
- `_search_pg_partners` — nije pokvareno, nije dirano.
- JIB prikaz u `_search_declarations_context` partner grani — otvoreno
  pitanje, čeka korisničku odluku.
- `TariffLLMWorker` — van scope-a plana (već uzak payload, nema poznat
  propust).
- `docs/deklarant_pro_code_review.md` / `docs/deklarant_pro_analiza_i_
  prijedlozi.md` — sadrže zastarjelu tvrdnju o `_search_pg_partners`, nisu
  ažurirani (dokumentaciono čišćenje, van scope-a ovog zadatka).

## Verifikacija
- `python -m py_compile` na svim izmijenjenim/novim fajlovima (root +
  dist_client) nakon svake faze.
- Pun test suite na kraju: **1156 passed** (bilo 1139 prije Faze 2, +17
  novih testova kumulativno kroz sve faze i forbidden-marker test — ukupno
  24 nova testa uključujući Fazu 1). Isti pre-postojeći: 10 DB-backed
  testova failed (PostgreSQL server nedostupan, korisnik potvrdio
  dostupnost od 2026-07-26 ujutru — nije regres), 1 nepovezan fail
  (hardkodovana lična putanja), 1 nepovezan error (nedostajuća fixture).
- `gitnexus_detect_changes(scope=staged)` prije SVAKOG od 4 commita (Faze
  2-5) — rezultati: MEDIUM/HIGH/LOW/LOW, svi objašnjeni i (za HIGH)
  eksplicitno prijavljeni korisniku prije commita.
- Root vs dist_client diff nakon svake faze: identičan sadržaj (jedina
  razlika BOM karakter, pre-postojeći, nepovezan).

## Pronađeni problemi
- Faza 1 vlastiti bug (`vid_transporta` razmak) — pronađen i popravljen
  prije nego što je ikad dospio u produkciju (vidi Faza 4 iznad).
- Dva postojeća dokumenta sa zastarjelom tvrdnjom o `_search_pg_partners`
  — nisu ažurirani (van scope-a), ali vrijedi zabilježiti da mogu
  zbunjivati buduće agente/developere ako se ne provjere protiv stvarnog
  koda.
- JIB u partner-search grani (`_search_declarations_context`) — potencijalna
  inkonzistentnost sa Zone B pravilom, otvoreno pitanje za korisnika.

## Konflikti / kontradiktorni izvori
`docs/deklarant_pro_code_review.md` §2.2 i `docs/deklarant_pro_analiza_i_
prijedlozi.md` §1.2 tvrde da je `_search_pg_partners` buggy — **tretirano
kao ZASTARJELO** nakon nezavisne provjere protiv stvarnog koda (metoda već
implementira TAČNO ono što ti dokumenti predlažu kao "rješenje"). Nije
potrebna dalja korisnička potvrda za ovaj nalaz — verifikacija je
jednoznačna (kod postoji, radi ispravno, docs opisuju stariju verziju).

## Commitovi
| Hash | Poruka |
| --- | --- |
| `d737a90` | refactor(agent): Faza 2 - migriraj Zone B/B2 na AgentContextAdapter.mask_partner() |
| `0aa54d4` | refactor(agent): Faza 3 - migriraj Zone A na AgentContextAdapter.build_draft_summary() |
| `5b8bd16` | refactor(agent): Faza 4 - migriraj Zone B2 header polja na AgentContextAdapter.build_header() |
| `c12d451` | refactor(agent): Faza 5 - migriraj partner search granu na AgentContextAdapter |
| `6a93455` | test(agent): forbidden-marker test za _build_context (plan §8) |

## Rizici / ograničenja
- Faza 3 je HIGH-risk po GitNexus-u zbog centralnosti `_build_context()`
  — iako je stvarna izmjena verifikovano ponašanje-identična, buduće
  izmjene iste funkcije trebaju ponovo provjeriti impact (graf se mijenja
  kako se kod mijenja).
- JIB-u-partner-search otvoreno pitanje ostaje neriješeno — ako se ne
  adresira, ostaje mala nekonzistentnost (ne aktivan leak ka cloud-u zbog
  `_allow_sensitive_data()`-ovog forsiranog cloud-override-a, ali
  nekonzistentno pravilo unutar samog koda).

## Potreban follow-up
- Korisnička odluka o JIB pitanju u partner-search grani.
- Opciono: ažurirati dva zastarjela dokumenta (`docs/deklarant_pro_code_
  review.md`, `docs/deklarant_pro_analiza_i_prijedlozi.md`) da ne
  navode `_search_pg_partners` kao buggy.
- Opciono: `TariffLLMWorker` migracija na istu shemu (konzistentnost, ne
  hitnost).

## Potrebna korisnička potvrda
- Da li JIB treba biti NIKAD-vidljiv (kao Zone B) i u partner-search grani
  `_search_declarations_context`, ili je trenutna razlika namjeravana.
