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
from app.sales_target.models import SalesTarget, SalesTargetMember, SalesTargetProduct  # noqa: E402

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
        self.assertIn('Pump X (PX)', html)
        self.assertNotIn('Bolt Z', html)  # only finished items are offered
        csrf, nonce = self.form_tokens('/sales-target/create')
        r = self.client.post('/sales-target/create', data=self.valid_form(
            csrf_token=csrf, form_nonce=nonce, product_ids=[str(self.x.id), str(self.y.id)]))
        self.assertEqual(r.status_code, 302)
        t = SalesTarget.query.one()
        self.assertEqual(t.product_ids, sorted([self.x.id, self.y.id]))
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


if __name__ == '__main__':
    unittest.main()
