from app import create_app
from app.models import Product, Expense, BOM
import os

app = create_app()
with app.app_context():
    print("--- Products ---")
    products = Product.query.filter_by(is_manufactured=True).all()
    for p in products:
        expenses = Expense.query.filter_by(product_id=p.id, is_bom_overhead=True).all()
        total_exp = sum(e.amount for e in expenses)
        print(f"ID: {p.id}, Name: {p.name}, Manufactured: {p.is_manufactured}, Total Actual Overhead: {total_exp}")
        for e in expenses:
            print(f"  - Expense: {e.expense_number}, Amount: {e.amount}, Category ID: {e.category_id}")

    print("\n--- BOMs ---")
    boms = BOM.query.all()
    for b in boms:
        print(f"BOM ID: {b.id}, Name: {b.name}, Product ID: {b.product_id}, Overhead: {b.overhead_cost}")
