"""Universal Filter Engine — converts JSON rules to SQLAlchemy filters safely."""
from sqlalchemy import and_, or_, func
from app import db

# ---------------------------------------------------------------------------
# Supported operators
# ---------------------------------------------------------------------------
VALID_OPERATORS = {
    'equal', 'not_equal', 'contains', 'not_contains',
    'begins_with', 'ends_with',
    'gt', 'lt', 'gte', 'lte',
    '>', '<', '>=', '<=',
    'in', 'not_in',
    'date_between',  # NEW: date range filter
}

OPERATOR_MAP = {
    'gt': '>',
    'lt': '<',
    'gte': '>=',
    'lte': '<=',
}


def _get_model_classes():
    """Lazy import to avoid circular dependency issues."""
    from app.models import (
        Expense, ExpenseCategory, Sale, PurchaseBill, Product,
        Vendor, Customer, Staff, ManufacturingOrder, BOM,
        SaleReturn, PurchaseReturn, PurchaseOrder, ProductionLog,
        SalaryPayment, ProductCategory, SaleItem, Salesman, SalesmanGroup, CustomerGroup
    )
    return {
        'expense': Expense,
        'sale': Sale,
        'purchase': PurchaseBill,
        'product': Product,
        'vendor': Vendor,
        'customer': Customer,
        'staff': Staff,
        'manufacturing_order': ManufacturingOrder,
        'bom': BOM,
        'sale_return': SaleReturn,
        'purchase_return': PurchaseReturn,
        'purchase_order': PurchaseOrder,
        'production_log': ProductionLog,
        'salary_payment': SalaryPayment,
        # Report aliases (map to same models)
        'sales_report': Sale,
        'purchase_report': PurchaseBill,
        'inventory_report': Product,
        'expense_report': Expense,
        'return_report': SaleReturn,
        'manufacturing_report': ManufacturingOrder,
        'bom_report': BOM,
        'salary_report': SalaryPayment,
        'vendor_report': Vendor,
        'customer_report': Customer,
        'cogs_report': SaleItem,  # COGS filters via SaleItem
        'profit_loss_report': Sale,  # P&L primary model
    }


