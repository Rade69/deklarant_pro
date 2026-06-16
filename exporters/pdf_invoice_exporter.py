"""
PDF Invoice Exporter - Export fakture sa naimenovanjima
Kreira PDF dokument sa tabelom faktura stavki grupisan po naimenovanjima.

Author: Radovan + Claude
Date: February 2026
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft


class PDFInvoiceExporter:
    """Export fakture u PDF format sa naimenovanjima."""

    def __init__(self):
        """Inicijalizuj PDF exporter."""
        self.font_regular = 'Helvetica'
        self.font_bold = 'Helvetica-Bold'
        self.font_italic = 'Helvetica-Oblique'
        self.font_bold_italic = 'Helvetica-BoldOblique'
        self._register_fonts()
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _register_fonts(self):
        """Registruj Liberation Sans fontove za UTF-8 podršku (srpska slova)."""
        font_files = {
            'regular': 'LiberationSans-Regular.ttf',
            'bold': 'LiberationSans-Bold.ttf',
            'italic': 'LiberationSans-Italic.ttf',
            'bold_italic': 'LiberationSans-BoldItalic.ttf',
        }
        candidate_dirs = [
            Path.home() / ".local/share/fonts",
            Path("/usr/share/fonts/truetype/liberation2"),
            Path("/usr/share/fonts/truetype/liberation"),
            Path("/usr/share/fonts/liberation-sans-fonts"),
            Path("/Library/Fonts"),
            Path("C:/Windows/Fonts"),
        ]
        try:
            for font_dir in candidate_dirs:
                regular = font_dir / font_files['regular']
                bold = font_dir / font_files['bold']
                italic = font_dir / font_files['italic']
                bold_italic = font_dir / font_files['bold_italic']
                if not all(path.exists() for path in [regular, bold, italic, bold_italic]):
                    continue

                pdfmetrics.registerFont(TTFont('LibSans', str(regular)))
                pdfmetrics.registerFont(TTFont('LibSans-Bold', str(bold)))
                pdfmetrics.registerFont(TTFont('LibSans-Italic', str(italic)))
                pdfmetrics.registerFont(TTFont('LibSans-BoldItalic', str(bold_italic)))
                self.font_regular = 'LibSans'
                self.font_bold = 'LibSans-Bold'
                self.font_italic = 'LibSans-Italic'
                self.font_bold_italic = 'LibSans-BoldItalic'
                print(f"✅ Liberation Sans fontovi registrovani: {font_dir}")
                return

            print("⚠️ Liberation Sans nije pronađen, koristim ReportLab default fontove")
        except Exception as e:
            print(f"⚠️ Greška pri registrovanju fontova: {e}")
            print("   Koristim ReportLab default fontove")

    def _setup_styles(self):
        """Postavi custom stilove za PDF."""
        # Heading style
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading1'],
            fontSize=14,
            fontName=self.font_bold,
            textColor=colors.HexColor('#2563EB'),
            spaceAfter=12,
            spaceBefore=6
        ))

        # Naimenovanje header style
        self.styles.add(ParagraphStyle(
            name='NaimenovanjeHeader',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName=self.font_bold,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=8,
            spaceBefore=12
        ))

        # Table cell style - za naziv robe sa word wrap
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName=self.font_regular,
            leading=10,  # Line height
            alignment=0,  # Left align
            wordWrap='LTR'
        ))

    def export(self, draft: DeclarationDraft, output_path: str) -> bool:
        """
        Export fakture u PDF format.

        Args:
            draft: DeclarationDraft sa invoice_lines i items (naimenovanjima)
            output_path: Putanja gdje će se sačuvati PDF

        Returns:
            True ako je export uspješan, False inače
        """
        try:
            # Kreiraj PDF dokument (landscape za širu tabelu)
            doc = SimpleDocTemplate(
                output_path,
                pagesize=landscape(A4),
                rightMargin=1*cm,
                leftMargin=1*cm,
                topMargin=1.5*cm,
                bottomMargin=1.5*cm
            )

            # Elementi za PDF
            elements = []

            # Title
            title = Paragraph(
                f"<b>Faktura stavke po naimenovanjima</b>",
                self.styles['CustomHeading']
            )
            elements.append(title)
            elements.append(Spacer(1, 0.3*cm))

            # Datum
            date_text = f"Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            elements.append(Paragraph(date_text, self.styles['Normal']))
            elements.append(Spacer(1, 0.5*cm))

            # Grupiši invoice_lines po naimenovanjima
            grouped_lines = self._group_by_naimenovanje(draft.invoice_lines)

            # Prođi kroz sva naimenovanja i kreiraj tabele
            for ordinal in sorted(grouped_lines.keys()):
                lines = grouped_lines[ordinal]
                if not lines:
                    continue

                # Pronađi naimenovanje u draft.items
                naimenovanje = self._find_naimenovanje(draft.items, ordinal)

                # Dodaj header za naimenovanje
                elements.append(self._create_naimenovanje_header(ordinal, naimenovanje, lines))
                elements.append(Spacer(1, 0.2*cm))

                # Dodaj tabelu sa stavkama
                elements.append(self._create_items_table(lines))
                elements.append(Spacer(1, 0.8*cm))

            # Sačuvaj PDF
            doc.build(elements)
            return True

        except Exception as e:
            print(f"❌ Greška pri export-u PDF-a: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _group_by_naimenovanje(self, invoice_lines: List[InvoiceLine]) -> Dict[int, List[InvoiceLine]]:
        """
        Grupiši faktura stavke po naimenovanjima (assigned_naimenovanje_ordinal).

        Args:
            invoice_lines: Lista faktura stavki

        Returns:
            Dict sa ordinal_no kao ključem i listom stavki kao vrijednošću
        """
        grouped = defaultdict(list)

        for line in invoice_lines:
            ordinal = line.assigned_naimenovanje_ordinal
            if ordinal > 0:  # Samo stavke koje su assigned naimenovanju
                grouped[ordinal].append(line)

        return grouped

    def _find_naimenovanje(self, items: List[NaimenovanjeDraft], ordinal: int) -> Optional[NaimenovanjeDraft]:
        """
        Pronađi naimenovanje po ordinal broju.

        Args:
            items: Lista naimenovanja
            ordinal: Redni broj naimenovanja

        Returns:
            NaimenovanjeDraft ili None ako nije pronađeno
        """
        for item in items:
            if item.ordinal_no == ordinal:
                return item
        return None

    def _create_naimenovanje_header(
        self,
        ordinal: int,
        naimenovanje: NaimenovanjeDraft,
        lines: List[InvoiceLine]
    ) -> Paragraph:
        """
        Kreiraj header za naimenovanje.

        Args:
            ordinal: Redni broj naimenovanja
            naimenovanje: NaimenovanjeDraft objekat
            lines: Lista stavki u naimenovanju

        Returns:
            Paragraph sa header tekstom
        """
        if naimenovanje:
            tariff = naimenovanje.tariff_code or "N/A"
            country = naimenovanje.origin_country_code or "N/A"
            preference = naimenovanje.preference_code or "N/A"
        else:
            # Ako naimenovanje nije pronađeno, uzmi podatke iz prve stavke
            tariff = lines[0].tarifni_broj if lines else "N/A"
            country = lines[0].zemlja_porijekla if lines else "N/A"
            preference = lines[0].povlastica if lines else "N/A"

        header_text = (
            f"<b>NAIMENOVANJE {ordinal}</b> | "
            f"Tarifni broj: {tariff} | "
            f"Zemlja porijekla: {country} | "
            f"Povlastica: {preference} | "
            f"Broj stavki: {len(lines)}"
        )

        return Paragraph(header_text, self.styles['NaimenovanjeHeader'])

    def _create_items_table(self, lines: List[InvoiceLine]) -> Table:
        """
        Kreiraj tabelu sa faktura stavkama.

        Args:
            lines: Lista faktura stavki

        Returns:
            Table objekat
        """
        # Header
        # docs/sections/export-pdf-excel.md — izbacena Sifra/Cijena, dodate Stavka/Naim.
        table_data = [[
            'RB',
            'Faktura',
            'Stavka',
            'Naim.',
            'Naziv robe',
            'Količina',
            'JM',
            'Vrijednost',
            'Valuta',
            'Tarifa',
            'Zemlja',
            'Povlastica',
            'Bruto kg',
            'Neto kg'
        ]]

        # Rows
        for idx, line in enumerate(lines, start=1):
            # Koristi Paragraph za naziv_robe da omogući word wrap
            naziv_paragraph = Paragraph(line.naziv_robe or '', self.styles['TableCell'])

            table_data.append([
                str(idx),
                line.invoice_number or '',  # Broj fakture
                str(line.line_no) if line.line_no > 0 else str(idx),  # Redni broj stavke iz fakture
                str(line.assigned_naimenovanje_ordinal) if line.assigned_naimenovanje_ordinal > 0 else '—',
                naziv_paragraph,  # Paragraph umjesto običnog stringa - omogućava word wrap
                f"{line.kolicina:.2f}",
                line.jm or '',
                f"{line.iznos:.2f}",
                line.valuta or 'EUR',
                line.tarifni_broj or '',
                line.zemlja_porijekla or '',
                line.povlastica or '',  # KOD povlastice (EUP, TRP, CEFTA...)
                f"{line.bruto_kg:.3f}",
                f"{line.neto_kg:.3f}"
            ])

        # Kreiraj tabelu
        table = Table(table_data, colWidths=[
            0.8*cm,  # RB
            3.8*cm,  # Faktura
            1.0*cm,  # Stavka (rb. stavke iz fakture)
            1.1*cm,  # Naimen.
            4.5*cm,  # Naziv robe
            1.5*cm,  # Količina
            1.0*cm,  # JM
            1.8*cm,  # Vrijednost
            1.2*cm,  # Valuta
            2.0*cm,  # Tarifa
            1.2*cm,  # Zemlja
            1.5*cm,  # Povlastica
            1.5*cm,  # Bruto kg
            1.5*cm   # Neto kg
        ])

        # Stilizuj tabelu
        table.setStyle(TableStyle([
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

            # Data rows styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # RB centered
            ('ALIGN', (3, 1), (7, -1), 'RIGHT'),   # Numbers right-aligned
            ('ALIGN', (11, 1), (12, -1), 'RIGHT'), # Weights right-aligned
            ('FONTNAME', (0, 1), (-1, -1), self.font_regular),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Vertikalno poravnanje na vrh

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')]),
        ]))

        return table


def export_invoice_to_pdf(draft: DeclarationDraft, output_path: str) -> bool:
    """
    Convenience funkcija za export fakture u PDF.

    Args:
        draft: DeclarationDraft sa invoice_lines i items
        output_path: Putanja gdje će se sačuvati PDF

    Returns:
        True ako je export uspješan, False inače
    """
    exporter = PDFInvoiceExporter()
    return exporter.export(draft, output_path)
