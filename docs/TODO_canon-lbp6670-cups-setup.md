# TODO: Dovršiti podešavanje Canon LBP6670 na serveru (192.168.0.41)

**Status:** Driver instaliran, čeka se mrežni pristup štampaču da bi se dodao CUPS red.

## Šta je već urađeno (2026-06-07)

- ✅ Pronađen i raspakovan `linux-UFRII-drv-v630-m17n-07.tar.gz` u `~/Downloads/ufrii_extract/` na serveru
- ✅ Instaliran `.deb` paket preko apt:
  `~/Downloads/ufrii_extract/linux-UFRII-drv-v630-m17n/x64/Debian/cnrdrvcups-ufr2-uk_6.30-1.07_amd64.deb`
- ✅ Status paketa: `dpkg -l | grep cnrdrv` → `ii  cnrdrvcups-ufr2-uk  6.30-1.07  amd64` (potpuno konfigurisan)
- ✅ CUPS servis aktivan (`systemctl is-active cups` → `active`)
- ✅ PPD za tačan model dostupan: **`/usr/share/cups/model/CNRCUPSLBP6670ZK.ppd`**
  (`lpinfo -m | grep 6670` → `CNRCUPSLBP6670ZK.ppd  Canon LBP6670 UFR II`)

### Usputni problem koji je rešen
Tokom instalacije se Canon-ova `cnsetuputil2` alatka (deo postinst skripta paketa)
zaglavila čekajući unos na "orphaned" pty terminalu (jer je SSH sesija koja je
pokrenula instalaciju prekinuta usred procesa) — to je zaključalo `dpkg` u stanju
"pola-konfigurisano" (`iF`). Rešeno: pronađeni i ubijeni zaglavljeni procesi
(`kill -9` na PID-ove `cnsetuputil2`), zatim `sudo DEBIAN_FRONTEND=noninteractive
dpkg --configure -a` da se dovrši konfiguracija.

**Ako se ponovi slična greška** (zaglavljen apt/dpkg) — proveri:
```bash
ps aux | grep -iE 'apt|dpkg|cnsetuputil'
```
i ubij osirotele `cnsetuputil2`/`apt`/`sudo` procese (`sudo kill -9 <pid>`), zatim
`sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a`.

## Šta NEDOSTAJE — blokirano na mrežnom pristupu

Server **192.168.0.41** je SAMO na mreži `192.168.0.0/24`. **Nema rutu** do mreže
`192.168.100.0/24` gde se nalazi štampač (i Windows klijent na `.55`).
Provereno: `ping`/`nc` na pretpostavljenu IP `192.168.100.226` — bez odgovora,
i `ip route` na serveru ne pokazuje rutu ka toj podmreži.

### Treba prikupiti/uraditi PRE nastavka:
1. **Tačna IP adresa LBP6670** — proveriti na Windows klijentu (.55, ista mreža
   kao štampač): Postavke > Štampači, ili odštampati konfiguracionu/test stranicu
   direktno sa uređaja (menu štampača → Network Settings / IP Address).
   - Korisnik je pretpostavio `192.168.100.226`, ali NIJE potvrđeno — provera
     pokazala da ta adresa ne odgovara (možda netačna, ili je štampač ugašen).
2. **Mrežna ruta između 192.168.0.x i 192.168.100.x** — proveriti da li postoji
   ruter/gateway koji ih povezuje. Ako server ne može da dosegne tu podmrežu
   nikako, CUPS red mora biti dodat sa neke mašine koja JESTE u toj mreži
   (npr. Windows klijent .55, ili drugi uređaj na 192.168.100.x), ili treba
   podesiti routing.

## Kada se dobije tačna IP i potvrdi mrežna dostupnost — finalni korak

Dodati CUPS red preko SSH-a na server:
```bash
sudo lpadmin -p Canon_LBP6670 \
  -E \
  -v "socket://<TACNA_IP_STAMPACA>:9100" \
  -P /usr/share/cups/model/CNRCUPSLBP6670ZK.ppd \
  -D "Canon LBP6670"
```
(`socket://` = raw 9100 port; ako štampač koristi IPP, koristiti `ipp://<ip>/ipp/print`)

Provera nakon dodavanja:
```bash
lpstat -p Canon_LBP6670
lpadmin -p Canon_LBP6670 -E   # omogući red ako nije aktivan
```

## Kredencijali / pristup (za referencu)

- Server: `192.168.0.41`, user `dmpromet`, lozinka `dm2008` (SSH)
- Driver fajlovi: `~/Downloads/linux-UFRII-drv-v630-m17n-07.tar.gz` i raspakovano u `~/Downloads/ufrii_extract/`
- Connection metoda iz Claude sesije: paramiko (Python) preko `ssh.exec_command`,
  jer OpenSSH/plink/sshpass/Posh-SSH nisu dostupni za neinteraktivni unos lozinke
  na ovom Windows klijentu (`pip install paramiko` rešilo problem)
