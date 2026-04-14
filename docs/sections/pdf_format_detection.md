---
section: pdf_format_detection
file: importers/smart_pdf_importer.py
---

## Svrha

Analizira tekst prvih 3 stranice PDF-a i vraća string-key koji identificira vendor format. Redoslijed provjera je kritičan — greška u redoslijedu može uzrokovati pogrešan parser.

## Zavisnosti i pretpostavke

- Koristi `pdfplumber` za ekstrakciju teksta
- Radi na uppercase tekstu (`text_upper`) i normalizovanom tekstu bez dijakritika (`text_norm`)
- Dijakritici u PDF-u su nepouzdani (BLAGIĆ može biti enkodiran i bez č): normalizacija je neophodna

## Pravila i granice

Provjere i **zašto ovaj redoslijed**:

1. `blagic_attos` — mora biti **prije** generičkog Blagić jer ATTOS je podformat sa specifičnim headerom
2. `invoice_improved` — mora biti **prije** `blagic_loren` jer moderni Blagić format ima "NO. CODE TITLE MEASURE" header koji se preklapa
3. `imamoglu` — mora biti **prije** `blagic_loren` jer Imamoglu fakture mogu imati "BLAGIC" kao ime kupca (uvoznik)
4. `blagic_loren` — dolazi nakon specifičnijih Blagić provjera
5. Ostali formati — nema međusobnog konflikta, redoslijed je nebitan
6. `generic` — uvijek posljednji fallback

Ako se promijeni redoslijed provjera, moguće je da pogrešan parser dobije validan PDF.

## Zašto ovako

Keyword detekcija je brza i pouzdana za poznate vendore koji imaju karakteristične tekste. Alternativa (heuristika tabela/kolonni layout) bi bila sporija i krhkija.
