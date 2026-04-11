import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader

def load_template_config(doc_type):
    try:
        if doc_type == 'invoice':
            from app.pdf_templates import invoice_template as template
        elif doc_type == 'purchase':
            from app.pdf_templates import purchase_bill_template as template
        elif doc_type == 'purchase_order':
            from app.pdf_templates import purchase_order_template as template
        else:
            return None
        return template
    except ImportError:
        return None
    except Exception:
        return None

DEFAULT_CURRENCY = 'Rs'
DEFAULT_FORMAT = ',.2f'

PRIMARY_COLOR   = colors.HexColor("#c0392b")
SECONDARY_COLOR = colors.HexColor("#e74c3c")
ACCENT_COLOR    = colors.HexColor("#f9f9f9")
TEXT_COLOR      = colors.HexColor("#1a1a1a")
MUTED_TEXT      = colors.HexColor("#6b6b6b")
WHITE           = colors.white
BLACK           = colors.black
LIGHT_GREY      = colors.HexColor("#e0e0e0")
BORDER_GREY     = colors.HexColor("#d0d0d0")
HEADER_STRIPE   = colors.HexColor("#1a1a1a")
PAGE_BG         = colors.HexColor("#f2f2f2")

# Height reserved at the bottom of every page for the pinned footer
FOOTER_H = 72


