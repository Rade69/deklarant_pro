# Agent Report: Cherry-pick main → windows (2026-06-09)

## Šta je urađeno

Portovano 15 commitova sa `origin/main` grane na `windows` granu, kako bi obje grane bile identične u poslovnoj logici.

## Commitovi koji su primijenjeni

| Hash | Opis | Status |
|------|------|--------|
| 7d61e6c | feat: tariff_doc_history | Primijenjen čisto |
| 8ca0ee9 | fix(xml): Description_of_goods | Primijenjen čisto |
| 12268cb | (prethodna sesija) | Primijenjen sa konfliktom |
| 4a05175 | (prethodna sesija) | Primijenjen sa konfliktom |
| 21fce7a | fix(zaglavlje): XML uvoz ne pregazi priložene dok. | PRAZAN — HEAD već sadržavao fix |
| f067150 | fix(history): FTAP/PE preskočeni u prijedlozima | PRAZAN — HEAD već sadržavao fix |
| bd94fdf | fix(xml): tariff_description2 fallback | PRAZAN — HEAD već sadržavao fix |
| 4a5cf30 | fix(parser): Šumaprom detekcija | PRAZAN — HEAD već sadržavao fix |
| 3a6b94e | fix(sumaprom): invoice_name fallback | Primijenjen sa konfliktom |
| 94cd16f | perf: ukloni debug printove + OCR cache | Primijenjen sa konfliktom |
| 9147e78 | refactor(agent): print → logger u LLMProvider | Primijenjen sa konfliktom |
| 0cc1460 | feat(agent): istorijska predikcija + frozen dugme | Primijenjen sa konfliktom |
| 4f0136a | refactor+feat+perf: kvote, optimizacije | Primijenjen sa konfliktom |
| b70f974 | fix(tests): ukloni debug + preimuj test funkcije | Primijenjen sa konfliktom |
| cf838d0 | refactor: ASYCUDA Pro → Deklarant Pro | Primijenjen sa konfliktom |

## Kako je urađeno

### Strategija rješavanja konflikata

Generalno pravilo: **HEAD (windows) verzija ima prioritet** osim u slučajevima gdje incoming donosi genuinu ispravku.

**Slučajevi gdje je zadržana HEAD verzija:**
- Logger imenovanje: `deklarant_pro.*` (HEAD) vs `asycuda_pro.*` (incoming)
- Windows-specifične funkcije: `_find_tesseract()`, `_find_poppler()` u `ocr_utils.py` — incoming ih brisao ali koriste se
- Fallback lanac u `LLMProvider` — HEAD ima kompletnu logiku (Groq→Gemini→OpenRouter→DeepSeek), incoming mijenjao na nepotpunu verziju
- Batch SQL optimizacija u `tariff_intent_service.py` — HEAD ima batch lookup, incoming bi ga uklonio
- `_merge_import_docs_add_only_missing` u `zaglavlje_controller.py` — HEAD ima napredniji helper

**Slučajevi gdje je uzeta incoming verzija:**
- `invoice_name` fallback u `import_service.py`: `stats.get("invoice_name") or filepath.stem` je bolji od `stats.get("invoice_name", "")`
- UI repaint u `naimenovanja_view.py`: `self.ui.update/repaint` + `self.repaint()` bolje na Windowsu

**Prazni commiti (skip):**
- 21fce7a, f067150, bd94fdf, 4a5cf30 — Windows verzija je već imala iste izmjene iz prethodnih sesija portovanja

## Zašto

Korisnik: "Uradi jer treba da budu identični" — `windows` i `main` grana trebaju biti sinhronizovane u poslovnoj logici. Razlike između grana su uglavnom:
1. Logger imenovanje (`deklarant_pro` vs `asycuda_pro`) — Windows je ispravno preimenovan
2. Windows-specifičan kod (Tesseract/Poppler detekcija, `SafeMessageBox`, `AppUserModelID`)
3. Neke optimizacije koje su bile portovane ranije u Windows sesijama

## Napomene

- `ocr_utils.py` ima Windows-specifičan kod koji NE smije ići na `main` (Tesseract/Poppler auto-detekcija)
- `llm_provider.py` zadržava prošireni fallback lanac sa OpenRouter-om
- `quota_service.py` i `quota_panel.py` su novi fajlovi (tarifne kvote) portovani uspješno
