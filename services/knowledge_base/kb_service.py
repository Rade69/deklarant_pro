"""
KnowledgeBaseService — upravljanje i pretraga zakonske regulative.

Tok rada:
  1. ingest_document(pdf_path) → parsira PDF, dijeli na chunks, upisuje u PostgreSQL
  2. search(query, top_k) → BM25 pretraga nad svim chunkovima → Groq re-ranking
  3. ChatWorker poziva search() i uključuje rezultate u kontekst

Napomena: BM25 indeks se gradi u memoriji pri prvom pozivu search() i kešira.
Invalidira se automatski nakon ingesta novog dokumenta.
"""

import hashlib
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from database.db import get_db_connection
from services.knowledge_base.pdf_chunker import chunk_pdf


@dataclass
class KBResult:
    doc_title: str
    filename: str
    page_number: int
    chunk_text: str
    score: float


class KnowledgeBaseService:
    """Pretraga zakonske regulative (BM25 + Groq re-ranking)."""

    def __init__(self):
        self._bm25 = None
        self._index_data: List[dict] = []  # [{doc_title, filename, page_number, chunk_text}]

    # ------------------------------------------------------------------ #
    # Ingest
    # ------------------------------------------------------------------ #

    def ingest_document(self, pdf_path: str, title: Optional[str] = None) -> dict:
        """
        Ingesta jedan PDF dokument u bazu.
        Ako je fajl već ingestan i nije se promijenio — preskače.

        Returns:
            {"status": "added"|"updated"|"skipped", "chunk_count": int}
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"Fajl ne postoji: {pdf_path}")

        file_hash = self._sha256(pdf_path)
        filename = path.name
        doc_title = title or path.stem.replace("_", " ").replace("-", " ").title()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, file_hash FROM public.knowledge_base_docs WHERE filename = %s",
                    (filename,)
                )
                existing = cur.fetchone()

                if existing:
                    if existing["file_hash"] == file_hash:
                        return {"status": "skipped", "chunk_count": 0}
                    # Fajl se promijenio — briši stare chunkove
                    cur.execute(
                        "DELETE FROM public.knowledge_base_chunks WHERE doc_id = %s",
                        (existing["id"],)
                    )
                    doc_id = existing["id"]
                    action = "updated"
                else:
                    cur.execute(
                        """INSERT INTO public.knowledge_base_docs
                           (filename, title, file_path, file_hash)
                           VALUES (%s, %s, %s, %s)
                           RETURNING id""",
                        (filename, doc_title, str(path.absolute()), file_hash)
                    )
                    doc_id = cur.fetchone()["id"]
                    action = "added"

                # Chunking + upis
                chunks = chunk_pdf(pdf_path)
                for chunk in chunks:
                    cur.execute(
                        """INSERT INTO public.knowledge_base_chunks
                           (doc_id, chunk_index, page_number, chunk_text)
                           VALUES (%s, %s, %s, %s)""",
                        (doc_id, chunk.chunk_index, chunk.page_number, chunk.text)
                    )

                # Ažuriraj statistiku dokumenta
                cur.execute(
                    """UPDATE public.knowledge_base_docs
                       SET chunk_count = %s,
                           page_count  = (SELECT MAX(page_number) FROM public.knowledge_base_chunks WHERE doc_id = %s),
                           file_hash   = %s,
                           updated_at  = NOW()
                       WHERE id = %s""",
                    (len(chunks), doc_id, file_hash, doc_id)
                )

            conn.commit()

        # Invalidira BM25 keš
        self._bm25 = None
        self._index_data = []

        print(f"📚 KB {action}: {filename} ({len(chunks)} chunkova)")
        return {"status": action, "chunk_count": len(chunks)}

    def ingest_folder(self, folder_path: str) -> List[dict]:
        """
        Ingesta sve PDF fajlove iz foldera.
        Preskače fajlove koji se nisu promijenili.
        """
        folder = Path(folder_path)
        results = []
        pdfs = sorted(folder.glob("*.pdf"))
        print(f"📂 Ingest foldera: {folder} ({len(pdfs)} PDF fajlova)")
        for pdf in pdfs:
            try:
                result = self.ingest_document(str(pdf))
                result["filename"] = pdf.name
                results.append(result)
            except Exception as e:
                print(f"  ⚠️ Greška pri ingestu {pdf.name}: {e}")
                results.append({"filename": pdf.name, "status": "error", "error": str(e)})
        return results

    # ------------------------------------------------------------------ #
    # Pretraga
    # ------------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 5, use_reranking: bool = True) -> List[KBResult]:
        """
        BM25 pretraga + opcionalni Groq re-ranking.

        Args:
            query: Pitanje/upit korisnika
            top_k: Broj finalnih rezultata
            use_reranking: Ako True, Groq re-rankira BM25 top 15

        Returns:
            Lista KBResult sortirana po relevantnosti
        """
        self._ensure_index()
        if not self._index_data:
            return []

        bm25_results = self._bm25_search(query, top_n=15)

        if not bm25_results:
            return []

        if use_reranking and len(bm25_results) > top_k:
            try:
                reranked = self._groq_rerank(query, bm25_results, top_k)
                return reranked
            except Exception as e:
                print(f"  ⚠️ Groq re-ranking neuspješan, vraćam BM25 top {top_k}: {e}")

        return bm25_results[:top_k]

    def list_documents(self) -> List[dict]:
        """Vraća listu svih ingestanih dokumenata."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT filename, title, page_count, chunk_count, updated_at
                       FROM public.knowledge_base_docs
                       ORDER BY filename"""
                )
                return [dict(row) for row in cur.fetchall()]

    def delete_document(self, filename: str) -> bool:
        """Briše dokument i sve njegove chunkove."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.knowledge_base_docs WHERE filename = %s RETURNING id",
                    (filename,)
                )
                deleted = cur.fetchone()
            conn.commit()

        if deleted:
            self._bm25 = None
            self._index_data = []
            print(f"🗑️ KB: obrisan {filename}")
            return True
        return False

    def get_tariff_descriptions(self, tariff_codes: List[str]) -> dict:
        """
        Za listu tarifnih brojeva vraća opise iz Carinske tarife.

        Strategija:
          1. Direktna pretraga — traži chunk koji sadrži formatirani kod (tačan match)
          2. BM25 fallback — ako direktna pretraga ne nađe ništa

        Args:
            tariff_codes: Lista tarifnih brojeva (npr. ["0201100000", "8471300000"])

        Returns:
            Dict: {tariff_code: chunk_text | None}
        """
        self._ensure_index()
        result = {}
        tarifa_filename = "Carinska_tarifa_za_2026_-_bosanski.pdf"

        for code in tariff_codes:
            formatted = self._format_tariff_code(code)

            # 1. Direktna pretraga — chunk koji SADRŽI tačan formatirani kod
            direct_match = None
            for item in self._index_data:
                if item["filename"] == tarifa_filename and formatted in item["chunk_text"]:
                    direct_match = item["chunk_text"]
                    break

            if direct_match:
                result[code] = direct_match
                continue

            # 2. BM25 fallback unutar Carinske tarife
            query_tokens = self._tokenize(formatted)
            scores = self._bm25.get_scores(query_tokens)
            best_score = -1
            best_chunk = None
            for idx, score in enumerate(scores):
                item = self._index_data[idx]
                if item["filename"] != tarifa_filename:
                    continue
                if score > best_score:
                    best_score = score
                    best_chunk = item["chunk_text"]

            result[code] = best_chunk if best_score > 0 else None

        return result

    @staticmethod
    def _format_tariff_code(code: str) -> str:
        """Formatira tarifni broj za pretragu (10 cifara → 'XXXX XX XX XX')."""
        digits = "".join(c for c in code if c.isdigit())
        if len(digits) >= 10:
            return f"{digits[:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}"
        if len(digits) >= 8:
            return f"{digits[:4]} {digits[4:6]} {digits[6:8]}"
        if len(digits) >= 4:
            return f"{digits[:4]} {digits[4:]}"
        return code

    def get_stats(self) -> dict:
        """Statistika knowledge base-a."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM public.knowledge_base_docs")
                doc_count = cur.fetchone()["count"]
                cur.execute("SELECT COUNT(*) FROM public.knowledge_base_chunks")
                chunk_count = cur.fetchone()["count"]
        return {"doc_count": doc_count, "chunk_count": chunk_count}

    # ------------------------------------------------------------------ #
    # Interni metodi
    # ------------------------------------------------------------------ #

    def _ensure_index(self):
        """Gradi BM25 indeks ako nije već u memoriji."""
        if self._bm25 is not None:
            return

        from rank_bm25 import BM25Okapi

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.chunk_text, c.page_number,
                              d.title, d.filename
                       FROM public.knowledge_base_chunks c
                       JOIN public.knowledge_base_docs d ON d.id = c.doc_id
                       ORDER BY c.id"""
                )
                rows = cur.fetchall()

        if not rows:
            return

        self._index_data = [
            {
                "chunk_text": row["chunk_text"],
                "page_number": row["page_number"],
                "doc_title": row["title"],
                "filename": row["filename"],
            }
            for row in rows
        ]

        corpus_tokens = [self._tokenize(item["chunk_text"]) for item in self._index_data]
        self._bm25 = BM25Okapi(corpus_tokens)
        print(f"📑 BM25 indeks izgrađen: {len(self._index_data)} chunkova")

    def _bm25_search(self, query: str, top_n: int) -> List[KBResult]:
        query_tokens = self._tokenize(query)
        scores = self._bm25.get_scores(query_tokens)

        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed[:top_n]:
            if score <= 0:
                break
            item = self._index_data[idx]
            results.append(KBResult(
                doc_title=item["doc_title"],
                filename=item["filename"],
                page_number=item["page_number"],
                chunk_text=item["chunk_text"],
                score=float(score),
            ))
        return results

    def _groq_rerank(self, query: str, candidates: List[KBResult], top_k: int) -> List[KBResult]:
        """
        Šalje BM25 kandidate Groq-u da odabere najrelevantnijih top_k.
        """
        from groq import Groq
        from dotenv import dotenv_values
        from pathlib import Path as _Path

        env_path = _Path(__file__).parent.parent.parent / ".env"
        env_vars = dotenv_values(env_path) if env_path.exists() else {}
        api_key = env_vars.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            return candidates[:top_k]

        # Pripremi listu za Groq
        passages = "\n\n".join(
            f"[{i+1}] (Dokument: {c.filename}, str. {c.page_number})\n{c.chunk_text[:400]}"
            for i, c in enumerate(candidates)
        )

        prompt = (
            f"Pitanje: {query}\n\n"
            f"Odlomci iz zakonske regulative:\n{passages}\n\n"
            f"Koji od gorenavedenih odlomaka su NAJRELEVANTNIJI za ovo pitanje? "
            f"Navedi samo redne brojeve (npr. 1,3,5) {top_k} najrelevantnijih, "
            f"sortirano od najrelevantnijeg. Odgovori samo brojevima odvojenim zarezom."
        )

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
        )

        text = response.choices[0].message.content.strip()
        # Parsiranje odgovora (npr. "1,3,5" ili "1, 3, 5")
        import re
        indices = [int(x.strip()) - 1 for x in re.findall(r'\d+', text)]

        reranked = []
        for idx in indices:
            if 0 <= idx < len(candidates):
                reranked.append(candidates[idx])

        # Dodaj preostale ako Groq nije vratio dovoljno
        seen = set(id(r) for r in reranked)
        for c in candidates:
            if id(c) not in seen and len(reranked) < top_k:
                reranked.append(c)

        return reranked[:top_k]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenizacija za BM25 (lowercase, split po riječima)."""
        import re
        text = text.lower()
        return re.findall(r'\w+', text)

    @staticmethod
    def _sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
