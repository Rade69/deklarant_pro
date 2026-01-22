"""PDF importer za fakture."""

from pathlib import Path
from typing import Any, Dict, List


class PDFImporter:
    """Uvozi fakture iz PDF fajlova."""

    def __init__(self):
        """Inicijalizuje PDF importer."""
        pass

    def import_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Uvozi PDF fajl.

        Args:
            file_path: Putanja do PDF fajla

        Returns:
            Dictionary sa faktura podacima

        Raises:
            FileNotFoundError: Ako fajl ne postoji
            ValueError: Ako format nije validan
        """
        # TODO: Implementirati PDF import
        # - Koristiti OCR za skenove
        # - Prepoznati strukturu fakture
        # - Ekstraktovati tekst i tabele
        raise NotImplementedError("PDF import nije još implementiran")

    def extract_text(self, file_path: Path) -> str:
        """Ekstraktuje tekst iz PDF-a."""
        # TODO: Implementirati ekstrakciju teksta
        return ""

    def extract_tables(self, file_path: Path) -> List[List[str]]:
        """Ekstraktuje tabele iz PDF-a."""
        # TODO: Implementirati ekstrakciju tabela
        return []

    def parse_invoice_data(self, text: str, tables: List[List[str]]) -> Dict[str, Any]:
        """Parsira podatke fakture iz teksta i tabela."""
        # TODO: Implementirati parsiranje
        return {}
