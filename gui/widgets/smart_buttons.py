"""
Deklarant Pro - Smart (Assist) Buttons
Automation helpers that make the app a TOOL, not just a form
"""

from PySide6.QtWidgets import QMessageBox
from .styled_button import StyledButton, ButtonType


class MassCalculatorButton(StyledButton):
    """
    🧮 Calculate Masses

    Auto-calculate Brutto/Netto masses based on available data.

    Logic:
    - If has brutto, no netto → estimate netto = brutto * 0.95
    - If has netto, no brutto → estimate brutto = netto * 1.05
    - If brutto < netto → validation warning
    - If both present → validate consistency
    """

    def __init__(self, parent_tab, parent=None):
        super().__init__("🧮 Izračunaj mase", ButtonType.ASSIST, None, parent)
        self.parent_tab = parent_tab
        self.clicked.connect(self._calculate_masses)

    def _calculate_masses(self):
        """Calculate or validate masses"""
        try:
            # Read current values
            bruto_text = self.parent_tab.ui.le_rubrika35.text().strip()
            neto_text = self.parent_tab.ui.le_rubrika38.text().strip()

            bruto = float(bruto_text.replace(',', '.')) if bruto_text else 0
            neto = float(neto_text.replace(',', '.')) if neto_text else 0

            # Case 1: Has brutto, no netto
            if bruto > 0 and neto == 0:
                neto = round(bruto * 0.95, 2)
                self.parent_tab.ui.le_rubrika38.setText(str(neto))
                QMessageBox.information(
                    self.parent_tab,
                    "✅ Uspješno",
                    f"Neto masa izračunata: {neto} kg\n(95% bruto mase)"
                )

            # Case 2: Has netto, no brutto
            elif neto > 0 and bruto == 0:
                bruto = round(neto * 1.05, 2)
                self.parent_tab.ui.le_rubrika35.setText(str(bruto))
                QMessageBox.information(
                    self.parent_tab,
                    "✅ Uspješno",
                    f"Bruto masa izračunata: {bruto} kg\n(105% neto mase)"
                )

            # Case 3: Validation - brutto < netto
            elif bruto > 0 and neto > 0 and bruto < neto:
                QMessageBox.warning(
                    self.parent_tab,
                    "⚠️ Greška",
                    f"Bruto masa ({bruto} kg) ne može biti manja\n"
                    f"od neto mase ({neto} kg)!"
                )

            # Case 4: Both filled and OK
            elif bruto > 0 and neto > 0:
                diff_percent = ((bruto - neto) / neto) * 100
                QMessageBox.information(
                    self.parent_tab,
                    "✅ U redu",
                    f"Bruto: {bruto} kg\n"
                    f"Neto: {neto} kg\n"
                    f"Razlika: {diff_percent:.1f}%\n\n"
                    f"Vrijednosti su validne."
                )

            # Case 5: Both empty
            else:
                QMessageBox.warning(
                    self.parent_tab,
                    "⚠️ Upozorenje",
                    "Morate unijeti barem jednu masu\n(bruto ili neto)!"
                )

            # Trigger dirty tracking if callback exists
            if self.parent_tab.on_dirty:
                self.parent_tab.on_dirty()

        except ValueError:
            QMessageBox.critical(
                self.parent_tab,
                "❌ Greška",
                "Masa mora biti broj (npr. 15.5)"
            )
        except AttributeError as e:
            QMessageBox.critical(
                self.parent_tab,
                "❌ Greška",
                f"Polje za masu nije pronađeno u UI-ju.\n\n"
                f"Greška: {str(e)}"
            )


