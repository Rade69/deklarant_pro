"""
PDF Faktura Pregled - Izvoz po fakturi sa mapiranjem na naimenovanja
Kreira PDF dokument koji cariniku omogućava brzu provjeru:
  - koje stavke iz koje fakture idu u koje naimenovanje
  - sa težinama, količinama i iznosima

docs/sections/export-pdf-excel.md — detaljna dokumentacija

Author: Radovan + Claude
Date: April 2026
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import OrderedDict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft


class PDFFakturaPregled:
    """
    Export faktura pregleda u PDF format.

    Struktura:
        Deklaracija: ref_br, datum
        ──────────────────────────────────
        Faktura: FAKT-001
          RB │ Naimen. │ Naziv robe │ Kol. │ JM │ Iznos │ Bruto │ Neto
          ──────────────────────────────────────────────────────────────
          UKUPNO:                         xxx        xxx     xxx     xxx
        ──────────────────────────────────
        Faktura: FAKT-002
          ...
        ──────────────────────────────────
        UKUPNO DEKLARACIJA:               xxx        xxx     xxx     xxx
    """

    def __init__(self):
        self.font_regular = 'Helvetica'
        self.font_bold = 'Helvetica-Bold'
        self.font_italic = 'Helvetica-Oblique'
        self.font_bold_italic = 'Helvetica-BoldOblique'
        self._register_fonts()
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _register_fonts(self):
        """Registruj Liberation Sans fontove za UTF-8 podršku."""
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

            windows_fonts = Path("C:/Windows/Fonts")
            arial_files = {
                'regular': windows_fonts / 'arial.ttf',
                'bold': windows_fonts / 'arialbd.ttf',
                'italic': windows_fonts / 'ariali.ttf',
                'bold_italic': windows_fonts / 'arialbi.ttf',
            }
            if all(path.exists() for path in arial_files.values()):
                pdfmetrics.registerFont(TTFont('DPArial', str(arial_files['regular'])))
                pdfmetrics.registerFont(TTFont('DPArial-Bold', str(arial_files['bold'])))
                pdfmetrics.registerFont(TTFont('DPArial-Italic', str(arial_files['italic'])))
                pdfmetrics.registerFont(TTFont('DPArial-BoldItalic', str(arial_files['bold_italic'])))
                self.font_regular = 'DPArial'
                self.font_bold = 'DPArial-Bold'
                self.font_italic = 'DPArial-Italic'
                self.font_bold_italic = 'DPArial-BoldItalic'
                return

            print("⚠️ Liberation Sans nije pronađen, koristim ReportLab default fontove")
        except Exception as e:
            print(f"⚠️ Greška pri registrovanju fontova: {e}")
            print("   Koristim ReportLab default fontove")

    def _setup_styles(self):
        """Postavi custom stilove za PDF."""
        self.styles.add(ParagraphStyle(
            name='PregledTitle',
            parent=self.styles['Heading1'],
            fontSize=14,
            fontName=self.font_bold,
            textColor=colors.HexColor('#2563EB'),
            spaceAfter=4,
            spaceBefore=6
        ))

        self.styles.add(ParagraphStyle(
            name='PregledSubTitle',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName=self.font_regular,
            textColor=colors.HexColor('#4B5563'),
            spaceAfter=8
        ))

        self.styles.add(ParagraphStyle(
            name='PregledFakturaHeader',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName=self.font_bold,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=4,
            spaceBefore=12
        ))

        self.styles.add(ParagraphStyle(
            name='PregledTableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName=self.font_regular,
            leading=10
        ))

    def _safe_str(self, val) -> str:
        """Bezbedno konvertovanje u string."""
        if val is None:
            return ""
        return str(val)

    def _format_float(self, val, decimals: int = 2) -> str:
        """Formatiraj broj sa zarezom kao separator hiljada."""
        try:
            f = float(val)
            if f == 0:
                return "0"
            return f"{f:,.{decimals}f}"
        except (ValueError, TypeError):
            return self._safe_str(val)

    def _group_by_invoice(self, invoice_lines: List[InvoiceLine]) -> OrderedDict:
        """
        Grupiši stavke po broju fakture, zadržavajući redoslijed pojavljivanja.

        Returns:
            OrderedDict: invoice_number → [(line_no, InvoiceLine), ...]
        """
        grouped = OrderedDict()
        for line in invoice_lines:
            inv = line.invoice_number or "(bez broja)"
            if inv not in grouped:
                grouped[inv] = []
            grouped[inv].append(line)
        return grouped

    def _find_naimenovanje_tariff(self, draft: DeclarationDraft, ordinal: int) -> str:
        """Pronađi tarifni broj za zadati ordinal naimenovanja."""
        for item in draft.items:
            if item.ordinal_no == ordinal:
                return item.tariff_code or "N/A"
        return "N/A"

    def export(self, draft: DeclarationDraft, output_path: str) -> bool:
        """
        Export faktura pregleda u PDF.

        Args:
            draft: DeclarationDraft sa invoice_lines i items (naimenovanjima)
            output_path: Putanja gdje će se sačuvati PDF

        Returns:
            True ako je export uspješan
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=landscape(A4),
                rightMargin=1*cm,
                leftMargin=1*cm,
                topMargin=1.5*cm,
                bottomMargin=1.5*cm
            )

            elements = []

            # ── ZAGLAVLJE ──
            ref_br = draft.ref_br or "(nepoznata)"
            sifra = draft.sifra_deklaracije or ""
            elements.append(Paragraph(
                f"<b>PREGLED FAKTURA — {sifra}</b>",
                self.styles['PregledTitle']
            ))
            elements.append(Paragraph(
                f"Deklaracija: {ref_br}  |  Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                self.styles['PregledSubTitle']
            ))
            elements.append(Spacer(1, 0.3*cm))

            # ── GRUPISANJE PO FAKTURI ──
            grouped = self._group_by_invoice(draft.invoice_lines)

            # Ukupni totali za deklaraciju
            uk_kolicina = 0.0
            uk_iznos = 0.0
            uk_bruto = 0.0
            uk_neto = 0.0

            for inv_number, lines in grouped.items():
                # Header fakture
                elements.append(Paragraph(
                    f"<b>Faktura: {inv_number}</b>",
                    self.styles['PregledFakturaHeader']
                ))

                # Tabela za ovu fakturu
                table, totali = self._create_invoice_table(lines, draft)
                elements.append(table)
                elements.append(Spacer(1, 0.15*cm))

                # Zbir za fakturu
                zbir_text = (
                    f"<b>UKUPNO FAKTURA {inv_number}:  "
                    f"Količina: {self._format_float(totali['kolicina'], 2)}  |  "
                    f"Iznos: {self._format_float(totali['iznos'], 2)} EUR  |  "
                    f"Bruto: {self._format_float(totali['bruto'], 3)} kg  |  "
                    f"Neto: {self._format_float(totali['neto'], 3)} kg</b>"
                )
                elements.append(Paragraph(zbir_text, ParagraphStyle(
                    'ZbirFakture',
                    parent=self.styles['Normal'],
                    fontSize=9,
                    fontName=self.font_bold,
                    textColor=colors.HexColor('#374151'),
                    spaceAfter=8,
                    leftIndent=6
                )))
                elements.append(Spacer(1, 0.3*cm))

                # Akumuliraj u ukupno
                uk_kolicina += totali['kolicina']
                uk_iznos += totali['iznos']
                uk_bruto += totali['bruto']
                uk_neto += totali['neto']

            # ── UKUPNO DEKLARACIJA ──
            if len(grouped) > 1:
                elements.append(Spacer(1, 0.3*cm))
                linija = "_" * 120
                elements.append(Paragraph(linija, self.styles['PregledSubTitle']))
                ukupno_text = (
                    f"<b>UKUPNO DEKLARACIJA:  "
                    f"Količina: {self._format_float(uk_kolicina, 2)}  |  "
                    f"Iznos: {self._format_float(uk_iznos, 2)} EUR  |  "
                    f"Bruto: {self._format_float(uk_bruto, 3)} kg  |  "
                    f"Neto: {self._format_float(uk_neto, 3)} kg</b>"
                )
                elements.append(Paragraph(ukupno_text, ParagraphStyle(
                    'Ukupno',
                    parent=self.styles['Normal'],
                    fontSize=11,
                    fontName=self.font_bold,
                    textColor=colors.HexColor('#1F2937'),
                    spaceBefore=6,
                    spaceAfter=12
                )))

            # ── NAPOMENA ──
            elements.append(Spacer(1, 0.5*cm))
            napomena = Paragraph(
                "<i>Napomena: Kolona 'Naimen.' pokazuje redni broj naimenovanja "
                "u koje je stavka raspoređena.</i>",
                ParagraphStyle(
                    'Napomena',
                    parent=self.styles['Normal'],
                    fontSize=8,
                    fontName=self.font_italic,
                    textColor=colors.grey
                )
            )
            elements.append(napomena)

            doc.build(elements)
            return True

        except Exception as e:
            print(f"❌ Greška pri export-u PDF-a: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _create_invoice_table(
        self, lines: List[InvoiceLine], draft: DeclarationDraft
    ) -> Tuple[Table, dict]:
        """
        Kreiraj tabelu za jednu fakturu.

        Returns:
            Tuple (Table, dict sa totalima)
        """
        # Header
        header = ['RB', 'Naimen.', 'Tarifa', 'Naziv robe', 'Količina', 'JM', 'Iznos (EUR)', 'Bruto kg', 'Neto kg']

        # Zaglavlje tabele
        table_data = [header]

        total_kolicina = 0.0
        total_iznos = 0.0
        total_bruto = 0.0
        total_neto = 0.0

        # Podaci
        for idx, line in enumerate(lines, start=1):
            ordinal = line.assigned_naimenovanje_ordinal
            tariff = self._find_naimenovanje_tariff(draft, ordinal) if ordinal > 0 else "—"

            naziv = Paragraph(line.naziv_robe or '', self.styles['PregledTableCell'])

            # Formatiraj brojeve
            kolicina_str = self._format_float(line.kolicina, 2)
            iznos_str = self._format_float(line.iznos, 2)
            bruto_str = self._format_float(line.bruto_kg, 3)
            neto_str = self._format_float(line.neto_kg, 3)

            table_data.append([
                str(idx),
                str(ordinal) if ordinal > 0 else "—",
                tariff,
                naziv,
                kolicina_str,
                line.jm or '',
                iznos_str,
                bruto_str,
                neto_str
            ])

            total_kolicina += line.kolicina
            total_iznos += line.iznos
            total_bruto += line.bruto_kg
            total_neto += line.neto_kg

        # Kreiraj tabelu (bez Šifre, Tarifa proširena)
        col_widths = [
            0.9*cm,   # RB
            1.1*cm,   # Naimen.
            3.0*cm,   # Tarifa (proširena)
            10.0*cm,  # Naziv robe (glavna kolona)
            1.5*cm,   # Količina
            1.0*cm,   # JM
            1.8*cm,   # Iznos
            1.5*cm,   # Bruto
            1.5*cm    # Neto
        ]

        table = Table(table_data, colWidths=col_widths)

        # Stil
        style_cmds = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

            # Data
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (1, -1), 'CENTER'),    # RB, Naimen.
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),     # Tarifa
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),      # Količina
            ('ALIGN', (6, 1), (8, -1), 'RIGHT'),      # Iznos, Bruto, Neto
            ('FONTNAME', (0, 1), (-1, -1), self.font_regular),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

            # Alternating rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')]),
        ]

        table.setStyle(TableStyle(style_cmds))

        totali = {
            'kolicina': total_kolicina,
            'iznos': total_iznos,
            'bruto': total_bruto,
            'neto': total_neto,
        }

        return table, totali


def export_faktura_pregled(draft: DeclarationDraft, output_path: str) -> bool:
    """
    Convenience funkcija za export faktura pregleda u PDF.

    Args:
        draft: DeclarationDraft sa invoice_lines i items
        output_path: Putanja gdje će se sačuvati PDF

    Returns:
        True ako je export uspješan
    """
    exporter = PDFFakturaPregled()
    return exporter.export(draft, output_path)