class ProfessionalPDFGenerator:
    def __init__(self, buffer, company=None, invoice_settings=None, template_config=None):
        self.buffer = buffer
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=28,
            bottomMargin=FOOTER_H + 18,   # content never overlaps the footer
        )
        self.styles = getSampleStyleSheet()
        self.company = company
        self.settings = invoice_settings
        self.template = template_config
        self.setup_custom_styles()
        self._apply_template_settings()

    def _apply_template_settings(self):
        if self.template:
            self.currency_symbol = getattr(self.template, 'CURRENCY_SYMBOL', DEFAULT_CURRENCY)
            self.currency_format = getattr(self.template, 'CURRENCY_FORMAT', DEFAULT_FORMAT)
            self.title           = getattr(self.template, 'TITLE', 'DOCUMENT')
            self.footer_message  = getattr(self.template, 'FOOTER_MESSAGE', 'Thank you for your business!')
            self.labels          = getattr(self.template, 'LABELS', {})
        else:
            self.currency_symbol = DEFAULT_CURRENCY
            self.currency_format = DEFAULT_FORMAT
            self.title           = 'DOCUMENT'
            self.footer_message  = 'Thank you for your business!'
            self.labels          = {}

    def _get_label(self, key, default):
        return self.labels.get(key, default)

    def _format_currency(self, value):
        try:
            return f"{self.currency_symbol}{value:,.2f}"
        except Exception:
            return f"{self.currency_symbol}{value}"

    # ── Typography ─────────────────────────────────────────────────────────
    def setup_custom_styles(self):
        add = self.styles.add
        add(ParagraphStyle('InvoiceTitle',   parent=self.styles['Normal'], fontSize=26, textColor=BLACK,         fontName='Helvetica-Bold', alignment=TA_RIGHT, spaceAfter=1))
        add(ParagraphStyle('InvoiceSub',     parent=self.styles['Normal'], fontSize=8,  textColor=MUTED_TEXT,    alignment=TA_RIGHT, spaceAfter=1))
        add(ParagraphStyle('MetaLabel',      parent=self.styles['Normal'], fontSize=7.5,textColor=MUTED_TEXT,    alignment=TA_RIGHT))
        add(ParagraphStyle('MetaValue',      parent=self.styles['Normal'], fontSize=8,  textColor=TEXT_COLOR,    fontName='Helvetica-Bold', alignment=TA_RIGHT))
        add(ParagraphStyle('StatusBadge',    parent=self.styles['Normal'], fontSize=7.5,textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', alignment=TA_RIGHT))
        add(ParagraphStyle('CompanyName',    parent=self.styles['Normal'], fontSize=11, textColor=TEXT_COLOR,    fontName='Helvetica-Bold', spaceAfter=1))
        add(ParagraphStyle('CompanyInfo',    parent=self.styles['Normal'], fontSize=7,  textColor=MUTED_TEXT,    leading=10))
        add(ParagraphStyle('BoxTitle',       parent=self.styles['Normal'], fontSize=8,  textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', spaceAfter=3))
        add(ParagraphStyle('BoxValue',       parent=self.styles['Normal'], fontSize=7.5,textColor=TEXT_COLOR,    leading=10))
        add(ParagraphStyle('TblHeader',      parent=self.styles['Normal'], fontSize=7.5,textColor=WHITE,         fontName='Helvetica-Bold'))
        add(ParagraphStyle('TblCell',        parent=self.styles['Normal'], fontSize=7.5,textColor=TEXT_COLOR,    leading=10))
        add(ParagraphStyle('TblCellSub',     parent=self.styles['Normal'], fontSize=6.5,textColor=MUTED_TEXT,    leading=9))
        add(ParagraphStyle('TotalLabel',     parent=self.styles['Normal'], fontSize=8,  textColor=TEXT_COLOR,    alignment=TA_LEFT))
        add(ParagraphStyle('TotalValue',     parent=self.styles['Normal'], fontSize=8,  textColor=TEXT_COLOR,    alignment=TA_RIGHT))
        add(ParagraphStyle('GrandLabel',     parent=self.styles['Normal'], fontSize=9,  textColor=TEXT_COLOR,    fontName='Helvetica-Bold', alignment=TA_LEFT))
        add(ParagraphStyle('GrandValue',     parent=self.styles['Normal'], fontSize=9,  textColor=TEXT_COLOR,    fontName='Helvetica-Bold', alignment=TA_RIGHT))
        add(ParagraphStyle('NotesTitle',     parent=self.styles['Normal'], fontSize=8,  textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', spaceAfter=3))
        add(ParagraphStyle('NotesText',      parent=self.styles['Normal'], fontSize=7,  textColor=TEXT_COLOR,    leading=10))
        add(ParagraphStyle('SectionHeader',  parent=self.styles['Normal'], fontSize=8,  textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=3))

    # ── Logo ───────────────────────────────────────────────────────────────
    def _get_logo(self):
        if self.company and hasattr(self.company, 'logo_path') and self.company.logo_path and os.path.exists(self.company.logo_path):
            try:
                img = Image(self.company.logo_path)
                aspect = img.imageHeight / float(img.imageWidth)
                w = 1.0 * inch
                img.drawWidth  = w
                img.drawHeight = w * aspect
                return img
            except Exception:
                pass
        return None

    # ── HEADER ─────────────────────────────────────────────────────────────
    def _build_header(self, title, doc_number, date, due_date, currency=None, status=None):
        left = []
        logo = self._get_logo()
        if logo:
            left.append(logo)
            left.append(Spacer(1, 6))

        cname = self.company.name if self.company else "COMPANY"
        left.append(Paragraph(cname, self.styles['CompanyName']))

        if self.company:
            for attr, label in [('email','<b>Email:</b> {}'), ('phone','<b>Phone:</b> {}'), ('whatsapp','<b>WhatsApp:</b> {}'), ('address','{}'), ('address2','{}'), ('gst_number','GST: {}')]:
                val = getattr(self.company, attr, None)
                if val:
                    left.append(Paragraph(label.format(val), self.styles['CompanyInfo']))

        RIGHT_W      = 3.2 * inch
        META_LABEL_W = 1.1 * inch
        META_VAL_W   = RIGHT_W - META_LABEL_W

        meta_rows = [["Invoice No:", f"{doc_number}"],
                     ["Invoice Date:", date.strftime('%m/%d/%Y') if date else "N/A"],
                     ["Due Date:", due_date.strftime('%m/%d/%Y') if due_date else "N/A"]]
        if currency:
            meta_rows.append(["Currency:", currency])

        meta_tbl = Table(
            [[Paragraph(l, self.styles['MetaLabel']), Paragraph(v, self.styles['MetaValue'])] for l, v in meta_rows],
            colWidths=[META_LABEL_W, META_VAL_W]
        )
        meta_tbl.setStyle(TableStyle([
            ('ALIGN',         (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ]))

        right_rows = [
            [Paragraph(title.upper(), self.styles['InvoiceTitle'])],
            [Spacer(1, 22)],
            [meta_tbl],
        ]
        if status:
            right_rows += [[Spacer(1, 4)], [Paragraph(status.upper(), self.styles['StatusBadge'])]]

        right_tbl = Table(right_rows, colWidths=[RIGHT_W])
        right_tbl.setStyle(TableStyle([
            ('ALIGN',  (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ]))

        LEFT_W = (523 / 72) * inch - RIGHT_W - 0.1 * inch
        header_tbl = Table([[left, right_tbl]], colWidths=[LEFT_W, RIGHT_W])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN',  (0,0), (0,0),   'LEFT'),
            ('ALIGN',  (1,0), (1,0),   'RIGHT'),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ]))
        return header_tbl

    # ── INFO BOXES ─────────────────────────────────────────────────────────
    def _build_info_boxes(self, client_data, ship_to=None, reference_data=None):
        BOX_W = 2.0 * inch
        GAP   = 0.125 * inch   # visible space between boxes

        def make_box(title_text, rows):
            data = [[Paragraph(title_text, self.styles['BoxTitle'])]]
            for row in rows:
                data.append([Paragraph(row, self.styles['BoxValue'])])
            tbl = Table(data, colWidths=[BOX_W])
            tbl.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING',    (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 6),
                ('BOX',           (0,0), (-1,-1), 0.6, BORDER_GREY),
            ]))
            return tbl

        # Box 1 – Bill To
        b1_rows = []
        for key in ('name', 'company', 'address', 'email', 'phone', 'gst_number'):
            val = client_data.get(key, '')
            if val:
                b1_rows.append(f"GST: {val}" if key == 'gst_number' else val)
        box1 = make_box(self._get_label('bill_to', 'BILL TO'), b1_rows)

        # Box 2 – Ship To / Ship From
        b2_rows = []
        if ship_to:
            for key in ('name', 'address'):
                val = ship_to.get(key, '')
                if val:
                    b2_rows.append(val)
            if ship_to.get('contact_person'):
                b2_rows.append(f"Contact: {ship_to['contact_person']}")
        if not b2_rows:
            b2_rows = ['N/A']
        
        # Use custom label if provided (e.g., "SHIP FROM" for purchase docs)
        ship_label = getattr(self, '_ship_to_label', None) or self._get_label('ship_to', 'SHIP TO')
        box2 = make_box(ship_label, b2_rows)

        # Box 3 – Reference
        b3_rows = [f"{k}: {v}" for k, v in (reference_data or {}).items() if v]

        if b3_rows:
            box3  = make_box(self._get_label('reference', 'REFERENCE'), b3_rows)
            # 3 boxes: Bill To | Gap | Ship To | Gap | Reference
            outer = Table([[box1, '', box2, '', box3]],
                          colWidths=[2.1*inch, 0.15*inch, 2.1*inch, 0.15*inch, 1.8*inch])
        else:
            # 2 boxes: Bill To on left, Ship To on right with small gap
            outer = Table([[box1, '', box2]],
                          colWidths=[2.8*inch, 1.5*inch, 2.8*inch])

        outer.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        return outer

    # ── ITEMS TABLE ────────────────────────────────────────────────────────
    def _build_items_table(self, items, show_item_code=True):
        headers = ['#', 'Description']
        if show_item_code:
            headers += ['Item Code']
        headers += ['Qty', 'Unit', 'Unit Price', 'Amount']

        header_row = [Paragraph(f"<b>{h}</b>", self.styles['TblHeader']) for h in headers]

        col_w = ([0.28*inch, 2.55*inch, 0.72*inch, 0.42*inch, 0.55*inch, 0.85*inch, 0.88*inch]
                 if show_item_code else
                 [0.28*inch, 3.2*inch, 0.55*inch, 0.72*inch, 0.95*inch, 0.95*inch])

        table_data = [header_row]
        for idx, item in enumerate(items, 1):
            desc = item.get('description', 'N/A')
            sub  = item.get('sub_description', '')
            desc_cell = ([Paragraph(desc, self.styles['TblCell']),
                          Paragraph(sub,  self.styles['TblCellSub'])]
                         if sub else Paragraph(desc, self.styles['TblCell']))
            row = [Paragraph(str(idx), self.styles['TblCell']), desc_cell]
            if show_item_code:
                row.append(Paragraph(item.get('item_code', '-'), self.styles['TblCell']))
            row += [Paragraph(str(item.get('quantity', 0)), self.styles['TblCell']),
                    Paragraph(item.get('unit', '-'),        self.styles['TblCell']),
                    Paragraph(item.get('rate', '-'),        self.styles['TblCell']),
                    Paragraph(item.get('amount', '-'),      self.styles['TblCell'])]
            table_data.append(row)

        if len(table_data) == 1:
            empty = [Paragraph('1', self.styles['TblCell']),
                     Paragraph('No items listed', self.styles['TblCell'])]
            if show_item_code:
                empty.append(Paragraph('-', self.styles['TblCell']))
            empty += [Paragraph('-', self.styles['TblCell'])] * 4
            table_data.append(empty)

        tbl = Table(table_data, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),  (-1,0),  HEADER_STRIPE),
            ('TEXTCOLOR',     (0,0),  (-1,0),  WHITE),
            ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0),  (-1,0),  7.5),
            ('TOPPADDING',    (0,0),  (-1,0),  5),
            ('BOTTOMPADDING', (0,0),  (-1,0),  5),
            ('LEFTPADDING',   (0,0),  (-1,0),  6),
            ('FONTSIZE',      (0,1),  (-1,-1), 7.5),
            ('TOPPADDING',    (0,1),  (-1,-1), 4),
            ('BOTTOMPADDING', (0,1),  (-1,-1), 4),
            ('LEFTPADDING',   (0,1),  (-1,-1), 6),
            ('RIGHTPADDING',  (0,0),  (-1,-1), 6),
            ('TEXTCOLOR',     (0,1),  (-1,-1), TEXT_COLOR),
            ('ROWBACKGROUNDS',(0,1),  (-1,-1), [WHITE, ACCENT_COLOR]),
            ('VALIGN',        (0,0),  (-1,-1), 'TOP'),
            ('ALIGN',         (0,0),  (0,-1),  'CENTER'),
            ('ALIGN',         (1,0),  (1,-1),  'LEFT'),
            ('ALIGN',         (-3,0), (-1,-1), 'RIGHT'),
            ('LINEBELOW',     (0,0),  (-1,0),  1.0, PRIMARY_COLOR),
            ('GRID',          (0,0),  (-1,-1), 0.3, LIGHT_GREY),
            ('LINEBELOW',     (0,-1), (-1,-1), 0.5, BORDER_GREY),
        ]))
        return tbl

    # ── TOTALS + NOTES ─────────────────────────────────────────────────────
    def _build_bottom_section(self, totals, payment_info, terms, notes):
        notes_content = []
        if payment_info:
            notes_content.append(Paragraph("NOTES / PAYMENT TERMS", self.styles['NotesTitle']))
            for k, v in payment_info.items():
                if v:
                    notes_content.append(Paragraph(f"<b>{k}:</b> {v}", self.styles['NotesText']))
            notes_content.append(Spacer(1, 6))
        if terms:
            if not payment_info:
                notes_content.append(Paragraph("TERMS & CONDITIONS", self.styles['NotesTitle']))
            for line in terms.split('\n'):
                if line.strip():
                    notes_content.append(Paragraph(line.strip(), self.styles['NotesText']))
            notes_content.append(Spacer(1, 6))
        if notes:
            if not payment_info and not terms:
                notes_content.append(Paragraph("NOTES", self.styles['NotesTitle']))
            for line in notes.split('\n'):
                if line.strip():
                    notes_content.append(Paragraph(line.strip(), self.styles['NotesText']))

        notes_tbl = None
        if notes_content:
            notes_tbl = Table([[item] for item in notes_content], colWidths=[3.2 * inch])
            notes_tbl.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
                ('TOPPADDING',    (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 6),
                ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
                ('BACKGROUND',    (0,0), (-1,-1), WHITE),
            ]))

        tot_rows = []
        for i, (label, value) in enumerate(totals):
            is_last = (i == len(totals) - 1)
            is_bold = label.startswith("Total") or label.startswith("Balance") or is_last
            lp = Paragraph(f"<b>{label}</b>" if is_bold else label,
                           self.styles['GrandLabel'] if is_bold else self.styles['TotalLabel'])
            vp = Paragraph(f"<b>{value}</b>" if is_bold else value,
                           self.styles['GrandValue'] if is_bold else self.styles['TotalValue'])
            tot_rows.append([lp, vp])

        tot_tbl = Table(tot_rows, colWidths=[2.0 * inch, 1.1 * inch])
        tot_style = [
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (0,-1),  'LEFT'),
            ('ALIGN',         (1,0), (1,-1),  'RIGHT'),
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 5),
            ('LINEBELOW',     (0,-1),(-1,-1), 0.5, BORDER_GREY),
        ]
        for i, (label, _) in enumerate(totals):
            if label.startswith("Total") or label.startswith("Balance"):
                tot_style += [('LINEABOVE',  (0,i), (-1,i), 0.8, BORDER_GREY),
                               ('BACKGROUND', (0,i), (-1,i), ACCENT_COLOR)]
        tot_tbl.setStyle(TableStyle(tot_style))

        left_cell = notes_tbl if notes_tbl else ''
        combo = Table([[left_cell, '', tot_tbl]], colWidths=[3.2*inch, 0.15*inch, 3.15*inch])
        combo.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        return combo

    # ── FOOTER — drawn directly on canvas, always at page bottom ──────────
    def _draw_footer(self, c, doc):
        w, h = A4
        card_margin = 18
        lx = card_margin + 16   # left edge of footer text
        rx = w - card_margin - 16  # right edge of footer text

        # Y positions (from bottom of page)
        divider_y = card_margin + FOOTER_H - 2
        y = divider_y - 11

        c.saveState()

        # Divider line
        c.setStrokeColor(BORDER_GREY)
        c.setLineWidth(0.4)
        c.line(lx, divider_y, rx, divider_y)

        # ── Left: PREPARED BY ──────────────────────────────────────────────
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(TEXT_COLOR)
        c.drawString(lx, y, "PREPARED BY")

        c.setFont('Helvetica', 6.5)
        c.setFillColor(MUTED_TEXT)
        y -= 10
        c.drawString(lx, y, getattr(self.company, 'name', '') if self.company else "")

        # Signature line or image
        sig_path = None
        if self.company:
            try:
                sig_path = self.company.signature_path
            except Exception:
                sig_path = None
        if sig_path and os.path.exists(sig_path):
            try:
                from reportlab.platypus import Image as RLImage
                sig_img = RLImage(sig_path)
                sig_img.drawWidth = 80
                sig_img.drawHeight = 25
                y -= 30
                sig_img.drawOn(c, lx, y)
            except Exception:
                y -= 14
                c.setStrokeColor(colors.HexColor("#555555"))
                c.setLineWidth(0.5)
                c.line(lx, y, lx + 110, y)
                y -= 8
                c.setFont('Helvetica', 6.5)
                c.setFillColor(MUTED_TEXT)
                c.drawString(lx, y, "Authorized Signature")
        else:
            y -= 14
            c.setStrokeColor(colors.HexColor("#555555"))
            c.setLineWidth(0.5)
            c.line(lx, y, lx + 110, y)
            y -= 8
            c.setFont('Helvetica', 6.5)
            c.setFillColor(MUTED_TEXT)
            c.drawString(lx, y, "Authorized Signature")

        # ── Right: CUSTOMER SUPPORT ────────────────────────────────────────
        cemail = getattr(self.company, 'email',    '') if self.company else ""
        cphone = getattr(self.company, 'phone',    '') if self.company else ""
        cwa    = getattr(self.company, 'whatsapp', '') if self.company else ""

        ry = divider_y - 11
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(TEXT_COLOR)
        c.drawRightString(rx, ry, "CUSTOMER SUPPORT")

        c.setFont('Helvetica', 6.5)
        c.setFillColor(MUTED_TEXT)
        for line in filter(None, [cemail, cphone, f"WhatsApp: {cwa}" if cwa else ""]):
            ry -= 9
            c.drawRightString(rx, ry, line)

        # Page number
        c.setFont('Helvetica', 7)
        c.setFillColor(MUTED_TEXT)
        c.drawCentredString(w / 2, card_margin + 6, f"Page {doc.page}")

        c.restoreState()

    # ── MAIN BUILDER ───────────────────────────────────────────────────────
    def generate_document(self, title, doc_number, date, due_date, client_data, items,
                          totals, payment_info=None, terms=None, notes=None,
                          status=None, ship_to=None, reference_data=None, currency=None,
                          ship_to_label=None):
        elements = []
        
        # Set custom ship_to label if provided (e.g., "SHIP FROM" for purchase docs)
        if ship_to_label:
            self._ship_to_label = ship_to_label
        else:
            self._ship_to_label = None

        elements.append(self._build_header(title, doc_number, date, due_date, currency, status))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=0.6, color=BORDER_GREY, spaceAfter=8))
        elements.append(self._build_info_boxes(client_data, ship_to, reference_data))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("INVOICE ITEMS", self.styles['SectionHeader']))

        show_item_code = any('item_code' in item for item in items)
        elements.append(self._build_items_table(items, show_item_code))
        elements.append(Spacer(1, 10))
        elements.append(self._build_bottom_section(totals, payment_info, terms, notes))

        self.doc.build(
            elements,
            onFirstPage=self._draw_page_decorations,
            onLaterPages=self._draw_page_decorations,
        )

    # ── PAGE DECORATIONS ───────────────────────────────────────────────────
    def _draw_page_decorations(self, c, doc):
        w, h = A4
        c.saveState()

        # Grey background
        c.setFillColor(PAGE_BG)
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # White card
        m = 18
        c.setFillColor(WHITE)
        c.roundRect(m, m, w - 2*m, h - 2*m, 6, fill=1, stroke=0)

        # Top bar
        bh = 8
        c.setFillColor(HEADER_STRIPE)
        c.rect(m, h - m - bh, (w - 2*m) * 0.75, bh, fill=1, stroke=0)
        c.setFillColor(PRIMARY_COLOR)
        c.rect(m + (w - 2*m) * 0.75, h - m - bh, (w - 2*m) * 0.25, bh, fill=1, stroke=0)

        c.restoreState()

        # Footer is drawn after restoreState so it always paints on top
        self._draw_footer(c, doc)


