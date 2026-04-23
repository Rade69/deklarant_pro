import logging
logger = logging.getLogger(__name__)
# services/export_service.py

"""
Export Service - Export fakturnih stavki u različite formate.
"""

import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from core.draft import InvoiceLine, DeclarationDraft


class ExportService:
    """Servis za export fakturnih stavki u različite formate."""

    @staticmethod
    def export_to_excel(items: List[InvoiceLine], filepath: str, draft: Optional[DeclarationDraft] = None) -> bool:
        """
        Export stavki u Excel (.xlsx) fajl.
        Grupisano po naimenovanjima kao PDF izvoz.
        Kolone: RB, Faktura, Stavka, Naim., Naziv robe, Količina, JM,
                Vrijednost, Valuta, Tarifa, Zemlja, Povlastica, Bruto kg, Neto kg

        Args:
            items: Lista InvoiceLine objekata
            filepath: Putanja gdje sačuvati fajl
            draft: Opcioni DeclarationDraft za podatke o naimenovanjima

        Returns:
            True ako je uspješno, False inače
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            import openpyxl.utils

            wb = Workbook()
            ws = wb.active
            ws.title = "Faktura po naimenovanjima"

            # Stilovi
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")

            group_font = Font(bold=True, color="1F2937", size=11)
            group_fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")

            total_font = Font(bold=True, color="374151")
            total_fill = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")

            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            # Headers
            headers = [
                "RB", "Faktura", "Stavka", "Naim.", "Naziv robe", "Količina", "JM",
                "Vrijednost", "Valuta", "Tarifa", "Zemlja", "Povlastica",
                "Bruto kg", "Neto kg"
            ]
            header_cols = len(headers)

            # Grupiši po naimenovanjima
            from collections import defaultdict
            grouped = defaultdict(list)
            for item in items:
                ordinal = item.assigned_naimenovanje_ordinal
                if ordinal > 0:
                    grouped[ordinal].append(item)

            row = 1  # Trenutni red

            for ordinal in sorted(grouped.keys()):
                lines = grouped[ordinal]

                # Pronađi naimenovanje u draft-u
                tariff = "N/A"
                if draft and hasattr(draft, 'items'):
                    for n_item in draft.items:
                        if n_item.ordinal_no == ordinal:
                            tariff = n_item.tariff_code or "N/A"
                            break
                    else:
                        tariff = lines[0].tarifni_broj if lines else "N/A"

                # Red sa nazivom naimenovanja
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=header_cols)
                group_cell = ws.cell(row=row, column=1, value=f"NAIMENOVANJE {ordinal} | Tarifa: {tariff} | Broj stavki: {len(lines)}")
                group_cell.font = group_font
                group_cell.fill = group_fill
                for c in range(1, header_cols + 1):
                    ws.cell(row=row, column=c).border = border
                    ws.cell(row=row, column=c).fill = group_fill
                row += 1

                # Header red
                for col_idx, header in enumerate(headers, start=1):
                    cell = ws.cell(row=row, column=col_idx, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                    cell.border = border
                row += 1

                # Data rows
                for idx, item in enumerate(lines, start=1):
                    ws.cell(row=row, column=1, value=idx).border = border
                    ws.cell(row=row, column=2, value=item.invoice_number or "").border = border
                    ws.cell(row=row, column=3, value=item.line_no if item.line_no > 0 else idx).border = border
                    ws.cell(row=row, column=4, value=ordinal).border = border
                    ws.cell(row=row, column=5, value=item.naziv_robe or "").border = border
                    ws.cell(row=row, column=6, value=item.kolicina or 0).border = border
                    ws.cell(row=row, column=7, value=item.jm or "").border = border
                    ws.cell(row=row, column=8, value=item.iznos or 0).border = border
                    ws.cell(row=row, column=9, value=item.valuta or "EUR").border = border
                    ws.cell(row=row, column=10, value=item.tarifni_broj or "").border = border
                    ws.cell(row=row, column=11, value=item.zemlja_porijekla or "").border = border
                    ws.cell(row=row, column=12, value=item.povlastica or "").border = border
                    ws.cell(row=row, column=13, value=item.bruto_kg or 0).border = border
                    ws.cell(row=row, column=14, value=item.neto_kg or 0).border = border
                    row += 1

                # Total red za ovo naimenovanje
                total_kol = sum(l.kolicina for l in lines)
                total_iznos = sum(l.iznos for l in lines)
                total_bruto = sum(l.bruto_kg for l in lines)
                total_neto = sum(l.neto_kg for l in lines)

                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
                total_label = ws.cell(row=row, column=1, value=f"UKUPNO NAIMENOVANJE {ordinal}:")
                total_label.font = total_font
                total_label.fill = total_fill
                for c in range(1, header_cols + 1):
                    ws.cell(row=row, column=c).fill = total_fill
                    ws.cell(row=row, column=c).border = border

                ws.cell(row=row, column=6, value=total_kol).font = total_font
                ws.cell(row=row, column=6).fill = total_fill
                ws.cell(row=row, column=6).border = border
                ws.cell(row=row, column=8, value=total_iznos).font = total_font
                ws.cell(row=row, column=8).fill = total_fill
                ws.cell(row=row, column=8).border = border
                ws.cell(row=row, column=13, value=total_bruto).font = total_font
                ws.cell(row=row, column=13).fill = total_fill
                ws.cell(row=row, column=13).border = border
                ws.cell(row=row, column=14, value=total_neto).font = total_font
                ws.cell(row=row, column=14).fill = total_fill
                ws.cell(row=row, column=14).border = border
                row += 1

                # Prazan red između naimenovanja
                row += 1

            # Fiksne širine kolona (isto kao PDF)
            fixed_widths = {
                1: 5,    # RB
                2: 22,   # Faktura
                3: 6,    # Stavka
                4: 6,    # Naim.
                5: 40,   # Naziv robe
                6: 10,   # Količina
                7: 5,    # JM
                8: 12,   # Vrijednost
                9: 7,    # Valuta
                10: 12,  # Tarifa
                11: 10,  # Zemlja
                12: 12,  # Povlastica
                13: 10,  # Bruto kg
                14: 10,  # Neto kg
            }
            for col_idx, width in fixed_widths.items():
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

            wb.save(filepath)
            wb.close()

            return True

        except Exception as e:
            logger.debug(f"Error exporting to Excel: {e}")
            import traceback
            traceback.print_exc()
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
