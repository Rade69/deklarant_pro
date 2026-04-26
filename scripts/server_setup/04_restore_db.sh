#!/bin/bash
# ============================================================
# Deklarant Pro â€” Restore baze na Ubuntu Server
# Pokrenuti NA SERVERU nakon Å¡to je backup fajl prenesen
#
# Upotreba:
#   bash scripts/server_setup/04_restore_db.sh ~/deklarant_pro_backup_DATUM.sql
# ============================================================

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "GreÅ¡ka: Nije naveden backup fajl."
    echo "Upotreba: bash 04_restore_db.sh /putanja/do/backup.sql"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "GreÅ¡ka: Fajl ne postoji: $BACKUP_FILE"
    exit 1
fi

echo "===================================================="
echo "  Deklarant Pro â€” Restore baze podataka"
echo "===================================================="
echo ""
echo ">>> Restoring: $BACKUP_FILE"
echo "    Unesite lozinku za deklarant_app korisnika:"

psql \
    -U deklarant_app \
    -d deklarant_pro \
    -h localhost \
    -f "$BACKUP_FILE"

echo ""
echo ">>> Provjera:"
psql -U deklarant_app -d deklarant_pro -h localhost -c "
    SELECT schemaname, tablename,
           (SELECT COUNT(*) FROM catalogs.zvanicna_tarifa) as tarifa_count
    FROM pg_tables
    WHERE schemaname = 'catalogs'
    LIMIT 5;
"

echo ""
echo "===================================================="
echo "  Restore zavrÅ¡en!"
echo "  Sada postavi .env na Windows klijentima:"
echo ""
echo "  DB_HOST=$(hostname -I | awk '{print $1}')"
echo "  DB_PORT=5432"
echo "  DB_NAME=deklarant_pro"
echo "  DB_USER=deklarant_app"
echo "  DB_PASSWORD=tvoja_lozinka"
echo "===================================================="

