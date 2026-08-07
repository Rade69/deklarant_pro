# Deklarant Pro

Aplikacija za carinske deklaracije — import faktura, naimenovanja, ASYCUDA XML export.

## Instalacija (Windows)

1. Pokreni `DeklarantPro_Setup_2.0.0.exe`
2. Nakon instalacije, kopiraj `.env.example` → `.env` u folderu aplikacije
3. Popuni `.env` sa podacima za konekciju na PostgreSQL:

```ini
DB_HOST=server.adresa
DB_PORT=5432
DB_NAME=deklarant_pro
DB_USER=korisnik
DB_PASSWORD=sifra
```

4. Pokreni `DeklarantPro.exe`

## Razvoj

```bash
pip install -r requirements.txt
python run.py
```

Zahtevi: Python 3.11+, PostgreSQL 16.

## Tabovi

1. **Faktura** — Unos i validacija faktura
2. **Naimenovanja** — Rubrike 31-46, tarifni brojevi
3. **Zaglavlje** — Rubrike 1-49, dokumenti
4. **Šifrarnici** — Upravljanje šifrarnicima, tarifne kvote
5. **Admin** — Plugin manager, baza, analitika, logovi, podešavanja
6. **Agent** — AI asistent za import i validaciju

## Testiranje

```bash
pytest tests/ -q
```
