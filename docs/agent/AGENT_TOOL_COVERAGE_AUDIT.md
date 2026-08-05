# Agent Tool Coverage Audit — SUSSINA-klasa bugova

**Datum revizije:** 2026-08-05
**Opseg:** Svih 10 alata u `services/agent/chat/tool_definitions.py:TOOLS` + njihove implementacije
**Metodologija:** Statička analiza implementacije svakog alata, klasifikacija po tome da li LLM mora SAM obrađivati rezultat
**Povod:** Korisnikov stvaran bug: "Koliko ima proizvoda SUSSINA" → pogrešan odgovor jer LLM nije imao alat za determinističku pretragu, morao je ručno brojati iz snapshot teksta (popravljeno sa `pretrazi_stavke`, commit `2c28ed5`)
**Referenca:** `agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md`

---

## 1. Metodologija klasifikacije

Svaki alat je klasifikovan u jednu od tri kategorije:

| Klasa | Značenje | Rizik SUSSINA-buga |
|-------|----------|---------------------|
| **DETERMINISTIČKI** | Alat VRAĆA tačan, izračunat rezultat. LLM samo prikazuje — ne obrađuje, ne broji, ne poredi. | Nizak |
| **STRUKTURIRAN** | Servis je uradio analizu, ali REZULTAT je HTML/tekst tabela iz koje LLM mora da EKSTRAKTUJE pojedinačne vrijednosti za follow-up pitanja (npr. "koji od ovih je najveći"). | Srednji |
| **SIROV TEKST** | Alat vraća snapshot cijelog drafta kao tekst — LLM mora SAM da broji, filtrira, poredi, sumira, sortira. | **Visok** — ovo je SUSSINA-klasa |

---

## 2. Klasifikacija svakog alata

### 2.1 `prikazi` — SIROV TEKST ⚠️ VISOK RIZIK

**Šta prima:** `target` (application/invoice/tariffs/origin/items/header/declaration/xml), `scope`, `ordinals`

**Šta STVARNO vraća:**
- Poziva `ApplicationContextService.format_html(scope)` (`services/agent/application_context_service.py:39`)
- Vraća HTML string: status linija + zaglavlje + fakturne linije (grupisane po fakturi, do 12, sa uzorcima naziva) + naimenovanja (do 20, sa tarifom, zemljom, masama, vrijednostima)
- Za pojedinačne stavke (`target=items` + `ordinals`): poziva `_pregledaj_naimenovanja()` → puni HTML sa svim rubrikama (Rb.31-Rb.46)
- Za pojedinačne fakturne linije (`target=invoice` + `ordinals`): poziva `_pregledaj_faktura_stavku()` → HTML sa nazivom, tarifom, količinom, iznosom, masama

**Da li LLM mora SAM da obrađuje:** **DA — za gotovo svako pitanje osim "pokaži mi sve".**

Primjeri gdje LLM mora sam:
- "Koja stavka ima najveću bruto masu?" → mora da skenira sve naimenovanja i poredi brojeve
- "Koliko ukupno kg imaju stavke iz Srbije?" → mora da filtrira po zemlji i ručno sabira
- "Koliko stavki nema tarifni broj?" → mora da prebrojava (iako summary prikazuje "Nedostaje: tarifa N", to je samo broj, ne i koje su)
- "Koje su top 3 najskuplje stavke?" → mora da sortira po vrijednosti

**Zašto je ovo problem:** `prikazi` je primarni alat za SVE upite o stanju drafta. Njegov izlaz je dizajniran za LJUDSKO čitanje (HTML tabela), ne za mašinsku obradu. Ovo je IDENTIČAN root cause kao SUSSINA — LLM dobije sirov tekst i mora sam da računa.

### 2.2 `provjeri` — STRUKTURIRAN ✅ NIZAK RIZIK

**Šta prima:** `target`, `scope`, `ordinals`, `depth`

