# Agent Task — Nova namjera: "upiši tarifne za [ključna riječ]"

**Datum:** 2026-03-29
**Kreirao:** Claude Sonnet (nadzorni agent)
**Executor:** Qwen / MiniMax
**Status:** ČEKA

---

> **IDE agent** (Qwen Code, GitHub Copilot, Cursor...): `AGENTS.md` već imaš u kontekstu — preskoči sekciju "Obavezno čitanje".
>
> **API/chat agent** (MiniMax, direktni API poziv...): pročitaj oba `AGENTS.md` fajla prije početka.

---

## Obavezno čitanje prije početka

1. `/home/radovan/.claude/AGENTS.md` — globalni standardi
2. `/home/radovan/Desktop/deklarant_pro/AGENTS.md` — projektni standardi
3. Fajlovi navedeni u sekciji "Fajlovi za čitanje"

---

## Kontekst

Korisnik kaže: **"Pogledaj po nazivu proizvoda i kao su ti vitamini upiši te tarifne brojeve"**

Trenutno se ovo detektuje kao LLM upit jer sadrži "pogledaj" (`_is_query=True`), pa
ChatWorker dobiva pitanje i slobodno halucinira kodove.

Ispravno ponašanje:
1. Prepoznati da korisnik traži filter po ključnoj riječi ("vitamini") + upis tarife
2. Filtrirati `invoice_lines` po toj ključnoj riječi u `naziv_robe`
3. Za svaku matching liniju pokrenuti `TariffMappingService` + `TariffRAGService`
4. Prikazati prijedloge i tražiti potvrdu (kao u postojećem `_on_tariff_llm_ready`)

Ključni pattern za detekciju:
- "pogledaj ... i upiši tarifne" / "kao su ti X upiši tarifne" / "upiši tarifne za X"
- Postoji ključna riječ + glagol upisa + "tarif"

---

## Fajlovi za čitanje (obavezno)

- `gui/tabs/agent/agent_controller.py` — `_on_chat_message()` i `_predlozi_tarifne_brojeve()`
- `gui/tabs/agent/agent_actions.py` — `TariffProposal` dataclass (provjeri polja!)

---

## Tačne promjene

### Fajl: `gui/tabs/agent/agent_controller.py`

#### Promjena 1 — Nova metoda `_predlozi_tarifne_po_filteru(keyword)`

Dodati novu metodu **odmah iza `_predlozi_tarifne_brojeve()`**.

Logika:

```python
def _predlozi_tarifne_po_filteru(self, keyword: str):
    """Predlaže tarifne brojeve samo za stavke čiji naziv_robe sadrži keyword."""
    from .agent_actions import TariffProposal
    from services.tariff_mapping_service import TariffMappingService
    from .widgets.tariff_llm_worker import TariffLLMWorker

    chat = self.view.get_chat_panel()

    if not self.draft or not self.draft.invoice_lines:
        chat.add_agent_message("⚠️ Nema učitanih stavki u Faktura tabu.")
        return

    kw = keyword.lower().strip()

    # Filtriraj po ključnoj riječi u nazivu
    filtrirane = [
        (i, line) for i, line in enumerate(self.draft.invoice_lines)
        if kw in (getattr(line, 'naziv_robe', '') or '').lower()
    ]

    if not filtrirane:
        chat.add_agent_message(f"⚠️ Nema stavki čiji naziv sadrži '{keyword}'.")
        return

    chat.add_activity(f"🔍 Nađeno {len(filtrirane)} stavki s '{keyword}', tražim tarifne...")

    # Lokalna baza znanja
    svc = TariffMappingService()
    proposals = []
    bez_lokalne = []

    for idx, line in filtrirane:
        naziv = (getattr(line, 'naziv_robe', '') or '').strip()
        product_code = (getattr(line, 'product_code', '') or '').strip()
        mapping = svc.find_mapping(
            product_code=product_code,
            naziv_robe=naziv,
            min_similarity=0.75
        )
        if mapping:
            proposals.append(TariffProposal(
                line_index=idx,
                naziv_robe=naziv[:60],
                product_code=product_code,
                proposed_tariff=mapping.tarifni_broj,
                confidence=mapping.similarity if hasattr(mapping, 'similarity') else 1.0,
                source="baza_znanja"
            ))
        else:
            bez_lokalne.append((idx, line))

    if bez_lokalne:
        chat.add_activity(
            f"✅ Lokalna baza: {len(proposals)}. "
            f"🤖 AI za preostalih {len(bez_lokalne)}..."
        )
        worker = TariffLLMWorker(bez_lokalne, parent=self.view)
        worker.proposals_ready.connect(
            lambda llm_p: self._on_tariff_llm_ready(proposals, llm_p, len(filtrirane), chat)
        )
        worker.error_occurred.connect(
            lambda err: self._on_tariff_llm_ready(proposals, [], len(filtrirane), chat)
        )
        worker.finished.connect(worker.deleteLater)
        if not hasattr(self, '_tariff_workers'):
            self._tariff_workers = []
        self._tariff_workers.append(worker)
        worker.finished.connect(
            lambda: self._tariff_workers.remove(worker) if worker in self._tariff_workers else None
        )
        worker.start()
    else:
        self._on_tariff_llm_ready(proposals, [], len(filtrirane), chat)
```

