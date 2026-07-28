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
            pass

    # ============================================================
    # Čiste kalkulacije (Faza 2)
    # ============================================================

    @staticmethod
    def parse_number(value_str: str) -> float:
        """Parse broj iz stringa (podržava zarez i tačku)."""
        if not value_str:
            return 0.0
        try:
            cleaned = str(value_str).replace(",", ".").replace(" ", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def parse_weight_input(text: str) -> float:
        """Parse težinu iz input polja."""
        return FakturaService.parse_number(text)

    @staticmethod
    def format_weight(weight: float) -> str:
        """Formatiraj težinu — pune preciznosti, sa hiljadnim separatorom."""
        if weight == 0.0:
            return "0.000"
        return f"{weight:,.3f}"

    @staticmethod
    def format_issue_counts(counts: dict[str, int], limit: int = 3) -> str:
        """Formatiraj broj problema za prikaz."""
        parts = [f"{k}: {v}" for k, v in counts.items() if v > 0]
        return ", ".join(parts[:limit])

    @staticmethod
    def extract_import_result_data(result) -> tuple:
        """Ekstraktuj podatke iz ImportResult ili liste."""
        from importers.import_result import ImportResult
        if isinstance(result, ImportResult):
            items = list(result.items)
            bruto_kg = getattr(result, "bruto_kg", 0.0) or 0.0
            neto_kg = getattr(result, "neto_kg", 0.0) or 0.0
            invoice_name = getattr(result, "invoice_name", "") or ""
            is_combined = getattr(result, "is_combined", False)
            import_type = getattr(result, "import_type", "invoice")
            has_origin_statement = getattr(result, "has_origin_statement", False)
            is_authorized_exporter = getattr(result, "is_authorized_exporter", False)
            exporter_name = getattr(result.exporter, "name", "") if getattr(result, "exporter", None) else ""
            importer_name = getattr(result.importer, "name", "") if getattr(result, "importer", None) else ""
            return (items, bruto_kg, neto_kg, invoice_name, is_combined,
                    import_type, has_origin_statement, is_authorized_exporter,
                    exporter_name, importer_name)
        elif isinstance(result, list):
            return (list(result), 0.0, 0.0, "", False, "invoice", False, False, "", "")
        return ([], 0.0, 0.0, "", False, "invoice", False, False, "", "")
