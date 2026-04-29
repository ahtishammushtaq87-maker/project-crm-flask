/**
 * Universal Query Builder — Dynamic Filter Modal Controller
 * Works with Bootstrap 5 + jQuery
 */

(function ($) {
    'use strict';

    const QB = {
        currentModule: null,
        fields: [],
        savedFilters: [],
        ruleCounter: 0,
        apiBase: '/api/filters',

        // Operator definitions per field type
        operators: {
            string: [
                { key: 'equal', label: 'Equals' },
                { key: 'not_equal', label: 'Not Equals' },
                { key: 'contains', label: 'Contains' },
                { key: 'not_contains', label: 'Not Contains' },
                { key: 'begins_with', label: 'Begins With' },
                { key: 'ends_with', label: 'Ends With' },
                { key: 'in', label: 'In List' },
                { key: 'not_in', label: 'Not In List' }
            ],
            number: [
                { key: 'equal', label: '=' },
                { key: 'not_equal', label: '!=' },
                { key: '>', label: '>' },
                { key: '<', label: '<' },
                { key: '>=', label: '>=' },
                { key: '<=', label: '<=' },
                { key: 'in', label: 'In List' },
                { key: 'not_in', label: 'Not In List' }
            ],
            date: [
                { key: 'equal', label: 'Equals' },
                { key: 'not_equal', label: 'Not Equals' },
                { key: 'date_between', label: 'Between (From → To)' },
                { key: '>', label: 'After' },
                { key: '<', label: 'Before' },
                { key: '>=', label: 'On or After' },
                { key: '<=', label: 'On or Before' }
            ],
            boolean: [
                { key: 'equal', label: 'Is' },
                { key: 'not_equal', label: 'Is Not' }
            ]
        },

        init: function () {
            QB.bindEvents();
        },

        bindEvents: function () {
            // Modal show — detect module and load fields
            $('#universalFilterModal').on('show.bs.modal', function () {
                QB.detectModule();
                if (QB.currentModule) {
                    QB.loadFields(QB.currentModule);
                    QB.loadSavedFilters(QB.currentModule);
                }
            });

            // Modal hidden — reset state optionally (keep rules for UX)
            // $('#universalFilterModal').on('hidden.bs.modal', function () { QB.clearRules(); });

            $('#ufm-btn-add-rule').on('click', function () {
                QB.addRuleRow();
            });

            $('#ufm-btn-clear').on('click', function () {
                QB.clearRules();
                QB.showMessage('Rules cleared', 'info');
            });

            $('#ufm-btn-save-toggle').on('click', function () {
                $('#ufm-save-panel').removeClass('d-none');
                $('#ufm-save-name').focus();
            });

            $('#ufm-btn-cancel-save').on('click', function () {
                $('#ufm-save-panel').addClass('d-none');
                $('#ufm-save-name').val('');
            });

            $('#ufm-btn-confirm-save').on('click', function () {
                QB.saveFilter();
            });

            $('#ufm-btn-apply').on('click', function () {
                QB.applyFilter();
            });

            $('#ufm-saved-filters').on('change', function () {
                const filterId = $(this).val();
                if (filterId) {
                    QB.loadFilterById(parseInt(filterId, 10));
                    $('#ufm-btn-delete-saved').removeClass('d-none');
                } else {
                    $('#ufm-btn-delete-saved').addClass('d-none');
                }
            });

            $('#ufm-btn-delete-saved').on('click', function () {
                const filterId = $('#ufm-saved-filters').val();
                if (filterId) {
                    QB.deleteFilter(parseInt(filterId, 10));
                }
            });

            // Delegated events for dynamic rows
            $('#ufm-rules-container').on('change', '.ufm-rule-field', function () {
                const row = $(this).closest('.ufm-rule-row');
                QB.updateOperatorsForRow(row);
            });

            $('#ufm-rules-container').on('change', '.ufm-rule-operator', function () {
                const row = $(this).closest('.ufm-rule-row');
                QB.updateValueInputForRow(row);
            });

            $('#ufm-rules-container').on('click', '.ufm-rule-remove', function () {
                $(this).closest('.ufm-rule-row').remove();
                if ($('.ufm-rule-row').length === 0) {
                    QB.addRuleRow(); // keep at least one
                }
            });
        },

        detectModule: function () {
            // Priority 1: trigger button data-module
            const triggerBtn = $('#universal-filter-trigger-btn');
            let mod = triggerBtn.attr('data-module');

            // Priority 2: page-level context div
            if (!mod) {
                mod = $('#module-context').attr('data-module');
            }

            // Priority 3: body data-module
            if (!mod) {
                mod = $('body').attr('data-module');
            }

            QB.currentModule = (mod || '').toLowerCase().trim();
            $('#ufm-module-label').text(QB.currentModule || 'none');
        },

        loadFields: function (module) {
            $.getJSON(QB.apiBase + '/fields?module=' + encodeURIComponent(module))
                .done(function (res) {
                    if (res.success) {
                        QB.fields = res.fields || [];
                        QB.renderInitialRule();
                    } else {
                        QB.showMessage(res.message || 'Failed to load fields', 'danger');
                    }
                })
                .fail(function () {
                    QB.showMessage('Error loading field metadata', 'danger');
                });
        },

        loadSavedFilters: function (module) {
            $.getJSON(QB.apiBase + '/?module=' + encodeURIComponent(module))
                .done(function (res) {
                    const sel = $('#ufm-saved-filters');
                    sel.empty().append('<option value="">-- Saved Filters --</option>');
                    QB.savedFilters = [];
                    if (res.success && res.filters) {
                        QB.savedFilters = res.filters;
                        res.filters.forEach(function (f) {
                            sel.append('<option value="' + f.id + '">' + QB.escapeHtml(f.name) + '</option>');
                        });
                    }
                    $('#ufm-btn-delete-saved').addClass('d-none');
                });
        },

        renderInitialRule: function () {
            $('#ufm-rules-container').empty();
            QB.ruleCounter = 0;
            QB.addRuleRow();
        },

        addRuleRow: function (prefill) {
            QB.ruleCounter++;
            const rid = 'ufm-rule-' + QB.ruleCounter;

            let fieldOptions = '<option value="">-- Field --</option>';
            QB.fields.forEach(function (f) {
                fieldOptions += '<option value="' + f.key + '">' + QB.escapeHtml(f.label) + '</option>';
            });

            const html =
                '<div class="ufm-rule-row" id="' + rid + '">' +
                '  <div class="row g-2">' +
                '    <div class="col-12 col-md-3">' +
                '      <select class="form-select form-select-sm ufm-rule-field">' + fieldOptions + '</select>' +
                '    </div>' +
                '    <div class="col-12 col-md-2">' +
                '      <select class="form-select form-select-sm ufm-rule-operator"></select>' +
                '    </div>' +
                '    <div class="col-12 col-md-6">' +
                '      <div class="ufm-rule-value-wrapper"></div>' +
                '    </div>' +
                '    <div class="col-auto text-md-center">' +
                '      <button type="button" class="ufm-rule-remove" title="Remove rule">' +
                '        <i class="fas fa-times-circle"></i>' +
                '      </button>' +
                '    </div>' +
                '  </div>' +
                '</div>';

            $('#ufm-rules-container').append(html);
            const row = $('#' + rid);

            if (prefill) {
                row.find('.ufm-rule-field').val(prefill.field);
                QB.updateOperatorsForRow(row);
                row.find('.ufm-rule-operator').val(prefill.operator);
                QB.updateValueInputForRow(row);
                if (prefill.operator === 'date_between' && Array.isArray(prefill.value) && prefill.value.length === 2) {
                    row.find('.ufm-rule-value-from').val(prefill.value[0]);
                    row.find('.ufm-rule-value-to').val(prefill.value[1]);
                } else {
                    row.find('.ufm-rule-value').val(prefill.value);
                }
            } else {
                QB.updateOperatorsForRow(row);
            }
        },

        updateOperatorsForRow: function (row) {
            const fieldKey = row.find('.ufm-rule-field').val();
            const opSelect = row.find('.ufm-rule-operator');
            opSelect.empty();

            if (!fieldKey) {
                opSelect.append('<option value="">-- Op --</option>');
                QB.updateValueInputForRow(row);
                return;
            }

            const field = QB.fields.find(function (f) { return f.key === fieldKey; });
            const type = field ? field.type : 'string';
            const ops = QB.operators[type] || QB.operators.string;

            ops.forEach(function (op) {
                opSelect.append('<option value="' + op.key + '">' + QB.escapeHtml(op.label) + '</option>');
            });

            QB.updateValueInputForRow(row);
        },

        updateValueInputForRow: function (row) {
            const fieldKey = row.find('.ufm-rule-field').val();
            const operator = row.find('.ufm-rule-operator').val();
            const wrapper = row.find('.ufm-rule-value-wrapper');

            if (!fieldKey || !operator) {
                wrapper.empty();
                return;
            }

            const field = QB.fields.find(function (f) { return f.key === fieldKey; });
            const type = field ? field.type : 'string';

            let inputHtml = '';

            if (type === 'boolean') {
                inputHtml =
                    '<select class="form-select form-select-sm ufm-rule-value">' +
                    '<option value="true">True</option>' +
                    '<option value="false">False</option>' +
                    '</select>';
            } else if (operator === 'date_between') {
                inputHtml =
                    '<div class="row g-2">' +
                    '<div class="col-6">' +
                    '<input type="date" class="form-control form-control-sm ufm-rule-value-from flex-fill" placeholder="From">' +
                    '</div>' +
                    '<div class="col-6">' +
                    '<input type="date" class="form-control form-control-sm ufm-rule-value-to flex-fill" placeholder="To">' +
                    '</div>' +
                    '</div>';
            } else if (operator === 'in' || operator === 'not_in') {
                inputHtml = '<textarea class="form-control form-control-sm ufm-rule-value" rows="2" placeholder="Comma-separated values"></textarea>';
            } else if (type === 'date') {
                inputHtml = '<input type="date" class="form-control form-control-sm ufm-rule-value">';
            } else if (type === 'number') {
                inputHtml = '<input type="number" step="any" class="form-control form-control-sm ufm-rule-value" placeholder="Value">';
            } else {
                inputHtml = '<input type="text" class="form-control form-control-sm ufm-rule-value" placeholder="Value">';
            }

            wrapper.html(inputHtml);
        },

        clearRules: function () {
            $('#ufm-rules-container').empty();
            QB.ruleCounter = 0;
            QB.addRuleRow();
            $('#ufm-condition-and').prop('checked', true);
            $('#ufm-saved-filters').val('');
            $('#ufm-btn-delete-saved').addClass('d-none');
        },

        buildRulesJson: function () {
            const condition = $('input[name="ufm-condition"]:checked').val() || 'AND';
            const rules = [];
            let hasError = false;

            $('.ufm-rule-row').each(function () {
                const row = $(this);
                const field = row.find('.ufm-rule-field').val();
                const operator = row.find('.ufm-rule-operator').val();
                let value = row.find('.ufm-rule-value').val();

                if (!field || !operator) {
                    return; // skip incomplete
                }

                const fieldMeta = QB.fields.find(function (f) { return f.key === field; });

                // Handle date_between with two inputs
                if (operator === 'date_between') {
                    const fromVal = row.find('.ufm-rule-value-from').val();
                    const toVal = row.find('.ufm-rule-value-to').val();
                    if (!fromVal || !toVal) {
                        hasError = true;
                        row.css('border-color', '#dc3545');
                        return;
                    }
                    value = [fromVal, toVal];
                }

                // Parse value based on type
                if (fieldMeta && fieldMeta.type === 'number') {
                    if (operator === 'in' || operator === 'not_in') {
                        value = value.split(',').map(function (v) { return parseFloat(v.trim()); }).filter(function (v) { return !isNaN(v); });
                    } else if (operator !== 'date_between') {
                        const num = parseFloat(value);
                        value = isNaN(num) ? value : num;
                    }
                } else if (fieldMeta && fieldMeta.type === 'boolean') {
                    value = (value === 'true' || value === true || value === 1 || value === '1');
                } else if (operator === 'in' || operator === 'not_in') {
                    value = value.split(',').map(function (v) { return v.trim(); }).filter(function (v) { return v !== ''; });
                }

                if ((operator === 'in' || operator === 'not_in') && (!Array.isArray(value) || value.length === 0)) {
                    hasError = true;
                    row.css('border-color', '#dc3545');
                } else if (operator === 'date_between' && (!Array.isArray(value) || value.length !== 2)) {
                    hasError = true;
                    row.css('border-color', '#dc3545');
                } else {
                    row.css('border-color', '#dee2e6');
                }

                rules.push({ field: field, operator: operator, value: value });
            });

            if (hasError) {
                return { error: 'Please fill all required values' };
            }

            if (rules.length === 0) {
                return { error: 'Add at least one rule' };
            }

            return { condition: condition, rules: rules };
        },

        applyFilter: function () {
            const rules = QB.buildRulesJson();
            if (rules.error) {
                QB.showMessage(rules.error, 'danger');
                return;
            }

            if (!QB.currentModule) {
                QB.showMessage('Module not detected', 'danger');
                return;
            }

            // Determine redirect URL from current page or data attribute
            let redirectUrl = $('#universal-filter-trigger-btn').attr('data-redirect-url');
            if (!redirectUrl) {
                redirectUrl = window.location.pathname + window.location.search;
            }

            QB.showMessage('Applying filter...', 'info');

            $.ajax({
                url: QB.apiBase + '/apply',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    module: QB.currentModule,
                    rules: rules,
                    redirect_url: redirectUrl
                }),
                success: function (res) {
                    if (res.success && res.redirect_url) {
                        window.location.href = res.redirect_url;
                    } else {
                        QB.showMessage(res.message || 'Apply failed', 'danger');
                    }
                },
                error: function (xhr) {
                    let msg = 'Server error';
                    try {
                        const data = JSON.parse(xhr.responseText);
                        msg = data.message || msg;
                    } catch (e) {}
                    QB.showMessage(msg, 'danger');
                }
            });
        },

        saveFilter: function () {
            const name = $('#ufm-save-name').val().trim();
            if (!name) {
                QB.showMessage('Enter a filter name', 'warning');
                return;
            }

            const rules = QB.buildRulesJson();
            if (rules.error) {
                QB.showMessage(rules.error, 'danger');
                return;
            }

            $.ajax({
                url: QB.apiBase + '/',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    name: name,
                    module: QB.currentModule,
                    rules: rules
                }),
                success: function (res) {
                    if (res.success) {
                        $('#ufm-save-panel').addClass('d-none');
                        $('#ufm-save-name').val('');
                        QB.showMessage('Filter saved', 'success');
                        QB.loadSavedFilters(QB.currentModule);
                    } else {
                        QB.showMessage(res.message || 'Save failed', 'danger');
                    }
                },
                error: function (xhr) {
                    let msg = 'Server error';
                    try {
                        const data = JSON.parse(xhr.responseText);
                        msg = data.message || msg;
                    } catch (e) {}
                    QB.showMessage(msg, 'danger');
                }
            });
        },

        loadFilterById: function (filterId) {
            const f = QB.savedFilters.find(function (item) { return item.id === filterId; });
            if (!f || !f.rules) return;

            // Populate condition
            const condition = (f.rules.condition || 'AND').toUpperCase();
            if (condition === 'OR') {
                $('#ufm-condition-or').prop('checked', true);
            } else {
                $('#ufm-condition-and').prop('checked', true);
            }

            // Populate rules
            $('#ufm-rules-container').empty();
            QB.ruleCounter = 0;
            const rules = f.rules.rules || [];
            if (rules.length === 0) {
                QB.addRuleRow();
            } else {
                rules.forEach(function (r) {
                    QB.addRuleRow({
                        field: r.field,
                        operator: r.operator,
                        value: r.value
                    });
                });
            }

            QB.showMessage('Loaded filter: ' + QB.escapeHtml(f.name), 'info');
        },

        deleteFilter: function (filterId) {
            if (!confirm('Delete this saved filter?')) return;

            $.ajax({
                url: QB.apiBase + '/' + filterId,
                method: 'DELETE',
                success: function (res) {
                    if (res.success) {
                        QB.showMessage('Filter deleted', 'success');
                        QB.loadSavedFilters(QB.currentModule);
                        QB.clearRules();
                    } else {
                        QB.showMessage(res.message || 'Delete failed', 'danger');
                    }
                },
                error: function () {
                    QB.showMessage('Server error during delete', 'danger');
                }
            });
        },

        showMessage: function (text, type) {
            const el = $('#ufm-message');
            el.removeClass('d-none alert-info alert-success alert-warning alert-danger');
            el.addClass('alert-' + type);
            el.text(text);
            el.removeClass('d-none');
            setTimeout(function () {
                el.addClass('d-none');
            }, 4000);
        },

        escapeHtml: function (text) {
            if (text == null) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '<')
                .replace(/>/g, '>')
                .replace(/"/g, '"');
        }
    };

    // Auto-init on DOM ready
    $(document).ready(function () {
        QB.init();
    });

    // Expose globally for debugging / manual trigger
    window.QueryBuilder = QB;

})(jQuery);

