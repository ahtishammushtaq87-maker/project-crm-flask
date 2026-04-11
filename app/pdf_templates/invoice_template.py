# Sale Invoice PDF Template Configuration
# This file defines the structure for sale invoice PDFs
# Edit this file to customize the invoice layout

DOCUMENT_TYPE = 'invoice'
TITLE = 'INVOICE'

# Table columns configuration
TABLE_COLUMNS = [
    ('description', 3.2, 'LEFT'),
    ('quantity', 0.8, 'CENTER'),
    ('rate', 1.2, 'RIGHT'),
    ('amount', 1.2, 'RIGHT'),
]

# Section labels
LABELS = {
    'from': 'FROM',
    'bill_to': 'BILL TO',
    'ship_to': 'SHIP TO',
    'reference': 'REFERENCE',
    'date': 'Date',
    'due_date': 'Due Date',
    'invoice_number': 'Invoice #',
    'subtotal': 'Subtotal',
    'tax': 'Tax',
    'discount': 'Discount',
    'total': 'Total',
    'total_due': 'Total Due',
    'paid': 'Paid',
    'balance_due': 'Balance Due',
    'payment_details': 'PAYMENT DETAILS',
    'terms': 'TERMS & CONDITIONS',
    'notes': 'NOTES',
    'bank_details': 'BANK DETAILS',
    'company': 'COMPANY',
    'shipping': 'Shipping',
}

# Invoice settings fields to include in payment details
# These fields come from InvoiceSettings model
INVOICE_FIELDS = [
    'bank_name',
    'account_holder_name', 
    'account_number',
    'ifsc_code',
    'swift_code',
    'bank_address',
    'payment_instructions',
]

# Default currency symbol
CURRENCY_SYMBOL = 'Rs'
CURRENCY_FORMAT = ',.2f'  # Format: ,.2f = 1,234.56

# Footer configuration
FOOTER_SHOW_PAGE_NUMBER = True
FOOTER_SHOW_COMPANY_INFO = True
FOOTER_MESSAGE = 'Thank you for your business!'

# Show/hide sections
SHOW_PAYMENT_DETAILS = True
SHOW_TERMS = True
SHOW_NOTES = True
SHOW_BANK_DETAILS = True