# Deklarant Pro — Instalacija na Windows

> **Za Radovana** — tačna procedura, korak po korak.  
> Datum: 2026-05-29

---

## Šta ti treba prije početka

- USB sa `DeklarantPro_Windows_Setup.zip` fajlom
- Windows računar (IP: 192.168.100.55) spojen na mrežu
- Server (`192.168.0.41`) mora biti upaljen i dostupan

---

## KORAK 1 — Raspakuj ZIP sa USB-a

1. Ubaci USB u Windows računar
2. Pronađi `DeklarantPro_Windows_Setup.zip`
3. Desni klik → **Extract All** (Izdvoji sve)
4. Kao destinaciju odaberi: `C:\Users\dm promet\Desktop\`
5. Klikni **Extract**

Nakon toga na Desktopu ćeš imati folder `deklarant_pro`.

---

## KORAK 2 — Pokreni postavljanje okruženja

1. Otvori folder `deklarant_pro` na Desktopu
2. Pronađi fajl **`setup_windows_venv.bat`**
3. Desni klik → **Pokreni kao administrator** (Run as administrator)
4. Klikni **Da** ako Windows pita za dozvolu

Skripta automatski radi sljedeće:
- Provjeri da Python postoji
- Kreira izolovano Python okruženje (`.venv` folder)
- Preuzme i instalira sve potrebne biblioteke sa interneta
- Kreira `.env` konfiguracioni fajl i otvori ga u Notepadu
- Testira konekciju na bazu podataka

**Može trajati 5–10 minuta** dok se paketi preuzimaju. Čekaj dok ne vidiš poruku `Postavljanje završeno!`

---

## KORAK 3 — Provjeri .env konfiguraciju

Kada skripta otvori Notepad sa `.env` fajlom, provjeri da piše:

```
DB_HOST=192.168.0.41
DB_PORT=5432
DB_NAME=deklarant_pro
DB_USER=radovan
DB_PASSWORD=postgres
CLIENT_NAME=dmwindows
```

Ako je sve u redu — **sačuvaj i zatvori** Notepad (`Ctrl+S`, pa `Alt+F4`).

> Ako server ima drugu IP adresu, promijeni `DB_HOST`.

---

## KORAK 4 — Uzmi fingerprint računara (za licencu)

1. Otvori folder `deklarant_pro` na Desktopu
2. Drži `Shift` + desni klik na prazan prostor u folderu
3. Odaberi **"Otvori PowerShell ovdje"** (ili "Open PowerShell window here")
4. Upiši i pritisni Enter:

```powershell
.\.venv\Scripts\python.exe -c "from core.licensing.machine_fingerprint import get_machine_fingerprint; import json; print(json.dumps(get_machine_fingerprint(), indent=2))"
```

5. Selektuj i kopiraj cijeli ispis koji izgleda ovako:
```json
{
  "machine_id": "3753AF3EB053...",
  "disk_id": "C80A5556C3CB...",
  "mac": "5B5B2CB8AE03...",
  "cpu": "D0C6F0FEFB22...",
  "hostname": "B1586D462861..."
}
```

6. Pošalji taj JSON tekst na Radovana (poruka, email, ili preko Claude Code agenta)

---

## KORAK 5 — Generiši licencu (radi Radovan na Linux laptopu)

**Ovo radi Radovan na svom laptpu**, ne ti:

```bash
cd /home/radovan/Desktop/deklarant_pro

uv run python3 tools/licensing/generate_license.py \
    --customer-name "DM Promet — Windows klijent" \
    --customer-id "dmwindows" \
    --fingerprint-json '{ ... JSON koji si dobio u Koraku 4 ... }' \
    --valid-from 2026-01-01 \
    --valid-to 2030-12-31 \
    --features full,agent \
    --output /tmp/dmwindows_licenca.dat
