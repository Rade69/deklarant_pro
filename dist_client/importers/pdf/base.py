# importers/pdf/base.py

"""
Base PDF parsing strategy.

Svaka strategija (Tabula, OCR, Text-based) mora implementirati ovaj interfejs.
"""

from abc import ABC, abstractmethod
from typing import List
from core.draft.draft import InvoiceLine


class PDFParseStrategy(ABC):
    """
    Apstraktna baza za PDF parsing strategije.
    """

    @abstractmethod
    def extract(self, filepath: str) -> List[InvoiceLine]:
        """
        Ekstraktuje stavke fakture iz PDF-a.

        Args:
            filepath: Putanja do PDF fajla

        Returns:
            Lista InvoiceLine objekata
        """
        raise NotImplementedError
