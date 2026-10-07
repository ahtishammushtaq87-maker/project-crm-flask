/* Spreadsheet module - workbook state, calculation, undo/redo and saving.
 *
 * Saving: every change is turned into an operation and queued. The queue is
 * sent as ONE batch after a short pause (or at once on Ctrl+S); while a
 * batch is in flight new changes keep queueing. Each batch carries the
 * version the client last saw so the server can detect conflicting edits.
 * Nothing is dropped on a failed save - the batch goes back to the front of
 * the queue and is retried.
 */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var X = CS.Formula, FM = CS.Format;

    var SAVE_DELAY = 900;
    var SAVE_MAX_WAIT = 4000;
    var POLL_MS = 12000;

    function clone(o) { return o === undefined ? undefined : JSON.parse(JSON.stringify(o)); }
    function sameFmt(a, b) { return JSON.stringify(a || null) === JSON.stringify(b || null); }
    function emptyProps() { return { cw: {}, rh: {}, hr: [], hc: [], merges: [], filter: null, cf: [], dv: [] }; }
    var tmpCounter = 0;

    function Workbook(book) {
        this.id = book.id;
        this.listeners = {};
        this.queue = [];
        this.inflight = null;
        this.undoStack = [];
        this.redoStack = [];
        this.tx = null;
        this.status = 'saved';
        this.lastSaved = new Date();
        this.retryDelay = 0;
        this.cache = new Map();
        this.evaluating = new Set();
        this.applyBook(book);
        var self = this;
        this.saveSoon = CS.debounce(function () { self.save(); }, SAVE_DELAY);
        this.pollTimer = setInterval(function () { self.poll(); }, POLL_MS);
        document.addEventListener('visibilitychange', function () { if (!document.hidden) self.poll(); });
    }
    CS.Workbook = Workbook;
    var P = Workbook.prototype;

    // ── Events ──────────────────────────────────────────────────────────
    P.on = function (name, fn) { (this.listeners[name] = this.listeners[name] || []).push(fn); };
    P.emit = function (name, detail) { (this.listeners[name] || []).forEach(function (fn) { fn(detail || {}); }); };

    // ── Loading ─────────────────────────────────────────────────────────
    P.applyBook = function (book) {
        this.name = book.name;
        this.description = book.description;
        this.owner = book.owner;
        this.version = book.version;
        this.can = book.can;
        this.role = book.role;
        this.updatedBy = book.updated_by;
        this.updatedAt = book.updated_at;
        this.favorite = book.favorite;
        this.viewersCanExport = book.viewers_can_export;
        this.sharedCount = book.shared_count;
        var old = {};
        (this.sheets || []).forEach(function (s) { old[s.id] = s; });
        this.sheets = book.sheets.map(function (m) {
            var s = old[m.id] || { id: m.id, cells: new Map(), loaded: false, props: emptyProps() };
            applyMeta(s, m);
            return s;
        });
        this.sortSheets();
    };
    function applyMeta(s, m) {
        s.name = m.name; s.position = m.position; s.color = m.color; s.hidden = !!m.hidden;
        s.rows = m.rows; s.cols = m.cols; s.frozenRows = m.frozen_rows || 0; s.frozenCols = m.frozen_cols || 0;
        s.propsVersion = m.props_version;
    }
    P.sortSheets = function () { this.sheets.sort(function (a, b) { return a.position - b.position; }); };
    P.sheetById = function (id) {
        for (var i = 0; i < this.sheets.length; i++) if (String(this.sheets[i].id) === String(id)) return this.sheets[i];
        return null;
    };
    P.sheetByName = function (name) {
        var n = String(name).toLowerCase();
        for (var i = 0; i < this.sheets.length; i++) if (this.sheets[i].name.toLowerCase() === n) return this.sheets[i];
        return null;
    };
    P.visibleSheets = function () { return this.sheets.filter(function (s) { return !s.hidden; }); };

    P.loadSheet = function (sheet) {
        var self = this;
        if (sheet.loaded || typeof sheet.id !== 'number') { sheet.loaded = true; return Promise.resolve(sheet); }
        if (sheet.loading) return sheet.loading;
        sheet.loading = CS.api('GET', '/spreadsheets/' + this.id + '/sheets/' + sheet.id).then(function (res) {
            sheet.loading = null;
            if (!res.ok) throw new Error(CS.errorText(res, 'Could not load this sheet.'));
            self.fillSheet(sheet, res.data.sheet);
            self.emit('loaded', { sheet: sheet });
            return sheet;
        });
        return sheet.loading;
    };
    P.fillSheet = function (sheet, data) {
        applyMeta(sheet, data);
        sheet.props = Object.assign(emptyProps(), data.props || {});
        sheet.cells = new Map();
        // Changes still waiting to be saved win over what the server sent.
        var pending = this.pendingCells(sheet);
        data.cells.forEach(function (c) {
            if (c.v !== null || c.f) sheet.cells.set(CS.key(c.r, c.c), { v: c.v, f: c.f || null });
        });
        pending.forEach(function (cell, key) {
            if (cell.v === null && !cell.f) sheet.cells.delete(key); else sheet.cells.set(key, { v: cell.v, f: cell.f || null });
        });
        sheet.loaded = true;
        sheet.usedDirty = true;
        this.invalidate();
    };
    P.loadAll = function () {
        var self = this;
        return Promise.all(this.sheets.map(function (s) { return self.loadSheet(s); }));
    };
    /** Reload everything from the server (after a conflict or another
     *  user's structural change). Pending changes must be empty. */
    P.reloadAll = function () {
        var self = this;
        return CS.api('GET', '/spreadsheets/' + this.id).then(function (res) {
            if (!res.ok) throw new Error(CS.errorText(res, 'Could not reload the spreadsheet.'));
            var wasLoaded = {};
            self.sheets.forEach(function (s) { if (s.loaded) wasLoaded[s.id] = true; });
            self.sheets = [];
            self.applyBook(res.data.book);
            self.invalidate();
            return Promise.all(self.sheets.filter(function (s) { return wasLoaded[s.id]; }).map(function (s) { return self.loadSheet(s); }));
        }).then(function () { self.emit('reloaded'); });
    };

    // ── Reading values ──────────────────────────────────────────────────
    P.raw = function (sheet, r, c) { return sheet.cells.get(CS.key(r, c)) || null; };
    P.invalidate = function () { this.cache.clear(); this.filterCache = null; };

    P.used = function (sheet) {
        if (sheet.usedDirty || !sheet.usedSize) {
            var mr = 0, mc = 0;
            sheet.cells.forEach(function (cell, key) {
                if (cell.v === null || cell.v === undefined || cell.v === '') return;
                var i = key.indexOf(','), r = +key.slice(0, i), c = +key.slice(i + 1);
                if (r + 1 > mr) mr = r + 1;
                if (c + 1 > mc) mc = c + 1;
            });
            sheet.usedSize = { rows: mr, cols: mc };
            sheet.usedDirty = false;
        }
        return sheet.usedSize;
    };

    /** Computed value of a cell (formulas evaluated, cached until the next change). */
    P.value = function (sheet, r, c) {
        var cacheKey = sheet.id + '!' + r + ',' + c;
        var hit = this.cache.get(cacheKey);
        if (hit) return hit;
        var cell = this.raw(sheet, r, c);
        var v;
        if (!cell || cell.v === null || cell.v === undefined || cell.v === '') {
            v = { t: 'empty' };
        } else if (typeof cell.v === 'string' && cell.v.charAt(0) === '=' && cell.v.length > 1) {
            if (this.evaluating.has(cacheKey)) return X.E(X.ERR.cycle, 'Circular reference');
            this.evaluating.add(cacheKey);
            try { v = X.evaluate(cell.v.slice(1), this.ctxFor(sheet)); } finally { this.evaluating.delete(cacheKey); }
        } else {
            v = FM.parse(cell.v);
            if (v.t === 'n' && cell.f && cell.f.nf && cell.f.nf.t === 'text') v = { t: 's', v: String(cell.v) };
        }
        this.cache.set(cacheKey, v);
        return v;
    };
    P.ctxFor = function (sheet) {
        var self = this;
        if (!sheet.ctx) {
            sheet.ctx = {
                cell: function (name, r, c) {
                    var s = name === null || name === undefined ? sheet : self.sheetByName(name);
                    if (!s) return X.E(X.ERR.ref, 'Unknown sheet ' + name);
                    if (!s.loaded) {
                        self.loadSheet(s).then(function () { self.invalidate(); self.emit('cells', { sheet: s, remote: true }); });
                        return X.E(X.ERR.loading, 'Loading…');
                    }
                    if (r < 0 || c < 0) return X.E(X.ERR.ref);
                    return self.value(s, r, c);
                },
                size: function (name) {
                    var s = name === null || name === undefined ? sheet : self.sheetByName(name);
                    if (!s) return null;
                    var u = self.used(s);
                    return { rows: s.rows, cols: s.cols, usedRows: u.rows, usedCols: u.cols };
                },
            };
        }
        return sheet.ctx;
    };
    /** Text shown in the cell. */
    P.display = function (sheet, r, c) {
        var cell = this.raw(sheet, r, c);
        var v = this.value(sheet, r, c);
        return FM.display(v, cell && cell.f ? cell.f.nf : null);
    };

    // ── Filtering ───────────────────────────────────────────────────────
    function filterMatch(v, display, crit) {
        if (crit.values) {
            if (crit.values.indexOf(display) < 0) return false;
        }
        if (crit.op) {
            var s = display.toLowerCase(), v1 = String(crit.v1 || ''), v2 = String(crit.v2 || '');
            var n = v.t === 'n' ? v.v : null, a = FM.parse(v1), b = FM.parse(v2);
            switch (crit.op) {
                case 'contains': return s.indexOf(v1.toLowerCase()) >= 0;
                case 'not_contains': return s.indexOf(v1.toLowerCase()) < 0;
                case 'eq': return a.t === 'n' && n !== null ? n === a.v : s === v1.toLowerCase();
                case 'neq': return a.t === 'n' && n !== null ? n !== a.v : s !== v1.toLowerCase();
                case 'gt': case 'date_after': return n !== null && a.t === 'n' && n > a.v;
                case 'gte': return n !== null && a.t === 'n' && n >= a.v;
                case 'lt': case 'date_before': return n !== null && a.t === 'n' && n < a.v;
                case 'lte': return n !== null && a.t === 'n' && n <= a.v;
                case 'date_eq': return n !== null && a.t === 'n' && Math.floor(n) === Math.floor(a.v);
                case 'between': return n !== null && a.t === 'n' && b.t === 'n' && n >= Math.min(a.v, b.v) && n <= Math.max(a.v, b.v);
                case 'empty': return v.t === 'empty' || display === '';
                case 'not_empty': return !(v.t === 'empty' || display === '');
            }
        }
        return true;
    }
    /** Set of row indexes hidden by the sheet's filter. */
    P.filterHidden = function (sheet) {
        var f = sheet.props.filter;
        if (!f || !f.crit || !Object.keys(f.crit).length) return null;
        if (this.filterCache && this.filterCache.sheet === sheet) return this.filterCache.rows;
        var hidden = new Set();
        var last = Math.min(f.r2, Math.max(f.r1, this.used(sheet).rows - 1));
        for (var r = f.r1 + 1; r <= last; r++) {
            for (var col in f.crit) {
                var c = +col;
                if (!filterMatch(this.value(sheet, r, c), this.display(sheet, r, c), f.crit[col])) { hidden.add(r); break; }
            }
        }
        this.filterCache = { sheet: sheet, rows: hidden };
        return hidden;
    };
    P.filterMatch = filterMatch;

    // ── Change tracking / undo ──────────────────────────────────────────
    /** Group several changes into one undo step. */
    P.begin = function (label) {
        if (this.tx) { this.tx.depth++; return; }
        this.tx = { label: label || 'Edit', steps: [], depth: 1 };
    };
    P.commit = function () {
        if (!this.tx) return;
        if (--this.tx.depth > 0) return;
        var tx = this.tx;
        this.tx = null;
        if (tx.steps.length) {
            this.undoStack.push(tx);
            if (this.undoStack.length > 200) this.undoStack.shift();
            this.redoStack = [];
        }
        this.emit('history');
    };
    P.record = function (step) {
        if (this.tx) { this.tx.steps.push(step); return; }
        this.undoStack.push({ label: step.label || 'Edit', steps: [step] });
        if (this.undoStack.length > 200) this.undoStack.shift();
        this.redoStack = [];
        this.emit('history');
    };
    P.canUndo = function () { return this.undoStack.length > 0; };
    P.canRedo = function () { return this.redoStack.length > 0; };
    P.undo = function () {
        var tx = this.undoStack.pop();
        if (!tx) return null;
        for (var i = tx.steps.length - 1; i >= 0; i--) this.replay(tx.steps[i], 'before');
        this.redoStack.push(tx);
        this.emit('history');
        return tx;
    };
    P.redo = function () {
        var tx = this.redoStack.pop();
        if (!tx) return null;
        for (var i = 0; i < tx.steps.length; i++) this.replay(tx.steps[i], 'after');
        this.undoStack.push(tx);
        this.emit('history');
        return tx;
    };
    P.replay = function (step, which) {
        var data = step[which];
        switch (step.type) {
            case 'cells': this.applyStates(step.sheet, data); break;
            case 'props': this.applyLayout(step.sheet, data); break;
            case 'snapshot': this.restoreSnapshot(step.sheet, data, step.label); break;
            case 'custom': data(); break;
        }
    };

    // ── Cell edits ──────────────────────────────────────────────────────
    function cellState(cell, r, c) { return { r: r, c: c, v: cell ? cell.v : null, f: cell && cell.f ? cell.f : null }; }

    /** Low-level: write cell states, queue the save, notify. */
    P.applyStates = function (sheet, states) {
        if (!states.length) return;
        var self = this;
        states.forEach(function (s) {
            var key = CS.key(s.r, s.c);
            var v = s.v === '' || s.v === undefined ? null : s.v;
            var f = s.f && Object.keys(s.f).length ? s.f : null;
            if (v === null && !f) sheet.cells.delete(key); else sheet.cells.set(key, { v: v, f: f });
            if (s.r + 1 > sheet.rows) sheet.rows = s.r + 1;
            if (s.c + 1 > sheet.cols) sheet.cols = s.c + 1;
        });
        sheet.usedDirty = true;
        this.invalidate();
        this.enqueue({ op: 'set_cells', sheet: sheet, cells: states.map(function (s) { return { r: s.r, c: s.c, v: s.v === '' ? null : s.v, f: s.f || null }; }) });
        this.emit('cells', { sheet: sheet });
        void self;
    };

    /**
     * Set cells. changes: [{r, c, v?, f?}] - a missing v/f keeps the current
     * one. Returns false when nothing changed.
     */
    P.setCells = function (sheet, changes, label) {
        if (!this.can.edit) return false;
        var before = [], after = [], seen = {};
        for (var i = 0; i < changes.length; i++) {
            var ch = changes[i], key = CS.key(ch.r, ch.c);
            if (seen[key] !== undefined) { after[seen[key]] = mergeChange(after[seen[key]], ch); continue; }
            var cur = this.raw(sheet, ch.r, ch.c);
            var b = cellState(cur, ch.r, ch.c);
            var a = mergeChange(b, ch);
            seen[key] = after.length;
            before.push(b);
            after.push(a);
        }
        var bi = [], ai = [];
        for (var j = 0; j < after.length; j++) {
            if (before[j].v === after[j].v && sameFmt(before[j].f, after[j].f)) continue;
            bi.push(before[j]); ai.push(after[j]);
        }
        if (!ai.length) return false;
        this.applyStates(sheet, ai);
        this.record({ type: 'cells', sheet: sheet, before: bi, after: ai, label: label });
        return true;
    };
    function mergeChange(base, ch) {
        return {
            r: base.r, c: base.c,
            v: ch.v !== undefined ? (ch.v === '' ? null : ch.v) : base.v,
            f: ch.f !== undefined ? (ch.f && Object.keys(ch.f).length ? ch.f : null) : base.f,
        };
    }

    // ── Layout (props, frozen, size) ────────────────────────────────────
    function layoutOf(sheet) {
        return { props: clone(sheet.props), rows: sheet.rows, cols: sheet.cols, frozenRows: sheet.frozenRows, frozenCols: sheet.frozenCols };
    }
    P.applyLayout = function (sheet, layout) {
        sheet.props = clone(layout.props);
        sheet.rows = layout.rows; sheet.cols = layout.cols;
        sheet.frozenRows = layout.frozenRows; sheet.frozenCols = layout.frozenCols;
        this.invalidate();
        this.enqueue({ op: 'sheet_props', sheet: sheet });
        this.emit('layout', { sheet: sheet });
    };
    /** Change layout through mutate(sheet); recorded for undo. */
    P.updateLayout = function (sheet, label, mutate) {
        if (!this.can.edit) return false;
        var before = layoutOf(sheet);
        mutate(sheet);
        var after = layoutOf(sheet);
        if (JSON.stringify(before) === JSON.stringify(after)) return false;
        this.applyLayout(sheet, after);
        this.record({ type: 'props', sheet: sheet, before: before, after: after, label: label });
        return true;
    };

    // ── Structural changes (rows/columns) ───────────────────────────────
    function snapshot(sheet) {
        return { cells: new Map(sheet.cells), layout: layoutOf(sheet) };
    }
    P.restoreSnapshot = function (sheet, snap, label) {
        sheet.cells = new Map(snap.cells);
        sheet.usedDirty = true;
        var layout = snap.layout;
        sheet.props = clone(layout.props);
        sheet.rows = layout.rows; sheet.cols = layout.cols;
        sheet.frozenRows = layout.frozenRows; sheet.frozenCols = layout.frozenCols;
        this.invalidate();
        this.enqueue({ op: 'replace_sheet', sheet: sheet, label: label });
        this.enqueue({ op: 'sheet_props', sheet: sheet });
        this.emit('structure', { sheet: sheet });
    };

    function shiftIndexMap(map, at, count) {
        var out = {};
        Object.keys(map || {}).forEach(function (k) {
            var i = +k;
            if (i < at) out[k] = map[k];
            else if (count > 0) out[String(i + count)] = map[k];
            else if (i >= at - count) out[String(i + count)] = map[k];
        });
        return out;
    }
    function shiftIndexList(list, at, count) {
        var out = [];
        (list || []).forEach(function (i) {
            if (i < at) out.push(i);
            else if (count > 0) out.push(i + count);
            else if (i >= at - count) out.push(i + count);
        });
        return out;
    }
    /** Shift a {r1,c1,r2,c2} range; returns null if it was deleted entirely. */
    function shiftRange(rg, axis, at, count) {
        var lo = axis === 'row' ? 'r1' : 'c1', hi = axis === 'row' ? 'r2' : 'c2';
        var out = Object.assign({}, rg);
        if (count > 0) {
            if (out[lo] >= at) out[lo] += count;
            if (out[hi] >= at) out[hi] += count;
            return out;
        }
        var del = -count, end = at + del - 1;
        if (out[lo] >= at && out[hi] <= end) return null;
        out[lo] = out[lo] > end ? out[lo] - del : (out[lo] >= at ? at : out[lo]);
        out[hi] = out[hi] > end ? out[hi] - del : (out[hi] >= at ? at - 1 : out[hi]);
        return out[hi] < out[lo] ? null : out;
    }
    CS.shiftRange = shiftRange;
    function shiftProps(props, axis, at, count) {
        var p = clone(props);
        if (axis === 'row') { p.rh = shiftIndexMap(p.rh, at, count); p.hr = shiftIndexList(p.hr, at, count); }
        else { p.cw = shiftIndexMap(p.cw, at, count); p.hc = shiftIndexList(p.hc, at, count); }
        p.merges = (p.merges || []).map(function (m) { return shiftRange(m, axis, at, count); })
            .filter(function (m) { return m && (m.r2 > m.r1 || m.c2 > m.c1); });
        p.cf = (p.cf || []).map(function (x) { var s = shiftRange(x, axis, at, count); return s ? Object.assign({}, x, s) : null; }).filter(Boolean);
        p.dv = (p.dv || []).map(function (x) { var s = shiftRange(x, axis, at, count); return s ? Object.assign({}, x, s) : null; }).filter(Boolean);
        if (p.filter) {
            var f = shiftRange(p.filter, axis, at, count);
            if (!f) p.filter = null;
            else {
                if (axis === 'col') {
                    var crit = {};
                    Object.keys(p.filter.crit || {}).forEach(function (k) {
                        var i = +k;
                        if (i < at) crit[k] = p.filter.crit[k];
                        else if (count > 0) crit[i + count] = p.filter.crit[k];
                        else if (i >= at - count) crit[i + count] = p.filter.crit[k];
                    });
                    f.crit = crit;
                }
                p.filter = f;
            }
        }
        return p;
    }

    /**
     * Insert (count > 0) or delete (count < 0) rows/columns at `at`.
     * Formulas anywhere in the workbook that point at moved cells are
     * rewritten. All sheets are loaded first so none are missed.
     */
    P.shiftLines = function (sheet, axis, at, count) {
        var self = this;
        if (!this.can.edit) return Promise.resolve(false);
        return this.loadAll().then(function () {
            var label = (count > 0 ? 'Insert ' : 'Delete ') + Math.abs(count) + ' ' + axis + (Math.abs(count) > 1 ? 's' : '');
            self.begin(label);
            var before = snapshot(sheet);
            var del = count < 0 ? -count : 0;
            // Move this sheet's cells.
            var moved = new Map();
            sheet.cells.forEach(function (cell, key) {
                var i = key.indexOf(','), r = +key.slice(0, i), c = +key.slice(i + 1);
                var idx = axis === 'row' ? r : c;
                if (count > 0) { if (idx >= at) idx += count; }
                else if (idx >= at && idx < at + del) return;
                else if (idx >= at + del) idx -= del;
                moved.set(axis === 'row' ? CS.key(idx, c) : CS.key(r, idx), cell);
            });
            sheet.cells = moved;
            sheet.props = shiftProps(sheet.props, axis, at, count);
            if (axis === 'row') {
                sheet.rows = Math.max(1, sheet.rows + count);
                if (sheet.frozenRows > at) sheet.frozenRows = Math.max(at, sheet.frozenRows + count);
            } else {
                sheet.cols = Math.max(1, sheet.cols + count);
                if (sheet.frozenCols > at) sheet.frozenCols = Math.max(at, sheet.frozenCols + count);
            }
            sheet.usedDirty = true;
            var op = (count > 0 ? 'insert_' : 'delete_') + (axis === 'row' ? 'rows' : 'cols');
            self.enqueue({ op: op, sheet: sheet, at: at, count: Math.abs(count) });
            // Rewrite formulas in this sheet (new coordinates) and others.
            var ownChanges = [];
            sheet.cells.forEach(function (cell, key) {
                if (typeof cell.v !== 'string' || cell.v.charAt(0) !== '=') return;
                var nv = X.adjust(cell.v, sheet.name, sheet.name, axis, at, count);
                if (nv !== cell.v) {
                    var i = key.indexOf(',');
                    ownChanges.push({ r: +key.slice(0, i), c: +key.slice(i + 1), v: nv, f: cell.f });
                    sheet.cells.set(key, { v: nv, f: cell.f });
                }
            });
            if (ownChanges.length) self.enqueue({ op: 'set_cells', sheet: sheet, cells: ownChanges });
            self.enqueue({ op: 'sheet_props', sheet: sheet });
            self.record({ type: 'snapshot', sheet: sheet, before: before, after: snapshot(sheet), label: label });
            self.sheets.forEach(function (other) {
                if (other === sheet) return;
                var changes = [];
                other.cells.forEach(function (cell, key) {
                    if (typeof cell.v !== 'string' || cell.v.charAt(0) !== '=') return;
                    var nv = X.adjust(cell.v, other.name, sheet.name, axis, at, count);
                    if (nv !== cell.v) { var i = key.indexOf(','); changes.push({ r: +key.slice(0, i), c: +key.slice(i + 1), v: nv }); }
                });
                if (changes.length) self.setCells(other, changes);
            });
            self.commit();
            self.invalidate();
            self.emit('structure', { sheet: sheet });
            return true;
        });
    };

    // ── Sheets ──────────────────────────────────────────────────────────
    P.uniqueSheetName = function (base, except) {
        var name = base, n = 2, self = this;
        while (this.sheets.some(function (s) { return s !== except && s.name.toLowerCase() === name.toLowerCase(); })) name = base + ' (' + (n++) + ')';
        return name;
    };
    P.nextSheetName = function () {
        var n = this.sheets.length + 1;
        while (this.sheetByName('Sheet' + n)) n++;
        return 'Sheet' + n;
    };
    P.addSheet = function (name, afterSheet) {
        var self = this;
        var pos = afterSheet ? afterSheet.position + 0.5 : this.sheets.length ? this.sheets[this.sheets.length - 1].position + 1 : 0;
        var sheet = {
            id: 'tmp-' + Date.now().toString(36) + '-' + (++tmpCounter), name: this.uniqueSheetName(name || this.nextSheetName()),
            position: pos, color: null, hidden: false, rows: 1000, cols: 26, frozenRows: 0, frozenCols: 0,
            props: emptyProps(), cells: new Map(), loaded: true,
        };
        var attach = function () {
            sheet.id = 'tmp-' + Date.now().toString(36) + '-' + (++tmpCounter);
            self.sheets.push(sheet);
            self.sortSheets();
            self.renumber();
            self.enqueue({ op: 'add_sheet', sheet: sheet, client_id: sheet.id, name: sheet.name, position: sheet.position });
            if (sheet.cells.size) self.enqueue({ op: 'replace_sheet', sheet: sheet });
            self.enqueue({ op: 'move_sheets' });
            self.emit('sheets');
        };
        var detach = function () {
            self.sheets.splice(self.sheets.indexOf(sheet), 1);
            self.enqueue({ op: 'delete_sheet', sheet: sheet });
            self.emit('sheets');
        };
        attach();
        this.record({ type: 'custom', before: detach, after: attach, label: 'Add sheet' });
        return sheet;
    };
    P.renumber = function () { this.sheets.forEach(function (s, i) { s.position = i; }); };
    P.duplicateSheet = function (src) {
        var self = this;
        return this.loadSheet(src).then(function () {
            var sheet = {
                id: 'tmp-' + Date.now().toString(36) + '-' + (++tmpCounter), name: self.uniqueSheetName('Copy of ' + src.name),
                position: src.position + 0.5, color: src.color, hidden: false, rows: src.rows, cols: src.cols,
                frozenRows: src.frozenRows, frozenCols: src.frozenCols, props: clone(src.props), cells: new Map(src.cells), loaded: true,
            };
            self.sheets.push(sheet);
            self.sortSheets();
            self.renumber();
            self.enqueue({ op: 'duplicate_sheet', sheet: src, client_id: sheet.id, name: sheet.name, position: sheet.position, target: sheet });
            self.enqueue({ op: 'move_sheets' });
            self.record({
                type: 'custom', label: 'Duplicate sheet',
                before: function () { self.sheets.splice(self.sheets.indexOf(sheet), 1); self.enqueue({ op: 'delete_sheet', sheet: sheet }); self.emit('sheets'); },
                after: function () {
                    sheet.id = 'tmp-' + Date.now().toString(36) + '-' + (++tmpCounter);
                    self.sheets.push(sheet); self.sortSheets(); self.renumber();
                    self.enqueue({ op: 'add_sheet', sheet: sheet, client_id: sheet.id, name: sheet.name, position: sheet.position });
                    self.enqueue({ op: 'replace_sheet', sheet: sheet });
                    self.enqueue({ op: 'sheet_props', sheet: sheet });
                    self.enqueue({ op: 'move_sheets' });
                    self.emit('sheets');
                },
            });
            self.emit('sheets');
            return sheet;
        });
    };
    /** Rename; formulas that name the sheet are updated too. */
    P.renameSheet = function (sheet, name) {
        var self = this;
        var old = sheet.name;
        if (name === old) return Promise.resolve(true);
        if (this.sheets.some(function (s) { return s !== sheet && s.name.toLowerCase() === name.toLowerCase(); })) {
            return Promise.reject(new Error('A sheet named "' + name + '" already exists.'));
        }
        return this.loadAll().then(function () {
            self.begin('Rename sheet');
            var apply = function (to, from) {
                sheet.name = to;
                self.enqueue({ op: 'sheet_meta', sheet: sheet, name: to });
                self.emit('sheets');
                void from;
            };
            apply(name, old);
            self.record({ type: 'custom', label: 'Rename sheet', before: function () { apply(old, name); }, after: function () { apply(name, old); } });
            self.sheets.forEach(function (s) {
                var changes = [];
                s.cells.forEach(function (cell, key) {
                    if (typeof cell.v !== 'string' || cell.v.charAt(0) !== '=') return;
                    var nv = X.renameSheet(cell.v, old, name);
                    if (nv !== cell.v) { var i = key.indexOf(','); changes.push({ r: +key.slice(0, i), c: +key.slice(i + 1), v: nv }); }
                });
                if (changes.length) self.setCells(s, changes);
            });
            self.commit();
            self.invalidate();
            return true;
        });
    };
    P.setSheetMeta = function (sheet, field, value, label) {
        var self = this, old = sheet[field];
        if (field === 'hidden' && value && this.visibleSheets().length <= 1) {
            CS.toast('At least one sheet must stay visible.', 'error');
            return false;
        }
        var apply = function (v) {
            sheet[field] = v;
            var op = { op: 'sheet_meta', sheet: sheet };
            op[field] = v;
            self.enqueue(op);
            self.emit('sheets');
        };
        apply(value);
        this.record({ type: 'custom', label: label, before: function () { apply(old); }, after: function () { apply(value); } });
        return true;
    };
    P.moveSheet = function (sheet, toIndex) {
        var self = this;
        var order = this.sheets.slice();
        var from = order.indexOf(sheet);
        if (from < 0 || toIndex === from) return;
        var apply = function (list) {
            self.sheets = list.slice();
            self.renumber();
            self.enqueue({ op: 'move_sheets' });
            self.emit('sheets');
        };
        var after = order.slice();
        after.splice(from, 1);
        after.splice(Math.max(0, Math.min(after.length, toIndex)), 0, sheet);
        apply(after);
        this.record({ type: 'custom', label: 'Move sheet', before: function () { apply(order); }, after: function () { apply(after); } });
    };
    /** Deleting a sheet can't be undone (the dialog says so). */
    P.deleteSheet = function (sheet) {
        if (this.sheets.length <= 1) { CS.toast('A spreadsheet must keep at least one sheet.', 'error'); return false; }
        var others = this.sheets.filter(function (s) { return s !== sheet && !s.hidden; });
        if (!others.length) { CS.toast('Unhide another sheet first - at least one must stay visible.', 'error'); return false; }
        this.sheets.splice(this.sheets.indexOf(sheet), 1);
        this.enqueue({ op: 'delete_sheet', sheet: sheet });
        // Undo history can't bring a deleted sheet back; drop steps that touch it.
        var touches = function (tx) { return tx.steps.some(function (st) { return st.sheet === sheet; }); };
        this.undoStack = this.undoStack.filter(function (tx) { return !touches(tx); });
        this.redoStack = this.redoStack.filter(function (tx) { return !touches(tx); });
        this.invalidate();
        this.emit('sheets');
        this.emit('history');
        return true;
    };

    // ── Save queue ──────────────────────────────────────────────────────
    P.enqueue = function (op) {
        var last = this.queue[this.queue.length - 1];
        if (op.op === 'set_cells') {
            if (last && last.op === 'set_cells' && last.sheet === op.sheet) {
                op.cells.forEach(function (c) { last.cells.set(CS.key(c.r, c.c), c); });
            } else {
                var m = new Map();
                op.cells.forEach(function (c) { m.set(CS.key(c.r, c.c), c); });
                this.queue.push({ op: 'set_cells', sheet: op.sheet, cells: m });
            }
        } else if (op.op === 'sheet_props' && last && last.op === 'sheet_props' && last.sheet === op.sheet) {
            // already queued; it reads the sheet's latest layout when sent
        } else if (op.op === 'move_sheets' && last && last.op === 'move_sheets') {
            // same
        } else {
            this.queue.push(op);
        }
        this.setStatus('pending');
        if (!this.firstQueuedAt) this.firstQueuedAt = Date.now();
        if (Date.now() - this.firstQueuedAt > SAVE_MAX_WAIT) this.save(); else this.saveSoon();
    };
    /** Cells still waiting to be saved for a sheet (key -> state). */
    P.pendingCells = function (sheet) {
        var out = new Map();
        [].concat(this.inflightOps || [], this.queue).forEach(function (op) {
            if (op.op === 'set_cells' && op.sheet === sheet) op.cells.forEach(function (c, k) { out.set(k, c); });
        });
        return out;
    };
    P.hasPending = function () { return this.queue.length > 0 || !!this.inflight; };

    function serialize(op, self) {
        var sid = op.sheet ? op.sheet.id : undefined;
        switch (op.op) {
            case 'set_cells': return { op: 'set_cells', sheet_id: sid, cells: Array.from(op.cells.values()) };
            case 'sheet_props': return {
                op: 'sheet_props', sheet_id: sid, props: op.sheet.props, rows: op.sheet.rows, cols: op.sheet.cols,
                frozen_rows: op.sheet.frozenRows, frozen_cols: op.sheet.frozenCols,
            };
            case 'replace_sheet': {
                var cells = [];
                op.sheet.cells.forEach(function (cell, key) {
                    var i = key.indexOf(',');
                    cells.push({ r: +key.slice(0, i), c: +key.slice(i + 1), v: cell.v, f: cell.f });
                });
                return { op: 'replace_sheet', sheet_id: sid, cells: cells, label: op.label };
            }
            case 'add_sheet': return { op: 'add_sheet', client_id: op.client_id, name: op.sheet.name, position: Math.round(op.sheet.position) };
            case 'duplicate_sheet': return { op: 'duplicate_sheet', sheet_id: sid, client_id: op.client_id, name: op.target.name, position: Math.round(op.target.position) };
            case 'move_sheets': return { op: 'move_sheets', order: self.sheets.map(function (s) { return s.id; }) };
            case 'delete_sheet': return { op: 'delete_sheet', sheet_id: sid };
            case 'sheet_meta': {
                var out = { op: 'sheet_meta', sheet_id: sid };
                ['name', 'color', 'hidden'].forEach(function (k) { if (k in op) out[k] = op[k]; });
                return out;
            }
            default: return Object.assign({}, op, { sheet: undefined, sheet_id: sid });
        }
    }

    P.setStatus = function (status, message) {
        this.status = status;
        this.statusMessage = message || '';
        this.emit('status', { status: status, message: message });
    };

    /** Send everything queued as one batch. */
    P.save = function (force) {
        var self = this;
        this.saveSoon.cancel();
        if (this.inflight || !this.queue.length) return this.inflight || Promise.resolve(true);
        clearTimeout(this.retryTimer);
        var ops = this.queue;
        this.queue = [];
        this.firstQueuedAt = null;
        this.inflightOps = ops;
        var payload = ops.map(function (op) { return serialize(op, self); });
        // A sheet that was added and deleted before saving never existed.
        payload = payload.filter(function (p) { return !(p.op === 'delete_sheet' && String(p.sheet_id).indexOf('tmp-') === 0 && !payload.some(function (q) { return (q.op === 'add_sheet' || q.op === 'duplicate_sheet') && q.client_id === p.sheet_id; })); });
        this.setStatus('saving');
        this.inflight = CS.api('POST', '/spreadsheets/' + this.id + '/batch', { base_version: this.version, ops: payload, force: !!force })
            .then(function (res) {
                self.inflight = null;
                self.inflightOps = null;
                if (res.ok) {
                    self.retryDelay = 0;
                    self.version = res.data.version;
                    self.applyIdMap(res.data.id_map || {});
                    self.lastSaved = new Date();
                    self.applyRemote(res.data.changes, true);
                    self.setStatus(self.queue.length ? 'pending' : 'saved');
                    if (self.queue.length) self.saveSoon();
                    return true;
                }
                // Put the changes back - nothing is lost.
                self.queue = ops.concat(self.queue);
                if (res.status === 409) {
                    self.setStatus('conflict', CS.errorText(res));
                    self.emit('conflict', res.data);
                    return false;
                }
                if (res.status === 0 || res.status >= 500 || res.status === 429) {
                    self.retryDelay = Math.min(60000, self.retryDelay ? self.retryDelay * 2 : 3000);
                    self.setStatus('error', CS.errorText(res, 'Unable to save changes.'));
                    self.retryTimer = setTimeout(function () { self.save(); }, self.retryDelay);
                    return false;
                }
                if (res.status === 401) { self.setStatus('error', 'Session expired.'); return false; }
                // 400/403/404: the server refused these changes. Drop them and
                // resync so the screen matches what is actually saved.
                self.queue = self.queue.slice(ops.length);
                self.setStatus('error', CS.errorText(res, 'Unable to save changes.'));
                self.emit('rejected', { message: CS.errorText(res, 'Unable to save changes.'), status: res.status });
                return false;
            });
        return this.inflight;
    };
    P.retry = function () { this.retryDelay = 0; return this.save(); };
    /** Conflict resolution: "Keep my changes". */
    P.forceSave = function () { return this.save(true); };
    /** Conflict resolution: "Reload latest" - discards unsaved changes. */
    P.discardAndReload = function () {
        this.queue = [];
        this.undoStack = [];
        this.redoStack = [];
        this.emit('history');
        this.setStatus('saved');
        return this.reloadAll();
    };

    P.applyIdMap = function (map) {
        var self = this;
        Object.keys(map).forEach(function (tmp) {
            var s = self.sheetById(tmp);
            if (s) { s.id = map[tmp]; s.loaded = true; }
        });
        if (Object.keys(map).length) this.emit('sheets');
    };

    /** Merge other people's changes (from a save response or a poll). */
    P.applyRemote = function (ch, fromSave) {
        if (!ch) return;
        var self = this;
        if (ch.reload) {
            if (!fromSave) this.emit('remote-structure', ch);
            return;
        }
        var touched = false;
        // Sheet list: names, colours, order, visibility, new/removed sheets.
        if (ch.sheets && !this.queue.some(function (op) { return /sheet|move/.test(op.op) && op.op !== 'set_cells' && op.op !== 'sheet_props'; })) {
            var seen = {};
            ch.sheets.forEach(function (m) {
                seen[m.id] = true;
                var s = self.sheetById(m.id);
                if (!s) {
                    self.sheets.push({ id: m.id, cells: new Map(), loaded: false, props: emptyProps(), name: m.name });
                    s = self.sheets[self.sheets.length - 1];
                    touched = true;
                }
                var before = s.name + s.color + s.hidden + s.position;
                applyMeta(s, m);
                if (before !== s.name + s.color + s.hidden + s.position) touched = true;
            });
            var keep = this.sheets.filter(function (s) { return seen[s.id] || typeof s.id !== 'number'; });
            if (keep.length !== this.sheets.length) touched = true;
            this.sheets = keep;
            this.sortSheets();
            if (touched) this.emit('sheets', { remote: true });
        }
        var changedCells = 0;
        Object.keys(ch.cells || {}).forEach(function (sid) {
            var s = self.sheetById(sid);
            if (!s || !s.loaded) return;
            var pending = self.pendingCells(s);
            ch.cells[sid].forEach(function (c) {
                var k = CS.key(c.r, c.c);
                if (pending.has(k)) return;
                if (c.v === null && !c.f) s.cells.delete(k); else s.cells.set(k, { v: c.v, f: c.f || null });
                changedCells++;
            });
            s.usedDirty = true;
        });
        Object.keys(ch.props || {}).forEach(function (sid) {
            var s = self.sheetById(sid);
            if (!s || self.queue.some(function (op) { return op.op === 'sheet_props' && op.sheet === s; })) return;
            s.props = Object.assign(emptyProps(), ch.props[sid]);
            touched = true;
            self.emit('layout', { sheet: s, remote: true });
        });
        if (changedCells || touched) {
            this.invalidate();
            this.emit('cells', { remote: true });
            if (!fromSave && ch.updated_by) this.emit('remote-edit', { by: ch.updated_by, count: changedCells });
        }
        if (ch.can) { this.can = ch.can; this.emit('permissions'); }
        if (ch.name && ch.name !== this.name) { this.name = ch.name; this.emit('meta'); }
    };

    /** Look for other people's changes while idle. */
    P.poll = function () {
        var self = this;
        if (document.hidden || this.inflight || this.queue.length || this.polling || this.status === 'conflict') return;
        this.polling = true;
        CS.api('GET', '/spreadsheets/' + this.id + '/changes?since=' + this.version).then(function (res) {
            self.polling = false;
            if (!res.ok) {
                if (res.status === 404) self.emit('lost-access');
                return;
            }
            var d = res.data;
            if (d.can) { var was = JSON.stringify(self.can); self.can = d.can; if (was !== JSON.stringify(d.can)) self.emit('permissions'); }
            if (d.version <= self.version) return;
            if (d.reload) {
                if (self.hasPending()) { self.emit('remote-structure', d); return; }
                self.reloadAll().then(function () {
                    self.version = d.version;
                    self.emit('remote-edit', { by: d.updated_by, structure: true });
                });
                return;
            }
            self.applyRemote(d, false);
            self.version = d.version;
        });
    };

    P.destroy = function () { clearInterval(this.pollTimer); };
})();
