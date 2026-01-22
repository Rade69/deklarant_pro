"""Database models za perzistenciju Draft-a."""

from datetime import datetime
from typing import Optional


class DraftModel:
    """Database model za DeclarationDraft."""

    def __init__(
        self,
        id: Optional[int] = None,
        broj_deklaracije: str = "",
        datum_kreiranja: Optional[datetime] = None,
        datum_izmene: Optional[datetime] = None,
        status: str = "draft",  # draft, submitted, approved
        json_data: str = "",  # Serialized Draft JSON
    ):
        """
        Inicijalizuje draft model.

        Args:
            id: Database ID
            broj_deklaracije: Broj deklaracije
            datum_kreiranja: Datum kreiranja
            datum_izmene: Datum poslednje izmene
            status: Status draft-a
            json_data: JSON reprezentacija Draft-a
        """
        self.id = id
        self.broj_deklaracije = broj_deklaracije
        self.datum_kreiranja = datum_kreiranja or datetime.now()
        self.datum_izmene = datum_izmene or datetime.now()
        self.status = status
        self.json_data = json_data


class AttachmentModel:
    """Database model za priloge (fajlove)."""

    def __init__(
        self,
        id: Optional[int] = None,
        draft_id: Optional[int] = None,
        file_name: str = "",
        file_path: str = "",
        file_type: str = "",
        file_size: int = 0,
        datum_upload: Optional[datetime] = None,
    ):
        """
        Inicijalizuje attachment model.

        Args:
            id: Database ID
            draft_id: ID povezanog draft-a
            file_name: Ime fajla
            file_path: Putanja do fajla
            file_type: Tip fajla (pdf, xlsx, xml...)
            file_size: Veličina fajla u bajtovima
            datum_upload: Datum upload-a
        """
        self.id = id
        self.draft_id = draft_id
        self.file_name = file_name
        self.file_path = file_path
        self.file_type = file_type
        self.file_size = file_size
        self.datum_upload = datum_upload or datetime.now()