**Šta STVARNO vraća:**
- Svaki target delegira posebnom review servisu:
  - `invoice`/`origin` → `provjeri_fakturu()` → strukturirani `InvoiceReviewSummary` sa `blocking`, `warnings`, `recommendations`
  - `items` → `provjeri_naimenovanja()` → strukturirani nalaz sa `prazne_obavezne` i `prazne_opcione`
  - `header` → `provjeri_zaglavlje()` → strukturirani
  - `cross_tab` → `provjeri_usklađenost_tabova()` → strukturirani
  - `xml` → `provjeri_spremnost_za_xml()` → strukturirani
  - `tariffs` → delegira na `_prikaz_tarifnih_trenutnih()` (istorijska validacija)
  - `application`/`declaration` → `_compliance_check()` → ComplianceReportDialog

**Da li LLM mora SAM da obrađuje:** **Uglavnom NE.** Servisi rade analizu — LLM samo prikazuje rezultat. Summary već sadrži gotove brojke (npr. "2 blokade, 3 upozorenja"). Za follow-up pitanja tipa "a koja konkretno naimenovanja imaju problem X" — provjeri već prikazuje pojedinačne nalaze.

**Ograničenje:** `provjeri` odgovara na pitanje "šta nije u redu", ali NE na pitanja tipa "koliko UKUPNO vrijede stavke sa tarifom X" ili "koja stavka je najteža" — to su upitni, ne validacioni upiti.

### 2.3 `pretrazi_tarifu` — DETERMINISTIČKI ✅ NIZAK RIZIK

**Implementacija:** `_pretrazi_tarifu()` (chat_intent_handler.py:2520)
- Poziva `tarifa_service.pretrazi(upit, limit=10)` → struktuirani rezultati iz `zvanicna_tarifa.db`
- Zatim `formatiraj_rezultate()` → HTML sa tarifnim kodom, nazivom, stopom
- Vraća tačne, izračunate rezultate. LLM ne obrađuje — samo prikazuje.

### 2.4 `pretrazi_porijeklo` — DETERMINISTIČKI ✅ NIZAK RIZIK

**Implementacija:** `_pretrazi_porijeklo()` (chat_intent_handler.py:2627)
- Prvo proba MCP server (`mcp_facade.find_product_origin()`) → struktuirani rezultati
- Fallback: `DeclarationSearchService.search_by_goods()` → Counter brojanje zemalja
- Vraća: "najčešće zemlje: RS (5×), DE (3×)..." — servis je već izbrojao i sortirao
- LLM samo prikazuje.

### 2.5 `pretrazi_stavke` — DETERMINISTIČKI ✅ NIZAK RIZIK

**Implementacija:** `_pretrazi_stavke()` (chat_intent_handler.py:2535)
- Case-insensitive substring pretraga kroz `draft.invoice_lines` i `draft.items`
- Vraća tačan broj (`len(invoice_matches) + len(item_matches)`) + listu sa nazivima, tarifama
- **Ovo je NOV alat koji je popravio SUSSINA bug** (commit `2c28ed5`)

**Ograničenje:** Pretraga je SAMO tekstualna (substring u `naziv_robe`/`goods_description`/`goods_trade_name`). Ne može da filtrira po brojčanim vrijednostima (tarifni kod, iznos, masa) ni po praznim poljima.

### 2.6 `pronadji_slicne_proizvode` — STRUKTURIRAN ⚠️ SREDNJI RIZIK

**Implementacija:** `_pronadji_slicne_proizvode()` → `render_similar_products_for_query()` (`similar_products_analysis_service.py:107`)
- Poziva `ProductSimilarityEmbeddingService.find_similar()` → embedding-based matching
- Grupiše po tarifi, računa `total_usage`, `max_similarity`, `share %`
- **Ali:** OUTPUT je HTML `<table>` sa sirovim podacima. Ako LLM treba da odgovori "koja tarifa ima najveći usage" — tabela SADRŽI tu informaciju, ali LLM mora da je parsira.

**Zašto ovo nije VISOK rizik:** Za razliku od `prikazi`, `pronadji_slicne_proizvode` ima mali, fokusiran output (nekoliko tarifnih grupa). LLM može relativno pouzdano da poredi nekoliko brojeva iz tabele. Ipak, nije idealno — trebalo bi da summary već kaže "najčešća tarifa: 9405 (15×)".

### 2.7 `analiziraj_tarifne` — STRUKTURIRAN ⚠️ SREDNJI RIZIK

