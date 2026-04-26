# Zadatak: Unificiran UI sistem boja — sve iz Zaglavlje palete

## Kontekst i filozofija

Zaglavlje tab ima 7 jasno definisanih tonova dugmadi koji se koriste kao
**ishodišna paleta hue-ova**. Sve ostalo u aplikaciji (Faktura toolbar naslovi,
tabovi, ostala dugmad) dobija boje iz iste familije — samo desaturirane
i prilagođene kontekstu. Rezultat: jedna vizualna logika kroz cijelu aplikaciju.

---

## Izvorna paleta iz Zaglavlja → Muted verzije

| Uloga | Original (Zaglavlje) | Muted verzija | Koristi se za |
|---|---|---|---|
| **Plava — Neutral/Novi** | `#62B0DC` | `#4A7FA5` | Novi, Učitaj listu, PDF, Excel, XML generičko |
| **Žuta — Sekundarno/Otvori** | `#E8C46A` | `#9B8250` | Otvori, neutral 2 |
| **Ljubičasta — Uvoz** | `#C4A3D4` | `#7B5C96` | Uvezi XML, PDF uvoz, Učitaj mappinge |
| **Zelena — Primarna/Snimi** | `#5CBF7A` | `#3D7A5F` | Snimi, Dodaj, Validacija |
| **Crvena — Opasnost** | `#F09080` | `#9B4A48` | Briši, Obriši, Očisti sve |
| **Teal — Izvoz** | `#5BCFBA` | `#3D8B7A` | Izvezi XML, PDF izvoz, Excel izvoz, Kreiraj Naimenovanja |
| **Siva — Izlaz** | `#D0D3D8` | `#6B7280` | Izlaz, Cancel |

---

## Mapiranje na Faktura toolbar sekcije

Svaka sekcija u Faktura toolbar-u dobija pozadinsku boju iz odgovarajuće
hue familije — ali izrazito svijetlu (~10% zasićenosti) da ne dominira:

| Sekcija | Hue familija | Header pozadina | Header tekst |
|---|---|---|---|
| **Glavna lista** | Plava | `#DAE8F2` | `#2C5570` |
| **Uvezi** | Ljubičasta | `#EDE4F5` | `#4A2E6B` |
| **Uredi** | Žuta | `#F5EDD8` | `#5C4A1E` |
| **Izvezi** | Teal | `#D8F0EC` | `#1E5A50` |
| **Pametna pomoć** | Ljubičasta (AI) | `#EDE4F5` | `#4A2E6B` |

---

## QSS — Kompletni stylesheet

