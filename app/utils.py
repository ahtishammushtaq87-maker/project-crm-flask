# app/utils.py
from datetime import datetime, timedelta
import random
import string
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

def generate_invoice_number():
    """Generate a unique invoice number"""
    year = datetime.now().strftime('%Y')
    month = datetime.now().strftime('%m')
    random_num = random.randint(1000, 9999)
    return f"INV-{year}{month}-{random_num}"

def generate_bill_number():
    """Generate a unique purchase bill number"""
    year = datetime.now().strftime('%Y')
    month = datetime.now().strftime('%m')
    random_num = random.randint(1000, 9999)
    return f"PO-{year}{month}-{random_num}"

def generate_sku(name):
    """Generate SKU from product name"""
    name_part = ''.join(word[0] for word in name.split()[:2]).upper()
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{name_part}{random_part}"

def generate_pdf_report(data, headers, filename):
    """Generate PDF report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Add title
    styles = getSampleStyleSheet()
    title = Paragraph(filename, styles['Title'])
    elements.append(title)
    
    # Create table
    table_data = [headers] + data
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

def calculate_profit_margin(cost_price, selling_price):
    """Calculate profit margin percentage"""
    if cost_price > 0:
        return ((selling_price - cost_price) / cost_price) * 100
    return 0

def format_date_range(start_date, end_date):
    """Format date range for display"""
    if start_date and end_date:
        return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
    return "All Time"