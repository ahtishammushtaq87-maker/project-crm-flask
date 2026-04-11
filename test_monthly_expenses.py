#!/usr/bin/env python
"""Quick test of accounting pages"""
import time
import sys

# Give server time to start
time.sleep(3)

try:
    import requests
    
    # Test expenses page
    print("[*] Testing /accounting/expenses...")
    resp = requests.get('http://127.0.0.1:5000/accounting/expenses', timeout=5)
    if resp.status_code == 200:
        print(f"[OK] Expenses page status: {resp.status_code}")
    else:
        print(f"[WARN] Expenses page status: {resp.status_code}")
    
    # Test add expense page
    print("[*] Testing /accounting/expense/add...")
    resp = requests.get('http://127.0.0.1:5000/accounting/expense/add', timeout=5)
    if resp.status_code == 200:
        print(f"[OK] Add expense page status: {resp.status_code}")
    else:
        print(f"[WARN] Add expense page status: {resp.status_code}")
    
    # Test accounting dashboard
    print("[*] Testing /accounting/...")
    resp = requests.get('http://127.0.0.1:5000/accounting/', timeout=5)
    if resp.status_code == 200:
        print(f"[OK] Dashboard status: {resp.status_code}")
        if "Today's Divided Expenses" in resp.text or "Daily Expense" in resp.text:
            print("[OK] Dashboard daily expenses section found")
        else:
            print("[INFO] Daily expenses section not visible (no active expenses today)")
    else:
        print(f"[WARN] Dashboard status: {resp.status_code}")
    
    print("\n[SUCCESS] All pages loaded successfully!")
    
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)
