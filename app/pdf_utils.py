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

# Modern Professional Color Palette
PRIMARY_COLOR = colors.HexColor("#3f51b5")  # Indigo
SECONDARY_COLOR = colors.HexColor("#5c6bc0")
ACCENT_COLOR = colors.HexColor("#f5f5f5")
TEXT_COLOR = colors.HexColor("#212121")
MUTED_TEXT_COLOR = colors.HexColor("#757575")
WHITE = colors.whitesmoke
BLACK = colors.black

class ProfessionalPDFGenerator:
    def __init__(self, buffer, company=None, invoice_settings=None):
        self.buffer = buffer
        self.doc = SimpleDocTemplate(
            self.buffer, 
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        self.styles = getSampleStyleSheet()
        self.company = company
        self.settings = invoice_settings
        self.setup_custom_styles()

    def setup_custom_styles(self):
        """Create professional typography styles."""
        self.styles.add(ParagraphStyle(
            name='DocTitle',
            parent=self.styles['Heading1'],
            fontSize=26,
            textColor=PRIMARY_COLOR,
            spaceAfter=10,
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='DocSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=MUTED_TEXT_COLOR,
            alignment=TA_RIGHT,
            spaceAfter=20
        ))
        
        self.styles.add(ParagraphStyle(
            name='CompanyName',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=PRIMARY_COLOR,
            fontName='Helvetica-Bold',
            spaceAfter=4
        ))
        
        self.styles.add(ParagraphStyle(
            name='CompanyInfo',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=MUTED_TEXT_COLOR,
            leading=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=PRIMARY_COLOR,
            fontName='Helvetica-Bold',
            spaceBefore=15,
            spaceAfter=8,
            textTransform='uppercase'
        ))

        self.styles.add(ParagraphStyle(
            name='ClientName',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=TEXT_COLOR,
            fontName='Helvetica-Bold',
            spaceAfter=4
        ))
        
        self.styles.add(ParagraphStyle(
            name='ClientInfo',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=TEXT_COLOR,
            leading=12
        ))

        self.styles.add(ParagraphStyle(
            name='TotalLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=TEXT_COLOR,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        ))

        self.styles.add(ParagraphStyle(
            name='TotalValue',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=PRIMARY_COLOR,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        ))

    def _get_logo(self):
        """Handle company logo if available."""
        if self.company and self.company.logo_path and os.path.exists(self.company.logo_path):
            try:
                # Standardize logo size for the header
                img = Image(self.company.logo_path)
                aspect = img.imageHeight / float(img.imageWidth)
                width = 1.5 * inch
                height = width * aspect
                img.drawHeight = height
                img.drawWidth = width
                return img
            except Exception:
                return None
        return None

    def generate_document(self, title, doc_number, date, due_date, client_data, items, totals, payment_info=None, terms=None, notes=None):
        """Generic method to build a professional PDF document."""
        elements = []
        
        # --- HEADER SECTION ---
        logo = self._get_logo()
        
        header_data = [
            [
                logo if logo else Paragraph(self.company.name if self.company else "COMPANY", self.styles['CompanyName']),
                [
                    Paragraph(title.upper(), self.styles['DocTitle']),
                    Paragraph(f"#{doc_number}", self.styles['DocSubtitle'])
                ]
            ]
        ]
        
        header_table = Table(header_data, colWidths=[3.5 * inch, 2.5 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY_COLOR, spaceAfter=20))
        
        # --- INFO SECTION (Company vs Client) ---
        info_data = [
            [
                # From (Company)
                [
                    Paragraph("FROM", self.styles['SectionHeader']),
                    Paragraph(self.company.name if self.company else "Company Name", self.styles['CompanyName']),
                    Paragraph(self.company.address if self.company else "", self.styles['CompanyInfo']),
                    Paragraph(f"Email: {self.company.email}" if self.company and self.company.email else "", self.styles['CompanyInfo']),
                    Paragraph(f"Phone: {self.company.phone}" if self.company and self.company.phone else "", self.styles['CompanyInfo']),
                    Paragraph(f"GST: {self.company.gst_number}" if self.company and self.company.gst_number else "", self.styles['CompanyInfo']),
                ],
                # To (Client/Vendor)
                [
                    Paragraph("BILL TO", self.styles['SectionHeader']),
                    Paragraph(client_data.get('name', 'N/A'), self.styles['ClientName']),
                    Paragraph(client_data.get('address', 'N/A'), self.styles['ClientInfo']),
                    Paragraph(f"Email: {client_data.get('email', 'N/A')}" if client_data.get('email') else "", self.styles['ClientInfo']),
                    Paragraph(f"Phone: {client_data.get('phone', 'N/A')}" if client_data.get('phone') else "", self.styles['ClientInfo']),
                    Paragraph(f"GST: {client_data.get('gst_number', 'N/A')}" if client_data.get('gst_number') else "", self.styles['ClientInfo']),
                ],
                # Dates
                [
                    Spacer(1, 15),
                    Table([
                        [Paragraph("Date:", self.styles['Normal']), Paragraph(date.strftime('%d/%m/%Y') if date else "N/A", self.styles['Normal'])],
                        [Paragraph("Due Date:", self.styles['Normal']), Paragraph(due_date.strftime('%d/%m/%Y') if due_date else "N/A", self.styles['Normal'])],
                    ], colWidths=[0.8 * inch, 1.2 * inch], style=TableStyle([
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ]))
                ]
            ]
        ]
        
        info_table = Table(info_data, colWidths=[2.2 * inch, 2.2 * inch, 2.2 * inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 25))
        
        # --- ITEMS TABLE ---
        table_headers = [
            Paragraph("<b>Description</b>", self.styles['Normal']),
            Paragraph("<b>Qty</b>", self.styles['Normal']),
            Paragraph("<b>Rate</b>", self.styles['Normal']),
            Paragraph("<b>Amount</b>", self.styles['Normal'])
        ]
        
        table_data = [table_headers]
        for item in items:
            table_data.append([
                item['description'],
                str(item['quantity']),
                item['rate'],
                item['amount']
            ])
            
        # If no items, add a placeholder
        if not items:
            table_data.append(["No items listed", "-", "-", "-"])

        items_table = Table(table_data, colWidths=[3.2 * inch, 0.8 * inch, 1.2 * inch, 1.2 * inch])
        
        # Professional Table Styling
        items_style = TableStyle([
            # Headers
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Rows
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_COLOR),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
            
            # Alternating row background
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ACCENT_COLOR]),
            
            # Border
            ('LINEBELOW', (0, 0), (-1, 0), 2, PRIMARY_COLOR),
            ('LINEBELOW', (0, -1), (-1, -1), 1, PRIMARY_COLOR),
        ])
        items_table.setStyle(items_style)
        elements.append(items_table)
        elements.append(Spacer(1, 15))
        
        # --- TOTALS SECTION ---
        totals_rows = []
        for label, value in totals:
            totals_rows.append([
                Paragraph(label, self.styles['TotalLabel']),
                Paragraph(value, self.styles['TotalValue'])
            ])
            
        totals_table = Table(totals_rows, colWidths=[5 * inch, 1.4 * inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(totals_table)
        elements.append(Spacer(1, 30))
        
        # --- PAYMENT INFO & NOTES ---
        notes_data = []
        
        if payment_info:
            notes_data.append([Paragraph("PAYMENT DETAILS", self.styles['SectionHeader'])])
            for key, value in payment_info.items():
                if value:
                    notes_data.append([Paragraph(f"<b>{key}:</b> {value}", self.styles['CompanyInfo'])])
            notes_data.append([Spacer(1, 15)])

        if terms:
            notes_data.append([Paragraph("TERMS & CONDITIONS", self.styles['SectionHeader'])])
            notes_data.append([Paragraph(terms, self.styles['CompanyInfo'])])
            notes_data.append([Spacer(1, 15)])
            
        if notes:
            notes_data.append([Paragraph("NOTES", self.styles['SectionHeader'])])
            notes_data.append([Paragraph(notes, self.styles['CompanyInfo'])])

        if notes_data:
            notes_table = Table(notes_data, colWidths=[6.4 * inch])
            notes_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(notes_table)

        # Build the final document
        self.doc.build(elements, onFirstPage=self._add_footer, onLaterPages=self._add_footer)

    def _add_footer(self, canvas, doc):
        """Add a professional footer to every page."""
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setStrokeColor(PRIMARY_COLOR)
        canvas.setLineWidth(0.5)
        canvas.line(40, 50, A4[0]-40, 50)
        
        # Footer text
        footer_text = f"Page {doc.page}"
        canvas.drawRightString(A4[0]-40, 35, footer_text)
        
        if self.company:
            company_footer = f"{self.company.name} | {self.company.email} | {self.company.phone}"
            canvas.drawString(40, 35, company_footer)
            
        canvas.drawCentredString(A4[0]/2.0, 35, "Thank you for your business!")
        canvas.restoreState()

def generate_professional_pdf(doc_type, obj, company, settings=None):
    """
    Convenience function to generate a professional PDF based on the object type.
    doc_type: 'invoice' or 'purchase'
    obj: Sale or PurchaseBill model instance
    """
    buffer = io.BytesIO()
    generator = ProfessionalPDFGenerator(buffer, company, settings)
    
    if doc_type == 'invoice':
        title = "Invoice"
        doc_number = obj.invoice_number
        client_data = {
            'name': obj.customer.name if obj.customer else "Walk-in Customer",
            'address': obj.customer.address if obj.customer else "",
            'email': obj.customer.email if obj.customer else "",
            'phone': obj.customer.phone if obj.customer else "",
            'gst_number': obj.customer.gst_number if obj.customer else "",
        }
        items = [
            {
                'description': item.product.name if item.product else "Unknown Product",
                'quantity': int(item.quantity) if item.quantity.is_integer() else item.quantity,
                'rate': f"Rs{item.unit_price:,.2f}",
                'amount': f"Rs{item.total:,.2f}"
            } for item in obj.items
        ]
        totals = [
            ("Subtotal:", f"Rs{obj.subtotal:,.2f}"),
            ("Tax:", f"Rs{obj.tax:,.2f}"),
            ("Discount:", f"-Rs{obj.discount:,.2f}"),
            ("Total:", f"Rs{obj.total:,.2f}"),
            ("Paid:", f"Rs{obj.paid_amount:,.2f}"),
            ("Balance Due:", f"Rs{obj.balance_due:,.2f}"),
        ]
        
        # Extract payment info
        payment_info = None
        if settings:
            payment_info = {
                'Bank Name': settings.bank_name,
                'Account Holder': settings.account_holder_name,
                'Account Number': settings.account_number,
                'IFSC Code': settings.ifsc_code,
                'SWIFT Code': settings.swift_code,
            }
        elif company:
             payment_info = {
                'Bank Name': company.bank_name,
                'Account Number': company.account_number,
                'IFSC Code': company.ifsc_code,
                'Account Holder': company.account_holder_name,
            }
            
        generator.generate_document(
            title=title,
            doc_number=doc_number,
            date=obj.date,
            due_date=obj.due_date,
            client_data=client_data,
            items=items,
            totals=totals,
            payment_info=payment_info,
            terms=obj.terms or (settings.default_terms if settings else None),
            notes=obj.notes or (settings.default_notes if settings else None)
        )
        
    elif doc_type == 'purchase':
        title = "Purchase Order"
        doc_number = obj.bill_number
        client_data = {
            'name': obj.vendor.name if obj.vendor else "Unknown Vendor",
            'address': obj.vendor.address if obj.vendor else "",
            'email': obj.vendor.email if obj.vendor else "",
            'phone': obj.vendor.phone if obj.vendor else "",
            'gst_number': obj.vendor.gst_number if obj.vendor else "",
        }
        items = [
            {
                'description': item.product.name if item.product else "Unknown Product",
                'quantity': int(item.quantity) if item.quantity.is_integer() else item.quantity,
                'rate': f"Rs{item.unit_price:,.2f}",
                'amount': f"Rs{item.total:,.2f}"
            } for item in obj.items
        ]
        totals = [
            ("Subtotal:", f"Rs{obj.subtotal:,.2f}"),
            ("Tax:", f"Rs{obj.tax:,.2f}"),
            ("Discount:", f"-Rs{obj.discount:,.2f}"),
            ("Shipping:", f"Rs{obj.shipping_charge:,.2f}"),
            ("Total:", f"Rs{obj.total:,.2f}"),
            ("Paid:", f"Rs{obj.paid_amount:,.2f}"),
            ("Balance Due:", f"Rs{obj.balance_due:,.2f}"),
        ]
        
        generator.generate_document(
            title=title,
            doc_number=doc_number,
            date=obj.date,
            due_date=obj.due_date,
            client_data=client_data,
            items=items,
            totals=totals,
            notes=obj.notes
        )
        
    buffer.seek(0)
    return buffer
