from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
from flask_login import login_required, current_user
from app import db
from app.models import MonthlyTarget, ManufacturingOrder, Sale, SaleItem, Product, BOM, Company
from datetime import datetime, timedelta
from sqlalchemy import func
from app.report_utils import generate_excel, generate_csv, generate_pdf

bp = Blueprint('targets', __name__)

@bp.route('/')
@login_required
def index():
    """List all monthly targets"""
    targets = MonthlyTarget.query.order_by(MonthlyTarget.year.desc(), MonthlyTarget.month.desc()).all()
    
    # Current month/year for defaults
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    return render_template('targets/list.html', 
                         targets=targets, 
                         current_month=current_month, 
                         current_year=current_year)

@bp.route('/set', methods=['GET', 'POST'])
@login_required
def set_target():
    """Set or update a monthly target"""
    if not (current_user.is_admin or current_user.can_view_settings):
        flash('You do not have permission to set targets.', 'danger')
        return redirect(url_for('targets.index'))
        
    target_id = request.args.get('id')
    target = None
    if target_id:
        target = MonthlyTarget.query.get_or_404(target_id)
        
    if request.method == 'POST':
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        prod_qty = float(request.form.get('target_production_qty', 0))
        prod_cost = float(request.form.get('target_production_cost', 0))
        sales_rev = float(request.form.get('target_sales_revenue', 0))
        sales_qty = float(request.form.get('target_sales_qty', 0))
        
        if not target:
            # Check if target already exists for this month/year
            existing = MonthlyTarget.query.filter_by(month=month, year=year).first()
            if existing:
                target = existing
            else:
                target = MonthlyTarget(month=month, year=year)
                db.session.add(target)
        
        target.target_production_qty = prod_qty
        target.target_production_cost = prod_cost
        target.target_sales_revenue = sales_rev
        target.target_sales_qty = sales_qty
        
        try:
            db.session.commit()
            flash(f'Target for {month}/{year} updated successfully.', 'success')
            return redirect(url_for('targets.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving target: {str(e)}', 'danger')
            
    return render_template('targets/form.html', target=target, now=datetime.now())


@bp.route('/report/<int:id>')
@login_required
def report(id):
    """Detailed Target vs Actual report with filtering"""
    target = MonthlyTarget.query.get_or_404(id)
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Calculate default start and end dates for the month if not provided
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        start_date = datetime(target.year, target.month, 1)
        
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        if target.month == 12:
            end_date = datetime(target.year + 1, 1, 1)
        else:
            end_date = datetime(target.year, target.month + 1, 1)
    
    # Logic for actuals
    mo_actuals = db.session.query(
        func.sum(ManufacturingOrder.quantity_to_produce).label('qty'),
        func.sum(ManufacturingOrder.total_cost).label('cost')
    ).filter(
        ManufacturingOrder.status == 'Completed',
        ManufacturingOrder.end_date >= start_date.date(),
        ManufacturingOrder.end_date < end_date.date()
    ).first()
    
    actual_prod_qty = mo_actuals.qty or 0
    actual_prod_cost = mo_actuals.cost or 0
    
    sales_actuals = db.session.query(
        func.sum(Sale.total).label('revenue')
    ).filter(
        Sale.date >= start_date,
        Sale.date < end_date
    ).first()
    
    actual_sales_revenue = sales_actuals.revenue or 0
    
    sales_qty_actual = db.session.query(
        func.sum(SaleItem.quantity).label('qty')
    ).join(Sale).filter(
        Sale.date >= start_date,
        Sale.date < end_date
    ).first()
    
    actual_sales_qty = sales_qty_actual.qty or 0
    
    def calc_pct(actual, target_val):
        if not target_val or target_val == 0:
            return 100 if actual > 0 else 0
        return min(round((actual / target_val) * 100, 1), 200)

    performance = {
        'prod_qty': {
            'actual': actual_prod_qty,
            'target': target.target_production_qty,
            'pct': calc_pct(actual_prod_qty, target.target_production_qty),
            'status': 'success' if actual_prod_qty >= target.target_production_qty else 'warning'
        },
        'prod_cost': {
            'actual': actual_prod_cost,
            'target': target.target_production_cost,
            'pct': calc_pct(actual_prod_cost, target.target_production_cost),
            'status': 'success' if actual_prod_cost <= target.target_production_cost else 'danger'
        },
        'sales_revenue': {
            'actual': actual_sales_revenue,
            'target': target.target_sales_revenue,
            'pct': calc_pct(actual_sales_revenue, target.target_sales_revenue),
            'status': 'success' if actual_sales_revenue >= target.target_sales_revenue else 'warning'
        },
        'sales_qty': {
            'actual': actual_sales_qty,
            'target': target.target_sales_qty,
            'pct': calc_pct(actual_sales_qty, target.target_sales_qty),
            'status': 'success' if actual_sales_qty >= target.target_sales_qty else 'warning'
        }
    }
    
    return render_template('targets/report.html', 
                         target=target, 
                         performance=performance,
                         start_date=start_date_str,
                         end_date=end_date_str)

@bp.route('/report/<int:id>/download/<string:format>')
@login_required
def download_report(id, format):
    """Download Target vs Actual report"""
    target = MonthlyTarget.query.get_or_404(id)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Recalculate or reuse performance logic (for simplicity here we just recalculate)
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        start_date = datetime(target.year, target.month, 1)
        
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        if target.month == 12:
            end_date = datetime(target.year + 1, 1, 1)
        else:
            end_date = datetime(target.year, target.month + 1, 1)

    # Reuse aggregation logic
    mo_actuals = db.session.query(
        func.sum(ManufacturingOrder.quantity_to_produce).label('qty'),
        func.sum(ManufacturingOrder.total_cost).label('cost')
    ).filter(ManufacturingOrder.status == 'Completed', ManufacturingOrder.end_date >= start_date.date(), ManufacturingOrder.end_date < end_date.date()).first()
    
    sales_actuals = db.session.query(func.sum(Sale.total).label('revenue')).filter(Sale.date >= start_date, Sale.date < end_date).first()
    sales_qty_actual = db.session.query(func.sum(SaleItem.quantity).label('qty')).join(Sale).filter(Sale.date >= start_date, Sale.date < end_date).first()

    actual_prod_qty = mo_actuals.qty or 0
    actual_prod_cost = mo_actuals.cost or 0
    actual_sales_rev = sales_actuals.revenue or 0
    actual_sales_qty = sales_qty_actual.qty or 0

    data = [
        {'Metric': 'Production Quantity (Units)', 'Target': target.target_production_qty, 'Actual': actual_prod_qty, 'Achievement %': f"{(actual_prod_qty/target.target_production_qty*100) if target.target_production_qty else 0:.1f}%"},
        {'Metric': 'Production Cost (Rs.)', 'Target': target.target_production_cost, 'Actual': actual_prod_cost, 'Achievement %': f"{(actual_prod_cost/target.target_production_cost*100) if target.target_production_cost else 0:.1f}%"},
        {'Metric': 'Sales Revenue (Rs.)', 'Target': target.target_sales_revenue, 'Actual': actual_sales_rev, 'Achievement %': f"{(actual_sales_rev/target.target_sales_revenue*100) if target.target_sales_revenue else 0:.1f}%"},
        {'Metric': 'Sales Quantity (Units)', 'Target': target.target_sales_qty, 'Actual': actual_sales_qty, 'Achievement %': f"{(actual_sales_qty/target.target_sales_qty*100) if target.target_sales_qty else 0:.1f}%"}
    ]
    
    headers = ['Metric', 'Target', 'Actual', 'Achievement %']
    title = f"Target Performance Report - {target.month}/{target.year}"
    if start_date_str and end_date_str:
        title += f" ({start_date_str} to {end_date_str})"

    if format == 'pdf':
        company = Company.query.first()
        company_info = {
            'name': company.name if company else 'ERP Portal',
            'address': company.address if company else '',
            'phone': company.phone if company else '',
            'email': company.email if company else ''
        }
        output = generate_pdf(data, title, headers, company_info)
        return send_file(output, as_attachment=True, download_name=f"target_report_{target.month}_{target.year}.pdf", mimetype='application/pdf')
    
    elif format == 'excel':
        output = generate_excel(data, "TargetPerformance")
        return send_file(output, as_attachment=True, download_name=f"target_report_{target.month}_{target.year}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    elif format == 'csv':
        output = generate_csv(data)
        return send_file(output, as_attachment=True, download_name=f"target_report_{target.month}_{target.year}.csv", mimetype='text/csv')
    
    return redirect(url_for('targets.report', id=id))

@bp.route('/delete/<int:id>')
@login_required
def delete_target(id):
    if not current_user.is_admin:
        flash('Only admins can delete targets.', 'danger')
        return redirect(url_for('targets.index'))
        
    target = MonthlyTarget.query.get_or_404(id)
    db.session.delete(target)
    db.session.commit()
    flash('Target deleted.', 'success')
    return redirect(url_for('targets.index'))
