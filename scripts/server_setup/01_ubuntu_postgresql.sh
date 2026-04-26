#!/bin/bash
# ============================================================
# Deklarant Pro â€” Ubuntu Server: Instalacija PostgreSQL-a
# Pokrenuti kao root ili sa sudo na Ubuntu Server laoptopu
# ============================================================

set -e  # Zaustavi na prvoj greÅ¡ci

echo "===================================================="
echo "  Deklarant Pro â€” PostgreSQL Server Setup"
echo "===================================================="

# 1. AÅ¾uriranje sistema i instalacija PostgreSQL
echo ""
echo ">>> Instalacija PostgreSQL..."
apt update
apt install -y postgresql postgresql-contrib

# 2. Pokretanje i enable na startup
systemctl start postgresql
systemctl enable postgresql
echo "    PostgreSQL pokrenut i dodan u startup."

# 3. Postavljanje lozinke za postgres superusera
echo ""
echo ">>> Postavljanje lozinke za postgres korisnika..."
echo "    Unesite lozinku za PostgreSQL 'postgres' superusera:"
sudo -u postgres psql -c "\password postgres"

# 4. Kreiranje baze i korisnika za aplikaciju
echo ""
echo ">>> Kreiranje baze 'deklarant_pro' i korisnika 'deklarant_app'..."
sudo -u postgres psql -f "$(dirname "$0")/02_create_db_user.sql"

# 5. Konfiguracija mreÅ¾nog pristupa
echo ""
echo ">>> Konfiguracija mreÅ¾nog pristupa..."
PG_VERSION=$(psql --version | awk '{print $3}' | cut -d. -f1)
PG_CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"
PG_HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"

# Dozvoli sluÅ¡anje na svim interfejsima (ne samo localhost)
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"
echo "    listen_addresses = '*' postavljeno."

# Dozvoli konekcije sa LAN-a (192.168.x.x)
echo "" >> "$PG_HBA"
echo "# Deklarant Pro â€” Windows klijenti na LAN-u" >> "$PG_HBA"
echo "host    deklarant_pro    deklarant_app    192.168.0.0/16    scram-sha-256" >> "$PG_HBA"
echo "    pg_hba.conf aÅ¾uriran za LAN pristup."

# 6. Restart PostgreSQL da primijeni promjene
systemctl restart postgresql
echo "    PostgreSQL restartovan."

# 7. Firewall â€” otvori port 5432
echo ""
echo ">>> Konfiguracija firewall-a (ufw)..."
ufw allow 5432/tcp
ufw --force enable
echo "    Port 5432 otvoren."

# 8. Provjera
echo ""
echo ">>> Provjera:"
systemctl status postgresql --no-pager | grep "Active:"
echo ""
echo "===================================================="
echo "  Setup zavrÅ¡en!"
echo ""
echo "  SljedeÄ‡i korak:"
echo "  1. Na ovom serveru pokreni:"
echo "     cd /putanja/do/deklarant_pro"
echo "     bash scripts/server_setup/03_restore_db.sh"
echo ""
echo "  2. IP adresa ovog servera:"
hostname -I | awk '{print $1}'
echo "  (ovu IP upiÅ¡i u .env na Windows klijentima)"
echo "===================================================="

