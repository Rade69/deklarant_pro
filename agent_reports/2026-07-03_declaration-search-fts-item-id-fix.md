# Ispravka pogrešnog item_id u FTS indeksu istorijskih deklaracija

**Datum:** 2026-07-03
**Grana:** windows
**Zadatak:** Istraga 2 test failure-a otkrivena tokom oporavka test suite-a (vidi [2026-07-03_test-suite-oporavak-i-zaglavlje-bugfix.md](2026-07-03_test-suite-oporavak-i-zaglavlje-bugfix.md))

---

## Šta je urađeno

Ispravljen pravi bug u `DeclarationSearchService` (`services/agent/chat/declaration_search_service.py`) — pretraga istorijskih deklaracija je za deklaracije sa 2+ stavke mogla vratiti podatke (zemlju porijekla, tarifni broj) koji pripadaju **pogrešnoj stavci** iz iste fakture, ili robu uopšte ne pronaći.

## Kako je urađeno

Prilikom prve verifikacije test suite-a, 2 testa u `test_declaration_search_service.py` su padala. Površna dijagnoza (fixture zavisnost, environment) bi bila pogrešna — standalone reprodukcija sa 1 stavkom je uvijek prolazila, što je zamaskiralo problem. Ponovljeno sa 2 stavke po deklaraciji (tačan fixture iz testa) — pouzdano je pucalo i van pytest-a, čime je potvrđeno da je uzrok u kodu, ne u test okruženju.

**Uzrok** (`_flush_batch`, [declaration_search_service.py:377](../services/agent/chat/declaration_search_service.py#L377)):
```python
cur.executemany("INSERT INTO items ...", [...])
last_id = cur.lastrowid          # ne radi ono što kod pretpostavlja
first_id = last_id - len(items) + 1
```
`sqlite3.Cursor.lastrowid` se **ne ažurira nakon `executemany()`** — zadržava vrijednost od prethodnog pojedinačnog `execute()` (INSERT deklaracije). Sa 1 item-om aritmetika slučajno ispadne tačna; sa 2+ item-a izračunati `item_id` u `items_fts` je pomjeren u odnosu na stvarne ID-jeve u `items` tabeli. Posljedica: JOIN između `items_fts` i `items` spaja pogrešne redove — pretraga po opisu robe A vraća metapodatke (zemlja porijekla, tarifa) robe B iz iste deklaracije, ili ništa ne vrati.

**Ispravka:** umjesto računanja `item_id` iz `lastrowid`, ID-jevi upravo upisanih stavki se dohvataju direktnim upitom (`SELECT id FROM items WHERE decl_id = ? ORDER BY id`), oslanjajući se na AUTOINCREMENT monotoni redoslijed unutar iste transakcije.

Verifikacija:
- `gitnexus_impact` na `_flush_batch` (upstream) → risk **LOW**, 7 pogođenih simbola, svi interni pozivaoci istog servisa (`search_by_goods`, `search_by_tariff`, `search_by_partner`, `search_by_country`, `get_stats`) — svi profitiraju od ispravke jer dijele isti indeks.
- Test suite: 551 prošlo, 0 palo, 41 preskočeno (bilo 549 prošlo / 2 pala prije ove ispravke).
- `gitnexus_detect_changes` nakon commita → LOW risk, 0 affected processes.

## Zašto

`DeclarationSearchService` hrani AI chat funkciju "šta smo ranije carinili za sličnu robu" — koristi se za predlaganje zemlje porijekla i tarifnog broja na osnovu istorijskih deklaracija. Netačan rezultat (kriva zemlja porijekla ili tarifa za sličan proizvod) direktno utiče na obračun carine i povlastica ako korisnik prihvati pogrešan prijedlog. Ovo je bio tihi bug — nije bacao izuzetak, samo vraćao pogrešne ili prazne rezultate, pa se ne bi lako primijetio bez testova sa više stavki po deklaraciji.

## Commitovi

| Hash | Poruka |
|------|--------|
| `359b428` | fix(agent): ispravi pogresan item_id u FTS indeksu istorijskih deklaracija |

## Napomena o GitNexus indeksu

Prilikom ove sesije index je zatečen zastario (`risk: critical` na potpuno nepovezane fajlove). Pokrenut `npx gitnexus analyze` prije i poslije ovog commita da bi `impact`/`detect_changes` davali tačne rezultate. Ubuduće provjeriti svježinu indeksa prije oslanjanja na njegove nalaze.
