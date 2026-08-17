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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

def load_template_config(doc_type):
    try:
        if doc_type == 'invoice':
            from app.pdf_templates import invoice_template as template
        elif doc_type == 'quotation':
            # A quotation reuses the invoice's exact design/config; only the
            # title and a couple of header labels differ (set at build time).
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

DEFAULT_CURRENCY = 'PKR'
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

# Shared width for the items table and terms & conditions box
TABLE_WIDTH = 7.5 * inch


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
        
        # Register Font for Urdu/Unicode support
        self.urdu_font = 'Helvetica'
        
        # Possible paths for Urdu-supporting fonts
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        possible_paths = [
            os.path.join(base_dir, 'app', 'static', 'fonts', 'arial.ttf'),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/arial.ttf",
            "C:\\Windows\\Fonts\\arial.ttf"
        ]
        
        print(f"DEBUG: Starting font search. Base directory: {base_dir}")
        for font_path in possible_paths:
            try:
                if os.path.exists(font_path):
                    font_name = 'UrduFont'  # Hardcoded simple name for reliability
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    self.urdu_font = font_name
                    print(f"DEBUG: Successfully loaded font: {font_path}")
                    break
                else:
                    print(f"DEBUG: Font path not found: {font_path}")
            except Exception as e:
                print(f"DEBUG: Error loading font {font_path}: {str(e)}")
                continue
        
        if self.urdu_font == 'Helvetica':
            print("DEBUG: WARNING: Failed to load any Urdu-supporting font. Falling back to Helvetica.")

        self.setup_custom_styles()
        self._apply_template_settings()

    def _apply_template_settings(self):
        if self.template:
            self.currency_symbol = getattr(self.template, 'CURRENCY_SYMBOL', DEFAULT_CURRENCY)
            self.currency_format = getattr(self.template, 'CURRENCY_FORMAT', DEFAULT_FORMAT)
            self.title           = getattr(self.template, 'TITLE', 'DOCUMENT')
            self.footer_message  = getattr(self.template, 'FOOTER_MESSAGE', 'Thank you for your business!')
            self.labels          = getattr(self.template, 'LABELS', {})
            self.show_payment_details = getattr(self.template, 'SHOW_PAYMENT_DETAILS', True)
            self.show_terms = getattr(self.template, 'SHOW_TERMS', True)
            self.show_notes = getattr(self.template, 'SHOW_NOTES', True)
            self.show_bank_details = getattr(self.template, 'SHOW_BANK_DETAILS', True)
            self.footer_show_page_number = getattr(self.template, 'FOOTER_SHOW_PAGE_NUMBER', True)
            self.footer_show_company_info = getattr(self.template, 'FOOTER_SHOW_COMPANY_INFO', True)
        else:
            self.currency_symbol = DEFAULT_CURRENCY
            self.currency_format = DEFAULT_FORMAT
            self.title           = 'DOCUMENT'
            self.footer_message  = 'Thank you for your business!'
            self.labels          = {}
            self.show_payment_details = True
            self.show_terms = True
            self.show_notes = True
            self.show_bank_details = True
            self.footer_show_page_number = True
            self.footer_show_company_info = True

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
        u_f = self.urdu_font
        u_f_b = self.urdu_font # Since we might not have a separate bold font, we use the same one
        
        add(ParagraphStyle('InvoiceTitle',   parent=self.styles['Normal'], fontSize=26, textColor=BLACK,         fontName=u_f_b, alignment=TA_RIGHT, spaceAfter=1))
        add(ParagraphStyle('InvoiceSub',     parent=self.styles['Normal'], fontSize=8,  textColor=MUTED_TEXT,    alignment=TA_RIGHT, spaceAfter=1))
        add(ParagraphStyle('MetaLabel',      parent=self.styles['Normal'], fontSize=7.5,textColor=MUTED_TEXT,    alignment=TA_RIGHT))
        add(ParagraphStyle('MetaValue',      parent=self.styles['Normal'], fontSize=8,  textColor=TEXT_COLOR,    fontName=u_f_b, alignment=TA_RIGHT))
        add(ParagraphStyle('StatusBadge',    parent=self.styles['Normal'], fontSize=7.5,textColor=PRIMARY_COLOR, fontName=u_f_b, alignment=TA_RIGHT))
        add(ParagraphStyle('CompanyName',    parent=self.styles['Normal'], fontSize=11, textColor=TEXT_COLOR,    fontName=u_f_b, spaceAfter=1))
        add(ParagraphStyle('CompanyInfo',    parent=self.styles['Normal'], fontSize=7,  textColor=MUTED_TEXT,    leading=10))
        add(ParagraphStyle('BoxTitle',       parent=self.styles['Normal'], fontSize=8,  textColor=PRIMARY_COLOR, fontName=u_f_b, spaceAfter=3, leftIndent=0))
        add(ParagraphStyle('BoxValue',       parent=self.styles['Normal'], fontSize=7.5,textColor=TEXT_COLOR,    leading=10, alignment=TA_LEFT, leftIndent=0, fontName=u_f))
        add(ParagraphStyle('TblHeader',      parent=self.styles['Normal'], fontSize=7.5,textColor=WHITE,         fontName=u_f_b))
        add(ParagraphStyle('TblCell',        parent=self.styles['Normal'], fontSize=7.5,textColor=TEXT_COLOR,    leading=10, fontName=u_f))
        add(ParagraphStyle('TblCellSub',     parent=self.styles['Normal'], fontSize=6.5,textColor=MUTED_TEXT,    leading=9, fontName=u_f))
        add(ParagraphStyle('TotalLabel',     parent=self.styles['Normal'], fontSize=8,  textColor=TEXT_COLOR,    alignment=TA_LEFT, fontName=u_f))
        add(ParagraphStyle('TotalValue',     parent=self.styles['Normal'], fontSize=8,  textColor=TEXT_COLOR,    alignment=TA_RIGHT, fontName=u_f))
        add(ParagraphStyle('GrandLabel',     parent=self.styles['Normal'], fontSize=9,  textColor=TEXT_COLOR,    fontName=u_f_b, alignment=TA_LEFT))
        add(ParagraphStyle('GrandValue',     parent=self.styles['Normal'], fontSize=9,  textColor=TEXT_COLOR,    fontName=u_f_b, alignment=TA_RIGHT))
        add(ParagraphStyle('NotesTitle',     parent=self.styles['Normal'], fontSize=8,  textColor=PRIMARY_COLOR, fontName=u_f_b, spaceAfter=3))
        add(ParagraphStyle('NotesText',      parent=self.styles['Normal'], fontSize=7,  textColor=TEXT_COLOR,    leading=9, fontName=u_f))
        add(ParagraphStyle('SectionHeader',  parent=self.styles['Normal'], fontSize=8,  textColor=PRIMARY_COLOR, fontName=u_f_b, spaceBefore=6, spaceAfter=3))

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
    def _build_header(self, title, doc_number, date, due_date, currency=None, status=None, meta_labels=None,
                       show_company_address=True):
        left = []
        logo = self._get_logo()
        if logo:
            left.append(logo)
            left.append(Spacer(1, 6))

        cname = self.company.name if self.company else "COMPANY"
        left.append(Paragraph(cname, self.styles['CompanyName']))

        if self.company:
            info_fields = [('email','<b>Email:</b> {}'), ('phone','<b>Phone:</b> {}'), ('whatsapp','<b>WhatsApp:</b> {}')]
            if show_company_address:
                info_fields += [('address','{}'), ('address2','{}')]
            for attr, label in info_fields:
                val = getattr(self.company, attr, None)
                if val:
                    left.append(Paragraph(label.format(val), self.styles['CompanyInfo']))
            left.append(Paragraph('<b>Website:</b> <a href="https://pumpter.com/"><font color="red">https://pumpter.com/</font></a>', self.styles['CompanyInfo']))

        RIGHT_W      = 3.2 * inch
        META_LABEL_W = 1.1 * inch
        META_VAL_W   = RIGHT_W - META_LABEL_W

        # Default to invoice labels; a quotation passes its own (Quotation No / Date / Valid Until).
        _lbl = meta_labels or {'number': 'Invoice No:', 'date': 'Invoice Date:', 'due': 'Due Date:'}
        meta_rows = [[_lbl['number'], f"{doc_number}"],
                     [_lbl['date'], date.strftime('%m/%d/%Y') if date else "N/A"],
                     [_lbl['due'], due_date.strftime('%m/%d/%Y') if due_date else "N/A"]]
        if currency:
            meta_rows.append(["Currency:", currency])

        meta_tbl = Table(
            [[Paragraph(l, self.styles['MetaLabel']), Paragraph(v, self.styles['MetaValue'])] for l, v in meta_rows],
            colWidths=[META_LABEL_W, META_VAL_W]
        )
        meta_tbl.setStyle(TableStyle([
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
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
            ('ALIGN',  (0,0), (-1,-1), 'LEFT'),
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
    def _build_info_boxes(self, client_data, ship_to=None, reference_data=None, is_invoice=False):
        GAP   = 0.15 * inch   # visible space between boxes

        def make_box(title_text, rows, width=3.0*inch, custom_style=None):
            # Ensure the title is always bold
            bold_title = f"<b>{title_text}</b>"
            data = [[Paragraph(bold_title, self.styles['BoxTitle'])]]
            for row in rows:
                data.append([Paragraph(row, self.styles['BoxValue'])])
            tbl = Table(data, colWidths=[width])
            style = [
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
                ('TOPPADDING',    (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 6),
                ('BACKGROUND',    (0,0), (-1,-1), WHITE),
            ]
            # Extra padding for title row and box bottom
            style.append(('TOPPADDING', (0,0), (-1,0), 3))
            style.append(('BOTTOMPADDING', (0,0), (-1,0), 3))
            style.append(('BOTTOMPADDING', (0,-1), (-1,-1), 4))
            if custom_style:
                style.extend(custom_style)
            else:
                style.append(('BOX', (0,0), (-1,-1), 0.5, BORDER_GREY))
            tbl.setStyle(TableStyle(style))
            return tbl

        # Define flexible widths based on layout
        if is_invoice and not reference_data and not ship_to:
            # Standard 2-box Invoice layout: Bill To | Our Locations
            box1_w = 4.6 * inch
            box4_w = 2.7 * inch
            gap_w  = TABLE_WIDTH - box1_w - box4_w
        else:
            box1_w = 3.0 * inch
            box4_w = 3.0 * inch
            gap_w  = GAP

        # Box 1 – Bill To
        b1_rows = []
        company = client_data.get('company')
        name = client_data.get('name')
        if company:
            b1_rows.append(f"<b>Company:</b> {company}")
        elif name:
            b1_rows.append(f"<b>Name:</b> {name}")

        if client_data.get('contact_person'):
            b1_rows.append(f"<b>Contact Person:</b> {client_data['contact_person']}")

        label_map = {'address': 'Address', 'email': 'Email', 'phone': 'Phone', 'gst_number': 'GST No'}
        for key in ('address', 'email', 'phone', 'gst_number'):
            val = client_data.get(key, '')
            if val:
                label = label_map.get(key, key)
                b1_rows.append(f"<b>{label}:</b> {val}")

        if client_data.get('customer_reference'):
            b1_rows.append(f"<b>Customer Reference:</b> {client_data['customer_reference']}")
        if client_data.get('salesperson'):
            b1_rows.append(f"<b>Salesperson:</b> {client_data['salesperson']}")

        box1 = make_box(self._bill_to_label or self._get_label('bill_to', 'BILL TO'), b1_rows, width=box1_w)

        # Box 2 – Ship To / Ship From
        box2 = None
        if ship_to:
            b2_rows = []
            for key in ('name', 'address'):
                val = ship_to.get(key, '')
                if val:
                    b2_rows.append(f"<b>{key.title()}:</b> {val}")
            if ship_to.get('contact_person'):
                b2_rows.append(f"<b>Contact:</b> {ship_to['contact_person']}")
            if not b2_rows: b2_rows = ['N/A']
            ship_label = getattr(self, '_ship_to_label', None) or self._get_label('ship_to', 'SHIP TO')
            box2 = make_box(ship_label, b2_rows, width=3.0*inch)

        # Box 3 – Reference
        b3_rows = [f"<b>{k}:</b> {v}" for k, v in (reference_data or {}).items() if v]

        # Box 4 – Locations
        box4 = None
        if is_invoice:
            # Head office = the company's own address on file (Company Settings);
            # Karachi is a second, fixed physical location.
            head_office_addr = (getattr(self.company, 'address', None) if self.company else None) or 'N/A'
            addr_rows = [
                f"<b>Head Office:</b> {head_office_addr}",
                "<b>Karachi:</b> LS-25, Super Auto Parts Market, Main Super Highway, Sohrab Goth, Karachi."
            ]
            box4 = make_box("OUR LOCATIONS", addr_rows, width=box4_w)

        if b3_rows:
            box3 = make_box(self._get_label('reference', 'REFERENCE'), b3_rows, width=2.0*inch)
            if box2:
                outer = Table([[box1, '', box2, '', box3]],
                              colWidths=[2.5*inch, 0.1*inch, 2.5*inch, 0.1*inch, 2.3*inch])
            elif box4:
                outer = Table([[box1, '', box4, '', box3]],
                              colWidths=[2.6*inch, 0.1*inch, 2.6*inch, 0.1*inch, 2.1*inch])
            else:
                outer = Table([[box1, '', box3]],
                              colWidths=[4.0*inch, 0.2*inch, 3.3*inch])
        else:
            if box2:
                # 2 boxes: Bill To | Ship To
                outer = Table([[box1, '', box2]],
                              colWidths=[3.6*inch, 0.3*inch, 3.6*inch])
            elif box4:
                # 2 boxes: Bill To | Our Locations
                outer = Table([[box1, '', box4]],
                              colWidths=[box1_w, gap_w, box4_w])
            else:
                # 1 box only: Bill To (center it)
                outer = Table([[box1]], colWidths=[TABLE_WIDTH])

        outer.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        return outer

    # ── ITEMS TABLE ────────────────────────────────────────────────────────
    def _build_items_table(self, items, show_item_code=True, show_sku=False, show_discount=False,
                            discount_header='Unit Discount', show_unit_col=False,
                            show_total_discount=False):
        headers = ['#', 'Description']
        if show_sku:
            headers += ['SKU']
        if show_item_code:
            headers += ['Item Code']
        # Only add Cancelled column if any item has a cancelled quantity
        show_cancelled = getattr(self, 'is_purchase', False) and getattr(self, '_has_cancelled_items', False)
        if show_cancelled:
            headers += ['Qty', 'Unit Price', 'Cancelled', 'Amount']
        else:
            headers += ['Qty', 'Unit Price', 'Amount']
        if show_unit_col:
            # A separate Unit column (pcs/kg/etc), right after Qty — distinct from
            # the purchase-bill behavior of folding the unit into the Qty text.
            qty_idx = headers.index('Qty')
            headers.insert(qty_idx + 1, 'Unit')
        if show_discount:
            # Discount amount, inserted right before the final Amount column.
            headers.insert(-1, discount_header)
            if show_total_discount:
                # Line-total discount, mirroring the invoice detail page which
                # shows "Unit Discount" and "Total Discount" side by side.
                headers.insert(-1, 'Total Discount')

        header_row = [Paragraph(f"<b>{h}</b>", self.styles['TblHeader']) for h in headers]

        if show_unit_col:
            # Dedicated layout for the quotation-style table (# | Description | [SKU] |
            # Qty | Unit | Unit Price | [Discount] | Amount) — computed directly rather
            # than via the generic insert-based branches below, so Amount/Unit Price
            # keep enough room and don't wrap onto a second line.
            col_w = [0.35*inch, (2.2 if show_sku else 2.9)*inch]
            if show_sku:
                col_w.append(0.7*inch)
            col_w += [0.5*inch, 0.5*inch, 0.95*inch]
            if show_discount:
                col_w.append(0.85*inch)
            col_w.append(0.95*inch)
        elif show_sku and show_item_code:
            col_w = [0.385*inch, 2.3*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.6*inch, 0.7*inch]
            if show_cancelled: col_w.insert(6, 0.8*inch)
        elif show_sku:
            col_w = [0.385*inch, 3.0*inch, 0.8*inch, 0.7*inch, 1.0*inch, 0.9*inch]
            if show_cancelled: col_w.insert(5, 0.8*inch)
        elif show_item_code:
            col_w = [0.385*inch, 3.0*inch, 0.8*inch, 0.7*inch, 1.0*inch, 0.9*inch]
            if show_cancelled: col_w.insert(5, 0.8*inch)
        else:
            col_w = [0.385*inch, 3.85*inch, 0.715*inch, 1.1*inch, 1.1*inch]
            if show_cancelled: col_w.insert(4, 0.8*inch)

        if show_discount and not show_unit_col:
            # Matches the header's insert(-1, ...) position: right before Amount's width.
            col_w.insert(-1, 0.8*inch)
            if show_total_discount:
                col_w.insert(-1, 0.8*inch)
                # Two money columns instead of one is tight — take the space from
                # Description (which wraps gracefully) and give Amount a little
                # extra so a figure like "PKR246,000.00" stays on one line.
                col_w[-1] += 0.3*inch
                col_w[1] = max(1.4*inch, col_w[1] - 1.1*inch)

        # Scale column widths so the items table matches the info boxes and notes (TABLE_WIDTH)
        # This ensures the table aligns with Statement/Locations boxes and the Notes section
        total_current = sum(col_w)
        col_w = [w * TABLE_WIDTH / total_current for w in col_w]

        table_data = [header_row]
        for idx, item in enumerate(items, 1):
            desc = item.get('description', 'N/A')
            sub  = item.get('sub_description', '')
            desc_cell = ([Paragraph(desc, self.styles['TblCell']),
                          Paragraph(sub,  self.styles['TblCellSub'])]
                         if sub else Paragraph(desc, self.styles['TblCell']))
            row = [Paragraph(str(idx), self.styles['TblCell']), desc_cell]
            if show_sku:
                row.append(Paragraph(item.get('sku', '-'), self.styles['TblCell']))
            if show_item_code:
                row.append(Paragraph(item.get('item_code', '-'), self.styles['TblCell']))
            qty = item.get('quantity', 0)
            unit = item.get('unit', '')
            qty_str = f"{qty:,.2f}" if isinstance(qty, (int, float)) else str(qty)

            if show_unit_col:
                row.append(Paragraph(qty_str, self.styles['TblCell']))
                row.append(Paragraph(unit or '-', self.styles['TblCell']))
                row.append(Paragraph(item.get('rate', '-'), self.styles['TblCell']))
                if show_discount:
                    row.append(Paragraph(item.get('unit_discount', '-'), self.styles['TblCell']))
                row.append(Paragraph(item.get('amount', '-'), self.styles['TblCell']))
                table_data.append(row)
                continue

            # Show unit in quantity column if it's a purchase bill
            if getattr(self, 'is_purchase', False):
                # For pieces/pcs, show as integer without decimal points
                if unit and unit.lower() in ['pcs', 'pieces', 'pc', 'piece']:
                    qty_str = f"{int(qty):,}" if isinstance(qty, (int, float)) else str(qty)
                
                if unit and unit != '-':
                    qty_str = f"{qty_str} {unit}"
            row += [Paragraph(qty_str, self.styles['TblCell']),
                    Paragraph(item.get('rate', '-'),        self.styles['TblCell'])]
            
            if show_cancelled:
                cq = item.get('cancelled_quantity', 0) or 0
                cq_str = f"{cq:,.2f}" if cq > 0 else "-"
                row.append(Paragraph(cq_str, self.styles['TblCell']))

            if show_discount:
                row.append(Paragraph(item.get('unit_discount', '-'), self.styles['TblCell']))
                if show_total_discount:
                    row.append(Paragraph(item.get('total_discount', '-'), self.styles['TblCell']))

            row.append(Paragraph(item.get('amount', '-'),      self.styles['TblCell']))
            table_data.append(row)

        if len(table_data) == 1:
            empty = [Paragraph('1', self.styles['TblCell']),
                     Paragraph('No items listed', self.styles['TblCell'])]
            if show_sku:
                empty.append(Paragraph('-', self.styles['TblCell']))
            if show_item_code:
                empty.append(Paragraph('-', self.styles['TblCell']))
            empty_trailing = (3 + (1 if show_unit_col else 0) + (1 if show_discount else 0)
                              + (1 if (show_discount and show_total_discount) else 0))
            empty += [Paragraph('-', self.styles['TblCell'])] * empty_trailing
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
            ('ALIGN',         (1,0),  (-1,-1), 'LEFT'),
            ('LINEBELOW',     (0,0),  (-1,0),  1.0, PRIMARY_COLOR),
            ('GRID',          (0,0),  (-1,-1), 0.3, LIGHT_GREY),
            ('LINEBELOW',     (0,-1), (-1,-1), 0.5, BORDER_GREY),
        ]))
        return tbl

    # ── TOTALS + NOTES ─────────────────────────────────────────────────────
    def _build_bottom_section(self, totals, payment_info, terms, notes, extra_thank=None, is_purchase=False):
        # ── Payment Info (Bank Details) Box ─────────────────────────────────────
        bank_tbl = None
        if payment_info and self.show_payment_details and self.show_bank_details:
            bank_rows = [Paragraph("BANK DETAILS", self.styles['NotesTitle'])]
            for k, v in payment_info.items():
                if v:
                    bank_rows.append(Paragraph(f"<b>{k}:</b> {v}", self.styles['NotesText']))
            bank_tbl = Table([[item] for item in bank_rows], colWidths=[3.7 * inch])
            bank_tbl.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
                ('TOPPADDING',    (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 6),
                ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
                ('BACKGROUND',    (0,0), (-1,-1), WHITE),
            ]))

        # ── Totals Table ───────────────────────────────────────────────────────
        tot_rows = []
        for i, (label, value) in enumerate(totals):
            is_last = (i == len(totals) - 1)
            is_bold = label.startswith("Total") or label.startswith("Balance") or is_last
            lp = Paragraph(f"<b>{label}</b>" if is_bold else label,
                           self.styles['GrandLabel'] if is_bold else self.styles['TotalLabel'])
            vp = Paragraph(f"<b>{value}</b>" if is_bold else value,
                           self.styles['GrandValue'] if is_bold else self.styles['TotalValue'])
            tot_rows.append([lp, vp])

        tot_tbl = Table(tot_rows, colWidths=[2.0 * inch, 1.7 * inch])
        tot_style = [
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (-1,-1),  'LEFT'),
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

        # ── Terms & Conditions Box ─────────────────────────────────────────────
        terms_tbl = None
        terms_content = []
        
        # Build terms content
        if terms and self.show_terms:
            terms_content.append(Paragraph("TERMS & CONDITIONS", self.styles['NotesTitle']))
            for line in terms.split('\n'):
                if line.strip():
                    terms_content.append(Paragraph(line.strip(), self.styles['NotesText']))
        if notes and self.show_notes:
            if not terms_content:
                terms_content.append(Paragraph("NOTES", self.styles['NotesTitle']))
            for line in notes.split('\n'):
                if line.strip():
                    terms_content.append(Paragraph(line.strip(), self.styles['NotesText']))
        
        if terms_content:
            terms_tbl = Table([[item] for item in terms_content], colWidths=[TABLE_WIDTH])
            terms_tbl.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
                ('TOPPADDING',    (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 6),
                ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
                ('BACKGROUND',    (0,0), (-1,-1), WHITE),
            ]))

        # ── Compose Final Layout ───────────────────────────────────────────────
        # Row 1: Bank box (50% width) + Totals table (50% width) side by side
        if bank_tbl:
            row1 = Table([[bank_tbl, '', tot_tbl]], colWidths=[3.7*inch, TABLE_WIDTH - 7.4*inch, 3.7*inch])
        else:
            # Right-align totals box within the full TABLE_WIDTH
            row1 = Table([['', tot_tbl]], colWidths=[TABLE_WIDTH - 3.7*inch, 3.7*inch])
        row1.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('ALIGN',         (1,0), (1,-1),  'LEFT'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))

        elements = [row1, Spacer(1, 8)]

        if terms_tbl:
            elements.append(terms_tbl)

        # Place thank-you message outside (below) the terms box
        if extra_thank:
            elements.append(Spacer(1, 15))
            elements.append(extra_thank)

        return elements

    # ── QUOTATION-ONLY SECTIONS ─────────────────────────────────────────────
    def _build_commercial_terms(self, rows):
        """4-column grid: Label | Value | Label | Value, one pair per row.
        `rows` is a list of (label1, value1, label2, value2) tuples."""
        data = [[Paragraph("COMMERCIAL TERMS", self.styles['NotesTitle']), '', '', '']]
        for l1, v1, l2, v2 in rows:
            data.append([
                Paragraph(f"<b>{l1}</b>", self.styles['BoxValue']),
                Paragraph(v1, self.styles['BoxValue']),
                Paragraph(f"<b>{l2}</b>", self.styles['BoxValue']),
                Paragraph(v2, self.styles['BoxValue']),
            ])
        col_w = [1.1*inch, 2.65*inch, 1.1*inch, 2.65*inch]
        tbl = Table(data, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ('SPAN',          (0,0), (-1,0)),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 6),
            ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('INNERGRID',     (0,1), (-1,-1), 0.3, LIGHT_GREY),
            ('BACKGROUND',    (0,0), (-1,-1), WHITE),
        ]))
        return tbl

    def _build_important_notice(self, text_en, text_ur=None):
        """Bilingual (English + optional Urdu) warning box, shaded like a caution note."""
        content = [Paragraph(f"<b>IMPORTANT:</b> {text_en}", self.styles['NotesText'])]
        if text_ur:
            try:
                reshaped = arabic_reshaper.reshape(text_ur)
                bidi_text = get_display(reshaped)
            except Exception:
                bidi_text = text_ur
            urdu_style = ParagraphStyle(
                'ImportantUrdu', parent=self.styles['NotesText'],
                fontName=self.urdu_font, alignment=TA_RIGHT, textColor=PRIMARY_COLOR, leading=13,
            )
            content.append(Spacer(1, 4))
            content.append(Paragraph(bidi_text, urdu_style))

        tbl = Table([[c] for c in content], colWidths=[TABLE_WIDTH])
        tbl.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('BOX',           (0,0), (-1,-1), 0.5, colors.HexColor("#e0c080")),
            ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor("#fdf6e3")),
        ]))
        return tbl

    def _build_acceptance_table(self):
        """CUSTOMER ACCEPTANCE sign-off grid: 2 rows x (label | blank box) x2 —
        no underscore fill line, just the empty grid-bordered cell."""
        blank = Paragraph('', self.styles['BoxValue'])
        rows = [
            [Paragraph("<b>Authorized Person</b>", self.styles['BoxValue']), blank,
             Paragraph("<b>Approval Method</b>", self.styles['BoxValue']),
             Paragraph("SIGN / WHATSAPP / EMAIL / PO", self.styles['BoxValue'])],
            [Paragraph("<b>Signature / Stamp</b>", self.styles['BoxValue']), Paragraph('', self.styles['BoxValue']),
             Paragraph("<b>Acceptance Date</b>", self.styles['BoxValue']), Paragraph('', self.styles['BoxValue'])],
        ]
        col_w = [1.3*inch, 2.45*inch, 1.3*inch, 2.45*inch]
        data = [[Paragraph("CUSTOMER ACCEPTANCE", self.styles['NotesTitle']), '', '', '']] + rows
        # Fixed row heights (rather than an underscore line) give each value
        # cell visible blank space to sign/write in, bounded by the grid box.
        tbl = Table(data, colWidths=col_w, rowHeights=[None, 34, 34])
        tbl.setStyle(TableStyle([
            ('SPAN',          (0,0), (-1,0)),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 6),
            ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('INNERGRID',     (0,1), (-1,-1), 0.3, LIGHT_GREY),
            ('BACKGROUND',    (0,0), (-1,-1), WHITE),
        ]))
        return tbl

    # ── PACKING SLIP ───────────────────────────────────────────────────────
    def _build_field_grid_box(self, title, fields, width):
        """A titled box with one (label | value) row per field, gridded like a
        form — used for the packing slip's fill-in-by-hand sections. A value
        of '' renders as a blank cell (pen field); anything else is auto-filled."""
        data = [[Paragraph(f"<b>{title}</b>", self.styles['NotesTitle']), '']]
        for label, value in fields:
            data.append([Paragraph(f"<b>{label}</b>", self.styles['BoxValue']),
                         Paragraph(value or '', self.styles['BoxValue'])])
        tbl = Table(data, colWidths=[width * 0.58, width * 0.42])
        tbl.setStyle(TableStyle([
            ('SPAN',          (0,0), (-1,0)),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 6),
            ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('INNERGRID',     (0,1), (-1,-1), 0.3, LIGHT_GREY),
            ('BACKGROUND',    (0,0), (-1,-1), WHITE),
            ('BACKGROUND',    (0,0), (-1,0),  ACCENT_COLOR),
        ]))
        return tbl

    def _build_packing_items_table(self, items):
        """# | Description | SKU | Unit | Qty Ordered | Qty Packed | Balance | Remarks.
        Qty Ordered comes from the sale; the last three columns are left blank
        for staff to fill in by hand while physically packing the order. Only
        as many rows as there are items — no padding blank rows, so a short
        order doesn't waste page space."""
        headers = ['#', 'Description', 'SKU', 'Unit', 'Qty Ordered', 'Qty Packed', 'Balance', 'Remarks']
        col_w_raw = [0.3, 2.3, 0.9, 0.6, 0.9, 0.9, 0.8, 0.8]
        col_w = [w * TABLE_WIDTH / sum(col_w_raw) for w in col_w_raw]

        header_row = [Paragraph(f"<b>{h}</b>", self.styles['TblHeader']) for h in headers]
        table_data = [header_row]
        for idx, item in enumerate(items, 1):
            qty = item.get('quantity', 0)
            qty_str = f"{qty:,.2f}" if isinstance(qty, (int, float)) else str(qty)
            table_data.append([
                Paragraph(str(idx), self.styles['TblCell']),
                Paragraph(item.get('description', 'N/A'), self.styles['TblCell']),
                Paragraph(item.get('sku', '-'), self.styles['TblCell']),
                Paragraph(item.get('unit', '-'), self.styles['TblCell']),
                Paragraph(qty_str, self.styles['TblCell']),
                Paragraph('', self.styles['TblCell']),
                Paragraph('', self.styles['TblCell']),
                Paragraph('', self.styles['TblCell']),
            ])

        if len(table_data) == 1:
            table_data.append([Paragraph('1', self.styles['TblCell']),
                                Paragraph('No items listed', self.styles['TblCell'])]
                               + [Paragraph('-', self.styles['TblCell'])] * 6)

        tbl = Table(table_data, colWidths=col_w, rowHeights=[16] + [20] * (len(table_data) - 1))
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
            ('ALIGN',         (1,0),  (-1,-1), 'LEFT'),
            ('LINEBELOW',     (0,0),  (-1,0),  1.0, PRIMARY_COLOR),
            ('GRID',          (0,0),  (-1,-1), 0.3, LIGHT_GREY),
            ('LINEBELOW',     (0,-1), (-1,-1), 0.5, BORDER_GREY),
        ]))
        return tbl

    def _build_packing_verification_table(self):
        """PACKING & RECEIVING VERIFICATION sign-off grid: 2 rows x 3 columns,
        each cell a label + a blank (grid-bordered) box for a name/date/
        signature to be written in by hand at the time of packing/dispatch/
        receipt — no underscore fill line, just the empty bordered cell."""
        def cell(label):
            return [Paragraph(f"<b>{label}</b>", self.styles['BoxValue']),
                    Paragraph('', self.styles['BoxValue'])]

        row1 = cell('Packed By') + cell('Dispatched By') + cell('Received By')
        row2 = cell('Checked By') + cell('Date') + cell('Signature / Stamp')
        data = [[Paragraph("PACKING & RECEIVING VERIFICATION", self.styles['NotesTitle']), '', '', '', '', '']]
        # Interleave label/value pairs into 6 columns per row for the 3-across layout
        data.append([row1[0], row1[1], row1[2], row1[3], row1[4], row1[5]])
        data.append([row2[0], row2[1], row2[2], row2[3], row2[4], row2[5]])
        col_w = [0.9*inch, 1.6*inch, 1.0*inch, 1.6*inch, 0.9*inch, 1.5*inch]
        # Fixed row heights (rather than an underscore line) give each value
        # cell visible blank space to sign/write in, bounded by the grid box.
        tbl = Table(data, colWidths=col_w, rowHeights=[None, 32, 32])
        tbl.setStyle(TableStyle([
            ('SPAN',          (0,0), (-1,0)),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
            ('RIGHTPADDING',  (0,0), (-1,-1), 4),
            ('BOX',           (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('INNERGRID',     (0,1), (-1,-1), 0.3, LIGHT_GREY),
            ('BACKGROUND',    (0,0), (-1,0),  ACCENT_COLOR),
            ('BACKGROUND',    (0,1), (-1,-1), WHITE),
        ]))
        return tbl

    def generate_packing_slip(self, sale, slip=None):
        """Bilingual (English/Urdu) Packing Slip — a shipping/logistics form,
        not a financial document (no prices, discounts, or balances shown).
        Customer info, Related Invoice No., and each item's Description/SKU/
        Unit/Qty Ordered are auto-filled from the sale. When `slip` (a
        PackingSlip record) is given, the slip no./date/PO/partial-shipment/
        package/shipping/packing fields are filled from it too — only the
        per-item Qty Packed/Balance/Remarks columns and the sign-off grid
        stay blank, since those can only be known/signed at physical pack
        time. Without `slip` (legacy callers), all of those fields render
        blank for staff to fill in by hand."""
        elements = []

        # ── Header: company block (left) + title & meta form (right) ──────
        left = []
        logo = self._get_logo()
        if logo:
            left.append(logo)
            left.append(Spacer(1, 6))
        cname = self.company.name if self.company else "COMPANY"
        left.append(Paragraph(cname, self.styles['CompanyName']))
        if self.company:
            for attr, label in [('email', '<b>Email:</b> {}'), ('phone', '<b>Phone:</b> {}'), ('website', '<b>Website:</b> {}')]:
                val = getattr(self.company, attr, None)
                if val:
                    left.append(Paragraph(label.format(val), self.styles['CompanyInfo']))

        RIGHT_W = 3.4 * inch
        title_p = Paragraph("PACKING SLIP", self.styles['InvoiceTitle'])
        try:
            ur_reshaped = get_display(arabic_reshaper.reshape("پیکنگ سلپ"))
        except Exception:
            ur_reshaped = "پیکنگ سلپ"
        subtitle_p = Paragraph(ur_reshaped, ParagraphStyle(
            'PackingSlipUrduTitle', parent=self.styles['InvoiceSub'],
            fontName=self.urdu_font, fontSize=13, alignment=TA_RIGHT, textColor=TEXT_COLOR))

        if slip:
            partial_display = 'No'
            if slip.is_partial:
                partial_display = (f"Yes (Shipment {slip.partial_shipment_no} of {slip.partial_shipment_total})"
                                    if slip.partial_shipment_no and slip.partial_shipment_total else 'Yes')
            meta_rows = [
                ('Packing Slip No.', slip.slip_number or ''),
                ('Packing Date', slip.packing_date.strftime('%d-%b-%Y') if slip.packing_date else ''),
                ('Related Invoice No.', sale.invoice_number or ''),
                ('Sales Order / PO No.', slip.po_number or ''),
                ('Partial Shipment', partial_display),
                ('Number of Packages', str(slip.package_count) if slip.package_count else ''),
            ]
        else:
            meta_rows = [
                ('Packing Slip No.', ''),
                ('Packing Date', ''),
                ('Related Invoice No.', sale.invoice_number or ''),
                ('Sales Order / PO No.', ''),
                ('Partial Shipment', ''),
                ('Number of Packages', ''),
            ]
        meta_tbl = Table(
            [[Paragraph(l, self.styles['MetaLabel']), Paragraph(v if (v or slip) else '_' * 18, self.styles['MetaValue'])] for l, v in meta_rows],
            colWidths=[1.6 * inch, RIGHT_W - 1.6 * inch]
        )
        meta_tbl.setStyle(TableStyle([
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('LINEBELOW',     (0,0), (-1,-1), 0.3, LIGHT_GREY),
        ]))
        # InvoiceTitle is 26pt but inherits Normal's ~12pt leading (unset here, same
        # as every other document's header), so its glyphs overflow well below the
        # row's nominal height — a wide gap is needed before the next row starts,
        # same margin the plain invoice header leaves via its own Spacer(1, 22).
        right_tbl = Table([[title_p], [Spacer(1, 20)], [subtitle_p], [Spacer(1, 10)], [meta_tbl]], colWidths=[RIGHT_W])
        right_tbl.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))

        LEFT_W = TABLE_WIDTH - RIGHT_W - 0.1 * inch
        header_tbl = Table([[left, right_tbl]], colWidths=[LEFT_W, RIGHT_W])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(header_tbl)
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=0.6, color=BORDER_GREY, spaceAfter=8))

        # ── SHIP TO / OUR LOCATIONS ─────────────────────────────────────────
        customer = sale.customer
        ship_rows = [f"<b>Customer:</b> {customer.name}" if customer else "<b>Customer:</b> Walk-in Customer"]
        if customer:
            if getattr(customer, 'contact_person', None):
                ship_rows.append(f"<b>Contact Person:</b> {customer.contact_person}")
            if customer.phone:
                ship_rows.append(f"<b>Phone:</b> {customer.phone}")
            if customer.address:
                ship_rows.append(f"<b>Address:</b> {customer.address}")
            if getattr(customer, 'city', None):
                ship_rows.append(f"<b>City:</b> {customer.city}")

        def make_box(title_text, rows, width):
            data = [[Paragraph(f"<b>{title_text}</b>", self.styles['BoxTitle'])]]
            for row in rows:
                data.append([Paragraph(row, self.styles['BoxValue'])])
            tbl = Table(data, colWidths=[width])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('TOPPADDING', (0,0), (-1,0), 3), ('BOTTOMPADDING', (0,0), (-1,0), 3),
                ('TOPPADDING', (0,1), (-1,-1), 0), ('BOTTOMPADDING', (0,1), (-1,-1), 2),
                ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER_GREY), ('BACKGROUND', (0,0), (-1,-1), WHITE),
            ]))
            return tbl

        head_office_addr = (getattr(self.company, 'address', None) if self.company else None) or 'N/A'
        loc_rows = [
            f"<b>Head Office:</b> {head_office_addr}",
            "<b>Karachi:</b> LS-25, Super Auto Parts Market, Main Super Highway, Sohrab Goth, Karachi.",
        ]
        box1 = make_box("SHIP TO", ship_rows, 3.9 * inch)
        box2 = make_box("OUR LOCATIONS", loc_rows, 3.3 * inch)
        info_outer = Table([[box1, '', box2]], colWidths=[3.9*inch, 0.15*inch, 3.45*inch])
        info_outer.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(info_outer)
        elements.append(Spacer(1, 10))

        # ── PACKED ITEMS ─────────────────────────────────────────────────────
        elements.append(Paragraph("PACKED ITEMS", self.styles['SectionHeader']))
        items = []
        total_qty = 0.0
        total_weight = 0.0
        has_weight = False
        for item in sale.items:
            qty = float(item.quantity or 0)
            total_qty += qty
            product = item.product
            if product and getattr(product, 'weight', None):
                total_weight += qty * product.weight
                has_weight = True
            items.append({
                'description': product.name if product else 'Unknown Product',
                'sku': (product.sku if product and product.sku else '-'),
                'unit': (product.unit if product and product.unit else 'pcs'),
                'quantity': qty,
            })
        elements.append(self._build_packing_items_table(items))
        elements.append(Spacer(1, 10))

        # ── SHIPPING DETAILS / PACKING SUMMARY ──────────────────────────────
        if slip:
            shipping_fields = [
                ('Transport Company', slip.transport_company or ''),
                ('Bilty / LR No.', slip.bilty_no or ''),
                ('Tracking No.', slip.tracking_no or ''),
                ('Vehicle No.', slip.vehicle_no or ''),
                ('Gate Pass No.', slip.gate_pass_no or ''),
                ('Dispatch Date', slip.dispatch_date.strftime('%d-%b-%Y') if slip.dispatch_date else ''),
            ]
            summary_fields = [
                ('Total Ordered Qty', f"{slip.total_ordered_qty:,.2f}" if slip.total_ordered_qty is not None else f"{total_qty:,.2f}"),
                ('Total Packed Qty', f"{slip.total_packed_qty:,.2f}" if slip.total_packed_qty is not None else ''),
                ('Balance Qty', f"{slip.balance_qty:,.2f}" if slip.balance_qty is not None else ''),
                ('Total Packages', str(slip.package_count) if slip.package_count else ''),
                ('Gross Weight', f"{slip.gross_weight:,.2f} kg" if slip.gross_weight is not None else ''),
                ('Net Weight', f"{slip.net_weight:,.2f} kg" if slip.net_weight is not None else (f"{total_weight:,.2f} kg" if has_weight else '')),
            ]
        else:
            shipping_fields = [
                ('Transport Company', ''), ('Bilty / LR No.', ''), ('Tracking No.', ''),
                ('Vehicle No.', ''), ('Gate Pass No.', ''), ('Dispatch Date', ''),
            ]
            summary_fields = [
                ('Total Ordered Qty', f"{total_qty:,.2f}"),
                ('Total Packed Qty', ''),
                ('Balance Qty', ''),
                ('Total Packages', ''),
                ('Gross Weight', ''),
                ('Net Weight', f"{total_weight:,.2f} kg" if has_weight else ''),
            ]
        box_ship = self._build_field_grid_box("SHIPPING DETAILS", shipping_fields, 3.9 * inch)
        box_sum = self._build_field_grid_box("PACKING DETAILS", summary_fields, 3.3 * inch)
        ship_outer = Table([[box_ship, '', box_sum]], colWidths=[3.9*inch, 0.15*inch, 3.45*inch])
        ship_outer.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(ship_outer)
        elements.append(Spacer(1, 10))

        # ── VERIFICATION ─────────────────────────────────────────────────────
        elements.append(self._build_packing_verification_table())
        elements.append(Spacer(1, 10))

        # ── IMPORTANT NOTICE (bilingual) ────────────────────────────────────
        cname_for_notice = self.company.name if self.company else 'us'
        notice_en = (
            f"Verify the number of packages, SKU, product description, and quantity at the time of receipt. "
            f"Report any shortage, damage, incorrect product, or packaging issue to {cname_for_notice} immediately. "
            f"This Packing Slip is for packing, shipping, and delivery verification only. It is not an invoice, "
            f"payment receipt, or proof of payment. Prices, discounts, payments, and balances are intentionally not shown."
        )
        notice_ur = (
            f"سامان وصول کرتے وقت پیکجز کی تعداد، SKU، پروڈکٹ کی تفصیل اور مقدار کی تصدیق کریں۔ کسی کمی، نقصان، غلط پروڈکٹ یا "
            f"پیکنگ کے مسئلے کی صورت میں فوری طور پر {cname_for_notice} کو اطلاع دیں۔ یہ پیکنگ سلپ صرف پیکنگ، ترسیل اور وصولی کی "
            f"تصدیق کے لیے ہے۔ یہ انوائس، ادائیگی کی رسید یا ادائیگی کا ثبوت نہیں ہے۔ قیمت، ڈسکاؤنٹ، ادائیگی اور بقایا رقم اس "
            f"دستاویز پر درج نہیں کی گئی۔"
        )
        elements.append(self._build_important_notice(notice_en, notice_ur))

        self.footer_message = f"Thank you for your business! / {cname_for_notice}"
        self.doc.build(
            elements,
            onFirstPage=self._draw_page_decorations,
            onLaterPages=self._draw_page_decorations,
        )

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
                sig_img.drawWidth = 100
                sig_img.drawHeight = 100
                y -= 70
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

        # ── Center: FOOTER MESSAGE ─────────────────────────────────────────
        if self.footer_message:
            msg_y = divider_y - 11 - 20
            # Use Urdu font if available, otherwise fallback to Helvetica-Bold
            f_name = self.urdu_font if self.urdu_font != 'Helvetica' else 'Helvetica-Bold'
            c.setFont(f_name, 7.5)
            c.setFillColor(TEXT_COLOR)
            
            # Shape Urdu text for canvas drawing if needed
            display_msg = str(self.footer_message)
            try:
                # If it looks like Urdu/Arabic, reshape it
                reshaped = arabic_reshaper.reshape(display_msg)
                display_msg = get_display(reshaped)
            except Exception:
                pass
                
            c.drawCentredString(w / 2, msg_y, display_msg)

        # ── Right: CUSTOMER SUPPORT ────────────────────────────────────────
        if self.footer_show_company_info:
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
        if self.footer_show_page_number:
            c.setFont('Helvetica', 7)
            c.setFillColor(MUTED_TEXT)
            c.drawCentredString(w / 2, card_margin + 6, f"Page {doc.page}")

        c.restoreState()

    def generate_document(self, title, doc_number, date, due_date, client_data, items,
                           totals, payment_info=None, terms=None, notes=None,
                           status=None, ship_to=None, reference_data=None, currency=None,
                           ship_to_label=None, bill_to_label=None,
                           customer_name=None, amount_due=None, due_date_str=None,
                           is_purchase=False, is_invoice=False,
                           meta_labels=None, items_header='INVOICE ITEMS',
                           show_unit_col=False, discount_header='Unit Discount',
                           commercial_terms=None, important_notice=None,
                           show_acceptance=False, footer_message_override=None,
                           show_company_address=True):
        self.is_purchase = is_purchase
        if footer_message_override:
            self.footer_message = footer_message_override
        elements = []
        
        # Set custom ship_to label if provided (e.g., "SHIP FROM" for purchase docs)
        if ship_to_label:
            self._ship_to_label = ship_to_label
        else:
            self._ship_to_label = None
            
        # Set custom bill_to label if provided (e.g., "Statement" for purchase docs)
        if bill_to_label:
            self._bill_to_label = bill_to_label
        else:
            self._bill_to_label = None

        elements.append(self._build_header(title, doc_number, date, due_date, currency, status, meta_labels=meta_labels,
                                            show_company_address=show_company_address))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=0.6, color=BORDER_GREY, spaceAfter=8))
        show_locations = is_invoice or is_purchase
        elements.append(self._build_info_boxes(client_data, ship_to, reference_data, is_invoice=show_locations))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(items_header, self.styles['SectionHeader']))

        show_item_code = any('item_code' in item for item in items)
        show_sku = any('sku' in item for item in items)
        show_discount = any('unit_discount' in item for item in items)
        show_total_discount = any('total_discount' in item for item in items)
        elements.append(self._build_items_table(items, show_item_code, show_sku, show_discount,
                                                  discount_header=discount_header, show_unit_col=show_unit_col,
                                                  show_total_discount=show_total_discount))
        elements.append(Spacer(1, 10))

        # Prepare extra thank you message for invoices only
        extra_thank = None
        if customer_name and title.lower() == 'invoice':
            extra_thank_style = ParagraphStyle(
                'ExtraThankYou',
                parent=self.styles['Normal'],
                fontSize=9,
                fontName=self.urdu_font,
                alignment=TA_RIGHT,
                textColor=TEXT_COLOR,
                spaceAfter=6,
                leading=14,
                leftIndent=0
            )
            amount_due_fmt = f'{currency}{amount_due:,.2f}' if amount_due is not None else 'N/A'
            due_date_fmt = due_date_str if due_date_str else 'N/A'
            
            # ── English Message (Left Aligned) ──
            eng_style = ParagraphStyle(
                'ExtraThankYouEng',
                parent=self.styles['Normal'],
                fontSize=8.5,
                fontName='Helvetica',
                alignment=TA_LEFT,
                textColor=TEXT_COLOR,
                leading=12
            )
            eng_text = (
                f"Thank you, {customer_name}, for your recent purchase.<br/>"
                f"Your amount due is {amount_due_fmt}, due by {due_date_fmt}.<br/>"
                f"Any discount is valid only if paid by the due date.<br/>"
                f"If you have any questions, please let us know.<br/><br/>"
                f"Best regards,"
                f"We look forward to serving you again in the future."
            )
            eng_p = Paragraph(eng_text, eng_style)

            # ── Urdu Message (Shaped & Right Aligned) ──
            u_text = (
                f"شکریہ، {customer_name}، آپ کی حالیہ خریداری کے لیے۔\n"
                f"آپ کی قابلِ ادائیگی رقم {amount_due_fmt} ہے، جس کی آخری تاریخ {due_date_fmt} ہے۔"
                f"کوئی بھی رعایت صرف مقررہ تاریخ تک ادائیگی کی صورت میں ہی قابلِ قبول ہوگی۔\n"
                f"اگر آپ کے کوئی سوالات ہوں تو براہِ کرم ہمیں آگاہ کریں۔\n"
                f"نیک تمناؤں کے ساتھ،"
                f"ہم مستقبل میں دوبارہ آپ کی خدمت کرنے کے منتظر ہیں۔"
            )
            reshaped_text = arabic_reshaper.reshape(u_text)
            bidi_text = get_display(reshaped_text)
            bidi_text = bidi_text.replace('\n', '<br/>')
            urdu_p = Paragraph(bidi_text, extra_thank_style)
            
            # Combine in a two-column table
            extra_thank = Table([[eng_p, urdu_p]], colWidths=[3.7 * inch, 3.7 * inch])
            extra_thank.setStyle(TableStyle([
                ('VALIGN',      (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING',(0,0), (-1,-1), 0),
            ]))

        elements.extend(self._build_bottom_section(totals, payment_info, terms, notes, extra_thank=extra_thank, is_purchase=is_purchase))

        if commercial_terms:
            elements.append(Spacer(1, 10))
            elements.append(self._build_commercial_terms(commercial_terms))
        if important_notice:
            elements.append(Spacer(1, 10))
            elements.append(self._build_important_notice(important_notice.get('en', ''), important_notice.get('ur')))
        if show_acceptance:
            elements.append(Spacer(1, 10))
            elements.append(self._build_acceptance_table())

        # If you want the thank-you message **above the header** instead, move it here:
        # elements.insert(0, extra_thank)
        # elements.insert(0, Spacer(1, 12))
        # (and remove extra_thank from _build_bottom_section call)

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

    # ── INVOICE / QUOTATION (same design; quotation only retitles) ────────
    if doc_type in ('invoice', 'quotation'):
        is_quote = (doc_type == 'quotation')
        if is_quote:
            title = 'Quotation'
            quote_meta_labels = {'number': 'Quotation No:', 'date': 'Quotation Date:', 'due': 'Valid Until:'}
            quote_items_header = 'QUOTATION ITEMS'
        else:
            title = getattr(template_config, 'TITLE', 'Invoice') if template_config else "Invoice"
            quote_meta_labels = None
            quote_items_header = 'INVOICE ITEMS'
        doc_number = obj.invoice_number
        if is_quote and doc_number and doc_number.upper().startswith('INV-'):
            # Display-only: a quotation shouldn't visibly borrow the invoice
            # numbering prefix. Doesn't touch the stored invoice_number.
            doc_number = 'QTN-' + doc_number[4:]
        client_data = {
            'name':       obj.customer.name        if obj.customer else "Walk-in Customer",
            'address':    obj.customer.address      if obj.customer else "",
            'email':      obj.customer.email        if obj.customer else "",
            'phone':      obj.customer.phone        if obj.customer else "",
            'gst_number': obj.customer.gst_number   if obj.customer else "",
        }
        if obj.customer and getattr(obj.customer, 'company_name', None):
            client_data['company'] = obj.customer.company_name
        if is_quote:
            if obj.customer and getattr(obj.customer, 'contact_person', None):
                client_data['contact_person'] = obj.customer.contact_person
            if getattr(obj, 'salesman', None):
                client_data['salesperson'] = obj.salesman.name

        ship_to = None

        reference_data = {}
        if hasattr(obj, 'po_number')   and obj.po_number:   reference_data['PO No']       = obj.po_number
        if hasattr(obj, 'sales_order') and obj.sales_order: reference_data['Sales Order'] = obj.sales_order
        if hasattr(obj, 'project')     and obj.project:     reference_data['Project']     = obj.project.name if obj.project else ""
        if obj.customer and hasattr(obj.customer, 'customer_id'):
            reference_data['Customer ID'] = str(obj.customer.customer_id)

        # Calculate effective discount based on overdue status and override flag
        is_restricted = getattr(obj, 'is_discount_restricted', False)
        effective_discount = getattr(obj, 'effective_discount_amount', 0)

        # Per-item discount total (same source used on the invoice detail page): prefer the
        # real per-item discount entered on the invoice, falling back to a proportional split
        # of the header discount only for older invoices created before per-item discounts
        # existed. Suspended entirely while the overdue restriction is in effect.
        items_discount_sum = sum(float(it.discount or 0) for it in obj.items)
        show_item_discount = (not is_restricted) and (effective_discount > 0 or items_discount_sum > 0)

        items = []
        for item in obj.items:
            entry = {
                'description': item.product.name if item.product else "Unknown Product",
                'quantity':    item.quantity,
                'rate':        f"{currency}{item.unit_price:,.2f}",
                'amount':      f"{currency}{item.total:,.2f}",
            }
            if item.product and hasattr(item.product, 'sku') and item.product.sku:
                entry['sku'] = item.product.sku
            if hasattr(item, 'item_code')        and item.item_code:        entry['item_code']        = item.item_code
            if hasattr(item, 'sub_description')  and item.sub_description:  entry['sub_description']  = item.sub_description
            if is_quote:
                entry['unit'] = (item.product.unit if item.product and item.product.unit else 'pcs')
            elif hasattr(item, 'unit') and item.unit:
                entry['unit'] = item.unit
            if show_item_discount:
                if items_discount_sum > 0:
                    item_discount_total = float(item.remaining_discount or 0)
                else:
                    item_discount_total = (item.total / obj.subtotal * effective_discount) if obj.subtotal > 0 else 0
                # Quotation shows the line's total discount (matches the "Amount" column
                # being a line total too); the invoice PDF shows a genuine per-unit figure.
                shown_discount = item_discount_total if is_quote else ((item_discount_total / item.quantity) if item.quantity else 0)
                entry['unit_discount'] = f"{currency}{shown_discount:,.2f}"
                if not is_quote:
                    # Line-total discount alongside the per-unit figure, with the
                    # percentage of the line subtotal — same pair the invoice
                    # detail page shows ("Unit Discount" / "Total Discount").
                    line_subtotal = float(item.quantity or 0) * float(item.unit_price or 0)
                    pct = (item_discount_total / line_subtotal * 100) if line_subtotal > 0 else 0
                    entry['total_discount'] = (
                        f"{currency}{item_discount_total:,.2f}"
                        + (f" ({pct:.0f}%)" if item_discount_total > 0 else "")
                    )
            items.append(entry)

        sc = obj.shipping_charge if (hasattr(obj, 'shipping_charge') and obj.shipping_charge) else 0

        if is_quote:
            # A quotation isn't a paid document yet — show what's quoted, not
            # payment/advance history.
            totals = [
                ("Subtotal",             f"{currency}{obj.subtotal:,.2f}"),
                ("Quotation Discount",   f"{currency}{effective_discount:,.2f}"),
                ("Shipping / Freight",   f"{currency}{sc:,.2f}"),
                ("Tax",                  f"{currency}{obj.tax:,.2f}"),
                ("Other Charges",        f"{currency}0.00"),
                ("Total Quoted Amount",  f"{currency}{obj.total:,.2f}"),
            ]
        else:
            # Determine discount display value
            discount_label = "<b>One Time Payment Discount</b>"
            discount_display = f"{currency}{effective_discount:,.2f}"
            if is_restricted and getattr(obj, 'base_discount_amount', 0) > 0:
                discount_label = "<b>Discount</b>"
                discount_display = "Reversal"

            # obj.subtotal/obj.tax are already net-of-returns (see
            # Sale.calculate_totals()) — reverse that here so the PDF shows the
            # gross, pre-return subtotal/tax with "Returns" as its own visible
            # deduction line. That way Subtotal - Discount + Shipping + Tax -
            # Returns reconciles exactly to Total Due instead of double-counting
            # the return (which is what net Subtotal + a separate Returns line
            # would do).
            returns_subtotal = sum(ret.subtotal for ret in obj.returns) if hasattr(obj, 'returns') else 0
            returns_tax = sum(ret.tax for ret in obj.returns) if hasattr(obj, 'returns') else 0
            returns_total = sum(ret.total for ret in obj.returns) if hasattr(obj, 'returns') else 0
            gross_subtotal = obj.subtotal + returns_subtotal
            gross_tax = obj.tax + returns_tax

            totals = [
                ("Subtotal",           f"{currency}{gross_subtotal:,.2f}"),
                (discount_label,       discount_display),
                ("Shipping / Freight", f"{currency}{sc:,.2f}"),
                ("Tax",                f"{currency}{gross_tax:,.2f}"),
            ]

            if returns_total > 0.009:
                totals.append(("Returns", f"-{currency}{returns_total:,.2f}"))

            totals.append(("Total Due", f"{currency}{obj.total:,.2f}"))

            # obj.paid_amount is a mix of actual cash payments AND any customer
            # advance credit applied to this invoice. Break the advance portion
            # out into its own line instead of folding it into "Amount Paid".
            advance_applied_amt = float(getattr(obj, 'advance_applied', 0) or 0)
            if advance_applied_amt > 0.009:
                totals.append(("Advance Applied", f"{currency}{advance_applied_amt:,.2f}"))

            # Cash-only portion of paid_amount (excludes advance credit applied above)
            cash_applied = max(0.0, obj.paid_amount - advance_applied_amt)

            # Gross cash amount actually received from the customer against this invoice
            # (approved Payment rows) — can exceed cash_applied when the customer
            # overpaid, since the excess is tracked separately as new customer
            # advance credit rather than applied to this invoice.
            gross_paid = sum(p.amount for p in obj.payments if p.is_approved) if hasattr(obj, 'payments') else cash_applied

            if gross_paid > cash_applied + 0.009:
                totals.append(("Paid Amount",  f"{currency}{gross_paid:,.2f}"))
                totals.append(("Invoice Paid", f"{currency}{cash_applied:,.2f}"))
            else:
                totals.append(("Amount Paid",  f"{currency}{cash_applied:,.2f}"))

            totals.append(("Balance", f"{currency}{obj.balance_due:,.2f}"))

            # Show any unapplied advance credit (e.g. from a past overpayment) so the
            # customer sees the remaining balance in their favor on the invoice itself.
            customer_remaining = float(obj.customer.remaining_advance_balance or 0) if obj.customer else 0
            if customer_remaining > 0.009:
                totals.append(("Customer Remaining Advance", f"{currency}{customer_remaining:,.2f}"))

        payment_info = None
        if settings:
            payment_info = {k: v for k, v in {
                'Payment Terms':  getattr(settings, 'payment_terms', None),
                'Bank Name':      getattr(settings, 'bank_name', None),
                'Account Holder': getattr(settings, 'account_holder_name', None),
                'Account Number': getattr(settings, 'account_number', None),
                'IBAN':           getattr(settings, 'ifsc_code', None),
                'SWIFT Code':     getattr(settings, 'swift_code', None),
            }.items() if v}
        elif company:
            payment_info = {k: v for k, v in {
                'Bank Name':      getattr(company, 'bank_name', None),
                'Account Number': getattr(company, 'account_number', None),
                'IBAN':           getattr(company, 'ifsc_code', None),
            }.items() if v}

        cur_label = getattr(obj, 'currency', None) or (currency if currency != 'PKR' else 'PKR')

        quote_extra = {}
        if is_quote:
            status_label = getattr(obj, 'status_label', None)
            if status_label:
                quote_status = status_label
            elif getattr(obj, 'is_draft', False):
                quote_status = 'DRAFT'
            elif not getattr(obj, 'is_approved', True):
                quote_status = 'PENDING APPROVAL'
            else:
                quote_status = 'CONFIRMED'

            # Validity reflects the quotation's actual "Valid Until" date rather
            # than a fixed figure — falls back to the old static wording only
            # when no due_date is set (e.g. an older quotation created before
            # "Valid Until" was required).
            if obj.due_date and obj.date and obj.due_date > obj.date:
                validity_days = (obj.due_date - obj.date).days
                validity_display = f"{validity_days} Calendar Day{'s' if validity_days != 1 else ''} (until {obj.due_date.strftime('%d-%b-%Y')})"
            elif obj.due_date:
                validity_display = f"Until {obj.due_date.strftime('%d-%b-%Y')}"
            else:
                validity_display = '7 Calendar Days'

            commercial_terms = [
                ('Validity',     validity_display,            'Payment Terms', '100% Advance / Credit Terms'),
                ('Delivery',     '3-5 Working Days',           'Freight',       'Included / Excluded'),
                ('Availability', 'Subject to Stock Confirmation', 'Warranty',   f"As per {company.name if company else 'Company'} Warranty Policy"),
            ]
            important_notice = {
                'en': ('Before approval, verify the product description, OE number, engine, chassis, quantity and '
                       'required cover / impeller configuration. This quotation is not an invoice and does not confirm payment.'),
                'ur': ('منظوری سے پہلے، پروڈکٹ کی تفصیل، او ای نمبر، انجن، چیسس، مقدار اور مطلوبہ کور یا امپیلر کنفیگریشن کی تصدیق کریں۔ '
                       'یہ کوٹیشن انوائس نہیں ہے اور ادائیگی کی تصدیق نہیں کرتی۔'),
            }
            quote_extra = dict(
                show_unit_col=True,
                discount_header='Discount',
                commercial_terms=commercial_terms,
                important_notice=important_notice,
                show_acceptance=True,
                footer_message_override=f"Thank you for considering {company.name}." if company else None,
            )

        generator.generate_document(
            title=title, doc_number=doc_number,
            date=obj.date, due_date=obj.due_date,
            client_data=client_data, items=items, totals=totals,
            payment_info=payment_info,
            terms=None if is_quote else (obj.terms or (settings.default_terms if settings else None)),
            notes=None if is_quote else (obj.notes or (settings.default_notes if settings else None)),
            status=quote_status if is_quote else getattr(obj, 'status', None),
            ship_to=ship_to, reference_data=reference_data, currency=cur_label,
            ship_to_label=None,
            bill_to_label='QUOTATION TO' if is_quote else None,
            customer_name=obj.customer.name if obj.customer else None,
            amount_due=obj.balance_due if hasattr(obj, 'balance_due') else None,
            due_date_str=obj.due_date.strftime('%d-%m-%Y') if hasattr(obj, 'due_date') and obj.due_date else None,
            is_invoice=True,
            meta_labels=quote_meta_labels,
            items_header=quote_items_header,
            show_company_address=False,
            **quote_extra,
        )

    # ── PURCHASE BILL ─────────────────────────────────────────────────────
    elif doc_type == 'purchase':
        title      = getattr(template_config, 'TITLE', 'Purchase') if template_config else "Purchase"
        doc_number = obj.bill_number
        client_data = {
            'name':       obj.vendor.name       if obj.vendor else "Unknown Vendor",
            'address':    obj.vendor.address    if obj.vendor else "",
            'email':      obj.vendor.email      if obj.vendor else "",
            'phone':      obj.vendor.phone      if obj.vendor else "",
            'gst_number': obj.vendor.gst_number if obj.vendor else "",
        }
        if obj.vendor and getattr(obj.vendor, 'company_name', None):
            client_data['company'] = obj.vendor.company_name
        
        ship_to = None
        
        reference_data = {}
        if obj.po_id and obj.source_po:
            reference_data['Purchase Order'] = obj.source_po.po_number
        if hasattr(obj, 'project') and obj.project:
            reference_data['Project'] = obj.project.name if obj.project else ""

        items = []
        has_cancelled = False
        for item in obj.items:
            unit_val = getattr(item, 'unit', None)
            if (not unit_val or unit_val == '-') and item.product:
                unit_val = getattr(item.product, 'unit', '-')

            cq = getattr(item, 'cancelled_quantity', 0) or 0
            if cq > 0:
                has_cancelled = True

            entry = {
                'description':        item.product.name if item.product else "Unknown Product",
                'quantity':           item.quantity,
                'unit':               unit_val or '-',
                'rate':               f"{currency}{item.unit_price:,.2f}",
                'amount':             f"{currency}{item.total:,.2f}",
                'cancelled_quantity': cq,
            }
            if item.product and hasattr(item.product, 'sku') and item.product.sku:
                entry['sku'] = item.product.sku
            items.append(entry)

        # Tell the generator whether to render the Cancelled column
        generator._has_cancelled_items = has_cancelled

        totals = [("Subtotal", f"{currency}{obj.subtotal:,.2f}"),
                  ("Tax",      f"{currency}{obj.tax:,.2f}"),
                  ("Discount", f"-{currency}{obj.discount:,.2f}")]
        
        # Shipping removed from PDF as per user request
        if obj.cancelled_amount > 0:
            totals += [("Cancelled Amount", f"-{currency}{obj.cancelled_amount:,.2f}")]
            
        totals += [("Total Due", f"{currency}{obj.total - obj.shipping_charge:,.2f}")]

        # Vendor advance credit applied to THIS bill (reduces what we pay now)
        advance_applied_amt = float(getattr(obj, 'advance_applied', 0) or 0)
        if advance_applied_amt > 0.009:
            totals.append(("Advance Applied", f"-{currency}{advance_applied_amt:,.2f}"))

        # Cash-only portion of paid_amount (excludes advance credit applied above)
        cash_applied = max(0.0, obj.paid_amount - advance_applied_amt)

        # Gross amount actually paid to the vendor against this bill (approved
        # BillPayments) — can exceed cash_applied when we overpaid, since the
        # excess is credited as new vendor advance rather than applied here.
        gross_paid = sum(p.amount for p in obj.bill_payments if p.is_approved) if hasattr(obj, 'bill_payments') else cash_applied

        if gross_paid > cash_applied + 0.009:
            totals.append(("Paid Amount", f"{currency}{gross_paid:,.2f}"))
            totals.append(("Bill Paid",   f"{currency}{cash_applied:,.2f}"))
        else:
            totals.append(("Amount Paid", f"{currency}{cash_applied:,.2f}"))

        totals.append(("Balance Due", f"{currency}{obj.balance_due:,.2f}"))

        # Show any remaining vendor advance credit (e.g. from this overpayment) so
        # the credit in our favour is visible on the bill itself.
        vendor_remaining = float(obj.vendor.remaining_advance_balance or 0) if getattr(obj, 'vendor', None) else 0
        if vendor_remaining > 0.009:
            totals.append(("Vendor Remaining Advance", f"{currency}{vendor_remaining:,.2f}"))

        # Build clean notes — strip internal audit lines ([Cancelled…] / [Reversed…])
        import re as _re
        raw_notes = obj.notes or ''
        clean_lines = [
            ln for ln in raw_notes.splitlines()
            if not _re.match(r'\s*\[(Cancelled|Rerversed|Reversed)', ln)
        ]
        notes = '\n'.join(clean_lines).strip()

        # Append useful bill info
        if obj.due_date:
            if notes: notes += '\n'
            notes += f"Due Date: {obj.due_date.strftime('%d-%m-%Y')}"
            if obj.is_overdue:
                days = (datetime.utcnow().date() - obj.due_date.date()).days
                notes += f" (Overdue by {days} days)"
        if obj.po_id and obj.source_po:
            if notes: notes += '\n'
            notes += f"Purchase Order: {obj.source_po.po_number}"

        # If cancelled, add a clean one-line summary
        if obj.status == 'cancelled' and obj.cancelled_at and obj.cancelled_amount > 0:
            if notes: notes += '\n'
            notes += (f"Cancellation Date: {obj.cancelled_at.strftime('%d-%m-%Y %H:%M')} — "
                      f"Cancelled Amount: {currency}{obj.cancelled_amount:,.2f}")

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
            bill_to_label='Statement',
            is_purchase=True
        )

    # ── PURCHASE ORDER ────────────────────────────────────────────────────
    elif doc_type == 'purchase_order':
        title      = getattr(template_config, 'TITLE', 'Purchase') if template_config else "Purchase"
        doc_number = obj.po_number
        client_data = {
            'name':       obj.vendor.name       if obj.vendor else "Unknown Vendor",
            'address':    obj.vendor.address    if obj.vendor else "",
            'email':      obj.vendor.email      if obj.vendor else "",
            'phone':      obj.vendor.phone      if obj.vendor else "",
            'gst_number': obj.vendor.gst_number if obj.vendor else "",
        }
        if obj.vendor and getattr(obj.vendor, 'company_name', None):
            client_data['company'] = obj.vendor.company_name
        
        ship_to = None
        
        reference_data = {}
        if hasattr(obj, 'project') and obj.project:
            reference_data['Project'] = obj.project.name if obj.project else ""

        items = []
        for item in obj.items:
            # Get unit from item if it exists, otherwise from product
            unit_val = getattr(item, 'unit', None)
            if (not unit_val or unit_val == '-') and item.product:
                unit_val = getattr(item.product, 'unit', '-')
                
            entry = {
                'description': item.product.name if item.product else "Unknown Product",
                'quantity':    item.quantity,
                'unit':        unit_val or '-',
                'rate':        f"{currency}{item.unit_price:,.2f}",
                'amount':      f"{currency}{item.total:,.2f}",
            }
            if item.product and hasattr(item.product, 'sku') and item.product.sku:
                entry['sku'] = item.product.sku
            items.append(entry)

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
            bill_to_label='Statement',
        )

    buffer.seek(0)
    return buffer


