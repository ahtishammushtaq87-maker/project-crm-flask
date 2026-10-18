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

    // Menus inside a horizontally scrolling table would be clipped by it;
    // a fixed-position popper escapes the scroll box.
    if (window.bootstrap && bootstrap.Dropdown) {
        document.querySelectorAll('[data-st-fixed-dropdown]').forEach(function (btn) {
            bootstrap.Dropdown.getOrCreateInstance(btn, { popperConfig: { strategy: 'fixed' } });
        });
    }

    // ── Target detail: show / hide the items of an invoice ──
    document.querySelectorAll('[data-st-lines-toggle]').forEach(function (btn) {
        var row = document.getElementById(btn.getAttribute('data-st-lines-toggle'));
        if (!row) return;
        var label = btn.querySelector('.sales-target-toggle-text');
        var showText = label ? label.textContent : '';
        btn.addEventListener('click', function () {
            row.hidden = !row.hidden;
            btn.setAttribute('aria-expanded', row.hidden ? 'false' : 'true');
            btn.classList.toggle('is-open', !row.hidden);
            if (label) label.textContent = row.hidden ? showText : 'Hide items';
        });
    });

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

    // ── Amount grid: yearly target <-> its months (or quarters) kept in step ──
    // Rows are [data-st-row]; each may have a yearly [data-st-total] and
    // has [data-st-cell] amounts ([data-st-fixed] = locked, e.g. completed).
    // Typing the yearly amount splits it equally over the months the user
    // hasn't typed in; typing a month re-adjusts only those untouched
    // months. If every month was typed by hand, the yearly amount follows.
    // The table's data-st-unit ("months"/"quarters") names them in messages.
    // Work in whole cents so the quarters always add up exactly.
    var toCents = function (v) {
        var n = parseFloat(String(v == null ? '' : v).replace(/,/g, ''));
        return isFinite(n) ? Math.round(n * 100) : null;
    };
    var fromCents = function (c) { return (c / 100).toFixed(2); };
    var money = function (c) {
        return 'PKR ' + (c / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    var esc = function (t) {
        return String(t).replace(/[&<>"']/g, function (ch) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
        });
    };
    var splitCents = function (total, n) {
        var base = Math.floor(total / n), out = [];
        for (var i = 0; i < n; i++) out.push(base);
        out[n - 1] = total - base * (n - 1);
        return out;
    };
    var rowCells = function (row) { return Array.prototype.slice.call(row.querySelectorAll('[data-st-cell]')); };
    var isFixed = function (c) { return c.hasAttribute('data-st-fixed'); };
    var isManual = function (c) { return c.dataset.manual === '1'; };
    var sumCents = function (cells) {
        return cells.reduce(function (a, c) { return a + (toCents(c.value) || 0); }, 0);
    };
    var setManual = function (c, on) {
        if (on) c.dataset.manual = '1'; else delete c.dataset.manual;
        c.classList.toggle('is-manual', !!on);
    };

    function gridRowStatus(row) {
        var total = row.querySelector('[data-st-total]');
        var cells = rowCells(row);
        var out = row.querySelector('[data-st-row-status]');
        var table = row.closest('table');
        var units = (table && table.getAttribute('data-st-unit')) || 'months';
        var Units = units.charAt(0).toUpperCase() + units.slice(1);
        var bad = false;
        cells.forEach(function (c) {
            var neg = (toCents(c.value) || 0) < 0;
            if (neg) bad = true;
            if (!isFixed(c)) c.classList.toggle('is-invalid', neg);
        });
        if (!total || !out) return !bad;
        var t = toCents(total.value);
        if (t === null || t <= 0) { out.className = 'sales-target-grid-status'; out.textContent = ''; return false; }
        var diff = sumCents(cells) - t;
        if (diff === 0 && !bad) {
            out.className = 'sales-target-grid-status is-ok';
            out.innerHTML = '<i class="fas fa-check"></i> ' + Units + ' add up';
            return true;
        }
        out.className = 'sales-target-grid-status is-bad';
        out.textContent = bad ? 'An amount is below zero; lower the ' + units + ' you changed'
            : Units + (diff > 0 ? ' are over by ' : ' are short by ') + money(Math.abs(diff));
        return false;
    }

    function gridRebalance(row, trigger) {
        var total = row.querySelector('[data-st-total]');
        if (!total) { gridRowStatus(row); return; }
        var cells = rowCells(row);
        var editable = cells.filter(function (c) { return !isFixed(c); });
        var auto = editable.filter(function (c) { return !isManual(c); });
        if (!auto.length) {
            if (trigger) {  // every month set by hand: the yearly amount follows
                total.value = fromCents(sumCents(cells));
                gridRowStatus(row);
                return;
            }
            editable.forEach(function (c) { setManual(c, false); });
            auto = editable;
        }
        var t = toCents(total.value);
        if (t === null || !auto.length) { gridRowStatus(row); return; }
        var rest = t - sumCents(cells.filter(isFixed)) - sumCents(editable.filter(isManual));
        splitCents(rest, auto.length).forEach(function (c, i) { auto[i].value = fromCents(c); });
        gridRowStatus(row);
    }

    function gridFoot(table) {
        var foot = table.querySelector('[data-st-foot]');
        var rows = table.querySelectorAll('[data-st-row]');
        if (!foot) return;
        if (rows.length < 2) { foot.innerHTML = ''; return; }
        var width = rows[0].children.length, sums = [];
        rows.forEach(function (row) {
            Array.prototype.forEach.call(row.children, function (td, i) {
                var input = td.querySelector('[data-st-total], [data-st-cell]');
                if (input) sums[i] = (sums[i] || 0) + (toCents(input.value) || 0);
            });
        });
        var html = '<tr><th>Total</th>';
        for (var i = 1; i < width; i++) html += '<td>' + (sums[i] !== undefined ? '<strong>' + money(sums[i]) + '</strong>' : '') + '</td>';
        foot.innerHTML = html + '</tr>';
    }

    function setupGrid(table, onChange) {
        var changed = function () { gridFoot(table); if (onChange) onChange(); };
        table.addEventListener('input', function (e) {
            var el = e.target, row = el.closest('[data-st-row]');
            if (!row) return;
            if (el.hasAttribute('data-st-total')) gridRebalance(row, null);
            else if (el.hasAttribute('data-st-cell')) { setManual(el, true); gridRebalance(row, el); }
            changed();
        });
        table.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-st-even]');
            if (!btn) return;
            var row = btn.closest('[data-st-row]');
            rowCells(row).forEach(function (c) { setManual(c, false); });
            gridRebalance(row, null);
            changed();
        });
        table.querySelectorAll('[data-st-row]').forEach(gridRowStatus);
        gridFoot(table);
    }

    function gridProblems(table) {
        var problems = [];
        table.querySelectorAll('[data-st-row]').forEach(function (row) {
            var label = (row.querySelector('th') || {}).textContent || 'A row';
            var total = row.querySelector('[data-st-total]');
            if (total) {
                if (!(toCents(total.value) > 0)) { total.classList.add('is-invalid'); problems.push(label.trim() + ': enter the total target.'); }
                else if (!gridRowStatus(row)) problems.push(label.trim() + ': the ' + (table.getAttribute('data-st-unit') || 'months') + ' must add up to the total.');
            } else {
                rowCells(row).forEach(function (c) {
                    var bad = !(toCents(c.value) > 0);
                    c.classList.toggle('is-invalid', bad);
                    if (bad) problems.push(label.trim() + ': enter a target amount.');
                });
            }
        });
        return problems;
    }

    // Edit yearly split page
    var planForm = document.getElementById('salesTargetPlanForm');
    if (planForm) {
        var planGrid = planForm.querySelector('[data-st-grid]');
        setupGrid(planGrid);
        planForm.addEventListener('submit', function (e) {
            var problems = gridProblems(planGrid);
            if (problems.length) { e.preventDefault(); alert(problems.join('\n')); }
        });
    }

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

    // ── Create: yearly plan (12 months) and/or a separate target per item ──
    var gridWrap = document.getElementById('stGridWrap');
    var grid = gridWrap && gridWrap.querySelector('[data-st-grid]');
    var amountInput = targetForm.querySelector('[name=target_amount]');
    var modeOf = function () {
        var m = targetForm.querySelector('[data-st-mode-input]:checked');
        return m ? m.value : 'single';
    };
    if (gridWrap) {
        var state = {};
        try { state = JSON.parse(document.getElementById('stGridState').textContent || '{}'); } catch (err) { state = {}; }
        var saved = state.values || {}, savedManual = {}, gridErrors = state.errors || {};
        var splitBox = targetForm.querySelector('[data-st-split]');
        var yearSel = document.getElementById('stPlanYear');
        var startSel = document.getElementById('stPlanStart');
        var splitSel = document.getElementById('stPlanSplit');
        var countSel = document.getElementById('stPlanCount');
        var spanHint = targetForm.querySelector('[data-st-span]');
        var plainAmount = targetForm.querySelector('[data-st-plain-amount]');
        var bulk = gridWrap.querySelector('[data-st-bulk]');
        var submitLabel = targetForm.querySelector('[data-st-submit-label]');
        var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        // ``count`` months or quarters from the start month (same as plans.periods).
        var periodsOf = function (year, month, each, count) {
            var out = [], y = year, m = month - 1;
            for (var n = 1; n <= count; n++) {
                if (each === 1) {
                    out.push({ no: n, label: MON[m], range: String(y), sy: y, sm: m, ey: y, em: m });
                } else {
                    var ey = y + Math.floor((m + 2) / 12), em = (m + 2) % 12;
                    out.push({ no: n, label: 'Q' + n, sy: y, sm: m, ey: ey, em: em,
                               range: y === ey ? MON[m] + '–' + MON[em] + ' ' + ey : MON[m] + ' ' + y + '–' + MON[em] + ' ' + ey });
                }
                m += each;
                if (m >= 12) { m -= 12; y += 1; }
            }
            return out;
        };
        // "How many" lists 1-12 months or 1-4 quarters; keeps the choice when it fits.
        var syncCountOptions = function () {
            var quarter = splitSel.value === 'quarter';
            var unit = quarter ? 'quarter' : 'month', full = quarter ? 4 : 12;
            if (countSel.getAttribute('data-unit') === unit) return;
            var prev = parseInt(countSel.value, 10);
            var wasFull = countSel.getAttribute('data-unit') ? prev === countSel.options.length : true;
            var html = '';
            for (var n = 1; n <= full; n++) {
                html += '<option value="' + n + '">' + n + ' ' + unit + (n === 1 ? '' : 's') + (n === full ? ' (full year)' : '') + '</option>';
            }
            countSel.innerHTML = html;
            countSel.value = String(wasFull || !(prev >= 1 && prev <= full) ? full : prev);
            countSel.setAttribute('data-unit', unit);
        };
        countSel.setAttribute('data-unit', splitSel.value === 'quarter' ? 'quarter' : 'month');
        var chosenItems = function () {
            if (!itemsSel) return [];
            return Array.prototype.filter.call(itemsSel.options, function (o) { return o.selected; })
                .map(function (o) { return { id: o.value, label: o.textContent.trim() }; });
        };
        var countTargets = function () {
            var n = 0;
            grid.querySelectorAll('[data-st-cell]').forEach(function (c) { if ((toCents(c.value) || 0) > 0) n++; });
            if (submitLabel) submitLabel.textContent = 'Create ' + n + ' target' + (n === 1 ? '' : 's');
        };

        // Suggested name follows the period until the user types their own.
        var nameInput = targetForm.querySelector('[name=name]');
        var autoName = nameInput.value;
        var singleName = nameInput.value;
        var suggestName = function (yearly) {
            if (nameInput.value !== autoName) return;
            var y = parseInt(yearSel.value, 10), m = parseInt(startSel.value, 10);
            syncCountOptions();
            var each = splitSel.value === 'quarter' ? 3 : 1;
            var count = parseInt(countSel.value, 10);
            var span = yearly ? (m === 1 ? String(y) : 'FY ' + y + '-' + String(y + 1).slice(-2)) : '';
            if (yearly && count * each < 12) {
                var ps = periodsOf(y, m, each, count), a = ps[0], z = ps[ps.length - 1];
                span = a.sy === z.ey && a.sm === z.em ? MON[a.sm] + ' ' + a.sy
                    : MON[a.sm] + (a.sy === z.ey ? '' : ' ' + a.sy) + '–' + MON[z.em] + ' ' + z.ey;
            }
            autoName = yearly ? span + ' Sales Target' : singleName;
            nameInput.value = autoName;
        };

        var rebuild = function () {
            var yearly = modeOf() === 'yearly';
            var split = !!(splitBox && splitBox.checked);
            suggestName(yearly);
            targetForm.querySelectorAll('[data-st-mode]').forEach(function (el) {
                el.hidden = el.getAttribute('data-st-mode') !== (yearly ? 'yearly' : 'single');
            });
            var useGrid = yearly || split;
            plainAmount.hidden = useGrid;
            amountInput.disabled = useGrid;
            gridWrap.hidden = !useGrid;
            if (!useGrid) { if (submitLabel) submitLabel.textContent = 'Create Target'; return; }

            // Keep what was typed when the layout changes.
            grid.querySelectorAll('input[name]').forEach(function (i) {
                saved[i.name] = i.value;
                savedManual[i.name] = isManual(i);
            });
            var items = chosenItems();
            var rows = split ? items.map(function (i) { return { key: 'p' + i.id, label: i.label }; })
                             : [{ key: 'all', label: items.length ? 'Selected items (combined)' : 'All items' }];
            syncCountOptions();
            var each = splitSel.value === 'quarter' ? 3 : 1;
            var units = each === 3 ? 'quarters' : 'months';
            var full = each === 3 ? 4 : 12;
            var count = parseInt(countSel.value, 10) || full;
            grid.setAttribute('data-st-unit', units);
            var cols = yearly ? periodsOf(parseInt(yearSel.value, 10), parseInt(startSel.value, 10), each, count)
                              : [{ no: 1, label: 'Target amount', range: '' }];

            var input = function (name, attrs) {
                var v = saved[name] !== undefined ? saved[name] : '';
                var err = gridErrors[name];
                return '<input type="number" step="0.01" min="0" inputmode="decimal" name="' + name + '" ' + attrs +
                    ' class="form-control form-control-sm' + (err ? ' is-invalid' : '') + (savedManual[name] ? ' is-manual' : '') + '"' +
                    (savedManual[name] ? ' data-manual="1"' : '') + (err ? ' title="' + esc(err) + '"' : '') +
                    ' value="' + esc(v) + '" placeholder="0.00">';
            };
            if (yearly && cols.length) {
                var a = cols[0], z = cols[cols.length - 1];
                spanHint.textContent = 'Covers ' + MON[a.sm] + ' ' + a.sy + ' – ' + MON[z.em] + ' ' + z.ey + '.';
            }
            var totalHead = count === full ? 'Yearly target' : 'Total target';
            var html = '<thead><tr><th>' + (split ? 'Item' : 'Target') + '</th>' + (yearly ? '<th>' + totalHead + '</th>' : '');
            cols.forEach(function (c) { html += '<th>' + c.label + (c.range ? '<small>' + c.range + '</small>' : '') + '</th>'; });
            html += (yearly ? '<th></th>' : '') + '</tr></thead><tbody>';
            if (!rows.length) {
                html += '<tr><td colspan="' + (cols.length + (yearly ? 3 : 1)) + '" class="sales-target-sub">Select the finished items above; each one gets its own row here.</td></tr>';
            }
            rows.forEach(function (r) {
                html += '<tr data-st-row><th class="text-break">' + esc(r.label) + '</th>';
                if (yearly) {
                    html += '<td>' + input('total_' + r.key, 'data-st-total') +
                        '<div class="sales-target-grid-status" data-st-row-status></div></td>';
                }
                cols.forEach(function (c) { html += '<td>' + input('amt_' + r.key + '_' + c.no, 'data-st-cell') + '</td>'; });
                if (yearly) html += '<td><button type="button" class="btn btn-sm btn-outline-secondary" data-st-even title="Divide the yearly target equally again"><i class="fas fa-equals"></i></button></td>';
                html += '</tr>';
            });
            grid.innerHTML = html + '</tbody><tfoot data-st-foot></tfoot>';
            gridErrors = {};  // server messages apply to the first layout only

            var unit = units.slice(0, -1);
            gridWrap.querySelector('[data-st-grid-title]').textContent = yearly
                ? totalHead + ' and ' + units : 'Target amount per item';
            gridWrap.querySelector('[data-st-grid-help]').textContent = yearly
                ? 'Enter the total and it is divided equally into the ' + count + ' ' + (count === 1 ? unit : units) +
                  '. Change any ' + unit + ' and the ' + units + ' you haven’t changed adjust, so the total still adds up. Enter 0 for a ' + unit + ' with no target.' +
                  (cols.length > 6 ? ' Scroll sideways to see them all.' : '')
                : 'Enter a target amount for each item. Each item becomes its own target for the dates above.';
            bulk.hidden = !split;
            gridWrap.querySelector('[data-st-bulk-label]').textContent = yearly ? 'Same total for every item' : 'Same amount for every item';
            grid.querySelectorAll('[data-st-row]').forEach(gridRowStatus);
            gridFoot(grid);
            countTargets();
        };

        setupGrid(grid, countTargets);
        gridWrap.querySelector('[data-st-bulk-apply]').addEventListener('click', function () {
            var v = toCents(document.getElementById('stBulkAmount').value);
            if (v === null || v <= 0) { alert('Enter an amount greater than zero.'); return; }
            grid.querySelectorAll('[data-st-row]').forEach(function (row) {
                var total = row.querySelector('[data-st-total]');
                if (total) {
                    total.value = fromCents(v);
                    rowCells(row).forEach(function (c) { setManual(c, false); });
                    gridRebalance(row, null);
                } else {
                    rowCells(row).forEach(function (c) { c.value = fromCents(v); });
                }
            });
            gridFoot(grid);
            countTargets();
        });
        targetForm.querySelectorAll('[data-st-mode-input]').forEach(function (r) { r.addEventListener('change', rebuild); });
        [splitBox, yearSel, startSel, splitSel, countSel, itemsSel].forEach(function (el) { if (el) el.addEventListener('change', rebuild); });
        if (itemsSel && window.jQuery) jQuery(itemsSel).on('change', rebuild);  // Select2 fires jQuery events
        rebuild();
    }

    // Client-side checks mirroring the server rules.
    targetForm.addEventListener('submit', function (e) {
        var problems = [];
        var mark = function (el, bad) { if (el) el.classList.toggle('is-invalid', bad); };
        var name = targetForm.querySelector('[name=name]');
        mark(name, !name.value.trim());
        if (!name.value.trim()) problems.push('Enter a target name.');

        var locked = amountInput.disabled && !gridWrap;
        if (!locked) {
            if (!amountInput.disabled) {
                var v = parseFloat(amountInput.value);
                var bad = !(v > 0);
                mark(amountInput, bad);
                if (bad) problems.push('Target amount must be greater than zero.');
            }
            if (modeOf() !== 'yearly') {
                var start = targetForm.querySelector('[name=start_date]');
                var end = targetForm.querySelector('[name=end_date]');
                var badRange = !start.value || !end.value || end.value < start.value;
                mark(end, badRange);
                if (badRange) problems.push('Choose a start date and an end date that is not before it.');
            }
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
            if (gridWrap && !gridWrap.hidden) {
                if (!grid.querySelector('[data-st-row]')) problems.push('Select the items to create a separate target for.');
                problems = problems.concat(gridProblems(grid));
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