```css
/* ============================================================
   Deklarant Pro — Unified Color System v3.0
   Izvor: Zaglavlje hue paleta, desaturirana
   ============================================================ */

/* ============================
   TABOVI
   ============================ */

QTabBar::tab {
    background-color: #C5CAD0;
    color: #3D4549;
    padding: 6px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
    font-size: 12px;
}
QTabBar::tab:hover {
    background-color: #A8B2BA;
    color: #263238;
}
QTabBar::tab:selected {
    background-color: #4A7FA5;
    color: #FFFFFF;
    border-bottom: 2px solid #2C5570;
}

/* ============================
   TOOLBAR POZADINA
   ============================ */

QToolBar,
QWidget#toolbarWidget,
QFrame#toolbarFrame {
    background-color: #EEF1F3;
    border-bottom: 1px solid #B0BEC5;
    spacing: 4px;
    padding: 4px 6px;
}

/* ============================
   NASLOVI SEKCIJA TOOLBAR-A
   ============================ */

/* Glavna lista — plava familija */
QLabel#lblGlavnaLista,
QGroupBox#grpGlavnaLista,
QFrame#frameGlavnaLista {
    background-color: #DAE8F2;
    color: #2C5570;
}
QGroupBox#grpGlavnaLista::title { color: #2C5570; background-color: #DAE8F2; }

/* Uvezi — ljubičasta familija */
QLabel#lblUvezi,
QGroupBox#grpUvezi,
QFrame#frameUvezi {
    background-color: #EDE4F5;
    color: #4A2E6B;
}
QGroupBox#grpUvezi::title { color: #4A2E6B; background-color: #EDE4F5; }

/* Uredi — žuta familija */
QLabel#lblUredi,
QGroupBox#grpUredi,
QFrame#frameUredi {
    background-color: #F5EDD8;
    color: #5C4A1E;
}
QGroupBox#grpUredi::title { color: #5C4A1E; background-color: #F5EDD8; }

/* Izvezi — teal familija */
QLabel#lblIzvezi,
QGroupBox#grpIzvezi,
QFrame#frameIzvezi {
    background-color: #D8F0EC;
    color: #1E5A50;
}
QGroupBox#grpIzvezi::title { color: #1E5A50; background-color: #D8F0EC; }

/* Pametna pomoć — ljubičasta (AI) */
QLabel#lblPametnaPomoc,
QGroupBox#grpPametnaPomoc,
QFrame#framePametnaPomoc {
    background-color: #EDE4F5;
    color: #4A2E6B;
}
QGroupBox#grpPametnaPomoc::title { color: #4A2E6B; background-color: #EDE4F5; }

/* Font za sve naslove sekcija */
QLabel[sectionHeader="true"] {
    font-weight: 700;
    font-size: 12px;
    padding: 3px 8px;
    border-bottom: 1px solid rgba(0,0,0,0.1);
}

/* ============================
   DUGMAD — BAZA
   ============================ */

QPushButton {
    background-color: #4A7FA5;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 600;
    font-size: 12px;
    min-height: 26px;
}
QPushButton:hover    { background-color: #5B93BB; }
QPushButton:pressed  { background-color: #346080; }
QPushButton:disabled { background-color: #B0BEC5; color: #78909C; }

/* ============================
   ZELENA — Primarna akcija
   Snimi, Dodaj, Validacija
   ============================ */

QPushButton#btnSnimi,
QPushButton#btnDodaj,
QPushButton#btnValidacija,
QPushButton[btnType="primary"] {
    background-color: #3D7A5F;
}
QPushButton#btnSnimi:hover,
QPushButton#btnDodaj:hover,
QPushButton#btnValidacija:hover,
QPushButton[btnType="primary"]:hover    { background-color: #4E9B77; }
QPushButton#btnSnimi:pressed,
QPushButton#btnDodaj:pressed,
QPushButton#btnValidacija:pressed,
QPushButton[btnType="primary"]:pressed  { background-color: #2E5E48; }

/* ============================
   LJUBIČASTA — Uvoz
   Uvezi XML, Učitaj mappinge
   ============================ */

QPushButton#btnUveziXML,
QPushButton#btnUcitajMappinge,
QPushButton[btnType="import"] {
    background-color: #7B5C96;
}
QPushButton#btnUveziXML:hover,
QPushButton#btnUcitajMappinge:hover,
QPushButton[btnType="import"]:hover    { background-color: #9472B0; }
QPushButton#btnUveziXML:pressed,
QPushButton#btnUcitajMappinge:pressed,
QPushButton[btnType="import"]:pressed  { background-color: #5E4272; }

/* ============================
   TEAL — Izvoz
   Izvezi XML, Excel, PDF, Kreiraj Naimenovanja
   ============================ */

QPushButton#btnIzveziXML,
QPushButton#btnExcel,
QPushButton#btnPDF,
QPushButton#btnKreirajNaimenovanja,
QPushButton[btnType="export"] {
    background-color: #3D8B7A;
}
QPushButton#btnIzveziXML:hover,
QPushButton#btnExcel:hover,
QPushButton#btnPDF:hover,
QPushButton#btnKreirajNaimenovanja:hover,
QPushButton[btnType="export"]:hover    { background-color: #4EAD99; }
QPushButton#btnIzveziXML:pressed,
QPushButton#btnExcel:pressed,
QPushButton#btnPDF:pressed,
QPushButton#btnKreirajNaimenovanja:pressed,
QPushButton[btnType="export"]:pressed  { background-color: #2C6B5C; }

/* ============================
   ŽUTA/BRAON — Sekundarno
   Otvori
   ============================ */

QPushButton#btnOtvori,
QPushButton[btnType="secondary"] {
    background-color: #9B8250;
}
QPushButton#btnOtvori:hover,
QPushButton[btnType="secondary"]:hover    { background-color: #B89A64; }
QPushButton#btnOtvori:pressed,
QPushButton[btnType="secondary"]:pressed  { background-color: #7A6338; }

/* ============================
   CRVENA — Opasnost
   Briši, Obriši, Očisti sve
   ============================ */

QPushButton#btnBrisi,
QPushButton#btnObrisi,
QPushButton#btnOcistiSve,
QPushButton[btnType="danger"] {
    background-color: #9B4A48;
}
QPushButton#btnBrisi:hover,
QPushButton#btnObrisi:hover,
QPushButton#btnOcistiSve:hover,
QPushButton[btnType="danger"]:hover    { background-color: #BC5C5A; }
QPushButton#btnBrisi:pressed,
QPushButton#btnObrisi:pressed,
QPushButton#btnOcistiSve:pressed,
QPushButton[btnType="danger"]:pressed  { background-color: #7A3432; }

/* ============================
   SIVA — Izlaz / Cancel
   ============================ */

QPushButton#btnIzlaz,
QPushButton#btnCancel,
QPushButton[btnType="cancel"] {
    background-color: #6B7280;
    color: #FFFFFF;
}
QPushButton#btnIzlaz:hover,
QPushButton#btnCancel:hover,
QPushButton[btnType="cancel"]:hover    { background-color: #8A9099; }
QPushButton#btnIzlaz:pressed,
QPushButton#btnCancel:pressed,
QPushButton[btnType="cancel"]:pressed  { background-color: #4E5560; }
```

