## Cilj
`normalize_exporter_name()` u `services/agent/learning/exporter_xml_indexer.py`
ne strippuje pravni oblik (`DOO`/`D.O.O.`/itd.) kad ga slijedi grad —
sufiks-regex je usidren na kraj stringa (`$`). `'CMANA DOO'` → `'CMANA'`
(radi), ali `'CMANA DOO KRNJEVO'` → `'CMANA DOO KRNJEVO'` (ne radi).
Docstring funkcije već tvrdi `'KONZUM DOO BEOGRAD' → 'KONZUM'` kao
podržan slučaj — to nikad nije bilo implementirano. Ovo uzrokuje da
"Prethodna deklaracija" (i drugi callers) ne pronađu postojeći XML u
indeksu kad je izvoznikovo ime na fakturi u obliku "Firma DOO Grad", iako
je isti izvoznik u arhivi ispravno indeksiran (samo bez grada u imenu).

## Pogođeno
GitNexus `impact()`: 29 povezanih simbola, CRITICAL rizik, 5 execution
flow-ova: `reindex()`, `find_xml_for_pair()`, `find_xml_by_consignee()`,
`find_xml_for_exporter()`, agent chat (`chat_worker._build_context`,
`_build_session_zone`), `header_autofill_service.auto_fill_header_from_history`,
`xml_workflow_service.primjeni_xml_template`, `mcp_facade.find_exporter_xml_template`,
Admin Learning panel `_ReindexWorker`. Rizik je visok zbog ŠIRINE upotrebe
(dijeljen ključ za poređenje kroz više podsistema), ne zbog složenosti same
izmjene.

## Plan
1. `services/agent/learning/exporter_xml_indexer.py::normalize_exporter_name` —
   dodati regex koji uklanja pravni-oblik-sufiks PLUS opcioni grad iza njega
   (1-2 riječi, bez brojeva) na kraju stringa.
2. Identična izmjena u `dist_client/services/agent/learning/exporter_xml_indexer.py`.
3. Ponovo pokrenuti `reindex()` (isti proces kao ranije danas) da se SVI
   `exporter_normalized`/`consignee_normalized` ključevi u
   `catalogs.exporter_xml_index` preračunaju sa novom logikom — inače bi
   novo-normalizovani lookup ključevi mogli biti nekonzistentni sa starim
   uskladištenim ključevima za entitete koji imaju grad u imenu.
4. Verifikacija: `find_xml_for_pair('CMANA DOO KRNJEVO')` mora naći isti
   XML kao `find_xml_for_pair('CMANA')`; postojeći test suite
   (`test_exporter_xml_indexer.py`, `test_faktura_controller.py`) mora
   proći isto kao prije (3 poznata pre-existing neuspjeha, ne više).

## Šta NE dirati
- `HistoricalLearningServiceSafe.normalize_exporter_name` (drugačija,
  zasebna implementacija u `historical_learning_service_safe.py`) — NIJE
  ista funkcija, van scope-a ovog fixa.
- Ostala logika `find_xml_for_pair`/`reindex`/matching prioriteta — samo
  normalizacija imena se mijenja.
- Fuzzy match threshold (`FUZZY_MATCH_THRESHOLD = 0.92`) — ne dira se.

## Prihvatljiv ishod (scope lock)
Svi postojeći match-evi koji već rade (npr. `'CMANA'` → nađeno) MORAJU
ostati identični nakon izmjene. Jedina promjena ponašanja: imena oblika
"Firma DOO/D.O.O./itd. Grad" se sada normalizuju isto kao "Firma DOO" bez
grada.

## Plan verifikacije
Ručni end-to-end test u Python konzoli protiv realne baze (`find_xml_for_pair`
za CMANA sa i bez grada), pun `pytest tests/unit -q -k exporter_xml_indexer`
prije/poslije poređenje, `git diff` root vs dist_client (moraju biti
identični, isto kao ranije danas).

## Rollback / oporavak
Git revert commit-a + ponovni `reindex()` sa starom funkcijom (indeks je
izvedena/cache tabela, sigurno se ponovo gradi iz XML arhive u svakom
trenutku — nema trajnog gubitka podataka).

## Nezavisni checker
Nije korišten (LOW kompleksnost same izmjene uprkos CRITICAL blast-radius
oznaci; korisnik eksplicitno potvrdio nastavak nakon prikazanog rizika po
AGENTS.md "Handoff visokog rizika" formatu).

## Odbačene opcije
- Opcija: samo popraviti `_on_load_previous_declaration` da dodatno pokuša
  `find_xml_for_pair` sa "prvom riječi do DOO" ako pun naziv ne uspije
  (workaround na pozivnoj strani, ne u `normalize_exporter_name`).
- Zašto je razmatrana: manji blast radius (samo jedan caller).
- Zašto je odbačena: problem je generički (bilo koji caller sa "Firma DOO
  Grad" formatom pati od istog bug-a — agent chat, auto-popuna zaglavlja,
  itd.), popravka na jednom mjestu (samoj normalizaciji) rješava sve
  callere odjednom i usklađuje kod sa sopstvenim docstring-om.
- Kada odluku ponovo otvoriti: ako se pokaže da promjena normalizacije
  pravi neželjene kolizije (dva različita izvoznika se stope u isti ključ)
  — tad razmotriti uže, caller-specific rješenje.
