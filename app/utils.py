"""Payment management utility functions"""

from app.models import Sale, PurchaseBill


def safe_update_paid_amount(model_instance, delta_amount):
    """
    Safely update paid_amount for Sale/PurchaseBill with bounds checking.
    
    Args:
        model_instance: Sale or PurchaseBill instance
        delta_amount: Amount to add/subtract (positive/negative)
    
    Returns:
        bool: True if update successful
    """
    if not isinstance(model_instance, (Sale, PurchaseBill)):
        raise ValueError("model_instance must be Sale or PurchaseBill")
    
    model_instance.paid_amount += delta_amount
    
    # Bounds checking
    if model_instance.paid_amount < 0:
        model_instance.paid_amount = 0
    if hasattr(model_instance, 'total') and model_instance.paid_amount > model_instance.total:
        model_instance.paid_amount = model_instance.total
    
    # Update status
    model_instance.update_status()
    
    return True


def cleanup_linked_transactions(payment_instance):
    """
    Cleanup accounting Transactions linked to this payment.
    
    Args:
        payment_instance: Payment or BillPayment instance
    """
    from app.models import Transaction
    from sqlalchemy import or_, and_
    
    ref_type = 'payment'  # Default
    ref_id_col = None
    
    if hasattr(payment_instance, 'invoice_id'):
        ref_type = 'sale'
        ref_id_col = payment_instance.invoice_id
    elif hasattr(payment_instance, 'bill_id'):
        ref_type = 'purchase'  
        ref_id_col = payment_instance.bill_id
    
    # Delete by reference
    Transaction.query.filter(
        or_(
            and_(Transaction.reference_type == 'payment', Transaction.reference_id == payment_instance.id),
            and_(Transaction.reference_type == ref_type, Transaction.reference_id == ref_id_col, 
                 Transaction.amount == payment_instance.amount)
        )
    ).delete()

