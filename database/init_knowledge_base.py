#!/usr/bin/env python3
"""
Inicijalizacija Knowledge Base — ingesta sve PDF dokumente iz docs foldera.
Pokreni jednom nakon setup_db.py:
  source .venv/bin/activate && python database/init_knowledge_base.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "data" / "knowledge_base"

# PDF-ovi koje uključujemo (zakonska regulativa, ne tarifa jer je prevelika)
SKIP_PATTERNS = [
    "Carinska_tarifa_za_2026",  # prevelik PDF, tarifa se učitava posebno
    "sifre.pdf",
]


def should_skip(filename: str) -> bool:
    return any(p in filename for p in SKIP_PATTERNS)


def run():
    print("📚 Inicijalizacija Knowledge Base")
    print("=" * 50)

    pdfs = sorted(DOCS_DIR.glob("*.pdf"))
    pdfs_to_ingest = [p for p in pdfs if not should_skip(p.name)]

    print(f"📂 Folder: {DOCS_DIR}")
    print(f"📄 Ukupno PDF-ova: {len(pdfs)}")
    print(f"📥 Za ingest: {len(pdfs_to_ingest)} (preskačem tarifu i sifre)")
    print()

    if not pdfs_to_ingest:
        print("❌ Nema PDF-ova za ingest!")
        return

    try:
        from services.knowledge_base.kb_service import KnowledgeBaseService
        svc = KnowledgeBaseService()

        added = updated = skipped = errors = 0

        for pdf in pdfs_to_ingest:
            print(f"  📄 {pdf.name}...", end=" ", flush=True)
            try:
                result = svc.ingest_document(str(pdf))
                status = result["status"]
                chunks = result.get("chunk_count", 0)
                if status == "added":
                    added += 1
                    print(f"✅ dodano ({chunks} chunkova)")
                elif status == "updated":
                    updated += 1
                    print(f"🔄 ažurirano ({chunks} chunkova)")
                else:
                    skipped += 1
                    print(f"⏭️  preskočeno (nije promijenjeno)")
            except Exception as e:
                errors += 1
                print(f"❌ Greška: {e}")

        print()
        print(f"✅ Dodano: {added}, Ažurirano: {updated}, Preskočeno: {skipped}, Greške: {errors}")

        # Statistika
        stats = svc.get_stats()
        print(f"\n📊 Knowledge Base statistika:")
        print(f"   Dokumenata: {stats['doc_count']}")
        print(f"   Chunkova: {stats['chunk_count']}")
        print("\n🎉 Knowledge Base je spreman!")

    except Exception as e:
        print(f"❌ Fatalna greška: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run()
