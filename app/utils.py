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


from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def permission_required(module, action='view'):
    """
    Decorator to check if current user has permission for a specific module and action.
    Options for action: 'view', 'add', 'edit', 'delete'.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            # Admins have full access
            if getattr(current_user, 'role', '') == 'admin':
                return f(*args, **kwargs)
                
            # Check specific permission
            attr_name = f'can_{action}_{module}'
            has_permission = getattr(current_user, attr_name, False)
            
            if not has_permission:
                flash(f'You do not have {action} permission for the {module} module.', 'danger')
                return redirect(request.referrer or url_for('dashboard.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
