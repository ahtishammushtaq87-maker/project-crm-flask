"""Database models for the Sales Target module.

Both tables are new; nothing here alters an existing CRM table. Invoices,
salesmen and users are only referenced by foreign key, and every such key
uses ON DELETE SET NULL / CASCADE so deleting a salesman or user elsewhere in
the CRM is never blocked by a target (SQLite foreign keys are ON in this app).

* ``sales_targets``         one row per target (amount, period, scope, status).
* ``sales_target_members``  the salesmen of a *team* target. Stored per target
                            (not read live from Salesman Groups) so changing a
                            group later never rewrites a past target.
* ``sales_target_products`` optional finished items a target is limited to.
* ``sales_target_plans``     a yearly target split into months (or, for plans
                            made before monthly splits, quarters). Each month
                            is an ordinary sales_targets row, linked through
* ``sales_target_plan_parts`` (plan, row, period -> target), so every report
                            and calculation keeps working on plain targets.
"""
from datetime import datetime

from app import db


class SalesTarget(db.Model):
    __tablename__ = 'sales_targets'

    TYPE_INDIVIDUAL = 'individual'
    TYPE_TEAM = 'team'
    TYPE_COMPANY = 'company'
    TYPES = (TYPE_INDIVIDUAL, TYPE_TEAM, TYPE_COMPANY)
    TYPE_LABELS = {
        TYPE_INDIVIDUAL: 'Individual Salesman',
        TYPE_TEAM: 'Team',
        TYPE_COMPANY: 'Company-wide',
    }

    # draft      - being prepared; shown, but never counted in the KPI cards.
    # active     - live target; counted in the KPI cards.
    # completed  - closed after its period ended; still counted (it is a real
    #              target that ran), but its amount/period/scope are locked.
    # cancelled  - abandoned; never counted, amount/period/scope locked.
    STATUSES = ('draft', 'active', 'completed', 'cancelled')
    STATUS_LABELS = {'draft': 'Draft', 'active': 'Active', 'completed': 'Completed', 'cancelled': 'Cancelled'}
    COUNTED_STATUSES = ('active', 'completed')
    CLOSED_STATUSES = ('completed', 'cancelled')

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)
    # Float, matching every other money column in this CRM (Sale.total etc.);
    # calculations convert to Decimal (see calculations.to_money).
    target_amount = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')
    description = db.Column(db.Text)
    # Optional incentive shown alongside the target; informational only — it is
    # not posted to payroll or accounting.
    bonus_amount = db.Column(db.Float, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint('target_amount > 0', name='ck_sales_targets_amount_positive'),
        db.CheckConstraint('end_date >= start_date', name='ck_sales_targets_period'),
        db.CheckConstraint("target_type IN ('individual', 'team', 'company')", name='ck_sales_targets_type'),
        db.CheckConstraint("status IN ('draft', 'active', 'completed', 'cancelled')", name='ck_sales_targets_status'),
        db.CheckConstraint('bonus_amount IS NULL OR bonus_amount >= 0', name='ck_sales_targets_bonus'),
        db.Index('ix_sales_targets_period', 'start_date', 'end_date'),
        db.Index('ix_sales_targets_status', 'status'),
        db.Index('ix_sales_targets_type', 'target_type'),
        db.Index('ix_sales_targets_salesman', 'salesman_id'),
    )

    # No backref: the existing Salesman/User models stay untouched.
    salesman = db.relationship('Salesman', foreign_keys=[salesman_id], lazy='joined')
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])
    members = db.relationship('SalesTargetMember', backref='target', lazy='selectin',
                              cascade='all, delete-orphan', passive_deletes=True)
    products = db.relationship('SalesTargetProduct', backref='target', lazy='selectin',
                               cascade='all, delete-orphan', passive_deletes=True)
    # Set when this target is one quarter of a yearly plan.
    plan_part = db.relationship('SalesTargetPlanPart', back_populates='target', uselist=False,
                                cascade='all, delete-orphan', passive_deletes=True)

    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.target_type, self.target_type)

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def member_ids(self):
        return sorted(m.salesman_id for m in self.members if m.salesman_id is not None)

    @property
    def has_item_scope(self):
        """True when the target is limited to chosen finished items (rows
        whose product was later deleted still count, so the target never
        silently widens to all sales)."""
        return bool(self.products)

    @property
    def product_ids(self):
        return sorted(p.product_id for p in self.products if p.product_id is not None)

    @property
    def removed_product_count(self):
        return sum(1 for p in self.products if p.product_id is None)

    def __repr__(self):
        return f'<SalesTarget {self.id} {self.name}>'


