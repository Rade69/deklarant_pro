# Agent Report — 2026-07-19: Faza B — jedinstveni LLM provider i fallback politika

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/agent/widgets/llm_provider.py` + dist_client mirror
- `services/agent/chat/tool_dispatcher.py` + dist_client mirror
- `services/agent/chat/intent_classifier.py` + dist_client mirror
- `services/agent/chat/tool_definitions.py` + dist_client mirror
- `gui/tabs/admin/panels/system_panel.py` + dist_client mirror
- `tests/unit/test_llm_provider_fallback.py`
- `docs/decisions/001-tool-use-refactoring.md`, `002-tool-dispatcher-integration.md`
- `project_rooms/2026-07-19_faza-b-llm-provider-unifikacija.md`

Realizovana **Faza B** iz `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md`.
Faze C–F nisu rađene.

---

## Status izvora

- Plan (dograđen §5.6/§6.6/§7.7/§10.4 od strane iste sesije ranije) — aktivan, jedini izvor.
- `agent_reports/2026-07-19_faza-a-sigurnosna-kapija-mutirajuci-alati.md` — Faza A,
  aktivna, `tool_policy.is_known_tool()` iskorišten za validaciju u ovoj fazi.

---

## GitNexus impact

**HIGH rizik** — potvrđen prije izmjene, obavezan `project_rooms/2026-07-19_faza-b-llm-provider-unifikacija.md`
napisan po `AGENTS.md` proceduri:

| Simbol | Rizik | Ključni nalaz |
|--------|-------|----------------|
| `LLMProvider` (klasa) | HIGH | 34 impacted, 16 direktnih uvoznika (centralna klasa) |
| `has_deepseek()` | HIGH | 19 impacted — **otkriven stvaran vanjski pozivalac**: `SystemPanel._on_ai_health_clicked` (admin AI health check), izvan plana predviđenog scope-a |

Ovaj nalaz je direktno promijenio implementaciju: bez otkrivanja i popravke
`system_panel.py`, admin "AI Health Check" dugme bi pucalo (`AttributeError`)
odmah nakon merge-a. `gitnexus_detect_changes()` nakon commitova: `risk_level:
medium`, 3 pogođena procesa (sva očekivana — `Run → _groq_stream`, `Run →
_gemini_stream`/`complete`, tačno metode koje sam mijenjao).

---

## Šta je urađeno

### 1. Korisnička odluka prije implementacije

Otkrio sam da `LLMProvider` (ne samo `tool_dispatcher.py`) i dalje ima
OpenRouter i DeepSeek kao 3./4. fallback, suprotno `AGENTS.md` politici
("Primarni: Groq; fallback: Gemini... DeepSeek isključen"). Plan §6.2
eksplicitno zabranjuje agentu da sam odluči o ovome ("kontradiktorna
poslovna odluka i mora se potvrditi"). Pitao sam korisnika — potvrđeno:
**ukloniti oba iz lanca u potpunosti**.

### 2. `llm_provider.py` — uklonjeni OpenRouter/DeepSeek, dodat `complete_with_tools()`

- Uklonjeno: `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`, `OPENROUTER_BASE_URL`,
  `OPENROUTER_MODEL`, `deepseek_key`, `openrouter_key`, `openrouter_model`,
  `has_deepseek()`, `has_openrouter()`, `_deepseek_stream`, `_deepseek_complete`,
  `_openrouter_stream`, `_openrouter_complete`. `stream_chat()`/`complete()`/
  `active_provider()` sad idu samo Groq → Gemini.
- Novo: `ProviderToolResponse` dataclass (`tool_name`, `tool_arguments`, `content`,
  `provider`, `error`) i `complete_with_tools(messages, tools, max_tokens)` —
  Groq → Gemini, isti fallback obrazac kao postojeće metode.
  - `_groq_complete_with_tools`: Groq je OpenAI-kompatibilan, `tools=`/
    `tool_choice="auto"` direktno.
  - `_gemini_complete_with_tools` + `_gemini_tool_declarations`: konvertuje
    OpenAI-stil `TOOLS` listu (iz `tool_definitions.py`) u
    `types.FunctionDeclaration`, parsira `function_call` iz `response.candidates`.
  - `provider` polje omogućava audit koji je provider stvarno završio poziv.

### 3. `tool_dispatcher.py::_dispatch` — uklonjen direktan DeepSeek klijent

Zamijenjen `OpenAI(base_url="https://api.deepseek.com")` blok sa
`provider.complete_with_tools(messages, tools=TOOLS, max_tokens=300)`. Dodata
validacija: `is_known_tool(response.tool_name)` (iz `tool_policy.py`, Faza A)
— ako LLM vrati nepostojeće ime alata, tretira se kao greška prije nego
stigne do `_execute_tool()`, ne kao validan `tool_call`.

### 4. `system_panel.py::_on_ai_health_clicked` — uklonjeni DeepSeek/OpenRouter redovi

Otkriveno GitNexus impact analizom (vidi gore). Health check sad testira
samo Groq/Gemini (ključ, DNS, testni upit).

### 5. `intent_classifier.py`, `tool_definitions.py` — samo zastarjeli komentari

Kod je već ispravno koristio `LLMProvider.complete()` (ne direktan provider).
Ispravljene samo docstring/komentar reference na "DeepSeek" koje više ne
odgovaraju stvarnosti.

### 6. `docs/decisions/001`, `002` — usklađeni sa stvarnim tokom

Dodane napomene "Ažurirano 2026-07-19 (Faza B)" koje objašnjavaju prelaz sa
DeepSeek-specifičnog originalnog dizajna na `LLMProvider.complete_with_tools()`.

---

## Zašto je urađeno

`tool_dispatcher.py` je pozivao DeepSeek direktno, mimo `LLMProvider`
apstrakcije — direktno kršenje AGENTS.md pravila "LLMProvider ostaje jedina
dozvoljena ulazna tačka za LLM pozive", potvrđeno čitanjem koda prije
dograđivanja plana (§6.6). Cilj Faze B je bio da chat, tool use i batch
pozivi dijele istu konfiguraciju/fallback/audit — sada svi idu kroz
`LLMProvider`.

---

## Kako je urađeno

Detaljno u "Šta je urađeno". Ključna tehnička odluka: Gemini function-calling
format (`types.FunctionDeclaration`) razlikuje se od OpenAI/Groq JSON schema
tool formata — napisan konverter (`_gemini_tool_declarations`) koji direktno
reuse-uje `parameters` dict iz `tool_definitions.py` (oba formata su
JSON-schema-bazirana, dovoljno kompatibilna bez punog remapiranja polja).

---

## Šta nije dirano

- `gui/tabs/admin/panels/analytics_panel.py:252` — `boje['deepseek']` u
  color-lookup dict-u za UI badge, potpuno neaktivan unos (nikad se neće
  matchovati) — bezopasno ostaviti, nije funkcionalni bug (vidi project_room).
- Faze C–F plana — van scope-a ovog prolaza.
- Regex fallback sloj u `chat_intent_handler.py` — ostaje (§10.2 pravilo).
- `docs/decisions/002` linija o "Faza 3" (brisanje regex sloja) — netaknuta,
  to je odvojena, još otvorena odluka (vidi §19 dograđenog plana).

---

## Verifikacija

```
python -m pytest tests/unit/test_llm_provider_fallback.py -v
→ 20 passed

