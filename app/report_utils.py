import pandas as pd
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, legal, landscape
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

def generate_manufacturing_fact_sheet_excel(fs, company_name=None):
    """Manufacturing/Sales Fact Sheet workbook - replicates the layout of the
    manually-built monthly fact sheet: a merged title row, a two-box
    assumptions/summary header (matching app/templates/reports/manufacturing_report.html),
    then the per-SKU pricing/margin table with a weighted TOTAL row and
    colour-coded margin status, and a footnote.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    NAVY = 'FF3F51B5'
    LIGHT_GRAY = 'FFF1F3F5'
    WHITE = 'FFFFFFFF'
    GREEN = 'FF198754'
    AMBER = 'FFB8860B'
    RED = 'FFDC3545'
    DARK = 'FF212529'
    status_color = {'success': GREEN, 'warning': AMBER, 'danger': RED}

    wb = Workbook()
    ws = wb.active
    ws.title = 'Fact Sheet'

    NCOLS = 15
    thin = Side(style='thin', color='FFDDDDDD')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def set_cell(row, col, value, *, bold=False, fill=None, font_color=None, fmt=None,
                 align='left', size=11, italic=False):
        c = ws.cell(row=row, column=col, value=value)
        c.font = Font(bold=bold, italic=italic, size=size,
                       color=font_color or ('FFFFFFFF' if fill else 'FF212529'))
        if fill:
            c.fill = PatternFill('solid', fgColor=fill)
        if fmt:
            c.number_format = fmt
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=(align == 'wrap'))
        c.border = border
        return c

    # Title
    title = f"{(company_name or 'COMPANY').upper()} - {fs['month_label']} MANUFACTURING / SALES FACT SHEET"
    set_cell(1, 1, title, bold=True, size=14, align='center')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NCOLS)
    ws.row_dimensions[1].height = 26

    money_fmt = '#,##0.00'
    pct_fmt = '0.0%'
    int_fmt = '#,##0'

    # Assumptions box (A3:E7) and Summary box (G3:O7)
    set_cell(3, 1, 'FACT SHEET ASSUMPTIONS', bold=True, fill=NAVY, align='center')
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=2)
    set_cell(3, 7, f"{fs['month_label']} SUMMARY", bold=True, fill=NAVY, align='center')
    ws.merge_cells(start_row=3, start_column=7, end_row=3, end_column=8)

    assumption_rows = [
        ('Expected Labour + Factory Overhead', fs['expected_overhead'], money_fmt),
        ('Target Manufacturing Margin', fs['target_margin'], pct_fmt),
        ('Total Planned BOM / Material Cost', fs['total_planned_bom_cost'], money_fmt),
        ('Overhead Loading Rate on BOM', fs['overhead_loading_rate'], pct_fmt),
    ]
    for i, (label, value, fmt) in enumerate(assumption_rows):
        r = 4 + i
        fill = LIGHT_GRAY if i % 2 == 1 else None
        set_cell(r, 1, label, fill=fill, font_color='FF6C757D')
        set_cell(r, 2, value, bold=True, fmt=fmt, fill=fill, align='right')

    summary_rows = [
        ('Planned Units', fs['totals']['qty'], int_fmt),
        ('Total Manufacturing Cost', fs['total_mfg_cost'], money_fmt),
        ('Total Sales Value', fs['total_sales_value'], money_fmt),
        ('Overall Margin', fs['overall_margin_pct'], pct_fmt),
        ('Total Margin (PKR)', fs['total_margin_amt'], money_fmt),
        ('Target Margin', fs['target_margin'], pct_fmt),
    ]
    for i, (label, value, fmt) in enumerate(summary_rows):
        r = 4 + i
        fill = LIGHT_GRAY if i % 2 == 1 else None
        set_cell(r, 7, label, fill=fill, font_color='FF6C757D')
        set_cell(r, 8, value, bold=True, fmt=fmt, fill=fill, align='right')

    # Header row
    header_row = 10
    headers = ['SKU', 'ITEM NAME', 'QTY', 'BOM COST / UNIT', 'OVERHEAD / UNIT',
               'TOTAL MFG COST / UNIT', 'SELLING PRICE / UNIT', 'MARGIN / UNIT',
               'MARGIN %', 'TOTAL BOM', 'TOTAL OVERHEAD', 'TOTAL MFG COST',
               'TOTAL SALES VALUE', 'TOTAL MARGIN', 'MARGIN STATUS']
    for col, h in enumerate(headers, start=1):
        set_cell(header_row, col, h, bold=True, fill=DARK, align='center')

    def data_row(r, row, bold=False):
        fill = LIGHT_GRAY if bold else None
        set_cell(r, 1, row['sku'] if 'sku' in row else 'TOTAL', bold=bold, fill=fill)
        set_cell(r, 2, row.get('name', 'WEIGHTED AVERAGE'), bold=bold, fill=fill)
        set_cell(r, 3, row['qty'], bold=bold, fmt=int_fmt, fill=fill, align='right')
        set_cell(r, 4, row['bom_cost_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 5, row['overhead_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 6, row['mfg_cost_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 7, row['selling_price'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 8, row['margin_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 9, row['margin_pct'], bold=bold, fmt=pct_fmt, fill=fill, align='right')
        set_cell(r, 10, row['total_bom'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 11, row['total_overhead'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 12, row['total_mfg_cost'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 13, row['total_sales'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 14, row['total_margin'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 15, row['status'], bold=True, fill=fill,
                 font_color=status_color.get(row['status_class'], 'FF6C757D'), align='center')

    r = header_row + 1
    for row in fs['rows']:
        data_row(r, row)
        r += 1
    total_row_num = r
    data_row(total_row_num, dict(fs['totals'], sku='TOTAL', name='WEIGHTED AVERAGE'), bold=True)

    # Footnote
    note_row = total_row_num + 2
    note = (f"NOTE: Overhead is allocated proportionally to BOM/material cost using the expected labour + "
            f"factory overhead of PKR {fs['expected_overhead']:,.2f} for {fs['month_label']}. Margin shown is "
            "manufacturing margin before sales/admin expenses, discounts, freight, warranty, bad debt, taxes, "
            "and financing costs.")
    c = ws.cell(row=note_row, column=1, value=note)
    c.font = Font(italic=True, size=9, color='FF6C757D')
    c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=NCOLS)
    ws.row_dimensions[note_row].height = 30

    # Column widths
    widths = [12, 42, 8, 14, 13, 16, 15, 13, 10, 14, 14, 15, 16, 14, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    output = BytesIO()
    wb.save(output)
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


def generate_manufacturing_fact_sheet_pdf(fs, company_info=None):
    """Manufacturing/Sales Fact Sheet PDF - mirrors the on-screen page
    (app/templates/reports/manufacturing_report.html): an assumptions box
    and a summary box side by side, followed by the per-SKU pricing/margin
    table with a weighted TOTAL row and colour-coded margin status.
    """
    GREEN = colors.HexColor('#198754')
    RED = colors.HexColor('#dc3545')
    AMBER = colors.HexColor('#b8860b')
    MUTED = colors.HexColor('#6c757d')
    HEAD_BG = colors.HexColor('#3f51b5')
    GRAY_BG = colors.HexColor('#f1f3f5')
    LINE = colors.HexColor('#e0e0e0')

    status_color = {'success': GREEN, 'warning': AMBER, 'danger': RED}

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(legal),
                            rightMargin=24, leftMargin=24,
                            topMargin=24, bottomMargin=24)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('FSTitle', parent=styles['Heading1'], alignment=1, fontSize=15)
    sub_style = ParagraphStyle('FSSub', parent=styles['Normal'], alignment=1, textColor=MUTED)

    if company_info:
        elements.append(Paragraph(f"<b>{company_info.get('name', 'Company Report')}</b>",
                                   ParagraphStyle('co', parent=styles['Heading2'], alignment=1)))
        elements.append(Spacer(1, 0.05 * inch))

    elements.append(Paragraph(f"MANUFACTURING / SALES FACT SHEET &mdash; {fs['month_label']}", title_style))
    elements.append(Spacer(1, 0.15 * inch))

    def money(n):
        return f"{n:,.2f}"

    label_style = ParagraphStyle('lbl', parent=styles['Normal'], fontSize=9, textColor=MUTED)
    value_style = ParagraphStyle('val', parent=styles['Normal'], fontSize=10.5, fontName='Helvetica-Bold')
    box_title_style = ParagraphStyle('boxTitle', parent=styles['Normal'], fontSize=10,
                                      fontName='Helvetica-Bold', textColor=colors.white)

    def info_box(title, rows):
        data = [[Paragraph(title, box_title_style), '']]
        cmds = [
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('GRID', (0, 0), (-1, -1), 0.4, LINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]
        for r, (label, value) in enumerate(rows, start=1):
            data.append([Paragraph(label, label_style), Paragraph(value, value_style)])
            if r % 2 == 0:
                cmds.append(('BACKGROUND', (0, r), (-1, r), GRAY_BG))
        t = Table(data, colWidths=[doc.width * 0.47 * 0.62, doc.width * 0.47 * 0.38])
        t.setStyle(TableStyle(cmds))
        return t

    assumptions = info_box('FACT SHEET ASSUMPTIONS', [
        ('Expected Labour + Factory Overhead', money(fs['expected_overhead'])),
        ('Target Manufacturing Margin', f"{fs['target_margin'] * 100:.1f}%"),
        ('Total Planned BOM / Material Cost', money(fs['total_planned_bom_cost'])),
        ('Overhead Loading Rate on BOM', f"{fs['overhead_loading_rate'] * 100:.1f}%"),
    ])
    summary = info_box(f"{fs['month_label']} SUMMARY", [
        ('Planned Units', f"{fs['totals']['qty']:,.0f}"),
        ('Total Manufacturing Cost', money(fs['total_mfg_cost'])),
        ('Total Sales Value', money(fs['total_sales_value'])),
        ('Overall Margin', f"{fs['overall_margin_pct'] * 100:.1f}%"),
        ('Total Margin (PKR)', money(fs['total_margin_amt'])),
        ('Target Margin', f"{fs['target_margin'] * 100:.1f}%"),
    ])

    boxes = Table([[assumptions, '', summary]],
                   colWidths=[doc.width * 0.47, doc.width * 0.06, doc.width * 0.47])
    boxes.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(boxes)
    elements.append(Spacer(1, 0.25 * inch))

    # SKU table
    headers = ['SKU', 'Item Name', 'Qty', 'BOM/Unit', 'OH/Unit', 'Mfg Cost/Unit',
               'Sell Price/Unit', 'Margin/Unit', 'Margin %', 'Total Mfg Cost',
               'Total Sales', 'Total Margin', 'Status']
    hdr_style = ParagraphStyle('hdr', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold',
                                alignment=1, textColor=colors.whitesmoke)
    cell_style = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7.5, alignment=1)
    name_style = ParagraphStyle('name', parent=styles['Normal'], fontSize=7, alignment=0)

    rows = [[Paragraph(h, hdr_style) for h in headers]]
    row_cmds = []

    def add_data_row(r, bold=False):
        idx = len(rows)
        status_style = ParagraphStyle(f'status{idx}', parent=cell_style,
                                       textColor=status_color.get(r['status_class'], MUTED),
                                       fontName='Helvetica-Bold' if bold else 'Helvetica')
        base = ParagraphStyle(f'c{idx}', parent=cell_style,
                               fontName='Helvetica-Bold' if bold else 'Helvetica')
        nm_style = ParagraphStyle(f'n{idx}', parent=name_style,
                                   fontName='Helvetica-Bold' if bold else 'Helvetica')
        rows.append([
            Paragraph(str(r.get('sku', 'TOTAL')), base),
            Paragraph(str(r.get('name', 'WEIGHTED AVERAGE')), nm_style),
            Paragraph(f"{r['qty']:,.0f}", base),
            Paragraph(money(r['bom_cost_unit']), base),
            Paragraph(money(r['overhead_unit']), base),
            Paragraph(money(r['mfg_cost_unit']), base),
            Paragraph(money(r['selling_price']), base),
            Paragraph(money(r['margin_unit']), base),
            Paragraph(f"{r['margin_pct'] * 100:.1f}%", base),
            Paragraph(money(r['total_mfg_cost']), base),
            Paragraph(money(r['total_sales']), base),
            Paragraph(money(r['total_margin']), base),
            Paragraph(r['status'], status_style),
        ])
        if bold:
            row_cmds.append(('BACKGROUND', (0, idx), (-1, idx), GRAY_BG))

    for r in fs['rows']:
        add_data_row(r)
    add_data_row(fs['totals'], bold=True)

    # Normalize so the fractions always sum to exactly 1 - a raw sum > 1 here
    # previously made the table wider than the page and pushed the rightmost
    # columns (Total Sales / Total Margin / Status) off the printable area.
    col_weights = [0.07, 0.20, 0.05, 0.075, 0.075, 0.08, 0.08, 0.08, 0.06, 0.09, 0.09, 0.09, 0.07]
    weight_total = sum(col_weights)
    col_widths = [doc.width * w / weight_total for w in col_weights]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ] + row_cmds
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 0.2 * inch))

    note = ("NOTE: Overhead is allocated proportionally to BOM/material cost using the expected "
            f"labour + factory overhead of PKR {money(fs['expected_overhead'])} for {fs['month_label']}. "
            "Margin shown is manufacturing margin before sales/admin expenses, discounts, freight, "
            "warranty, bad debt, taxes, and financing costs.")
    elements.append(Paragraph(note, ParagraphStyle('note', parent=styles['Normal'], fontSize=7.5,
                                                     textColor=MUTED, fontName='Helvetica-Oblique')))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                               ParagraphStyle('gen', parent=styles['Normal'], fontSize=8, textColor=MUTED)))

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
