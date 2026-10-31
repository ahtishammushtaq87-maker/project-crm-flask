"""Tests for the Sales Return verification flow: Customer Problem ->
inventory, Item / Packaging Issue -> Repair section, Scrap -> Scrap section.

Runs against a throw-away SQLite file, never the real instance/database.db:

    venv\\Scripts\\python.exe -m unittest tests.test_sale_return_verify -v
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime

_TMP = tempfile.mkdtemp(prefix='sale_return_verify_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import (User, Customer, Sale, Product, SaleReturn, SaleReturnItem,  # noqa: E402
                        RepairOrder, ScrapRecord)


class SaleReturnVerifyTestCase(unittest.TestCase):
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
        self.addCleanup(self._cleanup)
        self._wipe()
        self._seed()
        self.client = self.app.test_client()
        self.login(self.admin)

    def _cleanup(self):
        db.session.rollback()
        db.session.remove()
        self.ctx.pop()

    @staticmethod
    def _wipe():
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            tables = [r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))]
            for name in tables:
                conn.exec_driver_sql(f'DELETE FROM "{name}"')
            conn.commit()
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')

    def _seed(self):
        self.admin = User(username='admin', email='admin@example.com', role='admin')
        self.admin.set_password('pw')
        db.session.add(self.admin)
        customer = Customer(name='Acme Traders')
        db.session.add(customer)
        self.products = [Product(name=f'P{i}', sku=f'SKU{i}', cost_price=10, unit_price=20, quantity=100)
                         for i in range(4)]
        db.session.add_all(self.products)
        db.session.flush()
        sale = Sale(invoice_number='INV-1', customer_id=customer.id, date=datetime(2026, 9, 1),
                    subtotal=0, total=0, paid_amount=0, is_approved=True, status='unpaid')
        db.session.add(sale)
        db.session.flush()
        self.ret = SaleReturn(return_number='RET-1', sale_id=sale.id, customer_id=customer.id, reason='x',
                              status='approved', is_approved=True, created_by=self.admin.id)
        db.session.add(self.ret)
        db.session.flush()
        self.items = [SaleReturnItem(return_id=self.ret.id, product_id=p.id, quantity=5, unit_price=20, total=100)
                      for p in self.products]
        db.session.add_all(self.items)
        db.session.commit()

    def login(self, user):
        from flask import g
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        g.pop('_login_user', None)

    def qty(self, product):
        db.session.expire_all()
        return db.session.get(Product, product.id).quantity

    def verify(self):
        a, b, c, d = self.items
        return self.client.post(f'/returns/{self.ret.id}/verify', data={
            f'disposition_{a.id}': 'customer_issue', f'condition_{a.id}': 'New / Unused',
            f'disposition_{b.id}': 'item_issue', f'issue_{b.id}': 'Cracked',
            f'disposition_{c.id}': 'packaging_issue', f'issue_{c.id}': 'Torn box',
            f'disposition_{d.id}': 'scrap', f'scrap_reason_{d.id}': 'Burnt',
        })

    def test_detail_shows_verify_button(self):
        r = self.client.get(f'/returns/{self.ret.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Verify Return', r.data)
        self.assertEqual(self.client.get(f'/returns/{self.ret.id}/verify').status_code, 200)

    def test_verify_routes_each_item(self):
        self.assertEqual(self.verify().status_code, 302)
        p = self.products
        self.assertEqual(self.qty(p[0]), 105)  # restocked
        self.assertEqual(self.qty(p[1]), 100)  # in repair
        self.assertEqual(self.qty(p[2]), 100)
        self.assertEqual(self.qty(p[3]), 100)  # scrapped
        self.assertEqual(RepairOrder.query.count(), 2)
        scrap = ScrapRecord.query.one()
        self.assertEqual((scrap.quantity, scrap.total_cost), (5, 50))
        ret = db.session.get(SaleReturn, self.ret.id)
        self.assertTrue(ret.is_verified)
        self.assertEqual(ret.status, 'completed')
        # cannot verify twice
        self.verify()
        self.assertEqual(self.qty(p[0]), 105)

    def test_incomplete_verify_changes_nothing(self):
        r = self.client.post(f'/returns/{self.ret.id}/verify',
                             data={f'disposition_{self.items[0].id}': 'customer_issue'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.qty(self.products[0]), 100)
        self.assertFalse(db.session.get(SaleReturn, self.ret.id).is_verified)

    def test_repair_complete_restocks_and_scraps_rest(self):
        self.verify()
        repair = RepairOrder.query.filter_by(issue_type='item_issue').one()
        self.client.post(f'/returns/repairs/{repair.id}/start')
        self.client.post(f'/returns/repairs/{repair.id}/complete', data={'repaired_qty': '3', 'repair_cost': '15'})
        db.session.expire_all()
        repair = db.session.get(RepairOrder, repair.id)
        self.assertEqual(repair.status, 'completed')
        self.assertEqual((repair.repaired_qty, repair.scrapped_qty), (3, 2))
        self.assertEqual(self.qty(self.products[1]), 103)
        self.assertEqual(ScrapRecord.query.filter_by(source_type='repair_order').one().quantity, 2)

    def test_sections_render(self):
        self.verify()
        for url in ('/returns/repairs', '/returns/repairs?status=all', '/returns/scrap',
                    f'/returns/repairs/{RepairOrder.query.first().id}', f'/returns/{self.ret.id}', '/returns/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_delete_verified_return_reverses_only_restocked(self):
        self.verify()
        self.client.post(f'/returns/{self.ret.id}/delete')
        self.assertIsNone(db.session.get(SaleReturn, self.ret.id))
        self.assertEqual(self.qty(self.products[0]), 100)
        self.assertEqual(self.qty(self.products[1]), 100)
        self.assertEqual(RepairOrder.query.count(), 0)
        self.assertEqual(ScrapRecord.query.count(), 0)

    def test_delete_blocked_after_completed_repair(self):
        self.verify()
        repair = RepairOrder.query.first()
        self.client.post(f'/returns/repairs/{repair.id}/complete', data={'repaired_qty': '5'})
        self.client.post(f'/returns/{self.ret.id}/delete')
        self.assertIsNotNone(db.session.get(SaleReturn, self.ret.id))


if __name__ == '__main__':
    unittest.main()