# ── Convenience function ───────────────────────────────────────────────────
def generate_professional_pdf(doc_type, obj, company, settings=None):
    buffer = io.BytesIO()
    template_config = load_template_config(doc_type)
    generator = ProfessionalPDFGenerator(buffer, company, settings, template_config)
    currency = generator.currency_symbol if template_config else DEFAULT_CURRENCY

    # ── INVOICE ──────────────────────────────────────────────────────────
    if doc_type == 'invoice':
        title      = getattr(template_config, 'TITLE', 'Invoice') if template_config else "Invoice"
        doc_number = obj.invoice_number
        client_data = {
            'name':       obj.customer.name        if obj.customer else "Walk-in Customer",
            'address':    obj.customer.address      if obj.customer else "",
            'email':      obj.customer.email        if obj.customer else "",
            'phone':      obj.customer.phone        if obj.customer else "",
            'gst_number': obj.customer.gst_number   if obj.customer else "",
        }
        if obj.customer and getattr(obj.customer, 'company', None):
            client_data['company'] = obj.customer.company

        ship_to = None
        if hasattr(obj, 'job_site') and obj.job_site:
            ship_to = {
                'name':           obj.job_site.name,
                'address':        obj.job_site.address,
                'contact_person': obj.job_site.contact_person,
            }
        elif obj.customer:
            for attr, label in [
                ('installation_address', 'Installation Address'),
                ('shipping_address',     'Shipping Address'),
                ('delivery_address',     'Delivery Address'),
                ('work_address',         'Work Address'),
            ]:
                val = getattr(obj.customer, attr, None)
                if val:
                    ship_to = {'name': label, 'address': val,
                               'contact_person': getattr(obj.customer, 'contact_person', '') or ''}
                    break
            if not ship_to and obj.customer.address:
                ship_to = {'name': 'Billing Address', 'address': obj.customer.address, 'contact_person': ''}

        reference_data = {}
        if hasattr(obj, 'po_number')   and obj.po_number:   reference_data['PO No']       = obj.po_number
        if hasattr(obj, 'sales_order') and obj.sales_order: reference_data['Sales Order'] = obj.sales_order
        if hasattr(obj, 'project')     and obj.project:     reference_data['Project']     = obj.project.name if obj.project else ""
        if obj.customer and hasattr(obj.customer, 'customer_id'):
            reference_data['Customer ID'] = str(obj.customer.customer_id)

        items = []
        for item in obj.items:
            entry = {
                'description': item.product.name if item.product else "Unknown Product",
                'quantity':    int(item.quantity) if item.quantity.is_integer() else item.quantity,
                'rate':        f"{currency}{item.unit_price:,.2f}",
                'amount':      f"{currency}{item.total:,.2f}",
            }
            if hasattr(item, 'item_code')        and item.item_code:        entry['item_code']        = item.item_code
            if hasattr(item, 'unit')             and item.unit:             entry['unit']             = item.unit
            if hasattr(item, 'sub_description')  and item.sub_description:  entry['sub_description']  = item.sub_description
            items.append(entry)

        sc = obj.shipping_charge if (hasattr(obj, 'shipping_charge') and obj.shipping_charge) else 0
        totals = [
            ("Subtotal",           f"{currency}{obj.subtotal:,.2f}"),
            ("Discount",           f"{currency}{obj.discount:,.2f}"),
            ("Shipping / Freight", f"{currency}{sc:,.2f}"),
            ("Tax",                f"{currency}{obj.tax:,.2f}"),
            ("Total Due",          f"{currency}{obj.total:,.2f}"),
            ("Amount Paid",        f"{currency}{obj.paid_amount:,.2f}"),
            ("Balance",            f"{currency}{obj.balance_due:,.2f}"),
        ]

        payment_info = None
        if settings:
            payment_info = {k: v for k, v in {
                'Payment Terms':  getattr(settings, 'payment_terms', None),
                'Bank Name':      getattr(settings, 'bank_name', None),
                'Account Holder': getattr(settings, 'account_holder_name', None),
                'Account Number': getattr(settings, 'account_number', None),
                'IFSC Code':      getattr(settings, 'ifsc_code', None),
                'SWIFT Code':     getattr(settings, 'swift_code', None),
            }.items() if v}
        elif company:
            payment_info = {k: v for k, v in {
                'Bank Name':      getattr(company, 'bank_name', None),
                'Account Number': getattr(company, 'account_number', None),
                'IFSC Code':      getattr(company, 'ifsc_code', None),
            }.items() if v}

        cur_label = getattr(obj, 'currency', None) or (currency if currency != 'Rs' else 'USD')

        generator.generate_document(
            title=title, doc_number=doc_number,
            date=obj.date, due_date=obj.due_date,
            client_data=client_data, items=items, totals=totals,
            payment_info=payment_info,
            terms=obj.terms or (settings.default_terms if settings else None),
            notes=obj.notes or (settings.default_notes if settings else None),
            status=getattr(obj, 'status', None),
            ship_to=ship_to, reference_data=reference_data, currency=cur_label,
            ship_to_label=None,
        )

    # ── PURCHASE BILL ─────────────────────────────────────────────────────
    elif doc_type == 'purchase':
        title      = getattr(template_config, 'TITLE', 'Purchase Bill') if template_config else "Purchase Bill"
        doc_number = obj.bill_number
        client_data = {
            'name':       obj.vendor.name       if obj.vendor else "Unknown Vendor",
            'address':    obj.vendor.address    if obj.vendor else "",
            'email':      obj.vendor.email      if obj.vendor else "",
            'phone':      obj.vendor.phone      if obj.vendor else "",
            'gst_number': obj.vendor.gst_number if obj.vendor else "",
        }
        
        # Ship From - Vendor's shipping address
        ship_to = None
        if hasattr(obj, 'delivery_location') and obj.delivery_location:
            ship_to = {'name': obj.delivery_location.name, 'address': obj.delivery_location.address,
                       'contact_person': obj.delivery_location.contact_person}
        elif obj.vendor:
            if hasattr(obj.vendor, 'shipping_address') and obj.vendor.shipping_address:
                ship_to = {'name': 'Vendor Shipping Address', 'address': obj.vendor.shipping_address, 'contact_person': ''}
            elif obj.vendor.address:
                ship_to = {'name': 'Vendor Address', 'address': obj.vendor.address, 'contact_person': ''}
        
        reference_data = {}
        if obj.po_id and obj.source_po:
            reference_data['Purchase Order'] = obj.source_po.po_number
        if hasattr(obj, 'project') and obj.project:
            reference_data['Project'] = obj.project.name if obj.project else ""

        items = [{'description': item.product.name if item.product else "Unknown Product",
                  'quantity':    int(item.quantity) if item.quantity.is_integer() else item.quantity,
                  'unit':        getattr(item, 'unit', '-'),
                  'rate':        f"{currency}{item.unit_price:,.2f}",
                  'amount':      f"{currency}{item.total:,.2f}"} for item in obj.items]

        totals = [("Subtotal", f"{currency}{obj.subtotal:,.2f}"),
                  ("Tax",      f"{currency}{obj.tax:,.2f}"),
                  ("Discount", f"-{currency}{obj.discount:,.2f}"),
                  ("Shipping", f"{currency}{obj.shipping_charge:,.2f}"),
                  ("Total Due",f"{currency}{obj.total:,.2f}")]
        if hasattr(obj, 'advance_applied') and obj.advance_applied and obj.advance_applied > 0:
            totals += [("Advance Applied", f"-{currency}{obj.advance_applied:,.2f}"),
                       ("Balance Due",     f"{currency}{obj.balance_due:,.2f}")]
        else:
            totals += [("Amount Paid", f"{currency}{obj.paid_amount:,.2f}"),
                       ("Balance Due", f"{currency}{obj.balance_due:,.2f}")]

        notes = obj.notes or ''
        if obj.due_date:
            if notes: notes += '\n'
            notes += f"Due Date: {obj.due_date.strftime('%d-%m-%Y')}"
            if obj.is_overdue:
                days = (datetime.utcnow().date() - obj.due_date.date()).days
                notes += f" (Overdue by {days} days)"
        if obj.po_id and obj.source_po:
            if notes: notes += '\n'
            notes += f"Purchase Order: {obj.source_po.po_number}"

        terms = (settings.default_terms.strip() if settings and getattr(settings, 'default_terms', None) else '')
        dn    = (settings.default_notes.strip() if settings and getattr(settings, 'default_notes', None) else '')
        notes = (notes + '\n\n' + dn) if (dn and notes) else (dn or notes)

        generator.generate_document(
            title=title, doc_number=doc_number,
            date=obj.date, due_date=obj.due_date,
            client_data=client_data, items=items, totals=totals,
            terms=terms, notes=notes,
            status=getattr(obj, 'status', None),
            ship_to=ship_to, reference_data=reference_data,
            ship_to_label='SHIP FROM',
        )

    # ── PURCHASE ORDER ────────────────────────────────────────────────────
    elif doc_type == 'purchase_order':
        title      = getattr(template_config, 'TITLE', 'Purchase Order') if template_config else "Purchase Order"
        doc_number = obj.po_number
        client_data = {
            'name':       obj.vendor.name       if obj.vendor else "Unknown Vendor",
            'address':    obj.vendor.address    if obj.vendor else "",
            'email':      obj.vendor.email      if obj.vendor else "",
            'phone':      obj.vendor.phone      if obj.vendor else "",
            'gst_number': obj.vendor.gst_number if obj.vendor else "",
        }
        
        # Ship From - Vendor's shipping address
        ship_to = None
        if hasattr(obj, 'delivery_location') and obj.delivery_location:
            ship_to = {'name': obj.delivery_location.name, 'address': obj.delivery_location.address,
                       'contact_person': obj.delivery_location.contact_person}
        elif obj.vendor:
            if hasattr(obj.vendor, 'shipping_address') and obj.vendor.shipping_address:
                ship_to = {'name': 'Vendor Shipping Address', 'address': obj.vendor.shipping_address, 'contact_person': ''}
            elif obj.vendor.address:
                ship_to = {'name': 'Vendor Address', 'address': obj.vendor.address, 'contact_person': ''}
        
        reference_data = {}
        if hasattr(obj, 'project') and obj.project:
            reference_data['Project'] = obj.project.name if obj.project else ""

        items = [{'description': item.product.name if item.product else "Unknown Product",
                  'quantity':    int(item.quantity) if item.quantity.is_integer() else item.quantity,
                  'unit':        getattr(item, 'unit', '-'),
                  'rate':        f"{currency}{item.unit_price:,.2f}",
                  'amount':      f"{currency}{item.total:,.2f}"} for item in obj.items]

        totals = [("Subtotal",  f"{currency}{obj.subtotal:,.2f}"),
                  ("Tax",       f"{currency}{obj.tax:,.2f}"),
                  ("Discount",  f"-{currency}{obj.discount:,.2f}"),
                  ("Shipping",  f"{currency}{obj.shipping_charge:,.2f}"),
                  ("Total Due", f"{currency}{obj.total:,.2f}")]
        if obj.advance_amount and obj.advance_amount > 0:
            totals += [("Advance Paid", f"-{currency}{obj.advance_amount:,.2f}"),
                       ("Balance Due",  f"{currency}{obj.total - obj.advance_amount:,.2f}")]

        notes = obj.notes or ''
        ds, de = getattr(obj, 'delivery_start', None), getattr(obj, 'delivery_end', None)
        if ds or de:
            if notes: notes += '\n'
            if ds and de: notes += f"Delivery Window: {ds.strftime('%d-%m-%Y %H:%M')} to {de.strftime('%d-%m-%Y %H:%M')}"
            elif ds:      notes += f"Delivery Window: From {ds.strftime('%d-%m-%Y %H:%M')}"
            elif de:      notes += f"Delivery Window: Until {de.strftime('%d-%m-%Y %H:%M')}"

        generator.generate_document(
            title=title, doc_number=doc_number,
            date=obj.date, due_date=obj.expected_date,
            client_data=client_data, items=items, totals=totals,
            notes=notes, status=getattr(obj, 'status', None),
            ship_to=ship_to, reference_data=reference_data,
            ship_to_label='SHIP FROM',
        )

    buffer.seek(0)
    return buffer