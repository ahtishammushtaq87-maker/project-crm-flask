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

    NCOLS = 17
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
    headers = ['SKU', 'ITEM NAME', 'QTY', 'BOM COST / UNIT', 'LABOR COST / UNIT', 'OVERHEAD / UNIT',
               'TOTAL MFG COST / UNIT', 'SELLING PRICE / UNIT', 'MARGIN / UNIT',
               'MARGIN %', 'TOTAL BOM', 'TOTAL LABOR', 'TOTAL OVERHEAD', 'TOTAL MFG COST',
               'TOTAL SALES VALUE', 'TOTAL MARGIN', 'MARGIN STATUS']
    for col, h in enumerate(headers, start=1):
        set_cell(header_row, col, h, bold=True, fill=DARK, align='center')

    def data_row(r, row, bold=False):
        fill = LIGHT_GRAY if bold else None
        set_cell(r, 1, row['sku'] if 'sku' in row else 'TOTAL', bold=bold, fill=fill)
        set_cell(r, 2, row.get('name', 'WEIGHTED AVERAGE'), bold=bold, fill=fill)
        set_cell(r, 3, row['qty'], bold=bold, fmt=int_fmt, fill=fill, align='right')
        set_cell(r, 4, row['bom_cost_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 5, row['labor_cost_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 6, row['overhead_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 7, row['mfg_cost_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 8, row['selling_price'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 9, row['margin_unit'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 10, row['margin_pct'], bold=bold, fmt=pct_fmt, fill=fill, align='right')
        set_cell(r, 11, row['total_bom'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 12, row['total_labor'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 13, row['total_overhead'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 14, row['total_mfg_cost'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 15, row['total_sales'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 16, row['total_margin'], bold=bold, fmt=money_fmt, fill=fill, align='right')
        set_cell(r, 17, row['status'], bold=True, fill=fill,
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
            f"factory overhead of PKR {fs['expected_overhead']:,.2f} for {fs['month_label']}. Labor Cost/Unit "
            "uses the actual HR-staffed Manufacturing Order cost for that SKU this month when one exists, "
            "falling back to the BOM's estimated per-unit labor cost otherwise. Margin shown is manufacturing "
            "margin before sales/admin expenses, discounts, freight, warranty, bad debt, taxes, and financing costs.")
    c = ws.cell(row=note_row, column=1, value=note)
    c.font = Font(italic=True, size=9, color='FF6C757D')
    c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=NCOLS)
    ws.row_dimensions[note_row].height = 30

    # Column widths
    widths = [12, 42, 8, 14, 14, 13, 16, 15, 13, 10, 14, 14, 14, 15, 16, 14, 16]
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


def generate_manufacturing_fact_sheet_pdf(fs, company_info=None, audience='admin'):
    """Manufacturing Performance Report PDF - mirrors the on-screen page
    (app/templates/reports/manufacturing_report.html): production KPI cards,
    expected-vs-actual profit boxes, labour cost totals, the Target vs
    Achieved by Product table, and the Labour Cost by Staff table.

    audience:
      'admin' - everything, including every money figure.
      'staff' - production copy: quantities, completion % and staff
                assignments only. Every monetary figure (revenue, cost,
                profit, labour cost) is omitted entirely - not blanked out,
                but dropped from the layout - so the sheet can be handed to
                production staff without exposing financials.
    """
    staff_copy = (audience == 'staff')
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

    elements.append(Paragraph(f"MANUFACTURING PERFORMANCE REPORT &mdash; {fs['month_label']}", title_style))
    elements.append(Paragraph(
        'PRODUCTION COPY &mdash; quantities and staff assignments only' if staff_copy
        else 'MANAGEMENT COPY &mdash; full costing and profitability',
        sub_style))
    elements.append(Spacer(1, 0.18 * inch))

    def money(n):
        return f"PKR {n:,.2f}"

    perf = fs['performance_totals']
    label_style = ParagraphStyle('lbl', parent=styles['Normal'], fontSize=9, textColor=MUTED)
    value_style = ParagraphStyle('val', parent=styles['Normal'], fontSize=10.5, fontName='Helvetica-Bold')
    box_title_style = ParagraphStyle('boxTitle', parent=styles['Normal'], fontSize=9.5,
                                      fontName='Helvetica-Bold', textColor=colors.white)
    kpi_cap_style = ParagraphStyle('kpiCap', parent=styles['Normal'], fontSize=7.5,
                                    alignment=1, textColor=MUTED, fontName='Helvetica-Bold')
    hdr_style = ParagraphStyle('hdr', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold',
                                alignment=1, textColor=colors.whitesmoke)
    cell_style = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7.5, alignment=1)
    name_style = ParagraphStyle('name', parent=styles['Normal'], fontSize=7, alignment=0)
    sec_style = ParagraphStyle('sec', parent=styles['Normal'], fontSize=10,
                                fontName='Helvetica-Bold', textColor=HEAD_BG)

    # ── KPI cards: production quantities (safe for both audiences) ──────────
    def kpi_card(caption, value, value_color):
        v_style = ParagraphStyle(f'kpi{caption}', parent=styles['Normal'], fontSize=14,
                                  alignment=1, fontName='Helvetica-Bold', textColor=value_color)
        card = Table([[Paragraph(caption.upper(), kpi_cap_style)], [Paragraph(value, v_style)]])
        card.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.6, LINE),
            ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return card

    completion = perf['completion_pct']
    comp_color = GREEN if completion >= 100 else (AMBER if completion >= 70 else RED)
    kpis = [
        kpi_card('Target Production', f"{perf['target_units']:,.0f}", colors.black),
        kpi_card('Actual Production', f"{perf['produced_units']:,.0f}", HEAD_BG),
        kpi_card('Completion', f"{completion:.1f}%", comp_color),
        kpi_card('Shortfall', f"{perf['remaining']:,.0f}", RED if perf['remaining'] > 0 else GREEN),
    ]
    gap = doc.width * 0.02
    card_w = (doc.width - gap * 3) / 4
    kpi_row = Table([[kpis[0], '', kpis[1], '', kpis[2], '', kpis[3]]],
                    colWidths=[card_w, gap, card_w, gap, card_w, gap, card_w])
    kpi_row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(kpi_row)
    elements.append(Spacer(1, 0.25 * inch))

    def info_box(title, rows, width_fraction=0.47):
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
        t = Table(data, colWidths=[doc.width * width_fraction * 0.62,
                                    doc.width * width_fraction * 0.38])
        t.setStyle(TableStyle(cmds))
        return t

    # ── Financial sections: management copy only ───────────────────────────
    if not staff_copy:
        expected = info_box('EXPECTED PROFIT - IF FULL TARGET IS MET', [
            ('Target Revenue', money(perf['target_revenue'])),
            ('Estimated Cost', money(perf['estimated_cost'])),
            ('Expected Profit', money(perf['estimated_profit'])),
        ])
        actual = info_box('ACTUAL PROFIT - FROM REAL PRODUCTION SO FAR', [
            ('Actual Revenue', money(perf['actual_revenue'])),
            ('Actual Cost', money(perf['actual_cost'])),
            ('Actual Profit', money(perf['actual_profit'])),
        ])
        boxes = Table([[expected, '', actual]],
                       colWidths=[doc.width * 0.47, doc.width * 0.06, doc.width * 0.47])
        boxes.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        elements.append(boxes)
        elements.append(Spacer(1, 0.22 * inch))

        sl = fs['staff_labor_totals']
        labour = info_box('LABOUR COST SUMMARY', [
            ('Labour Cost (Produced)', money(sl['labor_cost_produced'])),
            ('Labour Cost (Remaining Produced)', money(sl['labor_cost_remaining'])),
            ('Total Labour Cost', money(sl['labor_cost_total'])),
        ], width_fraction=0.47)
        assumptions = info_box('COSTING ASSUMPTIONS', [
            ('Expected Labour + Factory Overhead', money(fs['expected_overhead'])),
            ('Target Manufacturing Margin', f"{fs['target_margin'] * 100:.1f}%"),
            ('Overhead Loading Rate on BOM', f"{fs['overhead_loading_rate'] * 100:.1f}%"),
        ], width_fraction=0.47)
        boxes2 = Table([[labour, '', assumptions]],
                        colWidths=[doc.width * 0.47, doc.width * 0.06, doc.width * 0.47])
        boxes2.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        elements.append(boxes2)
        elements.append(Spacer(1, 0.25 * inch))

    def build_table(headers, body_rows, col_weights, total_row_index=None):
        data = [[Paragraph(h, hdr_style) for h in headers]] + body_rows
        weight_total = sum(col_weights)
        widths = [doc.width * w / weight_total for w in col_weights]
        t = Table(data, colWidths=widths, repeatRows=1)
        cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('GRID', (0, 0), (-1, -1), 0.4, LINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        if total_row_index is not None:
            cmds.append(('BACKGROUND', (0, total_row_index), (-1, total_row_index), GRAY_BG))
        t.setStyle(TableStyle(cmds))
        return t

    # ── Target vs Achieved by Product ──────────────────────────────────────
    elements.append(Paragraph(f"TARGET VS ACHIEVED BY PRODUCT &mdash; {fs['month_label']}", sec_style))
    elements.append(Spacer(1, 0.08 * inch))

    if staff_copy:
        headers = ['SKU', 'Item Name', 'Target', 'Produced', 'Remaining', 'Completion %', 'Result']
        weights = [0.10, 0.40, 0.09, 0.09, 0.09, 0.11, 0.12]
    else:
        headers = ['SKU', 'Item Name', 'Target', 'Produced', 'Remaining', 'Completion %',
                   'Expected Profit', 'Actual Profit', 'Result']
        weights = [0.08, 0.26, 0.07, 0.07, 0.08, 0.10, 0.12, 0.12, 0.10]

    body = []
    for r in fs['performance_rows']:
        res_color = GREEN if r['achieved'] else RED
        res_style = ParagraphStyle(f"res{len(body)}", parent=cell_style,
                                    textColor=res_color, fontName='Helvetica-Bold')
        cells = [
            Paragraph(str(r['product'].sku or ''), cell_style),
            Paragraph(str(r['product'].name or ''), name_style),
            Paragraph(f"{r['target_units']:,.0f}", cell_style),
            Paragraph(f"{r['produced_units']:,.0f}", cell_style),
            Paragraph(f"{r['remaining']:,.0f}", cell_style),
            Paragraph(f"{r['completion_pct']:.1f}%", cell_style),
        ]
        if not staff_copy:
            cells.append(Paragraph(money(r['estimated_profit']), cell_style))
            cells.append(Paragraph(money(r['actual_profit']), cell_style))
        cells.append(Paragraph('ACHIEVED' if r['achieved'] else 'NOT ACHIEVED', res_style))
        body.append(cells)

    if not body:
        span = len(headers)
        body.append([Paragraph(f"No production targets found for {fs['month_label']}.",
                                ParagraphStyle('empty', parent=cell_style, textColor=MUTED))] +
                     [''] * (span - 1))

    elements.append(build_table(headers, body, weights))
    elements.append(Spacer(1, 0.28 * inch))

    # ── Staff breakdown ────────────────────────────────────────────────────
    elements.append(Paragraph(
        (f"STAFF PRODUCTION ASSIGNMENT &mdash; {fs['month_label']}" if staff_copy
         else f"LABOUR COST BY STAFF &mdash; {fs['month_label']}"), sec_style))
    elements.append(Spacer(1, 0.08 * inch))

    if staff_copy:
        s_headers = ['SKU', 'Item Name', 'Staff Name', 'Produced Qty', 'Remaining Qty']
        s_weights = [0.11, 0.42, 0.23, 0.12, 0.12]
    else:
        s_headers = ['SKU', 'Item Name', 'Staff Name', 'Produced Qty', 'Remaining Qty',
                     'Labour Cost (Produced)', 'Labour Cost (Remaining)', 'Total Labour Cost']
        s_weights = [0.08, 0.24, 0.16, 0.09, 0.09, 0.12, 0.12, 0.12]

    s_body = []
    for r in fs['staff_labor_rows']:
        staff_name = r['staff'].name or ''
        if r['staff'].designation:
            staff_name = f"{staff_name} ({r['staff'].designation})"
        cells = [
            Paragraph(str(r['product'].sku or ''), cell_style),
            Paragraph(str(r['product'].name or ''), name_style),
            Paragraph(staff_name, cell_style),
            Paragraph(f"{r['produced_qty']:,.0f}", cell_style),
            Paragraph(f"{r['remaining_qty']:,.0f}", cell_style),
        ]
        if not staff_copy:
            cells.append(Paragraph(money(r['labor_cost_produced']), cell_style))
            cells.append(Paragraph(money(r['labor_cost_remaining']), cell_style))
            cells.append(Paragraph(money(r['labor_cost_total']), cell_style))
        s_body.append(cells)

    total_idx = None
    if not s_body:
        s_body.append([Paragraph('No HR-staffed Manufacturing Orders found for this period.',
                                  ParagraphStyle('empty2', parent=cell_style, textColor=MUTED))] +
                       [''] * (len(s_headers) - 1))
    elif not staff_copy:
        bold_cell = ParagraphStyle('boldCell', parent=cell_style, fontName='Helvetica-Bold')
        sl = fs['staff_labor_totals']
        s_body.append([
            Paragraph('TOTAL', bold_cell), '', '', '', '',
            Paragraph(money(sl['labor_cost_produced']), bold_cell),
            Paragraph(money(sl['labor_cost_remaining']), bold_cell),
            Paragraph(money(sl['labor_cost_total']), bold_cell),
        ])
        total_idx = len(s_body)

    elements.append(build_table(s_headers, s_body, s_weights, total_row_index=total_idx))
    elements.append(Spacer(1, 0.2 * inch))

    if staff_copy:
        note = ("NOTE: This is the production copy of the monthly manufacturing report. It shows target "
                "vs actual production quantities and which staff worked on each product's orders. "
                "Costing, labour rates, revenue and profit figures are intentionally excluded. "
                "Produced/Remaining quantities are taken from each Manufacturing Order's own progress.")
    else:
        note = ("NOTE: Target combines the Production Target Tracker's manual target with the planned "
                "quantity of Manufacturing Orders started in the period. Produced is actual completed "
                "production for the SKU across all orders in the period. Labour cost per staff member "
                "comes from the order's HR 'Staff Used' assignment and is split between the quantity "
                "already produced and the quantity still remaining. Profit shown is manufacturing "
                "profit before sales/admin expenses, discounts, freight, warranty, taxes and financing costs.")
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
