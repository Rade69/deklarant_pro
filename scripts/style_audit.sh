#!/usr/bin/env bash
# Style Audit — read-only linter za stil anti-patterne
# Usage: bash scripts/style_audit.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STYLES_DIR="$ROOT/styles"
GUI_DIR="$ROOT/gui"
EXIT_CODE=0

echo "========================================"
echo "  STYLE AUDIT — Deklarant Pro"
echo "========================================"
echo ""

# --------------------------------------------------
# 1. Duplikat QComboBox::down-arrow deklaracije
# --------------------------------------------------
echo "[CHECK 1] Duplikat QComboBox::down-arrow u .qss fajlovima"
echo "-------------------------------------------------------------"

declarations=$(grep -rl "QComboBox::down-arrow" "$STYLES_DIR"/*.qss 2>/dev/null || true)
file_count=$(echo "$declarations" | grep -c . || true)

if [ "$file_count" -gt 1 ]; then
    echo "⚠️  PRONAĐENO $file_count .qss fajlova sa QComboBox::down-arrow:"
    for f in $declarations; do
        echo "   - $(basename "$f")"
        grep -n "QComboBox::down-arrow" "$f" | head -2 | sed 's/^/     /'
    done
    echo ""
    echo "   PREPORUKA: Ostavi samo jednu deklaraciju (najspecifičniju)."
    echo "   Ostale prebaci u fallback ili ukloni."
    EXIT_CODE=1
else
    echo "✅ Samo 1 fajl deklariše QComboBox::down-arrow"
fi
echo ""

# --------------------------------------------------
# 2. Inline setStyleSheet bez komentara razloga
# --------------------------------------------------
echo "[CHECK 2] Inline setStyleSheet bez komentara razloga (top 10)"
echo "-------------------------------------------------------------"

# Pronađi inline setStyleSheet pozive i provjeri da li prethodi komentar sa razlogom
# (tražimo '# Razlog:' ili '# STATE:' ili '# WORKAROUND:' u 3 prethodne linije)

temp_file=$(mktemp)

# Uzmemo sve .py fajlove, izdvojimo setStyleSheet linije i vidimo ima li komentar iznad
grep -rn "\.setStyleSheet(" "$GUI_DIR" --include="*.py" | grep -v "__pycache__" | \
while IFS=: read -r file line rest; do
    # Pročitaj 5 prethodnih linija
    ctx=$(sed -n "$((line-5)),$((line-1))p" "$file" 2>/dev/null || true)
    # Provjeri da li sadrži komentar koji objašnjava ZAŠTO
    if ! echo "$ctx" | grep -qiE "(# (STATE|WORKAROUND|Razlog|Reason|L1|inline|why|because|dynamic|runtime|hover|pressed|focus|error|warning|valid|invalid|highlight|TODO|FIXME))|(\"\"\".*state)"; then
        rel=${file#$ROOT/}
        # Pokaži samo prvi poziv po fajlu da ne flood-ujemo
        echo "$rel:$line" >> "$temp_file"
    fi
done

# Dedup po fajlu
if [ -s "$temp_file" ]; then
    count=$(cut -d: -f1 "$temp_file" | sort -u | wc -l)
    if [ "$count" -gt 0 ]; then
        echo "⚠️  PRONAĐENO $count fajlova sa setStyleSheet bez komentara razloga (top 10):"
        awk -F: '!seen[$1]++ { print $0 }' "$temp_file" | sed -n '1,10p' | sed 's/^/   /'
        total_matched=$(grep -rc "\.setStyleSheet(" "$GUI_DIR" --include="*.py" 2>/dev/null | grep -v ":0$" | wc -l)
        echo ""
        echo "   Ukupno fajlova sa setStyleSheet: $total_matched"
        echo "   PREPORUKA: Svaki L1 (inline) stil treba komentar: # STATE: <razlog>"
        EXIT_CODE=1
    fi
else
    echo "✅ Svi setStyleSheet pozivi imaju komentar razloga"
fi
rm -f "$temp_file"
echo ""

# --------------------------------------------------
# 3. Globalni nescopirani selektori visokog rizika
# --------------------------------------------------
echo "[CHECK 3] Globalni nescopirani selektori visokog rizika u .qss"
echo "-------------------------------------------------------------"

# Tražimo selektore koji targetuju sve instance bez tab/widget scopa
high_risk_selectors=(
    "^QLineEdit\s*{"         # Svi QLineEdit u aplikaciji
    "^QComboBox\s*{"         # Svi QComboBox
    "^QPushButton\s*{"       # Svi QPushButton
    "^QTableWidget\s*{"      # Sve tabele
    "^QGroupBox\s*{"         # Svi group box-ovi
)

found_any=0
for qss in "$STYLES_DIR"/*.qss; do
    [ -f "$qss" ] || continue
    for pattern in "${high_risk_selectors[@]}"; do
        matches=$(grep -n "$pattern" "$qss" 2>/dev/null || true)
        if [ -n "$matches" ]; then
            if [ "$found_any" -eq 0 ]; then
                echo "⚠️  PRONAĐENI nescopirani globalni selektori:"
            fi
            found_any=1
            echo "   $(basename "$qss"):"
            echo "$matches" | head -3 | sed 's/^/     /'
        fi
    done
done

if [ "$found_any" -eq 0 ]; then
    echo "✅ Nema globalnih nescopiranih selektora visokog rizika"
else
    echo ""
    echo "   PREPORUKA: Zamijeni globalne selektore sa scoped:"
    echo "   #TabName QLineEdit { }  ili  QLineEdit[class=\"input-primary\"] { }"
    EXIT_CODE=1
fi
echo ""

# --------------------------------------------------
# 4. Summary
# --------------------------------------------------
echo "========================================"
echo "  REZULTAT"
echo "========================================"

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "✅ Svi checkovi prolaze — nema detektovanih anti-patterna."
else
    echo "⚠️  Pronađeni potencijalni problemi. Pregledaj iznad."
fi

echo ""
echo "Ukupno .qss fajlova: $(ls "$STYLES_DIR"/*.qss 2>/dev/null | wc -l)"
echo "Ukupno setStyleSheet poziva: $(grep -r "\.setStyleSheet(" "$GUI_DIR" --include="*.py" 2>/dev/null | wc -l)"
echo ""

exit $EXIT_CODE
