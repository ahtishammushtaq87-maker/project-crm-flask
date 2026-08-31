from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
from app.utils import permission_required, log_activity
from flask_login import login_required, current_user
from app import db
from app.models import ProductionTarget, ProductionLog, Product, BOM, SaleItem, Sale, ManufacturingOrder
from datetime import datetime, timedelta
from calendar import monthrange
from sqlalchemy import func
from app.report_utils import generate_excel, generate_csv, generate_pdf
from app.services.production_targets import compute_target_result, finalize_overdue_targets

bp = Blueprint('production', __name__)

@bp.route('/')
@login_required
def index():
    """Production Target Dashboard - Main view"""
    # Defensive fallback: the background scheduler normally finalizes overdue
    # targets, but catch anything it hasn't gotten to yet whenever this page
    # is loaded.
    finalize_overdue_targets()

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    selected_product_id = request.args.get('product_id', type=int, default=None)
    view = request.args.get('view', 'active')
    if view not in ('active', 'previous'):
        view = 'active'

    if start_date_str:
        month_start = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        month_start = datetime(datetime.now().year, datetime.now().month, 1)

    if end_date_str:
        month_end = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    else:
        _, days_in_month = monthrange(month_start.year, month_start.month)
        month_end = datetime(month_start.year, month_start.month, days_in_month, 23, 59, 59)

    products = Product.query.filter_by(is_active=True, is_manufactured=True).order_by(Product.name).all()

    today = datetime.now().date()
    if today >= month_start.date() and today <= month_end.date():
        total_days = (month_end.date() - month_start.date()).days + 1
        elapsed_days = (today - month_start.date()).days + 1
        expected_progress = (elapsed_days / total_days) * 100
    elif today > month_end.date():
        expected_progress = 100
    else:
        expected_progress = 0

    results = []
    total_target = 0
    total_produced_all = 0
    total_remaining = 0
    total_revenue = 0
    total_cost = 0
    total_profit = 0
    actual_revenue_all = 0
    actual_cost_all = 0
    actual_profit_all = 0

    if view == 'active':
        query = ProductionTarget.query.filter(
            ProductionTarget.status == 'active',
            db.or_(
                db.and_(ProductionTarget.month == month_start.month, ProductionTarget.year == month_start.year),
                db.and_(ProductionTarget.start_date >= month_start.date(), ProductionTarget.start_date <= month_end.date()),
                db.and_(ProductionTarget.end_date >= month_start.date(), ProductionTarget.end_date <= month_end.date())
            )
        )
        if selected_product_id:
            query = query.filter_by(sku_id=selected_product_id)
        targets = query.all()

        for target in targets:
            result = compute_target_result(target, expected_progress=expected_progress)
            results.append(result)

            total_target += result['effective_target_units']
            total_produced_all += (result['net_produced'] + result['returned_qty'])  # Use Net Produced (pre-return) for the summary box, matching prior behavior
            total_remaining += result['remaining']
            total_revenue += result['target_revenue']
            total_cost += result['estimated_cost']
            total_profit += result['estimated_profit']
            actual_revenue_all += result['actual_revenue']
            actual_cost_all += result['actual_cost']
            actual_profit_all += result['actual_profit']
    else:
        query = ProductionTarget.query.filter(ProductionTarget.status == 'completed')
        if selected_product_id:
            query = query.filter_by(sku_id=selected_product_id)
        targets = query.order_by(ProductionTarget.result_generated_at.desc()).all()

        for target in targets:
            results.append({
                'target': target,
                'product': target.product,
                'target_units': target.final_target_units or 0,
                'produced_qty': target.final_produced_qty or 0,
                'net_produced': target.final_net_produced or 0,
                'completion_pct': target.final_completion_pct or 0,
                'status': target.final_result_status or '',
                'status_class': {'DONE': 'primary', 'ON TRACK': 'success', 'BEHIND': 'danger'}.get(target.final_result_status, 'secondary'),
                'actual_revenue': target.final_actual_revenue or 0,
                'actual_cost': target.final_actual_cost or 0,
                'actual_profit': target.final_actual_profit or 0,
            })

    overall_completion = (total_produced_all / total_target * 100) if total_target > 0 else 0

    return render_template('production/index.html',
                         results=results,
                         products=products,
                         view=view,
                         start_date=month_start.strftime('%Y-%m-%d'),
                         end_date=month_end.strftime('%Y-%m-%d'),
                         selected_product_id=selected_product_id,
                         total_target=total_target,
                         total_produced=total_produced_all,
                         total_remaining=total_remaining,
                         overall_completion=round(overall_completion, 1),
                         total_revenue=total_revenue,
                         total_cost=total_cost,
                         total_profit=total_profit,
                         actual_revenue=actual_revenue_all,
                         actual_cost=actual_cost_all,
                         actual_profit=actual_profit_all,
                         expected_progress=round(expected_progress, 1))


