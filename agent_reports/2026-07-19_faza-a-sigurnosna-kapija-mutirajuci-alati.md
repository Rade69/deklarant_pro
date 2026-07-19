# Agent Report — 2026-07-19: Faza A — sigurnosna kapija za mutirajuće alate

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- `services/agent/chat/tool_policy.py` (nov fajl) + dist_client mirror
- `gui/tabs/agent/services/chat_intent_handler.py` + dist_client mirror
- `gui/tabs/agent/agent_controller.py` + dist_client mirror
- `tests/unit/test_tool_policy.py`, `tests/unit/test_agent_mutation_gate.py` (novi, tracked)
- `tests/test_tool_use_offline.py` (izmijenjen, **netracen** — vidi "Konflikti/napomene")

Realizovana je **Faza A** iz `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md`
(dograđen 2026-07-19 ranije u istoj sesiji). Faze B–F **nisu** rađene — korisnik je
eksplicitno tražio samo Fazu A, pa stop za pregled.

---

## Status izvora

- `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` §5 — glavni izvor, uključujući
  moje ranije dograđene §5.1/§5.2/§5.6 (veza sa Decision Service). Aktivan, korišten kao
  jedini plan za ovu fazu.
- `agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md` +
  `agent_reports/2026-07-18_zavrsni-jedan-izvor-istine.md` — Decision Service migracija,
  aktivna, direktno integrisana (vidi ispod).

---

## GitNexus impact

`gitnexus_impact` je ovaj put vratio **smislene rezultate** (ranija degradacija iz
`docs/CONTEXT.md` §16 se čini otklonjena nakon nekoliko `npx gitnexus analyze` ciklusa
tokom sesije — vrijedi ponovo provjeriti u budućnosti da li je trajno popravljeno):

| Simbol | Rizik | Direktni pozivaoci |
|--------|-------|---------------------|
| `_execute_tool` | LOW | `_on_tool_call`, `ChatIntentHandler.execute_tool` |
| `AgentController._upisi_u_kolonu` | LOW | 0 (samo interni pozivaoci u istom fajlu — regex fallback) |
| `_on_proposal_confirmed` (free function) | LOW | `ChatIntentHandler.on_proposal_confirmed` |

`gitnexus_detect_changes()` prije zadnjeg commita: `risk_level: low`, `affected_count: 0`,
6 fajlova promijenjeno (uklj. `AGENTS.md`/`CLAUDE.md` auto-brojevi simbola).

---

## Šta je urađeno

### 1. `services/agent/chat/tool_policy.py` (commit `073f334`)

`ToolEffect` enum (`READ_ONLY`/`PROPOSE`/`MUTATE`) + eksplicitan whitelist registry za
svih 12 agent alata iz `tool_definitions.py`. `effect_for(name)` vraća `None` za nepoznat
alat — fail-closed po definiciji, ne po nagađanju.

Klasifikacija (verifikovana čitanjem stvarnog ponašanja svakog alata):

| Alat | Efekat | Zašto |
|------|--------|-------|
| `pregled_stanja_aplikacije`, `provjeri_tarife`, `pretrazi_tarifu`, `pretrazi_porijeklo`, `validuj_deklaraciju`, `prikazi_naimenovanja`, `provjeri_naimenovanja`, `analiziraj_tarifne`, `pronadji_slicne_proizvode` | READ_ONLY | Čisto čitanje/prikaz, bez upisa u draft |
| `predlozi_tarife`, `spoji_naimenovanja` | PROPOSE | Već koriste postojeći `_pending_action` mehanizam (`agent_controller.py:794-801`) — grade prijedlog, stvarna primjena čeka posebnu potvrdu |
| `upisi_u_kolonu` | MUTATE | Jedini alat koji je (prije ove izmjene) direktno pisao u draft |

### 2. Sigurnosna kapija u `chat_intent_handler.py` (commit `5813a1b`)