```

Radovan ti šalje nazad fajl `dmwindows_licenca.dat`.

---

## KORAK 6 — Kopiraj licencu

1. Uzmi fajl `dmwindows_licenca.dat` (od Radovana, USB ili mreža)
2. Na Windows računaru otvori **File Explorer** (Windows Explorer)
3. U adresnu traku upiši: `C:\ProgramData` i pritisni Enter
4. Ako ne postoji folder `DeklarantPro` — klikni desni klik → **New Folder** → nazovi ga `DeklarantPro`
5. Uđi u folder `DeklarantPro`
6. Kopiraj `dmwindows_licenca.dat` u taj folder
7. **Preimenuj** ga u `license.dat`

Rezultat: `C:\ProgramData\DeklarantPro\license.dat`

---

## KORAK 7 — Pokreni aplikaciju

1. Otvori folder `deklarant_pro` na Desktopu
2. Dvostruki klik na **`start_silent.vbs`**
3. Aplikacija se otvara — **bez crnog CMD prozora**, samo GUI

Ako aplikacija traži licencu → vrati se na Korak 6.  
Ako ne može spojiti na bazu → provjeri da je server (`192.168.0.41`) upaljen.

---

## KORAK 8 — Napravi prečicu na Desktopu (opcionalno)

Da ne moraš uvijek ulaziti u folder:

1. Desni klik na `start_silent.vbs`
2. Odaberi **"Create shortcut"** (Napravi prečicu)
3. Premjesti prečicu na Desktop
4. Desni klik na prečicu → **Properties** (Svojstva) → **Change Icon** (Promijeni ikonu)
5. Pronađi `deklarant_pro\assets\icons\app_icon.ico` (ako postoji)

---

## Pokretanje za debugiranje (ako nešto ne radi)

Ako aplikacija ne radi, pokreni ovu varijantu koja pokazuje greške:

1. Dvostruki klik na **`start_debug.bat`**
2. Otvara se crni prozor sa aplikacijom
3. Greška će biti ispisana u tom prozoru
4. Fotografiši ekran i pošalji Radovanu

---

## Kratki update procedure (nova verzija koda)

Kada Radovan napravi izmjene u aplikaciji:

1. Radovan pokreće `nadogradi_windows.sh` sa svog laptopa
2. Izmijenjeni fajlovi se automatski kopiraju putem mreže
3. Zatvoriš i ponovo otvoriš aplikaciju — nova verzija je aktivna

Nema reinstalacije, nema ZIP-a, nema čekanja.

---

## Pregled fajlova u projektu

| Fajl | Namjena |
|---|---|
| `setup_windows_venv.bat` | Jednom pokreni za instalaciju |
| `start_silent.vbs` | Svakodnevno pokretanje (bez terminala) |
| `start_debug.bat` | Pokretanje sa prikazom grešaka |
| `.env` | Konfiguracija (baza, API ključevi) |
| `.venv\` | Python biblioteke (automatski kreiran) |
| `run.py` | Glavni pokretač aplikacije |

---

## Kredencijali i kontakti

| Šta | Vrijednost |
|---|---|
| Ovaj Windows računar | IP: `192.168.100.55`, user: `dm promet`, pass: `1` |
| Server (baza podataka) | IP: `192.168.0.41` |
| Razvojni laptop | IP: `192.168.100.131` |

---

## Ako nešto ne radi — provjeri redom

1. **Python nije pronađen** → Reinstaliraj Python 3.11 sa python.org, označi "Add to PATH"
2. **Instalacija paketa pala** → Provjeri internet konekciju, ponovi `setup_windows_venv.bat`
3. **Konekcija na bazu pala** → Je li server (192.168.0.41) upaljen? Je li .env ispravan?
4. **Aplikacija traži licencu** → Je li `C:\ProgramData\DeklarantPro\license.dat` tu?
5. **Ostale greške** → Pokretaj `start_debug.bat`, fotografiši i pošalji Radovanu
