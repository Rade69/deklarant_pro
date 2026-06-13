# Duplicirane _pair_sort_key/_is_mapping_xlsx u ProcessingWorker

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
`gui/tabs/agent/widgets/processing_worker.py` (klasa `ProcessingWorker`)

## GitNexus impact
`gitnexus_impact` na `_pair_sort_key` i `_is_mapping_xlsx`
(`Method:gui/tabs/agent/widgets/processing_worker.py:ProcessingWorker.*`):
risk = **LOW**, impactedCount = 0 (gitnexus tretira oba duplikata kao isti
simbol pa nije prijavio dodatne upstream pozivaoce van same klase).
Nakon commita pokrenut `npx gitnexus analyze` — indeks ažuriran
(39181 nodes, 61593 edges, 1033 clusters, 300 flows).

## Šta je urađeno
Uklonjen drugi (kasniji u fajlu, linije ~488-536), stariji set definicija:
- `_normalized_invoice_token`
- `_is_mapping_xlsx`
- `_pair_sort_key`

Ostao je prvi set (linije ~330-387), koji je sada AKTIVAN (jedini definisan).

## Zašto je urađeno
Klasa `ProcessingWorker` je sadržala DVA seta definicija ovih istoimenih
metoda. U Python class body-u, kasnija definicija u kodu nadjačava
(shadow-uje) raniju u namespace-u klase — pa je u runtime-u bio AKTIVAN drugi,
STARIJI set, koji je imao dva propusta u odnosu na prvi set:

1. `_is_mapping_xlsx` (drugi set) NIJE prepoznavao markere `"ptp"` i `"15467"`
   za globalne mapping Excel fajlove (Master Frigo i slični) — fajl npr.
   `15467_lista.xlsx` ne bi bio prepoznat kao mapping Excel i mogao bi biti
   procesiran kao samostalna faktura (rizik duplikata stavki, vidi pravilo o
   `consumed_paths` u CLAUDE.md).
2. `_pair_sort_key` (drugi set) NIJE koristio `_natural_invoice_parts`
   (zero-padded natural sort) — fakture poput `invoice10.pdf` su se
   sortirale PRIJE `invoice2.pdf` (leksikografski), što kvari pretpostavku
   "previous+current susjedni u sortiranoj listi" koju koristi
   `ImportService` za Excel+PDF parovanje (komentar na vrhu `run()`,
   linija ~58-60).

Korijen uzroka: cherry-pick commit `4f0136ab2` (veliki dev-branch refactor,
26.04, primijenjen na windows granu) je donio cijeli blok novih metoda
(`_apply_excel_financials`, `_postprocess_master_frigo_pairs`, itd.) iz dev
grane — ali taj blok je sa sobom nosio i STARIJU verziju
`_normalized_invoice_token`/`_is_mapping_xlsx`/`_pair_sort_key` (iz prije
commita `5a32f2127` koji je dodao "ptp"/"15467" i natural sort). Rezultat:
duplikacija, sa starijom verzijom "na dnu" (pa aktivnom).

`dist_client/gui/tabs/agent/widgets/processing_worker.py` NIKAD nije imao ovu
duplikaciju (samo prvi/ispravan set) — služio je kao referentna "čista"
verzija za potvrdu koja je tačna.

## Kako je urađeno
- `git log -p -L 330,536:gui/tabs/agent/widgets/processing_worker.py` —
  rekonstruisana historija: `0149de9c` (initial), `5a32f2127` (natural sort
  fix + ptp/15467), `4f0136ab2` (cherry-pick donio duplikat), `b7423ee8`
  (mojibake fix, duplikat nije dirao).
- Pročitan `dist_client/` mirror — potvrđeno da nema duplikacije i da se
  poklapa sa PRVIM setom u root `gui/` kopiji.
- `Edit` — obrisan drugi (stariji) set definicija (linije ~488-536),
  jedan blok edit, bez izmjene prvog seta.

## Šta nije dirano
- `dist_client/gui/tabs/agent/widgets/processing_worker.py` — već čist, nema
  duplikacije, nije mijenjan.
- Ostale nestaging-ovane WIP izmjene u repou (display_profile/FlowLayout rad
  na `AGENTS.md`, `gui/main_window.py`, `dist_client/gui/main_window.py`,
  `gui/tabs/faktura_view.py`, `dist_client/gui/tabs/faktura_view.py`,
  `gui/utils/display_profile.py`, `styles/display_profiles.qss`,
  `tests/unit/test_display_profile.py`) — nepovezano sa ovim zadatkom,
  ostavljeno netaknuto i nekomitovano.

## Verifikacija
- `python -m py_compile gui/tabs/agent/widgets/processing_worker.py` → OK.
- Offscreen poziv direktno na klasi:
  - `ProcessingWorker._is_mapping_xlsx('PTP_export.xlsx')` → `True`
  - `ProcessingWorker._is_mapping_xlsx('15467_lista.xlsx')` → `True`
  - `ProcessingWorker._is_mapping_xlsx('tarife.xlsx')` → `True`
  - `sorted([invoice10.pdf, invoice2.pdf], key=ProcessingWorker._pair_sort_key)`
    → `[invoice2.pdf, invoice10.pdf]` (natural sort potvrđen)
- `gitnexus_detect_changes()` — pokazao samo nepovezane (pre-postojeće) WIP
  promjene u main_window.py/faktura_view.py; nije prijavio regresiju vezanu
  za ovu izmjenu.

## Pronađeni problemi
- `gitnexus_impact` na obje metode vratio `impactedCount: 0` / risk LOW —
  vjerovatno jer gitnexus deduplicira simbole po imenu+klasi (jedan node za
  oba duplikata), pa nije mogao precizno prikazati stvarne pozivaoce
  (`run()` linija 61, 85). Stvarna upotreba potvrđena grep-om i offscreen
  testom — nije bio lažni negativ koji bi promijenio odluku (LOW risk i dalje
  tačan, fix je lokalni i izolovan).

## Commitovi
| Hash | Poruka |
|------|--------|
| `98a101b` | fix(agent): ukloni duplirane _pair_sort_key/_is_mapping_xlsx definicije |

## Rizici / ograničenja
- Promjena ponašanja je STVARNA (ne samo cleanup): `_is_mapping_xlsx` sada
  prepoznaje više fajlova kao "mapping Excel" (ptp/15467), a `_pair_sort_key`
  mijenja redoslijed sortiranja fajlova s brojevima u imenu. Ovo je
  RESTAURACIJA namjeravanog ponašanja (poklapa se sa `dist_client/` i sa
  commitom `5a32f2127`), ali nije testirano sa stvarnim batch-om fajlova kroz
  GUI agent tab.

## Potreban follow-up
- Nema poznatog — fix je izolovan i usaglašen sa već-ispravnom dist_client
  kopijom.

## Potrebna korisnička potvrda
- Preporučeno: pri sljedećem batch-uvozu kroz "Pametna pomoć" agent tab,
  provjeriti da fajlovi s "ptp"/"15467" u imenu (mapping Excel) NE ulaze kao
  samostalne fakture, i da se fakture s brojevima (npr. invoice2/invoice10)
  sortiraju u prirodnom (numeričkom) redoslijedu.
