from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
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
    
    query = ProductionTarget.query.filter_by(month=selected_month, year=selected_year)
    if selected_product_id:
        query = query.filter_by(sku_id=selected_product_id)
    targets = query.all()
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
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
        
        net_produced = produced_qty - rejected_qty  # Net = Produced - Rejected
        total_produced = produced_qty + rejected_qty  # Total including rejected
        
        bom_cost = 0
        overhead_cost = 0
        selling_price = product.finished_good_price if product.finished_good_price else product.unit_price
        
        bom = BOM.query.filter_by(product_id=product.id, is_active=True).first()
        if bom:
            bom_cost = bom.total_cost - bom.overhead_cost - bom.labor_cost  # Component cost only
            overhead_cost = bom.overhead_cost + bom.labor_cost  # OH = overhead + labor
        else:
            bom_cost = product.cost_price
        
        if target.overhead_cost_per_unit > 0:
            overhead_cost = target.overhead_cost_per_unit
        
        remaining = target.target_units - total_produced
        completion_pct = (net_produced / target.target_units * 100) if target.target_units > 0 else 0
        
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
        estimated_cost = target.target_units * bom_cost
        estimated_profit = target_revenue - estimated_cost
        
        # Actual (based on net produced qty after rejecting)
        actual_revenue = net_produced * selling_price
        actual_cost = net_produced * bom_cost
        actual_profit = actual_revenue - actual_cost
        
        results.append({
            'target': target,
            'product': product,
            'produced_qty': produced_qty,
            'net_produced': net_produced,
            'rejected_qty': rejected_qty,
            'total_produced': total_produced,
            'remaining': remaining,
            'completion_pct': round(completion_pct, 1),
            'expected_progress': round(expected_progress, 1),
            'status': status,
            'status_class': status_class,
            'bom_cost': bom_cost,
            'overhead_cost': overhead_cost,
            'item_cost': bom_cost,
            'selling_price': selling_price,
            'target_revenue': target_revenue,
            'estimated_cost': estimated_cost,
            'estimated_profit': estimated_profit,
            'actual_revenue': actual_revenue,
            'actual_cost': actual_cost,
            'actual_profit': actual_profit
        })
        
        total_target += target.target_units
        total_produced_all += total_produced
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
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    selected_month = request.args.get('month', type=int, default=datetime.now().month)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)
    
    if request.method == 'POST':
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        sku_id = int(request.form.get('sku_id'))
        target_units = float(request.form.get('target_units', 0))
        overhead_cost_per_unit = float(request.form.get('overhead_cost_per_unit', 0))
        
        if not target:
            existing = ProductionTarget.query.filter_by(month=month, year=year, sku_id=sku_id).first()
            if existing:
                target = existing
            else:
                target = ProductionTarget(month=month, year=year, sku_id=sku_id)
                db.session.add(target)
        
        target.target_units = target_units
        target.overhead_cost_per_unit = overhead_cost_per_unit
        
        try:
            db.session.commit()
            flash('Target saved successfully.', 'success')
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
def delete_target(id):
    """Delete a production target"""
    target = ProductionTarget.query.get_or_404(id)
    month = target.month
    year = target.year
    
    db.session.delete(target)
    db.session.commit()
    flash('Target deleted.', 'success')
    return redirect(url_for('production.index', month=month, year=year))


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
            flash('Production log saved.', 'success')
            return redirect(url_for('production.logs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('production/log_form.html',
                         log=log,
                         products=products)


@bp.route('/log/<int:id>/delete')
@login_required
def delete_log(id):
    """Delete a production log"""
    log = ProductionLog.query.get_or_404(id)
    db.session.delete(log)
    db.session.commit()
    flash('Log deleted.', 'success')
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
def api_update_target():
    """API: Update production target inline"""
    data = request.get_json()
    target_id = data.get('target_id')
    field = data.get('field')
    value = data.get('value')
    
    target = ProductionTarget.query.get_or_404(target_id)
    
    if field == 'target_units':
        target.target_units = float(value)
    elif field == 'overhead_cost_per_unit':
        target.overhead_cost_per_unit = float(value)
    else:
        return jsonify({'success': False, 'message': 'Invalid field'}), 400
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Updated successfully'})
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
        
        bom = BOM.query.filter_by(product_id=product.id, is_active=True).first()
        bom_cost = (bom.total_cost - bom.overhead_cost - bom.labor_cost) if bom else product.cost_price
        overhead_cost = target.overhead_cost_per_unit if target.overhead_cost_per_unit > 0 else (bom.overhead_cost + bom.labor_cost if bom else 0)
        
        remaining = target.target_units - produced_qty
        completion_pct = (produced_qty / target.target_units * 100) if target.target_units > 0 else 0
        
        if completion_pct >= 100:
            status = 'DONE'
        elif completion_pct >= ((datetime.now().day / days_in_month) * 100):
            status = 'ON TRACK'
        else:
            status = 'BEHIND'
        
        data.append({
            'SKU': product.sku,
            'Product Name': product.name,
            'Target Units': target.target_units,
            'Produced Units': produced_qty,
            'Remaining': remaining,
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
