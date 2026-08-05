## Datum
2026-08-05

## Agent
Claude Code (Sonnet 5)

## Scope
`services/agent/chat/draft_aggregation_service.py`, `gui/tabs/agent/services/chat_intent_handler.py`,
`tests/unit/test_draft_aggregation_service.py`, `tests/test_tool_use.py` (gitignored) + dist_client kopije.

## Reprodukcija prije izmjene
Korisnik testirao novi `agregiraj_stavke` alat u stvarnom Agent chatu (nakon
`agent_reports/2026-08-05_agent-agregacija-filtriranje-stavki.md`):
- Upit "koja je ukupna vrijednost stavki sa tarifom 21069098" → odgovor
  "🧮 SUM — vrijednost (naimenovanja): 2261.480 (2 stavki)" — bez navođenja KOJE su to
  stavke.
- Upit "koja stavka ima najveću bruto masu" → odgovor je ISPRAVNO naveo "Rb.9: VITIX gel
  50ml — 118.600" (MAX/MIN grana je već imala listu preko `top_n` mehanizma).

Asimetrija potvrđena čitanjem koda: `agregiraj()` je za `max`/`min` vraćao `"top"` listu, ali
za `sum`/`avg` samo skalarni `"rezultat"` — `_agregiraj_stavke()` formatter je za sum/avg
prikazivao samo broj.

## GitNexus impact
Iste funkcije kao prethodni zadatak istog dana (`_agregiraj_stavke` u
`chat_intent_handler.py`) — već potvrđeno LOW risk, aditivna izmjena (dodat `"stavke"` ključ
u return dict, dodata petlja u formatteru). Nema promjene potpisa funkcija niti pozivalaca.

## Šta je urađeno
1. `agregiraj()` u `draft_aggregation_service.py` — za `sum`/`avg` granu dodat
   `"stavke": [{"row": row, "vrijednost": v} for row, v in parovi]` u povratni dict (isti
   oblik kao `"top"` za max/min, samo bez ograničenja na top_n).
2. `_agregiraj_stavke()` u `chat_intent_handler.py` — nakon prikaza SUM/AVG rezultata, dodata
   ista petlja za listanje stavki kao kod MAX/MIN grane (Rb./red + naziv + vrijednost po
   stavci), ograničeno na 20 sa "... i još N" sufiksom (isti obrazac kao `pretrazi_stavke`/
   `filtriraj_stavke`).
3. Postojeći test `test_agregiraj_sum_sa_filterom_po_tarifi` proširen asercijom da
   `rezultat["stavke"]` sadrži tačne `ordinal_no` vrijednosti.
4. Postojeći dispatch test `test_agregiraj_stavke_dispatch_sum_sa_filterom` proširen
   asercijom da poruka sadrži "Rb.1" i "Rb.2".
5. `py_compile` OK, ciljani testovi OK, puna `pytest tests/ -q -k "not test_db"
   --ignore=tests/test_origin_intent_routing.py` — 1696 passed, isti pre-postojeći 2 fail-a,
   bez regresije.
6. dist_client sync (CRLF očuvan).
7. `gitnexus_detect_changes` — risk low, `affected_count: 0`. Napomena: Crush u istom
   working tree-u paralelno mijenja `gui/tabs/admin/panels/*.py` (analytics_panel,
   database_panel, learning_panel, plugin_panel) — te izmjene NISU staged niti commitovane
   ovim zadatkom (nisu moje, van scope-a).
8. Commit `0f43f5c`.

## Zašto je urađeno
Korisnik je direktno testirao alat u produkcijskom chatu i prijavio nedostatak — SUM/AVG bez
liste stavki je manje korisno od MAX/MIN sa listom, i nekonzistentno u istom alatu.

## Kako je urađeno
Minimalna izmjena — jedan novi ključ u servisnom povratnom dict-u, jedna kopirana/prilagođena
petlja za formatiranje (isti stil kao već postojeća MAX/MIN i `pretrazi_stavke`/
`filtriraj_stavke` petlje).

## Šta nije dirano
`filtriraj_stavke` (već je imao listu stavki od početka), `count` grana (namjerno ostaje
samo broj — nema smisla nabrajati stavke za COUNT bez agregirane vrijednosti po stavci).

## Verifikacija
`py_compile` OK. Testovi ažurirani da PROVJERE ispravku (ne samo da ne padnu) — asercija na
"Rb.1"/"Rb.2" bi pukla na staroj implementaciji. Puna test suita bez regresije.

## Nezavisna provjera
- Checker korišćen: NE.
- Razlog: trivijalna, aditivna formatting izmjena istog obrasca koji već postoji u istom
  fajlu (MAX/MIN grana), pokrivena testom koji direktno reprodukuje korisnikov nalaz.

## Pronađeni problemi
Nema novih.

## Odbačene opcije
Nema — jasan, uzak fix.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `0f43f5c` | `fix(agent): agregiraj_stavke SUM/AVG prikazuje listu stavki, ne samo broj` |

## Rizici / ograničenja
Za veliki broj stavki (>20) lista se skraćuje — konzistentno sa ostalim alatima, ali ako
korisnik zatraži SUM preko stotina stavki, dobiće samo prvih 20 + broj ostatka, ne punu
listu. Prihvatljivo za chat format (previše dugo inače).

## Potreban follow-up
Nastaviti sa preostalim follow-up iz `agent_reports/2026-08-05_agent-agregacija-filtriranje-stavki.md`
(testiranje preostalih upita iz `AGENT_TOOL_COVERAGE_AUDIT.md`).

## Potrebna korisnička potvrda
Ponoviti isti upit ("koja je ukupna vrijednost stavki sa tarifom 21069098") u chatu i
potvrditi da sada prikazuje i listu naimenovanja.
