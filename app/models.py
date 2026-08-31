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
    can_view_receiving = db.Column(db.Boolean, default=True)
    can_view_delivering = db.Column(db.Boolean, default=True)
    can_view_activity_logs = db.Column(db.Boolean, default=False)

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
    can_add_receiving = db.Column(db.Boolean, default=False)
    can_add_delivering = db.Column(db.Boolean, default=False)

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
    can_edit_receiving = db.Column(db.Boolean, default=False)
    can_edit_delivering = db.Column(db.Boolean, default=False)

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
    can_delete_receiving = db.Column(db.Boolean, default=False)
    can_delete_delivering = db.Column(db.Boolean, default=False)
    can_delete_activity_logs = db.Column(db.Boolean, default=False)
    
    # New Media Module Permissions
    can_view_media = db.Column(db.Boolean, default=True)
    can_view_media_document = db.Column(db.Boolean, default=True)
    can_add_media = db.Column(db.Boolean, default=False)
    can_delete_media = db.Column(db.Boolean, default=False)

    # Sales Recovery Module Permissions
    can_view_recovery = db.Column(db.Boolean, default=True)
    can_add_recovery = db.Column(db.Boolean, default=False)
    can_edit_recovery = db.Column(db.Boolean, default=False)
    can_delete_recovery = db.Column(db.Boolean, default=False)

    # Quotation Module Permissions
    can_view_quotations = db.Column(db.Boolean, default=True)
    can_add_quotations = db.Column(db.Boolean, default=False)
    can_edit_quotations = db.Column(db.Boolean, default=False)
    can_delete_quotations = db.Column(db.Boolean, default=False)

    # Packing Slip Module Permissions
    # Gates the standalone Packing Slips module (app/routes/packing.py) — the
    # price-free invoice list warehouse/dispatch staff use to issue slips.
    # Deliberately separate from can_*_sales so someone can be given packing
    # access without ever seeing invoice amounts.
    can_view_packing = db.Column(db.Boolean, default=True)
    can_add_packing = db.Column(db.Boolean, default=False)
    can_edit_packing = db.Column(db.Boolean, default=False)
    can_delete_packing = db.Column(db.Boolean, default=False)

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
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    gst_number = db.Column(db.String(20), index=True)
    pan_number = db.Column(db.String(20))
    contact_person = db.Column(db.String(100))
    company_name = db.Column(db.String(150), index=True)
    sub_vendors = db.Column(db.Text, nullable=True) # JSON string of list of sub-vendors
    group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'), nullable=True, index=True)
    shipping_address = db.Column(db.Text)
    payment_method = db.Column(db.String(50), nullable=True)
    payment_terms = db.Column(db.Integer, default=30)  # Days
    credit_limit = db.Column(db.Float, default=0)
    opening_balance = db.Column(db.Float, default=0)  # Balance carried forward into the vendor ledger

    # Banking details
    bank_name = db.Column(db.String(100))
    account_holder_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    swift_code = db.Column(db.String(20))
    ifsc_code = db.Column(db.String(20))

    is_active = db.Column(db.Boolean, default=True)
    image_path = db.Column(db.String(255))  # Path to vendor image
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bills = db.relationship('PurchaseBill', backref='vendor', lazy=True, cascade='all, delete-orphan')
    advances = db.relationship('VendorAdvance', backref='vendor', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_purchases(self):
        return sum(bill.total - bill.shipping_charge for bill in self.bills)
    
    @property
    def outstanding_balance(self):
        return sum(bill.balance_due for bill in self.bills if bill.status != 'paid')

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
    
    @property
    def sub_vendors_list(self):
        """Parse the JSON string of sub-vendors into a list"""
        import json
        if self.sub_vendors:
            try:
                return json.loads(self.sub_vendors)
            except:
                return []
        return []

    def __repr__(self):
        return f'<Vendor {self.name}>'


class CustomerGroup(db.Model):
    """Customer Group model"""
    __tablename__ = 'customer_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=True)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    gst_number = db.Column(db.String(20), index=True)
    pan_number = db.Column(db.String(20))
    contact_person = db.Column(db.String(100))
    company_name = db.Column(db.String(150), index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'), nullable=True, index=True)
    payment_method = db.Column(db.String(50), nullable=True)
    payment_terms = db.Column(db.Integer, default=30)  # Days
    credit_limit = db.Column(db.Float, default=0)
    opening_balance = db.Column(db.Float, default=0)
    sub_customers = db.Column(db.Text, nullable=True) # JSON string of list of sub-customers
    image_path = db.Column(db.String(255), nullable=True)  # Path to customer image
    is_active = db.Column(db.Boolean, default=True)
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy=True, cascade='all, delete-orphan')
    quotations = db.relationship('Quotation', backref='customer', lazy=True, cascade='all, delete-orphan')
    advances = db.relationship('CustomerAdvance', backref='customer', lazy=True, cascade='all, delete-orphan')
    
    access_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    token_expiry = db.Column(db.DateTime, nullable=True)

    @property
    def valid_access_token(self):
        import uuid
        from datetime import datetime, timedelta
        from app import db
        if not self.access_token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self.access_token = str(uuid.uuid4())
            self.token_expiry = datetime.utcnow() + timedelta(days=30) # Ledgers last longer
            db.session.commit()
        return self.access_token
    
    @property
    def total_sales(self):
        """Total of approved sales only"""
        return sum(sale.total for sale in self.sales if sale.is_approved)
    
    @property
    def outstanding_balance(self):
        """Outstanding balance from approved sales only"""
        return sum(sale.total - sale.paid_amount for sale in self.sales if sale.status != 'paid' and sale.is_approved)

    @property
    def health_status(self):
        """
        Determine customer health flag color based on overdue invoices.
        - 'danger' (Red): 30+ days overdue
        - 'warning' (Yellow): Overdue but < 30 days
        - 'success' (Green): No overdue invoices
        """
        # We only care about approved sales that are overdue
        overdue_sales = [s for s in self.sales if s.is_overdue and s.is_approved]
        if not overdue_sales:
            return 'success'
        
        # Check if any sale is 30+ days overdue
        # (days_overdue property was added to Sale model in previous step)
        if any(s.days_overdue >= 30 for s in overdue_sales):
            return 'danger'
        
        return 'warning'
    
    @property
    def total_delivery_charges(self):
        return sum(sale.delivery_charge for sale in self.sales if hasattr(sale, 'delivery_charge'))

    @property
    def total_advances_received(self):
        """Total of approved advances only"""
        return sum(adv.amount for adv in self.advances if adv.is_approved)

    @property
    def total_advances_adjusted(self):
        return sum(adv.applied_amount for adv in self.advances)

    @property
    def remaining_advance_balance(self):
        return self.total_advances_received - self.total_advances_adjusted
    
    @property
    def sub_customers_list(self):
        """Parse the JSON string of sub-customers into a list"""
        import json
        if self.sub_customers:
            try:
                return json.loads(self.sub_customers)
            except:
                return []
        return []

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
    # Links this salesman to a login user so Sales Recovery reminders pop up
    # only for that user when they are logged in.
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sales = db.relationship('Sale', backref='salesman', lazy=True)
    quotations = db.relationship('Quotation', backref='salesman', lazy=True)
    login_user = db.relationship('User', foreign_keys=[user_id], backref='linked_salesmen', lazy=True)

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
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def total_products_count(self):
        """Returns the number of unique products that have stock in this warehouse"""
        # Count from ProductWarehouseStock
        multi_stock_ids = {s.product_id for s in self.product_stocks if s.quantity > 0}
        # Count from legacy Product.warehouse_id
        legacy_ids = {p.id for p in self.products if p.quantity > 0}
        return len(multi_stock_ids.union(legacy_ids))

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
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    def margin_percent(self):
        if self.unit_price > 0:
            return ((self.unit_price - self.cost_price) / self.unit_price) * 100
        return 0

    @property
    def margin_color(self):
        # Profit-margin colouring only applies to finished goods (manufactured
        # items). Raw materials / other items keep their default colour.
        if not self.is_manufactured:
            return ''
        m = self.margin_percent
        if m < 25:
            return 'danger'
        if m < 30:
            return 'warning'
        return ''

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


class ProductWarehouseStock(db.Model):
    """Tracks per-warehouse stock quantity for a product.
    Allows one product to have stock across multiple warehouses simultaneously.
    Updated by Tool Receiving (adds) and Tool Delivering (subtracts).
    """
    __tablename__ = 'product_warehouse_stock'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, default=0)
    __table_args__ = (db.UniqueConstraint('product_id', 'warehouse_id', name='uq_product_warehouse'),)

    product = db.relationship('Product', backref='warehouse_stocks', lazy=True)
    warehouse = db.relationship('Warehouse', backref='product_stocks', lazy=True)

    def __repr__(self):
        return f'<ProductWarehouseStock product={self.product_id} warehouse={self.warehouse_id} qty={self.quantity}>'


class ProductCategory(db.Model):
    """Product Category model"""
    __tablename__ = 'product_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'

class Unit(db.Model):
    """Unit of Measure model"""
    __tablename__ = 'units'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Unit {self.name}>'


class ActivityLog(db.Model):
    """Model for tracking user activities across the dashboard"""
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    module = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'Sales', 'Purchase', 'Inventory'
    action = db.Column(db.String(100), nullable=False) # e.g., 'Created Sale', 'Updated Vendor'
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))
    
    user = db.relationship('User', backref=db.backref('activity_logs', lazy=True))

    def __repr__(self):
        return f'<ActivityLog {self.module}:{self.action} by User {self.user_id}>'


