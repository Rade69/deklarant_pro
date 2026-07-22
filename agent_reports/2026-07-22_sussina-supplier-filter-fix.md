# Agent Report — 2026-07-22: SUSSINA — hard supplier filter isključivao najjači istorijski zapis

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `services/agent/validation/historical_tariff_search_service.py` + `dist_client` kopija
- `tests/unit/test_historical_tariff_validation.py` (dopuna, 3 nova testa)
- `docs/CONTEXT.md` (§29, nastavak §27 dopune 5)

## Status izvora

Direktan nastavak `docs/CONTEXT.md` §27 dopune 5 (2026-07-21, NEDOVRŠENO — agent okruženje
tada nije imalo mrežni pristup PostgreSQL serveru). Korisnik je u međuvremenu: (1) popravio
mrežni pristup ([vidi §28](../docs/CONTEXT.md) — Desktop prečica pokretala `dist_client/`
sa zastarjelim `.env`), (2) pokrenuo Admin → "Učenje iz XML-ova" (310 novih parova). Ova
sesija je nastavljena kad je baza postala dostupna.

## GitNexus impact

`HistoricalTariffSearchService._execute` — LOW (2 direktna pozivaoca unutar istog fajla:
`_query_strict`, `_query_broad`; 1 indirektan preko `_search_one`; 1 dodatni pristup iz
`dist_client/scripts/agent_tariff_eval_report.py`; 0 affected_processes).
`gitnexus_detect_changes()` nakon izmjene: `risk_level: low`, `affected_count: 0`.

## Šta je urađeno

Provjerom baze (`catalogs.product_tariff_mapping`) direktnim upitom potvrđeno: mapping
"SUSSINA 650 tbl." → `21069098` (usage_count=40) postoji od **aprila 2026** — reindeksiranje
iz XML-ova NIJE bio uzrok problema (baza je već imala tačan podatak prije ove sesije).

Pravi uzrok pronađen tračenjem `_search_one()`: kad je izvoznik poznat (ime iz Zaglavlja ili
`invoice_line.exporter`), metoda primjenjuje TVRD SQL filter `AND supplier ILIKE
'%kljucna_rijec%'` — namjera je "bolje bez prijedloga nego pogrešan prijedlog od drugog
dobavljača". Problem: 4 najčistija i najkorišćenija SUSSINA zapisa (usage 24-40) su učena BEZ
upisanog dobavljača (`supplier=''`), dok zapisi SA dobavljačem imaju generički,
concatenated tekst (iz sirovog `Commercial_Description` XML polja) sa niskim usage_count
(3-4). Filter je TIHO isključivao najjači dokaz (usage=40) u korist slabijeg (usage=3), koji
onda nije prošao `decide_tariff_match` prag pouzdanosti → `SUPPRESS` → "nema boljeg
prijedloga", iako je arhiva imala jasan, dosljedan odgovor (33/33 XML fajlova).

Potvrđeno direktnim testom prije/poslije fixa (`_search_one("SUSSINA 650 tbl.",
"MEDICO PHARM SERVIS", "")`):
- **Prije**: vraća samo 1 slab zapis (usage=3), `decide_tariff_match` → SUPPRESS.
- **Poslije**: vraća i jak zapis (usage=40) na prvom mjestu, `decide_tariff_match` →
  SHOW_STRONG, score=40.

## Zašto je urađeno

Filter treba da spriječi MIJEŠANJE tarifa različitih, POTVRĐENO drugačijih dobavljača — ali
"dobavljač nije upisan" nije isto što i "dobavljač je potvrđeno drugačiji". Trenutna verzija
je penalizovala baš onu podklasu zapisa (bez supplier metadata) koja je često najčistija i
najpouzdanija, jer dolazi iz drugog/boljeg import puta nego sirovi XML `Commercial_Description`
tekst.

## Kako je urađeno

Tri ciljane izmjene u `historical_tariff_search_service.py`:

1. `_execute()`: WHERE klauzula `AND supplier ILIKE %s` → `AND (supplier ILIKE %s OR
   supplier IS NULL OR supplier = '')`. Zaštita od zapisa POUZDANO drugog dobavljača
   ostaje netaknuta — samo "nepoznato" više ne broji kao "pogrešno".
2. `_search_one()`: prosljeđuje `supplier_key` (umjesto paušalnog `supplier_matched=True/False`)
   u `_to_matches()`, jer rezultat SQL upita sad može biti mješavina potvrđenih i
   nepotvrđenih zapisa.
