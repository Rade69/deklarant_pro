# AGENT TAB - STATUS IMPLEMENTACIJE

**Datum:** 2026-03-20  
**Status:** ✅ 90% završeno - problem sa kombinovanjem PDF+Excel

---

## ✅ ŠTO JE ZAVRŠENO:

### **1. Folder Struktura:**
```
gui/tabs/agent_tab.py                    # Wrapper
gui/tabs/agent/
├── agent_view.py                        # Split UI (70% dokumenti | 30% chat)
├── agent_controller.py                  # Controller sa 3 pipeline moda
├── constants.py                         # Boje, ikone, konstante
├── models/file_item.py                  # Dataclass
└── widgets/
    ├── header_bar.py                    # Status/Parser/Sesija
    ├── upload_area.py                   # Drag&drop + 3 mode buttona
    ├── file_table.py                    # 8 kolona + confidence bar
    ├── results_viewer.py                # Inline rezultati
    ├── document_panel.py                # Lijevi panel
    ├── chat_panel.py                    # 3 taba: Agent/Aktivnosti/Pitanja
    └── processing_worker.py             # Background thread
```

### **2. Features:**
- ✅ Split-view layout (dokumenti lijevo, chat desno)
- ✅ Tri pipeline moda: Analiza / Uvezi / Puna automatizacija
- ✅ Validacija prije uvoza (duplikati, partneri, tarifni)
- ✅ Auto-popuna tarifnih (AutoFillService)
- ✅ Izračun masa (MassCalculator)
- ✅ Kreiranje naimenovanja (CreateNaimenovanjaService)
- ✅ Izvještaj sa greškama i prijedlozima
- ✅ Debug logging

### **3. Workflow:**
```
1. Upload PDF/Excel fajlova
2. Odabir moda (Analiza/Uvezi/Puna auto)
3. ProcessingWorker uvozi kroz import_service
4. import_service SAM detektuje parove i kombinuje
5. Agent otvara Faktura tab
6. Auto-popuna tarifnih (ako treba)
7. Izračun masa (ako treba)
8. Kreiranje naimenovanja
9. Generisanje izvještaja
```

---

## ❌ TRENUTNI PROBLEM:

### **Issue: Kombinovanje PDF+Excel ne radi**

**Kad se ručno uvozi (Faktura Tab):**
```
✅ import_service kombinuje PDF+Excel → 31 stavka
```

**Kad Agent uvozi:**
```
❌ Excel: 31 stavka (is_combined=False)
❌ PDF: 31 stavka (is_combined=True - KOMBINOVANO!)
❌ UKUPNO: 62 stavke (DUPLIKATI!)
```

### **Pokušana rješenja (NISU RADILA):**
1. Sortiranje (Excel prije PDF-a)
2. Filtriranje po `is_combined=True`
3. Preskakanje Excel-ova koji su upareni
4. Provjera po `origin_statements` i `bruto_kg`

### **Root Cause:**
Neshvaćena logika kako `import_service` vraća rezultate za parove:
- **Excel:** vrati 31 stavku (`is_combined=False`)
- **PDF:** vrati 31 stavku KOMBINOVANU (`is_combined=True`)
- **Agent treba:** uzeti SAMO PDF (kombinovani), preskočiti Excel

---

## 📝 KLJUČNI FAJLOVI:

### `processing_worker.py`:
```python
# Koristi import_service - ISTO kao ručni uvoz!
result = svc.import_file(file_item.filepath)

if result.is_combined:
    # KOMBINOVANO (Excel+PDF)
    file_item.invoice_lines = result.items
```

### `agent_controller.py`:
```python
# _on_all_completed() - treba da filtrira kombinovane
for file_item in completed:
    if file_item.is_combined:
        all_lines.extend(file_item.invoice_lines)
    # else: preskoči (Excel je već uključen)
```

---

## 🔧 ŠTO TREBA URADITI:

### **Opcija A:** Filtriranje u `_on_all_completed()`
```python
# Uzmi SAMO fajlove sa is_combined=True
combined = [f for f in completed if hasattr(f, 'origin_statements')]
all_lines = []
for f in combined:
    all_lines.extend(f.invoice_lines)
```

### **Opcija B:** Modifikacija `import_service`
Da `import_service` NE vraća Excel kad je već uključen u kombinovani PDF.

### **Opcija C:** Drugi pristup
Neko ko razumije `import_service` logiku treba da pogleda kako se detektuje `is_combined`.

---

## 📊 METRIKE:

| Metrika | Vrijednost |
|---------|------------|
| **Fajlovi kreirani** | 13 |
| **Linija koda** | ~1,400 |
| **Testovi** | 67 passing |
| **Commiti** | 20+ |

---

## 🎯 SLJEDEĆI KORACI:

1. [ ] Neko ko razumije `import_service` treba da pogleda problem
2. [ ] Ili koristiti drugi pristup: samo `is_combined=True` fajlovi
3. [ ] Ili modifikovati `import_service` da ne vraća Excel za parove

---

**Napomena:** Sve ostalo radi savršeno! Samo kombinovanje PDF+Excel je problem.