# ---------------------------------------------------------------------------
# Field registry per module
# ---------------------------------------------------------------------------
def _build_field_registry():
    from app.models import (
        Expense, ExpenseCategory, Sale, PurchaseBill, Product,
        Vendor, Customer, Staff, ManufacturingOrder, BOM,
        SaleReturn, PurchaseReturn, PurchaseOrder, ProductionLog,
        SalaryPayment, ProductCategory, SaleItem, Salesman, SalesmanGroup, CustomerGroup
    )
    return {
        # === EXPENSE MODULE ===
        'expense': {
            'name':         {'expr': lambda: Expense.expense_number, 'type': 'string'},
            'date':         {'expr': lambda: Expense.date,           'type': 'date'},
            'year':         {'expr': lambda: func.extract('year', Expense.date), 'type': 'number'},
            'amount':       {'expr': lambda: Expense.amount,         'type': 'number'},
            'category':     {'expr': lambda: ExpenseCategory.name,   'type': 'string', 'join': ExpenseCategory, 'options_route': 'filters.get_expense_categories'},
            'payment_mode': {'expr': lambda: Expense.payment_method,'type': 'string', 'options_route': 'filters.get_payment_methods'},
            'billable':     {'expr': lambda: Expense.is_bom_overhead,'type': 'boolean'},
            'recurring':    {'expr': lambda: Expense.is_monthly_divided, 'type': 'boolean'},
            'vendor':       {'expr': lambda: Vendor.name,            'type': 'string', 'join': Vendor, 'options_route': 'filters.get_vendors'},
        },
        # === SALE MODULE (invoices + sales report) ===
        'sale': {
            'invoice_number': {'expr': lambda: Sale.invoice_number, 'type': 'string'},
            'date':           {'expr': lambda: Sale.date,            'type': 'date'},
            'year':           {'expr': lambda: func.extract('year', Sale.date), 'type': 'number'},
            'amount':         {'expr': lambda: Sale.total,           'type': 'number'},
            'subtotal':       {'expr': lambda: Sale.subtotal,        'type': 'number'},
            'tax':            {'expr': lambda: Sale.tax,             'type': 'number'},
            'paid_amount':    {'expr': lambda: Sale.paid_amount,     'type': 'number'},
            'balance_due':    {'expr': lambda: Sale.balance_due,     'type': 'number'},
            'customer':       {'expr': lambda: Customer.name,        'type': 'string', 'join': Customer, 'options_route': 'filters.get_customers'},
            'status':         {'expr': lambda: Sale.status,          'type': 'string'},
            'salesman':       {'expr': lambda: Sale.salesman_id,     'type': 'number', 'options_route': 'filters.get_salesmen'},
            'salesman_group': {'expr': lambda: SalesmanGroup.name,      'type': 'string', 'join': [Salesman, SalesmanGroup], 'options_route': 'filters.get_salesman_groups'},
            'customer_group': {'expr': lambda: CustomerGroup.name,      'type': 'string', 'join': [Customer, CustomerGroup], 'options_route': 'filters.get_customer_groups'},
        },
        # === PURCHASE MODULE (bills + purchase report) ===
        'purchase': {
            'bill_number':  {'expr': lambda: PurchaseBill.bill_number, 'type': 'string'},
            'date':         {'expr': lambda: PurchaseBill.date,        'type': 'date'},
            'year':         {'expr': lambda: func.extract('year', PurchaseBill.date), 'type': 'number'},
            'amount':       {'expr': lambda: PurchaseBill.total,       'type': 'number'},
            'subtotal':     {'expr': lambda: PurchaseBill.subtotal,    'type': 'number'},
            'tax':          {'expr': lambda: PurchaseBill.tax,         'type': 'number'},
            'paid_amount':  {'expr': lambda: PurchaseBill.paid_amount, 'type': 'number'},
            'balance_due':  {'expr': lambda: PurchaseBill.balance_due, 'type': 'number'},
            'vendor':       {'expr': lambda: Vendor.name,              'type': 'string', 'join': Vendor, 'options_route': 'filters.get_vendors'},
            'status':       {'expr': lambda: PurchaseBill.status,      'type': 'string'},
        },
        # === PRODUCT / INVENTORY MODULE ===
        'product': {
            'name':     {'expr': lambda: Product.name,       'type': 'string'},
            'sku':      {'expr': lambda: Product.sku,        'type': 'string'},
            'price':    {'expr': lambda: Product.unit_price, 'type': 'number'},
            'cost':     {'expr': lambda: Product.cost_price, 'type': 'number'},
            'quantity': {'expr': lambda: Product.quantity,   'type': 'number'},
            'min_quantity': {'expr': lambda: Product.min_quantity, 'type': 'number'},
            'max_quantity': {'expr': lambda: Product.max_quantity, 'type': 'number'},
            'category': {'expr': lambda: ProductCategory.name, 'type': 'string', 'join': ProductCategory, 'options_route': 'filters.get_product_categories'},
            'is_active': {'expr': lambda: Product.is_active, 'type': 'boolean'},
        },
        # === VENDOR MODULE ===
        'vendor': {
            'name':     {'expr': lambda: Vendor.name,  'type': 'string'},
            'email':    {'expr': lambda: Vendor.email, 'type': 'string'},
            'phone':    {'expr': lambda: Vendor.phone, 'type': 'string'},
            'gst_number': {'expr': lambda: Vendor.gst_number, 'type': 'string'},
            'is_active': {'expr': lambda: Vendor.is_active, 'type': 'boolean'},
        },
        # === CUSTOMER MODULE ===
        'customer': {
            'name':     {'expr': lambda: Customer.name,  'type': 'string'},
            'email':    {'expr': lambda: Customer.email, 'type': 'string'},
            'phone':    {'expr': lambda: Customer.phone, 'type': 'string'},
            'gst_number': {'expr': lambda: Customer.gst_number, 'type': 'string'},
            'is_active': {'expr': lambda: Customer.is_active, 'type': 'boolean'},
            'customer_group': {'expr': lambda: CustomerGroup.name, 'type': 'string', 'join': CustomerGroup, 'options_route': 'filters.get_customer_groups'},
        },
        # === STAFF MODULE ===
        'staff': {
            'name':       {'expr': lambda: Staff.name,         'type': 'string'},
            'designation':{'expr': lambda: Staff.designation,  'type': 'string'},
            'phone':      {'expr': lambda: Staff.phone,        'type': 'string'},
            'monthly_salary': {'expr': lambda: Staff.monthly_salary, 'type': 'number'},
            'is_active':  {'expr': lambda: Staff.is_active,    'type': 'boolean'},
        },
        # === MANUFACTURING ORDER MODULE ===
        'manufacturing_order': {
            'order_number':     {'expr': lambda: ManufacturingOrder.order_number,     'type': 'string'},
            'start_date':       {'expr': lambda: ManufacturingOrder.start_date,       'type': 'date'},
            'end_date':         {'expr': lambda: ManufacturingOrder.end_date,         'type': 'date'},
            'year':             {'expr': lambda: func.extract('year', ManufacturingOrder.start_date), 'type': 'number'},
            'quantity':         {'expr': lambda: ManufacturingOrder.quantity_to_produce, 'type': 'number'},
            'total_cost':       {'expr': lambda: ManufacturingOrder.total_cost,       'type': 'number'},
            'material_cost':    {'expr': lambda: ManufacturingOrder.actual_material_cost, 'type': 'number'},
            'labor_cost':       {'expr': lambda: ManufacturingOrder.actual_labor_cost, 'type': 'number'},
            'overhead_cost':    {'expr': lambda: ManufacturingOrder.actual_overhead_cost, 'type': 'number'},
            'status':           {'expr': lambda: ManufacturingOrder.status,           'type': 'string'},
        },
        # === BOM MODULE ===
        'bom': {
            'name':       {'expr': lambda: BOM.name,       'type': 'string'},
            'version':    {'expr': lambda: BOM.version,    'type': 'string'},
            'labor_cost': {'expr': lambda: BOM.labor_cost, 'type': 'number'},
            'overhead_cost': {'expr': lambda: BOM.overhead_cost, 'type': 'number'},
            'total_cost': {'expr': lambda: BOM.total_cost, 'type': 'number'},
            'is_active':  {'expr': lambda: BOM.is_active,  'type': 'boolean'},
        },
        # === SALE RETURN MODULE ===
        'sale_return': {
            'return_number': {'expr': lambda: SaleReturn.return_number, 'type': 'string'},
            'date':          {'expr': lambda: SaleReturn.date,          'type': 'date'},
            'year':          {'expr': lambda: func.extract('year', SaleReturn.date), 'type': 'number'},
            'subtotal':      {'expr': lambda: SaleReturn.subtotal,      'type': 'number'},
            'tax':           {'expr': lambda: SaleReturn.tax,           'type': 'number'},
            'total':         {'expr': lambda: SaleReturn.total,         'type': 'number'},
            'status':        {'expr': lambda: SaleReturn.status,        'type': 'string'},
        },
        # === PURCHASE RETURN MODULE ===
        'purchase_return': {
            'return_number': {'expr': lambda: PurchaseReturn.return_number, 'type': 'string'},
            'date':          {'expr': lambda: PurchaseReturn.date,          'type': 'date'},
            'year':          {'expr': lambda: func.extract('year', PurchaseReturn.date), 'type': 'number'},
            'subtotal':      {'expr': lambda: PurchaseReturn.subtotal,      'type': 'number'},
            'tax':           {'expr': lambda: PurchaseReturn.tax,           'type': 'number'},
            'total':         {'expr': lambda: PurchaseReturn.total,         'type': 'number'},
            'status':        {'expr': lambda: PurchaseReturn.status,        'type': 'string'},
        },
        # === PURCHASE ORDER MODULE ===
        'purchase_order': {
            'po_number':  {'expr': lambda: PurchaseOrder.po_number,  'type': 'string'},
            'date':       {'expr': lambda: PurchaseOrder.date,       'type': 'date'},
            'year':       {'expr': lambda: func.extract('year', PurchaseOrder.date), 'type': 'number'},
            'total':      {'expr': lambda: PurchaseOrder.total,      'type': 'number'},
            'status':     {'expr': lambda: PurchaseOrder.status,     'type': 'string'},
        },
        # === PRODUCTION LOG MODULE ===
        'production_log': {
            'date':       {'expr': lambda: ProductionLog.date,       'type': 'date'},
            'year':       {'expr': lambda: func.extract('year', ProductionLog.date), 'type': 'number'},
            'shift':      {'expr': lambda: ProductionLog.shift,      'type': 'string'},
            'operator':   {'expr': lambda: ProductionLog.operator,   'type': 'string'},
            'qty_produced': {'expr': lambda: ProductionLog.qty_produced, 'type': 'number'},
            'rejected_qty': {'expr': lambda: ProductionLog.rejected_qty, 'type': 'number'},
        },
        # === SALARY PAYMENT MODULE ===
        'salary_payment': {
            'payment_date': {'expr': lambda: SalaryPayment.payment_date, 'type': 'date'},
            'year':         {'expr': lambda: func.extract('year', SalaryPayment.payment_date), 'type': 'number'},
            'month':        {'expr': lambda: SalaryPayment.month,      'type': 'number'},
            'base_salary':  {'expr': lambda: SalaryPayment.base_salary, 'type': 'number'},
            'bonus':        {'expr': lambda: SalaryPayment.bonus,      'type': 'number'},
            'net_salary':   {'expr': lambda: SalaryPayment.net_salary, 'type': 'number'},
            'status':       {'expr': lambda: SalaryPayment.status,     'type': 'string'},
        },
        # === COGS REPORT MODULE (filters SaleItem via Sale/Product joins) ===
        'cogs_report': {
            'product_name': {'expr': lambda: Product.name, 'type': 'string', 'join': Product},
            'sku':          {'expr': lambda: Product.sku, 'type': 'string', 'join': Product},
            'category':     {'expr': lambda: ProductCategory.name, 'type': 'string', 'join': ProductCategory},
            'date':         {'expr': lambda: Sale.date, 'type': 'date', 'join': Sale},
            'amount':       {'expr': lambda: SaleItem.total, 'type': 'number'},
            'quantity':     {'expr': lambda: SaleItem.quantity, 'type': 'number'},
        },
        # === PROFIT & LOSS REPORT MODULE (primary: Sale model) ===
        'profit_loss_report': {
            'invoice_number': {'expr': lambda: Sale.invoice_number, 'type': 'string'},
            'date':           {'expr': lambda: Sale.date, 'type': 'date'},
            'amount':         {'expr': lambda: Sale.total, 'type': 'number'},
            'customer':       {'expr': lambda: Customer.name, 'type': 'string', 'join': Customer},
            'status':         {'expr': lambda: Sale.status, 'type': 'string'},
        },
        # === REPORT MODULE ALIASES (mirror base model fields) ===
        'sales_report': {
            'invoice_number': {'expr': lambda: Sale.invoice_number, 'type': 'string'},
            'date':           {'expr': lambda: Sale.date,            'type': 'date'},
            'year':           {'expr': lambda: func.extract('year', Sale.date), 'type': 'number'},
            'amount':         {'expr': lambda: Sale.total,           'type': 'number'},
            'subtotal':       {'expr': lambda: Sale.subtotal,        'type': 'number'},
            'tax':            {'expr': lambda: Sale.tax,             'type': 'number'},
            'paid_amount':    {'expr': lambda: Sale.paid_amount,     'type': 'number'},
            'balance_due':    {'expr': lambda: Sale.balance_due,     'type': 'number'},
            'customer':       {'expr': lambda: Customer.name,        'type': 'string', 'join': Customer, 'options_route': 'filters.get_customers'},
            'status':         {'expr': lambda: Sale.status,          'type': 'string'},
            'salesman':       {'expr': lambda: Sale.salesman_id,     'type': 'number', 'options_route': 'filters.get_salesmen'},
            'salesman_group': {'expr': lambda: SalesmanGroup.name,      'type': 'string', 'join': [Salesman, SalesmanGroup], 'options_route': 'filters.get_salesman_groups'},
            'customer_group': {'expr': lambda: CustomerGroup.name,      'type': 'string', 'join': [Customer, CustomerGroup], 'options_route': 'filters.get_customer_groups'},
        },
        'purchase_report': {
            'bill_number':  {'expr': lambda: PurchaseBill.bill_number, 'type': 'string'},
            'date':         {'expr': lambda: PurchaseBill.date,        'type': 'date'},
            'year':         {'expr': lambda: func.extract('year', PurchaseBill.date), 'type': 'number'},
            'amount':       {'expr': lambda: PurchaseBill.total,       'type': 'number'},
            'subtotal':     {'expr': lambda: PurchaseBill.subtotal,    'type': 'number'},
            'tax':          {'expr': lambda: PurchaseBill.tax,         'type': 'number'},
            'paid_amount':  {'expr': lambda: PurchaseBill.paid_amount, 'type': 'number'},
            'balance_due':  {'expr': lambda: PurchaseBill.balance_due, 'type': 'number'},
            'vendor':       {'expr': lambda: Vendor.name,              'type': 'string', 'join': Vendor},
            'status':       {'expr': lambda: PurchaseBill.status,      'type': 'string'},
        },
        'inventory_report': {
            'name':     {'expr': lambda: Product.name,       'type': 'string'},
            'sku':      {'expr': lambda: Product.sku,        'type': 'string'},
            'price':    {'expr': lambda: Product.unit_price, 'type': 'number'},
            'cost':     {'expr': lambda: Product.cost_price, 'type': 'number'},
            'quantity': {'expr': lambda: Product.quantity,   'type': 'number'},
            'min_quantity': {'expr': lambda: Product.min_quantity, 'type': 'number'},
            'max_quantity': {'expr': lambda: Product.max_quantity, 'type': 'number'},
            'category': {'expr': lambda: ProductCategory.name, 'type': 'string', 'join': ProductCategory},
            'is_active': {'expr': lambda: Product.is_active, 'type': 'boolean'},
        },
        'expense_report': {
            'name':         {'expr': lambda: Expense.expense_number, 'type': 'string'},
            'date':         {'expr': lambda: Expense.date,           'type': 'date'},
            'year':         {'expr': lambda: func.extract('year', Expense.date), 'type': 'number'},
            'amount':       {'expr': lambda: Expense.amount,         'type': 'number'},
            'category':     {'expr': lambda: ExpenseCategory.name,   'type': 'string', 'join': ExpenseCategory, 'options_route': 'filters.get_expense_categories'},
            'payment_mode': {'expr': lambda: Expense.payment_method,'type': 'string', 'options_route': 'filters.get_payment_methods'},
            'billable':     {'expr': lambda: Expense.is_bom_overhead,'type': 'boolean'},
            'recurring':    {'expr': lambda: Expense.is_monthly_divided, 'type': 'boolean'},
        },
        'return_report': {
            'return_number': {'expr': lambda: SaleReturn.return_number, 'type': 'string'},
            'date':          {'expr': lambda: SaleReturn.date,          'type': 'date'},
            'year':          {'expr': lambda: func.extract('year', SaleReturn.date), 'type': 'number'},
            'subtotal':      {'expr': lambda: SaleReturn.subtotal,      'type': 'number'},
            'tax':           {'expr': lambda: SaleReturn.tax,           'type': 'number'},
            'total':         {'expr': lambda: SaleReturn.total,         'type': 'number'},
            'status':        {'expr': lambda: SaleReturn.status,        'type': 'string'},
        },
        'manufacturing_report': {
            'order_number':     {'expr': lambda: ManufacturingOrder.order_number,     'type': 'string'},
            'start_date':       {'expr': lambda: ManufacturingOrder.start_date,       'type': 'date'},
            'end_date':         {'expr': lambda: ManufacturingOrder.end_date,         'type': 'date'},
            'year':             {'expr': lambda: func.extract('year', ManufacturingOrder.start_date), 'type': 'number'},
            'quantity':         {'expr': lambda: ManufacturingOrder.quantity_to_produce, 'type': 'number'},
            'total_cost':       {'expr': lambda: ManufacturingOrder.total_cost,       'type': 'number'},
            'material_cost':    {'expr': lambda: ManufacturingOrder.actual_material_cost, 'type': 'number'},
            'labor_cost':       {'expr': lambda: ManufacturingOrder.actual_labor_cost, 'type': 'number'},
            'overhead_cost':    {'expr': lambda: ManufacturingOrder.actual_overhead_cost, 'type': 'number'},
            'status':           {'expr': lambda: ManufacturingOrder.status,           'type': 'string'},
        },
        'bom_report': {
            'name':       {'expr': lambda: BOM.name,       'type': 'string'},
            'version':    {'expr': lambda: BOM.version,    'type': 'string'},
            'labor_cost': {'expr': lambda: BOM.labor_cost, 'type': 'number'},
            'overhead_cost': {'expr': lambda: BOM.overhead_cost, 'type': 'number'},
            'total_cost': {'expr': lambda: BOM.total_cost, 'type': 'number'},
            'is_active':  {'expr': lambda: BOM.is_active,  'type': 'boolean'},
        },
        'salary_report': {
            'payment_date': {'expr': lambda: SalaryPayment.payment_date, 'type': 'date'},
            'year':         {'expr': lambda: func.extract('year', SalaryPayment.payment_date), 'type': 'number'},
            'month':        {'expr': lambda: SalaryPayment.month,      'type': 'number'},
            'base_salary':  {'expr': lambda: SalaryPayment.base_salary, 'type': 'number'},
            'bonus':        {'expr': lambda: SalaryPayment.bonus,      'type': 'number'},
            'net_salary':   {'expr': lambda: SalaryPayment.net_salary, 'type': 'number'},
            'status':       {'expr': lambda: SalaryPayment.status,     'type': 'string'},
        },
        'vendor_report': {
            'name':     {'expr': lambda: Vendor.name,  'type': 'string'},
            'email':    {'expr': lambda: Vendor.email, 'type': 'string'},
            'phone':    {'expr': lambda: Vendor.phone, 'type': 'string'},
            'gst_number': {'expr': lambda: Vendor.gst_number, 'type': 'string'},
            'is_active': {'expr': lambda: Vendor.is_active, 'type': 'boolean'},
        },
        'customer_report': {
            'name':     {'expr': lambda: Customer.name,  'type': 'string'},
            'email':    {'expr': lambda: Customer.email, 'type': 'string'},
            'phone':    {'expr': lambda: Customer.phone, 'type': 'string'},
            'gst_number': {'expr': lambda: Customer.gst_number, 'type': 'string'},
            'is_active': {'expr': lambda: Customer.is_active, 'type': 'boolean'},
            'customer_group': {'expr': lambda: CustomerGroup.name, 'type': 'string', 'join': CustomerGroup, 'options_route': 'filters.get_customer_groups'},
        },
    }


