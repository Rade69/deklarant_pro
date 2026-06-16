"""
Deklarant Pro - CMANA Importer Package
"""

from importers.vendors.cmana.cmana_pdf_parser import (
    detect_cmana_pdf,
    parse_cmana_pdf,
)

__all__ = ["detect_cmana_pdf", "parse_cmana_pdf"]
