# importers/strategies/__init__.py

"""
Import Strategies Package

Sadrži sve implementacije import strategija:
- PDFImportStrategy - Import PDF faktura
- ExcelImportStrategy - Import Excel (.xlsx, .xls) faktura
- XMLImportStrategy - Import XML (ASYCUDA) deklaracija

Primjer:
    from importers.strategies import PDFImportStrategy, ExcelImportStrategy, XMLImportStrategy
"""

from importers.strategies.pdf_strategy import PDFImportStrategy
from importers.strategies.excel_strategy import ExcelImportStrategy
from importers.strategies.xml_strategy import XMLImportStrategy

__all__ = [
    'PDFImportStrategy',
    'ExcelImportStrategy',
    'XMLImportStrategy',
]
