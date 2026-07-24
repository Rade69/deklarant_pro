# Preostali cleanup tehnickog duga

## Datum

2026-07-24

## Agent

Codex

## Scope

- Lokalni CSV backup fajlovi u `scripts/`
- `services/naimenovanja/constants.py` + `dist_client` mirror
- Re-export shim fajlovi u `services/agent/` + `dist_client` mirror
- MCP historical tools u `mcp_server/tools/` + `dist_client` mirror

## Status izvora

Nastavak liste iz `agent_reports/2026-07-23_samostalna-istraga-tehnicki-dug.md`
i prethodnog Codex paketa `agent_reports/2026-07-24_scripts-dokumentacija-arhiva.md`.
Nalazi su provjereni prije izmjena; dio se pokazao kao aktivan kompatibilni sloj,
a ne kandidat za brisanje.

## GitNexus impact

- `NaimenovanjaConstants`: LOW, direktni importi postoje ali izmjena je samo
  uklanjanje neiskoristenog `typing.Dict` importa.
- 4 mrtva shim fajla u `services/agent/`: GitNexus ih ne indeksira kao targete
  (`UNKNOWN`), pa je uradjena rucna provjera import putanja preko `rg`; rezultat:
  0 aktivnih Python importa po staroj putanji.
- MCP funkcije `search_historical_declarations`, `find_product_origin`,
  `suggest_tariff_from_history`, `suggest_preference`: LOW. Izmijenjene su samo
  prve tri; `suggest_preference` je provjerena i ostavljena netaknuta.
- `gitnexus_detect_changes(scope=staged)`: LOW, bez pogodjenih procesa.

## Sta je uradjeno

- 7 lokalnih CSV backup fajlova premjesteno iz `scripts/` u
  `database/backups/2026-07-24_scripts_csv/`. Podaci nisu obrisani; folder je
  gitignored.
- Uklonjen neiskoristen `Dict` import iz `services/naimenovanja/constants.py`
  i `dist_client/services/naimenovanja/constants.py`.
- Uklonjena 4 mrtva re-export shim para:
  - `services/agent/enhanced_tariff_suggestion_service.py`
  - `services/agent/hybrid_tariff_agent.py`
  - `services/agent/tariff_rag_service.py`
  - `services/agent/xml_template_service.py`
  - iste putanje u `dist_client/`
- Dodan `mcp_server/tools/search_helpers.py` i `dist_client` mirror sa
  `searchable_words()` helperom.
- MCP historical alati sada dijele pripremu pretraznih rijeci, bez promjene SQL
  uslova i bez uvodjenja `unaccent` zavisnosti.

## Zasto je uradjeno

`scripts/` treba da ostane folder za izvrsne skripte. Neiskoristeni importi i
mrtvi shimovi dodaju sum bez koristi. MCP alati su imali malu ponovljenu logiku
za pripremu rijeci; centralizacija smanjuje drift izmedju alata, ali zadrzava
razdvojenost MCP i GUI agent tool sistema.

## Kako je uradjeno

CSV fajlovi su premjesteni eksplicitnim putanjama u gitignored backup folder,
uz provjeru da izvori ostaju unutar `scripts/`. Shim kandidati su prvo mapirani
preko `rg`, zatim su obrisana samo 4 modula sa 0 aktivnih importa. MCP promjena
je ogranicena na helper za isti izraz `word for word in text.strip().split()`.

## Sta nije dirano

- Nisu obrisani aktivni re-export shimovi koji imaju postojece importe.
- Nije uvodjen PostgreSQL `unaccent`, jer bi to zahtijevalo provjeru/instalaciju
  extension-a na serveru.
- MCP tools nisu pretvoreni u proxy prema GUI agent tools; to su namjerno odvojeni
  interfejsi za spoljne agente i aplikacioni chat.
- `AGENTS.md` i `CLAUDE.md` generated GitNexus brojaci nisu stage-ovani.

## Verifikacija

- `python -m py_compile` za sve dirnute MCP/constants fajlove: OK.
- `python -m pytest mcp_server/tests/test_tools.py -q`: 31 passed.
- `rg` provjera za obrisane shim import putanje: nema Python pogodaka.
- `git diff --cached --check`: OK.
- Pre-commit hook: staged `.py` py_compile OK.

## Pronadjeni problemi

- Raniji nalaz je pominjao 8 CSV backup fajlova; trenutno ih je bilo 7.
- Vecina re-export shimova nije mrtva: postoje aktivni importi, posebno u root i
  `dist_client` tokovima, pa ih nije bezbjedno uklanjati u ovom prolazu.
- MCP i GUI agent tools nisu duplikat koji se moze spojiti bez vece arhitektonske
  odluke; koriste razlicite ulaze i runtime kontekst.

## Konflikti / kontradiktorni izvori

Nema konflikta. Nalaz "moguca duplikacija" tretiran je kao provjera, ne kao
nalog za spajanje sistema.

## Commitovi

| Hash | Poruka |
|---|---|
| `d7b033c` | `refactor(cleanup): smanji tehnicki dug pomocnih modula` |

## Rizici / ogranicenja

Runtime rizik je nizak: obrisani shimovi nisu imali aktivne importe, a MCP testovi
prolaze. Preostali rizik je da neki eksterni skript van repozitorija uvozi jedan
od obrisanih starih shim modula; u tom slucaju treba ga prebaciti na nove putanje
`services.agent.tariff.*` ili `services.agent.validation.*`.

## Potreban follow-up

- Za dijakritik-neosjetljivu MCP pretragu napraviti poseban plan: provjera
  PostgreSQL `unaccent` extension-a, migracija/enable korak i testovi.
- Aktivne re-export shimove uklanjati samo uz migraciju pozivalaca, ne grupno.

## Potrebna korisnicka potvrda

Nema za ovaj paket.
