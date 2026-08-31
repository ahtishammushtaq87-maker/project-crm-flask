"""Production Target Tracker: shared result computation + auto-finalization.

compute_target_result() holds the exact math the Target Tracker has always
used to compare a target against actual production (MO-derived target units,
produced/rejected/returned quantities, completion %, DONE/ON TRACK/BEHIND
status, revenue/cost/profit) — used both for the live Active-tab view and,
via finalize_overdue_targets(), to freeze a target's numbers the moment its
deadline passes so it can move to the Previous Targets tab without being
recomputed forever.
"""
from datetime import datetime

from app import db
from app.models import ProductionTarget, ProductionLog, BOM, ManufacturingOrder, SaleReturn, SaleReturnItem
from sqlalchemy import func


def compute_target_result(target, expected_progress=100):
    """Compute the full tracker result dict for one ProductionTarget.

    expected_progress: 0-100, how far through the target's time window we
    are (used only to classify ON TRACK vs BEHIND). Callers viewing a live
    dashboard pass the page's own elapsed-vs-total-days figure; finalization
    (the deadline has already passed) uses the default of 100.
    """
    product = target.product

    log_start = target.start_date or datetime.utcnow().date()
    log_end = target.end_date or datetime.utcnow().date()

    mo_target_units = db.session.query(func.sum(ManufacturingOrder.quantity_to_produce)).join(BOM).filter(
        BOM.product_id == target.sku_id,
        ManufacturingOrder.start_date >= log_start,
        ManufacturingOrder.start_date <= log_end
    ).scalar() or 0

    effective_target_units = (target.target_units or 0) + mo_target_units

    if target.produced_qty is not None:
        produced_qty = target.produced_qty
    else:
        produced_qty = db.session.query(func.sum(ProductionLog.qty_produced)).filter(
            ProductionLog.sku_id == target.sku_id,
            ProductionLog.date >= log_start,
            ProductionLog.date <= log_end
        ).scalar() or 0

    rejected_qty = db.session.query(func.sum(ProductionLog.rejected_qty)).filter(
        ProductionLog.sku_id == target.sku_id,
        ProductionLog.date >= log_start,
        ProductionLog.date <= log_end
    ).scalar() or 0

    net_produced = produced_qty - rejected_qty
    total_produced = produced_qty + rejected_qty

    returned_qty = db.session.query(func.sum(SaleReturnItem.quantity)).join(SaleReturn).filter(
        SaleReturnItem.product_id == target.sku_id,
        SaleReturn.date >= log_start,
        SaleReturn.date <= log_end
    ).scalar() or 0

    final_net_produced = net_produced - returned_qty

    selling_price = product.finished_good_price if product.finished_good_price else product.unit_price
    bom = BOM.query.filter_by(product_id=product.id, is_active=True).first()

    item_unit_cost = product.cost_price if product.cost_price > 0 else (bom.total_cost if bom else 0)

    if bom:
        reference_bom_cost = bom.total_cost - bom.overhead_cost - bom.labor_cost
        reference_overhead = bom.overhead_cost + bom.labor_cost
    else:
        reference_bom_cost = product.cost_price
        reference_overhead = 0

    if target.overhead_cost_per_unit > 0:
        reference_overhead = target.overhead_cost_per_unit

    remaining = effective_target_units - total_produced
    completion_pct = (final_net_produced / effective_target_units * 100) if effective_target_units > 0 else 0

    if completion_pct >= 100:
        status = 'DONE'
        status_class = 'primary'
    elif completion_pct >= expected_progress:
        status = 'ON TRACK'
        status_class = 'success'
    else:
        status = 'BEHIND'
        status_class = 'danger'

    target_revenue = effective_target_units * selling_price
    estimated_cost = effective_target_units * item_unit_cost
    estimated_profit = target_revenue - estimated_cost

    actual_revenue = final_net_produced * selling_price
    actual_cost = final_net_produced * item_unit_cost
    actual_profit = actual_revenue - actual_cost

    return {
        'target': target,
        'product': product,
        'produced_qty': produced_qty,
        'net_produced': final_net_produced,
        'returned_qty': returned_qty,
        'rejected_qty': rejected_qty,
        'total_produced': total_produced,
        'remaining': remaining,
        'completion_pct': round(completion_pct, 1),
        'expected_progress': round(expected_progress, 1),
        'status': status,
        'status_class': status_class,
        'production_cost': item_unit_cost,
        'overhead_cost': reference_overhead,
        'item_cost': item_unit_cost,
        'selling_price': selling_price,
        'target_revenue': target_revenue,
        'estimated_cost': estimated_cost,
        'estimated_profit': estimated_profit,
        'actual_revenue': actual_revenue,
        'actual_cost': actual_cost,
        'actual_profit': actual_profit,
        'effective_target_units': effective_target_units
    }


def finalize_overdue_targets():
    """Freeze the result for every active target whose deadline has passed,
    and flip it to 'completed' so it moves to the Previous Targets tab.
    Called by the background scheduler and, as a fallback, by the Target
    Tracker page itself on load."""
    now = datetime.now()
    active_targets = ProductionTarget.query.filter_by(status='active').all()

    finalized = 0
    for target in active_targets:
        deadline = target.deadline_datetime
        if not deadline or deadline > now:
            continue

        result = compute_target_result(target, expected_progress=100)

        target.status = 'completed'
        target.result_generated_at = now
        target.final_target_units = result['effective_target_units']
        target.final_produced_qty = result['produced_qty']
        target.final_net_produced = result['net_produced']
        target.final_completion_pct = result['completion_pct']
        target.final_result_status = result['status']
        target.final_actual_revenue = result['actual_revenue']
        target.final_actual_cost = result['actual_cost']
        target.final_actual_profit = result['actual_profit']
        finalized += 1

    if finalized:
        db.session.commit()

    return finalized