class PackingFillerButton(StyledButton):
    """
    📦 Fill From Packing

    Automatically fill R41 (supplementary unit) from R31 (packing info).

    Logic:
    - Read R31 number of packages
    - Read R31 package type (PK, KG, etc.)
    - Copy to R41 supplementary unit
    - Ask for user confirmation
    """

    def __init__(self, parent_tab, parent=None):
        super().__init__("📦 Popuni iz pakovanja", ButtonType.ASSIST, None, parent)
        self.parent_tab = parent_tab
        self.clicked.connect(self._fill_from_packing)

    def _fill_from_packing(self):
        """Fill R41 from R31 packing info"""
        try:
            # Read R31 - number of packages
            broj_paketa = self.parent_tab.ui.le_r31_broj.text().strip()

            # Read R31 - package type
            vrsta_paketa = self.parent_tab.ui.le_r31_vrsta_naziv.text().strip()

            if not broj_paketa or not vrsta_paketa:
                QMessageBox.warning(
                    self.parent_tab,
                    "⚠️ Upozorenje",
                    "Morate prvo popuniti:\n"
                    "- Broj paketa (le_r31_broj)\n"
                    "- Vrsta paketa (le_r31_vrsta_naziv)"
                )
                return

            # Format: "9 PK" or just number
            dopunska = f"{broj_paketa} {vrsta_paketa}"

            # User confirmation
            reply = QMessageBox.question(
                self.parent_tab,
                "📦 Potvrda",
                f"Popuniti dopunsku jedinicu (R41) sa:\n\n"
                f"{dopunska}\n\n"
                f"Nastaviti?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Fill R41
                self.parent_tab.ui.te_rubrika41.setPlainText(dopunska)

                QMessageBox.information(
                    self.parent_tab,
                    "✅ Uspješno",
                    f"Dopunska jedinica popunjena:\n{dopunska}"
                )

                # Trigger dirty tracking
                if self.parent_tab.on_dirty:
                    self.parent_tab.on_dirty()

        except AttributeError as e:
            QMessageBox.critical(
                self.parent_tab,
                "❌ Greška",
                f"Potrebna polja nisu pronađena u UI-ju.\n\n"
                f"Provjerite da postoje:\n"
                f"- le_r31_broj\n"
                f"- le_r31_vrsta_naziv\n"
                f"- te_rubrika41\n\n"
                f"Greška: {str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self.parent_tab,
                "❌ Greška",
                f"Došlo je do greške:\n{str(e)}"
            )


class CurrencyConverterButton(StyledButton):
    """
    💶 Convert Currency

    Convert currency value (BAM → EUR, USD → BAM, etc.)

    PLACEHOLDER - Full implementation coming soon.
    Will include:
    - EUR → BAM (fixed rate 1.95583)
    - USD → BAM (dynamic rate)
    - API integration (exchangerate-api.com)
    """

    def __init__(self, parent_tab, parent=None):
        super().__init__("💶 Preračunaj vrijednost", ButtonType.ASSIST, None, parent)
        self.parent_tab = parent_tab
        self.clicked.connect(self._convert_currency)

    def _convert_currency(self):
        """Convert currency - PLACEHOLDER"""
        QMessageBox.information(
            self.parent_tab,
            "💶 Preračunaj vrijednost",
            "Ova funkcionalnost će biti dostupna uskoro.\n\n"
            "Planirane features:\n"
            "• EUR → BAM (fiksni kurs 1.95583)\n"
            "• USD → BAM (dinamički kurs)\n"
            "• API integracija (exchangerate-api.com)\n"
            "• Manual override opcija"
        )


class OriginLookupButton(StyledButton):
    """
    🌍 Lookup Origin Country

    Lookup country of origin based on HS code.

    PLACEHOLDER - Full implementation coming soon.
    Will include:
    - HS code lookup in tariff database
    - Suggest most common origin country for that HS
    - User can override suggestion
    """

    def __init__(self, parent_tab, parent=None):
        super().__init__("🌍 Preuzmi porijeklo", ButtonType.ASSIST, None, parent)
        self.parent_tab = parent_tab
        self.clicked.connect(self._lookup_origin)

    def _lookup_origin(self):
        """Lookup origin country - PLACEHOLDER"""
        QMessageBox.information(
            self.parent_tab,
            "🌍 Preuzmi porijeklo",
            "Ova funkcionalnost će biti dostupna uskoro.\n\n"
            "Planirane features:\n"
            "• Lookup HS koda u šifarniku\n"
            "• Predlog najčešće zemlje za taj HS\n"
            "• User može override-ovati\n"
            "• History tracking"
        )