python -m pytest tests/unit/test_tool_dispatcher.py tests/unit/test_tool_result.py -v
→ 14 passed (nepromijenjeno, regresija nula)

python -m pytest tests/unit tests/integration -q --ignore=tests/unit/test_decision_characterization.py
→ 679 passed, 44 skipped, 2 failed, 1 xfailed

python -m py_compile <svi izmijenjeni/novi fajlovi + dist_client mirrors> → OK

diff (sadržaj bez BOM) <root> <dist_client> za svih 5 izmijenjenih fajlova → IDENTIČNI
```

2 fail-a (`test_tariff_validation_dialog.py`) su pretpostojeća, već
dokumentovana regresija iz Pi/Codex commita `7eb31fd` (2026-07-18) — potvrđeno
`git log`, nepovezano sa ovom izmjenom.

`tests/unit/test_decision_characterization.py` (10 testova) je namjerno
isključen iz ovog run-a — PostgreSQL server (192.168.0.25) je bio privremeno
nedostupan (`DB circuit breaker aktivan`) tokom rada, isti povremeni problem
viđen ranije u sesiji. Nepovezano sa LLM provider kodom (ti testovi hit-uju
pravu bazu za tarifne mapinge, ne LLM). Preporuka: ponovo pokrenuti taj fajl
kad je server dostupan.

---

## Pronađeni problemi

- Vidi "GitNexus impact" — `system_panel.py` je otkriven kao skriven
  pozivalac tek impact analizom, ne iz plana samog. Dobar primjer zašto je
  obavezna provjera prije izmjene vrijedna truda.
- PostgreSQL server privremeno nedostupan tokom sesije (van moje kontrole) —
  spriječio potpunu verifikaciju `test_decision_characterization.py`.

---

## Konflikti / kontradiktorni izvori

Plan (§6.2) je eksplicitno označio pitanje OpenRouter/DeepSeek zadržavanja
kao potencijalni konflikt koji zahtijeva korisničku potvrdu — nisam sam
odlučio, pitao sam prije implementacije. Korisnik je potvrdio potpuno
uklanjanje. Nema drugih kontradiktornih izvora.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `fa687a2` | refactor(llm): objedini tool use kroz llm provider |
| `2bef683` | test(agent): pokrij provider i tool fallback tokove |
| `f8c6551` | docs(agent): uskladi odluke i agentski tok (Faza B provider) |

---

## Rizici / ograničenja

- `complete_with_tools()` za Gemini granu nije testirana protiv PRAVOG Gemini
  API-ja u ovoj sesiji (samo mock-based unit testovi, per plan §9.2 "Provider
  transport se smije zamijeniti determinističkim fake adapterom"). Format
  konverzije (`_gemini_tool_declarations`) je zasnovan na dokumentovanom
  `google.genai` SDK API-ju, ali live-test protiv stvarnog Gemini function
  calling odgovora nije rađen — preporučujem ručnu provjeru (vidi ispod).
- Ako korisnik ikad poželi DeepSeek/OpenRouter kao plaćeni emergency
  fallback, to je sad potpuno uklonjeno iz koda (ne samo deaktivirano) —
  vraćanje zahtijeva novi eksplicitan zadatak, ne samo dodavanje API ključa
  u `.env`.

---

## Potreban follow-up

- Faze C–F plana (pipeline pouzdanost, observability, integracioni testovi,
  razlaganje `chat_intent_handler.py`) čekaju odluku korisnika o nastavku.
- Ponovo pokrenuti `test_decision_characterization.py` kad je PostgreSQL
  server dostupan (nepovezano sa ovom fazom, ali nezavršena verifikacija).

---

## Potrebna korisnička potvrda

- U pravoj aplikaciji: privremeno onemogućiti Groq (npr. pogrešan
  `GROQ_API_KEY`) i poslati chat poruku koja zahtijeva Tool Use — potvrditi
  da se Gemini stvarno aktivira i da tool-call i dalje radi (plan §14, tačka 10).
- Provjeriti da Admin → System → "AI Health Check" dugme radi bez greške
  (ranije bi pucalo bez izmjene u `system_panel.py`).
