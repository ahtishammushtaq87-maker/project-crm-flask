/* Spreadsheet module - the grid: virtualised rendering, selection, editing,
 * keyboard, mouse, clipboard and resizing.
 *
 * Only the visible rows/columns are in the DOM. A tall/wide spacer inside a
 * native scroll container provides real scrollbars (and touch scrolling);
 * a sticky "stage" on top of it is redrawn from the scroll offsets. Frozen
 * rows/columns are separate panes on the stage.
 */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var X = CS.Formula, FM = CS.Format;

    var DEFAULT_W = 100, DEFAULT_H = 23, HEAD_W = 46, HEAD_H = 24, MIN_W = 20, MIN_H = 12;
    var MAX_ROWS = 50000, MAX_COLS = 260;

    function Grid(root, model, opts) {
        this.root = root;
        this.model = model;
        this.opts = opts || {};
        this.sheet = null;
        this.sel = { ranges: [{ r1: 0, c1: 0, r2: 0, c2: 0 }], active: { r: 0, c: 0 } };
        this.edit = null;
        this.clip = null;
        this.findHit = null;
        this.build();
    }
    CS.Grid = Grid;
    var G = Grid.prototype;
    Grid.DEFAULT_W = DEFAULT_W;
    Grid.DEFAULT_H = DEFAULT_H;

    // ── DOM ─────────────────────────────────────────────────────────────
    G.build = function () {
        var root = this.root;
        root.classList.add('crm-sheet-grid');
        root.innerHTML =
            '<div class="crm-sheet-scroller" tabindex="-1">' +
            '  <div class="crm-sheet-inner"><div class="crm-sheet-stage">' +
            '    <div class="crm-sheet-pane" data-pane="main"></div><div class="crm-sheet-pane" data-pane="top"></div>' +
            '    <div class="crm-sheet-pane" data-pane="left"></div><div class="crm-sheet-pane" data-pane="corner"></div>' +
            '    <div class="crm-sheet-colhead" data-head="colmain"></div><div class="crm-sheet-colhead" data-head="colfrozen"></div>' +
            '    <div class="crm-sheet-rowhead" data-head="rowmain"></div><div class="crm-sheet-rowhead" data-head="rowfrozen"></div>' +
            '    <div class="crm-sheet-corner" role="button" title="Select all" aria-label="Select all"></div>' +
            '    <div class="crm-sheet-freeze-v"></div><div class="crm-sheet-freeze-h"></div>' +
            '    <div class="crm-sheet-guide"></div>' +
            '  </div></div>' +
            '</div>' +
            '<textarea class="crm-sheet-focus" aria-label="Spreadsheet grid. Use arrow keys to move between cells." autocomplete="off" spellcheck="false"></textarea>' +
            '<textarea class="crm-sheet-input" aria-label="Cell editor" spellcheck="false" autocomplete="off"></textarea>' +
            '<div class="crm-sheet-ac" role="listbox"></div>' +
            '<div class="crm-sheet-hint"></div>' +
            '<div class="crm-sheet-linkchip"></div>';
        this.scroller = root.querySelector('.crm-sheet-scroller');
        this.inner = root.querySelector('.crm-sheet-inner');
        this.stage = root.querySelector('.crm-sheet-stage');
        this.panes = {};
        var self = this;
        root.querySelectorAll('.crm-sheet-pane').forEach(function (p) { self.panes[p.dataset.pane] = p; });
        this.heads = {};
        root.querySelectorAll('[data-head]').forEach(function (h) { self.heads[h.dataset.head] = h; });
        this.focusEl = root.querySelector('.crm-sheet-focus');
        this.input = root.querySelector('.crm-sheet-input');
        this.acEl = root.querySelector('.crm-sheet-ac');
        this.hintEl = root.querySelector('.crm-sheet-hint');
        this.linkEl = root.querySelector('.crm-sheet-linkchip');
        this.guide = root.querySelector('.crm-sheet-guide');
        this.measureCtx = document.createElement('canvas').getContext('2d');

        this.scroller.addEventListener('scroll', function () { self.requestRender(); });
        window.addEventListener('resize', function () { self.requestRender(); });
        if (window.ResizeObserver) new ResizeObserver(function () { self.requestRender(); }).observe(root);
        this.bindMouse();
        this.bindKeys();
        this.bindClipboard();
        this.bindEditor();
        root.querySelector('.crm-sheet-corner').addEventListener('mousedown', function (e) {
            e.preventDefault();
            self.commitIfEditing();
            self.selectAll();
            self.focus();
        });
    };

    G.focus = function () {
        if (this.edit) { this.input.focus({ preventScroll: true }); return; }
        if (document.activeElement !== this.focusEl) this.focusEl.focus({ preventScroll: true });
    };

    // ── Geometry ────────────────────────────────────────────────────────
    G.setSheet = function (sheet) {
        this.commitIfEditing();
        this.sheet = sheet;
        this.clip = this.clip && this.clip.sheet === sheet ? this.clip : this.clip;
        this.findHit = null;
        var saved = sheet.viewState;
        if (saved) {
            this.sel = saved.sel;
        } else {
            this.sel = { ranges: [{ r1: 0, c1: 0, r2: 0, c2: 0 }], active: { r: 0, c: 0 } };
        }
        this.relayout();
        this.scroller.scrollTop = saved ? saved.top : 0;
        this.scroller.scrollLeft = saved ? saved.left : 0;
        this.render();
        this.emitSelection();
    };
    G.saveViewState = function () {
        if (this.sheet) this.sheet.viewState = { sel: JSON.parse(JSON.stringify(this.sel)), top: this.scroller.scrollTop, left: this.scroller.scrollLeft };
    };

    /** Rebuild the column/row offset tables (after any layout change). */
    G.relayout = function () {
        var s = this.sheet;
        if (!s) return;
        var props = s.props || {};
        var hc = new Set(props.hc || []), hr = new Set(props.hr || []);
        var filt = this.model.filterHidden(s);
        var cols = Math.min(MAX_COLS, s.cols), rows = Math.min(MAX_ROWS, s.rows);
        var cx = new Float64Array(cols + 1), ry = new Float64Array(rows + 1);
        var cw = props.cw || {}, rh = props.rh || {};
        for (var c = 0; c < cols; c++) cx[c + 1] = cx[c] + (hc.has(c) ? 0 : (cw[c] || DEFAULT_W));
        for (var r = 0; r < rows; r++) ry[r + 1] = ry[r] + (hr.has(r) || (filt && filt.has(r)) ? 0 : (rh[r] || DEFAULT_H));
        this.cx = cx; this.ry = ry;
        this.nCols = cols; this.nRows = rows;
        this.hiddenCols = hc; this.hiddenRows = hr; this.filtered = filt;
        this.fr = Math.min(s.frozenRows || 0, rows - 1);
        this.fc = Math.min(s.frozenCols || 0, cols - 1);
        this.FW = cx[this.fc];
        this.FH = ry[this.fr];
        this.mergeIndex = null;
        this.inner.style.width = (HEAD_W + cx[cols] + 60) + 'px';
        this.inner.style.height = (HEAD_H + ry[rows] + 60) + 'px';
    };
    G.colW = function (c) { return this.cx[c + 1] - this.cx[c]; };
    G.rowH = function (r) { return this.ry[r + 1] - this.ry[r]; };
    function search(arr, n, v) {
        // largest i in [0, n) with arr[i] <= v
        var lo = 0, hi = n - 1;
        while (lo < hi) {
            var mid = (lo + hi + 1) >> 1;
            if (arr[mid] <= v) lo = mid; else hi = mid - 1;
        }
        return lo;
    }
    G.colAt = function (x) { return Math.max(0, Math.min(this.nCols - 1, search(this.cx, this.nCols, x))); };
    G.rowAt = function (y) { return Math.max(0, Math.min(this.nRows - 1, search(this.ry, this.nRows, y))); };
    G.isHiddenRow = function (r) { return this.rowH(r) === 0; };
    G.isHiddenCol = function (c) { return this.colW(c) === 0; };

    // ── Merges ──────────────────────────────────────────────────────────
    G.merges = function () { return (this.sheet && this.sheet.props.merges) || []; };
    G.mergeAt = function (r, c) {
        if (!this.mergeIndex) {
            var idx = new Map();
            this.merges().forEach(function (m) {
                for (var rr = m.r1; rr <= m.r2; rr++) for (var cc = m.c1; cc <= m.c2; cc++) idx.set(CS.key(rr, cc), m);
            });
            this.mergeIndex = idx;
        }
        return this.mergeIndex.get(CS.key(r, c)) || null;
    };
    /** Grow a range so it never cuts through a merged cell. */
    G.expandForMerges = function (rg) {
        rg = CS.normRange(rg);
        var ms = this.merges();
        if (!ms.length) return rg;
        var changed = true;
        while (changed) {
            changed = false;
            for (var i = 0; i < ms.length; i++) {
                var m = ms[i];
                if (m.r2 < rg.r1 || m.r1 > rg.r2 || m.c2 < rg.c1 || m.c1 > rg.c2) continue;
                if (m.r1 < rg.r1 || m.r2 > rg.r2 || m.c1 < rg.c1 || m.c2 > rg.c2) {
                    rg = { r1: Math.min(rg.r1, m.r1), c1: Math.min(rg.c1, m.c1), r2: Math.max(rg.r2, m.r2), c2: Math.max(rg.c2, m.c2) };
                    changed = true;
                }
            }
        }
        return rg;
    };

    // ── Rendering ───────────────────────────────────────────────────────
    G.requestRender = function () {
        var self = this;
        if (this.raf) return;
        this.raf = requestAnimationFrame(function () { self.raf = null; self.render(); });
    };

    G.viewport = function () {
        var w = this.scroller.clientWidth, h = this.scroller.clientHeight;
        return { w: w, h: h, sl: this.scroller.scrollLeft, st: this.scroller.scrollTop };
    };

    G.render = function () {
        if (!this.sheet) return;
        var vp = this.viewport();
        this.stage.style.width = vp.w + 'px';
        this.stage.style.height = vp.h + 'px';
        var FW = this.FW, FH = this.FH;
        var mainW = Math.max(0, vp.w - HEAD_W - FW), mainH = Math.max(0, vp.h - HEAD_H - FH);
        var ox = this.cx[this.fc] + vp.sl, oy = this.ry[this.fr] + vp.st;

        var colsScroll = this.visibleSpan(this.cx, this.nCols, this.fc, ox, mainW);
        var rowsScroll = this.visibleSpan(this.ry, this.nRows, this.fr, oy, mainH);
        var colsFrozen = this.fc ? [0, this.fc - 1] : null;
        var rowsFrozen = this.fr ? [0, this.fr - 1] : null;

        this.layoutPane('main', HEAD_W + FW, HEAD_H + FH, mainW, mainH);
        this.layoutPane('top', HEAD_W + FW, HEAD_H, mainW, FH);
        this.layoutPane('left', HEAD_W, HEAD_H + FH, FW, mainH);
        this.layoutPane('corner', HEAD_W, HEAD_H, FW, FH);

        this.renderPane('main', rowsScroll, colsScroll, ox, oy);
        this.renderPane('top', rowsFrozen, colsScroll, ox, 0);
        this.renderPane('left', rowsScroll, colsFrozen, 0, oy);
        this.renderPane('corner', rowsFrozen, colsFrozen, 0, 0);

        this.renderColHead('colmain', colsScroll, ox, HEAD_W + FW, mainW);
        this.renderColHead('colfrozen', colsFrozen, 0, HEAD_W, FW);
        this.renderRowHead('rowmain', rowsScroll, oy, HEAD_H + FH, mainH);
        this.renderRowHead('rowfrozen', rowsFrozen, 0, HEAD_H, FH);

        var fv = this.root.querySelector('.crm-sheet-freeze-v'), fh = this.root.querySelector('.crm-sheet-freeze-h');
        fv.style.display = this.fc ? '' : 'none';
        fv.style.left = (HEAD_W + FW - 1) + 'px';
        fh.style.display = this.fr ? '' : 'none';
        fh.style.top = (HEAD_H + FH - 1) + 'px';

        this.view = { ox: ox, oy: oy, mainW: mainW, mainH: mainH, vp: vp };
        if (this.edit) this.positionEditor();
        this.updateLinkChip();
    };

    G.visibleSpan = function (arr, n, start, origin, size) {
        if (start >= n || size <= 0) return null;
        var first = Math.max(start, search(arr, n, origin));
        var last = Math.min(n - 1, search(arr, n, origin + size));
        return [first, last];
    };

    G.layoutPane = function (name, left, top, w, h) {
        var p = this.panes[name];
        p.style.left = left + 'px'; p.style.top = top + 'px';
        p.style.width = Math.max(0, w) + 'px'; p.style.height = Math.max(0, h) + 'px';
        p.style.display = w > 0 && h > 0 ? '' : 'none';
    };

    function cfMatches(model, sheet, rule, v, text, dupCache) {
        var n = v.t === 'n' ? v.v : null, a = FM.parse(rule.v1), b = FM.parse(rule.v2);
        var low = text.toLowerCase();
        switch (rule.type) {
            case 'gt': return n !== null && a.t === 'n' && n > a.v;
            case 'gte': return n !== null && a.t === 'n' && n >= a.v;
            case 'lt': return n !== null && a.t === 'n' && n < a.v;
            case 'lte': return n !== null && a.t === 'n' && n <= a.v;
            case 'eq': return a.t === 'n' && n !== null ? n === a.v : (text !== '' && low === String(rule.v1).toLowerCase());
            case 'neq': return a.t === 'n' && n !== null ? n !== a.v : low !== String(rule.v1).toLowerCase();
            case 'between': return n !== null && a.t === 'n' && b.t === 'n' && n >= Math.min(a.v, b.v) && n <= Math.max(a.v, b.v);
            case 'contains': return rule.v1 !== '' && low.indexOf(String(rule.v1).toLowerCase()) >= 0;
            case 'not_contains': return low.indexOf(String(rule.v1).toLowerCase()) < 0;
            case 'empty': return text === '';
            case 'not_empty': return text !== '';
            case 'duplicate': {
                if (text === '') return false;
                if (!dupCache.has(rule)) {
                    var counts = new Map();
                    var last = Math.min(rule.r2, model.used(sheet).rows - 1);
                    for (var r = rule.r1; r <= last; r++) for (var c = rule.c1; c <= rule.c2; c++) {
                        var t = model.display(sheet, r, c).toLowerCase();
                        if (t !== '') counts.set(t, (counts.get(t) || 0) + 1);
                    }
                    dupCache.set(rule, counts);
                }
                return (dupCache.get(rule).get(low) || 0) > 1;
            }
        }
        return false;
    }

    G.cfStyle = function (r, c, v, text, dupCache) {
        var rules = this.sheet.props.cf || [];
        for (var i = 0; i < rules.length; i++) {
            var rule = rules[i];
            if (r < rule.r1 || r > rule.r2 || c < rule.c1 || c > rule.c2) continue;
            if (cfMatches(this.model, this.sheet, rule, v, text, dupCache)) return rule.style || {};
        }
        return null;
    };
    G.listRule = function (r, c) {
        var dv = this.sheet.props.dv || [];
        for (var i = dv.length - 1; i >= 0; i--) {
            var d = dv[i];
            if (d.type === 'list' && r >= d.r1 && r <= d.r2 && c >= d.c1 && c <= d.c2) return d;
        }
        return null;
    };

    G.renderPane = function (name, rowSpan, colSpan, ox, oy) {
        var pane = this.panes[name];
        if (!rowSpan || !colSpan || pane.style.display === 'none') { pane.innerHTML = ''; return; }
        var model = this.model, sheet = this.sheet, self = this;
        var r0 = rowSpan[0], r1 = rowSpan[1], c0 = colSpan[0], c1 = colSpan[1];
        var html = [];
        var cx = this.cx, ry = this.ry;
        var paneW = parseFloat(pane.style.width), paneH = parseFloat(pane.style.height);
        // Grid lines
        for (var r = r0; r <= r1 + 1 && r <= this.nRows; r++) {
            var y = ry[r] - oy - 1;
            if (y >= -1 && y <= paneH) html.push('<div class="crm-sheet-hl" style="top:' + y + 'px"></div>');
        }
        for (var c = c0; c <= c1 + 1 && c <= this.nCols; c++) {
            var x = cx[c] - ox - 1;
            if (x >= -1 && x <= paneW) html.push('<div class="crm-sheet-vl" style="left:' + x + 'px"></div>');
        }
        var covered = new Set();
        var drawn = new Set();
        var dupCache = new Map();
        var filter = sheet.props.filter;
        var canEdit = this.model.can.edit;
        // Merged cells that reach into this pane are drawn from their anchor.
        this.merges().forEach(function (m) {
            if (m.r2 < r0 || m.r1 > r1 || m.c2 < c0 || m.c1 > c1) return;
            for (var rr = m.r1; rr <= m.r2; rr++) for (var cc = m.c1; cc <= m.c2; cc++) if (rr !== m.r1 || cc !== m.c1) covered.add(CS.key(rr, cc));
            html.push(self.cellHtml(m.r1, m.c1, ox, oy, m, dupCache, filter, canEdit, null));
            drawn.add(CS.key(m.r1, m.c1));
        });
        for (r = r0; r <= r1; r++) {
            if (ry[r + 1] === ry[r]) continue;
            for (c = c0; c <= c1; c++) {
                if (cx[c + 1] === cx[c]) continue;
                var k = CS.key(r, c);
                if (covered.has(k) || drawn.has(k)) continue;
                var cell = sheet.cells.get(k);
                var isActive = r === this.sel.active.r && c === this.sel.active.c;
                var needs = cell || (filter && r === filter.r1 && c >= filter.c1 && c <= filter.c2) || (isActive && canEdit && this.listRule(r, c)) || (sheet.props.cf && sheet.props.cf.length);
                if (!needs) continue;
                html.push(this.cellHtml(r, c, ox, oy, null, dupCache, filter, canEdit, c1));
            }
        }
        html.push(this.selectionHtml(r0, r1, c0, c1, ox, oy));
        if (name === 'main' && r1 >= this.nRows - 1 && canEdit && this.sheet.rows < MAX_ROWS) {
            html.push('<div class="crm-sheet-addrows" style="top:' + (ry[this.nRows] - oy + 8) + 'px;left:' + (8) + 'px">' +
                '<button type="button" class="btn btn-sm btn-outline-secondary" data-action="add-rows">Add 1000 more rows at the bottom</button></div>');
        }
        pane.innerHTML = html.join('');
    };

    G.cellHtml = function (r, c, ox, oy, merge, dupCache, filter, canEdit, lastCol) {
        var model = this.model, sheet = this.sheet;
        var cell = sheet.cells.get(CS.key(r, c));
        var f = cell && cell.f ? cell.f : {};
        var v = model.value(sheet, r, c);
        var text = FM.display(v, f.nf);
        var x = this.cx[c] - ox, y = this.ry[r] - oy;
        var w = merge ? this.cx[merge.c2 + 1] - this.cx[merge.c1] : this.colW(c);
        var h = merge ? this.ry[merge.r2 + 1] - this.ry[merge.r1] : this.rowH(r);
        var cf = text !== '' || (sheet.props.cf || []).length ? this.cfStyle(r, c, v, text, dupCache) : null;
        var style = FM.css(f);
        if (cf) {
            if (cf.bg) style += 'background-color:' + cf.bg + ';';
            if (cf.c) style += 'color:' + cf.c + ';';
            if (cf.b) style += 'font-weight:700;';
        }
        var cls = 'crm-sheet-cell';
        var ha = f.ha || (v.t === 'n' ? 'right' : v.t === 'b' || v.t === 'e' ? 'center' : 'left');
        var wrap = f.wrap || 'overflow';
        if (v.t === 'e') cls += ' crm-sheet-err';
        if (wrap === 'wrap') cls += ' crm-sheet-wrap';
        if (merge || f.bg || (cf && cf.bg)) cls += ' crm-sheet-filled';
        // Text overflows into empty cells to the right (like Google Sheets).
        if (!merge && wrap === 'overflow' && ha === 'left' && v.t === 's' && text && lastCol !== null) {
            var tw = this.textWidth(text, f);
            var cc = c + 1, span = w;
            while (span < tw + 6 && cc <= Math.min(this.nCols - 1, c + 20)) {
                var nk = CS.key(r, cc);
                var ncell = sheet.cells.get(nk);
                if ((ncell && ncell.v !== null && ncell.v !== '') || this.mergeAt(r, cc)) break;
                span += this.colW(cc);
                cc++;
            }
            if (span > w) { w = span; cls += ' crm-sheet-spill'; }
        }
        var va = f.va === 'top' ? 'flex-start' : f.va === 'middle' ? 'center' : 'flex-end';
        var inner = CS.esc(text);
        var link = v.link || (v.t === 's' ? CS.safeUrl(text) : null);
        if (link) {
            inner = '<span class="crm-sheet-link" data-href="' + CS.esc(link) + '">' + inner + '</span>';
            cls += ' crm-sheet-haslink';
        }
        var extra = '';
        if (filter && r === filter.r1 && c >= filter.c1 && c <= filter.c2) {
            var active = filter.crit && filter.crit[c];
            extra += '<button type="button" class="crm-sheet-filterbtn' + (active ? ' crm-sheet-on' : '') + '" data-filter-col="' + c + '" aria-label="Filter column ' + CS.colName(c) + '"><i class="fas fa-' + (active ? 'filter' : 'caret-down') + '"></i></button>';
        } else if (canEdit && (text !== '' || (r === this.sel.active.r && c === this.sel.active.c)) && this.listRule(r, c)) {
            extra += '<button type="button" class="crm-sheet-dvbtn" data-dv-r="' + r + '" data-dv-c="' + c + '" aria-label="Choose a value"><i class="fas fa-caret-down"></i></button>';
        }
        var borders = FM.borderCss(f);
        if (borders) extra += '<div class="crm-sheet-bd" style="' + borders + '"></div>';
        return '<div class="' + cls + '" style="left:' + x + 'px;top:' + y + 'px;width:' + w + 'px;height:' + h + 'px;' + style + '">' +
            '<div class="crm-sheet-cv" style="justify-content:' + (ha === 'right' ? 'flex-end' : ha === 'center' ? 'center' : 'flex-start') + ';align-items:' + va + ';text-align:' + ha + '">' + inner + '</div>' + extra + '</div>';
    };

    G.textWidth = function (text, f) {
        var size = f && f.fs ? f.fs * 4 / 3 : 13;
        this.measureCtx.font = (f && f.b ? 'bold ' : '') + (f && f.i ? 'italic ' : '') + size + 'px ' + (f && f.ff ? '"' + f.ff + '"' : 'Arial, sans-serif');
        return this.measureCtx.measureText(text).width;
    };

    G.rectFor = function (rg, ox, oy) {
        return { x: this.cx[rg.c1] - ox, y: this.ry[rg.r1] - oy, w: this.cx[rg.c2 + 1] - this.cx[rg.c1], h: this.ry[rg.r2 + 1] - this.ry[rg.r1] };
    };
    G.selectionHtml = function (r0, r1, c0, c1, ox, oy) {
        var out = [], self = this;
        var visible = function (rg) { return !(rg.r2 < r0 || rg.r1 > r1 || rg.c2 < c0 || rg.c1 > c1); };
        var box = function (rg, cls) {
            var rc = self.rectFor(rg, ox, oy);
            return '<div class="' + cls + '" style="left:' + (rc.x - 1) + 'px;top:' + (rc.y - 1) + 'px;width:' + (rc.w + 1) + 'px;height:' + (rc.h + 1) + 'px"></div>';
        };
        if (this.clip && this.clip.sheet === this.sheet && visible(this.clip.range)) out.push(box(this.clip.range, 'crm-sheet-clipbox'));
        if (this.findHit && this.findHit.sheet === this.sheet && visible(this.findHit.range)) out.push(box(this.findHit.range, 'crm-sheet-findbox'));
        if (this.refInsert && this.refInsert.range && visible(this.refInsert.range)) out.push(box(this.refInsert.range, 'crm-sheet-refbox'));
        var ranges = this.sel.ranges;
        for (var i = 0; i < ranges.length; i++) {
            var rg = ranges[i];
            if (!visible(rg)) continue;
            if (rg.r1 !== rg.r2 || rg.c1 !== rg.c2 || ranges.length > 1) {
                var m = this.mergeAt(rg.r1, rg.c1);
                if (!(m && m.r1 === rg.r1 && m.c1 === rg.c1 && m.r2 === rg.r2 && m.c2 === rg.c2 && ranges.length === 1)) out.push(box(rg, 'crm-sheet-selbox'));
            }
        }
        var a = this.sel.active;
        var am = this.mergeAt(a.r, a.c) || { r1: a.r, c1: a.c, r2: a.r, c2: a.c };
        if (visible(am)) out.push(box(am, 'crm-sheet-activebox'));
        return out.join('');
    };

    G.selectedCols = function () {
        var set = new Set();
        this.sel.ranges.forEach(function (rg) { for (var c = rg.c1; c <= rg.c2; c++) set.add(c); });
        return set;
    };
    G.selectedRows = function () {
        var set = new Set();
        this.sel.ranges.forEach(function (rg) { for (var r = rg.r1; r <= Math.min(rg.r2, rg.r1 + 5000); r++) set.add(r); });
        return set;
    };
    G.fullCols = function () {
        var self = this, set = new Set();
        this.sel.ranges.forEach(function (rg) { if (rg.r1 === 0 && rg.r2 >= self.nRows - 1) for (var c = rg.c1; c <= rg.c2; c++) set.add(c); });
        return set;
    };
    G.fullRows = function () {
        var self = this, set = new Set();
        this.sel.ranges.forEach(function (rg) { if (rg.c1 === 0 && rg.c2 >= self.nCols - 1) for (var r = rg.r1; r <= rg.r2; r++) set.add(r); });
        return set;
    };

    G.renderColHead = function (name, span, ox, left, width) {
        var el = this.heads[name];
        el.style.left = left + 'px'; el.style.width = Math.max(0, width) + 'px'; el.style.height = HEAD_H + 'px';
        if (!span || width <= 0) { el.innerHTML = ''; el.style.display = 'none'; return; }
        el.style.display = '';
        var sel = this.selectedCols(), full = this.fullCols(), html = [];
        var filter = this.sheet.props.filter;
        for (var c = span[0]; c <= span[1]; c++) {
            var w = this.colW(c), x = this.cx[c] - ox;
            if (c > 0 && this.hiddenCols.has(c - 1)) {
                html.push('<button type="button" class="crm-sheet-unhide crm-sheet-unhide-col" style="left:' + (x - 6) + 'px" data-unhide-col="' + c + '" title="Show hidden columns" aria-label="Show hidden columns">&#8596;</button>');
            }
            if (!w) continue;
            var cls = 'crm-sheet-hcell' + (full.has(c) ? ' crm-sheet-hfull' : sel.has(c) ? ' crm-sheet-hsel' : '') + (filter && c >= filter.c1 && c <= filter.c2 && filter.crit && filter.crit[c] ? ' crm-sheet-hfilter' : '');
            html.push('<div class="' + cls + '" style="left:' + x + 'px;width:' + w + 'px">' + CS.colName(c) + '</div>');
        }
        el.innerHTML = html.join('');
    };
    G.renderRowHead = function (name, span, oy, top, height) {
        var el = this.heads[name];
        el.style.top = top + 'px'; el.style.height = Math.max(0, height) + 'px'; el.style.width = HEAD_W + 'px';
        if (!span || height <= 0) { el.innerHTML = ''; el.style.display = 'none'; return; }
        el.style.display = '';
        var sel = this.selectedRows(), full = this.fullRows(), html = [];
        for (var r = span[0]; r <= span[1]; r++) {
            var h = this.rowH(r), y = this.ry[r] - oy;
            if (r > 0 && this.hiddenRows.has(r - 1)) {
                html.push('<button type="button" class="crm-sheet-unhide crm-sheet-unhide-row" style="top:' + (y - 6) + 'px" data-unhide-row="' + r + '" title="Show hidden rows" aria-label="Show hidden rows">&#8597;</button>');
            }
            if (!h) continue;
            var cls = 'crm-sheet-hcell' + (full.has(r) ? ' crm-sheet-hfull' : sel.has(r) ? ' crm-sheet-hsel' : '');
            html.push('<div class="' + cls + '" style="top:' + y + 'px;height:' + h + 'px;line-height:' + h + 'px">' + (r + 1) + '</div>');
        }
        el.innerHTML = html.join('');
    };

    // ── Hit testing ─────────────────────────────────────────────────────
    G.hit = function (clientX, clientY) {
        var rect = this.stage.getBoundingClientRect();
        var x = clientX - rect.left, y = clientY - rect.top;
        var vp = this.view ? this.view.vp : this.viewport();
        var res = { x: x, y: y };
        var colFromX = function (self) {
            var gx = x - HEAD_W;
            return gx < self.FW ? self.colAt(gx) : self.colAt(self.cx[self.fc] + vp.sl + (gx - self.FW));
        };
        var rowFromY = function (self) {
            var gy = y - HEAD_H;
            return gy < self.FH ? self.rowAt(gy) : self.rowAt(self.ry[self.fr] + vp.st + (gy - self.FH));
        };
        var colScreenRight = function (self, c) {
            return HEAD_W + (c < self.fc ? self.cx[c + 1] : self.FW + self.cx[c + 1] - self.cx[self.fc] - vp.sl);
        };
        var rowScreenBottom = function (self, r) {
            return HEAD_H + (r < self.fr ? self.ry[r + 1] : self.FH + self.ry[r + 1] - self.ry[self.fr] - vp.st);
        };
        if (x < HEAD_W && y < HEAD_H) { res.area = 'corner'; return res; }
        if (y < HEAD_H) {
            res.area = 'colhead';
            res.c = colFromX(this);
            var right = colScreenRight(this, res.c);
            if (right - x <= 4) res.edge = res.c;
            else if (x - (right - this.colW(res.c)) <= 3 && res.c > 0) { res.edge = this.prevVisibleCol(res.c); }
            return res;
        }
        if (x < HEAD_W) {
            res.area = 'rowhead';
            res.r = rowFromY(this);
            var bottom = rowScreenBottom(this, res.r);
            if (bottom - y <= 3) res.edge = res.r;
            else if (y - (bottom - this.rowH(res.r)) <= 2 && res.r > 0) res.edge = this.prevVisibleRow(res.r);
            return res;
        }
        res.area = 'cell';
        res.r = rowFromY(this);
        res.c = colFromX(this);
        return res;
    };
    G.prevVisibleCol = function (c) { c--; while (c > 0 && this.isHiddenCol(c)) c--; return Math.max(0, c); };
    G.prevVisibleRow = function (r) { r--; while (r > 0 && this.isHiddenRow(r)) r--; return Math.max(0, r); };

    // ── Selection ───────────────────────────────────────────────────────
    G.activeRange = function () { return this.sel.ranges[this.sel.ranges.length - 1]; };
    G.selectedRanges = function () { return this.sel.ranges.slice(); };
    G.select = function (rg, active, add) {
        rg = this.expandForMerges(rg);
        if (add) this.sel.ranges.push(rg); else this.sel.ranges = [rg];
        this.sel.active = active || { r: rg.r1, c: rg.c1 };
        // The moving end of a Shift+Arrow extension is the far corner.
        this.sel.focusCell = { r: this.sel.active.r === rg.r1 ? rg.r2 : rg.r1, c: this.sel.active.c === rg.c1 ? rg.c2 : rg.c1 };
        this.requestRender();
        this.emitSelection();
    };
    G.selectCell = function (r, c, opts) {
        opts = opts || {};
        r = Math.max(0, Math.min(this.nRows - 1, r));
        c = Math.max(0, Math.min(this.nCols - 1, c));
        if (opts.extend) {
            var a = this.sel.active;
            var rg = this.expandForMerges({ r1: a.r, c1: a.c, r2: r, c2: c });
            this.sel.ranges[this.sel.ranges.length - 1] = rg;
            this.sel.focusCell = { r: r, c: c };
        } else {
            var m = this.mergeAt(r, c);
            if (m) { r = m.r1; c = m.c1; }
            var cell = m ? { r1: m.r1, c1: m.c1, r2: m.r2, c2: m.c2 } : { r1: r, c1: c, r2: r, c2: c };
            if (opts.add) this.sel.ranges.push(cell); else this.sel.ranges = [cell];
            this.sel.active = { r: r, c: c };
            this.sel.focusCell = { r: r, c: c };
        }
        if (opts.scroll !== false) this.scrollIntoView(opts.extend ? r : this.sel.active.r, opts.extend ? c : this.sel.active.c);
        this.requestRender();
        this.emitSelection();
    };
    G.selectAll = function () {
        this.sel.ranges = [{ r1: 0, c1: 0, r2: this.nRows - 1, c2: this.nCols - 1 }];
        this.sel.focusCell = { r: this.nRows - 1, c: this.nCols - 1 };
        this.requestRender();
        this.emitSelection();
    };
    G.selectCols = function (c1, c2, add) {
        var rg = { r1: 0, c1: Math.min(c1, c2), r2: this.nRows - 1, c2: Math.max(c1, c2) };
        if (add) this.sel.ranges.push(rg); else this.sel.ranges = [rg];
        if (!add || this.sel.ranges.length === 1) this.sel.active = { r: this.firstVisibleRow(this.viewTopRow()), c: c1 };
        this.sel.focusCell = { r: this.sel.active.r, c: c2 };
        this.requestRender();
        this.emitSelection();
    };
    G.selectRows = function (r1, r2, add) {
        var rg = { r1: Math.min(r1, r2), c1: 0, r2: Math.max(r1, r2), c2: this.nCols - 1 };
        if (add) this.sel.ranges.push(rg); else this.sel.ranges = [rg];
        if (!add || this.sel.ranges.length === 1) this.sel.active = { r: r1, c: this.firstVisibleCol(0) };
        this.sel.focusCell = { r: r2, c: this.sel.active.c };
        this.requestRender();
        this.emitSelection();
    };
    G.viewTopRow = function () { return this.rowAt(this.ry[this.fr] + this.scroller.scrollTop); };
    G.firstVisibleRow = function (r) { while (r < this.nRows - 1 && this.isHiddenRow(r)) r++; return r; };
    G.firstVisibleCol = function (c) { while (c < this.nCols - 1 && this.isHiddenCol(c)) c++; return c; };
    G.emitSelection = function () { if (this.opts.onSelect) this.opts.onSelect(this); };

    G.scrollIntoView = function (r, c) {
        var vp = this.viewport();
        var mainW = vp.w - HEAD_W - this.FW, mainH = vp.h - HEAD_H - this.FH;
        if (c >= this.fc) {
            var left = this.cx[c] - this.cx[this.fc], right = this.cx[c + 1] - this.cx[this.fc];
            if (left < vp.sl) this.scroller.scrollLeft = left;
            else if (right > vp.sl + mainW) this.scroller.scrollLeft = Math.max(0, right - mainW + 2);
        }
        if (r >= this.fr) {
            var top = this.ry[r] - this.ry[this.fr], bottom = this.ry[r + 1] - this.ry[this.fr];
            if (top < vp.st) this.scroller.scrollTop = top;
            else if (bottom > vp.st + mainH) this.scroller.scrollTop = Math.max(0, bottom - mainH + 2);
        }
    };

    // Moves skip hidden rows/columns and step over merged cells.
    G.step = function (r, c, dr, dc) {
        var m = this.mergeAt(r, c);
        if (m) {
            if (dr > 0) r = m.r2; if (dr < 0) r = m.r1;
            if (dc > 0) c = m.c2; if (dc < 0) c = m.c1;
        }
        var nr = r + dr, nc = c + dc;
        while (nr > 0 && nr < this.nRows - 1 && this.isHiddenRow(nr)) nr += dr || 0;
        while (nc > 0 && nc < this.nCols - 1 && this.isHiddenCol(nc)) nc += dc || 0;
        nr = Math.max(0, Math.min(this.nRows - 1, nr));
        nc = Math.max(0, Math.min(this.nCols - 1, nc));
        if (this.isHiddenRow(nr)) nr = r;
        if (this.isHiddenCol(nc)) nc = c;
        return { r: nr, c: nc };
    };
    G.hasValue = function (r, c) {
        var cell = this.sheet.cells.get(CS.key(r, c));
        return !!(cell && cell.v !== null && cell.v !== '');
    };
    /** Ctrl+Arrow: jump to the edge of the current block of data. */
    G.jump = function (r, c, dr, dc) {
        var limitR = this.nRows - 1, limitC = this.nCols - 1;
        var nxt = function (rr, cc) { return { r: Math.max(0, Math.min(limitR, rr + dr)), c: Math.max(0, Math.min(limitC, cc + dc)) }; };
        var n = nxt(r, c);
        if (n.r === r && n.c === c) return n;
        if (this.hasValue(r, c) && this.hasValue(n.r, n.c)) {
            while (true) {
                var m = nxt(n.r, n.c);
                if ((m.r === n.r && m.c === n.c) || !this.hasValue(m.r, m.c)) return n;
                n = m;
            }
        }
        while (!this.hasValue(n.r, n.c)) {
            var m2 = nxt(n.r, n.c);
            if (m2.r === n.r && m2.c === n.c) return n;
            n = m2;
        }
        return n;
    };

    // ── Mouse ───────────────────────────────────────────────────────────
    G.bindMouse = function () {
        var self = this;
        var stage = this.stage;
        var drag = null;

        stage.addEventListener('mousemove', function (e) {
            if (drag) return;
            var h = self.hit(e.clientX, e.clientY);
            stage.style.cursor = (h.area === 'colhead' && h.edge !== undefined && self.model.can.edit) ? 'col-resize'
                : (h.area === 'rowhead' && h.edge !== undefined && self.model.can.edit) ? 'row-resize' : '';
        });

        stage.addEventListener('mousedown', function (e) {
            if (e.button !== 0 && e.button !== 2) return;
            var t = e.target;
            if (t.closest('[data-action="add-rows"]')) { e.preventDefault(); if (self.opts.onAddRows) self.opts.onAddRows(); return; }
            var unc = t.closest('[data-unhide-col]'), unr = t.closest('[data-unhide-row]');
            if ((unc || unr) && e.button === 0) {
                e.preventDefault();
                if (self.opts.onUnhide) self.opts.onUnhide(unc ? 'col' : 'row', +(unc ? unc.dataset.unhideCol : unr.dataset.unhideRow));
                return;
            }
            var fb = t.closest('[data-filter-col]');
            if (fb && e.button === 0) { e.preventDefault(); if (self.opts.onFilterButton) self.opts.onFilterButton(+fb.dataset.filterCol, fb); return; }
            var dvb = t.closest('[data-dv-r]');
            if (dvb && e.button === 0) {
                e.preventDefault();
                self.commitIfEditing();
                self.selectCell(+dvb.dataset.dvR, +dvb.dataset.dvC);
                self.openListPicker(dvb);
                return;
            }
            var h = self.hit(e.clientX, e.clientY);
            if (e.button === 2) {
                // Right-click inside the selection keeps it.
                if (h.area === 'cell' && !self.sel.ranges.some(function (rg) { return CS.inRange(rg, h.r, h.c); })) { self.commitIfEditing(); self.selectCell(h.r, h.c, { scroll: false }); }
                if (h.area === 'colhead' && !self.fullCols().has(h.c)) { self.commitIfEditing(); self.selectCols(h.c, h.c); }
                if (h.area === 'rowhead' && !self.fullRows().has(h.r)) { self.commitIfEditing(); self.selectRows(h.r, h.r); }
                return;
            }
            // Clicking a cell while typing a formula inserts its reference.
            if (h.area === 'cell' && self.edit && self.canInsertRef()) {
                e.preventDefault();
                self.beginRefInsert(h.r, h.c);
                drag = { kind: 'ref', r: h.r, c: h.c };
                return;
            }
            if (h.area === 'colhead' && h.edge !== undefined && self.model.can.edit) {
                e.preventDefault();
                drag = { kind: 'colsize', c: h.edge, start: e.clientX, w: self.colW(h.edge) };
                self.showGuide('v', e.clientX);
                return;
            }
            if (h.area === 'rowhead' && h.edge !== undefined && self.model.can.edit) {
                e.preventDefault();
                drag = { kind: 'rowsize', r: h.edge, start: e.clientY, h: self.rowH(h.edge) };
                self.showGuide('h', e.clientY);
                return;
            }
            e.preventDefault();
            self.commitIfEditing();
            var add = CS.mod(e) && !e.shiftKey;
            if (h.area === 'colhead') {
                if (e.shiftKey) self.selectCols(self.sel.active.c, h.c); else self.selectCols(h.c, h.c, add);
                drag = { kind: 'cols', c: h.c };
            } else if (h.area === 'rowhead') {
                if (e.shiftKey) self.selectRows(self.sel.active.r, h.r); else self.selectRows(h.r, h.r, add);
                drag = { kind: 'rows', r: h.r };
            } else if (h.area === 'cell') {
                var link = t.closest('.crm-sheet-link');
                if (link && CS.mod(e)) { window.open(link.dataset.href, '_blank', 'noopener,noreferrer'); return; }
                if (e.shiftKey) self.selectCell(h.r, h.c, { extend: true, scroll: false });
                else self.selectCell(h.r, h.c, { add: add, scroll: false });
                drag = { kind: 'cells' };
            }
            self.focus();
        });

        stage.addEventListener('dblclick', function (e) {
            var h = self.hit(e.clientX, e.clientY);
            if (h.area === 'colhead' && h.edge !== undefined && self.model.can.edit) { self.autofitCols(self.fullCols().has(h.edge) ? Array.from(self.fullCols()) : [h.edge]); return; }
            if (h.area === 'rowhead' && h.edge !== undefined && self.model.can.edit) { self.autofitRows(self.fullRows().has(h.edge) ? Array.from(self.fullRows()) : [h.edge]); return; }
            if (h.area === 'cell' && !e.target.closest('button')) self.startEdit(null, 'edit');
        });

        stage.addEventListener('contextmenu', function (e) {
            e.preventDefault();
            var h = self.hit(e.clientX, e.clientY);
            if (self.opts.onContextMenu) self.opts.onContextMenu(h, e.clientX, e.clientY);
        });

        var autoScroll = null;
        document.addEventListener('mousemove', function (e) {
            if (!drag) return;
            if (drag.kind === 'colsize') { self.showGuide('v', Math.max(e.clientX, drag.start - drag.w + MIN_W)); return; }
            if (drag.kind === 'rowsize') { self.showGuide('h', Math.max(e.clientY, drag.start - drag.h + MIN_H)); return; }
            var rect = self.stage.getBoundingClientRect();
            var h = self.hit(Math.max(rect.left + HEAD_W + 1, Math.min(rect.right - 2, e.clientX)), Math.max(rect.top + HEAD_H + 1, Math.min(rect.bottom - 2, e.clientY)));
            if (drag.kind === 'cells' && h.r !== undefined && h.c !== undefined) self.selectCell(h.r, h.c, { extend: true, scroll: false });
            else if (drag.kind === 'cols' && h.c !== undefined) self.selectCols(self.sel.active.c, h.c);
            else if (drag.kind === 'rows' && h.r !== undefined) self.selectRows(self.sel.active.r, h.r);
            else if (drag.kind === 'ref' && h.r !== undefined) self.updateRefInsert(drag.r, drag.c, h.r, h.c);
            // Auto-scroll while dragging past the edge.
            var dx = e.clientX > rect.right - 20 ? 20 : e.clientX < rect.left + HEAD_W + self.FW ? -20 : 0;
            var dy = e.clientY > rect.bottom - 20 ? 20 : e.clientY < rect.top + HEAD_H + self.FH ? -20 : 0;
            clearInterval(autoScroll);
            if ((dx || dy) && drag.kind !== 'colsize') {
                autoScroll = setInterval(function () { self.scroller.scrollLeft += dx; self.scroller.scrollTop += dy; }, 40);
            }
        });
        document.addEventListener('mouseup', function (e) {
            clearInterval(autoScroll);
            if (!drag) return;
            var d = drag;
            drag = null;
            self.hideGuide();
            if (d.kind === 'colsize') {
                var w = Math.max(MIN_W, Math.round(d.w + e.clientX - d.start));
                var cols = self.fullCols().has(d.c) ? Array.from(self.fullCols()) : [d.c];
                if (self.opts.onResize) self.opts.onResize('col', cols, w);
            } else if (d.kind === 'rowsize') {
                var hgt = Math.max(MIN_H, Math.round(d.h + e.clientY - d.start));
                var rows = self.fullRows().has(d.r) ? Array.from(self.fullRows()) : [d.r];
                if (self.opts.onResize) self.opts.onResize('row', rows, hgt);
            } else if (d.kind === 'ref') {
                self.input.focus();
            }
        });
    };

    G.showGuide = function (dir, pos) {
        var rect = this.stage.getBoundingClientRect();
        this.guide.style.display = 'block';
        if (dir === 'v') {
            this.guide.className = 'crm-sheet-guide crm-sheet-guide-v';
            this.guide.style.left = (pos - rect.left) + 'px'; this.guide.style.top = '0';
        } else {
            this.guide.className = 'crm-sheet-guide crm-sheet-guide-h';
            this.guide.style.top = (pos - rect.top) + 'px'; this.guide.style.left = '0';
        }
    };
    G.hideGuide = function () { this.guide.style.display = 'none'; };

    G.cellFont = function (f) { return f || {}; };
    G.autofitCols = function (cols) {
        var self = this, sheet = this.sheet, widths = {};
        var used = this.model.used(sheet).rows;
        cols.forEach(function (c) {
            var max = 0;
            for (var r = 0; r < Math.min(used, 3000); r++) {
                var cell = sheet.cells.get(CS.key(r, c));
                if (!cell) continue;
                var text = self.model.display(sheet, r, c);
                if (!text) continue;
                var w = self.textWidth(text, cell.f);
                if (w > max) max = w;
            }
            widths[c] = Math.max(MIN_W, Math.min(1000, Math.ceil(max + 14)));
            if (!max) widths[c] = DEFAULT_W;
        });
        if (this.opts.onAutofit) this.opts.onAutofit('col', widths);
    };
    G.autofitRows = function (rows) {
        var sheet = this.sheet, heights = {};
        rows.forEach(function (r) {
            var maxFs = 10, lines = 1;
            sheet.cells.forEach(function (cell, key) {
                if (+key.slice(0, key.indexOf(',')) !== r) return;
                if (cell.f && cell.f.fs) maxFs = Math.max(maxFs, cell.f.fs);
                if (cell.f && cell.f.wrap === 'wrap' && typeof cell.v === 'string') lines = Math.max(lines, cell.v.split('\n').length);
            });
            heights[r] = Math.max(DEFAULT_H, Math.round(maxFs * 4 / 3 * 1.45 * lines + 4));
        });
        if (this.opts.onAutofit) this.opts.onAutofit('row', heights);
    };

    // ── Keyboard ────────────────────────────────────────────────────────
    G.bindKeys = function () {
        var self = this;
        this.focusEl.addEventListener('keydown', function (e) { self.onKey(e); });
        // Typing directly into a selected cell starts editing with that text.
        this.focusEl.addEventListener('input', function () {
            var v = self.focusEl.value;
            self.focusEl.value = '';
            if (v && self.model.can.edit && !self.edit) self.startEdit(v, 'enter');
        });
    };
    G.onKey = function (e) {
        if (this.edit) return;
        if (this.opts.onKey && this.opts.onKey(e) === true) { e.preventDefault(); return; }
        var mod = CS.mod(e), a = this.sel.active, f = this.sel.focusCell || a, p;
        var move = function (self, dr, dc) {
            if (e.shiftKey) {
                p = mod ? self.jump(f.r, f.c, dr, dc) : self.step(f.r, f.c, dr, dc);
                self.selectCell(p.r, p.c, { extend: true });
            } else {
                p = mod ? self.jump(a.r, a.c, dr, dc) : self.step(a.r, a.c, dr, dc);
                self.selectCell(p.r, p.c);
            }
        };
        switch (e.key) {
            case 'ArrowUp': e.preventDefault(); move(this, -1, 0); return;
            case 'ArrowDown':
                if (e.altKey && this.listRule(a.r, a.c)) { e.preventDefault(); this.openListPicker(); return; }
                e.preventDefault(); move(this, 1, 0); return;
            case 'ArrowLeft': e.preventDefault(); move(this, 0, -1); return;
            case 'ArrowRight': e.preventDefault(); move(this, 0, 1); return;
            case 'Tab': e.preventDefault(); this.moveWithin(e.shiftKey ? 0 : 0, e.shiftKey ? -1 : 1); return;
            case 'Enter':
                e.preventDefault();
                if (e.shiftKey) { this.moveWithin(-1, 0); return; }
                if (this.sel.ranges.length === 1 && (this.activeRange().r1 !== this.activeRange().r2 || this.activeRange().c1 !== this.activeRange().c2) && !this.mergeAt(a.r, a.c)) { this.moveWithin(1, 0); return; }
                this.startEdit(null, 'edit');
                return;
            case 'F2': e.preventDefault(); this.startEdit(null, 'edit'); return;
            case 'Delete': case 'Backspace': e.preventDefault(); if (this.opts.onClear) this.opts.onClear(); return;
            case 'Escape': if (this.clip) { this.clip = null; this.requestRender(); } return;
            case 'Home':
                e.preventDefault();
                if (mod) this.selectCell(0, 0); else this.selectCell(a.r, this.firstVisibleCol(0), { extend: e.shiftKey });
                return;
            case 'End': {
                e.preventDefault();
                var used = this.model.used(this.sheet);
                if (mod) this.selectCell(Math.max(0, used.rows - 1), Math.max(0, used.cols - 1), { extend: e.shiftKey });
                else this.selectCell(a.r, Math.max(0, used.cols - 1), { extend: e.shiftKey });
                return;
            }
            case 'PageDown': case 'PageUp': {
                e.preventDefault();
                var rows = Math.max(1, Math.floor((this.viewport().h - HEAD_H - this.FH) / DEFAULT_H) - 1);
                var dir = e.key === 'PageDown' ? 1 : -1;
                var tr = Math.max(0, Math.min(this.nRows - 1, (e.shiftKey ? f.r : a.r) + dir * rows));
                this.selectCell(tr, e.shiftKey ? f.c : a.c, { extend: e.shiftKey });
                return;
            }
        }
        if (mod && (e.key === 'a' || e.key === 'A')) { e.preventDefault(); this.selectAll(); return; }
        if (mod && e.key === ' ') { e.preventDefault(); this.selectCols(a.c, a.c); return; }
        if (e.shiftKey && e.key === ' ' && !mod) { e.preventDefault(); this.selectRows(a.r, a.r); return; }
    };
    /** Enter/Tab move inside a multi-cell selection (wrapping), else one cell. */
    G.moveWithin = function (dr, dc) {
        var rg = this.activeRange(), a = this.sel.active;
        var single = this.sel.ranges.length === 1 && rg.r1 === rg.r2 && rg.c1 === rg.c2;
        var merge = this.mergeAt(a.r, a.c);
        if (single || (merge && merge.r1 === rg.r1 && merge.c1 === rg.c1 && merge.r2 === rg.r2 && merge.c2 === rg.c2)) {
            var p = this.step(a.r, a.c, dr, dc);
            this.selectCell(p.r, p.c);
            return;
        }
        var r = a.r + dr, c = a.c + dc;
        if (c > rg.c2) { c = rg.c1; r++; } if (c < rg.c1) { c = rg.c2; r--; }
        if (r > rg.r2) { r = rg.r1; if (dr) c = c + 1 > rg.c2 ? rg.c1 : c + 1; }
        if (r < rg.r1) { r = rg.r2; if (dr) c = c - 1 < rg.c1 ? rg.c2 : c - 1; }
        this.sel.active = { r: r, c: c };
        this.scrollIntoView(r, c);
        this.requestRender();
        this.emitSelection();
    };

    // ── Editing ─────────────────────────────────────────────────────────
    G.isEditing = function () { return !!this.edit; };
    /**
     * mode: 'enter' (started by typing - arrow keys commit and move) or
     * 'edit' (F2/double-click/Enter - arrow keys move the caret).
     */
    G.startEdit = function (text, mode, opts) {
        if (!this.model.can.edit) {
            if (this.opts.onReadOnly) this.opts.onReadOnly();
            return false;
        }
        var a = this.sel.active;
        var cell = this.model.raw(this.sheet, a.r, a.c);
        var raw = cell && cell.v !== null ? String(cell.v) : '';
        // A date/time typed as a number shows in a familiar form for editing.
        if (cell && cell.f && cell.f.nf && /^(date|datetime|time)$/.test(cell.f.nf.t) && raw && raw.charAt(0) !== '=') {
            var pv = FM.parse(raw);
            if (pv.t === 'n' && !pv.kind) raw = FM.display(pv, cell.f.nf);
        }
        this.edit = { r: a.r, c: a.c, mode: mode || 'edit', original: raw, sheet: this.sheet };
        this.scrollIntoView(a.r, a.c);
        this.render();
        var input = this.input;
        input.value = text !== null && text !== undefined ? text : raw;
        input.style.display = 'block';
        var f = cell && cell.f ? cell.f : {};
        input.style.font = (f.i ? 'italic ' : '') + (f.b ? 'bold ' : '') + (f.fs ? f.fs + 'pt ' : '13px ') + (f.ff ? '"' + f.ff + '"' : 'Arial, sans-serif');
        input.style.color = f.c || '';
        input.style.background = f.bg || '#fff';
        input.style.textAlign = f.ha || 'left';
        this.positionEditor();
        input.focus({ preventScroll: true });
        var len = input.value.length;
        input.setSelectionRange(len, len);
        this.updateAutocomplete();
        if (this.opts.onEditChange) this.opts.onEditChange(input.value);
        return true;
    };
    G.positionEditor = function () {
        if (!this.edit || this.edit.sheet !== this.sheet) return;
        var r = this.edit.r, c = this.edit.c;
        var m = this.mergeAt(r, c) || { r1: r, c1: c, r2: r, c2: c };
        var vp = this.view ? this.view.vp : this.viewport();
        var x = HEAD_W + (c < this.fc ? this.cx[c] : this.FW + this.cx[c] - this.cx[this.fc] - vp.sl);
        var y = HEAD_H + (r < this.fr ? this.ry[r] : this.FH + this.ry[r] - this.ry[this.fr] - vp.st);
        var w = this.cx[m.c2 + 1] - this.cx[m.c1], h = this.ry[m.r2 + 1] - this.ry[m.r1];
        var input = this.input;
        input.style.left = (x - 1) + 'px';
        input.style.top = (y - 1) + 'px';
        input.style.minWidth = (w + 2) + 'px';
        input.style.minHeight = (h + 2) + 'px';
        input.style.height = 'auto';
        input.style.width = 'auto';
        var lines = input.value.split('\n');
        var longest = 0, self = this;
        lines.forEach(function (l) { longest = Math.max(longest, self.textWidth(l + 'W', null)); });
        input.style.width = Math.min(vp.w - x - 8, Math.max(w + 2, longest + 12)) + 'px';
        input.style.height = Math.max(h + 2, input.scrollHeight) + 'px';
        this.positionAutocomplete();
    };
    G.commitIfEditing = function () { if (this.edit) this.commitEdit(0, 0); };
    G.commitEdit = function (dr, dc) {
        if (!this.edit) return true;
        var ed = this.edit, value = this.input.value;
        if (this.opts.validate) {
            var res = this.opts.validate(ed.sheet, ed.r, ed.c, value);
            if (res && !res.ok) {
                if (res.strict) {
                    if (this.opts.onInvalid) this.opts.onInvalid(res.message);
                    this.input.focus();
                    return false;
                }
                if (this.opts.onInvalid) this.opts.onInvalid(res.message, true);
            }
        }
        this.closeEditor();
        if (value !== ed.original && this.opts.onCommit) this.opts.onCommit(ed.sheet, ed.r, ed.c, value);
        if (dr || dc) this.moveWithin(dr, dc);
        this.focus();
        this.requestRender();
        return true;
    };
    G.cancelEdit = function () {
        if (!this.edit) return;
        this.closeEditor();
        this.focus();
        this.requestRender();
        if (this.opts.onEditChange) this.opts.onEditChange(null);
    };
    G.closeEditor = function () {
        this.edit = null;
        this.refInsert = null;
        this.input.style.display = 'none';
        this.hideAutocomplete();
    };
    /** Typing in the formula bar edits the active cell too. */
    G.editFromBar = function (value) {
        if (!this.edit) { if (!this.startEdit(value, 'edit')) return; }
        this.input.value = value;
        this.positionEditor();
        this.updateAutocomplete();
    };

    G.bindEditor = function () {
        var self = this, input = this.input;
        input.addEventListener('input', function () {
            self.refInsert = null;
            self.positionEditor();
            self.updateAutocomplete();
            if (self.opts.onEditChange) self.opts.onEditChange(input.value);
        });
        input.addEventListener('keydown', function (e) {
            if (self.acOpen() && self.acKey(e)) return;
            var mod = CS.mod(e);
            if (e.key === 'Enter' && (e.altKey || mod)) {
                e.preventDefault();
                var s = input.selectionStart, en = input.selectionEnd;
                input.value = input.value.slice(0, s) + '\n' + input.value.slice(en);
                input.setSelectionRange(s + 1, s + 1);
                self.positionEditor();
                return;
            }
            if (e.key === 'Enter') { e.preventDefault(); self.commitEdit(e.shiftKey ? -1 : 1, 0); return; }
            if (e.key === 'Tab') { e.preventDefault(); self.commitEdit(0, e.shiftKey ? -1 : 1); return; }
            if (e.key === 'Escape') { e.preventDefault(); self.cancelEdit(); return; }
            if (e.key === 'F2') { e.preventDefault(); self.edit.mode = self.edit.mode === 'edit' ? 'enter' : 'edit'; return; }
            if (self.edit && self.edit.mode === 'enter' && /^Arrow/.test(e.key) && !e.shiftKey) {
                if (self.canInsertRef()) {
                    // Arrow keys pick a reference while typing a formula.
                    e.preventDefault();
                    var base = self.refInsert ? self.refInsert.cell : { r: self.edit.r, c: self.edit.c };
                    var d = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
                    var p = self.step(base.r, base.c, d[0], d[1]);
                    self.beginRefInsert(p.r, p.c, true);
                    return;
                }
                e.preventDefault();
                var dd = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
                self.commitEdit(dd[0], dd[1]);
                return;
            }
            e.stopPropagation();
        });
        input.addEventListener('blur', function () {
            // Clicking a toolbar button keeps the edit; clicking elsewhere commits.
            setTimeout(function () {
                if (!self.edit) return;
                var ae = document.activeElement;
                if (ae === input || (ae && ae.closest && ae.closest('.crm-sheet-formulabar, .crm-sheet-ac'))) return;
                if (ae && ae.closest && ae.closest('.crm-sheet-modal, .crm-sheet-menu')) return;
                self.commitEdit(0, 0);
            }, 0);
        });
    };

    // Formula reference insertion (click a cell / arrow keys while typing "=")
    G.canInsertRef = function () {
        if (!this.edit || this.edit.sheet !== this.sheet) return false;
        var v = this.input.value;
        if (v.charAt(0) !== '=') return false;
        if (this.refInsert) return true;
        var before = v.slice(0, this.input.selectionStart).replace(/\s+$/, '');
        return /[=(,+\-*/^&<>:;]$/.test(before);
    };
    G.beginRefInsert = function (r, c, keyboard) {
        var input = this.input;
        var start = this.refInsert ? this.refInsert.start : input.selectionStart;
        var end = this.refInsert ? this.refInsert.end : input.selectionEnd;
        var text = CS.addr(r, c);
        input.value = input.value.slice(0, start) + text + input.value.slice(end);
        this.refInsert = { start: start, end: start + text.length, cell: { r: r, c: c }, range: { r1: r, c1: c, r2: r, c2: c } };
        input.setSelectionRange(start + text.length, start + text.length);
        if (keyboard) this.scrollIntoView(r, c);
        this.positionEditor();
        this.requestRender();
        if (this.opts.onEditChange) this.opts.onEditChange(input.value);
    };
    G.updateRefInsert = function (r1, c1, r2, c2) {
        if (!this.refInsert) return;
        var rg = CS.normRange({ r1: r1, c1: c1, r2: r2, c2: c2 });
        var text = CS.rangeStr(rg);
        var input = this.input, s = this.refInsert.start;
        input.value = input.value.slice(0, s) + text + input.value.slice(this.refInsert.end);
        this.refInsert.end = s + text.length;
        this.refInsert.range = rg;
        this.refInsert.cell = { r: r2, c: c2 };
        input.setSelectionRange(this.refInsert.end, this.refInsert.end);
        this.requestRender();
        if (this.opts.onEditChange) this.opts.onEditChange(input.value);
    };

    // Function autocomplete - common functions are suggested first.
    var POPULAR = ['SUM', 'AVERAGE', 'COUNT', 'COUNTA', 'IF', 'MIN', 'MAX', 'ROUND', 'VLOOKUP', 'SUMIF', 'COUNTIF', 'IFERROR', 'CONCAT', 'TODAY', 'AND', 'OR'];
    function popularity(name) { var i = POPULAR.indexOf(name); return i < 0 ? 100 : i; }
    G.acOpen = function () { return this.acEl.style.display === 'block'; };
    G.hideAutocomplete = function () { this.acEl.style.display = 'none'; this.hintEl.style.display = 'none'; this.acItems = null; };
    G.updateAutocomplete = function (inputEl) {
        var input = inputEl || this.input;
        var v = input.value, pos = input.selectionStart;
        if (v.charAt(0) !== '=') { this.hideAutocomplete(); return; }
        var before = v.slice(0, pos);
        var m = /(^|[^A-Za-z0-9_."$])([A-Za-z][A-Za-z0-9.]*)$/.exec(before);
        var inString = (before.match(/"/g) || []).length % 2 === 1;
        this.acItems = null;
        if (m && !inString && !/^[A-Za-z]{1,3}\d+$/.test(m[2])) {
            var prefix = m[2].toUpperCase();
            var items = X.functions().filter(function (f) { return f.name.indexOf(prefix) === 0; })
                .sort(function (a, b) { return popularity(a.name) - popularity(b.name) || (a.name < b.name ? -1 : 1); }).slice(0, 8);
            if (items.length && !(items.length === 1 && items[0].name === prefix && before.charAt(before.length) === '(')) {
                this.acItems = items;
                this.acIndex = 0;
                this.acPrefix = prefix;
                this.acInput = input;
                this.acEl.innerHTML = items.map(function (f, i) {
                    return '<div class="crm-sheet-ac-item' + (i === 0 ? ' crm-sheet-on' : '') + '" role="option" data-i="' + i + '"><b>' + CS.esc(f.name) + '</b><span>' + CS.esc(f.desc) + '</span></div>';
                }).join('');
                this.acEl.style.display = 'block';
                var self = this;
                this.acEl.querySelectorAll('.crm-sheet-ac-item').forEach(function (el) {
                    el.addEventListener('mousedown', function (e) { e.preventDefault(); self.acIndex = +el.dataset.i; self.acAccept(); });
                });
            } else {
                this.acEl.style.display = 'none';
            }
        } else {
            this.acEl.style.display = 'none';
        }
        // Signature hint for the function the caret is inside.
        var depth = 0, fn = null;
        for (var i = before.length - 1; i >= 0; i--) {
            var ch = before.charAt(i);
            if (ch === ')') depth++;
            else if (ch === '(') {
                if (depth === 0) { var nm = /([A-Za-z][A-Za-z0-9.]*)$/.exec(before.slice(0, i)); fn = nm ? nm[1].toUpperCase() : null; break; }
                depth--;
            }
        }
        var info = fn ? X.fn(fn) : null;
        if (info && !this.acOpen()) {
            this.hintEl.innerHTML = '<code>' + CS.esc(info.syntax) + '</code><div>' + CS.esc(info.desc) + '</div>';
            this.hintEl.style.display = 'block';
        } else {
            this.hintEl.style.display = 'none';
        }
        this.positionAutocomplete();
    };
    G.positionAutocomplete = function () {
        var input = this.acInput && this.acInput !== this.input && document.activeElement === this.acInput ? this.acInput : this.input;
        if (input.style.display === 'none' && input === this.input) return;
        var rootRect = this.root.getBoundingClientRect(), r = input.getBoundingClientRect();
        var top = r.bottom - rootRect.top + 2, left = Math.max(0, r.left - rootRect.left);
        [this.acEl, this.hintEl].forEach(function (el) { el.style.left = left + 'px'; el.style.top = top + 'px'; });
        if (this.acOpen()) this.hintEl.style.top = (top + this.acEl.offsetHeight + 4) + 'px';
    };
    G.acKey = function (e) {
        if (!this.acItems) return false;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            this.acIndex = (this.acIndex + (e.key === 'ArrowDown' ? 1 : -1) + this.acItems.length) % this.acItems.length;
            var idx = this.acIndex;
            this.acEl.querySelectorAll('.crm-sheet-ac-item').forEach(function (el, i) { el.classList.toggle('crm-sheet-on', i === idx); });
            return true;
        }
        if (e.key === 'Tab' || e.key === 'Enter') { e.preventDefault(); this.acAccept(); return true; }
        if (e.key === 'Escape') { e.preventDefault(); this.acEl.style.display = 'none'; this.acItems = null; return true; }
        return false;
    };
    G.acAccept = function () {
        var item = this.acItems && this.acItems[this.acIndex];
        if (!item) return;
        var input = this.acInput || this.input;
        var pos = input.selectionStart, v = input.value;
        var start = pos - this.acPrefix.length;
        var after = v.slice(pos);
        var insert = item.name + (after.charAt(0) === '(' ? '' : '(');
        input.value = v.slice(0, start) + insert + after;
        var np = start + insert.length;
        input.setSelectionRange(np, np);
        input.focus();
        this.acEl.style.display = 'none';
        this.acItems = null;
        if (input === this.input) { this.positionEditor(); if (this.opts.onEditChange) this.opts.onEditChange(input.value); }
        else input.dispatchEvent(new Event('input'));
        this.updateAutocomplete(input);
    };

    // Data validation dropdown
    G.openListPicker = function (anchorEl) {
        var a = this.sel.active, rule = this.listRule(a.r, a.c), self = this;
        if (!rule || !this.model.can.edit) return;
        var current = this.model.display(this.sheet, a.r, a.c);
        var items = rule.values.map(function (v) {
            return { label: v, checked: v === current, action: function () { if (self.opts.onCommit) self.opts.onCommit(self.sheet, a.r, a.c, v); self.focus(); } };
        });
        items.push({ divider: true }, { label: 'Clear', icon: 'fas fa-eraser', action: function () { if (self.opts.onCommit) self.opts.onCommit(self.sheet, a.r, a.c, ''); self.focus(); } });
        var anchor = anchorEl || this.panes.main.querySelector('.crm-sheet-activebox');
        if (anchor) CS.menu(items, 0, 0, anchor);
    };

    // Link chip for the active cell
    G.updateLinkChip = function () {
        var el = this.linkEl;
        if (this.edit || !this.sheet) { el.style.display = 'none'; return; }
        var a = this.sel.active, v = this.model.value(this.sheet, a.r, a.c);
        var link = v.link || (v.t === 's' ? CS.safeUrl(v.v) : null);
        if (!link) { el.style.display = 'none'; return; }
        var vp = this.view.vp;
        if (a.r >= this.fr && (this.ry[a.r] - this.ry[this.fr] < vp.st)) { el.style.display = 'none'; return; }
        var x = HEAD_W + (a.c < this.fc ? this.cx[a.c] : this.FW + this.cx[a.c] - this.cx[this.fc] - vp.sl);
        var y = HEAD_H + (a.r < this.fr ? this.ry[a.r + 1] : this.FH + this.ry[a.r + 1] - this.ry[this.fr] - vp.st);
        el.innerHTML = '<i class="fas fa-link"></i> <a href="' + CS.esc(link) + '" target="_blank" rel="noopener noreferrer">' + CS.esc(link.length > 60 ? link.slice(0, 57) + '…' : link) + '</a>';
        el.style.left = Math.max(HEAD_W, x) + 'px';
        el.style.top = (y + 2) + 'px';
        el.style.display = 'block';
    };

    // ── Clipboard ───────────────────────────────────────────────────────
    G.bindClipboard = function () {
        var self = this;
        this.focusEl.addEventListener('copy', function (e) { self.onCopy(e, false); });
        this.focusEl.addEventListener('cut', function (e) { self.onCopy(e, true); });
        this.focusEl.addEventListener('paste', function (e) { self.onPaste(e); });
    };
    function tsvEscape(s) { return /[\t\n"]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }
    G.onCopy = function (e, cut) {
        if (this.edit) return;
        e.preventDefault();
        if (this.sel.ranges.length > 1) { if (this.opts.onInvalid) this.opts.onInvalid('Copying multiple separate ranges is not supported - select one range.', true); return; }
        if (cut && !this.model.can.edit) { if (this.opts.onReadOnly) this.opts.onReadOnly(); return; }
        var rg = this.activeRange();
        var used = this.model.used(this.sheet);
        var r2 = Math.min(rg.r2, Math.max(rg.r1, used.rows - 1)), c2 = Math.min(rg.c2, Math.max(rg.c1, used.cols - 1));
        var lines = [], cells = [], html = ['<table>'];
        for (var r = rg.r1; r <= r2; r++) {
            var line = [], rowCells = [];
            html.push('<tr>');
            for (var c = rg.c1; c <= c2; c++) {
                var raw = this.model.raw(this.sheet, r, c);
                var text = this.model.display(this.sheet, r, c);
                line.push(tsvEscape(text));
                rowCells.push(raw ? { v: raw.v, f: raw.f } : null);
                html.push('<td style="' + CS.esc(FM.css(raw && raw.f)) + '">' + CS.esc(text) + '</td>');
            }
            html.push('</tr>');
            lines.push(line.join('\t'));
            cells.push(rowCells);
        }
        html.push('</table>');
        var plain = lines.join('\n');
        e.clipboardData.setData('text/plain', plain);
        e.clipboardData.setData('text/html', html.join(''));
        this.clip = { sheet: this.sheet, range: { r1: rg.r1, c1: rg.c1, r2: r2, c2: c2 }, cells: cells, text: plain, cut: cut };
        this.requestRender();
    };
    function parseTsv(text) {
        var rows = [], row = [], field = '', i = 0, q = false;
        text = text.replace(/\r\n?/g, '\n');
        if (text.charAt(text.length - 1) === '\n') text = text.slice(0, -1);
        while (i < text.length) {
            var ch = text.charAt(i);
            if (q) {
                if (ch === '"') { if (text.charAt(i + 1) === '"') { field += '"'; i += 2; continue; } q = false; i++; continue; }
                field += ch; i++; continue;
            }
            if (ch === '"' && field === '') { q = true; i++; continue; }
            if (ch === '\t') { row.push(field); field = ''; i++; continue; }
            if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; i++; continue; }
            field += ch; i++;
        }
        row.push(field);
        rows.push(row);
        return rows;
    }
    G.onPaste = function (e) {
        if (this.edit) return;
        e.preventDefault();
        if (!this.model.can.edit) { if (this.opts.onReadOnly) this.opts.onReadOnly(); return; }
        var text = e.clipboardData.getData('text/plain');
        var mode = this.pasteMode || 'all';
        this.pasteMode = null;
        if (this.opts.onPaste) this.opts.onPaste(text, mode, this.clip && this.clip.text === text ? this.clip : null, parseTsv);
    };
    Grid.parseTsv = parseTsv;
})();