_FIELD_REGISTRY = None


def get_field_registry():
    global _FIELD_REGISTRY
    if _FIELD_REGISTRY is None:
        _FIELD_REGISTRY = _build_field_registry()
    return _FIELD_REGISTRY


def get_field_config(module, field_key):
    registry = get_field_registry()
    mod_cfg = registry.get(module)
    if not mod_cfg:
        raise ValueError(f"Unknown module: {module}")
    cfg = mod_cfg.get(field_key)
    if not cfg:
        raise ValueError(f"Unknown field '{field_key}' for module '{module}'")
    return cfg


def validate_rules(rules_json, module):
    if not isinstance(rules_json, dict):
        return False, "Rules must be a JSON object"
    condition = rules_json.get('condition', 'AND')
    if condition not in ('AND', 'OR'):
        return False, "condition must be AND or OR"
    rules = rules_json.get('rules')
    if rules is None:
        return False, "rules key is required"
    if not isinstance(rules, list):
        return False, "rules must be a list"

    registry = get_field_registry()
    mod_cfg = registry.get(module)
    if not mod_cfg:
        return False, f"Unknown module: {module}"

    def _validate_node(node):
        if not isinstance(node, dict):
            return False, "Each rule must be an object"
        if 'condition' in node and 'rules' in node:
            return validate_rules(node, module)
        field = node.get('field')
        op = node.get('operator')
        value = node.get('value')
        if field is None:
            return False, "field is required"
        if op is None:
            return False, "operator is required"
        if field not in mod_cfg:
            return False, f"Unknown field: {field}"
        mapped_op = OPERATOR_MAP.get(op, op)
        if mapped_op not in VALID_OPERATORS:
            return False, f"Unknown operator: {op}"
        cfg = mod_cfg[field]
        ftype = cfg['type']
        if mapped_op in ('in', 'not_in') and not isinstance(value, list):
            return False, f"Operator '{op}' requires a list value"
        if mapped_op == 'date_between':
            if not isinstance(value, list) or len(value) != 2:
                return False, f"Operator '{op}' requires an array of two dates [from, to]"
        if ftype == 'boolean':
            if value not in (True, False, 0, 1, 'true', 'false', 'True', 'False'):
                return False, f"Boolean field '{field}' requires true/false"
        return True, None

    for r in rules:
        ok, err = _validate_node(r)
        if not ok:
            return False, err
    return True, None


