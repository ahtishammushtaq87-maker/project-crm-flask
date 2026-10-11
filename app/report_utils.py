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

def _write_fact_sheet_costing(ws, fs, company_name=None):
    """'Costing & Margin' sheet of the Manufacturing Report workbook -
    replicates the layout of the manually-built monthly fact sheet: a merged
    title row, a two-box assumptions/summary header, then the per-SKU
    pricing/margin table with a weighted TOTAL row and colour-coded margin
    status, and a footnote.
    """
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


def generate_manufacturing_fact_sheet_excel(fs, company_name=None, mo_costs=None):
    """Kept for existing callers - see generate_manufacturing_report_excel."""
    return generate_manufacturing_report_excel(fs, mo_costs, company_name)


def generate_csv(data):
    """
    Generate CSV from a list of dictionaries.
    """
    df = pd.DataFrame(data)
    output = BytesIO()
    # utf-8-sig (with BOM) so Excel opens dashes, ×, Urdu text etc. correctly
    # instead of showing them as garbled characters.
    df.to_csv(output, index=False, encoding='utf-8-sig')
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
    
    # A single table row can't span pages, so cap very long cell text (e.g. a
    # long "Invoices Used" list) to keep every row shorter than one page.
    max_cell_chars = 300
    def _cell(value):
        text = str(value)
        if len(text) > max_cell_chars:
            text = text[:max_cell_chars].rstrip(', ') + ' …'
        return Paragraph(text, cell_style)

    table_data = [[Paragraph(str(h), hdr_style) for h in headers]]
    for row in data:
        table_data.append([_cell(row.get(h, '')) for h in headers])
    
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


