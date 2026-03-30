# Agent Task — Integriši HybridTariffAgent u TariffLLMWorker

**Datum:** 2026-03-29
**Kreirao:** Claude Sonnet (nadzorni agent)
**Executor:** Qwen / MiniMax
**Status:** ZAVRŠENO

---

> **IDE agent** (Qwen Code, GitHub Copilot, Cursor...): `AGENTS.md` već imaš u kontekstu — preskoči sekciju "Obavezno čitanje".
>
> **API/chat agent** (MiniMax, direktni API poziv...): pročitaj oba `AGENTS.md` fajla prije početka.

---

## Obavezno čitanje prije početka

1. `/home/radovan/.claude/AGENTS.md` — globalni standardi
2. `/home/radovan/Desktop/asycuda_pro/AGENTS.md` — projektni standardi
3. Fajlovi navedeni u sekciji "Fajlovi za čitanje"

---

## Kontekst

Agent tab predlaže tarifne brojeve putem `TariffLLMWorker`. Trenutni tok:

```text
TariffRAGService.search_official(naziv) → kandidati → LLM (bira između kandidata)
```

Problem: LLM i dalje može pogriješiti. U Admin panelu postoji `HybridTariffAgent` koji radi bolje jer:

1. Prvo provjeri `TariffMappingService` — ako je isti ili sličan naziv već ručno klasifikovan (confidence ≥ 0.85), vrati taj rezultat **bez LLM poziva**
2. Tek ako nema pouzdanog matchinga, ide na RAG + LLM

Cilj: Koristiti `TariffMappingService` kao **pre-filter** u `TariffLLMWorker._process_batch()`.
Stavke koje mapping servis riješi s confidence ≥ 0.85 ne idu LLM-u.

---

## Fajlovi za čitanje (obavezno)

- `gui/tabs/agent/widgets/tariff_llm_worker.py` — trenutna implementacija, ovdje se vrše promjene
- `services/agent/hybrid_tariff_agent.py` — referenca za logiku, ne mijenja se
- `services/tariff_mapping_service.py` — servis koji se dodaje

---

## Tačne promjene

### Fajl: `gui/tabs/agent/widgets/tariff_llm_worker.py`

**Gdje:** Metoda `_process_batch()`, na početku, prije petlje `for idx, line in batch:`

**Šta:** Dodati pre-filter korak koji za svaku stavku provjeri `TariffMappingService`.
Stavke s confidence ≥ 0.85 se odmah dodaju u `resolved` listu i ne šalju LLM-u.
Ostatak ide kroz postojeći RAG → LLM tok.

**Logika (pseudokod):**

```text
resolved = []       # direktni rezultati iz mappinga
remaining = []      # ide dalje na RAG + LLM

za svaku (idx, line) u batch:
    mapping_result = mapping_service.find_mapping(
        product_code=line.product_code,
        naziv_robe=line.naziv_robe,
        min_similarity=0.70
    )
    ako mapping_result postoji I similarity >= 0.85:
        kreiraj TariffProposal(
            line_index=idx,
            tarifni_broj=mapping_result.tarifni_broj,
            confidence=mapping_result.similarity,
            explanation="Mapping: " + mapping_result.naziv_robe
        )
        dodaj u resolved
    inače:
        dodaj (idx, line) u remaining

ako remaining je prazan → vrati resolved
ako remaining nije prazan → izvrši postojeći RAG+LLM tok za remaining
                         → vrati resolved + llm_proposals
```

**Važno:**

- `TariffMappingService` se inicijalizuje unutar `_process_batch()` (kao što se i `TariffRAGService` inicijalizuje)
- Ako `TariffMappingService` nije dostupan (ImportError/Exception) — nastavi normalno bez pre-filtera
- `TariffProposal` se uvozi iz `gui.tabs.agent.agent_actions`
- `mapping_result.similarity` atribut nosi confidence vrijednost
- `mapping_result.naziv_robe` je naziv iz baze koji je matchovao

---

## Norme koje se primjenjuju

- Ne mijenjati logiku za `remaining` stavke — samo dodati pre-filter korak
- Ne dodavati docstrings na metode koje nisu mijenjane
- Ne refaktorisati `_process_batch` strukturu van navedenog
- Ako `TariffProposal` dataclass nema sve navedene atribute — pročitaj `agent_actions.py` i prilagodi, BLOKIRAJ ako nije jasno

---

## Provjera (kako znamo da je završeno)

- [ ] `_process_batch()` inicijalizuje `TariffMappingService` na početku (try/except)
- [ ] Stavke s mapping confidence ≥ 0.85 ne prolaze kroz LLM
- [ ] Stavke bez matchinga prolaze kroz isti RAG+LLM tok kao i prije
- [ ] Rezultati se spajaju i vraćaju kao jedna lista
- [ ] Greška u mapping servisu ne prekida cijeli batch (try/except)

---

## Output format (obavezan pri predaji)

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: opis
ŠTA NIJE URAĐENO: razlog (ako parcijalno/blokirano)
PITANJA: lista nejasnoća (ako postoje)
```