3. `_to_matches(rows, naziv_original, supplier_key: str = "")`: `supplier_match` se sad
   računa PO REDU (`supplier_key.lower() in supplier.lower()`) umjesto jednog bool-a za
   cijeli poziv — bitno jer nakon fixa rezultat MOŽE sadržati i redove gdje je dobavljač
   potvrđen i redove gdje nije, i evidence/confidence downstream zavisi od tačnog
   `supplier_match` po redu.

`dist_client` kopija bila je identična root-u prije izmjene (potvrđeno diff-om) — izmjena
primijenjena identično, `diff` nakon izmjene potvrđuje potpunu podudarnost.

## Šta nije dirano

- `decide_tariff_match`/`TariffDecisionThresholds`/pragovi (`MIN_USAGE_FOR_CROSS_CHAPTER` itd.)
  — problem nije bio u pragovima nego u tome koji zapisi uopšte stižu do te provjere.
- `_query_strict`/`_query_broad` — samo prosljeđuju `supplier_key` nepromijenjeno dalje.
- Sporedni nalaz: baza sadrži i POGREŠAN par (SUSSINA → `38249993`, usage=2) — vjerovatno
  ostatak istih pogrešnih deklaracija koje je korisnik prijavio. Nije čišćeno/brisano — nema
  praktičan negativan efekat jer jači `21069098` zapis (usage=40) uvijek pobjeđuje po
  `ORDER BY usage_count DESC`. Follow-up ako se pokaže problematičnim za neki drugi proizvod
  gdje bi omjer usage_count-a mogao ići u prilog pogrešnom zapisu.

## Verifikacija

```
python -m pytest tests/unit/test_historical_tariff_validation.py -v
  → 33 passed (30 postojećih + 3 nova)
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 842 passed, 58 skipped, 3 failed, 1 error (identično pretpostojećim/nepovezanim
    failovima iz prethodnih izvještaja — dist/ torch sken, cp1252 test fajl, hardkodovana
    Linux putanja, model_benchmark)
python -m py_compile services/agent/validation/historical_tariff_search_service.py
  dist_client/services/agent/validation/historical_tariff_search_service.py → OK
diff (root vs dist_client) → IDENTIČNI nakon izmjene
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
Direktan test protiv prave PostgreSQL baze (192.168.0.25): prije/poslije fixa,
  potvrđeno da _search_one sad vraća ispravan zapis (21069098, usage=40, SHOW_STRONG)
```

## Pronađeni problemi

Baza sadrži i pogrešan SUSSINA→38249993 zapis (usage=2) — dokumentovano gore, nije čišćeno
(van scope-a, nema trenutni negativan efekat).

## Konflikti / kontradiktorni izvori

Nema — ovo je čisto novo istraživanje/fix, prethodni izvještaj (§27 dopuna 5) je bio
eksplicitno NEDOVRŠEN i njegova hipoteza (zastarjela baza) je ovom sesijom OPOVRGNUTA
direktnim dokazom (mapping postoji od aprila) — CONTEXT.md §29 to eksplicitno navodi kao
korekciju.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | fix(tarifa): supplier filter ne isključuje zapise bez upisanog dobavljača |

## Rizici / ograničenja

- Relaksiranje filtera znači da će se sad prikazivati VIŠE prijedloga nego prije (uključujući
  neke koji ranije nisu prošli tvrd filter) — očekivano poboljšanje, ali vrijedi pratiti da
  li se pojavljuju netačni prijedlozi gdje je dobavljač GENUINELY drugačiji a slučajno nema
  upisan `supplier` (rijedak slučaj, filter i dalje isključuje POTVRĐENO drugačije dobavljače).
- Pogrešan SUSSINA→38249993 zapis (usage=2) ostaje u bazi — ne utiče trenutno, ali je
  "smeće" koje bi jednog dana moglo zbuniti drugu stavku sa niskim usage_count kontekstom.

## Potreban follow-up

- Ručni test u aplikaciji: "Provjeri" na SUSSINA stavkama treba sad predložiti 21069098.
- Razmotriti čišćenje pogrešnog `product_tariff_mapping` zapisa (SUSSINA→38249993) ako
  postane praktičan problem.
- Razmotriti rebuild `.exe`-a kad korisnik bude spreman da testira (server sada dostupan).

## Potrebna korisnička potvrda

- Da li "Provjeri" sad ispravno predlaže 21069098 za SUSSINA stavke u aplikaciji.
