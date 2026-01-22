"""Excel importer za fakture."""

from pathlib import Path
from typing import Any, Dict, List


class ExcelImporter:
    """Uvozi fakture iz Excel fajlova."""

    def __init__(self):
        """Inicijalizuje Excel importer."""
        pass

    def import_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Uvozi Excel fajl.

        Args:
            file_path: Putanja do Excel fajla

        Returns:
            Dictionary sa faktura podacima

        Raises:
            FileNotFoundError: Ako fajl ne postoji
            ValueError: Ako format nije validan
        """
        # TODO: Implementirati Excel import
        # - Podržati .xlsx i .xls formate
        # - Prepoznati zaglavlje i stavke
        # - Mapirati kolone u Draft format
        raise NotImplementedError("Excel import nije još implementiran")

    def validate_format(self, file_path: Path) -> bool:
        """
        Validira da li je Excel fajl validan.

        Args:
            file_path: Putanja do fajla

        Returns:
            True ako je format validan
        """
        # TODO: Implementirati validaciju
        return False

    def extract_header(self, data: Any) -> Dict[str, Any]:
        """Ekstraktuje zaglavlje fakture."""
        # TODO: Implementirati ekstrakciju zaglavlja
        return {}

    def extract_items(self, data: Any) -> List[Dict[str, Any]]:
        """Ekstraktuje stavke fakture."""
        # TODO: Implementirati ekstrakciju stavki
        return []
