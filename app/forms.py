from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, TextAreaField, DateField, FileField, BooleanField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, EqualTo, InputRequired
from wtforms.fields import DateTimeField
from datetime import datetime

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    sku = StringField('SKU', validators=[DataRequired()])
    description = TextAreaField('Description')
    unit_price = FloatField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    cost_price = FloatField('Cost Price', validators=[Optional(), NumberRange(min=0)])
    quantity = FloatField('Initial Quantity', default=0)
    reorder_level = FloatField('Reorder Level', default=0)
    category = StringField('Category')
    is_manufactured = BooleanField('Is Manufactured Item', default=False)
    image = FileField('Product Image')

class VendorForm(FlaskForm):
    name = StringField('Vendor Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    phone = StringField('Phone')
    address = TextAreaField('Address')
    gst_number = StringField('GST Number')

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    phone = StringField('Phone')
    address = TextAreaField('Address')
    gst_number = StringField('GST Number')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])

class ExpenseForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    vendor_id = SelectField('Vendor (Optional)', coerce=int, validators=[Optional()])
    description = TextAreaField('Description')
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    payment_method = StringField('Payment Method')
    reference = StringField('Reference')
    bill_image = FileField('Bill Image')
    notes = TextAreaField('Notes')
    is_bom_overhead = BooleanField('BOM Overhead Expense', default=False)
    product_id = SelectField('Linked Finished Product (Overhead)', coerce=int, validators=[Optional()])

class ExpenseCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired()])
    description = TextAreaField('Description')

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

class SaleForm(FlaskForm):
    customer_id = SelectField('Customer', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    # Items will be handled dynamically

class PurchaseForm(FlaskForm):
    vendor_id = SelectField('Vendor', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = StringField('Password', validators=[DataRequired(message='Password is required')])  # Required for new users
    role = SelectField('Role', choices=[('admin', 'Admin'), ('manager', 'Manager'), ('user', 'Staff')], validators=[DataRequired()])
    is_active = SelectField('Status', choices=[('True', 'Active'), ('False', 'Inactive')], default='True', coerce=lambda x: x == 'True', validators=[InputRequired()])
    
    # Permissions
    can_view_sales = BooleanField('Sales Access', default=True)
    can_view_purchases = BooleanField('Purchases Access', default=True)
    can_view_inventory = BooleanField('Inventory Access', default=True)
    can_view_expenses = BooleanField('Expenses Access', default=True)
    can_view_returns = BooleanField('Returns Access', default=True)
    can_view_vendors = BooleanField('Vendors Access', default=True)
    can_view_customers = BooleanField('Customers Access', default=True)
    can_view_reports = BooleanField('Reports Access', default=True)
    can_view_settings = BooleanField('Settings Access', default=True)

class UserEditForm(FlaskForm):
    username = StringField('Username', validators=[Optional()])  # Not editable, so optional
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = StringField('Password', validators=[Optional()])  # Optional for edit
    role = SelectField('Role', choices=[('admin', 'Admin'), ('manager', 'Manager'), ('user', 'Staff')], validators=[DataRequired()])
    is_active = SelectField('Status', choices=[('True', 'Active'), ('False', 'Inactive')], default='True', coerce=lambda x: x == 'True', validators=[InputRequired()])
    
    # Permissions
    can_view_sales = BooleanField('Sales Access', default=True)
    can_view_purchases = BooleanField('Purchases Access', default=True)
    can_view_inventory = BooleanField('Inventory Access', default=True)
    can_view_expenses = BooleanField('Expenses Access', default=True)
    can_view_returns = BooleanField('Returns Access', default=True)
    can_view_vendors = BooleanField('Vendors Access', default=True)
    can_view_customers = BooleanField('Customers Access', default=True)
    can_view_reports = BooleanField('Reports Access', default=True)
    can_view_settings = BooleanField('Settings Access', default=True)

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