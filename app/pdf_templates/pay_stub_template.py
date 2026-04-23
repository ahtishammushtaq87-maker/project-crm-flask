import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus.flowables import HRFlowable

# ─── Constants ─────────────────────────────────────────────────────────────────
CURRENCY_SYMBOL = 'Rs'
TITLE = 'PAY SLIP'
FOOTER_MESSAGE = 'This is a computer-generated document. No signature required.'

PAGE_W, PAGE_H = A4
L_MARGIN = R_MARGIN = 28
T_MARGIN = 22
B_MARGIN = 28
USABLE_W = PAGE_W - L_MARGIN - R_MARGIN   # ≈ 539 pts

# Column widths (must sum to USABLE_W)
LEFT_COL  = USABLE_W * 0.47   # earnings / deductions
RIGHT_COL = USABLE_W * 0.47   # attendance / summary
GAP_COL   = USABLE_W * 0.06   # spacer between columns

# Inner table label/value splits
LBL_W  = LEFT_COL  * 0.62
VAL_W  = LEFT_COL  * 0.38
RLBL_W = RIGHT_COL * 0.62
RVAL_W = RIGHT_COL * 0.38

# ─── Palette ───────────────────────────────────────────────────────────────────
C_PRIMARY   = colors.HexColor("#1B3A6B")   # deep navy
C_ACCENT    = colors.HexColor("#1B7F4B")   # forest green
C_DANGER    = colors.HexColor("#B71C1C")   # deep red
C_AMBER     = colors.HexColor("#E65100")   # orange-amber for net pay
C_HEADER_BG = colors.HexColor("#1B3A6B")
C_WHITE     = colors.white
C_BLACK     = colors.HexColor("#1A1A1A")
C_LIGHT_BG  = colors.HexColor("#F7F9FC")
C_STRIPE    = colors.HexColor("#EEF2F7")
C_BORDER    = colors.HexColor("#C8D4E8")
C_MUTED     = colors.HexColor("#5C6B82")
C_ATT_BG    = colors.HexColor("#EBF5FF")
C_ATT_HEAD  = colors.HexColor("#1B6B9B")
C_NET_BG    = colors.HexColor("#FFF3E0")
C_NET_BORDER= colors.HexColor("#E65100")
C_TOTAL_BG  = colors.HexColor("#E8EFF8")


def _hex(h):
    return colors.HexColor(h)


