"""
Data model za fajl u Agent Tab-u.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List


@dataclass
class FileItem:
    """Model za jedan fajl."""

    filepath: str
    filename: str
    file_type: str          # 'PDF', 'Excel', 'XML'
    size_bytes: int
    parser: str             # Auto-detect, Master Frigo, etc.
    status: str             # Uploaded, Processing, Completed, Error
    confidence: float       # 0.0 - 1.0 (pouzdanost)
    added_at: datetime

    # Rezultati procesiranja
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    tariff_code: Optional[str] = None
    needs_review: bool = False
    error_message: Optional[str] = None

    # Parsed invoice lines i info o parseru
    invoice_lines: list = field(default_factory=list)  # List[InvoiceLine] - rezultati parsiranja
    detected_parser: str = ""  # koji parser je korišten

    # ⭐ Težine i izjave o porijeklu (iz ImportResult)
    bruto_kg: float = 0.0  # Ukupna bruto težina sa fakture
    neto_kg: float = 0.0  # Ukupna neto težina sa fakture
    has_origin_statement: bool = False  # Da li faktura ima izjavu o poreklu
    origin_statements: Optional[List] = None  # Lista izjava o poreklu
    is_combined: bool = False  # Da li je import_service kombinovao Excel+PDF

    @property
    def size_str(self) -> str:
        """Format file size."""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        else:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"

    @property
    def confidence_pct(self) -> int:
        """Confidence kao procenat."""
        return int(self.confidence * 100)

    @classmethod
    def from_filepath(cls, filepath: str) -> 'FileItem':
        """Kreiraj FileItem iz filepath-a."""
        path = Path(filepath)

        # Detect type
        ext = path.suffix.lower()
        if ext == '.pdf':
            file_type = 'PDF'
        elif ext in ['.xlsx', '.xls']:
            file_type = 'Excel'
        elif ext == '.xml':
            file_type = 'XML'
        else:
            file_type = 'Unknown'

        return cls(
            filepath=filepath,
            filename=path.name,
            file_type=file_type,
            size_bytes=path.stat().st_size,
            parser='Auto-detect',
            status='Uploaded',
            confidence=0.0,
            added_at=datetime.now()
        )
