import os

path = 'app/templates/sales/create_invoice.html'
with open(path, 'r') as f:
    content = f.read()

script_to_add = """
    $('#saveSalesmanBtn').on('click', function() {
        const name = $('#newSalesmanName').val();
        if (!name) return alert('Name is required');
        
        $.post("{{ url_for('sales.quick_add_salesman') }}", { name: name }, function(data) {
            if (data.success) {
                const newOption = new Option(data.salesman.name, data.salesman.id, true, true);
                $('#salesmanSelect').append(newOption).trigger('change');
                $('#quickAddSalesmanModal').modal('hide');
                $('#newSalesmanName').val('');
            } else {
                alert(data.message);
            }
        });
    });
"""

modal_to_add = """
<!-- Quick Add Salesman Modal -->
<div class="modal fade" id="quickAddSalesmanModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Quick Add Salesman</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <label class="form-label">Salesman Name</label>
                    <input type="text" id="newSalesmanName" class="form-control" placeholder="Enter name">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" id="saveSalesmanBtn">Save Salesman</button>
            </div>
        </div>
    </div>
</div>
"""

if script_to_add not in content:
    content = content.replace("});\n</script>", script_to_add + "});\n</script>")

if "quickAddSalesmanModal" not in content:
    content = content.replace("{% endblock %}", modal_to_add + "{% endblock %}")

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated create_invoice.html")
