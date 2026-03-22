# services/audit_service.py
"""
Audit trail - logovanje svih značajnih akcija
COMPLIANCE REQUIREMENT za carinski software!
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
import json
import logging

# Setup structured logging
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# File handler - JSON format
fh = logging.FileHandler("audit.log")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(message)s"))  # Raw JSON
audit_logger.addHandler(fh)


class AuditEvent(Enum):
    """Tipovi audit event-a"""

    # Declaration lifecycle
    DECLARATION_CREATED = "declaration_created"
    DECLARATION_OPENED = "declaration_opened"
    DECLARATION_SAVED = "declaration_saved"
    DECLARATION_DELETED = "declaration_deleted"

    # Item operations
    ITEM_ADDED = "item_added"
    ITEM_MODIFIED = "item_modified"
    ITEM_DELETED = "item_deleted"

    # Critical field changes
    TARIFF_CHANGED = "tariff_changed"
    MASS_CHANGED = "mass_changed"
    PRICE_CHANGED = "price_changed"

    # Import/Export
    PDF_IMPORTED = "pdf_imported"
    XLS_IMPORTED = "xls_imported"
    XML_EXPORTED = "xml_exported"

    # Validation
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"


class AuditService:
    """Centralni audit logging service"""

    def __init__(self, db_service):
        """
        Initialize audit service

        Args:
            db_service: Database service instance (any object with execute() and fetch_all() methods)
        """
        self.db = db_service

    def log_event(
        self,
        event: AuditEvent,
        user: str,
        declaration_id: Optional[str] = None,
        item_index: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Log audit event

        Args:
            event: Tip event-a (iz enum)
            user: Korisnik koji je izvršio akciju
            declaration_id: ID deklaracije (ako relevantno)
            item_index: Index stavke (ako relevantno)
            details: Dodatni detalji (bilo koji JSON-serializable data)
            timestamp: Vrijeme event-a (default: now)
        """

        audit_record = {
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "event": event.value,
            "user": user,
            "declaration_id": declaration_id,
            "item_index": item_index,
            "details": details or {},
        }

        # Log to file (structured JSON - jedna linija po event-u)
        audit_logger.info(json.dumps(audit_record, ensure_ascii=False))

        # Log to database (opciono - za query-able audit trail)
        self._save_to_database(audit_record)

    def _save_to_database(self, record: Dict):
        """Save audit record to database"""
        query = """
            INSERT INTO audit_log 
            (timestamp, event_type, user_name, declaration_id, item_index, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        self.db.execute(
            query,
            (
                record["timestamp"],
                record["event"],
                record["user"],
                record["declaration_id"],
                record["item_index"],
                json.dumps(record["details"]),
            ),
        )

    # Convenience methods za česte akcije

    def log_item_modification(
        self,
        user: str,
        declaration_id: str,
        item_index: int,
        field: str,
        old_value: Any,
        new_value: Any,
    ):
        """Log kada korisnik modificira polje u stavci"""

        self.log_event(
            event=AuditEvent.ITEM_MODIFIED,
            user=user,
            declaration_id=declaration_id,
            item_index=item_index,
            details={
                "field": field,
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
        )

    def log_tariff_change(
        self,
        user: str,
        declaration_id: str,
        item_index: int,
        old_tariff: str,
        new_tariff: str,
    ):
        """
        KRITIČNO - logovanje promjene tarifnog broja
        Ovo je posebno značajno za carinu!
        """

        self.log_event(
            event=AuditEvent.TARIFF_CHANGED,
            user=user,
            declaration_id=declaration_id,
            item_index=item_index,
            details={
                "old_tariff": old_tariff,
                "new_tariff": new_tariff,
                "severity": "high",  # Ova promjena je kritična
            },
        )

    def log_xml_export(
        self, user: str, declaration_id: str, export_path: str, item_count: int
    ):
        """Log XML export-a"""

        self.log_event(
            event=AuditEvent.XML_EXPORTED,
            user=user,
            declaration_id=declaration_id,
            details={
                "export_path": export_path,
                "item_count": item_count,
                "format": "ASYCUDA XML",
            },
        )

    def log_validation_result(
        self,
        user: str,
        declaration_id: str,
        passed: bool,
        error_count: int = 0,
        warning_count: int = 0,
    ):
        """Log rezultat validacije"""

        event = AuditEvent.VALIDATION_PASSED if passed else AuditEvent.VALIDATION_FAILED

        self.log_event(
            event=event,
            user=user,
            declaration_id=declaration_id,
            details={"error_count": error_count, "warning_count": warning_count},
        )

    # Query methods

    def get_declaration_history(self, declaration_id: str, limit: int = 100) -> list:
        """
        Dobavi audit trail za jednu deklaraciju
        Ovo omogućava da se vidi ko je šta radio sa deklaracijom
        """

        query = """
            SELECT timestamp, event_type, user_name, details
            FROM audit_log
            WHERE declaration_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """

        return self.db.fetch_all(query, (declaration_id, limit))

    def get_user_activity(
        self, user: str, start_date: datetime, end_date: datetime
    ) -> list:
        """Dobavi sve akcije korisnika u određenom periodu"""

        query = """
            SELECT timestamp, event_type, declaration_id, details
            FROM audit_log
            WHERE user_name = %s
              AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp DESC
        """

        return self.db.fetch_all(
            query, (user, start_date.isoformat(), end_date.isoformat())
        )


# Global audit service instance
# Note: Uncomment after database service is initialized
# audit_service = AuditService(db_service)


# Usage primer:
"""
# U GUI-u, nakon što korisnik izmijeni polje:
audit_service.log_item_modification(
    user=current_user,
    declaration_id=draft.id,
    item_index=current_item_index,
    field="bruto_masa",
    old_value=old_bruto,
    new_value=new_bruto
)

# Posebno za tarifni broj (kritično!):
audit_service.log_tariff_change(
    user=current_user,
    declaration_id=draft.id,
    item_index=current_item_index,
    old_tariff="84713000",
    new_tariff="84713099"
)

# Pri XML export-u:
audit_service.log_xml_export(
    user=current_user,
    declaration_id=draft.id,
    export_path="/exports/declaration_123.xml",
    item_count=len(draft.items)
)
"""
