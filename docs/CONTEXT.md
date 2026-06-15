# CONTEXT.md — Zajednička memorija za sve agente

> Ovaj fajl čitaju SVI agenti: Claude, Qwen, DeepSeek, i drugi.
> Sadrži ne-trivijalne odluke i pravila koja nisu vidljiva iz samog koda.
> Ažurira ga Claude na kraju svake sesije u kojoj je donesena nova bitna odluka.
> Posljednje ažuriranje: 2026-05-29

---

## 1. Importeri i parseri — kritična pravila

### consumed_paths — OBAVEZNO
Svaki kombinirani importer (Excel+PDF, Invoice+PackingList) MORA postaviti
`consumed_paths=[putanja_potrošenog_fajla]` u `ImportResult`.
Bez toga agent procesira oba fajla zasebno → duplikati stavki u deklaraciji.
Primjeri: Blagić (CASE 1/2), Šumaprom (CASE 1B/2B), Leburic, Invoice+PackingList (CASE 3/4).

### ImportService singleton — zabranjeno
Worker MORA koristiti `ImportService()` (privatna instanca).
NIKAD `get_import_service()` singleton — prouzrokuje race condition u višenitnom uvozu.

### KG Fashion parser
Universal parser za fakture s "K...G...FASHION" D.O.O. u zaglavlju.
Dobavljači: Petite Jolie, Vizzano, Benetton, Sisley, Ambitious, Kese, Bueno, Mod, Jagger.
XLS manifest auto-detekcija → `eur1_suggested` flag (ne `has_origin_statement`).

---

## 2. Tarife i naimenovanja — kritična pravila

### Historijski prijedlozi tarifarnih — samo isti izvoznik
`find_historical_tariff()` MORA imati hard `WHERE exporter = ?` filter.
Nema fallback na druge izvoznike — pogrešne tarife su lošije od praznog polja.
Razlog: različiti izvoznici imaju iste šifre proizvoda ali različite tarife.

### Tariff prefix match
`find_mapping()` prihvata i slučaj gdje je DB kod prefiks traženog koda.
Npr. DB ima `620342` → pokriva `62034211`, `62034219` itd. (varijante boja/veličina).

### Auto-popuni — ne dira povlastice
`TariffMappingService` preskače stavke koje već imaju PE1/PE2/PE3.
Popunjava SAMO tarifni broj, nikad povlasticu ili `eur1_number`.

### _choose_tariff_description filter
`tariff_description1` i `tariff_description2` su isključeni iz `product_names` filtera.
Opisi s brojevima (npr. "27,6 MPa") pogrešno se klasificiraju bez ovog filtera.

### _tariff_heading 4-cifreni fallback
Kad je specifičan opis generički ("ostali", "druge"), koristi 4-cifreni heading iz tarifne baze
umjesto generičkog opisa — daje bolji Rub.31.

---

## 3. ASYCUDA XML export — kritična pravila

### Rb.31 format — strogo 3 linije
ASYCUDA Rub.31 XML izlaz mora ostati max 280 karaktera i najviše 3 linije.
GUI smije prikazati duži pregled radi rada korisnika, ali finalno skraćivanje se radi pri buildanju XML-a.
```
Linija 1: opis robe po tarifi (iz tarifne baze)
Linija 2: komercijalni nazivi iz fakture
Linija 3: broj fakture i datum
```
`_fmt_weight()` uvijek 2 decimale. `Commercial_Description` MORA imati `\n` separator.

### En-dash u tarifnoj bazi
Tarifna baza čuva `–` (U+2013, en-dash) u opisima.
Bez konverzije prikazuje se kao `â` u ASYCUDA. Uvijek konvertovati pri uvozu/izvozu.

### Rb.31 overflow marker
`goods_description` koji sadrži "(+N više)" MORA proći filter — ne tretirati kao grešku.

### Rb.48 — NE kopirati iz historijskog XML-a
Šifra odgođenog plaćanja (`odgodjeno_placanje`) se mijenja godišnje.
Mijenjati samo `TEMPLATE_FIELDS` whitelist u `xml_template_service.py`.

### Attached_doc_item
Svi header dokumenti (faktura, CMR, EUR.1...) moraju biti u `Attached_doc_item`.
Ne samo dokumenti specifični za naimenovanje.

### AttachedDocument normalizacija
`header_attached_documents` i `item.attached_documents` u XML exportu mogu doci kao
`AttachedDocument` objekti ili dict strukture iz GUI/import toka. `AsycudaXMLBuilder`
mora normalizovati oba oblika prije pristupa `code`, `number` i `from_rule`, inace
GUI/EXE moze prikazati samo genericku poruku "Greska pri eksportu".

---

## 4. EUR.1 i povlastice