class SalesTargetMember(db.Model):
    __tablename__ = 'sales_target_members'

    id = db.Column(db.Integer, primary_key=True)
    target_id = db.Column(db.Integer, db.ForeignKey('sales_targets.id', ondelete='CASCADE'), nullable=False)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.id', ondelete='CASCADE'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('target_id', 'salesman_id', name='uq_sales_target_member'),
        db.Index('ix_sales_target_members_target', 'target_id'),
        db.Index('ix_sales_target_members_salesman', 'salesman_id'),
    )

    salesman = db.relationship('Salesman', lazy='joined')


class SalesTargetProduct(db.Model):
    """Finished items a target is limited to. No rows = all sales count.
    product_id becomes NULL (not deleted) if the product is removed, so the
    target reports the missing item instead of turning into an all-sales one."""
    __tablename__ = 'sales_target_products'

    id = db.Column(db.Integer, primary_key=True)
    target_id = db.Column(db.Integer, db.ForeignKey('sales_targets.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('target_id', 'product_id', name='uq_sales_target_product'),
        db.Index('ix_sales_target_products_target', 'target_id'),
        db.Index('ix_sales_target_products_product', 'product_id'),
    )

    product = db.relationship('Product', lazy='joined')


class SalesTargetPlan(db.Model):
    """A yearly target divided into 12 monthly targets (period_months=1) or,
    for older plans, 4 quarter targets (period_months=3). The yearly amount
    is never stored: it is always the sum of its targets, so it can't drift."""
    __tablename__ = 'sales_target_plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    year = db.Column(db.Integer, nullable=False)          # year the plan starts in
    start_month = db.Column(db.Integer, nullable=False, default=1)  # 1 = Jan-Dec, 7 = Jul-Jun, ...
    split_by_item = db.Column(db.Boolean, nullable=False, default=False)
    period_months = db.Column(db.Integer, nullable=False, default=1)  # 1 = monthly, 3 = quarterly
    # How many months/quarters from start_month; NULL = the full year (12 or 4).
    period_count = db.Column(db.Integer, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint('start_month BETWEEN 1 AND 12', name='ck_sales_target_plans_month'),
        db.CheckConstraint('period_months IN (1, 3)', name='ck_sales_target_plans_period'),
        db.CheckConstraint('period_count IS NULL OR period_count BETWEEN 1 AND 12',
                           name='ck_sales_target_plans_count'),
    )

    @property
    def is_monthly(self):
        return self.period_months == 1

    parts = db.relationship('SalesTargetPlanPart', back_populates='plan', lazy='selectin',
                            cascade='all, delete-orphan', passive_deletes=True,
                            order_by='(SalesTargetPlanPart.row_no, SalesTargetPlanPart.period_no)')

    def __repr__(self):
        return f'<SalesTargetPlan {self.id} {self.name}>'


class SalesTargetPlanPart(db.Model):
    """One month (or quarter) of a plan: period_no 1-12 (1-4). row_no groups
    the periods of one item when the plan has a separate target per item
    (always 0 otherwise)."""
    __tablename__ = 'sales_target_plan_parts'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('sales_target_plans.id', ondelete='CASCADE'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('sales_targets.id', ondelete='CASCADE'), nullable=False)
    row_no = db.Column(db.Integer, nullable=False, default=0)
    period_no = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('target_id', name='uq_sales_target_plan_part_target'),
        db.UniqueConstraint('plan_id', 'row_no', 'period_no', name='uq_sales_target_plan_part_slot'),
        db.CheckConstraint('period_no BETWEEN 1 AND 12', name='ck_sales_target_plan_parts_period'),
        db.Index('ix_sales_target_plan_parts_plan', 'plan_id'),
    )

    plan = db.relationship('SalesTargetPlan', back_populates='parts')
    target = db.relationship('SalesTarget', back_populates='plan_part', lazy='joined')


ALL_MODELS = (SalesTarget, SalesTargetMember, SalesTargetProduct, SalesTargetPlan, SalesTargetPlanPart)
