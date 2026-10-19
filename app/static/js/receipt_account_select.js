/* "Received into Account" dropdowns on sales payment forms (Record Payment,
   Edit Payment, Universal Pay). The same searchable account picker the
   Expense form uses (Select2), for <select data-receipt-account>.

   data-source="<url>"  loads the active accounts as JSON the first time the
                        surrounding modal opens (Universal Pay lives in
                        base.html, so its options aren't rendered server-side).
   data-required        the form can't be submitted without an account while
                        an amount is entered (the server enforces the same).
                        Not the native `required`: Select2 hides the real
                        <select>, and a hidden required field blocks the
                        submit without telling the user why.
   Works without Select2 too: it stays a plain dropdown. */
(function () {
    'use strict';

    function hasSelect2() { return !!(window.jQuery && jQuery.fn && jQuery.fn.select2); }

    function enhance(sel) {
        if (!hasSelect2() || sel.dataset.receiptAccountReady === '1') return;
        var modal = sel.closest('.modal');
        // Inside a Bootstrap modal the list must be attached to the modal (or
        // its search box can't take focus) — and to the dialog's CONTENT, not
        // the outer .modal: Select2 opens on mousedown, so when the button
        // comes up over the list, the browser sends the click to the common
        // parent of the two. With the list on the outer .modal that parent is
        // .modal itself, which Bootstrap reads as a backdrop click and closes
        // the whole popup (e.g. Universal Pay). Inside .modal-content the
        // click always stays within the dialog.
        var parent = modal ? (modal.querySelector('.modal-content') || modal) : document.body;
        jQuery(sel).select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: sel.getAttribute('data-placeholder') || '— Select Account —',
            allowClear: !sel.hasAttribute('data-required'),
            dropdownParent: jQuery(parent)
        });
        sel.dataset.receiptAccountReady = '1';
    }

    function fill(sel, accounts) {
        var keep = sel.value;
        while (sel.options.length > 1) sel.remove(1);  // keep the "no account" option
        accounts.forEach(function (a) {
            var opt = document.createElement('option');
            opt.value = a.id;
            opt.textContent = a.name + (a.type ? ' (' + a.type + ')' : '');
            sel.appendChild(opt);
        });
        sel.value = keep;
        if (hasSelect2()) jQuery(sel).trigger('change');
    }

    function load(sel) {
        var url = sel.getAttribute('data-source');
        if (!url || sel.dataset.receiptAccountLoaded === '1') return;
        sel.dataset.receiptAccountLoaded = '1';
        fetch(url, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) { fill(sel, data.accounts || []); })
            .catch(function () { sel.dataset.receiptAccountLoaded = ''; });
    }

    function init(root) {
        (root || document).querySelectorAll('select[data-receipt-account]').forEach(function (sel) {
            var modal = sel.closest('.modal');
            if (modal) {
                // Enhance once the modal is visible, so Select2 measures its width.
                modal.addEventListener('shown.bs.modal', function () { load(sel); enhance(sel); });
            } else {
                load(sel);
                enhance(sel);
            }
        });
    }

    function feedback(sel) {
        var box = sel.parentNode.querySelector('.receipt-account-error');
        if (!box) {
            box = document.createElement('div');
            box.className = 'receipt-account-error text-danger small mt-1';
            box.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Select the account this payment was received into.';
            sel.parentNode.insertBefore(box, sel.nextSibling && sel.nextSibling.nextSibling);
        }
        return box;
    }

    function markInvalid(sel, bad) {
        sel.classList.toggle('is-invalid', bad);
        var s2 = sel.nextElementSibling;
        if (s2 && s2.classList.contains('select2')) {
            var box = s2.querySelector('.select2-selection');
            if (box) box.style.borderColor = bad ? '#dc3545' : '';
        }
        if (bad) feedback(sel).style.display = '';
        else {
            var err = sel.parentNode.querySelector('.receipt-account-error');
            if (err) err.style.display = 'none';
        }
    }

    // Capture phase on document: runs before the forms' own submit handlers,
    // and stops them when the account is missing (so none of them disables
    // the submit button or shows a spinner for a submit that won't happen).
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form || !form.querySelectorAll) return;
        var amount = form.querySelector('[name=amount]');
        if (amount && !(parseFloat(amount.value) > 0)) return;  // no money received
        var missing = null;
        form.querySelectorAll('select[data-receipt-account][data-required]').forEach(function (sel) {
            var bad = !sel.value;
            markInvalid(sel, bad);
            if (bad && !missing) missing = sel;
        });
        if (missing) {
            e.preventDefault();
            e.stopPropagation();
            if (hasSelect2() && missing.dataset.receiptAccountReady === '1') jQuery(missing).select2('open');
            else missing.focus();
        }
    }, true);

    document.addEventListener('change', function (e) {
        var sel = e.target;
        if (sel && sel.matches && sel.matches('select[data-receipt-account][data-required]') && sel.value) {
            markInvalid(sel, false);
        }
    });
    if (window.jQuery) {
        // Select2 reports picks as jQuery events.
        jQuery(document).on('change', 'select[data-receipt-account][data-required]', function () {
            if (this.value) markInvalid(this, false);
        });
    }

    // form.reset() (Universal Pay does it every time it opens) only resets the
    // native <select>; tell Select2 so the box shows "no account" again.
    document.addEventListener('reset', function (e) {
        var form = e.target;
        setTimeout(function () {
            form.querySelectorAll('select[data-receipt-account]').forEach(function (sel) {
                if (sel.dataset.receiptAccountReady === '1') jQuery(sel).trigger('change');
                if (sel.hasAttribute('data-required')) markInvalid(sel, false);
            });
        }, 0);
    }, true);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { init(); });
    } else {
        init();
    }
})();