---

## Python — objectName postavljanje

```python
# ---- Zaglavlje tab ----
self.btn_novi.setObjectName("btnNovi")           # baza (plava)
self.btn_otvori.setObjectName("btnOtvori")       # žuta/braon
self.btn_uvezi_xml.setObjectName("btnUveziXML")  # ljubičasta
self.btn_snimi.setObjectName("btnSnimi")         # zelena
self.btn_brisi.setObjectName("btnBrisi")         # crvena
self.btn_izvezi_xml.setObjectName("btnIzveziXML")# teal
self.btn_izlaz.setObjectName("btnIzlaz")         # siva

# ---- Faktura tab ----
self.btn_dodaj.setObjectName("btnDodaj")
self.btn_obrisi.setObjectName("btnObrisi")
self.btn_ocisti_sve.setObjectName("btnOcistiSve")
self.btn_excel_izvoz.setObjectName("btnExcel")
self.btn_pdf_izvoz.setObjectName("btnPDF")
self.btn_kreiraj_naimenovanja.setObjectName("btnKreirajNaimenovanja")
self.btn_validacija.setObjectName("btnValidacija")
self.btn_auto_popuni.setObjectName("btnAutoPopuni")    # AI → import boja
self.btn_izracunaj_mase.setObjectName("btnIzracunajMase")
self.btn_ucitaj_mappinge.setObjectName("btnUcitajMappinge")
self.btn_ucitaj_listu.setObjectName("btnNovi")  # ili ostavi default plavu

# ---- Naslovi sekcija (ako su QLabel) ----
self.lbl_glavna_lista.setObjectName("lblGlavnaLista")
self.lbl_uvezi.setObjectName("lblUvezi")
self.lbl_uredi.setObjectName("lblUredi")
self.lbl_izvezi.setObjectName("lblIzvezi")
self.lbl_pametna_pomoc.setObjectName("lblPametnaPomoc")

# Ako su QGroupBox:
self.grp_uvezi.setObjectName("grpUvezi")
# itd.
```

---

## Vizualna logika (sažetak)

```
Plava   (#4A7FA5) → Novi, Učitaj, generično     [Faktura: Glavna lista header]
Žuta    (#9B8250) → Otvori                       [Faktura: Uredi header]
Ljubič. (#7B5C96) → Uvoz, AI akcije             [Faktura: Uvezi + Pametna pomoć header]
Zelena  (#3D7A5F) → Snimi, Dodaj, Validacija
Crvena  (#9B4A48) → Briši, Obriši, Očisti
Teal    (#3D8B7A) → Izvoz, Kreiraj Naimenovanja [Faktura: Izvezi header]
Siva    (#6B7280) → Izlaz, Cancel
```

Isti hue-ovi, isti semantički smisao — kroz sve tabove.
