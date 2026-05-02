from app import db
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import Enum, func
from werkzeug.security import generate_password_hash, check_password_hash
from calendar import monthrange

class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, manager, user
    is_active = db.Column(db.Boolean, default=True)
    
    # Permissions - View
    can_view_sales = db.Column(db.Boolean, default=True)
    can_view_purchases = db.Column(db.Boolean, default=True)
    can_view_inventory = db.Column(db.Boolean, default=True)
    can_view_expenses = db.Column(db.Boolean, default=True)
    can_view_returns = db.Column(db.Boolean, default=True)
    can_view_vendors = db.Column(db.Boolean, default=True)
    can_view_customers = db.Column(db.Boolean, default=True)
    can_view_reports = db.Column(db.Boolean, default=True)
    can_view_settings = db.Column(db.Boolean, default=True)
    can_view_manufacturing = db.Column(db.Boolean, default=True)
    can_view_production = db.Column(db.Boolean, default=True)
    can_view_warehouse = db.Column(db.Boolean, default=True)
    can_view_attendance = db.Column(db.Boolean, default=True)
    can_view_salary = db.Column(db.Boolean, default=True)
    can_view_targets = db.Column(db.Boolean, default=True)
    can_view_dashboard = db.Column(db.Boolean, default=True)
    can_view_accounting = db.Column(db.Boolean, default=True)
    can_view_salesmen = db.Column(db.Boolean, default=True)
    can_view_product_dev = db.Column(db.Boolean, default=True)
    can_view_categories = db.Column(db.Boolean, default=True)
    can_view_customer_groups = db.Column(db.Boolean, default=True)
    can_view_tasks = db.Column(db.Boolean, default=True)
    can_view_profit_loss = db.Column(db.Boolean, default=True)
    can_view_users = db.Column(db.Boolean, default=False)

    # Permissions - Add
    can_add_sales = db.Column(db.Boolean, default=False)
    can_add_purchases = db.Column(db.Boolean, default=False)
    can_add_inventory = db.Column(db.Boolean, default=False)
    can_add_expenses = db.Column(db.Boolean, default=False)
    can_add_returns = db.Column(db.Boolean, default=False)
    can_add_vendors = db.Column(db.Boolean, default=False)
    can_add_customers = db.Column(db.Boolean, default=False)
    can_add_reports = db.Column(db.Boolean, default=False)
    can_add_settings = db.Column(db.Boolean, default=False)
    can_add_manufacturing = db.Column(db.Boolean, default=False)
    can_add_production = db.Column(db.Boolean, default=False)
    can_add_warehouse = db.Column(db.Boolean, default=False)
    can_add_attendance = db.Column(db.Boolean, default=False)
    can_add_salary = db.Column(db.Boolean, default=False)
    can_add_targets = db.Column(db.Boolean, default=False)
    can_add_dashboard = db.Column(db.Boolean, default=False)
    can_add_accounting = db.Column(db.Boolean, default=False)
    can_add_salesmen = db.Column(db.Boolean, default=False)
    can_add_product_dev = db.Column(db.Boolean, default=False)
    can_add_categories = db.Column(db.Boolean, default=False)
    can_add_customer_groups = db.Column(db.Boolean, default=False)
    can_add_tasks = db.Column(db.Boolean, default=False)
    can_add_profit_loss = db.Column(db.Boolean, default=False)
    can_add_users = db.Column(db.Boolean, default=False)

    # Permissions - Edit
    can_edit_sales = db.Column(db.Boolean, default=False)
    can_edit_purchases = db.Column(db.Boolean, default=False)
    can_edit_inventory = db.Column(db.Boolean, default=False)
    can_edit_expenses = db.Column(db.Boolean, default=False)
    can_edit_returns = db.Column(db.Boolean, default=False)
    can_edit_vendors = db.Column(db.Boolean, default=False)
    can_edit_customers = db.Column(db.Boolean, default=False)
    can_edit_reports = db.Column(db.Boolean, default=False)
    can_edit_settings = db.Column(db.Boolean, default=False)
    can_edit_manufacturing = db.Column(db.Boolean, default=False)
    can_edit_production = db.Column(db.Boolean, default=False)
    can_edit_warehouse = db.Column(db.Boolean, default=False)
    can_edit_attendance = db.Column(db.Boolean, default=False)
    can_edit_salary = db.Column(db.Boolean, default=False)
    can_edit_targets = db.Column(db.Boolean, default=False)
    can_edit_dashboard = db.Column(db.Boolean, default=False)
    can_edit_accounting = db.Column(db.Boolean, default=False)
    can_edit_salesmen = db.Column(db.Boolean, default=False)
    can_edit_product_dev = db.Column(db.Boolean, default=False)
    can_edit_categories = db.Column(db.Boolean, default=False)
    can_edit_customer_groups = db.Column(db.Boolean, default=False)
    can_edit_tasks = db.Column(db.Boolean, default=False)
    can_edit_profit_loss = db.Column(db.Boolean, default=False)
    can_edit_users = db.Column(db.Boolean, default=False)

    # Permissions - Delete
    can_delete_sales = db.Column(db.Boolean, default=False)
    can_delete_purchases = db.Column(db.Boolean, default=False)
    can_delete_inventory = db.Column(db.Boolean, default=False)
    can_delete_expenses = db.Column(db.Boolean, default=False)
    can_delete_returns = db.Column(db.Boolean, default=False)
    can_delete_vendors = db.Column(db.Boolean, default=False)
    can_delete_customers = db.Column(db.Boolean, default=False)
    can_delete_reports = db.Column(db.Boolean, default=False)
    can_delete_settings = db.Column(db.Boolean, default=False)
    can_delete_manufacturing = db.Column(db.Boolean, default=False)
    can_delete_production = db.Column(db.Boolean, default=False)
    can_delete_warehouse = db.Column(db.Boolean, default=False)
    can_delete_attendance = db.Column(db.Boolean, default=False)
    can_delete_salary = db.Column(db.Boolean, default=False)
    can_delete_targets = db.Column(db.Boolean, default=False)
    can_delete_dashboard = db.Column(db.Boolean, default=False)
    can_delete_accounting = db.Column(db.Boolean, default=False)
    can_delete_salesmen = db.Column(db.Boolean, default=False)
    can_delete_product_dev = db.Column(db.Boolean, default=False)
    can_delete_categories = db.Column(db.Boolean, default=False)
    can_delete_customer_groups = db.Column(db.Boolean, default=False)
    can_delete_tasks = db.Column(db.Boolean, default=False)
    can_delete_profit_loss = db.Column(db.Boolean, default=False)
    can_delete_users = db.Column(db.Boolean, default=False)

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
    
    def has_permission(self, module, action='view'):
        if self.role == 'admin':
            return True
        attr = f'can_{action}_{module}'
        return getattr(self, attr, False)
        
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
    company_name = db.Column(db.String(150), index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'), nullable=True, index=True)
    shipping_address = db.Column(db.Text)
    payment_method = db.Column(db.String(50), nullable=True)
    payment_terms = db.Column(db.Integer, default=30)  # Days
    credit_limit = db.Column(db.Float, default=0)
    
    # Banking details
    bank_name = db.Column(db.String(100))
    account_holder_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    swift_code = db.Column(db.String(20))
    ifsc_code = db.Column(db.String(20))
    
    is_active = db.Column(db.Boolean, default=True)
    image_path = db.Column(db.String(255))  # Path to vendor image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bills = db.relationship('PurchaseBill', backref='vendor', lazy=True, cascade='all, delete-orphan')
    advances = db.relationship('VendorAdvance', backref='vendor', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_purchases(self):
        return sum(bill.total for bill in self.bills)
    
    @property
    def outstanding_balance(self):
        return sum(bill.total - bill.paid_amount for bill in self.bills if bill.status != 'paid')

    @property
    def total_shipping_charges(self):
        return sum(bill.shipping_charge for bill in self.bills)

    @property
    def total_advances_given(self):
        return sum(adv.amount for adv in self.advances)

    @property
    def total_advances_adjusted(self):
        return sum(adv.applied_amount for adv in self.advances)

    @property
    def remaining_advance_balance(self):
        return self.total_advances_given - self.total_advances_adjusted
    
    @property
    def total_purchase_returns(self):
        return sum(ret.total for ret in self.purchase_returns)
    
    @property
    def total_refund_paid(self):
        return sum(ret.refund_amount for ret in self.purchase_returns if ret.refund_status == 'paid')
    
    @property
    def pending_refund(self):
        return sum(ret.total for ret in self.purchase_returns if ret.refund_status == 'pending')
    
    def __repr__(self):
        return f'<Vendor {self.name}>'


class CustomerGroup(db.Model):
    """Customer Group model"""
    __tablename__ = 'customer_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customers = db.relationship('Customer', backref='group', lazy=True)
    
    def __repr__(self):
        return f'<CustomerGroup {self.name}>'

class SalesmanGroup(db.Model):
    """Salesman Group model"""
    __tablename__ = 'salesman_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    salesmen = db.relationship('Salesman', backref='group', lazy=True)
    
    def __repr__(self):
        return f'<SalesmanGroup {self.name}>'

class Customer(db.Model):
    """Customer model"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    gst_number = db.Column(db.String(20), index=True)
    pan_number = db.Column(db.String(20))
    contact_person = db.Column(db.String(100))
    company_name = db.Column(db.String(150), index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'), nullable=True, index=True)
    payment_method = db.Column(db.String(50), nullable=True)
    payment_terms = db.Column(db.Integer, default=30)  # Days
    credit_limit = db.Column(db.Float, default=0)
    opening_balance = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy=True, cascade='all, delete-orphan')
    advances = db.relationship('CustomerAdvance', backref='customer', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_sales(self):
        return sum(sale.total for sale in self.sales)
    
    @property
    def outstanding_balance(self):
        return sum(sale.total - sale.paid_amount for sale in self.sales if sale.status != 'paid')
    
    @property
    def total_delivery_charges(self):
        return sum(sale.delivery_charge for sale in self.sales if hasattr(sale, 'delivery_charge'))

    @property
    def total_advances_received(self):
        return sum(adv.amount for adv in self.advances)

    @property
    def total_advances_adjusted(self):
        return sum(adv.applied_amount for adv in self.advances)

    @property
    def remaining_advance_balance(self):
        return self.total_advances_received - self.total_advances_adjusted
    
    def __repr__(self):
        return f'<Customer {self.name}>'

class Salesman(db.Model):
    """Salesman/Salesperson model"""
    __tablename__ = 'salesmen'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('salesman_groups.id'), nullable=True, index=True)
    group_assigned = db.Column(db.String(100), nullable=True) # Legacy field
    commission_rate = db.Column(db.Float, default=0) # Commission percentage
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='salesman', lazy=True)
    
    def __repr__(self):
        return f'<Salesman {self.name}>'

class Warehouse(db.Model):
    """Warehouse model"""
    __tablename__ = 'warehouses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    manager = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'


class Product(db.Model):
    """Product/Inventory model"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    barcode = db.Column(db.String(50), index=True)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'), nullable=True, index=True)
    category = db.relationship('ProductCategory', backref='products', lazy=True)
    # Legacy category string field for backward compatibility
    category_name = db.Column(db.String(50), index=True)
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
    is_manufactured = db.Column(db.Boolean, default=False)
    finished_good_price = db.Column(db.Float, nullable=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    warehouse = db.relationship('Warehouse', backref='products', lazy=True)
    
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


class ProductCategory(db.Model):
    """Product Category model"""
    __tablename__ = 'product_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'


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
    delivery_charge = db.Column(db.Float, default=0)  # Delivery cost
    advance_applied = db.Column(db.Float, default=0)  # Advance amount applied to this invoice
    total = db.Column(db.Float, default=0)
    status = db.Column(Enum('paid', 'unpaid', 'partial', name='payment_status'), default='unpaid', index=True)
    paid_amount = db.Column(db.Float, default=0)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), index=True, nullable=True)
    vendor = db.relationship('Vendor', backref='sales', lazy=True)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.id'), index=True, nullable=True)
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
        """Calculate invoice totals including delivery and advance"""
        self.subtotal = sum(item.total for item in self.items)
        
        # Calculate tax
        self.tax = self.subtotal * (self.tax_rate / 100)
        
        # Calculate discount
        if self.discount_type == 'percentage':
            discount_amount = self.subtotal * (self.discount / 100)
        else:
            discount_amount = self.discount
        
        # Calculate total = subtotal + tax + delivery - discount - advance
        self.total = self.subtotal + self.tax + self.delivery_charge - discount_amount - self.advance_applied
        
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
    delivery_fee = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    
    @property
    def net_total(self):
        """Calculate net total after discount"""
        return self.total - self.discount
    
    @property
    def item_subtotal(self):
        """Subtotal before delivery fee"""
        return self.quantity * self.unit_price
    
    def __repr__(self):
        return f'<SaleItem {self.sale_id} - {self.product_id}>'

class PurchaseBill(db.Model):
    """Purchase Bill model"""
    __tablename__ = 'purchase_bills'
    
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True, index=True)  # source PO
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
    advance_applied = db.Column(db.Float, default=0)  # Advance from vendor profile applied to this bill
    total = db.Column(db.Float, default=0)
    status = db.Column(Enum('paid', 'unpaid', 'partial', 'return', 'partial_return', name='payment_status'), default='unpaid', index=True)
    paid_amount = db.Column(db.Float, default=0)
    bill_image_path = db.Column(db.String(255))  # Path to uploaded bill image
    notes = db.Column(db.Text)
    inventory_received = db.Column(db.Boolean, default=False)  # True when stock has been received into inventory
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('PurchaseItem', backref='bill', lazy=True, cascade='all, delete-orphan')
    bill_payments = db.relationship('BillPayment', backref='bill', lazy=True, cascade='all, delete-orphan')
    bill_receives = db.relationship('BillReceive', backref='bill', lazy=True, cascade='all, delete-orphan')

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
    shipping_charge = db.Column(db.Float, default=0)  # Per-item shipping cost
    total = db.Column(db.Float, nullable=False)
    
    @property
    def net_total(self):
        """Calculate net total after discount and including shipping"""
        return (self.total - self.discount) + self.shipping_charge
    
    @property
    def per_unit_shipping(self):
        """Calculate shipping per unit"""
        return self.shipping_charge / self.quantity if self.quantity > 0 else 0
    
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
    symbol = db.Column(db.String(10), default='PKR')
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
    image_path = db.Column(db.String(255))  # Path to uploaded payment receipt/bill image
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