def build_manufacturing_statement(fs, mo_costs=None, staff_copy=False):
    """Single source for every Manufacturing Report export (PDF / Excel / CSV).

    Returns the report as P&L-style statement blocks that mirror the on-screen
    page (app/templates/reports/manufacturing_report.html) section for section,
    so a download reads exactly like the screen:

        {'summary':  [block, ...],   # Production Performance + MO Cost summaries
         'products': [block, ...],   # one statement per product (target vs achieved + labor used)
         'orders':   [block, ...]}   # one statement per Manufacturing Order (material/labor/overhead)

    A block is {'title', 'subtitle', 'lines'}; each line is a dict with
    kind  - section | band | line | total | primary | grand | spacer | note
    label, amount, total - number or text; fmt - money | int | text;
    neg   - show the figure as a deduction, e.g. (1,234.00); color - green/red/amber/muted.

    staff_copy drops every money figure (revenue, cost, profit, labor cost)
    entirely, leaving the production quantities and staff assignments.
    """
    def L(kind, label='', amount=None, total=None, fmt='money', neg=False, color=None, total_color=None):
        return {'kind': kind, 'label': label, 'amount': amount, 'total': total, 'fmt': fmt,
                'neg': neg, 'color': color, 'total_color': total_color}

    def staff_label(staff):
        name = staff.name or ''
        return f"{name} ({staff.designation})" if staff.designation else name

    pt = fs['performance_totals']
    lt = fs['staff_labor_totals']
    month = fs['month_label']

    # ── Production Performance Summary ─────────────────────────────────────
    lines = [
        L('section', 'PRODUCTION (UNITS)', total=f"{pt['completion_pct']:.1f}% complete", fmt='text'),
        L('line', 'Target Production (units planned)', pt['target_units'], fmt='int'),
        L('line', 'Actual Production (units produced)', pt['produced_units'], fmt='int', color='green'),
        L('line', 'Less: Shortfall (units still short of target)', pt['remaining'], fmt='int', neg=True, color='red'),
        L('total', 'SKUs ACHIEVED / NOT ACHIEVED', total=f"{pt['achieved_count']} / {pt['not_achieved_count']}", fmt='text'),
    ]
    if not staff_copy:
        lines += [
            L('spacer'),
            L('band', 'EXPECTED PROFIT — IF FULL TARGET IS MET (PKR)'),
            L('line', 'Target Revenue', pt['target_revenue'], color='green'),
            L('line', 'Less: Estimated Cost', pt['estimated_cost'], neg=True, color='red'),
            L('primary', 'EXPECTED PROFIT', total=pt['estimated_profit']),
            L('spacer'),
            L('band', 'LABOR USED ACCORDING TO PRODUCTION (PKR)'),
            L('line', f"Labor Used on Produced Units ({pt['produced_units']:,.0f})", lt['labor_cost_produced'], color='green'),
            L('line', f"Labor Tied Up in Remaining Units ({pt['remaining']:,.0f})", lt['labor_cost_remaining'], color='amber'),
            L('total', 'TOTAL LABOR COST (HR-STAFFED ORDERS)', total=lt['labor_cost_total'], neg=True, total_color='red'),
            L('spacer'),
            L('band', 'ACTUAL PROFIT — FROM REAL PRODUCTION SO FAR (PKR)'),
            L('line', 'Actual Revenue', pt['actual_revenue'], color='green'),
            L('line', 'Less: Actual Cost', pt['actual_cost'], neg=True, color='red'),
            L('grand', 'ACTUAL PROFIT', total=pt['actual_profit']),
        ]
    summary = [{'title': f"PRODUCTION PERFORMANCE SUMMARY — {month}",
                'subtitle': ('Units planned vs. units produced this month.' if staff_copy else
                             'Target vs achieved this month, the profit each represents, and labor used according to production.'),
                'lines': lines}]

    # ── One statement per product ──────────────────────────────────────────
    products = []
    for r in fs['performance_rows']:
        p = r['product']
        staff_rows = [s for s in fs['staff_labor_rows'] if s['product'].id == p.id]
        lines = [
            L('section', 'PRODUCTION (UNITS)', total=f"{r['completion_pct']:.1f}% complete", fmt='text'),
            L('line', 'Target', r['target_units'], fmt='int'),
            L('line', 'Produced', r['produced_units'], fmt='int', color='green'),
            L('line', 'Remaining', r['remaining'], fmt='int', neg=True, color='red'),
        ]
        if staff_copy:
            lines += [L('spacer'), L('section', 'STAFF ON THIS PRODUCT (PRODUCED / REMAINING UNITS)')]
            lines += [L('line', staff_label(s['staff']),
                        f"{s['produced_qty']:,.0f} / {s['remaining_qty']:,.0f}", fmt='text')
                      for s in staff_rows] or [L('note', 'No HR-staffed Manufacturing Orders for this product this month.')]
        else:
            used = sum(s['labor_cost_produced'] for s in staff_rows)
            remaining = sum(s['labor_cost_remaining'] for s in staff_rows)
            lines += [
                L('spacer'),
                L('band', 'EXPECTED — FULL TARGET (PKR)'),
                L('line', 'Target Revenue', r['target_revenue'], color='green'),
                L('line', 'Less: Estimated Cost', r['estimated_cost'], neg=True, color='red'),
                L('primary', 'EXPECTED PROFIT', total=r['estimated_profit']),
                L('spacer'),
                L('section', 'LABOR USED ON PRODUCED UNITS (PKR)', total=used),
            ]
            lines += [L('line', f"{staff_label(s['staff'])} — {s['produced_qty']:,.0f} unit(s) produced",
                        s['labor_cost_produced']) for s in staff_rows] \
                or [L('note', 'No HR-staffed Manufacturing Orders for this product this month.')]
            if staff_rows:
                lines += [L('spacer'), L('section', 'LABOR TIED UP IN REMAINING UNITS (PKR)', total=remaining)]
                lines += [L('line', f"{staff_label(s['staff'])} — {s['remaining_qty']:,.0f} unit(s) remaining",
                            s['labor_cost_remaining']) for s in staff_rows]
                lines.append(L('total', 'TOTAL LABOR COST', total=used + remaining, neg=True, total_color='red'))
            lines += [
                L('spacer'),
                L('band', 'ACTUAL — REAL PRODUCTION SO FAR (PKR)'),
                L('line', 'Actual Revenue', r['actual_revenue'], color='green'),
                L('line', 'Less: Actual Cost', r['actual_cost'], neg=True, color='red'),
                L('grand', 'ACTUAL PROFIT', total=r['actual_profit']),
            ]
        products.append({
            'title': f"{p.sku or ''} — {p.name or ''}",
            'subtitle': (f"{r['produced_units']:,.0f} of {r['target_units']:,.0f} units produced · "
                         f"{r['completion_pct']:.1f}% · {'ACHIEVED' if r['achieved'] else 'NOT ACHIEVED'}"),
            'achieved': r['achieved'],
            'lines': lines,
        })

    # ── Manufacturing Orders: cost summary + one statement per order ───────
    orders = []
    if mo_costs is not None:
        mt = mo_costs['totals']
        if not staff_copy:
            summary.append({
                'title': f"MANUFACTURING ORDER COST SUMMARY — {month}",
                'subtitle': 'Every material, labor and overhead cost charged to this month\'s Manufacturing Orders.',
                'lines': [
                    L('section', f"MANUFACTURING ORDERS ({len(mo_costs['rows'])})", total=f"{mt['qty']:,.0f} units", fmt='text'),
                    L('line', 'Units Planned', mt['qty'], fmt='int'),
                    L('line', 'Units Produced', mt['produced_qty'], fmt='int', color='green'),
                    L('spacer'),
                    L('band', 'COSTS CHARGED TO ORDERS (PKR)'),
                    L('line', 'Direct Material (BOM Components)', mt['material']),
                    L('line', 'Labor Cost (Staff Salary Allocation)', mt['labor']),
                    L('line', 'Factory Overhead Expenses', mt['overhead']),
                    L('line', 'Other Linked Costs', mt['other']),
                    L('total', 'TOTAL MANUFACTURING COST', total=mt['total'], neg=True, total_color='red'),
                    L('spacer'),
                    L('grand', 'AVERAGE COST PER UNIT', total=mt['cost_per_unit']),
                ],
            })

        for r in mo_costs['rows']:
            o = r['order']
            subtitle = (f"{o.status} · {r['produced_qty']:,.0f} of {r['qty']:,.0f} units produced · "
                        f"Start {o.start_date.strftime('%Y-%m-%d') if o.start_date else '-'} · "
                        f"End {o.end_date.strftime('%Y-%m-%d') if o.end_date else '-'} · "
                        f"BOM {o.bom.name if o.bom else '-'}")
            if staff_copy:
                lines = [
                    L('section', 'PRODUCTION (UNITS)'),
                    L('line', 'Planned', r['qty'], fmt='int'),
                    L('line', 'Produced', r['produced_qty'], fmt='int', color='green'),
                    L('line', 'Remaining', max(0, r['qty'] - r['produced_qty']), fmt='int', neg=True, color='red'),
                    L('spacer'),
                    L('section', 'COMPONENTS REQUIRED (QTY)'),
                ]
                lines += [L('line', f"{m['name']}" + (f" ({m['sku']})" if m['sku'] else ''), m['qty'], fmt='int')
                          for m in r['materials']] or [L('note', 'No components on this order.')]
                lines += [L('spacer'), L('section', 'STAFF ASSIGNED')]
                lines += [L('line', l['name'] + (f" ({l['designation']})" if l['designation'] else ''))
                          for l in r['labor']] or [L('note', 'No staff assigned.')]
            else:
                lines = [L('section', 'DIRECT MATERIAL', total=r['material_total'])]
                lines += [L('line', f"{m['name']}" + (f" ({m['sku']})" if m['sku'] else '') + f" × {m['qty']:,.2f}",
                            m['amount']) for m in r['materials']] or [L('note', 'No components on this order.')]

                lines += [L('spacer'), L('section', 'LABOR COST', total=r['labor_total'])]
                for l in r['labor']:
                    label = l['name'] + (f" ({l['designation']})" if l['designation'] else '')
                    if l['days']:
                        label += f" — {l['daily_rate']:,.2f}/day × {l['days']:g} days"
                    lines.append(L('line', label, l['amount']))
                if r['bom_labor_estimate']:
                    lines.append(L('line', 'BOM Labor Estimate (not allocated to staff)', r['bom_labor_estimate']))
                if not r['labor'] and not r['bom_labor_estimate']:
                    lines.append(L('note', 'No labor cost charged.'))

                def expense_lines(entries):
                    out = []
                    for e in entries:
                        label = e['category'] + (f" — {e['description']}" if e['description'] else '')
                        label += f" ({e['number'] or ''} {e['date'].strftime('%Y-%m-%d') if e['date'] else ''})".replace('( ', '(')
                        if e['status'] != 'confirmed':
                            label += f" [{e['status'].capitalize()}]"
                        out.append(L('line', label, e['amount']))
                    return out

                lines += [L('spacer'), L('section', 'FACTORY OVERHEAD EXPENSES', total=r['overhead_total'])]
                lines += expense_lines(r['overheads']) or [L('note', 'No overhead expenses linked to this order.')]
                if r['other_costs']:
                    lines += [L('spacer'), L('section', 'OTHER COSTS', total=r['other_total'])]
                    lines += expense_lines(r['other_costs'])

                lines += [
                    L('spacer'),
                    L('total', 'TOTAL ORDER COST', total=r['total'], neg=True, total_color='red'),
                    L('grand', f"COST PER UNIT ({r['qty']:,.0f} units)", total=r['cost_per_unit']),
                ]
                if r['batches']:
                    lines += [L('spacer'), L('band', 'PRODUCTION BATCHES (INFORMATIONAL)')]
                    for b in r['batches']:
                        lines.append(L('line',
                            f"{b.completion_date.strftime('%Y-%m-%d') if b.completion_date else '-'} — "
                            f"{b.quantity_produced:,.0f} unit(s) (Material {b.material_cost or 0:,.2f} · "
                            f"Labor {b.labor_cost or 0:,.2f} · Overhead {b.overhead_cost or 0:,.2f}"
                            f"{' manual' if b.is_manual_overhead else ''})",
                            b.total_cost or 0))
                    lines.append(L('note', 'Batch costs are what was booked into finished-goods cost at each '
                                           'completion and are not added again above.'))
            orders.append({
                'title': f"{o.order_number} — {r['product'].name if r['product'] else 'N/A'}",
                'subtitle': subtitle,
                'head_total': None if staff_copy else r['total'],
                'lines': lines,
            })

    return {'summary': summary, 'products': products, 'orders': orders}


