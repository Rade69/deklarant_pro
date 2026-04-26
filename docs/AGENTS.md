# AGENTS.md — Deklarant Pro projektni standard

**Čitaj zajedno s globalnim `~/.claude/AGENTS.md`.**
Ovaj dokument je specifičan za projekat **Deklarant Pro** — desktop aplikacija za pripremu carinskih deklaracija.

---

## 1. Stack

| Komponenta | Verzija / detalj |
|------------|-----------------|
| Jezik | Python 3.11+ |
| GUI | PySide6 (Qt 6) |
| Baza (glavna) | PostgreSQL — `catalogs` schema |
| Baza (lokalna) | SQLite — `deklarant_sistem.db` |
| Tarifa (lookup) | SQLite — `zvanicna_tarifa.db` |
| PDF parsing | pdfplumber |
| Excel parsing | openpyxl |
| AI/LLM | Groq API (primarni) + Google Gemini (fallback) |
| Env varijable | python-dotenv, `.env` fajl |

---

## 2. Arhitektura — 3-layer pattern (OBAVEZNO)

Svaki tab/modul mora biti podijeljen na tri sloja. **Ne miješati slojeve.**

```
View       — samo UI, signali, prikaz podataka, NEMA business logike
Controller — orchestration, event handling, povezuje View ↔ Service
Service    — sva business logika, DB operacije, kalkulacije
```

### Primjer ispravne strukture:
```python
# ✅ ISPRAVNO — View samo emituje signal
def _on_btn_click(self):
    self.action_requested.emit(self.get_data())

# ✅ ISPRAVNO — Controller orchestrira
def _on_action_requested(self, data):
    result = self.service.process(data)
    self.view.show_result(result)

# ❌ POGREŠNO — business logika u View-u
def _on_btn_click(self):
    conn = psycopg2.connect(...)  # NE!
    result = self._calculate_something(data)  # NE!
```

---

## 3. Imenovanje polja — KRITIČNO

Projekat koristi **srpski nazivi polja** na InvoiceLine i srodnim modelima.
Ovo je namjerno i ne smije se mijenjati na engleski ekvivalent.

| Ispravno | Pogrešno |
|----------|----------|
| `tarifni_broj` | `tariff_code`, `tariff_number` |
| `naziv_robe` | `goods_name`, `product_name` |
| `zemlja_porijekla` | `origin_country`, `country_of_origin` |
| `povlastica` | `preference`, `preference_code` |
| `bruto_kg` | `gross_weight`, `gross_kg` |
| `neto_kg` | `net_weight`, `net_kg` |
| `iznos` | `amount`, `value` |
| `kolicina` | `quantity`, `qty` |
| `jm` | `unit`, `unit_of_measure` |
| `eur1_number` | `eur1`, `eur_number` |

**NaimenovanjeDraft koristi engleski** (`tariff_code`, `goods_description`, `origin_country_code`) — ovo je konzistentno s ASYCUDA XML formatom i ne smije se mijenjati.

---

## 4. Tarifni broj format

- Sistem interno koristi **8-cifreni format bez tačaka**: `08052190`
- PostgreSQL baza ima **10-cifreni format**: `0805219000`
- Konverzija: dodati `'00'` na kraj pri PG lookup-u
- **Nikad ne čuvati format s tačkama** (`0805.21.90` ili `2936.00.00`)
- Normalizacija: `re.sub(r'\D', '', raw)[:10]`

---

## 5. Importeri — pravila

Svaki importer mora:
- Vraćati `ImportResult` objekat (ne dict, ne tuple)
- Imati `detect_*` funkciju za auto-detekciju formata
- Postavljati `bruto_kg` i `neto_kg` na ukupnoj razini (ne po liniji ako PDF nema per-line težine)
- Koristiti srpske field names na `InvoiceLine` (vidi sekciju 3)

```python
# ✅ Ispravan return
return ImportResult(
    items=lines,          # List[InvoiceLine]
    bruto_kg=total_bruto,
    neto_kg=total_neto,
    invoice_name=name,
    currency="EUR",
)
```

---

