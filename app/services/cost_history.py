"""Automatic cost-change history.

Item cost is changed from many places (Edit Item, purchase bills, production,
manufacturing orders, warehouse transfers, tools, expenses, approvals, bulk
upload ...). Instead of every one of them having to remember to write a
CostPriceHistory row, a single `before_flush` hook does it: whenever

  * Product.cost_price (the item's normal cost), or
  * ProductWarehouseStock.cost_price (one warehouse's own cost)

is about to be saved with a *different effective value*, a CostPriceHistory
row is added in the same flush, with the old/new cost, the warehouse (NULL =
item cost), who did it and where it came from (derived from the request).

Rows the purchase module already writes itself (bill receive / shipping /
tax updates) are detected and not duplicated.
"""
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

COST_EPS = 0.005  # below half a paisa is "no change"

# endpoint (or blueprint) -> where the change came from
_ENDPOINT_SOURCES = {
    'inventory.add_product': 'Opening cost (new item)',
    'inventory.edit_product': 'Edited on item page',
    'inventory.bulk_upload': 'Bulk upload',
    'inventory.bulk_assign_warehouse': 'Warehouse assignment',
    'api.universal_approval': 'Approval',
}
_BLUEPRINT_SOURCES = {
    'inventory': 'Inventory',
    'purchase': 'Purchase bill',
    'manufacturing': 'Manufacturing order',
    'production': 'Production (BOM cost)',
    'warehouse_transfer': 'Warehouse transfer',
    'tools': 'Tools receiving / delivering',
    'accounting': 'Expense / accounting',
    'api': 'Approval',
    'returns': 'Returns',
    'sales': 'Sales',
}


def _source():
    try:
        from flask import has_request_context, request
        if not has_request_context() or not request.endpoint:
            return 'System update'
        ep = request.endpoint
        if ep in _ENDPOINT_SOURCES:
            return _ENDPOINT_SOURCES[ep]
        bp = ep.split('.', 1)[0]
        return _BLUEPRINT_SOURCES.get(bp, bp.replace('_', ' ').title())
    except Exception:
        return 'System update'


def _user_id():
    try:
        from flask import has_request_context
        from flask_login import current_user
        if has_request_context() and current_user and current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def _old_value(obj, attr):
    """(changed?, old value) for a column attribute in this flush."""
    hist = inspect(obj).attrs[attr].history
    if not hist.has_changes():
        return False, None
    return True, (hist.deleted[0] if hist.deleted else None)


def _num(v):
    return float(v) if v is not None else None


def _before_flush(session, flush_context, instances):
    from app.models import Product, ProductWarehouseStock, CostPriceHistory
    try:
        # Rows the app is writing explicitly in this transaction:
        # {product_id: new_price} - don't duplicate those.
        explicit = session.info.setdefault('explicit_cost_history', {})
        auto_rows = session.info.setdefault('_auto_cost_rows', set())
        for obj in session.new:
            if isinstance(obj, CostPriceHistory) and id(obj) not in auto_rows:
                pid = obj.product_id or (obj.product.id if obj.product is not None else None)
                if pid and obj.warehouse_id is None:
                    explicit[pid] = _num(obj.new_price)

        source = None
        user_id = None
        product_old_cost = {}  # product id -> normal cost before this flush

        def add_row(**kw):
            nonlocal source, user_id
            if source is None:
                source, user_id = _source(), _user_id()
            row = CostPriceHistory(reason=kw.pop('reason', None) or source, created_by=user_id,
                                   used_quantity=0, is_active=True, **kw)
            session.add(row)
            auto_rows.add(id(row))

        # ── Item (normal) cost ────────────────────────────────────────────
        for obj in list(session.new) + list(session.dirty):
            if not isinstance(obj, Product):
                continue
            new = _num(obj.cost_price) or 0.0
            if obj in session.new:
                if new > COST_EPS:
                    add_row(product=obj, old_price=None, new_price=new,
                            quantity_at_old_price=0, reason='Opening cost (new item)')
                continue
            changed, old = _old_value(obj, 'cost_price')
            if not changed:
                continue
            old = _num(old) or 0.0
            product_old_cost[obj.id] = old
            if abs(new - old) < COST_EPS:
                continue
            exp = explicit.get(obj.id)
            if exp is not None and abs(exp - new) < COST_EPS:
                continue  # the purchase module already recorded this one
            q_changed, q_old = _old_value(obj, 'quantity')
            qty = _num(q_old) if q_changed else _num(obj.quantity)
            add_row(product=obj, old_price=old if old > COST_EPS else None, new_price=new,
                    quantity_at_old_price=max(qty or 0, 0))

        # ── A warehouse's own cost ────────────────────────────────────────
        for obj in list(session.new) + list(session.dirty):
            if not isinstance(obj, ProductWarehouseStock):
                continue
            is_new = obj in session.new
            if is_new:
                if obj.cost_price is None:
                    continue
                old_own = None
            else:
                changed, old_own = _old_value(obj, 'cost_price')
                if not changed:
                    continue
            product = obj.product or (session.get(Product, obj.product_id) if obj.product_id else None)
            if product is None:
                continue
            item_new = _num(product.cost_price) or 0.0
            item_old = product_old_cost.get(product.id, item_new)
            # Effective cost = own cost, or the item's normal cost when none.
            eff_old = _num(old_own) if old_own is not None else item_old
            eff_new = _num(obj.cost_price) if obj.cost_price is not None else item_new
            if abs(eff_new - eff_old) < COST_EPS:
                continue  # e.g. freezing a warehouse at the cost it already had
            q_changed, q_old = (False, None) if is_new else _old_value(obj, 'quantity')
            qty = _num(q_old) if q_changed else _num(obj.quantity)
            add_row(product=product, warehouse_id=obj.warehouse_id,
                    old_price=eff_old if eff_old > COST_EPS else None, new_price=eff_new,
                    quantity_at_old_price=max(qty or 0, 0))
    except Exception as e:  # history must never block saving the real data
        print(f"[cost_history] could not record cost change: {e}")


def _reset(session, *args):
    session.info.pop('explicit_cost_history', None)
    session.info.pop('_auto_cost_rows', None)


_registered = False


def register():
    """Install the hook once (called from create_app)."""
    global _registered
    if _registered:
        return
    event.listen(Session, 'before_flush', _before_flush)
    event.listen(Session, 'after_commit', _reset)
    event.listen(Session, 'after_rollback', _reset)
    _registered = True
