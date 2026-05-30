# Deklarant Pro — Windows instalacija

> Ovaj fajl čita Claude Code agent na Windows računaru da zna šta treba uraditi.
> Datum pripreme: 2026-05-29 | Razvojni laptop: 192.168.100.131

---

## Šta je ovo

Deklarant Pro je carinska aplikacija (Python + PySide6 GUI) za kreiranje ASYCUDA XML deklaracija.
Baza podataka (PostgreSQL) je na serveru `192.168.0.41` — Windows samo pokreće GUI koji se spaja na server.

---

## Stanje na ovom računaru

- ✅ Python 3.11.9 instaliran
- ✅ Fajlovi projekta kopirani
- ❌ Build EXE-a nije urađen
- ❌ Licenca nije generisana

---

## Korak 1 — Pokreni build

Otvori CMD ili PowerShell kao **Administrator**, uđi u folder projekta i pokreni:

```cmd
cd "C:\Users\dm promet\Desktop\deklarant_pro"
build_windows.bat
```

Ovo automatski:
1. Instalira PyInstaller i zavisnosti
2. Gradi `dist\DeklarantPro\DeklarantPro.exe` (standalone, bez potrebe za Python-om)

Može trajati **10–20 minuta**. Čekaj da završi.

---

## Korak 2 — Uzmi fingerprint računara

Nakon build-a, pokreni:

```cmd
cd "C:\Users\dm promet\Desktop\deklarant_pro"
python -c "from core.licensing.machine_fingerprint import get_machine_fingerprint; import json; print(json.dumps(get_machine_fingerprint(), indent=2))"
```

Sačuvaj JSON ispis — treba ga poslati na razvojni laptop (192.168.100.131) da se generiše licenca.

---

## Korak 3 — Generiši licencu (na Linux laptopu)

Na razvojnom laptopu (`/home/radovan/Desktop/deklarant_pro`) pokreni:

```bash
uv run python3 tools/licensing/generate_license.py \
    --customer-name "DM Promet — Windows klijent" \
    --customer-id "dmwindows" \
    --fingerprint-json '{ ... JSON iz Koraka 2 ... }' \
    --valid-from 2026-01-01 \
    --valid-to 2030-12-31 \
    --features full,agent \
    --output /tmp/dmwindows_licenca.dat
```

---

## Korak 4 — Kopiraj licencu na Windows

Kopirati `dmwindows_licenca.dat` kao `license.dat` u:
```
C:\ProgramData\DeklarantPro\license.dat
```

Ako folder ne postoji, kreirati ga ručno.

---

## Korak 5 — Napravi .env fajl

U `dist\DeklarantPro\` kreirati fajl `.env` sa sadržajem:

```
DB_HOST=192.168.0.41
DB_PORT=5432
DB_NAME=deklarant_pro
DB_USER=radovan
DB_PASSWORD=postgres
DEBUG=False
CLIENT_NAME=dmwindows
GROQ_API_KEY=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
GEMINI_API_KEY=AIzaSyBOYdE9AqvHSd84X8H9LHcAl781laK2Lx0
DEEPSEEK_API_KEY=sk-7930a4bb836e4069a848d74e7bef21d8
SEND_SENSITIVE_DATA=false
SESSION_TOKEN_BUDGET=50000
```

---

## Korak 6 — Testiraj

Pokrenuti `dist\DeklarantPro\DeklarantPro.exe` — ne smije tražiti licencu, mora se spojiti na bazu.

---

## Korak 7 — Inno Setup installer (opcionalno)

Za pravi `.exe` installer:
1. Preuzeti Inno Setup: https://jrsoftware.org/isdl.php
2. Otvoriti `installer\setup.iss` i kompajlirati (Ctrl+F9)

---

## Kontakti i kredencijali

| Šta | Vrijednost |
|---|---|
| Razvojni laptop IP | 192.168.100.131 |
| Server (baza) IP | 192.168.0.41 |
| SSH na ovaj Windows | `ssh "dm promet@192.168.100.55"`, lozinka: `1` |
| SSH na server | `ssh dmpromet@192.168.0.41`, lozinka: `dm2008` |