## 6. Naimenovanja — pravila grupiranja

Naimensovnja se grupišu po **4 ključa** — svi moraju biti identični:
1. `tarifni_broj`
2. `zemlja_porijekla`
3. `povlastica`
4. `eur1_number`

Koristi `CreateNaimenovanjaService.create_smart_group()` — **ne pisati vlastitu logiku grupiranja**.

---

## 7. LLM / Agent integracija

- Primarni provider: Groq (`llama-3.3-70b-versatile` za chat, `llama-3.1-8b-instant` za batch)
- Fallback: Gemini (`gemini-2.5-flash-lite`) — jedini koji radi na free tier bez billing-a
- Koristiti `LLMProvider` klasu iz `gui/tabs/agent/widgets/llm_provider.py` — **ne pozivati Groq/Gemini direktno**
- Streaming ide kroz `provider.stream_chat()`, batch kroz `provider.complete()`
- QThread workeri za sve LLM pozive — nikad blokirati UI thread

---

## 8. Baza podataka

### PostgreSQL
```python
# ✅ Parametrizovani upit — uvijek ovako
cur.execute("SELECT * FROM catalogs.zvanicna_tarifa WHERE kod = %s", (kod,))

# ❌ String interpolacija — nikad
cur.execute(f"SELECT * FROM catalogs.zvanicna_tarifa WHERE kod = '{kod}'")
```

### SQLite
- `deklarant_sistem.db` — mappinzi, šifrarnici, lokalni podaci
- `zvanicna_tarifa.db` — samo čitanje, carinska tarifa 2026
- Koristiti context manager (`with conn:`) za transakcije

---

## 9. GUI konvencije

- `QTextEdit` za multi-line prikaz, `QLineEdit` za single-line
- Read-only polja za auto-popunjene vrijednosti (`setReadOnly(True)`)
- Debug ispisi koriste emoji za vizualno praćenje: `🔍`, `✅`, `⚠️`, `📝`
- Signali su jedini ispravni način komunikacije između slojeva (ne direktni pozivi metoda prema gore)
- `blockSignals(True/False)` pri bulk operacijama na tablicama

---

## 10. Što je specifično zabranjeno u ovom projektu

| Zabrana | Razlog |
|---------|--------|
| Pozivati Groq/Gemini direktno bez `LLMProvider` | Nema fallback logike |
| Pisati logiku grupiranja naim van `CreateNaimenovanjaService` | Duplikacija, greške |
| Mijenjati field names na srpskim modelima | Lomi sve importere |
| `mock` za SQLite/PostgreSQL u testovima | Prethodna iskustva — mask-uje realne greške |
| Zaokruživati težine na 2 decimale | Gubi se preciznost pri carinskom obračunu |
| `draft.items` miješati s `draft.invoice_lines` | Potpuno različiti koncepti |

---

## 11. Struktura projekta

```
deklarant_pro/
├── core/draft/          # Modeli: DeclarationDraft, InvoiceLine, NaimenovanjeDraft
├── gui/
│   ├── main_window.py   # QMainWindow, tab setup
│   └── tabs/            # Tabovi: faktura, naimenovanja, zaglavlje, agent
│       └── agent/       # AgentTab, AgentController, AgentView, widgeti
├── importers/           # PDF/Excel parseri po dobavljaču
├── services/            # Business logika (svi servisi ovdje)
├── database/            # DB konekcije, migracije
├── exporters/           # XML/PDF eksport
└── ui/                  # Qt .ui fajlovi
```

---

## 12. Workflow za agente

1. Pročitaj ovaj fajl i globalni `~/.claude/AGENTS.md`
2. Pročitaj relevantne fajlove koje mijenjаš
3. Implementiraj samo ono što je u promptu
4. Vrati output u formatu koji traži sekcija 3.2 globalnog AGENTS.md
5. Ako nešto nije jasno — prijavi kao BLOKIRANO

---

*Ovaj fajl kreira i održava Claude Sonnet kao nadzorni agent.*
*Izmjene odobrava Claude Sonnet u dogovoru s korisnikom (Radovan).*