class Sale(db.Model):
    """Sales/Invoice model"""
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    due_date = db.Column(db.DateTime)
    overdue_date = db.Column(db.DateTime, nullable=True)
    # Optional per-tranche payment plan, e.g. [{"amount": 20000, "due_date": "2026-07-10"}, ...].
    # Independent of due_date above — see get_installment_status() for per-tranche overdue tracking.
    installment_schedule = db.Column(db.Text, nullable=True)
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), nullable=True)
    exchange_rate = db.Column(db.Float, default=1)
    subtotal = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)  # Tax percentage
    tax = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(10), default='fixed')  # fixed or percentage
    discount = db.Column(db.Float, default=0)
    delivery_charge = db.Column(db.Float, default=0)  # Delivery cost
    advance_applied = db.Column(db.Float, default=0)  # Advance amount applied to this invoice
    ignore_overdue_discount = db.Column(db.Boolean, default=False)
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
    access_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    # Approval workflow: staff-created invoices require admin approval before counting in sales totals
    is_approved = db.Column(db.Boolean, default=True, index=True)  # True for admin-created, False for staff-created
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    # Draft lifecycle flag (separate from is_approved/is_rejected). A draft is a
    # held invoice: not approved, not rejected, not counted as an active sale.
    is_draft = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    discount_violation = db.Column(db.Text, nullable=True)
    stock_updated = db.Column(db.Boolean, default=False)
    # Top-of-page overdue notification banner: once an admin dismisses it for
    # this invoice, it never reappears (regardless of days_overdue).
    overdue_alert_dismissed = db.Column(db.Boolean, default=False)
    
    # Relationships
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')
    returns = db.relationship('SaleReturn', backref='sale', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='invoice', lazy=True, cascade='all, delete-orphan')

    currency = db.relationship('Currency', backref='sales', lazy=True)
    
    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return self.total - self.paid_amount
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if self.status != 'paid':
            check_date = self.due_date.date() if self.due_date else self.date.date()
            return datetime.utcnow().date() > check_date
        return False
    
    @property
    def days_overdue(self):
        """Calculate days since due date"""
        if self.is_overdue:
            check_date = self.due_date.date() if self.due_date else self.date.date()
            delta = datetime.utcnow().date() - check_date
            return delta.days
        return 0

    @property
    def show_overdue_alert(self):
        """
        Whether this invoice should currently appear in the top-of-page
        overdue notification banner: starts once the invoice is 3 days
        overdue, and auto-disappears after being shown for 2 days (i.e. by
        day 5) unless an admin dismisses it sooner via overdue_alert_dismissed.
        """
        if self.overdue_alert_dismissed or not self.is_overdue:
            return False
        return 3 <= self.days_overdue < 5

    @property
    def invoice_health_status(self):
        """
        Per-invoice flag color based on THIS invoice's overdue status.
        - 'danger' (Red): 30+ days overdue
        - 'warning' (Yellow): Overdue but < 30 days
        - 'success' (Green): Not overdue (paid, on-time, or no due date passed)
        """
        if self.status == 'paid':
            return 'success'
        if self.is_overdue:
            if self.days_overdue >= 30:
                return 'danger'
            return 'warning'
        return 'success'

    @property
    def installments(self):
        """Parsed, sorted installment schedule: [{'amount': float, 'due_date': 'YYYY-MM-DD'}, ...].
        JSON-safe (plain str/float), so it can be passed straight to |tojson in templates."""
        if not self.installment_schedule:
            return []
        import json
        try:
            data = json.loads(self.installment_schedule)
        except (ValueError, TypeError):
            return []
        parsed = []
        for item in data:
            try:
                amount = float(item.get('amount', 0) or 0)
                due_date = str(item.get('due_date', ''))
                datetime.strptime(due_date, '%Y-%m-%d')  # validate format
                if amount > 0 and due_date:
                    parsed.append({'amount': amount, 'due_date': due_date})
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
        parsed.sort(key=lambda i: i['due_date'])
        return parsed

    def get_installment_status(self):
        """
        Per-tranche payment status, independent of is_overdue/due_date above.
        Walks the schedule in due-date order, applying paid_amount against each
        tranche in turn (earliest first). A tranche is 'overdue' only if its own
        date has passed and it isn't yet fully covered by payments received so far.
        """
        schedule = self.installments
        if not schedule:
            return []
        today = datetime.utcnow().date()
        remaining = float(self.paid_amount or 0)
        result = []
        for inst in schedule:
            amount = inst['amount']
            due = datetime.strptime(inst['due_date'], '%Y-%m-%d').date()
            if remaining >= amount:
                status = 'paid'
                shortfall = 0.0
                remaining -= amount
            else:
                shortfall = amount - remaining
                status = 'overdue' if due < today else 'upcoming'
                remaining = 0.0
            result.append({
                'amount': amount,
                'due_date': due,
                'status': status,
                'shortfall': shortfall,
            })
        return result

    @property
    def has_overdue_installment(self):
        return any(i['status'] == 'overdue' for i in self.get_installment_status())

    @property
    def installment_overdue_days(self):
        """Days overdue for the worst (longest-overdue) unpaid installment tranche, or 0."""
        overdue_rows = [i for i in self.get_installment_status() if i['status'] == 'overdue']
        if not overdue_rows:
            return 0
        today = datetime.utcnow().date()
        return max((today - i['due_date']).days for i in overdue_rows)

    @property
    def effective_is_overdue(self):
        """
        Display-facing overdue flag used for the invoice list/detail status badge
        AND the recovery automation trigger: overdue if EITHER the single
        due_date has passed (is_overdue) OR at least one installment tranche is
        overdue on its own date. Kept separate from is_overdue so
        calculate_totals()'s overdue-discount-suspension rule (which should only
        ever key off the invoice's own due_date) is unaffected by installment
        schedules.
        """
        return self.is_overdue or self.has_overdue_installment

    @property
    def effective_days_overdue(self):
        """Day count to display alongside effective_is_overdue — the worse of the
        single due_date's overdue days and the worst overdue installment tranche."""
        return max(self.days_overdue, self.installment_overdue_days)

    @property
    def overdue_amount(self):
        """
        The amount that is actually overdue right now — not the whole balance.
        For an installment invoice, only the shortfall on tranches whose own
        date has passed (future tranches aren't due yet, so they don't count).
        For a plain invoice, the full balance once the single due_date passes
        (unchanged behavior).
        """
        if self.installments:
            return sum(i['shortfall'] for i in self.get_installment_status() if i['status'] == 'overdue')
        return self.balance_due if self.is_overdue else 0.0

    def update_status(self):
        """Update payment status based on paid amount"""
        if self.paid_amount >= self.total:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'unpaid'
        self.updated_at = datetime.utcnow()
        self._sync_recovery_task()

    def _sync_recovery_task(self):
        """Keep the linked RecoveryTask (Sales Recovery module) in sync so a
        paid, cancelled, draft, or rejected invoice drops off the recovery dashboard immediately,
        regardless of which payment/status route triggered the change."""
        rtask = self.recovery_task
        is_inactive = (self.status in ('paid', 'cancelled')) or self.is_draft or self.is_rejected

        # Standalone linked tasks without a RecoveryTask object should also be cancelled if invoice is inactive
        if not rtask:
            if is_inactive:
                linked_tasks = Task.query.filter(
                    Task.linked_invoice_id == self.id,
                    Task.status.in_(['Pending', 'In Progress'])
                ).all()
                for t in linked_tasks:
                    t.status = 'Cancelled'
                    t.is_notification_shown = True
            return

        # A written-off task is an intentional admin decision — never auto-touch it.
        if rtask.recovery_status == 'CLOSED_WRITTEN_OFF':
            return

        # A task auto-closed as paid/inactive must REOPEN if the invoice becomes active & unpaid
        # again — e.g. a payment is reversed/deleted or an applied advance is
        # undone in the Sales module. Otherwise the invoice silently stays closed
        # and never returns to the recovery dashboard.
        if rtask.recovery_status == 'CLOSED_PAID':
            if is_inactive:
                return  # still inactive — leave it closed
            rtask.recovery_status = 'PARTIAL_RECOVERY' if self.status == 'partial' else 'OVERDUE'
            rtask.closed_at = None
            rtask.closed_reason = None
            rtask.closed_by = None
            rtask.salesman_id = self.salesman_id
            rtask.updated_at = datetime.utcnow()
            db.session.add(RecoveryLog(
                task_id=rtask.id,
                response_type='general',
                note='Reopened: invoice status changed back to active unpaid/partial.',
            ))
            # Bring back a live popup reminder for the responsible salesman.
            from app.services.recovery_automation import _ensure_reminder
            _ensure_reminder(rtask)
            return

        # If the invoice was reassigned to a different salesman, the recovery
        # task must follow it — otherwise reminders keep popping up for
        # whoever used to own it instead of the salesman who is actually
        # responsible for this invoice now.
        if rtask.salesman_id != self.salesman_id:
            from app.services.recovery_automation import _cancel_reminders, _ensure_reminder
            _cancel_reminders(rtask)  # any open popup was addressed to the old salesman
            rtask.salesman_id = self.salesman_id
            if not is_inactive:
                _ensure_reminder(rtask)  # raise a fresh one for the new salesman right away

        if is_inactive:
            rtask.recovery_status = 'CLOSED_PAID'
            rtask.closed_at = datetime.utcnow()
            for t in rtask.reminder_tasks:
                if t.status in ('Pending', 'In Progress'):
                    t.status = 'Cancelled'
                    t.is_notification_shown = True
                    t.is_escalation_broadcast_shown = True
                    t.is_completion_broadcast_shown = True
            linked_tasks = Task.query.filter(
                Task.linked_invoice_id == self.id,
                Task.status.in_(['Pending', 'In Progress'])
            ).all()
            for t in linked_tasks:
                t.status = 'Cancelled'
                t.is_notification_shown = True
        elif self.status == 'partial':
            if rtask.recovery_status not in ('PROMISED_PAYMENT', 'FOLLOW_UP_REQUIRED'):
                rtask.recovery_status = 'PARTIAL_RECOVERY'

    def calculate_totals(self):
        """Calculate invoice totals including delivery, returns and discounts"""
        # Calculate base from items
        items_subtotal = sum(item.total for item in self.items)
        items_tax = items_subtotal * (self.tax_rate / 100)
        
        # Deduct returns (using ret.total which accounts for subtotal + tax - return_discount)
        returns_total = sum(ret.total for ret in self.returns)
        
        self.subtotal = items_subtotal - sum(ret.subtotal for ret in self.returns)
        self.tax = items_tax - sum(ret.tax for ret in self.returns)
        # Total will be calculated later including delivery and discount, 
        # but we need to ensure returns_total is subtracted at the end.
        
        # Check if overdue rule applies to this customer's group
        rule_applies = False
        settings = InvoiceSettings.query.first()
        if settings:
            from app.models import CustomerGroup # Ensure available or use relationship
            restricted_groups = settings.restricted_group_ids
            if self.customer and self.customer.group_id in restricted_groups:
                rule_applies = True
        
        # Calculate discount - suspended if overdue unless forced AND rule applies
        # Important: discount is usually on original price, but we should be careful 
        # not to let total go negative if returns are large.
        if self.is_overdue and not self.ignore_overdue_discount and rule_applies:
            discount_amount = 0
        else:
            if self.discount_type == 'percentage':
                # Apply percentage discount to ORIGINAL subtotal or net? 
                # Usually original, but here we'll use items_subtotal to be safe.
                discount_amount = items_subtotal * (self.discount / 100)
            else:
                discount_amount = self.discount
                
        # The discount applies as soon as it is entered — a staff-created
        # invoice sitting in Pending still shows and charges the discounted
        # total. Approval is a review step, not a gate on the discount (the
        # invoice itself still waits for admin approval before counting as an
        # approved sale). The overdue suspension above is a separate rule and
        # still stands.
        applied_discount = discount_amount


        # Calculate total = subtotal + tax + delivery - applied_discount - returns_total
        # Note: self.subtotal and self.tax already had returns deducted, 
        # but we use returns_total to ensure return-specific discounts are also handled.
        # Actually, if we use ret.total, we are subtracting (subtotal + tax - disc).
        # Since self.subtotal and self.tax ALREADY subtracted ret.subtotal and ret.tax,
        # subtracting ret.total would be double counting subtotal/tax.
        
        # CORRECT LOGIC:
        # Grand Total = (ItemsSubtotal + ItemsTax + Delivery - ItemsDiscount) - (ReturnsTotal)
        # However, self.subtotal/tax are already returns-deducted.
        
        self.total = self.subtotal + self.tax + self.delivery_charge - applied_discount
        # Add back any return discounts that were subtracted twice if using self.subtotal
        # Actually, let's keep it simple:
        # Total = Subtotal + Tax + Delivery - Discount
        # Since Subtotal and Tax are already net-of-returns, this is correct.
        # BUT we must also SUBTRACT the return discounts to the customer (they get back less).
        # Wait, if they get back LESS, the invoice total should go down by LESS.
        # So we should actually ADD the return discounts to the total.
        
        return_discounts = sum(ret.discount for ret in self.returns)
        self.total += return_discounts
        
        # Ensure total is not negative
        if self.total < 0:
            self.total = 0
        
        # Ensure total is not negative
        if self.total < 0:
            self.total = 0

        # Check Product Discount Conditions: each item's OWN discount is validated
        # against that item's product-specific min/max rule (mirrors the same
        # per-item check performed in routes/sales.py at invoice create/edit time).
        violations = []
        if settings and settings.product_discount_conditions:
            import json
            try:
                conditions = json.loads(settings.product_discount_conditions)
                rules_by_product = {c['product_id']: c for c in conditions if 'product_id' in c}
                for item in self.items:
                    cond = rules_by_product.get(item.product_id)
                    if not cond:
                        continue
                    min_allowed = float(cond.get('min_discount', 0))
                    max_allowed = float(cond.get('max_discount', 0))
                    item_discount = item.discount or 0
                    product_label = item.product.name if item.product else f"Product #{item.product_id}"

                    if item_discount < min_allowed:
                        violations.append(f"{product_label}: Discount PKR {item_discount} is less than Rule Minimum (PKR {min_allowed})")
                    if max_allowed > 0 and item_discount > max_allowed:
                        violations.append(f"{product_label}: Discount PKR {item_discount} is greater than Rule Maximum (PKR {max_allowed})")
            except:
                pass

        if violations:
            self.discount_violation = "; ".join(violations)
        else:
            self.discount_violation = None
            
    @property
    def is_discount_restricted(self):
        """Check if the overdue discount restriction is currently active for this sale"""
        if not self.is_overdue or self.ignore_overdue_discount:
            return False
            
        settings = InvoiceSettings.query.first()
        if settings:
            restricted_groups = settings.restricted_group_ids
            if self.customer and self.customer.group_id in restricted_groups:
                return True
        return False

    @property
    def base_discount_amount(self):
        """Calculated PKR amount of the discount BEFORE any overdue restrictions"""
        if self.discount_type == 'percentage':
            return (self.subtotal or 0) * ((self.discount or 0) / 100)
        return self.discount or 0

    @property
    def effective_discount_amount(self):
        """Calculated PKR amount of the discount AFTER applying overdue restrictions"""
        if self.is_discount_restricted:
            return 0
        return self.base_discount_amount

    @property
    def valid_access_token(self):
        import uuid
        from datetime import datetime, timedelta
        from app import db
        if not self.access_token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self.access_token = str(uuid.uuid4())
            self.token_expiry = datetime.utcnow() + timedelta(days=7)
            db.session.commit()
        return self.access_token
    
    def __repr__(self):
        return f'<Sale {self.invoice_number}>'

class SaleItem(db.Model):
    """Sales item details"""
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    # Discount per unit, as typed on the invoice form. `discount` stays the
    # whole-line figure (unit_discount x quantity) so every existing consumer —
    # totals, returns, reports, P&L — keeps working untouched.
    unit_discount = db.Column(db.Float, default=0)
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

    @property
    def effective_unit_discount(self):
        """Per-unit discount for display.

        Rows created before per-unit discounts existed only carry a line total,
        so derive the per-unit figure from it rather than showing zero.
        """
        if self.unit_discount:
            return self.unit_discount
        if self.discount and self.quantity:
            return self.discount / self.quantity
        return 0
    
    @property
    def return_quantity(self):
        """Sum of quantity returned for this product on this sale"""
        total_returned = 0
        if self.sale and self.sale.returns:
            for ret in self.sale.returns:
                for item in ret.items:
                    if item.product_id == self.product_id:
                        total_returned += item.quantity
        return total_returned

    @property
    def returned_discount(self):
        """Sum of this item's discount already prorated to returns of this product on this sale"""
        total_returned = 0
        if self.sale and self.sale.returns:
            for ret in self.sale.returns:
                for item in ret.items:
                    if item.product_id == self.product_id:
                        total_returned += item.discount or 0
        return total_returned

    @property
    def remaining_discount(self):
        """This item's original discount minus the portion already prorated away to returns"""
        return max((self.discount or 0) - self.returned_discount, 0)

    def __repr__(self):
        return f'<SaleItem {self.sale_id} - {self.product_id}>'


class Quotation(db.Model):
    """Standalone Quotation — a lightweight pre-sale document. Unlike Sale it
    never touches stock, has no payments/returns/advance handling, and has no
    admin-approval workflow. Can be converted into a real Sale once accepted."""
    __tablename__ = 'quotations'

    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.id'), index=True, nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    due_date = db.Column(db.DateTime, nullable=True)  # "Valid Until"
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), nullable=True)
    exchange_rate = db.Column(db.Float, default=1)
    subtotal = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(10), default='fixed')
    discount = db.Column(db.Float, default=0)
    delivery_charge = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='draft', index=True)  # draft, sent, accepted, rejected, expired
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    access_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    converted_sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('QuotationItem', backref='quotation', lazy=True, cascade='all, delete-orphan')
    currency = db.relationship('Currency', backref='quotations', lazy=True)
    converted_sale = db.relationship('Sale', foreign_keys=[converted_sale_id], backref='source_quotation', uselist=False, lazy=True)

    STATUS_LABELS = {
        'draft': 'DRAFT',
        'sent': 'SENT',
        'accepted': 'ACCEPTED',
        'rejected': 'REJECTED',
        'expired': 'EXPIRED',
    }

    @property
    def invoice_number(self):
        """Compat shim: generate_professional_pdf() reads obj.invoice_number
        regardless of document type — see app/pdf_utils.py."""
        return self.quotation_number

    @property
    def is_draft(self):
        return self.status == 'draft'

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, 'DRAFT')

    @property
    def is_expired_pending(self):
        """"Valid Until" has passed while this quotation still awaits a
        decision — not a draft, not yet accepted, and not rejected. Powers
        the top-of-page notification banner on the Quotation module pages."""
        if self.status in ('draft', 'accepted', 'rejected'):
            return False
        if not self.due_date:
            return False
        return datetime.utcnow().date() > self.due_date.date()

    @property
    def days_expired(self):
        if not self.is_expired_pending:
            return 0
        return (datetime.utcnow().date() - self.due_date.date()).days

    @property
    def effective_discount_amount(self):
        return self.discount or 0

    @property
    def warehouse_names(self):
        """Distinct warehouse names tagged across this quotation's line items,
        in first-seen order — a quotation can span more than one warehouse."""
        names = []
        for item in self.items:
            if item.warehouse and item.warehouse.name not in names:
                names.append(item.warehouse.name)
        return names

    @property
    def valid_access_token(self):
        import uuid
        from datetime import datetime, timedelta
        from app import db
        if not self.access_token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self.access_token = str(uuid.uuid4())
            self.token_expiry = datetime.utcnow() + timedelta(days=7)
            db.session.commit()
        return self.access_token

    def calculate_totals(self):
        """Recompute subtotal/tax/total from line items (no returns/delivery-discount
        overdue logic — those only apply to real Sales)."""
        items_subtotal = sum(item.total for item in self.items)
        self.subtotal = items_subtotal
        self.tax = items_subtotal * (self.tax_rate / 100)

        if self.discount_type == 'percentage':
            discount_amount = items_subtotal * ((self.discount or 0) / 100)
        else:
            discount_amount = self.discount or 0

        self.total = self.subtotal + self.tax + self.delivery_charge - discount_amount
        if self.total < 0:
            self.total = 0

    def __repr__(self):
        return f'<Quotation {self.quotation_number}>'


