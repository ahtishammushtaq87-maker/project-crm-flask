import os

# --- Helper for template content ---
def get_customer_form_fields():
    return """
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Customer Name *</label>
                                {{ form.name(class="form-control", placeholder="Enter name") }}
                                {% for error in form.name.errors %}<div class="text-danger small">{{ error }}</div>{% endfor %}
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Company Name</label>
                                {{ form.company_name(class="form-control", placeholder="Employer or Business name") }}
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-12 mb-3">
                                <label class="form-label fw-bold">Customer Group</label>
                                <div class="input-group">
                                    {{ form.group_id(class="form-control select2", id="groupSelect") }}
                                    <button class="btn btn-outline-primary" type="button" data-bs-toggle="modal" data-bs-target="#quickAddGroupModal">
                                        <i class="fas fa-plus"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Email</label>
                                {{ form.email(class="form-control", placeholder="email@example.com") }}
                                {% for error in form.email.errors %}<div class="text-danger small">{{ error }}</div>{% endfor %}
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Phone</label>
                                {{ form.phone(class="form-control", placeholder="Phone number") }}
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-12 mb-3">
                                <label class="form-label fw-bold">GST Number</label>
                                {{ form.gst_number(class="form-control", placeholder="GSTIN") }}
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold">Address</label>
                            {{ form.address(class="form-control", rows=3, placeholder="Full address") }}
                        </div>
                        <div class="mb-4">
                            <label class="form-label fw-bold">Payment Method (Optional)</label>
                            {{ form.payment_method(class="form-control", placeholder="e.g. Cash, Bank Transfer") }}
                        </div>
"""

def get_js_and_modal():
    return """
{% block extra_css %}
<link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.min.css" />
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
<script>
$(document).ready(function() {
    $('.select2').select2({
        theme: 'bootstrap-5',
        width: '100%'
    });

    $('#saveGroupBtn').on('click', function() {
        const name = $('#newGroupName').val();
        if (!name) return alert('Name is required');
        
        $.post("{{ url_for('sales.quick_add_customer_group') }}", { name: name }, function(data) {
            if (data.success) {
                const newOption = new Option(data.group.name, data.group.id, true, true);
                $('#groupSelect').append(newOption).trigger('change');
                $('#quickAddGroupModal').modal('hide');
                $('#newGroupName').val('');
            } else {
                alert(data.message);
            }
        });
    });
});
</script>

<div class="modal fade" id="quickAddGroupModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Quick Add Group</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <label class="form-label">Group Name</label>
                    <input type="text" id="newGroupName" class="form-control" placeholder="Enter name">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" id="saveGroupBtn">Save Group</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

# Patch add_customer.html
add_path = 'app/templates/sales/add_customer.html'
with open(add_path, 'w') as f:
    f.write('{% extends "base.html" %}\n' +
            '{% block title %}Add Customer{% endblock %}\n' +
            get_js_and_modal() +
            '\n{% block content %}\n' +
            '<div class="container-fluid">\n' +
            '    <div class="row justify-content-center">\n' +
            '        <div class="col-md-8">\n' +
            '            <div class="card shadow-sm border-0">\n' +
            '                <div class="card-header bg-white py-3"><h4>Add New Customer</h4></div>\n' +
            '                <div class="card-body p-4">\n' +
            '                    <form method="POST">\n' +
            '                        {{ form.hidden_tag() }}\n' +
            get_customer_form_fields() +
            '                        <div class="d-flex gap-2">\n' +
            '                            <button type="submit" class="btn btn-primary px-4"><i class="fas fa-save me-1"></i> Save Customer</button>\n' +
            '                            <a href="{{ url_for(\'sales.customers\') }}" class="btn btn-outline-secondary px-4"><i class="fas fa-times me-1"></i> Cancel</a>\n' +
            '                        </div>\n' +
            '                    </form>\n' +
            '                </div>\n' +
            '            </div>\n' +
            '        </div>\n' +
            '    </div>\n' +
            '</div>\n{% endblock %}\n')

# Patch edit_customer.html
edit_path = 'app/templates/sales/edit_customer.html'
with open(edit_path, 'w') as f:
    f.write('{% extends "base.html" %}\n' +
            '{% block title %}Edit Customer{% endblock %}\n' +
            get_js_and_modal() +
            '\n{% block content %}\n' +
            '<div class="container-fluid">\n' +
            '    <div class="row justify-content-center">\n' +
            '        <div class="col-md-8">\n' +
            '            <div class="card shadow-sm border-0">\n' +
            '                <div class="card-header bg-white py-3"><h4 class="mb-0">Edit Customer: {{ customer.name }}</h4></div>\n' +
            '                <div class="card-body p-4">\n' +
            '                    <form method="POST">\n' +
            '                        {{ form.hidden_tag() }}\n' +
            get_customer_form_fields() +
            '                        <div class="d-flex gap-2">\n' +
            '                            <button type="submit" class="btn btn-primary px-4"><i class="fas fa-save me-1"></i> Update Customer</button>\n' +
            '                            <a href="{{ url_for(\'sales.customers\') }}" class="btn btn-outline-secondary px-4"><i class="fas fa-times me-1"></i> Cancel</a>\n' +
            '                        </div>\n' +
            '                    </form>\n' +
            '                </div>\n' +
            '            </div>\n' +
            '        </div>\n' +
            '    </div>\n' +
            '</div>\n{% endblock %}\n')

print("Successfully updated customer forms")
