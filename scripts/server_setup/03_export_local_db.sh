#!/bin/bash
# ============================================================
# Deklarant Pro — Export lokalne baze za prenos na server
# Pokrenuti sa razvoj mašine (Fedora) PRIJE preseljenja na server
# ============================================================

set -e

EXPORT_FILE="deklarant_pro_backup_$(date +%Y%m%d_%H%M%S).sql"
EXPORT_DIR="$(dirname "$0")/../../backup"
mkdir -p "$EXPORT_DIR"

echo "===================================================="
echo "  Deklarant Pro — Export baze podataka"
echo "===================================================="
echo ""
echo ">>> Eksportujem bazu 'deklarant_pro' iz lokalne instance..."

# pg_dump sa svim podacima i shemama
pg_dump \
    -U radovan \
    -d deklarant_pro \
    --format=plain \
    --no-owner \
    --no-acl \
    --schema=catalogs \
    -f "${EXPORT_DIR}/${EXPORT_FILE}"

echo "    Backup snimljen: backup/${EXPORT_FILE}"
echo ""

# Veličina fajla
SIZE=$(du -sh "${EXPORT_DIR}/${EXPORT_FILE}" | cut -f1)
echo "    Veličina: ${SIZE}"
echo ""
echo "===================================================="
echo "  Prenos na server:"
echo ""
echo "  scp backup/${EXPORT_FILE} korisnik@IP_SERVERA:~/"
echo ""
echo "  Zatim na serveru:"
echo "  bash scripts/server_setup/03_restore_db.sh ~/${EXPORT_FILE}"
echo "===================================================="
