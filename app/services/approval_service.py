"""
Universal Approval Service
==========================
Provides a consistent, safe interface for approval/rejection/draft/cancel operations
across all modules. Wraps existing per-module approval logic without modifying any
model definitions or existing route handlers.

Supported modules: sale, payment, advance, expense, sale_return,
                   purchase_return, purchase_order, purchase_bill
"""

from datetime import datetime
from flask import current_app
from flask_login import current_user


class ApprovalService:
    """Centralized approval handling — read-only analysis + action dispatch."""

    MODULE_CONFIG = {
        'sale': {
            'model': 'Sale',
            'label': 'Invoice',
            'label_field': 'invoice_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'draft_field': 'is_draft',
            'default_is_approved': True,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'payment': {
            'model': 'Payment',
            'label': 'Payment',
            'label_field': 'payment_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': True,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'bill_payment': {
            'model': 'BillPayment',
            'label': 'Bill Payment',
            'label_field': 'id',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'advance': {
            'model': 'CustomerAdvance',
            'label': 'Advance',
            'label_field': 'customer_id',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': True,
            'actions': ['approve', 'reject'],
        },
        'expense': {
            'model': 'Expense',
            'label': 'Expense',
            'label_field': 'expense_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'draft_field': 'is_draft',
            'default_is_approved': True,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'expense_debit': {
            'model': 'ExpenseAccountTransaction',
            'label': 'Debit Entry',
            'label_field': 'id',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'draft_field': 'is_draft',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'sale_return': {
            'model': 'SaleReturn',
            'label': 'Sale Return',
            'label_field': 'return_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'purchase_return': {
            'model': 'PurchaseReturn',
            'label': 'Purchase Return',
            'label_field': 'return_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'vendor_advance': {
            'model': 'VendorAdvance',
            'label': 'Vendor Advance',
            'label_field': 'id',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': True,
            'actions': ['approve', 'reject'],
        },
        'purchase_order': {
            'model': 'PurchaseOrder',
            'label': 'Purchase Order',
            'label_field': 'po_number',
            'use_boolean_flags': False,
            'status_field': 'status',
            'status_values': {
                'approved': 'Confirmed',
                'rejected': 'Draft',
                'pending': 'Draft',
                'cancel': 'Cancelled',
                'draft': 'Draft',
            },
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'purchase_bill': {
            'model': 'PurchaseBill',
            'label': 'Purchase Bill',
            'label_field': 'bill_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': True,
            # This widget is ONLY the create-approval control. A bill's payment
            # status of 'cancelled' (from the Cancel-Remaining feature) must NOT
            # hijack the approval badge, and approving/rejecting must not touch it.
            'decouple_status_cancelled': True,
            'actions': ['approve', 'reject', 'draft'],
        },
        # ── New modules added for universal approval expansion ──────────────────
        'product': {
            'model': 'Product',
            'label': 'Product',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'tool_receiving': {
            'model': 'ToolReceiving',
            'label': 'Receiving Voucher',
            'label_field': 'receiving_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'tool_delivering': {
            'model': 'ToolDelivering',
            'label': 'Delivery Voucher',
            'label_field': 'delivering_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'customer': {
            'model': 'Customer',
            'label': 'Customer',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'vendor': {
            'model': 'Vendor',
            'label': 'Vendor',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'salesman': {
            'model': 'Salesman',
            'label': 'Salesman',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'warehouse': {
            'model': 'Warehouse',
            'label': 'Warehouse',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'product_category': {
            'model': 'ProductCategory',
            'label': 'Product Category',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'bom': {
            'model': 'BOM',
            'label': 'Bill of Materials',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved_flag',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'manufacturing_order': {
            'model': 'ManufacturingOrder',
            'label': 'Manufacturing Order',
            'label_field': 'order_number',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'payment_method': {
            'model': 'PaymentMethod',
            'label': 'Payment Method',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'customer_group': {
            'model': 'CustomerGroup',
            'label': 'Customer Group',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'expense_category': {
            'model': 'ExpenseCategory',
            'label': 'Expense Category',
            'label_field': 'name',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
        'journal_entry': {
            'model': 'JournalEntry',
            'label': 'Journal Entry',
            'label_field': 'id',
            'use_boolean_flags': True,
            'approve_field': 'is_approved',
            'reject_field': 'is_rejected',
            'reason_field': 'rejection_reason',
            'approved_by_field': 'approved_by',
            'approved_at_field': 'approved_at',
            'draft_field': 'is_draft',
            'default_is_approved': False,
            'actions': ['approve', 'reject', 'cancel', 'draft'],
        },
    }

    @classmethod
    def get_supported_modules(cls):
        return list(cls.MODULE_CONFIG.keys())

    @classmethod
    def get_config(cls, module):
        return cls.MODULE_CONFIG.get(module)

    @classmethod
    def _resolve_model(cls, config):
        from app import models as app_models
        return getattr(app_models, config['model'])

    @classmethod
    def get_entity(cls, module, item_id):
        config = cls.MODULE_CONFIG.get(module)
        if not config:
            raise ValueError(f"Unsupported module: {module}")
        model = cls._resolve_model(config)
        entity = model.query.get(item_id)
        if entity is None:
            raise ValueError(f"Entity not found: {module} id={item_id}")
        return entity

    @classmethod
    def get_pending_count(cls, module):
        """Returns the number of pending items for a module"""
        config = cls.MODULE_CONFIG.get(module)
        if not config:
            return 0
        model = cls._resolve_model(config)
        
        # Check for both is_approved=False and is_rejected=False
        approve_field = config.get('approve_field', 'is_approved')
        reject_field = config.get('reject_field', 'is_rejected')

        # We assume pending means not approved AND not rejected.
        filters = {approve_field: False, reject_field: False}
        # Drafts are held, not pending — exclude them where a draft flag exists.
        draft_field = config.get('draft_field')
        if draft_field:
            filters[draft_field] = False
        count = model.query.filter_by(**filters).count()
        return count

    @classmethod
    def get_status(cls, entity, module):
        """Return universal status string: approved, rejected, pending, cancelled, draft."""
        config = cls.MODULE_CONFIG.get(module)
        if not config:
            return 'pending'

        if config.get('use_boolean_flags'):
            is_rejected = getattr(entity, config.get('reject_field', 'is_rejected'), False)
            is_approved = getattr(entity, config.get('approve_field', 'is_approved'),
                                   config.get('default_is_approved', True))
            status_val = getattr(entity, 'status', '').lower() if hasattr(entity, 'status') else ''

            if status_val == 'cancelled' and not config.get('decouple_status_cancelled'):
                return 'cancelled'
            if is_rejected:
                reason_field = config.get('reason_field')
                if reason_field and getattr(entity, reason_field, '') == 'Cancelled by Admin':
                    return 'cancelled'
                return 'rejected'
            # A staff-recorded payment/advance is applied to the invoice right
            # away (is_approved=True) but still awaits an admin decision, which
            # it signals through `needs_approval`. Surface that as 'pending' so
            # the badge and the admin's Approve/Reject actions still appear.
            if getattr(entity, 'needs_approval', False):
                return 'pending'
            if is_approved:
                return 'approved'
            # Explicit draft marker via a dedicated boolean flag (e.g. Sale.is_draft)
            draft_field = config.get('draft_field')
            if draft_field and getattr(entity, draft_field, False):
                return 'draft'
            # Or via a 'draft' status value (legacy)
            if status_val == 'draft':
                return 'draft'
            return 'pending'
        else:
            actual_status = getattr(entity, config['status_field'], '')
            sv = config.get('status_values', {})
            for universal, actual in sv.items():
                if actual == actual_status and universal != 'rejected':
                    return universal
            if actual_status:
                return actual_status.lower()
            return 'pending'

    @classmethod
    def get_badge_class(cls, status):
        mapping = {
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'pending': 'bg-warning text-dark',
            'draft': 'bg-info',
            'cancelled': 'bg-secondary',
            'confirmed': 'bg-success',
            'completed': 'bg-info',
            'converted': 'bg-primary',
            'paid': 'bg-success',
            'unpaid': 'bg-danger',
            'partial': 'bg-warning text-dark',
            'return': 'bg-warning text-dark',
        }
        return mapping.get(status, 'bg-secondary')

    @classmethod
    def get_badge_icon(cls, status):
        mapping = {
            'approved': 'fa-check-circle',
            'rejected': 'fa-times-circle',
            'pending': 'fa-clock',
            'draft': 'fa-file',
            'cancelled': 'fa-ban',
            'confirmed': 'fa-check-circle',
            'completed': 'fa-check-double',
            'converted': 'fa-exchange-alt',
        }
        return mapping.get(status, 'fa-question-circle')

    @classmethod
    def get_available_actions(cls, entity, module):
        """Return list of actions admin can perform on this entity right now."""
        # Standardize check: must be logged in and satisfy admin criteria
        if not current_user.is_authenticated:
            return []
            
        is_admin_user = (current_user.role == 'admin')
        
        if not is_admin_user:
            return []

        config = cls.MODULE_CONFIG.get(module)
        if not config:
            return []

        status = cls.get_status(entity, module)
        actions = []

        # Admins can always perform all supported actions to allow corrections
        if is_admin_user:
            for action in config.get('actions', []):
                if action == 'approve' and status != 'approved':
                    actions.append('approve')
                elif action == 'reject' and status != 'rejected':
                    actions.append('reject')
                elif action == 'cancel' and status != 'cancelled':
                    actions.append('cancel')
                elif action == 'draft' and status != 'draft' and status != 'pending':
                    actions.append('draft')
            if status != 'pending':
                actions.append('pending')
            return actions

        # Non-admins follow normal terminal state rules
        terminal = {'approved', 'rejected', 'cancelled', 'completed', 'paid', 'converted'}
        if status in terminal:
            return []

        for action in config.get('actions', []):
            if action == 'approve' and status not in ('approved',):
                actions.append('approve')
            elif action == 'reject' and status not in ('rejected',):
                actions.append('reject')
            elif action == 'cancel' and status not in ('cancelled',):
                actions.append('cancel')
            elif action == 'draft' and status not in ('draft',):
                actions.append('draft')

        return actions

    @classmethod
    def get_entity_label(cls, entity, module):
        config = cls.MODULE_CONFIG.get(module)
        if not config:
            return f'#{entity.id}'
        return getattr(entity, config['label_field'], f'#{entity.id}')

    # ── Action Executors ────────────────────────────────────────────────────────
    # These mirror existing route logic but operate on fresh entity context.
    # They DO NOT modify any existing route behavior.

    @classmethod
    def approve(cls, module, item_id):
        config = cls.MODULE_CONFIG.get(module)
        if not config or 'approve' not in config.get('actions', []):
            raise ValueError(f"Approve not supported for module: {module}")

        entity = cls.get_entity(module, item_id)

        # A staff payment/advance flagged `needs_approval` was ALREADY applied to
        # the invoice when it was recorded. Remember that before the flags are
        # flipped so the post-approve hook does not add the money a second time.
        entity._was_already_applied = bool(
            getattr(entity, 'needs_approval', False)
            and getattr(entity, config.get('approve_field', 'is_approved'), False)
        )

        if config.get('use_boolean_flags'):
            setattr(entity, config['approve_field'], True)
            setattr(entity, config.get('reject_field', 'is_rejected'), False)
            if hasattr(entity, 'needs_approval'):
                entity.needs_approval = False
            if config.get('draft_field'):
                setattr(entity, config['draft_field'], False)
            setattr(entity, config['approved_by_field'], current_user.id)
            setattr(entity, config['approved_at_field'], datetime.utcnow())

            # Reset cancelled status if applicable — but NOT for modules that keep
            # their payment-cancel state independent of create-approval.
            if (hasattr(entity, 'status') and getattr(entity, 'status') == 'cancelled'
                    and not config.get('decouple_status_cancelled')):
                setattr(entity, 'status', 'unpaid') # Default back to unpaid
        else:
            current_status = getattr(entity, config['status_field'], '')
            new_status = config['status_values'].get('approved', current_status)
            setattr(entity, config['status_field'], new_status)

        # Module-specific post-approve side effects
        hook = getattr(cls, f"_post_approve_{module}", None)
        if hook:
            hook(entity)

        from app import db
        db.session.commit()
        msg = f"{config['label']} {cls.get_entity_label(entity, module)} approved"
        cls._log_approval_action(module, config['label'], cls.get_entity_label(entity, module), 'Approved')
        return entity, msg

    @classmethod
    def reject(cls, module, item_id, reason=''):
        config = cls.MODULE_CONFIG.get(module)
        if not config or 'reject' not in config.get('actions', []):
            raise ValueError(f"Reject not supported for module: {module}")

        entity = cls.get_entity(module, item_id)

        # Same reasoning as approve(): a `needs_approval` record is already
        # applied, so rejecting it has to take the money back out. Capture that
        # before the flags are cleared — the hook below reads it.
        entity._was_already_applied = bool(
            getattr(entity, 'needs_approval', False)
            and getattr(entity, config.get('approve_field', 'is_approved'), False)
        )

        if config.get('use_boolean_flags'):
            setattr(entity, config.get('reject_field', 'is_rejected'), True)
            setattr(entity, config.get('approve_field', 'is_approved'), False)
            if hasattr(entity, 'needs_approval'):
                entity.needs_approval = False
            if config.get('draft_field'):
                setattr(entity, config['draft_field'], False)
            if config.get('reason_field'):
                setattr(entity, config['reason_field'], reason or '')

            # Reset cancelled status if applicable — but NOT for decoupled modules.
            if (hasattr(entity, 'status') and getattr(entity, 'status') == 'cancelled'
                    and not config.get('decouple_status_cancelled')):
                setattr(entity, 'status', 'unpaid')
        else:
            new_status = config['status_values'].get('rejected', 'pending')
            setattr(entity, config['status_field'], new_status)

        from app import db
        # Trigger post status change hook on reject
        status_hook = getattr(cls, f"_post_status_change_{module}", None)
        if status_hook:
            status_hook(entity, 'reject')

        db.session.commit()
        msg = f"{config['label']} {cls.get_entity_label(entity, module)} rejected"
        detail = f"Reason: {reason}" if reason else None
        cls._log_approval_action(module, config['label'], cls.get_entity_label(entity, module), 'Rejected', detail)
        return entity, msg

    @classmethod
    def set_status(cls, module, item_id, universal_status):
        """Set to a non-approve/reject status (e.g. draft, cancel)."""
        config = cls.MODULE_CONFIG.get(module)
        if not config:
            raise ValueError(f"Unsupported module: {module}")

        entity = cls.get_entity(module, item_id)

        draft_field = config.get('draft_field')
        if config.get('use_boolean_flags'):
            if universal_status in ('draft', 'pending'):
                setattr(entity, config.get('approve_field', 'is_approved'), False)
                setattr(entity, config.get('reject_field', 'is_rejected'), False)
                if config.get('reason_field'):
                    setattr(entity, config['reason_field'], None)
                if (hasattr(entity, 'status') and getattr(entity, 'status') == 'cancelled'
                        and not config.get('decouple_status_cancelled')):
                    setattr(entity, 'status', 'unpaid')
                # Persist the draft flag: True only for 'draft', cleared for 'pending'.
                if draft_field:
                    setattr(entity, draft_field, universal_status == 'draft')
            elif universal_status == 'cancel':
                if draft_field:
                    setattr(entity, draft_field, False)
                if hasattr(entity, 'status') and 'cancelled' in str(type(entity).status.type.enums if hasattr(type(entity).status, 'type') and hasattr(type(entity).status.type, 'enums') else []):
                    setattr(entity, 'status', 'cancelled')
                    setattr(entity, config.get('approve_field', 'is_approved'), False) # Must be unapproved if cancelled
                    setattr(entity, config.get('reject_field', 'is_rejected'), False)
                else:
                    # Fallback to rejection if cancelled status not in enum
                    setattr(entity, config.get('reject_field', 'is_rejected'), True)
                    setattr(entity, config.get('approve_field', 'is_approved'), False)
                    if config.get('reason_field'):
                        setattr(entity, config['reason_field'], 'Cancelled by Admin')
        else:
            sv = config.get('status_values', {})
            actual_status = sv.get(universal_status)
            if not actual_status:
                raise ValueError(f"Status '{universal_status}' not valid for module {module}")
            setattr(entity, config['status_field'], actual_status)

        from app import db
        # Universal post-status hooks (dynamically resolved)
        status_hook = getattr(cls, f"_post_status_change_{module}", None)
        if status_hook:
            status_hook(entity, universal_status)

        db.session.commit()
        msg = f"{config['label']} {cls.get_entity_label(entity, module)} set to {universal_status}"
        action_labels = {'cancel': 'Cancelled', 'draft': 'Set to Draft', 'pending': 'Set to Pending'}
        action_label = action_labels.get(universal_status, f'Set to {universal_status.capitalize()}')
        cls._log_approval_action(module, config['label'], cls.get_entity_label(entity, module), action_label)
        return entity, msg

    @classmethod
    def _log_approval_action(cls, module, label, record_label, action_verb, extra_detail=None):
        """
        Write a structured entry to the ActivityLog for any approval/rejection/status action.
        Safe — never raises; silently skips if outside request context.
        """
        try:
            from app.utils import log_activity
            module_display = {
                'sale': 'Sales', 'payment': 'Sales', 'advance': 'Sales',
                'sale_return': 'Returns', 'purchase_return': 'Returns',
                'purchase_order': 'Purchase', 'purchase_bill': 'Purchase',
                'bill_payment': 'Purchase', 'vendor_advance': 'Purchase',
                'expense': 'Expenses', 'expense_debit': 'Expenses', 'tool_receiving': 'Tools',
                'tool_delivering': 'Tools', 'manufacturing_order': 'Manufacturing',
                'bom': 'Manufacturing', 'product': 'Inventory',
                'customer': 'Customers', 'vendor': 'Vendors',
                'salesman': 'Staff', 'warehouse': 'Inventory',
                'product_category': 'Inventory', 'payment_method': 'Settings',
                'customer_group': 'Customers', 'expense_category': 'Expenses',
                'journal_entry': 'Journal',
            }.get(module, 'Approval')

            action_str = f"{action_verb} {label} #{record_label}"
            details_parts = [f"Module: {label}", f"Record: {record_label}", f"Action: {action_verb}"]
            if extra_detail:
                details_parts.append(extra_detail)
            details_str = " | ".join(details_parts)

            log_activity(
                module=f"Approval – {module_display}",
                action=action_str,
                details=details_str
            )
        except Exception:
            pass  # Never break core approval logic because of logging

    @classmethod
    def _post_status_change_sale(cls, sale, new_status):
        """Handle side effects when a sale status is changed (e.g., reverting stock, syncing recovery)."""
        from app import db
        from app.models import Product, ProductWarehouseStock

        # If moving AWAY from approved (to draft, reject, or cancel) and stock was deducted, RESTORE it
        if new_status in ('draft', 'cancel', 'reject') and sale.stock_updated:
            for item in sale.items:
                product = Product.query.get(item.product_id)
                if product:
                    # restore quantity
                    product.update_quantity(item.quantity)

                    # restore warehouse stock
                    wh_id = item.warehouse_id
                    if wh_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=wh_id).first()
                        if wh_stock:
                            wh_stock.quantity += item.quantity
                    elif product.warehouse_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=product.warehouse_id).first()
                        if wh_stock:
                            wh_stock.quantity += item.quantity
            
            sale.stock_updated = False

        # Ensure linked RecoveryTask and alarm reminders are cancelled or updated immediately
        sale._sync_recovery_task()
        db.session.commit()

    # Expense.status is a separate legacy string field ('pending' / 'confirmed'
    # / 'rejected') that pre-dates is_approved/is_rejected — Sales/Profit
    # reports, the Dashboard, Manufacturing overhead costing, and several
    # other modules all gate on `Expense.status == 'confirmed'` rather than
    # is_approved, since that's what the original Add/Confirm Expense flow
    # set. The universal approval widget only ever flipped is_approved/
    # is_rejected, never this string, so a staff-created expense approved
    # through it would show "Approved" in the Expenses list yet stay
    # permanently invisible to every one of those reports. Map every
    # universal status onto the equivalent legacy string so they stay in
    # sync no matter which action path changed the expense.
    _STATUS_STRING_MAP = {'reject': 'rejected', 'cancel': 'rejected', 'draft': 'pending', 'pending': 'pending'}

    @classmethod
    def _post_status_change_expense(cls, expense, universal_status):
        """Keep Expense.status and the linked ExpenseAccountTransaction
        (Account Activity) in sync for every non-approve transition —
        reject, cancel, draft, and pending. See _sync_linked_expense_txn /
        _post_approve_expense, which covers the approve case."""
        expense.status = cls._STATUS_STRING_MAP.get(universal_status, expense.status)
        cls._sync_linked_expense_txn(expense)

    # ── Post-approve hooks ──────────────────────────────────────────────────────

    @classmethod
    def _post_approve_sale(cls, sale):
        """Mirrors sales.py approve_invoice logic exactly."""
        from app import db
        from app.models import CustomerAdvance, Payment

        if sale.advance_applied > 0 and not sale.adjusted_advances:
            customer_id = sale.customer_id
            if customer_id:
                from app.models import Customer
                customer = Customer.query.get(customer_id)
                remaining_to_apply = sale.advance_applied
                advances = CustomerAdvance.query.filter_by(
                    customer_id=customer_id, is_adjusted=False, is_approved=True
                ).order_by(CustomerAdvance.date).all()

                for adv in advances:
                    if remaining_to_apply <= 0:
                        break
                    available = adv.remaining_balance
                    if available > 0:
                        apply_amt = min(available, remaining_to_apply)
                        adv.applied_amount += apply_amt
                        remaining_to_apply -= apply_amt
                        if adv.remaining_balance <= 0:
                            adv.is_adjusted = True
                        adv.adjusted_invoice_id = sale.id

                sale.paid_amount += (sale.advance_applied - remaining_to_apply)

        pending_payments = Payment.query.filter_by(invoice_id=sale.id, is_approved=False).all()
        for pmt in pending_payments:
            sale.paid_amount += pmt.amount
            pmt.is_approved = True
            pmt.approved_by = current_user.id
            pmt.approved_at = datetime.utcnow()

        sale.calculate_totals()
        sale.update_status()

        # Deduct inventory ONLY if not already updated (to avoid double deduction)
        if not sale.stock_updated:
            from app.models import Product, ProductWarehouseStock
            for item in sale.items:
                product = Product.query.get(item.product_id)
                if product:
                    # reduce total product quantity
                    product.update_quantity(-item.quantity)

                    # Update per-warehouse stock
                    wh_id = item.warehouse_id
                    if wh_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=wh_id).first()
                        if not wh_stock:
                            wh_stock = ProductWarehouseStock(product_id=item.product_id, warehouse_id=wh_id, quantity=0)
                            db.session.add(wh_stock)
                        wh_stock.quantity -= item.quantity
                    elif product.warehouse_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(product_id=item.product_id, warehouse_id=product.warehouse_id).first()
                        if not wh_stock:
                            wh_stock = ProductWarehouseStock(product_id=item.product_id, warehouse_id=product.warehouse_id, quantity=0)
                            db.session.add(wh_stock)
                        wh_stock.quantity -= item.quantity
            sale.stock_updated = True
        
        db.session.commit()

    @classmethod
    def _sync_linked_expense_txn(cls, expense):
        """Mirror this expense's current approval flags onto its linked
        ExpenseAccountTransaction — the row Account Activity reads its status
        and money-in/out totals from (see accounting._sync_expense_account_
        transaction, which creates it). Without this, an expense approved/
        rejected/cancelled/drafted via the universal approval widget would
        update the Expenses list but leave Account Activity showing the old
        ("Pending") status for the very same entry."""
        from app.models import ExpenseAccountTransaction
        linked_txn = ExpenseAccountTransaction.query.filter_by(expense_id=expense.id).first()
        if not linked_txn:
            return
        is_approved = bool(expense.is_approved)
        linked_txn.is_approved = is_approved
        linked_txn.is_rejected = bool(expense.is_rejected)
        linked_txn.rejection_reason = expense.rejection_reason
        if hasattr(expense, 'is_draft') and hasattr(linked_txn, 'is_draft'):
            linked_txn.is_draft = bool(expense.is_draft)
        linked_txn.approved_by = expense.approved_by if is_approved else None
        linked_txn.approved_at = expense.approved_at if is_approved else None

    @classmethod
    def _post_approve_expense(cls, expense):
        """Mirrors accounting.py confirm_expense logic."""
        from app import db
        from app.models import ManufacturingOrder, BOM
        from app.services.bom_versioning import BOMVersioningService

        # See _STATUS_STRING_MAP above — this is the field Sales/Profit
        # reports, the Dashboard, and Manufacturing overhead actually filter
        # on, so it must flip to 'confirmed' here too, not just is_approved.
        expense.status = 'confirmed'
        cls._sync_linked_expense_txn(expense)

        if expense.is_bom_overhead and expense.mo_id:
            mo = ManufacturingOrder.query.get(expense.mo_id)
            if mo:
                mo.actual_overhead_cost = (mo.actual_overhead_cost or 0) + expense.amount
                mo.total_cost = (mo.actual_material_cost or 0) + (mo.actual_labor_cost or 0) + mo.actual_overhead_cost

        if expense.is_bom_overhead:
            bom_to_update = None
            if expense.bom_id:
                bom_to_update = BOM.query.get(expense.bom_id)
            elif expense.product_id:
                bom_to_update = BOM.query.filter_by(product_id=expense.product_id, is_active=True).first()

            if bom_to_update:
                try:
                    BOMVersioningService.create_bom_version(
                        bom=bom_to_update,
                        change_reason=f"Overhead expense confirmed: {expense.description}",
                        change_type='overhead_added',
                        created_by_id=current_user.id,
                        recalculate_overhead=True
                    )
                except Exception as e:
                    current_app.logger.warning(f"BOM versioning during expense approval: {e}")

    @classmethod
    def _post_approve_sale_return(cls, sale_return):
        """Mirrors returns.py return_to-inventory logic when a sale return is approved."""
        from app import db
        from app.models import Product, ProductWarehouseStock

        if not sale_return.returned_to_inventory:
            for item in sale_return.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(item.quantity)

                try:
                    wh_id = getattr(item, 'warehouse_id', None)
                except Exception:
                    wh_id = None
                if wh_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(
                        product_id=item.product_id, warehouse_id=wh_id
                    ).first()
                    if not wh_stock:
                        wh_stock = ProductWarehouseStock(
                            product_id=item.product_id, warehouse_id=wh_id, quantity=0
                        )
                        db.session.add(wh_stock)
                    wh_stock.quantity += item.quantity
                elif product and product.warehouse_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(
                        product_id=item.product_id, warehouse_id=product.warehouse_id
                    ).first()
                    if not wh_stock:
                        wh_stock = ProductWarehouseStock(
                            product_id=item.product_id, warehouse_id=product.warehouse_id, quantity=0
                        )
                        db.session.add(wh_stock)
                    wh_stock.quantity += item.quantity

            sale_return.returned_to_inventory = True
            sale_return.status = 'completed'

    @classmethod
    def _post_approve_payment(cls, payment):
        """Mirrors sales.py approve_payment logic.

        Skips payments that were already applied to the invoice when recorded
        (staff payments flagged needs_approval) — approving those only
        acknowledges them, so adding the amount again would double-pay.
        """
        if getattr(payment, '_was_already_applied', False):
            return
        from app.models import Sale
        if payment.invoice_id:
            sale = Sale.query.get(payment.invoice_id)
            if sale:
                sale.paid_amount = (sale.paid_amount or 0) + payment.amount
                sale.update_status()

    @classmethod
    def _post_approve_advance(cls, advance):
        """No extra logic for CustomerAdvance approval — just flips flag."""
        pass

    @classmethod
    def _post_status_change_payment(cls, payment, universal_status):
        """Reverse an already-applied payment when it is rejected/cancelled.

        Staff payments are applied to the invoice at record time, so refusing
        one must pull the money back out — otherwise the invoice stays paid by
        a payment the admin refused. Legacy pending payments were never applied
        (_was_already_applied is False), so nothing happens for them.
        """
        if universal_status not in ('reject', 'cancel'):
            return
        from app.models import Sale
        if not payment.invoice_id:
            return
        sale = Sale.query.get(payment.invoice_id)
        if not sale:
            return

        if getattr(payment, '_was_already_applied', False):
            from app.utils import adjust_sale_payment
            adjust_sale_payment(sale, -float(payment.amount or 0), current_user.id)

        # A refused payment also takes back any lump-sum discount it granted,
        # regardless of whether its cash had been applied yet.
        if float(getattr(payment, 'lump_discount_amount', 0) or 0) > 0:
            from app.utils import reverse_lump_sum_discount
            reverse_lump_sum_discount(sale, payment.lump_discount_amount)
            payment.lump_discount_amount = 0

    @classmethod
    def _post_approve_purchase_bill(cls, bill):
        """Ensure payment status reflects current amounts after approval."""
        bill.update_status()

    @classmethod
    def _post_approve_purchase_return(cls, ret):
        """Handle side effects when a purchase return is approved."""
        from app import db
        from app.models import Product, ProductWarehouseStock, PurchaseBill
        
        if not ret.is_approved: return # Should be covered by caller
        
        # 1. Update Inventory
        for item in ret.items:
            product = Product.query.get(item.product_id)
            if product:
                product.update_quantity(-item.quantity)
                
                wh_id = getattr(item, 'warehouse_id', None)
                if wh_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(
                        product_id=item.product_id, warehouse_id=wh_id
                    ).first()
                    if wh_stock:
                        wh_stock.quantity -= item.quantity
                elif product.warehouse_id:
                    wh_stock = ProductWarehouseStock.query.filter_by(
                        product_id=item.product_id, warehouse_id=product.warehouse_id
                    ).first()
                    if wh_stock:
                        wh_stock.quantity -= item.quantity

        # 2. Adjust Bill Total
        if ret.bill_id:
            bill = PurchaseBill.query.get(ret.bill_id)
            if bill:
                bill.total -= ret.total
                bill.base_total -= ret.subtotal
                bill.tax_amount -= ret.tax
                bill.update_status()
        
        db.session.commit()

    @classmethod
    def _post_approve_vendor_advance(cls, advance):
        """No extra logic for VendorAdvance approval — just flips flag."""
        pass

    @classmethod
    def _post_approve_bill_payment(cls, payment):
        """Mirrors purchase.py pay_bill logic when a payment is approved."""
        from app.models import PurchaseBill
        if payment.bill_id:
            bill = PurchaseBill.query.get(payment.bill_id)
            if bill:
                bill.paid_amount = (bill.paid_amount or 0) + payment.amount
                bill.update_status()

    @classmethod
    def _post_approve_tool_receiving(cls, receiving):
        """Increase inventory when receiving is approved."""
        if not receiving.stock_updated:
            from app import db
            from app.models import Product, ProductWarehouseStock
            for item in receiving.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(item.quantity)
                    product.cost_price = item.unit_price
                    if item.warehouse_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(
                            product_id=item.product_id, warehouse_id=item.warehouse_id
                        ).first()
                        if not wh_stock:
                            wh_stock = ProductWarehouseStock(
                                product_id=item.product_id, warehouse_id=item.warehouse_id, quantity=0.0
                            )
                            db.session.add(wh_stock)
                        wh_stock.quantity += item.quantity
            receiving.stock_updated = True
            db.session.commit()

    @classmethod
    def _post_status_change_tool_receiving(cls, receiving, new_status):
        """Revert inventory additions if tool receiving status changes to draft/reject/cancel."""
        if new_status in ('draft', 'cancel', 'reject') and receiving.stock_updated:
            from app import db
            from app.models import Product, ProductWarehouseStock
            for item in receiving.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(-item.quantity)
                    wh_id = getattr(item, 'warehouse_id', None)
                    if wh_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(
                            product_id=item.product_id, warehouse_id=wh_id
                        ).first()
                        if wh_stock:
                            wh_stock.quantity = max(0.0, wh_stock.quantity - item.quantity)
            receiving.stock_updated = False
            db.session.commit()

    @classmethod
    def _post_approve_tool_delivering(cls, delivering):
        """Decrease inventory when delivering is approved."""
        if not delivering.stock_updated:
            from app import db
            from app.models import Product, ProductWarehouseStock
            for item in delivering.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(-item.quantity)
                    if item.warehouse_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(
                            product_id=item.product_id, warehouse_id=item.warehouse_id
                        ).first()
                        if not wh_stock:
                            wh_stock = ProductWarehouseStock(
                                product_id=item.product_id, warehouse_id=item.warehouse_id, quantity=0.0
                            )
                            db.session.add(wh_stock)
                        wh_stock.quantity = max(0.0, wh_stock.quantity - item.quantity)
            delivering.stock_updated = True
            db.session.commit()

    @classmethod
    def _post_status_change_tool_delivering(cls, delivering, new_status):
        """Revert inventory deduction if tool delivering status changes to draft/reject/cancel."""
        if new_status in ('draft', 'cancel', 'reject') and delivering.stock_updated:
            from app import db
            from app.models import Product, ProductWarehouseStock
            for item in delivering.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.update_quantity(item.quantity)
                    wh_id = getattr(item, 'warehouse_id', None)
                    if wh_id:
                        wh_stock = ProductWarehouseStock.query.filter_by(
                            product_id=item.product_id, warehouse_id=wh_id
                        ).first()
                        if wh_stock:
                            wh_stock.quantity += item.quantity
            delivering.stock_updated = False
            db.session.commit()
