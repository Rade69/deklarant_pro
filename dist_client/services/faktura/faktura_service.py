"""
Faktura Service - Glavni servis za fakturu
"""

from typing import List
from core.draft import InvoiceLine, DeclarationDraft


class FakturaService:
    """Business logic za fakturu - odvojen od UI"""

    @staticmethod
    def add_item(draft: DeclarationDraft, item: InvoiceLine) -> None:
        """Dodaj stavku u draft"""
        draft.invoice_lines.append(item)

    @staticmethod
    def delete_item(draft: DeclarationDraft, row: int) -> None:
        """Obriši stavku iz drafta"""
        if 0 <= row < len(draft.invoice_lines):
            del draft.invoice_lines[row]

    @staticmethod
    def clear_all(draft: DeclarationDraft) -> None:
        """Očisti sve stavke iz drafta"""
        draft.invoice_lines.clear()

    @staticmethod
    def sync_table_to_draft(table_items, draft_items) -> None:
        """
        Sinhronizuje podatke iz tabele u draft.

        Args:
            table_items: Lista QTableWidgetItem redova
            draft_items: Lista InvoiceLine stavki
        """
        for row, item in enumerate(draft_items):
            if row >= len(table_items):
                break

            # Ovo bi trebalo biti implementirano u GUI sloju
            # jer zavisi od QTableWidgetItem
            pass