class QuotationItem(db.Model):
    """Quotation line item — mirrors SaleItem, including an optional warehouse
    tag per line (quotations still don't touch stock, but recording the
    intended warehouse up front lets it carry straight through on convert-to-sale)."""
    __tablename__ = 'quotation_items'

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    unit_discount = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    delivery_fee = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='quotation_items', lazy=True)
    warehouse = db.relationship('Warehouse', foreign_keys=[warehouse_id], lazy=True)

    @property
    def net_total(self):
        return self.total - self.discount

    @property
    def item_subtotal(self):
        return self.quantity * self.unit_price

    @property
    def effective_unit_discount(self):
        if self.unit_discount:
            return self.unit_discount
        if self.discount and self.quantity:
            return self.discount / self.quantity
        return 0

    @property
    def remaining_discount(self):
        """No returns concept for quotations, so nothing is ever prorated away —
        kept as a property (rather than reusing `discount` directly) so
        generate_professional_pdf()'s shared per-item discount block, which
        expects this attribute name, works unmodified."""
        return self.discount or 0

    def __repr__(self):
        return f'<QuotationItem {self.quotation_id} - {self.product_id}>'


class SaleReturnItem(db.Model):
    """Sales return item details"""
    __tablename__ = 'sale_return_items'

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('sale_returns.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='return_items', lazy=True)
    warehouse = db.relationship('Warehouse', foreign_keys=[warehouse_id], lazy=True)

    @property
    def net_total(self):
        """Total after this item's prorated discount"""
        return self.total - (self.discount or 0)

    def __repr__(self):
        return f'<SaleReturnItem {self.return_id} - {self.product_id}>'

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
    status = db.Column(Enum('paid', 'unpaid', 'partial', 'return', 'partial_return', 'cancelled', name='payment_status'), default='unpaid', index=True)
    paid_amount = db.Column(db.Float, default=0)
    cancelled_amount = db.Column(db.Float, default=0)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    bill_image_path = db.Column(db.String(255))  # Path to uploaded bill image
    notes = db.Column(db.Text)
    inventory_received = db.Column(db.Boolean, default=False)  # True when stock has been received into inventory
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    access_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    # Approval workflow: staff-created bills require admin approval before counting in totals
    is_approved = db.Column(db.Boolean, default=True, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    # ── Action-approval workflow (Cancel Remaining / Reverse Cancellation) ──
    # When a non-admin (staff/manager) requests one of these actions, it is held
    # here until an admin approves. Nothing on the bill changes until approval.
    pending_action = db.Column(db.String(20), nullable=True)          # 'cancel' | 'reverse' | None
    pending_action_reason = db.Column(db.Text, nullable=True)          # optional reason from requester
    pending_action_payload = db.Column(db.Text, nullable=True)         # JSON: {purchase_item_id: cancel_qty}
    pending_action_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    pending_action_at = db.Column(db.DateTime, nullable=True)

    @property
    def pending_action_requester(self):
        """The user who requested the pending cancel/reverse action (or None)."""
        if not self.pending_action_by:
            return None
        return User.query.get(self.pending_action_by)

    @property
    def pending_action_label(self):
        """Human label for the pending action type."""
        return {
            'cancel': 'Cancel Remaining',
            'reverse': 'Reverse Cancellation',
        }.get(self.pending_action)

    # Relationships
    items = db.relationship('PurchaseItem', backref='bill', lazy=True, cascade='all, delete-orphan')
    bill_payments = db.relationship('BillPayment', backref='bill', lazy=True, cascade='all, delete-orphan')
    bill_receives = db.relationship('BillReceive', backref='bill', lazy=True, cascade='all, delete-orphan')
    cost_price_history = db.relationship('CostPriceHistory', back_populates='purchase_bill', lazy=True, cascade='all, delete-orphan', overlaps="cost_price_changes,bill")

    currency = db.relationship('Currency', backref='purchase_bills', lazy=True)
    
    @property
    def balance_due(self):
        """Calculate remaining balance owed to vendor (excludes shipping)"""
        vendor_payable = self.total - self.shipping_charge
        balance = vendor_payable - self.paid_amount - self.cancelled_amount
        return max(0, balance)
    
    @property
    def shipping_due(self):
        """Calculate remaining shipping charge not yet paid"""
        vendor_payable = self.total - self.shipping_charge
        if self.paid_amount > vendor_payable:
            shipping_paid = self.paid_amount - vendor_payable
            if shipping_paid > self.shipping_charge:
                shipping_paid = self.shipping_charge
        else:
            shipping_paid = 0
        return max(0, self.shipping_charge - shipping_paid)
    
    @property
    def is_overdue(self):
        """Check if bill is overdue"""
        if self.status != 'paid' and self.due_date:
            return datetime.utcnow().date() > self.due_date.date()
        return False
    
    def update_status(self):
        """Update payment status based on paid amount towards vendor (excludes shipping)"""
        vendor_payable = self.total - self.shipping_charge
        if self.status == 'cancelled':
            return
            
        if self.paid_amount + self.cancelled_amount >= vendor_payable:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'unpaid'
        self.updated_at = datetime.utcnow()
    
    def calculate_totals(self):
        """Calculate bill totals net of returns"""
        items_subtotal = sum(item.total for item in self.items)
        items_tax = items_subtotal * (self.tax_rate / 100)
        
        # Calculate returns to deduct
        returns_subtotal = sum(ret.subtotal for ret in self.purchase_returns) if hasattr(self, 'purchase_returns') else 0
        returns_tax = sum(ret.tax for ret in self.purchase_returns) if hasattr(self, 'purchase_returns') else 0
        
        self.subtotal = items_subtotal - returns_subtotal
        self.tax = items_tax - returns_tax
        
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
            
    @property
    def valid_access_token(self):
        import uuid
        from datetime import datetime, timedelta
        from app import db
        if not self.access_token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self.access_token = str(uuid.uuid4())
            self.token_expiry = datetime.utcnow() + timedelta(days=7)
            db.session.commit()
        return self.access_token
    
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
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    total = db.Column(db.Float, nullable=False)
    cancelled_quantity = db.Column(db.Float, default=0)
    
    warehouse = db.relationship('Warehouse', backref='purchase_items', lazy=True)
    
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

    # Relationship moved to Sale model for cascade deletion
    # invoice = db.relationship('Sale', backref='transactions', lazy=True)
    
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
    # Lump-sum discount granted at the moment this payment was recorded (the
    # "Lump Sum" option on the payment popups). The discount itself lives on the
    # invoice/items exactly like a discount given from the Apply Discount modal —
    # these two columns only record what was granted with this payment and the
    # proof supplied for it, so it stays auditable from the Payment History.
    lump_discount_amount = db.Column(db.Float, default=0)
    lump_discount_proof = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    # `is_approved` is the MONEY flag: True means this amount is already included
    # in Sale.paid_amount. Every add/reverse path (approve/reject/edit/delete)
    # keys off it, so it must never be True without the money being applied.
    is_approved = db.Column(db.Boolean, default=False, index=True)  # True for admin-created, False for staff-created
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    # `needs_approval` is the REVIEW flag, independent of the money flag above.
    # A staff-recorded payment is applied to the invoice straight away
    # (is_approved=True) but still raises an admin approval request
    # (needs_approval=True) — admin approving only clears this flag, and
    # rejecting reverses the money. Legacy rows keep needs_approval=False and
    # continue through the original "approve to apply" path.
    needs_approval = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    # Relationship moved to Sale model for cascade deletion
    # invoice = db.relationship('Sale', backref='payments', lazy=True)
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
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentMethod {self.name}>'


class ExpenseSource(db.Model):
    """A reference tag for where the money in a debit ('Add Money')
    ExpenseAccountTransaction actually came from (e.g. Owner Investment, Bank
    Loan, Sales Collection). Purely descriptive/for filtering — unlike
    ExpenseAccount it carries no balance of its own. Managed the same way as
    ExpenseCategory: admins add entries via the "Add Source" button, and any
    logged-in user can pick from the list when recording a debit."""
    __tablename__ = 'expense_sources'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<ExpenseSource {self.name}>'


class ExpenseAccount(db.Model):
    """A named account (e.g. Cash, Bank, Owner) that Expenses and Fixed
    Expenses can be charged against — entirely independent of the Journal
    module's own JournalAccount. The Expense module owns and manages its own
    accounts end to end (create/edit/delete, debit/credit, balance) rather
    than sharing state with Journal, which keeps its own accounts separately."""
    __tablename__ = 'expense_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    account_type = db.Column(db.String(50), nullable=True)   # optional label: Cash / Bank / Income …
    opening_balance = db.Column(db.Float, default=0)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    custodian_name = db.Column(db.String(120), nullable=True)
    location = db.Column(db.String(120), nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    linked_funding_account_id = db.Column(db.Integer, db.ForeignKey('expense_accounts.id'), nullable=True)
    linked_funding_account = db.relationship('ExpenseAccount', remote_side=[id])

    # Set when this account was auto-created for an HR staff member (see
    # _ensure_staff_expense_account in app/routes/salary.py) — one account
    # per staff member, so it can be found again on later edits instead of
    # creating a duplicate.
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True, unique=True)
    staff = db.relationship('Staff', backref=db.backref('expense_account', uselist=False))

    @property
    def total_debit(self):
        return sum((t.amount or 0) for t in self.transactions if t.entry_type == 'debit' and t.is_approved)

    @property
    def total_credit(self):
        return sum((t.amount or 0) for t in self.transactions if t.entry_type == 'credit' and t.is_approved)

    @property
    def balance(self):
        """Running balance: opening + debits (money in) − credits (money out).
        Only approved transactions count, same convention as the rest of the
        app's balance figures."""
        return (self.opening_balance or 0) + self.total_debit - self.total_credit

    def __repr__(self):
        return f'<ExpenseAccount {self.name}>'


class ExpenseAccountTransaction(db.Model):
    """One debit or credit movement against an ExpenseAccount. Unlike the
    Journal module's two-table JournalEntry+JournalLine design, this is a
    single row per movement — an Expense (or a Fixed Expense cycle) only ever
    posts one account movement at a time, so there's no need for a
    multi-line "entry" wrapper.

    entry_type='credit' means money OUT of the account (a real expense —
    expense_id is set). entry_type='debit' means money IN to the account (a
    plain "add money" transaction — expense_id stays None, since debit
    transactions never create an Expense record)."""
    __tablename__ = 'expense_account_transactions'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('expense_accounts.id'), nullable=False, index=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True, index=True)
    # Only ever set directly on a debit ("Add Money") row — a credit row
    # linked to an Expense shows its customer/warehouse via expense.customer/
    # expense.warehouse instead, same as Expense's own fields.
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    # Only ever set on a debit ("Add Money") row — where that incoming money
    # actually came from (see ExpenseSource). Required in the UI for new
    # debit entries, but nullable here so older rows recorded before this
    # field existed stay valid.
    source_id = db.Column(db.Integer, db.ForeignKey('expense_sources.id'), nullable=True, index=True)

    date = db.Column(db.Date, nullable=False, index=True)
    entry_type = db.Column(db.String(10), nullable=False, default='credit')  # 'debit' | 'credit'
    amount = db.Column(db.Float, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    reference = db.Column(db.String(120), nullable=True)
    bill_image_path = db.Column(db.String(255), nullable=True)

    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # transaction_type distinguishes what kind of movement this row represents,
    # since entry_type alone only says debit/credit direction, not the source
    # ('expense' rows always carry an expense_id; 'transfer' rows always come
    # in pairs sharing transfer_group; 'add_money' is the older single-sided
    # manual debit path with no counterparty).
    transaction_type = db.Column(db.String(20), nullable=False, default='expense')
    counterparty_account_id = db.Column(db.Integer, db.ForeignKey('expense_accounts.id'), nullable=True)
    transfer_group = db.Column(db.String(36), nullable=True, index=True)
    payee = db.Column(db.String(160), nullable=True)

    is_draft = db.Column(db.Boolean, default=False, index=True)
    is_reversed = db.Column(db.Boolean, default=False, index=True)
    reversed_at = db.Column(db.DateTime, nullable=True)
    reversed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Set when this debit ("Add Money") row was routed to a Sale invoice
    # payment instead of a plain account top-up — see
    # _sync_add_money_sale_transfer. Mirrors Expense.linked_sale_id/
    # is_payment_transfer, but points at the specific Payment row created
    # (rather than duplicating the Sale reference here too, since
    # Payment.invoice_id already reaches it).
    linked_payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True, index=True)

    account = db.relationship('ExpenseAccount', foreign_keys=[account_id],
                               backref=db.backref('transactions', lazy=True))
    counterparty_account = db.relationship('ExpenseAccount', foreign_keys=[counterparty_account_id])
    expense = db.relationship('Expense', backref=db.backref('account_transaction', uselist=False, lazy=True))
    linked_payment = db.relationship('Payment', foreign_keys=[linked_payment_id])
    customer = db.relationship('Customer', backref='account_debit_entries', lazy=True)
    warehouse = db.relationship('Warehouse', backref='account_debit_entries', lazy=True)
    source = db.relationship('ExpenseSource', backref='transactions', lazy=True)

    def __repr__(self):
        return f'<ExpenseAccountTransaction {self.entry_type} {self.amount} -> account {self.account_id}>'


class AccountDailyClose(db.Model):
    """One physical cash-count record per ExpenseAccount per day. Expected
    balance is the system's computed balance at close time; actual balance is
    what the custodian counted. Reconciliation is a verified flag on this same
    row (set by finance) rather than a separate table — a close only ever
    needs one verification pass."""
    __tablename__ = 'account_daily_closes'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('expense_accounts.id'), nullable=False, index=True)
    close_date = db.Column(db.Date, nullable=False, index=True)
    expected_balance = db.Column(db.Float, nullable=False, default=0)
    actual_balance = db.Column(db.Float, nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    closed_at = db.Column(db.DateTime, default=datetime.utcnow)

    is_reconciled = db.Column(db.Boolean, default=False)
    reconciled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reconciled_at = db.Column(db.DateTime, nullable=True)

    account = db.relationship('ExpenseAccount', backref=db.backref('daily_closes', lazy=True))

    @property
    def variance(self):
        return (self.actual_balance or 0) - (self.expected_balance or 0)

    def __repr__(self):
        return f'<AccountDailyClose account={self.account_id} {self.close_date}>'


class Expense(db.Model):
    """Expense tracking model"""
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(50), unique=True, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), index=True, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True, nullable=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), index=True, nullable=True)
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
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    # Held back by an admin — distinct from pending, which awaits review.
    # Without this the "Set as Draft" action has nowhere to record itself and
    # silently reads back as Pending.
    is_draft = db.Column(db.Boolean, default=False, index=True)
    # Set when this row was generated by a Fixed Expense template, so the list
    # can show its state (e.g. Stopped) and a stop can trim the open cycle.
    fixed_expense_id = db.Column(db.Integer, db.ForeignKey('fixed_expenses.id'), nullable=True, index=True)
    
    # Monthly distribution fields
    is_monthly_divided = db.Column(db.Boolean, default=False)  # Whether expense is divided across month
    monthly_start_date = db.Column(db.Date)  # Start date for monthly distribution
    monthly_end_date = db.Column(db.Date)  # End date for monthly distribution
    daily_amount = db.Column(db.Float, default=0)  # Calculated daily amount
    
    # Expense Shifting fields
    is_shifted = db.Column(db.Boolean, default=False)
    shifted_to_pd_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=True)
    pd_expense_id = db.Column(db.Integer, db.ForeignKey('product_development_expenses.id'), nullable=True)

    # Inventory cost shifting fields (shift an op expense onto inventory item cost)
    is_inventory_shifted = db.Column(db.Boolean, default=False)
    shifted_to_product_ids = db.Column(db.Text, nullable=True)  # comma-separated product ids the expense was applied to
    # Quantity added to each product's stock when this expense was shifted to
    # inventory cost (see shift_expense_to_inventory) — 'pid:qty,pid:qty,...'.
    # Kept separate from shifted_to_product_ids (whose 'pid:new_cost:old_cost'
    # format is parsed by _parse_shifted_product_costs) so reversing a shift
    # made before quantity support existed still works with no quantity to
    # subtract back off.
    shifted_product_quantities = db.Column(db.Text, nullable=True)

    # ── Sale/Purchase payment transfer ──────────────────────────────────────
    # When set, this expense's amount was applied as a real payment against a
    # Sale invoice (linked_sale_id) or PurchaseBill (linked_bill_id) instead of
    # being a genuine cost — see _sync_expense_payment_transfer in
    # app/routes/accounting.py. is_payment_transfer is the flag totals/reports
    # filter on to exclude it; the two link columns are mutually exclusive and
    # only used to render the "Transferred" badge / know which side to reverse.
    linked_sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True, index=True)
    linked_bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), nullable=True, index=True)
    is_payment_transfer = db.Column(db.Boolean, default=False, index=True)

    # Relationships
    vendor = db.relationship('Vendor', backref='expenses', lazy=True)
    customer = db.relationship('Customer', backref='expenses', lazy=True)
    warehouse = db.relationship('Warehouse', backref='expenses', lazy=True)
    product = db.relationship('Product', backref='overhead_expenses', lazy=True)
    bom = db.relationship('BOM', backref='overhead_expenses', lazy=True)
    manufacturing_order = db.relationship('ManufacturingOrder', backref='overhead_expenses', lazy=True)
    linked_sale = db.relationship('Sale', foreign_keys=[linked_sale_id])
    linked_bill = db.relationship('PurchaseBill', foreign_keys=[linked_bill_id])
    
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

    @property
    def shifted_products(self):
        """Products this expense was shifted onto via "Shift to Inventory
        Cost" (accounting.shift_expense_to_inventory), each paired with the
        value applied and how it was applied. Parses `shifted_to_product_ids`:
        current format 'pid:new_cost:old_cost,...' replaces the item's cost
        outright (mode 'set', value is new_cost); the older per-item
        'pid:amount,...' format and the original equal-split plain-id format
        ('pid,pid,...', split from `amount`) both added the value on top of
        whatever the item's cost already was (mode 'add'). Empty list when
        not shifted. Returns a list of (product, value, mode) tuples."""
        if not self.shifted_to_product_ids:
            return []
        tokens = [t.strip() for t in self.shifted_to_product_ids.split(',') if t.strip()]
        if not tokens:
            return []
        triples = []
        first_parts = tokens[0].split(':')
        if len(first_parts) >= 3:
            for t in tokens:
                parts = t.split(':')
                if len(parts) < 3:
                    continue
                try:
                    triples.append((int(parts[0]), float(parts[1]), 'set'))
                except (ValueError, IndexError):
                    continue
        elif len(first_parts) == 2:
            for t in tokens:
                try:
                    pid_str, amt_str = t.split(':', 1)
                    triples.append((int(pid_str), float(amt_str), 'add'))
                except (ValueError, IndexError):
                    continue
        else:
            ids = [int(t) for t in tokens if t.isdigit()]
            if ids:
                per = (self.amount or 0) / len(ids)
                triples = [(pid, per, 'add') for pid in ids]
        if not triples:
            return []
        products_by_id = {p.id: p for p in Product.query.filter(Product.id.in_([pid for pid, _, _ in triples])).all()}
        return [(products_by_id[pid], val, mode) for pid, val, mode in triples if pid in products_by_id]

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

    # Product Development number settings
    pd_prefix = db.Column(db.String(20), default='PDV')
    pd_suffix = db.Column(db.String(10), default='')
    next_pd_number = db.Column(db.Integer, default=1)
    pd_code_format = db.Column(db.String(50), default='{prefix}-{year}-{number}')

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

    # Quotation numbering (separate counter from invoices)
    quotation_prefix = db.Column(db.String(10), default='QO-')
    quotation_suffix = db.Column(db.String(10), default='')
    quotation_next_number = db.Column(db.Integer, default=1)

    # Tax settings
    tax_name = db.Column(db.String(50))
    tax_rate = db.Column(db.Numeric(10, 2), default=10)
    
    # Additional
    payment_terms = db.Column(db.Text)
    notes = db.Column(db.Text)
    overdue_restricted_groups = db.Column(db.Text) # Stored as JSON list of group IDs
    
    @property
    def restricted_group_ids(self):
        if not self.overdue_restricted_groups:
            return []
        import json
        try:
            return json.loads(self.overdue_restricted_groups)
        except:
            return []

    product_discount_conditions = db.Column(db.Text) # JSON list: [{product_id, min_discount, max_discount}]

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


