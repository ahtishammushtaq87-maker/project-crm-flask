from app import create_app, db
from app.models import Staff, SalaryAdvance, SalaryPayment
from datetime import datetime

app = create_app()
with app.app_context():
    try:
        # 1. Add a test staff
        test_staff = Staff(
            name="Test Employee",
            designation="Tester",
            monthly_salary=50000,
            joining_date=datetime.utcnow().date()
        )
        db.session.add(test_staff)
        db.session.commit()
        print(f"Created staff: {test_staff.name}")

        # 2. Add an advance
        advance = SalaryAdvance(
            staff_id=test_staff.id,
            amount=5000,
            date=datetime.utcnow().date(),
            description="Emergency Advance"
        )
        db.session.add(advance)
        db.session.commit()
        print(f"Recorded advance: {advance.amount} for {test_staff.name}")

        # 3. Process Salary
        net_salary = test_staff.monthly_salary - 5000 # Deducting advance
        payment = SalaryPayment(
            staff_id=test_staff.id,
            month=datetime.utcnow().month,
            year=datetime.utcnow().year,
            base_salary=test_staff.monthly_salary,
            advance_deduction=5000,
            net_salary=net_salary,
            payment_date=datetime.utcnow().date(),
            status='paid'
        )
        db.session.add(payment)
        db.session.flush()

        # Mark advance as deducted
        advance.is_deducted = True
        advance.salary_payment_id = payment.id
        
        db.session.commit()
        print(f"Processed salary: Net {net_salary} for {test_staff.name}")
        print("Verification successful!")

        # Cleanup (Optional, but good for testing)
        db.session.delete(payment)
        db.session.delete(advance)
        db.session.delete(test_staff)
        db.session.commit()
        print("Cleanup complete.")

    except Exception as e:
        db.session.rollback()
        print(f"Verification failed: {e}")