**Implementacija:** `_analiziraj_tarifne_historiju()` → `analiziraj_tarifne_historiju()` (`tariff_history_analysis_service.py:503`)
- Servis radi KOMPLETNU analizu: prikuplja kontekste linija, poredi sa PG historijom, SQLite brojačem, oficijelnom tarifom
- Za svaku liniju računa status (OK/PROVJERI/RIZIK) sa razlogom i kandidatima
- Summary već sadrži gotove brojke: "OK: 5 | Provjeri: 2 | Rizik: 1"

**Ali:** OUTPUT je HTML tabela sa svim procjenama. Za follow-up "koji tarifni broj ima najveći score kandidata" — LLM mora da čita tabelu. Slično kao `pronadji_slicne_proizvode` — mali skup podataka, pa je rizik srednji, ne visok.

### 2.8 `predlozi_tarife` — NIJE UPITNI ALAT

Nije relevantan za SUSSINA-klasu — ovo je akcioni alat (PROPOSE), pokreće batch proces.

### 2.9 `spoji_naimenovanja` — NIJE UPITNI ALAT

Nije relevantan — akcioni alat (PROPOSE).

### 2.10 `upisi_u_kolonu` — NIJE UPITNI ALAT

Nije relevantan — akcioni alat (MUTATE).

---

## 3. Konkretni upiti BEZ pouzdanog determinističkog puta

Ovo su realni upiti koje deklarant može postaviti tokom rada, a za koje trenutno **ne postoji nijedan alat** koji bi vratio tačan, izračunat odgovor — LLM bi morao da procesira sirovi tekst iz `prikazi`:

### Kategorija A: AGREGACIJA (SUM, AVG, MAX, MIN) — NAJVEĆI PRIORITET

| # | Upit | Šta LLM mora da radi | Dostupni podaci u draftu |
|---|------|-----------------------|--------------------------|
| 1 | **"Koja je ukupna vrijednost svih stavki sa tarifom 9405?"** | Filtrira `prikazi` output, ručno sabira `item_value` za svaku stavku sa tim tarifnim kodom | `NaimenovanjeDraft.item_value`, `NaimenovanjeDraft.tariff_code` |
| 2 | **"Koja stavka ima najveću bruto masu?"** | Skenira sva naimenovanja iz `prikazi`, poredi `gross_mass_kg` | `NaimenovanjeDraft.gross_mass_kg` |
| 3 | **"Koliko ukupno kg (bruto) imaju stavke iz Srbije?"** | Filtrira po `origin_country_code == 'RS'`, sabira `gross_mass_kg` | `NaimenovanjeDraft.gross_mass_kg`, `origin_country_code` |
| 4 | **"Koliki je prosječan iznos fakturnih stavki?"** | Dijeli ukupni iznos sa brojem stavki iz `prikazi` | `InvoiceLine.iznos`, broj `invoice_lines` |
| 5 | **"Koja faktura ima najveći ukupni iznos?"** | Grupiše po `invoice_number`, sabira iznose, poredi | `InvoiceLine.invoice_number`, `InvoiceLine.iznos` |

### Kategorija B: BROJANJE SA USLOVIMA — VISOK PRIORITET

| # | Upit | Šta LLM mora da radi | Dostupni podaci |
|---|------|-----------------------|------------------|
| 6 | **"Koliko naimenovanja ima tarifni broj 9405?"** | Broji naimenovanja sa tim kodom iz `prikazi`. `pretrazi_stavke` ne pomaže — radi tekstualnu pretragu, ne numeričku | `NaimenovanjeDraft.tariff_code` |
| 7 | **"Koliko fakturnih linija nema ni tarifu ni zemlju porijekla?"** | Kombinovani uslov — `provjeri` pokazuje nedostatke pojedinačno, ali ne daje broj za kombinaciju | `InvoiceLine.tarifni_broj`, `InvoiceLine.zemlja_porijekla` |
| 8 | **"Koliko stavki koristi povlasticu 300?"** | Filtrira i broji — `pretrazi_stavke` ne pretražuje polje povlastica | `NaimenovanjeDraft.preference_code`, `InvoiceLine.povlastica` |

### Kategorija C: FILTRIRANJE PO POLJU — VISOK PRIORITET

