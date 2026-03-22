# ASYCUDA Pro Test Suite

Sveobuhvatni testovi za ASYCUDA Pro aplikaciju.

## Rezultati

- **231 test prolazi**
- **0 testova pada**
- **0 preskočeno** (svi testovi sada rade sa instaliranim pydantic)

## Struktura Testova

```
tests/
├── __init__.py              # Test package init
├── conftest.py              # Pytest konfiguracija i fixtures
├── test_draft.py            # Core Draft modeli
├── test_database.py         # Database modeli i repository
├── test_xml_export.py       # XML exporter i builder
├── test_sifrarnici.py       # Šifrarnici (zemlje, transport, pakovanja)
├── test_utils.py            # Utility funkcije (money, weight, text)
└── test_importers.py        # Importeri (Excel, PDF, XML)
```

## Pokretanje Testova

### Svi testovi
```bash
cd /home/radovan/Desktop/PythonProjects/asycuda_pro
python -m pytest tests/ -v
```

### Testovi po fajlovima
```bash
# Core modeli
python -m pytest tests/test_draft.py -v

# Database
python -m pytest tests/test_database.py -v

# XML Export
python -m pytest tests/test_xml_export.py -v

# Šifrarnici
python -m pytest tests/test_sifrarnici.py -v

# Utility funkcije
python -m pytest tests/test_utils.py -v

# Importeri
python -m pytest tests/test_importers.py -v
```

### Testovi po kategorijama
```bash
# Samo unit testovi
python -m pytest tests/ -v -k "not Integration"

# Samo integracioni testovi
python -m pytest tests/ -v -k "Integration"

# Testovi specifične klase
python -m pytest tests/test_draft.py::TestDeclarationDraft -v
```

### Coverage izveštaj
```bash
python -m pytest tests/ --cov=. --cov-report=html
```

## Pokrivene Komponente

### 1. Core Draft Modeli (`test_draft.py`)
- `DeclarationDraft` - Centralni radni objekat
- `InvoiceLine` - Stavka fakture
- `NaimenovanjeDraft` - Stavka deklaracije
- `Party` - Podaci o strankama (izvoznik, primalac)
- `AttachedDocument` - Priloženi dokumenti
- Helper funkcije (`_s`, `_f`)

### 2. Database Modeli (`test_database.py`)
- `DraftModel` - Model za čuvanje draft-ova
- `AttachmentModel` - Model za priloge
- `DraftRepository` - CRUD operacije
- `AttachmentRepository` - Upravljanje prilozima

### 3. XML Export (`test_xml_export.py`)
- `read_asycuda_xml` - Parsiranje ASYCUDA XML-a
- `build_template_from_xml_files` - Kreiranje template-a
- `write_xml_stub` - XML stub exporter
- `AsycudaXMLBuilder` - Buildovanje XML-a iz Draft-a
- Regex pattern-i za validaciju
- Type inference funkcije

### 4. Šifrarnici (`test_sifrarnici.py`)
- `zemlje` - ISO 3166-1 alpha-2 kodovi
- `transport` - UN/ECE Recommendation 19 kodovi
- `pakovanja` - Vrste pakovanja
- `povlastice` - Preferencijalni tretmani

### 5. Utility Funkcije (`test_utils.py`)
- `money` - Formatiranje, parsiranje, konverzija valuta
- `weight` - Konverzija jedinica mere (kg, g, ton)
- `text` - Obrada teksta (normalizacija, skraćivanje, čišćenje)
- `country_normalizer` - Normalizacija naziva zemalja u ISO kodove

### 6. Importeri (`test_importers.py`)
- `ImportResult` - Rezultat importa
- `ExcelImporter` - Import Excel fajlova
- `ExcelImportConfig` - Konfiguracija Excel importa
- `InvoiceLine.from_any` - Parsiranje različitih formata

## Preskočeni Testovi

Trenutno nema preskočenih testova. Svi testovi se izvršavaju uspešno.

Napomena: Neki Excel importer testovi mogu zahtevati dodatne zavisnosti u specifičnim
okolnostima (npr. nedostupne specijalizovane servise), ali pytest će ih automatski
preskočiti sa odgovarajućom porukom.

## Dodavanje Novih Testova

1. Kreiraj novi test fajl sa prefiksom `test_`
2. Dodaj test klase sa prefiksom `Test`
3. Dodaj test metode sa prefiksom `test_`
4. Koristi `assert` za validaciju
5. Koristi `pytest.fixture` za shared setup

### Primer
```python
def test_my_feature():
    """Test description."""
    result = my_function(input)
    assert result == expected_value
```

## CI/CD Integracija

Za GitHub Actions ili druge CI alate:

```yaml
- name: Run tests
  run: |
    pip install pytest openpyxl
    python -m pytest tests/ -v --tb=short
```

## Napomene

- Testovi koriste `pytest` framework
- Svi testovi su nezavisni i mogu se pokretati pojedinačno
- Testovi ne modifikuju stvarne fajlove ili baze podataka
- Korišćeni su `tmp_path` fixture-i za privremene fajlove
