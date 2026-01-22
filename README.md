# ASYCUDA Pro

Aplikacija za carinske deklaracije.

## Instalacija zavisnosti

```bash
pip install PySide6 openpyxl PyPDF2 lxml
```

## Testiranje

Pre prvog pokretanja, možete testirati da li je sve ispravno konfigurisano:

```bash
python3 test_app.py
```

Ovaj script će proveriti:
- Da li se svi moduli mogu importovati
- Da li Draft objekat može da se kreira
- Da li UI fajlovi postoje

## Pokretanje aplikacije

**Napomena:** Aplikacija se može zaustaviti sa `Ctrl+C` u terminalu.

### Metoda 1: Direktno pokretanje (Preporučeno)
```bash
cd /home/radovan/Desktop/PythonProjects/asycuda_pro
python3 __main__.py
```

### Metoda 2: Korišćenjem shell skripta
```bash
cd /home/radovan/Desktop/PythonProjects/asycuda_pro
./run_app.sh
```

### Metoda 3: Kao Python modul (iz parent direktorija)
```bash
cd /home/radovan/Desktop/PythonProjects
python3 -m asycuda_pro
```

## Struktura projekta

```
asycuda_pro/
├── app/            - Glavna aplikacija (QApplication)
├── core/           - Osnovni modeli (Draft, Naimenovanje)
├── database/       - Database modeli i migracije
├── exporters/      - XML exporteri
├── gui/            - GUI komponente
│   └── tabs/       - Tab widgeti
├── importers/      - Importeri (Excel, PDF, XML)
├── sifrarnici/     - Šifarnici (zemlje, transport, itd.)
├── ui/             - Qt Designer .ui fajlovi
├── utils/          - Utility funkcije
└── __main__.py     - Entry point
```

## Zavisnosti

- Python 3.10+
- PySide6 (Qt6 bindings)
- openpyxl (Excel)
- PyPDF2 (PDF)
- lxml (XML)
