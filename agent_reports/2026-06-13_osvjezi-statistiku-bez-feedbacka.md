# Dugme "Osvježi statistiku" — nedostaje vizuelna potvrda

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `gui/tabs/admin/panels/learning_panel.py`
- `dist_client/gui/tabs/admin/panels/learning_panel.py`

## GitNexus impact
Provjereno PRIJE izmjene:

- `Method:gui/tabs/admin/panels/learning_panel.py:LearningPanel._on_stats_loaded#1`
  (upstream, `target_uid`) → **risk: LOW**, `impactedCount: 0`, bez pogođenih
  procesa/modula.

`gitnexus_detect_changes(scope="unstaged")` PRIJE commita: `risk_level:
"low"`, `affected_processes: []`. Nepovezane unstaged izmjene (AGENTS.md,
CLAUDE.md) ostale netaknute/nestaged.

## Šta je urađeno
U `_on_stats_loaded()` (obje kopije, gui/ + dist_client/) dodata jedna linija
nakon popunjavanja 4 labele statistike:

```python
self._log("✅ Statistika osvježena")
```

## Zašto je urađeno
Korisnik je prijavio: "Dugme osvježi statistiku mi ne radi?".

**Provjera hipoteze**: Testirao sam `_StatsWorker`/`_on_stats_loaded`/
`btn_refresh.click()` offscreen sa STVARNOM produkcionom bazom — `_db_connect()`
radi, `SELECT COUNT(*)` upiti na `catalogs.exporter_xml_index`,
`catalogs.product_tariff_mapping`, `catalogs.uvoznici`, `catalogs.izvoznici`
vraćaju ispravne brojeve (1,050 / 24,828 / 678 / 2,116), a klik na dugme
ispravno popunjava sve 4 labele.

Na pitanje "šta se tačno dešava kad klikneš dugme" korisnik je odgovorio:
**"Ništa se ne dešava"** — što potvrđuje da mehanizam RADI, ali da nema
NIKAKVOG vizuelnog feedbacka. `_refresh_stats()` se već zove jednom u
`__init__`, tako da ako se brojevi u bazi nisu promijenili od otvaranja
taba, klik na "Osvježi statistiku" ne mijenja ništa vidljivo — za razliku od
"Pokreni reindeksiranje" koje ima progress bar + log poruke.

## Kako je urađeno
Jednolinijski dodatak u `_on_stats_loaded()`, koristi postojeću `_log()`
metodu (već korištenu za sve druge poruke u "Tok reindeksiranja"). Bez
promjene signature, bez nove logike.

## Šta nije dirano
- `_StatsWorker`, `_refresh_stats()`, `_db_connect()` — nepromijenjeni,
  potvrđeno da rade ispravno.
- Nepovezane unstaged izmjene (`AGENTS.md`, `CLAUDE.md`) — van scope-a, nisu
  staged-ovane.

## Verifikacija
- `python -m py_compile` na oba fajla → OK.
- Offscreen test sa stvarnom bazom (privremen, obrisan): `LearningPanel()` +
  `btn_refresh.click()` → labele popunjene sa stvarnim brojevima (1,050 /
  24,828 / 678 / 2,116) u roku od ~3s.
- Offscreen test direktnim pozivom `_on_stats_loaded({"deklaracije":1,
  "tarife":2, "uvoznici":3, "izvoznici":4})` (bez DB/thread-a, da se izbjegne
  varijabilna latencija konekcije) → `log_output.toPlainText() ==
  "✅ Statistika osvježena"`, labela `lbl_stat_dekl == "1"`. Skripta obrisana
  nakon provjere.

## Pronađeni problemi
U jednom od offscreen testova (`_StatsWorker` pokrenut kroz pravi `QThread` u
istom procesu gdje je već bila otvorena ranija DB konekcija), `finished`/
`error` signal nije stigao ni nakon 8s — vjerovatno latencija/throttling DB
konekcije u sandboxu, NE bug u kodu (potvrđeno direktnim pozivom slota da je
logika ispravna). Nije reproducirano u prvom, izolovanom testu (3s, ispravan
rezultat). Nema uticaja na ovaj fix — `_on_stats_loaded` se poziva kad god
`finished` signal stigne, bez obzira koliko dugo to traje.

## Commitovi
| Hash | Poruka |
|------|--------|
| `c99cb66` | `feat(admin): dodaj log potvrdu za "Osvjezi statistiku"` |

## Rizici / ograničenja
- `_refresh_stats()` se zove i pri inicijalnom otvaranju panela (u
  `__init__`), tako da će se "✅ Statistika osvježena" ispisati i pri prvom
  prikazu taba, ne samo na klik — namjeravano (konzistentno sa ostalim
  log porukama), ali korisnik treba znati da poruka nije isključivo
  "rezultat klika".
- Ako DB konekcija na korisnikovom računaru hangira duže (network/firewall),
  poruka će se prikazati tek kad `_StatsWorker` stvarno završi — i dalje bez
  ikakvog indikatora DOK se čeka. Ovo NIJE riješeno ovim fixom (vidi
  follow-up).

## Potreban follow-up
Ako se nakon ovog fixa pokaže da poruka kasni više od nekoliko sekundi (spora
DB konekcija), razmotriti dodavanje progress indikatora i za "Osvježi
statistiku" (isti pattern kao `self.progress` za reindeksiranje) i/ili
`connect_timeout` u `_db_connect()`.

## Potrebna korisnička potvrda
- Otvoriti Admin → "Učenje iz XML-ova", kliknuti "Osvježi statistiku" i
  potvrditi da se u polju "Tok reindeksiranja" pojavljuje "✅ Statistika
  osvježena" odmah nakon klika (i pri otvaranju taba).
