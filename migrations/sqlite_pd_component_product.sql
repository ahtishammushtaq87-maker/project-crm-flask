-- Product Development components: link each component to its inventory item
-- so the Materials & Components table can show SKU and item category.
-- The app adds the column automatically at startup; the backfill UPDATE links
-- components saved before this change by matching the item name.
-- Manual apply:  sqlite3 instance/database.db < migrations/sqlite_pd_component_product.sql

ALTER TABLE pd_components ADD COLUMN product_id INTEGER REFERENCES products(id);

CREATE INDEX IF NOT EXISTS ix_pd_components_product_id ON pd_components (product_id);

UPDATE pd_components
SET product_id = (SELECT p.id FROM products p WHERE p.name = pd_components.component_name ORDER BY p.id LIMIT 1)
WHERE product_id IS NULL;
