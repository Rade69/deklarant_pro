# Deklarant Pro — Procedura za incident

**Za:** Operatere i administratora  
**Primjenjivo:** Kada aplikacija ne radi ispravno

---

## Brzi vodič — Šta uraditi kada nešto ne radi

### 1. Ne mogu pokrenuti aplikaciju

**Simptom:** Dvostruki klik na ikonu — ništa se ne dešava ili se prozor odmah zatvori.

**Koraci:**
1. Pokušajte pokrenuti ponovo (pričekajte 30 sekundi između pokušaja)
2. Provjerite je li server uključen
3. Restartujte računar
4. Ako i dalje ne radi — pozovite administratora

---

### 2. Aplikacija se pokrenula ali ne vidi bazu (crveno "Nije povezan")

**Simptom:** U donjem uglu piše crveno, ne možete uvesti fakturu.

**Koraci:**
1. Provjerite je li Ubuntu server uključen
2. Provjerite mrežnu vezu (otvorite browser — učitava li se neka stranica?)
3. Pričekajte 2 minute i provjerite ponovo — server se možda pokretao
4. Ako traje duže od 5 minuta — pozovite administratora

---

### 3. Aplikacija se zamrzla / ne reaguje

**Simptom:** Kliknete dugme ali se ništa ne dešava, prozor je siv.

**Koraci:**
1. Pričekajte 60 sekundi — možda se učitava veliki fajl
2. Ako i dalje ne reaguje: zatvorite aplikaciju (Alt+F4 ili X u uglu)
3. Pokrenite ponovo
4. Provjerite da li uvoz koji ste pokrenuli ima smisla (nije li PDF prevelik ili oštećen?)

---

### 4. Uvoz fakture je prošao ali podaci izgledaju pogrešno

**Simptom:** Stavke su uvezene, ali nazivi/cijene/težine nisu ispravne.

**Koraci:**
1. Provjerite je li ovo ispravna faktura od poznatog dobavljača
2. Ručno ispravite pogrešne vrijednosti (dvostruki klik na ćeliju)
3. Zabilježite naziv fakture i šta je pogrešno — javite administratoru
4. Administrator će provjeriti/popraviti parser za taj dobavljač

---

### 5. XML export ne radi

**Simptom:** Kliknete "Export XML" ali dobijete grešku ili se fajl ne kreira.

**Koraci:**
1. Provjerite da li svako naimenovanje ima tarifni broj (mora biti 8 cifara)
2. Provjerite da li je zaglavlje popunjeno i snimljeno
3. Provjerite da li folder u koji exportate postoji i da imate pravo pisanja
4. Pogledajte poruke u crvenom — one govore šta nedostaje

---

### 6. Aplikacija se srušila (zatvorila se sama)

**Simptom:** Prozor se zatvorio bez upozorenja.

**Koraci:**
1. Pokrenite aplikaciju ponovo
2. Podaci su sačuvani u bazi — ne bi trebalo biti gubitka
3. Zabilježite što ste radili u trenutku rušenja
4. Javite administratoru što ste radili — log fajl sa greškom će biti dostupan

---

## Kontakt

| Situacija | Kontakt |
|-----------|---------|
| Aplikacija ne radi > 10 minuta | Radovan |
| Server nedostupan | Radovan |
| Greška pri exportu za Asycudu | Radovan |
| Pitanje o tarifnim brojevima | Interni carinski stručnjak |

---

## Za administratora — Gdje su logovi

Log fajlovi aplikacije nalaze se u:

```
# Linux
~/.local/share/deklarant_pro/logs/

# Windows
%APPDATA%\deklarant_pro\logs\
```

Fajl se zove `deklarant_pro_YYYY-MM-DD.log`. Zadnji log je uvijek najrelevantiji.

Greške su označene sa `ERROR`, upozorenja sa `WARNING`.

---

*Ovaj dokument ažurirati kada se pojavi novi tip incidenta koji nije pokriven.*