class PaymentMethod(db.Model):
    """Payment method model"""
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentMethod {self.name}>'

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
    is_bom_overhead = db.Column(db.Boolean, default=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=True)
    mo_id = db.Column(db.Integer, db.ForeignKey('manufacturing_orders.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, confirmed, rejected
    
    # Monthly distribution fields
    is_monthly_divided = db.Column(db.Boolean, default=False)  # Whether expense is divided across month
    monthly_start_date = db.Column(db.Date)  # Start date for monthly distribution
    monthly_end_date = db.Column(db.Date)  # End date for monthly distribution
    daily_amount = db.Column(db.Float, default=0)  # Calculated daily amount
    
    # Relationships
    vendor = db.relationship('Vendor', backref='expenses', lazy=True)
    product = db.relationship('Product', backref='overhead_expenses', lazy=True)
    bom = db.relationship('BOM', backref='overhead_expenses', lazy=True)
    manufacturing_order = db.relationship('ManufacturingOrder', backref='overhead_expenses', lazy=True)
    
    @property
    def days_in_month(self):
        """Calculate number of days in the distribution period"""
        if self.is_monthly_divided and self.monthly_start_date and self.monthly_end_date:
            delta = self.monthly_end_date - self.monthly_start_date
            return delta.days + 1  # Include both start and end date
        return 0
    
    def calculate_daily_amount(self):
        """Calculate daily amount for monthly divided expense"""
        if self.is_monthly_divided and self.days_in_month > 0:
            self.daily_amount = self.amount / self.days_in_month
        else:
            self.daily_amount = 0
    
    def get_today_expense(self):
        """Get expense amount for today if it falls within distribution period"""
        if self.is_monthly_divided and self.monthly_start_date and self.monthly_end_date:
            today = datetime.utcnow().date()
            if self.monthly_start_date <= today <= self.monthly_end_date:
                return self.daily_amount
        return 0
    
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
    logo_path = db.Column(db.String(200))
    signature_path = db.Column(db.String(200))

    # Date format setting (Python strftime format string)
    date_format = db.Column(db.String(20), default='%Y-%m-%d')

    # Manufacturing Order number settings (prefix, suffix, next sequential number)
    mo_prefix = db.Column(db.String(20), default='MO-')
    mo_suffix = db.Column(db.String(10), default='')
    next_mo_number = db.Column(db.Integer, default=1)

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
    
    # Invoice numbering
    invoice_prefix = db.Column(db.String(10))
    invoice_suffix = db.Column(db.String(10))
    next_number = db.Column(db.Integer, default=1)
    
    # Tax settings
    tax_name = db.Column(db.String(50))
    tax_rate = db.Column(db.Numeric(10, 2), default=10)
    
    # Additional
    payment_terms = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InvoiceSettings {self.id}>'


class PurchaseSettings(db.Model):
    """Purchase settings and templates"""
    __tablename__ = 'purchase_settings'

    id = db.Column(db.Integer, primary_key=True)
    default_notes = db.Column(db.Text)
    default_terms = db.Column(db.Text)  # Policy/terms for purchase bills

    # Bill number formatting
    bill_prefix = db.Column(db.String(10), default='PB-')
    bill_suffix = db.Column(db.String(10), default='')
    next_bill_number = db.Column(db.Integer, default=1)

    # PO number formatting
    po_prefix = db.Column(db.String(10), default='PO-')
    po_suffix = db.Column(db.String(10), default='')
    next_po_number = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PurchaseSettings {self.id}>'


class ExpenseSettings(db.Model):
    """Expense number formatting settings"""
    __tablename__ = 'expense_settings'

    id = db.Column(db.Integer, primary_key=True)
    expense_prefix = db.Column(db.String(10), default='EXP-')
    expense_suffix = db.Column(db.String(10), default='')
    next_number = db.Column(db.Integer, default=1)
    date_format = db.Column(db.String(20), default='%Y-%m-%d')  # Python strftime format

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ExpenseSettings {self.id}>'


class SaleReturnSettings(db.Model):
    """Sale return number formatting settings"""
    __tablename__ = 'sale_return_settings'

    id = db.Column(db.Integer, primary_key=True)
    return_prefix = db.Column(db.String(10), default='RET-')
    return_suffix = db.Column(db.String(10), default='')
    next_number = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SaleReturnSettings {self.id}>'


class PurchaseReturnSettings(db.Model):
    """Purchase return number formatting settings"""
    __tablename__ = 'purchase_return_settings'

    id = db.Column(db.Integer, primary_key=True)
    return_prefix = db.Column(db.String(10), default='PRet-')
    return_suffix = db.Column(db.String(10), default='')
    next_number = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PurchaseReturnSettings {self.id}>'


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
    returned_to_inventory = db.Column(db.Boolean, default=False)
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


class PurchaseReturn(db.Model):
    """Purchase return model"""
    __tablename__ = 'purchase_returns'

    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    subtotal = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    reason = db.Column(db.Text)
    status = db.Column(Enum('pending', 'approved', 'completed', name='purchase_return_status'), default='pending', index=True)
    returned_to_inventory = db.Column(db.Boolean, default=False)
    refund_amount = db.Column(db.Float, default=0)
    refund_status = db.Column(Enum('none', 'pending', 'paid', name='purchase_refund_status'), default='none', index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bill = db.relationship('PurchaseBill', backref='purchase_returns', lazy=True)
    vendor = db.relationship('Vendor', backref='purchase_returns', lazy=True)
    items = db.relationship('PurchaseReturnItem', backref='purchase_return', lazy=True, cascade='all, delete-orphan')

    def calculate_totals(self):
        """Calculate return totals"""
        self.subtotal = sum(item.total for item in self.items)
        self.tax = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax - self.discount
        if self.total < 0:
            self.total = 0

    def __repr__(self):
        return f'<PurchaseReturn {self.return_number}>'


class PurchaseReturnItem(db.Model):
    """Purchase return item details"""
    __tablename__ = 'purchase_return_items'

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('purchase_returns.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='purchase_return_items', lazy=True)

    def __repr__(self):
        return f'<PurchaseReturnItem {self.return_id} - {self.product_id}>'


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

class BOM(db.Model):
    """Bill of Materials"""
    __tablename__ = 'boms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    version = db.Column(db.String(10), default='v1')  # Current version: v1, v2, v3, etc
    labor_cost = db.Column(db.Float, default=0)
    overhead_cost = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)  # Only latest version is active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    product = db.relationship('Product', backref='boms', lazy=True)
    items = db.relationship('BOMItem', backref='bom', lazy=True, cascade='all, delete-orphan')
    
    def calculate_total_cost(self):
        components_cost = sum(item.total_cost for item in self.items)
        self.total_cost = components_cost + self.labor_cost + self.overhead_cost
    
    @property
    def version_number(self):
        """Get numeric version (v2 -> 2)"""
        return int(self.version[1:]) if self.version.startswith('v') else 1

class BOMItem(db.Model):
    """Bill of Materials Component"""
    __tablename__ = 'bom_items'
    
    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, default=0)  # Cost per unit
    shipping_per_unit = db.Column(db.Float, default=0)  # Shipping per unit (allocated from purchase)
    total_cost = db.Column(db.Float, default=0)  # (unit_cost + shipping_per_unit) * quantity
    cost_price_history_id = db.Column(db.Integer, db.ForeignKey('cost_price_history.id'))  # Track which cost price
    
    component = db.relationship('Product', foreign_keys=[component_id])
    cost_history = db.relationship('CostPriceHistory', foreign_keys=[cost_price_history_id])

class Staff(db.Model):
    """Staff/Employee model"""
    __tablename__ = 'staff'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    designation = db.Column(db.String(100))
    monthly_salary = db.Column(db.Float, nullable=False, default=0)
    joining_date = db.Column(db.Date, default=datetime.utcnow().date())
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Monthly divided salary fields
    daily_salary = db.Column(db.Float, default=0)  # Calculated daily salary (monthly ÷ 30)
    
    # Relationships
    advances = db.relationship('SalaryAdvance', backref='staff', lazy=True, cascade='all, delete-orphan')
    salary_payments = db.relationship('SalaryPayment', backref='staff', lazy=True, cascade='all, delete-orphan')

    @property
    def total_outstanding_advance(self):
        """Calculate total non-deducted advances"""
        return sum(advance.amount for advance in self.advances if not advance.is_deducted)
    
    def calculate_daily_salary(self, reference_date=None):
        """
        Calculate daily salary based on actual days in the month.
        
        Args:
            reference_date: Date to use for determining the month (default: today)
            Examples:
            - January (31 days): 10000 / 31 = 322.58 per day
            - February (28/29 days): 10000 / 28 = 357.14 per day
            - April (30 days): 10000 / 30 = 333.33 per day
        """
        if reference_date is None:
            reference_date = datetime.utcnow().date()
        
        # Get the number of days in the month
        _, days_in_month = monthrange(reference_date.year, reference_date.month)
        
        # Calculate daily salary
        self.daily_salary = self.monthly_salary / float(days_in_month)
    
    def get_today_salary(self):
        """Get salary amount for today if staff is active"""
        if self.is_active and self.daily_salary > 0:
            return self.daily_salary
        return 0
    
    def __repr__(self):
        return f'<Staff {self.name}>'

class Attendance(db.Model):
    """Staff Attendance/Time Tracking model - for hourly wage calculation"""
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    clock_in = db.Column(db.DateTime, nullable=True)  # When staff clocked in
    clock_out = db.Column(db.DateTime, nullable=True)  # When staff clocked out
    hours_worked = db.Column(db.Float, default=0)  # Total hours worked (calculated)
    minutes_worked = db.Column(db.Integer, default=0)  # Remaining minutes (0-59)
    hourly_rate = db.Column(db.Float, default=0)  # Calculated hourly rate (monthly ÷ 30 ÷ 8)
    earned_amount = db.Column(db.Float, default=0)  # Amount earned (hours_worked × hourly_rate + minutes contribution)
    notes = db.Column(db.Text)  # Optional notes (e.g., half day, late, etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    staff = db.relationship('Staff', backref=db.backref('attendance_records', lazy=True, cascade='all, delete-orphan'))
    
    def calculate_hours_worked(self):
        """Calculate hours and minutes worked from clock in/out times"""
        if self.clock_in and self.clock_out:
            time_diff = self.clock_out - self.clock_in
            total_seconds = time_diff.total_seconds()
            
            # Calculate hours and minutes
            total_minutes = int(total_seconds / 60)
            self.hours_worked = total_minutes // 60
            self.minutes_worked = total_minutes % 60
        else:
            self.hours_worked = 0
            self.minutes_worked = 0
    
    def calculate_hourly_rate(self):
        """
        Calculate hourly rate from staff monthly salary based on actual days in the month.
        
        Formula: monthly_salary / days_in_month / 8 hours_per_day
        
        Examples:
        - January (31 days): 10000 / 31 / 8 = 40.32 per hour
        - February (28 days): 10000 / 28 / 8 = 44.64 per hour
        - April (30 days): 10000 / 30 / 8 = 41.67 per hour
        """
        if self.staff and self.staff.monthly_salary > 0:
            # Get the number of days in the month for this attendance record
            _, days_in_month = monthrange(self.date.year, self.date.month)
            
            # Assumption: 8 hours per working day
            self.hourly_rate = self.staff.monthly_salary / float(days_in_month) / 8.0
        else:
            self.hourly_rate = 0
    
    def calculate_earned_amount(self):
        """Calculate total earned amount for the day"""
        self.calculate_hourly_rate()
        
        if self.hourly_rate > 0 and (self.hours_worked > 0 or self.minutes_worked > 0):
            # Calculate: hours × hourly_rate + (minutes / 60) × hourly_rate
            total_hours_decimal = self.hours_worked + (self.minutes_worked / 60.0)
            self.earned_amount = total_hours_decimal * self.hourly_rate
        else:
            self.earned_amount = 0
    
    def get_time_summary(self):
        """Return formatted time summary (e.g., '8h 30m')"""
        if self.hours_worked > 0 or self.minutes_worked > 0:
            return f"{self.hours_worked}h {self.minutes_worked}m"
        return "0h 0m"
    
    def __repr__(self):
        return f'<Attendance {self.staff_id} - {self.date}: {self.get_time_summary()}>'

class SalaryAdvance(db.Model):
    """Salary advance model"""
    __tablename__ = 'salary_advances'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date())
    description = db.Column(db.String(255))
    is_deducted = db.Column(db.Boolean, default=False)
    salary_payment_id = db.Column(db.Integer, db.ForeignKey('salary_payments.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SalaryAdvance {self.staff_id} - {self.amount}>'

class SalaryPayment(db.Model):
    """Monthly salary payment model"""
    __tablename__ = 'salary_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    base_salary = db.Column(db.Float, nullable=False)
    advance_deduction = db.Column(db.Float, default=0)
    bonus = db.Column(db.Float, default=0)
    other_deductions = db.Column(db.Float, default=0)
    net_salary = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=datetime.utcnow().date())
    payment_method = db.Column(db.String(50), default='Cash')
    status = db.Column(Enum('paid', 'pending', name='salary_payment_status'), default='paid', index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Back-relationship for advances deducted in this payment
    deducted_advances = db.relationship('SalaryAdvance', backref='salary_payment', foreign_keys=[SalaryAdvance.salary_payment_id], lazy=True)
    
    def __repr__(self):
        return f'<SalaryPayment {self.staff_id} - {self.month}/{self.year}>'

class ManufacturingOrder(db.Model):
    """Manufacturing Order"""
    __tablename__ = 'manufacturing_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=False, index=True)
    status = db.Column(Enum('Draft', 'In Progress', 'Completed', name='mo_status'), default='Draft', index=True)
    quantity_to_produce = db.Column(db.Float, nullable=False)
    produced_qty = db.Column(db.Float, default=0)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    actual_labor_cost = db.Column(db.Float, default=0)
    actual_material_cost = db.Column(db.Float, default=0)
    actual_overhead_cost = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    bom = db.relationship('BOM', backref='manufacturing_orders', lazy=True)
    items = db.relationship('ManufacturingOrderItem', backref='manufacturing_order', lazy=True, cascade='all, delete-orphan')
    history = db.relationship('ManufacturingOrderHistory', backref='order', lazy=True, cascade='all, delete-orphan')

    @property
    def remaining_qty(self):
        return max(0, self.quantity_to_produce - (self.produced_qty or 0))

class ManufacturingOrderHistory(db.Model):
    """Tracks partial completions of a Manufacturing Order"""
    __tablename__ = 'manufacturing_order_history'
    
    id = db.Column(db.Integer, primary_key=True)
    mo_id = db.Column(db.Integer, db.ForeignKey('manufacturing_orders.id'), nullable=False, index=True)
    quantity_produced = db.Column(db.Float, nullable=False)
    material_cost = db.Column(db.Float, default=0)
    labor_cost = db.Column(db.Float, default=0)
    overhead_cost = db.Column(db.Float, default=0)
    is_manual_overhead = db.Column(db.Boolean, default=False)
    total_cost = db.Column(db.Float, default=0)
    completion_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by])

class ManufacturingOrderItem(db.Model):
    """Manufacturing Order Component"""
    __tablename__ = 'manufacturing_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    mo_id = db.Column(db.Integer, db.ForeignKey('manufacturing_orders.id'), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity_required = db.Column(db.Float, nullable=False)
    quantity_consumed = db.Column(db.Float, default=0)
    cost = db.Column(db.Float, default=0)
    
    component = db.relationship('Product', foreign_keys=[component_id])

class MonthlyTarget(db.Model):
    """Monthly target model for KPIs"""
    __tablename__ = 'monthly_targets'
    
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False) # 1-12
    year = db.Column(db.Integer, nullable=False)
    
    target_production_qty = db.Column(db.Float, default=0)
    target_production_cost = db.Column(db.Float, default=0)
    target_sales_revenue = db.Column(db.Float, default=0)
    target_sales_qty = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<MonthlyTarget {self.month}/{self.year}>'


