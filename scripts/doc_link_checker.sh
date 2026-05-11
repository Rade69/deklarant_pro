#!/usr/bin/env bash
# doc_link_checker.sh
# Provjerava sve # DOC: linkove u Python fajlovima.
# Read-only — ne mijenja ništa.
# Izlazni kod: 0 = sve OK, 1 = postoje problemi

set -euo pipefail

PROJECT_ROOT="${1:-.}"
PYTHON_FILES=$(find "$PROJECT_ROOT" -name "*.py" \
  -not -path "*/\.*" \
  -not -path "*/venv/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/node_modules/*")

BROKEN=0
STALE=0
OK=0

declare -a BROKEN_LIST=()
declare -a STALE_LIST=()

echo "=== DOC Link Checker ==="
echo "Root: $PROJECT_ROOT"
echo "Datum: $(date '+%Y-%m-%d %H:%M')"
echo ""

while IFS= read -r py_file; do
  # Pronađi sve # DOC: linije
  while IFS= read -r match; do
    lineno=$(echo "$match" | cut -d: -f1)
    line=$(echo "$match" | cut -d: -f2-)

    # Izvuci putanju iza # DOC:
    doc_path=$(echo "$line" | sed 's/.*#\s*DOC:\s*//' | tr -d '[:space:]')

    if [[ -z "$doc_path" ]]; then
      continue
    fi

    # Resolve relativno na project root
    full_doc_path="$PROJECT_ROOT/$doc_path"

    if [[ ! -f "$full_doc_path" ]]; then
      BROKEN=$((BROKEN + 1))
      BROKEN_LIST+=("$py_file:$lineno -> $doc_path")
    else
      # Stale check: da li je .py noviji od .md?
      if [[ "$py_file" -nt "$full_doc_path" ]]; then
        STALE=$((STALE + 1))
        py_mod=$(date -r "$py_file" '+%Y-%m-%d %H:%M')
        md_mod=$(date -r "$full_doc_path" '+%Y-%m-%d %H:%M')
        STALE_LIST+=("$py_file:$lineno -> $doc_path (py: $py_mod / md: $md_mod)")
      else
        OK=$((OK + 1))
      fi
    fi
  done < <(grep -n "# DOC:" "$py_file" 2>/dev/null || true)
done <<< "$PYTHON_FILES"

# --- Ispis rezultata ---

if [[ ${#BROKEN_LIST[@]} -gt 0 ]]; then
  echo "--- BROKEN (fajl ne postoji) ---"
  for item in "${BROKEN_LIST[@]}"; do
    echo "  ✗ $item"
  done
  echo ""
fi

if [[ ${#STALE_LIST[@]} -gt 0 ]]; then
  echo "--- STALE (py noviji od md) ---"
  for item in "${STALE_LIST[@]}"; do
    echo "  ⚠ $item"
  done
  echo ""
fi

echo "--- Rezime ---"
echo "  OK:     $OK"
echo "  STALE:  $STALE"
echo "  BROKEN: $BROKEN"
echo ""

if [[ $BROKEN -gt 0 || $STALE -gt 0 ]]; then
  echo "STATUS: PROBLEMI PRONAĐENI"
  exit 1
else
  echo "STATUS: SVE OK"
  exit 0
fi
