"""
Product Development Module - Test Script
This script creates sample data to demonstrate the full functionality
"""
from app import create_app, db
from app.models import PDProject, PDProjectBOM, PDComponent, PDTooling, PDTesting, PDApproval, PDAsset, Product, Vendor
from datetime import date

app = create_app()

with app.app_context():
    # Check if test project already exists
    existing = PDProject.query.filter_by(pdv_code='PDV-2026-0001').first()
    if existing:
        print("=" * 50)
        print("Test project already exists!")
        print("=" * 50)
        print(f"Project: {existing.pdv_code} - {existing.product_name}")
        print(f"Status: {existing.status}, Phase: {existing.current_phase}")
        print(f"Total Investment: PKR {existing.total_investment:,.0f}")
        print(f"BOM Items: {len(existing.bom_items)}")
        print(f"Components: {len(existing.components)}")
        print(f"Tooling: {len(existing.tooling)}")
        print(f"Testing: {len(existing.testing)}")
        print(f"Approval: {existing.approval.approval_status if existing.approval else 'N/A'}")
        exit()

    print("Creating test data for Product Development Module...")
    print("=" * 50)

    # Get some vendors for testing
    vendors = Vendor.query.limit(3).all()
    if not vendors:
        print("No vendors found. Creating sample vendor...")
        vendor = Vendor(name="Test Vendor Co.", email="test@vendor.com", phone="+92-300-1234567", is_active=True)
        db.session.add(vendor)
        db.session.commit()
        vendors = [vendor]

    # ==================== STEP 1: Create Project ====================
    print("\n[Step 1] Creating Project...")
    project = PDProject(
        pdv_code='PDV-2026-0001',
        product_name='Adjuster Pulley',
        start_date=date(2026, 1, 1),
        promise_date=date(2026, 6, 30),
        budget=500000,
        status='Active',
        current_phase=1,
        description='Development of new adjuster pulley for automotive application'
    )
    db.session.add(project)
    db.session.commit()
    
    # Create initial approval
    approval = PDApproval(project_id=project.id, approval_status='Pending')
    db.session.add(approval)
    db.session.commit()
    print(f"   Created: {project.pdv_code} - {project.product_name}")
    print(f"   Budget: PKR {project.budget:,.0f}")

    # ==================== STEP 2: Add BOM Items ====================
    print("\n[Step 2] Adding BOM Items (Phase 1: BOM)...")
    bom_items = [
        PDProjectBOM(project_id=project.id, material_name='Steel Rod 10mm', quantity_per_unit=2, estimated_cost=150),
        PDProjectBOM(project_id=project.id, material_name='Bearing 6204', quantity_per_unit=2, estimated_cost=200),
        PDProjectBOM(project_id=project.id, material_name='Aluminum Casting', quantity_per_unit=1, estimated_cost=350),
        PDProjectBOM(project_id=project.id, material_name='Rubber Belt', quantity_per_unit=1, estimated_cost=50),
    ]
    for item in bom_items:
        db.session.add(item)
    db.session.commit()
    print(f"   Added {len(bom_items)} BOM items")
    print(f"   Total BOM Cost: PKR {project.total_bom_cost:,.0f}")

    # ==================== STEP 3: Add Components ====================
    print("\n[Step 3] Adding Components (Phase 2: Components)...")
    components = [
        PDComponent(project_id=project.id, component_name='Main Shaft', component_type='MAKE', quantity=100, estimated_cost=250, vendor_id=vendors[0].id),
        PDComponent(project_id=project.id, component_name='Pulley Wheel', component_type='BUY', quantity=100, estimated_cost=180, vendor_id=vendors[0].id),
        PDComponent(project_id=project.id, component_name='Bearing Assembly', component_type='OUTSOURCE', quantity=100, estimated_cost=300, vendor_id=vendors[0].id),
    ]
    for comp in components:
        db.session.add(comp)
    db.session.commit()
    print(f"   Added {len(components)} components")
    print(f"   Total Component Cost: PKR {project.total_component_cost:,.0f}")

    # ==================== STEP 4: Add Tooling ====================
    print("\n[Step 4] Adding Tooling (Phase 3: Tooling)...")
    tooling = [
        PDTooling(project_id=project.id, tool_name='Casting Mold', tool_type='mold', quantity=1, vendor_id=vendors[0].id, cost=85000, status='In Progress'),
        PDTooling(project_id=project.id, tool_name='Machining Jig', tool_type='jig', quantity=2, vendor_id=vendors[0].id, cost=45000, status='Planned'),
        PDTooling(project_id=project.id, tool_name='Press Die', tool_type='die', quantity=1, vendor_id=vendors[0].id, cost=120000, status='Planned'),
    ]
    for tool in tooling:
        db.session.add(tool)
    db.session.commit()
    print(f"   Added {len(tooling)} tooling items")
    print(f"   Total Tooling Cost: PKR {project.total_tooling_cost:,.0f}")

    # ==================== STEP 5: Add Testing/Trials ====================
    print("\n[Step 5] Adding Testing Records (Phase 4: Testing)...")
    testing = [
        PDTesting(project_id=project.id, trial_number=1, trial_date=date(2026, 3, 15), quantity_produced=50, rejected_quantity=8, test_type='Functional', result='PASS'),
        PDTesting(project_id=project.id, trial_number=2, trial_date=date(2026, 4, 1), quantity_produced=80, rejected_quantity=5, test_type='Dimensional', result='PASS'),
    ]
    for test in testing:
        db.session.add(test)
    db.session.commit()
    print(f"   Added {len(testing)} trial records")
    latest_test = PDTesting.query.filter_by(project_id=project.id).order_by(PDTesting.trial_number.desc()).first()
    print(f"   Latest: T{latest_test.trial_number} - Pass Rate: {latest_test.pass_rate}%")

    # ==================== STEP 6: Update Approval ====================
    print("\n[Step 6] Updating Approval (Phase 5: Approval)...")
    approval.approval_status = 'Approved'
    approval.remarks = 'All trials passed. Ready for production.'
    db.session.commit()
    print(f"   Status: {approval.approval_status}")
    print(f"   Remarks: {approval.remarks}")

    # ==================== SUMMARY ====================
    print("\n" + "=" * 50)
    print("PROJECT SUMMARY")
    print("=" * 50)
    print(f"PDV Code       : {project.pdv_code}")
    print(f"Product        : {project.product_name}")
    print(f"Status         : {project.status}")
    print(f"Current Phase  : {project.current_phase} - {project.phase_name}")
    print(f"\n--- Financials ---")
    print(f"Budget              : PKR {project.budget:,.0f}")
    print(f"Total Investment    : PKR {project.total_investment:,.0f}")
    print(f"  - BOM Cost        : PKR {project.total_bom_cost:,.0f}")
    print(f"  - Component Cost  : PKR {project.total_component_cost:,.0f}")
    print(f"  - Tooling Cost    : PKR {project.total_tooling_cost:,.0f}")
    print(f"Budget vs Actual    : PKR {project.budget_vs_actual:,.0f}")
    print(f"\n--- Deliverables ---")
    print(f"BOM Items       : {len(bom_items)}")
    print(f"Components      : {len(components)}")
    print(f"Tooling         : {len(tooling)}")
    print(f"Testing Trials  : {len(testing)}")
    print("\n" + "=" * 50)
    print("Test Data Created Successfully!")
    print("=" * 50)
    print("\nNow you can:")
    print("1. Go to Product Development module")
    print("2. View the 'Adjuster Pulley' project")
    print("3. See all 6 phases with data")
    print("4. Complete Phase 6 to activate production")