"""
Weight Manager - Upravljanje težinama
"""

from typing import Optional


class WeightManager:
    """Upravlja akumulacijom i formatiranjem težina"""

    def __init__(self):
        self.accumulated_bruto_kg: float = 0.0
        self.accumulated_neto_kg: float = 0.0

    def accumulate_weights(
        self, bruto_kg: float, neto_kg: float, replace: bool = False
    ) -> None:
        """
        Akumuliraj težine iz importa.

        Args:
            bruto_kg: Bruto težina za dodati/zamijeniti
            neto_kg: Neto težina za dodati/zamijeniti
            replace: Ako je True, zamijeni postojeće težine (za kombinovanje parova).
                     Ako je False, saberi sa postojećim (default - normalno učitavanje).
        """
        if bruto_kg > 0 or neto_kg > 0:
            if replace:
                self.accumulated_bruto_kg = bruto_kg
                self.accumulated_neto_kg = neto_kg
            else:
                self.accumulated_bruto_kg += bruto_kg
                self.accumulated_neto_kg += neto_kg

    def reset_weights(self) -> None:
        """Resetuj akumulirane težine"""
        self.accumulated_bruto_kg = 0.0
        self.accumulated_neto_kg = 0.0

    def format_weight(self, weight: float) -> str:
        """
        Formatiraj težinu sa hiljadama separatorom i bez zaokruživanja.

        Args:
            weight: Težina u kg

        Returns:
            Formatirani string (npr. "1,234.567")
        """
        if weight <= 0:
            return ""

        # Convert to string to preserve all decimals
        weight_str = f"{weight:f}".rstrip("0").rstrip(".")

        # Split into integer and decimal parts
        if "." in weight_str:
            integer_part, decimal_part = weight_str.split(".")
        else:
            integer_part = weight_str
            decimal_part = ""

        # Add thousands separator to integer part
        integer_with_sep = f"{int(integer_part):,}"

        # Combine with decimal part
        if decimal_part:
            return f"{integer_with_sep}.{decimal_part}"
        else:
            return integer_with_sep

    def get_bruto_text(self) -> str:
        """Dobij formatiranu bruto težinu za prikaz"""
        return self.format_weight(self.accumulated_bruto_kg)

    def get_neto_text(self) -> str:
        """Dobij formatiranu neto težinu za prikaz"""
        return self.format_weight(self.accumulated_neto_kg)