- `_execute_tool()` sad ima gate na samom ulazu: `if effect_for(name) is None: ... return`
  prije ijedne `if/elif` grane — sprječava da nepoznato ime alata slučajno pogodi neku granu.
- Nova `_propose_kolona_upis(ctrl, atribut, vrijednost, tab)` — gradi `proposal` dict u
  formatu koji **već postoji** (`ProposalCardWidget` docstring,
  `gui/tabs/agent/widgets/proposal_card.py`) i poziva `_show_proposal_card()`. **Nije
  napravljen nov mehanizam potvrde** — `show_proposal_card`/`_on_proposal_confirmed`/
  `_on_proposal_rejected` su postojali u kodu od ranije, ali nisu imali nijednog stvarnog
  pozivaoca (provjereno grep-om) — samo formalizovano i wired.
- `_on_proposal_confirmed()` više ne hardkoduje `tab='faktura'` (bio bi tih bug za upis u
  `naim` tab preko iste kartice) — čita `ctrl._pending_kolona_tab`, postavljen od strane
  `_propose_kolona_upis` i očišćen odmah nakon upotrebe (i na confirm i na reject).
- `agent_controller._upisi_u_kolonu` (pozivan iz regex fallback puta,
  `_handle_message_regex_fallback`) sad delegira na
  `chat_intent_svc.propose_kolona_upis(...)` umjesto na `naim_intent_svc.execute(...)`
  direktno — **isti gate za oba ulazna puta** (Tool Use i regex fallback), bez duplog koda.

### 3. Decision Service integracija (dio istog commita `5813a1b`)

Za `tarifni_broj`/`zemlja_porijekla`/`povlastica` (mapirano na `DecisionField.TARIFF`/
`ORIGIN_COUNTRY`/`PREFERENCE`), potvrđen upis sad poziva
`sync_decision_state_after_manual_edit(line, field, value)` po liniji u
`draft.invoice_lines` — isti mehanizam koji `_apply_single_tariff_to_line` već koristi za
ručnu izmjenu ćelije u Faktura tabu (Faza 4.2 Decision Service migracije). Prazna vrijednost
(brisanje) se **ne** sinhronizuje — nema "obriši odluku" koncepta u
`DeclarationDecisionService`, i sinhronizacija prazne vrijednosti kao "potvrđena vrijednost"
ne bi imala smisla.

Ovo direktno adresira glavni nalaz iz dograđenog plana (§5.1/§5.6): bez ove integracije,
`upisi_u_kolonu` bi postao **treći paralelan upisni put** mimo `DeclarationDecisionService`,
tačno onaj obrazac koji je dograđeni plan upozoravao da se izbjegne.

---

## Zašto je urađeno

Plan (Faza A) i moj raniji nalaz (§5.6) su pokazali da `upisi_u_kolonu` — jedini agent alat
koji direktno mijenja draft — nije imao nikakvu potvrdu: poruka poput "upiši zemlju
porijekla RS" bi odmah promijenila **sve stavke** u Faktura tabu prije nego korisnik vidi
ili odobri promjenu. Cilj je bio zatvoriti tu rupu koristeći **postojeću** infrastrukturu
(proposal kartica, Decision Service) umjesto pisanja paralelnih mehanizama.

---

## Kako je urađeno

Detaljno opisano u "Šta je urađeno" gore. Ključna arhitektonska odluka: umjesto da
`upisi_u_kolonu` dobije SVOJ NOVI proposal/confirm mehanizam (kako bi se moglo pogrešno
protumačiti iz plana), otkrio sam da `show_proposal_card`/`_on_proposal_confirmed` **već
postoje u kodu bez pozivaoca** — samo sam ih povezao. Ovo je značajno manji i sigurniji
zahvat od pisanja novog `draft_mutation_handler.py` modula (koji je plan predložio kao
"po potrebi") — procijenio sam da nije potreban jer postojeći mehanizam već tačno
odgovara potrebnom obliku (`{atribut: vrijednost}` dict, editable polja, potvrdi/odbaci
dugmad).