**Napomena:** Provjeri koja polja ima `TariffProposal` u `agent_actions.py` i prilagodi poziv ako se razlikuje.

---

#### Promjena 2 — Detekcija namjere u `_on_chat_message()`

**Gdje:** U metodi `_on_chat_message()`, odmah **ispred** bloka za brisanje tarifnih brojeva (oko linije 1114).

**Šta:** Dodati detekciju nove namjere.

Pattern za detekciju:
- Poruka sadrži ("pogledaj" ili "nađi" ili "traži") AND "upiši" AND "tarif"
- ILI: poruka sadrži "upiši tarifne za" ili "upiši tarife za"

Extractovanje ključne riječi — uzeti riječ koja slijedi iza "vitamini"/"za X"/"kao su ti X":

```python
# --- DETEKCIJA NAMJERE: upiši tarifne za [keyword] ---
import re as _re2
_filter_tariff_match = _re2.search(
    r'(?:pogledaj|nađi|trazi|traži).{0,40}?(\w{3,})\s+upiši\s+(?:te\s+)?tarif'
    r'|upiši\s+(?:te\s+)?tarif\w*\s+za\s+(\w+)'
    r'|(\w+)\s+upiši\s+(?:te\s+)?tarif',
    msg
)
if _filter_tariff_match:
    keyword = next(g for g in _filter_tariff_match.groups() if g)
    # Preskoči opšte riječi koje nisu filter
    _skip = {'te', 'sve', 'koji', 'koje', 'ovi', 'ove', 'tarif', 'tarifne', 'broj'}
    if keyword not in _skip and len(keyword) >= 3:
        self._predlozi_tarifne_po_filteru(keyword)
        return
```

---

## Norme koje se primjenjuju

- Nova metoda `_predlozi_tarifne_po_filteru` se dodaje odmah iza `_predlozi_tarifne_brojeve`
- Ne mijenjati `_predlozi_tarifne_brojeve` ni `_on_tariff_llm_ready`
- Ne dodavati docstrings na metode koje nisu mijenjane
- Ako `TariffProposal` nema neko od navedenih polja — pročitaj `agent_actions.py` i prilagodi, BLOKIRAJ ako nije jasno

---

## Provjera (kako znamo da je završeno)

- [ ] Metoda `_predlozi_tarifne_po_filteru(keyword)` postoji u `agent_controller.py`
- [ ] Regex detekcija postoji u `_on_chat_message()` ispred brisanja tarifnih
- [ ] Poruka "Pogledaj po nazivu i kao su ti vitamini upiši te tarifne" → poziva `_predlozi_tarifne_po_filteru("vitamini")`
- [ ] Poruka "upiši tarifne za vitamine" → poziva `_predlozi_tarifne_po_filteru("vitamine")`
- [ ] Nije promijenjen flow za "popuni tarif" (svi bez tarife)

---

## Output format (obavezan pri predaji)

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: opis
ŠTA NIJE URAĐENO: razlog (ako parcijalno/blokirano)
PITANJA: lista nejasnoća (ako postoje)
```