def _coerce_value(value, ftype):
    if value is None:
        return None
    if ftype == 'string':
        return str(value)
    if ftype == 'number':
        try:
            val = float(value)
            if val.is_integer():
                return int(val)
            return val
        except (ValueError, TypeError):
            raise ValueError(f"Invalid number: {value}")
    if ftype == 'boolean':
        if isinstance(value, bool):
            return value
        if value in (1, '1', 'true', 'True', 'yes', 'YES'):
            return True
        if value in (0, '0', 'false', 'False', 'no', 'NO'):
            return False
        raise ValueError(f"Invalid boolean: {value}")
    if ftype == 'date':
        from datetime import datetime
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        raise ValueError(f"Invalid date: {value}")
    return value


def _build_filter_expression(field_key, operator, value, module):
    cfg = get_field_config(module, field_key)
    expr = cfg['expr']()
    ftype = cfg['type']
    op = OPERATOR_MAP.get(operator, operator)

    if op == 'date_between':
        from datetime import datetime, timedelta
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("date_between requires [from_date, to_date]")
        from_date = _coerce_value(value[0], 'date')
        to_date = _coerce_value(value[1], 'date')
        # Include the full end date
        to_date = to_date.replace(hour=23, minute=59, second=59)
        return and_(expr >= from_date, expr <= to_date)

    coerced = _coerce_value(value, ftype)

    if op == 'equal':
        if ftype == 'string':
            return func.lower(expr) == func.lower(coerced)
        if ftype == 'date':
            # Date equality should cover the whole day
            from datetime import timedelta
            next_day = coerced + timedelta(days=1)
            return and_(expr >= coerced, expr < next_day)
        return expr == coerced
    if op == 'not_equal':
        if ftype == 'string':
            return func.lower(expr) != func.lower(coerced)
        if ftype == 'date':
            from datetime import timedelta
            next_day = coerced + timedelta(days=1)
            return or_(expr < coerced, expr >= next_day)
        return expr != coerced
    if op == 'contains':
        return expr.ilike(f'%{coerced}%')
    if op == 'not_contains':
        return ~expr.ilike(f'%{coerced}%')
    if op == 'begins_with':
        return expr.ilike(f'{coerced}%')
    if op == 'ends_with':
        return expr.ilike(f'%{coerced}')
    if op == '>':
        return expr > coerced
    if op == '<':
        return expr < coerced
    if op == '>=':
        return expr >= coerced
    if op == '<=':
        return expr <= coerced
    if op == 'in':
        return expr.in_(coerced)
    if op == 'not_in':
        return ~expr.in_(coerced)

    raise ValueError(f"Unhandled operator: {op}")


