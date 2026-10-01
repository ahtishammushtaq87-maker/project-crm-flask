"""Per-warehouse item cost.

Every item keeps its normal Product.cost_price. A warehouse can also carry
its own cost for the item in ProductWarehouseStock.cost_price. NULL there
means "no own cost - use Product.cost_price", which is what every warehouse
starts with, so data from before this feature behaves exactly as before.

A warehouse gets its own cost when:
  * stock is transferred into it at a different cost or with shipping
    (weighted average of what it held + the incoming landed cost),
  * a manufacturing order finishes goods into it (only that warehouse's
    cost changes - other warehouses holding the item keep theirs),
  * it is set by hand on the item's edit page.

Sales (invoice cost/profit, COGS reports) read the cost of the warehouse the
line was sold from; manufacturing reads each component's cost from the
warehouse it is consumed from.
"""
from sqlalchemy import and_, func
from sqlalchemy.orm import aliased

from app import db
from app.models import Product, ProductWarehouseStock, SaleItem

COST_EPS = 1e-6
QTY_EPS = 1e-9


# ── Reading ──────────────────────────────────────────────────────────────

def own_cost(product_id, warehouse_id):
    """The warehouse's own cost for the item, or None if it has none."""
    if not warehouse_id:
        return None
    row = ProductWarehouseStock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
    return row.cost_price if row else None


def get_cost(product, warehouse_id):
    """Cost per unit of `product` in `warehouse_id` (falls back to the item's
    normal cost when the warehouse has no cost of its own / no warehouse)."""
    if product is None:
        return 0.0
    c = own_cost(product.id, warehouse_id)
    return float(c) if c is not None else float(product.cost_price or 0)


def cost_map(product_ids=None):
    """{product_id: {warehouse_id: cost}} for every warehouse that has its
    own cost - one query, for pages that need many lookups."""
    q = ProductWarehouseStock.query.filter(ProductWarehouseStock.cost_price.isnot(None))
    if product_ids is not None:
        ids = list(product_ids)
        if not ids:
            return {}
        q = q.filter(ProductWarehouseStock.product_id.in_(ids))
    out = {}
    for r in q.all():
        out.setdefault(r.product_id, {})[r.warehouse_id] = float(r.cost_price)
    return out


def sale_item_cost(item, cmap=None):
    """Unit cost of a SaleItem / SaleReturnItem: the cost in the warehouse it
    was sold from (the item's default warehouse when none was picked - the
    same warehouse the stock is taken out of)."""
    product = item.product
    if product is None:
        return 0.0
    wh_id = getattr(item, 'warehouse_id', None) or product.warehouse_id
    if cmap is not None:
        c = cmap.get(product.id, {}).get(wh_id)
        return float(c) if c is not None else float(product.cost_price or 0)
    return get_cost(product, wh_id)


# SQL version of sale_item_cost, for SUM(...) COGS queries. Use with
# join_sale_item_cost(query) after the query has joined Product.
_SaleItemPWS = aliased(ProductWarehouseStock, name='sale_item_wh_cost')
SALE_ITEM_UNIT_COST = func.coalesce(_SaleItemPWS.cost_price, Product.cost_price)


def join_sale_item_cost(query):
    return query.outerjoin(_SaleItemPWS, and_(
        _SaleItemPWS.product_id == SaleItem.product_id,
        _SaleItemPWS.warehouse_id == func.coalesce(SaleItem.warehouse_id, Product.warehouse_id)))


# ── Writing ──────────────────────────────────────────────────────────────

def stock_row(product_id, warehouse_id):
    row = ProductWarehouseStock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
    if not row:
        row = ProductWarehouseStock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        db.session.add(row)
        db.session.flush()
    return row


def materialize_legacy(product):
    """An item that has never had a ProductWarehouseStock row keeps all its
    stock implicitly in Product.warehouse_id. Turn that into a real row
    before adding any row, or the implicit quantity would stop counting."""
    has_rows = ProductWarehouseStock.query.filter_by(product_id=product.id).first() is not None
    if not has_rows and product.warehouse_id and (product.quantity or 0) > 0:
        db.session.add(ProductWarehouseStock(product_id=product.id, warehouse_id=product.warehouse_id,
                                             quantity=product.quantity))
        db.session.flush()


def freeze_other_warehouses(product, except_warehouse_id):
    """Before the item's normal cost changes because of ONE warehouse, give
    every other warehouse that holds stock at the current normal cost that
    cost as its own - so their cost stays where it was."""
    materialize_legacy(product)
    current = float(product.cost_price or 0)
    rows = ProductWarehouseStock.query.filter(
        ProductWarehouseStock.product_id == product.id,
        ProductWarehouseStock.warehouse_id != except_warehouse_id,
        ProductWarehouseStock.cost_price.is_(None),
        ProductWarehouseStock.quantity > QTY_EPS).all()
    for r in rows:
        r.cost_price = current
    db.session.flush()


def set_cost(product, warehouse_id, new_cost):
    """Give one warehouse its own cost for the item."""
    materialize_legacy(product)
    row = stock_row(product.id, warehouse_id)
    row.cost_price = round(max(float(new_cost or 0), 0.0), 6)
    return row


def _store(product, row, new_cost):
    """Write new_cost on the row, but leave a warehouse that follows the
    item's normal cost alone when the result IS that normal cost - so a
    plain transfer with no shipping doesn't pin a cost on anything."""
    new_cost = round(max(new_cost, 0.0), 6)
    if row.cost_price is None and abs(new_cost - float(product.cost_price or 0)) < COST_EPS:
        return
    row.cost_price = new_cost


def receive(product, row, qty, unit_cost):
    """`qty` units are arriving into `row`'s warehouse at `unit_cost`:
    moving-average the warehouse's cost. Call BEFORE adding qty to the row."""
    have = max(float(row.quantity or 0), 0.0)
    cur = float(row.cost_price) if row.cost_price is not None else float(product.cost_price or 0)
    total = have + qty
    new_cost = unit_cost if total <= QTY_EPS or have <= QTY_EPS else (have * cur + qty * unit_cost) / total
    _store(product, row, new_cost)


def unreceive(product, row, qty, unit_cost):
    """Undo receive(): `qty` units that came in at `unit_cost` are leaving
    again. Call BEFORE taking qty off the row."""
    have = float(row.quantity or 0)
    cur = float(row.cost_price) if row.cost_price is not None else float(product.cost_price or 0)
    left = have - qty
    if left <= QTY_EPS:
        return  # nothing left to value - keep the cost as it is
    _store(product, row, (have * cur - qty * unit_cost) / left)
