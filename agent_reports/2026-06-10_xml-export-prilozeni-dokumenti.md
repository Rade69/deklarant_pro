# XML export - prilozeni dokumenti i EXE build

## Kontekst

Korisnik je prijavio da export XML-a iz instalirane/buildovane Windows aplikacije javlja
genericku poruku "Greska pri eksportu". Istovremeno je potvrdjeno da je Claude kreirao
`dist\DeklarantPro\DeklarantPro.exe` i `.env` pored EXE-a sa `DB_HOST=192.168.100.154`.

## Sta je provjereno

- Provjereno je da frozen build po `config/settings.py` cita `.env` iz foldera pored EXE-a.
- Provjereno je da postoje dvije runtime kopije XML buildera:
  - `exporters/asycuda_xml_builder.py`
  - `dist_client/exporters/asycuda_xml_builder.py`
- GUI export u Zaglavlje tabu ide preko `exporters.asycuda_xml_builder.export_to_xml`.
- `export_to_xml()` hvata sve izuzetke i vraca `False`, zbog cega GUI prikazuje samo
  genericku poruku bez stvarnog traceback-a.

## Ključna odluka

Problem je tretiran defanzivno u XML builderu, a ne u GUI sloju. Razlog je sto
`header_attached_documents` i `item.attached_documents` mogu doci iz vise tokova:
Zaglavlje tab, Naimenovanja tab, import pipeline, agent workflow i historijski reload.
U tim tokovima dokumenti mogu biti `AttachedDocument` objekti, ali i dict strukture.

Zato je uvedena normalizacija dokumenata prije pristupa poljima `code`, `number`,
`name` i `from_rule`.

## Izmjene

- U `exporters/asycuda_xml_builder.py` i `dist_client/exporters/asycuda_xml_builder.py`
  dodani su helperi:
  - `_doc_value()`
  - `_doc_bool()`
  - `_normalize_attached_document()`
- `_record_export_warnings()` sada normalizuje dokumente prije provjere reference.
- `_add_items()` normalizuje header dokumente prije sortiranja po `from_rule`.
- `_add_single_item()` normalizuje item-level dokumente prije dodavanja u XML.
- `_add_attached_doc()` dodatno stiti ulaz i preskace nevalidan dokument.
- Auto-ucenje istorije dokumenata u `export_to_xml()` takodje koristi normalizovane dokumente.
- Dodan je regresioni test u `tests/unit/test_asycuda_goods_description.py` za slucaj kada
  `header_attached_documents` dodje kao dict.

## Verifikacija

- `py_compile` je prosao za obje kopije XML buildera.
- `py_compile` je prosao za izmijenjeni test fajl.
- Direktni smoke test iz root runtime-a je potvrdio da dict dokument izvozi `N380` i `from_rule=1`.
- Direktni smoke test iz `dist_client` runtime-a je potvrdio da `export_to_xml()` vraca `True`
  i generise XML fajl.
- `pytest` nije pokrenut jer `dist_client\.venv` nema instaliran `pytest`.

## Napomena za EXE

Ova promjena popravlja izvorni kod i `dist_client` runtime, ali vec buildovani
`dist\DeklarantPro\DeklarantPro.exe` ne moze automatski dobiti ovu izmjenu.
Za EXE varijantu potreban je novi build poslije ovog commita.
