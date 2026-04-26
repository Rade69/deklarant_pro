# Agent Task — [KRATAK NAZIV]

**Datum:** YYYY-MM-DD
**Kreirao:** Claude Sonnet (nadzorni agent)
**Executor:** Qwen / MiniMax / drugi agent
**Status:** ČEKA / U TOKU / ZAVRŠENO / BLOKIRANO

---

> **IDE agent** (Qwen Code, GitHub Copilot, Cursor...): `AGENTS.md` već imaš u kontekstu — preskoči sekciju "Obavezno čitanje".
> **API/chat agent** (MiniMax, direktni API poziv...): pročitaj oba `AGENTS.md` fajla prije početka.

---

## Obavezno čitanje prije početka

1. `/home/radovan/.claude/AGENTS.md` — globalni standardi
2. `/home/radovan/Desktop/deklarant_pro/AGENTS.md` — projektni standardi
3. Fajlovi navedeni u sekciji "Fajlovi za čitanje"

---

## Kontekst

[Kratko objašnjenje zašto se ovaj zadatak radi — šta je problem ili šta se poboljšava]

---

## Zadatak

[Tačan opis šta treba uraditi — što konkretniji, bez ambigviteta]

---

## Fajlovi za čitanje (obavezno)

- `path/to/file.py` — razlog zašto ga čitaš
- `path/to/other.py` — razlog

---

## Tačne promjene

### Fajl: `path/to/file.py`

**Gdje:** [naziv metode / klase / linija]
**Šta:** [tačan opis izmjene]

```python
# PRIJE:
stari_kod_ovdje

# POSLIJE:
novi_kod_ovdje
```

---

## Norme koje se primjenjuju

- Srpski field names na modelima (`tarifni_broj`, ne `tariff_code`)
- Ne dodavati docstrings na kod koji nije mijenjan
- Ne refaktorisati van scope-a zadatka
- [Ostale norme specifične za ovaj zadatak]

---

## Provjera (kako znamo da je završeno)

- [ ] [Konkretna provjera 1]
- [ ] [Konkretna provjera 2]

---

## Output format (obavezan pri predaji)

```
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: opis
ŠTA NIJE URAĐENO: razlog (ako parcijalno/blokirano)
PITANJA: lista nejasnoća (ako postoje)
```
