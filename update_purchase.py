import os

file_path = r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\app\routes\purchase.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update create_bill
old_create = """        # Add items WITHOUT updating inventory (deferred to Receive Quantity step)
        for item_data in items_data:
            prod_id = item_data['product_id']
            qty = item_data['quantity']
            price = item_data['unit_price']
            item_total = item_data['total']

            item = PurchaseItem(
                product_id=prod_id,
                quantity=qty,
                unit_price=price,
                total=item_total
            )
            bill.items.append(item)
            # NOTE: inventory & cost price are NOT updated on bill creation.
            # They update when user clicks "Receive Quantity" on the bill detail page."""

new_create = """        # Add items and automatically update inventory and cost prices
        receive_record = BillReceive(
            bill_id=bill.id,
            notes="Automatically received on bill creation",
            created_by=current_user.id
        )
        db.session.add(receive_record)
        db.session.flush() # to get receive_record.id

        for item_data in items_data:
            prod_id = item_data['product_id']
            qty = item_data['quantity']
            price = item_data['unit_price']
            item_total = item_data['total']

            item = PurchaseItem(
                product_id=prod_id,
                quantity=qty,
                unit_price=price,
                total=item_total
            )
            bill.items.append(item)
            db.session.flush() # to get item.id for BillReceiveItem

            # Save receive item record
            bri = BillReceiveItem(
                receive_id=receive_record.id,
                purchase_item_id=item.id,
                product_id=prod_id,
                quantity_received=qty
            )
            db.session.add(bri)
            db.session.flush()

            # Update inventory & cost
            product = Product.query.get(prod_id)
            if product:
                old_qty = product.quantity
                product.update_quantity(qty)

                # Calculate proportional cost (shipping + tax allocated by item value)
                if total_items_cost > 0:
                    allocation_ratio = item_total / total_items_cost
                    allocated_additional = total_additional_cost * allocation_ratio
                else:
                    allocated_additional = 0
                new_unit_cost = price + (allocated_additional / qty) if qty > 0 else price

                # Record cost price history
                old_price = product.cost_price
                cost_history = CostPriceHistory(
                    product_id=prod_id,
                    purchase_bill_id=bill.id,
                    bill_receive_item_id=bri.id,
                    old_price=old_price if old_price > 0 else None,
                    new_price=new_unit_cost,
                    quantity_at_old_price=old_qty,
                    used_quantity=0,
                    reason=f"Automatically received from Bill {bill_number}",
                    is_active=True,
                    created_by=current_user.id
                )
                db.session.add(cost_history)
                product.cost_price = new_unit_cost

                # Trigger BOM versioning
                try:
                    user_id = current_user.id if current_user.is_authenticated else 1
                    BOMVersioningService.check_and_update_bom_for_cost_changes(
                        product_id=prod_id,
                        created_by_id=user_id
                    )
                except Exception as e:
                    print(f"BOM versioning error for product {prod_id}: {e}")

        bill.inventory_received = True"""

if old_create in content:
    content = content.replace(old_create, new_create)
    print("Success: Updated create_bill")
else:
    # Try normalized match
    old_create_norm = old_create.replace('\r\n', '\n')
    content_norm = content.replace('\r\n', '\n')
    if old_create_norm in content_norm:
        content = content_norm.replace(old_create_norm, new_create.replace('\r\n', '\n'))
        print("Success: Updated create_bill (normalized)")

# 2. Update edit_bill
old_edit = """        bill.update_status()

        # Handle bill image upload on edit"""

new_edit = """        bill.update_status()

        # Automatically update inventory and cost prices on edit
        receive_record = BillReceive(
            bill_id=bill.id,
            notes="Automatically received on bill update",
            created_by=current_user.id
        )
        db.session.add(receive_record)
        db.session.flush()

        # Recalculate allocation for cost
        total_items_cost = sum(item.total for item in bill.items)
        taxable_amount = total_items_cost + bill.shipping_charge
        tax_amount = (taxable_amount * bill.tax_rate) / 100 if bill.tax_rate > 0 else 0
        total_additional_cost = bill.shipping_charge + tax_amount

        for item in bill.items:
            # Save receive item record
            bri = BillReceiveItem(
                receive_id=receive_record.id,
                purchase_item_id=item.id,
                product_id=item.product_id,
                quantity_received=item.quantity
            )
            db.session.add(bri)
            db.session.flush()

            # Update inventory & cost
            product = Product.query.get(item.product_id)
            if product:
                old_qty = product.quantity
                product.update_quantity(item.quantity)

                # Calculate proportional cost
                if total_items_cost > 0:
                    allocation_ratio = item.total / total_items_cost
                    allocated_additional = total_additional_cost * allocation_ratio
                else:
                    allocated_additional = 0
                new_unit_cost = item.unit_price + (allocated_additional / item.quantity) if item.quantity > 0 else item.unit_price

                # Record cost price history
                old_price = product.cost_price
                cost_history = CostPriceHistory(
                    product_id=item.product_id,
                    purchase_bill_id=bill.id,
                    bill_receive_item_id=bri.id,
                    old_price=old_price if old_price > 0 else None,
                    new_price=new_unit_cost,
                    quantity_at_old_price=old_qty,
                    used_quantity=0,
                    reason=f"Automatically received from Bill Update {bill.bill_number}",
                    is_active=True,
                    created_by=current_user.id
                )
                db.session.add(cost_history)
                product.cost_price = new_unit_cost
                
                # Trigger BOM versioning
                try:
                    user_id = current_user.id if current_user.is_authenticated else 1
                    BOMVersioningService.check_and_update_bom_for_cost_changes(
                        product_id=item.product_id,
                        created_by_id=user_id
                    )
                except Exception as e:
                    print(f"BOM versioning error: {e}")

        bill.inventory_received = True

        # Handle bill image upload on edit"""

if old_edit in content:
    content = content.replace(old_edit, new_edit)
    print("Success: Updated edit_bill")

# 3. Update flash messages
flash_old1 = 'flash(\'Purchase bill created successfully! Use "Receive Quantity" on the bill detail page to update inventory.\', \'success\')'
flash_new1 = 'flash(\'Purchase bill created successfully! Inventory and cost prices have been updated.\', \'success\')'
content = content.replace(flash_old1, flash_new1)

flash_old2 = 'flash(\'Purchase bill updated successfully! Use "Receive Quantity" to re-update inventory.\', \'success\')'
flash_new2 = 'flash(\'Purchase bill updated successfully! Inventory and cost prices have been updated.\', \'success\')'
content = content.replace(flash_old2, flash_new2)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