class VendorAdvance(db.Model):
    """Advance payment given to a vendor against material (before bill is raised)"""
    __tablename__ = 'vendor_advances'

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    applied_amount = db.Column(db.Float, default=0)  # Amount actually applied to bills
    date = db.Column(db.Date, default=datetime.utcnow().date)
    description = db.Column(db.String(255))
    is_adjusted = db.Column(db.Boolean, default=False)  # True when fully settled/applied against a bill
    adjusted_bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    adjusted_bill = db.relationship('PurchaseBill', backref='adjusted_advances', lazy=True)

    @property
    def remaining_balance(self):
        """Get remaining unapplied balance of this advance"""
        return self.amount - self.applied_amount

    def __repr__(self):
        return f'<VendorAdvance vendor={self.vendor_id} amount={self.amount}>'


class CustomerAdvance(db.Model):
    """Advance payment received from a customer (before sale invoice is raised)"""
    __tablename__ = 'customer_advances'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    applied_amount = db.Column(db.Float, default=0)  # Amount actually applied to invoices
    date = db.Column(db.Date, default=datetime.utcnow().date)
    description = db.Column(db.String(255))
    is_adjusted = db.Column(db.Boolean, default=False)  # True when fully settled/applied against an invoice
    adjusted_invoice_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    adjusted_invoice = db.relationship('Sale', backref='adjusted_advances', lazy=True)

    @property
    def remaining_balance(self):
        """Get remaining unapplied balance of this advance"""
        return self.amount - self.applied_amount

    def __repr__(self):
        return f'<CustomerAdvance customer={self.customer_id} amount={self.amount}>'


