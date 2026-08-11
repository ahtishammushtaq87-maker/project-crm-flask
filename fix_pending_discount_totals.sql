-- =====================================================================
-- LIVE DATA FIX (SQLite)  —  pending invoices whose stored total still
-- excludes their discount.
--
-- Background: the total used to be calculated with the discount forced to
-- zero while an invoice was unapproved. Now the discount applies as soon
-- as it is entered, so invoices created as PENDING before this change
-- still carry an inflated `total` until they are recalculated.
--
-- PREFERRED METHOD: skip this file and use the app instead —
--   POST /sales/recalculate-all   ("Recalculate Totals" button)
-- It calls Sale.calculate_totals(), which correctly handles returns, the
-- overdue-discount suspension and per-item discounts. The SQL below is a
-- fallback for the simple cases only.
--
-- ALWAYS back up first:
--     cp instance/database.db instance/database.db.bak
-- =====================================================================

-- ---------------------------------------------------------------------
-- STEP 1 — DRY RUN. See exactly which invoices would change.
-- Run this on its own first and read the output.
-- ---------------------------------------------------------------------
SELECT  s.invoice_number,
        s.subtotal,
        s.tax,
        s.delivery_charge,
        s.discount,
        s.total                                                   AS current_total,
        ROUND(s.subtotal + s.tax + s.delivery_charge - s.discount, 2) AS corrected_total,
        ROUND(s.total - (s.subtotal + s.tax + s.delivery_charge - s.discount), 2) AS difference,
        s.paid_amount,
        s.status
FROM    sales s
WHERE   s.discount > 0
  AND   s.is_approved = 0          -- pending only
  AND   s.is_rejected = 0          -- not rejected / cancelled
  AND   s.is_draft    = 0          -- not a draft
  AND   ABS(s.total - (s.subtotal + s.tax + s.delivery_charge - s.discount)) > 0.01
  -- Skip invoices with returns: their totals also fold in return discounts,
  -- so the simple formula above would be wrong. Use the app for those.
  AND   NOT EXISTS (SELECT 1 FROM sale_returns r WHERE r.sale_id = s.id)
ORDER BY s.id;


-- ---------------------------------------------------------------------
-- STEP 2 — apply the correction (same WHERE clause as the dry run).
-- Only run after STEP 1 shows the rows you expect.
-- ---------------------------------------------------------------------
UPDATE sales
SET    total = ROUND(subtotal + tax + delivery_charge - discount, 2)
WHERE  discount > 0
  AND  is_approved = 0
  AND  is_rejected = 0
  AND  is_draft    = 0
  AND  ABS(total - (subtotal + tax + delivery_charge - discount)) > 0.01
  AND  NOT EXISTS (SELECT 1 FROM sale_returns r WHERE r.sale_id = sales.id);


-- ---------------------------------------------------------------------
-- STEP 3 — re-sync payment status for anything the new total affected.
-- paid_amount is untouched, only the paid/partial/unpaid label moves.
-- ---------------------------------------------------------------------
UPDATE sales
SET    status = CASE
                  WHEN paid_amount >= total THEN 'paid'
                  WHEN paid_amount > 0      THEN 'partial'
                  ELSE 'unpaid'
                END
WHERE  is_rejected = 0
  AND  is_draft    = 0
  AND  status <> CASE
                   WHEN paid_amount >= total THEN 'paid'
                   WHEN paid_amount > 0      THEN 'partial'
                   ELSE 'unpaid'
                 END;


-- ---------------------------------------------------------------------
-- STEP 4 — verify: should return no rows.
-- ---------------------------------------------------------------------
SELECT  invoice_number,
        total,
        ROUND(subtotal + tax + delivery_charge - discount, 2) AS expected
FROM    sales
WHERE   discount > 0
  AND   is_approved = 0 AND is_rejected = 0 AND is_draft = 0
  AND   ABS(total - (subtotal + tax + delivery_charge - discount)) > 0.01
  AND   NOT EXISTS (SELECT 1 FROM sale_returns r WHERE r.sale_id = sales.id);