@bp.route('/set-target', methods=['GET', 'POST'])
@login_required
@permission_required('production', action='add')
def set_target():
    """Set monthly production targets for products"""
    target_id = request.args.get('id', type=int)
    target = None
    if target_id:
        target = ProductionTarget.query.get_or_404(target_id)
    
    products = Product.query.filter_by(is_active=True, is_manufactured=True).order_by(Product.name).all()

    # Gather in-progress MO numbers per product (via BOM relationship)
    inprogress_mos = ManufacturingOrder.query.filter(
        ManufacturingOrder.status == 'In Progress'
    ).all()
    # Build dict: product_id -> list of order_numbers
    mo_by_product = {}
    for mo in inprogress_mos:
        try:
            prod_id = mo.bom.product_id
            mo_by_product.setdefault(prod_id, []).append(mo.order_number)
        except Exception:
            pass
    
    selected_month = request.args.get('month', type=int, default=datetime.now().month)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)
    
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if not start_date_str or not end_date_str:
            flash('Please select a valid date range.', 'danger')
            return redirect(url_for('production.set_target'))
            
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        start_time = datetime.strptime(start_time_str, '%H:%M').time() if start_time_str else None
        end_time = datetime.strptime(end_time_str, '%H:%M').time() if end_time_str else None

        month = start_date.month
        year = start_date.year

        sku_ids = request.form.getlist('sku_ids')
        target_units_val = request.form.get('target_units')
        target_units = float(target_units_val) if target_units_val else 0.0
        overhead_cost_per_unit = float(request.form.get('overhead_cost_per_unit', 0))
        
        submitted_sku_ids = [int(sid) for sid in sku_ids if sid]
        
        if not submitted_sku_ids and not target:
            flash('Please select at least one product.', 'danger')
            return redirect(url_for('production.set_target'))

        try:
            if target:
                # Single edit mode
                target.start_date = start_date
                target.end_date = end_date
                target.start_time = start_time
                target.end_time = end_time
                target.month = month
                target.year = year
                target.target_units = target_units
                target.overhead_cost_per_unit = overhead_cost_per_unit
                # Editing a previously auto-completed target re-activates it,
                # so it goes back to live tracking instead of staying frozen
                # with numbers that no longer match the edited target.
                target.status = 'active'
                target.result_generated_at = None
            else:
                # Bulk add/update mode
                for sku_id in submitted_sku_ids:
                    # Look for existing target in this EXACT range for this SKU
                    existing = ProductionTarget.query.filter_by(
                        start_date=start_date,
                        end_date=end_date,
                        sku_id=sku_id
                    ).first()

                    if existing:
                        curr_target = existing
                    else:
                        curr_target = ProductionTarget(
                            start_date=start_date,
                            end_date=end_date,
                            month=month,
                            year=year,
                            sku_id=sku_id
                        )
                        db.session.add(curr_target)

                    curr_target.start_time = start_time
                    curr_target.end_time = end_time
                    curr_target.target_units = target_units
                    curr_target.overhead_cost_per_unit = overhead_cost_per_unit
                    curr_target.status = 'active'
                    curr_target.result_generated_at = None
            
            db.session.commit()
            log_activity('Production', f'Saved Production Targets', f'Month: {month}/{year}')
            flash('Targets saved successfully.', 'success')
            return redirect(url_for('production.index', month=month, year=year))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('production/set_target.html',
                         target=target,
                         products=products,
                         mo_by_product=mo_by_product,
                         selected_month=selected_month,
                         selected_year=selected_year)


@bp.route('/delete-target/<int:id>')
@login_required
@permission_required('production', action='delete')
def delete_target(id):
    """Delete a production target"""
    try:
        target = ProductionTarget.query.get_or_404(id)
        month = target.month
        year = target.year
        target_sku_id = target.sku_id

        db.session.delete(target)
        db.session.commit()
        log_activity('Production', f'Deleted Production Target', f'Product ID: {target_sku_id}, Month: {month}/{year}')
        flash('Target deleted successfully.', 'success')
        return redirect(url_for('production.index', month=month, year=year))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting target: {str(e)}', 'danger')
        return redirect(url_for('production.index'))