def format_statement_value(value, fmt='money', neg=False):
    """Text for one statement figure: 1,234.00 / (1,234.00) / 1,234 / text."""
    if value is None or value == '':
        return ''
    if fmt == 'text' or isinstance(value, str):
        return str(value)
    pattern = '{:,.0f}' if fmt == 'int' else '{:,.2f}'
    if neg:
        return '(' + pattern.format(abs(value)) + ')'
    if value < 0:
        return '(' + pattern.format(abs(value)) + ')'
    return pattern.format(value)


def manufacturing_statement_csv_rows(fs, mo_costs=None, staff_copy=False):
    """Flat CSV rows (Section / Account Description / Amount / Total) of the
    same statements the PDF and Excel show, in the same order."""
    st = build_manufacturing_statement(fs, mo_costs, staff_copy)
    groups = [('', st['summary']), ('TARGET VS ACHIEVED BY PRODUCT', st['products']),
              ('MANUFACTURING ORDERS', st['orders'])]
    rows = []

    def row(section='', label='', amount='', total=''):
        rows.append({'Section': section, 'Account Description': label, 'Amount': amount, 'Total': total})

    for group_title, blocks in groups:
        if group_title and blocks:
            row(group_title)
        for b in blocks:
            row(b['title'], b.get('subtitle', ''))
            for ln in b['lines']:
                if ln['kind'] == 'spacer':
                    continue
                indent = '    ' if ln['kind'] == 'line' else ''
                row(b['title'], indent + ln['label'],
                    format_statement_value(ln['amount'], ln['fmt'], ln['neg']) if ln['kind'] != 'total' and ln['amount'] is not None else '',
                    format_statement_value(ln['total'], ln['fmt'], ln['neg']) if ln['total'] is not None else '')
            row()
    return rows


