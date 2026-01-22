"""Validation rules za draft."""

from typing import Any


class ValidationError(Exception):
    """Custom validation error."""

    pass


class DraftValidator:
    """Validira Draft model prema ASYCUDA pravilima."""

    def validate_zaglavlje(self, zaglavlje: Any) -> list[str]:
        """
        Validira zaglavlje deklaracije.

        Args:
            zaglavlje: Zaglavlje model

        Returns:
            Lista grešaka (prazna lista ako nema grešaka)
        """
        errors = []

        # TODO: Implementirati validaciju
        # - Broj deklaracije format
        # - Datum deklaracije obavezan
        # - Carinarnica kod
        # - Procedura format

        return errors

    def validate_naimenovanje(self, naimenovanje: Any) -> list[str]:
        """
        Validira stavku robe.

        Args:
            naimenovanje: Naimenovanje model

        Returns:
            Lista grešaka
        """
        errors = []

        # TODO: Implementirati validaciju
        # - Tarifni broj format (10 cifara)
        # - Količina > 0
        # - Neto masa > 0
        # - Fakturna vrednost > 0
        # - Zemlja porekla kod (2 slova)
        # - Povlastica validan kod

        return errors

    def validate_draft(self, draft: Any) -> list[str]:
        """
        Validira ceo draft.

        Args:
            draft: DeclarationDraft model

        Returns:
            Lista svih grešaka
        """
        errors = []

        # Validacija zaglavlja
        # errors.extend(self.validate_zaglavlje(draft.zaglavlje))

        # Validacija svih stavki
        # for stavka in draft.naimenovanja:
        #     errors.extend(self.validate_naimenovanje(stavka))

        return errors
