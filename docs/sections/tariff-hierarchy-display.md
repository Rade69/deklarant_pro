# TariffHierarchyDisplay

## Svrha
Prikazuje hijerarhijsku strukturu carinskih tarifa kad korisnik unese
brojčani prefiks (2+ cifre) u polje Pretraga. Umjesto obične tabele,
prikazuje cijelo poglavlje sa indentacijom, ikonicama i boldiranim root-om.

Izvor podataka je SQLite baza (`deklarant_sistem.db` → `tarifa_2026`),
**ne** PostgreSQL (`catalogs.zvanicna_tarifa`).

## Zavisnosti i pretpostavke
- `database/deklarant_sistem.db` mora postojati sa tabelom `tarifa_2026`
- Tabela `tarifa_2026` ima kolone: `kod`, `naziv`, `stopa_uvozna`, `nivo`
- `nivo` može biti: `glava`, `podglava`, `tarifni_broj` (nema `podbroj` u SQLite)
- QtAwesome (`qtawesome`) je optional — fallback na emoji
- `is_code_search()` koristi regex `^\d{2,}$` za detekciju brojčane pretrage

## Pravila i granice
- Funkcija `populate_tariff_hierarchy()` popunjava QTableWidget sa 2 kolone
- Root čvor (tačan match prefiksa) je **boldiran**
- Potomci su indentirani: svake 2 cifre = 1 nivo dublje (`'  ' * (extra // 2)`)
- Maksimalno 300 potomaka (LIMIT u SQL)
- Ne mijenjati SQL upit bez razumijevanja hijerarhije tarifa
- Za tekstualnu pretragu koristi se PostgreSQL preko Service layer-a

## Zašto ovako
SQLite se koristi umjesto PostgreSQL jer `tarifa_2026` ima `nivo` kolonu
(za hijerarhiju) i `stopa_uvozna` — koje `catalogs.zvanicna_tarifa` nema.
PostgreSQL ima samo `tarifni_kod` i `opis`.
Alternativa: dodati `nivo` i `stopa_uvozna` u PostgreSQL — odbijeno jer
bi zahtijevalo migraciju 13K+ redova.
Provjera: ukucati `8516` — mora prikazati root boldiran sa potomcima.
