# Deklarant Pro — Instalacijska procedura

**Za:** Administratora sistema  
**Primjenjivo na:** Novi Windows/Linux terminal koji se spaja na postojeći PostgreSQL server

---

## Preduvjeti

- Ubuntu/Windows računar sa pristupom lokalnoj mreži
- Python 3.11 ili noviji (`python3 --version`)
- `uv` package manager (`uv --version`)
- Pristup PostgreSQL serveru (IP adresa, port, korisničko ime, lozinka)
- Git (`git --version`)

---

## Korak 1 — Preuzimanje koda

```bash
git clone <repo-url> deklarant_pro
cd deklarant_pro
```

Ili kopirajte folder sa postojećeg računara.

---

## Korak 2 — Instalacija zavisnosti

```bash
uv sync
```

Ovo instalira sve Python pakete. Može trajati 2-5 minuta pri prvom pokretanju.

Provjeri da je sve OK:

```bash
uv run python -c "import PySide6; print('PySide6 OK')"
```

---

## Korak 3 — Konfiguracija baze podataka

Kopirajte `.env.example` u `.env`:

```bash
cp .env.example .env
```

Na Windows PowerShellu:

```powershell
Copy-Item .env.example .env
```

Otvorite `.env` u tekst editoru i popunite podatke za PostgreSQL server:

```dotenv
DB_HOST=192.168.1.100
DB_PORT=5432
DB_NAME=deklarant_pro
DB_USER=deklarant_app
DB_PASSWORD=VAŠA_LOZINKA
DB_SSLMODE=prefer
```

**Važno:** Ne koristite istu lozinku kao u git historiji — rotirana je. Tražite aktuelnu lozinku od administratora.

Ako pokrećete aplikaciju iz `dist_client`, njegova konfiguracija je zaseban fajl
`dist_client/.env`. Promjena korijenskog `.env` tada nema uticaja na aplikaciju.

---

## Korak 4 — Provjera konekcije

```bash
uv run python -c "from database.db import get_db_connection; get_db_connection(); print('DB OK')"
```

Ako vidite `DB OK` — konekcija radi. Ako vidite grešku, provjerite:
- Je li server uključen i dostupan (`ping 192.168.1.100`)
- Je li lozinka ispravna
- Je li port 5432 otvoren (firewall)

---

## Korak 5 — Pokretanje aplikacije

```bash
uv run python run.py
```

Ili kreirajte shell skriptu za lakše pokretanje:

```bash
# start.sh
#!/bin/bash
cd /putanja/do/deklarant_pro
uv run python run.py
```

Na Windowsu kreirajte `start.bat`:

```batch
cd C:\putanja\do\deklarant_pro
uv run python run.py
```

---

## Korak 6 — Provjera licence

Pri prvom pokretanju aplikacija provjerava licencu. Ako prikaže poruku o licenci:
1. Otvorite tab **"⚙️ Admin"**
2. Kliknite na **"Licensing"**
3. Uvezite licencni fajl koji ste dobili od administratora

---

## Korak 7 — Smoke test

Potvrdite da sve radi:

1. Pokrenite aplikaciju
2. Provjerite da piše zeleno **"Povezan"** u donjem desnom uglu
3. Otvorite tab **"Faktura"** i uvezite jednu testnu fakturu
4. Provjerite da se stavke pojavljuju u tabeli

---

## Ažuriranje aplikacije

Kada izlazi nova verzija:

```bash
git pull
uv sync
```

Pokrenite aplikaciju normalno — baza podataka se ažurira automatski ako je potrebno.

---

## Uklanjanje/reinstalacija

```bash
# Ukloni instaliranu okolinu
uv clean

# Reinstaliraj
uv sync
```

`.env` se ne briše automatski — sačuvajte ga ako reinstalirate.

---

*Za probleme pri instalaciji obratite se Radovanu.*
