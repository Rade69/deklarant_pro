# Izmjene 2026-04-27 — logo, launcher i Faktura tab

## Šta je rađeno
- Dodan je icon/logo paket za Deklarant Pro u `assets/icons/`.
- Dodan je Linux launcher fajl `scripts/linux/deklarant-pro.desktop`.
- U `run.py` je postavljeno učitavanje app ikonice iz `assets/icons/deklarant_icon_256.png`.
- Vraćen je `reportlab` u `requirements.txt` jer je nedostajao u runtime okruženju.

## Zašto je Faktura tab "nestao"
Faktura tab nije bio obrisan iz koda. Problem je bio runtime greška:
- `No module named 'reportlab'`
- TabFactory nije mogao kreirati `faktura` tab i vraćao je `None`.

## Rješenje
- `requirements.txt` dopunjen sa `reportlab>=4.0.0`.
- Lokalno potvrđen import `reportlab`.

## Relevantni commit
- `e65bd83` — `fix(app): vracen reportlab i dodate ikone/launcher`

## Dock ikonica (Linux) — aktivni prozor
- Problem: aplikacija se prikazivala sa generičkom ikonicom u dock-u iako `.desktop` fajl ima `Icon=...`.
- Uzrok: nedostajalo mapiranje između aktivnog Qt prozora i desktop launchera.
- Primijenjeno:
  - `run.py`: `app.setDesktopFileName("deklarant-pro")`
  - `scripts/linux/deklarant-pro.desktop`: `StartupWMClass=deklarant-pro`
  - osvježeni instalirani launcheri na Desktopu i u `~/.local/share/applications/`.
