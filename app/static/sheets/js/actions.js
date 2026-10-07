/* Spreadsheet module - editing commands (formatting, borders, merging,
 * rows/columns, sort, filter, paste, find/replace, validation...).
 * Each command is one undo step. The UI (ui.js) calls these. */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var X = CS.Formula, FM = CS.Format;
    var MAX_CELLS_PER_ACTION = 250000;

    function clone(o) { return o ? JSON.parse(JSON.stringify(o)) : {}; }

    function Actions(model, grid, ui) {
        this.model = model;
        this.grid = grid;
        this.ui = ui;
    }
    CS.Actions = Actions;
    var A = Actions.prototype;

    A.sheet = function () { return this.grid.sheet; };
    A.guard = function () {
        if (!this.model.can.edit) { this.ui.readOnly(); return false; }
        return true;
    };

    /** Selected ranges clipped to the sheet; whole rows/columns included. */
    A.ranges = function () {
        var g = this.grid;
        return g.selectedRanges().map(function (rg) {
            return { r1: rg.r1, c1: rg.c1, r2: Math.min(rg.r2, g.nRows - 1), c2: Math.min(rg.c2, g.nCols - 1) };
        });
    };
    A.cellCount = function (ranges) {
        return ranges.reduce(function (n, rg) { return n + (rg.r2 - rg.r1 + 1) * (rg.c2 - rg.c1 + 1); }, 0);
    };
    /** Visit every selected cell (formatting a whole column touches every row). */
    A.eachCell = function (fn, ranges) {
        ranges = ranges || this.ranges();
        if (this.cellCount(ranges) > MAX_CELLS_PER_ACTION) {
            CS.toast('That selection is too large to change at once. Select fewer rows or columns.', 'error');
            return false;
        }
        var seen = new Set();
        ranges.forEach(function (rg) {
            for (var r = rg.r1; r <= rg.r2; r++) for (var c = rg.c1; c <= rg.c2; c++) {
                var k = CS.key(r, c);
                if (seen.has(k)) continue;
                seen.add(k);
                fn(r, c);
            }
        });
        return true;
    };
    /** Like eachCell but only cells that have content (for clearing etc.). */
    A.eachFilledCell = function (fn, ranges) {
        var sheet = this.sheet();
        ranges = ranges || this.ranges();
        sheet.cells.forEach(function (cell, key) {
            var i = key.indexOf(','), r = +key.slice(0, i), c = +key.slice(i + 1);
            for (var j = 0; j < ranges.length; j++) if (CS.inRange(ranges[j], r, c)) { fn(r, c, cell); return; }
        });
    };

    A.activeFmt = function () {
        var a = this.grid.sel.active, cell = this.model.raw(this.sheet(), a.r, a.c);
        return cell && cell.f ? cell.f : {};
    };

    // ── Values ──────────────────────────────────────────────────────────
    A.setValue = function (sheet, r, c, raw) {
        if (!this.guard()) return;
        var cell = this.model.raw(sheet, r, c);
        var f = cell && cell.f ? clone(cell.f) : null;
        // Typing "Rs 1,500", "12%" or a date also sets a matching number format.
        if (raw && raw.charAt(0) !== '=' && raw.charAt(0) !== "'" && (!f || !f.nf)) {
            var p = FM.parse(raw);
            if (p.t === 'n' && p.kind && p.kind !== 'datetime') {
                f = f || {};
                if (p.kind === 'currency') f.nf = { t: 'currency', cur: p.cur, d: Number.isInteger(p.v) ? 0 : 2 };
                else if (p.kind === 'percent') f.nf = { t: 'percent', d: Number.isInteger(p.v * 100) ? 0 : 2 };
                else f.nf = { t: p.kind };
            }
        }
        this.model.setCells(sheet, [{ r: r, c: c, v: raw === '' ? null : raw, f: f }], 'Edit cell');
    };

    A.clearContents = function () {
        if (!this.guard()) return;
        var changes = [];
        this.eachFilledCell(function (r, c, cell) { if (cell.v !== null) changes.push({ r: r, c: c, v: null }); });
        if (changes.length) this.model.setCells(this.sheet(), changes, 'Clear contents');
    };
    A.clearFormatting = function () {
        if (!this.guard()) return;
        var changes = [];
        this.eachFilledCell(function (r, c, cell) { if (cell.f) changes.push({ r: r, c: c, f: null }); });
        if (changes.length) this.model.setCells(this.sheet(), changes, 'Clear formatting');
    };
    A.clearAll = function () {
        if (!this.guard()) return;
        var changes = [];
        this.eachFilledCell(function (r, c) { changes.push({ r: r, c: c, v: null, f: null }); });
        if (changes.length) this.model.setCells(this.sheet(), changes, 'Clear');
    };

    // ── Formatting ──────────────────────────────────────────────────────
    A.formatCells = function (mutate, label) {
        if (!this.guard()) return;
        var self = this, sheet = this.sheet(), changes = [];
        var ok = this.eachCell(function (r, c) {
            var cell = self.model.raw(sheet, r, c);
            var f = mutate(clone(cell && cell.f), r, c);
            changes.push({ r: r, c: c, f: f && Object.keys(f).length ? f : null });
        });
        if (ok && changes.length) this.model.setCells(sheet, changes, label || 'Format');
    };
    A.toggleStyle = function (key) {
        var on = !this.activeFmt()[key];
        var names = { b: 'Bold', i: 'Italic', u: 'Underline', s: 'Strikethrough' };
        this.formatCells(function (f) { if (on) f[key] = true; else delete f[key]; return f; }, names[key]);
    };
    A.setStyle = function (key, value, label) {
        this.formatCells(function (f) {
            if (value === null || value === undefined || value === '') delete f[key]; else f[key] = value;
            return f;
        }, label || 'Format');
    };
    A.setNumberFormat = function (nf) {
        this.formatCells(function (f) { if (!nf || nf.t === 'auto') delete f.nf; else f.nf = clone(nf); return f; }, 'Number format');
    };
    A.adjustDecimals = function (delta) {
        var self = this, sheet = this.sheet();
        this.formatCells(function (f, r, c) {
            var v = self.model.value(sheet, r, c);
            if (v.t !== 'n') return f;
            var nf = f.nf ? clone(f.nf) : { t: v.kind === 'currency' ? 'currency' : v.kind === 'percent' ? 'percent' : 'decimal' };
            if (/^(date|time|datetime|text)$/.test(nf.t)) return f;
            if (nf.t === 'currency' && !nf.cur) nf.cur = v.cur || 'Rs';
            var cur = nf.d !== undefined ? nf.d : (nf.t === 'number' ? 0 : nf.t === 'currency' ? 0 : 2);
            if (nf.d === undefined && (nf.t === 'decimal' || nf.t === 'auto')) {
                var s = String(v.v), i = s.indexOf('.');
                cur = i >= 0 ? Math.min(10, s.length - i - 1) : 0;
            }
            nf.d = Math.max(0, Math.min(10, cur + delta));
            if (nf.t === 'auto') nf.t = 'decimal';
            f.nf = nf;
            return f;
        }, delta > 0 ? 'Increase decimals' : 'Decrease decimals');
    };

    /** kind: all|outer|inner|horizontal|vertical|top|bottom|left|right|none */
    A.borders = function (kind, spec) {
        if (!this.guard()) return;
        var self = this, sheet = this.sheet(), changes = [];
        var b = { w: spec.w || 1, s: spec.s || 'solid', c: spec.c || '#000000' };
        var ranges = this.ranges();
        if (this.cellCount(ranges) > MAX_CELLS_PER_ACTION) { CS.toast('That selection is too large to change at once.', 'error'); return; }
        var states = new Map();
        var get = function (r, c) {
            var k = CS.key(r, c);
            if (!states.has(k)) { var cell = self.model.raw(sheet, r, c); states.set(k, { r: r, c: c, f: clone(cell && cell.f) }); }
            return states.get(k).f;
        };
        ranges.forEach(function (rg) {
            for (var r = rg.r1; r <= rg.r2; r++) for (var c = rg.c1; c <= rg.c2; c++) {
                var f = get(r, c);
                var top = r === rg.r1, bottom = r === rg.r2, left = c === rg.c1, right = c === rg.c2;
                var set = function (side, on) { if (on) f[side] = clone(b); };
                switch (kind) {
                    case 'none': delete f.bt; delete f.bb; delete f.bl; delete f.br; break;
                    case 'all': set('bt', true); set('bb', true); set('bl', true); set('br', true); break;
                    case 'outer': set('bt', top); set('bb', bottom); set('bl', left); set('br', right); break;
                    case 'inner': set('bb', !bottom); set('br', !right); break;
                    case 'horizontal': set('bb', !bottom); break;
                    case 'vertical': set('br', !right); break;
                    case 'top': set('bt', top); break;
                    case 'bottom': set('bb', bottom); break;
                    case 'left': set('bl', left); break;
                    case 'right': set('br', right); break;
                }
            }
            if (kind === 'none') {
                // Also remove the neighbours' sides that touch the range.
                for (var cc = rg.c1; cc <= rg.c2; cc++) {
                    if (rg.r1 > 0) delete get(rg.r1 - 1, cc).bb;
                    if (rg.r2 < self.grid.nRows - 1) delete get(rg.r2 + 1, cc).bt;
                }
                for (var rr = rg.r1; rr <= rg.r2; rr++) {
                    if (rg.c1 > 0) delete get(rr, rg.c1 - 1).br;
                    if (rg.c2 < self.grid.nCols - 1) delete get(rr, rg.c2 + 1).bl;
                }
            }
        });
        states.forEach(function (s) { changes.push({ r: s.r, c: s.c, f: Object.keys(s.f).length ? s.f : null }); });
        this.model.setCells(sheet, changes, 'Borders');
    };

    // ── Merging ─────────────────────────────────────────────────────────
    /** kind: all | horizontal | vertical | unmerge */
    A.merge = function (kind) {
        if (!this.guard()) return;
        var self = this, sheet = this.sheet(), ranges = this.ranges();
        var targets = [];
        ranges.forEach(function (rg) {
            if (kind === 'all') targets.push(rg);
            else if (kind === 'horizontal') for (var r = rg.r1; r <= rg.r2; r++) targets.push({ r1: r, c1: rg.c1, r2: r, c2: rg.c2 });
            else if (kind === 'vertical') for (var c = rg.c1; c <= rg.c2; c++) targets.push({ r1: rg.r1, c1: c, r2: rg.r2, c2: c });
        });
        var overlaps = function (a, b) { return !(a.r2 < b.r1 || a.r1 > b.r2 || a.c2 < b.c1 || a.c1 > b.c2); };
        if (kind === 'unmerge') {
            this.model.updateLayout(sheet, 'Unmerge', function (s) {
                s.props.merges = (s.props.merges || []).filter(function (m) { return !ranges.some(function (rg) { return overlaps(m, rg); }); });
            });
            this.grid.mergeIndex = null;
            return;
        }
        targets = targets.filter(function (t) { return t.r2 > t.r1 || t.c2 > t.c1; });
        if (!targets.length) { CS.toast('Select more than one cell to merge.', 'info'); return; }
        if (this.cellCount(targets) > 20000) { CS.toast('That range is too large to merge.', 'error'); return; }
        var lost = [];
        targets.forEach(function (t) {
            for (var r = t.r1; r <= t.r2; r++) for (var c = t.c1; c <= t.c2; c++) {
                if ((r !== t.r1 || c !== t.c1) && self.grid.hasValue(r, c)) lost.push({ r: r, c: c, v: null });
            }
        });
        var go = function () {
            self.model.begin('Merge cells');
            if (lost.length) self.model.setCells(sheet, lost);
            self.model.updateLayout(sheet, 'Merge cells', function (s) {
                var keep = (s.props.merges || []).filter(function (m) { return !targets.some(function (t) { return overlaps(m, t); }); });
                s.props.merges = keep.concat(targets.map(function (t) { return { r1: t.r1, c1: t.c1, r2: t.r2, c2: t.c2 }; }));
            });
            self.model.commit();
            self.grid.mergeIndex = null;
            var first = targets[0];
            self.grid.select({ r1: first.r1, c1: first.c1, r2: first.r2, c2: first.c2 }, { r: first.r1, c: first.c1 });
        };
        if (lost.length) {
            CS.confirm('Merging cells only keeps the top-left value. The other ' + lost.length + ' value(s) will be removed.', { ok: 'Merge', title: 'Merge cells' })
                .then(function (ok) { if (ok) go(); });
        } else go();
    };

    // ── Rows & columns ──────────────────────────────────────────────────
    A.lineSpan = function (axis) {
        var rg = this.grid.activeRange();
        return axis === 'row' ? { at: rg.r1, count: Math.min(rg.r2, this.grid.nRows - 1) - rg.r1 + 1 } : { at: rg.c1, count: Math.min(rg.c2, this.grid.nCols - 1) - rg.c1 + 1 };
    };
    A.insertLines = function (axis, where) {
        if (!this.guard()) return;
        var span = this.lineSpan(axis), self = this;
        var count = Math.min(span.count, 1000);
        var at = where === 'before' ? span.at : span.at + span.count;
        var limit = axis === 'row' ? 50000 : 260;
        if ((axis === 'row' ? this.sheet().rows : this.sheet().cols) + count > limit) {
            CS.toast('A sheet can have at most ' + limit.toLocaleString() + ' ' + axis + 's.', 'error');
            return;
        }
        this.model.shiftLines(this.sheet(), axis, at, count).then(function () {
            if (axis === 'row') self.grid.selectRows(at, at + count - 1); else self.grid.selectCols(at, at + count - 1);
        });
    };
    A.deleteLines = function (axis) {
        if (!this.guard()) return;
        var span = this.lineSpan(axis), self = this, sheet = this.sheet();
        var total = axis === 'row' ? sheet.rows : sheet.cols;
        if (span.count >= total) { CS.toast('You can\'t delete every ' + axis + ' of a sheet.', 'error'); return; }
        this.model.shiftLines(sheet, axis, span.at, -span.count).then(function () {
            var p = Math.min(span.at, (axis === 'row' ? sheet.rows : sheet.cols) - 1);
            if (axis === 'row') self.grid.selectCell(p, self.grid.sel.active.c); else self.grid.selectCell(self.grid.sel.active.r, p);
        });
    };
    A.hideLines = function (axis) {
        if (!this.guard()) return;
        var span = this.lineSpan(axis), sheet = this.sheet();
        var total = axis === 'row' ? sheet.rows : sheet.cols;
        var key = axis === 'row' ? 'hr' : 'hc';
        this.model.updateLayout(sheet, 'Hide ' + axis + 's', function (s) {
            var set = new Set(s.props[key] || []);
            for (var i = span.at; i < span.at + span.count; i++) set.add(i);
            if (set.size >= total) return;
            s.props[key] = Array.from(set).sort(function (a, b) { return a - b; });
        });
    };
    /** Show hidden rows/columns: all of them, or the block ending before `at`. */
    A.unhideLines = function (axis, at) {
        if (!this.guard()) return;
        var key = axis === 'row' ? 'hr' : 'hc', span = at === undefined ? this.lineSpan(axis) : null;
        this.model.updateLayout(this.sheet(), 'Show hidden ' + axis + 's', function (s) {
            var list = s.props[key] || [];
            if (at !== undefined) {
                var set = new Set(list), i = at - 1;
                while (i >= 0 && set.has(i)) { set.delete(i); i--; }
                s.props[key] = Array.from(set).sort(function (a, b) { return a - b; });
            } else if (span && span.count > 1) {
                s.props[key] = list.filter(function (i) { return i < span.at || i >= span.at + span.count; });
            } else {
                s.props[key] = [];
            }
        });
    };
    A.resizeLines = function (axis, indexes, size) {
        if (!this.guard()) return;
        var key = axis === 'row' ? 'rh' : 'cw', def = axis === 'row' ? CS.Grid.DEFAULT_H : CS.Grid.DEFAULT_W;
        this.model.updateLayout(this.sheet(), axis === 'row' ? 'Resize rows' : 'Resize columns', function (s) {
            indexes.forEach(function (i) { if (size === def || size === null) delete s.props[key][i]; else s.props[key][i] = size; });
        });
    };
    A.setSizes = function (axis, map) {
        if (!this.guard()) return;
        var key = axis === 'row' ? 'rh' : 'cw', def = axis === 'row' ? CS.Grid.DEFAULT_H : CS.Grid.DEFAULT_W;
        this.model.updateLayout(this.sheet(), 'Fit to data', function (s) {
            Object.keys(map).forEach(function (i) { if (map[i] === def) delete s.props[key][i]; else s.props[key][i] = map[i]; });
        });
    };
    A.addRows = function (n) {
        if (!this.guard()) return;
        this.model.updateLayout(this.sheet(), 'Add rows', function (s) { s.rows = Math.min(50000, s.rows + n); });
    };
    A.addCols = function (n) {
        if (!this.guard()) return;
        this.model.updateLayout(this.sheet(), 'Add columns', function (s) { s.cols = Math.min(260, s.cols + n); });
    };
    A.freeze = function (rows, cols) {
        if (!this.guard()) return;
        this.model.updateLayout(this.sheet(), 'Freeze', function (s) {
            if (rows !== null) s.frozenRows = Math.max(0, Math.min(50, rows));
            if (cols !== null) s.frozenCols = Math.max(0, Math.min(26, cols));
        });
    };

    // ── Data region / sort / filter ─────────────────────────────────────
    /** The block of data around (r, c), bounded by empty rows/columns. */
    A.dataRegion = function (r, c) {
        var g = this.grid, rg = { r1: r, c1: c, r2: r, c2: c }, changed = true;
        var rowHas = function (rr, c1, c2) { for (var cc = c1; cc <= c2; cc++) if (g.hasValue(rr, cc)) return true; return false; };
        var colHas = function (cc, r1, r2) { for (var rr = r1; rr <= r2; rr++) if (g.hasValue(rr, cc)) return true; return false; };
        var guard = 0;
        while (changed && guard++ < 10000) {
            changed = false;
            var c1 = Math.max(0, rg.c1 - 1), c2 = Math.min(g.nCols - 1, rg.c2 + 1);
            if (rg.r1 > 0 && rowHas(rg.r1 - 1, c1, c2)) { rg.r1--; changed = true; }
            if (rg.r2 < g.nRows - 1 && rowHas(rg.r2 + 1, c1, c2)) { rg.r2++; changed = true; }
            var r1 = Math.max(0, rg.r1 - 1), r2 = Math.min(g.nRows - 1, rg.r2 + 1);
            if (rg.c1 > 0 && colHas(rg.c1 - 1, r1, r2)) { rg.c1--; changed = true; }
            if (rg.c2 < g.nCols - 1 && colHas(rg.c2 + 1, r1, r2)) { rg.c2++; changed = true; }
        }
        return rg;
    };

    /**
     * Sort rows of `rg` by keys [{c, asc}]. Each row moves as a whole; values
     * and formats move together and relative references in moved formulas
     * follow their row.
     */
    A.sortRange = function (rg, keys, hasHeader) {
        if (!this.guard()) return;
        var self = this, sheet = this.sheet(), model = this.model;
        var start = rg.r1 + (hasHeader ? 1 : 0);
        var used = model.used(sheet);
        var end = Math.min(rg.r2, used.rows - 1);
        if (end <= start) return;
        var merges = (sheet.props.merges || []).filter(function (m) { return !(m.r2 < start || m.r1 > end || m.c2 < rg.c1 || m.c1 > rg.c2); });
        if (merges.length) { CS.toast('Unmerge cells in the range before sorting.', 'error'); return; }
        var rows = [];
        for (var r = start; r <= end; r++) {
            var cells = [], vals = [];
            for (var c = rg.c1; c <= rg.c2; c++) cells.push(model.raw(sheet, r, c));
            keys.forEach(function (k) { vals.push(model.value(sheet, r, k.c)); });
            rows.push({ r: r, cells: cells, vals: vals });
        }
        rows.sort(function (a, b) {
            for (var i = 0; i < keys.length; i++) {
                var va = a.vals[i], vb = b.vals[i];
                var ea = va.t === 'empty', eb = vb.t === 'empty';
                if (ea || eb) { if (ea && eb) continue; return ea ? 1 : -1; } // blanks last
                var d = X.compare(va, vb);
                if (d) return keys[i].asc ? d : -d;
            }
            return a.r - b.r;
        });
        var changes = [];
        rows.forEach(function (row, i) {
            var target = start + i;
            row.cells.forEach(function (cell, j) {
                var v = cell ? cell.v : null;
                if (typeof v === 'string' && v.charAt(0) === '=' && target !== row.r) v = X.shift(v, target - row.r, 0);
                changes.push({ r: target, c: rg.c1 + j, v: v, f: cell ? cell.f : null });
            });
        });
        model.setCells(sheet, changes, 'Sort range');
        self.grid.requestRender();
    };
    /** Sort the table around the selection by the active column. */
    A.quickSort = function (asc) {
        if (!this.guard()) return;
        var g = this.grid, rg = g.activeRange(), a = g.sel.active, self = this;
        var single = rg.r1 === rg.r2 && rg.c1 === rg.c2;
        var wholeCols = rg.r1 === 0 && rg.r2 >= g.nRows - 1;
        if (single || wholeCols) {
            var region = this.dataRegion(a.r, a.c);
            var filter = this.sheet().props.filter;
            if (filter && CS.inRange(filter, a.r, a.c)) region = { r1: filter.r1, c1: filter.c1, r2: filter.r2, c2: filter.c2 };
            var headerGuess = this.looksLikeHeader(region);
            this.sortRange(region, [{ c: a.c, asc: asc }], headerGuess);
            return;
        }
        if (rg.c1 === rg.c2) {
            var region2 = this.dataRegion(a.r, a.c);
            if (region2.c1 < rg.c1 || region2.c2 > rg.c2) {
                // Sorting one column of a table would scramble the rows.
                CS.dialog({
                    title: 'Sort range',
                    body: '<p>The selected column is part of a table (' + CS.esc(CS.rangeStr(region2)) + '). Sorting only this column would separate its values from the rest of each row.</p>',
                    buttons: [
                        { label: 'Cancel', cls: 'btn-outline-secondary' },
                        { label: 'Sort selected column only', cls: 'btn-outline-danger', action: function () { self.sortRange(rg, [{ c: a.c, asc: asc }], false); } },
                        { label: 'Expand and sort table', cls: 'btn-primary', action: function () { self.sortRange(region2, [{ c: a.c, asc: asc }], self.looksLikeHeader(region2)); } },
                    ],
                });
                return;
            }
        }
        this.sortRange(rg, [{ c: a.c, asc: asc }], false);
    };
    /** First row is a header when it's all text and the next row isn't. */
    A.looksLikeHeader = function (rg) {
        if (rg.r2 <= rg.r1) return false;
        var m = this.model, s = this.sheet(), allText = true, nextHasNumber = false;
        for (var c = rg.c1; c <= rg.c2; c++) {
            var v = m.value(s, rg.r1, c), w = m.value(s, rg.r1 + 1, c);
            if (v.t !== 's' && v.t !== 'empty') allText = false;
            if (w.t === 'n') nextHasNumber = true;
            var cell = m.raw(s, rg.r1, c);
            if (cell && cell.f && cell.f.b) return true;
        }
        return allText && nextHasNumber;
    };

    A.toggleFilter = function () {
        if (!this.guard()) return;
        var sheet = this.sheet(), self = this;
        if (sheet.props.filter) {
            this.model.updateLayout(sheet, 'Remove filter', function (s) { s.props.filter = null; });
            return;
        }
        var g = this.grid, rg = g.activeRange(), a = g.sel.active;
        var region = (rg.r1 === rg.r2 && rg.c1 === rg.c2) || (rg.r1 === 0 && rg.r2 >= g.nRows - 1) ? this.dataRegion(a.r, a.c) : rg;
        if (region.r1 === region.r2 && !g.hasValue(region.r1, region.c1)) { CS.toast('Select a table with a header row to filter.', 'info'); return; }
        region.r2 = Math.max(region.r2, Math.min(g.nRows - 1, this.model.used(sheet).rows - 1));
        this.model.updateLayout(sheet, 'Create filter', function (s) {
            s.props.filter = { r1: region.r1, c1: region.c1, r2: region.r2, c2: region.c2, crit: {} };
        });
        self.grid.select(region, { r: region.r1, c: region.c1 });
    };
    A.setFilterCriteria = function (col, crit) {
        if (!this.model.can.edit) {
            // Viewers may filter for themselves; it isn't saved.
            var f = this.sheet().props.filter;
            if (!f) return;
            if (crit) f.crit[col] = crit; else delete f.crit[col];
            this.model.invalidate();
            this.grid.relayout();
            this.grid.requestRender();
            return;
        }
        this.model.updateLayout(this.sheet(), crit ? 'Filter' : 'Clear filter', function (s) {
            if (!s.props.filter) return;
            s.props.filter.crit = s.props.filter.crit || {};
            if (crit) s.props.filter.crit[col] = crit; else delete s.props.filter.crit[col];
        });
    };
    A.distinctValues = function (col) {
        var f = this.sheet().props.filter, m = this.model, s = this.sheet(), out = new Map();
        var last = Math.min(f.r2, Math.max(f.r1, m.used(s).rows - 1));
        for (var r = f.r1 + 1; r <= last; r++) {
            var d = m.display(s, r, col);
            out.set(d, (out.get(d) || 0) + 1);
        }
        return Array.from(out.keys()).sort(function (a, b) { return a === '' ? 1 : b === '' ? -1 : a.localeCompare(b, undefined, { numeric: true }); });
    };

    // ── Paste / fill ────────────────────────────────────────────────────
    /** mode: all | values | format */
    A.paste = function (text, mode, clip, parseTsv) {
        if (!this.guard()) return;
        var self = this, g = this.grid, sheet = this.sheet(), changes = [];
        var target = g.activeRange();
        var data, h, w;
        if (clip) {
            data = clip.cells;
            h = data.length; w = h ? data[0].length : 0;
        } else {
            var rows = parseTsv(text);
            data = rows.map(function (row) { return row.map(function (v) { return v === '' ? null : { v: v, f: null }; }); });
            h = data.length; w = data.reduce(function (m, r) { return Math.max(m, r.length); }, 0);
        }
        if (!h || !w) return;
        // A single copied cell fills the whole selection; otherwise paste once at the top-left.
        var tileR = clip || h === 1 ? Math.max(1, Math.floor((target.r2 - target.r1 + 1) / h)) : 1;
        var tileC = clip || w === 1 ? Math.max(1, Math.floor((target.c2 - target.c1 + 1) / w)) : 1;
        if (h * tileR * w * tileC > MAX_CELLS_PER_ACTION) { CS.toast('That paste is too large.', 'error'); return; }
        var maxR = target.r1 + h * tileR, maxC = target.c1 + w * tileC;
        if (maxC > 260) { CS.toast('The pasted data doesn\'t fit - a sheet can have at most 260 columns.', 'error'); return; }
        for (var tr = 0; tr < tileR; tr++) for (var tc = 0; tc < tileC; tc++) {
            for (var i = 0; i < h; i++) for (var j = 0; j < w; j++) {
                var src = data[i] ? data[i][j] : null;
                var r = target.r1 + tr * h + i, c = target.c1 + tc * w + j;
                var cur = this.model.raw(sheet, r, c);
                if (mode === 'format') {
                    changes.push({ r: r, c: c, f: src && src.f ? clone(src.f) : null });
                } else if (mode === 'values') {
                    var val = null;
                    if (clip && src) {
                        var sv = this.model.value(clip.sheet, clip.range.r1 + i, clip.range.c1 + j);
                        val = sv.t === 'empty' ? null : sv.t === 'n' ? String(sv.v) : sv.t === 'b' ? (sv.v ? 'TRUE' : 'FALSE') : sv.t === 'e' ? sv.v : sv.v;
                        if (typeof val === 'string' && val.charAt(0) === '=') val = "'" + val;
                    } else if (src) {
                        val = src.v;
                    }
                    changes.push({ r: r, c: c, v: val, f: cur ? cur.f : null });
                } else {
                    var v = src ? src.v : null;
                    if (clip && typeof v === 'string' && v.charAt(0) === '=') v = X.shift(v, r - (clip.range.r1 + i), c - (clip.range.c1 + j));
                    changes.push({ r: r, c: c, v: v, f: clip ? (src && src.f ? clone(src.f) : null) : (cur ? cur.f : null) });
                }
            }
        }
        this.model.begin(clip && clip.cut ? 'Cut and paste' : 'Paste');
        if (clip && clip.cut && mode === 'all') {
            // Moving: clear the source cells that aren't overwritten.
            var dest = { r1: target.r1, c1: target.c1, r2: target.r1 + h - 1, c2: target.c1 + w - 1 };
            var clears = [];
            for (var r0 = clip.range.r1; r0 <= clip.range.r2; r0++) for (var c0 = clip.range.c1; c0 <= clip.range.c2; c0++) {
                if (clip.sheet !== sheet || !CS.inRange(dest, r0, c0)) clears.push({ r: r0, c: c0, v: null, f: null });
            }
            if (clears.length) this.model.setCells(clip.sheet, clears);
            g.clip = null;
        }
        this.model.setCells(sheet, changes, 'Paste');
        this.model.commit();
        if (maxR > sheet.rows) this.model.updateLayout(sheet, 'Grow', function (s) { s.rows = Math.min(50000, maxR + 100); });
        g.select({ r1: target.r1, c1: target.c1, r2: maxR - 1, c2: maxC - 1 }, { r: target.r1, c: target.c1 });
        void self;
    };
    /** Ctrl+D / Ctrl+R: copy the first row/column of the selection across it. */
    A.fill = function (dir) {
        if (!this.guard()) return;
        var rg = this.grid.activeRange(), sheet = this.sheet(), changes = [], m = this.model;
        if (dir === 'down') {
            var srcR = rg.r1 === rg.r2 ? rg.r1 - 1 : rg.r1;
            if (srcR < 0) return;
            for (var r = srcR + 1; r <= rg.r2; r++) for (var c = rg.c1; c <= rg.c2; c++) {
                var cell = m.raw(sheet, srcR, c), v = cell ? cell.v : null;
                if (typeof v === 'string' && v.charAt(0) === '=') v = X.shift(v, r - srcR, 0);
                changes.push({ r: r, c: c, v: v, f: cell ? cell.f : null });
            }
        } else {
            var srcC = rg.c1 === rg.c2 ? rg.c1 - 1 : rg.c1;
            if (srcC < 0) return;
            for (var r2 = rg.r1; r2 <= rg.r2; r2++) for (var c2 = srcC + 1; c2 <= rg.c2; c2++) {
                var cell2 = m.raw(sheet, r2, srcC), v2 = cell2 ? cell2.v : null;
                if (typeof v2 === 'string' && v2.charAt(0) === '=') v2 = X.shift(v2, 0, c2 - srcC);
                changes.push({ r: r2, c: c2, v: v2, f: cell2 ? cell2.f : null });
            }
        }
        if (changes.length) m.setCells(sheet, changes, dir === 'down' ? 'Fill down' : 'Fill right');
    };

    // ── Find & replace ──────────────────────────────────────────────────
    /** All matches in the sheet(s): [{sheet, r, c}] in reading order. */
    A.findAll = function (query, opts) {
        var model = this.model, out = [];
        if (!query) return out;
        var sheets = opts.allSheets ? model.sheets.filter(function (s) { return !s.hidden; }) : [this.sheet()];
        var q = opts.matchCase ? query : query.toLowerCase();
        sheets.forEach(function (s) {
            var hits = [];
            s.cells.forEach(function (cell, key) {
                if (cell.v === null || cell.v === undefined) return;
                var i = key.indexOf(','), r = +key.slice(0, i), c = +key.slice(i + 1);
                var hay = opts.formulas ? String(cell.v) : model.display(s, r, c);
                if (!opts.matchCase) hay = hay.toLowerCase();
                if (opts.wholeCell ? hay === q : hay.indexOf(q) >= 0) hits.push({ sheet: s, r: r, c: c });
            });
            hits.sort(function (a, b) { return a.r - b.r || a.c - b.c; });
            out = out.concat(hits);
        });
        return out;
    };
    A.replaceIn = function (hits, query, replacement, opts) {
        if (!this.guard()) return 0;
        var model = this.model, bySheet = new Map(), count = 0;
        var flags = opts.matchCase ? 'g' : 'gi';
        var re = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags);
        hits.forEach(function (h) {
            var cell = model.raw(h.sheet, h.r, h.c);
            if (!cell || cell.v === null) return;
            var nv = opts.wholeCell ? replacement : String(cell.v).replace(re, function () { return replacement; });
            if (nv === cell.v) return;
            if (!bySheet.has(h.sheet)) bySheet.set(h.sheet, []);
            bySheet.get(h.sheet).push({ r: h.r, c: h.c, v: nv });
            count++;
        });
        if (!count) return 0;
        model.begin('Replace');
        bySheet.forEach(function (changes, s) { model.setCells(s, changes); });
        model.commit();
        return count;
    };

    // ── Data validation ─────────────────────────────────────────────────
    A.validationFor = function (sheet, r, c) {
        var dv = sheet.props.dv || [];
        for (var i = dv.length - 1; i >= 0; i--) if (CS.inRange(dv[i], r, c)) return dv[i];
        return null;
    };
    A.validate = function (sheet, r, c, raw) {
        var rule = this.validationFor(sheet, r, c);
        if (!rule || raw === '' || raw === null || (typeof raw === 'string' && raw.charAt(0) === '=')) return { ok: true };
        var p = FM.parse(raw), ok = true, msg = rule.msg;
        switch (rule.type) {
            case 'list':
                ok = rule.values.some(function (v) { return v.toLowerCase() === String(raw).trim().toLowerCase(); });
                msg = msg || 'Choose one of: ' + rule.values.join(', ');
                break;
            case 'number':
                ok = p.t === 'n' && (rule.min === null || p.v >= rule.min) && (rule.max === null || p.v <= rule.max);
                msg = msg || 'Enter a number' + rangeText(rule.min, rule.max) + '.';
                break;
            case 'text_length': {
                var len = String(raw).length;
                ok = (rule.min === null || len >= rule.min) && (rule.max === null || len <= rule.max);
                msg = msg || 'Text must be' + rangeText(rule.min, rule.max, ' characters') + '.';
                break;
            }
            case 'text_contains':
                ok = String(raw).toLowerCase().indexOf(String(rule.text).toLowerCase()) >= 0;
                msg = msg || 'Text must contain "' + rule.text + '".';
                break;
            case 'date':
                ok = p.t === 'n' && /date/.test(p.kind || '') && (rule.min === null || p.v >= rule.min) && (rule.max === null || p.v <= rule.max);
                msg = msg || 'Enter a valid date' + (rule.min !== null || rule.max !== null ? ' in the allowed range' : '') + ' (e.g. 2026-10-07).';
                break;
        }
        return ok ? { ok: true } : { ok: false, strict: rule.strict !== false, message: msg };
    };
    function rangeText(min, max, unit) {
        unit = unit || '';
        if (min !== null && max !== null) return ' between ' + min + ' and ' + max + unit;
        if (min !== null) return ' of at least ' + min + unit;
        if (max !== null) return ' of at most ' + max + unit;
        return unit ? ' of any length' : '';
    }
    A.setValidation = function (rule) {
        if (!this.guard()) return;
        var rg = this.grid.activeRange();
        this.model.updateLayout(this.sheet(), rule ? 'Data validation' : 'Remove validation', function (s) {
            var overlaps = function (d) { return !(d.r2 < rg.r1 || d.r1 > rg.r2 || d.c2 < rg.c1 || d.c1 > rg.c2); };
            s.props.dv = (s.props.dv || []).filter(function (d) { return !overlaps(d); });
            if (rule) s.props.dv.push(Object.assign({ r1: rg.r1, c1: rg.c1, r2: rg.r2, c2: rg.c2 }, rule));
        });
    };

    // ── Conditional formatting ──────────────────────────────────────────
    A.setCondFormats = function (list, label) {
        if (!this.guard()) return;
        this.model.updateLayout(this.sheet(), label || 'Conditional formatting', function (s) { s.props.cf = list; });
    };
})();
