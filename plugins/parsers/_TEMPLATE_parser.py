"""
TEMPLATE ZA NOVI PARSER

Kopiraj ovaj fajl i preimenuj u: firma_naziv_parser.py

Zamijeni:
- FirmaNazivParser sa pravim imenom klase
- can_handle logiku sa specifičnim pravilima
- import_file logiku sa parsing logikom
"""

from importers.base_strategy import ImportStrategy
from typing import Dict, Any


class FirmaNazivParser(ImportStrategy):
    """
    Parser za faktore firme XYZ.

    Format: PDF/Excel sa specifičnom strukturom
    Kreirao: [Ime autora]
    Datum: [Datum kreiranja]
    """

    def __init__(self):
        super().__init__()
        self._is_plugin = True  # Označava da je plugin

    @property
    def strategy_name(self) -> str:
        """Jedinstveno ime parsera."""
        return "Template Parser"

    @property
    def priority(self) -> int:
        """
        Prioritet (1-100).

        Viši broj = viši prioritet
        Built-in parseri: 10
        Plugin parseri: obično 20-30
        """
        return 20

    def can_handle(self, file_path: str) -> bool:
        """
        Provjeri da li ovaj parser može obraditi fajl.

        Args:
            file_path: Put do fajla

        Returns:
            True ako može obraditi, False ako ne
        """
        # TODO: Implementiraj specifičnu logiku za detekciju formata
        # Primjeri:
        # - PDF sa specifičnim tekstom u header-u
        # - Excel sa određenim nazivom sheet-a
        # - Naziv fajla sa određenim pattern-om

        return False

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parsiraj fajl i vrati strukturirane podatke.

        Args:
            file_path: Put do fajla

        Returns:
            Dict sa parsiranim podacima:
            {
                'izvoznik': {...},
                'primalac': {...},
                'stavke': [...],
                'valuta': '...',
                'ukupno': 0.00,
                ...
            }
        """
        if file_path.endswith('.pdf'):
            return self._parse_pdf(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            return self._parse_excel(file_path)
        else:
            raise ValueError(f"Nepodržan format: {file_path}")

    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Parsiraj PDF fakturu.

        Implementiraj specifičnu logiku za PDF format ove firme.
        """
        import pdfplumber

        data = {
            'izvoznik': {},
            'primalac': {},
            'stavke': [],
            'valuta': 'EUR',
            'ukupno': 0.0
        }

        with pdfplumber.open(file_path) as pdf:
            # TODO: Implementiraj specifičnu logiku
            pass

        return data

    def _parse_excel(self, file_path: str) -> Dict[str, Any]:
        """
        Parsiraj Excel fakturu.

        Implementiraj specifičnu logiku za Excel format ove firme.
        """
        import openpyxl

        data = {
            'izvoznik': {},
            'primalac': {},
            'stavke': [],
            'valuta': 'EUR',
            'ukupno': 0.0
        }

        wb = openpyxl.load_workbook(file_path)
        ws = wb.active

        # TODO: Implementiraj specifičnu logiku

        return data
