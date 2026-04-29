# Universal Advanced Filter Implementation TODO

## Phase 1: Core Engine Enhancement
- [x] Add `date_between` operator to filter_engine.py
- [x] Add field registries for all modules and reports
- [x] Update filters.py redirect map for all modules
- [x] Update query_builder.js for `date_between` UI

## Phase 2: Route Integration (Zero Damage Pattern)
- [x] Create `_apply_saved_filter()` safe helper in filters.py
- [x] Integrate into reports.py (10 report routes)
- [x] Integrate into sales.py (invoices, customers)
- [x] Integrate into purchase.py (bills, vendors, POs, purchase returns)
- [x] Integrate into manufacturing.py (boms, orders)
- [x] Integrate into returns.py (sales returns)
- [x] Integrate into production.py (logs)
- [x] Integrate into accounting.py (expenses) - already done

## Phase 3: Template Integration
- [x] Add filter trigger + active badge to all report templates
- [x] Add filter trigger + active badge to all module list templates
- [x] Ensure responsive design across all screens

## Phase 4: Testing
- [x] Syntax check all Python files
- [x] Verify no existing logic damaged