class PurchaseOrder(db.Model):
    """Purchase Order — created before a Purchase Bill. Can be converted into a bill."""
    __tablename__ = 'purchase_orders'

    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expected_date = db.Column(db.DateTime, nullable=True)
    delivery_start = db.Column(db.DateTime, nullable=True)  # Delivery time window start
    delivery_end = db.Column(db.DateTime, nullable=True)    # Delivery time window end
    advance_amount = db.Column(db.Float, default=0)        # Advance paid to vendor for this PO
    status = db.Column(
        Enum('Draft', 'Confirmed', 'Converted', 'Cancelled', name='po_status'),
        default='Draft', index=True
    )
    notes = db.Column(db.Text)
    subtotal = db.Column(db.Float, default=0)
    shipping_charge = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vendor = db.relationship('Vendor', backref='purchase_orders', lazy=True)
    items = db.relationship('PurchaseOrderItem', backref='po', lazy=True, cascade='all, delete-orphan')
    bills = db.relationship('PurchaseBill', backref='source_po', lazy=True, foreign_keys='PurchaseBill.po_id')

    def calculate_totals(self):
        self.subtotal = sum(item.total for item in self.items)
        self.tax = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax + self.shipping_charge - self.discount
        if self.total < 0:
            self.total = 0

    def __repr__(self):
        return f'<PurchaseOrder {self.po_number}>'