### Povlastica zahtijeva eksplicitnu potvrdu deklaranta
Parser smije samo detektovati PE2/PE3 izjavu ili potrebu za EUR1 obrascem.
Zemlja porijekla, EU/CEFTA porijeklo, istorija, product master list ili tariff mapping
NISU dokaz za automatsko popunjavanje Rub.36.

Povlastica se primjenjuje tek nakon eksplicitne potvrde deklaranta kroz PE2/PE3/EUR1
dijalog ili rucni unos. Agent i auto-fill smiju prikazati kandidata, ali ne smiju sami
upisati `povlastica`.

### Tok
- Faktura NEMA izjavu o poreklu → EUR.1 dialog (PE1 + broj)
- Faktura IMA izjavu → PE2 dialog (samo zemlja, bez broja)
- `eur1_suggested` flag (ne `has_origin_statement`) određuje koji dijalog se otvara

### Batch uvoz — EUR1 dijalog
`_should_show_eur1_dialog()` vraća False za fakture s `has_origin_statement=True`.
U batch uvozu dijalog se odgađa (defer) — paziti da se ne preskači nepravilno.

### Auto-podjela po zemljama porijekla
`split_draft_by_country()` kreira MultiDraftNavigator ◀▶.
EU zemlje idu zajedno u jedan draft. Mixed-invoice → proporcionalna raspodjela težine.

---

## 5. GUI — poznati bugovi i rješenja

### itemChanged + blockSignals
`setData(ValidationColorRole)` okida `itemChanged` signal 12× po redu.
Bez `blockSignals(True/False)` u `_flush_pending_validation` → beskonačna petlja debounce timera.
Uvijek koristiti `blockSignals` pri masovnim `setData` pozivima.

### scrollToBottom zamjena
`scrollToBottom()` + `_install_bottom_scroll_buffer` zajedno sakrivaju zadnje redove.
Koristiti `EnsureVisible` umjesto `scrollToBottom()`.

### Multi-draft tab sync
`NaimenovanjaView.draft` i Zaglavlje tab moraju se eksplicitno ažurirati pri `_switch_to_draft()`.
`MainWindow._on_tab_changed` uzima `faktura_view.draft` — oba taba moraju primiti novi draft.

---

## 6. Mase i težine

### MassCalculator
Zaokružuje mase na 2 decimale s korekcijom ostatka da bi prikazani zbir bio konzistentan.
Koristiti `weight_guards` servis: `normalize_invoice_key`, `group_lines_by_invoice`.

### Per-invoice raspodjela
`invoice_weights` se čuva u draftu po fakturi, ne globalno.
Dugme "Izračunaj mase" u toolbar-u pokreće per-faktura raspodjelu.

---

## 7. Infrastruktura — sigurnost i arhitektura

### SQL — zabrana f-stringa
NIKAD f-string u SQL upitima. Koristiti isključivo `psycopg2.sql` parametrizaciju.
Pronađena i ispravljena 4 mjesta (Maj 2026) — provjeriti svaki novi SQL.

### Aktivni pipeline
`_puna_auto_pipeline` je jedini aktivni put u agent pipelinu.
`_uvezi_u_deklaraciju` i `_izracunaj_tezine_interno` su mrtav kod — nikad nisu bili aktivni.

### Tool-first agent
Agent prvo koristi lokalni router/tool/servis. Ako tool rezultat ima status `unknown`
ili `needs_review`, LLM ne smije dopuniti tarifni broj, porijeklo, povlasticu ili zaključak.
`TOOL_RESULT` je autoritativan; LLM ga smije samo formatirati za korisnika.

### Lozinka u git historiji
Commit `produkcijska-ociscenja` (Maj 2026) — lozinka je mogla biti eksponirana.
Rotirati DB lozinku ako još nije urađeno!

---

## 8. GitNexus — kako koristiti

GitNexus je mapa koda — zna ko koga poziva, koje funkcije postoje, blast radius promjena.
Index: `deklarant_pro` (18002 simbola, 300 execution flows)

```
Prije izmjene simbola:   gitnexus_impact({target: "ime", direction: "upstream"})
Za razumijevanje koda:   gitnexus_context({name: "ime"})
Za pretragu koncepta:    gitnexus_query({query: "pojam"})
Za provjeru promjena:    gitnexus_detect_changes()
Ako index zastari:       npx gitnexus analyze
```

**Pravilo**: GitNexus odgovara na "šta postoji i ko koga poziva".
Ovaj CONTEXT.md odgovara na "zašto je nešto urađeno tako".

---

## 9. Agent optimizacije (Maj 2026)

### HybridMatchingService — jednom izvan petlje
U `tariff_intent_service.py` (propose_all i propose_by_keyword) `HybridMatchingService()`
se instancira JEDNOM prije petlje i prosljeđuje u `_try_history_match(hybrid, ...)`.
NIKAD unutar petlje — za 30 stavki to znači 30 novih instanci i ~90 suvišnih SQL upita.

