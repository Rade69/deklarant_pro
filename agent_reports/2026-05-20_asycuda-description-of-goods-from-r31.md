# Agent report — ASYCUDA Description_of_goods iz Rub.31 teksta

Datum: 2026-05-20

## Problem

Nakon prethodne Rub.31 popravke korisnik je testirao novi XML u ASYCUDA aplikaciji
i i dalje vidio genericki opis `-- ostali` kao prvi red prikaza.

Uzrok nije bio samo u `Commercial_Description`. ASYCUDA prikazuje i
`Description_of_goods`, a u stvarnom GUI slucaju detaljni tarifni opis nije bio
popunjen u `goods_description`, nego se nalazio samo u `goods_trade_name`.
Zbog toga je `Description_of_goods` i dalje padao na `tariff_description2`
vrijednost `-- ostali`.

## Urađeno

- `Description_of_goods` sada preferira detaljne opise:
  1. `tariff_description1`
  2. `goods_description`
  3. prvu smislenu cjelinu iz `goods_trade_name`
  4. `tariff_description2`
- Ako postoje samo genericki opisi tipa `-- ostali`, builder izvlaci opis iz
  `goods_trade_name` prije nego sto padne na genericki opis.
- `Commercial_Description` pri kompakciji vise ne ponavlja istu cjelinu koja je
  vec prebacena u `Description_of_goods`.
- Kod jednolinijskog Rub.31 teksta sa vise tacaka razdvojenih tacka-zarezom,
  tekst se razdvaja na opisne cjeline, naziv robe i fakturu.
- Kada nema prostora za sve cjeline, cuva se robna linija i faktura.

Primjer novog izlaza:

```text
Description_of_goods:
Elektricni protocni ili akumulacijski grijaci vode i uronjivi grijaci

Commercial_Description:
elektricni aparati za grijanje prostora i elektricni...
GREJAC RERNE KONCAR 1550W MKR 20215300.1 4015
Faktura: 263VP-2026 (rb. 1)
```

## Testovi

Pokrenuto:

```bash
python -m pytest tests/unit/test_asycuda_goods_description.py tests/unit/test_parse_naimenovanja_xml.py tests/unit/test_pe_rub44_consistency.py tests/unit/test_naimenovanja_view_display_values.py -q
python -m py_compile exporters/asycuda_xml_builder.py
```

Rezultat:

```text
41 passed
py_compile OK
```

## GitNexus

- `impact(_build_description_of_goods)`: LOW
- `detect_changes`: LOW, bez pogodjenih execution flow-ova

## Napomena

`AGENTS.md` i `CLAUDE.md` su imali nevezane lokalne izmjene i nisu dio ove
promjene.