def _manufacturing_statement_excel_sheet(ws, blocks, heading=None, start_row=1):
    """Write statement blocks onto one worksheet in the P&L layout.
    Returns the next free row."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    NAVY, INFO, PRIMARY, DARK, LIGHT = 'FF3F51B5', 'FFD1ECF1', 'FFCFE2FF', 'FF212529', 'FFF1F3F5'
    COLORS = {'green': 'FF198754', 'red': 'FFDC3545', 'amber': 'FFB8860B', 'muted': 'FF6C757D'}
    money_fmt = '#,##0.00;(#,##0.00)'
    int_fmt = '#,##0;(#,##0)'
    thin = Side(style='thin', color='FFE0E0E0')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    top_bottom = Border(top=Side(style='thin', color='FF495057'), bottom=Side(style='double', color='FF495057'))

    ws.column_dimensions['A'].width = 78
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 22

    def put(r, c, value, fmt='money', neg=False, bold=False, italic=False, color=None, fill=None, align=None):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and fmt != 'text':
            value = -abs(value) if neg else value
        cell = ws.cell(row=r, column=c, value=value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cell.number_format = int_fmt if fmt == 'int' else money_fmt
            cell.alignment = Alignment(horizontal='right', vertical='center')
        else:
            cell.alignment = Alignment(horizontal=align or ('right' if c > 1 else 'left'),
                                       vertical='center', wrap_text=(c == 1))
        cell.font = Font(bold=bold, italic=italic, color=color or 'FF212529')
        if fill:
            cell.fill = PatternFill('solid', fgColor=fill)
        cell.border = border
        return cell

    r = start_row
    if heading:
        c = ws.cell(row=r, column=1, value=heading)
        c.font = Font(bold=True, size=14, color=NAVY)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        r += 2

    for b in blocks:
        # Block title bar (like the accordion header / card header)
        title = b['title']
        put(r, 1, title, bold=True, color='FFFFFFFF', fill=NAVY)
        head_total = b.get('head_total')
        put(r, 2, None, fill=NAVY)
        if head_total is not None:
            put(r, 3, head_total, bold=True, color='FFFFFFFF', fill=NAVY)
        else:
            put(r, 3, None, fill=NAVY)
        r += 1
        if b.get('subtitle'):
            put(r, 1, b['subtitle'], italic=True, color=COLORS['muted'])
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            r += 1
        for col, h in enumerate(['Account Description', 'Amount', 'Total'], start=1):
            put(r, col, h, bold=True, fill=LIGHT, align='left' if col == 1 else 'right')
        r += 1

        for ln in b['lines']:
            kind = ln['kind']
            color = COLORS.get(ln['color'])
            tcolor = COLORS.get(ln['total_color'])
            if kind == 'spacer':
                r += 1
                continue
            if kind == 'note':
                put(r, 1, ln['label'], italic=True, color=COLORS['muted'])
                ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            elif kind == 'band':
                put(r, 1, ln['label'].upper(), bold=True, fill=LIGHT)
                put(r, 2, None, fill=LIGHT)
                put(r, 3, None, fill=LIGHT)
            elif kind == 'line':
                put(r, 1, '    ' + ln['label'], color=COLORS['muted'])
                put(r, 2, ln['amount'], ln['fmt'], ln['neg'], color=color)
                put(r, 3, None)
            else:
                fill = {'section': INFO, 'primary': PRIMARY, 'grand': DARK}.get(kind)
                font_color = 'FFFFFFFF' if kind == 'grand' else None
                total = ln['total']
                if kind == 'grand' and isinstance(total, (int, float)):
                    tcolor = 'FF75D99B' if total >= 0 else 'FFFF8A95'
                put(r, 1, ln['label'], bold=True, fill=fill, color=font_color)
                put(r, 2, None, fill=fill)
                put(r, 3, total, ln['fmt'], ln['neg'], bold=True, fill=fill, color=tcolor or font_color)
                if kind == 'total':
                    for col in (1, 2, 3):
                        ws.cell(row=r, column=col).border = top_bottom
            r += 1
        r += 2
    return r


def generate_manufacturing_report_excel(fs, mo_costs=None, company_name=None):
    """Manufacturing Report workbook, laid out like the screen and the P&L:

      Summary                - Production Performance + MO Cost summaries
      By Product             - one statement per product (target vs achieved, labor used vs remaining)
      By Manufacturing Order - one statement per order (material, labor, overhead, other)
      Costing & Margin       - the per-SKU planned costing / margin fact sheet
    """
    from openpyxl import Workbook

    st = build_manufacturing_statement(fs, mo_costs)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Summary'
    company = (company_name or 'COMPANY').upper()
    _manufacturing_statement_excel_sheet(ws, st['summary'],
                                         heading=f"{company} — MANUFACTURING REPORT — {fs['month_label']}")

    ws_p = wb.create_sheet('By Product')
    if st['products']:
        _manufacturing_statement_excel_sheet(ws_p, st['products'],
                                             heading=f"TARGET VS ACHIEVED BY PRODUCT — {fs['month_label']}")
    else:
        ws_p['A1'] = f"No production targets found for {fs['month_label']}."

    ws_o = wb.create_sheet('By Manufacturing Order')
    if st['orders']:
        _manufacturing_statement_excel_sheet(ws_o, st['orders'],
                                             heading=f"MANUFACTURING ORDER COSTS — {fs['month_label']}")
    else:
        ws_o['A1'] = f"No Manufacturing Orders found for {fs['month_label']}."

    _write_fact_sheet_costing(wb.create_sheet('Costing & Margin'), fs, company_name)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def generate_manufacturing_fact_sheet_pdf(fs, company_info=None, audience='admin', mo_costs=None):
    """Manufacturing Report PDF in the Profit & Loss statement style - mirrors
    the on-screen page section for section (see build_manufacturing_statement):
    headline badges, the Production Performance summary, one statement per
    product, then the Manufacturing Order cost summary and one statement per
    order.

    audience:
      'admin' - everything, including every money figure.
      'staff' - production copy: quantities, completion %, components and
                staff assignments only. Every monetary figure is dropped from
                the layout entirely, so the sheet can be handed to production
                staff without exposing financials.
    """
    from xml.sax.saxutils import escape
    from reportlab.platypus import KeepTogether, PageBreak

    staff_copy = (audience == 'staff')
    st = build_manufacturing_statement(fs, mo_costs, staff_copy)

    GREEN = colors.HexColor('#198754')
    RED = colors.HexColor('#dc3545')
    AMBER = colors.HexColor('#b8860b')
    BLUE = colors.HexColor('#0d6efd')
    MUTED = colors.HexColor('#6c757d')
    NAVY = colors.HexColor('#3f51b5')
    GRAY_BG = colors.HexColor('#f1f3f5')
    INFO_BG = colors.HexColor('#d1ecf1')
    PRIMARY_BG = colors.HexColor('#cfe2ff')
    DARK_BG = colors.HexColor('#212529')
    LINE = colors.HexColor('#e9ecef')
    COLORS = {'green': GREEN, 'red': RED, 'amber': AMBER, 'muted': MUTED}

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter,
                            rightMargin=36, leftMargin=36, topMargin=32, bottomMargin=32,
                            title=f"Manufacturing Report {fs['month_label']}")
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('MRTitle', parent=styles['Heading1'], alignment=1, fontSize=16)
    sub_style = ParagraphStyle('MRSub', parent=styles['Normal'], alignment=1, textColor=MUTED)
    part_style = ParagraphStyle('MRPart', parent=styles['Heading2'], textColor=NAVY, fontSize=13,
                                spaceBefore=4, spaceAfter=6, keepWithNext=1)
    block_title_style = ParagraphStyle('MRBlock', parent=styles['Normal'], fontName='Helvetica-Bold',
                                       fontSize=10.5, textColor=colors.white)
    block_total_style = ParagraphStyle('MRBlockTot', parent=block_title_style, alignment=2)
    block_sub_style = ParagraphStyle('MRBlockSub', parent=styles['Normal'], fontSize=8,
                                     textColor=MUTED, fontName='Helvetica-Oblique')
    label_style = ParagraphStyle('MRLabel', parent=styles['Normal'], fontSize=9, leading=11)
    line_style = ParagraphStyle('MRLine', parent=label_style, leftIndent=12, textColor=colors.HexColor('#555555'))
    bold_style = ParagraphStyle('MRBold', parent=label_style, fontName='Helvetica-Bold')
    white_style = ParagraphStyle('MRWhite', parent=bold_style, textColor=colors.white, fontSize=10.5)
    note_style = ParagraphStyle('MRNote', parent=label_style, fontSize=7.5, textColor=MUTED,
                                fontName='Helvetica-Oblique', leftIndent=12)

    if company_info:
        elements.append(Paragraph(f"<b>{escape(company_info.get('name') or 'Company Report')}</b>",
                                  ParagraphStyle('co', parent=styles['Heading2'], alignment=1)))
        addr_bits = [b for b in [
            company_info.get('address'),
            f"Phone: {company_info.get('phone')}" if company_info.get('phone') else None,
            company_info.get('email'),
        ] if b]
        if addr_bits:
            elements.append(Paragraph(escape(' | '.join(addr_bits)),
                                      ParagraphStyle('co2', parent=styles['Normal'], alignment=1,
                                                     fontSize=9, textColor=MUTED)))
        elements.append(Spacer(1, 0.12 * inch))

    elements.append(Paragraph(f"MANUFACTURING REPORT &mdash; {escape(fs['month_label'])}", title_style))
    elements.append(Paragraph(
        'PRODUCTION COPY &mdash; quantities and staff assignments only' if staff_copy
        else 'MANAGEMENT COPY &mdash; full costing and profitability', sub_style))
    elements.append(Spacer(1, 0.18 * inch))

    # ── Headline badges (like the P&L's Net Profit Margin card) ────────────
    pt = fs['performance_totals']
    completion = pt['completion_pct']
    comp_bg = GREEN if completion >= 100 else (AMBER if completion >= 70 else RED)
    badge_label = ParagraphStyle('bl', parent=styles['Normal'], alignment=1, textColor=colors.white, fontSize=9)
    badge_value = ParagraphStyle('bv', parent=styles['Normal'], alignment=1, textColor=colors.white,
                                 fontSize=20, leading=24, fontName='Helvetica-Bold')
    badge_foot = ParagraphStyle('bf', parent=badge_label, fontSize=8)

    def badge(label, value, foot, bg):
        t = Table([[Paragraph(label, badge_label)], [Paragraph(value, badge_value)], [Paragraph(foot, badge_foot)]])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ]))
        return t

    badges = [badge('TARGET COMPLETION', f"{completion:.1f}%",
                    f"{pt['produced_units']:,.0f} of {pt['target_units']:,.0f} units produced", comp_bg)]
    if not staff_copy:
        badges.append(badge('ACTUAL PROFIT (SO FAR)', f"PKR {pt['actual_profit']:,.0f}",
                            f"Expected if target met: PKR {pt['estimated_profit']:,.0f}",
                            BLUE if pt['actual_profit'] >= 0 else RED))
        if mo_costs is not None:
            badges.append(badge('TOTAL MANUFACTURING COST', f"PKR {mo_costs['totals']['total']:,.0f}",
                                f"across {len(mo_costs['rows'])} order(s)", NAVY))
    gap = 8
    bw = (doc.width - gap * (len(badges) - 1)) / len(badges)
    cells, widths = [], []
    for i, b in enumerate(badges):
        if i:
            cells.append('')
            widths.append(gap)
        cells.append(b)
        widths.append(bw)
    badge_row = Table([cells], colWidths=widths)
    badge_row.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                   ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(badge_row)
    elements.append(Spacer(1, 0.22 * inch))

    # ── Statement block renderer (same styling as generate_profit_loss_pdf) ─
    col_w = [doc.width * 0.62, doc.width * 0.19, doc.width * 0.19]

    def render_block(b):
        rows = [[Paragraph(escape(b['title']), block_title_style), '',
                 Paragraph(f"PKR {b['head_total']:,.2f}", block_total_style) if b.get('head_total') is not None else '']]
        cmds = [
            ('SPAN', (0, 0), (1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('GRID', (0, 1), (-1, -1), 0.4, LINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        if b.get('subtitle'):
            rows.append([Paragraph(escape(b['subtitle']), block_sub_style), '', ''])
            cmds.append(('SPAN', (0, 1), (2, 1)))
        hr = len(rows)
        header_rows = hr + 1
        rows.append([Paragraph('<b>Account Description</b>', label_style), 'Amount', 'Total'])
        cmds += [('BACKGROUND', (0, hr), (-1, hr), colors.HexColor('#f8f9fa')),
                 ('FONTNAME', (1, hr), (-1, hr), 'Helvetica-Bold')]

        for ln in b['lines']:
            r = len(rows)
            kind = ln['kind']
            if kind == 'spacer':
                rows.append(['', '', ''])
                cmds += [('SPAN', (0, r), (2, r)), ('TOPPADDING', (0, r), (-1, r), 1),
                         ('BOTTOMPADDING', (0, r), (-1, r), 1)]
                continue
            if kind == 'note':
                rows.append([Paragraph(escape(ln['label']), note_style), '', ''])
                cmds.append(('SPAN', (0, r), (2, r)))
                continue
            if kind == 'band':
                rows.append([Paragraph(escape(ln['label'].upper()), bold_style), '', ''])
                cmds += [('SPAN', (0, r), (2, r)), ('BACKGROUND', (0, r), (-1, r), GRAY_BG)]
                continue
            if kind == 'line':
                rows.append([Paragraph(escape(ln['label']), line_style),
                             format_statement_value(ln['amount'], ln['fmt'], ln['neg']), ''])
                if ln['color']:
                    cmds.append(('TEXTCOLOR', (1, r), (1, r), COLORS[ln['color']]))
                continue
            # section / total / primary / grand: label spans two columns, figure in Total
            total = ln['total']
            style = white_style if kind == 'grand' else bold_style
            rows.append([Paragraph(escape(ln['label']), style), '',
                         format_statement_value(total, ln['fmt'], ln['neg'])])
            cmds += [('SPAN', (0, r), (1, r)), ('FONTNAME', (2, r), (2, r), 'Helvetica-Bold')]
            if kind == 'section':
                cmds.append(('BACKGROUND', (0, r), (-1, r), INFO_BG))
            elif kind == 'primary':
                cmds.append(('BACKGROUND', (0, r), (-1, r), PRIMARY_BG))
                if isinstance(total, (int, float)) and total < 0:
                    cmds.append(('TEXTCOLOR', (2, r), (2, r), RED))
            elif kind == 'grand':
                cmds += [('BACKGROUND', (0, r), (-1, r), DARK_BG), ('FONTSIZE', (2, r), (2, r), 10.5)]
                if isinstance(total, (int, float)):
                    cmds.append(('TEXTCOLOR', (2, r), (2, r),
                                 colors.HexColor('#75d99b') if total >= 0 else colors.HexColor('#ff8a95')))
                else:
                    cmds.append(('TEXTCOLOR', (2, r), (2, r), colors.white))
            elif kind == 'total':
                cmds += [('LINEABOVE', (0, r), (-1, r), 0.8, colors.HexColor('#495057')),
                         ('LINEBELOW', (0, r), (-1, r), 1.2, colors.HexColor('#495057'))]
            if ln['total_color']:
                cmds.append(('TEXTCOLOR', (2, r), (2, r), COLORS[ln['total_color']]))

        # A statement that runs onto the next page repeats its title + column header there.
        t = Table(rows, colWidths=col_w, repeatRows=header_rows)
        t.setStyle(TableStyle(cmds))
        return t

    def add_blocks(blocks, lead=None):
        # lead: a section heading kept on the same page as the first statement.
        for i, b in enumerate(blocks):
            t = render_block(b)
            group = ([lead] if (lead is not None and i == 0) else []) + [t]
            # Short statements stay on one page; long ones flow on with a repeated header
            # rather than jumping whole to a new page and leaving a gap.
            if len(b['lines']) <= 22:
                elements.append(KeepTogether(group))
            else:
                elements.extend(group)
            elements.append(Spacer(1, 0.18 * inch))

    # Part A - production performance
    elements.append(Paragraph('PART A &mdash; PRODUCTION PERFORMANCE: TARGET VS ACHIEVED', part_style))
    add_blocks(st['summary'][:1])
    products_heading = Paragraph(f"TARGET VS ACHIEVED BY PRODUCT &mdash; {escape(fs['month_label'])}", part_style)
    if st['products']:
        add_blocks(st['products'], lead=products_heading)
    else:
        elements.append(products_heading)
        elements.append(Paragraph(f"No production targets found for {escape(fs['month_label'])}.", note_style))
        elements.append(Spacer(1, 0.18 * inch))

    # Part B - manufacturing order costs
    if mo_costs is not None:
        elements.append(PageBreak())
        elements.append(Paragraph('PART B &mdash; MANUFACTURING ORDER ' +
                                  ('PRODUCTION SHEET' if staff_copy else 'COST STATEMENT'), part_style))
        add_blocks(st['summary'][1:])
        if st['orders']:
            add_blocks(st['orders'])
        else:
            elements.append(Paragraph(f"No Manufacturing Orders found for {escape(fs['month_label'])}.", note_style))

    if staff_copy:
        note = ("NOTE: This is the production copy of the monthly manufacturing report. It shows target vs "
                "actual production quantities, the components each order needs and which staff worked on each "
                "product's orders. Costing, labour rates, revenue and profit figures are intentionally excluded.")
    else:
        note = ("NOTE: Target combines the Production Target Tracker's manual target with the planned quantity "
                "of Manufacturing Orders started in the period. Labour cost per staff member comes from the "
                "order's HR 'Staff Used' assignment and is split between the quantity already produced (labor "
                "used) and the quantity still remaining. Figures in brackets are deductions. Profit shown is "
                "manufacturing profit before sales/admin expenses, discounts, freight, warranty, taxes and "
                "financing costs.")
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(note, ParagraphStyle('note', parent=styles['Normal'], fontSize=7.5,
                                                   textColor=MUTED, fontName='Helvetica-Oblique')))
    elements.append(Spacer(1, 0.1 * inch))
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
