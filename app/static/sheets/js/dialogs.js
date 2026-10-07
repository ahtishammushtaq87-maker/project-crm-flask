/* Spreadsheet module - editor dialogs and panels. Each takes the editor
 * `app` ({model, grid, actions, ...}) created in ui.js. */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var FM = CS.Format, X = CS.Formula;
    var D = CS.Dialogs = {};
    var esc = CS.esc;

    function opt(value, label, selected) {
        return '<option value="' + esc(value) + '"' + (selected ? ' selected' : '') + '>' + esc(label) + '</option>';
    }

    // ── Share ───────────────────────────────────────────────────────────
    D.share = function (app, bookId, opts) {
        opts = opts || {};
        var model = app && app.model;
        var id = bookId || model.id;
        var state = { items: [], can: model ? model.can : {}, owner_id: null };
        var body = document.createElement('div');
        body.innerHTML =
            '<div class="crm-sheet-share-add">' +
            '  <label class="form-label fw-semibold" for="crmShareSearch">Add people</label>' +
            '  <div class="d-flex gap-2 flex-wrap">' +
            '    <div class="position-relative flex-grow-1"><input type="search" class="form-control" id="crmShareSearch" placeholder="Search users by name or email" autocomplete="off">' +
            '      <div class="crm-sheet-share-results" role="listbox"></div></div>' +
            '    <select class="form-select w-auto" id="crmShareRole" aria-label="Permission">' + opt('viewer', 'Viewer') + opt('editor', 'Editor') + opt('manager', 'Manager') + '</select>' +
            '  </div>' +
            '  <div class="form-text">Viewer: open and filter. Editor: change cells and sheets. Manager: edit and share with others.</div>' +
            '</div>' +
            '<hr><div class="fw-semibold mb-2">People with access</div>' +
            '<div class="crm-sheet-share-list"><div class="text-muted small">Loading…</div></div>' +
            '<div class="crm-sheet-share-export mt-3"></div>';
        var list = body.querySelector('.crm-sheet-share-list');
        var search = body.querySelector('#crmShareSearch');
        var results = body.querySelector('.crm-sheet-share-results');
        var roleSel = body.querySelector('#crmShareRole');

        function render() {
            var can = state.can || {};
            if (!can.share) body.querySelector('.crm-sheet-share-add').innerHTML = '<div class="alert alert-light border small mb-0"><i class="fas fa-lock me-1"></i>Only the owner and managers can share this spreadsheet.</div>';
            if (!can.grant_manager) { var mo = roleSel.querySelector('option[value=manager]'); if (mo) mo.remove(); }
            list.innerHTML = state.items.map(function (p) {
                var isOwner = p.role === 'owner';
                var canChange = !isOwner && can.share && (can.grant_manager || p.role !== 'manager');
                var roleCtl = canChange
                    ? '<select class="form-select form-select-sm w-auto" data-role-for="' + p.user_id + '" aria-label="Permission for ' + esc(p.username) + '">' +
                      opt('viewer', 'Viewer', p.role === 'viewer') + opt('editor', 'Editor', p.role === 'editor') +
                      (can.grant_manager ? opt('manager', 'Manager', p.role === 'manager') : '') + '</select>'
                    : '<span class="badge ' + (isOwner ? 'bg-primary' : 'bg-light text-dark border') + '">' + esc(p.role_label) + '</span>';
                var actions = '';
                if (canChange) actions += '<button type="button" class="btn btn-sm btn-link text-danger" data-remove="' + p.user_id + '" title="Remove access" aria-label="Remove ' + esc(p.username) + '"><i class="fas fa-times"></i></button>';
                if (!isOwner && can.transfer && p.active !== false) actions += '<button type="button" class="btn btn-sm btn-link" data-transfer="' + p.user_id + '" title="Make owner">Make owner</button>';
                return '<div class="crm-sheet-share-row"><div class="crm-sheet-avatar">' + esc((p.username || '?').charAt(0).toUpperCase()) + '</div>' +
                    '<div class="flex-grow-1 min-w-0"><div class="fw-semibold text-truncate">' + esc(p.username) + (p.active === false ? ' <span class="badge bg-secondary">disabled</span>' : '') + '</div>' +
                    '<div class="small text-muted text-truncate">' + esc(p.email || '') + (p.crm_role ? ' · CRM role: ' + esc(p.crm_role) : '') + '</div></div>' +
                    roleCtl + actions + '</div>';
            }).join('');
            var exp = body.querySelector('.crm-sheet-share-export');
            if (can.delete && model) {
                exp.innerHTML = '<div class="form-check form-switch"><input class="form-check-input" type="checkbox" id="crmViewerExport"' + (model.viewersCanExport ? ' checked' : '') + '>' +
                    '<label class="form-check-label" for="crmViewerExport">Viewers can download, export and print</label></div>';
                exp.querySelector('input').onchange = function (e) {
                    CS.api('PATCH', '/spreadsheets/' + id, { viewers_can_export: e.target.checked }).then(function (res) {
                        if (!res.ok) { CS.toast(CS.errorText(res), 'error'); e.target.checked = !e.target.checked; return; }
                        model.viewersCanExport = e.target.checked;
                        CS.toast('Download setting saved.', 'success');
                    });
                };
            }
            if (!can.share && model && model.role !== 'owner' && model.role !== 'admin') {
                exp.innerHTML += '<button type="button" class="btn btn-sm btn-outline-danger mt-2" data-leave="1">Remove my access</button>';
            }
        }
        function load() {
            CS.api('GET', '/spreadsheets/' + id + '/permissions').then(function (res) {
                if (!res.ok) { list.innerHTML = '<div class="text-danger small">' + esc(CS.errorText(res)) + '</div>'; return; }
                state.items = res.data.items; state.can = res.data.can; state.owner_id = res.data.owner_id;
                render();
            });
        }
        var doSearch = CS.debounce(function () {
            var q = search.value.trim();
            CS.api('GET', '/users?q=' + encodeURIComponent(q)).then(function (res) {
                if (!res.ok) return;
                var have = {};
                state.items.forEach(function (p) { have[p.user_id] = p.role_label; });
                results.innerHTML = res.data.items.length ? res.data.items.map(function (u) {
                    return '<button type="button" class="crm-sheet-share-result" data-add="' + u.user_id + '"' + (have[u.user_id] ? ' disabled' : '') + '>' +
                        '<span class="crm-sheet-avatar">' + esc(u.username.charAt(0).toUpperCase()) + '</span><span class="flex-grow-1 text-start"><b>' + esc(u.username) + '</b><br><small class="text-muted">' + esc(u.email) + ' · ' + esc(u.crm_role) + '</small></span>' +
                        (have[u.user_id] ? '<small class="text-muted">' + esc(have[u.user_id]) + '</small>' : '<i class="fas fa-plus text-primary"></i>') + '</button>';
                }).join('') : '<div class="p-2 small text-muted">No users found.</div>';
                results.style.display = 'block';
            });
        }, 250);
        search && search.addEventListener('input', doSearch);
        search && search.addEventListener('focus', doSearch);
        body.addEventListener('mousedown', function (e) { if (results && !e.target.closest('.crm-sheet-share-results') && e.target !== search) results.style.display = 'none'; });
        body.addEventListener('click', function (e) {
            var add = e.target.closest('[data-add]'), rm = e.target.closest('[data-remove]'), tr = e.target.closest('[data-transfer]'), leave = e.target.closest('[data-leave]');
            if (add) {
                results.style.display = 'none';
                search.value = '';
                CS.api('POST', '/spreadsheets/' + id + '/permissions', { user_id: +add.dataset.add, role: roleSel.value }).then(function (res) {
                    if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                    state.items = res.data.items; render();
                    CS.toast('Shared.', 'success');
                    if (opts.onChange) opts.onChange();
                });
            } else if (rm) {
                var who = state.items.filter(function (p) { return String(p.user_id) === rm.dataset.remove; })[0];
                CS.confirm('Remove ' + (who ? who.username : 'this person') + '\'s access?', { ok: 'Remove', danger: true }).then(function (ok) {
                    if (!ok) return;
                    CS.api('DELETE', '/spreadsheets/' + id + '/permissions/' + rm.dataset.remove).then(function (res) {
                        if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                        state.items = res.data.items; render();
                        if (opts.onChange) opts.onChange();
                    });
                });
            } else if (tr) {
                var person = state.items.filter(function (p) { return String(p.user_id) === tr.dataset.transfer; })[0];
                CS.confirm('Make ' + person.username + ' the owner? You will keep access as a Manager.', { ok: 'Transfer ownership', danger: true }).then(function (ok) {
                    if (!ok) return;
                    CS.api('POST', '/spreadsheets/' + id + '/transfer', { user_id: +tr.dataset.transfer }).then(function (res) {
                        if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                        CS.toast('Ownership transferred.', 'success');
                        if (opts.onChange) opts.onChange(); else window.location.reload();
                        load();
                    });
                });
            } else if (leave) {
                CS.confirm('Remove your own access to this spreadsheet?', { ok: 'Remove my access', danger: true }).then(function (ok) {
                    if (!ok) return;
                    CS.api('DELETE', '/spreadsheets/' + id + '/permissions/' + document.body.dataset.crmSheetUser).then(function (res) {
                        if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                        window.location.href = CS.base() + '/';
                    });
                });
            }
        });
        body.addEventListener('change', function (e) {
            var sel = e.target.closest('[data-role-for]');
            if (!sel) return;
            CS.api('POST', '/spreadsheets/' + id + '/permissions', { user_id: +sel.dataset.roleFor, role: sel.value }).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); load(); return; }
                state.items = res.data.items; render();
                CS.toast('Permission updated.', 'success');
            });
        });
        CS.dialog({ title: 'Share "' + (opts.name || (model && model.name) || 'spreadsheet') + '"', body: body, buttons: [{ label: 'Done', cls: 'btn-primary' }] });
        load();
    };

    // ── Version history ─────────────────────────────────────────────────
    D.history = function (app) {
        var body = document.createElement('div');
        body.innerHTML = '<div class="text-muted small">Loading…</div>';
        CS.dialog({ title: 'Version history', body: body, size: 'lg' });
        CS.api('GET', '/spreadsheets/' + app.model.id + '/history').then(function (res) {
            if (!res.ok) { body.innerHTML = '<div class="text-danger">' + esc(CS.errorText(res)) + '</div>'; return; }
            if (!res.data.items.length) { body.innerHTML = '<div class="text-muted">No history yet.</div>'; return; }
            var lastDay = '', html = '<div class="crm-sheet-history">';
            res.data.items.forEach(function (h) {
                var d = new Date(h.at);
                var day = d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
                if (day !== lastDay) { html += '<div class="crm-sheet-history-day">' + esc(day) + '</div>'; lastDay = day; }
                var icon = { created: 'fa-plus-circle text-success', edit: 'fa-pen text-primary', structure: 'fa-table-cells text-info', shared: 'fa-user-plus text-success', unshared: 'fa-user-minus text-danger', permission: 'fa-user-shield text-warning', ownership: 'fa-crown text-warning', deleted: 'fa-trash text-danger', restored: 'fa-rotate-left text-success', settings: 'fa-gear text-secondary' }[h.action] || 'fa-circle text-secondary';
                html += '<div class="crm-sheet-history-row"><i class="fas ' + icon + '"></i><div><div>' + esc(h.summary) + '</div>' +
                    '<div class="small text-muted">' + esc(d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })) + ' — ' + esc(h.user) + (h.version ? ' · version ' + h.version : '') + '</div></div></div>';
            });
            html += '</div><p class="small text-muted mt-3 mb-0"><i class="fas fa-info-circle me-1"></i>History records who changed what and when. Restoring an earlier version is not available yet - use File › Make a copy before big changes.</p>';
            body.innerHTML = html;
        });
    };

    // ── Details / settings ──────────────────────────────────────────────
    D.details = function (app) {
        var m = app.model, can = m.can;
        var body =
            '<div class="mb-3"><label class="form-label">Name</label><input type="text" class="form-control" id="crmDetName" maxlength="200" value="' + esc(m.name) + '"' + (can.settings ? '' : ' disabled') + '></div>' +
            '<div class="mb-3"><label class="form-label">Description</label><textarea class="form-control" id="crmDetDesc" rows="3" maxlength="2000"' + (can.settings ? '' : ' disabled') + '>' + esc(m.description || '') + '</textarea></div>' +
            '<dl class="row small mb-0"><dt class="col-4">Owner</dt><dd class="col-8">' + esc(m.owner) + '</dd>' +
            '<dt class="col-4">Your access</dt><dd class="col-8">' + esc(can.role_label) + '</dd>' +
            '<dt class="col-4">Last modified</dt><dd class="col-8">' + esc(CS.dateTime(m.updatedAt)) + (m.updatedBy ? ' by ' + esc(m.updatedBy) : '') + '</dd>' +
            '<dt class="col-4">Sheets</dt><dd class="col-8">' + m.sheets.length + '</dd></dl>';
        CS.dialog({
            title: 'Spreadsheet details', body: body,
            buttons: can.settings ? [
                { label: 'Cancel', cls: 'btn-outline-secondary' },
                {
                    label: 'Save', cls: 'btn-primary', action: function (el) {
                        var name = el.querySelector('#crmDetName').value.trim(), desc = el.querySelector('#crmDetDesc').value;
                        if (!name) { el.querySelector('#crmDetName').classList.add('is-invalid'); return false; }
                        return CS.api('PATCH', '/spreadsheets/' + m.id, { name: name, description: desc }).then(function (res) {
                            if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return false; }
                            m.name = res.data.book.name; m.description = res.data.book.description;
                            app.refreshMeta();
                            CS.toast('Saved.', 'success');
                        });
                    },
                },
            ] : [{ label: 'Close', cls: 'btn-primary' }],
        });
    };

    // ── Import into this spreadsheet / a new one ───────────────────────
    /** opts.spreadsheetId: add as new sheets there; otherwise create a new spreadsheet. */
    D.importFile = function (opts) {
        opts = opts || {};
        var body = document.createElement('div');
        body.innerHTML =
            '<div class="crm-sheet-drop" tabindex="0"><i class="fas fa-file-arrow-up fa-2x mb-2 text-primary"></i>' +
            '<div><b>Choose a .csv or .xlsx file</b> or drop it here</div><div class="small text-muted">Up to 16 MB, ' + (opts.spreadsheetId ? 'imported as new sheet(s) - existing sheets are not changed.' : 'imported as a new spreadsheet.') + '</div>' +
            '<input type="file" accept=".csv,.tsv,.txt,.xlsx,.xlsm" class="d-none"></div>' +
            '<div class="crm-sheet-import-preview mt-3"></div>';
        var fileInput = body.querySelector('input[type=file]');
        var drop = body.querySelector('.crm-sheet-drop');
        var preview = body.querySelector('.crm-sheet-import-preview');
        var token = null, filename = '';
        drop.onclick = function () { fileInput.click(); };
        drop.onkeydown = function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); } };
        drop.ondragover = function (e) { e.preventDefault(); drop.classList.add('crm-sheet-drop-over'); };
        drop.ondragleave = function () { drop.classList.remove('crm-sheet-drop-over'); };
        drop.ondrop = function (e) { e.preventDefault(); drop.classList.remove('crm-sheet-drop-over'); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); };
        fileInput.onchange = function () { if (fileInput.files[0]) upload(fileInput.files[0]); };
        function upload(file) {
            var fd = new FormData();
            fd.append('file', file);
            preview.innerHTML = '<div class="crm-sheet-loading"><span class="spinner-border spinner-border-sm me-2"></span>Reading ' + esc(file.name) + '…</div>';
            CS.api('POST', '/import/preview', fd).then(function (res) {
                if (!res.ok) { preview.innerHTML = '<div class="alert alert-danger mb-0">' + esc(CS.errorText(res)) + '</div>'; token = null; return; }
                token = res.data.token; filename = res.data.filename;
                var html = '';
                if (!opts.spreadsheetId) html += '<div class="mb-3"><label class="form-label fw-semibold">New spreadsheet name</label><input type="text" class="form-control" id="crmImpName" maxlength="200" value="' + esc(filename.replace(/\.[^.]+$/, '')) + '"></div>';
                res.data.sheets.forEach(function (s, i) {
                    html += '<div class="crm-sheet-import-sheet"><div class="form-check"><input class="form-check-input" type="checkbox" checked id="crmImpS' + i + '" data-sheet="' + i + '">' +
                        '<label class="form-check-label fw-semibold" for="crmImpS' + i + '">' + esc(s.name) + '</label> <span class="small text-muted">' + s.row_count.toLocaleString() + ' rows × ' + s.col_count + ' columns</span></div>' +
                        '<div class="small text-muted mb-1">Columns: ' + s.columns.slice(0, 20).map(function (c) { return esc(c.header || CS.colName(c.index)) + ' <span class="badge bg-light text-dark border">' + esc(c.kind) + '</span>'; }).join(', ') + (s.columns.length > 20 ? ' …' : '') + '</div>' +
                        '<div class="crm-sheet-preview-table"><table class="table table-sm table-bordered mb-0 no-datatable"><tbody>' +
                        s.rows.slice(0, 8).map(function (row, ri) { return '<tr>' + row.slice(0, 12).map(function (v) { return (ri === 0 ? '<th>' : '<td>') + esc(v) + (ri === 0 ? '</th>' : '</td>'); }).join('') + '</tr>'; }).join('') +
                        '</tbody></table></div></div>';
                });
                preview.innerHTML = html;
            });
        }
        CS.dialog({
            title: opts.spreadsheetId ? 'Import into this spreadsheet' : 'Import spreadsheet', body: body, size: 'lg',
            buttons: [
                { label: 'Cancel', cls: 'btn-outline-secondary' },
                {
                    label: 'Import', cls: 'btn-primary', action: function (el) {
                        if (!token) { CS.toast('Choose a file first.', 'info'); return false; }
                        var chosen = Array.prototype.map.call(el.querySelectorAll('[data-sheet]:checked'), function (c) { return +c.dataset.sheet; });
                        if (!chosen.length) { CS.toast('Choose at least one sheet.', 'info'); return false; }
                        var payload = { token: token, sheets: chosen };
                        if (opts.spreadsheetId) payload.spreadsheet_id = opts.spreadsheetId;
                        var nameEl = el.querySelector('#crmImpName');
                        if (nameEl) payload.name = nameEl.value.trim() || filename;
                        return CS.api('POST', '/import/confirm', payload).then(function (res) {
                            if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return false; }
                            if (opts.onDone) opts.onDone(res.data);
                        });
                    },
                },
            ],
        });
    };

    // ── Print ───────────────────────────────────────────────────────────
    D.print = function (app) {
        var body =
            '<div class="row g-3">' +
            '<div class="col-12"><label class="form-label fw-semibold">Print</label>' +
            '<div class="form-check"><input class="form-check-input" type="radio" name="crmPrWhat" id="crmPrSheet" value="sheet" checked><label class="form-check-label" for="crmPrSheet">Current sheet</label></div>' +
            '<div class="form-check"><input class="form-check-input" type="radio" name="crmPrWhat" id="crmPrSel" value="selection"><label class="form-check-label" for="crmPrSel">Selected cells (' + esc(CS.rangeStr(app.grid.activeRange())) + ')</label></div>' +
            '<div class="form-check"><input class="form-check-input" type="radio" name="crmPrWhat" id="crmPrAll" value="all"><label class="form-check-label" for="crmPrAll">Entire spreadsheet (all visible sheets)</label></div></div>' +
            '<div class="col-sm-6"><label class="form-label" for="crmPrOrient">Orientation</label><select class="form-select" id="crmPrOrient">' + opt('portrait', 'Portrait') + opt('landscape', 'Landscape', true) + '</select></div>' +
            '<div class="col-sm-6"><label class="form-label" for="crmPrMargin">Margins</label><select class="form-select" id="crmPrMargin">' + opt('10mm', 'Normal') + opt('5mm', 'Narrow') + opt('20mm', 'Wide') + '</select></div>' +
            '<div class="col-sm-6"><div class="form-check"><input class="form-check-input" type="checkbox" id="crmPrFit" checked><label class="form-check-label" for="crmPrFit">Fit to page width</label></div></div>' +
            '<div class="col-sm-6"><div class="form-check"><input class="form-check-input" type="checkbox" id="crmPrGrid" checked><label class="form-check-label" for="crmPrGrid">Show gridlines</label></div></div>' +
            '</div><p class="small text-muted mt-3 mb-0">To save as PDF, choose "Save as PDF" as the printer.</p>';
        CS.dialog({
            title: 'Print', body: body,
            buttons: [
                { label: 'Cancel', cls: 'btn-outline-secondary' },
                {
                    label: 'Print', cls: 'btn-primary', action: function (el) {
                        var what = el.querySelector('input[name=crmPrWhat]:checked').value;
                        var o = { orient: el.querySelector('#crmPrOrient').value, margin: el.querySelector('#crmPrMargin').value, fit: el.querySelector('#crmPrFit').checked, grid: el.querySelector('#crmPrGrid').checked };
                        var jobs;
                        if (what === 'selection') jobs = [{ sheet: app.grid.sheet, range: app.grid.activeRange() }];
                        else if (what === 'all') jobs = app.model.visibleSheets().map(function (s) { return { sheet: s }; });
                        else jobs = [{ sheet: app.grid.sheet }];
                        app.model.loadAll().then(function () { printJobs(app, jobs, o); });
                    },
                },
            ],
        });
    };
    function printJobs(app, jobs, o) {
        var model = app.model, parts = [];
        jobs.forEach(function (job, ji) {
            var s = job.sheet, used = model.used(s);
            var rg = job.range ? CS.normRange(job.range) : { r1: 0, c1: 0, r2: Math.max(0, used.rows - 1), c2: Math.max(0, used.cols - 1) };
            rg.r2 = Math.min(rg.r2, Math.max(rg.r1, used.rows - 1));
            rg.c2 = Math.min(rg.c2, Math.max(rg.c1, used.cols - 1));
            var hr = new Set(s.props.hr || []), hc = new Set(s.props.hc || []);
            var merges = s.props.merges || [], covered = new Set(), anchors = {};
            merges.forEach(function (m) {
                anchors[CS.key(m.r1, m.c1)] = m;
                for (var r = m.r1; r <= m.r2; r++) for (var c = m.c1; c <= m.c2; c++) if (r !== m.r1 || c !== m.c1) covered.add(CS.key(r, c));
            });
            var html = '<section' + (ji ? ' class="pb"' : '') + '><h1>' + esc(model.name) + (jobs.length > 1 || s !== app.grid.sheet ? ' — ' + esc(s.name) : '') + '</h1><table><colgroup>';
            for (var c = rg.c1; c <= rg.c2; c++) if (!hc.has(c)) html += '<col style="width:' + ((s.props.cw || {})[c] || CS.Grid.DEFAULT_W) + 'px">';
            html += '</colgroup>';
            for (var r = rg.r1; r <= rg.r2; r++) {
                if (hr.has(r)) continue;
                html += '<tr style="height:' + ((s.props.rh || {})[r] || CS.Grid.DEFAULT_H) + 'px">';
                for (c = rg.c1; c <= rg.c2; c++) {
                    var k = CS.key(r, c);
                    if (hc.has(c) || covered.has(k)) continue;
                    var cell = model.raw(s, r, c), f = cell && cell.f ? cell.f : {};
                    var v = model.value(s, r, c), text = FM.display(v, f.nf);
                    var ha = f.ha || (v.t === 'n' ? 'right' : v.t === 'b' ? 'center' : 'left');
                    var m = anchors[k], span = m ? ' rowspan="' + (Math.min(m.r2, rg.r2) - r + 1) + '" colspan="' + (Math.min(m.c2, rg.c2) - c + 1) + '"' : '';
                    html += '<td' + span + ' style="' + esc(FM.css(f) + FM.borderCss(f) + 'text-align:' + ha + ';vertical-align:' + (f.va === 'top' ? 'top' : f.va === 'middle' ? 'middle' : 'bottom') + (f.wrap === 'wrap' ? ';white-space:pre-wrap' : '')) + '">' + esc(text) + '</td>';
                }
                html += '</tr>';
            }
            parts.push(html + '</table></section>');
        });
        var css = '@page{size:A4 ' + o.orient + ';margin:' + o.margin + '}body{font:10pt Arial,sans-serif;color:#000;margin:0}' +
            'h1{font-size:12pt;margin:0 0 6px}table{border-collapse:collapse;table-layout:fixed' + (o.fit ? ';width:100%' : '') + '}' +
            'td{padding:2px 4px;overflow:hidden;white-space:nowrap;text-overflow:clip;' + (o.grid ? 'border:1px solid #ccc;' : '') + '}' +
            '.pb{page-break-before:always}';
        var frame = document.createElement('iframe');
        frame.className = 'crm-sheet-printframe';
        frame.setAttribute('aria-hidden', 'true');
        document.body.appendChild(frame);
        var doc = frame.contentDocument;
        doc.open();
        doc.write('<!doctype html><html><head><meta charset="utf-8"><title>' + esc(model.name) + '</title><style>' + css + '</style></head><body>' + parts.join('') + '</body></html>');
        doc.close();
        setTimeout(function () {
            frame.contentWindow.focus();
            frame.contentWindow.print();
            setTimeout(function () { frame.remove(); }, 1000);
        }, 200);
    }

    // ── Data validation ─────────────────────────────────────────────────
    D.validation = function (app) {
        var a = app.grid.sel.active, existing = app.actions.validationFor(app.grid.sheet, a.r, a.c) || {};
        var rg = app.grid.activeRange();
        var numMin = existing.min !== null && existing.min !== undefined ? existing.min : '';
        var numMax = existing.max !== null && existing.max !== undefined ? existing.max : '';
        var minDate = existing.type === 'date' && numMin !== '' ? FM.formatDate(numMin) : '';
        var maxDate = existing.type === 'date' && numMax !== '' ? FM.formatDate(numMax) : '';
        var body =
            '<div class="mb-3"><label class="form-label">Apply to range</label><input type="text" class="form-control" id="crmDvRange" value="' + esc(CS.rangeStr(rg)) + '" disabled></div>' +
            '<div class="mb-3"><label class="form-label" for="crmDvType">Criteria</label><select class="form-select" id="crmDvType">' +
            opt('list', 'Dropdown (list of items)', existing.type === 'list' || !existing.type) + opt('number', 'Number', existing.type === 'number') +
            opt('text_length', 'Text length', existing.type === 'text_length') + opt('text_contains', 'Text contains', existing.type === 'text_contains') +
            opt('date', 'Date', existing.type === 'date') + '</select></div>' +
            '<div class="mb-3 crm-dv crm-dv-list"><label class="form-label" for="crmDvList">Items (one per line or comma separated)</label><textarea class="form-control" id="crmDvList" rows="4">' + esc((existing.values || []).join('\n')) + '</textarea></div>' +
            '<div class="row g-2 mb-3 crm-dv crm-dv-number crm-dv-text_length"><div class="col"><label class="form-label">Minimum</label><input type="number" class="form-control" id="crmDvMin" value="' + esc(existing.type === 'date' ? '' : numMin) + '"></div><div class="col"><label class="form-label">Maximum</label><input type="number" class="form-control" id="crmDvMax" value="' + esc(existing.type === 'date' ? '' : numMax) + '"></div></div>' +
            '<div class="row g-2 mb-3 crm-dv crm-dv-date"><div class="col"><label class="form-label">On or after</label><input type="date" class="form-control" id="crmDvDMin" value="' + esc(minDate) + '"></div><div class="col"><label class="form-label">On or before</label><input type="date" class="form-control" id="crmDvDMax" value="' + esc(maxDate) + '"></div></div>' +
            '<div class="mb-3 crm-dv crm-dv-text_contains"><label class="form-label" for="crmDvText">Must contain</label><input type="text" class="form-control" id="crmDvText" value="' + esc(existing.text || '') + '"></div>' +
            '<div class="mb-3"><label class="form-label">If the data is invalid</label>' +
            '<div class="form-check"><input class="form-check-input" type="radio" name="crmDvStrict" id="crmDvReject" value="1"' + (existing.strict === false ? '' : ' checked') + '><label class="form-check-label" for="crmDvReject">Reject the input</label></div>' +
            '<div class="form-check"><input class="form-check-input" type="radio" name="crmDvStrict" id="crmDvWarn" value="0"' + (existing.strict === false ? ' checked' : '') + '><label class="form-check-label" for="crmDvWarn">Show a warning</label></div></div>' +
            '<div><label class="form-label" for="crmDvMsg">Custom error message (optional)</label><input type="text" class="form-control" id="crmDvMsg" maxlength="300" value="' + esc(existing.msg || '') + '"></div>';
        var dlg = CS.dialog({
            title: 'Data validation', body: body,
            buttons: [
                { label: 'Remove rule', cls: 'btn-outline-danger me-auto', action: function () { app.actions.setValidation(null); } },
                { label: 'Cancel', cls: 'btn-outline-secondary' },
                {
                    label: 'Save', cls: 'btn-primary', action: function (el) {
                        var type = el.querySelector('#crmDvType').value;
                        var rule = { type: type, strict: el.querySelector('input[name=crmDvStrict]:checked').value === '1', msg: el.querySelector('#crmDvMsg').value.trim(), min: null, max: null, values: [], text: '' };
                        if (type === 'list') {
                            rule.values = el.querySelector('#crmDvList').value.split(/[\n,]/).map(function (s) { return s.trim(); }).filter(Boolean);
                            if (!rule.values.length) { CS.toast('Add at least one item.', 'info'); return false; }
                        } else if (type === 'number' || type === 'text_length') {
                            var mn = el.querySelector('#crmDvMin').value, mx = el.querySelector('#crmDvMax').value;
                            rule.min = mn === '' ? null : +mn; rule.max = mx === '' ? null : +mx;
                        } else if (type === 'date') {
                            var d1 = el.querySelector('#crmDvDMin').value, d2 = el.querySelector('#crmDvDMax').value;
                            rule.min = d1 ? FM.parse(d1).v : null; rule.max = d2 ? FM.parse(d2).v : null;
                        } else {
                            rule.text = el.querySelector('#crmDvText').value;
                            if (!rule.text) { CS.toast('Enter the text the cells must contain.', 'info'); return false; }
                        }
                        app.actions.setValidation(rule);
                    },
                },
            ],
        });
        var typeSel = dlg.querySelector('#crmDvType');
        var sync = function () {
            dlg.querySelectorAll('.crm-dv').forEach(function (el) { el.style.display = el.classList.contains('crm-dv-' + typeSel.value) ? '' : 'none'; });
        };
        typeSel.addEventListener('change', sync);
        sync();
    };

    // ── Conditional formatting ──────────────────────────────────────────
    var CF_TYPES = [['gt', 'Greater than'], ['gte', 'Greater than or equal to'], ['lt', 'Less than'], ['lte', 'Less than or equal to'], ['eq', 'Is equal to'], ['neq', 'Is not equal to'], ['between', 'Is between'], ['contains', 'Text contains'], ['not_contains', 'Text does not contain'], ['empty', 'Is empty'], ['not_empty', 'Is not empty'], ['duplicate', 'Duplicate values']];
    D.conditional = function (app) {
        var sheet = app.grid.sheet;
        var rules = JSON.parse(JSON.stringify(sheet.props.cf || []));
        var body = document.createElement('div');
        function label(t) { for (var i = 0; i < CF_TYPES.length; i++) if (CF_TYPES[i][0] === t) return CF_TYPES[i][1]; return t; }
        function renderList() {
            var html = rules.length ? '' : '<div class="text-muted small mb-2">No rules on this sheet yet.</div>';
            rules.forEach(function (r, i) {
                var st = r.style || {};
                html += '<div class="crm-sheet-cf-row"><span class="crm-sheet-cf-swatch" style="background:' + esc(st.bg || '#fff') + ';color:' + esc(st.c || '#000') + ';font-weight:' + (st.b ? 700 : 400) + '">123</span>' +
                    '<div class="flex-grow-1"><b>' + esc(CS.rangeStr(r)) + '</b> · ' + esc(label(r.type)) + (r.v1 && !/empty|duplicate/.test(r.type) ? ' ' + esc(r.v1) : '') + (r.type === 'between' ? ' and ' + esc(r.v2) : '') + '</div>' +
                    '<button type="button" class="btn btn-sm btn-link text-danger" data-del="' + i + '" aria-label="Delete rule"><i class="fas fa-trash"></i></button></div>';
            });
            body.querySelector('.crm-sheet-cf-list').innerHTML = html;
        }
        body.innerHTML = '<div class="crm-sheet-cf-list mb-3"></div><hr><div class="fw-semibold mb-2">Add a rule</div>' +
            '<div class="row g-2"><div class="col-sm-4"><label class="form-label small">Range</label><input class="form-control form-control-sm" id="crmCfRange" value="' + esc(CS.rangeStr(app.grid.activeRange())) + '"></div>' +
            '<div class="col-sm-8"><label class="form-label small">Format cells if…</label><select class="form-select form-select-sm" id="crmCfType">' + CF_TYPES.map(function (t) { return opt(t[0], t[1]); }).join('') + '</select></div>' +
            '<div class="col-sm-6 crm-cf-v1"><label class="form-label small">Value</label><input class="form-control form-control-sm" id="crmCfV1"></div>' +
            '<div class="col-sm-6 crm-cf-v2"><label class="form-label small">and</label><input class="form-control form-control-sm" id="crmCfV2"></div>' +
            '<div class="col-12 d-flex gap-3 align-items-end flex-wrap"><div><label class="form-label small d-block">Fill</label><input type="color" class="form-control form-control-color" id="crmCfBg" value="#b7e1cd"></div>' +
            '<div><label class="form-label small d-block">Text</label><input type="color" class="form-control form-control-color" id="crmCfC" value="#0b5d1e"></div>' +
            '<div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="crmCfB"><label class="form-check-label" for="crmCfB">Bold</label></div>' +
            '<button type="button" class="btn btn-sm btn-outline-primary ms-auto" id="crmCfAdd"><i class="fas fa-plus me-1"></i>Add rule</button></div></div>';
        renderList();
        var typeSel = body.querySelector('#crmCfType');
        var sync = function () {
            var t = typeSel.value;
            body.querySelector('.crm-cf-v1').style.display = /empty|duplicate/.test(t) ? 'none' : '';
            body.querySelector('.crm-cf-v2').style.display = t === 'between' ? '' : 'none';
        };
        typeSel.addEventListener('change', sync);
        sync();
        body.addEventListener('click', function (e) {
            var del = e.target.closest('[data-del]');
            if (del) { rules.splice(+del.dataset.del, 1); renderList(); return; }
            if (e.target.closest('#crmCfAdd')) {
                var rg = CS.parseRange(body.querySelector('#crmCfRange').value, sheet.rows, sheet.cols);
                if (!rg) { body.querySelector('#crmCfRange').classList.add('is-invalid'); return; }
                body.querySelector('#crmCfRange').classList.remove('is-invalid');
                rules.push(Object.assign(rg, {
                    type: typeSel.value, v1: body.querySelector('#crmCfV1').value, v2: body.querySelector('#crmCfV2').value,
                    style: { bg: body.querySelector('#crmCfBg').value, c: body.querySelector('#crmCfC').value, b: body.querySelector('#crmCfB').checked || undefined },
                }));
                renderList();
            }
        });
        CS.dialog({
            title: 'Conditional formatting', body: body, size: 'lg',
            buttons: [{ label: 'Cancel', cls: 'btn-outline-secondary' }, { label: 'Save', cls: 'btn-primary', action: function () { app.actions.setCondFormats(rules); } }],
        });
    };

    // ── Sort range ──────────────────────────────────────────────────────
    D.sortRange = function (app) {
        var g = app.grid, a = g.sel.active, rg = g.activeRange();
        if (rg.r1 === rg.r2 && rg.c1 === rg.c2) rg = app.actions.dataRegion(a.r, a.c);
        var header = app.actions.looksLikeHeader(rg);
        var body = document.createElement('div');
        function colOptions(withHeader) {
            var out = '';
            for (var c = rg.c1; c <= rg.c2; c++) {
                var h = withHeader ? app.model.display(g.sheet, rg.r1, c) : '';
                out += opt(c, 'Column ' + CS.colName(c) + (h ? ' — ' + h : ''), c === a.c);
            }
            return out;
        }
        function keyRow() {
            return '<div class="d-flex gap-2 mb-2 crm-sheet-sortkey"><select class="form-select form-select-sm" data-col>' + colOptions(header) + '</select>' +
                '<select class="form-select form-select-sm w-auto" data-dir>' + opt('asc', 'A → Z') + opt('desc', 'Z → A') + '</select></div>';
        }
        body.innerHTML = '<div class="mb-3"><label class="form-label">Range</label><input class="form-control" id="crmSortRange" value="' + esc(CS.rangeStr(rg)) + '"></div>' +
            '<div class="form-check mb-3"><input class="form-check-input" type="checkbox" id="crmSortHeader"' + (header ? ' checked' : '') + '><label class="form-check-label" for="crmSortHeader">Data has a header row</label></div>' +
            '<div class="crm-sheet-sortkeys">' + keyRow() + '</div><button type="button" class="btn btn-sm btn-link px-0" id="crmSortAdd"><i class="fas fa-plus me-1"></i>Add another sort column</button>';
        body.querySelector('#crmSortHeader').addEventListener('change', function (e) {
            header = e.target.checked;
            body.querySelectorAll('[data-col]').forEach(function (s) { var v = s.value; s.innerHTML = colOptions(header); s.value = v; });
        });
        body.querySelector('#crmSortRange').addEventListener('change', function (e) {
            var parsed = CS.parseRange(e.target.value, g.nRows, g.nCols);
            if (parsed) { rg = parsed; body.querySelectorAll('[data-col]').forEach(function (s) { s.innerHTML = colOptions(header); }); }
        });
        body.querySelector('#crmSortAdd').addEventListener('click', function () { body.querySelector('.crm-sheet-sortkeys').insertAdjacentHTML('beforeend', keyRow()); });
        CS.dialog({
            title: 'Sort range', body: body,
            buttons: [{ label: 'Cancel', cls: 'btn-outline-secondary' }, {
                label: 'Sort', cls: 'btn-primary', action: function (el) {
                    var parsed = CS.parseRange(el.querySelector('#crmSortRange').value, g.nRows, g.nCols);
                    if (!parsed) { el.querySelector('#crmSortRange').classList.add('is-invalid'); return false; }
                    var keys = Array.prototype.map.call(el.querySelectorAll('.crm-sheet-sortkey'), function (row) {
                        return { c: +row.querySelector('[data-col]').value, asc: row.querySelector('[data-dir]').value === 'asc' };
                    }).filter(function (k) { return k.c >= parsed.c1 && k.c <= parsed.c2; });
                    if (!keys.length) { CS.toast('Choose a column inside the range.', 'info'); return false; }
                    app.actions.sortRange(parsed, keys, el.querySelector('#crmSortHeader').checked);
                },
            }],
        });
    };

    // ── Filter dropdown for one column ──────────────────────────────────
    D.filterMenu = function (app, col, anchor) {
        var f = app.grid.sheet.props.filter;
        if (!f) return;
        var crit = (f.crit && f.crit[col]) || {};
        var values = app.actions.distinctValues(col);
        var selected = crit.values ? new Set(crit.values) : null;
        var el = document.createElement('div');
        el.className = 'crm-sheet-filterpop';
        el.innerHTML =
            (app.model.can.edit ? '<button type="button" class="crm-sheet-menu-item" data-sort="asc"><span class="crm-sheet-menu-ico"><i class="fas fa-arrow-down-a-z"></i></span>Sort A → Z</button>' +
                '<button type="button" class="crm-sheet-menu-item" data-sort="desc"><span class="crm-sheet-menu-ico"><i class="fas fa-arrow-down-z-a"></i></span>Sort Z → A</button><div class="crm-sheet-menu-divider"></div>' : '') +
            '<div class="px-2"><label class="form-label small fw-semibold mb-1">Filter by condition</label>' +
            '<select class="form-select form-select-sm mb-1" data-op>' + opt('', 'None') + opt('contains', 'Text contains', crit.op === 'contains') + opt('not_contains', 'Text does not contain', crit.op === 'not_contains') +
            opt('eq', 'Is equal to', crit.op === 'eq') + opt('neq', 'Is not equal to', crit.op === 'neq') + opt('gt', 'Greater than', crit.op === 'gt') + opt('gte', 'Greater than or equal', crit.op === 'gte') +
            opt('lt', 'Less than', crit.op === 'lt') + opt('lte', 'Less than or equal', crit.op === 'lte') + opt('between', 'Is between', crit.op === 'between') +
            opt('date_eq', 'Date is', crit.op === 'date_eq') + opt('date_before', 'Date is before', crit.op === 'date_before') + opt('date_after', 'Date is after', crit.op === 'date_after') +
            opt('empty', 'Is empty', crit.op === 'empty') + opt('not_empty', 'Is not empty', crit.op === 'not_empty') + '</select>' +
            '<div class="d-flex gap-1 mb-2"><input class="form-control form-control-sm" data-v1 placeholder="Value" value="' + esc(crit.v1 || '') + '"><input class="form-control form-control-sm" data-v2 placeholder="and" value="' + esc(crit.v2 || '') + '"></div>' +
            '<label class="form-label small fw-semibold mb-1">Filter by values</label>' +
            '<div class="d-flex justify-content-between small mb-1"><a href="#" data-all>Select all</a><a href="#" data-none>Clear</a></div>' +
            '<input type="search" class="form-control form-control-sm mb-1" data-search placeholder="Search values">' +
            '<div class="crm-sheet-filtervals"></div>' +
            '<div class="d-flex justify-content-end gap-2 py-2"><button type="button" class="btn btn-sm btn-outline-secondary" data-clear>Clear filter</button><button type="button" class="btn btn-sm btn-primary" data-ok>OK</button></div></div>';
        var box = el.querySelector('.crm-sheet-filtervals');
        box.innerHTML = values.map(function (v, i) {
            return '<label class="crm-sheet-filterval" data-text="' + esc(v.toLowerCase()) + '"><input type="checkbox" class="form-check-input me-2" data-val="' + i + '"' + (!selected || selected.has(v) ? ' checked' : '') + '>' + (v === '' ? '<i class="text-muted">(Blanks)</i>' : esc(v)) + '</label>';
        }).join('');
        var syncOp = function () { var op = el.querySelector('[data-op]').value; el.querySelector('[data-v1]').style.display = op && !/empty/.test(op) ? '' : 'none'; el.querySelector('[data-v2]').style.display = op === 'between' ? '' : 'none'; };
        el.querySelector('[data-op]').addEventListener('change', syncOp);
        syncOp();
        el.querySelector('[data-search]').addEventListener('input', function (e) {
            var q = e.target.value.toLowerCase();
            box.querySelectorAll('.crm-sheet-filterval').forEach(function (l) { l.style.display = l.dataset.text.indexOf(q) >= 0 ? '' : 'none'; });
        });
        el.addEventListener('click', function (e) {
            var t = e.target;
            if (t.closest('[data-all]')) { e.preventDefault(); box.querySelectorAll('input').forEach(function (i) { i.checked = true; }); }
            else if (t.closest('[data-none]')) { e.preventDefault(); box.querySelectorAll('input').forEach(function (i) { i.checked = false; }); }
            else if (t.closest('[data-sort]')) {
                CS.closeMenu();
                var dir = t.closest('[data-sort]').dataset.sort === 'asc';
                app.actions.sortRange({ r1: f.r1, c1: f.c1, r2: f.r2, c2: f.c2 }, [{ c: col, asc: dir }], true);
            } else if (t.closest('[data-clear]')) { CS.closeMenu(); app.actions.setFilterCriteria(col, null); }
            else if (t.closest('[data-ok]')) {
                var checks = box.querySelectorAll('input'), chosen = [], all = true;
                checks.forEach(function (c) { if (c.checked) chosen.push(values[+c.dataset.val]); else all = false; });
                var op = el.querySelector('[data-op]').value;
                var nc = {};
                if (!all) nc.values = chosen;
                if (op) { nc.op = op; nc.v1 = el.querySelector('[data-v1]').value; nc.v2 = el.querySelector('[data-v2]').value; }
                CS.closeMenu();
                app.actions.setFilterCriteria(col, Object.keys(nc).length ? nc : null);
            }
        });
        CS.popover(anchor, el);
    };

    // ── Find & replace panel ────────────────────────────────────────────
    D.find = function (app, replace) {
        var panel = document.querySelector('.crm-sheet-findpanel');
        if (panel) {
            panel.querySelector('[data-replace-row]').style.display = replace && app.model.can.edit ? '' : 'none';
            panel.querySelector('[data-q]').focus();
            panel.querySelector('[data-q]').select();
            return;
        }
        panel = document.createElement('div');
        panel.className = 'crm-sheet-findpanel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Find and replace');
        panel.innerHTML =
            '<div class="d-flex align-items-center gap-1 mb-2"><input type="search" class="form-control form-control-sm" data-q placeholder="Find in sheet" aria-label="Find">' +
            '<span class="small text-muted text-nowrap crm-sheet-findcount" aria-live="polite"></span>' +
            '<button type="button" class="btn btn-sm btn-light" data-prev title="Previous (Shift+Enter)" aria-label="Previous match"><i class="fas fa-chevron-up"></i></button>' +
            '<button type="button" class="btn btn-sm btn-light" data-next title="Next (Enter)" aria-label="Next match"><i class="fas fa-chevron-down"></i></button>' +
            '<button type="button" class="btn btn-sm btn-light" data-close title="Close (Esc)" aria-label="Close"><i class="fas fa-times"></i></button></div>' +
            '<div class="d-flex align-items-center gap-1 mb-2" data-replace-row><input type="text" class="form-control form-control-sm" data-r placeholder="Replace with" aria-label="Replace with">' +
            '<button type="button" class="btn btn-sm btn-outline-primary text-nowrap" data-one>Replace</button><button type="button" class="btn btn-sm btn-primary text-nowrap" data-all>Replace all</button></div>' +
            '<div class="d-flex flex-wrap gap-3 small">' +
            '<label><input type="checkbox" class="form-check-input me-1" data-case>Match case</label>' +
            '<label><input type="checkbox" class="form-check-input me-1" data-whole>Entire cell</label>' +
            '<label><input type="checkbox" class="form-check-input me-1" data-formulas>Search formulas</label>' +
            '<label><input type="checkbox" class="form-check-input me-1" data-sheets>All sheets</label></div>';
        app.root.appendChild(panel);
        var q = panel.querySelector('[data-q]'), count = panel.querySelector('.crm-sheet-findcount');
        var hits = [], idx = -1;
        var options = function () {
            return { matchCase: panel.querySelector('[data-case]').checked, wholeCell: panel.querySelector('[data-whole]').checked, formulas: panel.querySelector('[data-formulas]').checked, allSheets: panel.querySelector('[data-sheets]').checked };
        };
        var refresh = function (keepIdx) {
            var o = options();
            var run = function () {
                hits = app.actions.findAll(q.value, o);
                if (!keepIdx) idx = -1;
                if (idx >= hits.length) idx = hits.length - 1;
                count.textContent = q.value ? (hits.length ? (idx >= 0 ? (idx + 1) + ' of ' + hits.length : hits.length + ' found') : 'No results') : '';
            };
            if (o.allSheets) app.model.loadAll().then(run); else run();
        };
        var go = function (dir) {
            if (!hits.length) { refresh(); if (!hits.length) return; }
            var a = app.grid.sel.active, cur = app.grid.sheet;
            if (idx < 0) {
                // Start from the active cell.
                idx = dir > 0 ? 0 : hits.length - 1;
                for (var i = 0; i < hits.length; i++) {
                    var h = hits[i];
                    if (h.sheet === cur && (h.r > a.r || (h.r === a.r && h.c > a.c))) { idx = dir > 0 ? i : Math.max(0, i - 1); break; }
                }
            } else {
                idx = (idx + dir + hits.length) % hits.length;
            }
            var hit = hits[idx];
            if (hit.sheet !== app.grid.sheet) app.showSheet(hit.sheet);
            app.grid.findHit = { sheet: hit.sheet, range: { r1: hit.r, c1: hit.c, r2: hit.r, c2: hit.c } };
            app.grid.selectCell(hit.r, hit.c);
            count.textContent = (idx + 1) + ' of ' + hits.length;
        };
        q.addEventListener('input', CS.debounce(function () { refresh(); }, 150));
        panel.querySelectorAll('input[type=checkbox]').forEach(function (c) { c.addEventListener('change', function () { refresh(); }); });
        panel.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { e.preventDefault(); close(); }
            else if (e.key === 'Enter' && e.target === q) { e.preventDefault(); go(e.shiftKey ? -1 : 1); }
            e.stopPropagation();
        });
        var close = function () { panel.remove(); app.grid.findHit = null; app.grid.requestRender(); app.grid.focus(); };
        panel.addEventListener('click', function (e) {
            if (e.target.closest('[data-next]')) go(1);
            else if (e.target.closest('[data-prev]')) go(-1);
            else if (e.target.closest('[data-close]')) close();
            else if (e.target.closest('[data-one]')) {
                if (idx < 0 || !hits[idx]) { go(1); return; }
                var n = app.actions.replaceIn([hits[idx]], q.value, panel.querySelector('[data-r]').value, options());
                refresh(true);
                if (n) go(0);
            } else if (e.target.closest('[data-all]')) {
                var total = app.actions.replaceIn(hits, q.value, panel.querySelector('[data-r]').value, options());
                CS.toast(total ? 'Replaced ' + total + ' occurrence(s).' : 'Nothing to replace.', total ? 'success' : 'info');
                refresh();
            }
        });
        panel.querySelector('[data-replace-row]').style.display = replace && app.model.can.edit ? '' : 'none';
        q.focus();
    };

    // ── Small dialogs ───────────────────────────────────────────────────
    D.link = function (app) {
        var a = app.grid.sel.active, cell = app.model.raw(app.grid.sheet, a.r, a.c);
        var current = cell && cell.v ? String(cell.v) : '';
        var m = /^=HYPERLINK\("((?:[^"]|"")*)"(?:,\s*"((?:[^"]|"")*)")?\)$/i.exec(current);
        var url = m ? m[1].replace(/""/g, '"') : (CS.safeUrl(current) ? current : '');
        var label = m ? (m[2] || '').replace(/""/g, '"') : (url ? '' : current);
        CS.dialog({
            title: 'Insert link', size: 'sm',
            body: '<div class="mb-3"><label class="form-label">Text</label><input type="text" class="form-control" id="crmLinkText" value="' + esc(label) + '"></div>' +
                '<div><label class="form-label">Link (https:// or mailto:)</label><input type="url" class="form-control" id="crmLinkUrl" placeholder="https://example.com" value="' + esc(url) + '" autofocus></div>',
            buttons: [{ label: 'Cancel', cls: 'btn-outline-secondary' }, {
                label: 'Apply', cls: 'btn-primary', action: function (el) {
                    var u = el.querySelector('#crmLinkUrl').value.trim(), t = el.querySelector('#crmLinkText').value.trim();
                    var safe = CS.safeUrl(u);
                    if (!safe) { el.querySelector('#crmLinkUrl').classList.add('is-invalid'); CS.toast('Only http(s):// and mailto: links are allowed.', 'error'); return false; }
                    var v = t && t !== safe ? '=HYPERLINK("' + safe.replace(/"/g, '""') + '","' + t.replace(/"/g, '""') + '")' : safe;
                    app.actions.setValue(app.grid.sheet, a.r, a.c, v);
                },
            }],
        });
    };
    D.currency = function (app) {
        var nf = app.actions.activeFmt().nf || {};
        CS.dialog({
            title: 'Custom currency', size: 'sm',
            body: '<div class="mb-3"><label class="form-label">Symbol</label><input type="text" class="form-control" id="crmCurSym" maxlength="6" value="' + esc(nf.t === 'currency' ? nf.cur || 'Rs' : 'Rs') + '"></div>' +
                '<div><label class="form-label">Decimal places</label><input type="number" min="0" max="10" class="form-control" id="crmCurDec" value="' + (nf.d !== undefined ? nf.d : 2) + '"></div>',
            buttons: [{ label: 'Cancel', cls: 'btn-outline-secondary' }, {
                label: 'Apply', cls: 'btn-primary', action: function (el) {
                    var sym = el.querySelector('#crmCurSym').value.trim() || 'Rs';
                    var d = Math.max(0, Math.min(10, parseInt(el.querySelector('#crmCurDec').value, 10) || 0));
                    app.actions.setNumberFormat({ t: 'currency', cur: sym, d: d });
                },
            }],
        });
    };
    D.resize = function (app, axis, indexes) {
        var cur = axis === 'row' ? app.grid.rowH(indexes[0]) : app.grid.colW(indexes[0]);
        CS.prompt('Resize ' + (axis === 'row' ? 'row' : 'column') + (indexes.length > 1 ? 's' : ''), (axis === 'row' ? 'Height' : 'Width') + ' in pixels (default ' + (axis === 'row' ? CS.Grid.DEFAULT_H : CS.Grid.DEFAULT_W) + ')', String(cur || ''), { ok: 'Resize' }).then(function (v) {
            if (v === null) return;
            var n = parseInt(v, 10);
            var min = axis === 'row' ? 12 : 20, max = axis === 'row' ? 1000 : 2000;
            if (!(n >= min && n <= max)) { CS.toast('Enter a size between ' + min + ' and ' + max + '.', 'error'); return; }
            app.actions.resizeLines(axis, indexes, n);
        });
    };
    D.shortcuts = function () {
        var mod = CS.isMac ? '⌘' : 'Ctrl';
        var rows = [
            ['Copy / Cut / Paste', mod + '+C / ' + mod + '+X / ' + mod + '+V'], ['Paste values only', mod + '+Shift+V'], ['Undo / Redo', mod + '+Z / ' + mod + '+Y'],
            ['Save now', mod + '+S'], ['Find / Find and replace', mod + '+F / ' + mod + '+H'], ['Bold / Italic / Underline', mod + '+B / ' + mod + '+I / ' + mod + '+U'],
            ['Edit cell', 'F2 or Enter, or just start typing'], ['New line in a cell', 'Alt+Enter'], ['Confirm and move down / up', 'Enter / Shift+Enter'],
            ['Confirm and move right / left', 'Tab / Shift+Tab'], ['Cancel editing', 'Esc'], ['Clear cells', 'Delete or Backspace'],
            ['Extend selection', 'Shift+Arrow'], ['Jump to edge of data', mod + '+Arrow'], ['Select all', mod + '+A'], ['Select column / row', mod + '+Space / Shift+Space'],
            ['Fill down / right', mod + '+D / ' + mod + '+R'], ['Open dropdown list', 'Alt+↓'], ['Open link in cell', mod + '+click'],
        ];
        CS.dialog({
            title: 'Keyboard shortcuts', size: 'lg',
            body: '<table class="table table-sm no-datatable mb-0"><tbody>' + rows.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td class="text-end"><kbd>' + esc(r[1]) + '</kbd></td></tr>'; }).join('') + '</tbody></table>',
        });
    };
    D.functions = function (app) {
        var list = X.functions();
        var body = document.createElement('div');
        body.innerHTML = '<input type="search" class="form-control mb-2" placeholder="Search functions" aria-label="Search functions">' +
            '<div class="crm-sheet-fnlist">' + list.map(function (f) {
                return '<div class="crm-sheet-fnrow" data-name="' + esc(f.name.toLowerCase()) + ' ' + esc(f.desc.toLowerCase()) + '"><code>' + esc(f.syntax) + '</code><div class="small text-muted">' + esc(f.desc) + '</div>' +
                    (app && app.model.can.edit ? '<button type="button" class="btn btn-sm btn-link px-0" data-insert="' + esc(f.name) + '">Insert</button>' : '') + '</div>';
            }).join('') + '</div><p class="small text-muted mt-2 mb-0">Operators: + - * / ^ (power) &amp; (join text) = &lt;&gt; &lt; &gt; &lt;= &gt;=. References: A1, $A$1, A1:B10, A:A, \'Other sheet\'!A1.</p>';
        body.querySelector('input').addEventListener('input', function (e) {
            var q = e.target.value.toLowerCase();
            body.querySelectorAll('.crm-sheet-fnrow').forEach(function (r) { r.style.display = r.dataset.name.indexOf(q) >= 0 ? '' : 'none'; });
        });
        var dlg = CS.dialog({ title: 'Functions', body: body, size: 'lg' });
        body.addEventListener('click', function (e) {
            var b = e.target.closest('[data-insert]');
            if (!b) return;
            dlg.crmModal.hide();
            setTimeout(function () { app.grid.startEdit('=' + b.dataset.insert + '(', 'edit'); }, 300);
        });
    };
})();
