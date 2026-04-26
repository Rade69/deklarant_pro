# Agent Task — Spriječi haluciniranje tarifnih brojeva u ChatWorker-u

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
3. Fajl naveden u sekciji "Fajlovi za čitanje"

---

## Kontekst

Kada korisnik pita agenta o tarifnim brojevima (npr. "koji su tarifni za vitamine?"),
ChatWorker šalje pitanje LLM-u koji **izmišlja kodove iz opšteg znanja**.

Primjer lošeg odgovora koji LLM daje:

```text
- BA VITAMIN B COMPLEX: 3105201000   ← gnojivo!
- BA MG DUO VIT. B6:   1806906000   ← čokolada!
- Vitamin C:            2936210000
- Vitamin D:            2936290000
```

Uzrok: system prompt kaže:
> "Koristi prijedloge iz baze znanja i istorije kao osnovu, **ali ih provjeri sa znanjem**"

Ova rečenica dozvoljava LLM-u da koristi opšte znanje za tarifne kodove → halucinacija.

Uz to, min_similarity threshold u `_predlozi_tarifne_brojeve()` je 0.65 — prenizak,
dozvoljava slabe fuzzy matcheve koji daju pogrešne kodove pri Auto-popuni.

---

## Zadatak

Dvije izmjene:

### 1. Zabraniti haluciniranje u system promptu

### 2. Podići threshold za mapping service

---

## Fajlovi za čitanje (obavezno)

- `gui/tabs/agent/widgets/chat_worker.py` — sadrži `_system_prompt()` metodu
- `gui/tabs/agent/agent_controller.py` — sadrži `_predlozi_tarifne_brojeve()`

---

## Tačne promjene

### Fajl: `gui/tabs/agent/widgets/chat_worker.py`

**Gdje:** Metoda `_system_prompt()`, u sekciji `PRAVILA:` (oko linije 858-860)

**Šta:** Zamijeni dozvolu za opšte znanje sa eksplicitnom zabranom:

```python
# PRIJE (oko linije 859):
"- Koristi prijedloge iz baze znanja i istorije kao osnovu, ali ih provjeri sa znanjem\n"

# POSLIJE:
"- Za tarifne brojeve KORISTI ISKLJUČIVO prijedloge iz baze znanja i istorije deklaracija "
"— NIKADA ne izmišljaj kodove iz opšteg znanja\n"
"- Ako baza znanja i istorija nemaju prijedlog — reci 'Nije pronađen u bazi' umjesto da izmisliš kod\n"
```

---

### Fajl: `gui/tabs/agent/agent_controller.py`

**Gdje:** Metoda `_predlozi_tarifne_brojeve()`, poziv `svc.find_mapping()` (oko linije 1221-1226)

**Šta:** Podići `min_similarity` s `0.65` na `0.75`:

```python
# PRIJE:
mapping = svc.find_mapping(
    product_code=line.product_code,
    naziv_robe=line.naziv_robe,
    min_similarity=0.65
)

# POSLIJE:
mapping = svc.find_mapping(
    product_code=line.product_code,
    naziv_robe=line.naziv_robe,
    min_similarity=0.75
)
```

---

## Norme koje se primjenjuju

- Ne mijenjati ništa van navedenih linija
- Ne dodavati docstrings ni komentare na kod koji nije mijenjan
- Ne refaktorisati `_system_prompt()` strukturu

---

## Provjera (kako znamo da je završeno)

- [ ] String "ali ih provjeri sa znanjem" više ne postoji u `chat_worker.py`
- [ ] String "NIKADA ne izmišljaj kodove" postoji u `chat_worker.py`
- [ ] `min_similarity=0.65` ne postoji u `_predlozi_tarifne_brojeve()` u `agent_controller.py`
- [ ] `min_similarity=0.75` postoji na tom mjestu

---

## Output format (obavezan pri predaji)

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: opis
ŠTA NIJE URAĐENO: razlog (ako parcijalno/blokirano)
PITANJA: lista nejasnoća (ako postoje)
```
