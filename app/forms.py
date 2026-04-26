from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, TextAreaField, DateField, FileField, BooleanField, DecimalField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, EqualTo, InputRequired
from wtforms.fields import DateTimeField
from datetime import datetime
from decimal import Decimal
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    sku = StringField('SKU', validators=[DataRequired()])
    description = TextAreaField('Description')
    unit_price = FloatField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    cost_price = FloatField('Cost Price', validators=[Optional(), NumberRange(min=0)])
    quantity = FloatField('Initial Quantity', default=0)
    reorder_level = FloatField('Reorder Level', default=0)
    category = StringField('Category')
    is_manufactured = BooleanField('Manufactured Product')
    image = FileField('Product Image', validators=[Optional()])

class WarehouseForm(FlaskForm):
    name = StringField('Warehouse Name', validators=[DataRequired()])
    address = TextAreaField('Address')
    manager = StringField('Manager')
    capacity = FloatField('Capacity', validators=[Optional(), NumberRange(min=0)])

def get_warehouse_choices(warehouses=None):
    if warehouses is None:
        return [(0, 'No Warehouse')]
    return [(0, 'No Warehouse')] + [(w.id, w.name) for w in warehouses]

class InvoiceSettingsForm(FlaskForm):
    default_notes = TextAreaField('Default Invoice Notes')
    default_terms = TextAreaField('Default Terms & Conditions')
    bank_name = StringField('Bank Name')
    account_holder_name = StringField('Account Holder Name')
    account_number = StringField('Account Number')
    ifsc_code = StringField('IFSC Code')
    swift_code = StringField('SWIFT Code')
    bank_address = TextAreaField('Bank Address')
    payment_instructions = TextAreaField('Payment Instructions')
    invoice_prefix = StringField('Invoice Prefix')
    invoice_suffix = StringField('Invoice Suffix')
    next_number = IntegerField('Next Invoice Number', default=1)
    tax_name = StringField('Tax Name', default='GST')
    tax_rate = DecimalField('Tax Rate (%)', default=lambda: Decimal('10'))
    payment_terms = TextAreaField('Payment Terms')
    notes = TextAreaField('Notes')

class PurchaseSettingsForm(FlaskForm):
    default_notes = TextAreaField('Default Purchase Bill Notes')
    default_terms = TextAreaField('Default Terms & Conditions (Policy)')
    bill_prefix = StringField('Bill Prefix', default='PB-')
    bill_suffix = StringField('Bill Suffix')
    next_bill_number = IntegerField('Next Bill Number', default=1)
    po_prefix = StringField('Purchase Order Prefix', default='PO-')
    po_suffix = StringField('Purchase Order Suffix')
    next_po_number = IntegerField('Next PO Number', default=1)

class ExpenseSettingsForm(FlaskForm):
    expense_prefix = StringField('Expense Prefix', default='EXP-')
    expense_suffix = StringField('Expense Suffix')
    next_number = IntegerField('Next Expense Number', default=1)

class SaleReturnSettingsForm(FlaskForm):
    return_prefix = StringField('Sale Return Prefix', default='RET-')
    return_suffix = StringField('Sale Return Suffix')
    next_number = IntegerField('Next Sale Return Number', default=1)

class PurchaseReturnSettingsForm(FlaskForm):
    return_prefix = StringField('Purchase Return Prefix', default='PRet-')
    return_suffix = StringField('Purchase Return Suffix')
    next_number = IntegerField('Next Purchase Return Number', default=1)

class SaleForm(FlaskForm):
    customer_id = SelectField('Customer', coerce=int, validators=[DataRequired()])
    salesman_id = SelectField('Salesman', coerce=int, validators=[Optional()])
    date = DateField('Date', validators=[DataRequired()])

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    phone = StringField('Phone')
    address = TextAreaField('Address')
    gst_number = StringField('GST Number')
    payment_method = StringField('Payment Method', validators=[Optional()])

