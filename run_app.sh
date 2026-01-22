#!/bin/bash
# Script za pokretanje ASYCUDA Pro aplikacije

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
python3 __main__.py
