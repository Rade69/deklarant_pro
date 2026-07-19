# Agent Report — 2026-07-19: Tačan product_code match ne čeka usage_count>=3

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- `services/decision/evidence_adapters.py` + `dist_client/` mirror
- `tests/unit/test_evidence_adapters_tariff.py` (nov fajl)
- `docs/CONTEXT.md` (§16, nova sekcija)

---

## Status izvora

- `agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md` — Pi/Codex
  zadatak, status "IMPLEMENTIRANO — čeka Codex verifikaciju" u trenutku pisanja
  ovog izvještaja. Ovaj fix je bug unutar njihovog novog koda (Faza 3), ne
  konflikt sa njim — tretiran kao aktivan izvor.
- `agent_reports/2026-07-18_zavrsni-jedan-izvor-istine.md` — Pi-jev završni
  izvještaj, aktivan, korišten za razumijevanje arhitekture prije izmjene.
- Nije pronađen poseban Codex verifikacioni izvještaj (provjereno u prethodnoj
  konverzaciji) — nije korišćen kao izvor jer ne postoji.

---

## GitNexus impact

**GitNexus MCP alat je vraćao "not found" i za osnovne, davno postojeće simbole**
(npr. `TariffMappingService`) uprkos ranije prijavljenom "uspješnom" indeksiranju
— vidi `docs/CONTEXT.md` §16 za detalje. `gitnexus_detect_changes()` nakon commita
je prijavio `changed_files: 2, changed_symbols: [], risk_level: "low"` — ne
prepoznaje simbole unutar izmijenjenih fajlova.

Zbog toga je urađena **ručna (grep-based) impact analiza** kao kompenzacija:
- `adapt_tariff_evidence` — pozivaoci: `declaration_decision_service.py:127`
  (root + dist_client, isti fajl) i spomen u docstringu jednog testa. Nijedan
  test ne poziva funkciju direktno (potvrđeno grep-om) — sigurno za izmjenu.
- Riziк procijenjen: **LOW** — izolovana funkcija, 2 poznata pozivaoca (root/
  dist_client isti kod), bez postojećih testova koji pinuju staro ponašanje.

---

## Šta je urađeno

U `adapt_tariff_evidence()` (i root i dist_client kopija, identične):

- Uklonjen `is_same_exporter` uslov koji je poredio ime izvoznika sa
  `mapping.naziv_robe` (naziv proizvoda — pogrešno polje).
- Zamijenjen uslovom `mapping.similarity >= 0.99` — `find_mapping()` vraća
  `similarity=1.0` isključivo za tačan `product_code` match.
- Gate je sad: `is_exact_code_match or mapping.usage_count >= 3` (ranije:
  `is_same_exporter or mapping.usage_count >= 3`, gdje je `is_same_exporter`
  praktično uvijek bio `False`).
- Score za tačan match: `min(95, 80 + usage_count*3)` — usage_count=1 daje 83,
  usage_count=2 daje 86 (prelazi prag za auto-apply 85 iz `decision_policy.py`).
- Source za tačan match promijenjen na `DecisionSource.TARIFF_DATABASE` (bilo
  `EXPORTER_HISTORY`, semantički netačno jer se izvoznik više ne provjerava).

---

## Zašto je urađeno

Korisnički scenario: desni klik "Promijeni tarifni broj" u Faktura tabu poziva
`TariffMappingService.correct_mapping()`, koja upisuje ispravku sa
`usage_count=1`. Na sljedećem uvozu iste robe, `adapt_tariff_evidence()` je tu
ispravku filtrirala jer `usage_count=1 < 3`, a `is_same_exporter` gate nikad
nije prolazio (poredio je pogrešna polja). Rezultat: "provjeri" nije ponudila
ispravku kao kandidat — tačno simptom koji je korisnik prijavio.

`find_mapping()` već razlikuje tačan match (`similarity=1.0`, grana 1 — direktan
`product_code` lookup) od fuzzy/majority-vote matcheva (`similarity<1.0`) — ovo
polje je pouzdaniji signal za "da li vjerovati odmah" nego `usage_count`, koji
ima smisla samo za fuzzy/naučene obrasce (ponovljena potvrda gradi povjerenje).

---

## Kako je urađeno

- Analiza `find_mapping()` (`services/tariff/tariff_mapping_service.py:409-433`)
  potvrdila da `similarity=1.0` dolazi isključivo iz grane tačnog match-a.
- Test protiv prave PostgreSQL baze (`correct_mapping()` end-to-end) potvrdio da
  VARCHAR(10) fix (prethodni commit) radi — `correct_mapping` više ne pada.
- Izmjena ograničena na `evidence_adapters.py` jer je to obična `.py` datoteka —
  **NE** kompajlirana u `dist_client`, za razliku od `tariff_mapping_service.py`
  koji je Nuitka `.pyd` (`dist_client/services/tariff_mapping_service.cp314-win_amd64.pyd`).
  Izmjena kompajliranog fajla bi zahtijevala pun rebuild koji nije bezbjedno
  izvesti unutar ove sesije (nema potvrđenog build okruženja/kompajlera).

