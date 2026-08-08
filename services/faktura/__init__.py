"""
Faktura service layer - Modularna arhitektura za faktura_tab_v2.py
"""

from services.faktura.constants import FakturaConstants
from services.faktura.validation_cache import ValidationCache
from services.faktura.weight_manager import WeightManager
from services.faktura.mass_calculator import MassCalculator
from services.faktura.auto_fill_service import AutoFillService
from services.faktura.import_service import ImportService
from services.faktura.export_service import ExportService
from services.faktura.validation_service import ValidationService
from services.faktura.faktura_service import FakturaService
from services.faktura.error_handler import ErrorHandler
from services.faktura.theme_manager import ThemeManager
from services.faktura.mass_workflow_service import MassWorkflowService
from services.faktura.undo_redo_service import UndoRedoService
from services.faktura.weight_guards import normalize_invoice_key
from services.faktura.xml_header_extraction import extract_header_from_xml
from services.faktura.preference_rules_service import (
    similar_partner_names,
    suggest_preference_by_country,
    should_show_eur1_dialog,
    should_show_pe2_dialog,
    auto_handle_povlastice_agent,
)
from services.faktura.header_doc_sync_service import (
    collect_pe_docs_from_items,
    build_pe_attached_documents,
    collect_inspection_docs_from_items,
    sync_duim_docs_to_items,
)

__all__ = [
    "FakturaConstants",
    "ValidationCache",
    "WeightManager",
    "MassCalculator",
    "AutoFillService",
    "ImportService",
    "ExportService",
    "ValidationService",
    "FakturaService",
    "MassWorkflowService",
    "ErrorHandler",
    "ThemeManager",
    "UndoRedoService",
    "normalize_invoice_key",
    "extract_header_from_xml",
    "similar_partner_names",
    "suggest_preference_by_country",
    "should_show_eur1_dialog",
    "should_show_pe2_dialog",
    "auto_handle_povlastice_agent",
    "collect_pe_docs_from_items",
    "build_pe_attached_documents",
    "collect_inspection_docs_from_items",
    "sync_duim_docs_to_items",
]
