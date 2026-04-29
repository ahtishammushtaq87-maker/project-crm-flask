#!/usr/bin/env python
"""
BOM Versioning Service
Handles automatic BOM version creation and updates
"""
from app import db
from app.models import BOM, BOMItem, BOMVersion, BOMVersionItem, CostPriceHistory
from sqlalchemy import func
from datetime import datetime


class BOMVersioningService:
    """Service for managing BOM versions"""
    
    @staticmethod
    def get_next_version(current_version):
        """Get next version number (v1 -> v2, v2 -> v3)"""
        try:
            num = int(current_version[1:])
            return f"v{num + 1}"
        except (ValueError, IndexError):
            return "v2"
    
    @staticmethod
    def create_bom_version(bom, change_reason, change_type, created_by_id, recalculate_overhead=True):
        """
        Create a new version of a BOM
        
        Args:
            bom: BOM object
            change_reason: Reason for version change (e.g., "Component price increase")
            change_type: Type of change ('component_cost', 'overhead_added', 'manual')
            created_by_id: User ID who triggered the change
            recalculate_overhead: Whether to recalculate overhead from expenses
        
        Returns:
            BOMVersion object
        """
        # Calculate overhead from linked expenses if needed
        if recalculate_overhead:
            from app.models import Expense
            total_overhead = db.session.query(func.sum(Expense.amount)).filter(
                Expense.bom_id == bom.id,
                Expense.is_bom_overhead == True
            ).scalar() or 0
            bom.overhead_cost = total_overhead
        
        # Recalculate total cost before creating version
        bom.calculate_total_cost()
        
        # Get next version number
        new_version_num = BOMVersioningService.get_next_version(bom.version)
        
        # Create version record
        version = BOMVersion(
            bom_id=bom.id,
            version_number=new_version_num,
            labor_cost=bom.labor_cost,
            overhead_cost=bom.overhead_cost,
            total_cost=bom.total_cost,
            change_reason=change_reason,
            change_type=change_type,
            previous_version=bom.version,
            created_by=created_by_id
        )
        db.session.add(version)
        db.session.flush()  # Get version ID
        
        # Copy current BOM items as version items (snapshot)
        for item in bom.items:
            version_item = BOMVersionItem(
                version_id=version.id,
                component_id=item.component_id,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                shipping_per_unit=item.shipping_per_unit,
                total_cost=item.total_cost
            )
            db.session.add(version_item)
        
        # Update BOM to new version
        bom.version = new_version_num
        bom.is_active = True
        
        db.session.commit()
        return version
    
    @staticmethod
    def check_and_update_bom_for_cost_changes(product_id, created_by_id, recalculate_overhead=True):
        """
        Check all BOMs that use this product as a component
        If component cost changed, create new BOM version
        
        Args:
            product_id: Product ID that had cost change
            created_by_id: User ID
            recalculate_overhead: Whether to recalculate overhead from expenses
        
        Returns:
            List of updated BOM objects
        """
        print(f"\n[BOM_VERSION_SERVICE] check_and_update_bom_for_cost_changes called")
        print(f"[BOM_VERSION_SERVICE] Product ID: {product_id}, User ID: {created_by_id}")
        
        updated_boms = []
        
        # Find all BOM items that use this product
        bom_items = BOMItem.query.filter_by(component_id=product_id).all()
        print(f"[BOM_VERSION_SERVICE] Found {len(bom_items)} BOM items using this product")
        
        for bom_item in bom_items:
            bom = bom_item.bom
            print(f"[BOM_VERSION_SERVICE] Processing BOM: {bom.name if bom else 'NULL'} (ID: {bom.id if bom else 'NULL'})")
            
            if not bom:
                print(f"[BOM_VERSION_SERVICE] ⚠ BOM is NULL, skipping")
                continue
            
            # Get product's current cost
            component = bom_item.component
            if not component:
                print(f"[BOM_VERSION_SERVICE] ⚠ Component is NULL, skipping")
                continue
            
            # Check if cost in BOM item matches current product cost
            current_cost = component.cost_price
            bom_item_cost = bom_item.unit_cost
            
            print(f"[BOM_VERSION_SERVICE] Component: {component.name}")
            print(f"[BOM_VERSION_SERVICE]   Current product cost: PKR {current_cost}")
            print(f"[BOM_VERSION_SERVICE]   BOM item cost: PKR {bom_item_cost}")
            
            if bom_item_cost != current_cost:
                print(f"[BOM_VERSION_SERVICE] ✓ COST MISMATCH DETECTED!")
                # Cost has changed, update the BOM item with new cost FIRST
                bom_item.unit_cost = current_cost
                bom_item.total_cost = (current_cost + bom_item.shipping_per_unit) * bom_item.quantity
                print(f"[BOM_VERSION_SERVICE] BOM item updated: unit_cost={bom_item.unit_cost}, total_cost={bom_item.total_cost}")
                
                # Then create new version (which will recalculate BOM total_cost)
                change_reason = f"Component '{component.name}' cost changed from PKR {bom_item_cost} to PKR {current_cost}"
                print(f"[BOM_VERSION_SERVICE] Creating new version: {change_reason}")
                
                BOMVersioningService.create_bom_version(
                    bom=bom,
                    change_reason=change_reason,
                    change_type='component_cost',
                    created_by_id=created_by_id,
                    recalculate_overhead=recalculate_overhead
                )
                
                updated_boms.append(bom)
            else:
                print(f"[BOM_VERSION_SERVICE] ✓ Costs match, no version needed")
        
        if updated_boms:
            print(f"[BOM_VERSION_SERVICE] Committing {len(updated_boms)} updated BOM(s)")
            db.session.commit()
        else:
            print(f"[BOM_VERSION_SERVICE] No BOMs were updated")
        
        return updated_boms
    
    @staticmethod
    def check_and_update_bom_for_overhead_changes(bom_id, new_overhead, old_overhead, created_by_id):
        """
        Check if overhead cost changed and create new BOM version if needed
        
        Args:
            bom_id: BOM ID
            new_overhead: New overhead cost
            old_overhead: Previous overhead cost
            created_by_id: User ID
        
        Returns:
            BOMVersion if created, None otherwise
        """
        if new_overhead == old_overhead:
            return None
        
        bom = BOM.query.get(bom_id)
        if not bom:
            return None
        
        # Create new version
        change_reason = f"Overhead cost changed from PKR {old_overhead} to PKR {new_overhead}"
        
        version = BOMVersioningService.create_bom_version(
            bom=bom,
            change_reason=change_reason,
            change_type='overhead_added',
            created_by_id=created_by_id,
            recalculate_overhead=True
        )
        
        return version
    
    @staticmethod
    def get_bom_version_history(bom_id):
        """
        Get version history for a BOM (most recent first)
        
        Returns:
            List of BOMVersion objects
        """
        versions = BOMVersion.query.filter_by(bom_id=bom_id).order_by(
            BOMVersion.created_at.desc()
        ).all()
        return versions
    
    @staticmethod
    def compare_bom_versions(version1_id, version2_id):
        """
        Compare two BOM versions
        
        Returns:
            Dict with comparison data
        """
        v1 = BOMVersion.query.get(version1_id)
        v2 = BOMVersion.query.get(version2_id)
        
        if not v1 or not v2:
            return None
        
        comparison = {
            'version1': {
                'version': v1.version_number,
                'labor_cost': v1.labor_cost,
                'overhead_cost': v1.overhead_cost,
                'total_cost': v1.total_cost,
                'items': []
            },
            'version2': {
                'version': v2.version_number,
                'labor_cost': v2.labor_cost,
                'overhead_cost': v2.overhead_cost,
                'total_cost': v2.total_cost,
                'items': []
            },
            'cost_difference': v2.total_cost - v1.total_cost,
            'percentage_change': ((v2.total_cost - v1.total_cost) / v1.total_cost * 100) if v1.total_cost > 0 else 0
        }
        
        # Get items from both versions
        for item in v1.items:
            comparison['version1']['items'].append({
                'component_id': item.component_id,
                'component_name': item.component.name if item.component else 'Unknown',
                'quantity': item.quantity,
                'unit_cost': item.unit_cost,
                'shipping_per_unit': item.shipping_per_unit,
                'total_cost': item.total_cost
            })
        
        for item in v2.items:
            comparison['version2']['items'].append({
                'component_id': item.component_id,
                'component_name': item.component.name if item.component else 'Unknown',
                'quantity': item.quantity,
                'unit_cost': item.unit_cost,
                'shipping_per_unit': item.shipping_per_unit,
                'total_cost': item.total_cost
            })
        
        return comparison
    
    @staticmethod
    def allocate_purchase_shipping_to_bom(purchase_item_id):
        """
        When a purchase item is added, calculate per-unit shipping
        and propagate to BOM items if applicable
        
        This helps track product shipping cost in BOM calculations
        """
        from app.models import PurchaseItem
        
        purchase_item = PurchaseItem.query.get(purchase_item_id)
        if not purchase_item:
            return
        
        # Calculate per-unit shipping
        per_unit_shipping = purchase_item.per_unit_shipping
        
        # Find all BOM items that use this product
        bom_items = BOMItem.query.filter_by(
            component_id=purchase_item.product_id
        ).all()
        
        # Update shipping cost in BOM items (if not already set)
        for bom_item in bom_items:
            if bom_item.shipping_per_unit == 0 or bom_item.shipping_per_unit < per_unit_shipping:
                # Update to latest/highest shipping cost
                bom_item.shipping_per_unit = per_unit_shipping
                bom_item.total_cost = (bom_item.unit_cost + per_unit_shipping) * bom_item.quantity
        
        if bom_items:
            db.session.commit()
