from app import db
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import Enum, func
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, manager, user
    is_active = db.Column(db.Boolean, default=True)
    
    # Permissions
    can_view_sales = db.Column(db.Boolean, default=True)
    can_view_purchases = db.Column(db.Boolean, default=True)
    can_view_inventory = db.Column(db.Boolean, default=True)
    can_view_expenses = db.Column(db.Boolean, default=True)
    can_view_vendors = db.Column(db.Boolean, default=True)
    can_view_customers = db.Column(db.Boolean, default=True)
    can_view_reports = db.Column(db.Boolean, default=True)
    can_view_settings = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_sales = db.relationship('Sale', backref='created_by_user', foreign_keys='Sale.created_by', lazy=True)
    created_purchases = db.relationship('PurchaseBill', backref='created_by_user', foreign_keys='PurchaseBill.created_by', lazy=True)
    assigned_tasks = db.relationship('Task', backref='assigned_to', foreign_keys='Task.assigned_to_id', lazy=True)
    tasks_created = db.relationship('Task', backref='created_by', foreign_keys='Task.created_by_id', lazy=True)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username}>'

class Vendor(db.Model):
    """Vendor/Supplier model"""
    __tablename__ = 'vendors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    gst_number = db.Column(db.String(20), index=True)
    pan_number = db.Column(db.String(20))
    contact_person = db.Column(db.String(100))
    payment_terms = db.Column(db.Integer, default=30)  # Days
    credit_limit = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bills = db.relationship('PurchaseBill', backref='vendor', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_purchases(self):
        return sum(bill.total for bill in self.bills)
    
    @property
    def outstanding_balance(self):
        return sum(bill.total - bill.paid_amount for bill in self.bills if bill.status != 'paid')
    
    def __repr__(self):
        return f'<Vendor {self.name}>'

class Customer(db.Model):
    """Customer model"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    gst_number = db.Column(db.String(20), index=True)
    credit_limit = db.Column(db.Float, default=0)
    opening_balance = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_sales(self):
        return sum(sale.total for sale in self.sales)
    
    @property
    def outstanding_balance(self):
        return sum(sale.total - sale.paid_amount for sale in self.sales if sale.status != 'paid')
    
    def __repr__(self):
        return f'<Customer {self.name}>'

class Product(db.Model):
    """Product/Inventory model"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    barcode = db.Column(db.String(50), index=True)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), index=True)
    brand = db.Column(db.String(50))
    unit = db.Column(db.String(20), default='pcs')  # pcs, kg, meter, etc.
    unit_price = db.Column(db.Float, nullable=False, default=0)
    cost_price = db.Column(db.Float, nullable=False, default=0)
    quantity = db.Column(db.Float, default=0)
    reorder_level = db.Column(db.Float, default=0)
    min_quantity = db.Column(db.Float, default=0)
    max_quantity = db.Column(db.Float, default=0)
    location = db.Column(db.String(100))
    weight = db.Column(db.Float, default=0)
    image_path = db.Column(db.String(255))  # Path to product image
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='product', lazy=True)
    purchase_items = db.relationship('PurchaseItem', backref='product', lazy=True)
    
    @property
    def stock_value(self):
        """Calculate total stock value at cost price"""
        return self.quantity * self.cost_price
    
    @property
    def sales_value(self):
        """Calculate potential sales value at selling price"""
        return self.quantity * self.unit_price
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price > 0:
            return ((self.unit_price - self.cost_price) / self.cost_price) * 100
        return 0
    
    @property
    def is_low_stock(self):
        """Check if product is low in stock"""
        return self.quantity <= self.reorder_level
    
    @property
    def is_out_of_stock(self):
        """Check if product is out of stock"""
        return self.quantity <= 0
    
    def update_quantity(self, quantity_change):
        """Update product quantity"""
        self.quantity += quantity_change
        self.updated_at = datetime.utcnow()
        return self.quantity
    
    def __repr__(self):
        return f'<Product {self.name} ({self.sku})>'

