from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, TextAreaField, DateField, FileField
from wtforms.validators import DataRequired, Email, Optional, NumberRange
from wtforms.fields import DateTimeField

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    sku = StringField('SKU', validators=[DataRequired()])
    description = TextAreaField('Description')
    unit_price = FloatField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    cost_price = FloatField('Cost Price', validators=[DataRequired(), NumberRange(min=0)])
    quantity = FloatField('Initial Quantity', default=0)
    reorder_level = FloatField('Reorder Level', default=0)
    category = StringField('Category')
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