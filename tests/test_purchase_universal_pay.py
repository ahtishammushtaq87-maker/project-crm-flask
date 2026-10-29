"""Tests for the purchase Universal Pay (one vendor payment spread across
unpaid bills oldest-first, leftover -> vendor advance) and its effect on the
vendor ledger and the paid-from bank / cash account.

Runs against a throw-away SQLite file, never the real instance/database.db:

    venv\\Scripts\\python.exe -m unittest tests.test_purchase_universal_pay -v
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime

_TMP = tempfile.mkdtemp(prefix='purchase_universal_pay_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import (User, Vendor, PurchaseBill, BillPayment, VendorAdvance,  # noqa: E402
                        ExpenseAccount, ExpenseAccountTransaction)


class PurchaseUniversalPayTestCase(unittest.TestCase):
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
        from flask import g
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin.id)
            sess['_fresh'] = True
        g.pop('_login_user', None)

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
        self.vendor = Vendor(name='Steel Supplier', is_active=True)
        self.bank = ExpenseAccount(name='Meezan Bank', account_type='Bank', opening_balance=5000, is_active=True)
        db.session.add_all([self.vendor, self.bank])
        db.session.flush()
        self.b1 = self._bill('PO-1', 500, datetime(2026, 9, 1))
        self.b2 = self._bill('PO-2', 300, datetime(2026, 9, 5))
        db.session.commit()

    def _bill(self, number, total, when):
        b = PurchaseBill(bill_number=number, vendor_id=self.vendor.id, date=when, subtotal=total, total=total,
                         tax_rate=0, shipping_charge=0, paid_amount=0, cancelled_amount=0, status='unpaid')
        db.session.add(b)
        db.session.flush()
        return b

    def upay(self, amount, account=None, method='Bank Transfer'):
        data = {'amount': str(amount), 'payment_method': method, 'payment_date': '2026-09-10'}
        if account is not None:
            data['expense_account_id'] = str(account.id)
        return self.client.post(f'/purchase/vendor/{self.vendor.id}/universal-pay', data=data)

    def ledger(self):
        from app.routes.purchase import build_vendor_ledger
        db.session.expire_all()
        return build_vendor_ledger(db.session.get(Vendor, self.vendor.id))

    def test_oldest_first_and_leftover_advance(self):
        r = self.upay(1000, self.bank)
        self.assertEqual(r.status_code, 302)
        db.session.expire_all()
        b1, b2 = db.session.get(PurchaseBill, self.b1.id), db.session.get(PurchaseBill, self.b2.id)
        self.assertEqual((b1.paid_amount, b1.status), (500, 'paid'))
        self.assertEqual((b2.paid_amount, b2.status), (300, 'paid'))
        pays = {p.bill_id: p.amount for p in BillPayment.query.all()}
        self.assertEqual(pays, {b1.id: 500, b2.id: 300})
        adv = VendorAdvance.query.one()
        self.assertEqual((adv.amount, adv.applied_amount), (200, 0))
        # Account: three credit rows totalling the full amount paid out.
        rows = ExpenseAccountTransaction.query.all()
        self.assertEqual(sorted(t.amount for t in rows), [200, 300, 500])
        self.assertTrue(all(t.entry_type == 'credit' and t.is_approved for t in rows))
        self.assertEqual(round(db.session.get(ExpenseAccount, self.bank.id).balance, 2), 4000)
        # Ledger: bills fully paid, leftover advance not yet counted.
        self.assertEqual(self.ledger()['closing_balance'], 0)

    def test_partial_payment_stops_at_oldest(self):
        self.upay(350)
        db.session.expire_all()
        self.assertEqual(db.session.get(PurchaseBill, self.b1.id).paid_amount, 350)
        self.assertEqual(db.session.get(PurchaseBill, self.b2.id).paid_amount, 0)
        self.assertEqual(VendorAdvance.query.count(), 0)
        self.assertEqual(ExpenseAccountTransaction.query.count(), 0)
        self.assertEqual(self.ledger()['closing_balance'], 450)

    def test_pending_staff_payment_not_allocated_twice(self):
        db.session.add(BillPayment(bill_id=self.b1.id, amount=500, is_approved=False))
        db.session.commit()
        self.upay(300)
        db.session.expire_all()
        new = BillPayment.query.filter_by(is_approved=True).one()
        self.assertEqual((new.bill_id, new.amount), (self.b2.id, 300))

    def test_leftover_advance_counts_once_when_applied(self):
        self.upay(1000)  # 200 leftover advance
        b3 = self._bill('PO-3', 150, datetime(2026, 9, 20))
        db.session.commit()
        from app.utils import auto_apply_vendor_advance
        auto_apply_vendor_advance(db.session.get(PurchaseBill, b3.id))
        db.session.commit()
        # 150 bill fully covered by advance -> nothing owed, not negative.
        self.assertEqual(self.ledger()['closing_balance'], 0)

    def _pay_on(self, bill):
        db.session.expire_all()
        return BillPayment.query.filter_by(bill_id=bill.id).one()

    def test_delete_universal_payment_reverses_bill_account_and_ledger(self):
        self.upay(800, self.bank)
        p = self._pay_on(self.b1)
        self.client.post(f'/purchase/bill/{self.b1.id}/payment/{p.id}/delete')
        db.session.expire_all()
        b1 = db.session.get(PurchaseBill, self.b1.id)
        self.assertEqual((b1.paid_amount, b1.status), (0, 'unpaid'))
        self.assertEqual(db.session.get(PurchaseBill, self.b2.id).paid_amount, 300)  # other bill untouched
        self.assertEqual(round(db.session.get(ExpenseAccount, self.bank.id).balance, 2), 4700)
        self.assertEqual(self.ledger()['closing_balance'], 500)

    def test_edit_universal_payment_down_and_up(self):
        self.upay(800, self.bank)
        p = self._pay_on(self.b1)
        url = f'/purchase/bill/{self.b1.id}/payment/{p.id}/edit'
        form = {'payment_date': '2026-09-10', 'payment_method': 'Bank Transfer',
                'expense_account_id': str(self.bank.id)}
        self.client.post(url, data={**form, 'amount': '200'})
        db.session.expire_all()
        self.assertEqual(db.session.get(PurchaseBill, self.b1.id).paid_amount, 200)
        self.assertEqual(round(db.session.get(ExpenseAccount, self.bank.id).balance, 2), 4500)
        self.assertEqual(self.ledger()['closing_balance'], 300)
        # Raise above the bill: excess becomes an auto-credit advance, ledger not double counted.
        self.client.post(url, data={**form, 'amount': '600'})
        db.session.expire_all()
        self.assertEqual(db.session.get(PurchaseBill, self.b1.id).paid_amount, 500)
        self.assertEqual(VendorAdvance.query.one().amount, 100)
        self.assertEqual(self.ledger()['closing_balance'], -100)  # vendor owes us the 100 overpaid

    def test_delete_pending_payment_leaves_bill_alone(self):
        self.b1.paid_amount = 100
        db.session.add(BillPayment(bill_id=self.b1.id, amount=400, is_approved=False))
        db.session.commit()
        p = BillPayment.query.one()
        self.client.post(f'/purchase/bill/{self.b1.id}/payment/{p.id}/delete')
        db.session.expire_all()
        self.assertEqual(db.session.get(PurchaseBill, self.b1.id).paid_amount, 100)

    def _applied_advance(self):
        """Universal Pay leaves a 200 advance (paid from bank) that is then
        auto-applied to a new 150 bill."""
        self.upay(1000, self.bank)
        b3 = self._bill('PO-3', 150, datetime(2026, 9, 20))
        db.session.commit()
        from app.utils import auto_apply_vendor_advance
        auto_apply_vendor_advance(db.session.get(PurchaseBill, b3.id))
        db.session.commit()
        return b3, VendorAdvance.query.one()

    def test_bill_detail_shows_advance_actions(self):
        b3, adv = self._applied_advance()
        r = self.client.get(f'/purchase/bill/{b3.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'editAdvanceModal{adv.id}'.encode(), r.data)

    def test_edit_applied_advance_from_bill(self):
        b3, adv = self._applied_advance()
        url = f'/purchase/vendor/{self.vendor.id}/advance/{adv.id}/edit'
        base = {'return_bill_id': str(b3.id), 'expense_account_id': str(self.bank.id), 'advance_date': '2026-09-10'}
        r = self.client.post(url, data={**base, 'amount': '100'})  # below the 150 applied -> refused
        self.assertTrue(r.location.endswith(f'/purchase/bill/{b3.id}'))
        db.session.expire_all()
        self.assertEqual(db.session.get(VendorAdvance, adv.id).amount, 200)
        self.client.post(url, data={**base, 'amount': '250', 'description': 'Corrected'})
        db.session.expire_all()
        a = db.session.get(VendorAdvance, adv.id)
        self.assertEqual((a.amount, a.description), (250, 'Corrected'))
        self.assertEqual(ExpenseAccountTransaction.query.filter_by(vendor_advance_id=adv.id).one().amount, 250)
        self.assertEqual(db.session.get(PurchaseBill, b3.id).paid_amount, 150)  # bill unchanged
        self.assertEqual(self.ledger()['closing_balance'], 0)

    def test_delete_applied_advance_from_bill_reverses(self):
        b3, adv = self._applied_advance()
        r = self.client.post(f'/purchase/vendor/{self.vendor.id}/advance/{adv.id}/delete',
                             data={'return_bill_id': str(b3.id)})
        self.assertTrue(r.location.endswith(f'/purchase/bill/{b3.id}'))
        db.session.expire_all()
        self.assertEqual(VendorAdvance.query.count(), 0)
        self.assertEqual(db.session.get(PurchaseBill, b3.id).paid_amount, 0)
        self.assertEqual(round(db.session.get(ExpenseAccount, self.bank.id).balance, 2), 4200)  # 200 back
        self.assertEqual(self.ledger()['closing_balance'], 150)

    def test_zero_amount_rejected(self):
        self.upay(0)
        self.assertEqual(BillPayment.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