class Sale(db.Model):
    """Sales/Invoice model"""
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    due_date = db.Column(db.DateTime)
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), nullable=True)
    exchange_rate = db.Column(db.Float, default=1)
    subtotal = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)  # Tax percentage
    tax = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(10), default='fixed')  # fixed or percentage
    discount = db.Column(db.Float, default=0)
    shipping_charge = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(Enum('paid', 'unpaid', 'partial', name='payment_status'), default='unpaid', index=True)
    paid_amount = db.Column(db.Float, default=0)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), index=True, nullable=True)
    vendor = db.relationship('Vendor', backref='sales', lazy=True)
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')

    currency = db.relationship('Currency', backref='sales', lazy=True)
    
    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return self.total - self.paid_amount
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if self.status != 'paid' and self.due_date:
            return datetime.utcnow().date() > self.due_date.date()
        return False
    
    def update_status(self):
        """Update payment status based on paid amount"""
        if self.paid_amount >= self.total:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'unpaid'
        self.updated_at = datetime.utcnow()
    
    def calculate_totals(self):
        """Calculate invoice totals"""
        self.subtotal = sum(item.total for item in self.items)
        
        # Calculate tax
        self.tax = self.subtotal * (self.tax_rate / 100)
        
        # Calculate discount
        if self.discount_type == 'percentage':
            discount_amount = self.subtotal * (self.discount / 100)
        else:
            discount_amount = self.discount
        
        # Calculate total
        self.total = self.subtotal + self.tax + self.shipping_charge - discount_amount
        
        # Ensure total is not negative
        if self.total < 0:
            self.total = 0
    
    def __repr__(self):
        return f'<Sale {self.invoice_number}>'

class SaleItem(db.Model):
    """Sales item details"""
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    
    @property
    def net_total(self):
        """Calculate net total after discount"""
        return self.total - self.discount
    
    def __repr__(self):
        return f'<SaleItem {self.sale_id} - {self.product_id}>'

class PurchaseBill(db.Model):
    """Purchase Bill model"""
    __tablename__ = 'purchase_bills'
    
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    due_date = db.Column(db.DateTime)
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), nullable=True)
    exchange_rate = db.Column(db.Float, default=1)
    subtotal = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=10)
    tax = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(10), default='fixed')
    discount = db.Column(db.Float, default=0)
    shipping_charge = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(Enum('paid', 'unpaid', 'partial', name='payment_status'), default='unpaid', index=True)
    paid_amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('PurchaseItem', backref='bill', lazy=True, cascade='all, delete-orphan')

    currency = db.relationship('Currency', backref='purchase_bills', lazy=True)
    
    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return self.total - self.paid_amount
    
    @property
    def is_overdue(self):
        """Check if bill is overdue"""
        if self.status != 'paid' and self.due_date:
            return datetime.utcnow().date() > self.due_date.date()
        return False
    
    def update_status(self):
        """Update payment status based on paid amount"""
        if self.paid_amount >= self.total:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'unpaid'
        self.updated_at = datetime.utcnow()
    
    def calculate_totals(self):
        """Calculate bill totals"""
        self.subtotal = sum(item.total for item in self.items)
        
        # Calculate tax
        self.tax = self.subtotal * (self.tax_rate / 100)
        
        # Calculate discount
        if self.discount_type == 'percentage':
            discount_amount = self.subtotal * (self.discount / 100)
        else:
            discount_amount = self.discount
        
        # Calculate total
        self.total = self.subtotal + self.tax + self.shipping_charge - discount_amount
        
        # Ensure total is not negative
        if self.total < 0:
            self.total = 0
    
    def __repr__(self):
        return f'<PurchaseBill {self.bill_number}>'

class PurchaseItem(db.Model):
    """Purchase item details"""
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    
    @property
    def net_total(self):
        """Calculate net total after discount"""
        return self.total - self.discount
    
    def __repr__(self):
        return f'<PurchaseItem {self.bill_id} - {self.product_id}>'

