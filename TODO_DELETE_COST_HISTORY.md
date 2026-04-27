# TODO: Add Delete Button to Cost Price History

## Plan
1. ✅ Add safe delete API endpoint in `app/routes/purchase.py`
2. ✅ Add delete button and JavaScript in `app/templates/inventory/products.html`
3. ✅ Test the implementation

## Safety Checks
- ✅ Block deletion if `BOMItem` references the history entry via `cost_price_history_id`
- ✅ Confirm dialog before deletion
- ✅ Refresh modal after successful deletion

## Implementation Complete
- New endpoint: `POST /purchase/api/cost-history/<int:history_id>/delete`
- Deletes history entry only if NOT referenced by any BOMItem
- UI: Red trash icon button in Actions column of history table
- JS: `deleteCostHistory()` with confirmation, API call, and modal refresh

