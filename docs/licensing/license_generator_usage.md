# License Generator Usage

Ovaj dokument opisuje kako koristiti `tools/licensing/generate_license.py`
za legacy `machine_id` licence i novi fingerprint mode.

## 1) Legacy mode (machine ID)

Koristi kada imas samo `DKP-...` identifikator:

```bash
python tools/licensing/generate_license.py \
  --customer-name "Firma Legacy" \
  --customer-id "LEG001" \
  --machine-id "DKP-AAAA-BBBB-CCCC-DDDD-EEEE" \
  --valid-from "2026-05-01" \
  --valid-to "2027-05-01" \
  --features "full" \
  --output "licenses/LEG001_license.dat"
```

## 2) Fingerprint mode (preporuceno)

U Deklarant Pro klijentu koristi "Kopiraj fingerprint", sacuvaj JSON u fajl, pa:

```bash
python tools/licensing/generate_license.py \
  --customer-name "Firma FP" \
  --customer-id "FP001" \
  --fingerprint-file "/tmp/fingerprint.json" \
  --min-score 70 \
  --valid-from "2026-05-01" \
  --valid-to "2027-05-01" \
  --features "full" \
  --output "licenses/FP001_license.dat"
```

Napomena:
- Ako fingerprint JSON vec sadrzi `min_score`, taj broj se koristi.
- `--min-score` sluzi kao fallback kada ga fingerprint payload nema.

## 3) Inline fingerprint JSON

Ako ne zelis fajl:

```bash
python tools/licensing/generate_license.py \
  --customer-name "Firma Inline" \
  --customer-id "FP002" \
  --fingerprint-json '{"fingerprint":{"machine_id":"...","disk_id":"..."},"min_score":70}' \
  --valid-from "2026-05-01" \
  --valid-to "2027-05-01" \
  --features "full,agent" \
  --output "licenses/FP002_license.dat"
```

## 4) Pravila i validacija

- Mora biti zadat jedan od modova:
  - `--machine-id`
  - `--fingerprint-json` ili `--fingerprint-file`
- Ne smije se kombinovati `machine_id` i fingerprint u istoj komandi.
- `license.dat` se potpisuje private key-em iz:
  - `tools/licensing/keys/private_key.pem`

## 5) Brza provjera

```bash
python tools/licensing/generate_license.py --help
```

