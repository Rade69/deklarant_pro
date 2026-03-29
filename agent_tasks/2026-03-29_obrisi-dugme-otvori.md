# Agent Task — Obriši dugme "Otvori" iz toolbara Zaglavlje taba

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
3. Fajl naveden u sekciji "Fajlovi za čitanje"

---

## Kontekst

U toolbar-u Zaglavlje taba postoje dva dugmeta s istom funkcionalnošću:

- **"Otvori"** (`btn_otvori`) — otvara file dialog, emituje `open_requested` signal
- **"Uvezi XML"** (`btn_import`) — otvara file dialog, emituje `import_xml_requested` signal

U controlleru oba signala završavaju na istom handleru `_on_import_xml()`.
Dugme "Otvori" je redundantno i treba ga ukloniti zajedno sa svim referencama.

---

## Zadatak

Ukloniti dugme "Otvori" (`btn_otvori`) iz Zaglavlje taba — kompletno, bez ostataka.

---

## Fajlovi za čitanje (obavezno)

- `gui/tabs/zaglavlje_view.py` — sadrži definiciju toolbar-a i signale
- `gui/tabs/zaglavlje_controller.py` — sadrži signal handler

---

## Tačne promjene

### Fajl: `gui/tabs/zaglavlje_view.py`

**1. Ukloni deklaraciju atributa** (oko linije 256):

```python
# BRIŠE SE:
self.btn_otvori: Optional[QPushButton] = None
```

**2. Ukloni kreiranje dugmeta** (oko linije 352-353):

```python
# BRIŠE SE:
self.btn_otvori = self._create_icon_button("Otvori", "fa5.folder-open")
self.btn_otvori.setObjectName("btnOtvori")
```

**3. Ukloni dodavanje u layout** (oko linije 371):

```python
# BRIŠE SE:
layout.addWidget(self.btn_otvori)
```

**4. Ukloni signal konekciju** (oko linije 1480):

```python
# BRIŠE SE:
self.btn_otvori.clicked.connect(self.open_requested.emit)
```

**5. Ukloni CSS stil** (oko linije 1545-1549):

```css
/* BRIŠE SE: */
QPushButton#btnOtvori {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fff3e0, stop:1 #ffcc80);
    border: 1px solid #ff9800; color: black; font-weight: 500;
}
```

**6. Ukloni signal deklaraciju** (oko linije 236):

```python
# BRIŠE SE:
open_requested = Signal()
```

### Fajl: `gui/tabs/zaglavlje_controller.py`

**7. Ukloni signal konekciju** (oko linije 85):

```python
# BRIŠE SE:
self.view.open_requested.connect(self._on_open)
```

**8. Ukloni komentar o signalu** (oko linije 75):

```text
# BRIŠE SE (samo ovaj red u listi):
- open_requested → _on_open
```

**9. Ukloni cijelu `_on_open` metodu** (oko linije 230-251):

```python
# BRIŠE SE cijela metoda:
def _on_open(self):
    """Otvori ASYCUDA XML deklaraciju (isti flow kao uvoz XML-a)."""
    try:
        ...
    except Exception as e:
        ...
```

---

## Norme koje se primjenjuju

- Ne dodavati docstrings ni komentare na kod koji nije mijenjan
- Ne refaktorisati ništa van navedenih tačaka
- Ako se `open_requested` signal koristi negdje drugdje u projektu — BLOKIRAJ i prijavi

---

## Provjera (kako znamo da je završeno)

- [ ] `btn_otvori` ne postoji nigdje u `zaglavlje_view.py`
- [ ] `open_requested` signal ne postoji nigdje u `zaglavlje_view.py`
- [ ] `_on_open` metoda ne postoji u `zaglavlje_controller.py`
- [ ] `grep -rn "btn_otvori\|open_requested\|_on_open" gui/tabs/zaglavlje_*` ne vraća ništa
- [ ] Toolbar i dalje ima: Novi, Uvezi XML, Snimi, Briši, Izvezi XML, Izlaz

---

## Output format (obavezan pri predaji)

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: opis
ŠTA NIJE URAĐENO: razlog (ako parcijalno/blokirano)
PITANJA: lista nejasnoća (ako postoje)
```