class SaleReturnReason(db.Model):
    """Admin-managed list of selectable reasons for the Sales Return creation
    form's "Reason for Return" dropdown — added/removed via the "Manage
    Reasons" popup on that page (admin-only)."""
    __tablename__ = 'sale_return_reasons'

    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.String(200), nullable=False, unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SaleReturnReason {self.reason}>'


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
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(Enum('pending', 'approved', 'completed', name='return_status'), default='pending', index=True)
    returned_to_inventory = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    # Relationship moved to Sale model for cascade deletion
    # sale = db.relationship('Sale', backref='returns', lazy=True)
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
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
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
    reminder_at = db.Column(db.DateTime, nullable=True) # When to show the alarm
    is_notification_shown = db.Column(db.Boolean, default=False) # To avoid duplicate alarms
    is_email_sent = db.Column(db.Boolean, default=False) # To avoid duplicate emails
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # New fields: task group label and linked overdue invoice
    task_group_name = db.Column(db.String(100), nullable=True)  # Free-text group label
    linked_invoice_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)  # Linked overdue invoice
    linked_invoice = db.relationship('Sale', foreign_keys=[linked_invoice_id], backref='linked_tasks', lazy=True)

    # Recovery reminder support: ties this Task back to the RecoveryTask it was
    # scheduled from, and groups sibling Task rows created for one bulk
    # multi-user recovery reminder so completing one clears it for everyone
    # (recovery_task_id is the authoritative "this is a recovery reminder" flag —
    # deliberately separate from linked_invoice_id, which staff can also set on
    # ordinary tasks via the general Tasks screen and must not be swept in here).
    recovery_task_id = db.Column(db.Integer, db.ForeignKey('recovery_tasks.id'), nullable=True, index=True)
    recovery_task = db.relationship('RecoveryTask', foreign_keys=[recovery_task_id],
                                    backref=db.backref('reminder_tasks', cascade='all, delete-orphan'), lazy=True)
    reminder_batch_id = db.Column(db.String(36), nullable=True, index=True)
    is_escalation_broadcast_shown = db.Column(db.Boolean, default=False)
    is_completion_broadcast_shown = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Task {self.title}>'

class TaskSettings(db.Model):
    """Configuration for Task Notifications (SMTP)"""
    __tablename__ = 'task_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(120), default='smtp.gmail.com')
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(120))
    smtp_password = db.Column(db.String(120))
    sender_email = db.Column(db.String(120))
    notification_email = db.Column(db.String(120)) # Where to send alerts
    is_enabled = db.Column(db.Boolean, default=False)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TaskSettings {self.id}>'

