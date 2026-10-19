"""Tests for receiving a sales invoice payment into a bank / cash account
(Record Payment, Universal Pay, Edit / Reject / Delete Payment).

Runs against a throw-away SQLite file, never the real instance/database.db:

    venv\\Scripts\\python.exe -m unittest tests.test_sale_payment_account -v
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime

_TMP = tempfile.mkdtemp(prefix='sale_payment_account_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
for _flag in ('RECOVERY', 'BACKUP', 'PRODUCTION_TARGET', 'MO_TIMER', 'ATTENDANCE_BONUS'):
    os.environ[f'{_flag}_SCHEDULER_DISABLED'] = '1'

from app import create_app, db  # noqa: E402
from app.models import (User, Customer, Sale, Payment, CustomerAdvance,  # noqa: E402
                        ExpenseAccount, ExpenseAccountTransaction)


class SalePaymentAccountTestCase(unittest.TestCase):
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
        self.customer = Customer(name='Acme Traders')
        db.session.add(self.customer)
        self.bank = ExpenseAccount(name='Meezan Bank', account_type='Bank', opening_balance=1000, is_active=True)
        self.cash = ExpenseAccount(name='Cash Box', account_type='Cash', opening_balance=0, is_active=True)
        self.closed = ExpenseAccount(name='Old Account', is_active=False)
        db.session.add_all([self.bank, self.cash, self.closed])
        db.session.flush()
        self.s1 = self._sale('INV-1', 500, datetime(2026, 9, 1))
        self.s2 = self._sale('INV-2', 300, datetime(2026, 9, 5))
        db.session.commit()

    def _sale(self, number, total, when):
        s = Sale(invoice_number=number, customer_id=self.customer.id, date=when, subtotal=total, total=total,
                 paid_amount=0, is_approved=True, status='unpaid')
        db.session.add(s)
        db.session.flush()
        return s

    def login(self, user):
        from flask import g
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        g.pop('_login_user', None)

    def pay(self, sale, amount, account=None, **extra):
        data = {'amount': str(amount), 'payment_method': 'Bank Transfer', 'payment_date': '2026-09-10'}
        if account is not None:
            data['account_id'] = str(account.id) if hasattr(account, 'id') else account
        data.update(extra)
        return self.client.post(f'/sales/invoice/{sale.id}/pay', data=data)

    def balance(self, account):
        db.session.expire_all()
        return round(db.session.get(ExpenseAccount, account.id).balance, 2)

    # ── Record Payment ────────────────────────────────────────────────────
    def test_payment_into_account_posts_debit(self):
        r = self.pay(self.s1, 200, self.bank)
        self.assertEqual(r.status_code, 302)
        p = Payment.query.one()
        self.assertEqual(p.expense_account_id, self.bank.id)
        t = ExpenseAccountTransaction.query.one()
        self.assertEqual((t.sale_payment_id, t.entry_type, t.transaction_type, t.amount, t.is_approved),
                         (p.id, 'debit', 'sale_payment', 200, True))
        self.assertEqual(t.customer_id, self.customer.id)
        self.assertIn('INV-1', t.description)
        self.assertEqual(self.balance(self.bank), 1200)          # opening 1000 + 200 in
        self.assertEqual(db.session.get(Sale, self.s1.id).paid_amount, 200)

    def test_account_is_required(self):
        for account in (None, ''):
            self.pay(self.s1, 200, account)
        self.assertEqual(Payment.query.count(), 0)
        self.assertEqual(db.session.get(Sale, self.s1.id).paid_amount, 0)

    def test_lump_sum_alone_needs_no_account(self):
        # No money received -> nothing to put in an account.
        self.pay(self.s1, 0, lump_sum='on', lump_sum_amount='50')
        self.assertEqual(Payment.query.count(), 0)
        self.assertEqual(ExpenseAccountTransaction.query.count(), 0)

    def test_inactive_or_unknown_account_records_nothing(self):
        for bad in (self.closed, '99999'):
            self.pay(self.s1, 200, bad)
        self.assertEqual(Payment.query.count(), 0)
        self.assertEqual(ExpenseAccountTransaction.query.count(), 0)
        self.assertEqual(db.session.get(Sale, self.s1.id).paid_amount, 0)

    def test_overpayment_full_amount_reaches_account(self):
        self.pay(self.s1, 800, self.bank)                        # 300 over the balance
        self.assertEqual(self.balance(self.bank), 1800)
        self.assertEqual(ExpenseAccountTransaction.query.one().amount, 800)

    # ── Universal Pay ─────────────────────────────────────────────────────
    def test_universal_pay_debits_every_portion_and_leftover(self):
        r = self.client.post(f'/sales/customer/{self.customer.id}/universal-pay',
                             data={'amount': '1000', 'payment_method': 'Bank Transfer',
                                   'payment_date': '2026-09-10', 'account_id': str(self.cash.id)})
        self.assertEqual(r.status_code, 302)
        rows = ExpenseAccountTransaction.query.order_by(ExpenseAccountTransaction.id).all()
        self.assertEqual([(t.transaction_type, t.amount) for t in rows],
                         [('sale_payment', 500), ('sale_payment', 300), ('customer_advance', 200)])
        adv = CustomerAdvance.query.one()
        self.assertEqual(rows[2].customer_advance_id, adv.id)
        self.assertEqual(self.balance(self.cash), 1000)          # the whole amount came in
        self.assertTrue(all(p.expense_account_id == self.cash.id for p in Payment.query.all()))

    def test_universal_pay_requires_account(self):
        self.client.post(f'/sales/customer/{self.customer.id}/universal-pay',
                         data={'amount': '600', 'payment_method': 'Bank Transfer', 'payment_date': '2026-09-10'})
        self.assertEqual(Payment.query.count(), 0)
        self.assertEqual(CustomerAdvance.query.count(), 0)

    def test_deleting_the_advance_removes_its_account_row(self):
        self.client.post(f'/sales/customer/{self.customer.id}/universal-pay',
                         data={'amount': '900', 'payment_method': 'Bank Transfer',
                               'payment_date': '2026-09-10', 'account_id': str(self.cash.id)})
        db.session.delete(CustomerAdvance.query.one())
        db.session.commit()
        self.assertEqual(ExpenseAccountTransaction.query.filter_by(transaction_type='customer_advance').count(), 0)
        self.assertEqual(self.balance(self.cash), 800)

    # ── Edit / reject / delete ────────────────────────────────────────────
    def _edit(self, payment, **fields):
        data = {'amount': str(payment.amount), 'payment_date': '2026-09-12', 'payment_method': 'Bank Transfer',
                'payment_notes': ''}
        data.update(fields)
        return self.client.post(f'/sales/invoice/{payment.invoice_id}/payment/{payment.id}/edit', data=data)

    def test_edit_amount_and_move_account(self):
        self.pay(self.s1, 200, self.bank)
        p = Payment.query.one()
        self._edit(p, amount='250', account_id=str(self.cash.id))
        t = ExpenseAccountTransaction.query.one()
        self.assertEqual((t.account_id, t.amount), (self.cash.id, 250))
        self.assertEqual(self.balance(self.bank), 1000)
        self.assertEqual(self.balance(self.cash), 250)
        self.assertEqual(db.session.get(Sale, self.s1.id).paid_amount, 250)

    def test_edit_cannot_clear_the_account(self):
        self.pay(self.s1, 200, self.bank)
        self._edit(Payment.query.one(), amount='999', account_id='')
        db.session.expire_all()
        p = Payment.query.one()
        self.assertEqual((p.amount, p.expense_account_id), (200, self.bank.id))
        self.assertEqual(ExpenseAccountTransaction.query.one().amount, 200)

    def test_edit_form_without_field_keeps_account(self):
        self.pay(self.s1, 200, self.bank)
        self._edit(Payment.query.one(), amount='150')            # no account_id posted
        t = ExpenseAccountTransaction.query.one()
        self.assertEqual((t.account_id, t.amount), (self.bank.id, 150))

    def test_add_account_to_older_payment(self):
        # A payment recorded before this feature has no account.
        db.session.add(Payment(payment_number='PAY-OLD', amount=200, method='Cash', invoice_id=self.s1.id,
                               date=datetime(2026, 9, 2), is_approved=True))
        self.s1.paid_amount = 200
        db.session.commit()
        self._edit(Payment.query.one(), account_id=str(self.bank.id))
        self.assertEqual(self.balance(self.bank), 1200)

    def test_reject_staff_payment_stops_counting(self):
        self.pay(self.s1, 200, self.bank)
        p = Payment.query.one()
        p.needs_approval = True                                   # as if recorded by staff
        db.session.commit()
        self.client.post(f'/sales/invoice/{self.s1.id}/payment/{p.id}/reject', data={'reason': 'wrong'})
        t = ExpenseAccountTransaction.query.one()
        self.assertEqual((t.is_approved, t.is_rejected), (False, True))
        self.assertEqual(self.balance(self.bank), 1000)

    def test_delete_payment_reverses_the_debit(self):
        self.pay(self.s1, 200, self.bank)
        self.assertEqual(self.balance(self.bank), 1200)
        p = Payment.query.one()
        self.client.post(f'/sales/invoice/{self.s1.id}/payment/{p.id}/delete')
        self.assertEqual(ExpenseAccountTransaction.query.count(), 0)
        self.assertEqual(self.balance(self.bank), 1000)           # back to the opening balance
        self.assertEqual(db.session.get(Sale, self.s1.id).paid_amount, 0)

    def test_delete_payment_and_invoice_remove_rows(self):
        self.pay(self.s1, 200, self.bank)
        self.pay(self.s2, 100, self.bank)
        p1 = Payment.query.filter_by(invoice_id=self.s1.id).one()
        self.client.post(f'/sales/invoice/{self.s1.id}/payment/{p1.id}/delete')
        self.assertEqual(self.balance(self.bank), 1100)
        self.client.post(f'/sales/invoice/{self.s2.id}/delete')
        self.assertEqual(ExpenseAccountTransaction.query.count(), 0)
        self.assertEqual(self.balance(self.bank), 1000)

    def test_account_screens_refuse_to_edit_or_delete_the_row(self):
        self.pay(self.s1, 200, self.bank)
        t = ExpenseAccountTransaction.query.one()
        r = self.client.post(f'/accounting/expense-accounts/transaction/{t.id}/edit-quick',
                             data={'account_id': str(self.cash.id), 'amount': '5'})
        self.assertFalse(r.get_json()['success'])
        db.session.expire_all()
        self.assertEqual(ExpenseAccountTransaction.query.one().amount, 200)

    # ── Pages ─────────────────────────────────────────────────────────────
    def test_invoice_page_offers_accounts(self):
        self.pay(self.s1, 200, self.bank)
        html = self.client.get(f'/sales/invoice/{self.s1.id}').get_data(as_text=True)
        self.assertIn('name="account_id"', html)
        self.assertIn('Meezan Bank (Bank)', html)
        self.assertNotIn('>Old Account', html)                    # inactive accounts are not offered
        self.assertIn('fa-wallet me-1"></i>Meezan Bank', html)    # shown in Payment History

    def test_accounts_json_for_universal_pay(self):
        data = self.client.get('/sales/receipt-accounts-json').get_json()
        self.assertEqual([a['name'] for a in data['accounts']], ['Cash Box', 'Meezan Bank'])

    def test_account_activity_shows_invoice_payment(self):
        self.pay(self.s1, 200, self.bank)
        html = self.client.get(f'/accounting/expenses/account-activity?account_id={self.bank.id}&date_from=2026-01-01&date_to=2026-12-31').get_data(as_text=True)
        self.assertIn('Invoice Payment', html)
        self.assertIn('INV-1', html)


if __name__ == '__main__':
    unittest.main()