---

## Šta nije dirano

- `TariffMapping` dataclass i `find_mapping()`/`correct_mapping()` u
  `services/tariff/tariff_mapping_service.py` — namjerno netaknuto (vidi gore,
  zahtijeva .pyd rebuild). Prava popravka `is_same_exporter` (dodavanje
  `supplier` polja) ostaje kao follow-up.
- `auto_populate_tariffs()` skip-existing-tariff ponašanje (linija ~199) —
  namjerno po dizajnu nove Faza 3 politike (Document > DB za tarifu), već
  označeno DEPRECATED komentarom od strane Pi tima — nije moj scope da to
  arhitekturno mijenjam.
- Sav ostali kod iz Pi/Codex migracije (Faze 0-6) — netaknut.

---

## Verifikacija

```
python -m py_compile services/decision/evidence_adapters.py dist_client/services/decision/evidence_adapters.py tests/unit/test_evidence_adapters_tariff.py
→ OK

python -m pytest tests/unit/test_evidence_adapters_tariff.py -v
→ 3 passed (novi testovi za ovaj fix)

python -m pytest tests/unit/test_evidence_model.py tests/unit/test_agent_decision_regression.py \
    tests/unit/test_decision_characterization.py tests/unit/test_declaration_decision_model.py \
    tests/unit/test_declaration_decision_service.py tests/unit/test_decision_tariff_policy.py \
    tests/unit/test_decision_origin_policy.py tests/unit/test_decision_preference_policy.py \
    tests/unit/test_decision_controlled_learning.py tests/integration/test_decision_draft_roundtrip.py \
    tests/integration/test_decision_to_naimenovanja.py tests/integration/test_decision_xml_preflight.py \
    tests/integration/test_manual_agent_decision_parity.py -q
→ 197 passed, 5 xfailed (identično Pi-jevom baseline-u — bez regresije)

diff services/decision/evidence_adapters.py dist_client/services/decision/evidence_adapters.py
→ identične (exit 0)
```

Dodatna live-DB verifikacija (protiv `192.168.0.25`, sintetički `product_code`
obrisan nakon testa): `correct_mapping()` s dugačkom `zemlja_porijekla` (19
znakova) uspješno upisuje ispravku bez VARCHAR(10) greške — potvrđuje da
prethodni fix (migracija 008 + defanzivna truncacija) radi u produkciji.

---

## Pronađeni problemi

- GitNexus MCP index degradiran za `deklarant_pro` repo — ne prepoznaje ni
  osnovne simbole. Zahtijeva istragu van scope-a ovog zadatka (vidi CONTEXT.md
  §16).
- `TariffMapping` dataclass nema `supplier` polje iako DB kolona postoji —
  strukturni gap koji čini pravu `is_same_exporter` provjeru nemogućom bez
  dodatne izmjene + .pyd rebuild.

---

## Konflikti / kontradiktorni izvori

Nema — ovo je bug fix unutar koda koji je Pi tim upravo uveo (Faza 3), nema
suprotstavljenih ranijih odluka. Korisnik je eksplicitno zatražio da se
pronađeni problem ispravi ("Ispravi sve što misliš da treba da se uradi").

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `556b7a5` | fix(decision): tacan product_code match ne cekas usage_count>=3 |

---

## Rizici / ograničenja

- Score formula za tačan match (`80 + usage_count*3`) je nova procjena, ne
  arhitekturna odluka Pi/Codex tima — ako Codex verifikacija ima drugačiji
  očekivani prag, treba uskladiti.
- `DecisionSource.TARIFF_DATABASE` label za ovaj slučaj nije prethodno
  korišten u `adapt_tariff_evidence` — provjeriti da UI prikaz izvora (ako
  postoji tekst po `DecisionSource` vrijednosti) ima smislen prikaz za ovaj
  source u kombinaciji sa tarifom.

---

## Potreban follow-up

1. Dodati `supplier` polje u `TariffMapping` + `find_mapping()` SELECT, zatim
   ispraviti pravu `is_same_exporter` logiku — zahtijeva `.pyd` rebuild
   (`scripts/build_distribution.bat` ili ciljani Nuitka `--module` compile).
2. Istražiti zašto GitNexus index ne prepoznaje osnovne simbole unatoč
   "uspješnom" `npx gitnexus analyze`.
3. Codex nezavisna verifikacija cijele Faze 0-6 migracije (i dalje nije
   pronađena u repou).

---

## Potrebna korisnička potvrda

- Testirati u realnom scenariju: desni klik → ispravi tarifu → ponovo uvezi
  istu fakturu → "Provjeri" bi sada trebalo da ponudi ispravljenu tarifu kao
  kandidat (ne automatski primijenjenu — i dalje treba potvrda jer je score<85
  pri usage_count=1).