class TaskGroup(db.Model):
    """Named group for organizing tasks (managed by admin, selected on tasks)"""
    __tablename__ = 'task_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TaskGroup {self.name}>'

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
    # Universal approval fields (using is_approved_flag to not conflict with is_active)
    is_approved_flag = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    # Optional per-component warehouse: which warehouse components are drawn from when producing
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    warehouse = db.relationship('Warehouse', foreign_keys=[warehouse_id])

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
    agreement_letter = db.Column(db.String(255))
    cnic = db.Column(db.String(255))
    cv = db.Column(db.String(255))
    left_date = db.Column(db.Date, nullable=True)  # set when marked as having left the company
    joining_advance = db.Column(db.Float, default=0)
    remaining_joining_advance = db.Column(db.Float, default=0)
    def __init__(self, name, designation=None, monthly_salary=0,
                 joining_date=None, joining_advance=0,
                 remaining_joining_advance=0, is_active=True,
                 agreement_letter=None, cnic=None, cv=None):
        self.name = name
        self.designation = designation
        self.monthly_salary = monthly_salary
        self.joining_date = joining_date
        self.joining_advance = joining_advance
        self.remaining_joining_advance = remaining_joining_advance
        self.is_active = is_active
        self.agreement_letter = agreement_letter
        self.cnic = cnic
        self.cv = cv
    
    # Monthly divided salary fields
    daily_salary = db.Column(db.Float, default=0)  # Calculated daily salary (monthly ÷ 30)
    
    # Relationships
    advances = db.relationship('SalaryAdvance', backref='staff', lazy=True, cascade='all, delete-orphan')
    salary_payments = db.relationship('SalaryPayment', backref='staff', lazy=True, cascade='all, delete-orphan')

    @property
    def total_outstanding_advance(self):
        """Calculate total non-deducted advances"""
        return self.get_outstanding_advance()

    def get_outstanding_advance(self, start_date=None, end_date=None):
        """Calculate total non-deducted advances within a date range"""
        advs = self.advances
        if start_date:
            advs = [a for a in advs if a.date >= start_date]
        if end_date:
            advs = [a for a in advs if a.date <= end_date]
        return sum(advance.amount for advance in advs if not advance.is_deducted)
    
    @property
    def total_attendance_earnings(self):
        """Calculate total earnings from all attendance records"""
        return self.get_attendance_earnings()

    def get_attendance_earnings(self, start_date=None, end_date=None):
        """Calculate total earnings from attendance records within a date range"""
        records = self.attendance_records
        if start_date:
            records = [r for r in records if r.date >= start_date]
        if end_date:
            records = [r for r in records if r.date <= end_date]
        return sum(r.earned_amount for r in records if r.earned_amount)

    @property
    def total_absents(self):
        """Calculate total absent days from attendance records"""
        return self.get_absents_count()

    def get_absents_count(self, start_date=None, end_date=None):
        """Calculate total absent days within a date range"""
        records = self.attendance_records
        if start_date:
            records = [r for r in records if r.date >= start_date]
        if end_date:
            records = [r for r in records if r.date <= end_date]
        return sum(1 for r in records if getattr(r, 'is_absent', False))

    def get_total_hours(self, start_date=None, end_date=None):
        """Calculate total hours worked within a date range"""
        records = self.attendance_records
        if start_date:
            records = [r for r in records if r.date >= start_date]
        if end_date:
            records = [r for r in records if r.date <= end_date]
        
        total_h = sum(r.hours_worked for r in records if r.hours_worked)
        total_m = sum(r.minutes_worked for r in records if r.minutes_worked)
        return total_h + (total_m / 60.0)

    def get_overtime_hours(self, start_date=None, end_date=None):
        """Computed overtime: how far actual worked hours in this period exceed
        the required hours for the period (working days, excluding Sundays and
        holidays, times 8h/day). Zero if actual hours are at or below required."""
        from app.utils import get_required_hours_in_range
        actual = self.get_total_hours(start_date, end_date)
        required = get_required_hours_in_range(self, start_date, end_date)
        return max(0.0, actual - required)

    def get_overtime_amount(self, start_date=None, end_date=None):
        """Overtime hours priced at this staff's current hourly rate
        (daily_salary / 8, recalculated for the relevant month)."""
        overtime_hours = self.get_overtime_hours(start_date, end_date)
        if overtime_hours <= 0:
            return 0.0
        self.calculate_daily_salary(end_date or datetime.utcnow().date())
        hourly_rate = (self.daily_salary or 0) / 8.0
        return overtime_hours * hourly_rate

    @property
    def current_month_hours(self):
        """Calculate total hours worked in the current calendar month"""
        from datetime import date
        today = date.today()
        start_of_month = date(today.year, today.month, 1)
        return self.get_total_hours(start_date=start_of_month)

    @property
    def total_paid_regular_advance(self):
        """Calculate total deducted regular advances"""
        return self.get_regular_adv_deducted()

    def get_regular_adv_deducted(self, start_date=None, end_date=None):
        """Calculate regular advances deducted within a date range"""
        payments = self.salary_payments
        if start_date:
            payments = [p for p in payments if p.payment_date and p.payment_date >= start_date]
        if end_date:
            payments = [p for p in payments if p.payment_date and p.payment_date <= end_date]
        return sum(p.advance_deduction for p in payments if p.advance_deduction)
    
    @property
    def joining_advance_paid(self):
        """Calculate joining advance already paid/deducted"""
        return self.get_joining_adv_paid()

    def get_joining_adv_paid(self, start_date=None, end_date=None):
        """Calculate joining advances deducted within a date range"""
        payments = self.salary_payments
        if start_date:
            payments = [p for p in payments if p.payment_date and p.payment_date >= start_date]
        if end_date:
            payments = [p for p in payments if p.payment_date and p.payment_date <= end_date]
        return sum(p.joining_advance_deduction for p in payments if p.joining_advance_deduction)

    @property
    def total_paid_advance(self):
        """Sum of all paid advances (Joining + Regular)"""
        return self.total_paid_regular_advance + self.joining_advance_paid
    
    @property
    def total_bonus_paid(self):
        """Total sum of all bonuses across all payments"""
        return self.get_bonus_paid()

    def get_bonus_paid(self, start_date=None, end_date=None):
        """Calculate bonuses paid within a date range"""
        payments = self.salary_payments
        if start_date:
            payments = [p for p in payments if p.payment_date and p.payment_date >= start_date]
        if end_date:
            payments = [p for p in payments if p.payment_date and p.payment_date <= end_date]
        return sum(p.bonus for p in payments if p.bonus)

    @property
    def total_other_deductions(self):
        """Total sum of all other deductions across all payments"""
        return self.get_other_deductions()

    def get_other_deductions(self, start_date=None, end_date=None):
        """Calculate other deductions within a date range"""
        payments = self.salary_payments
        if start_date:
            payments = [p for p in payments if p.payment_date and p.payment_date >= start_date]
        if end_date:
            payments = [p for p in payments if p.payment_date and p.payment_date <= end_date]
        return sum(p.other_deductions for p in payments if p.other_deductions)

    def get_net_paid(self, start_date=None, end_date=None):
        """Calculate net salary paid within a date range"""
        payments = self.salary_payments
        if start_date:
            payments = [p for p in payments if p.payment_date and p.payment_date >= start_date]
        if end_date:
            payments = [p for p in payments if p.payment_date and p.payment_date <= end_date]
        return sum(p.net_salary for p in payments if p.net_salary)
    
    @property
    def total_salary_remaining(self):
        """User formula: (advance_deduction - J.A advance paid - netpay - other deduction + Bonus)"""
        p_adv = sum(p.advance_deduction for p in self.salary_payments if p.advance_deduction)
        p_ja = self.joining_advance_paid
        p_net = sum(p.net_salary for p in self.salary_payments if p.net_salary)
        p_other = sum(p.other_deductions for p in self.salary_payments if p.other_deductions)
        p_bonus = sum(p.bonus for p in self.salary_payments if p.bonus)
        return p_ja - p_net - p_other + p_bonus

    def calculate_daily_salary(self, reference_date=None):
        """
        Calculate daily salary based on actual working days in the month.
        Excludes Sundays AND manually marked holidays.
        """
        from app.utils import get_working_days_in_month
        from sqlalchemy import extract
        
        if reference_date is None:
            reference_date = datetime.utcnow().date()
        
        # 1. Get standard working days (Total - Sundays)
        working_days = get_working_days_in_month(reference_date.year, reference_date.month)
        
        # 2. Subtract staff-specific holidays for this month
        holidays_count = Attendance.query.filter(
            Attendance.staff_id == self.id,
            Attendance.is_holiday == True,
            extract('year', Attendance.date) == reference_date.year,
            extract('month', Attendance.date) == reference_date.month
        ).count()
        
        actual_working_days = working_days - holidays_count
        if actual_working_days <= 0:
            actual_working_days = 1 # Safety fallback
            
        self.daily_salary = self.monthly_salary / float(actual_working_days)
    
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
    used_break = db.Column(db.Boolean, default=False)  # Whether to subtract 1 hour break
    deduct_hours = db.Column(db.Float, default=0)
    deduct_minutes = db.Column(db.Integer, default=0)
    deduct_reason = db.Column(db.Text)
    # Overtime worked on top of the regular shift. Kept SEPARATE from
    # hours_worked/earned_amount so existing salary, reports, accounting and
    # dashboard totals are unaffected; overtime pay is exposed on its own via
    # the overtime_earned property below.
    overtime_hours = db.Column(db.Float, default=0)
    overtime_minutes = db.Column(db.Integer, default=0)
    overtime_reason = db.Column(db.Text)
    is_holiday = db.Column(db.Boolean, default=False)
    is_absent = db.Column(db.Boolean, default=False)  # Auto-set if no clock-in by end of shift day
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    def __init__(self, staff_id, date, clock_in=None, clock_out=None, notes=None):
        self.staff_id = staff_id
        self.date = date
        self.clock_in = clock_in
        self.clock_out = clock_out
        self.notes = notes
    
    # Relationship
    staff = db.relationship('Staff', backref=db.backref('attendance_records', lazy=True, cascade='all, delete-orphan'))
    
    @property
    def lost_hours(self):
        """For absent records, returns the standard lost shift hours (8h)"""
        if getattr(self, 'is_absent', False):
            return 8.0
        return 0.0

    def calculate_hours_worked(self):
        """Calculate hours and minutes worked from clock in/out times, optionally subtracting 1 hour break and custom deductions"""
        if getattr(self, 'is_holiday', False) or getattr(self, 'is_absent', False):
            self.hours_worked = 0
            self.minutes_worked = 0
            return

        if self.clock_in and self.clock_out:
            time_diff = self.clock_out - self.clock_in
            total_seconds = time_diff.total_seconds()
            
            # Calculate total minutes from raw difference
            total_minutes = int(total_seconds / 60)
            
            # 1. Standard 1-hour break (60 minutes)
            # Only subtract if Shift is at least 4 hours (240 mins) to avoid zeroing out short shifts
            if self.used_break and total_minutes >= 240:
                total_minutes -= 60
            
            # 2. Custom deductions (hours + minutes)
            # Use getattr to safely handle cases where the object might not have the attributes yet
            d_hours = getattr(self, 'deduct_hours', 0) or 0
            d_mins = getattr(self, 'deduct_minutes', 0) or 0
            custom_deduction_total_mins = int(d_hours * 60) + int(d_mins)
            
            if total_minutes >= custom_deduction_total_mins:
                total_minutes -= custom_deduction_total_mins
            else:
                total_minutes = 0
            
            if total_minutes < 0:
                total_minutes = 0
            
            self.hours_worked = total_minutes // 60
            self.minutes_worked = total_minutes % 60
        else:
            self.hours_worked = 0
            self.minutes_worked = 0
    
    def calculate_hourly_rate(self):
        """
        Calculate hourly rate from staff monthly salary based on actual working days (Total - Sundays - Holidays).
        """
        if self.staff and self.staff.monthly_salary > 0:
            # First, ensure staff daily salary is up to date for this month
            self.staff.calculate_daily_salary(self.date)
            # Standard 8 hour working day
            self.hourly_rate = self.staff.daily_salary / 8.0
        else:
            self.hourly_rate = 0
    
    def calculate_earned_amount(self):
        """Calculate total earned amount for the day = regular pay + overtime pay.

        Overtime is paid at the same hourly rate and added on top of the
        regular earnings. When there is no overtime (the default) this behaves
        exactly as before, so existing records are unchanged."""
        # Always have an up-to-date hourly rate (also needed for overtime pay,
        # e.g. overtime worked on a holiday).
        self.calculate_hourly_rate()

        # Regular earnings — zero on holiday/absent.
        base = 0
        if not (getattr(self, 'is_holiday', False) or getattr(self, 'is_absent', False)):
            if self.hourly_rate > 0 and (self.hours_worked > 0 or self.minutes_worked > 0):
                total_hours_decimal = self.hours_worked + (self.minutes_worked / 60.0)
                base = total_hours_decimal * self.hourly_rate

        # Overtime earnings — extra hours beyond the regular shift.
        overtime_pay = self.overtime_total_hours * (self.hourly_rate or 0)

        self.earned_amount = base + overtime_pay
    
    def get_current_duration(self):
        """Return live duration for active shifts or saved duration for completed shifts"""
        if getattr(self, 'is_holiday', False):
            return "Holiday"
        if getattr(self, 'is_absent', False):
            return "Absent (Lost: 8h 0m)"
            
        if self.clock_in and not self.clock_out:
            diff = datetime.now() - self.clock_in
            total_mins = int(diff.total_seconds() / 60)
            
            # Subtraction logic (matching calculate_hours_worked)
            if self.used_break and total_mins >= 240:
                total_mins -= 60
            
            # Custom deductions
            d_hours = getattr(self, 'deduct_hours', 0) or 0
            d_mins = getattr(self, 'deduct_minutes', 0) or 0
            total_mins -= int(d_hours * 60 + d_mins)
            
            if total_mins < 0: total_mins = 0
            
            h = total_mins // 60
            m = total_mins % 60
            return f"{h}h {m}m"
        return self.get_time_summary()

    def get_current_earned(self):
        """Return live earnings for active shifts or saved earnings for completed shifts"""
        if self.clock_in and not self.clock_out:
            diff = datetime.now() - self.clock_in
            total_mins = int(diff.total_seconds() / 60)
            
            if self.used_break and total_mins >= 240:
                total_mins -= 60
            
            d_hours = getattr(self, 'deduct_hours', 0) or 0
            d_mins = getattr(self, 'deduct_minutes', 0) or 0
            total_mins -= int(d_hours * 60 + d_mins)
            
            if total_mins < 0: total_mins = 0
            
            # Ensure hourly rate is calculated
            if not self.hourly_rate:
                self.calculate_hourly_rate()
                
            return (total_mins / 60.0) * self.hourly_rate
        return self.earned_amount

    def get_time_summary(self):
        """Return formatted time summary (e.g., '8h 30m')"""
        if getattr(self, 'is_holiday', False):
            return "Holiday"
        if getattr(self, 'is_absent', False):
            return "Absent"
        if self.hours_worked > 0 or self.minutes_worked > 0:
            return f"{int(self.hours_worked)}h {int(self.minutes_worked)}m"
        return "0h 0m"

    @property
    def overtime_total_hours(self):
        """Overtime expressed as a single decimal-hours figure."""
        oh = getattr(self, 'overtime_hours', 0) or 0
        om = getattr(self, 'overtime_minutes', 0) or 0
        return oh + (om / 60.0)

    def get_overtime_summary(self):
        """Formatted overtime (e.g., '2h 30m'), or '—' when there is none."""
        oh = int(getattr(self, 'overtime_hours', 0) or 0)
        om = int(getattr(self, 'overtime_minutes', 0) or 0)
        if oh == 0 and om == 0:
            return "—"
        return f"{oh}h {om}m"

    @property
    def overtime_earned(self):
        """Overtime pay at the record's regular hourly rate. Computed on demand
        and NOT added to earned_amount, so other modules stay unchanged."""
        if self.overtime_total_hours <= 0:
            return 0.0
        rate = self.hourly_rate
        if not rate:
            self.calculate_hourly_rate()
            rate = self.hourly_rate or 0
        return self.overtime_total_hours * rate
    
    def __repr__(self):
        return f'<Attendance {self.staff_id} - {self.date}: {self.get_time_summary()}>'

class StaffReview(db.Model):
    """Performance review/note left on a staff member. Permanent log — no edit/delete."""
    __tablename__ = 'staff_reviews'

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    staff = db.relationship('Staff', backref=db.backref('reviews', lazy=True, cascade='all, delete-orphan', order_by='StaffReview.created_at.desc()'))
    author = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<StaffReview {self.staff_id} - {self.rating}*>'

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
    def __init__(self,staff_id,amount,date,description ):
     self.staff_id=staff_id
     self.amount=amount
     self.date=date
     self.description=description
        
    
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
    joining_advance_deduction = db.Column(db.Float, default=0)
    bonus = db.Column(db.Float, default=0)
    other_deductions = db.Column(db.Float, default=0)
    net_salary = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=datetime.utcnow().date())
    payment_method = db.Column(db.String(50), default='Cash')
    status = db.Column(Enum('paid', 'pending', name='salary_payment_status'), default='paid', index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __init__(self,staff_id,month,year,base_salary,advance_deduction,joining_advance_deduction,bonus,other_deductions,net_salary,payment_date,payment_method,status,notes):
        self.staff_id=staff_id
        self.month=month
        self.year=year
        self.base_salary=base_salary
        self.advance_deduction=advance_deduction
        self.joining_advance_deduction=joining_advance_deduction
        self.bonus=bonus
        self.other_deductions=other_deductions
        self.net_salary=net_salary
        self.payment_date=payment_date
        self.payment_method=payment_method
        self.status=status
        self.notes=notes
    
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
    # Warehouse where finished goods will be stored after completion
    finished_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    finished_warehouse = db.relationship('Warehouse', foreign_keys=[finished_warehouse_id])
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
    # Universal approval fields
    is_approved = db.Column(db.Boolean, default=False)
    is_rejected = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    # Optional per-item/component warehouse to consume from (copied from BOMItem at MO creation)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    warehouse = db.relationship('Warehouse', foreign_keys=[warehouse_id])
    
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
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

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
    # Approval workflow: staff-recorded advances require admin approval before being available for use
    is_approved = db.Column(db.Boolean, default=True, index=True)  # True for admin-created, False for staff-created
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    # Review flag mirroring Payment.needs_approval: a staff-recorded advance is
    # usable immediately (is_approved=True) but still raises an admin approval
    # request. See Payment.needs_approval for the full rationale.
    needs_approval = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

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
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    total = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='po_items', lazy=True)
    warehouse = db.relationship('Warehouse', backref='po_items', lazy=True)

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
    # Approval workflow: staff-recorded payments require admin approval before updating paid_amount
    is_approved = db.Column(db.Boolean, default=False, index=True)  # True for admin-created, False for staff-created
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    advance_id = db.Column(db.Integer, db.ForeignKey('vendor_advances.id'), nullable=True)
    # Set when this payment was created by checking "Add this to Purchase
    # Payment" on an Expense — mirrors Payment.expense_id on the sale side.
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True, index=True)

    creator = db.relationship('User', foreign_keys=[created_by], backref='bill_payments_created', lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], lazy=True)
    expense = db.relationship('Expense', foreign_keys=[expense_id], backref='bill_payments')

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
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)

    product = db.relationship('Product', backref='bill_receive_items', lazy=True)
    warehouse = db.relationship('Warehouse', backref='bill_receive_items', lazy=True)
    purchase_item = db.relationship('PurchaseItem', backref=db.backref('receive_items', lazy=True, cascade='all, delete-orphan'))
    price_history = db.relationship('CostPriceHistory', back_populates='bill_receive_item', lazy=True, cascade='all, delete-orphan', overlaps="cost_price_change,receive_item")

    def __repr__(self):
        return f'<BillReceiveItem receive={self.receive_id} product={self.product_id} qty={self.quantity_received}>'


