"""
Skripta za ingestanje PDF dokumenata u Knowledge Base.

Upotreba:
    # Ingesta sve PDF-ove iz data/knowledge_base/
    python scripts/ingest_kb.py

    # Ingesta specifičan fajl
    python scripts/ingest_kb.py --file data/knowledge_base/carinski_zakon.pdf

    # Prikaži listu ingestanih dokumenata
    python scripts/ingest_kb.py --list

    # Obriši dokument
    python scripts/ingest_kb.py --delete carinski_zakon.pdf
"""

import sys
from pathlib import Path

# Dodaj root projekta u sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from services.knowledge_base.kb_service import KnowledgeBaseService

KB_FOLDER = ROOT / "data" / "knowledge_base"


def main():
    svc = KnowledgeBaseService()

    if "--list" in sys.argv:
        docs = svc.list_documents()
        if not docs:
            print("Knowledge Base je prazan.")
            return
        print(f"\n{'Naziv fajla':<50} {'Stranice':>8} {'Chunkovi':>9}  Ažurirano")
        print("-" * 90)
        for d in docs:
            print(
                f"{d['filename']:<50} {d['page_count']:>8} {d['chunk_count']:>9}"
                f"  {str(d['updated_at'])[:16]}"
            )
        stats = svc.get_stats()
        print(f"\nUkupno: {stats['doc_count']} dokumenata, {stats['chunk_count']} chunkova")
        return

    if "--delete" in sys.argv:
        idx = sys.argv.index("--delete")
        if idx + 1 >= len(sys.argv):
            print("Greška: navedi naziv fajla nakon --delete")
            sys.exit(1)
        filename = sys.argv[idx + 1]
        if svc.delete_document(filename):
            print(f"✅ Obrisano: {filename}")
        else:
            print(f"⚠️ Dokument nije pronađen: {filename}")
        return

    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx + 1 >= len(sys.argv):
            print("Greška: navedi putanju fajla nakon --file")
            sys.exit(1)
        pdf_path = sys.argv[idx + 1]
        result = svc.ingest_document(pdf_path)
        print(f"✅ {result['status'].upper()}: {Path(pdf_path).name} ({result['chunk_count']} chunkova)")
        return

    # Bez argumenata — ingesta cijeli folder
    if not KB_FOLDER.exists():
        print(f"⚠️ Folder ne postoji: {KB_FOLDER}")
        print("Kreiraj folder i dodaj PDF fajlove:")
        print(f"  mkdir -p {KB_FOLDER}")
        sys.exit(1)

    results = svc.ingest_folder(str(KB_FOLDER))

    print("\n=== Rezultat ingesta ===")
    added = sum(1 for r in results if r.get("status") == "added")
    updated = sum(1 for r in results if r.get("status") == "updated")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    errors = sum(1 for r in results if r.get("status") == "error")

    print(f"  Dodano:     {added}")
    print(f"  Ažurirano:  {updated}")
    print(f"  Preskočeno: {skipped} (bez izmjena)")
    print(f"  Greške:     {errors}")

    stats = svc.get_stats()
    print(f"\nTrenutno u KB: {stats['doc_count']} dokumenata, {stats['chunk_count']} chunkova")


if __name__ == "__main__":
    main()
