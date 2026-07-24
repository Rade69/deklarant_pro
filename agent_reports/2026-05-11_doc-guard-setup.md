# DOC Guard — Instalacija i prvi checker run

**Datum:** 2026-05-11  
**Agent:** Claude Sonnet 4.6  
**Zadatak:** Implementacija DOC Guard sistema iz `docs/files/`

---

## Šta je urađeno

| Korak | Status | Putanja |
|---|---|---|
| `doc_link_checker.sh` kopiran | ✅ | `scripts/doc_link_checker.sh` |
| `doc-guard-hook.cjs` kopiran | ✅ | `.claude/hooks/doc-guard-hook.cjs` |
| `DECISION_RECORD_TEMPLATE.md` kopiran | ✅ | `.claude/DECISION_RECORD_TEMPLATE.md` |
| PostToolUse hook registrovan | ✅ | `.claude/settings.json` |
| Checker pokrenut | ✅ | Exit code 1 (pronađeni problemi) |

---

## Rezultati prvog checker run-a

```
OK:     13
STALE:  19
BROKEN:  1
```

### BROKEN (1) — fajl ne postoji

| Python fajl | Linija | Broken link |
|---|---|---|
| `importers/smart_pdf_importer.py` | 295 | `docs/sections/master_frigo_mapping.md—consumed_paths+importerfix` |

> Putanja sadrži em-dash (`—`) i `+` — vjerovatno greška u kucanju `# DOC:` komentara.

### STALE (19) — `.py` noviji od `.md`

| Python fajl | Linija | Linked doc |
|---|---|---|
| `gui/tabs/agent/widgets/processing_worker.py` | 52 | `docs/archive/2026-04-26/master_frigo_agent_import_2026-04-26.md` |
| `gui/tabs/sifarnici/partner_form_strip.py` | 21 | `docs/sections/partner-form-strip.md` |
| `gui/tabs/sifarnici/tariff_hierarchy.py` | 30 | `docs/sections/tariff-hierarchy-display.md` |
| `importers/vendors/master_frigo/master_frigo_importer.py` | 44 | `docs/archive/2026-04-26/master_frigo_agent_import_2026-04-26.md` |
| `importers/smart_pdf_importer.py` | 23 | `docs/sections/pdf_parse_pipeline.md` |
| `importers/smart_pdf_importer.py` | 143 | `docs/sections/pdf_format_detection.md` |
| `importers/smart_pdf_importer.py` | 269 | `docs/archive/2026-04-26/master_frigo_agent_import_2026-04-26.md` |
| `services/import_service.py` | 25 | `docs/sections/known_vendor_formats.md` |
| `services/import_service.py` | 35 | `docs/sections/invoice_number_similarity.md` |
| `services/import_service.py` | 96 | `docs/sections/import_pipeline.md` |
| `services/import_service.py` | 172 | `docs/sections/packing_list_gate.md` |
| `services/import_service.py` | 206 | `docs/sections/import_state_machine.md` |
| `services/import_service.py` | 252 | `docs/sections/combine_pairs.md` |
| `services/inspection_service.py` | 20 | `docs/sections/inspection-rules-pg.md` |
| `services/sifarnici_service.py` | 1218 | `docs/sections/inspection-rules-pg.md` |
| `mcp_server/tools/declaration_search.py` | 4 | `docs/sections/mcp-declaration-search-tool.md` |
| `mcp_server/tools/product_origin.py` | 4, 34 | `docs/sections/mcp-product-origin-tool.md` |
| `mcp_server/tools/validation.py` | 4 | `docs/sections/mcp-validation-tool.md` |

---

## Hook — kako funkcioniše od sada

Svaki put kada agent uradi `Write`, `Edit` ili `MultiEdit` na `.py` fajlu,
`doc-guard-hook.cjs` se izvršava i injektuje reminder u kontekst ako:
- link je **BROKEN** → zahtijeva kreiranje fajla ili ispravku putanje
- link **postoji** → podsjeća da provjeri da li je dokumentacija ažurna

Hook ne blokira edit — samo injektuje poruku.

---

## Šta nije urađeno (namjerno)

- Broken link nije popravljen — `# DOC:` u `smart_pdf_importer.py:295` sadrži neispravan karakter; treba ručna odluka
- STALE linkovi nisu ažurirani — ovo je posao vlasnika tih modula, ne automatske skripte
- Broken i stale `.md` fajlovi nisu kreirani ni mijenjani

---

## Pokretanje checkera ručno

```bash
bash scripts/doc_link_checker.sh .
```
