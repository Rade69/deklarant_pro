---
section: invoice_number_similarity
file: services/import_service.py
---

## Svrha

Fuzzy matching dvije datoteke po broju fakture. Koristi se za automatsko sparivanje Excel i PDF datoteka istog posla (npr. `FAI-7-0-26.xlsx` + `FAI-7-0-26 PACKING LIST.pdf`).

## Zavisnosti i pretpostavke

- Ulazi su `filepath.stem` (ime datoteke bez ekstenzije)
- Funkcija ne gleda sadržaj datoteka, samo nazive
- Pretpostavlja da korisnik importuje par datoteka u kratkom nizu (jedna za drugom)

## Pravila i granice

Algoritam radi u dva koraka:
1. **Normalizacija**: ukloni crtice, podcrtice, razmake, pa ukloni generičke ključne riječi (`packing`, `list`, `pl`, `invoice`, `inv`, `faktura`)
2. **Provjera**: ili je jedan string podstring drugog (`n1 in n2`), ili dijele ≥80% zajedničkog prefiksa (za minimalni dužinu ≥5)

Prag 80% je empirijski — sprečava lažna sparivanja kratkih kodova a toleriše sitne razlike u oznakama.

## Zašto ovako

Alternativa je tražiti tačan match, ali vendori često dodaju " PL", "-packing", " PACKING LIST" na kraj istog broja fakture. Tačan match bi zahtijevao da korisnik preimenuje fajlove.
