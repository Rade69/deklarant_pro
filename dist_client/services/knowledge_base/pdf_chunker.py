"""
PDF Chunker — dijeli PDF dokument na tekstualne odlomke (chunks) pogodne za BM25 pretragu.

Strategija:
  1. Svaka stranica se izvlači kao tekst
  2. Duge stranice (>1000 znakova) se dijele na manje odlomke (~600 znakova, overlap 100)
  3. Kratke stranice ostaju kao jedan chunk
  4. Prazni/beznačajni chunks se odbacuju
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Chunk:
    text: str
    page_number: int
    chunk_index: int


MAX_CHUNK_SIZE = 600
OVERLAP = 100
MIN_CHUNK_LEN = 50


def _clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def _split_page(page_text: str, page_num: int, start_index: int) -> List[Chunk]:
    chunks = []
    text = _clean_text(page_text)
    if len(text) < MIN_CHUNK_LEN:
        return chunks

    if len(text) <= MAX_CHUNK_SIZE:
        chunks.append(Chunk(text=text, page_number=page_num, chunk_index=start_index))
        return chunks

    # Dijeli na odlomke sa overlapom
    pos = 0
    idx = start_index
    while pos < len(text):
        end = pos + MAX_CHUNK_SIZE
        snippet = text[pos:end]
        if len(snippet) >= MIN_CHUNK_LEN:
            chunks.append(Chunk(text=snippet, page_number=page_num, chunk_index=idx))
            idx += 1
        pos += MAX_CHUNK_SIZE - OVERLAP

    return chunks


def chunk_pdf(pdf_path: str) -> List[Chunk]:
    """
    Parsira PDF i vraća listu Chunk objekata.

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        Lista Chunk objekata sa tekstom, brojem stranice i indeksom
    """
    import fitz  # PyMuPDF

    all_chunks: List[Chunk] = []
    global_index = 0

    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text")
        page_chunks = _split_page(page_text, page_num, global_index)
        all_chunks.extend(page_chunks)
        global_index += len(page_chunks)

    doc.close()
    return all_chunks
