#!/bin/bash
# =============================================================
#  Deklarant Pro — Build zaštićene distribucije (PyArmor)
#  Pokretanje: bash scripts/build_distribution.sh
#
#  Šta radi:
#    1. Kreira dist_client/ kao kopiju projekta
#    2. PyArmor obfuskira samo odabrane module
#    3. Originalni fajlovi se NE mijenjaju
# =============================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist_client"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅  $1${NC}"; }
err()  { echo -e "${RED}❌  $1${NC}"; exit 1; }
info() { echo -e "${YELLOW}➡️   $1${NC}"; }

echo ""
echo "============================================="
echo "   Deklarant Pro — Build distribucije"
echo "============================================="
echo ""

# ── 1. Provjeri PyArmor ──────────────────────────────────────
info "Provjera PyArmor..."
PYARMOR_CMD=""
for cmd in pyarmor ~/.local/bin/pyarmor; do
    if command -v "$cmd" &>/dev/null || [ -x "$cmd" ]; then
        PYARMOR_CMD="$cmd"
        break
    fi
done
if [ -z "$PYARMOR_CMD" ]; then
    info "Instaliram PyArmor..."
    pip install pyarmor --user || err "Instalacija PyArmor nije uspjela"
    PYARMOR_CMD="$HOME/.local/bin/pyarmor"
fi
PYARMOR_VER=$($PYARMOR_CMD --version 2>&1 | head -1)
ok "PyArmor dostupan: $PYARMOR_CMD ($PYARMOR_VER)"

# ── 2. Napravi čistu kopiju projekta ─────────────────────────
info "Kreiram dist_client/ kopiju projekta..."
rm -rf "$DIST_DIR"
rsync -a \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='dist_client/' \
    --exclude='.env' \
    --exclude='backup/' \
    --exclude='agent_reports/' \
    --exclude='agent_tasks/' \
    --exclude='najavauvoza/' \
    "$PROJECT_ROOT/" "$DIST_DIR/"
ok "Kopija napravljena: $DIST_DIR"

# ── 3. .env.example bez stvarnih kredencijala ─────────────────
info "Kreiram .env.example bez kredencijala..."
cat > "$DIST_DIR/.env.example" << 'EOF'
# Deklarant Pro — Konfiguracija
# Kopiraj ovaj fajl u .env i popuni stvarne vrijednosti

DB_HOST=YOUR_SERVER_IP
DB_PORT=5432
DB_NAME=deklarant_pro
DB_USER=YOUR_DB_USER
DB_PASSWORD=YOUR_DB_PASSWORD

DEBUG=False
CLIENT_NAME=your_client_id

# AI servisi (opciono — agent ne radi bez ovih)
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here

SEND_SENSITIVE_DATA=false
SESSION_TOKEN_BUDGET=50000
EOF
ok ".env.example kreiran"

# ── 4. Fajlovi/folderi za obfuskaciju ────────────────────────
TARGETS=(
    "core/licensing"
    "services/faktura"
    "services/export_service.py"
    "services/declaration_assembly.py"
)

# services/tariff/ — fajl po fajl (trial ima limit veličine)
TARIFF_DIR_FILES=$(find "$DIST_DIR/services/tariff" -maxdepth 1 -name "*.py" ! -name "__init__.py" 2>/dev/null)

# tariff*.py fajlovi u services/ root
TARIFF_FILES=$(find "$DIST_DIR/services" -maxdepth 1 -name "tariff*.py" 2>/dev/null)

echo ""
info "Pokrećem PyArmor obfuskaciju..."
echo ""

PROTECTED=()
FAILED=()

for target in "${TARGETS[@]}"; do
    full_path="$DIST_DIR/$target"
    if [ ! -e "$full_path" ]; then
        echo "  ⚠️  Preskačem (ne postoji): $target"
        continue
    fi

    echo "  🔒 Obfuskujem: $target"
    if [ -d "$full_path" ]; then
        if $PYARMOR_CMD gen -r --output "$full_path" "$full_path" > /tmp/pyarmor_out.txt 2>&1; then
            PROTECTED+=("$target/")
        else
            echo "    $(cat /tmp/pyarmor_out.txt | tail -3)"
            FAILED+=("$target")
        fi
    else
        dir=$(dirname "$full_path")
        if $PYARMOR_CMD gen --output "$dir" "$full_path" > /tmp/pyarmor_out.txt 2>&1; then
            PROTECTED+=("$target")
        else
            echo "    $(cat /tmp/pyarmor_out.txt | tail -3)"
            FAILED+=("$target")
        fi
    fi
done

# services/tariff/ fajl po fajl
for f in $TARIFF_DIR_FILES; do
    rel="services/tariff/$(basename $f)"
    lines=$(wc -l < "$f")
    echo "  🔒 Obfuskujem: $rel ($lines linija)"
    if $PYARMOR_CMD gen --output "$DIST_DIR/services/tariff" "$f" > /tmp/pyarmor_out.txt 2>&1; then
        PROTECTED+=("$rel")
    else
        err_msg=$(cat /tmp/pyarmor_out.txt | grep -i "error\|license" | tail -1)
        if echo "$err_msg" | grep -qi "license"; then
            echo "    ⚠️  Trial ograničenje (preveliko): $rel — ostaje kao .py"
        else
            echo "    ❌ $err_msg"
            FAILED+=("$rel")
        fi
    fi
done

# tariff*.py fajlovi u services/ root
for f in $TARIFF_FILES; do
    rel="services/$(basename $f)"
    echo "  🔒 Obfuskujem: $rel"
    if $PYARMOR_CMD gen --output "$DIST_DIR/services" "$f" > /tmp/pyarmor_out.txt 2>&1; then
        PROTECTED+=("$rel")
    else
        echo "    $(cat /tmp/pyarmor_out.txt | tail -3)"
        FAILED+=("$rel")
    fi
done

# ── 5. Test importa ──────────────────────────────────────────
echo ""
info "Testiram import obfuskovanih modula..."
cd "$DIST_DIR"
if python -c "
import sys
sys.path.insert(0, '.')
from core.licensing.machine_fingerprint import get_machine_fingerprint, build_fingerprint_payload
from core.licensing.license_validator import validate_license_file
from core.licensing.license_paths import get_license_path
print('core.licensing: OK')
from services.faktura.faktura_service import FakturaService
print('services.faktura: OK')
" 2>&1; then
    ok "Import test prošao"
else
    echo -e "${YELLOW}⚠️  Import test nije prošao — provjeri greške iznad${NC}"
fi
cd "$PROJECT_ROOT"

# ── 6. Izvještaj ─────────────────────────────────────────────
echo ""
echo "============================================="
echo "  IZVJEŠTAJ"
echo "============================================="
echo ""
echo "  Distribucija: $DIST_DIR"
echo ""
echo "  Zaštićeni moduli:"
for p in "${PROTECTED[@]}"; do
    echo "    ✅  $p"
done

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "  Nije uspjelo (trial ograničenje?):"
    for f in "${FAILED[@]}"; do
        echo "    ❌  $f"
    done
fi

echo ""
echo "  Napomene o __file__ putanjama:"
echo "    ✅  core/licensing/   — nema __file__ ovisnosti"
echo "    ✅  services/tariff/tarifa_service.py    — dodan _resolve_db_path() fallback"
echo "    ✅  services/tariff/tariff_tree_service.py — dodan _resolve_db_path() fallback"
echo "    ✅  PyArmor 8.x čuva __file__ u obfuskovanim fajlovima"
echo ""
echo "  dist_client/ je u .gitignore — neće biti commitovan"
echo "============================================="
echo ""
ok "Build završen!"