class PurchaseForm(FlaskForm):
    vendor_id = SelectField('Vendor', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    bill_image = FileField('Bill Image', validators=[Optional()])

class VendorForm(FlaskForm):
    name = StringField('Vendor Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    phone = StringField('Phone')
    address = TextAreaField('Address')
    shipping_address = TextAreaField(' Shipping Address')
    gst_number = StringField('GST Number')
    payment_method = StringField('Payment Method', validators=[Optional()])

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = StringField('Password', validators=[DataRequired(message='Password is required')])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('manager', 'Manager'), ('user', 'Staff')], validators=[DataRequired()])
    is_active = SelectField('Status', choices=[('True', 'Active'), ('False', 'Inactive')], default='True', coerce=lambda x: x == 'True', validators=[InputRequired()])
    can_view_sales = BooleanField('Sales Access', default=True)
    can_view_purchases = BooleanField('Purchases Access', default=True)
    can_view_inventory = BooleanField('Inventory Access', default=True)
    can_view_expenses = BooleanField('Expenses Access', default=True)
    can_view_returns = BooleanField('Returns Access', default=True)
    can_view_vendors = BooleanField('Vendors Access', default=True)
    can_view_customers = BooleanField('Customers Access', default=True)
    can_view_reports = BooleanField('Reports Access', default=True)
    can_view_settings = BooleanField('Settings Access', default=True)
    can_view_manufacturing = BooleanField('Manufacturing Access', default=True)
    can_view_production = BooleanField('Production Access', default=True)
    can_view_warehouse = BooleanField('Warehouse Access', default=True)
    can_view_attendance = BooleanField('Attendance Access', default=True)
    can_view_salary = BooleanField('Salary Access', default=True)
    can_view_targets = BooleanField('Targets Access', default=True)
    can_view_dashboard = BooleanField('Dashboard Access', default=True)
    can_view_accounting = BooleanField('Accounting Access', default=True)

class UserEditForm(FlaskForm):
    username = StringField('Username', validators=[Optional()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = StringField('Password', validators=[Optional()])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('manager', 'Manager'), ('user', 'Staff')], validators=[DataRequired()])
    is_active = SelectField('Status', choices=[('True', 'Active'), ('False', 'Inactive')], default='True', coerce=lambda x: x == 'True', validators=[InputRequired()])
    can_view_sales = BooleanField('Sales Access', default=True)
    can_view_purchases = BooleanField('Purchases Access', default=True)
    can_view_inventory = BooleanField('Inventory Access', default=True)
    can_view_expenses = BooleanField('Expenses Access', default=True)
    can_view_returns = BooleanField('Returns Access', default=True)
    can_view_vendors = BooleanField('Vendors Access', default=True)
    can_view_customers = BooleanField('Customers Access', default=True)
    can_view_reports = BooleanField('Reports Access', default=True)
    can_view_settings = BooleanField('Settings Access', default=True)
    can_view_manufacturing = BooleanField('Manufacturing Access', default=True)
    can_view_production = BooleanField('Production Access', default=True)
    can_view_warehouse = BooleanField('Warehouse Access', default=True)
    can_view_attendance = BooleanField('Attendance Access', default=True)
    can_view_salary = BooleanField('Salary Access', default=True)
    can_view_targets = BooleanField('Targets Access', default=True)
    can_view_dashboard = BooleanField('Dashboard Access', default=True)
    can_view_accounting = BooleanField('Accounting Access', default=True)

class TaskForm(FlaskForm):
    title = StringField('Task Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    priority = SelectField('Priority', choices=[('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')], default='Medium')
    status = SelectField('Status', choices=[('Pending', 'Pending'), ('In Progress', 'In Progress'), ('Completed', 'Completed'), ('Cancelled', 'Cancelled')], default='Pending')
    due_date = DateField('Due Date', validators=[Optional()])
    assigned_to_id = SelectField('Assign To', coerce=int, validators=[DataRequired()])

class BOMForm(FlaskForm):
    name = StringField('BOM Name', validators=[DataRequired()])
    product_id = SelectField('Finished Product', coerce=int, validators=[DataRequired()])
    labor_cost = FloatField('Total Labor Cost', default=0, validators=[Optional(), NumberRange(min=0)])
    overhead_cost = FloatField('Overhead Cost', default=0, validators=[Optional(), NumberRange(min=0)])

class ManufacturingOrderForm(FlaskForm):
    bom_id = SelectField('Bill of Materials', coerce=int, validators=[DataRequired()])
    quantity_to_produce = FloatField('Quantity to Produce', validators=[DataRequired(), NumberRange(min=0.1)])
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])

