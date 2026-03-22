# Zadatak: Implementacija nove palete boja za dugmad

## Kontekst
Radi se o PySide6 desktop aplikaciji (ASYCUDA Pro) za carinsku deklaraciju.
Aplikacija ima višestruke toolbar-e sa dugmadima grupisanim po funkciji.
Cilj je zamijeniti trenutne previše zasićene boje sa muted profesionalnom paletom
koja ne zamara oči pri dugotrajnom radu.

---

## Nova paleta boja

### Funkcionalni sistem boja

| Kategorija | HEX | RGB | Primjena |
|---|---|---|---|
| **Primarna / Snimi / Potvrdi** | `#2E7D6B` | rgb(46,125,107) | Snimi, Dodaj, Validacija |
| **Uvoz** | `#5C6BC0` | rgb(92,107,192) | Uvezi XML, Učitaj, PDF uvoz |
| **Izvoz** | `#4A7B9D` | rgb(74,123,157) | Izvezi XML, Excel, PDF izvoz |
| **Destruktivno** | `#B85450` | rgb(184,84,80) | Briši, Obriši, Očisti sve |
| **Neutralno / Otvori** | `#8D6E63` | rgb(141,110,99) | Otvori, Novi, Učitaj listu |
| **AI / Pametna pomoć** | `#7B5EA7` | rgb(123,94,167) | Auto-popuni, Izračunaj mase, Mappings |
| **Izlaz / Cancel** | `#6B7280` | rgb(107,114,128) | Izlaz, Cancel |

### Hover stanja (posvijetliti za ~15%)

| Kategorija | Hover HEX |
|---|---|
| Primarna | `#3B9B87` |
| Uvoz | `#7986CB` |
| Izvoz | `#5B9DBF` |
| Destruktivno | `#D4726E` |
| Neutralno | `#A1887F` |
| AI | `#9575CD` |
| Izlaz | `#9CA3AF` |

### Pressed stanja (potamniti za ~10%)

| Kategorija | Pressed HEX |
|---|---|
| Primarna | `#245F53` |
| Uvoz | `#3F51B5` |
| Izvoz | `#3A6180` |
| Destruktivno | `#963F3C` |
| Neutralno | `#6D4C41` |
| AI | `#5E3D8F` |
| Izlaz | `#4B5563` |

---

## QSS implementacija

Kreiraj ili ažuriraj fajl `styles/button_styles.qss` (ili gdje se trenutno nalazi QSS):