| # | Upit | Šta LLM mora da radi | Dostupni podaci |
|---|------|-----------------------|------------------|
| 9 | **"Prikaži sve stavke iz fakture FA-15"** | Skenira sve invoice_lines iz `prikazi`, filtrira po `invoice_number` | `InvoiceLine.invoice_number` |
| 10 | **"Koje stavke imaju prazan tarifni broj ALI popunjenu zemlju?"** | Kombinovani filter — provjeri pokazuje "nedostaje tarifa" ali ne u kombinaciji sa "zemlja postoji" | `InvoiceLine.tarifni_broj`, `InvoiceLine.zemlja_porijekla` |
| 11 | **"Koji proizvodi nemaju EUR.1 broj?"** | Filtrira po praznom `eur1_number` | `InvoiceLine.eur1_number` |

### Kategorija D: SORTIRANJE I RANGIRANJE — SREDNJI PRIORITET

| # | Upit | Šta LLM mora da radi | Dostupni podaci |
|---|------|-----------------------|------------------|
| 12 | **"Koje su top 3 najskuplje stavke?"** | Sortira sve stavke po `item_value` opadajuće iz `prikazi` | `NaimenovanjeDraft.item_value` |
| 13 | **"Sortiraj naimenovanja po neto masi opadajuće"** | Sortira iz `prikazi` | `NaimenovanjeDraft.net_mass_kg` |

### Kategorija E: DUPLIKATI I SKUPOVI — SREDNJI PRIORITET

| # | Upit | Šta LLM mora da radi | Dostupni podaci |
|---|------|-----------------------|------------------|
| 14 | **"Da li se neki tarifni broj ponavlja u više naimenovanja?"** | Grupiše naimenovanja po tarifnom kodu, broji pojavljivanja | `NaimenovanjeDraft.tariff_code` |
| 15 | **"Koje zemlje porijekla se pojavljuju u više od jedne stavke?"** | Grupiše i filtrira | `InvoiceLine.zemlja_porijekla`, `NaimenovanjeDraft.origin_country_code` |

---

## 4. Root cause: zašto `prikazi` dominira rizicima

`prikazi` je **jedini alat za uvid u stanje drafta**. Svaki drugi upitni alat (`pretrazi_stavke`, `provjeri`, `analiziraj_tarifne`) pokriva PO JEDNU specifičnu operaciju. Sve ostalo ide kroz `prikazi` → LLM dobije 50-200 linija HTML-a i mora sam da:

- **Broji** (umjesto `COUNT WHERE`)
- **Sabira** (umjesto `SUM`)
- **Poredi** (umjesto `MAX`/`MIN`)
- **Sortira** (umjesto `ORDER BY`)
- **Filtrira po više polja** (umjesto `WHERE x AND y`)

Ovo je **strukturni problem**, ne pojedinačni propust: arhitektura alata je dizajnirana oko PITANJA-SU-GOTOVE-OPERACIJE (`provjeri`, `pretrazi_tarifu`), ali realni korisnički upiti su ČESTO AD-HOC i zahtijevaju fleksibilnu agregaciju/filtriranje postojećih podataka iz drafta.

**Poređenje sa SUSSINA slučajem:**
- SUSSINA: "koliko ima proizvoda X" → nema alata za pretragu po nazivu → `prikazi` vratio sirov tekst → LLM brojao ručno → promašio
- Svaki gornji upit: "suma/MAX/filter/duplikat za X" → nema alata za agregaciju/filtriranje → `prikazi` vratio sirov tekst → LLM računa ručno → **ista klasa greške**

---

## 5. Preporučeni novi/prošireni alati (rangirani po prioritetu)

### Prioritet 1 — KRITIČNO: `agregiraj_stavke` (novi alat)

**Pokriva upite:** #1, #2, #3, #4, #5, #12, #13 (agregacija i sortiranje)

**Šta bi radio:** Deterministička agregacija postojećih podataka iz drafta, bez potrebe da LLM išta računa.

```text
agregiraj_stavke(
    operacija: "sum" | "avg" | "max" | "min" | "count",
    polje: "vrijednost" | "bruto_masa" | "neto_masa" | "iznos" | "kolicina",
    filter_polje: opciono ("tarifa" | "zemlja" | "povlastica" | "faktura" | ...),
    filter_vrijednost: opciono,
    target: "faktura" | "naimenovanja" | "all",
    top_n: opciono (za "koje su top 3")
)
```