### find_batch_by_product_codes — batch SQL
`TariffMappingService.find_batch_by_product_codes(codes)` radi jedan `ANY(ARRAY[...])` upit
za sve product_code-ove odjednom. Koristiti prije petlje u svim mjestima gdje se iterira
po stavkama i traži tarifa po product_code.

### set_analysis_summary — diskretna analiza u status baru
`FakturaView.set_analysis_summary(text, level)` prikazuje rezultat analize u status baru
(lbl_analysis, normalno skriven). Poziva se iz `AgentController._proactive_analysis(lines, fw)`.
Chat poruka: max 2 linije, BEZ prijedloga. Korisnik pita agenta ako hoće — agent ne nudi.

---

## 10. Performansne optimizacije (Maj 2026)

### ManualBatchImportWorker — ručni batch uvoz u background threadu
`services/import_worker.py` — `ManualBatchImportWorker(QThread)` parsira fajlove u pozadini.
NIKAD ne prikazuje dijaloge (EUR1/PE2) — to radi main thread u `_process_batch_records()`.
Koristi privatnu `ImportService()` instancu (ne singleton — race condition).
`_import_multiple_files()` u `faktura_view.py` pokraje worker i odmah vraća kontrolu.

### Packing list matching — O(n×m) → O(n+m)
`importers/packing_list_parser.py`: `code_index` dict za O(1) exact match po product_code.
`packing_norm` lista: nazivi normalizovani jednom prije petlje, ne po svakoj stavci.
`_fuzzy_match_normalized(t1, t2)`: prima već normalizovane stringove — bez redundantnog lower/strip.

### FTS5 indeks za XML arhivu — schema versioning
`declaration_search_service.py`: `items_fts` FTS5 virtual table za `commercial_desc` + `description`.
`_SCHEMA_VERSION = 2` — povećati kad se mijenja shema; `_ensure_index` automatski rebuilda.
`search_by_goods` koristi `MATCH` + `bm25()` ranking umjesto `LIKE %keyword%`.
LIKE fallback ostaje ako FTS5 indeks nije populiran (backward compat).

---

## 11. Windows instalacija — status (2026-05-29)

### Što je pripremljeno
`build_windows.bat`, `deklarant_pro.spec`, `installer/setup.iss`, `build_hooks/version_info.txt`
commitovano u `1cbe4c7` (2026-05-28). Gradi standalone `DeklarantPro.exe` putem PyInstaller.

### Windows klijent (IP: 192.168.100.55, user: "dm promet", pass: "1")
- Python 3.11.9 instaliran ✅
- Fajlovi projekta na `C:\Users\dm promet\Desktop\deklarant_pro` ✅
- **Sljedeći korak:** pokrenuti `build_windows.bat` na Windows računaru

### Procedura licenciranja
Svaka mašina treba zasebnu licencu (machine fingerprint). Detalji u:
`agent_reports/2026-05-24_licenciranje-novih-instalacija.md`
Privatni ključ: `tools/licensing/keys/private_key.pem` — nikad ne commitovati.

### Baza podataka
PostgreSQL je samo na serveru `192.168.0.41`. Windows klijent se SPAJA na server,
ne instalira lokalnu bazu. `.env` na Windows mora imati `DB_HOST=192.168.0.41`.

---

## 12. Encoding i PowerShell bulk izmjene

Tokom Windows portovanja potvrđeno je da bulk skripte koje čitaju/pišu tekst preko
PowerShell `Get-Content`/`Set-Content` mogu proizvesti mojibake u UTF-8/BOM fajlovima.
Za masovne tekstualne izmjene koristiti byte-preserving Python alat ili eksplicitno
`-Encoding utf8`; prije commita obavezno skenirati `Ã`, `Ä`, `Å` i C1 kontrolne znakove.
BOM fajlove ne konvertovati slijepo u LF/bez BOM-a jer dio Windows toka očekuje postojeći format.

---

## 13. Kako ažurirati ovaj fajl

Claude ažurira CONTEXT.md na kraju svake sesije gdje je:
- Donesena nova arhitekturna odluka
- Pronađen i riješen ne-trivijalan bug
- Uvedeno novo pravilo koje nije vidljivo iz koda

Format dodavanja: kratka sekcija u odgovarajućoj temi, max 5-6 linija.
Ne dodavati: šta kod radi (to se vidi iz koda), git historiju, privremeno stanje.

---

## 14. Radni nacrti deklaracije

Radni nacrt se čuva kao prenosivi `DeklarantProDraft` XML na lokaciji koju korisnik izabere.
Ne čuva se u PostgreSQL-u i nema posebno dugme za listu nacrta.
`Uvezi XML` razlikuje Deklarant Pro nacrt od ASYCUDA XML-a: nacrt obnavlja cijeli
`DeclarationDraft`, dok ASYCUDA XML ostaje u postojećem import toku.
Podrazumijevani folder je `Documents/Deklarant Pro/Nacrti`; pamti se posljednja lokacija.
