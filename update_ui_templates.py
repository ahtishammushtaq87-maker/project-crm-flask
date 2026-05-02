import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match the form-check div containing a can_view_xxx
    # We use a callable to construct the replacement
    def replacer(match):
        full_match = match.group(0)
        mb_class = match.group(1) # e.g. " mb-2" or ""
        module_name = match.group(2) # e.g. "sales"
        label_text_code = match.group(3) # e.g. "Returns Access" or "{{ form.can_view_sales.label.text }}"
        
        replacement = f"""<div class="form-check{mb_class}">
    {{{{ form.can_view_{module_name}(class="form-check-input view-toggle", onchange="toggleSubPermissions(this, '{module_name}')") }}}}
    <label class="form-check-label fw-semibold">{label_text_code}</label>
    <div class="ms-4 mt-1 border-start ps-3 sub-permissions-{module_name}" id="sub_{module_name}">
        <div class="form-check form-check-inline">
            {{{{ form.can_add_{module_name}(class="form-check-input sub-cb-{module_name}") }}}} <label class="form-check-label small text-muted">Add</label>
        </div>
        <div class="form-check form-check-inline">
            {{{{ form.can_edit_{module_name}(class="form-check-input sub-cb-{module_name}") }}}} <label class="form-check-label small text-muted">Edit</label>
        </div>
        <div class="form-check form-check-inline">
            {{{{ form.can_delete_{module_name}(class="form-check-input sub-cb-{module_name}") }}}} <label class="form-check-label small text-muted">Delete</label>
        </div>
    </div>
</div>"""
        return replacement

    # Regex explanation:
    # <div class="form-check( mb-2)?">...{{ form.can_view_([a-z_]+)\(class="form-check-input"\) }}...<label.*?>(.*?)</label>...</div>
    pattern = r'<div class="form-check(\s+mb-2)?">\s*\{\{\s*form\.can_view_([a-z_]+)\(class="form-check-input"\)\s*\}\}\s*<label class="form-check-label">(.*?)</label>\s*</div>'
    
    new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    # We also need to add the JavaScript function `toggleSubPermissions` at the end
    script_to_add = """
                        function toggleSubPermissions(checkbox, moduleName) {
                            const subs = document.querySelectorAll('.sub-cb-' + moduleName);
                            subs.forEach(cb => {
                                if (checkbox.checked) {
                                    cb.disabled = false;
                                } else {
                                    cb.checked = false;
                                    cb.disabled = true;
                                }
                            });
                        }
                        
                        // Initialize permissions on load
                        document.addEventListener('DOMContentLoaded', function() {
                            document.querySelectorAll('.view-toggle').forEach(toggle => {
                                const moduleName = toggle.getAttribute('onchange').match(/'([^']+)'/)[1];
                                toggleSubPermissions(toggle, moduleName);
                            });
                        });
"""
    if "function toggleSubPermissions" not in new_content:
        new_content = new_content.replace(
            "function togglePermissions(checked) {",
            script_to_add + "\n                        function togglePermissions(checked) {"
        )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

process_file('app/templates/users/create.html')
process_file('app/templates/users/edit.html')

print("Done updating templates.")