**Primjeri poziva:**
- `agregiraj_stavke(operacija="sum", polje="vrijednost", filter_polje="tarifa", filter_vrijednost="9405")` → "Ukupna vrijednost stavki sa tarifom 9405: 12,345.67 EUR (3 stavke)"
- `agregiraj_stavke(operacija="max", polje="bruto_masa", target="naimenovanja", top_n=3)` → "Top 3: Rb.2 (245.3 kg), Rb.5 (180.1 kg), Rb.1 (120.0 kg)"

**Šta bi trebalo dirati:**
- `services/agent/chat/tool_definitions.py` — dodati u `TOOLS` i `SYSTEM_PROMPT`
- `services/agent/chat/tool_policy.py` — dodati u `TOOL_EFFECTS`
- `gui/tabs/agent/services/chat_intent_handler.py` — nova funkcija `_agregiraj_stavke()` + dispatch grana
- Podaci već postoje u `DeclarationDraft.invoice_lines` i `DeclarationDraft.items`

### Prioritet 2 — VISOK: `filtriraj_stavke` (novi alat)

**Pokriva upite:** #6, #7, #8, #9, #10, #11, #14, #15 (filtriranje i brojanje sa uslovima)

**Šta bi radio:** Fleksibilno filtriranje fakturnih linija i naimenovanja po bilo kom polju.

```text
filtriraj_stavke(
    target: "faktura" | "naimenovanja" | "all",
    uslovi: [
        {polje: "tarifa", operator: "=" | "!=" | "prazno" | "nije_prazno", vrijednost: "9405"},
        {polje: "zemlja", operator: "=", vrijednost: "RS"},
    ],
    grupisi_po: opciono ("tarifa" | "zemlja" | "faktura" | "povlastica"),
    prikazi: "broj" | "listu" | "oboje"
)
```

**Primjeri:**
- `filtriraj_stavke(target="faktura", uslovi=[{polje:"tarifa", operator:"prazno"}, {polje:"zemlja", operator:"prazno"}])` → "4 fakturne linije nemaju ni tarifu ni zemlju"
- `filtriraj_stavke(target="naimenovanja", grupisi_po="tarifa", prikazi="oboje")` → "Tarifni brojevi: 9405 (2×), 8401 (1×), 7326 (1×)"

**Šta bi trebalo dirati:** Isti fajlovi kao iznad, plus potencijalno novi servis za fleksibilno filtriranje.

### Prioritet 3 — SREDNJI: Proširiti `pretrazi_stavke` parametrom `polje`

Trenutni `pretrazi_stavke` pretražuje SAMO tekstualna polja (`naziv_robe`, `goods_description`, `goods_trade_name`). Dodati opcioni parametar `polje` za pretragu po drugim poljima:

```text
pretrazi_stavke(upit="9405", polje="tarifa")  → numerička pretraga tarifnog koda
pretrazi_stavke(upit="300", polje="povlastica") → pretraga povlastice
pretrazi_stavke(upit="FA-15", polje="faktura") → pretraga broja fakture
```

**Šta bi trebalo dirati:** Proširiti postojeću `_pretrazi_stavke()` funkciju i `TOOLS` definiciju.

### Prioritet 4 — NIZAK: Proširiti `pronadji_slicne_proizvode` sa summary linijom

Dodati summary na vrh HTML output-a (npr. "Najsličnija tarifa: 9405, 15× korištena, sličnost 0.92") — trivijalna izmjena, smanjuje potrebu da LLM parsira tabelu.

---

## 6. Zbirni pregled