@bp.route('/logs')
@login_required
def logs():
    """Daily Production Log View"""
    selected_date = request.args.get('date')
    selected_sku_id = request.args.get('sku_id', type=int)
    
    query = ProductionLog.query
    
    if selected_date:
        log_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        query = query.filter_by(date=log_date)
    
    if selected_sku_id:
        query = query.filter_by(sku_id=selected_sku_id)
    
    logs = query.order_by(ProductionLog.date.desc(), ProductionLog.id.desc()).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    return render_template('production/logs.html',
                         logs=logs,
                         products=products,
                         selected_date=selected_date,
                         selected_sku_id=selected_sku_id)


@bp.route('/log/add', methods=['GET', 'POST'])
@login_required
@permission_required('production', action='add')
def add_log():
    """Add daily production log entry"""
    log_id = request.args.get('id', type=int)
    log = None
    if log_id:
        log = ProductionLog.query.get_or_404(log_id)
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        sku_id = int(request.form.get('sku_id'))
        shift = request.form.get('shift')
        operator = request.form.get('operator')
        qty_produced = float(request.form.get('qty_produced', 0))
        rejected_qty = float(request.form.get('rejected_qty', 0))
        notes = request.form.get('notes')
        
        if not log:
            log = ProductionLog(
                date=date,
                sku_id=sku_id,
                shift=shift,
                operator=operator,
                qty_produced=qty_produced,
                rejected_qty=rejected_qty,
                notes=notes,
                created_by=current_user.id
            )
            db.session.add(log)
        else:
            log.date = date
            log.sku_id = sku_id
            log.shift = shift
            log.operator = operator
            log.qty_produced = qty_produced
            log.rejected_qty = rejected_qty
            log.notes = notes
        
        try:
            db.session.commit()
            
            # Update stock: add production qty to finished good
            production_product = Product.query.get(sku_id)
            if production_product:
                # Add to inventory
                from app.models import StockMovement
                production_product.quantity += qty_produced
                
                # Log movement
                move = StockMovement(
                    product_id=production_product.id,
                    quantity=qty_produced,
                    movement_type='in',
                    reference_type='production_log',
                    reference_id=log.id,
                    notes=f"Production log: {shift} - {operator}"
                )
                db.session.add(move)
                
                # Sync cost price as well
                active_bom = BOM.query.filter_by(product_id=production_product.id, is_active=True).first()
                if active_bom:
                    production_product.cost_price = active_bom.total_cost
                
            db.session.commit()
            log_activity('Production', f'{"Updated" if log_id else "Created"} Production Log', f'Product ID: {sku_id}, Qty: {produced_qty}')
            flash('Production log saved and inventory updated.', 'success')
            return redirect(url_for('production.logs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('production/log_form.html',
                         log=log,
                         products=products)


@bp.route('/log/<int:id>/delete')
@login_required
@permission_required('production', action='delete')
def delete_log(id):
    """Delete a production log and reverse stock"""
    log = ProductionLog.query.get_or_404(id)
    sku_id = log.sku_id
    qty = log.qty_produced
    log_product_name = log.product.name if log.product else "N/A"

    try:
        # Reverse stock
        product = Product.query.get(sku_id)
        if product:
            product.quantity -= qty
            
            # Remove stock movement
            from app.models import StockMovement
            StockMovement.query.filter_by(
                product_id=sku_id,
                reference_type='production_log',
                reference_id=log.id
            ).delete()
            
        # Update Production Target Produced Qty (Stateful)
        from app.models import ProductionTarget
        target = ProductionTarget.query.filter(
            ProductionTarget.sku_id == sku_id,
            ProductionTarget.start_date <= log.date,
            ProductionTarget.end_date >= log.date
        ).first()
        if target and target.produced_qty is not None:
            target.produced_qty -= qty
            
        db.session.delete(log)
        db.session.commit()
        log_activity('Production', f'Deleted Production Log', f'Product: {log_product_name}, Qty: {qty}')
        flash('Production log deleted and stock reversed.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting log: {str(e)}', 'danger')
        
    return redirect(url_for('production.logs'))


@bp.route('/api/produced-qty')
@login_required
def api_produced_qty():
    """API: Get produced quantity for a SKU within date range"""
    sku_id = request.args.get('sku_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not all([sku_id, start_date, end_date]):
        return jsonify({'error': 'Missing parameters'}), 400
    
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    produced = db.session.query(func.sum(ProductionLog.qty_produced)).filter(
        ProductionLog.sku_id == sku_id,
        ProductionLog.date >= start,
        ProductionLog.date <= end
    ).scalar() or 0
    
    rejected = db.session.query(func.sum(ProductionLog.rejected_qty)).filter(
        ProductionLog.sku_id == sku_id,
        ProductionLog.date >= start,
        ProductionLog.date <= end
    ).scalar() or 0
    
    return jsonify({
        'sku_id': sku_id,
        'produced_qty': produced,
        'rejected_qty': rejected,
        'total': produced + rejected
    })


@bp.route('/api/bom-cost/<int:sku_id>')
@login_required
def api_bom_cost(sku_id):
    """API: Get BOM cost for a product"""
    product = Product.query.get_or_404(sku_id)
    
    bom = BOM.query.filter_by(product_id=product.id, is_active=True).first()
    if bom:
        bom_cost = bom.total_cost - bom.overhead_cost - bom.labor_cost
        overhead_cost = bom.overhead_cost + bom.labor_cost
        labor_cost = bom.labor_cost
    else:
        bom_cost = product.cost_price
        overhead_cost = 0
        labor_cost = 0
    
    return jsonify({
        'sku_id': sku_id,
        'bom_cost': bom_cost,
        'overhead_cost': overhead_cost,
        'labor_cost': labor_cost,
        'product_cost': product.cost_price
    })


@bp.route('/api/update-target', methods=['POST'])
@login_required
@permission_required('production', action='edit')
def api_update_target():
    """API: Update production target inline"""
    data = request.get_json()
    target_id = data.get('target_id')
    field = data.get('field')
    value = data.get('value')
    
    target = ProductionTarget.query.get_or_404(target_id)
    
    try:
        # Convert value safely
        if value is None or str(value).strip() == '':
            num_value = None # Reset to use logs
        else:
            num_value = float(value)
            
        if field == 'target_units':
            target.target_units = num_value if num_value is not None else 0
        elif field == 'produced_qty':
            target.produced_qty = num_value
        elif field == 'overhead_cost_per_unit':
            target.overhead_cost_per_unit = num_value
        else:
            return jsonify({'success': False, 'message': 'Invalid field'}), 400
            
        db.session.commit()
        log_activity('Production', f'Updated target {field}', f'Target ID: {target_id}, Value: {value}')
        return jsonify({'success': True, 'message': 'Updated successfully'})
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid number format'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/selling-price/<int:sku_id>')
@login_required
def api_selling_price(sku_id):
    """API: Get selling price for a product"""
    product = Product.query.get_or_404(sku_id)
    
    return jsonify({
        'sku_id': sku_id,
        'selling_price': product.finished_good_price if product.finished_good_price else product.unit_price
    })


@bp.route('/export/<string:format>')
@login_required
def export_report(format):
    """Export production target report"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str:
        month_start = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        month_start = datetime(datetime.now().year, datetime.now().month, 1)
        
    if end_date_str:
        month_end = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    else:
        _, days_in_month = monthrange(month_start.year, month_start.month)
        month_end = datetime(month_start.year, month_start.month, days_in_month, 23, 59, 59)

    # Filter targets occurring in this range or with label matching the start of range
    targets = ProductionTarget.query.filter(
        db.or_(
            db.and_(ProductionTarget.month == month_start.month, ProductionTarget.year == month_start.year),
            db.and_(ProductionTarget.start_date >= month_start.date(), ProductionTarget.start_date <= month_end.date()),
            db.and_(ProductionTarget.end_date >= month_start.date(), ProductionTarget.end_date <= month_end.date())
        )
    ).all()
    
    data = []
    
    for target in targets:
        product = target.product
        
        # Target Units from MOs
        mo_target_units = db.session.query(func.sum(ManufacturingOrder.quantity_to_produce)).join(BOM).filter(
            BOM.product_id == target.sku_id,
            ManufacturingOrder.start_date >= month_start.date(),
            ManufacturingOrder.start_date <= month_end.date()
        ).scalar() or 0
        
        effective_target_units = (target.target_units or 0) + mo_target_units

        produced_qty = db.session.query(func.sum(ProductionLog.qty_produced)).filter(
            ProductionLog.sku_id == target.sku_id,
            ProductionLog.date >= month_start.date(),
            ProductionLog.date <= month_end.date()
        ).scalar() or 0
        
        rejected_qty = db.session.query(func.sum(ProductionLog.rejected_qty)).filter(
            ProductionLog.sku_id == target.sku_id,
            ProductionLog.date >= month_start.date(),
            ProductionLog.date <= month_end.date()
        ).scalar() or 0
        
        from app.models import SaleReturn, SaleReturnItem
        returned_qty = db.session.query(func.sum(SaleReturnItem.quantity)).join(SaleReturn).filter(
            SaleReturnItem.product_id == target.sku_id,
            SaleReturn.date >= month_start.date(),
            SaleReturn.date <= month_end.date()
        ).scalar() or 0
        
        net_produced = produced_qty - rejected_qty - returned_qty
        
        bom = BOM.query.filter_by(product_id=product.id, is_active=True).first()
        bom_cost = (bom.total_cost - bom.overhead_cost - bom.labor_cost) if bom else product.cost_price
        overhead_cost = target.overhead_cost_per_unit if target.overhead_cost_per_unit > 0 else (bom.overhead_cost + bom.labor_cost if bom else 0)
        
        # Calculate expected progress for status
        today = datetime.now().date()
        if today >= month_start.date() and today <= month_end.date():
            total_days_range = (month_end.date() - month_start.date()).days + 1
            elapsed_days_range = (today - month_start.date()).days + 1
            expected_progress_val = (elapsed_days_range / total_days_range) * 100
        elif today > month_end.date():
            expected_progress_val = 100
        else:
            expected_progress_val = 0

        completion_pct = (net_produced / effective_target_units * 100) if effective_target_units > 0 else 0
        
        if completion_pct >= 100:
            status = 'DONE'
        elif completion_pct >= expected_progress_val:
            status = 'ON TRACK'
        else:
            status = 'BEHIND'
        
        data.append({
            'SKU': product.sku,
            'Product Name': product.name,
            'Target Units': effective_target_units,
            'Produced Units': produced_qty,
            'Rejected Units': rejected_qty,
            'Returned Units': returned_qty,
            'Net Produced': net_produced,
            'Remaining': effective_target_units - net_produced,
            'Completion %': f"{completion_pct:.1f}%",
            'BOM Cost': bom_cost,
            'OH Cost (Labor+Overhead)': overhead_cost,
            'Item Cost': bom_cost,
            'Selling Price': product.finished_good_price if product.finished_good_price else product.unit_price,
            'Target Revenue': effective_target_units * (product.finished_good_price if product.finished_good_price else product.unit_price),
            'Est. Cost': effective_target_units * bom_cost,
            'Est. Profit': (effective_target_units * (product.finished_good_price if product.finished_good_price else product.unit_price)) - (effective_target_units * bom_cost),
            'Status': status
        })
    
    headers = ['SKU', 'Product Name', 'Target Units', 'Produced Units', 'Remaining', 
               'Completion %', 'BOM Cost', 'OH Cost (Labor+Overhead)', 'Item Cost', 
               'Selling Price', 'Target Revenue', 'Est. Cost', 'Est. Profit', 'Status']
    
    title = f"Production Target Report ({month_start.strftime('%d-%m-%Y')} to {month_end.strftime('%d-%m-%Y')})"
    
    if format == 'pdf':
        from app.models import Company
        company = Company.query.first()
        company_info = {
            'name': company.name if company else 'ERP Portal',
            'address': company.address if company else '',
            'phone': company.phone if company else '',
            'email': company.email if company else ''
        }
        output = generate_pdf(data, title, headers, company_info)
        return send_file(output, as_attachment=True, download_name=f"production_report_{month_start.strftime('%Y%m%d')}.pdf", mimetype='application/pdf')
    
    elif format == 'excel':
        output = generate_excel(data, "ProductionTarget")
        return send_file(output, as_attachment=True, download_name=f"production_report_{month_start.strftime('%Y%m%d')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    elif format == 'csv':
        output = generate_csv(data)
        return send_file(output, as_attachment=True, download_name=f"production_report_{month_start.strftime('%Y%m%d')}.csv", mimetype='text/csv')
    
    return redirect(url_for('production.index'))
