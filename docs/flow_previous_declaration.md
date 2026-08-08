# Automatizacija: Prethodna deklaracija → Zaglavlje

## Cilj

Kad korisnik klikne **"Prethodna deklaracija"** na Faktura tabu, aplikacija:
1. Automatski pronađe odgovarajući ASYCUDA XML za izvoznika
2. Prikaže pronađene podatke u dijalogu
3. Korisnik bira: **Učitaj** (uvezi u zaglavlje), **Ručno...** (odaberi drugi XML), ili **Odustani**

## Problem

`extract_header_from_xml()` je vraćao samo 9 polja:
- `izvoznik_naziv`, `drzava_izvoza_sifra`, `drzava_izvoza_naziv`, `valuta`, `uslovi_kod`, `uslovi_mjesto`, `deklaracija_tip`, `deklaracija_oznaka`, `deklaracija_a`

Nedostajala su polja: primalac (naziv, grad, adresa, JIB), izvoznik (grad, država, adresa), carinska ispostava (šifra + naziv).

## Rješenje

### 1. Proširena XML ekstrakcija (`extract_header_from_xml`)

Funkcija sada parsira multiline formate i čita dodatne XML elemente:

| XML element | Draft polje | Napomena |
|---|---|---|
| `Exporter_name` (1. linija) | `izvoznik_naziv` | multiline: `"CMANA DOO\nKRNJEVO\nSRBIJA"` |
| `Exporter_name` (2. linija) | `izvoznik_grad` | |
| `Exporter_name` (3. linija) | `izvoznik_drzava` | |
| `Consignee_name` (1. linija) | `primalac_naziv` | multiline: `"LEBURIĆ KOMERC DOO\nPRNJAVOR\nVIJAKA BB"` |
| `Consignee_name` (2. linija) | `primalac_grad` | |
| `Consignee_name` (3. linija) | `primalac_adresa` | |
| `Consignee_code` | `primalac_id` | JIB/PIB primaoca |
| `Customs_clearance_office_code` + `Customs_Clearance_office_name` | `ured_odredista` | format: `"BA097012  CI Bijeljina"` |

### 2. Dopuna iz baze (`_enrich_header_from_catalogs`)

Nakon XML ekstrakcije, podaci se dopunjuju iz PostgreSQL kataloga:
- `catalogs.izvoznici` → adresa, grad, država, JIB izvoznika
- `catalogs.uvoznici` → adresa, grad, država, JIB primaoca

Koristi `or` logiku — vrijednosti iz baze se upisuju SAMO ako draft polje nije već popunjeno (XML vrijednosti imaju prioritet).

### 3. Automatska izgradnja indeksa (`_ensure_exporter_index_ready`)

`find_xml_for_pair()` zavisi od indeksa `catalogs.exporter_xml_index` u bazi.
Ako tabela nema podataka (nikad nije građena), automatski se pokreće `reindex()`:
- Skenira svih ~5700 XML-ova iz `docs/NOVA ASIKUDA`
- Gradi indeks po parovima (exporter, consignee)
- Jednokratna operacija — svaki sljedeći klik je instantan

### 4. Dijalog toka

```
Korisnik klikne "Prethodna deklaracija"
        │
        ▼
   Poznat izvoznik? ──NE──▶ "Odaberi XML" dijalog ──▶ File picker
        │
       DA
        │
        ▼
   Indeks prazan? ──DA──▶ reindex() ──▶ "⏳ Gradim indeks..."
        │
        NE
        │
        ▼
   find_xml_for_pair()
        │
        ├── Nađen ──▶ Preview dijalog ──▶ [Učitaj] [Ručno...] [Odustani]
        │                  │
        │               Ručno...
        │                  │
        │                  ▼
        │              File picker ──▶ Parsiraj ──▶ Preview ──▶ [Učitaj] [Odustani]
        │                                          
        └── Nije nađen ──▶ "Odaberi XML" ──▶ File picker ──▶ (isti flow)
```

Sva dugmad su na **srpskom jeziku**: Učitaj, Ručno..., Odustani, Odaberi.

### 5. Rezultat

Nakon potvrde "Učitaj":
- `apply_header_to_draft()` upisuje sva XML polja u draft
- `_enrich_header_from_catalogs()` dopunjava iz baze
- `ZaglavljeTab.load_from_draft()` osvježava GUI
- Status labela: "✓ Zaglavlje učitano iz prethodne deklaracije"

## Izmijenjeni fajlovi

| Fajl | Izmjena |
|---|---|
| `services/faktura/xml_header_extraction.py` | Proširena XML ekstrakcija, multiline parsing |
| `gui/tabs/faktura_view.py` | `_on_load_previous_declaration` tok, `_ensure_exporter_index_ready`, enrich |
| `dist_client/services/faktura/xml_header_extraction.py` | Sinhronizovana kopija |
| `dist_client/gui/tabs/faktura_view.py` | Sinhronizovana kopija |

## Napomene

- **Rb.1 Deklarant**: carinska ispostava (`ured_odredista`) se popunjava iz XML polja `Customs_clearance_office_code` i `Customs_Clearance_office_name`
- **Enrich iz baze**: adresa izvoznika, poštanski brojevi i država primaoca nisu u XML-u — popunjavaju se iz kataloga
- **Indeks**: prvi put se gradi automatski (može potrajati nekoliko minuta za ~5700 XML-ova). Poslije je instantan
