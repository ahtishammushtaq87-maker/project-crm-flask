"""Starting content for "New spreadsheet" templates.

Each template is one sheet: a bold, filled header row (frozen), sensible
column widths and number formats, a few example rows and - where it makes
sense - a totals row built from real formulas.
"""

HEADER_FMT = {'b': True, 'bg': '#e8f0fe', 'c': '#1a3e72', 'bb': {'w': 2, 's': 'solid', 'c': '#1a73e8'}}
TOTAL_FMT = {'b': True, 'bt': {'w': 1, 's': 'solid', 'c': '#5f6368'}}


def _money(cur='Rs'):
    return {'nf': {'t': 'currency', 'd': 0, 'cur': cur}}


DATE = {'nf': {'t': 'date'}}
PCT = {'nf': {'t': 'percent', 'd': 0}}


def _table(name, headers, widths, rows, col_fmts=None, totals=None):
    """headers: list of str; rows: list of lists; col_fmts: {col: fmt};
    totals: {col: formula template using {first} and {last} row numbers}."""
    col_fmts = col_fmts or {}
    cells = []
    for c, h in enumerate(headers):
        cells.append((0, c, h, dict(HEADER_FMT)))
    for r, row in enumerate(rows, start=1):
        for c, v in enumerate(row):
            if v is None or v == '':
                continue
            cells.append((r, c, str(v), dict(col_fmts[c]) if c in col_fmts else None))
    if totals:
        tr = len(rows) + 1
        first, last = 2, len(rows) + 1
        cells.append((tr, 0, 'Total', dict(TOTAL_FMT)))
        for c, tmpl in totals.items():
            fmt = dict(TOTAL_FMT)
            fmt.update(col_fmts.get(c, {}))
            cells.append((tr, c, tmpl.format(first=first, last=last), fmt))
    return {
        'name': name,
        'frozen_rows': 1,
        'props': {'cw': {str(i): w for i, w in enumerate(widths)}},
        'cells': cells,
    }


def _col(c):
    return chr(ord('A') + c)