| Alat | Klasa | Rizik SUSSINA-buga | Broj nepokrivenih upita |
|------|-------|---------------------|------------------------|
| `prikazi` | SIROV TEKST | **VISOK** | 15 (svi gore navedeni) |
| `provjeri` | STRUKTURIRAN | NIZAK | 0 |
| `pretrazi_tarifu` | DETERMINISTIČKI | NIZAK | 0 |
| `pretrazi_porijeklo` | DETERMINISTIČKI | NIZAK | 0 |
| `pretrazi_stavke` | DETERMINISTIČKI | NIZAK | 3 (filtriranje po ne-tekstualnim poljima) |
| `pronadji_slicne_proizvode` | STRUKTURIRAN | SREDNJI | 1 (ekstrakcija max iz tabele) |
| `analiziraj_tarifne` | STRUKTURIRAN | SREDNJI | 0 (summary već sadrži brojke) |
| `predlozi_tarife` | N/A (akcioni) | N/A | N/A |
| `spoji_naimenovanja` | N/A (akcioni) | N/A | N/A |
| `upisi_u_kolonu` | N/A (akcioni) | N/A | N/A |

**Ukupno identifikovano: 15 konkretnih upita bez pouzdanog determinističkog puta.**

**Rangirano po prioritetu:**
1. 🔴 KRITIČNO (5 upita): Agregacija (SUM/AVG/MAX/MIN/COUNT sa uslovima) — `agregiraj_stavke`
2. 🟠 VISOKO (5 upita): Filtriranje i brojanje sa uslovima — `filtriraj_stavke`
3. 🟡 SREDNJE (3 upita): Sortiranje/rangiranje — pokriveno kroz `agregiraj_stavke(top_n=...)`
4. 🟢 NISKO (2 upita): Duplikati/skupovi — pokriveno kroz `filtriraj_stavke(grupisi_po=...)`

**SUSSINA-klasa je sistemski problem:** od 10 alata, 1 (`prikazi` — najvažniji) je SIROV TEKST, 2 su STRUKTURIRANI (tabela bez summary-ja), a samo 3 su DETERMINISTIČKI. Ostatak su akcioni alati. Arhitektura je zdrava za unaprijed definisane operacije (`provjeri`, `pretrazi_tarifu`), ali je **slijepa za ad-hoc upite** koji čine većinu realne konverzacije sa agentom tokom rada na deklaraciji.

---

## 7. Šta će biti potrebno dirati pri implementaciji

### Za `agregiraj_stavke` (Prioritet 1):
- **Novi servis (preporučeno):** `services/agent/chat/draft_aggregation_service.py` — čiste funkcije za agregaciju nad `draft.invoice_lines` i `draft.items`. Ne zavisi od GUI-ja.
- **Izmjene:**
  - `services/agent/chat/tool_definitions.py` — dodati u `TOOLS` i `SYSTEM_PROMPT`
  - `services/agent/chat/tool_policy.py` — dodati `"agregiraj_stavke": ToolEffect.READ_ONLY`
  - `gui/tabs/agent/services/chat_intent_handler.py` — `_agregiraj_stavke()` + elif grana u `_dispatch_known_tool`
- **Broj fajlova:** 4 (od kojih 1 novi)

### Za `filtriraj_stavke` (Prioritet 2):
- **Može se integrisati** u isti `draft_aggregation_service.py` ili kao poseban servis
- **Izmjene:** isti set fajlova kao gore
- **Broj fajlova:** 4 (od kojih 1 novi ili proširen)

### Za proširenje `pretrazi_stavke` (Prioritet 3):
- Samo izmjena postojeće `_pretrazi_stavke()` i `TOOLS` definicije
- **Broj fajlova:** 2

---

## 8. Nalazi van scope-a (ne diraju se u ovom zadatku)

1. **Stara imena alata** (`prikazi_naimenovanja`, `provjeri_naimenovanja`, `provjeri_tarife`, `validuj_deklaraciju`) su uklonjena iz `TOOLS` ali i dalje postoje kao dispatch grane u `_dispatch_known_tool` i u `TOOL_EFFECTS` — ovo je namjerno (Faza 1 konsolidacije). Dva testa (`test_svi_ocekivani_alati_postoje`, `test_ima_tacno_12_alata`) su stale — ne diraju se.
2. `tests/test_origin_intent_routing.py` — slomljen import (nepovezan sa ovim audituom).
3. `ChatIntentHandler` (3035 linija) je i dalje monolit — refaktor je van scope-a ovog audita, ali je relevantan kontekst: dodavanje novih alata u postojeći elif lanac pogoršava tehnički dug.

---

Reviziju izvršio: Crush (DeepSeek V4 Pro), 2026-08-05
