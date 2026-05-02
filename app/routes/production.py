from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
from app.utils import permission_required
from flask_login import login_required, current_user
from app import db
from app.models import ProductionTarget, ProductionLog, Product, BOM, SaleItem, Sale
from datetime import datetime, timedelta
from calendar import monthrange
from sqlalchemy import func
from app.report_utils import generate_excel, generate_csv, generate_pdf

bp = Blueprint('production', __name__)

@bp.route('/')
@login_required
def index():
    """Production Target Dashboard - Main view"""
    selected_month = request.args.get('month', type=int, default=datetime.now().month)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)
    selected_product_id = request.args.get('product_id', type=int, default=None)
    
    _, days_in_month = monthrange(selected_year, selected_month)
    month_start = datetime(selected_year, selected_month, 1)
    month_end = datetime(selected_year, selected_month, days_in_month, 23, 59, 59)
    
    # Filter targets occurring in this month or with this month/year label
    query = ProductionTarget.query.filter(
        db.or_(
            db.and_(ProductionTarget.month == selected_month, ProductionTarget.year == selected_year),
            db.and_(ProductionTarget.start_date >= month_start.date(), ProductionTarget.start_date <= month_end.date())
        )
    )
    if selected_product_id:
        query = query.filter_by(sku_id=selected_product_id)
    targets = query.all()
    
    products = Product.query.filter_by(is_active=True, is_manufactured=True).order_by(Product.name).all()
    
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
    
    today = datetime.now().date()
    current_day = today.day if today.year == selected_year and today.month == selected_month else days_in_month
    expected_progress = (current_day / days_in_month) * 100
    
    for target in targets:
        product = target.product
        
        # Filter logs based on target range if available, else month/year
        log_start = target.start_date if target.start_date else month_start.date()
        log_end = target.end_date if target.end_date else month_end.date()

        # Determine Produced Qty: Stateful Value vs dynamic Logs sum
        if target.produced_qty is not None:
            # Use stateful value (manual entry + automated additions)
            produced_qty = target.produced_qty
            log_produced = 0 # Not used in stateful mode
        else:
            # Fallback: Dynamic logs sum (only if never manually adjusted)
            log_produced = db.session.query(func.sum(ProductionLog.qty_produced)).filter(
                ProductionLog.sku_id == target.sku_id,
                ProductionLog.date >= log_start,
                ProductionLog.date <= log_end
            ).scalar() or 0
            produced_qty = log_produced
            
        # Calculate rejected qty for the range
        rejected_qty = db.session.query(func.sum(ProductionLog.rejected_qty)).filter(
            ProductionLog.sku_id == target.sku_id,
            ProductionLog.date >= log_start,
            ProductionLog.date <= log_end
        ).scalar() or 0
            
        net_produced = produced_qty - rejected_qty  # Net = Produced - Rejected
        total_produced = produced_qty + rejected_qty  # Total including rejected
        
        # Calculate Returns for this product in this range
        from app.models import SaleReturn, SaleReturnItem
        returned_qty = db.session.query(func.sum(SaleReturnItem.quantity)).join(SaleReturn).filter(
            SaleReturnItem.product_id == target.sku_id,
            SaleReturn.date >= log_start,
            SaleReturn.date <= log_end
        ).scalar() or 0
        
        # Truly net produced = Produced - Rejected - Returned
        final_net_produced = net_produced - returned_qty
        
        selling_price = product.finished_good_price if product.finished_good_price else product.unit_price
        bom = BOM.query.filter_by(product_id=product.id, is_active=True).first()
        
        # Use current product cost (which is updated after complete production)
        # instead of relying solely on BOM estimate if production has happened
        item_unit_cost = product.cost_price if product.cost_price > 0 else (bom.total_cost if bom else 0)
        
        # Breakdown still shows BOM reference if needed, but calculations use item_unit_cost
        if bom:
            reference_bom_cost = bom.total_cost - bom.overhead_cost - bom.labor_cost
            reference_overhead = bom.overhead_cost + bom.labor_cost
        else:
            reference_bom_cost = product.cost_price
            reference_overhead = 0
            
        if target.overhead_cost_per_unit > 0:
            # If target has specific overhead, reflect it in the display
            reference_overhead = target.overhead_cost_per_unit
            
        remaining = target.target_units - total_produced
        completion_pct = (final_net_produced / target.target_units * 100) if target.target_units > 0 else 0
        
        if completion_pct >= 100:
            status = 'DONE'
            status_class = 'primary'
        elif completion_pct >= expected_progress:
            status = 'ON TRACK'
            status_class = 'success'
        else:
            status = 'BEHIND'
            status_class = 'danger'
        
        target_revenue = target.target_units * selling_price
        estimated_cost = target.target_units * item_unit_cost
        estimated_profit = target_revenue - estimated_cost
        
        # Actual (based on net produced qty after rejecting and returns)
        actual_revenue = final_net_produced * selling_price
        actual_cost = final_net_produced * item_unit_cost
        actual_profit = actual_revenue - actual_cost
        
        results.append({
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
            'actual_profit': actual_profit
        })
        
        total_target += target.target_units
        total_produced_all += net_produced # Use Net Produced for the summary box
        total_remaining += remaining
        total_revenue += target_revenue
        total_cost += estimated_cost
        total_profit += estimated_profit
        actual_revenue_all += actual_revenue
        actual_cost_all += actual_cost
        actual_profit_all += actual_profit
    
    overall_completion = (total_produced_all / total_target * 100) if total_target > 0 else 0
    
    return render_template('production/index.html',
                         results=results,
                         products=products,
                         selected_month=selected_month,
                         selected_year=selected_year,
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
                         days_in_month=days_in_month,
                         current_day=current_day,
                         expected_progress=round(expected_progress, 1))


