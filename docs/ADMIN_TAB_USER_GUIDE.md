# ASYCUDA Pro - Admin Tab User Guide

## 📋 Uvod

Admin Tab je centralni panel za administraciju ASYCUDA Pro aplikacije. Omogućava upravljanje plugin-ovima, konfiguraciju, backup baze podataka, pregled logova i pristup sistemskim informacijama.

### Kako pristupiti Admin Tab-u

1. Pokrenite ASYCUDA Pro aplikaciju
2. Kliknite na posljednji tab **"⚙️ Admin"** u glavnom prozoru

---

## 📦 Plugin Manager

Plugin Manager omogućava upravljanje parserima za uvoz deklaracija.

### Instalacija novog parsera

1. Kliknite na **"📦 Plugin Manager"** u sidebar-u
2. Kliknite na dugme **"Instaliraj Novi Parser"**
3. Odaberite `.py` fajl parsera sa vašeg računara
4. Parser će biti automatski kopiran u `plugins/parsers/` direktorij
5. Kliknite **"Reload Parsera"** da aktivirate novi parser

### Pregled instaliranih parsera

- Lijeva strana prikazuje listu svih instaliranih parsera
- Desna strana prikazuje detalje o odabranom parseru:
  - Ime parsera
  - Prioritet izvršavanja
  - Klijent i firma
  - Verzija
  - Autor

### Uklanjanje parsera

1. Odaberite parser iz liste
2. Kliknite na **"Ukloni"**
3. Potvrdite brisanje u dijalogu

### Reload parsera

Nakon instalacije novog parsera ili izmjene postojećeg:
1. Kliknite na **"Reload Parsera"**
2. Svi parseri će biti ponovo učitani

---

## ⚙️ Settings

Settings panel omogućava konfiguraciju aplikacije.

### Dostupne opcije

| Opcija | Opis | Vrijednosti |
|--------|------|-------------|
| **Tema** | Izgled aplikacije | light / dark |
| **Jezik** | Jezik interfejsa | sr / en |
| **Auto Backup** | Automatsko kreiranje backup-a | Da / Ne |
| **Backup Interval** | Koliko često kreirati backup (u danima) | Broj dana |
| **Log Level** | Nivo detaljnosti logova | DEBUG, INFO, WARNING, ERROR |
| **Auto Load Plugins** | Automatsko učitavanje plugin-ova | Da / Ne |

### Čuvanje settings-a

1. Promijenite željene opcije
2. Kliknite na **"Sačuvaj Settings"**
3. Settings se čuvaju u `~/.asycuda_pro/settings.json`

---

## 💾 Database Management

Upravljanje backup-om i restore-om baze podataka.

### Kreiranje backup-a

1. Kliknite na **"💾 Database"** u sidebar-u
2. U sekciji **"Backup"** kliknite na **"Kreiraj Backup"**
3. Odaberite lokaciju i ime fajla
4. Backup će biti kreiran na odabranoj lokaciji

**Preporuka:** Čuvajte backup-e na eksternom disku ili cloud servisu.

### Restore database

1. U sekciji **"Restore"** odaberite backup fajl iz liste
2. Kliknite na **"Restore-uj Izabranu"**
3. Potvrdite upozorenje (⚠️ Trenutna baza će biti PREPISANA!)
4. Baza će biti restore-ovana iz backup-a

### Refresh liste backup-ova

Ako ste ručno dodali backup fajlove:
1. Kliknite na **"Refresh Listu"**
2. Lista će biti ažurirana

---

## 📊 Analytics

Pregled statistike korištenja aplikacije.

### Import Statistika

- **Ukupno Importa:** Ukupan broj uvezenih deklaracija
- **Danas:** Broj import-a danas
- **Ove Nedjelje:** Broj import-a ove sedmice
- **Ovog Mjeseca:** Broj import-a ovog mjeseca

### Deklaracije

- **Ukupno Deklaracija:** Ukupan broj kreiranih deklaracija
- **Po Statusu:** Pregled deklaracija grupisanih po statusu

### Parser Usage

*(Ova funkcionalnost je u razvoju)*

Prikazuje koji parseri se najčešće koriste za uvoz.

---

## 📋 Logs

Pregled i filtriranje sistemskih logova.

### Pregled logova

1. Kliknite na **"📋 Logs"** u sidebar-u
2. Logovi se prikazuju u tekstualnom polju
3. Svaki log sadrži:
   - Vremensku oznaku
   - Nivo (INFO, DEBUG, WARNING, ERROR)
   - Poruku

### Filtriranje logova

**Po nivou:**
- Odaberite nivo iz dropdown-a (INFO, DEBUG, WARNING, ERROR)

**Pretragom:**
- Ukucajte pojam u "Search" polje
- Pritisnite Enter

**Po datumu:**
- Odaberite datumski opseg ("Od" i "Do")

### Refresh logova

Kliknite na **"Refresh"** da učitate najnovije logove.

---

## ℹ️ System Info

Informacije o sistemu i aplikaciji.

### Prikazane informacije

- **Aplikacija:** Ime i verzija ASYCUDA Pro
- **Python:** Verzija Python interpretera
- **Platforma:** Operativni sistem
- **Arhitektura:** Hardverska arhitektura
- **Plugin-ovi:** Broj instaliranih plugin-ova
- **Database:** Veličina database fajla

### Kopiranje informacija

1. Kliknite na **"Kopiraj Info"**
2. Informacije su kopirane u clipboard
3. Zalijepite (Ctrl+V) u email, dokument ili bug report

---

## ⌨️ Prečice na tastaturi

| Akcija | Prečica |
|--------|---------|
| Refresh logova | F5 |
| Refresh statistike | F5 |
| Kopiraj system info | Ctrl+C (kada je System Info aktivan) |

---

## 📁 Lokacije fajlova

| Fajl/Direktorij | Opis | Lokacija |
|-----------------|------|----------|
| `settings.json` | Korisnički settings | `~/.asycuda_pro/settings.json` |
| `backups/` | Backup-ovi baze | `~/.asycuda_pro/backups/` |
| `logs/` | Log fajlovi | `~/.asycuda_pro/logs/` |
| `parsers/` | Instalirani parseri | `plugins/parsers/` |

---

## ❓ Česta pitanja

### Gdje se nalaze instalirani parseri?

Parseri se čuvaju u `plugins/parsers/` direktoriju u glavnom folderu aplikacije.

### Kako da napravim backup prije važnih operacija?

Idite na **Database** tab i kliknite na **"Kreiraj Backup"**. Preporučuje se prije:
- Većih izmjena u bazi
- Instalacije novih parsera
- Nadogradnje aplikacije

### Šta ako se pojavi greška pri učitavanju parsera?

1. Provjerite da li je parser kompatibilan sa vašom verzijom
2. Pogledajte **Logs** za detalje o grešci
3. Kontaktirajte autora parsera

### Kako da prijavim bug?

1. Idite na **System Info**
2. Kliknite na **"Kopiraj Info"**
3. Opišite problem i pošaljite uz kopirane informacije

---

## 📞 Podrška

Za tehničku podršku kontaktirajte:
- Email: support@asycuda.pro
- Dokumentacija: docs/ folder u instalaciji

---

**Verzija dokumentacije:** 1.0  
**Datum:** Mart 2026.
