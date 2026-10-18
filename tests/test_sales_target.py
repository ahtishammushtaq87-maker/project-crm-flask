"""Tests for the Sales Target module.

Runs against a throw-away SQLite file, never the real instance/database.db:

    venv\\Scripts\\python.exe -m unittest tests.test_sales_target -v
"""
import os
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta

_TMP = tempfile.mkdtemp(prefix='sales_target_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import (User, Salesman, Customer, Sale, SaleReturn, Payment, Product,  # noqa: E402
                        SaleItem, SaleReturnItem)
from app.sales_target import calculations as calc  # noqa: E402
from app.sales_target import services as svc  # noqa: E402
from app.sales_target import plans  # noqa: E402
from app.sales_target.models import (SalesTarget, SalesTargetMember, SalesTargetPlan,  # noqa: E402
                                     SalesTargetProduct)

PERIOD_START = date(2026, 9, 1)
PERIOD_END = date(2026, 9, 30)


def dt(d, h=10, m=0):
    return datetime(d.year, d.month, d.day, h, m)


class SalesTargetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self._cleanup)  # runs even if setUp fails, so no lock is left behind
        self._wipe()
        self._seed()
        self.client = self.app.test_client()

    def _cleanup(self):
        db.session.rollback()
        db.session.remove()
        self.ctx.pop()

    @staticmethod
    def _wipe():
        """Empty every table of the throw-away DB. Other CRM code (activity
        log etc.) writes rows that reference users, so FKs are off while wiping;
        the PRAGMA must run before the transaction starts to take effect."""
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            tables = [r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))]
            for name in tables:
                conn.exec_driver_sql(f'DELETE FROM "{name}"')
            conn.commit()
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')

    # ── fixtures ───────────────────────────────────────────────────────
    def _user(self, username, role='user', **perms):
        u = User(username=username, email=f'{username}@example.com', role=role, **perms)
        u.set_password('pw')
        db.session.add(u)
        db.session.flush()
        return u

    def _sale(self, number, total, when, salesman=None, approved=True, rejected=False, draft=False,
              reason=None):
        s = Sale(invoice_number=number, customer_id=self.customer.id, date=when, subtotal=total, total=total,
                 salesman_id=salesman.id if salesman else None, is_approved=approved, is_rejected=rejected,
                 is_draft=draft, rejection_reason=reason, status='unpaid')
        db.session.add(s)
        db.session.flush()
        return s

    def _seed(self):
        self.admin = self._user('admin', role='admin')
        self.viewer = self._user('viewer', can_view_targets=True, can_view_sales=True)
        self.no_sales = self._user('nosales', can_view_targets=True, can_view_sales=False)
        self.manager = self._user('manager', can_view_targets=True, can_view_sales=True,
                                  can_add_targets=True, can_edit_targets=True, can_delete_targets=True)
        self.rep_user = self._user('rep', can_view_targets=True, can_view_sales=True,
                                   can_add_targets=True, can_edit_targets=True, can_delete_targets=True)
        self.customer = Customer(name='Acme Traders')
        db.session.add(self.customer)
        self.a = Salesman(name='Ali', is_active=True, user_id=self.rep_user.id)
        self.b = Salesman(name='Bilal', is_active=True)
        db.session.add_all([self.a, self.b])
        db.session.flush()

        mid = date(2026, 9, 15)
        # Counted for A: 1000 + 800 (the latter after an approved return of 200)
        self.s1 = self._sale('T-1', 1000, dt(mid), self.a)
        self.s_ret = self._sale('T-2', 800, dt(mid), self.a)
        ret = SaleReturn(return_number='R-1', sale_id=self.s_ret.id, customer_id=self.customer.id,
                         date=dt(date(2026, 10, 5)), subtotal=200, total=200,
                         is_approved=True, status='approved')
        db.session.add(ret)
        # Not counted for A
        self._sale('T-3', 500, dt(mid), self.a, approved=False)                  # pending
        self._sale('T-4', 300, dt(mid), self.a, approved=False, draft=True)      # draft
        self._sale('T-5', 200, dt(mid), self.a, approved=False, rejected=True,
                   reason='Cancelled by Admin')                                  # cancelled
        self._sale('T-6', 700, dt(date(2026, 10, 1), 0, 0), self.a)               # next day after period
        self._sale('T-7', 900, dt(date(2026, 8, 31), 23, 59), self.a)             # day before period
        # Boundary: last day of period, late evening -> counted
        self.s_edge = self._sale('T-8', 100, dt(PERIOD_END, 23, 30), self.a)
        # B and unassigned
        self._sale('T-9', 400, dt(mid), self.b)
        self._sale('T-10', 50, dt(mid), None)
        # Finished items X, Y and a non-finished part Z, with invoice lines
        self.x = Product(name='Pump X', sku='PX', unit_price=300, cost_price=100, is_manufactured=True, is_active=True)
        self.y = Product(name='Pump Y', sku='PY', unit_price=400, cost_price=100, is_manufactured=True, is_active=True)
        self.z = Product(name='Bolt Z', sku='BZ', unit_price=10, cost_price=5, is_manufactured=False, is_active=True)
        db.session.add_all([self.x, self.y, self.z])
        db.session.flush()

        def line(sale, product, qty, price, discount=0):
            db.session.add(SaleItem(sale_id=sale.id, product_id=product.id, quantity=qty, unit_price=price,
                                    discount=discount, total=qty * price))
        line(self.s1, self.x, 2, 300, discount=50)     # X net 550
        line(self.s1, self.y, 1, 400)                  # Y net 400
        line(self.s_ret, self.x, 4, 200)               # X net 800, 200 of it returned
        db.session.flush()
        db.session.add(SaleReturnItem(return_id=ret.id, product_id=self.x.id, quantity=1, unit_price=200, total=200))
        pending = Sale.query.filter_by(invoice_number='T-3').one()
        line(pending, self.x, 1, 500)                  # pending invoice: not counted
        line(Sale.query.filter_by(invoice_number='T-9').one(), self.x, 1, 400)  # salesman B
        # Payments must never inflate sales
        for i, amt in enumerate((600, 400)):
            db.session.add(Payment(payment_number=f'P-{i}', amount=amt, invoice_id=self.s1.id,
                                   is_approved=True, date=dt(date(2026, 9, 20))))
        db.session.commit()

    def _target(self, ttype='individual', amount=2000, salesman=None, members=(), status='active',
                start=PERIOD_START, end=PERIOD_END, name='Sept', products=()):
        t = SalesTarget(name=name, target_type=ttype, target_amount=amount, start_date=start, end_date=end,
                        salesman_id=salesman.id if salesman else None, status=status, created_by=self.admin.id)
        for m in members:
            t.members.append(SalesTargetMember(salesman_id=m.id))
        for p in products:
            t.products.append(SalesTargetProduct(product_id=p.id))
        db.session.add(t)
        db.session.commit()
        return t

    def login(self, user):
        from flask import g
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        # The test keeps an app context pushed, which requests reuse, so drop
        # Flask-Login's per-context cache of the previous user.
        g.pop('_login_user', None)

    def form_tokens(self, url):
        html = self.client.get(url).get_data(as_text=True)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        nonce = re.search(r'name="form_nonce" value="([^"]+)"', html).group(1)
        return csrf, nonce

    def valid_form(self, **over):
        data = {'name': 'September Target', 'target_type': 'individual', 'target_amount': '2000',
                'start_date': PERIOD_START.isoformat(), 'end_date': PERIOD_END.isoformat(),
                'salesman_id': str(self.a.id), 'status': 'active', 'description': 'Push Q3'}
        data.update(over)
        return data

    # ── calculations ───────────────────────────────────────────────────
    def test_individual_target_uses_invoice_salesman_and_eligibility(self):
        p = calc.performance(self._target(salesman=self.a))
        # 1000 + 800 (return already netted in Sale.total) + 100 (late on last day)
        self.assertEqual(p['actual'], calc.to_money(1900))
        self.assertEqual(p['invoice_count'], 3)
        self.assertEqual(p['remaining'], calc.to_money(100))
        self.assertEqual(p['exceeded'], calc.to_money(0))
        self.assertEqual(str(p['achievement']), '95.0')

    def test_company_target_counts_all_eligible_including_unassigned(self):
        p = calc.performance(self._target(ttype='company', amount=2000))
        self.assertEqual(p['actual'], calc.to_money(1900 + 400 + 50))
        self.assertEqual(p['exceeded'], calc.to_money(350))
        self.assertEqual(p['remaining'], calc.to_money(0))

    def test_team_target_counts_each_invoice_once(self):
        p = calc.performance(self._target(ttype='team', members=(self.a, self.b), amount=5000))
        self.assertEqual(p['actual'], calc.to_money(2300))
        self.assertEqual(p['invoice_count'], 4)

    def test_returns_are_not_subtracted_twice(self):
        p = calc.performance(self._target(salesman=self.a))
        _, rows = calc.contributing_invoices(self._target(salesman=self.a, name='dup-scope', status='draft'))
        ret_row = next(r for r in rows if r['sale'].id == self.s_ret.id)
        self.assertEqual(ret_row['amount'], calc.to_money(800))
        self.assertEqual(ret_row['returns'], calc.to_money(200))
        self.assertEqual(p['actual'], calc.to_money(1900))

    def test_dates_outside_period_are_excluded(self):
        p = calc.performance(self._target(salesman=self.a, start=date(2026, 10, 1), end=date(2026, 10, 31)))
        self.assertEqual(p['actual'], calc.to_money(700))  # only T-6, midnight Oct 1

    def test_detail_rows_add_up_to_actual(self):
        t = self._target(ttype='company')
        p = calc.performance(t)
        pagination, rows = calc.contributing_invoices(t, per_page=100)
        self.assertEqual(sum(r['amount'] for r in rows), p['actual'])
        self.assertEqual(pagination.total, p['invoice_count'])

    def test_missing_salesman_is_reported_not_zero(self):
        t = self._target(ttype='individual', salesman=None)
        p = calc.performance(t)
        self.assertFalse(p['available'])
        self.assertIsNone(p['actual'])
        self.assertIn('no longer exists', p['error'])

    def test_exclusions_explain_uncounted_invoices(self):
        ex = calc.exclusions(self._target(salesman=self.a))
        self.assertEqual(ex['pending']['amount'], calc.to_money(500))
        self.assertEqual(ex['draft']['amount'], calc.to_money(300))
        self.assertEqual(ex['rejected']['amount'], calc.to_money(200))

    def test_summary_uses_one_type_and_counted_statuses(self):
        perfs = svc.compute_all([
            self._target(ttype='company', amount=3000, name='c'),
            self._target(salesman=self.a, amount=1000, name='i'),
            self._target(salesman=self.b, amount=1000, status='draft', name='d'),
        ])
        s = svc.summarize(perfs, 'company')
        self.assertEqual(s['count'], 1)
        self.assertEqual(s['total_target'], calc.to_money(3000))
        self.assertEqual(s['actual'], calc.to_money(2350))
        s_ind = svc.summarize(perfs, 'individual')
        self.assertEqual(s_ind['count'], 1)  # draft excluded
        self.assertEqual(s_ind['actual'], calc.to_money(1900))

    def test_zero_target_amount_is_division_safe(self):
        self.assertIsNone(calc.achievement_pct(calc.to_money(10), calc.to_money(0)))

    def test_completed_not_allowed_while_period_running(self):
        from werkzeug.datastructures import MultiDict
        form = MultiDict(self.valid_form(status='completed', end_date=(date.today() + timedelta(days=3)).isoformat(),
                                         start_date=date.today().isoformat()))
        _, errors = svc.validate_target_form(form)
        self.assertIn('status', errors)

    # ── finished-item targets ──────────────────────────────────────────
    def test_item_target_counts_only_chosen_item_lines(self):
        p = calc.performance(self._target(salesman=self.a, products=(self.x,), amount=1000))
        # s1: 600 - 50 line discount = 550; s_ret: 800 - 200 returned = 600; pending T-3 excluded
        self.assertEqual(p['actual'], calc.to_money(1150))
        self.assertEqual(p['invoice_count'], 2)

    def test_item_target_team_and_company(self):
        team = calc.performance(self._target(ttype='team', members=(self.a, self.b), products=(self.x,)))
        self.assertEqual(team['actual'], calc.to_money(1550))
        co = calc.performance(self._target(ttype='company', products=(self.x, self.y), name='co'))
        self.assertEqual(co['actual'], calc.to_money(1950))
        self.assertEqual(co['invoice_count'], 3)  # an invoice with both items still counts once

    def test_item_target_detail_rows_add_up(self):
        t = self._target(ttype='company', products=(self.x, self.y))
        pagination, rows = calc.contributing_invoices(t, per_page=100)
        self.assertEqual(sum(r['amount'] for r in rows), calc.performance(t)['actual'])
        ret_row = next(r for r in rows if r['sale'].id == self.s_ret.id)
        self.assertEqual((ret_row['amount'], ret_row['returns'], ret_row['qty']),
                         (calc.to_money(600), calc.to_money(200), 4))
        self.assertEqual(calc.exclusions(t)['pending']['amount'], calc.to_money(500))

    def test_create_item_target_via_form(self):
        self.login(self.admin)
        html = self.client.get('/sales-target/create').get_data(as_text=True)
        self.assertNotIn('name="product_ids"', html)  # new targets count every item
        self.assertNotIn('Bolt Z', html)
        csrf, nonce = self.form_tokens('/sales-target/create')
        r = self.client.post('/sales-target/create', data=self.valid_form(
            csrf_token=csrf, form_nonce=nonce, product_ids=[str(self.x.id), str(self.y.id)]))
        self.assertEqual(r.status_code, 302)
        t = SalesTarget.query.one()
        self.assertEqual(t.product_ids, sorted([self.x.id, self.y.id]))
        # An item-limited target keeps its picker on edit, so it never silently widens.
        edit_html = self.client.get(f'/sales-target/{t.id}/edit').get_data(as_text=True)
        self.assertIn('Pump X (PX)', edit_html)
        self.assertNotIn('Bolt Z', edit_html)  # only finished items are offered
        detail = self.client.get(f'/sales-target/{t.id}').get_data(as_text=True)
        self.assertIn('Pump X', detail)
        self.assertIn('PKR 1,550.00', detail)  # A: X 550 + Y 400 + X 600

        # Same scope + period but different items is not a duplicate
        csrf, nonce = self.form_tokens('/sales-target/create')
        r = self.client.post('/sales-target/create', data=self.valid_form(
            csrf_token=csrf, form_nonce=nonce, product_ids=[str(self.x.id)]))
        self.assertEqual(r.status_code, 302)

        # Edit with no items selected -> whole-invoice target again
        csrf, nonce = self.form_tokens(f'/sales-target/{t.id}/edit')
        self.client.post(f'/sales-target/{t.id}/edit',
                         data=self.valid_form(csrf_token=csrf, form_nonce=nonce, name='No items'))
        db.session.expire_all()
        self.assertEqual(db.session.get(SalesTarget, t.id).product_ids, [])

    # ── cost, selling price, profit ────────────────────────────────────
    def test_economics_of_whole_invoice_target(self):
        e = calc.economics(self._target(salesman=self.a))
        # X: 550 + (800 - 200 returned) = 1150 over 5 units; Y: 400 over 1. Cost 100 each.
        self.assertEqual((e['selling'], e['cost'], e['profit']),
                         (calc.to_money(1550), calc.to_money(600), calc.to_money(950)))
        self.assertEqual(str(e['margin']), '61.3')
        x, y = e['by_item']
        self.assertEqual((x['name'], x['qty'], x['returned_qty'], x['cost'], x['unit_price']),
                         ('Pump X', 5.0, 1.0, calc.to_money(500), calc.to_money(230)))
        self.assertEqual((y['profit'], str(y['margin']), str(y['share'])), (calc.to_money(300), '75.0', '25.8'))
        # Actual Sales (1900) = item selling price + invoice-level charges.
        self.assertEqual(e['invoice_charges'], calc.to_money(350))
        self.assertEqual(e['profit_at_target'], calc.to_money(1000))  # 950 / 1900 x 2000
        inv = e['by_sale'][self.s1.id]
        self.assertEqual((inv['selling'], inv['cost'], inv['profit']),
                         (calc.to_money(950), calc.to_money(300), calc.to_money(650)))
        self.assertEqual(len(inv['lines']), 2)

    def test_economics_of_item_target_matches_actual(self):
        t = self._target(ttype='company', products=(self.x,))
        e = calc.economics(t)
        self.assertEqual(e['selling'], calc.performance(t)['actual'])  # 550 + 600 + 400 (B)
        self.assertEqual(e['cost'], calc.to_money(600))
        self.assertEqual(e['invoice_charges'], calc.to_money(0))
        self.assertEqual([i['name'] for i in e['by_item']], ['Pump X'])

    def test_warehouse_cost_is_used(self):
        from app.models import ProductWarehouseStock, Warehouse
        wh = Warehouse(name='Main', code='MAIN')
        db.session.add(wh)
        db.session.flush()
        SaleItem.query.filter_by(sale_id=self.s1.id, product_id=self.y.id).update({'warehouse_id': wh.id})
        db.session.add(ProductWarehouseStock(product_id=self.y.id, warehouse_id=wh.id, quantity=5, cost_price=250))
        db.session.commit()
        e = calc.economics(self._target(salesman=self.a))
        self.assertEqual(e['cost'], calc.to_money(750))  # Y now 250 instead of 100

    def test_running_achievement_and_invoice_share(self):
        t = self._target(salesman=self.a, amount=1500)
        running, reached = calc.running_achievement(t)
        self.assertEqual([str(running[s.id][1]) for s in (self.s1, self.s_ret, self.s_edge)],
                         ['66.7', '120.0', '126.7'])
        self.assertEqual(reached, self.s_ret.id)
        _, rows = calc.contributing_invoices(t, per_page=100)
        calc.annotate_invoices(t, rows, calc.economics(t), running)
        row = next(r for r in rows if r['sale'].id == self.s1.id)
        self.assertEqual((str(row['share']), row['econ']['profit']), ('66.7', calc.to_money(650)))

    def test_summary_totals_cost_and_profit(self):
        self._target(salesman=self.a)
        self._target(salesman=self.b, name='B')
        s = svc.summarize(svc.compute_all(SalesTarget.query.all()), 'individual')
        # A: 1550 / 600; B: one X at 400 / 100
        self.assertEqual((s['selling'], s['cost'], s['profit']),
                         (calc.to_money(1950), calc.to_money(700), calc.to_money(1250)))

    def test_detail_and_dashboard_show_profit(self):
        t = self._target(salesman=self.a)
        self.login(self.admin)
        html = self.client.get(f'/sales-target/{t.id}').get_data(as_text=True)
        for text in ('Total Cost', 'Gross Profit', 'PKR 950.00', 'Sales by Item', 'Achieved after',
                     f'id="stLines{self.s1.id}"'):
            self.assertIn(text, html)
        dash = self.client.get('/sales-target/?period=all').get_data(as_text=True)
        self.assertIn('Gross Profit', dash)
        self.assertIn('PKR 950.00', dash)

    def test_profit_hidden_without_profit_loss_access(self):
        t = self._target(salesman=self.a)
        user = self._user('noprofit', can_view_targets=True, can_view_sales=True, can_view_profit_loss=False)
        db.session.commit()
        self.login(user)
        html = self.client.get(f'/sales-target/{t.id}').get_data(as_text=True)
        self.assertIn('Achieved after', html)   # share of the target is still shown
        self.assertIn('Sales by Item', html)
        self.assertNotIn('Gross Profit', html)
        self.assertNotIn('Total Cost', html)
        dash = self.client.get('/sales-target/?period=all&sort=profit').get_data(as_text=True)
        self.assertNotIn('Gross Profit', dash)

    def test_non_finished_item_rejected(self):
        self.login(self.admin)
        csrf, nonce = self.form_tokens('/sales-target/create')
        r = self.client.post('/sales-target/create', data=self.valid_form(
            csrf_token=csrf, form_nonce=nonce, product_ids=[str(self.z.id)]))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SalesTarget.query.count(), 0)

    def test_search_by_item(self):
        self._target(salesman=self.a, products=(self.y,), name='Y push')
        self._target(salesman=self.b, name='General', amount=10)
        self.login(self.admin)
        html = self.client.get('/sales-target/?period=all&q=Pump+Y').get_data(as_text=True)
        self.assertIn('Y push', html)
        self.assertNotIn('General', html)

    def test_deleted_item_does_not_widen_target(self):
        t = self._target(salesman=self.a, products=(self.y,))
        # Other CRM tables (sale lines, cost history) must go first, as in a real
        # product delete; sales_target_products must never be what blocks it.
        db.session.execute(db.text('DELETE FROM sale_items WHERE product_id = :p'), {'p': self.y.id})
        db.session.execute(db.text('DELETE FROM cost_price_history WHERE product_id = :p'), {'p': self.y.id})
        db.session.execute(db.text('DELETE FROM products WHERE id = :p'), {'p': self.y.id})
        db.session.commit()
        db.session.expire_all()
        t = db.session.get(SalesTarget, t.id)
        self.assertTrue(t.has_item_scope)
        p = calc.performance(t)
        self.assertFalse(p['available'])
        self.assertIn('no longer exist', p['error'])

    # ── HTTP: pages and CRUD ───────────────────────────────────────────
    def test_login_page_and_existing_sales_routes_still_work(self):
        self.assertEqual(self.client.get('/auth/login').status_code, 200)
        self.login(self.admin)
        endpoints = ['sales.invoices', 'packing.index', 'quotation.list_quotations', 'returns.return_list',
                     'recovery.dashboard', 'sales.customers', 'sales.customer_groups_list',
                     'sales.salesmen_list', 'reports.profit_loss_report', 'reports.sales_report',
                     'targets.index', 'dashboard.index']
        from flask import url_for
        with self.app.test_request_context():
            urls = {e: url_for(e) for e in endpoints}
        for endpoint, url in urls.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.client.get(url).status_code, 200, endpoint)

    def test_sidebar_position(self):
        self.login(self.admin)
        html = self.client.get('/sales-target/').get_data(as_text=True)
        nav = html[html.index('NavSales"'):]
        i_salesmen, i_target, i_pl = nav.index('>Salesmen<'), nav.index('>Sales Target<'), nav.index('Profit &amp; Loss')
        self.assertTrue(i_salesmen < i_target < i_pl)

    def test_empty_state(self):
        self.login(self.admin)
        html = self.client.get('/sales-target/').get_data(as_text=True)
        self.assertIn('Create Your First Target', html)

    def test_create_view_edit_delete_flow(self):
        self.login(self.manager)
        csrf, nonce = self.form_tokens('/sales-target/create')
        r = self.client.post('/sales-target/create', data=self.valid_form(csrf_token=csrf, form_nonce=nonce))
        self.assertEqual(r.status_code, 302)
        t = SalesTarget.query.one()
        self.assertEqual((t.target_amount, t.salesman_id, t.created_by), (2000.0, self.a.id, self.manager.id))

        html = self.client.get(f'/sales-target/{t.id}').get_data(as_text=True)
        self.assertIn('T-1', html)
        self.assertNotIn('T-3', html)        # pending invoice not listed
        self.assertIn('PKR 1,900.00', html)

        index_html = self.client.get('/sales-target/?period=all').get_data(as_text=True)
        self.assertIn('PKR 1,900.00', index_html)  # dashboard agrees with detail

        csrf, nonce = self.form_tokens(f'/sales-target/{t.id}/edit')
        r = self.client.post(f'/sales-target/{t.id}/edit',
                             data=self.valid_form(csrf_token=csrf, form_nonce=nonce, target_amount='2500.50'))
        self.assertEqual(r.status_code, 302)
        db.session.expire_all()
        self.assertEqual(db.session.get(SalesTarget, t.id).target_amount, 2500.5)

        self.assertEqual(self.client.get(f'/sales-target/{t.id}/delete').status_code, 405)
        r = self.client.post(f'/sales-target/{t.id}/delete', data={'csrf_token': csrf})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SalesTarget.query.count(), 0)

    def test_form_offers_only_individual_type(self):
        self.login(self.admin)
        html = self.client.get('/sales-target/create').get_data(as_text=True)
        self.assertIn('value="individual"', html)
        self.assertNotIn('value="team"', html)
        self.assertNotIn('value="company"', html)
        self.assertNotIn('Combined invoices of chosen salesmen', html)
        self.assertNotIn('All approved invoices', html)
        for ttype, extra in (('team', {'member_ids': [str(self.a.id), str(self.b.id)]}), ('company', {})):
            with self.subTest(ttype):
                csrf, nonce = self.form_tokens('/sales-target/create')
                r = self.client.post('/sales-target/create', data=self.valid_form(
                    csrf_token=csrf, form_nonce=nonce, target_type=ttype, **extra))
                self.assertEqual(r.status_code, 400)
        self.assertEqual(SalesTarget.query.count(), 0)

    def test_existing_team_target_still_editable(self):
        t = self._target(ttype='team', members=(self.a, self.b), name='Old team')
        self.login(self.admin)
        csrf, nonce = self.form_tokens(f'/sales-target/{t.id}/edit')
        r = self.client.post(f'/sales-target/{t.id}/edit', data=self.valid_form(
            csrf_token=csrf, form_nonce=nonce, target_type='team', salesman_id='', name='Old team renamed',
            member_ids=[str(self.a.id), str(self.b.id)]))
        self.assertEqual(r.status_code, 302)
        db.session.expire_all()
        t = db.session.get(SalesTarget, t.id)
        self.assertEqual((t.name, t.target_type), ('Old team renamed', 'team'))
        # ...but an individual target can't be switched to company-wide
        ind = self._target(salesman=self.a, name='Ind')
        csrf, nonce = self.form_tokens(f'/sales-target/{ind.id}/edit')
        r = self.client.post(f'/sales-target/{ind.id}/edit', data=self.valid_form(
            csrf_token=csrf, form_nonce=nonce, target_type='company', name='Ind'))
        self.assertEqual(r.status_code, 400)

    def test_validation_rejects_bad_input_and_keeps_values(self):
        self.login(self.admin)
        cases = {
            'zero amount': dict(target_amount='0'),
            'negative amount': dict(target_amount='-5'),
            'text amount': dict(target_amount='abc'),
            'too many decimals': dict(target_amount='10.123'),
            'end before start': dict(start_date='2026-09-30', end_date='2026-09-01'),
            'missing salesman': dict(salesman_id=''),
            'unknown salesman': dict(salesman_id='99999'),
            'bad status': dict(status='approved'),
            'bad type': dict(target_type='region'),
        }
        for label, over in cases.items():
            with self.subTest(label):
                csrf, nonce = self.form_tokens('/sales-target/create')
                r = self.client.post('/sales-target/create',
                                     data=self.valid_form(csrf_token=csrf, form_nonce=nonce, **over))
                self.assertEqual(r.status_code, 400)
                self.assertIn('September Target', r.get_data(as_text=True))
                self.assertEqual(SalesTarget.query.count(), 0)

    def test_duplicate_submission_and_duplicate_target(self):
        self.login(self.admin)
        csrf, nonce = self.form_tokens('/sales-target/create')
        data = self.valid_form(csrf_token=csrf, form_nonce=nonce)
        self.assertEqual(self.client.post('/sales-target/create', data=data).status_code, 302)
        self.client.post('/sales-target/create', data=data)   # same nonce = double click
        self.assertEqual(SalesTarget.query.count(), 1)

        csrf, nonce = self.form_tokens('/sales-target/create')
        r = self.client.post('/sales-target/create', data=self.valid_form(csrf_token=csrf, form_nonce=nonce))
        self.assertEqual(r.status_code, 400)                  # same scope + period
        self.assertEqual(SalesTarget.query.count(), 1)

    def test_csrf_required(self):
        self.login(self.admin)
        _, nonce = self.form_tokens('/sales-target/create')
        self.client.post('/sales-target/create', data=self.valid_form(form_nonce=nonce, csrf_token='bogus'))
        self.assertEqual(SalesTarget.query.count(), 0)
        t = self._target(salesman=self.a)
        self.client.post(f'/sales-target/{t.id}/delete', data={})
        self.assertEqual(SalesTarget.query.count(), 1)

    def test_closed_target_locks_amount(self):
        t = self._target(salesman=self.a, status='completed')
        self.login(self.admin)
        csrf, nonce = self.form_tokens(f'/sales-target/{t.id}/edit')
        self.client.post(f'/sales-target/{t.id}/edit', data={
            'csrf_token': csrf, 'form_nonce': nonce, 'name': 'Renamed', 'status': 'completed',
            'target_amount': '1', 'target_type': 'company'})
        db.session.expire_all()
        t = db.session.get(SalesTarget, t.id)
        self.assertEqual((t.name, t.target_amount, t.target_type), ('Renamed', 2000.0, 'individual'))

    # ── permissions ────────────────────────────────────────────────────
    def test_view_requires_targets_and_sales_permission(self):
        self.login(self.no_sales)
        self.assertEqual(self.client.get('/sales-target/').status_code, 302)
        self.login(self.viewer)
        self.assertEqual(self.client.get('/sales-target/').status_code, 200)

    def test_viewer_cannot_create_edit_or_delete(self):
        t = self._target(salesman=self.a)
        self.login(self.viewer)
        self.assertEqual(self.client.get('/sales-target/create').status_code, 302)
        r = self.client.post('/sales-target/create', data=self.valid_form(name='Hack'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(f'/sales-target/{t.id}/edit').status_code, 302)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"',
                         self.client.get(f'/sales-target/{t.id}').get_data(as_text=True))
        self.client.post(f'/sales-target/{t.id}/delete', data={'csrf_token': csrf.group(1) if csrf else ''})
        self.assertEqual(SalesTarget.query.count(), 1)

    def test_salesperson_sees_only_own_targets(self):
        own = self._target(salesman=self.a, name='Mine')
        other = self._target(salesman=self.b, name='Theirs')
        co = self._target(ttype='company', name='Company')
        self.login(self.rep_user)  # linked to salesman A
        self.assertEqual(self.client.get(f'/sales-target/{own.id}').status_code, 200)
        self.assertEqual(self.client.get(f'/sales-target/{other.id}').status_code, 302)  # 404 -> app redirect
        self.assertEqual(self.client.get(f'/sales-target/{co.id}').status_code, 302)
        html = self.client.get('/sales-target/?period=all').get_data(as_text=True)
        self.assertIn('Mine', html)
        self.assertNotIn('Theirs', html)
        # Linked salespeople can't create/edit targets even with the flags.
        self.assertEqual(self.client.get('/sales-target/create').status_code, 302)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get('/sales-target/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/auth/login', r.headers['Location'])

    def test_deleting_salesman_elsewhere_is_not_blocked(self):
        c = Salesman(name='Temp', is_active=True)
        db.session.add(c)
        db.session.commit()
        t = self._target(salesman=c, name='Temp target')
        db.session.delete(c)
        db.session.commit()
        db.session.expire_all()
        t = db.session.get(SalesTarget, t.id)
        self.assertIsNone(t.salesman_id)
        self.assertFalse(calc.performance(t)['available'])


    # ── yearly plans (12 months) and bulk per-item targets ─────────────
    MONTHS_2026 = ['100000', '100000', '100000', '100000', '100000', '100000',
                   '100000', '100000', '150000', '100000', '100000', '50000.01']   # 1,200,000.01

    def plan_form(self, **over):
        data = {'name': '2026 Sales', 'target_type': 'individual', 'salesman_id': str(self.a.id),
                'status': 'active', 'description': '', 'period_mode': 'yearly',
                'plan_year': '2026', 'plan_start_month': '1', 'total_all': '1200000.01'}
        data.update({f'amt_all_{n}': v for n, v in enumerate(self.MONTHS_2026, 1)})
        data.update(over)
        return data

    def months(self, key, amounts, total=None):
        out = {f'amt_{key}_{n}': str(v) for n, v in enumerate(amounts, 1)}
        out[f'total_{key}'] = str(total if total is not None else sum(amounts))
        return out

    def post_create(self, data):
        csrf, nonce = self.form_tokens('/sales-target/create')
        data = dict(data, csrf_token=csrf, form_nonce=nonce)
        return self.client.post('/sales-target/create', data=data)

    def test_periods_and_equal_split(self):
        ms = plans.periods(2026, 7)  # July-June financial year, monthly
        self.assertEqual(len(ms), 12)
        self.assertEqual((ms[0]['start'], ms[0]['end'], ms[0]['title']), (date(2026, 7, 1), date(2026, 7, 31), 'Jul 2026'))
        self.assertEqual((ms[7]['start'], ms[7]['end']), (date(2027, 2, 1), date(2027, 2, 28)))
        self.assertEqual((ms[11]['start'], ms[11]['end']), (date(2027, 6, 1), date(2027, 6, 30)))
        qs = plans.quarters(2026, 7)
        self.assertEqual([(q['start'], q['end']) for q in qs],
                         [(date(2026, 7, 1), date(2026, 9, 30)), (date(2026, 10, 1), date(2026, 12, 31)),
                          (date(2027, 1, 1), date(2027, 3, 31)), (date(2027, 4, 1), date(2027, 6, 30))])
        self.assertEqual(plans.year_label(2026, 7), 'FY 2026-27')
        from decimal import Decimal
        self.assertEqual(plans.split_equal(Decimal('100.01'), 4), [Decimal('25.00')] * 3 + [Decimal('25.01')])

    def test_create_yearly_plan_with_custom_months(self):
        self.login(self.admin)
        r = self.post_create(self.plan_form())
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:3000])
        plan = SalesTargetPlan.query.one()
        self.assertTrue(plan.is_monthly)
        self.assertIn(f'/sales-target/plan/{plan.id}', r.headers['Location'])
        ts = sorted(plans.plan_targets(plan), key=lambda t: t.start_date)
        self.assertEqual(len(ts), 12)
        self.assertEqual([t.target_amount for t in ts], [float(v) for v in self.MONTHS_2026])
        self.assertEqual((ts[1].start_date, ts[1].end_date), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual((ts[8].start_date, ts[8].end_date), (PERIOD_START, PERIOD_END))
        self.assertTrue(all(t.salesman_id == self.a.id and t.status == 'active' for t in ts))
        self.assertIn('Sep 2026', ts[8].name)
        page = self.client.get(f'/sales-target/plan/{plan.id}').get_data(as_text=True)
        self.assertIn('PKR 1,200,000.01', page)
        self.assertIn('PKR 1,900.00', page)          # Ali's September invoices
        self.assertIn('PKR 900.00', page)            # ...and 31 August in August
        detail = self.client.get(f'/sales-target/{ts[8].id}').get_data(as_text=True)
        # The period switcher lists the full year and every month of the plan.
        self.assertIn('Full year', detail)
        self.assertIn(f'/sales-target/plan/{plan.id}', detail)
        self.assertIn(f'href="/sales-target/{ts[0].id}"', detail)
        self.assertIn('Sep 2026', detail)

    def test_months_must_add_up_to_year(self):
        self.login(self.admin)
        r = self.post_create(self.plan_form(amt_all_12='1'))
        self.assertEqual(r.status_code, 400)
        html = r.get_data(as_text=True)
        self.assertIn('the months add up to', html)
        self.assertIn('short by PKR 49,999.01', html)
        self.assertIn('"amt_all_9": "150000"', html)    # typed values come back
        self.assertEqual(SalesTarget.query.count(), 0)
        r = self.post_create(self.plan_form(amt_all_1='-5', amt_all_2='200005'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SalesTarget.query.count(), 0)

    def test_zero_month_is_skipped(self):
        self.login(self.admin)
        self.post_create(self.plan_form(**self.months('all', [100] * 6 + [0] + [100] * 5)))
        plan = SalesTargetPlan.query.one()
        self.assertEqual(sorted(p.period_no for p in plan.parts), [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12])

    def test_yearly_plan_per_item_financial_year(self):
        self.login(self.admin)
        x, y = self.x.id, self.y.id
        r = self.post_create(self.plan_form(
            split_items='1', product_ids=[str(x), str(y)], plan_year='2026', plan_start_month='7',
            **self.months(f'p{x}', [100] * 12), **self.months(f'p{y}', [10] * 11 + [20])))
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:3000])
        plan = SalesTargetPlan.query.one()
        self.assertTrue(plan.split_by_item)
        ts = plans.plan_targets(plan)
        self.assertEqual(len(ts), 24)
        self.assertEqual(min(t.start_date for t in ts), date(2026, 7, 1))
        self.assertEqual(max(t.end_date for t in ts), date(2027, 6, 30))
        y_jun = next(t for t in ts if t.product_ids == [y] and t.start_date == date(2027, 6, 1))
        self.assertEqual(y_jun.target_amount, 20)
        _, rows = plans.plan_layout(plan)
        self.assertEqual(len(rows), 2)

    def test_item_month_actual(self):
        self.login(self.admin)
        x = self.x.id
        self.post_create(self.plan_form(split_items='1', product_ids=[str(x)], **self.months(f'p{x}', [100] * 12)))
        ts = plans.plan_targets(SalesTargetPlan.query.one())
        x_sep = next(t for t in ts if t.start_date == PERIOD_START)
        # Item X lines of Ali in September: 550 + (800 - 200 returned) = 1150
        self.assertEqual(str(calc.performance(x_sep)['actual']), '1150.00')

    def test_bulk_single_period_targets_per_item(self):
        self.login(self.admin)
        r = self.post_create(self.valid_form(
            split_items='1', product_ids=[str(self.x.id), str(self.y.id)], target_amount='',
            **{f'amt_p{self.x.id}_1': '5000', f'amt_p{self.y.id}_1': '7000'}))
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:3000])
        ts = SalesTarget.query.order_by(SalesTarget.target_amount).all()
        self.assertEqual([(t.target_amount, t.product_ids) for t in ts],
                         [(5000, [self.x.id]), (7000, [self.y.id])])
        self.assertTrue(all(t.start_date == PERIOD_START and t.end_date == PERIOD_END for t in ts))
        self.assertEqual(SalesTargetPlan.query.count(), 0)
        r = self.post_create(self.valid_form(split_items='1', name='Other'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Choose the finished items', r.get_data(as_text=True))

    def test_duplicate_plan_rejected(self):
        self.login(self.admin)
        self.post_create(self.plan_form())
        r = self.post_create(self.plan_form(name='Again'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('already exists', r.get_data(as_text=True))
        self.assertEqual(SalesTarget.query.count(), 12)

    def test_form_has_no_table_tools_on_grid(self):
        self.login(self.admin)
        html = self.client.get('/sales-target/create').get_data(as_text=True)
        self.assertIn('no-datatable" data-st-grid data-st-unit="months"', html)

    def _plan_edit_post(self, plan, data):
        html = self.client.get(f'/sales-target/plan/{plan.id}/edit').get_data(as_text=True)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        nonce = re.search(r'name="form_nonce" value="([^"]+)"', html).group(1)
        return self.client.post(f'/sales-target/plan/{plan.id}/edit',
                                data=dict(data, csrf_token=csrf, form_nonce=nonce))

    def test_quarters_and_partial_count(self):
        """Split into quarters, or only some months/quarters from the start month."""
        self.login(self.admin)
        r = self.post_create(self.plan_form(plan_split='quarter', plan_count='4', plan_start_month='7',
                                            **self.months('all', [100, 200, 300, 400])))
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:3000])
        plan = SalesTargetPlan.query.one()
        self.assertEqual((plan.period_months, plan.period_count), (3, None))
        ts = sorted(plans.plan_targets(plan), key=lambda t: t.start_date)
        self.assertEqual([(t.start_date, t.end_date, t.target_amount) for t in ts],
                         [(date(2026, 7, 1), date(2026, 9, 30), 100), (date(2026, 10, 1), date(2026, 12, 31), 200),
                          (date(2027, 1, 1), date(2027, 3, 31), 300), (date(2027, 4, 1), date(2027, 6, 30), 400)])
        self.assertIn('FY 2026-27', self.client.get(f'/sales-target/plan/{plan.id}').get_data(as_text=True))
        # three months only, Oct-Dec 2027
        r = self.post_create(self.plan_form(name='Q4 push', plan_year='2027', plan_start_month='10', plan_count='3',
                                            **self.months('all', [50, 50, 100])))
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:3000])
        p2 = SalesTargetPlan.query.filter_by(name='Q4 push').one()
        self.assertEqual((p2.period_months, p2.period_count), (1, 3))
        ts = sorted(plans.plan_targets(p2), key=lambda t: t.start_date)
        self.assertEqual([t.start_date for t in ts], [date(2027, 10, 1), date(2027, 11, 1), date(2027, 12, 1)])
        page = self.client.get(f'/sales-target/plan/{p2.id}').get_data(as_text=True)
        self.assertIn('Oct 2027 – Dec 2027', page)
        self.assertEqual(len(plans.plan_layout(p2)[0]), 3)
        # extra posted months beyond the count are ignored; a count too high is refused
        r = self.post_create(self.plan_form(name='Bad', plan_split='quarter', plan_count='5'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('between 1 and 4', r.get_data(as_text=True))

    def test_edit_yearly_split(self):
        self.login(self.admin)
        self.post_create(self.plan_form(**self.months('all', [100] * 12)))
        plan = SalesTargetPlan.query.one()
        m = {p.period_no: p.target for p in plan.parts}
        m[1].status = 'completed'   # January: locked, but still part of the year
        db.session.commit()
        page = self.client.get(f'/sales-target/plan/{plan.id}/edit').get_data(as_text=True)
        self.assertNotIn('name="amt_r0_1"', page)
        self.assertIn('Save month targets', page)
        new = {f'amt_r0_{n}': '100' for n in range(2, 13)}
        new.update(amt_r0_2='400', amt_r0_3='0.5', amt_r0_12='99.5', total_r0='1400')
        r = self._plan_edit_post(plan, new)
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:3000])
        db.session.expire_all()
        self.assertEqual([db.session.get(SalesTarget, m[n].id).target_amount for n in (1, 2, 3, 12)],
                         [100, 400, 0.5, 99.5])
        new['amt_r0_12'] = '1'
        r = self._plan_edit_post(plan, new)
        self.assertEqual(r.status_code, 400)
        self.assertIn('short by PKR 98.50', r.get_data(as_text=True))

    def test_older_quarterly_plan_still_works(self):
        plan = SalesTargetPlan(name='Old', year=2026, start_month=1, split_by_item=False, period_months=3,
                               created_by=self.admin.id)
        db.session.add(plan)
        q3 = self._target(salesman=self.a, amount=500, start=date(2026, 7, 1), end=date(2026, 9, 30), name='Old Q3')
        q4 = self._target(salesman=self.a, amount=500, start=date(2026, 10, 1), end=date(2026, 12, 31), name='Old Q4')
        from app.sales_target.models import SalesTargetPlanPart
        db.session.add_all([SalesTargetPlanPart(plan=plan, target_id=q3.id, row_no=0, period_no=3),
                            SalesTargetPlanPart(plan=plan, target_id=q4.id, row_no=0, period_no=4)])
        db.session.commit()
        self.login(self.admin)
        page = self.client.get(f'/sales-target/plan/{plan.id}').get_data(as_text=True)
        self.assertIn('split into quarters', page)
        self.assertIn('Jul–Sep 2026', page)
        self.assertIn('Q3 (Jul–Sep 2026)', self.client.get(f'/sales-target/{q3.id}').get_data(as_text=True))
        edit = self.client.get(f'/sales-target/plan/{plan.id}/edit').get_data(as_text=True)
        self.assertIn('Save quarter targets', edit)
        r = self._plan_edit_post(plan, {'total_r0': '1000', 'amt_r0_3': '300', 'amt_r0_4': '700'})
        self.assertEqual(r.status_code, 302)

    def test_upgrade_from_quarter_only_tables(self):
        """The first version's tables (quarter 1-4) are upgraded in place,
        keeping their rows, and the upgrade is a no-op afterwards."""
        import sqlite3
        from sqlalchemy import create_engine
        from app.sales_target import upgrade_plan_tables
        path = os.path.join(_TMP, 'upgrade.db')
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE sales_targets (id INTEGER PRIMARY KEY);
            CREATE TABLE sales_target_plans (id INTEGER NOT NULL PRIMARY KEY, name VARCHAR(150) NOT NULL,
                year INTEGER NOT NULL, start_month INTEGER NOT NULL, split_by_item BOOLEAN NOT NULL,
                created_by INTEGER, created_at DATETIME NOT NULL,
                CONSTRAINT ck_sales_target_plans_month CHECK (start_month BETWEEN 1 AND 12));
            CREATE TABLE sales_target_plan_parts (id INTEGER NOT NULL PRIMARY KEY, plan_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL, row_no INTEGER NOT NULL, quarter INTEGER NOT NULL,
                CONSTRAINT ck_sales_target_plan_parts_quarter CHECK (quarter BETWEEN 1 AND 4));
            INSERT INTO sales_targets VALUES (7);
            INSERT INTO sales_target_plans VALUES (1, 'Old', 2026, 1, 0, NULL, '2026-10-01');
            INSERT INTO sales_target_plan_parts VALUES (1, 1, 7, 0, 2);
        """)
        con.commit()
        con.close()
        engine = create_engine('sqlite:///' + path.replace('\\', '/'))
        upgrade_plan_tables(engine)
        upgrade_plan_tables(engine)   # second run does nothing
        with engine.connect() as conn:
            self.assertEqual(conn.exec_driver_sql('SELECT period_months FROM sales_target_plans').scalar(), 3)
            self.assertIsNone(conn.exec_driver_sql('SELECT period_count FROM sales_target_plans').scalar())
            self.assertEqual(conn.exec_driver_sql('SELECT period_no FROM sales_target_plan_parts').scalar(), 2)
            conn.exec_driver_sql("INSERT INTO sales_target_plans (id, name, year, start_month, split_by_item, "
                                 "period_months, created_at) VALUES (2, 'New', 2027, 1, 0, 1, '2026-10-17')")
            conn.exec_driver_sql('INSERT INTO sales_target_plan_parts (plan_id, target_id, row_no, period_no) '
                                 'VALUES (2, 8, 0, 12)')   # month 12 is allowed now
            from sqlalchemy.exc import IntegrityError
            with self.assertRaises(IntegrityError):
                conn.exec_driver_sql('INSERT INTO sales_target_plan_parts (plan_id, target_id, row_no, period_no) '
                                     'VALUES (2, 9, 0, 13)')
        engine.dispose()

    def test_plan_permissions_and_delete(self):
        self.login(self.admin)
        self.post_create(self.plan_form(**self.months('all', [100, 100] + [0] * 10)))
        plan = SalesTargetPlan.query.one()
        self.login(self.viewer)
        self.assertEqual(self.client.get(f'/sales-target/plan/{plan.id}').status_code, 200)
        self.assertEqual(self.client.get(f'/sales-target/plan/{plan.id}/edit').status_code, 302)
        self.login(self.rep_user)       # salesperson for Ali: sees Ali's plan
        self.assertEqual(self.client.get(f'/sales-target/plan/{plan.id}').status_code, 200)
        # deleting months: the plan stays until its last month is gone
        self.login(self.admin)
        html = self.client.get('/sales-target/').get_data(as_text=True)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        ids = [p.target_id for p in plan.parts]
        for i, tid in enumerate(ids):
            self.client.post(f'/sales-target/{tid}/delete', data={'csrf_token': csrf})
            db.session.expire_all()
            self.assertEqual(SalesTargetPlan.query.count(), 0 if i == len(ids) - 1 else 1)
        r = self.client.get(f'/sales-target/plan/{plan.id}')
        self.assertEqual((r.status_code, r.headers['Location']), (302, '/'))  # 404 -> app redirect

    def test_plan_hidden_from_other_salesperson(self):
        self.login(self.admin)
        self.post_create(self.plan_form(salesman_id=str(self.b.id)))
        plan = SalesTargetPlan.query.one()
        self.login(self.rep_user)       # linked to Ali, plan is Bilal's
        r = self.client.get(f'/sales-target/plan/{plan.id}')
        self.assertEqual((r.status_code, r.headers['Location']), (302, '/'))  # 404 -> app redirect

if __name__ == '__main__':
    unittest.main()