class StaffForm(FlaskForm):
    name = StringField('Staff Name', validators=[DataRequired()])
    designation = StringField('Designation')
    monthly_salary = FloatField('Monthly Salary', validators=[DataRequired(), NumberRange(min=0)])
    joining_date = DateField('Joining Date', validators=[Optional()])
    is_active = BooleanField('Active', default=True)

class SalaryAdvanceForm(FlaskForm):
    staff_id = SelectField('Staff', coerce=int, validators=[DataRequired()])
    amount = FloatField('Advance Amount', validators=[DataRequired(), NumberRange(min=1)])
    date = DateField('Date', validators=[DataRequired()])
    description = TextAreaField('Description')

class SalaryPaymentForm(FlaskForm):
    staff_id = SelectField('Staff', coerce=int, validators=[DataRequired()])
    month = SelectField('Month', coerce=int, choices=[(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)], validators=[DataRequired()])
    year = IntegerField('Year', validators=[DataRequired()])
    base_salary = FloatField('Base Salary', validators=[DataRequired(), NumberRange(min=0)])
    advance_deduction = FloatField('Advance Deduction', default=0)
    bonus = FloatField('Bonus', default=0)
    other_deductions = FloatField('Other Deductions', default=0)
    payment_date = DateField('Payment Date', validators=[DataRequired()])
    payment_method = StringField('Payment Method', default='Cash')
    status = SelectField('Status', choices=[('paid', 'Paid'), ('pending', 'Pending')], default='paid')
    notes = TextAreaField('Notes')

class AttendanceForm(FlaskForm):
    staff_id = SelectField('Staff', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    status = SelectField('Status', choices=[('Present', 'Present'), ('Absent', 'Absent'), ('Leave', 'Leave')], validators=[DataRequired()])

class ExpenseForm(FlaskForm):
    reference = StringField('Reference')
    description = StringField('Description', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    date = DateField('Date', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    vendor_id = SelectField('Vendor (Optional)', coerce=int, validators=[Optional()])
    payment_method = SelectField('Payment Method', choices=[])
    notes = TextAreaField('Notes')
    product_id = SelectMultipleField('Product (Optional)', coerce=int, validators=[Optional()])


    bom_id = SelectMultipleField('BOM (Optional)', coerce=int, validators=[Optional()])
    bill_image = FileField('Bill Image', validators=[Optional()])
    is_monthly_divided = BooleanField('Is Monthly Divided', default=False)
    monthly_start_date = DateField('Monthly Start Date', validators=[Optional()])
    monthly_end_date = DateField('Monthly End Date', validators=[Optional()])
    is_bom_overhead = BooleanField('Is BOM Overhead', default=False)
    mo_id = SelectMultipleField('Manufacturing Order (Optional)', coerce=int, validators=[Optional()])

class PaymentMethodForm(FlaskForm):
    name = StringField('Payment Method Name', validators=[DataRequired()])
    description = TextAreaField('Description')

class ExpenseCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    expense_type = SelectField('Type', choices=[('operational', 'Operational'), ('capital', 'Capital'), ('maintenance', 'Maintenance')], default='operational')

class AccountForm(FlaskForm):
    name = StringField('Account Name', validators=[DataRequired()])
    account_type = SelectField('Type', choices=[('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Equity'), ('revenue', 'Revenue'), ('expense', 'Expense')], validators=[DataRequired()])
    description = TextAreaField('Description')

class TransactionForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    debit_account_id = SelectField('Debit Account', coerce=int, validators=[DataRequired()])
    credit_account_id = SelectField('Credit Account', coerce=int, validators=[DataRequired()])

class PaymentForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    date = DateField('Date', validators=[DataRequired()])
    payment_method = StringField('Payment Method')
    notes = TextAreaField('Notes')

class SalesmanForm(FlaskForm):
    name = StringField('Salesman Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    phone = StringField('Phone')
    address = TextAreaField('Address')
    commission_rate = FloatField('Commission Rate (%)', default=0, validators=[Optional(), NumberRange(min=0, max=100)])
    is_active = BooleanField('Active', default=True)