# Style Governance — Pravila i guardrails za stilove

**Datum:** 2026-05-03
**Task:** TASK-005
**Scope:** Dokumentacija + read-only linter skripta

---

## 1. 3-Layer model

Svi stilovi moraju pripadati tačno jednom sloju:

```
┌─────────────────────────────────────┐
│  L1 — Inline (state-only)           │  setStyleSheet sa runtime logikom
│  Prioritet: 🔴 NAJVIŠI              │  Primer: boja validacije, drag highlight
├─────────────────────────────────────┤
│  L2 — Tab/Component QSS             │  .qss fajl za specifičan tab/widget
│  Prioritet: 🟡 SREDNJI              │  Primer: naimenovanja_components.qss
├─────────────────────────────────────┤
│  L3 — Global QSS                    │  .qss fajlovi u main_window.py
│  Prioritet: 🟢 NAJNIŽI              │  Primer: unified_color_system.qss
└─────────────────────────────────────┘
```

### Pravilo prioriteta
- Niži sloj NE SME pregaziti viši bez **eksplicitnog komentara** sa razlogom.
- Ako L3 pregazi L2, to je **bug** osim ako nije dokumentovano.
- Inline (L1) je dozvoljen samo za **state runtime** promjene.

---

## 2. Kada koristiti koji sloj

| Scenario | Sloj | Primer |
|----------|------|--------|
| Boja se mijenja po logici (error/success) | L1 | `setStyleSheet("color: red")` na validaciji |
| Drag & drop highlight | L1 | `dragEnterEvent` → highlight |
| Hover/pressed na custom widgetu | L1 | Card sa kompleksnim hover state |
| Stilovi specifični za jedan tab | L2 | `#NaimenovanjaTab QLineEdit` |
| Stilovi za reusable komponentu | L2 | `.proposal_card`类 u komponent QSS |
| Paleta boja aplikacije | L3 | `unified_color_system.qss` |
| Tipografija (font, size) | L3 | `typography.qss` |
| Sistem dugmadi | L3 | `button_system.qss` |
| Razmaci i layout | L3 | `spacing_system.qss` |

---

## 3. Naming konvencije

### objectName konvencija

| Element | Format | Primer |
|---------|--------|--------|
| Tab container | `{Naziv}Tab` | `#FakturaTab`, `#ZaglavljeTab` |
| Glavni widget u tabu | `{naziv}TabWidget` | `#fakturaTabWidget` |
| Dugme po akciji | `btn{Naziv}` | `#btnSnimi`, `#btnDodaj` |
| Dugme po tipu (atribut) | `btnType="{tip}"` | `[btnType="primary"]` |
| Input polje | `input{Naziv}` | `#inputBruto` |
| Label po nameni | `lbl{Naziv}` | `#lblStatus` |
| Grupa/sekcija | `grp{Naziv}` | `#grpIzvoznik` |

### QSS class property (alternativa objectName)

```python
widget.setProperty("class", "card-primary")  # Python
```
```css
QWidget[class="card-primary"] { ... }  /* QSS */
```

**Kada koristiti `class` umjesto `objectName`**:
- Više instanci iste komponente
- Reusable widget (npr. card, panel)
- Ne želiš globalno jedinstven ID

---

## 4. Zabranjeni patterni (anti-patterns)

| Anti-pattern | Zašto je loše | Primer |
|-------------|---------------|--------|
| Hardkodirane boje bez varijable | Divergencija, teško održavanje | `color: #2c3e50` umjesto `color: #2C5570` |
| Globalni `QLineEdit` bez scopa | Pregazi sve inpute u aplikaciji | `QLineEdit { border: ... }` |
| Duplikat QSS fajlovi | Identičan sadržaj, 2x održavanje | `asycuda_modern_material.qss` + `deklarant_modern_material.qss` |
| Inline BASE stilovi | Pregazuj L2/L3, teško refaktorisati | `setStyleSheet("font-size: 12px")` na 20+ mjesta |
| `!important` u QSS | Indikator loše organizacije | `background: red !important` |
| ID selektor bez tab scopa | Utice na sve tabove | `#btnSnimi` umjesto `#ZaglavljeTab #btnSnimi` |
| QComboBox::down-arrow duplikat | Konflikt strelice | 3 deklaracije u različitim .qss |

---

## 5. Proces dodavanja novog stila

```
1. Da li je runtime state promjena?
   └── DA → L1 (inline, sa komentarom zašto)

2. Da li pripada specifičnom tabu/komponenti?
   └── DA → L2 (novi ili postojeći .qss za taj tab)
      └── Dodaj objectName ili class property
      └── Piši scoped selektor: #TabName QLineEdit { }

3. Da li je aplikacijski-wide pattern?
   └── DA → L3 (dodaj u odgovarajući global .qss)
      └── Koristi klasu umjesto ID ako je reusable
      └── Dokumentuj u STYLE_INVENTORY.md

4. Pokreni style_audit.sh
   └── Provjeri da nema konflikata
```

---

## 6. Linter skripta

Pokreni:
```bash
bash scripts/style_audit.sh
```

Skripta provjerava:
- Duplikat `QComboBox::down-arrow` deklaracije
- Inline stilovi bez komentara razloga
- Globalni nescopirani selektori visokog rizika

---

## 7. Odgovornosti

| Uloga | Dužnost |
|-------|---------|
| Agent koji dodaje stil | Odabrati pravi sloj, dokumentovati u komentaru |
| Code review | Pokrenuti `style_audit.sh`, provjeriti diff |
| Održavanje | Ažurirati STYLE_INVENTORY.md kad se dodaje novi .qss |
