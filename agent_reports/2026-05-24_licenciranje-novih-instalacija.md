# Licenciranje novih instalacija — Procedura

**Datum:** 2026-05-24  
**Autor:** Claude Sonnet 4.6

---

## Kontekst

Svaka nova instalacija aplikacije Deklarant Pro zahtijeva zasebnu licencu vezanu za fingerprint te mašine. Licenca se NE može kopirati između računara — mora se generisati za svaki računar posebno.

---

## Koraci za licenciranje novog računara

### Korak 1 — Instaliraj aplikaciju na novi računar

Aplikacija mora biti instalirana i `uv sync` mora biti završen prije generisanja licence.

### Korak 2 — Uzmi fingerprint novog računara

Na novom računaru (ili remote putem SSH):

```bash
cd ~/deklarant_pro
uv run python3 -c "
from core.licensing.machine_fingerprint import get_machine_fingerprint
import json
fp = get_machine_fingerprint()
print(json.dumps(fp, indent=2, ensure_ascii=False))
"
```

Primjer ispisa:
```json
{
  "machine_id": "3753AF3EB053E4793196A7FD2128DA5045B62969B29270AF46C83F36DF6ACDB3",
  "disk_id": "C80A5556C3CB5F4CF888E23E2E7D8C0C056A1AE94BAA9A63168C0C428BB1F7C1",
  "mac": "5B5B2CB8AE03DA4BA891B3A9C950402D53F31CEECD94247DF34F9CAC1CF7D916",
  "cpu": "D0C6F0FEFB22CB6A2388A2C127CFE3C33CB9A46F571D24ADB00AA585700CDA5F",
  "hostname": "B1586D462861872275D1B1F3BA22960CB823C4DD79E2692845FB4FA79840D8AB"
}
```

### Korak 3 — Generiši licencu (sa razvojnog računara)

Na razvojnom računaru gdje postoji `tools/licensing/keys/private_key.pem`:

```bash
cd ~/Desktop/deklarant_pro

uv run python3 tools/licensing/generate_license.py \
    --customer-name "Naziv firme / opis računara" \
    --customer-id "kratki_id" \
    --fingerprint-json '{"machine_id":"...","disk_id":"...","mac":"...","cpu":"...","hostname":"..."}' \
    --valid-from 2026-01-01 \
    --valid-to 2030-12-31 \
    --features full,agent \
    --output /tmp/nova_licenca.dat
```

**Parametri:**
| Parametar | Opis |
|---|---|
| `--customer-name` | Naziv firme ili opis računara (slobodan tekst) |
| `--customer-id` | Kratki identifikator bez razmaka (npr. `klijent1`, `dmserver`) |
| `--fingerprint-json` | JSON string iz Koraka 2 |
| `--valid-from` | Datum početka važenja (YYYY-MM-DD) |
| `--valid-to` | Datum isteka (YYYY-MM-DD) |
| `--features` | `full` za sve funkcije, `full,agent` uključuje i AI agenta |
| `--output` | Putanja gdje se snima `license.dat` |

### Korak 4 — Kopiraj licencu na novi računar

**Ako imaš SSH pristup:**
```bash
scp /tmp/nova_licenca.dat korisnik@IP:~/.config/deklarant_pro/license.dat
```

**Ako nemaš SSH (ručno):**
1. Kopiraj `nova_licenca.dat` na USB
2. Na novom računaru kopiraj na:
   - **Linux:** `~/.config/deklarant_pro/license.dat`
   - **Windows:** `%PROGRAMDATA%\DeklarantPro\license.dat`

### Korak 5 — Provjeri

Pokreni aplikaciju — ne smije tražiti licencu.

---

## Licencirani računari (evidencija)

| Računar | customer-id | Vrijedi do | Datum izdavanja |
|---|---|---|---|
| Razvojni laptop (radovan) | klijent1 | 2027-04-26 | 2026-04-26 |
| Ubuntu server laptop (dmserver) | dmserver | 2030-12-31 | 2026-05-24 |

---

## Važne napomene

- **Privatni ključ** se nalazi u `tools/licensing/keys/private_key.pem` — nikad ne commitovati, nikad ne dijeliti
- **Licenca je vezana za hardware** — ako se promijeni disk ili matična ploča, treba nova licenca
- **Score sistem:** fingerprint ima 5 signala (machine_id 30%, disk_id 30%, mac 15%, cpu 15%, hostname 10%) — minimalan score za validaciju je 70%
- **Bez privatnog ključa** nema generisanja licenci — čuvaj backup ključa na sigurnom mjestu

---

## Brzi referentni SSH pristup server laptopu

```bash
# Korisnik: dmpromet
# IP: 192.168.0.41
ssh dmpromet@192.168.0.41

# Uzmi fingerprint:
sshpass -p "LOZINKA" ssh dmpromet@192.168.0.41 \
  "source ~/.local/bin/env && cd ~/deklarant_pro && uv run python3 -c \
  'from core.licensing.machine_fingerprint import get_machine_fingerprint; import json; print(json.dumps(get_machine_fingerprint(), indent=2))'"
```
