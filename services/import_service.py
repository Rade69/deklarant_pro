# services/import_service.py

"""
Import Service - Orchestrator sa memorijom za kombinovanje parova

Koristi Strategy Registry za parsiranje, ali dodaje sloj memorije
za auto-kombinovanje parova (Blagić-Loren Excel+PDF, Invoice+Packing List).
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Callable, Union, List

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from importers.strategy_registry import get_registry
from importers.exceptions import ImportError as ImportException


logger = logging.getLogger("asycuda_pro.import")

# Poznati vendor formati koji se NE tretiraju kao packing lista
_KNOWN_VENDOR_FORMATS = {
    "invoice_improved", "blagic_loren", "blagic_attos",
    "imamoglu", "master_frigo", "medicopharm"
}


def _similar_invoice_number(name1: str, name2: str) -> bool:
    """
    Provjera da li dva imena fajlova imaju sličan broj fakture.

    Npr:
    - "FAI-7-0-26.pdf" i "FAI-7-0-26 PACKING LIST.pdf" → True
    - "702VP-2025.pdf" i "702VP-2025-PL.pdf" → True
    """
    n1 = name1.lower().replace("-", "").replace("_", "").replace(" ", "")
    n2 = name2.lower().replace("-", "").replace("_", "").replace(" ", "")

    keywords = ["packing", "list", "pl", "invoice", "inv", "faktura"]
    for kw in keywords:
        n1 = n1.replace(kw, "")
        n2 = n2.replace(kw, "")

    if n1 in n2 or n2 in n1:
        return True

    min_len = min(len(n1), len(n2))
    if min_len >= 5:
        common_prefix_len = 0
        for i in range(min_len):
            if n1[i] == n2[i]:
                common_prefix_len += 1
            else:
                break
        if common_prefix_len >= min_len * 0.8:
            return True

    return False


class ImportService:
    """
    Import orchestrator sa memorijom za auto-kombinovanje parova.

    Kombinuje:
    - Blagić-Loren Excel + PDF (isti broj fakture)
    - Invoice + Packing List (isti broj fakture)
    """

    def __init__(self):
        self.registry = get_registry()
        self.logger = logger

        # Memorija za auto-kombinovanje
        self.last_import_result: Optional[Union[List[InvoiceLine], ImportResult]] = None
        self.last_import_path: Optional[str] = None
        self.last_import_type: Optional[str] = None

    def clear_memory(self):
        """Resetuj memoriju importa (za kombinovanje parova Excel+PDF)."""
        self.last_import_result = None
        self.last_import_path = None
        self.last_import_type = None
        self.logger.info("🗑️ Import memory cleared")

    def import_file(
        self,
        filepath: str | Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Union[List[InvoiceLine], ImportResult]:
        """
        Importuj fajl uz auto-kombinovanje parova Excel+PDF ili Invoice+PackingList.

        Redoslijed:
        1. Provjeri može li se kombinovati sa prethodnim importom
        2. Za PDF: detektuj packing listu (prije registry-a)
        3. Delegiraj registry-u za parsiranje
        4. Sačuvaj stanje za sljedeći import
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Fajl ne postoji: {filepath}")

        self.logger.info(f"🔄 Importing: {filepath.name}")

        try:
            # 1. Pokušaj kombinovanje sa prethodnim importom
            combined = self._try_combine_with_previous(filepath)
            if combined is not None:
                self.logger.info(f"✅ Kombinovani import: {filepath.name}")
                return combined

            ext = filepath.suffix.lower()

            # 2. Za PDF: provjeri da li je packing lista PRIJE registry-a
            if ext == ".pdf":
                packing_result = self._try_import_as_packing_list(filepath)
                if packing_result is not None:
                    self.last_import_result = packing_result
                    self.last_import_path = str(filepath)
                    self.last_import_type = "packing_list"
                    self.logger.info("💡 Packing lista sačuvana - čeka Invoice sa istim brojem")
                    return packing_result

            # 3. Delegiraj registry-u za parsiranje
            result = self.registry.import_file(filepath, progress_callback=progress_callback)

            # 4. Sačuvaj stanje za sljedeći import
            self._save_import_state(filepath, result)

            has_os = getattr(result, "has_origin_statement", False)
            origin_stmts = getattr(result, "origin_statements", None)
            origin_stmts_len = len(origin_stmts) if origin_stmts else 0
            self.logger.info(f"✅ Import uspješan: {filepath.name} (type={self.last_import_type}, has_origin_statement={has_os}, origin_statements={origin_stmts_len})")
            return result

        except ImportException as e:
            self.logger.error(f"❌ Import failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"❌ Neočekivana greška tokom importa")
            raise ImportException(f"Import failed: {e}") from e

    def _try_import_as_packing_list(self, filepath: Path) -> Optional[ImportResult]:
        """
        Pokušaj import kao packing lista (samo za PDF koji nisu poznati vendor format).
        Vraća ImportResult ako je packing lista, None inače.
        """
        try:
            from importers.smart_pdf_importer import _detect_pdf_format
            from importers.packing_list_parser import detect_packing_list, parse_packing_list

            pdf_format = _detect_pdf_format(str(filepath))
            if pdf_format in _KNOWN_VENDOR_FORMATS:
                return None  # Poznati vendor → nije packing lista

            if not detect_packing_list(str(filepath)):
                return None

            self.logger.info("📦 Detektovana PACKING LISTA")
            packing_items = parse_packing_list(str(filepath))
            invoice_items = [item.to_invoice_line() for item in packing_items]

            return ImportResult(
                items=invoice_items,
                bruto_kg=sum(item.bruto_kg for item in packing_items),
                neto_kg=sum(item.neto_kg for item in packing_items),
                invoice_name="PACKING LIST",
                currency="EUR",
            )
        except Exception as e:
            self.logger.warning(f"Packing list detekcija nije uspjela: {e}")
            return None

    def _save_import_state(self, filepath: Path, result) -> None:
        """Detektuj tip importa i sačuvaj stanje za sljedeći import."""
        ext = filepath.suffix.lower()
        self.last_import_result = result
        self.last_import_path = str(filepath)

        if ext in (".xlsx", ".xls", ".xlsm"):
            try:
                from importers.blagic_loren_importer import detect_blagic_loren_excel
                if detect_blagic_loren_excel(str(filepath)):
                    self.last_import_type = "loren_excel"
                    self.logger.info("💡 Loren Excel sačuvan - čeka Loren PDF sa istim brojem")
                    return
                    
                from importers.sumaprom_excel_parser import detect_sumaprom_excel
                if detect_sumaprom_excel(str(filepath)):
                    self.last_import_type = "sumaprom_excel"
                    self.logger.info("💡 ŠUMAPROM Excel sačuvan - čeka ŠUMAPROM PDF sa istim brojem")
                    return
            except Exception:
                pass
            self.last_import_type = "excel"

        elif ext == ".pdf":
            try:
                from importers.smart_pdf_importer import _detect_pdf_format
                fmt = _detect_pdf_format(str(filepath))
                if fmt == "blagic_loren":
                    self.last_import_type = "loren_pdf"
                    self.logger.info("💡 Loren PDF sačuvan - čeka Loren Excel sa istim brojem")
                    return
                elif fmt == "sumaprom":
                    self.last_import_type = "sumaprom_pdf"
                    self.logger.info("💡 ŠUMAPROM PDF sačuvan - čeka ŠUMAPROM Excel sa istim brojem")
                    return
            except Exception:
                pass
            self.last_import_type = "invoice"

        else:
            self.last_import_type = "other"

    def _try_combine_with_previous(
        self, filepath: Path
    ) -> Optional[Union[List[InvoiceLine], ImportResult]]:
        """
        Provjeri može li se trenutni fajl kombinovati sa prethodnim importom.

        CASE 1: Prethodni Loren Excel + trenutni Loren PDF
        CASE 2: Prethodni Loren PDF + trenutni Loren Excel
        CASE 3: Prethodni Invoice + trenutni Packing List
        CASE 4: Prethodni Packing List + trenutni Invoice
        """
        if not self.last_import_path or self.last_import_result is None:
            return None

        ext = filepath.suffix.lower()
        last_ext = Path(self.last_import_path).suffix.lower()
        current_basename = filepath.stem
        last_basename = Path(self.last_import_path).stem

        logger.debug("=" * 60)
        logger.debug(f"🔍 _try_combine_with_previous: {filepath.name}")
        logger.debug(f"   Prethodni: {Path(self.last_import_path).name} (type={self.last_import_type})")

        try:
            from importers.blagic_loren_importer import detect_blagic_loren_excel
            from importers.blagic_loren_pdf_parser import detect_blagic_loren_pdf
            from importers.blagic_combined_importer import combine_blagic_excel_and_pdf

            current_is_loren_excel = ext in (".xlsx", ".xls") and detect_blagic_loren_excel(str(filepath))
            current_is_loren_pdf = ext == ".pdf" and detect_blagic_loren_pdf(str(filepath))
            last_is_loren_excel = self.last_import_type == "loren_excel"
            last_is_loren_pdf = self.last_import_type == "loren_pdf"

            logger.debug(f"   current_is_loren_excel={current_is_loren_excel}")
            logger.debug(f"   current_is_loren_pdf={current_is_loren_pdf}")

            # CASE 1: Excel → PDF
            if last_is_loren_excel and current_is_loren_pdf:
                if _similar_invoice_number(current_basename, last_basename):
                    logger.info("   ✅ CASE 1: Excel+PDF par - kombinujem")
                    combined_items, stats = combine_blagic_excel_and_pdf(
                        self.last_import_path, str(filepath)
                    )
                    self.clear_memory()
                    return ImportResult(
                        items=combined_items,
                        bruto_kg=stats.get("bruto_kg", 0.0),
                        neto_kg=stats.get("neto_kg", 0.0),
                        invoice_name=filepath.stem,
                        currency=stats.get("currency", "EUR"),
                        is_combined=True,
                        import_type="loren_excel",
                        has_origin_statement=stats.get("has_origin_statement", False),
                        origin_statements=stats.get("origin_statements", []),
                    )

            # CASE 2: PDF → Excel
            elif last_is_loren_pdf and current_is_loren_excel:
                if _similar_invoice_number(current_basename, last_basename):
                    logger.info("   ✅ CASE 2: PDF+Excel par - kombinujem")
                    combined_items, stats = combine_blagic_excel_and_pdf(
                        str(filepath), self.last_import_path
                    )
                    self.clear_memory()
                    return ImportResult(
                        items=combined_items,
                        bruto_kg=stats.get("bruto_kg", 0.0),
                        neto_kg=stats.get("neto_kg", 0.0),
                        invoice_name=filepath.stem,
                        currency=stats.get("currency", "EUR"),
                        is_combined=True,
                        import_type="loren_excel",
                        has_origin_statement=stats.get("has_origin_statement", False),
                        origin_statements=stats.get("origin_statements", []),
                    )

        except Exception as e:
            self.logger.warning(f"Loren kombinovanje nije uspjelo: {e}")

        # CASE 1B & 2B: ŠUMAPROM Excel + PDF kombinovanje
        try:
            from importers.sumaprom_excel_parser import detect_sumaprom_excel
            from importers.sumaprom_pdf_parser import detect_sumaprom_pdf  # Will be created when needed
            from importers.sumaprom_combined_importer import combine_sumaprom_excel_and_pdf  # Will be created

            current_is_sumaprom_excel = ext in (".xlsx", ".xls") and detect_sumaprom_excel(str(filepath))
            current_is_sumaprom_pdf = ext == ".pdf" and detect_sumaprom_pdf(str(filepath))
            last_is_sumaprom_excel = self.last_import_type == "sumaprom_excel"
            last_is_sumaprom_pdf = self.last_import_type == "sumaprom_pdf"

            logger.debug(f"   current_is_sumaprom_excel={current_is_sumaprom_excel}")
            logger.debug(f"   current_is_sumaprom_pdf={current_is_sumaprom_pdf}")

            # CASE 1B: ŠUMAPROM Excel → PDF
            if last_is_sumaprom_excel and current_is_sumaprom_pdf:
                if _similar_invoice_number(current_basename, last_basename):
                    logger.info("   ✅ CASE 1B: ŠUMAPROM Excel+PDF par - kombinujem")
                    combined_items, stats = combine_sumaprom_excel_and_pdf(
                        self.last_import_path, str(filepath)
                    )
                    self.clear_memory()
                    return ImportResult(
                        items=combined_items,
                        bruto_kg=stats.get("bruto_kg", 0.0),
                        neto_kg=stats.get("neto_kg", 0.0),
                        invoice_name=filepath.stem,
                        currency=stats.get("currency", "EUR"),
                        is_combined=True,
                        import_type="sumaprom_excel",
                        warnings=stats.get("warnings", []),
                    )

            # CASE 2B: ŠUMAPROM PDF → Excel
            elif last_is_sumaprom_pdf and current_is_sumaprom_excel:
                if _similar_invoice_number(current_basename, last_basename):
                    logger.info("   ✅ CASE 2B: ŠUMAPROM PDF+Excel par - kombinujem")
                    combined_items, stats = combine_sumaprom_excel_and_pdf(
                        str(filepath), self.last_import_path
                    )
                    self.clear_memory()
                    return ImportResult(
                        items=combined_items,
                        bruto_kg=stats.get("bruto_kg", 0.0),
                        neto_kg=stats.get("neto_kg", 0.0),
                        invoice_name=filepath.stem,
                        currency=stats.get("currency", "EUR"),
                        is_combined=True,
                        import_type="sumaprom_excel",
                        warnings=stats.get("warnings", []),
                    )

        except ImportError:
            # ŠUMAPROM PDF parser još nije kreiran - ovo je očekivano
            logger.debug("   ℹ️  ŠUMAPROM PDF parser još nije dostupan")
        except Exception as e:
            self.logger.warning(f"ŠUMAPROM kombinovanje nije uspjelo: {e}")

        # CASE 3 & 4: Invoice + Packing List
        try:
            from importers.packing_list_parser import (
                detect_packing_list, parse_packing_list, combine_invoice_and_packing
            )
            from importers.smart_pdf_importer import _detect_pdf_format

            # Provjeri da li je TRENUTNI fajl packing lista (samo ne-vendor PDF)
            pdf_format = _detect_pdf_format(str(filepath)) if ext == ".pdf" else "generic"
            is_known_vendor = pdf_format in _KNOWN_VENDOR_FORMATS
            current_is_packing = (
                ext == ".pdf"
                and not is_known_vendor
                and detect_packing_list(str(filepath))
            )
            last_is_invoice = self.last_import_type in ("invoice", "invoice_improved", "generic")
            last_is_packing = self.last_import_type == "packing_list"
            current_is_pdf_invoice = ext == ".pdf"

            logger.debug(f"   current_is_packing={current_is_packing}, last_is_invoice={last_is_invoice}")

            # CASE 3: Invoice pa Packing List
            if last_is_invoice and current_is_packing:
                if _similar_invoice_number(current_basename, last_basename):
                    logger.info("   ✅ CASE 3: Invoice+PackingList - kombinujem")
                    packing_items = parse_packing_list(str(filepath))
                    prev = self.last_import_result
                    invoice_items = prev.items if isinstance(prev, ImportResult) else prev
                    combined = combine_invoice_and_packing(invoice_items, packing_items)
                    self.clear_memory()
                    return ImportResult(
                        items=combined,
                        bruto_kg=sum(getattr(i, "bruto_kg", 0) for i in packing_items),
                        neto_kg=sum(getattr(i, "neto_kg", 0) for i in packing_items),
                        invoice_name=last_basename,
                        currency="EUR",
                        is_combined=True,
                        has_origin_statement=getattr(prev, "has_origin_statement", False),
                        origin_statements=getattr(prev, "origin_statements", []),
                    )

            # CASE 4: Packing List pa Invoice
            elif last_is_packing and current_is_pdf_invoice:
                if _similar_invoice_number(current_basename, last_basename):
                    logger.info("   ✅ CASE 4: PackingList+Invoice - kombinujem")
                    # Importuj invoice via registry
                    invoice_result = self.registry.import_file(filepath)
                    invoice_items = (
                        invoice_result.items
                        if isinstance(invoice_result, ImportResult)
                        else invoice_result
                    )
                    packing_items_raw = self.last_import_result
                    # Packing items su već InvoiceLine (konvertovani pri prvom importu)
                    combined = combine_invoice_and_packing(
                        invoice_items,
                        packing_items_raw.items if isinstance(packing_items_raw, ImportResult) else packing_items_raw
                    )
                    bruto = invoice_result.bruto_kg if isinstance(invoice_result, ImportResult) else 0.0
                    neto = invoice_result.neto_kg if isinstance(invoice_result, ImportResult) else 0.0
                    self.clear_memory()
                    return ImportResult(
                        items=combined,
                        bruto_kg=bruto,
                        neto_kg=neto,
                        invoice_name=current_basename,
                        currency="EUR",
                        is_combined=True,
                        has_origin_statement=getattr(invoice_result, "has_origin_statement", False),
                        origin_statements=getattr(invoice_result, "origin_statements", []),
                    )

        except Exception as e:
            self.logger.warning(f"Invoice+PackingList kombinovanje nije uspjelo: {e}")

        logger.warning("   ⚠️  Nije par - nema kombinovanja")
        return None

    def can_import(self, filepath: str | Path) -> bool:
        filepath = Path(filepath)
        return self.registry.find_strategy(filepath) is not None

    def get_supported_formats(self) -> List[str]:
        formats = []
        for ext in ["pdf", "xlsx", "xls", "xlsm", "xml"]:
            test = Path(f"test.{ext}")
            if self.registry.find_strategy(test) and f".{ext}" not in formats:
                formats.append(f".{ext}")
        return formats


# ============================================================
# SINGLETON
# ============================================================

_import_service_instance: Optional[ImportService] = None


def get_import_service() -> ImportService:
    """Vrati singleton ImportService instancu."""
    global _import_service_instance
    if _import_service_instance is None:
        _import_service_instance = ImportService()
    return _import_service_instance