class PayStubPDFGenerator:

    def __init__(self, buffer, company=None):
        self.buffer = buffer
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=R_MARGIN,
            leftMargin=L_MARGIN,
            topMargin=T_MARGIN,
            bottomMargin=B_MARGIN,
        )
        self.styles = getSampleStyleSheet()
        self.company = company
        self._build_styles()

    # ── Styles ──────────────────────────────────────────────────────────────────
    def _build_styles(self):
        S = self.styles

        def add(name, **kw):
            base = kw.pop('parent', S['Normal'])
            S.add(ParagraphStyle(name, parent=base, **kw))

        # Header area
        add('DocTitle',      fontSize=18, textColor=C_PRIMARY,  fontName='Helvetica-Bold',  alignment=TA_CENTER, spaceAfter=1, leading=22)
        add('DocSubTitle',   fontSize=8.5,textColor=C_MUTED,    alignment=TA_CENTER, spaceAfter=4, leading=11)
        add('CompanyName',   fontSize=11, textColor=C_PRIMARY,  fontName='Helvetica-Bold',  alignment=TA_CENTER, spaceAfter=2, leading=14)
        add('CompanyAddr',   fontSize=7.5,textColor=C_MUTED,    alignment=TA_CENTER, spaceAfter=0, leading=10)

        # Employee info block
        add('EmpName',       fontSize=10.5,textColor=C_BLACK,  fontName='Helvetica-Bold', alignment=TA_LEFT, leading=13, spaceAfter=1)
        add('EmpLabel',      fontSize=7.5, textColor=C_MUTED,   alignment=TA_LEFT,  leading=10)
        add('EmpValue',      fontSize=8,   textColor=C_BLACK,   fontName='Helvetica-Bold', alignment=TA_LEFT, leading=10)

        # Section headers (colored band)
        add('SecHdr',        fontSize=8,   textColor=C_WHITE,   fontName='Helvetica-Bold', alignment=TA_LEFT,  leading=10)
        add('SecHdrAtt',     fontSize=8,   textColor=C_WHITE,   fontName='Helvetica-Bold', alignment=TA_LEFT,  leading=10)

        # Row labels & values
        add('RowLabel',      fontSize=8,   textColor=C_MUTED,   alignment=TA_LEFT,  leading=10)
        add('RowValue',      fontSize=8,   textColor=C_BLACK,   alignment=TA_RIGHT, leading=10)
        add('RowValPos',     fontSize=8,   textColor=C_ACCENT,  fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=10)
        add('RowValNeg',     fontSize=8,   textColor=C_DANGER,  fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=10)
        add('RowValAmb',     fontSize=8,   textColor=C_AMBER,   fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=10)

        # Totals
        add('TotLabel',      fontSize=8.5, textColor=C_BLACK,   fontName='Helvetica-Bold', alignment=TA_LEFT,  leading=11)
        add('TotValue',      fontSize=8.5, textColor=C_BLACK,   fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=11)

        # Net row
        add('NetLabel',      fontSize=10,  textColor=C_AMBER,   fontName='Helvetica-Bold', alignment=TA_LEFT,  leading=13)
        add('NetValue',      fontSize=10,  textColor=C_AMBER,   fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=13)

        # Misc
        add('Footer',        fontSize=7,   textColor=C_MUTED,   alignment=TA_CENTER, spaceBefore=6, leading=9)
        add('Notes',         fontSize=7.5, textColor=C_MUTED,   alignment=TA_LEFT,  leading=10)
        add('NotesBold',     fontSize=7.5, textColor=C_BLACK,   fontName='Helvetica-Bold', alignment=TA_LEFT, leading=10)

    # ── Helpers ─────────────────────────────────────────────────────────────────
    def fmt(self, v):
        return f"{CURRENCY_SYMBOL} {v:,.2f}"

    def _section_hdr(self, text, bg=C_HEADER_BG, width=LEFT_COL):
        t = Table([[Paragraph(f"  {text}", self.styles['SecHdr'])]], colWidths=[width])
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), bg),
            ('TOPPADDING',   (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',(0,0), (-1,-1), 5),
            ('LEFTPADDING',  (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ]))
        return t

    def _table_style(self, n_rows, stripe=True, box_color=C_BORDER, last_total=True):
        cmds = [
            ('BOX',          (0,0), (-1,-1), 0.75, box_color),
            ('INNERGRID',    (0,0), (-1,-1), 0.3,  C_BORDER),
            ('TOPPADDING',   (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',(0,0), (-1,-1), 5),
            ('LEFTPADDING',  (0,0), (-1,-1), 7),
            ('RIGHTPADDING', (0,0), (-1,-1), 7),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ]
        if stripe:
            for r in range(0, n_rows - (1 if last_total else 0), 2):
                cmds.append(('BACKGROUND', (0,r), (-1,r), C_LIGHT_BG))
            for r in range(1, n_rows - (1 if last_total else 0), 2):
                cmds.append(('BACKGROUND', (0,r), (-1,r), C_STRIPE))
        if last_total and n_rows > 0:
            cmds += [
                ('BACKGROUND',   (0, n_rows-1), (-1, n_rows-1), C_TOTAL_BG),
                ('LINEABOVE',    (0, n_rows-1), (-1, n_rows-1), 0.75, box_color),
            ]
        return TableStyle(cmds)

    def _logo(self):
        if self.company and hasattr(self.company, 'logo_path') and \
                self.company.logo_path and os.path.exists(self.company.logo_path):
            try:
                img = Image(self.company.logo_path)
                aspect = img.imageHeight / float(img.imageWidth)
                w = 0.75 * inch
                img.drawWidth  = w
                img.drawHeight = w * aspect
                return img
            except Exception:
                pass
        return None

    # ── Main builder ────────────────────────────────────────────────────────────
    def generate_pay_stub(self, staff, payment, attendance_data, advances):
        S = self.styles
        elements = []

        company_name = (self.company.name if self.company else "Your Company")
        logo = self._logo()

        # ── HEADER BAND ─────────────────────────────────────────────────────────
        # Left: logo + title block  |  Right: employee info card
        # -----------------------------------------------------------------------
        HEADER_LEFT_W  = USABLE_W * 0.42
        HEADER_RIGHT_W = USABLE_W * 0.58

        # Title column
        title_rows = []
        if logo:
            title_rows.append([logo])
        title_rows.append([Paragraph(TITLE, S['DocTitle'])])
        title_rows.append([Paragraph(
            f"Salary Slip &mdash; {payment.get('month_name','')} {payment.get('year','')}",
            S['DocSubTitle']
        )])
        title_rows.append([Paragraph(company_name, S['CompanyName'])])

        title_tbl = Table(title_rows, colWidths=[HEADER_LEFT_W])
        title_tbl.setStyle(TableStyle([
            ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',  (0,0), (-1,-1), 2),
            ('BOTTOMPADDING',(0,0), (-1,-1), 2),
        ]))

        # Employee info column — two sub-columns: label | value
        EMP_LBL = HEADER_RIGHT_W * 0.40
        EMP_VAL = HEADER_RIGHT_W * 0.60

        emp_fields = [
            ("Employee Name",  staff.name),
            ("Designation",    staff.designation or "N/A"),
            ("Employee ID",    f"EMP-{staff.id:04d}"),
            ("Pay Period",     f"{payment.get('month_name','')} {payment.get('year','')}"),
            ("Payment Date",   payment.get('payment_date', 'N/A')),
            ("Payment Mode",   payment.get('payment_method', 'Cash')),
        ]
        emp_data = [
            [Paragraph(lbl, S['EmpLabel']), Paragraph(val, S['EmpValue'])]
            for lbl, val in emp_fields
        ]

        emp_tbl = Table(emp_data, colWidths=[EMP_LBL, EMP_VAL])
        emp_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), C_LIGHT_BG),
            ('BOX',           (0,0), (-1,-1), 0.75, C_BORDER),
            ('INNERGRID',     (0,0), (-1,-1), 0.3,  C_BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            # Alternate stripe
            *[('BACKGROUND', (0,r), (-1,r), C_STRIPE) for r in range(1, len(emp_data), 2)],
            # Name row highlight
            ('BACKGROUND',    (0,0), (-1,0), C_PRIMARY),
            ('TEXTCOLOR',     (0,0), (-1,0), C_WHITE),
        ]))
        # Override name style for white bg
        emp_data[0] = [
            Paragraph(emp_fields[0][0], ParagraphStyle('_', parent=S['EmpLabel'], textColor=colors.HexColor("#CBD5E8"))),
            Paragraph(emp_fields[0][1], ParagraphStyle('_', parent=S['EmpValue'], textColor=C_WHITE, fontSize=10)),
        ]
        # Rebuild with corrected first row
        emp_tbl_final = Table(emp_data, colWidths=[EMP_LBL, EMP_VAL])
        emp_tbl_final.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), C_LIGHT_BG),
            ('BOX',           (0,0), (-1,-1), 0.75, C_BORDER),
            ('INNERGRID',     (0,0), (-1,-1), 0.3,  C_BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            *[('BACKGROUND', (0,r), (-1,r), C_STRIPE) for r in range(1, len(emp_data), 2)],
            ('BACKGROUND',    (0,0), (-1,0), C_PRIMARY),
        ]))

        header_row = Table(
            [[title_tbl, emp_tbl_final]],
            colWidths=[HEADER_LEFT_W, HEADER_RIGHT_W]
        )
        header_row.setStyle(TableStyle([
            ('VALIGN',  (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',   (0,0), (-1,-1), 0),
            ('BOTTOMPADDING',(0,0), (-1,-1), 0),
        ]))

        elements.append(header_row)
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(
            width="100%", thickness=1.5, color=C_PRIMARY,
            spaceAfter=10, spaceBefore=2
        ))

        # ── BODY: two columns ───────────────────────────────────────────────────
        #   LEFT  col: Earnings + Deductions + Net Pay
        #   RIGHT col: Attendance (if present) + Summary badge
        # -----------------------------------------------------------------------

        # ── EARNINGS TABLE ──────────────────────────────────────────────────────
        base_sal = payment.get('base_salary', 0)
        bonus    = payment.get('bonus', 0)
        total_earn = base_sal + bonus

        earn_rows = []
        earn_rows.append([
            Paragraph("Base Monthly Salary", S['RowLabel']),
            Paragraph(self.fmt(base_sal), S['RowValue'])
        ])
        if bonus > 0:
            earn_rows.append([
                Paragraph("Bonus / Allowance", S['RowLabel']),
                Paragraph(f"+{self.fmt(bonus)}", S['RowValPos'])
            ])
        earn_rows.append([
            Paragraph("Total Earnings", S['TotLabel']),
            Paragraph(self.fmt(total_earn), S['TotValue'])
        ])

        earn_tbl = Table(earn_rows, colWidths=[LBL_W, VAL_W])
        earn_tbl.setStyle(self._table_style(len(earn_rows)))

        # ── DEDUCTIONS TABLE ────────────────────────────────────────────────────
        adv_ded   = payment.get('advance_deduction', 0)
        other_ded = payment.get('other_deductions', 0)
        total_ded = adv_ded + other_ded

        ded_rows = []
        if adv_ded > 0:
            ded_rows.append([
                Paragraph("Advance Deduction", S['RowLabel']),
                Paragraph(f"-{self.fmt(adv_ded)}", S['RowValNeg'])
            ])
        if other_ded > 0:
            ded_rows.append([
                Paragraph("Other Deductions", S['RowLabel']),
                Paragraph(f"-{self.fmt(other_ded)}", S['RowValNeg'])
            ])
        if not ded_rows:
            ded_rows.append([
                Paragraph("No Deductions Applied", S['RowLabel']),
                Paragraph("—", S['RowValue'])
            ])
        ded_rows.append([
            Paragraph("Total Deductions", S['TotLabel']),
            Paragraph(f"-{self.fmt(total_ded)}", S['RowValNeg'] if total_ded else S['TotValue'])
        ])

        ded_tbl = Table(ded_rows, colWidths=[LBL_W, VAL_W])
        ded_tbl.setStyle(self._table_style(len(ded_rows)))

        # ── NET PAY BOX ─────────────────────────────────────────────────────────
        net_salary = total_earn - total_ded
        net_tbl = Table(
            [[Paragraph("NET SALARY PAYABLE", S['NetLabel']),
              Paragraph(self.fmt(net_salary),  S['NetValue'])]],
            colWidths=[LBL_W, VAL_W]
        )
        net_tbl.setStyle(TableStyle([
            ('BOX',          (0,0), (-1,-1), 1.5, C_NET_BORDER),
            ('BACKGROUND',   (0,0), (-1,-1), C_NET_BG),
            ('TOPPADDING',   (0,0), (-1,-1), 9),
            ('BOTTOMPADDING',(0,0), (-1,-1), 9),
            ('LEFTPADDING',  (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ]))

        # Left column assembly
        left_col_data = [
            [self._section_hdr("SALARY EARNINGS", C_PRIMARY, LEFT_COL)],
            [earn_tbl],
            [Spacer(1, 6)],
            [self._section_hdr("DEDUCTIONS", C_DANGER, LEFT_COL)],
            [ded_tbl],
            [Spacer(1, 6)],
            [net_tbl],
        ]
        left_col_tbl = Table(left_col_data, colWidths=[LEFT_COL])
        left_col_tbl.setStyle(TableStyle([
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',   (0,0), (-1,-1), 0),
            ('BOTTOMPADDING',(0,0), (-1,-1), 0),
        ]))

        # ── RIGHT COLUMN ────────────────────────────────────────────────────────
        right_parts = []

        has_att = attendance_data.get('total_hours', 0) > 0
        if has_att:
            att_rows = [
                [Paragraph("Total Hours Worked",  S['RowLabel']),
                 Paragraph(f"{attendance_data.get('total_hours',0):.1f} hrs", S['RowValue'])],
                [Paragraph("Days Present",         S['RowLabel']),
                 Paragraph(str(attendance_data.get('days_worked',0)), S['RowValue'])],
                [Paragraph("Hourly Rate",           S['RowLabel']),
                 Paragraph(self.fmt(attendance_data.get('hourly_rate',0)), S['RowValue'])],
            ]
            hourly_earn = attendance_data.get('hourly_earnings', 0)
            if hourly_earn > 0:
                att_rows.append([
                    Paragraph("Extra / Overtime Earnings", S['TotLabel']),
                    Paragraph(self.fmt(hourly_earn), S['RowValPos'])
                ])

            att_tbl = Table(att_rows, colWidths=[RLBL_W, RVAL_W])
            att_tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), C_ATT_BG),
                ('BOX',           (0,0), (-1,-1), 0.75, C_ATT_HEAD),
                ('INNERGRID',     (0,0), (-1,-1), 0.3,  colors.HexColor("#B3D4EC")),
                ('TOPPADDING',    (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING',   (0,0), (-1,-1), 7),
                ('RIGHTPADDING',  (0,0), (-1,-1), 7),
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
                *([('BACKGROUND', (0, len(att_rows)-1), (-1, len(att_rows)-1), colors.HexColor("#D0E8F5"))]
                  if hourly_earn > 0 else []),
            ]))

            right_parts += [
                [self._section_hdr("ATTENDANCE DETAILS", C_ATT_HEAD, RIGHT_COL)],
                [att_tbl],
                [Spacer(1, 6)],
            ]

        # Summary card
        summary_data = [
            [Paragraph("Gross Earnings",  S['RowLabel']),  Paragraph(self.fmt(total_earn), S['RowValPos'])],
            [Paragraph("Total Deductions",S['RowLabel']),  Paragraph(f"-{self.fmt(total_ded)}", S['RowValNeg'])],
            [Paragraph("Net Payable",     S['TotLabel']),  Paragraph(self.fmt(net_salary), S['NetValue'])],
        ]
        sum_tbl = Table(summary_data, colWidths=[RLBL_W, RVAL_W])
        sum_tbl.setStyle(TableStyle([
            ('BOX',          (0,0), (-1,-1), 1.0, C_NET_BORDER),
            ('INNERGRID',    (0,0), (-1,-1), 0.4, colors.HexColor("#F5C99A")),
            ('BACKGROUND',   (0,0), (-1, 1), C_NET_BG),
            ('BACKGROUND',   (0,2), (-1,2),  colors.HexColor("#FFE0B2")),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ]))

        right_parts += [
            [self._section_hdr("PAYMENT SUMMARY", C_AMBER, RIGHT_COL)],
            [sum_tbl],
        ]

        right_col_tbl = Table(right_parts, colWidths=[RIGHT_COL])
        right_col_tbl.setStyle(TableStyle([
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',   (0,0), (-1,-1), 0),
            ('BOTTOMPADDING',(0,0), (-1,-1), 0),
        ]))

        # ── BODY ROW ────────────────────────────────────────────────────────────
        body_row = Table(
            [[left_col_tbl, Spacer(GAP_COL, 1), right_col_tbl]],
            colWidths=[LEFT_COL, GAP_COL, RIGHT_COL]
        )
        body_row.setStyle(TableStyle([
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',   (0,0), (-1,-1), 0),
            ('BOTTOMPADDING',(0,0), (-1,-1), 0),
        ]))
        elements.append(body_row)

        # ── NOTES ───────────────────────────────────────────────────────────────
        if payment.get('notes'):
            elements.append(Spacer(1, 10))
            note_tbl = Table([[
                Paragraph("Notes:", S['NotesBold']),
                Paragraph(payment.get('notes', ''), S['Notes'])
            ]], colWidths=[0.55*inch, USABLE_W - 0.55*inch])
            note_tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), C_LIGHT_BG),
                ('BOX',           (0,0), (-1,-1), 0.5, C_BORDER),
                ('TOPPADDING',    (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 8),
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ]))
            elements.append(note_tbl)

        # ── FOOTER ──────────────────────────────────────────────────────────────
        elements.append(Spacer(1, 14))
        elements.append(HRFlowable(
            width="100%", thickness=0.6, color=C_BORDER,
            spaceAfter=6, spaceBefore=0
        ))
        elements.append(Paragraph(FOOTER_MESSAGE, S['Footer']))

        self.doc.build(elements)

    # ── Entry points ────────────────────────────────────────────────────────────
    def generate_stub_from_payment(self, staff, payment, attendance_data=None, advances=None):
        if attendance_data is None:
            attendance_data = {'total_hours': 0, 'days_worked': 0, 'hourly_rate': 0, 'hourly_earnings': 0}
        if advances is None:
            advances = []

        MONTHS = ['', 'January','February','March','April','May','June',
                  'July','August','September','October','November','December']

        pay_data = {
            'base_salary':       payment.base_salary,
            'advance_deduction': payment.advance_deduction,
            'bonus':             payment.bonus,
            'other_deductions':  payment.other_deductions,
            'payment_date':      payment.payment_date.strftime('%d %b %Y') if payment.payment_date else 'N/A',
            'payment_method':    payment.payment_method,
            'month_name':        MONTHS[payment.month] if 1 <= payment.month <= 12 else '',
            'year':              payment.year,
            'notes':             payment.notes or '',
        }
        self.generate_pay_stub(staff, pay_data, attendance_data, advances)
        self.buffer.seek(0)
        return self.buffer


# ─── Public helpers ─────────────────────────────────────────────────────────────

def generate_pay_stub_pdf(staff, payment, attendance_data=None, advances=None):
    buffer = io.BytesIO()
    generator = PayStubPDFGenerator(buffer, company=None)
    return generator.generate_stub_from_payment(staff, payment, attendance_data, advances)


def generate_pay_stub_pdf_with_company(staff, payment, company, attendance_data=None, advances=None):
    buffer = io.BytesIO()
    generator = PayStubPDFGenerator(buffer, company=company)
    return generator.generate_stub_from_payment(staff, payment, attendance_data, advances)