class PurchaseOrderItem(db.Model):
    """Line items on a Purchase Order"""
    __tablename__ = 'purchase_order_items'

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='po_items', lazy=True)

    def __repr__(self):
        return f'<PurchaseOrderItem po={self.po_id} product={self.product_id}>'


class BillPayment(db.Model):
    """Records each payment transaction against a purchase bill"""
    __tablename__ = 'bill_payments'

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), nullable=False, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='Cash')
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    image_path = db.Column(db.String(255))  # Upload receipt/payment proof
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='bill_payments_created', lazy=True)

    def __repr__(self):
        return f'<BillPayment bill={self.bill_id} amount={self.amount}>'


class BillReceive(db.Model):
    """Records each 'receive quantity' entry against a purchase bill"""
    __tablename__ = 'bill_receives'

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), nullable=False, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    receive_items = db.relationship('BillReceiveItem', backref='receive', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', backref='bill_receives_created', lazy=True)

    def __repr__(self):
        return f'<BillReceive bill={self.bill_id}>'


class BillReceiveItem(db.Model):
    """Line items for a receive entry - which products and how many were received"""
    __tablename__ = 'bill_receive_items'

    id = db.Column(db.Integer, primary_key=True)
    receive_id = db.Column(db.Integer, db.ForeignKey('bill_receives.id'), nullable=False, index=True)
    purchase_item_id = db.Column(db.Integer, db.ForeignKey('purchase_items.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity_received = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='bill_receive_items', lazy=True)
    purchase_item = db.relationship('PurchaseItem', backref='receive_items', lazy=True)

    def __repr__(self):
        return f'<BillReceiveItem receive={self.receive_id} product={self.product_id} qty={self.quantity_received}>'


class CostPriceHistory(db.Model):
    """Track cost price changes for products when new purchases are received"""
    __tablename__ = 'cost_price_history'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    purchase_bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), index=True)
    old_price = db.Column(db.Float)  # Previous cost price (None if first entry)
    new_price = db.Column(db.Float, nullable=False)  # New cost price
    quantity_at_old_price = db.Column(db.Float, default=0)  # Quantity still available at old price
    used_quantity = db.Column(db.Float, default=0)  # Quantity already used/sold at old price
    change_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    reason = db.Column(db.String(200))  # e.g., "Purchase bill #12345"
    is_active = db.Column(db.Boolean, default=True)  # Active until old_price stock is consumed
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    product = db.relationship('Product', backref='cost_price_changes')
    purchase_bill = db.relationship('PurchaseBill', backref='cost_price_changes')
    
    @property
    def remaining_at_old_price(self):
        """Calculate remaining quantity at old price"""
        return max(0, self.quantity_at_old_price - self.used_quantity)
    
    def __repr__(self):
        return f'<CostPriceHistory product={self.product_id} old={self.old_price} new={self.new_price}>'


class BOMVersion(db.Model):
    """Version tracking for Bill of Materials - stores version history"""
    __tablename__ = 'bom_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = db.Column(db.String(10), nullable=False)  # v1, v2, v3, etc
    labor_cost = db.Column(db.Float, default=0)
    overhead_cost = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)
    change_reason = db.Column(db.String(200))  # e.g., "Component price increase", "Overhead added"
    change_type = db.Column(db.String(50))  # 'component_cost', 'overhead_added', 'manual'
    previous_version = db.Column(db.String(10))  # Reference to previous version
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    bom = db.relationship('BOM', backref='versions', lazy=True)
    items = db.relationship('BOMVersionItem', backref='version', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<BOMVersion bom={self.bom_id} {self.version_number}>'


class BOMVersionItem(db.Model):
    """Components for a specific BOM version - snapshot of BOM items at that version"""
    __tablename__ = 'bom_version_items'
    
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('bom_versions.id'), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, default=0)  # Cost per unit at time of this version
    shipping_per_unit = db.Column(db.Float, default=0)  # Shipping cost per unit at time
    total_cost = db.Column(db.Float, default=0)  # unit_cost + shipping * quantity
    
    component = db.relationship('Product', foreign_keys=[component_id])
    
    def __repr__(self):
        return f'<BOMVersionItem version={self.version_id} component={self.component_id}>'


