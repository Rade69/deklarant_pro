#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agent.learning.product_similarity_memory_service import (  # noqa: E402
    sync_product_similarity_memory,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sinhronizuje catalogs.product_tariff_mapping u product_similarity_memory."
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    result = sync_product_similarity_memory(limit=args.limit)
    if result.error:
        print(f"GREŠKA: {result.error}")
        return 1

    print(
        "OK: "
        f"scanned={result.scanned}, synced={result.synced}, skipped={result.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