TEMPLATES = {
    'blank': {
        'label': 'Blank spreadsheet',
        'icon': 'fa-file',
        'description': 'Start from an empty grid.',
        'sheet': None,
    },
    'sales': {
        'label': 'Sales Tracker',
        'icon': 'fa-chart-line',
        'description': 'Invoices, quantities and totals.',
        'sheet': lambda: _table(
            'Sales',
            ['Date', 'Invoice #', 'Customer', 'Product', 'Qty', 'Unit Price', 'Amount', 'Status'],
            [100, 100, 170, 170, 70, 110, 120, 100],
            [
                ['2026-10-01', 'INV-1001', 'Acme Traders', 'Water Pump', 5, 3500, '=E2*F2', 'Paid'],
                ['2026-10-02', 'INV-1002', 'Star Motors', 'Fuel Pump', 2, 3800, '=E3*F3', 'Pending'],
                ['2026-10-03', 'INV-1003', 'City Spares', 'Gasket Set', 20, 70, '=E4*F4', 'Paid'],
            ],
            col_fmts={0: DATE, 5: _money(), 6: _money()},
            totals={4: '=SUM(E{first}:E{last})', 6: '=SUM(G{first}:G{last})'},
        ),
    },
    'expenses': {
        'label': 'Expense Tracker',
        'icon': 'fa-receipt',
        'description': 'Track spending by category.',
        'sheet': lambda: _table(
            'Expenses',
            ['Date', 'Category', 'Description', 'Paid To', 'Method', 'Amount'],
            [100, 140, 220, 160, 110, 120],
            [
                ['2026-10-01', 'Utilities', 'Electricity bill', 'LESCO', 'Bank', 42000],
                ['2026-10-03', 'Transport', 'Courier charges', 'TCS', 'Cash', 3500],
                ['2026-10-05', 'Office', 'Stationery', 'Book Mart', 'Cash', 2200],
            ],
            col_fmts={0: DATE, 5: _money()},
            totals={5: '=SUM(F{first}:F{last})'},
        ),
    },
    'inventory': {
        'label': 'Inventory',
        'icon': 'fa-boxes-stacked',
        'description': 'Stock levels, cost and value.',
        'sheet': lambda: _table(
            'Inventory',
            ['SKU', 'Item', 'Warehouse', 'Qty', 'Unit Cost', 'Stock Value', 'Reorder Level', 'Reorder?'],
            [100, 220, 140, 80, 110, 130, 110, 90],
            [
                ['1010001', 'Water Pump 6BT', 'Lahore - Main', 120, 3500, '=D2*E2', 20, '=IF(D2<=G2,"Yes","No")'],
                ['2010005', 'O-Ring DCEC 6BT', 'Lahore - Main', 15, 520, '=D3*E3', 50, '=IF(D3<=G3,"Yes","No")'],
                ['3010001', 'Main Body Casting', 'Lahore - Main', 300, 426, '=D4*E4', 100, '=IF(D4<=G4,"Yes","No")'],
            ],
            col_fmts={4: _money(), 5: _money()},
            totals={3: '=SUM(D{first}:D{last})', 5: '=SUM(F{first}:F{last})'},
        ),
    },
    'customers': {
        'label': 'Customer List',
        'icon': 'fa-address-book',
        'description': 'Contacts, cities and status.',
        'sheet': lambda: _table(
            'Customers',
            ['Customer', 'Contact Person', 'Phone', 'Email', 'City', 'Status', 'Notes'],
            [180, 150, 130, 200, 110, 100, 220],
            [
                ['Acme Traders', 'Ali Raza', '0300-1234567', 'ali@example.com', 'Lahore', 'Active', ''],
                ['Star Motors', 'Sara Khan', '0321-7654321', 'sara@example.com', 'Karachi', 'Active', ''],
                ['City Spares', 'Bilal Ahmed', '0333-1112223', 'bilal@example.com', 'Multan', 'Prospect', ''],
            ],
        ),
    },
    'employees': {
        'label': 'Employee List',
        'icon': 'fa-id-badge',
        'description': 'Staff, roles and joining dates.',
        'sheet': lambda: _table(
            'Employees',
            ['Employee', 'Designation', 'Department', 'Joining Date', 'Phone', 'Monthly Salary'],
            [170, 150, 130, 110, 130, 130],
            [
                ['Ahmed Khan', 'Sales Executive', 'Sales', '2025-02-01', '0300-0000001', 60000],
                ['Sara Ali', 'Accountant', 'Finance', '2024-08-15', '0300-0000002', 75000],
                ['Bilal Hussain', 'Machinist', 'Production', '2023-11-20', '0300-0000003', 55000],
            ],
            col_fmts={3: DATE, 5: _money()},
            totals={5: '=SUM(F{first}:F{last})'},
        ),
    },
    'projects': {
        'label': 'Project Tracker',
        'icon': 'fa-list-check',
        'description': 'Tasks, owners, dates and progress.',
        'sheet': lambda: _table(
            'Projects',
            ['Task', 'Owner', 'Start', 'Due', 'Status', 'Progress', 'Notes'],
            [220, 130, 100, 100, 110, 90, 220],
            [
                ['Prepare new pump drawings', 'Ahmed', '2026-10-01', '2026-10-10', 'In Progress', 0.4, ''],
                ['Order castings', 'Sara', '2026-10-05', '2026-10-15', 'Not Started', 0, ''],
                ['Pilot batch testing', 'Bilal', '2026-10-12', '2026-10-25', 'Not Started', 0, ''],
            ],
            col_fmts={2: DATE, 3: DATE, 5: PCT},
        ),
    },
}


def template_choices():
    return [{'key': k, 'label': t['label'], 'icon': t['icon'], 'description': t['description']}
            for k, t in TEMPLATES.items()]


def build_template(key):
    """The first sheet for a new spreadsheet, or None for a blank one."""
    tmpl = TEMPLATES.get(key) or TEMPLATES['blank']
    return tmpl['sheet']() if tmpl['sheet'] else None


# Status columns get a dropdown so the template shows data validation in use.
STATUS_VALIDATION = {
    'sales': (7, ['Paid', 'Pending', 'Cancelled']),
    'customers': (5, ['Active', 'Prospect', 'Inactive']),
    'projects': (4, ['Not Started', 'In Progress', 'Blocked', 'Done']),
}
