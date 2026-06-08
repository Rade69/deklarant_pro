# Uputstvo: Postavljanje zajedničkog XML arhiva deklaracija

**Cilj:** Spojiti XML arhive sa oba Windows terminala u jedan centralni folder na Ubuntu serveru,
tako da AI agent na svakom terminalu ima pristup svim historijskim deklaracijama.

**Infrastruktura:**
- Ubuntu server: `192.168.0.41`
- Terminal 1 i Terminal 2: Windows mašine u lokalnoj mreži
- Aplikacija: `dist_client/` folder na svakom terminalu

---

## DIO 1 — Ubuntu server (192.168.0.41)

### Korak 1 — Kreiranje foldera za XML arhiv

Poveži se na server putem SSH ili direktno na terminalu:

```bash
ssh radovan@192.168.0.41
```

Kreiraj folder za zajednički arhiv:

```bash
sudo mkdir -p /srv/deklarant/xml_archive
sudo chown radovan:radovan /srv/deklarant/xml_archive
sudo chmod 775 /srv/deklarant/xml_archive
```

### Korak 2 — Instalacija Samba (ako nije instalirana)

```bash
sudo apt update
sudo apt install samba -y
```

Provjeri da li Samba radi:

```bash
sudo systemctl status smbd
```

### Korak 3 — Konfiguracija Samba sharea

Otvori Samba konfiguraciju:

```bash
sudo nano /etc/samba/smb.conf
```

Na kraj fajla dodaj sljedeće (ne mijenjaj ništa što već postoji):

```ini
[xml_archive]
   path = /srv/deklarant/xml_archive
   browseable = yes
   read only = no
   guest ok = no
   valid users = radovan
   create mask = 0664
   directory mask = 0775
   force group = radovan
```

Sačuvaj i zatvori (`Ctrl+X`, zatim `Y`, zatim `Enter`).

### Korak 4 — Samba lozinka za korisnika

```bash
sudo smbpasswd -a radovan
```

Unesi lozinku (može biti ista kao sistemska, ili nova — zapamti je, treba na terminalima).

### Korak 5 — Restart Samba servisa

```bash
sudo systemctl restart smbd
sudo systemctl enable smbd
```

### Korak 6 — Dozvole u firewallu (ako je UFW aktivan)

```bash
sudo ufw allow samba
sudo ufw status
```

### Korak 7 — Provjera sharea

Na serveru provjeri da li je share vidljiv:

```bash
smbclient -L localhost -U radovan
```

Trebao bi vidjeti `xml_archive` u listi.

---

## DIO 2 — Kopiranje XML fajlova na server

### Sa svakog Windows terminala

Na terminalu otvori **File Explorer** i u adresnu traku upiši:

```
\\192.168.0.41\xml_archive
```

Unesi Samba korisničko ime `radovan` i lozinku koju si postavio u Koraku 4.

Zatim kopiraj sadržaj NOVA ASIKUDA foldera sa terminala na server:

- **Terminal 1:** Kopiraj sve XML fajlove iz:
  ```
  C:\[putanja do dist_client]\data\knowledge_base\NOVA ASIKUDA\
  ```
  direktno u `\\192.168.0.41\xml_archive\`

- **Terminal 2:** Kopiraj XML fajlove sa drugog terminala na isti share.
  Ako se pojavi pitanje o prepisivanju fajla istog naziva — odaberi **"Uporedi informacije"** (ne prepiši automatski),
  pa zadrži veći / noviji fajl.

> **Napomena:** Fajlovi sa istim imenom a različitim sadržajem su različite deklaracije.
> U tom slučaju preimenuj fajlove sa terminala 2 dodavanjem sufiksa, npr. `1 MAJ CIGLA_T2.xml`.

---

## DIO 3 — Merge skripta (opciono, preporučeno)

Umjesto ručnog kopiranja sa upozorenjem o prepisivanju,
možeš pokrenuti Python skriptu koja automatski deduplikuje XML fajlove.

Kreiraj fajl `merge_xml_archive.py` na serveru:

```bash
nano /srv/deklarant/merge_xml_archive.py
```

Sadržaj skripte:

```python
#!/usr/bin/env python3
"""
Spaja XML arhive sa dva terminala bez gubitka podataka.
Deduplikacija po ASYCUDA id atributu gdje je dostupan,
po sadrzaju fajla gdje nije.
"""

import hashlib
import re
import shutil
import sys
from pathlib import Path

# Folderi — prilagodi putanje
TERMINAL1 = Path("/mnt/terminal1/NOVA ASIKUDA")   # mount point ili lokalni folder
TERMINAL2 = Path("/mnt/terminal2/NOVA ASIKUDA")   # mount point ili lokalni folder
OUTPUT    = Path("/srv/deklarant/xml_archive")

OUTPUT.mkdir(parents=True, exist_ok=True)