@bp.route('/set-target', methods=['GET', 'POST'])
@login_required
def set_target():
    """Set monthly production targets for products"""
    target_id = request.args.get('id', type=int)
    target = None
    if target_id:
        target = ProductionTarget.query.get_or_404(target_id)
    
    products = Product.query.filter_by(is_active=True, is_manufactured=True).order_by(Product.name).all()
    
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
        
        month = start_date.month
        year = start_date.year
        
        sku_ids = request.form.getlist('sku_ids')
        target_units = float(request.form.get('target_units', 0))
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
                target.month = month
                target.year = year
                target.target_units = target_units
                target.overhead_cost_per_unit = overhead_cost_per_unit
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
                    
                    curr_target.target_units = target_units
                    curr_target.overhead_cost_per_unit = overhead_cost_per_unit
            
            db.session.commit()
            flash('Targets saved successfully.', 'success')
            return redirect(url_for('production.index', month=month, year=year))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('production/set_target.html',
                         target=target,
                         products=products,
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
        
        db.session.delete(target)
        db.session.commit()
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
    selected_month = request.args.get('month', type=int, default=datetime.now().month)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)
    
    targets = ProductionTarget.query.filter_by(month=selected_month, year=selected_year).all()
    
    _, days_in_month = monthrange(selected_year, selected_month)
    month_start = datetime(selected_year, selected_month, 1)
    month_end = datetime(selected_year, selected_month, days_in_month, 23, 59, 59)
    
    data = []
    
    for target in targets:
        product = target.product
        
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
        
        completion_pct = (net_produced / target.target_units * 100) if target.target_units > 0 else 0
        
        if completion_pct >= 100:
            status = 'DONE'
        elif completion_pct >= ((datetime.now().day / monthrange(selected_year, selected_month)[1]) * 100):
            status = 'ON TRACK'
        else:
            status = 'BEHIND'
        
        data.append({
            'SKU': product.sku,
            'Product Name': product.name,
            'Target Units': target.target_units,
            'Produced Units': produced_qty,
            'Rejected Units': rejected_qty,
            'Returned Units': returned_qty,
            'Net Produced': net_produced,
            'Remaining': target.target_units - net_produced,
            'Completion %': f"{completion_pct:.1f}%",
            'BOM Cost': bom_cost,
            'OH Cost (Labor+Overhead)': overhead_cost,
            'Item Cost': bom_cost,
            'Selling Price': product.finished_good_price if product.finished_good_price else product.unit_price,
            'Target Revenue': target.target_units * (product.finished_good_price if product.finished_good_price else product.unit_price),
            'Est. Cost': target.target_units * bom_cost,
            'Est. Profit': (target.target_units * (product.finished_good_price if product.finished_good_price else product.unit_price)) - (target.target_units * bom_cost),
            'Status': status
        })
    
    headers = ['SKU', 'Product Name', 'Target Units', 'Produced Units', 'Remaining', 
               'Completion %', 'BOM Cost', 'OH Cost (Labor+Overhead)', 'Item Cost', 
               'Selling Price', 'Target Revenue', 'Est. Cost', 'Est. Profit', 'Status']
    
    title = f"Production Target Report - {selected_month}/{selected_year}"
    
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
        return send_file(output, as_attachment=True, download_name=f"production_report_{selected_month}_{selected_year}.pdf", mimetype='application/pdf')
    
    elif format == 'excel':
        output = generate_excel(data, "ProductionTarget")
        return send_file(output, as_attachment=True, download_name=f"production_report_{selected_month}_{selected_year}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    elif format == 'csv':
        output = generate_csv(data)
        return send_file(output, as_attachment=True, download_name=f"production_report_{selected_month}_{selected_year}.csv", mimetype='text/csv')
    
    return redirect(url_for('production.index'))
