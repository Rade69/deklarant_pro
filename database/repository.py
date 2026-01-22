"""Repository za CRUD operacije sa Draft-om."""

from typing import List, Optional
from .models import DraftModel, AttachmentModel


class DraftRepository:
    """Repository za upravljanje Draft-ovima u bazi."""

    def __init__(self, db_path: str = "asycuda_pro.db"):
        """
        Inicijalizuje repository.

        Args:
            db_path: Putanja do SQLite database fajla
        """
        self.db_path = db_path
        # TODO: Inicijalizovati SQLite connection

    def create(self, draft: DraftModel) -> int:
        """
        Kreira novi draft u bazi.

        Args:
            draft: Draft model za čuvanje

        Returns:
            ID kreiranog draft-a
        """
        # TODO: Implementirati INSERT
        raise NotImplementedError()

    def get_by_id(self, draft_id: int) -> Optional[DraftModel]:
        """
        Vraća draft po ID-u.

        Args:
            draft_id: ID draft-a

        Returns:
            Draft model ili None ako ne postoji
        """
        # TODO: Implementirati SELECT by ID
        raise NotImplementedError()

    def get_all(self) -> List[DraftModel]:
        """
        Vraća sve draft-ove.

        Returns:
            Lista svih draft-ova
        """
        # TODO: Implementirati SELECT all
        raise NotImplementedError()

    def update(self, draft: DraftModel) -> bool:
        """
        Ažurira postojeći draft.

        Args:
            draft: Draft model sa izmenjenim podacima

        Returns:
            True ako je uspešno ažurirano
        """
        # TODO: Implementirati UPDATE
        raise NotImplementedError()

    def delete(self, draft_id: int) -> bool:
        """
        Briše draft iz baze.

        Args:
            draft_id: ID draft-a za brisanje

        Returns:
            True ako je uspešno obrisano
        """
        # TODO: Implementirati DELETE
        raise NotImplementedError()

    def search(self, query: str) -> List[DraftModel]:
        """
        Pretražuje draft-ove.

        Args:
            query: Search query (broj deklaracije, status...)

        Returns:
            Lista pronađenih draft-ova
        """
        # TODO: Implementirati SEARCH
        raise NotImplementedError()


class AttachmentRepository:
    """Repository za upravljanje prilozima."""

    def __init__(self, db_path: str = "asycuda_pro.db"):
        """Inicijalizuje repository."""
        self.db_path = db_path

    def create(self, attachment: AttachmentModel) -> int:
        """Kreira novi prilog."""
        # TODO: Implementirati
        raise NotImplementedError()

    def get_by_draft_id(self, draft_id: int) -> List[AttachmentModel]:
        """Vraća sve priloge za draft."""
        # TODO: Implementirati
        raise NotImplementedError()

    def delete(self, attachment_id: int) -> bool:
        """Briše prilog."""
        # TODO: Implementirati
        raise NotImplementedError()
