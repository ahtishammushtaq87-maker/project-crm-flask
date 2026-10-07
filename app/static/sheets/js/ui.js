/* Spreadsheet module - editor page: menus, toolbar, formula bar, sheet tabs,
 * status/autosave indicator, context menus and keyboard shortcuts. */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var FM = CS.Format, D = CS.Dialogs;
    var esc = CS.esc;

    var PALETTE = [
        '#000000', '#434343', '#666666', '#999999', '#b7b7b7', '#cccccc', '#d9d9d9', '#efefef', '#f3f3f3', '#ffffff',
        '#980000', '#ff0000', '#ff9900', '#ffff00', '#00ff00', '#00ffff', '#4a86e8', '#0000ff', '#9900ff', '#ff00ff',
        '#e6b8af', '#f4cccc', '#fce5cd', '#fff2cc', '#d9ead3', '#d0e0e3', '#c9daf8', '#cfe2f3', '#d9d2e9', '#ead1dc',
        '#dd7e6b', '#ea9999', '#f9cb9c', '#ffe599', '#b6d7a8', '#a2c4c9', '#a4c2f4', '#9fc5e8', '#b4a7d6', '#d5a6bd',
        '#cc4125', '#e06666', '#f6b26b', '#ffd966', '#93c47d', '#76a5af', '#6d9eeb', '#6fa8dc', '#8e7cc3', '#c27ba0',
        '#a61c00', '#cc0000', '#e69138', '#f1c232', '#6aa84f', '#45818e', '#3c78d8', '#3d85c6', '#674ea7', '#a64d79',
    ];
    var FONT_SIZES = [6, 7, 8, 9, 10, 11, 12, 14, 18, 24, 36];
    var FONTS = ['Arial', 'Calibri', 'Courier New', 'Georgia', 'Roboto', 'Segoe UI', 'Tahoma', 'Times New Roman', 'Trebuchet MS', 'Verdana'];
    var TAB_COLORS = ['#ea4335', '#fbbc04', '#34a853', '#4285f4', '#9c27b0', '#ff6d01', '#46bdc6', '#7f8c8d'];

    function App(root) {
        this.root = root;
        this.bookId = +root.dataset.bookId;
        document.body.dataset.crmSheetUser = root.dataset.userId;
        this.el = function (sel) { return root.querySelector(sel); };
        this.start();
    }
    CS.App = App;
    var U = App.prototype;

    U.start = function () {
        var self = this;
        this.el('.crm-sheet-gridhost').innerHTML = '<div class="crm-sheet-loading crm-sheet-loading-big"><span class="spinner-border text-primary me-2"></span>Loading spreadsheet…</div>';
        CS.api('GET', '/spreadsheets/' + this.bookId).then(function (res) {
            if (!res.ok) {
                self.el('.crm-sheet-gridhost').innerHTML = '<div class="crm-sheet-empty"><i class="fas fa-circle-exclamation fa-2x text-danger mb-2"></i><div class="fw-semibold">' + esc(CS.errorText(res, 'Spreadsheet not found.')) + '</div><a class="btn btn-primary btn-sm mt-3" href="' + CS.base() + '/">Back to spreadsheets</a></div>';
                return;
            }
            self.init(res.data.book);
        });
    };

    U.init = function (book) {
        var self = this;
        this.model = new CS.Workbook(book);
        var host = this.el('.crm-sheet-gridhost');
        host.innerHTML = '';
        this.grid = new CS.Grid(host, this.model, {
            onSelect: function () { self.onSelection(); },
            onCommit: function (sheet, r, c, value) { self.actions.setValue(sheet, r, c, value); },
            onClear: function () { self.actions.clearContents(); },
            onEditChange: function (v) { self.syncFormulaBar(v); },
            validate: function (sheet, r, c, raw) { return self.actions.validate(sheet, r, c, raw); },
            onInvalid: function (msg, warnOnly) { CS.toast(msg, warnOnly ? 'warning' : 'error'); },
            onReadOnly: function () { self.readOnly(); },
            onResize: function (axis, idx, size) { self.actions.resizeLines(axis, idx, size); },
            onAutofit: function (axis, map) { self.actions.setSizes(axis, map); },
            onContextMenu: function (hit, x, y) { self.contextMenu(hit, x, y); },
            onKey: function (e) { return self.shortcut(e); },
            onPaste: function (text, mode, clip, parse) { self.actions.paste(text, mode, clip, parse); },
            onFilterButton: function (col, el) { D.filterMenu(self, col, el); },
            onAddRows: function () { self.actions.addRows(1000); },
            onUnhide: function (axis, at) { self.actions.unhideLines(axis, at); },
        });
        this.actions = new CS.Actions(this.model, this.grid, this);
        this.bindModel();
        this.bindHeader();
        this.bindToolbar();
        this.bindFormulaBar();
        this.bindTabs();
        this.sizeToViewport();
        window.addEventListener('resize', function () { self.sizeToViewport(); });
        window.addEventListener('beforeunload', function (e) {
            if (self.model.hasPending()) {
                self.model.save();
                e.preventDefault();
                e.returnValue = 'Changes are still being saved.';
                return e.returnValue;
            }
        });
        // After a menu/popover closes, keyboard focus returns to the grid so
        // shortcuts (Ctrl+Z, arrows...) keep working.
        CS.afterMenuAction = function () {
            setTimeout(function () {
                var ae = document.activeElement;
                if ((!ae || ae === document.body) && !document.querySelector('.modal.show, .crm-sheet-findpanel :focus')) self.grid.focus();
            }, 0);
        };
        document.addEventListener('keydown', function (e) {
            if (e.target !== document.body || document.querySelector('.modal.show') || e.defaultPrevented) return;
            self.grid.focus();
            if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (self.model.can.edit) self.grid.startEdit(e.key, 'enter'); else self.readOnly();
                return;
            }
            self.grid.onKey(e);
        });
        this.refreshMeta();
        this.applyPermissions();
        var first = this.model.visibleSheets()[0] || this.model.sheets[0];
        this.showSheet(first);
        this.renderStatus();
        setInterval(function () { self.renderStatus(); }, 15000);
    };

    /** Fill the browser window below the CRM header. */
    U.sizeToViewport = function () {
        var top = this.root.getBoundingClientRect().top + window.scrollY;
        var h = Math.max(420, window.innerHeight - top - 16);
        if (document.fullscreenElement === this.root) h = window.innerHeight;
        this.root.style.height = h + 'px';
        if (this.grid) this.grid.requestRender();
    };

    U.readOnly = function () {
        CS.toast('You have view-only access to this spreadsheet.', 'info');
    };

    // ── Sheets ──────────────────────────────────────────────────────────
    U.showSheet = function (sheet) {
        var self = this;
        if (!sheet) return;
        if (sheet === this.activeSheet && this.grid.sheet === sheet) { this.grid.focus(); return; }
        if (this.grid.sheet && this.grid.sheet !== sheet) this.grid.saveViewState();
        this.grid.commitIfEditing();
        this.activeSheet = sheet;
        this.renderTabs();
        if (!sheet.loaded) {
            this.el('.crm-sheet-gridhost').classList.add('crm-sheet-busy');
            this.model.loadSheet(sheet).then(function () {
                self.el('.crm-sheet-gridhost').classList.remove('crm-sheet-busy');
                if (self.activeSheet === sheet) { self.grid.setSheet(sheet); self.grid.focus(); }
            }).catch(function (e) {
                self.el('.crm-sheet-gridhost').classList.remove('crm-sheet-busy');
                CS.toast(e.message, 'error');
            });
        } else {
            this.grid.setSheet(sheet);
            this.grid.focus();
        }
    };

    // ── Model events ────────────────────────────────────────────────────
    U.bindModel = function () {
        var self = this, m = this.model;
        var rerender = function (e) {
            if (e && e.sheet && e.sheet !== self.grid.sheet && !e.remote) return;
            self.grid.relayout();
            self.grid.requestRender();
            self.onSelection();
        };
        m.on('cells', function (e) {
            if (self.grid.sheet && self.grid.sheet.props.filter) self.grid.relayout();
            self.grid.requestRender();
            self.onSelection();
            void e;
        });
        m.on('layout', function (e) { self.grid.mergeIndex = null; rerender(e); });
        m.on('structure', function (e) { self.grid.mergeIndex = null; rerender(e); });
        m.on('loaded', function (e) { if (e.sheet === self.grid.sheet) rerender(); });
        m.on('sheets', function () {
            if (self.activeSheet && m.sheets.indexOf(self.activeSheet) < 0) {
                self.showSheet(m.visibleSheets()[0] || m.sheets[0]);
            } else if (self.activeSheet && self.activeSheet.hidden) {
                self.showSheet(m.visibleSheets()[0]);
            }
            self.renderTabs();
        });
        m.on('status', function () { self.renderStatus(); });
        m.on('history', function () { self.updateToolbarState(); });
        m.on('meta', function () { self.refreshMeta(); });
        m.on('permissions', function () { self.applyPermissions(); });
        m.on('reloaded', function () {
            var s = m.sheetById(self.activeSheet && self.activeSheet.id) || m.visibleSheets()[0] || m.sheets[0];
            self.activeSheet = null;
            self.grid.sheet = null;
            self.showSheet(s);
            self.refreshMeta();
            self.applyPermissions();
        });
        m.on('conflict', function (data) { self.conflictDialog(data); });
        m.on('rejected', function (e) {
            CS.toast(e.message, 'error');
            if (!m.hasPending()) m.reloadAll();
        });
        var remoteToast = CS.debounce(function (e) {
            CS.toast((e.by || 'Someone') + (e.structure ? ' rearranged this spreadsheet - it was reloaded.' : ' updated this spreadsheet.'), 'info');
        }, 1500);
        m.on('remote-edit', remoteToast);
        m.on('remote-structure', function (d) {
            var banner = self.el('.crm-sheet-banner');
            banner.innerHTML = '<i class="fas fa-triangle-exclamation me-2"></i><span>' + esc((d.updated_by || 'Another user') + ' changed rows, columns or sheets. Reload to see the latest version.') +
                '</span><button type="button" class="btn btn-sm btn-warning ms-auto" data-reload>Reload latest</button>';
            banner.style.display = 'flex';
            banner.querySelector('[data-reload]').onclick = function () {
                banner.style.display = 'none';
                var after = function () { m.discardAndReload(); };
                if (m.hasPending()) {
                    CS.confirm('You have changes that are not saved yet. Reloading discards them.', { ok: 'Discard and reload', danger: true }).then(function (ok) { if (ok) after(); });
                } else after();
            };
        });
        m.on('lost-access', function () {
            CS.dialog({
                title: 'Access removed',
                body: '<p class="mb-0">This spreadsheet was deleted or is no longer shared with you.</p>',
                buttons: [{ label: 'Back to spreadsheets', cls: 'btn-primary', action: function () { window.location.href = CS.base() + '/'; } }],
            });
            m.destroy();
        });
    };

    U.conflictDialog = function (data) {
        var self = this;
        if (this.conflictOpen) return;
        this.conflictOpen = true;
        var who = data && data.by ? data.by : 'another user';
        var structural = data && data.structural;
        CS.dialog({
            title: 'This spreadsheet was modified',
            body: '<p>' + esc(data && data.error ? data.error : 'This spreadsheet was modified by ' + who + '.') + '</p>' +
                '<p class="mb-0 small text-muted">' + (structural
                    ? '<b>Reload latest</b> discards your unsaved changes. <b>Keep my changes</b> saves them anyway - because rows or columns moved, they may land in different cells than you expect.'
                    : '<b>Reload latest</b> discards your unsaved changes. <b>Keep my changes</b> overwrites ' + esc(who) + '\'s version of those cells.') + '</p>',
            buttons: [
                { label: 'Reload latest', cls: 'btn-outline-secondary', action: function () { self.conflictOpen = false; self.model.discardAndReload(); } },
                { label: 'Keep my changes', cls: 'btn-primary', action: function () { self.conflictOpen = false; self.model.forceSave(); } },
            ],
            onClose: function () { self.conflictOpen = false; },
        });
    };

    // ── Header / status ─────────────────────────────────────────────────
    U.refreshMeta = function () {
        var m = this.model;
        var title = this.el('.crm-sheet-title');
        if (document.activeElement !== title) title.value = m.name;
        document.title = m.name + ' - Spreadsheet';
        this.el('.crm-sheet-star').innerHTML = '<i class="' + (m.favorite ? 'fas text-warning' : 'far') + ' fa-star"></i>';
        this.el('.crm-sheet-star').setAttribute('aria-pressed', m.favorite ? 'true' : 'false');
        this.el('.crm-sheet-ownerinfo').textContent = 'Owner: ' + m.owner + (m.sharedCount ? ' · Shared with ' + m.sharedCount + ' user' + (m.sharedCount > 1 ? 's' : '') : '');
    };
    U.renderStatus = function () {
        var m = this.model, el = this.el('.crm-sheet-savestate');
        if (!m) return;
        var html;
        switch (m.status) {
            case 'saving': html = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…'; break;
            case 'pending': html = '<i class="fas fa-pen me-1"></i>Unsaved changes'; break;
            case 'error': html = '<span class="text-danger"><i class="fas fa-circle-exclamation me-1"></i>' + esc(m.statusMessage || 'Unable to save changes') + '</span> <button type="button" class="btn btn-link btn-sm p-0 ms-1" data-retry>Retry</button>'; break;
            case 'conflict': html = '<span class="text-warning"><i class="fas fa-triangle-exclamation me-1"></i>Conflict - choose how to continue</span>'; break;
            default: html = '<i class="fas fa-check-circle text-success me-1"></i>Saved' + (m.lastSaved ? ' · ' + esc(CS.timeAgo(m.lastSaved.toISOString())) : '');
        }
        el.innerHTML = html;
        var self = this;
        var retry = el.querySelector('[data-retry]');
        if (retry) retry.onclick = function () { self.model.retry(); };
    };

    U.applyPermissions = function () {
        var can = this.model.can, root = this.root;
        root.classList.toggle('crm-sheet-readonly', !can.edit);
        this.el('.crm-sheet-rolebadge').innerHTML = can.edit
            ? '<span class="badge bg-success-subtle text-success border"><i class="fas fa-pen me-1"></i>' + esc(can.role_label) + '</span>'
            : '<span class="badge bg-secondary"><i class="fas fa-eye me-1"></i>View only</span>';
        this.el('.crm-sheet-title').readOnly = !can.settings;
        this.el('.crm-sheet-formula').readOnly = !can.edit;
        this.el('.crm-sheet-sharebtn').innerHTML = can.share ? '<i class="fas fa-user-plus me-1"></i>Share' : '<i class="fas fa-users me-1"></i>Access';
        root.querySelectorAll('[data-edit-only]').forEach(function (b) { b.disabled = !can.edit; });
        this.updateToolbarState();
    };

    U.bindHeader = function () {
        var self = this, title = this.el('.crm-sheet-title');
        var commitTitle = function () {
            var v = title.value.trim();
            if (!v || v === self.model.name || !self.model.can.settings) { title.value = self.model.name; return; }
            CS.api('PATCH', '/spreadsheets/' + self.model.id, { name: v }).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); title.value = self.model.name; return; }
                self.model.name = res.data.book.name;
                self.refreshMeta();
                CS.toast('Renamed.', 'success');
            });
        };
        title.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); title.blur(); }
            if (e.key === 'Escape') { title.value = self.model.name; title.blur(); }
        });
        title.addEventListener('blur', commitTitle);
        this.el('.crm-sheet-star').addEventListener('click', function () {
            var fav = !self.model.favorite;
            CS.api('POST', '/spreadsheets/' + self.model.id + '/favorite', { favorite: fav }).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                self.model.favorite = res.data.favorite;
                self.refreshMeta();
            });
        });
        this.el('.crm-sheet-sharebtn').addEventListener('click', function () { D.share(self, null, { onChange: function () { self.refreshShareCount(); } }); });
        this.root.querySelectorAll('[data-menu]').forEach(function (btn) {
            btn.addEventListener('click', function () { CS.menu(self.menuItems(btn.dataset.menu), 0, 0, btn); });
            btn.addEventListener('mouseenter', function () {
                if (document.querySelector('.crm-sheet-menu-root') && !document.querySelector('.crm-sheet-popover')) CS.menu(self.menuItems(btn.dataset.menu), 0, 0, btn);
            });
        });
        document.addEventListener('fullscreenchange', function () { self.sizeToViewport(); });
    };
    U.refreshShareCount = function () {
        var self = this;
        CS.api('GET', '/spreadsheets/' + this.model.id).then(function (res) {
            if (res.ok) { self.model.sharedCount = res.data.book.shared_count; self.refreshMeta(); }
        });
    };

    // ── Selection → formula bar, toolbar, stats ─────────────────────────
    U.onSelection = function () {
        var g = this.grid;
        if (!g.sheet) return;
        var a = g.sel.active, rg = g.activeRange();
        var single = g.sel.ranges.length === 1 && rg.r1 === rg.r2 && rg.c1 === rg.c2;
        var m = g.mergeAt(a.r, a.c);
        var nameText = single || (m && m.r1 === rg.r1 && m.c1 === rg.c1 && m.r2 === rg.r2 && m.c2 === rg.c2) ? CS.addr(a.r, a.c)
            : (rg.r1 === 0 && rg.r2 >= g.nRows - 1 ? CS.colName(rg.c1) + (rg.c2 !== rg.c1 ? ':' + CS.colName(rg.c2) : '')
                : rg.c1 === 0 && rg.c2 >= g.nCols - 1 ? (rg.r1 + 1) + (rg.r2 !== rg.r1 ? ':' + (rg.r2 + 1) : '') : CS.rangeStr(rg));
        var nb = this.el('.crm-sheet-namebox');
        if (document.activeElement !== nb) nb.value = nameText;
        if (!g.isEditing()) this.syncFormulaBar(null);
        this.updateToolbarState();
        this.updateStats();
    };
    U.syncFormulaBar = function (editingValue) {
        var fb = this.el('.crm-sheet-formula'), g = this.grid;
        if (document.activeElement === fb && editingValue === null) return;
        if (editingValue !== null && editingValue !== undefined) { if (document.activeElement !== fb) fb.value = editingValue; return; }
        var a = g.sel.active, cell = this.model.raw(g.sheet, a.r, a.c);
        var v = cell && cell.v !== null && cell.v !== undefined ? String(cell.v) : '';
        if (v && v.charAt(0) !== '=' && cell.f && cell.f.nf && /^(date|datetime|time)$/.test(cell.f.nf.t)) {
            var p = FM.parse(v);
            if (p.t === 'n' && !p.kind) v = FM.display(p, cell.f.nf);
        }
        fb.value = v;
    };
    U.updateStats = function () {
        var g = this.grid, m = this.model, el = this.el('.crm-sheet-stats');
        var ranges = g.selectedRanges(), used = m.used(g.sheet);
        var sum = 0, count = 0, filled = 0, cells = 0;
        var single = ranges.length === 1 && ranges[0].r1 === ranges[0].r2 && ranges[0].c1 === ranges[0].c2;
        if (!single) {
            for (var i = 0; i < ranges.length && cells < 50000; i++) {
                var rg = ranges[i];
                for (var r = rg.r1; r <= Math.min(rg.r2, used.rows - 1); r++) for (var c = rg.c1; c <= Math.min(rg.c2, used.cols - 1); c++) {
                    if (++cells > 50000) break;
                    if (g.isHiddenRow(r)) continue;
                    var v = m.value(g.sheet, r, c);
                    if (v.t !== 'empty') filled++;
                    if (v.t === 'n') { sum += v.v; count++; }
                }
            }
        }
        if (single || !filled) { el.innerHTML = ''; return; }
        var fmt = function (n) { return FM.grouped(n, Number.isInteger(n) ? 0 : 2); };
        el.innerHTML = count
            ? '<span>Sum: <b>' + fmt(sum) + '</b></span><span>Average: <b>' + fmt(sum / count) + '</b></span><span>Count: <b>' + filled + '</b></span>'
            : '<span>Count: <b>' + filled + '</b></span>';
    };

    // ── Formula bar ─────────────────────────────────────────────────────
    U.bindFormulaBar = function () {
        var self = this, fb = this.el('.crm-sheet-formula'), nb = this.el('.crm-sheet-namebox');
        fb.addEventListener('focus', function () {
            if (!self.model.can.edit) return;
            if (!self.grid.isEditing()) self.grid.startEdit(null, 'edit');
            self.grid.input.style.visibility = 'hidden';
            setTimeout(function () { fb.focus(); }, 0);
        });
        fb.addEventListener('input', function () {
            self.grid.editFromBar(fb.value);
            self.grid.updateAutocomplete(fb);
        });
        fb.addEventListener('keydown', function (e) {
            if (self.grid.acOpen() && self.grid.acKey(e)) return;
            if (e.key === 'Enter' && !e.altKey) { e.preventDefault(); self.grid.input.value = fb.value; self.grid.input.style.visibility = ''; self.grid.commitEdit(e.shiftKey ? -1 : 1, 0); }
            else if (e.key === 'Tab') { e.preventDefault(); self.grid.input.value = fb.value; self.grid.input.style.visibility = ''; self.grid.commitEdit(0, e.shiftKey ? -1 : 1); }
            else if (e.key === 'Escape') { e.preventDefault(); self.grid.input.style.visibility = ''; self.grid.cancelEdit(); self.syncFormulaBar(null); }
        });
        fb.addEventListener('blur', function () {
            setTimeout(function () {
                if (document.activeElement === fb || document.activeElement === self.grid.input) return;
                self.grid.input.style.visibility = '';
                if (self.grid.isEditing()) { self.grid.input.value = fb.value; self.grid.commitEdit(0, 0); }
                self.grid.hideAutocomplete();
            }, 0);
        });
        nb.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var g = self.grid, text = nb.value.trim(), m;
                var sheet = g.sheet;
                if ((m = /^(.+)!(.+)$/.exec(text))) {
                    var target = self.model.sheetByName(m[1].replace(/^'|'$/g, ''));
                    if (target) { self.showSheet(target); text = m[2]; }
                }
                var rg = CS.parseRange(text, g.nRows, g.nCols);
                if (!rg || rg.r2 >= g.nRows || rg.c2 >= g.nCols) { CS.toast('Enter a cell or range like B5 or A1:D10.', 'error'); return; }
                g.select(rg, { r: rg.r1, c: rg.c1 });
                g.scrollIntoView(rg.r1, rg.c1);
                g.focus();
                void sheet;
            } else if (e.key === 'Escape') { nb.blur(); self.grid.focus(); self.onSelection(); }
        });
        nb.addEventListener('focus', function () { nb.select(); });
    };

    // ── Toolbar ─────────────────────────────────────────────────────────
    U.bindToolbar = function () {
        var self = this;
        this.root.querySelectorAll('[data-cmd]').forEach(function (b) {
            b.addEventListener('mousedown', function (e) { e.preventDefault(); }); // keep cell editing focus
            b.addEventListener('click', function () { self.command(b.dataset.cmd, b); });
        });
    };
    U.updateToolbarState = function () {
        if (!this.grid || !this.grid.sheet) return;
        var f = this.actions.activeFmt(), root = this.root, m = this.model;
        var setOn = function (cmd, on) { var b = root.querySelector('[data-cmd="' + cmd + '"]'); if (b) { b.classList.toggle('crm-sheet-on', !!on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); } };
        setOn('bold', f.b); setOn('italic', f.i); setOn('underline', f.u); setOn('strike', f.s);
        setOn('filter', !!this.grid.sheet.props.filter);
        var und = root.querySelector('[data-cmd="undo"]'), red = root.querySelector('[data-cmd="redo"]');
        if (und) und.disabled = !m.can.edit || !m.canUndo();
        if (red) red.disabled = !m.can.edit || !m.canRedo();
        var fs = root.querySelector('.crm-sheet-fontsize');
        if (fs) fs.textContent = f.fs || 10;
        var ff = root.querySelector('.crm-sheet-fontname');
        if (ff) ff.textContent = f.ff || 'Default';
        var tc = root.querySelector('[data-cmd="color"] .crm-sheet-swatchbar'), bg = root.querySelector('[data-cmd="fill"] .crm-sheet-swatchbar');
        if (tc) tc.style.background = f.c || '#000000';
        if (bg) bg.style.background = f.bg || 'transparent';
        var exportOk = m.can.export;
        root.querySelectorAll('[data-export-only]').forEach(function (b) { b.disabled = !exportOk; });
    };

    U.colorPicker = function (anchor, current, onPick, label) {
        var html = '<div class="crm-sheet-palette" role="grid" aria-label="' + esc(label) + '">' +
            '<button type="button" class="crm-sheet-reset" data-color=""><i class="fas fa-rotate-left me-1"></i>Reset</button>' +
            '<div class="crm-sheet-swatches">' + PALETTE.map(function (c) {
                return '<button type="button" class="crm-sheet-swatch' + (c === current ? ' crm-sheet-on' : '') + '" style="background:' + c + '" data-color="' + c + '" title="' + c + '" aria-label="' + c + '"></button>';
            }).join('') + '</div><label class="crm-sheet-custom">Custom <input type="color" value="' + esc(current || '#000000') + '"></label></div>';
        var el = CS.popover(anchor, html);
        el.addEventListener('click', function (e) {
            var b = e.target.closest('[data-color]');
            if (b) { CS.closeMenu(); onPick(b.dataset.color || null); }
        });
        el.querySelector('input[type=color]').addEventListener('change', function (e) { CS.closeMenu(); onPick(e.target.value); });
    };

    U.borderPicker = function (anchor) {
        var self = this, spec = this.borderSpec || (this.borderSpec = { w: 1, s: 'solid', c: '#000000' });
        var kinds = [['all', 'fa-border-all', 'All borders'], ['inner', 'fa-table-cells', 'Inner borders'], ['horizontal', 'fa-grip-lines', 'Horizontal borders'], ['vertical', 'fa-grip-lines-vertical', 'Vertical borders'],
            ['outer', 'fa-square', 'Outer border'], ['left', 'fa-arrow-left', 'Left border'], ['top', 'fa-arrow-up', 'Top border'], ['right', 'fa-arrow-right', 'Right border'], ['bottom', 'fa-arrow-down', 'Bottom border'], ['none', 'fa-border-none', 'Clear borders']];
        var html = '<div class="crm-sheet-borders"><div class="crm-sheet-borderkinds">' + kinds.map(function (k) {
            return '<button type="button" data-kind="' + k[0] + '" title="' + k[2] + '" aria-label="' + k[2] + '"><i class="fas ' + k[1] + '"></i></button>';
        }).join('') + '</div><div class="crm-sheet-borderopts">' +
            '<label class="small">Style <select class="form-select form-select-sm" data-s>' + ['solid', 'dashed', 'dotted', 'double'].map(function (s) { return '<option' + (s === spec.s ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select></label>' +
            '<label class="small">Width <select class="form-select form-select-sm" data-w>' + [1, 2, 3].map(function (w) { return '<option value="' + w + '"' + (w === spec.w ? ' selected' : '') + '>' + w + 'px</option>'; }).join('') + '</select></label>' +
            '<label class="small">Colour <input type="color" class="form-control form-control-color form-control-sm" data-c value="' + esc(spec.c) + '"></label></div></div>';
        var el = CS.popover(anchor, html);
        el.addEventListener('change', function () {
            spec.s = el.querySelector('[data-s]').value; spec.w = +el.querySelector('[data-w]').value; spec.c = el.querySelector('[data-c]').value;
        });
        el.addEventListener('click', function (e) {
            var b = e.target.closest('[data-kind]');
            if (b) { CS.closeMenu(); self.actions.borders(b.dataset.kind, spec); self.grid.focus(); }
        });
    };

    U.command = function (cmd, btn) {
        var A = this.actions, g = this.grid, self = this;
        var editCmds = { undo: 1, redo: 1, paintformat: 1, currency: 1, percent: 1, decless: 1, decmore: 1, numfmt: 1, font: 1, fontsize: 1, fsminus: 1, fsplus: 1, bold: 1, italic: 1, strike: 1, underline: 1, color: 1, fill: 1, borders: 1, merge: 1, halign: 1, valign: 1, wrap: 1, link: 1, functions: 1, clearformat: 1, filter: 0 };
        if (editCmds[cmd] && !this.model.can.edit) { this.readOnly(); return; }
        var keepFocus = true;
        switch (cmd) {
            case 'undo': this.undo(); break;
            case 'redo': this.redo(); break;
            case 'print': if (this.model.can.export) D.print(this); else CS.toast('The owner has not allowed viewers to print.', 'info'); break;
            case 'paintformat': {
                var f = JSON.parse(JSON.stringify(A.activeFmt()));
                this.paintFormat = f;
                btn.classList.add('crm-sheet-on');
                CS.toast('Select the cells to apply this format to.', 'info');
                var once = function () {
                    if (!self.paintFormat) return;
                    var pf = self.paintFormat;
                    self.paintFormat = null;
                    btn.classList.remove('crm-sheet-on');
                    document.removeEventListener('mouseup', once, true);
                    setTimeout(function () { A.formatCells(function () { return JSON.parse(JSON.stringify(pf)); }, 'Paint format'); }, 0);
                };
                setTimeout(function () { document.addEventListener('mouseup', once, true); }, 0);
                break;
            }
            case 'currency': A.setNumberFormat({ t: 'currency', cur: 'Rs', d: 0 }); break;
            case 'percent': A.setNumberFormat({ t: 'percent', d: 0 }); break;
            case 'decless': A.adjustDecimals(-1); break;
            case 'decmore': A.adjustDecimals(1); break;
            case 'numfmt': {
                var cur = A.activeFmt().nf || { t: 'auto' };
                var items = FM.NUMBER_FORMATS.map(function (n) {
                    return { html: esc(n.label) + ' <span class="crm-sheet-menu-hint">' + esc(n.sample) + '</span>', checked: cur.t === n.t && (n.t !== 'currency' || cur.cur === n.cur), action: function () { A.setNumberFormat(n); } };
                });
                items.push({ divider: true }, { label: 'Custom currency…', action: function () { D.currency(self); } });
                CS.menu(items, 0, 0, btn);
                keepFocus = false;
                break;
            }
            case 'font':
                CS.menu(FONTS.map(function (n) { return { html: '<span style="font-family:\'' + n + '\'">' + esc(n) + '</span>', checked: A.activeFmt().ff === n, action: function () { A.setStyle('ff', n, 'Font'); } }; })
                    .concat([{ divider: true }, { label: 'Default', action: function () { A.setStyle('ff', null, 'Font'); } }]), 0, 0, btn);
                keepFocus = false;
                break;
            case 'fontsize':
                CS.menu(FONT_SIZES.map(function (n) { return { label: String(n), checked: (A.activeFmt().fs || 10) === n, action: function () { A.setStyle('fs', n === 10 ? null : n, 'Font size'); } }; }), 0, 0, btn);
                keepFocus = false;
                break;
            case 'fsminus': case 'fsplus': {
                var size = A.activeFmt().fs || 10;
                var next = cmd === 'fsplus' ? FONT_SIZES.filter(function (s) { return s > size; })[0] : FONT_SIZES.filter(function (s) { return s < size; }).pop();
                if (next) A.setStyle('fs', next === 10 ? null : next, 'Font size');
                break;
            }
            case 'bold': A.toggleStyle('b'); break;
            case 'italic': A.toggleStyle('i'); break;
            case 'underline': A.toggleStyle('u'); break;
            case 'strike': A.toggleStyle('s'); break;
            case 'color': this.colorPicker(btn, A.activeFmt().c, function (c) { A.setStyle('c', c, 'Text colour'); g.focus(); }, 'Text colour'); keepFocus = false; break;
            case 'fill': this.colorPicker(btn, A.activeFmt().bg, function (c) { A.setStyle('bg', c, 'Fill colour'); g.focus(); }, 'Fill colour'); keepFocus = false; break;
            case 'borders': this.borderPicker(btn); keepFocus = false; break;
            case 'merge':
                CS.menu([
                    { label: 'Merge all', icon: 'fas fa-object-group', action: function () { A.merge('all'); } },
                    { label: 'Merge horizontally', icon: 'fas fa-arrows-left-right', action: function () { A.merge('horizontal'); } },
                    { label: 'Merge vertically', icon: 'fas fa-arrows-up-down', action: function () { A.merge('vertical'); } },
                    { label: 'Unmerge', icon: 'fas fa-object-ungroup', action: function () { A.merge('unmerge'); } },
                ], 0, 0, btn);
                keepFocus = false;
                break;
            case 'halign':
                CS.menu([['left', 'fa-align-left', 'Left'], ['center', 'fa-align-center', 'Center'], ['right', 'fa-align-right', 'Right']].map(function (x) {
                    return { label: x[2], icon: 'fas ' + x[1], checked: A.activeFmt().ha === x[0], action: function () { A.setStyle('ha', x[0], 'Align'); } };
                }), 0, 0, btn);
                keepFocus = false;
                break;
            case 'valign':
                CS.menu([['top', 'Top'], ['middle', 'Middle'], ['bottom', 'Bottom']].map(function (x) {
                    return { label: x[1], checked: (A.activeFmt().va || 'bottom') === x[0], action: function () { A.setStyle('va', x[0] === 'bottom' ? null : x[0], 'Vertical align'); } };
                }), 0, 0, btn);
                keepFocus = false;
                break;
            case 'wrap':
                CS.menu([['overflow', 'Overflow'], ['wrap', 'Wrap'], ['clip', 'Clip']].map(function (x) {
                    return { label: x[1], checked: (A.activeFmt().wrap || 'overflow') === x[0], action: function () { A.setStyle('wrap', x[0] === 'overflow' ? null : x[0], 'Text wrapping'); } };
                }), 0, 0, btn);
                keepFocus = false;
                break;
            case 'link': D.link(this); keepFocus = false; break;
            case 'filter': A.toggleFilter(); break;
            case 'functions':
                CS.menu(['SUM', 'AVERAGE', 'COUNT', 'MAX', 'MIN', 'IF'].map(function (n) {
                    return { label: n, action: function () { self.insertFunction(n); } };
                }).concat([{ divider: true }, { label: 'All functions…', action: function () { D.functions(self); } }]), 0, 0, btn);
                keepFocus = false;
                break;
            case 'clearformat': A.clearFormatting(); break;
            case 'find': D.find(this, false); keepFocus = false; break;
        }
        if (keepFocus) g.focus();
        this.updateToolbarState();
    };

    /** Σ: on a selected column of numbers, put the total underneath. */
    U.insertFunction = function (name) {
        var g = this.grid, rg = g.activeRange();
        if (rg.r2 > rg.r1 && rg.c1 === rg.c2 && rg.r2 < g.nRows - 1) {
            var target = rg.r2 + 1;
            this.actions.setValue(g.sheet, target, rg.c1, '=' + name + '(' + CS.rangeStr(rg) + ')');
            g.selectCell(target, rg.c1);
            return;
        }
        g.startEdit('=' + name + '(', 'enter');
    };

    U.undo = function () {
        if (!this.model.can.edit) return;
        this.grid.commitIfEditing();
        var tx = this.model.undo();
        if (tx) CS.toast('Undo: ' + tx.label, 'info');
        this.grid.relayout();
        this.grid.requestRender();
    };
    U.redo = function () {
        if (!this.model.can.edit) return;
        var tx = this.model.redo();
        if (tx) CS.toast('Redo: ' + tx.label, 'info');
        this.grid.relayout();
        this.grid.requestRender();
    };

    U.copyCmd = function (cut) {
        this.grid.focusEl.focus();
        var ok = false;
        try { ok = document.execCommand(cut ? 'cut' : 'copy'); } catch (e) { ok = false; }
        if (!ok) CS.toast('Use ' + (CS.isMac ? '⌘' : 'Ctrl') + '+' + (cut ? 'X' : 'C') + ' to ' + (cut ? 'cut' : 'copy') + '.', 'info');
    };
    U.pasteCmd = function (mode) {
        var self = this;
        if (!this.model.can.edit) { this.readOnly(); return; }
        if (navigator.clipboard && navigator.clipboard.readText) {
            navigator.clipboard.readText().then(function (text) {
                var g = self.grid;
                self.actions.paste(text, mode, g.clip && g.clip.text === text ? g.clip : null, CS.Grid.parseTsv);
            }).catch(function () { CS.toast('Use ' + (CS.isMac ? '⌘' : 'Ctrl') + '+V to paste (your browser blocked clipboard access).', 'info'); });
        } else {
            CS.toast('Use ' + (CS.isMac ? '⌘' : 'Ctrl') + '+V to paste.', 'info');
        }
    };

    // ── Keyboard shortcuts (grid focused, not editing) ──────────────────
    U.shortcut = function (e) {
        var mod = CS.mod(e), k = e.key.toLowerCase(), A = this.actions;
        if (!mod) return false;
        if (k === 'z' && !e.shiftKey) { this.undo(); return true; }
        if ((k === 'y') || (k === 'z' && e.shiftKey)) { this.redo(); return true; }
        if (k === 's') { this.model.save(); if (!this.model.hasPending()) CS.toast('All changes saved.', 'success'); return true; }
        if (k === 'f') { D.find(this, false); return true; }
        if (k === 'h') { D.find(this, true); return true; }
        if (k === 'p') { this.command('print'); return true; }
        if (k === 'b') { this.command('bold'); return true; }
        if (k === 'i') { this.command('italic'); return true; }
        if (k === 'u') { this.command('underline'); return true; }
        if (k === 'd') { A.fill('down'); return true; }
        if (k === 'r') { A.fill('right'); return true; }
        if (k === 'k') { this.command('link'); return true; }
        if (k === 'v' && e.shiftKey) { this.grid.pasteMode = 'values'; return false; } // let the paste event fire
        if (e.key === '\\') { A.clearFormatting(); return true; }
        return false;
    };

    // ── Menus ───────────────────────────────────────────────────────────
    U.menuItems = function (name) {
        var self = this, A = this.actions, m = this.model, g = this.grid, can = m.can;
        var mod = CS.isMac ? '⌘' : 'Ctrl+';
        var ro = !can.edit;
        var sheet = g.sheet;
        switch (name) {
            case 'file': return [
                { label: 'New spreadsheet', icon: 'fas fa-plus', action: function () { window.location.href = CS.base() + '/?new=1'; } },
                {
                    label: 'Make a copy', icon: 'fas fa-copy', action: function () {
                        CS.prompt('Make a copy', 'Name', 'Copy of ' + m.name, { ok: 'Make a copy' }).then(function (name2) {
                            if (!name2) return;
                            m.save();
                            CS.api('POST', '/spreadsheets/' + m.id + '/duplicate', { name: name2 }).then(function (res) {
                                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                                CS.toast('Copy created.', 'success');
                                window.open(CS.base() + '/' + res.data.id, '_blank');
                            });
                        });
                    },
                },
                { label: 'Import CSV/Excel as new sheets…', icon: 'fas fa-file-import', disabled: ro, action: function () { m.save(); D.importFile({ spreadsheetId: m.id, onDone: function () { m.reloadAll().then(function () { CS.toast('Imported.', 'success'); }); } }); } },
                { divider: true },
                {
                    label: 'Download', icon: 'fas fa-download', disabled: !can.export, submenu: [
                        { label: 'Microsoft Excel (.xlsx)', action: function () { self.downloadXlsx(); } },
                        { label: 'CSV - current sheet', action: function () { self.downloadCsv(); } },
                        { label: 'PDF - via Print (Save as PDF)', action: function () { D.print(self); } },
                    ],
                },
                { label: 'Print', icon: 'fas fa-print', hint: mod + 'P', disabled: !can.export, action: function () { D.print(self); } },
                { divider: true },
                { label: can.share ? 'Share…' : 'People with access…', icon: 'fas fa-user-plus', action: function () { D.share(self, null, { onChange: function () { self.refreshShareCount(); } }); } },
                { label: 'Details…', icon: 'fas fa-circle-info', action: function () { D.details(self); } },
                { label: 'Version history', icon: 'fas fa-clock-rotate-left', action: function () { D.history(self); } },
                { divider: true },
                { label: 'Delete spreadsheet', icon: 'fas fa-trash', disabled: !can.delete, action: function () { self.deleteBook(); } },
                { label: 'All spreadsheets', icon: 'fas fa-table-list', action: function () { window.location.href = CS.base() + '/'; } },
            ];
            case 'edit': return [
                { label: 'Undo', icon: 'fas fa-rotate-left', hint: mod + 'Z', disabled: ro || !m.canUndo(), action: function () { self.undo(); } },
                { label: 'Redo', icon: 'fas fa-rotate-right', hint: mod + 'Y', disabled: ro || !m.canRedo(), action: function () { self.redo(); } },
                { divider: true },
                { label: 'Cut', icon: 'fas fa-scissors', hint: mod + 'X', disabled: ro, action: function () { self.copyCmd(true); } },
                { label: 'Copy', icon: 'fas fa-copy', hint: mod + 'C', action: function () { self.copyCmd(false); } },
                { label: 'Paste', icon: 'fas fa-paste', hint: mod + 'V', disabled: ro, action: function () { self.pasteCmd('all'); } },
                {
                    label: 'Paste special', disabled: ro, submenu: [
                        { label: 'Values only', hint: mod + 'Shift+V', action: function () { self.pasteCmd('values'); } },
                        { label: 'Format only', action: function () { self.pasteCmd('format'); } },
                    ],
                },
                { divider: true },
                { label: 'Find and replace', icon: 'fas fa-magnifying-glass', hint: mod + 'H', action: function () { D.find(self, true); } },
                { label: 'Select all', hint: mod + 'A', action: function () { g.selectAll(); } },
                { label: 'Fill down', hint: mod + 'D', disabled: ro, action: function () { A.fill('down'); } },
                { label: 'Fill right', hint: mod + 'R', disabled: ro, action: function () { A.fill('right'); } },
                { divider: true },
                {
                    label: 'Delete', disabled: ro, submenu: [
                        { label: 'Values', action: function () { A.clearContents(); } },
                        { label: 'Values and formatting', action: function () { A.clearAll(); } },
                        { label: 'Selected rows', action: function () { A.deleteLines('row'); } },
                        { label: 'Selected columns', action: function () { A.deleteLines('col'); } },
                    ],
                },
            ];
            case 'view': return [
                {
                    label: 'Freeze', icon: 'fas fa-snowflake', disabled: ro, submenu: [
                        { label: 'No rows', checked: !sheet.frozenRows, action: function () { A.freeze(0, null); } },
                        { label: '1 row', checked: sheet.frozenRows === 1, action: function () { A.freeze(1, null); } },
                        { label: '2 rows', checked: sheet.frozenRows === 2, action: function () { A.freeze(2, null); } },
                        { label: 'Up to row ' + (g.sel.active.r + 1), action: function () { A.freeze(g.sel.active.r + 1, null); } },
                        { divider: true },
                        { label: 'No columns', checked: !sheet.frozenCols, action: function () { A.freeze(null, 0); } },
                        { label: '1 column', checked: sheet.frozenCols === 1, action: function () { A.freeze(null, 1); } },
                        { label: '2 columns', checked: sheet.frozenCols === 2, action: function () { A.freeze(null, 2); } },
                        { label: 'Up to column ' + CS.colName(g.sel.active.c), action: function () { A.freeze(null, g.sel.active.c + 1); } },
                    ],
                },
                { label: 'Gridlines', checked: !this.root.classList.contains('crm-sheet-nogrid'), action: function () { self.root.classList.toggle('crm-sheet-nogrid'); } },
                { label: 'Show formulas', checked: !!this.showFormulas, action: function () { self.toggleFormulas(); } },
                { divider: true },
                { label: 'Show hidden rows', disabled: ro || !(sheet.props.hr || []).length, action: function () { A.unhideLines('row'); } },
                { label: 'Show hidden columns', disabled: ro || !(sheet.props.hc || []).length, action: function () { A.unhideLines('col'); } },
                { divider: true },
                { label: document.fullscreenElement ? 'Exit full screen' : 'Full screen', icon: 'fas fa-expand', action: function () { self.toggleFullscreen(); } },
            ];
            case 'insert': return [
                { label: 'Row above', disabled: ro, action: function () { A.insertLines('row', 'before'); } },
                { label: 'Row below', disabled: ro, action: function () { A.insertLines('row', 'after'); } },
                { label: 'Column left', disabled: ro, action: function () { A.insertLines('col', 'before'); } },
                { label: 'Column right', disabled: ro, action: function () { A.insertLines('col', 'after'); } },
                { divider: true },
                { label: 'Sheet', icon: 'fas fa-plus', disabled: ro, action: function () { self.addSheet(); } },
                { label: 'Function…', icon: 'fas fa-square-root-variable', disabled: ro, action: function () { D.functions(self); } },
                { label: 'Link…', icon: 'fas fa-link', hint: mod + 'K', disabled: ro, action: function () { D.link(self); } },
                { label: '1000 rows at the bottom', disabled: ro, action: function () { A.addRows(1000); } },
                { label: '10 columns at the end', disabled: ro || sheet.cols >= 260, action: function () { A.addCols(10); } },
            ];
            case 'format': return [
                {
                    label: 'Number', icon: 'fas fa-hashtag', disabled: ro, submenu: FM.NUMBER_FORMATS.map(function (n) {
                        return { html: esc(n.label) + ' <span class="crm-sheet-menu-hint">' + esc(n.sample) + '</span>', action: function () { A.setNumberFormat(n); } };
                    }).concat([{ divider: true }, { label: 'Custom currency…', action: function () { D.currency(self); } }]),
                },
                {
                    label: 'Text', icon: 'fas fa-bold', disabled: ro, submenu: [
                        { label: 'Bold', hint: mod + 'B', action: function () { A.toggleStyle('b'); } },
                        { label: 'Italic', hint: mod + 'I', action: function () { A.toggleStyle('i'); } },
                        { label: 'Underline', hint: mod + 'U', action: function () { A.toggleStyle('u'); } },
                        { label: 'Strikethrough', action: function () { A.toggleStyle('s'); } },
                    ],
                },
                {
                    label: 'Alignment', icon: 'fas fa-align-left', disabled: ro, submenu: [
                        { label: 'Left', action: function () { A.setStyle('ha', 'left', 'Align'); } },
                        { label: 'Center', action: function () { A.setStyle('ha', 'center', 'Align'); } },
                        { label: 'Right', action: function () { A.setStyle('ha', 'right', 'Align'); } },
                        { divider: true },
                        { label: 'Top', action: function () { A.setStyle('va', 'top', 'Vertical align'); } },
                        { label: 'Middle', action: function () { A.setStyle('va', 'middle', 'Vertical align'); } },
                        { label: 'Bottom', action: function () { A.setStyle('va', null, 'Vertical align'); } },
                    ],
                },
                {
                    label: 'Wrapping', icon: 'fas fa-paragraph', disabled: ro, submenu: [
                        { label: 'Overflow', action: function () { A.setStyle('wrap', null, 'Text wrapping'); } },
                        { label: 'Wrap', action: function () { A.setStyle('wrap', 'wrap', 'Text wrapping'); } },
                        { label: 'Clip', action: function () { A.setStyle('wrap', 'clip', 'Text wrapping'); } },
                    ],
                },
                {
                    label: 'Merge cells', icon: 'fas fa-object-group', disabled: ro, submenu: [
                        { label: 'Merge all', action: function () { A.merge('all'); } },
                        { label: 'Merge horizontally', action: function () { A.merge('horizontal'); } },
                        { label: 'Merge vertically', action: function () { A.merge('vertical'); } },
                        { label: 'Unmerge', action: function () { A.merge('unmerge'); } },
                    ],
                },
                { divider: true },
                { label: 'Conditional formatting…', icon: 'fas fa-palette', disabled: ro, action: function () { D.conditional(self); } },
                { label: 'Clear formatting', icon: 'fas fa-text-slash', hint: mod + '\\', disabled: ro, action: function () { A.clearFormatting(); } },
            ];
            case 'data': return [
                { label: 'Sort range by column ' + CS.colName(g.sel.active.c) + ' (A → Z)', icon: 'fas fa-arrow-down-a-z', disabled: ro, action: function () { A.quickSort(true); } },
                { label: 'Sort range by column ' + CS.colName(g.sel.active.c) + ' (Z → A)', icon: 'fas fa-arrow-down-z-a', disabled: ro, action: function () { A.quickSort(false); } },
                { label: 'Advanced sort…', icon: 'fas fa-sort', disabled: ro, action: function () { D.sortRange(self); } },
                { divider: true },
                { label: sheet.props.filter ? 'Remove filter' : 'Create a filter', icon: 'fas fa-filter', disabled: ro, action: function () { A.toggleFilter(); } },
                { label: 'Data validation…', icon: 'fas fa-list-check', disabled: ro, action: function () { D.validation(self); } },
            ];
            case 'tools': return [
                { label: 'Spreadsheet details…', icon: 'fas fa-circle-info', action: function () { D.details(self); } },
                { label: 'Version history', icon: 'fas fa-clock-rotate-left', action: function () { D.history(self); } },
                { label: can.share ? 'Share…' : 'People with access…', icon: 'fas fa-users', action: function () { D.share(self, null, { onChange: function () { self.refreshShareCount(); } }); } },
                { label: 'Save now', icon: 'fas fa-floppy-disk', hint: mod + 'S', disabled: ro, action: function () { m.save(); } },
            ];
            case 'help': return [
                { label: 'Keyboard shortcuts', icon: 'fas fa-keyboard', action: function () { D.shortcuts(); } },
                { label: 'Function list', icon: 'fas fa-square-root-variable', action: function () { D.functions(self); } },
            ];
        }
        return [];
    };

    U.toggleFormulas = function () {
        this.showFormulas = !this.showFormulas;
        var m = this.model;
        if (this.showFormulas) {
            m._display = m.display;
            m.display = function (sheet, r, c) {
                var cell = this.raw(sheet, r, c);
                return cell && typeof cell.v === 'string' && cell.v.charAt(0) === '=' ? cell.v : this._display(sheet, r, c);
            };
            var origValue = m.value;
            m._value = origValue;
            m.value = function (sheet, r, c) {
                var cell = this.raw(sheet, r, c);
                if (cell && typeof cell.v === 'string' && cell.v.charAt(0) === '=') return { t: 's', v: cell.v };
                return this._value(sheet, r, c);
            };
        } else {
            m.display = m._display;
            m.value = m._value;
        }
        m.invalidate();
        this.grid.requestRender();
    };
    U.toggleFullscreen = function () {
        if (document.fullscreenElement) document.exitFullscreen();
        else if (this.root.requestFullscreen) this.root.requestFullscreen();
    };

    U.downloadXlsx = function () {
        var self = this;
        var go = function () { window.location.href = CS.base() + '/api/spreadsheets/' + self.model.id + '/export.xlsx'; };
        if (this.model.hasPending()) this.model.save().then(go); else go();
    };
    U.downloadCsv = function () {
        var m = this.model, s = this.grid.sheet, used = m.used(s), lines = [];
        for (var r = 0; r < used.rows; r++) {
            var row = [];
            for (var c = 0; c < used.cols; c++) {
                var t = m.display(s, r, c);
                row.push(/[",\n\r]/.test(t) || /^[=+\-@]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t);
            }
            lines.push(row.join(','));
        }
        var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = (m.name + ' - ' + s.name).replace(/[\\/:*?"<>|]+/g, '_') + '.csv';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    };
    U.deleteBook = function () {
        var m = this.model;
        CS.confirm('Delete "' + m.name + '"? People it is shared with will lose access. An administrator can restore it.', { ok: 'Delete', danger: true, title: 'Delete spreadsheet' }).then(function (ok) {
            if (!ok) return;
            CS.api('DELETE', '/spreadsheets/' + m.id).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                m.destroy();
                window.location.href = CS.base() + '/';
            });
        });
    };

    // ── Context menus ───────────────────────────────────────────────────
    U.contextMenu = function (hit, x, y) {
        var self = this, A = this.actions, g = this.grid, ro = !this.model.can.edit;
        var mod = CS.isMac ? '⌘' : 'Ctrl+';
        var rows = A.lineSpan('row'), cols = A.lineSpan('col');
        var rowsLabel = rows.count > 1 ? rows.count + ' rows' : 'row';
        var colsLabel = cols.count > 1 ? cols.count + ' columns' : 'column';
        var clip = [
            { label: 'Cut', icon: 'fas fa-scissors', hint: mod + 'X', disabled: ro, action: function () { self.copyCmd(true); } },
            { label: 'Copy', icon: 'fas fa-copy', hint: mod + 'C', action: function () { self.copyCmd(false); } },
            { label: 'Paste', icon: 'fas fa-paste', hint: mod + 'V', disabled: ro, action: function () { self.pasteCmd('all'); } },
            { label: 'Paste values only', hint: mod + 'Shift+V', disabled: ro, action: function () { self.pasteCmd('values'); } },
        ];
        var items;
        if (hit.area === 'colhead') {
            items = clip.concat([{ divider: true },
                { label: 'Insert ' + colsLabel + ' left', disabled: ro, action: function () { A.insertLines('col', 'before'); } },
                { label: 'Insert ' + colsLabel + ' right', disabled: ro, action: function () { A.insertLines('col', 'after'); } },
                { label: 'Delete ' + colsLabel, disabled: ro, action: function () { A.deleteLines('col'); } },
                { label: 'Clear ' + colsLabel, disabled: ro, action: function () { A.clearAll(); } },
                { label: 'Hide ' + colsLabel, disabled: ro, action: function () { A.hideLines('col'); } },
                (g.sheet.props.hc || []).length ? { label: 'Show hidden columns', disabled: ro, action: function () { A.unhideLines('col'); } } : null,
                { label: 'Resize ' + colsLabel + '…', disabled: ro, action: function () { D.resize(self, 'col', Array.from(g.fullCols())); } },
                { label: 'Fit to data', disabled: ro, action: function () { g.autofitCols(Array.from(g.fullCols())); } },
                { divider: true },
                { label: 'Sort sheet A → Z', disabled: ro, action: function () { self.sortSheetBy(hit.c, true); } },
                { label: 'Sort sheet Z → A', disabled: ro, action: function () { self.sortSheetBy(hit.c, false); } },
                { label: 'Freeze up to column ' + CS.colName(cols.at + cols.count - 1), disabled: ro, action: function () { A.freeze(null, cols.at + cols.count); } },
            ]);
        } else if (hit.area === 'rowhead') {
            items = clip.concat([{ divider: true },
                { label: 'Insert ' + rowsLabel + ' above', disabled: ro, action: function () { A.insertLines('row', 'before'); } },
                { label: 'Insert ' + rowsLabel + ' below', disabled: ro, action: function () { A.insertLines('row', 'after'); } },
                { label: 'Delete ' + rowsLabel, disabled: ro, action: function () { A.deleteLines('row'); } },
                { label: 'Clear ' + rowsLabel, disabled: ro, action: function () { A.clearAll(); } },
                { label: 'Hide ' + rowsLabel, disabled: ro, action: function () { A.hideLines('row'); } },
                (g.sheet.props.hr || []).length ? { label: 'Show hidden rows', disabled: ro, action: function () { A.unhideLines('row'); } } : null,
                { label: 'Resize ' + rowsLabel + '…', disabled: ro, action: function () { D.resize(self, 'row', Array.from(g.fullRows())); } },
                { label: 'Fit to data', disabled: ro, action: function () { g.autofitRows(Array.from(g.fullRows())); } },
                { divider: true },
                { label: 'Freeze up to row ' + (rows.at + rows.count), disabled: ro, action: function () { A.freeze(rows.at + rows.count, null); } },
            ]);
        } else if (hit.area === 'cell') {
            items = clip.concat([{ divider: true },
                { label: 'Insert ' + rowsLabel + ' above', disabled: ro, action: function () { A.insertLines('row', 'before'); } },
                { label: 'Insert ' + rowsLabel + ' below', disabled: ro, action: function () { A.insertLines('row', 'after'); } },
                { label: 'Insert ' + colsLabel + ' left', disabled: ro, action: function () { A.insertLines('col', 'before'); } },
                { label: 'Insert ' + colsLabel + ' right', disabled: ro, action: function () { A.insertLines('col', 'after'); } },
                { label: 'Delete ' + rowsLabel, disabled: ro, action: function () { A.deleteLines('row'); } },
                { label: 'Delete ' + colsLabel, disabled: ro, action: function () { A.deleteLines('col'); } },
                { divider: true },
                { label: 'Insert link', icon: 'fas fa-link', disabled: ro, action: function () { D.link(self); } },
                { label: 'Data validation…', icon: 'fas fa-list-check', disabled: ro, action: function () { D.validation(self); } },
                { label: 'Conditional formatting…', icon: 'fas fa-palette', disabled: ro, action: function () { D.conditional(self); } },
                { divider: true },
                { label: 'Sort range A → Z', disabled: ro, action: function () { A.quickSort(true); } },
                { label: 'Sort range Z → A', disabled: ro, action: function () { A.quickSort(false); } },
                { divider: true },
                { label: 'Clear contents', icon: 'fas fa-eraser', hint: 'Delete', disabled: ro, action: function () { A.clearContents(); } },
                { label: 'Clear formatting', icon: 'fas fa-text-slash', disabled: ro, action: function () { A.clearFormatting(); } },
            ]);
        } else {
            return;
        }
        CS.menu(items.filter(Boolean), x, y);
    };
    U.sortSheetBy = function (col, asc) {
        var g = this.grid, used = this.model.used(g.sheet);
        var fr = g.sheet.frozenRows || 0;
        this.actions.sortRange({ r1: fr, c1: 0, r2: Math.max(fr, used.rows - 1), c2: Math.max(0, used.cols - 1) }, [{ c: col, asc: asc }], false);
    };

    // ── Sheet tabs ──────────────────────────────────────────────────────
    U.bindTabs = function () {
        var self = this;
        this.el('.crm-sheet-addtab').addEventListener('click', function () { self.addSheet(); });
        this.el('.crm-sheet-alltabs').addEventListener('click', function (e) {
            var items = self.model.sheets.map(function (s) {
                return {
                    html: (s.color ? '<span class="crm-sheet-tabdot" style="background:' + esc(s.color) + '"></span>' : '') + esc(s.name) + (s.hidden ? ' <span class="crm-sheet-menu-hint">hidden</span>' : ''),
                    checked: s === self.activeSheet,
                    action: function () {
                        if (s.hidden) {
                            if (!self.model.can.edit) { CS.toast('This sheet is hidden.', 'info'); return; }
                            self.model.setSheetMeta(s, 'hidden', false, 'Unhide sheet');
                        }
                        self.showSheet(s);
                    },
                };
            });
            CS.menu(items, 0, 0, e.currentTarget);
        });
        var tabs = this.el('.crm-sheet-tablist');
        tabs.addEventListener('click', function (e) {
            var t = e.target.closest('[data-sheet-id]');
            if (t) self.showSheet(self.model.sheetById(t.dataset.sheetId));
        });
        tabs.addEventListener('dblclick', function (e) {
            var t = e.target.closest('[data-sheet-id]');
            if (t && self.model.can.edit) self.renameSheetPrompt(self.model.sheetById(t.dataset.sheetId));
        });
        tabs.addEventListener('contextmenu', function (e) {
            var t = e.target.closest('[data-sheet-id]');
            if (!t) return;
            e.preventDefault();
            var s = self.model.sheetById(t.dataset.sheetId);
            self.showSheet(s);
            self.tabMenu(s, e.clientX, e.clientY);
        });
        tabs.addEventListener('keydown', function (e) {
            var t = e.target.closest('[data-sheet-id]');
            if (!t) return;
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                var list = self.model.visibleSheets(), i = list.indexOf(self.model.sheetById(t.dataset.sheetId));
                var n = list[(i + (e.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length];
                self.showSheet(n);
                var el = tabs.querySelector('[data-sheet-id="' + n.id + '"]');
                if (el) el.focus();
                e.preventDefault();
            } else if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) {
                var r = t.getBoundingClientRect();
                self.tabMenu(self.model.sheetById(t.dataset.sheetId), r.left, r.top - 4);
                e.preventDefault();
            }
        });
        // Drag a tab to reorder.
        var dragId = null;
        tabs.addEventListener('dragstart', function (e) {
            var t = e.target.closest('[data-sheet-id]');
            if (!t || !self.model.can.edit) { e.preventDefault(); return; }
            dragId = t.dataset.sheetId;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', dragId);
        });
        tabs.addEventListener('dragover', function (e) { if (dragId) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } });
        tabs.addEventListener('drop', function (e) {
            e.preventDefault();
            var t = e.target.closest('[data-sheet-id]');
            if (!dragId || !t || t.dataset.sheetId === dragId) { dragId = null; return; }
            var s = self.model.sheetById(dragId), target = self.model.sheetById(t.dataset.sheetId);
            self.model.moveSheet(s, self.model.sheets.indexOf(target));
            dragId = null;
        });
    };
    U.renderTabs = function () {
        var self = this, list = this.el('.crm-sheet-tablist');
        list.innerHTML = this.model.sheets.filter(function (s) { return !s.hidden; }).map(function (s) {
            var active = s === self.activeSheet;
            return '<button type="button" role="tab" class="crm-sheet-tab' + (active ? ' crm-sheet-tab-active' : '') + '" data-sheet-id="' + esc(s.id) + '" draggable="true" aria-selected="' + active + '" tabindex="' + (active ? 0 : -1) + '"' +
                (s.color ? ' style="--crm-sheet-tabcolor:' + esc(s.color) + '"' : '') + '>' + esc(s.name) + '<span class="crm-sheet-tabcaret" aria-hidden="true"><i class="fas fa-caret-down"></i></span></button>';
        }).join('');
        list.querySelectorAll('.crm-sheet-tabcaret').forEach(function (c) {
            c.addEventListener('click', function (e) {
                e.stopPropagation();
                var s = self.model.sheetById(c.parentNode.dataset.sheetId);
                self.showSheet(s);
                var r = c.getBoundingClientRect();
                self.tabMenu(s, r.left, r.top - 4);
            });
        });
        var act = list.querySelector('.crm-sheet-tab-active');
        if (act && act.scrollIntoView) act.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    };
    U.tabMenu = function (s, x, y) {
        var self = this, m = this.model, ro = !m.can.edit;
        var idx = m.sheets.indexOf(s);
        var items = [
            { label: 'Rename…', disabled: ro, action: function () { self.renameSheetPrompt(s); } },
            { label: 'Duplicate', disabled: ro, action: function () { m.duplicateSheet(s).then(function (copy) { self.showSheet(copy); }); } },
            {
                label: 'Change colour', disabled: ro, submenu: TAB_COLORS.map(function (c) {
                    return { html: '<span class="crm-sheet-tabdot" style="background:' + c + '"></span>' + c, checked: s.color === c, action: function () { m.setSheetMeta(s, 'color', c, 'Sheet colour'); } };
                }).concat([{ label: 'Reset', action: function () { m.setSheetMeta(s, 'color', null, 'Sheet colour'); } }]),
            },
            { label: 'Hide sheet', disabled: ro || m.visibleSheets().length <= 1, action: function () { m.setSheetMeta(s, 'hidden', true, 'Hide sheet'); } },
            { divider: true },
            { label: 'Move left', disabled: ro || idx <= 0, action: function () { m.moveSheet(s, idx - 1); } },
            { label: 'Move right', disabled: ro || idx >= m.sheets.length - 1, action: function () { m.moveSheet(s, idx + 1); } },
            { divider: true },
            { label: 'Delete', icon: 'fas fa-trash', disabled: ro || m.sheets.length <= 1, action: function () { self.deleteSheet(s); } },
        ];
        CS.menu(items, x, y);
        var menu = document.querySelector('.crm-sheet-menu-root');
        if (menu) { menu.style.top = Math.max(4, y - menu.offsetHeight) + 'px'; }
    };
    U.addSheet = function () {
        if (!this.model.can.edit) { this.readOnly(); return; }
        var s = this.model.addSheet(null, this.activeSheet);
        this.showSheet(s);
    };
    U.renameSheetPrompt = function (s) {
        var self = this;
        CS.prompt('Rename sheet', 'Sheet name', s.name, { ok: 'Rename', maxlength: 100 }).then(function (name) {
            if (!name || name === s.name) return;
            self.model.renameSheet(s, name).then(function () { self.renderTabs(); }).catch(function (e) { CS.toast(e.message, 'error'); });
        });
    };
    U.deleteSheet = function (s) {
        var self = this;
        CS.confirm('Delete sheet "' + s.name + '"? This cannot be undone.', { ok: 'Delete', danger: true, title: 'Delete sheet' }).then(function (ok) {
            if (ok && self.model.deleteSheet(s)) CS.toast('Sheet deleted.', 'success');
        });
    };

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('.crm-sheet-app[data-book-id]');
        if (root) window.CrmSheetApp = new App(root);
    });
})();