def _recursive_build_query(query, node, module, joined_models):
    if 'condition' in node and 'rules' in node:
        condition = node['condition']
        clauses = []
        for child in node['rules']:
            q = _recursive_build_query(query, child, module, joined_models)
            if q is not None:
                clauses.append(q)
        if not clauses:
            return None
        if condition == 'AND':
            return and_(*clauses)
        return or_(*clauses)

    field = node['field']
    op = node['operator']
    value = node['value']

    return _build_filter_expression(field, op, value, module)


def apply_filters(query, module, rules_json):
    ok, err = validate_rules(rules_json, module)
    if not ok:
        raise ValueError(err)

    rules = rules_json.get('rules', [])
    sort_field = rules_json.get('sort_field')
    if not rules and not sort_field:
        return query

    # Pass 1: Collect all required joins from the rule tree
    # We use a list to preserve the order (important for chained joins)
    required_joins = []
    
    def _collect(node):
        if node is None: return
        if 'rules' in node:
            for r in node['rules']: _collect(r)
        elif 'field' in node:
            cfg = get_field_config(module, node['field'])
            j = cfg.get('join')
            if j:
                if isinstance(j, list):
                    for m in j:
                        if m not in required_joins:
                            required_joins.append(m)
                elif j not in required_joins:
                    required_joins.append(j)
    
    _collect(rules_json)
    
    # Also collect joins for the sort field
    sort_field = rules_json.get('sort_field')
    if sort_field:
        cfg = get_field_config(module, sort_field)
        j = cfg.get('join')
        if j:
            if isinstance(j, list):
                for m in j:
                    if m not in required_joins: required_joins.append(m)
            elif j not in required_joins: required_joins.append(j)

    # Apply joins to the query object sequentially
    for model_cls in required_joins:
        query = query.outerjoin(model_cls)

    # Pass 2: Build the filter expressions
    joined_models = set(required_joins)
    condition = rules_json.get('condition', 'AND')
    clauses = []

    for node in rules:
        clause = _recursive_build_query(query, node, module, joined_models)
        if clause is not None:
            clauses.append(clause)

    if clauses:
        if condition == 'AND':
            query = query.filter(and_(*clauses))
        else:
            query = query.filter(or_(*clauses))

    # Finally, apply sorting if requested
    if sort_field:
        sort_order = rules_json.get('sort_order', 'asc').lower()
        cfg = get_field_config(module, sort_field)
        expr = cfg['expr']()
        
        # Clear existing order_by to make advanced filter sort primary
        query = query.order_by(None)
        if sort_order == 'desc':
            query = query.order_by(expr.desc())
        else:
            query = query.order_by(expr.asc())

    return query


def get_module_fields(module):
    registry = get_field_registry()
    mod_cfg = registry.get(module)
    if not mod_cfg:
        return []
    result = []
    for key, cfg in mod_cfg.items():
        result.append({
            'key': key,
            'type': cfg['type'],
            'label': key.replace('_', ' ').title(),
            'options_route': cfg.get('options_route')
        })
    return result