class Transaction(db.Model):
    """Accounting transaction model"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), unique=True, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    amount = db.Column(db.Float, default=0)
    payment_mode = db.Column(db.String(30), default='Cash')
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True, index=True)
    status = db.Column(db.Enum('Completed', 'Pending', 'Failed', name='transaction_status'), default='Pending', index=True)
    is_mapped = db.Column(db.Boolean, default=False)
    reference_type = db.Column(Enum('sale', 'purchase', 'payment', 'expense', name='reference_type'), index=True)
    reference_id = db.Column(db.Integer, index=True)
    debit_account = db.Column(db.String(100), index=True)
    credit_account = db.Column(db.String(100), index=True)
    description = db.Column(db.String(200))
    account = db.Column(db.String(100), index=True)
    debit = db.Column(db.Float, default=0)
    credit = db.Column(db.Float, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoice = db.relationship('Sale', backref='transactions', lazy=True)
    
    def __repr__(self):
        return f'<Transaction {self.transaction_number}>'


class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    code = db.Column(db.String(50), unique=True, index=True)
    type = db.Column(db.Enum('Asset', 'Liability', 'Equity', 'Income', 'Expense', name='account_types'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship('Account', remote_side=[id], backref='children', lazy=True)

    def __repr__(self):
        return f'<Account {self.name} ({self.type})>'


class TaxRate(db.Model):
    __tablename__ = 'tax_rates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    rate = db.Column(db.Float, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TaxRate {self.name} {self.rate}%>'


class Currency(db.Model):
    __tablename__ = 'currencies'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(10), default='Rs')
    rate_to_base = db.Column(db.Float, nullable=False, default=1)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Currency {self.code}>'


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50))
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    invoice = db.relationship('Sale', backref='payments', lazy=True)
    expense = db.relationship('Expense', backref='payments', lazy=True)

    def __repr__(self):
        return f'<Payment {self.payment_number} {self.amount}>'


class RecurringExpense(db.Model):
    __tablename__ = 'recurring_expenses'

    id = db.Column(db.Integer, primary_key=True)
    expense_category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.Enum('daily', 'weekly', 'monthly', 'yearly', name='recurring_frequency'), nullable=False)
    next_due_date = db.Column(db.Date)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    category = db.relationship('ExpenseCategory', backref='recurring_expenses', lazy=True)
    vendor = db.relationship('Vendor', backref='recurring_expenses', lazy=True)

    def __repr__(self):
        return f'<RecurringExpense {self.id} {self.amount}>'

class ExpenseCategory(db.Model):
    """Expense category model"""
    __tablename__ = 'expense_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    expenses = db.relationship('Expense', backref='expense_category', lazy=True)
    
    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'

class Expense(db.Model):
    """Expense tracking model"""
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(50), unique=True, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), index=True, nullable=True)
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    bill_image_path = db.Column(db.String(255))  # Path to bill image
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Vendor', backref='expenses', lazy=True)
    
    def __repr__(self):
        return f'<Expense {self.expense_number}>'

class StockMovement(db.Model):
    """Stock movement tracking model"""
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    movement_type = db.Column(Enum('in', 'out', 'adjustment', name='movement_type'), index=True)
    reference_type = db.Column(db.String(50))  # sale, purchase, adjustment
    reference_id = db.Column(db.Integer)
    quantity = db.Column(db.Float, nullable=False)
    previous_quantity = db.Column(db.Float)
    new_quantity = db.Column(db.Float)
    reason = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref='stock_movements')
    
    def __repr__(self):
        return f'<StockMovement {self.product_id} - {self.movement_type}>'

class Company(db.Model):
    """Company information for invoices and reports"""
    __tablename__ = 'company'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    gst_number = db.Column(db.String(20))
    pan_number = db.Column(db.String(20))
    website = db.Column(db.String(100))
    
    # Banking details
    bank_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    account_holder_name = db.Column(db.String(100))
    
    # Logo path
    logo_path = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Company {self.name}>'

class InvoiceSettings(db.Model):
    """Invoice settings and templates"""
    __tablename__ = 'invoice_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    default_notes = db.Column(db.Text)
    default_terms = db.Column(db.Text)
    
    # Banking details
    bank_name = db.Column(db.String(100))
    account_holder_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    swift_code = db.Column(db.String(20))
    bank_address = db.Column(db.Text)
    payment_instructions = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InvoiceSettings {self.id}>'

class SaleReturn(db.Model):
    """Sales return model"""
    __tablename__ = 'sale_returns'

    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    subtotal = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    reason = db.Column(db.Text)
    status = db.Column(Enum('pending', 'approved', 'completed', name='return_status'), default='pending', index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sale = db.relationship('Sale', backref='returns', lazy=True)
    customer = db.relationship('Customer', backref='sale_returns', lazy=True)
    items = db.relationship('SaleReturnItem', backref='sale_return', lazy=True, cascade='all, delete-orphan')

    def calculate_totals(self):
        """Calculate return totals"""
        self.subtotal = sum(item.total for item in self.items)
        self.tax = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax - self.discount
        if self.total < 0:
            self.total = 0

    def __repr__(self):
        return f'<SaleReturn {self.return_number}>'


class SaleReturnItem(db.Model):
    """Sales return item details"""
    __tablename__ = 'sale_return_items'

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('sale_returns.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='return_items', lazy=True)

    def __repr__(self):
        return f'<SaleReturnItem {self.return_id} - {self.product_id}>'


class Task(db.Model):
    """Task assignment model"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.Enum('Pending', 'In Progress', 'Completed', 'Cancelled', name='task_status'), default='Pending')
    priority = db.Column(db.Enum('Low', 'Medium', 'High', 'Critical', name='task_priority'), default='Medium')
    due_date = db.Column(db.DateTime)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Task {self.title}>'