class ProductionTarget(db.Model):
    """Monthly production targets per product (SKU-based)"""
    __tablename__ = 'production_targets'
    
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    sku_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=True) # Range Start
    end_date = db.Column(db.Date, nullable=True)   # Range End
    target_units = db.Column(db.Float, nullable=False, default=0)
    produced_qty = db.Column(db.Float, nullable=True) # Manual override for production qty (None = use logs)
    overhead_cost_per_unit = db.Column(db.Float, default=0)  # Manual overhead cost per unit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    product = db.relationship('Product', backref='production_targets', lazy=True)
    
    def __repr__(self):
        return f'<ProductionTarget {self.month}/{self.year} - {self.product.sku if self.product else self.sku_id}>'


class ProductionLog(db.Model):
    """Daily production logs - tracks actual production per SKU"""
    __tablename__ = 'production_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    sku_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    shift = db.Column(db.String(20))  # Morning, Evening, Night
    operator = db.Column(db.String(100))
    qty_produced = db.Column(db.Float, default=0)
    rejected_qty = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    product = db.relationship('Product', backref='production_logs', lazy=True)
    creator = db.relationship('User', backref='created_production_logs', lazy=True)
    
    @property
    def pass_rate(self):
        """Calculate pass rate percentage"""
        total = self.qty_produced + self.rejected_qty
        if total == 0:
            return 0
        return round((self.qty_produced / total) * 100, 2)
    
    def __repr__(self):
        return f'<ProductionLog {self.date} - {self.product.sku if self.product else self.sku_id}>'