class CostPriceHistory(db.Model):
    """Track cost price changes for products when new purchases are received"""
    __tablename__ = 'cost_price_history'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    purchase_bill_id = db.Column(db.Integer, db.ForeignKey('purchase_bills.id'), index=True)
    bill_receive_item_id = db.Column(db.Integer, db.ForeignKey('bill_receive_items.id'), nullable=True, index=True)
    old_price = db.Column(db.Float)  # Previous cost price (None if first entry)
    new_price = db.Column(db.Float, nullable=False)  # New cost price
    quantity_at_old_price = db.Column(db.Float, default=0)  # Quantity still available at old price
    used_quantity = db.Column(db.Float, default=0)  # Quantity already used/sold at old price
    change_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    reason = db.Column(db.String(200))  # e.g., "Purchase bill #12345"
    is_active = db.Column(db.Boolean, default=True)  # Active until old_price stock is consumed
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    product = db.relationship('Product', backref='cost_price_changes')
    purchase_bill = db.relationship('PurchaseBill', back_populates='cost_price_history', overlaps="cost_price_changes,bill")
    bill_receive_item = db.relationship('BillReceiveItem', back_populates='price_history', lazy=True, overlaps="cost_price_change,receive_item")
    
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
    cost = db.Column(db.Float, default=0)
    damage_percent = db.Column(db.Float, default=0)
    start_date = db.Column(db.Date, nullable=True)
    promise_date = db.Column(db.Date, nullable=True)
    budget = db.Column(db.Float, default=0)
    status = db.Column(db.Enum('Draft', 'Active', 'Completed', 'On Hold', name='pd_project_status'), default='Draft', index=True)
    current_phase = db.Column(db.Integer, default=1)  # 1-6 for phases
    description = db.Column(db.Text)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'), nullable=True, index=True)
    oem_part_number = db.Column(db.String(100), nullable=True, index=True)
    aftermarket_part_number = db.Column(db.String(100), nullable=True, index=True)
    vehicle_application = db.Column(db.String(200), nullable=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    project_owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    target_market = db.Column(db.String(100), nullable=True)
    expected_monthly_demand = db.Column(db.Float, default=0)
    target_selling_price = db.Column(db.Float, default=0)
    approved_budget = db.Column(db.Float, default=0)
    project_stage = db.Column(db.Enum(
        'New Request', 'Sample Required', 'Sample Received', 'Reverse Engineering', 'Drawing In Progress',
        'Tooling Required', 'Tooling In Progress', 'Tooling Trial', 'Prototype In Progress', 'Testing',
        'Costing Review', 'Approval Pending', 'Released for Production', 'On Hold', 'Rejected',
        'Revision Required', 'Discontinued', name='pd_project_stage'), default='New Request', index=True)
    next_action = db.Column(db.String(200), nullable=True)
    revision_number = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sku = db.relationship('Product', backref='pd_projects', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_pd_projects', lazy=True)
    product_category = db.relationship('ProductCategory', backref='pd_projects', lazy=True)
    requester = db.relationship('User', foreign_keys=[requested_by], backref='requested_pd_projects', lazy=True)
    project_owner = db.relationship('User', foreign_keys=[project_owner_id], backref='owned_pd_projects', lazy=True)
    bom_items = db.relationship('PDProjectBOM', backref='project', lazy=True, cascade='all, delete-orphan')
    components = db.relationship('PDComponent', backref='project', lazy=True, cascade='all, delete-orphan')
    tooling = db.relationship('PDTooling', backref='project', lazy=True, cascade='all, delete-orphan')
    testing = db.relationship('PDTesting', backref='project', lazy=True, cascade='all, delete-orphan')
    approval = db.relationship('PDApproval', backref='project', uselist=False, cascade='all, delete-orphan')
    assets = db.relationship('PDAsset', backref='project', lazy=True, cascade='all, delete-orphan')
    samples = db.relationship('ProductSample', backref='project', lazy=True, cascade='all, delete-orphan')
    reverse_engineering = db.relationship('ProductReverseEngineering', backref='project', lazy=True, cascade='all, delete-orphan')
    drawings = db.relationship('ProductDrawing', backref='project', lazy=True, cascade='all, delete-orphan')
    tooling_trials = db.relationship('ProductToolingTrial', backref='project', lazy=True, cascade='all, delete-orphan')
    prototype_batches = db.relationship('ProductPrototypeBatch', backref='project', lazy=True, cascade='all, delete-orphan')
    development_expenses = db.relationship('ProductDevelopmentExpense', backref='project', lazy=True, cascade='all, delete-orphan')
    bom_versions = db.relationship('ProductBOMVersion', backref='project', lazy=True, cascade='all, delete-orphan')
    release_records = db.relationship('ProductRelease', backref='project', lazy=True, cascade='all, delete-orphan')
    revision_history = db.relationship('ProductRevisionHistory', backref='project', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('ProductAttachment', backref='project', lazy=True, cascade='all, delete-orphan')
    
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
        return self.total_tooling_cost + self.total_component_cost + self.total_bom_cost + self.total_expense_cost

    @property
    def total_expense_cost(self):
        return sum(exp.amount or 0 for exp in self.development_expenses)

    @property
    def current_total_cost(self):
        return self.total_investment

    @property
    def budget_variance(self):
        target = self.approved_budget if self.approved_budget else self.budget
        return target - self.current_total_cost if target else 0

    @property
    def stage_name(self):
        return self.project_stage or 'New Request'
    
    @property
    def budget_vs_actual(self):
        return self.budget - self.total_investment if self.budget else 0

    @property
    def computed_cost(self):
        base_cost = self.sku.cost_price if self.sku and self.sku.cost_price else (self.cost or 0)
        damage_multiplier = 1 + (self.damage_percent or 0) / 100
        return base_cost * damage_multiplier

    @property
    def base_cost(self):
        return self.sku.cost_price if self.sku and self.sku.cost_price else (self.cost or 0)

    @property
    def is_delayed(self):
        if self.promise_date and self.status not in ['Completed']:
            return datetime.utcnow().date() > self.promise_date
        return False
    
    @property
    def phase_name(self):
        phases = {1: 'Initiation & BOM', 2: 'Tooling', 3: 'Testing', 
                  4: 'Production Expense', 5: 'Approval', 6: 'Production Ready'}
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


class ProductSample(db.Model):
    """Sample control records for product development"""
    __tablename__ = 'product_samples'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    sample_code = db.Column(db.String(100), nullable=True, index=True)
    received = db.Column(db.Boolean, default=False)
    received_date = db.Column(db.Date, nullable=True, index=True)
    source = db.Column(db.String(200), nullable=True)
    condition = db.Column(db.String(100), nullable=True)
    quantity = db.Column(db.Float, default=0)
    storage_location = db.Column(db.String(200), nullable=True)
    returned = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProductSample {self.project_id} - {self.sample_code or self.id}>'


class ProductReverseEngineering(db.Model):
    """Reverse engineering checklist and notes"""
    __tablename__ = 'product_reverse_engineering'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    teardown_completed = db.Column(db.Boolean, default=False)
    measured_by = db.Column(db.String(120), nullable=True)
    measurement_method = db.Column(db.String(120), nullable=True)
    critical_dimensions_recorded = db.Column(db.Boolean, default=False)
    tolerance_defined = db.Column(db.Boolean, default=False)
    material_identified = db.Column(db.Boolean, default=False)
    bearings_seals_identified = db.Column(db.Boolean, default=False)
    weight_recorded = db.Column(db.Boolean, default=False)
    fitment_verified = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProductReverseEngineering {self.project_id}>'


class ProductDrawing(db.Model):
    """Drawing and CAD records for PD"""
    __tablename__ = 'product_drawings'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    drawing_required_2d = db.Column(db.Boolean, default=False)
    drawing_required_3d = db.Column(db.Boolean, default=False)
    drawing_number = db.Column(db.String(100), nullable=True, index=True)
    drawing_revision = db.Column(db.String(50), nullable=True)
    drawing_status = db.Column(db.Enum('Draft', 'In Review', 'Approved', 'Released', 'Cancelled', name='pd_drawing_status'), default='Draft', index=True)
    prepared_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    file_path = db.Column(db.String(255), nullable=True)
    revision_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    preparer = db.relationship('User', foreign_keys=[prepared_by], lazy=True)
    checker = db.relationship('User', foreign_keys=[checked_by], lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], lazy=True)

    def __repr__(self):
        return f'<ProductDrawing {self.project_id} - {self.drawing_number}>'


class ProductToolingTrial(db.Model):
    """Individual tooling trials linked to PD tooling"""
    __tablename__ = 'product_tooling_trials'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    tooling_id = db.Column(db.Integer, db.ForeignKey('pd_tooling.id'), nullable=False, index=True)
    trial_number = db.Column(db.Integer, default=1)
    trial_date = db.Column(db.Date, nullable=True)
    result = db.Column(db.Enum('PENDING', 'PASS', 'FAIL', name='pd_tooling_trial_result'), default='PENDING', index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tooling = db.relationship('PDTooling', backref='trials', lazy=True)

    def __repr__(self):
        return f'<ProductToolingTrial {self.project_id} - T{self.trial_number}>'


class ProductPrototypeBatch(db.Model):
    """Prototype batch records for PD"""
    __tablename__ = 'product_prototypes'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    batch_code = db.Column(db.String(100), nullable=True, index=True)
    batch_date = db.Column(db.Date, nullable=True)
    material_used = db.Column(db.Text)
    prototype_cost = db.Column(db.Float, default=0)
    assembly_cost = db.Column(db.Float, default=0)
    testing_status = db.Column(db.Enum('Pending', 'In Progress', 'Passed', 'Failed', name='pd_prototype_status'), default='Pending', index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProductPrototypeBatch {self.project_id} - {self.batch_code or self.id}>'


class ProductDevelopmentExpense(db.Model):
    """Project development expense records"""
    __tablename__ = 'product_development_expenses'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=True, index=True)
    tooling_id = db.Column(db.Integer, db.ForeignKey('pd_tooling.id'), nullable=True, index=True)
    prototype_batch_id = db.Column(db.Integer, db.ForeignKey('product_prototypes.id'), nullable=True, index=True)
    item_code = db.Column(db.String(100), nullable=True, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('manufacturing_orders.id'), nullable=True, index=True)
    expense_category = db.Column(db.Enum(
        'Sample Purchase', 'Reverse Engineering', 'Measurement', 'CAD', 'Prototype', 'Testing',
        'Mold', 'Die', 'Fixture', 'Pattern', 'Jig', 'Gauge',
        'Raw Material', 'Purchased Components', 'Machining', 'Casting',
        'Electricity', 'Maintenance', 'Factory Wages',
        'Office Rent', 'Salaries', 'Marketing', 'Travel',
        'Scrap', 'Prototype Failure', 'Warranty', name='pd_expense_category'), nullable=False, index=True)
    amount = db.Column(db.Float, default=0)
    cost_center = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text)
    amortization_selected = db.Column(db.Boolean, default=False)
    expected_recovery_quantity = db.Column(db.Float, default=0)
    shared_cost = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tooling = db.relationship('PDTooling', backref='development_expenses', lazy=True)
    prototype_batch = db.relationship('ProductPrototypeBatch', backref='development_expenses', lazy=True)
    work_order = db.relationship('ManufacturingOrder', backref='development_expenses', lazy=True)

    def __repr__(self):
        return f'<ProductDevelopmentExpense {self.project_id} - {self.expense_category}>'


class ProductBOMVersion(db.Model):
    """BOM version history for development projects"""
    __tablename__ = 'product_bom_versions'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    version = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='created_product_bom_versions', lazy=True)

    def __repr__(self):
        return f'<ProductBOMVersion {self.project_id} - {self.version}>'


class ProductRelease(db.Model):
    """Production release and approval records"""
    __tablename__ = 'product_release'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    released_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    release_date = db.Column(db.DateTime, nullable=True)
    approval_status = db.Column(db.Enum('Pending', 'Approved', 'Rejected', name='pd_release_status'), default='Pending', index=True)
    release_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    releaser = db.relationship('User', backref='product_releases', lazy=True)

    def __repr__(self):
        return f'<ProductRelease {self.project_id} - {self.approval_status}>'


class ProductRevisionHistory(db.Model):
    """Revision history for product development projects"""
    __tablename__ = 'product_revision_history'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    revision_number = db.Column(db.Integer, default=1)
    change_summary = db.Column(db.Text)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    changer = db.relationship('User', backref='project_revisions', lazy=True)

    def __repr__(self):
        return f'<ProductRevisionHistory {self.project_id} - rev{self.revision_number}>'


class SharedCostAllocation(db.Model):
    """Allocation of shared development cost across multiple projects"""
    __tablename__ = 'shared_cost_allocations'

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('product_development_expenses.id'), nullable=False, index=True)
    allocated_project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    allocation_percent = db.Column(db.Float, default=0)
    allocated_amount = db.Column(db.Float, default=0)
    reason = db.Column(db.Text)

    expense = db.relationship('ProductDevelopmentExpense', backref='allocations', lazy=True)
    allocated_project = db.relationship('PDProject', backref='shared_allocations', lazy=True)

    def __repr__(self):
        return f'<SharedCostAllocation {self.expense_id} -> {self.allocated_project_id}>'


class ProductAttachment(db.Model):
    """Project file attachments for development records"""
    __tablename__ = 'product_attachments'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('pd_projects.id'), nullable=False, index=True)
    attachment_type = db.Column(db.String(100), nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    uploader = db.relationship('User', backref='pd_attachments', lazy=True)

    def __repr__(self):
        return f'<ProductAttachment {self.project_id} - {self.attachment_type}>'

class ToolReceiving(db.Model):
    __tablename__ = 'tool_receiving'
    id = db.Column(db.Integer, primary_key=True)
    receiving_number = db.Column(db.String(50), unique=True, index=True)
    tool_name = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    description = db.Column(db.Text)
    shipping_charges = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)
    bill_image_path = db.Column(db.String(255))
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Approval workflow
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    stock_updated = db.Column(db.Boolean, default=False)  # True once inventory has been adjusted

    # BOM Overhead Allocation fields
    is_bom_overhead = db.Column(db.Boolean, default=False)
    overhead_type = db.Column(db.String(20)) # 'mo', 'bulk'
    allocated_ids = db.Column(db.Text) # Stored as comma-separated or JSON list for pre-filling UI
    
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    
    items = db.relationship('ToolReceivingItem', backref='receiving', lazy=True, cascade='all, delete-orphan')
    expense = db.relationship('Expense', backref='tool_receiving', lazy=True)
    buyer = db.relationship('Staff', foreign_keys=[buyer_id], backref='tool_purchases', lazy=True)
    vendor_rel = db.relationship('Vendor', foreign_keys=[vendor_id], backref='tool_supplies', lazy=True)
    requester = db.relationship('Staff', foreign_keys=[requester_id], backref='tool_requests', lazy=True)
    customer = db.relationship('Customer', foreign_keys=[customer_id], lazy=True)
    sale = db.relationship('Sale', foreign_keys=[sale_id], lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], backref='tool_receiving_approvals', lazy=True)

