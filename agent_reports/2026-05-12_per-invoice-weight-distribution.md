# Per-Invoice Raspodjela Težina — Agent Report

**Datum:** 2026-05-12  
**Commit:** d143050

---

## Šta je urađeno

Popravljeno dugme "Izračunaj mase" u tabu Faktura — više ne koristi globalni
toolbar total za distribuciju težina već raspoređuje težinu svake fakture
**samo na stavke te fakture**.

---

## Zašto

Korisnik je primijetio da faktura 2601019 (ukupno 20 kg) nakon klika na dugme
"Izračunaj mase" pokazuje stavke s težinom 81 kg i sličnim pogrešnim vrijednostima.

**Uzrok:** Dugme je uzimalo toolbar total (suma SVIH faktura u deklaraciji,
npr. 3062 kg) i proporcionalno ga dijelilo na SVE stavke bez razlikovanja kojoj
fakturi stavka pripada. Sa 563 stavki × 5.44 kg/kom po udjelu količine,
faktura od 20 kg je dobivala pogrešne vrijednosti.

---

## Kako je urađeno

### 1. Novi field u modelu (`core/draft/draft.py`)

```python
invoice_weights: Dict[str, Tuple[float, float]] = field(default_factory=dict)
```

Čuva per-invoice težine: `{invoice_name: (bruto_kg, neto_kg)}`.

### 2. Punjenje pri uvozu (`gui/tabs/faktura_view.py`)

U oba puta uvoza (single-file `_on_import_finished` i multi-file `_import_multiple_files`),
odmah nakon `_distribute_invoice_weights`:

```python
if bruto_kg > 0 or neto_kg > 0:
    self.draft.invoice_weights[invoice_name] = (bruto_kg, neto_kg)
```

Ključ = `result.invoice_name` ili `Path(filepath).stem` kao fallback.

### 3. Refaktor `_on_calculate_masses`

Staro: `MassCalculator.calculate_masses(self.draft.invoice_lines, bruto_total, neto_total)`

Novo:
1. Grupiši `draft.invoice_lines` po `line.invoice_number`
2. Za svaku grupu traži `draft.invoice_weights[inv_key]` → pozovi `MassCalculator` sa tim težinama
3. Fakture bez sačuvane težine → upozori korisnika (ne radi pogrešnu distribuciju)
4. Stavke bez `invoice_number` → fallback na toolbar total (stari draft, ručni unos)

---

## Tabela commitova

| Hash | Opis |
|------|------|
| d143050 | fix(faktura): dugme 'Izračunaj mase' raspoređuje težine per-faktura |

---

## Edge Cases

| Situacija | Ponašanje |
|-----------|-----------|
| Stari draft bez `invoice_weights` | Upozorenje s imenima faktura, ne pogrešna distribucija |
| Stavke bez `invoice_number` | Fallback na toolbar total |
| Kombinirani import (Excel+PDF) | Težina se čuva iz `result.invoice_name`, zamijeni se pri ponovnom uvozu |
| Faktura sa jednom stavkom | Dobija tačno svoju težinu sa fakture, ne udio globalnog totala |
