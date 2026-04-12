# Plan refaktorisanja importers/ foldera

**Datum:** April 2026
**Cilj:** Organizovati 20 flat .py fajlova u logičke sub-pakete.
**Metoda:** Ista kao services/ — premještanje + stub fajlovi za backward compat.

---

## Trenutno stanje

```
importers/
├── pdf/           ✅ već postoji (OCR, base, utils)
├── strategies/    ✅ već postoji (excel, pdf, xml strategije)
│
└── [20 flat fajlova — PROBLEM]
    ├── 8 vendor-specifičnih (blagic, imamoglu, sumaprom, ...)
    ├── 5 generičkih parsera
    ├── 4 core/infrastruktura
    └── 3 vendor parseri koji idu uz vendor importere
```

---

## Predložena finalna struktura

```
importers/
├── pdf/               ✅ (nepromijenjeno)
├── strategies/        ✅ (nepromijenjeno)
├── vendors/           ← NOVA
│   ├── blagic/        — 4 fajla
│   ├── imamoglu/      — 2 fajla
│   ├── sumaprom/      — 3 fajla
│   ├── medicopharm/   — 1 fajl
│   ├── master_frigo/  — 1 fajl
│   └── leburic/       — 1 fajl
└── [core fajlovi ostaju u importers/ root]
    base_strategy.py, exceptions.py, import_result.py,
    invoice_line_utils.py, strategy_registry.py, plugin_loader.py,
    generic_pdf_importer.py, smart_pdf_importer.py,
    excel_importer.py, xml_importer.py, invoice_improved_parser.py,
    packing_list_parser.py
```

---

## Faza I — vendors/blagic/ (4 fajla)

| Fajl | Vanjski callers |
|------|----------------|
| `blagic_importer.py` | services/import_service.py, faktura/import_service.py, faktura_view.py |
| `blagic_combined_importer.py` | services/import_service.py, faktura/import_service.py, faktura_view.py |
| `blagic_loren_importer.py` | services/import_service.py, faktura/import_service.py |
| `blagic_attos_importer.py` | services/import_service.py, faktura/import_service.py |
| `blagic_loren_pdf_parser.py` | blagic_loren_importer.py (interni) |

> `blagic_loren_pdf_parser.py` je interni za blagic grupu — ide u `vendors/blagic/` bez stuba.

---

## Faza II — vendors/imamoglu/ (2 fajla)

| Fajl | Vanjski callers |
|------|----------------|
| `imamoglu_pdf_parser.py` | services/import_service.py, faktura/import_service.py |
| `imamoglu_excel_importer.py` | services/import_service.py, faktura/import_service.py |

---

## Faza III — vendors/sumaprom/ (3 fajla)

| Fajl | Vanjski callers |
|------|----------------|
| `sumaprom_combined_importer.py` | services/import_service.py, faktura/import_service.py, faktura_view.py |
| `sumaprom_excel_parser.py` | sumaprom_combined_importer.py (interni) |
| `sumaprom_pdf_parser.py` | sumaprom_combined_importer.py (interni) |

> Excel i PDF parseri su interni za sumaprom grupu — idu bez stuba.

---

## Faza IV — vendors/ostali/ (3 fajla)

| Fajl | Vanjski callers |
|------|----------------|
| `medicopharm_importer.py` | services/import_service.py, faktura/import_service.py |
| `master_frigo_importer.py` | services/import_service.py, faktura/import_service.py |
| `leburic_pekabesko_importer.py` | services/import_service.py, faktura/import_service.py, test_leburic |

> Svaki ima vlastiti `vendors/<naziv>/` folder ili svi zajedno u `vendors/misc/`.

---

## Core fajlovi — ostaju u importers/ root

Ovi fajlovi su generički/infrastrukturni i koriste ih mnogi vendor importeri
(bili bi cirkularni importi ako bi se premještali):

| Fajl | Ko ga koristi |
|------|---------------|
| `base_strategy.py` | strategies/, vendors/ importeri |
| `exceptions.py` | skoro svi importeri |
| `import_result.py` | skoro svi importeri |
| `invoice_line_utils.py` | više importera |
| `strategy_registry.py` | services/import_service, plugin_loader |
| `plugin_loader.py` | services/plugin_service, admin/plugin_service |
| `generic_pdf_importer.py` | services/import_service, faktura_view, tests |
| `smart_pdf_importer.py` | services/import_service, faktura_view |
| `excel_importer.py` | services/import_service, faktura/import_service |
| `xml_importer.py` | services/import_service |
| `invoice_improved_parser.py` | services/import_service |
| `packing_list_parser.py` | services/import_service |

---

## Redoslijed

```
Faza I   → Faza II  → Faza III → Faza IV
(blagic)  (imamoglu) (sumaprom) (ostali)
```

Svaka faza:
1. Kreiraj `vendors/<naziv>/` folder + `__init__.py`
2. Premjesti fajlove
3. Stub fajlovi samo za one koje vanjske callers direktno importuju
4. Testovi (110 passed)
5. Commit