---

## Šta nije dirano

- Faze B–F plana (LLM provider unifikacija, pipeline pouzdanost, observability,
  integracioni testovi, razlaganje `chat_intent_handler.py`) — eksplicitno van scope-a
  ovog prolaza, korisnik je tražio samo Fazu A.
- `predlozi_tarife`/`spoji_naimenovanja` (`_pending_action` mehanizam) — već su PROPOSE
  po ponašanju, nisu dirani, samo formalno klasifikovani u registry.
- `_izvrsi_spajanje_naimenovanja`, `_provjeri_naimenovanja`, `_has_origin_keyword`,
  `_start_chat_worker`, `_on_proposal_rejected` — GitNexus ih je prijavio kao "touched" u
  `detect_changes`, ali to je isključivo posljedica pomjeranja linija zbog dodatog koda
  iznad njih u istom fajlu — logika nepromijenjena (verifikovano čitanjem diff-a).
- `operation_id`/potpuna idempotencija dvostruke potvrde — vidi "Pronađeni problemi".

---

## Verifikacija

```
python -m pytest tests/unit/test_tool_policy.py tests/unit/test_agent_mutation_gate.py -v
→ 9 passed, 1 xfailed (dokumentovan poznat gap)

python -m pytest tests/test_tool_use_offline.py -v   (netracen fajl, lokalna provjera)
→ 40 passed, 1 xfailed

python -m pytest tests/ -q   (pun postojeći suite)
→ 798 passed, 58 skipped, 6 xfailed, 4 failed, 1 error

python -m py_compile <svi izmijenjeni/novi fajlovi + dist_client mirrors> → OK

diff <root> <dist_client> za sva 3 izmijenjena/nova fajla → IDENTIČNI
```

4 fail + 1 error u punom `tests/` runu su **pretpostojeći, nepovezani** sa ovom izmjenom
(potvrđeno `git log` — nijedan od ta 4 fajla nije mijenjan danas):
- `test_pdf_plumber_only.py::test_tabula_not_in_smart_pdf` — Unicode greška, nepovezano
- `test_xml_parser_fix.py::test_xml_parser` — hardkodovana `/home/radovan/...` putanja
  (Linux-specifičan lokalni test, ne postoji na ovoj mašini)
- `test_model_benchmark.py::test_model` — nedostaje pytest fixture `model_name`
  (skripta očekuje CLI parametrizaciju, nije mišljena za plain `pytest tests/`)
- `test_tariff_validation_dialog.py` (2 testa) — poznata pretpostojeća regresija iz
  Pi/Codex commita `7eb31fd` (2026-07-18), već prijavljena u ranijem izvještaju istog dana

---

## Pronađeni problemi

1. **`tests/test_tool_use_offline.py` je netracen git-om.** `.gitignore:78` ignoriše
   `test_*.py` direktno pod `tests/` (scratch konvencija), sa izuzetkom
   `tests/*/test_*.py` (jedan nivo poddirektorija — `tests/unit/`, `tests/integration/`,
   itd.). Ovaj fajl sjedi direktno u `tests/`, pa NIKAD nije bio dio git istorije iako
   sadrži solidan, dobro strukturisan test suite za Tool Use sistem (30+ testova,
   referencira `docs/decisions/001-tool-use-refactoring.md`). Moje izmjene tamo (ažurirana
   `test_ima_tacno_10_alata`→`12`, novi `TestUpisUKolonuMutationGate`) su realne i prolaze,
   ali su **lokalne samo na ovoj mašini** — neće ih vidjeti Pi/Codex ni buduće sesije bez
   ovog fajla. Tracked pokrivenost za Faza A gate živi u `tests/unit/test_tool_policy.py`
   i `tests/unit/test_agent_mutation_gate.py` — dovoljna za DoD kriterijume, ali uža nego
   ono što lokalno postoji.
