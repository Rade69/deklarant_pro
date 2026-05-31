# core/utils/form_validator.py

"""
FormValidator i ValidationRule — generička validacija za forme.

Koristi se u Šifrarnici tabu i drugim tabovima gdje je potrebna
validacija korisničkog unosa prije slanja u servis/spremaju.
"""

from typing import Dict, List


# ============================================================
# SECTION: form-validator
# PURPOSE: Rule-based validation for form fields
# DOC: docs/sections/form-validator.md
# ============================================================


class ValidationRule:
    """Pravilo za validaciju jednog polja."""

    def __init__(
        self,
        field_name: str,
        is_required: bool = True,
        min_length: int = 0,
        max_length: int = 255,
    ):
        self.field_name = field_name
        self.is_required = is_required
        self.min_length = min_length
        self.max_length = max_length


class FormValidator:
    """Validator za form fields sa fleksibilnim pravilima.

    Ova klasa je čista (bez Qt dependency) — može se koristiti
    u servisima, CLI alatima i testovima.
    """

    @staticmethod
    def validate_required_fields(fields_dict: Dict[str, str]) -> List[str]:
        """Validira obavezna polja.

        Returns:
            Lista imena polja koja nedostaju ili su prazna.
        """
        return [
            field_name
            for field_name, field_value in fields_dict.items()
            if not field_value or not field_value.strip()
        ]

    @staticmethod
    def validate_with_rules(
        data: Dict[str, str], rules: List[ValidationRule]
    ) -> Dict[str, List[str]]:
        """Validira podatke prema definisanim pravilima.

        Returns:
            Dictionary sa greškama po poljima.
        """
        errors: Dict[str, List[str]] = {}
        for rule in rules:
            value = data.get(rule.field_name, "")
            field_errors = []

            if rule.is_required and (not value or not value.strip()):
                field_errors.append(f"{rule.field_name} je obavezno polje")

            if value:
                if len(value) < rule.min_length:
                    field_errors.append(
                        f"{rule.field_name} mora imati najmanje {rule.min_length} karaktera"
                    )
                if len(value) > rule.max_length:
                    field_errors.append(
                        f"{rule.field_name} može imati najviše {rule.max_length} karaktera"
                    )

            if field_errors:
                errors[rule.field_name] = field_errors

        return errors

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Čisti i sanitizuje input tekst (uklanja leading/trailing whitespace)."""
        return text.strip() if text else ""
