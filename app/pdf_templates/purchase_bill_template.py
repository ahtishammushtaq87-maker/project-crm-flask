# Purchase Bill PDF Template Configuration
# This file defines the structure for purchase bill PDFs
# Edit this file to customize the bill layout

DOCUMENT_TYPE = 'purchase'
TITLE = 'PURCHASE BILL'

# Table columns configuration
# Format: (header_key, width_multiplier, align)
TABLE_COLUMNS = [
    ('description', 3.2, 'LEFT'),
    ('quantity', 0.8, 'CENTER'),
    ('rate', 1.2, 'RIGHT'),
    ('amount', 1.2, 'RIGHT'),
]

# Section labels
LABELS = {
    'from': 'FROM',
    'vendor': 'VENDOR',
    'ship_from': 'SHIP FROM',
    'date': 'Date',
    'due_date': 'Due Date',
    'bill_number': 'Bill #',
    'subtotal': 'Subtotal',
    'tax': 'Tax',
    'discount': 'Discount',
    'shipping': 'Shipping',
    'total': 'Total',
    'advance_applied': 'Advance Applied',
    'paid': 'Paid',
    'balance_due': 'Balance Due',
    'terms': 'TERMS & CONDITIONS',
    'notes': 'NOTES',
}

# Totals configuration - which fields to show and in what order
# Each tuple: (field_name, display_label, apply_currency=True)
TOTALS = [
    ('subtotal', 'Subtotal:', True),
    ('tax', 'Tax:', True),
    ('discount', 'Discount:', True),
    ('shipping', 'Shipping:', True),
    ('total', 'Total:', True),
    ('advance_applied', 'Advance Applied:', True),
    ('paid', 'Paid:', True),
    ('balance_due', 'Balance Due:', True),
]

# Default currency symbol
CURRENCY_SYMBOL = 'Rs'
CURRENCY_FORMAT = ',.2f'  # Format: ,.2f = 1,234.56

# Item field mappings
ITEM_MAPPING = {
    'description': 'product.name',
    'quantity': 'quantity',
    'rate': 'unit_price',
    'total': 'total',
}

# Vendor field mappings
CLIENT_MAPPING = {
    'name': 'vendor.name',
    'address': 'vendor.address',
    'email': 'vendor.email',
    'phone': 'vendor.phone',
    'gst_number': 'vendor.gst_number',
}

# Footer configuration
FOOTER_SHOW_PAGE_NUMBER = True
FOOTER_SHOW_COMPANY_INFO = True
FOOTER_MESSAGE = ''

# Additional notes to include from bill
INCLUDE_DUE_DATE = True
INCLUDE_PO_REFERENCE = True
INCLUDE_DELIVERY_INFO = True
