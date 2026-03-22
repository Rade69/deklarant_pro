import logging
logger = logging.getLogger(__name__)
# services/export_service.py

"""
Export Service - Export fakturnih stavki u različite formate.
"""

import os
from pathlib import Path
from typing import List
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from core.draft import InvoiceLine


class ExportService:
    """Servis za export fakturnih stavki u različite formate."""

    @staticmethod
    def export_to_excel(items: List[InvoiceLine], filepath: str) -> bool:
        """
        Export stavki u Excel (.xlsx) fajl.

        Args:
            items: Lista InvoiceLine objekata
            filepath: Putanja gdje sačuvati fajl

        Returns:
            True ako je uspješno, False inače
        """
        try:
            # Kreiraj workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Faktura"

            # Header style
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            # Headers
            headers = [
                "Red.br.", "Naimenovanje", "Naziv robe", "Tarifni broj",
                "Količina", "JM", "Cijena", "Iznos", "Valuta",
                "Bruto (kg)", "Neto (kg)", "Zemlja", "Povlastica"
            ]

            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = border

            # Data rows
            for row_idx, item in enumerate(items, start=2):
                ws.cell(row=row_idx, column=1, value=item.line_no)
                ws.cell(row=row_idx, column=2, value=item.naimenovanje or "")
                ws.cell(row=row_idx, column=3, value=item.naziv_robe or "")
                ws.cell(row=row_idx, column=4, value=item.tarifni_broj or "")
                ws.cell(row=row_idx, column=5, value=item.kolicina or 0)
                ws.cell(row=row_idx, column=6, value=item.jm or "")
                ws.cell(row=row_idx, column=7, value=item.cijena_jed or 0)
                ws.cell(row=row_idx, column=8, value=item.iznos or 0)
                ws.cell(row=row_idx, column=9, value=item.valuta or "")
                ws.cell(row=row_idx, column=10, value=item.bruto_kg or 0)
                ws.cell(row=row_idx, column=11, value=item.neto_kg or 0)
                ws.cell(row=row_idx, column=12, value=item.zemlja_porijekla or "")
                ws.cell(row=row_idx, column=13, value=item.povlastica or "")

                # Apply borders to all cells
                for col_idx in range(1, len(headers) + 1):
                    ws.cell(row=row_idx, column=col_idx).border = border

            # Auto-adjust column widths
            for col_idx, header in enumerate(headers, start=1):
                max_length = len(header)
                for row in range(2, len(items) + 2):
                    cell_value = str(ws.cell(row=row, column=col_idx).value or "")
                    max_length = max(max_length, len(cell_value))

                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max_length + 2, 50)

            # Save
            wb.save(filepath)
            wb.close()

            return True

        except Exception as e:
            logger.debug(f"Error exporting to Excel: {e}")
            return False

    @staticmethod
    def export_to_csv(items: List[InvoiceLine], filepath: str) -> bool:
        """
        Export stavki u CSV fajl.

        Args:
            items: Lista InvoiceLine objekata
            filepath: Putanja gdje sačuvati fajl

        Returns:
            True ako je uspješno, False inače
        """
        try:
            import csv

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')  # Use semicolon for European format

                # Header
                writer.writerow([
                    "Red.br.", "Naimenovanje", "Naziv robe", "Tarifni broj",
                    "Količina", "JM", "Cijena", "Iznos", "Valuta",
                    "Bruto (kg)", "Neto (kg)", "Zemlja", "Povlastica"
                ])

                # Data rows
                for item in items:
                    writer.writerow([
                        item.line_no,
                        item.naimenovanje or "",
                        item.naziv_robe or "",
                        item.tarifni_broj or "",
                        item.kolicina or 0,
                        item.jm or "",
                        item.cijena_jed or 0,
                        item.iznos or 0,
                        item.valuta or "",
                        item.bruto_kg or 0,
                        item.neto_kg or 0,
                        item.zemlja_porijekla or "",
                        item.povlastica or ""
                    ])

            return True

        except Exception as e:
            logger.debug(f"Error exporting to CSV: {e}")
            return False

    @staticmethod
    def export_to_pdf(items: List[InvoiceLine], filepath: str) -> bool:
        """
        Export stavki u PDF fajl.

        Args:
            items: Lista InvoiceLine objekata
            filepath: Putanja gdje sačuvati fajl

        Returns:
            True ako je uspješno, False inače
        """
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet

            # Create PDF
            doc = SimpleDocTemplate(filepath, pagesize=landscape(A4))
            elements = []

            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("<b>Faktura - Pregled Stavki</b>", styles['Title'])
            elements.append(title)

            # Table data
            data = [[
                "Rb.", "Naziv", "Tarifa", "Qty", "JM", "Cijena",
                "Iznos", "Val", "Bruto", "Neto", "Zemlja", "Pov."
            ]]

            for item in items:
                data.append([
                    str(item.line_no),
                    (item.naziv_robe or "")[:30],  # Truncate long names
                    item.tarifni_broj or "",
                    f"{item.kolicina or 0:.2f}",
                    item.jm or "",
                    f"{item.cijena_jed or 0:.2f}",
                    f"{item.iznos or 0:.2f}",
                    item.valuta or "",
                    f"{item.bruto_kg or 0:.2f}",
                    f"{item.neto_kg or 0:.2f}",
                    item.zemlja_porijekla or "",
                    item.povlastica or ""
                ])

            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))

            elements.append(table)

            # Build PDF
            doc.build(elements)

            return True

        except ImportError:
            logger.debug("Error: reportlab not installed. Install with: pip install reportlab")
            return False
        except Exception as e:
            logger.debug(f"Error exporting to PDF: {e}")
            return False
