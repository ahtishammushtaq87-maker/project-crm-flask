-- Speed: indexes on foreign-key columns used by list pages / joins.
-- Safe to re-run (IF NOT EXISTS). Names match SQLAlchemy's ix_<table>_<column>
-- so they line up with index=True on the models.
CREATE INDEX IF NOT EXISTS ix_payments_invoice_id                    ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS ix_payments_expense_id                    ON payments(expense_id);
CREATE INDEX IF NOT EXISTS ix_tasks_assigned_to_id                   ON tasks(assigned_to_id);
CREATE INDEX IF NOT EXISTS ix_tasks_created_by_id                    ON tasks(created_by_id);
CREATE INDEX IF NOT EXISTS ix_tasks_linked_invoice_id                ON tasks(linked_invoice_id);
CREATE INDEX IF NOT EXISTS ix_bom_version_items_component_id         ON bom_version_items(component_id);
CREATE INDEX IF NOT EXISTS ix_recovery_logs_logged_by                ON recovery_logs(logged_by);
CREATE INDEX IF NOT EXISTS ix_expenses_product_id                    ON expenses(product_id);
CREATE INDEX IF NOT EXISTS ix_expenses_warehouse_id                  ON expenses(warehouse_id);
CREATE INDEX IF NOT EXISTS ix_expenses_customer_id                   ON expenses(customer_id);
CREATE INDEX IF NOT EXISTS ix_expense_account_transactions_source_id ON expense_account_transactions(source_id);