def get_asycuda_id(xml_path: Path) -> str | None:
    """Čita ASYCUDA id iz XML fajla ako postoji."""
    try:
        with open(xml_path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 5:
                    break
                m = re.search(r'ASYCUDA id="(\d+)"', line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def file_hash(path: Path) -> str:
    """MD5 hash sadrzaja fajla za provjeru duplikata."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def copy_safe(src: Path, dest_dir: Path, prefix: str = "") -> str:
    """Kopira fajl, dodaje prefiks ako postoji konflikt."""
    name = (prefix + src.name) if prefix else src.name
    dest = dest_dir / name

    if not dest.exists():
        shutil.copy2(src, dest)
        return "kopirano"

    if file_hash(src) == file_hash(dest):
        return "preskoceno (identično)"

    # Konflikt — isti naziv, različit sadrzaj
    stem = src.stem
    suffix = src.suffix
    counter = 2
    while dest.exists():
        dest = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    shutil.copy2(src, dest)
    return f"preimenovano u {dest.name}"


def merge_folder(source: Path, label: str):
    if not source.exists():
        print(f"  PRESKOCENO: {source} ne postoji")
        return

    xml_files = list(source.glob("*.xml"))
    print(f"\n  {label}: {len(xml_files)} XML fajlova")

    by_id   = {}   # asycuda_id → src_path
    no_id   = []   # fajlovi bez ASYCUDA id

    for f in xml_files:
        aid = get_asycuda_id(f)
        if aid:
            if aid not in by_id:
                by_id[aid] = f
            else:
                print(f"    Duplikat po ID {aid}: {f.name} — preskacam")
        else:
            no_id.append(f)

    # Kopiraj fajlove sa ASYCUDA id (preименovano po ID-u)
    copied = skipped = renamed = 0
    for aid, src in by_id.items():
        dest = OUTPUT / f"{aid}.xml"
        if not dest.exists():
            shutil.copy2(src, dest)
            copied += 1
        elif file_hash(src) == file_hash(dest):
            skipped += 1
        else:
            shutil.copy2(src, dest)
            copied += 1

    # Kopiraj fajlove bez ASYCUDA id (po originalnom imenu)
    for src in no_id:
        rezultat = copy_safe(src, OUTPUT)
        if "kopirano" in rezultat:
            copied += 1
        elif "preskoceno" in rezultat:
            skipped += 1
        else:
            renamed += 1

    print(f"    Kopirano: {copied}, Preskoceno: {skipped}, Preimenovano: {renamed}")


print("=" * 60)
print("  Merge XML arhiva")
print("=" * 60)

merge_folder(TERMINAL1, "Terminal 1")
merge_folder(TERMINAL2, "Terminal 2")

total = len(list(OUTPUT.glob("*.xml")))
print(f"\n  Ukupno XML fajlova u arhivu: {total}")
print("  Gotovo.")
```

Pokretanje skripte:

```bash
python3 /srv/deklarant/merge_xml_archive.py
```

---

## DIO 4 — Podešavanje na Windows terminalima

### Korak 1 — Mapiranje mrežnog diska (preporučeno)

U **File Exploreru** → desni klik na "Ovaj računar" → "Mapiraj mrežni disk":

- Slovo diska: `Z:`
- Folder: `\\192.168.0.41\xml_archive`
- Označi: "Poveži se pri prijavi"
- Unesi korisničko ime: `radovan` i Samba lozinku

### Korak 2 — Izmjena .env fajla

Otvori `.env` fajl koji se nalazi u korijenu aplikacije
(isti folder gdje je `run.py` i `start_silent.vbs`):

```
XML_ARCHIVE_DIR=Z:\
```

Ili bez mapiranog diska, direktno UNC putanjom:

```
XML_ARCHIVE_DIR=\\192.168.0.41\xml_archive
```

> **Napomena:** Ako koristiš UNC putanju bez mapiranog diska, Samba autentifikacija mora
> biti podešena da ne traži lozinku svaki put (Windows Credential Manager).

### Korak 3 — Dodavanje Samba kredencijala u Windows

Da Windows automatski pristupi shareu bez pitanja za lozinku:

1. Otvori **Start** → pretraži "Credential Manager" (Upravljanje akreditivima)
2. Klikni "Windows Credentials" → "Add a Windows credential"
3. Unesi:
   - Internet or network address: `192.168.0.41`
   - User name: `radovan`
   - Password: (Samba lozinka)

### Korak 4 — Brisanje starog declaration_index.db

Aplikacija čuva lokalni indeks XML fajlova. Nakon promjene `XML_ARCHIVE_DIR`
treba obrisati stari indeks da se izgradi novi sa centralizovanog foldera:

```
C:\[putanja do dist_client]\data\knowledge_base\declaration_index.db
```

Obriši taj fajl. Aplikacija će pri sljedećem pokretanju AI agenta automatski
izgraditi novi indeks (jednom, traje 30-60 sekundi).

### Korak 5 — Provjera

Pokreni aplikaciju → otvori tab **"Pametna pomoć"** → postavi bilo koji upit o robi.

Ako AI agent odgovori sa prijedlogom tarifnog broja — konfiguracija je uspješna.

---

## Provjera na serveru

U bilo kom trenutku možeš provjeriti koliko XML fajlova je u arhivu:

```bash
ls /srv/deklarant/xml_archive/*.xml | wc -l
```

I da li je Samba share aktivan:

```bash
sudo systemctl status smbd
```

---

## Sažetak

| Ko | Šta | Alat |
|----|-----|------|
| **Server** | Kreirati folder + Samba share + Samba lozinka | SSH terminal |
| **Terminal 1** | Kopirati NOVA ASIKUDA → server | File Explorer |
| **Terminal 2** | Kopirati NOVA ASIKUDA → server (merge) | File Explorer |
| **Oba terminala** | Dodati `XML_ARCHIVE_DIR` u `.env` | Notepad |
| **Oba terminala** | Obrisati stari `declaration_index.db` | File Explorer |
| **Oba terminala** | Pokrenuti aplikaciju i testirati AI agenta | Aplikacija |
