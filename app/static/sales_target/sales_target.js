/* Sales Target module: small progressive enhancements. Every rule is also
   enforced on the server; this only makes the forms friendlier. */
(function () {
    'use strict';

    // ── Filters: auto-submit selects, show custom dates only when needed ──
    var filters = document.getElementById('salesTargetFilters');
    if (filters) {
        var period = filters.querySelector('[name=period]');
        var customs = filters.querySelectorAll('[data-sales-target-custom]');
        var syncCustom = function () {
            customs.forEach(function (el) { el.hidden = period.value !== 'custom'; });
        };
        filters.querySelectorAll('[data-sales-target-autosubmit]').forEach(function (sel) {
            sel.addEventListener('change', function () {
                if (sel === period && period.value === 'custom') { syncCustom(); return; }
                filters.submit();
            });
        });
        syncCustom();
    }

    // ── Delete confirmation modal ──
    var modalEl = document.getElementById('salesTargetDeleteModal');
    if (modalEl && window.bootstrap) {
        var modal = new bootstrap.Modal(modalEl);
        var form = document.getElementById('salesTargetDeleteForm');
        var nameEl = modalEl.querySelector('[data-sales-target-delete-name]');
        document.querySelectorAll('[data-sales-target-delete]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                form.action = btn.getAttribute('data-sales-target-delete');
                nameEl.textContent = btn.getAttribute('data-sales-target-name') || 'this target';
                modal.show();
            });
        });
    }

    // ── Prevent double submission ──
    // Listens on document so it runs after each form's own validation
    // handler and can skip submits that validation already cancelled.
    document.addEventListener('submit', function (e) {
        var f = e.target;
        var btn = f && f.querySelector && f.querySelector('[data-sales-target-once]');
        if (!btn) return;
        if (f.dataset.salesTargetSubmitting === '1') { e.preventDefault(); return; }
        if (e.defaultPrevented) return;
        f.dataset.salesTargetSubmitting = '1';
        btn.disabled = true;
        btn.insertAdjacentHTML('afterbegin', '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>');
    });

    // ── Create / edit form ──
    var targetForm = document.getElementById('salesTargetForm');
    if (!targetForm) return;

    var typeInputs = targetForm.querySelectorAll('input[name=target_type]');
    var sections = targetForm.querySelectorAll('[data-sales-target-show]');
    var currentType = function () {
        var checked = targetForm.querySelector('input[name=target_type]:checked');
        return checked ? checked.value : '';
    };
    var syncType = function () {
        var t = currentType();
        sections.forEach(function (s) { s.hidden = s.getAttribute('data-sales-target-show') !== t; });
    };
    typeInputs.forEach(function (i) { i.addEventListener('change', syncType); });
    syncType();

    // Searchable finished-items picker (Select2 is loaded globally by base.html;
    // without it the plain multi-select still works).
    var itemsSel = targetForm.querySelector('[data-sales-target-items]');
    if (itemsSel && window.jQuery && jQuery.fn.select2) {
        jQuery(itemsSel).select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: itemsSel.getAttribute('data-placeholder'),
            closeOnSelect: false,
            allowClear: true
        });
    }

    // Fill team members from a Salesman Group (adds to the current selection).
    var groupFill = document.getElementById('stGroupFill');
    if (groupFill) {
        groupFill.addEventListener('change', function () {
            if (!groupFill.value) return;
            targetForm.querySelectorAll('input[name=member_ids]').forEach(function (cb) {
                if (cb.getAttribute('data-group') === groupFill.value) cb.checked = true;
            });
            groupFill.value = '';
        });
    }

    // Closed targets: locked fields unlock when the status is set back to
    // Draft/Active (disabled inputs aren't submitted, so they must be enabled).
    var statusSel = document.getElementById('stStatusField');
    // Coloured dot next to the status (green Active, grey Draft, ...).
    if (statusSel && statusSel.parentElement.hasAttribute('data-status')) {
        statusSel.addEventListener('change', function () {
            statusSel.parentElement.setAttribute('data-status', statusSel.value);
        });
    }
    if (statusSel && statusSel.getAttribute('data-sales-target-locked-status') === 'true') {
        statusSel.addEventListener('change', function () {
            var unlock = statusSel.value === 'draft' || statusSel.value === 'active';
            targetForm.querySelectorAll('[data-sales-target-lockable]').forEach(function (el) {
                el.disabled = !unlock;
            });
        });
    }

    // Client-side checks mirroring the server rules.
    targetForm.addEventListener('submit', function (e) {
        var problems = [];
        var mark = function (el, bad) { if (el) el.classList.toggle('is-invalid', bad); };
        var name = targetForm.querySelector('[name=name]');
        mark(name, !name.value.trim());
        if (!name.value.trim()) problems.push('Enter a target name.');

        var amount = targetForm.querySelector('[name=target_amount]');
        if (!amount.disabled) {
            var v = parseFloat(amount.value);
            var bad = !(v > 0);
            mark(amount, bad);
            if (bad) problems.push('Target amount must be greater than zero.');

            var start = targetForm.querySelector('[name=start_date]');
            var end = targetForm.querySelector('[name=end_date]');
            var badRange = !start.value || !end.value || end.value < start.value;
            mark(end, badRange);
            if (badRange) problems.push('Choose a start date and an end date that is not before it.');

            var t = currentType();
            if (!t) problems.push('Choose a target type.');
            if (t === 'individual') {
                var sm = targetForm.querySelector('[name=salesman_id]');
                mark(sm, !sm.value);
                if (!sm.value) problems.push('Choose the salesman this target is for.');
            }
            if (t === 'team') {
                var n = targetForm.querySelectorAll('input[name=member_ids]:checked').length;
                var box = targetForm.querySelector('.sales-target-members');
                if (box) box.classList.toggle('is-invalid', n < 2);
                if (n < 2) problems.push('Choose at least two salesmen for a team target.');
            }
        }
        if (problems.length) {
            e.preventDefault();
            var first = targetForm.querySelector('.is-invalid');
            if (first && first.focus) first.focus();
            alert(problems.join('\n'));
        }
    });
})();
