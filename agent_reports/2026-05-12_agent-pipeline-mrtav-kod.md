# Uklanjanje mrtvog koda iz agent pipelina — Agent Report

**Datum:** 2026-05-12  
**Commit:** 06fe2d3

---

## Šta je urađeno

Uklonjena su dva mrtva koda iz agent pipelina koje je Codex analiza
flagirala kao rizik (linije 426 i 621 u `import_pipeline_service.py`).

---

## Zašto

Codex je u reviзiji prethodnog fixa (per-invoice raspodjela težina) primijetio
da linije 426 i 621 koriste globalni toolbar total za raspodjelu masa — isti
bug koji je upravo popravljan. Istraga je pokazala da su obje funkcije
**nikad pozvane** iz aktivnog koda, pa je rješenje bilo brisanje.

---

## Šta je uklonjeno

### `_izracunaj_tezine_interno` (`import_pipeline_service.py`)
Stari globalni mass calc koji je čitao toolbar total i distribuirao na
sve stavke bez razlikovanja faktura. Ostalo je kao relikt nakon
centralizacije na MassCalculator (commit 3ef0247).

### `_uvezi_u_deklaraciju` (`import_pipeline_service.py`, ~150 linija)
Kompletan alternativni pipeline: validacija → uvoz u draft → toolbar
težine → globalni mass calc (linija 621) → PE2/EUR.1 dijalozi → rezime.
Nikad integrisan u aktivan tok.

### Wrapper metode
- `izracunaj_tezine_interno` u service klasi
- `uvezi_u_deklaraciju` u service klasi
- `_izracunaj_težine_interno` u `agent_controller.py`
- `_uvezi_u_deklaraciju` u `agent_controller.py`

---

## Aktivni agent tok (ostaje nepromijenjen)

```
_puna_auto_pipeline:
  1. fw._on_calculate_masses(auto=True)   ← per-invoice logika
  2. fw._on_auto_fill(auto=True)
  3. fw._on_validate_all(auto=True)
  4. Dijalog potvrde deklaranta
  5. fw._on_create_naimenovanja(auto=True)
```

---

## Tabela commitova

| Hash | Opis |
|------|------|
| 06fe2d3 | chore(agent): ukloni mrtav kod — _uvezi_u_deklaraciju i _izracunaj_tezine_interno |

---

## Metrika

- **Uklonjeno:** 207 linija  
- **Rizici zatvoreni:** oba Codex rizika (linija 426 i 621)