# ==================== PRODUCT DEVELOPMENT MODULE ====================

class PDProject(db.Model):
    """Product Development Project - manages full lifecycle from idea to production"""
    __tablename__ = 'pd_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    pdv_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    sku_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    start_date = db.Column(db.Date, nullable=True)
    promise_date = db.Column(db.Date, nullable=True)
    budget = db.Column(db.Float, default=0)
    status = db.Column(db.Enum('Draft', 'Active', 'Completed', 'On Hold', name='pd_project_status'), default='Draft', index=True)
    current_phase = db.Column(db.Integer, default=1)  # 1-6 for phases
    description = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sku = db.relationship('Product', backref='pd_projects', lazy=True)
    creator = db.relationship('User', backref='created_pd_projects', lazy=True)
    bom_items = db.relationship('PDProjectBOM', backref='project', lazy=True, cascade='all, delete-orphan')
    components = db.relationship('PDComponent', backref='project', lazy=True, cascade='all, delete-orphan')
    tooling = db.relationship('PDTooling', backref='project', lazy=True, cascade='all, delete-orphan')
    testing = db.relationship('PDTesting', backref='project', lazy=True, cascade='all, delete-orphan')
    approval = db.relationship('PDApproval', backref='project', uselist=False, cascade='all, delete-orphan')
    assets = db.relationship('PDAsset', backref='project', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_tooling_cost(self):
        return sum(tool.cost for tool in self.tooling)
    
    @property
    def total_component_cost(self):
        return sum(comp.cost or 0 for comp in self.components)
    
    @property
    def total_bom_cost(self):
        return sum(item.estimated_cost or 0 for item in self.bom_items)
    
    @property
    def total_investment(self):
        return self.total_tooling_cost + self.total_component_cost + self.total_bom_cost
    
    @property
    def budget_vs_actual(self):
        return self.budget - self.total_investment if self.budget else 0
    
    @property
    def is_delayed(self):
        if self.promise_date and self.status not in ['Completed']:
            return datetime.utcnow().date() > self.promise_date
        return False
    
    @property
    def phase_name(self):
        phases = {1: 'Initiation & BOM', 2: 'Component Management', 3: 'Tooling', 
                  4: 'Testing', 5: 'Approval', 6: 'Production Ready'}
        return phases.get(self.current_phase, 'Unknown')
    
    def __repr__(self):
        return f'<PDProject {self.pdv_code} - {self.product_name}>'


class PDProjectBOM(db.Model):
    """Bill of Materials for Product Development"""
    __tablename__ = 'pd_bom'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    material_name = db.Column(db.String(200), nullable=False)
    sku_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    quantity_per_unit = db.Column(db.Float, default=1)
    estimated_cost = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    material = db.relationship('Product', foreign_keys=[sku_id], lazy=True)
    
    @property
    def total_cost(self):
        return (self.estimated_cost or 0) * (self.quantity_per_unit or 0)
    
    def __repr__(self):
        return f'<PDProjectBOM {self.project_id} - {self.material_name}>'


class PDComponent(db.Model):
    """Components required for product development - MAKE/BUY/OUTSOURCE"""
    __tablename__ = 'pd_components'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    component_name = db.Column(db.String(200), nullable=False)
    component_type = db.Column(db.Enum('MAKE', 'BUY', 'OUTSOURCE', name='pd_component_type'), nullable=False, default='BUY')
    quantity = db.Column(db.Float, default=1)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    estimated_cost = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    manufacturing_order_id = db.Column(db.Integer, db.ForeignKey('manufacturing_orders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    vendor = db.relationship('Vendor', backref='pd_components', lazy=True)
    purchase_order = db.relationship('PurchaseOrder', backref='pd_components', lazy=True)
    manufacturing_order = db.relationship('ManufacturingOrder', backref='pd_components', lazy=True)
    
    @property
    def cost(self):
        return (self.estimated_cost or 0) * (self.quantity or 0)
    
    def __repr__(self):
        return f'<PDComponent {self.project_id} - {self.component_name}>'


class PDTooling(db.Model):
    """Tooling development - molds, dies, injection, forging"""
    __tablename__ = 'pd_tooling'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    tool_name = db.Column(db.String(200), nullable=False)
    tool_type = db.Column(db.Enum('mold', 'die', 'injection', 'forging', 'jig', 'fixture', 'other', name='pd_tool_type'), nullable=False)
    quantity = db.Column(db.Float, default=1)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    cost = db.Column(db.Float, default=0)
    status = db.Column(db.Enum('Planned', 'In Progress', 'Completed', 'Cancelled', name='pd_tool_status'), default='Planned', index=True)
    expected_completion = db.Column(db.Date, nullable=True)
    actual_completion = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    vendor = db.relationship('Vendor', backref='pd_tooling', lazy=True)
    purchase_order = db.relationship('PurchaseOrder', backref='pd_tooling', lazy=True)
    
    def __repr__(self):
        return f'<PDTooling {self.project_id} - {self.tool_name}>'


class PDTesting(db.Model):
    """Prototype testing - trial production T1, T2, etc."""
    __tablename__ = 'pd_testing'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    trial_number = db.Column(db.Integer, default=1)  # T1, T2, T3
    trial_date = db.Column(db.Date, nullable=True)
    quantity_produced = db.Column(db.Float, default=0)
    rejected_quantity = db.Column(db.Float, default=0)
    test_type = db.Column(db.Enum('Functional', 'Dimensional', 'Final', name='pd_test_type'), default='Functional')
    result = db.Column(db.Enum('PASS', 'FAIL', 'PENDING', name='pd_test_result'), default='PENDING', index=True)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    creator = db.relationship('User', backref='pd_testing', lazy=True)
    
    @property
    def passed_quantity(self):
        return (self.quantity_produced or 0) - (self.rejected_quantity or 0)
    
    @property
    def pass_rate(self):
        if self.quantity_produced and self.quantity_produced > 0:
            return round((self.passed_quantity / self.quantity_produced) * 100, 2)
        return 0
    
    def __repr__(self):
        return f'<PDTesting {self.project_id} - Trial {self.trial_number}>'


class PDApproval(db.Model):
    """Final approval gate before production"""
    __tablename__ = 'pd_approval'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    approval_status = db.Column(db.Enum('Pending', 'Approved', 'Rejected', name='pd_approval_status'), default='Pending', index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approval_date = db.Column(db.DateTime, nullable=True)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approver = db.relationship('User', backref='pd_approvals', lazy=True)
    
    def __repr__(self):
        return f'<PDApproval {self.project_id} - {self.approval_status}>'


class PDAsset(db.Model):
    """Convert tooling to assets when project is completed"""
    __tablename__ = 'pd_assets'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    tooling_id = db.Column(db.Integer, db.ForeignKey('pd_tooling.id'), nullable=True)
    asset_name = db.Column(db.String(200), nullable=False)
    asset_tag = db.Column(db.String(50), unique=True, nullable=True)
    value = db.Column(db.Float, default=0)
    useful_life_years = db.Column(db.Integer, default=5)
    depreciation_method = db.Column(db.String(50), default='Straight Line')
    is_activated = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tooling = db.relationship('PDTooling', backref='pd_assets', lazy=True)
    
    def __repr__(self):
        return f'<PDAsset {self.project_id} - {self.asset_name}>'
