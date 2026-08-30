"""Backfill: create the auto Expense account for every existing Staff member
who doesn't have one yet.

This only needs to run once, for staff that were added to HR before the
auto-create-on-add feature existed (see _ensure_staff_expense_account in
app/routes/salary.py, wired into add_staff / bulk_upload_staff). New staff
added from now on get their account automatically — this script just closes
the gap for staff added before that.

Safe to run repeatedly: staff that already have a linked account are skipped.

    python backfill_staff_expense_accounts.py
"""
from run import app
from app import db
from app.models import Staff
from app.routes.salary import _ensure_staff_expense_account


def main():
    with app.app_context():
        staff_list = Staff.query.order_by(Staff.name).all()
        created = 0
        skipped = 0
        for staff in staff_list:
            if staff.expense_account:
                skipped += 1
                continue
            account = _ensure_staff_expense_account(staff)
            if account:
                created += 1
                print(f'  + created account "{account.name}" for staff "{staff.name}"')
        db.session.commit()
        print(f'Done — {created} account(s) created, {skipped} staff already had one.')


if __name__ == '__main__':
    main()
