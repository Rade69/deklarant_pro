#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agent.learning.product_similarity_embedding_service import (  # noqa: E402
    ProductSimilarityEmbeddingService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generiše embeddinge za catalogs.product_similarity_memory."
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=None)
    args = parser.parse_args()

    result = ProductSimilarityEmbeddingService().embed_pending(
        batch_size=args.batch_size,
        max_batches=args.max_batches,
    )
    if result.error:
        print(f"GREŠKA: {result.error}")
        return 1
    print(
        "OK: "
        f"scanned={result.scanned}, embedded={result.embedded}, skipped={result.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
