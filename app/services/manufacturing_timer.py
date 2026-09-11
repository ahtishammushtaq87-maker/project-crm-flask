"""Manufacturing Order auto-stop timer.

Mirrors app.services.production_targets' finalize_overdue_targets() pattern:
once an order's From/To date+time window (ManufacturingOrder.deadline_datetime)
passes, flip timer_stopped so it moves from the Active tab to the Previous tab
on the Manufacturing Orders list. This is a label-only move - it never touches
status, stock, produced_qty, or any completion/reversal logic, so batch
complete, undo, and delete keep working identically on a stopped order.
"""
from datetime import datetime

from app import db
from app.models import ManufacturingOrder


def finalize_overdue_manufacturing_orders():
    """Flip timer_stopped for every not-yet-stopped order whose deadline has
    passed. Called by the background scheduler and, as a fallback, by the
    Manufacturing Orders list view itself on load."""
    now = datetime.now()

    candidates = ManufacturingOrder.query.filter(
        ManufacturingOrder.timer_stopped == False,
        ManufacturingOrder.end_date.isnot(None)
    ).all()

    stopped = 0
    for order in candidates:
        deadline = order.deadline_datetime
        if deadline and deadline <= now:
            order.timer_stopped = True
            order.timer_stopped_at = now
            stopped += 1

    if stopped:
        db.session.commit()

    return stopped
