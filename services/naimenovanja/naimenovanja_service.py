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

from typing import Dict, Any, List, Optional
from core.draft.draft import DeclarationDraft, NaimenovanjeDraft, InvoiceLine
from services.naimenovanja.tariff_service import TariffService
from services.origin_statement_detector import OriginStatementDetector


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
        import logging
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
    def compute_pd_codes(item) -> str:
        """Rb.44 P.D. — objedinjene šifre from_rule priloženih dokumenata."""
        from core.draft import AttachedDocument
        codes = []
        for doc in getattr(item, "attached_documents", []) or []:
            code = getattr(doc, "code", "")
            from_rule = getattr(doc, "from_rule", False)
            if code and from_rule:
                codes.append(code)
        return ", ".join(codes)

    @staticmethod
    def compute_statistical_value(item) -> str:
        """Izračunaj statističku vrijednost (Rb.46)."""
        value = getattr(item, "item_value", 0.0) or 0.0
        if value > 0:
            return f"{value:.2f}"
        return ""

    @staticmethod
    def resolve_supplementary_unit(tariff_code: str) -> str:
        """Vrati ASYCUDA kod dopunske JM za tarifni broj, ili '' ako ne postoji."""
        try:
            from services.naimenovanja.create_naimenovanja_service import get_supplementary_unit
            return get_supplementary_unit(tariff_code)
        except Exception:
            return ""

    @staticmethod
    def normalize_field_value(field_name: str, value):
        """Normalizuj vrijednost polja."""
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(value) if field_name not in ("ordinal_no",) else int(value)
        return str(value)

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
        faktura_str = "; ".join(faktura_parts)

        # Spoji
        if nazivi_dio and faktura_str:
            result = f"{nazivi_dio}\nFaktura: {faktura_str}"
        elif nazivi_dio:
            result = nazivi_dio
        else:
            result = f"Faktura: {faktura_str}"

        if len(result) > max_chars:
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
    def apply_form_to_item(form_data: dict, item) -> None:
        """Primijeni vrijednosti iz forme na NaimenovanjeDraft item.

        Normalizuje vrijednosti i setuje atribute. NE dira DB.
        Preskače virtualna polja (statistical_value, pd_codes).
        """
        _VIRTUAL_FIELDS = {"statistical_value", "pd_codes"}
        for field_name, raw_value in form_data.items():
            if not field_name or field_name in _VIRTUAL_FIELDS:
                continue
            normalized = NaimenovanjaService.normalize_field_value(field_name, raw_value)
            setattr(item, field_name, normalized)

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
