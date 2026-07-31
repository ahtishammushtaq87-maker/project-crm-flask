import pandas as pd
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import os

def generate_excel(data, sheet_name="Report"):
    """
    Generate Excel from a list of dictionaries.
    """
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output

def generate_csv(data):
    """
    Generate CSV from a list of dictionaries.
    """
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return output

def generate_pdf(data, title, headers, company_info=None):
    """
    Generate PDF from data list and headers.
    """
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(letter), 
                            rightMargin=30, leftMargin=30, 
                            topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header Style
    title_style = styles['Heading1']
    title_style.alignment = 1 # Center
    
    # Company Header
    if company_info:
        elements.append(Paragraph(f"<b>{company_info.get('name', 'Company Report')}</b>", title_style))
        elements.append(Paragraph(company_info.get('address', ''), styles['Normal']))
        elements.append(Paragraph(f"Phone: {company_info.get('phone', '')} | Email: {company_info.get('email', '')}", styles['Normal']))
        elements.append(Spacer(1, 0.2 * inch))
    
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Table Data
    hdr_style = ParagraphStyle(name='Hdr', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', alignment=1, textColor=colors.whitesmoke)
    cell_style = ParagraphStyle(name='Cell', parent=styles['Normal'], fontSize=9, alignment=1)
    
    table_data = [[Paragraph(str(h), hdr_style) for h in headers]]
    for row in data:
        table_data.append([Paragraph(str(row.get(h, '')), cell_style) for h in headers])
    
    # Create Table
    # Use variable column widths based on number of headers
    col_widths = [doc.width/len(headers)] * len(headers)
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Style Table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3f51b5")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ])
    t.setStyle(style)
    
    elements.append(t)
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    
    doc.build(elements)
    output.seek(0)
    return output


def generate_profit_loss_pdf(pl, start_date_str, end_date_str, company_info=None):
    """Financial-statement-style PDF for the Profit & Loss report.

    Mirrors the on-screen page (app/templates/reports/profit_loss.html)
    section-for-section: color-coded revenue/expense bands, a Net Profit
    Margin badge, and a Gross Profit vs Operating Expenses breakdown bar —
    so the download reads exactly like the screen instead of a flat table.
    """
    GREEN = colors.HexColor('#198754')
    RED = colors.HexColor('#dc3545')
    BLUE = colors.HexColor('#0d6efd')
    MUTED = colors.HexColor('#6c757d')
    GRAY_BG = colors.HexColor('#f1f3f5')
    INFO_BG = colors.HexColor('#d1ecf1')
    PRIMARY_BG = colors.HexColor('#cfe2ff')
    DARK_BG = colors.HexColor('#212529')
    LINE = colors.HexColor('#e9ecef')

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter,
                            rightMargin=36, leftMargin=36,
                            topMargin=32, bottomMargin=32)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('PLTitle', parent=styles['Heading1'], alignment=1, fontSize=16)
    sub_style = ParagraphStyle('PLSub', parent=styles['Normal'], alignment=1, textColor=MUTED)

    if company_info:
        elements.append(Paragraph(f"<b>{company_info.get('name', 'Company Report')}</b>",
                                   ParagraphStyle('co', parent=styles['Heading2'], alignment=1)))
        addr_bits = [b for b in [
            company_info.get('address'),
            f"Phone: {company_info.get('phone')}" if company_info.get('phone') else None,
            company_info.get('email'),
        ] if b]
        if addr_bits:
            elements.append(Paragraph(' | '.join(addr_bits),
                                       ParagraphStyle('co2', parent=styles['Normal'], alignment=1,
                                                      fontSize=9, textColor=MUTED)))
        elements.append(Spacer(1, 0.15 * inch))

    elements.append(Paragraph('PROFIT &amp; LOSS STATEMENT', title_style))
    elements.append(Paragraph(f"{start_date_str} to {end_date_str}", sub_style))
    elements.append(Spacer(1, 0.2 * inch))

    net_revenue = pl['net_revenue']
    net_profit = pl['net_profit']
    margin_pct = (net_profit / net_revenue * 100) if net_revenue else 0.0

    badge_label_style = ParagraphStyle('badgeLabel', parent=styles['Normal'], alignment=1,
                                        textColor=colors.white, fontSize=10)
    badge_value_style = ParagraphStyle('badgeValue', parent=styles['Normal'], alignment=1,
                                        textColor=colors.white, fontSize=22, fontName='Helvetica-Bold')
    badge = Table([
        [Paragraph('NET PROFIT MARGIN', badge_label_style)],
        [Paragraph(f"{margin_pct:,.1f}%", badge_value_style)],
    ], colWidths=[doc.width])
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLUE),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('TOPPADDING', (0, 1), (-1, 1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 14),
    ]))
    elements.append(badge)
    elements.append(Spacer(1, 0.25 * inch))

    def money(n):
        return f"{n:,.2f}"

    def money_paren(n):
        return f"({n:,.2f})"

    def money_signed(n):
        return f"{n:,.2f}" if n >= 0 else f"({abs(n):,.2f})"

    rows = [['Account Description', 'Amount (PKR)', 'Total (PKR)']]
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]

    def add_row(label, amount='', total='', *, bg=None, label_bold=False, amount_color=None,
                total_color=None, total_bold=False, italic=False, fontsize=None,
                merge=None, label_color=None):
        r = len(rows)
        rows.append([label, amount, total])
        if merge == 'label':
            cmds.append(('SPAN', (0, r), (1, r)))
        elif merge == 'full':
            cmds.append(('SPAN', (0, r), (2, r)))
        if bg:
            cmds.append(('BACKGROUND', (0, r), (-1, r), bg))
        if label_bold:
            cmds.append(('FONTNAME', (0, r), (0, r), 'Helvetica-Bold'))
        if total_bold:
            cmds.append(('FONTNAME', (2, r), (2, r), 'Helvetica-Bold'))
        if italic:
            cmds.append(('FONTNAME', (0, r), (0, r), 'Helvetica-Oblique'))
        if amount_color:
            cmds.append(('TEXTCOLOR', (1, r), (1, r), amount_color))
        if total_color:
            cmds.append(('TEXTCOLOR', (2, r), (2, r), total_color))
        if label_color:
            cmds.append(('TEXTCOLOR', (0, r), (0, r), label_color))
        if fontsize:
            cmds.append(('FONTSIZE', (0, r), (-1, r), fontsize))
        return r

    # Revenue
    add_row('REVENUE', total=money(pl['total_revenue']), bg=INFO_BG, label_bold=True,
            total_bold=True, merge='label')
    add_row('   Total Sales Invoices', amount=money(pl['total_revenue']), amount_color=GREEN)
    add_row('   Less: Sales Returns', amount=money_paren(pl['total_returns']), amount_color=RED)
    add_row('TOTAL NET REVENUE', total=money(net_revenue), label_bold=True, total_bold=True,
            total_color=BLUE, merge='label')

    add_row('')

    # COGS / Gross Profit
    add_row('COST OF GOODS SOLD (COGS)', total=money_paren(pl['total_cogs']), label_bold=True,
            total_bold=True, total_color=RED, merge='label')
    add_row('GROSS PROFIT', total=money(pl['gross_profit']), bg=PRIMARY_BG, label_bold=True,
            total_bold=True, fontsize=11, merge='label')

    add_row('')

    # Operating expenses
    add_row('OPERATING EXPENSES (DEDUCTED FROM PROFIT)', bg=GRAY_BG, label_bold=True, merge='full')

    if pl['expense_summary']:
        add_row('Simple / Daily Expenses', italic=True, label_color=MUTED, merge='full')
        for cat, amt in pl['expense_summary'].items():
            add_row(f'   {cat}', amount=money(amt))

    if pl['divided_expense_summary']:
        add_row('Salary / Divided Expenses (Prorated)', italic=True, label_color=MUTED, merge='full')
        for cat, amt in pl['divided_expense_summary'].items():
            add_row(f'   {cat}', amount=money(amt))

    add_row('Staff Payroll (Salaries & Advances)', amount=money(pl['total_payroll']))
    add_row('TOTAL OPERATING EXPENSES', total=money_paren(pl['total_operating_expenses']),
            label_bold=True, total_bold=True, total_color=RED, merge='label')

    add_row('')

    # Net profit
    add_row('NET PROFIT', total=money_signed(net_profit), bg=DARK_BG, label_bold=True,
            total_bold=True, label_color=colors.white,
            total_color=(GREEN if net_profit >= 0 else RED), fontsize=12, merge='label')

    add_row('')

    # Informational
    add_row('INVENTORY & MANUFACTURING ACTIVITY (INFORMATIONAL)', bg=GRAY_BG, label_bold=True, merge='full')
    add_row('Direct Inventory Purchases (Asset Investment)', amount=money(pl['total_purchases']))
    add_row('Manufacturing (BOM) Costs (In-process/Stock)',
            amount=money(pl['total_bom_costs'] + pl['total_bom_overhead']))
    add_row('TOTAL SECONDARY OUTFLOW', total=money(pl['total_informational_outflow']),
            label_bold=True, total_bold=True, total_color=MUTED, merge='label')

    footnote_style = ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5,
                                     textColor=MUTED, fontName='Helvetica-Oblique')
    r = len(rows)
    rows.append([Paragraph(
        'These costs are reflected in COGS at the time of sale and are not deducted again from Net Profit here.',
        footnote_style), '', ''])
    cmds.append(('SPAN', (0, r), (2, r)))

    col_widths = [doc.width * 0.5, doc.width * 0.25, doc.width * 0.25]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # Profit Breakdown bars (Gross Profit vs Operating Expenses)
    elements.append(Paragraph('<b>Profit Breakdown</b>', styles['Heading3']))
    elements.append(Spacer(1, 0.08 * inch))

    bar_width = doc.width
    max_val = max(pl['gross_profit'], pl['total_operating_expenses'], 1)

    def bar_row(label, value, color_):
        label_line = Table([[
            Paragraph(f"<b>{label}</b>", styles['Normal']),
            Paragraph(f"{value:,.0f}", ParagraphStyle('r', parent=styles['Normal'], alignment=2)),
        ]], colWidths=[bar_width * 0.5, bar_width * 0.5])
        label_line.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(label_line)

        frac = 0.0 if max_val == 0 else max(min(value / max_val, 1.0), 0.0)
        frac = min(max(frac, 0.02), 0.98)
        filled = bar_width * frac
        empty = bar_width - filled
        bar = Table([['', '']], colWidths=[filled, empty])
        bar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), color_),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#e9ecef')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(bar)
        elements.append(Spacer(1, 0.15 * inch))

    bar_row('Gross Profit', pl['gross_profit'], GREEN)
    bar_row('Operating Expenses', pl['total_operating_expenses'], RED)

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                               ParagraphStyle('gen', parent=styles['Normal'], fontSize=8, textColor=MUTED)))

    doc.build(elements)
    output.seek(0)
    return output
