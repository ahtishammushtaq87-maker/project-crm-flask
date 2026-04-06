from app import create_app, db
from app.models import SalaryPayment, Staff
from flask import url_for

app = create_app()
with app.app_context():
    try:
        # Check if the salary-report route exists
        with app.test_request_context():
            report_url = url_for('reports.salary_report')
            download_pdf_url = url_for('reports.download_report', format='pdf', report_type='salary')
            print(f"Salary Report URL: {report_url}")
            print(f"Download PDF URL: {download_pdf_url}")
            
        print("Verification of URLs successful!")
    except Exception as e:
        print(f"Verification failed: {e}")
