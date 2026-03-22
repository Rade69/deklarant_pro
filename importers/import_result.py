# importers/import_result.py

"""
Result objekat za PDF/Excel import sa dodatnim podacima.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from core.draft.draft import InvoiceLine


@dataclass
class ImportResult:
    """
    Rezultat importa fakture sa dodatnim metadata podacima.

    Attributes:
        items: Lista InvoiceLine objekata
        bruto_kg: Ukupna bruto težina sa fakture (kg)
        neto_kg: Ukupna neto težina sa fakture (kg)
        invoice_name: Ime/broj fakture
        currency: Valuta (EUR, USD, itd.)
        is_combined: Da li je ovo kombinovani import (Excel + PDF)
        import_type: Tip importa ('loren_pdf', 'loren_excel', 'loren_combined', 'invoice')
        has_origin_statement: Da li faktura sadrži izjavu o poreklu (PE2)
        origin_statements: Lista detektovanih izjava o poreklu (za fakture sa više izjava)
    """
    items: List[InvoiceLine] = field(default_factory=list)
    bruto_kg: float = 0.0
    neto_kg: float = 0.0
    invoice_name: str = ""
    currency: str = "EUR"
    is_combined: bool = False  # Flag za kombinovane importe (Excel + PDF)
    import_type: str = "invoice"  # Tip importa (loren_pdf, loren_excel, loren_combined, invoice)
    has_origin_statement: bool = False  # Da li faktura sadrži izjavu o poreklu (PE2)
    origin_statements: Optional[List] = None  # Lista OriginStatementMatch objekata (za višestruke izjave)
    warnings: List[str] = field(default_factory=list)  # Upozorenja koja treba prikazati korisniku

    def __len__(self) -> int:
        """Return number of items (for len() support)."""
        return len(self.items)

    def __getitem__(self, index: int | slice) -> InvoiceLine | List[InvoiceLine]:
        """Return item at index or slice (for indexing/slicing support)."""
        return self.items[index]
