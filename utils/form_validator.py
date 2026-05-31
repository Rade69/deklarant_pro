"""FormValidator - validator za form fields sa fleksibilnim pravilima."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ValidationRule:
    """Pravila za validaciju"""

    field_name: str
    is_required: bool = True
    min_length: int = 0
    max_length: int = 255


class FormValidator:
    """Validator za form fields sa fleksibilnim pravilima"""

    @staticmethod
    def validate_required_fields(fields_dict: Dict[str, str]) -> List[str]:
        """Validira obavezna polja

        Args:
            fields_dict: Dictionary gde key je ime polja, value je vrednost

        Returns:
            Lista imena polja koja nedostaju
        """
        missing_fields = []
        for field_name, field_value in fields_dict.items():
            if not field_value or not field_value.strip():
                missing_fields.append(field_name)
        return missing_fields

    @staticmethod
    def validate_with_rules(
        data: Dict[str, str], rules: List[ValidationRule]
    ) -> Dict[str, List[str]]:
        """Validira podatke prema definisanim pravilima

        Args:
            data: Podaci za validaciju
            rules: Lista validacionih pravila

        Returns:
            Dictionary sa greškama po poljima
        """
        errors = {}
        for rule in rules:
            value = data.get(rule.field_name, "")

            field_errors = []

            # Required field check
            if rule.is_required and (not value or not value.strip()):
                field_errors.append(f"{rule.field_name} je obavezno polje")

            # Length checks
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
        """Čisti i sanitizuje input tekst

        Args:
            text: Input tekst za sanitizaciju

        Returns:
            Očišćeni tekst
        """
        if not text:
            return ""
        return text.strip()