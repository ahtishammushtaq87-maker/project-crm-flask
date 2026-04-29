# Universal Advanced Filter Fix – Implementation Steps

## Phase A – Fix `query_builder.js` date_between UI
- [ ] 1. Fix `loadFilterById` to pass raw array for date_between instead of joining
- [ ] 2. Fix `addRuleRow` to populate `.ufm-rule-value-from` and `.ufm-rule-value-to`
- [ ] 3. Widen value column / shrink remove button to prevent overlap

## Phase B – Integrate into report routes (`reports.py`)
- [ ] 4. `inventory_report` → module `inventory_report`
- [ ] 5. `expense_report` → module `expense_report`
- [ ] 6. `return_report` → module `return_report`
- [ ] 7. `vendor_report` → module `vendor_report`
- [ ] 8. `customer_report` → module `customer_report`
- [ ] 9. `manufacturing_report` → module `manufacturing_report`
- [ ] 10. `bom_report` → module `bom_report`
- [ ] 11. `salary_report` → module `salary_report`

## Phase C – Integrate into module list routes
- [ ] 12. `sales.py` → `invoices` (module `sale`)
- [ ] 13. `sales.py` → `customers` (module `customer`)
- [ ] 14. `purchase.py` → `bills` (module `purchase`)
- [ ] 15. `purchase.py` → `vendors` (module `vendor`)
- [ ] 16. `purchase.py` → `purchase_orders` (module `purchase_order`)
- [ ] 17. `purchase.py` → `purchase_return_list` (module `purchase_return`)
- [ ] 18. `returns.py` → `return_list` (module `sale_return`)
- [ ] 19. `inventory.py` → `products` (module `product`)

## Phase D – Clean up `accounting.py`
- [ ] 20. Replace inline raw filter in `expenses()` with `apply_saved_filter_to_query`
- [ ] 21. Pass `active_module='expense'` and `filter_id` to template

## Phase E – Verification
- [ ] 22. Python syntax check all modified `.py` files