class ToolReceivingItem(db.Model):
    __tablename__ = 'tool_receiving_items'
    id = db.Column(db.Integer, primary_key=True)
    receiving_id = db.Column(db.Integer, db.ForeignKey('tool_receiving.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    
    product = db.relationship('Product', backref='tool_receivings', lazy=True)
    warehouse = db.relationship('Warehouse', backref='tool_receiving_items', lazy=True)

class ToolDelivering(db.Model):
    __tablename__ = 'tool_delivering'
    id = db.Column(db.Integer, primary_key=True)
    delivering_number = db.Column(db.String(50), unique=True, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    description = db.Column(db.Text)
    shipping_charges = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    bill_image_path = db.Column(db.String(255))
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Approval workflow
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    stock_updated = db.Column(db.Boolean, default=False)  # True once inventory has been adjusted
    
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    
    items = db.relationship('ToolDeliveringItem', backref='delivering', lazy=True, cascade='all, delete-orphan')
    expense = db.relationship('Expense', backref='tool_deliveries', lazy=True)
    buyer = db.relationship('Staff', foreign_keys=[buyer_id], backref='tool_delivery_buys', lazy=True)
    vendor_rel = db.relationship('Vendor', foreign_keys=[vendor_id], backref='tool_delivery_vendors', lazy=True)
    requester = db.relationship('Staff', foreign_keys=[requester_id], backref='tool_delivery_requests', lazy=True)
    customer = db.relationship('Customer', foreign_keys=[customer_id], lazy=True)
    sale = db.relationship('Sale', foreign_keys=[sale_id], lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], backref='tool_delivering_approvals', lazy=True)

class ToolDeliveringItem(db.Model):
    __tablename__ = 'tool_delivering_items'
    id = db.Column(db.Integer, primary_key=True)
    delivering_id = db.Column(db.Integer, db.ForeignKey('tool_delivering.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    
    product = db.relationship('Product', backref='tool_deliverings', lazy=True)
    warehouse = db.relationship('Warehouse', backref='tool_delivering_items', lazy=True)

class ToolSettings(db.Model):
    __tablename__ = 'tool_settings'
    id = db.Column(db.Integer, primary_key=True)
    receiving_prefix = db.Column(db.String(10), default='TREC-')
    delivering_prefix = db.Column(db.String(10), default='TDEL-')
    next_receiving_number = db.Column(db.Integer, default=1)
    next_delivering_number = db.Column(db.Integer, default=1)

class Media(db.Model):
    """Media/Document model"""
    __tablename__ = 'media'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer) # in bytes
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    uploaded_by = db.relationship('User', backref='uploaded_media')

    def __repr__(self):
        return f'<Media {self.filename}>'


class RecoveryTask(db.Model):
    """One recovery task per overdue invoice, auto-created by the automation job."""
    __tablename__ = 'recovery_tasks'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.id'), nullable=True, index=True)

    # OVERDUE | PARTIAL_RECOVERY | PROMISED_PAYMENT | FOLLOW_UP_REQUIRED | CLOSED_PAID | CLOSED_WRITTEN_OFF
    recovery_status = db.Column(db.String(30), default='OVERDUE', index=True)

    promise_date = db.Column(db.Date, nullable=True)
    promised_amount = db.Column(db.Float, nullable=True)
    broken_promise_count = db.Column(db.Integer, default=0)
    # The most recent promise date the customer failed to honour (balance still
    # outstanding after the promised day passed). Set by the automation's
    # _check_promise; surfaced in the recovery detail box.
    last_broken_promise_date = db.Column(db.Date, nullable=True)
    next_follow_up_date = db.Column(db.Date, nullable=True)

    # low | medium | high | critical
    risk_level = db.Column(db.String(20), default='medium', index=True)
    priority = db.Column(db.Integer, default=1)

    is_escalated = db.Column(db.Boolean, default=False)
    escalated_at = db.Column(db.DateTime, nullable=True)

    # Per-invoice notification mute: pauses popup reminders (and the dashboard
    # countdown) for this task without affecting its recovery_status/tracking.
    is_muted = db.Column(db.Boolean, default=False)
    muted_at = db.Column(db.DateTime, nullable=True)
    muted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Per-invoice "On Hold": we are not actively working this invoice right now,
    # so — like mute — it raises no popup reminders and its countdown timer does
    # not run. Unlike mute it is surfaced as a visible status label and has its
    # own "On Hold" dashboard tab so held invoices can be found in one place.
    is_on_hold = db.Column(db.Boolean, default=False)
    on_hold_at = db.Column(db.DateTime, nullable=True)
    on_hold_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    closed_reason = db.Column(db.Text, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Deleting the invoice deletes its recovery task (invoice_id is NOT NULL, so
    # it must cascade-delete rather than null out the FK).
    invoice = db.relationship('Sale', backref=db.backref('recovery_task', uselist=False,
                              cascade='all, delete-orphan'))
    salesman = db.relationship('Salesman', backref='recovery_tasks', lazy=True)
    logs = db.relationship(
        'RecoveryLog', backref='task', lazy=True,
        cascade='all, delete-orphan',
        order_by='RecoveryLog.created_at.desc()'
    )

    @property
    def last_log(self):
        return self.logs[0] if self.logs else None

    @property
    def broken_promises(self):
        """Details of every broken promise for this task, newest first.

        Reconstructed from the conversation log (the automation records a
        'no_response' entry each time a promise date passes with the balance
        still due). Each item is a dict: {'date', 'amount', 'when', 'note'}."""
        import re
        items = []
        for log in self.logs:  # logs are ordered newest-first
            if log.response_type != 'no_response':
                continue
            note = log.note or ''
            if 'romise' not in note:  # matches "Promise broken" / "Broken promise"
                continue
            # Prefer the structured date on the log; else parse it from the note.
            bdate = log.promise_date
            if not bdate:
                m = re.search(r'(\d{2}-\d{2}-\d{4})', note) or re.search(r'(\d{4}-\d{2}-\d{2})', note)
                if m:
                    from datetime import datetime
                    fmt = '%d-%m-%Y' if '-' in m.group(1)[2:3] else '%Y-%m-%d'
                    try:
                        bdate = datetime.strptime(m.group(1), fmt).date()
                    except ValueError:
                        bdate = None
            items.append({
                'date': bdate,
                'amount': log.promised_amount,
                'when': log.created_at,
                'note': note,
            })
        return items

    @property
    def broken_promise_date(self):
        """Date of the most recent broken promise. Uses the stored field, then
        the reconstructed log history, then the still-recorded promise_date
        once it has passed."""
        from datetime import date
        if self.last_broken_promise_date:
            return self.last_broken_promise_date
        for bp in self.broken_promises:
            if bp['date']:
                return bp['date']
        if (self.broken_promise_count and self.promise_date
                and self.promise_date < date.today()):
            return self.promise_date
        return None

    @property
    def next_reminder_at(self):
        """Earliest scheduled reminder time among still-open reminder popups
        for this recovery task (used to show a live countdown)."""
        open_reminders = [
            t.reminder_at for t in self.reminder_tasks
            if t.reminder_at and t.status in ('Pending', 'In Progress')
        ]
        return min(open_reminders) if open_reminders else None

    @property
    def overdue_days(self):
        """Delegates to Sale.effective_days_overdue, which is installment-aware
        (falls back to the plain due_date calc when there's no schedule, so
        this is unchanged for ordinary invoices)."""
        return self.invoice.effective_days_overdue if self.invoice else 0

    @property
    def last_payment_date(self):
        if self.invoice and self.invoice.payments:
            approved = [p.date for p in self.invoice.payments if p.is_approved]
            return max(approved) if approved else None
        return None

    @property
    def days_since_last_payment(self):
        from datetime import date
        lpd = self.last_payment_date
        if lpd:
            d = lpd.date() if hasattr(lpd, 'date') else lpd
            return (date.today() - d).days
        return None

    def compute_risk_level(self):
        overdue = self.overdue_days
        if overdue > 30:
            return 'critical'
        if overdue >= 15:
            return 'high'
        if overdue >= 10:
            return 'medium'
        return 'low'

    def __repr__(self):
        return f'<RecoveryTask invoice={self.invoice_id} status={self.recovery_status}>'


class RecoveryLog(db.Model):
    """Conversation / follow-up log entry for a recovery task."""
    __tablename__ = 'recovery_logs'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('recovery_tasks.id'), nullable=False, index=True)

    # general | promised_payment | partial_payment | no_response | escalated
    response_type = db.Column(db.String(30), default='general')
    note = db.Column(db.Text, nullable=False)

    promised_amount = db.Column(db.Float, nullable=True)
    promise_date = db.Column(db.Date, nullable=True)
    next_follow_up_date = db.Column(db.Date, nullable=True)

    logged_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Set when this log entry came from a scheduled "Send Reminder" popup alarm;
    # matches the Task(s).reminder_batch_id created alongside it, so the
    # Conversation Log can show a live countdown / completed status for it.
    reminder_batch_id = db.Column(db.String(36), nullable=True, index=True)

    logged_by_user = db.relationship('User', backref='recovery_logs')

    @property
    def reminder_task(self):
        """One representative Task from this log's reminder batch (all siblings
        share the same status/reminder_at, so any one reflects the group)."""
        if not self.reminder_batch_id:
            return None
        return Task.query.filter_by(reminder_batch_id=self.reminder_batch_id).first()

    def __repr__(self):
        return f'<RecoveryLog task={self.task_id} type={self.response_type}>'


class RecoveryComment(db.Model):
    """Free-form comment/note on a recovery task. Kept separate from
    RecoveryLog (which drives status changes, reminders and countdowns) so
    staff have a plain running discussion thread that never affects automation."""
    __tablename__ = 'recovery_comments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('recovery_tasks.id'), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Set when an admin edits the comment (used to show an "(edited)" marker).
    edited_at = db.Column(db.DateTime, nullable=True)

    task = db.relationship(
        'RecoveryTask',
        backref=db.backref('comments', lazy=True, cascade='all, delete-orphan',
                           order_by='RecoveryComment.created_at.desc()')
    )
    created_by_user = db.relationship('User', backref='recovery_comments')

    def __repr__(self):
        return f'<RecoveryComment task={self.task_id}>'


# ─── Journal Entry module (standalone double-entry style bookkeeping) ──────────

class FixedExpense(db.Model):
    """A recurring, day-based expense template.

    Two ways to describe the same cycle:
      • divide   — a fixed total spread evenly across N days (per day = amount / days)
      • multiply — a per-day rate charged for N days   (cycle total = amount * days)

    It accrues its per-day amount once per elapsed day. When the day count is
    reached the counter simply rolls over and a new cycle starts from day 1, so
    an active template keeps running until it is switched off.

    Nothing is written to the books automatically: the accrued balance sits here
    until someone posts it, which is the only moment a real Expense row is
    created. Inactive templates do not accrue — time does not pass for them —
    so reactivating resumes from the current day rather than back-charging.
    """
    __tablename__ = 'fixed_expenses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)

    mode = db.Column(db.String(10), default='divide')   # 'divide' | 'multiply'
    amount = db.Column(db.Float, default=0)             # divide: cycle total; multiply: per-day rate
    days = db.Column(db.Integer, default=1)             # cycle length in days (fixed_days mode only)
    start_date = db.Column(db.Date, nullable=True)

    # Legacy: an early version of this feature charged cycles against a
    # Journal Account. Kept only so any pre-existing linked data (and its
    # ExpenseAccountTransaction-free history) keeps working read-only —
    # nothing writes to this column anymore. See expense_account_id below
    # for the account field the app actually uses now.
    account_id = db.Column(db.Integer, db.ForeignKey('journal_accounts.id'), nullable=True)
    # The Expense module's OWN account (ExpenseAccount, independent of the
    # Journal module) this template's cycles are charged against (always a
    # credit/money-out — a Fixed Expense is always a recurring cost). Applied
    # to every cycle's Expense row as it's posted, the same way a one-off Add
    # Expense links to an account; edits only affect cycles posted AFTER the
    # change, never past ones.
    expense_account_id = db.Column(db.Integer, db.ForeignKey('expense_accounts.id'), nullable=True)
    # Payment method and bill image are set once on the template and copied
    # onto every cycle's generated Expense row (e.g. the same rent receipt /
    # "Bank Transfer" for every month), same fields Add Expense uses.
    payment_method = db.Column(db.String(50), nullable=True)
    bill_image_path = db.Column(db.String(255), nullable=True)

    # cycle_type: 'fixed_days' (default, existing behavior — a rolling N-day
    # window from start_date) or 'calendar_month' (cycle 1 runs from
    # start_date to the end of that month; every cycle after that is a full
    # calendar month, so the "day count" naturally varies 28-31 and resets on
    # the 1st). cycle_base_n supports pause/resume under calendar_month mode:
    # when a resume re-anchors start_date to the resume date, cycle_base_n is
    # set to cycles_posted at that moment, so cycle_window(n) can keep
    # counting forward correctly (n - cycle_base_n = cycles since the anchor)
    # without disturbing the numbering of cycles already posted. Unused in
    # fixed_days mode.
    cycle_type = db.Column(db.String(20), default='fixed_days')
    cycle_base_n = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True, index=True)
    # When on, each cycle is written into the Expense book automatically as a
    # day-divided expense, so the reports and dashboard pro-rate it per day.
    auto_post = db.Column(db.Boolean, default=True)
    cycles_posted = db.Column(db.Integer, default=0)    # legacy counter, kept for old rows
    days_posted = db.Column(db.Integer, default=0)      # how many days already written to the book
    paused_on = db.Column(db.Date, nullable=True)       # date it was last switched off

    # Running state, advanced by sync_accrual()
    accrued_amount = db.Column(db.Float, default=0)     # accrued but not yet posted
    posted_amount = db.Column(db.Float, default=0)      # lifetime total already posted
    days_accrued = db.Column(db.Integer, default=0)     # lifetime days counted
    last_accrued_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    category = db.relationship('ExpenseCategory', foreign_keys=[category_id])
    vendor = db.relationship('Vendor', foreign_keys=[vendor_id])
    account = db.relationship('JournalAccount', foreign_keys=[account_id])  # legacy, read-only
    expense_account = db.relationship('ExpenseAccount', foreign_keys=[expense_account_id])
    expenses = db.relationship('Expense', backref='fixed_expense',
                               foreign_keys='Expense.fixed_expense_id', lazy=True)

    @property
    def _is_calendar_month(self):
        return (self.cycle_type or 'fixed_days') == 'calendar_month'

    @property
    def cycle_days(self):
        """Length in days of the CURRENT (today's) cycle. Constant in
        fixed_days mode; varies 28-31 in calendar_month mode."""
        if self._is_calendar_month and self.start_date:
            n = max(1, self.cycles_started() or 1)
            return self.cycle_length_for(n)
        return max(1, int(self.days or 1))

    @property
    def per_day_amount(self):
        """Amount accrued for one day of the CURRENT cycle."""
        if self._is_calendar_month and self.start_date:
            return self.per_day_amount_for(max(1, self.cycles_started() or 1))
        return self._rate_for_length(self.cycle_days)

    @property
    def cycle_total(self):
        """What the CURRENT cycle costs in total."""
        if self._is_calendar_month and self.start_date:
            return self.cycle_total_for(max(1, self.cycles_started() or 1))
        return self._total_for_length(self.cycle_days)

    def _rate_for_length(self, length_days):
        amt = float(self.amount or 0)
        if (self.mode or 'divide') == 'multiply':
            return amt
        return amt / max(1, length_days)

    def _total_for_length(self, length_days):
        amt = float(self.amount or 0)
        if (self.mode or 'divide') == 'multiply':
            return amt * max(1, length_days)
        return amt

    def cycle_length_for(self, n):
        """Length in days of cycle `n` specifically."""
        start, end = self.cycle_window(n)
        return max(1, (end - start).days + 1)

    def per_day_amount_for(self, n):
        """Per-day rate for cycle `n` specifically.

        calendar_month + divide mode: 'Total Amount' means per FULL calendar
        month, so the rate is amount / (days in THAT month) even when the
        cycle itself is a partial period (a first cycle that starts mid-month)
        — that's what lets cycle_total_for() prorate a partial cycle DOWN from
        the full monthly amount, rather than charging the whole month's
        amount for only part of it.

        fixed_days mode (and multiply mode, any cycle_type): unchanged —
        amount / that cycle's own length (multiply: just `amount`).
        """
        if self._is_calendar_month and (self.mode or 'divide') == 'divide':
            import calendar
            start, _end = self.cycle_window(n)
            full_month_days = calendar.monthrange(start.year, start.month)[1]
            return self._rate_for_length(full_month_days)
        return self._rate_for_length(self.cycle_length_for(n))

    def cycle_total_for(self, n):
        """What cycle `n` actually costs — its per-day rate times its own
        (possibly partial, in calendar_month mode) length."""
        return self.per_day_amount_for(n) * self.cycle_length_for(n)

    @property
    def day_in_cycle(self):
        """Which day of the current cycle we are on (1.., 0 before it starts).
        Driven by last_accrued_date so it stays correct across variable-length
        calendar-month cycles; days_accrued alone (a lifetime counter) can't
        be turned back into "day of cycle" once cycles stop being uniform."""
        if self._is_calendar_month:
            if not self.last_accrued_date or not self.start_date:
                return 0
            n = self.cycles_started(self.last_accrued_date)
            if n <= 0:
                return 0
            start, _end = self.cycle_window(n)
            return (self.last_accrued_date - start).days + 1
        done = int(self.days_accrued or 0)
        if done <= 0:
            return 0
        return ((done - 1) % self.cycle_days) + 1

    @property
    def cycles_completed(self):
        if self._is_calendar_month:
            if not self.last_accrued_date or not self.start_date:
                return 0
            n = self.cycles_started(self.last_accrued_date)
            if n <= 0:
                return 0
            _start, end = self.cycle_window(n)
            return n if self.last_accrued_date >= end else n - 1
        return int(self.days_accrued or 0) // self.cycle_days

    @property
    def cycle_progress_pct(self):
        if self.day_in_cycle <= 0:
            return 0
        return round(self.day_in_cycle * 100.0 / self.cycle_days)

    def _calendar_window(self, rel_n):
        """(start, end) of the rel_n-th (1-based) calendar-month cycle,
        relative to start_date: cycle 1 runs start_date -> end of that month
        (a partial month unless start_date happens to be the 1st); every
        cycle after that is a full calendar month."""
        import calendar
        from datetime import date as _date
        if rel_n <= 1:
            start = self.start_date
        else:
            total_month_index = (self.start_date.year * 12 + (self.start_date.month - 1)) + (rel_n - 1)
            y2, m2 = divmod(total_month_index, 12)
            start = _date(y2, m2 + 1, 1)
        last_day = calendar.monthrange(start.year, start.month)[1]
        end = _date(start.year, start.month, last_day)
        return start, end

    def cycle_window(self, n):
        """(start, end) dates of cycle `n` (1-based, absolute — counts from
        the template's whole lifetime, not reset by a pause/resume)."""
        if self._is_calendar_month:
            rel_n = n - int(self.cycle_base_n or 0)
            if rel_n < 1:
                rel_n = 1
            return self._calendar_window(rel_n)
        from datetime import timedelta as _timedelta
        cycle_days = max(1, int(self.days or 1))
        first = self.start_date + _timedelta(days=(n - 1) * cycle_days)
        return first, first + _timedelta(days=cycle_days - 1)

    def cycles_started(self, as_of=None):
        """How many cycles have begun on or before `as_of` (0 before the start)."""
        from datetime import date as _date
        as_of = as_of or _date.today()
        if not self.start_date or as_of < self.start_date:
            return 0
        if self._is_calendar_month:
            base = int(self.cycle_base_n or 0)
            rel = 1
            while True:
                nxt_start, _end = self._calendar_window(rel + 1)
                if nxt_start > as_of:
                    return base + rel
                rel += 1
                if rel > 1200:      # ~100 years — should never be reached in practice
                    return base + rel
        cycle_days = max(1, int(self.days or 1))
        return ((as_of - self.start_date).days // cycle_days) + 1

    def _cycle_number_for_date(self, d):
        """Which cycle number (absolute, 1-based) contains date `d`. Assumes
        d >= start_date (callers only ever ask for dates in that range)."""
        if not self._is_calendar_month:
            cycle_days = max(1, int(self.days or 1))
            return ((d - self.start_date).days // cycle_days) + 1
        base = int(self.cycle_base_n or 0)
        n = base + 1
        while True:
            start, end = self.cycle_window(n)
            if start <= d <= end:
                return n
            if d < start:
                return max(base + 1, n - 1)
            n += 1
            if n > base + 1200:
                return n

    def sync_accrual(self, as_of=None):
        """Advance the accrual to `as_of` (default today). Returns days added.

        Caller commits. Safe to call repeatedly — it only ever counts days that
        have not been counted yet, so it cannot double-charge.
        """
        from datetime import date as _date
        as_of = as_of or _date.today()
        if not self.is_active or not self.start_date or as_of < self.start_date:
            return 0

        from datetime import timedelta as _timedelta
        last = self.last_accrued_date
        if last is None:
            base = self.start_date - _timedelta(days=1)  # so the start day itself counts
        else:
            base = last
        new_days = (as_of - base).days
        if new_days <= 0:
            return 0

        if self._is_calendar_month:
            # Walk day by day so a gap spanning a month boundary charges each
            # day at THAT day's own month rate, not one blended rate — the
            # common case (synced roughly daily) only ever runs this loop once.
            added_amount = 0.0
            cursor = base + _timedelta(days=1)
            n = self._cycle_number_for_date(cursor)
            rate = self.per_day_amount_for(n)
            _cyc_start, cyc_end = self.cycle_window(n)
            for _ in range(new_days):
                if cursor > cyc_end:
                    n += 1
                    rate = self.per_day_amount_for(n)
                    _cyc_start, cyc_end = self.cycle_window(n)
                added_amount += rate
                cursor += _timedelta(days=1)
            self.accrued_amount = float(self.accrued_amount or 0) + added_amount
        else:
            self.accrued_amount = float(self.accrued_amount or 0) + (self.per_day_amount * new_days)

        self.days_accrued = int(self.days_accrued or 0) + new_days
        self.last_accrued_date = as_of
        return new_days

    def __repr__(self):
        return f'<FixedExpense {self.name} {self.mode} {self.amount}x{self.days}>'


class JournalAccount(db.Model):
    """A named account (e.g. Cash, Bank, Owner, an expense head) used by the
    Journal Entry module. Kept completely separate from the rest of the app's
    accounting so nothing else is affected."""
    __tablename__ = 'journal_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    account_type = db.Column(db.String(50), nullable=True)   # optional label: Cash / Bank / Expense / Income …
    opening_balance = db.Column(db.Float, default=0)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    @property
    def total_debit(self):
        return sum((l.amount or 0) for l in self.lines if l.entry_type == 'debit' and getattr(l.entry, 'is_approved', True))

    @property
    def total_credit(self):
        return sum((l.amount or 0) for l in self.lines if l.entry_type == 'credit' and getattr(l.entry, 'is_approved', True))

    @property
    def balance(self):
        """Running balance: opening + debits (money in) − credits (money out)."""
        return (self.opening_balance or 0) + self.total_debit - self.total_credit

    def __repr__(self):
        return f'<JournalAccount {self.name}>'


class JournalEntry(db.Model):
    """One journal entry (a single form submission) that groups one or more
    lines. Each line posts a debit or credit against an account."""
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True, default=datetime.utcnow)
    reference = db.Column(db.String(120), nullable=True)   # optional voucher / ref no
    description = db.Column(db.Text, nullable=True)         # overall narration
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # Set once the entry's expense (credit / money-out) has been pushed to the
    # Expense module, so it can't be sent twice.
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)

    # Approval workflow
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_rejected = db.Column(db.Boolean, default=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    # Held back by an admin — distinct from pending, which is awaiting review.
    # Drafts never count towards an account balance (that needs is_approved).
    is_draft = db.Column(db.Boolean, default=False, index=True)

    lines = db.relationship(
        'JournalLine', backref='entry', lazy=True,
        cascade='all, delete-orphan', order_by='JournalLine.id'
    )
    created_by_user = db.relationship('User', foreign_keys=[created_by], backref='journal_entries')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='journal_entry_approvals', lazy=True)

    @property
    def total_debit(self):
        return sum((l.amount or 0) for l in self.lines if l.entry_type == 'debit')

    @property
    def total_credit(self):
        return sum((l.amount or 0) for l in self.lines if l.entry_type == 'credit')

    @property
    def is_balanced(self):
        return abs(self.total_debit - self.total_credit) < 0.01

    def __repr__(self):
        return f'<JournalEntry {self.id} {self.date}>'


class JournalLine(db.Model):
    """A single debit or credit line within a journal entry."""
    __tablename__ = 'journal_lines'

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('journal_accounts.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)         # expense / line details
    entry_type = db.Column(db.String(10), nullable=False, default='debit')  # 'debit' | 'credit'
    amount = db.Column(db.Float, nullable=False, default=0)
    bill_image_path = db.Column(db.String(255), nullable=True)  # Path to per-line bill/receipt image

    account = db.relationship('JournalAccount', backref=db.backref('lines', lazy=True))
    category = db.relationship('ExpenseCategory', backref=db.backref('journal_lines', lazy=True))

    def __repr__(self):
        return f'<JournalLine {self.entry_type} {self.amount} acct={self.account_id}>'


class DatabaseBackup(db.Model):
    """A snapshot of the live database file, taken automatically every night
    at 10 PM Pakistan time or manually from the Backup module (Settings).
    Only the most recent 10 rows are kept — see
    app/routes/backup.py:_enforce_retention(). This table lives inside the
    same file it describes, so a restore (which replaces that whole file)
    can leave it out of date; app/routes/backup.py:_reconcile_backup_index()
    re-derives any missing rows from what's actually on disk."""
    __tablename__ = 'database_backups'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    size_bytes = db.Column(db.Integer, default=0)
    backup_type = db.Column(db.String(20), default='manual')  # 'manual', 'auto', 'safety', 'unknown'
    note = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_restored_at = db.Column(db.DateTime, nullable=True)

    created_by_user = db.relationship('User', foreign_keys=[created_by], lazy=True)

    def __repr__(self):
        return f'<DatabaseBackup {self.filename}>'


class PackingSlipSettings(db.Model):
    """Packing Slip number formatting settings (mirrors InvoiceSettings'
    prefix/suffix/next_number pattern)."""
    __tablename__ = 'packing_slip_settings'

    id = db.Column(db.Integer, primary_key=True)
    prefix = db.Column(db.String(10), default='PKG-')
    suffix = db.Column(db.String(10), default='')
    next_number = db.Column(db.Integer, default=1)
    number_padding = db.Column(db.Integer, default=5)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PackingSlipSettings {self.id}>'


class PackingSlip(db.Model):
    """A filled-in Packing Slip issued for a Sale — the digital record behind
    the bilingual PDF generated in app/pdf_utils.py:generate_packing_slip().
    Filled in by staff via the modal on the invoice detail page rather than
    left blank for hand-writing."""
    __tablename__ = 'packing_slips'

    id = db.Column(db.Integer, primary_key=True)
    slip_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)

    packing_date = db.Column(db.Date)
    po_number = db.Column(db.String(100))

    is_partial = db.Column(db.Boolean, default=False)
    partial_shipment_no = db.Column(db.Integer)
    partial_shipment_total = db.Column(db.Integer)

    package_count = db.Column(db.Integer)

    # Shipping details
    transport_company = db.Column(db.String(150))
    bilty_no = db.Column(db.String(100))
    tracking_no = db.Column(db.String(100))
    vehicle_no = db.Column(db.String(100))
    gate_pass_no = db.Column(db.String(100))
    dispatch_date = db.Column(db.Date)

    # Packing details
    total_ordered_qty = db.Column(db.Float)
    total_packed_qty = db.Column(db.Float)
    balance_qty = db.Column(db.Float)
    gross_weight = db.Column(db.Float)
    net_weight = db.Column(db.Float)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Same public-share pattern as Sale/PurchaseBill/Quotation — lets the
    # WhatsApp share button link straight to the PDF with no login required.
    access_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    token_expiry = db.Column(db.DateTime, nullable=True)

    sale = db.relationship('Sale', backref=db.backref('packing_slips', lazy=True))
    created_by_user = db.relationship('User', foreign_keys=[created_by], lazy=True)

    @property
    def valid_access_token(self):
        import uuid
        from datetime import datetime, timedelta
        from app import db
        if not self.access_token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self.access_token = str(uuid.uuid4())
            self.token_expiry = datetime.utcnow() + timedelta(days=30)
            db.session.commit()
        return self.access_token

    @property
    def display_number(self):
        """slip_number without the zero-padding, e.g. 'PKG-00021' -> 'PKG-21'
        — cosmetic only, the stored/generated number is unchanged."""
        import re
        return re.sub(r'0*(\d+)', r'\1', self.slip_number or '', count=1)

    def __repr__(self):
        return f'<PackingSlip {self.slip_number}>'