2. **Nepotpuna idempotencija dvostruke potvrde** — `_on_proposal_confirmed` nema
   `operation_id`; dvije uzastopne eksplicitne invokacije iste potvrde bi izvršile
   mutaciju dvaput. U stvarnom GUI toku, `ProposalCardWidget` se uništava
   (`hide_proposal_card()` → `deleteLater()`) odmah nakon prvog klika na dugme, što
   sprječava doslovan dvostruki klik na ISTI widget — ali ne štiti od reprodukovanog/
   replay Qt signala. Dokumentovano kao `xfail` test u
   `tests/unit/test_agent_mutation_gate.py::test_dvostruka_potvrda_ne_izvrsava_mutaciju_dvaput`
   umjesto da se lažno predstavi kao riješeno.

---

## Konflikti / kontradiktorni izvori

Nema. Plan (dograđen ranije danas) je jedini aktivni izvor za ovu fazu, i implementacija
ga prati bez odstupanja osim gore navedene odluke da se NE piše novi
`draft_mutation_handler.py` modul (plan ga je predložio kao "po potrebi" — procijenjeno
da nije potreban jer postojeća infrastruktura već odgovara).

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `073f334` | feat(agent): dodaj politiku efekata alata (ToolPolicy) |
| `d078879` | test(agent): zakljucaj sigurnosna pravila alata (ToolPolicy + mutation gate) |
| `5813a1b` | fix(agent): zahtijevaj potvrdu prije izmjene drafta (upisi_u_kolonu) |

Napomena o redoslijedu: plan (§12) predlaže test-commit PRIJE feat-commit-a. Ja sam
obrnuo redoslijed (feat prvo) jer testovi direktno importuju `tool_policy.py` — commit
testova prije te datoteke bi ostavio međukorak u istoriji koji ne prolazi
(`ImportError` pri checkout-u tog commita). Ishod (3 odvojena, jasno obilježena commita,
nijedan koji miješa sigurnosnu kapiju sa provider politikom ili pipeline statusima) je
isti kao što plan traži.

---

## Rizici / ograničenja

- Vidi "Pronađeni problemi" — netracen postojeći test fajl i nepotpuna idempotencija.
- `_propose_kolona_upis` za `tab='naim'` je implementirana i testirana (mock nivo), ali
  nije ručno provjerena u pravom GUI-ju (offscreen/vizuelni test nije rađen ovom prilikom
  — vidi "Potrebna korisnička potvrda").

---

## Potreban follow-up

- Razmotriti premještanje `tests/test_tool_use_offline.py` u `tests/unit/` da postane
  tracked (ili eksplicitno potvrditi da treba ostati lokalni scratch fajl).
- `operation_id`/idempotencija dvostruke potvrde — trenutno djelimično pokriveno samo
  GUI widget-destroy ponašanjem.
- Faze B–F plana ostaju neurađene, čekaju eksplicitnu odluku korisnika o nastavku.

---

## Potrebna korisnička potvrda

Minimalni ručni test iz plana §14, tačke 4-6 (relevantne za Fazu A):
- U pravoj aplikaciji: "upiši zemlju porijekla RS" → provjeriti da se NE mijenja
  draft prije klika na "Potvrdi i upiši" u proposal kartici.
- Kliknuti "✕ Odbaci" → provjeriti da draft ostaje identičan.
- Ponoviti i kliknuti potvrdu → provjeriti da se mijenja SAMO očekivano polje, i da se
  Faktura tab osvježava.
- Isto za kolonu koja cilja `naim` tab (npr. "upiši pakovanje PP u naim") — provjeriti
  da se upisuje u Naimenovanja, ne u Fakturu (ovo je nova putanja koju je bug prije
  onemogućavao — hardkodovan `tab='faktura'` u starom `_on_proposal_confirmed`).
