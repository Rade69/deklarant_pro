# services/naimenovanja_service.py

"""
Naimenovanja Service - Business Logic Layer

Service layer za Naimenovanja tab - potpuno Qt-independent.
Odgovoran za:
- Tariff lookup i validation
- Naimenovanje draft conversion
- Origin statement detection
- Business rules enforcement
"""

import logging
import re
from typing import Dict, Any, List, Optional
from core.draft.draft import DeclarationDraft, NaimenovanjeDraft, InvoiceLine
from services.naimenovanja.tariff_service import TariffService
from services.origin_statement_detector import OriginStatementDetector
from services.naimenovanja.models import (
    DocumentMergeResult,
    TariffLookupResult,
    XmlImportResult,
)


class NaimenovanjaService:
    """
    Service layer za Naimenovanja tab - Qt independent!
    
    Odgovornosti:
    - Business logic (tariff lookup, validation, origin detection)
    - Data conversion (Draft ↔ View data)
    - Tariff suggestions
    
    NEMA:
    - UI kreiranje
    - Signal/Slot mehanizam
    - Direct database pristup
    """
    
    def __init__(self):
        """Inicijalizacija bez Qt dependency."""
        self.tariff_service: Optional[TariffService] = None
        self.origin_detector: Optional[OriginStatementDetector] = None
    
    def _get_tariff_service(self, tab_reference=None) -> TariffService:
        """Lazy initialization of TariffService."""
        if self.tariff_service is None:
            self.tariff_service = TariffService(tab_reference)
        return self.tariff_service
    
    def _get_origin_detector(self) -> OriginStatementDetector:
        """Lazy initialization of OriginStatementDetector."""
        if self.origin_detector is None:
            self.origin_detector = OriginStatementDetector()
        return self.origin_detector
    
    # ============================================================
    # KRITIČNE METODE - DRAFT CONVERSION
    # ============================================================
    
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Konvertuj DeclarationDraft → View data format.
        
        Args:
            draft: DeclarationDraft objekat
        
        Returns:
            Dict sa podacima spremnim za View.set_data()
        """
        import uuid
        
        data = {
            'current_item_index': 0,
            'items': [],
        }
        
        # Convert NaimenovanjeDraft items to dict format
        if hasattr(draft, 'items') and draft.items:
            for i, item in enumerate(draft.items):
                if isinstance(item, NaimenovanjeDraft):
                    item_data = {
                        'item_id': getattr(item, 'item_id', str(uuid.uuid4())),
                        'ordinal_no': getattr(item, 'ordinal_no', ''),
                        'tariff_code': getattr(item, 'tariff_code', ''),
                        'goods_trade_name': getattr(item, 'goods_trade_name', ''),
                        'origin_country_code': getattr(item, 'origin_country_code', ''),
                        'package_code': getattr(item, 'package_code', ''),
                        'package_name': getattr(item, 'package_name', ''),
                        'package_qty': getattr(item, 'package_qty', 0),
                        'container_number1': getattr(item, 'container_number1', ''),
                        'container_number2': getattr(item, 'container_number2', ''),
                        'goods_description': getattr(item, 'goods_description', ''),
                    }
                    data['items'].append(item_data)
        
        data['current_item_index'] = 0  # Start with first item
        self._log_operation("load_from_draft", True, len(data['items']))
        return data
    
    def save_to_draft(
        self,
        draft: DeclarationDraft,
        data: Dict[str, Any]
    ) -> DeclarationDraft:
        """
        Konvertuj View data → DeclarationDraft.
        
        Args:
            draft: DeclarationDraft objekat
            data: View data dict
        
        Returns:
            Ažurirani Draft objekat
        """
        # Update items from data
        if 'items' in data:
            draft.items = []
            for item_data in data['items']:
                naimenovanje = NaimenovanjeDraft(
                    item_id=item_data.get('item_id', ''),
                    ordinal_no=item_data.get('ordinal_no', 0),
                    tariff_code=item_data.get('tariff_code', ''),
                    goods_trade_name=item_data.get('goods_trade_name', ''),
                    origin_country_code=item_data.get('origin_country_code', ''),
                    package_code=item_data.get('package_code', ''),
                    package_name=item_data.get('package_name', ''),
                    package_qty=item_data.get('package_qty', 0),
                    container_number1=item_data.get('container_number1', ''),
                    container_number2=item_data.get('container_number2', ''),
                    goods_description=item_data.get('goods_description', ''),
                )
                draft.items.append(naimenovanje)
        
        self._log_operation("save_to_draft", True, len(draft.items))
        return draft
    
    # ============================================================
    # BUSINESS LOGIC - TARIFF OPERATIONS
    # ============================================================
    
    def lookup_tariff_description(
        self,
        tariff_code: str,
        tab_reference=None
    ) -> str:
        """
        Potraži opis tarife za dati tarifni broj.
        
        Args:
            tariff_code: Tarifni broj
            tab_reference: Reference to tab for database access
        
        Returns:
            Opis tarife ili prazan string
        """
        service = self._get_tariff_service(tab_reference)
        return service.load_tariff_description(tariff_code)
    
    def suggest_tariff(
        self,
        goods_trade_name: str,
        origin_country_code: str,
        tab_reference=None
    ) -> List[Dict[str, Any]]:
        """
        Sugeriši tarifni broj na osnovu naziva robe.
        
        Koristi HybridTariffAgent za AI-potpomognute prijedloge.

        Args:
            goods_trade_name: Naziv robe
            origin_country_code: Šifra zemlje porijekla
            tab_reference: Reference to tab

        Returns:
            Lista prijedloga sa tarifnim brojevima
        """
        # Koristi TariffFacade — docs/architecture/TARIFF_FACADE_REFACTORING.md
        from services.tariff_facade import TariffFacade

        r = TariffFacade.get_instance().suggest(goods_trade_name, zemlja=origin_country_code)

        suggestions = []
        if r.tarifni_broj:
            suggestions.append({
                'tariff_code': r.tarifni_broj,
                'description': r.obrazlozenje,
                'similarity': r.confidence,
                'method': r.source,
                'needs_review': r.needs_review,
            })

        return suggestions
    
    def validate_tariff(self, tariff_code: str, tab_reference=None) -> bool:
        """
        Validiraj da li tarifni broj postoji u zvaničnoj tarifi.
        
        Args:
            tariff_code: Tarifni broj za validaciju
            tab_reference: Reference to tab
        
        Returns:
            True ako tarifni broj postoji
        """
        service = self._get_tariff_service(tab_reference)
        return service.validate_tariff(tariff_code)
    
    def extract_short_code(self, tariff_code: str) -> str:
        """
        Ekstraktuj kraći kod iz tarifnog broja (6 cifara).
        
        Args:
            tariff_code: Puni tarifni broj
        
        Returns:
            Kraći kod (6 cifara)
        """
        if not tariff_code:
            return ""
        
        # Extract only digits
        digits = ''.join(filter(str.isdigit, tariff_code))
        
        # Return first 6 digits
        return digits[:6] if len(digits) >= 6 else digits
    
    def clean_tariff_description(self, description: str) -> str:
        """
    Čisti opis tarife od tehničkih podataka.
        
        Args:
            description: Opis tarife
        
        Returns:
            Pročišćeni opis
        """
        if not description:
            return ""
        
        import re
        
        # Remove sequences of numbers that appear to be technical codes
        cleaned = re.sub(r'\b\d+\s+\d+\s+\d+\s+\d+(\s+\d+)*\s*$', '', description)
        
        # Remove trailing sequences of numbers separated by spaces
        cleaned = re.sub(r'\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s*$', '', cleaned)
        
        # Remove any remaining trailing numeric sequences
        cleaned = re.sub(r'\s+\d+\s+\d+\s+\d+\s*$', '', cleaned)
        
        # Clean up trailing whitespace
        cleaned = cleaned.rstrip()
        
        # If cleaning resulted in empty string, return original
        return cleaned if cleaned.strip() else description
    
    # ============================================================
    # BUSINESS LOGIC - ORIGIN DETECTION
    # ============================================================
    
    def detect_origin_statement(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detektuj izjavu o poreklu u tekstu.
        
        Args:
            text: Tekst PDF fakture
        
        Returns:
            Dict sa podacima o izjavi ili None
        """
        detector = self._get_origin_detector()
        result = detector.detect_in_text(text)
        
        if result:
            return {
                'jezik': getattr(result, 'jezik', ''),
                'tip_izjave': getattr(result, 'tip_izjave', ''),
                'origin_country': getattr(result, 'origin_country', ''),
                'authorization_number': getattr(result, 'authorization_number', ''),
                'full_text': getattr(result, 'full_text', ''),
                'confidence': getattr(result, 'confidence', 1.0),
            }
        
        return None
    
    def detect_all_origin_statements(self, text: str) -> List[Dict[str, Any]]:
        """
        Detektuj SVE izjave o poreklu u tekstu.
        
        Args:
            text: Tekst PDF fakture
        
        Returns:
            Lista detektovanih izjava
        """
        detector = self._get_origin_detector()
        results = detector.detect_all_in_text(text)
        
        statements = []
        for result in results:
            statements.append({
                'jezik': getattr(result, 'jezik', ''),
                'tip_izjave': getattr(result, 'tip_izjave', ''),
                'origin_country': getattr(result, 'origin_country', ''),
                'authorization_number': getattr(result, 'authorization_number', ''),
                'full_text': getattr(result, 'full_text', ''),
                'confidence': getattr(result, 'confidence', 1.0),
                'item_range': getattr(result, 'item_range', None),
            })
        
        return statements
    
    # ============================================================
    # BUSINESS LOGIC - VALIDATION
    # ============================================================
    
    def validate_naimenovanje(self, item_data: Dict[str, Any]) -> List[str]:
        """
        Validiraj naimenovanje.
        
        Args:
            item_data: Dict sa podacima naimenovanja
        
        Returns:
            Lista error poruka
        """
        errors = []
        
        # Required fields
        if not item_data.get('tariff_code'):
            errors.append("Tarifni broj je obavezan")
        
        if not item_data.get('goods_trade_name'):
            errors.append("Naziv robe je obavezan")
        
        # Tariff code format (should be numeric)
        tariff = item_data.get('tariff_code', '')
        if tariff and not tariff.isdigit():
            errors.append("Tarifni broj mora sadržavati samo cifre")
        
        # Package quantity
        package_qty = item_data.get('package_qty', 0)
        if package_qty < 0:
            errors.append("Količina paketa ne može biti negativna")
        
        return errors
    
    def validate_all_naimenovanja(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[int, List[str]]:
        """
        Validiraj sva naimenovanja.
        
        Args:
            items: Lista naimenovanja
        
        Returns:
            Dict {index: [error_messages]}
        """
        errors_by_index = {}
        
        for i, item in enumerate(items):
            errors = self.validate_naimenovanje(item)
            if errors:
                errors_by_index[i] = errors
        
        return errors_by_index
    
    # ============================================================
    # PRIVATE HELPERS
    # ============================================================
    
    def _log_operation(self, operation: str, success: bool, count: int = 0):
        """Logging helper."""
        logger = logging.getLogger("deklarant_pro.services.naimenovanja")
        status = "✅" if success else "❌"
        logger.info(f"{status} {operation}: {count} items")

    # ============================================================
    # Čiste kalkulacije (Faza 2 — izdvojene iz NaimenovanjaView)
    # ============================================================

    @staticmethod
    def parse_cost(val) -> float:
        """Parse trošak iz stringa (podržava zarez i tačku)."""
        try:
            return float(str(val or 0).replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def compute_pd_codes(item=None, draft=None) -> str:
        docs = []
        if draft is not None:
            docs.extend(getattr(draft, "header_attached_documents", []) or [])
        if item is not None:
            docs.extend(getattr(item, "attached_documents", []) or [])
        codes = []
        seen = set()
        for doc in docs:
            code = (getattr(doc, "code", "") or "").strip().upper()
            if not code or not getattr(doc, "from_rule", False):
                continue
            if code in {"PE1", "PE2", "PE3"} or code in seen:
                continue
            seen.add(code)
            codes.append(code)
        return " ".join(codes)

    @staticmethod
    def compute_statistical_value(item, draft=None) -> str:
        value = float(getattr(item, "item_value", 0.0) or 0.0)
        if value <= 0:
            return ""
        if draft is None:
            return f"{value:.2f}"
        total = sum(float(getattr(it, "item_value", 0.0) or 0.0) for it in draft.items)
        if total <= 0:
            return ""
        kurs = float(getattr(draft, "kurs", 1.0) or 1.0)
        freight = NaimenovanjaService.parse_cost(getattr(draft, "trosak_1", 0))
        result = round(value * kurs, 2) + freight * (value / total)
        if result > 0:
            return f"{result:.2f}"
        return ""

    @staticmethod
    def resolve_supplementary_unit(tariff_code: str) -> str:
        """Vrati ASYCUDA kod dopunske JM za tarifni broj, ili '' ako ne postoji."""
        try:
            from services.naimenovanja.create_naimenovanja_service import get_supplementary_unit
            return get_supplementary_unit(tariff_code)
        except Exception:
            return ""

    def build_tariff_lookup(self, tariff_code: str) -> TariffLookupResult:
        code = self.normalize_field_value("tariff_code", tariff_code)
        full, short = self._get_tariff_service().load_tariff_descriptions(code)
        warnings = []
        if code and not full and not short:
            warnings.append(
                f"Tarifni broj '{code}' nije pronađen u zvaničnoj tarifi"
            )
        return TariffLookupResult(
            tariff_code=code,
            full_description=full,
            short_description=short,
            supplementary_unit_code=self.resolve_supplementary_unit(code),
            warnings=warnings,
        )

    @staticmethod
    def add_tariff_documents(draft, tariff_code: str) -> int:
        from core.draft.draft import AttachedDocument
        from services.tariff_controls_service import get_required_docs
        from services.tariff_doc_history_service import (
            get_tariff_doc_history_service,
        )

        if not tariff_code or len(tariff_code.strip()) < 4:
            return 0
        candidates = []
        try:
            candidates.extend(get_required_docs(tariff_code) or [])
        except Exception:
            pass
        try:
            candidates.extend(
                get_tariff_doc_history_service().get_suggested_docs(
                    tariff_code, min_count=3
                ) or []
            )
        except Exception:
            pass

        header_docs = getattr(draft, "header_attached_documents", None)
        if header_docs is None:
            return 0
        existing = {
            (getattr(doc, "code", "") or "").strip().upper()
            for doc in header_docs
        }
        added = 0
        for candidate in candidates:
            code = (candidate.get("code") or "").strip().upper()
            if not code or code in existing:
                continue
            header_docs.append(AttachedDocument(
                code=code,
                name=candidate.get("name") or code,
                number="",
                from_rule=False,
            ))
            existing.add(code)
            added += 1
        return added

    @staticmethod
    def assigned_invoice_lines(draft, item) -> list:
        ordinal = getattr(item, "ordinal_no", 0)
        return [
            line for line in (getattr(draft, "invoice_lines", []) or [])
            if getattr(line, "assigned_naimenovanje_ordinal", 0) == ordinal
        ]

    @staticmethod
    def normalize_pe_document(value: str) -> str:
        text = " ".join((value or "").strip().split())
        if not text:
            return ""
        parts = text.split(" ", 1)
        code = parts[0].upper()
        if code not in {"PE1", "PE2", "PE3"}:
            return text
        return code + (f" {parts[1]}" if len(parts) > 1 else "")

    @staticmethod
    def clear_secondary_pe_documents(item) -> bool:
        changed = False
        for field_name in (
            "attached_document1",
            "attached_document2",
            "attached_document3",
            "attached_document5",
        ):
            value = (getattr(item, field_name, "") or "").strip()
            code = value.split(" ", 1)[0].upper() if value else ""
            if code in {"PE1", "PE2", "PE3"}:
                setattr(item, field_name, "")
                changed = True
        return changed

    def apply_pe_document(self, draft, current_index: int, value: str) -> DocumentMergeResult:
        from core.draft.draft import AttachedDocument

        normalized = self.normalize_pe_document(value)
        items = getattr(draft, "items", []) or []
        if not items or current_index < 0 or current_index >= len(items):
            return DocumentMergeResult(warnings=["Nema aktivnog naimenovanja"])

        for index, item in enumerate(items):
            has_preference = bool(
                (getattr(item, "preference_code", "") or "").strip()
            )
            if index == current_index or not normalized or has_preference:
                item.attached_document4 = normalized
            self.clear_secondary_pe_documents(item)

        entries = []
        seen = set()
        for item in items:
            doc = self.normalize_pe_document(
                getattr(item, "attached_document4", "") or ""
            )
            if doc and not (getattr(item, "preference_code", "") or "").strip():
                item.attached_document4 = ""
                continue
            item.attached_document4 = doc
            parts = doc.split(" ", 1) if doc else []
            code = parts[0] if parts else ""
            number = parts[1] if len(parts) > 1 else ""
            if code in {"PE1", "PE2", "PE3"} and code not in seen:
                seen.add(code)
                entries.append((code, number))

        header_docs = list(getattr(draft, "header_attached_documents", []) or [])
        header_docs = [
            doc for doc in header_docs
            if (getattr(doc, "code", "") or "").upper() not in {"PE1", "PE2", "PE3"}
        ]
        names = {
            "PE1": "EUR.1 obrazac",
            "PE2": "Izjava na fakturi",
            "PE3": "Izjava ovlaštenog izvoznika",
        }
        for code, number in entries:
            header_docs.append(AttachedDocument(
                code=code,
                name=names[code],
                number=number,
                from_rule=code == "PE1",
            ))
        draft.header_attached_documents = header_docs
        return DocumentMergeResult(
            documents=[{"code": code, "number": number} for code, number in entries]
        )

    def import_xml(self, draft, filepath: str) -> XmlImportResult:
        from services.zaglavlje_service import ZaglavljeService
        from core.draft.draft import AttachedDocument

        service = ZaglavljeService()
        items = service.parse_naimenovanja_from_xml(filepath)
        if not items:
            return XmlImportResult(warnings=["XML fajl ne sadrži naimenovanja"])

        global_docs = []
        seen = set()
        for item in items:
            for field_name in (
                "attached_document1",
                "attached_document2",
                "attached_document3",
                "attached_document4",
                "attached_document5",
            ):
                raw = (getattr(item, field_name, "") or "").strip()
                if not raw:
                    continue
                parts = raw.split(" ", 1)
                key = (parts[0].upper(), parts[1] if len(parts) > 1 else "")
                if key not in seen:
                    seen.add(key)
                    global_docs.append({"code": key[0], "number": key[1]})

        imported_header = service.load_from_xml(filepath)
        preserved_transport = {
            name: getattr(draft, name, "")
            for name in (
                "transport_id",
                "aktivno_transport",
                "aktivno_transport_nat",
            )
        }
        service.save_to_draft(draft, imported_header)
        for name, value in preserved_transport.items():
            setattr(draft, name, value)

        draft.header_attached_documents = [
            AttachedDocument(
                code=doc["code"],
                name=doc["code"],
                number=doc["number"] if doc["code"] == "DIS" else "",
            )
            for doc in global_docs
            if doc["code"] not in {"PE1", "PE2", "PE3"}
        ]
        draft.items = items
        self.apply_pe_document(
            draft,
            0,
            getattr(items[0], "attached_document4", "") if items else "",
        )
        return XmlImportResult(
            items_count=len(items),
            global_documents=global_docs,
        )

    @staticmethod
    def normalize_field_value(field_name: str, value):
        if field_name == "package_qty":
            try:
                return int(float(value)) if value not in (None, "") else 0
            except (TypeError, ValueError):
                return 0
        if field_name in {
            "gross_mass_kg",
            "net_mass_kg",
            "item_value",
            "statistical_value",
            "supplementary_unit_qty",
        }:
            try:
                return float(value) if value not in (None, "") else 0.0
            except (TypeError, ValueError):
                return 0.0
        if field_name == "ordinal_no":
            try:
                return int(value) if value not in (None, "") else 0
            except (TypeError, ValueError):
                return 0
        if field_name == "tariff_code" and value:
            digits = re.sub(r"\D", "", str(value))[:10]
            if len(digits) == 10 and digits.endswith("00"):
                digits = digits[:8]
            return digits
        return "" if value is None else str(value)

    @staticmethod
    def format_trading_names(draft, item_index: int, max_chars: int = 280) -> str:
        """Formatuj sve nazive proizvoda iz fakture za jedno naimenovanje.

        Premješteno iz NaimenovanjaView._format_trading_names.
        """
        items = getattr(draft, "items", []) or []
        if not items or item_index >= len(items):
            return ""

        current_item = items[item_index]
        ordinal_no = current_item.ordinal_no

        assigned_lines = [
            line for line in (getattr(draft, "invoice_lines", []) or [])
            if getattr(line, "assigned_naimenovanje_ordinal", 0) == ordinal_no
        ]

        if not assigned_lines:
            return ""

        # Nazivi proizvoda
        product_names = [line.naziv_robe for line in assigned_lines if getattr(line, "naziv_robe", None)]
        nazivi_dio = ", ".join(product_names) if product_names else ""

        # Faktura info
        from collections import OrderedDict
        fakture: dict = OrderedDict()
        for line in assigned_lines:
            inv = getattr(line, "invoice_number", "") or "?"
            if inv not in fakture:
                fakture[inv] = []
            fakture[inv].append(str(line.line_no))

        faktura_parts = []
        for inv, rbs in fakture.items():
            faktura_parts.append(f"{inv} (rb. {', '.join(rbs)})")
        faktura_str = ", ".join(faktura_parts)

        faktura_dio = f"Faktura: {faktura_str}"
        heading = (getattr(current_item, "tariff_description2", "") or "").strip()
        core_parts = [part for part in (nazivi_dio, faktura_dio) if part]
        core = ", ".join(core_parts)

        if heading:
            heading_budget = max_chars - len(core) - 2
            if heading_budget >= len(heading):
                final_heading = heading
            elif heading_budget > 6:
                cut = heading[:heading_budget - 3]
                last_space = cut.rfind(" ")
                final_heading = (
                    cut[:last_space] if last_space > 0 else cut
                ) + "..."
            else:
                final_heading = ""
            result = ", ".join(
                part for part in (final_heading, nazivi_dio, faktura_dio) if part
            )
        else:
            result = core

        if len(result) > max_chars:
            fakture_len = len(faktura_dio) + 2
            nazivi_max = max_chars - fakture_len - 3
            if nazivi_max > 20 and product_names:
                truncated_names = nazivi_dio[:nazivi_max]
                last_comma = truncated_names.rfind(", ")
                if last_comma > 0:
                    truncated_names = truncated_names[:last_comma]
                result = ", ".join([truncated_names + "...", faktura_dio])
            else:
                result = result[:max_chars - 3] + "..."
        return result

    # ============================================================
    # Šifrarnici (paketovi, dokumenti) — učitavanje iz PostgreSQL
    # Premješteno iz NaimenovanjaView (nalaz 3b — DB u View sloju)
    # ============================================================

    def load_package_codes(self) -> dict:
        """Učitaj šifre pakovanja iz catalogs.pakovanja.

        Returns:
            dict: {sifra: opis} — prazan dict ako PG nije dostupan.
        """
        result = {"": ""}
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT sifra, opis FROM catalogs.pakovanja ORDER BY sifra"
                    )
                    rows = cur.fetchall()
            for r in rows:
                result[r["sifra"]] = r["opis"]
            import logging
            logging.getLogger("deklarant_pro.services.naimenovanja").info(
                f"✅ Loaded {len(rows)} package codes from database"
            )
        except Exception as e:
            import logging
            logging.getLogger("deklarant_pro.services.naimenovanja").error(
                f"❌ Error loading package codes from database: {e}"
            )
        return result

    def load_previous_documents(self) -> list:
        """Učitaj šifre prethodnih dokumenata iz catalogs.prethodni_dokumenti.

        Returns:
            list: formatirani stringovi "skraćenica – vrsta_dokumenta".
        """
        result = []
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT skracenica, vrsta_dokumenta "
                        "FROM catalogs.prethodni_dokumenti ORDER BY skracenica"
                    )
                    rows = cur.fetchall()
            result = [
                f"{r['skracenica']} – {r['vrsta_dokumenta']}" for r in rows
            ]
            import logging
            logging.getLogger("deklarant_pro.services.naimenovanja").info(
                f"✅ Učitano {len(result)} vrsta dok. iz baze (prethodni_dokumenti)"
            )
        except Exception as e:
            import logging
            logging.getLogger("deklarant_pro.services.naimenovanja").warning(
                f"⚠️ Greška pri učitavanju Rb.40 iz baze: {e}"
            )
        return result

    # ============================================================
    # Save/Navigation (Faza 4)
    # ============================================================

    @staticmethod
    def apply_form_to_item(form_data: dict, item) -> bool:
        """Primijeni vrijednosti iz forme na NaimenovanjeDraft item.

        Normalizuje vrijednosti i setuje atribute. NE dira DB.
        Preskače virtualna polja (statistical_value, pd_codes).
        """
        _VIRTUAL_FIELDS = {"statistical_value", "pd_codes"}
        changed = False
        for field_name, raw_value in form_data.items():
            if not field_name or field_name in _VIRTUAL_FIELDS:
                continue
            normalized = NaimenovanjaService.normalize_field_value(field_name, raw_value)
            if getattr(item, field_name, None) != normalized:
                setattr(item, field_name, normalized)
                changed = True
        return changed

    @staticmethod
    def sync_tariff_to_invoice_lines(
        old_tariff: str, old_suffix: str,
        new_tariff: str, new_suffix: str,
        item, draft,
    ) -> int:
        """Sinhronizuj promjenu tarifnog broja na povezane InvoiceLine stavke.

        Za grupisana naimenovanja koristi assigned_naimenovanje_ordinal,
        ne ordinal_no - 1 (kritična korekcija iz Codex plana §7.4).

        Returns:
            Broj ažuriranih InvoiceLine stavki.
        """
        if not new_tariff:
            return 0
        if new_tariff == old_tariff and new_suffix == old_suffix:
            return 0

        ordinal = getattr(item, "ordinal_no", 0)
        updated = 0
        for line in (getattr(draft, "invoice_lines", []) or []):
            if getattr(line, "assigned_naimenovanje_ordinal", 0) == ordinal:
                line.tarifni_broj = new_tariff
                line.tariff_suffix = new_suffix
                updated += 1
        return updated
