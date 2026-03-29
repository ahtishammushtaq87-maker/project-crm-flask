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
    table_data = [headers]
    for row in data:
        table_data.append([str(row.get(h, '')) for h in headers])
    
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
