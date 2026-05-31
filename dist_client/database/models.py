"""Database models za perzistenciju Draft-a."""

from datetime import datetime
from typing import Optional, Any, Dict
import json


class DraftModel:
    """Database model za DeclarationDraft."""

    def __init__(
        self,
        id: Optional[int] = None,
        broj_deklaracije: str = "",
        status: str = "draft",  # draft, submitted, approved
        data: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        """
        Inicijalizuje draft model.

        Args:
            id: Database ID
            broj_deklaracije: Broj deklaracije
            status: Status draft-a
            data: Dictionary sa podacima draft-a
            created_at: Datum kreiranja kao string
            updated_at: Datum poslednje izmene kao string
        """
        self.id = id
        self.broj_deklaracije = broj_deklaracije
        self.status = status
        self.data = data or {}
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertuje model u dictionary za JSON serializaciju.
        
        Returns:
            Dictionary sa svim podacima modela
        """
        return {
            'id': self.id,
            'broj_deklaracije': self.broj_deklaracije,
            'status': self.status,
            'data': self.data,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DraftModel':
        """
        Kreira DraftModel iz dictionary-a.
        
        Args:
            data: Dictionary sa podacima
            
        Returns:
            DraftModel instanca
        """
        return cls(
            id=data.get('id'),
            broj_deklaracije=data.get('broj_deklaracije', ''),
            status=data.get('status', 'draft'),
            data=data.get('data', {}),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )


class AttachmentModel:
    """Database model za priloge (fajlove)."""

    def __init__(
        self,
        id: Optional[int] = None,
        draft_id: Optional[int] = None,
        filename: str = "",
        filepath: str = "",
        file_type: str = "",
        size: int = 0,
        uploaded_at: Optional[str] = None,
    ):
        """
        Inicijalizuje attachment model.

        Args:
            id: Database ID
            draft_id: ID povezanog draft-a
            filename: Ime fajla
            filepath: Putanja do fajla
            file_type: Tip fajla (pdf, xlsx, xml...)
            size: Veličina fajla u bajtovima
            uploaded_at: Datum upload-a kao string
        """
        self.id = id
        self.draft_id = draft_id
        self.filename = filename
        self.filepath = filepath
        self.file_type = file_type
        self.size = size
        self.uploaded_at = uploaded_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertuje model u dictionary za JSON serializaciju.
        
        Returns:
            Dictionary sa svim podacima modela
        """
        return {
            'id': self.id,
            'draft_id': self.draft_id,
            'filename': self.filename,
            'filepath': self.filepath,
            'file_type': self.file_type,
            'size': self.size,
            'uploaded_at': self.uploaded_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttachmentModel':
        """
        Kreira AttachmentModel iz dictionary-a.
        
        Args:
            data: Dictionary sa podacima
            
        Returns:
            AttachmentModel instanca
        """
        return cls(
            id=data.get('id'),
            draft_id=data.get('draft_id'),
            filename=data.get('filename', ''),
            filepath=data.get('filepath', ''),
            file_type=data.get('file_type', ''),
            size=data.get('size', 0),
            uploaded_at=data.get('uploaded_at')
        )