def _build_payment_receipt_pdf(
    payment_number, payment_date, payment_method, amount, notes,
    party_role_label, party_name, party_phone, party_email, party_address,
    doc_label, doc_number, doc_total, doc_paid_to_date, doc_balance_due,
    amount_label, thank_you_note, company=None,
):
    """
    Shared layout for both the Sales (customer) and Purchase (vendor) auto-
    generated cash-payment receipts — kept as one function so the two receipt
    types always look consistent. Returns a BytesIO buffer positioned at 0.
    """
    DARK_GREEN = colors.HexColor('#146c43')
    GREEN = colors.HexColor('#198754')
    LIGHT_GREEN = colors.HexColor('#eaf7ef')
    BORDER = colors.HexColor('#dee2e6')
    MUTED = colors.HexColor('#6c757d')
    INK = colors.HexColor('#212529')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=36, bottomMargin=36, leftMargin=40, rightMargin=40,
    )
    header_company_style = ParagraphStyle('ReceiptHeaderCompany', fontName='Helvetica-Bold', fontSize=15,
                                           textColor=colors.white, leading=18)
    header_sub_style = ParagraphStyle('ReceiptHeaderSub', fontName='Helvetica', fontSize=9,
                                       textColor=colors.HexColor('#d4f0e0'), leading=12)
    header_title_style = ParagraphStyle('ReceiptHeaderTitle', fontName='Helvetica-Bold', fontSize=18,
                                         textColor=colors.white, alignment=TA_RIGHT, leading=20)
    header_num_style = ParagraphStyle('ReceiptHeaderNum', fontName='Helvetica', fontSize=9,
                                       textColor=colors.HexColor('#d4f0e0'), alignment=TA_RIGHT, leading=12)
    section_label_style = ParagraphStyle('ReceiptSectionLabel', fontName='Helvetica-Bold', fontSize=9,
                                          textColor=DARK_GREEN, spaceAfter=4)
    label_style = ParagraphStyle('ReceiptLabel', fontName='Helvetica', fontSize=8, textColor=MUTED, leading=11)
    value_style = ParagraphStyle('ReceiptValue', fontName='Helvetica', fontSize=10.5, textColor=INK, leading=14)
    value_bold_style = ParagraphStyle('ReceiptValueBold', parent=value_style, fontName='Helvetica-Bold')

    elements = []

    # ── Header banner ────────────────────────────────────────────────────
    company_name = getattr(company, 'name', None) or 'Company'
    company_addr = getattr(company, 'address', None) or ''
    header_left = [Paragraph(company_name, header_company_style)]
    if company_addr:
        header_left.append(Paragraph(company_addr, header_sub_style))
    header_right = [
        Paragraph('PAYMENT RECEIPT', header_title_style),
        Paragraph(f"#{payment_number}", header_num_style),
    ]
    header_table = Table([[header_left, header_right]], colWidths=[300, 200])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_GREEN),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 16),
        ('RIGHTPADDING', (1, 0), (1, 0), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 16),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width='100%', color=GREEN, thickness=3, spaceAfter=0))
    elements.append(Spacer(1, 18))

    # ── Party info / Receipt info, side by side ─────────────────────────
    party_block = [
        Paragraph(party_role_label, section_label_style),
        Paragraph(party_name, value_bold_style),
    ]
    if party_phone:
        party_block.append(Paragraph(f"Phone: {party_phone}", value_style))
    if party_email:
        party_block.append(Paragraph(f"Email: {party_email}", value_style))
    if party_address:
        party_block.append(Paragraph(party_address, value_style))

    receipt_info = Table([
        [Paragraph(doc_label, label_style), Paragraph(doc_number, value_bold_style)],
        [Paragraph('Payment Date', label_style), Paragraph(payment_date.strftime('%d-%m-%Y'), value_style)],
        [Paragraph('Payment Method', label_style), Paragraph(payment_method, value_style)],
    ], colWidths=[90, 130])
    receipt_info.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    info_table = Table([[party_block, receipt_info]], colWidths=[280, 220])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    # ── Amount highlight ─────────────────────────────────────────────────
    amount_label_style = ParagraphStyle('ReceiptAmountLabel', fontName='Helvetica-Bold', fontSize=10,
                                         textColor=DARK_GREEN, alignment=TA_LEFT)
    amount_value_style = ParagraphStyle('ReceiptAmountValue', fontName='Helvetica-Bold', fontSize=22,
                                         textColor=DARK_GREEN, alignment=TA_RIGHT)
    amount_box = Table([[
        Paragraph(amount_label, amount_label_style),
        Paragraph(f"PKR {amount:,.2f}", amount_value_style),
    ]], colWidths=[250, 250])
    amount_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREEN),
        ('BOX', (0, 0), (-1, -1), 1, GREEN),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 14),
        ('RIGHTPADDING', (1, 0), (1, 0), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(amount_box)
    elements.append(Spacer(1, 18))

    # ── Balance summary ──────────────────────────────────────────────────
    summary_rows = [
        [Paragraph(f"{doc_label.rstrip('#').strip()} Total", label_style), Paragraph('Paid to Date', label_style), Paragraph('Balance Due', label_style)],
        [Paragraph(f"PKR {doc_total:,.2f}", value_style),
         Paragraph(f"PKR {doc_paid_to_date:,.2f}", value_style),
         Paragraph(f"PKR {doc_balance_due:,.2f}", value_bold_style if doc_balance_due > 0 else value_style)],
    ]
    summary_table = Table(summary_rows, colWidths=[160, 160, 160])
    summary_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(summary_table)

    if notes:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph('NOTES', section_label_style))
        notes_box = Table([[Paragraph(notes, value_style)]], colWidths=[480])
        notes_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(notes_box)

    elements.append(Spacer(1, 28))
    elements.append(HRFlowable(width='100%', color=BORDER, thickness=0.75))
    elements.append(Spacer(1, 8))
    footer_style = ParagraphStyle('ReceiptFooter', fontName='Helvetica', fontSize=8, textColor=MUTED, alignment=TA_CENTER)
    elements.append(Paragraph(thank_you_note, footer_style))
    elements.append(Paragraph(
        f"Auto-generated cash payment receipt — no signature required. Generated on {datetime.now().strftime('%d-%m-%Y %H:%M')}.",
        footer_style,
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_payment_receipt_pdf(payment, sale, company=None):
    """
    Self-contained receipt PDF, auto-generated for Cash payments that skip the
    manual proof upload — stands in for the uploaded image/PDF so the Payment
    History table's Receipt column always has something to show/link to.
    Returns a BytesIO buffer positioned at 0.
    """
    customer = sale.customer
    return _build_payment_receipt_pdf(
        payment_number=payment.payment_number,
        payment_date=payment.date,
        payment_method=payment.method,
        amount=payment.amount,
        notes=payment.notes,
        party_role_label='BILLED TO',
        party_name=customer.name if customer else 'Walk-in Customer',
        party_phone=customer.phone if customer else None,
        party_email=customer.email if customer else None,
        party_address=customer.address if customer else None,
        doc_label='Invoice #',
        doc_number=sale.invoice_number,
        doc_total=sale.total,
        doc_paid_to_date=sale.paid_amount,
        doc_balance_due=sale.total - sale.paid_amount,
        amount_label='AMOUNT RECEIVED',
        thank_you_note='Thank you for your payment.',
        company=company,
    )


def generate_bill_payment_receipt_pdf(payment, bill, company=None):
    """
    Same auto-generated receipt as generate_payment_receipt_pdf(), for the
    Purchase module: a Cash payment recorded against a vendor bill that skips
    the manual proof upload gets this instead, showing the vendor's full
    details rather than a customer's.
    """
    vendor = bill.vendor
    return _build_payment_receipt_pdf(
        payment_number=f"BP-{payment.id}" if payment.id else 'BP-NEW',
        payment_date=payment.date,
        payment_method=payment.payment_method,
        amount=payment.amount,
        notes=payment.notes,
        party_role_label='PAID TO',
        party_name=vendor.name if vendor else 'Vendor',
        party_phone=vendor.phone if vendor else None,
        party_email=vendor.email if vendor else None,
        party_address=vendor.address if vendor else None,
        doc_label='Bill #',
        doc_number=bill.bill_number,
        doc_total=bill.total,
        doc_paid_to_date=bill.paid_amount,
        doc_balance_due=bill.total - bill.paid_amount,
        amount_label='AMOUNT PAID',
        thank_you_note='Thank you for your business.',
        company=company,
    )


def generate_packing_slip_pdf(sale, company, slip=None):
    """Bilingual (English/Urdu) shipping Packing Slip for a Sale — a physical
    packing/dispatch form, not a financial document. See
    ProfessionalPDFGenerator.generate_packing_slip() for what's auto-filled
    from the sale/slip vs. left blank for staff to fill in by hand."""
    buffer = io.BytesIO()
    generator = ProfessionalPDFGenerator(buffer, company, None, None)
    generator.generate_packing_slip(sale, slip)
    buffer.seek(0)
    return buffer