```css
/* ============================================
   ASYCUDA Pro - Button Color System
   Muted Professional Palette v2.0
   ============================================ */

/* BASE za sva dugmad */
QPushButton {
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 13px;
    color: #FFFFFF;
    min-height: 28px;
}

/* ---- PRIMARNA akcija (Snimi, Dodaj, Validacija) ---- */
QPushButton[btnType="primary"],
QPushButton#btnSnimi,
QPushButton#btnDodaj,
QPushButton#btnValidacija {
    background-color: #2E7D6B;
}
QPushButton[btnType="primary"]:hover,
QPushButton#btnSnimi:hover,
QPushButton#btnDodaj:hover,
QPushButton#btnValidacija:hover {
    background-color: #3B9B87;
}
QPushButton[btnType="primary"]:pressed,
QPushButton#btnSnimi:pressed,
QPushButton#btnDodaj:pressed,
QPushButton#btnValidacija:pressed {
    background-color: #245F53;
}

/* ---- UVOZ (Uvezi XML, Učitaj, PDF in) ---- */
QPushButton[btnType="import"],
QPushButton#btnUveziXML,
QPushButton#btnUcitajListu,
QPushButton#btnUcitajMappinge {
    background-color: #5C6BC0;
}
QPushButton[btnType="import"]:hover,
QPushButton#btnUveziXML:hover,
QPushButton#btnUcitajListu:hover,
QPushButton#btnUcitajMappinge:hover {
    background-color: #7986CB;
}
QPushButton[btnType="import"]:pressed,
QPushButton#btnUveziXML:pressed,
QPushButton#btnUcitajListu:pressed,
QPushButton#btnUcitajMappinge:pressed {
    background-color: #3F51B5;
}

/* ---- IZVOZ (Izvezi XML, Excel, PDF out) ---- */
QPushButton[btnType="export"],
QPushButton#btnIzveziXML,
QPushButton#btnExcel,
QPushButton#btnPDF,
QPushButton#btnKreirajNaimenovanja {
    background-color: #4A7B9D;
}
QPushButton[btnType="export"]:hover,
QPushButton#btnIzveziXML:hover,
QPushButton#btnExcel:hover,
QPushButton#btnPDF:hover,
QPushButton#btnKreirajNaimenovanja:hover {
    background-color: #5B9DBF;
}
QPushButton[btnType="export"]:pressed,
QPushButton#btnIzveziXML:pressed,
QPushButton#btnExcel:pressed,
QPushButton#btnPDF:pressed,
QPushButton#btnKreirajNaimenovanja:pressed {
    background-color: #3A6180;
}

/* ---- DESTRUKTIVNO (Briši, Obriši, Očisti sve) ---- */
QPushButton[btnType="danger"],
QPushButton#btnBrisi,
QPushButton#btnObrisi,
QPushButton#btnOcistiSve {
    background-color: #B85450;
}
QPushButton[btnType="danger"]:hover,
QPushButton#btnBrisi:hover,
QPushButton#btnObrisi:hover,
QPushButton#btnOcistiSve:hover {
    background-color: #D4726E;
}
QPushButton[btnType="danger"]:pressed,
QPushButton#btnBrisi:pressed,
QPushButton#btnObrisi:pressed,
QPushButton#btnOcistiSve:pressed {
    background-color: #963F3C;
}

/* ---- NEUTRALNO (Otvori, Novi, Učitaj glavnu listu) ---- */
QPushButton[btnType="neutral"],
QPushButton#btnOtvori,
QPushButton#btnNovi {
    background-color: #8D6E63;
}
QPushButton[btnType="neutral"]:hover,
QPushButton#btnOtvori:hover,
QPushButton#btnNovi:hover {
    background-color: #A1887F;
}
QPushButton[btnType="neutral"]:pressed,
QPushButton#btnOtvori:pressed,
QPushButton#btnNovi:pressed {
    background-color: #6D4C41;
}

/* ---- AI / PAMETNA POMOĆ ---- */
QPushButton[btnType="ai"],
QPushButton#btnAutoPopuni,
QPushButton#btnIzracunajMase,
QPushButton#btnMappings {
    background-color: #7B5EA7;
}
QPushButton[btnType="ai"]:hover,
QPushButton#btnAutoPopuni:hover,
QPushButton#btnIzracunajMase:hover,
QPushButton#btnMappings:hover {
    background-color: #9575CD;
}
QPushButton[btnType="ai"]:pressed,
QPushButton#btnAutoPopuni:pressed,
QPushButton#btnIzracunajMase:pressed,
QPushButton#btnMappings:pressed {
    background-color: #5E3D8F;
}

/* ---- IZLAZ / CANCEL ---- */
QPushButton[btnType="cancel"],
QPushButton#btnIzlaz,
QPushButton#btnCancel {
    background-color: #6B7280;
}
QPushButton[btnType="cancel"]:hover,
QPushButton#btnIzlaz:hover,
QPushButton#btnCancel:hover {
    background-color: #9CA3AF;
}
QPushButton[btnType="cancel"]:pressed,
QPushButton#btnIzlaz:pressed,
QPushButton#btnCancel:pressed {
    background-color: #4B5563;
}

/* ---- DISABLED stanje za sva dugmad ---- */
QPushButton:disabled {
    background-color: #D1D5DB;
    color: #9CA3AF;
}
```

---

## Upute za implementaciju

### Opcija A — Postavljanje objectName na dugmadima (preporučeno)

Pronađi gdje se kreira svako dugme u kodu i dodaj `setObjectName`:

```python
# Primjeri
self.btn_snimi.setObjectName("btnSnimi")
self.btn_uvezi_xml.setObjectName("btnUveziXML")
self.btn_izvezi_xml.setObjectName("btnIzveziXML")
self.btn_brisi.setObjectName("btnBrisi")
self.btn_otvori.setObjectName("btnOtvori")
self.btn_novi.setObjectName("btnNovi")
self.btn_izlaz.setObjectName("btnIzlaz")
self.btn_dodaj.setObjectName("btnDodaj")
self.btn_obrisi.setObjectName("btnObrisi")
self.btn_ocisti_sve.setObjectName("btnOcistiSve")
self.btn_excel.setObjectName("btnExcel")
self.btn_pdf.setObjectName("btnPDF")
self.btn_kreiraj_naimenovanja.setObjectName("btnKreirajNaimenovanja")
self.btn_validacija.setObjectName("btnValidacija")
self.btn_auto_popuni.setObjectName("btnAutoPopuni")
self.btn_izracunaj_mase.setObjectName("btnIzracunajMase")
self.btn_ucitaj_mappinge.setObjectName("btnUcitajMappinge")
self.btn_ucitaj_listu.setObjectName("btnUcitajListu")
```

### Opcija B — setProperty za grupno definisanje (alternativa)

```python
# Primjer grupnog dodjeljvanja
for btn in [self.btn_snimi, self.btn_dodaj, self.btn_validacija]:
    btn.setProperty("btnType", "primary")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
```

### Učitavanje QSS-a

```python
# U main.py ili gdje se inicijalizuje aplikacija
def load_stylesheet(app: QApplication) -> None:
    qss_path = Path(__file__).parent / "styles" / "button_styles.qss"
    with open(qss_path, "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
```

---

## Napomene

- Provjeri stvarne `objectName` vrijednosti u kodu — uskladi ih sa QSS selektorima ako se razlikuju
- Toolbar pozadina: preporučuje se `#F8F9FA` (umjesto čisto bijele) za manji kontrast zamor
- Ikone na dugmadima ostaju nepromijenjene — boje su dovoljne za razlikovanje
- Nakon primjene, testiraj na Fedora i Windows (Qt renderer se razlikuje u nijansama)
