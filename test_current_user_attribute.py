#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test the exact line that's failing: current_user.id in a request context
"""
from app import create_app
from flask_login import current_user

app = create_app()

print("\n" + "="*80)
print("TEST: current_user.id access")
print("="*80)

# Test 1: Without request context
print("\n[TEST 1] Without request context:")
try:
    print(f"  Accessing current_user: {current_user}")
    print(f"  Accessing current_user.id: {current_user.id}")
    print("  ✓ Works")
except AttributeError as e:
    print(f"  ✗ AttributeError: {e}")
except Exception as e:
    print(f"  ✗ Error: {type(e).__name__}: {e}")

# Test 2: With test_request_context
print("\n[TEST 2] With test_request_context:")
with app.test_request_context():
    try:
        print(f"  Accessing current_user: {current_user}")
        print(f"  current_user.is_authenticated: {current_user.is_authenticated}")
        print(f"  Accessing current_user.id: {current_user.id}")
        print("  ✓ Works")
    except AttributeError as e:
        print(f"  ✗ AttributeError: {e}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")

# Test 3: Check what happens when accessing .id on AnonymousUserMixin
print("\n[TEST 3] Understanding AnonymousUserMixin:")
with app.test_request_context():
    from flask_login import AnonymousUserMixin
    anon = AnonymousUserMixin()
    print(f"  Type: {type(current_user)}")
    print(f"  Has 'id' attribute: {hasattr(current_user, 'id')}")
    print(f"  Dir: {[x for x in dir(current_user) if not x.startswith('_')]}")
    
    # Check if it has get_id method
    if hasattr(current_user, 'get_id'):
        print(f"  Has get_id method: True")
        try:
            print(f"  get_id(): {current_user.get_id()}")
        except Exception as e:
            print(f"  get_id() error: {e}")

print("\n" + "="*80)
