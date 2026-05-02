# Instrukcija za agenta: pisanje koda koji se može razumjeti

**Datum:** 2026-04-14  
**Primjena:** Sve verzije agenata koji pišu ili mijenjaju kod

---

## Zašto ovo postoji

AI-generisan kod prolazi testove i stiže u produkciju — ali ga niko ne razumije u potpunosti.  
Ne inženjer koji ga je isporučio. Ne tim koji ga održava.

Ovo se zove **dark code**: kod koji nikad nije bio razumljiv ni jednom čovjeku ni u jednom trenutku.

Nije problem u kvalitetu. Nije problem u sigurnosti. Problem je u razumijevanju.

Tvoj zadatak nije samo da napišeš kod koji radi — nego da napišeš kod koji **može biti razumljen** bez čitanja svake linije.

---

## Osnovno pravilo

Za svaku funkcionalnu cjelinu koju uvediš ili značajno izmijeniš, uradiš dvije stvari:

1. U kodu dodaš **kratku sekcijsku oznaku** koja pokazuje na dokumentaciju.
2. U dokumentaciji objasniš **namjeru, odluke i rizike** — ne mehaničko ponašanje.

---

## Kada se ovo primjenjuje

**Primjenjuje se kada:**
- uvodeš novi servis, klasu ili modul
- dodaješ novu poslovnu logiku ili validaciju
- uvodiš novu integraciju ili vanjsku zavisnost
- mijenjaš workflow na način koji mijenja ponašanje sistema
- pišeš kod koji će drugi agent ili developer kasnije morati mijenjati

**Ne primjenjuje se za:**
- helper funkcije bez poslovne logike
- kozmetičke izmjene i preimenovanja
- bugfix koji ne mijenja strukturu ni ponašanje

---

## Format sekcijske oznake u kodu

Dodaj header iznad svake dokumentovane cjeline. Kratko, čitljivo, pretraživo.

**Python:**
```python
# ============================================================
# SECTION: order-payment-validation
# PURPOSE: Validates payment data before order persistence
# DOC: docs/sections/order-payment-validation.md
# ============================================================
```

**JavaScript / TypeScript:**
```javascript
// ============================================================
// SECTION: tariff-suggestion-flow
// PURPOSE: Builds and validates tariff suggestions from customs data
// DOC: docs/sections/tariff-suggestion-flow.md
// ============================================================
```

**Pravila za oznaku:**
- `SECTION` — stabilan, jedinstven naziv cjeline (kebab-case)
- `PURPOSE` — jedna rečenica, šta cjelina radi i zašto
- `DOC` — stvarna putanja do `.md` fajla koji postoji ili će biti kreiran
- Oznaka je kratka — nije esej

---

## Gdje se čuva dokumentacija

```
docs/sections/    ← tehnička cjelina unutar koda
docs/features/    ← feature ili poslovna funkcionalnost
docs/workflows/   ← tok rada ili proces
```

Naziv fajla mora odgovarati nazivu iz `SECTION` polja u kodu.

---

## Šta `.md` dokument mora sadržavati

Dokument mora odgovoriti na četiri pitanja. Ništa više.

### 1. Svrha
Šta ova cjelina radi, zašto postoji i koji problem rješava.  
*Ne opisuj mehaničko ponašanje koje se vidi iz koda.*

### 2. Zavisnosti i pretpostavke
Od kojih servisa, modula ili modela zavisi.  
Koje pretpostavke moraju biti istinite da bi cjelina radila ispravno.

### 3. Pravila i granice
Koja poslovna ili tehnička pravila ova cjelina mora poštovati.  
Šta se ne smije promijeniti bez razumijevanja posljedica.  
Koje su tipične greške ili mjesta gdje se lako nešto pokvari.

### 4. Zašto je implementirano baš ovako
Koji trade-off je prihvaćen.  
Koje alternative su razmatrane i zašto su odbačene.  
Kako provjeriti da li izmjena nije pokvarila ponašanje.

---

## Primjer `.md` dokumenta

**Fajl:** `docs/sections/order-payment-validation.md`

```md
# Order Payment Validation

## Svrha
Provjerava da li podaci o plaćanju ispunjavaju minimalne uslove
prije upisa narudžbe u bazu. Odvaja validaciju od UI sloja
da bi bila testabilna i pregledna nezavisno od forme.

## Zavisnosti i pretpostavke
- PaymentService mora biti inicijalizovan prije poziva
- Korisnik mora imati aktivan session sa validnim customer_id
- Iznos mora biti izražen u osnovnoj valuti (KM), konverzija se
  obavlja ranije u toku prije nego ova cjelina bude pozvana

## Pravila i granice
- Narudžba se ne smije upisati ako postoji kritična greška plaćanja
- Upozorenja (warnings) ne blokiraju upis — samo se loguju
- Redosljed provjera je bitan: iznos → metoda → limit
  Promjena redosljeda može promijeniti ponašanje za edge case-ove
- Ne smije se tiho gutati PaymentValidationError — mora se propagirati

## Zašto ovako
Validacija je izvučena iz OrderService jer je testiranje
narudžbi bez validacije plaćanja bilo nemoguće u izolaciji.
Alternativa je bila inline validacija u servisu — odbijena
jer bi svaki test narudžbe zahtijevao mock payment gateway-a.
Provjera: pokrenuti test suite za PaymentValidationService,
posebno scenarije sa iznosom 0 i neaktivnom platnom metodom.
```

---

## Pravilo ažuriranja

Ako mijenjаš cjelinu koja već ima `.md` fajl:

1. Pročitaj postojeći dokument **prije** izmjene koda.
2. Nakon izmjene, ažuriraj dokument ako se logika, zavisnosti ili pravila promijenila.
3. Kod i dokumentacija moraju uvijek opisivati isti sistem.

**Strogo pravilo:** Ako se ponašanje promijeni, mora se promijeniti i dokumentacija.  
Neusklađena dokumentacija je gora od nepostojeće.

---

## Šta agent ne smije pisati u dokumentaciji

- Prepričavanje koda liniju po liniju
- Generičke rečenice bez konkretne vrijednosti ("ova funkcija obrađuje podatke")
- Opis očiglednih stvari koje se vide direktno iz koda
- Dokumentaciju koja nije vezana za stvarni kod

---

## Format završnog izvještaja

Kada isporučuješ izmjene koje uključuju dokumentaciju, navedi:

```
DOKUMENTACIJA:
- Dodano: docs/sections/naziv.md
- Ažurirano: docs/sections/drugi-naziv.md
- Bez dokumentacije: [naziv cjeline] — razlog zašto nije potrebna
```

---

## Jedna rečenica za pamćenje

Kod pokazuje **šta** sistem radi.  
Dokumentacija objašnjava **zašto** je napravljen baš tako — i šta će se pokvariti ako ga neko promijeni bez razumijevanja.
