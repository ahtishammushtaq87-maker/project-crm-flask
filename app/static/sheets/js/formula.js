/* Spreadsheet module - formula engine.
 *
 * A small tokenizer + recursive-descent parser + evaluator. Formulas are
 * never passed to eval()/Function(); only the operators and functions
 * defined below exist, so a formula can't run arbitrary code.
 *
 * Values are the same typed objects as CrmSheet.Format.parse returns:
 *   {t:'n', v, kind?} {t:'s', v} {t:'b', v} {t:'e', v:'#DIV/0!'} {t:'empty'}
 */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var FM = CS.Format;
    var X = CS.Formula = {};

    var ERR = {
        div0: '#DIV/0!', value: '#VALUE!', ref: '#REF!', name: '#NAME?', num: '#NUM!', na: '#N/A',
        cycle: '#CYCLE!', loading: '#LOADING', parse: '#ERROR!',
    };
    X.ERR = ERR;
    function E(code, msg) { return { t: 'e', v: code, msg: msg }; }
    function N(v, kind) { return isFinite(v) ? (kind ? { t: 'n', v: v, kind: kind } : { t: 'n', v: v }) : E(ERR.num); }
    function S(v) { return { t: 's', v: String(v) }; }
    function B(v) { return { t: 'b', v: !!v }; }
    var EMPTY = { t: 'empty' };
    X.E = E;

    // ── Tokenizer ───────────────────────────────────────────────────────
    var SHEET_PREFIX = /^('(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!/;
    var CELL = /^(\$?)([A-Za-z]{1,3})(\$?)(\d+)/;
    var COLRANGE = /^(\$?)([A-Za-z]{1,3}):(\$?)([A-Za-z]{1,3})(?![A-Za-z0-9_(])/;
    var ROWRANGE = /^(\$?)(\d+):(\$?)(\d+)(?![\d.A-Za-z])/;
    var NUMBER = /^(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/;
    var NAME = /^[A-Za-z_][A-Za-z0-9_.]*/;
    var ERRLIT = /^#(?:N\/A|REF!|DIV\/0!|VALUE!|NAME\?|NUM!|NULL!|ERROR!)/i;

    function unquoteSheet(s) {
        return s.charAt(0) === "'" ? s.slice(1, -1).replace(/''/g, "'") : s;
    }
    X.quoteSheet = function (name) {
        return /^[A-Za-z_][A-Za-z0-9_]*$/.test(name) && !CELL.test(name) ? name : "'" + name.replace(/'/g, "''") + "'";
    };

    function partFromCell(m) {
        return { absC: !!m[1], c: CS.colIndex(m[2]), absR: !!m[3], r: parseInt(m[4], 10) - 1 };
    }

    /** Tokens with source positions; refs carry parsed coordinates. */
    X.tokenize = function (src) {
        var toks = [], i = 0, m, rest;
        while (i < src.length) {
            var ch = src.charAt(i);
            if (/\s/.test(ch)) { i++; continue; }
            rest = src.slice(i);
            var start = i;
            if (ch === '"') {
                var j = i + 1, out = '';
                while (j < src.length) {
                    if (src.charAt(j) === '"') {
                        if (src.charAt(j + 1) === '"') { out += '"'; j += 2; continue; }
                        break;
                    }
                    out += src.charAt(j++);
                }
                if (j >= src.length) throw new Error('Missing closing quote');
                toks.push({ type: 'str', value: out, start: start, end: j + 1 });
                i = j + 1;
                continue;
            }
            if ((m = ERRLIT.exec(rest))) { toks.push({ type: 'err', value: m[0].toUpperCase(), start: start, end: i + m[0].length }); i += m[0].length; continue; }
            // Optional sheet prefix followed by a reference.
            var sheet = null, prefixLen = 0, pm = SHEET_PREFIX.exec(rest);
            if (pm) { sheet = unquoteSheet(pm[1]); prefixLen = pm[0].length; rest = rest.slice(prefixLen); }
            var ref = null;
            if ((m = COLRANGE.exec(rest))) {
                ref = { kind: 'range', a: { absC: !!m[1], c: CS.colIndex(m[2]), absR: false, r: null }, b: { absC: !!m[3], c: CS.colIndex(m[4]), absR: false, r: null }, len: m[0].length };
            } else if ((m = ROWRANGE.exec(rest)) && (sheet || !NUMBER.test(rest) || /^\$?\d+:\$?\d+/.test(rest))) {
                ref = { kind: 'range', a: { absR: !!m[1], r: parseInt(m[2], 10) - 1, absC: false, c: null }, b: { absR: !!m[3], r: parseInt(m[4], 10) - 1, absC: false, c: null }, len: m[0].length };
            } else if ((m = CELL.exec(rest)) && !/^[A-Za-z0-9_(.]/.test(rest.slice(m[0].length))) {
                var a = partFromCell(m), len = m[0].length, m2;
                if (rest.charAt(len) === ':' && (m2 = CELL.exec(rest.slice(len + 1))) && !/^[A-Za-z0-9_(.]/.test(rest.slice(len + 1 + m2[0].length))) {
                    ref = { kind: 'range', a: a, b: partFromCell(m2), len: len + 1 + m2[0].length };
                } else {
                    ref = { kind: 'cell', a: a, len: len };
                }
            }
            if (ref) {
                toks.push({ type: 'ref', ref: ref, sheet: sheet, start: start, end: i + prefixLen + ref.len });
                i += prefixLen + ref.len;
                continue;
            }
            if (sheet) throw new Error('Invalid reference');
            if ((m = NUMBER.exec(rest))) { toks.push({ type: 'num', value: parseFloat(m[0]), start: start, end: i + m[0].length }); i += m[0].length; continue; }
            if ((m = NAME.exec(rest))) {
                var up = m[0].toUpperCase();
                if ((up === 'TRUE' || up === 'FALSE') && rest.charAt(m[0].length) !== '(') toks.push({ type: 'bool', value: up === 'TRUE', start: start, end: i + m[0].length });
                else toks.push({ type: 'name', value: up, start: start, end: i + m[0].length });
                i += m[0].length;
                continue;
            }
            var two = src.substr(i, 2);
            if (two === '<=' || two === '>=' || two === '<>') { toks.push({ type: 'op', value: two, start: start, end: i + 2 }); i += 2; continue; }
            if ('+-*/^&=<>%'.indexOf(ch) >= 0) { toks.push({ type: 'op', value: ch, start: start, end: i + 1 }); i++; continue; }
            if (ch === '(') { toks.push({ type: 'lp', start: start, end: i + 1 }); i++; continue; }
            if (ch === ')') { toks.push({ type: 'rp', start: start, end: i + 1 }); i++; continue; }
            if (ch === ',' || ch === ';') { toks.push({ type: 'comma', start: start, end: i + 1 }); i++; continue; }
            throw new Error('Unexpected "' + ch + '"');
        }
        return toks;
    };

    // ── Parser ──────────────────────────────────────────────────────────
    X.parse = function (src) {
        var toks = X.tokenize(src), p = 0;
        function peek() { return toks[p]; }
        function take() { return toks[p++]; }
        function isOp(t, ops) { return t && t.type === 'op' && ops.indexOf(t.value) >= 0; }

        function comparison() {
            var left = concat();
            while (isOp(peek(), ['=', '<>', '<', '>', '<=', '>='])) {
                var op = take().value;
                left = { k: 'bin', op: op, a: left, b: concat() };
            }
            return left;
        }
        function concat() {
            var left = additive();
            while (isOp(peek(), ['&'])) { take(); left = { k: 'bin', op: '&', a: left, b: additive() }; }
            return left;
        }
        function additive() {
            var left = multiplicative();
            while (isOp(peek(), ['+', '-'])) { var op = take().value; left = { k: 'bin', op: op, a: left, b: multiplicative() }; }
            return left;
        }
        function multiplicative() {
            var left = power();
            while (isOp(peek(), ['*', '/'])) { var op = take().value; left = { k: 'bin', op: op, a: left, b: power() }; }
            return left;
        }
        function power() {
            var left = unary();
            while (isOp(peek(), ['^'])) { take(); left = { k: 'bin', op: '^', a: left, b: unary() }; }
            return left;
        }
        function unary() {
            if (isOp(peek(), ['-', '+'])) { var op = take().value; return { k: 'un', op: op, a: unary() }; }
            return postfix();
        }
        function postfix() {
            var node = primary();
            while (isOp(peek(), ['%'])) { take(); node = { k: 'pct', a: node }; }
            return node;
        }
        function primary() {
            var t = take();
            if (!t) throw new Error('Formula is incomplete');
            switch (t.type) {
                case 'num': return { k: 'num', v: t.value };
                case 'str': return { k: 'str', v: t.value };
                case 'bool': return { k: 'bool', v: t.value };
                case 'err': return { k: 'err', v: t.value };
                case 'ref': return { k: t.ref.kind, sheet: t.sheet, a: t.ref.a, b: t.ref.b };
                case 'lp': {
                    var inner = comparison();
                    if (!peek() || peek().type !== 'rp') throw new Error('Missing )');
                    take();
                    return inner;
                }
                case 'name': {
                    if (!peek() || peek().type !== 'lp') throw new Error('Unknown name ' + t.value);
                    take();
                    var args = [];
                    if (peek() && peek().type === 'rp') { take(); return { k: 'fn', name: t.value, args: args }; }
                    while (true) {
                        if (peek() && (peek().type === 'comma' || peek().type === 'rp')) args.push({ k: 'blank' });
                        else args.push(comparison());
                        var nx = take();
                        if (!nx) throw new Error('Missing )');
                        if (nx.type === 'rp') break;
                        if (nx.type !== 'comma') throw new Error('Expected , or )');
                    }
                    return { k: 'fn', name: t.value, args: args };
                }
                default: throw new Error('Unexpected ' + (t.value || t.type));
            }
        }
        if (!toks.length) throw new Error('Formula is empty');
        var ast = comparison();
        if (p < toks.length) throw new Error('Unexpected ' + (toks[p].value || toks[p].type));
        return ast;
    };

    var parseCache = new Map();
    X.compile = function (src) {
        var hit = parseCache.get(src);
        if (hit) return hit;
        var res;
        try { res = { ast: X.parse(src) }; } catch (e) { res = { error: e.message }; }
        if (parseCache.size > 20000) parseCache.clear();
        parseCache.set(src, res);
        return res;
    };

    // ── Coercion helpers ────────────────────────────────────────────────
    function isErr(v) { return v && v.t === 'e'; }
    function toNum(v) {
        if (!v || v.t === 'empty') return N(0);
        if (v.t === 'n') return v;
        if (v.t === 'b') return N(v.v ? 1 : 0);
        if (v.t === 'e') return v;
        var p = FM.parse(v.v);
        return p.t === 'n' ? p : (v.v.trim() === '' ? N(0) : E(ERR.value, '"' + v.v + '" is not a number'));
    }
    function toStr(v) {
        if (!v || v.t === 'empty') return '';
        if (v.t === 's') return v.v;
        if (v.t === 'b') return v.v ? 'TRUE' : 'FALSE';
        if (v.t === 'n') return v.kind ? FM.display(v, null) : FM.display({ t: 'n', v: v.v }, null);
        return v.v;
    }
    function toBool(v) {
        if (!v || v.t === 'empty') return B(false);
        if (v.t === 'b') return v;
        if (v.t === 'n') return B(v.v !== 0);
        if (v.t === 'e') return v;
        var u = v.v.trim().toUpperCase();
        if (u === 'TRUE' || u === 'FALSE') return B(u === 'TRUE');
        return E(ERR.value, '"' + v.v + '" is not TRUE/FALSE');
    }
    X.toStr = toStr;

    function compare(a, b) {
        // Excel ordering: numbers < text < booleans; text case-insensitive.
        function rank(v) { return v.t === 'n' || v.t === 'empty' ? 0 : v.t === 's' ? 1 : 2; }
        if (a.t === 'empty' && b.t === 's') a = S('');
        if (b.t === 'empty' && a.t === 's') b = S('');
        var ra = rank(a), rb = rank(b);
        if (ra !== rb) return ra - rb;
        if (ra === 0) { var x = a.t === 'empty' ? 0 : a.v, y = b.t === 'empty' ? 0 : b.v; return x < y ? -1 : x > y ? 1 : 0; }
        if (ra === 1) { var s1 = a.v.toLowerCase(), s2 = b.v.toLowerCase(); return s1 < s2 ? -1 : s1 > s2 ? 1 : 0; }
        return (a.v ? 1 : 0) - (b.v ? 1 : 0);
    }
    X.compare = compare;

    // ── Evaluator ───────────────────────────────────────────────────────
    /** A range argument: lazily materialised 2-D array of values. */
    function RangeVal(ctx, node) {
        var size = ctx.size(node.sheet);
        if (!size) return E(ERR.ref, 'Unknown sheet ' + node.sheet);
        var a = node.a, b = node.b;
        var r1 = a.r === null ? 0 : a.r, r2 = b.r === null ? size.rows - 1 : b.r;
        var c1 = a.c === null ? 0 : a.c, c2 = b.c === null ? size.cols - 1 : b.c;
        if (r1 > r2) { var t = r1; r1 = r2; r2 = t; }
        if (c1 > c2) { var u = c1; c1 = c2; c2 = u; }
        // Don't walk thousands of empty rows of a whole-column reference.
        if (a.r === null || b.r === null) r2 = Math.min(r2, Math.max(r1, size.usedRows - 1));
        if (a.c === null || b.c === null) c2 = Math.min(c2, Math.max(c1, size.usedCols - 1));
        return { t: 'range', sheet: node.sheet, r1: r1, c1: c1, r2: r2, c2: c2, ctx: ctx };
    }
    function rangeEach(rv, fn) {
        for (var r = rv.r1; r <= rv.r2; r++) for (var c = rv.c1; c <= rv.c2; c++) fn(rv.ctx.cell(rv.sheet, r, c), r - rv.r1, c - rv.c1);
    }
    function rangeAt(rv, i, j) { return rv.ctx.cell(rv.sheet, rv.r1 + i, rv.c1 + j); }
    function rangeRows(rv) { return rv.r2 - rv.r1 + 1; }
    function rangeCols(rv) { return rv.c2 - rv.c1 + 1; }

    /** Scalar value of an expression (a 1x1 range collapses to its cell). */
    function scalar(v) {
        if (v && v.t === 'range') {
            if (rangeRows(v) === 1 && rangeCols(v) === 1) return rangeAt(v, 0, 0);
            return E(ERR.value, 'A range can\'t be used here');
        }
        return v;
    }

    function evalNode(node, ctx) {
        switch (node.k) {
            case 'num': return N(node.v);
            case 'str': return S(node.v);
            case 'bool': return B(node.v);
            case 'err': return E(node.v);
            case 'blank': return EMPTY;
            case 'cell': return ctx.cell(node.sheet, node.a.r, node.a.c);
            case 'range': return RangeVal(ctx, node);
            case 'un': {
                var v = toNum(scalar(evalNode(node.a, ctx)));
                if (isErr(v)) return v;
                return N(node.op === '-' ? -v.v : v.v, v.kind);
            }
            case 'pct': {
                var pv = toNum(scalar(evalNode(node.a, ctx)));
                return isErr(pv) ? pv : N(pv.v / 100, 'percent');
            }
            case 'bin': return binary(node.op, scalar(evalNode(node.a, ctx)), scalar(evalNode(node.b, ctx)));
            case 'fn': return callFn(node, ctx);
        }
        return E(ERR.parse);
    }

    function binary(op, a, b) {
        if (isErr(a)) return a;
        if (isErr(b)) return b;
        if (op === '&') return S(toStr(a) + toStr(b));
        if (op === '=' || op === '<>' || op === '<' || op === '>' || op === '<=' || op === '>=') {
            var c = compare(a, b);
            return B(op === '=' ? c === 0 : op === '<>' ? c !== 0 : op === '<' ? c < 0 : op === '>' ? c > 0 : op === '<=' ? c <= 0 : c >= 0);
        }
        var x = toNum(a), y = toNum(b);
        if (isErr(x)) return x;
        if (isErr(y)) return y;
        var kind;
        if (op === '+' || op === '-') {
            var dk = function (v) { return v.kind === 'date' || v.kind === 'datetime' ? v.kind : null; };
            if (dk(x) && !dk(y)) kind = dk(x);
            else if (dk(y) && !dk(x) && op === '+') kind = dk(y);
            else if (x.kind === 'currency' || y.kind === 'currency') kind = 'currency';
        } else if ((op === '*' || op === '/') && (x.kind === 'currency') !== (y.kind === 'currency')) {
            kind = 'currency';
        }
        switch (op) {
            case '+': return N(x.v + y.v, kind);
            case '-': return N(x.v - y.v, kind);
            case '*': return N(x.v * y.v, kind);
            case '/': return y.v === 0 ? E(ERR.div0, 'Division by zero') : N(x.v / y.v, kind);
            case '^': return N(Math.pow(x.v, y.v));
        }
        return E(ERR.parse);
    }

    // Collect values of arguments for aggregate functions. Ranges contribute
    // only their numbers (text/blank skipped); direct arguments are coerced.
    function numbersOf(args, ctx, opts) {
        opts = opts || {};
        var out = [];
        for (var i = 0; i < args.length; i++) {
            var v = evalNode(args[i], ctx);
            if (v.t === 'range') {
                var err = null;
                rangeEach(v, function (cv) {
                    if (err) return;
                    if (cv.t === 'e') err = cv;
                    else if (cv.t === 'n') out.push(cv.v);
                });
                if (err) return err;
            } else if (v.t === 'e') {
                return v;
            } else if (v.t !== 'empty' || opts.blankAsZero) {
                var n = toNum(v);
                if (isErr(n)) return n;
                out.push(n.v);
            }
        }
        return out;
    }

    function flatValues(args, ctx) {
        var out = [];
        args.forEach(function (a) {
            var v = evalNode(a, ctx);
            if (v.t === 'range') rangeEach(v, function (cv) { out.push(cv); });
            else out.push(v);
        });
        return out;
    }

    function wildcardRe(pattern) {
        var re = '';
        for (var i = 0; i < pattern.length; i++) {
            var ch = pattern.charAt(i);
            if (ch === '~' && i + 1 < pattern.length) { re += pattern.charAt(++i).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
            else if (ch === '*') re += '.*';
            else if (ch === '?') re += '.';
            else re += ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }
        return new RegExp('^' + re + '$', 'i');
    }

    /** SUMIF/COUNTIF criteria: 10, ">10", "<>x", "app*", "=". */
    function criteria(crit) {
        crit = scalar(crit);
        if (crit.t === 'n' || crit.t === 'b') return function (v) { return v.t !== 'empty' && compare(v, crit) === 0; };
        var s = toStr(crit), m = /^(<=|>=|<>|<|>|=)?(.*)$/.exec(s), op = m[1] || '=', rhs = m[2];
        var num = FM.parse(rhs);
        if (num.t === 'n' && rhs.trim() !== '') {
            return function (v) {
                if (v.t !== 'n') return op === '<>';
                var c = v.v < num.v ? -1 : v.v > num.v ? 1 : 0;
                return op === '=' ? c === 0 : op === '<>' ? c !== 0 : op === '<' ? c < 0 : op === '>' ? c > 0 : op === '<=' ? c <= 0 : c >= 0;
            };
        }
        if (op === '=' || op === '<>') {
            var re = wildcardRe(rhs);
            return function (v) {
                var ok = rhs === '' ? (v.t === 'empty' || toStr(v) === '') : re.test(toStr(v));
                return op === '=' ? ok : !ok;
            };
        }
        return function (v) {
            if (v.t !== 's') return false;
            var c = compare(v, S(rhs));
            return op === '<' ? c < 0 : op === '>' ? c > 0 : op === '<=' ? c <= 0 : c >= 0;
        };
    }

    function argNum(node, ctx) { return toNum(scalar(evalNode(node, ctx))); }
    function argStr(node, ctx) { var v = scalar(evalNode(node, ctx)); return isErr(v) ? v : toStr(v); }
    function round(n, d, mode) {
        var f = Math.pow(10, d);
        var x = n * f;
        x = Math.abs(x - Math.round(x)) < 1e-9 ? Math.round(x) : x;
        var r = mode === 'up' ? Math.sign(x) * Math.ceil(Math.abs(x)) : mode === 'down' ? Math.sign(x) * Math.floor(Math.abs(x)) : Math.sign(x) * Math.round(Math.abs(x));
        return r / f;
    }
    function ifIsStr(v) { return typeof v !== 'string'; }

    function lookupMatch(rv, isRow, idx, key, sorted) {
        var len = isRow ? rangeCols(rv) : rangeRows(rv), best = -1;
        for (var i = 0; i < len; i++) {
            var v = isRow ? rangeAt(rv, idx, i) : rangeAt(rv, i, idx);
            if (v.t === 'empty') continue;
            var c = compare(v, key);
            if (sorted) {
                if (c <= 0 && (key.t === 'n') === (v.t === 'n')) best = i; else if (c > 0) break;
            } else if (c === 0 || (key.t === 's' && v.t !== 'n' && wildcardRe(key.v).test(toStr(v)))) {
                return i;
            }
        }
        return best;
    }

    var FUNCS = {
        SUM: { min: 1, syntax: 'SUM(value1, [value2, ...])', desc: 'Adds numbers and ranges.', fn: function (a, ctx) {
            var ns = numbersOf(a, ctx); if (!Array.isArray(ns)) return ns;
            return N(ns.reduce(function (s, n) { return s + n; }, 0), kindOfFirst(a, ctx));
        } },
        AVERAGE: { min: 1, syntax: 'AVERAGE(value1, [value2, ...])', desc: 'Average of the numbers.', fn: function (a, ctx) {
            var ns = numbersOf(a, ctx); if (!Array.isArray(ns)) return ns;
            return ns.length ? N(ns.reduce(function (s, n) { return s + n; }, 0) / ns.length, kindOfFirst(a, ctx)) : E(ERR.div0, 'No numbers to average');
        } },
        MIN: { min: 1, syntax: 'MIN(value1, [value2, ...])', desc: 'Smallest number.', fn: function (a, ctx) {
            var ns = numbersOf(a, ctx); if (!Array.isArray(ns)) return ns;
            return N(ns.length ? Math.min.apply(null, ns) : 0, kindOfFirst(a, ctx));
        } },
        MAX: { min: 1, syntax: 'MAX(value1, [value2, ...])', desc: 'Largest number.', fn: function (a, ctx) {
            var ns = numbersOf(a, ctx); if (!Array.isArray(ns)) return ns;
            return N(ns.length ? Math.max.apply(null, ns) : 0, kindOfFirst(a, ctx));
        } },
        MEDIAN: { min: 1, syntax: 'MEDIAN(value1, [value2, ...])', desc: 'Middle number.', fn: function (a, ctx) {
            var ns = numbersOf(a, ctx); if (!Array.isArray(ns)) return ns;
            if (!ns.length) return E(ERR.num);
            ns.sort(function (x, y) { return x - y; });
            var mid = Math.floor(ns.length / 2);
            return N(ns.length % 2 ? ns[mid] : (ns[mid - 1] + ns[mid]) / 2);
        } },
        PRODUCT: { min: 1, syntax: 'PRODUCT(value1, [value2, ...])', desc: 'Multiplies numbers.', fn: function (a, ctx) {
            var ns = numbersOf(a, ctx); if (!Array.isArray(ns)) return ns;
            return N(ns.reduce(function (s, n) { return s * n; }, ns.length ? 1 : 0));
        } },
        COUNT: { min: 1, syntax: 'COUNT(value1, [value2, ...])', desc: 'Counts numeric values.', fn: function (a, ctx) {
            var n = 0;
            flatValues(a, ctx).forEach(function (v) { if (v.t === 'n') n++; });
            return N(n);
        } },
        COUNTA: { min: 1, syntax: 'COUNTA(value1, [value2, ...])', desc: 'Counts non-empty values.', fn: function (a, ctx) {
            var n = 0;
            flatValues(a, ctx).forEach(function (v) { if (v.t !== 'empty') n++; });
            return N(n);
        } },
        COUNTBLANK: { min: 1, max: 1, syntax: 'COUNTBLANK(range)', desc: 'Counts empty cells.', fn: function (a, ctx) {
            var n = 0;
            flatValues(a, ctx).forEach(function (v) { if (v.t === 'empty' || (v.t === 's' && v.v === '')) n++; });
            return N(n);
        } },
        IF: { min: 2, max: 3, lazy: true, syntax: 'IF(condition, value_if_true, [value_if_false])', desc: 'Returns one value if a condition is TRUE and another if FALSE.', fn: function (a, ctx) {
            var c = toBool(scalar(evalNode(a[0], ctx)));
            if (isErr(c)) return c;
            if (c.v) return scalar(evalNode(a[1], ctx));
            return a.length > 2 ? scalar(evalNode(a[2], ctx)) : B(false);
        } },
        IFERROR: { min: 2, max: 2, lazy: true, syntax: 'IFERROR(value, value_if_error)', desc: 'Returns a fallback when value is an error.', fn: function (a, ctx) {
            var v = scalar(evalNode(a[0], ctx));
            return isErr(v) ? scalar(evalNode(a[1], ctx)) : v;
        } },
        AND: { min: 1, syntax: 'AND(logical1, [logical2, ...])', desc: 'TRUE if all are TRUE.', fn: function (a, ctx) {
            var vals = flatValues(a, ctx), res = true;
            for (var i = 0; i < vals.length; i++) {
                if (vals[i].t === 'empty' || vals[i].t === 's') continue;
                var b = toBool(vals[i]); if (isErr(b)) return b; res = res && b.v;
            }
            return B(res);
        } },
        OR: { min: 1, syntax: 'OR(logical1, [logical2, ...])', desc: 'TRUE if any is TRUE.', fn: function (a, ctx) {
            var vals = flatValues(a, ctx), res = false;
            for (var i = 0; i < vals.length; i++) {
                if (vals[i].t === 'empty' || vals[i].t === 's') continue;
                var b = toBool(vals[i]); if (isErr(b)) return b; res = res || b.v;
            }
            return B(res);
        } },
        NOT: { min: 1, max: 1, syntax: 'NOT(logical)', desc: 'Reverses TRUE/FALSE.', fn: function (a, ctx) {
            var b = toBool(scalar(evalNode(a[0], ctx))); return isErr(b) ? b : B(!b.v);
        } },
        ROUND: { min: 1, max: 2, syntax: 'ROUND(value, [places])', desc: 'Rounds to a number of decimal places.', fn: function (a, ctx) { return roundFn(a, ctx, 'half'); } },
        ROUNDUP: { min: 1, max: 2, syntax: 'ROUNDUP(value, [places])', desc: 'Rounds away from zero.', fn: function (a, ctx) { return roundFn(a, ctx, 'up'); } },
        ROUNDDOWN: { min: 1, max: 2, syntax: 'ROUNDDOWN(value, [places])', desc: 'Rounds towards zero.', fn: function (a, ctx) { return roundFn(a, ctx, 'down'); } },
        INT: { min: 1, max: 1, syntax: 'INT(value)', desc: 'Rounds down to an integer.', fn: function (a, ctx) { var n = argNum(a[0], ctx); return isErr(n) ? n : N(Math.floor(n.v)); } },
        ABS: { min: 1, max: 1, syntax: 'ABS(value)', desc: 'Absolute value.', fn: function (a, ctx) { var n = argNum(a[0], ctx); return isErr(n) ? n : N(Math.abs(n.v), n.kind); } },
        MOD: { min: 2, max: 2, syntax: 'MOD(dividend, divisor)', desc: 'Remainder after division.', fn: function (a, ctx) {
            var x = argNum(a[0], ctx), y = argNum(a[1], ctx);
            if (isErr(x)) return x; if (isErr(y)) return y;
            return y.v === 0 ? E(ERR.div0) : N(x.v - y.v * Math.floor(x.v / y.v));
        } },
        POWER: { min: 2, max: 2, syntax: 'POWER(base, exponent)', desc: 'Base raised to a power.', fn: function (a, ctx) {
            var x = argNum(a[0], ctx), y = argNum(a[1], ctx);
            if (isErr(x)) return x; if (isErr(y)) return y;
            return N(Math.pow(x.v, y.v));
        } },
        SQRT: { min: 1, max: 1, syntax: 'SQRT(value)', desc: 'Square root.', fn: function (a, ctx) {
            var x = argNum(a[0], ctx); if (isErr(x)) return x;
            return x.v < 0 ? E(ERR.num) : N(Math.sqrt(x.v));
        } },
        CONCAT: { min: 1, syntax: 'CONCAT(value1, [value2, ...])', desc: 'Joins text.', fn: concatFn },
        CONCATENATE: { min: 1, syntax: 'CONCATENATE(value1, [value2, ...])', desc: 'Joins text.', fn: concatFn },
        TEXTJOIN: { min: 3, syntax: 'TEXTJOIN(delimiter, ignore_empty, text1, ...)', desc: 'Joins text with a delimiter.', fn: function (a, ctx) {
            var d = argStr(a[0], ctx); if (ifIsStr(d)) return d;
            var ig = toBool(scalar(evalNode(a[1], ctx))); if (isErr(ig)) return ig;
            var parts = [];
            var vals = flatValues(a.slice(2), ctx);
            for (var i = 0; i < vals.length; i++) {
                if (isErr(vals[i])) return vals[i];
                var s = toStr(vals[i]);
                if (s !== '' || !ig.v) parts.push(s);
            }
            return S(parts.join(d));
        } },
        LEN: { min: 1, max: 1, syntax: 'LEN(text)', desc: 'Number of characters.', fn: function (a, ctx) { var s = argStr(a[0], ctx); return ifIsStr(s) ? s : N(s.length); } },
        UPPER: { min: 1, max: 1, syntax: 'UPPER(text)', desc: 'Upper case.', fn: function (a, ctx) { var s = argStr(a[0], ctx); return ifIsStr(s) ? s : S(s.toUpperCase()); } },
        LOWER: { min: 1, max: 1, syntax: 'LOWER(text)', desc: 'Lower case.', fn: function (a, ctx) { var s = argStr(a[0], ctx); return ifIsStr(s) ? s : S(s.toLowerCase()); } },
        PROPER: { min: 1, max: 1, syntax: 'PROPER(text)', desc: 'Capitalises each word.', fn: function (a, ctx) {
            var s = argStr(a[0], ctx); if (ifIsStr(s)) return s;
            return S(s.toLowerCase().replace(/(^|[^a-z])([a-z])/g, function (m, p, c) { return p + c.toUpperCase(); }));
        } },
        TRIM: { min: 1, max: 1, syntax: 'TRIM(text)', desc: 'Removes extra spaces.', fn: function (a, ctx) { var s = argStr(a[0], ctx); return ifIsStr(s) ? s : S(s.replace(/\s+/g, ' ').trim()); } },
        LEFT: { min: 1, max: 2, syntax: 'LEFT(text, [count])', desc: 'Characters from the start.', fn: function (a, ctx) { return sliceFn(a, ctx, 'left'); } },
        RIGHT: { min: 1, max: 2, syntax: 'RIGHT(text, [count])', desc: 'Characters from the end.', fn: function (a, ctx) { return sliceFn(a, ctx, 'right'); } },
        MID: { min: 3, max: 3, syntax: 'MID(text, start, count)', desc: 'Characters from the middle.', fn: function (a, ctx) {
            var s = argStr(a[0], ctx), st = argNum(a[1], ctx), n = argNum(a[2], ctx);
            if (ifIsStr(s)) return s; if (isErr(st)) return st; if (isErr(n)) return n;
            if (st.v < 1 || n.v < 0) return E(ERR.value);
            return S(s.substr(Math.floor(st.v) - 1, Math.floor(n.v)));
        } },
        SUBSTITUTE: { min: 3, max: 3, syntax: 'SUBSTITUTE(text, search, replacement)', desc: 'Replaces text.', fn: function (a, ctx) {
            var s = argStr(a[0], ctx), f = argStr(a[1], ctx), r = argStr(a[2], ctx);
            if (ifIsStr(s)) return s; if (ifIsStr(f)) return f; if (ifIsStr(r)) return r;
            return S(f === '' ? s : s.split(f).join(r));
        } },
        FIND: { min: 2, max: 3, syntax: 'FIND(search, text, [start])', desc: 'Position of text (case-sensitive).', fn: function (a, ctx) {
            var f = argStr(a[0], ctx), s = argStr(a[1], ctx);
            if (ifIsStr(f)) return f; if (ifIsStr(s)) return s;
            var st = a.length > 2 ? argNum(a[2], ctx) : N(1); if (isErr(st)) return st;
            var i = s.indexOf(f, st.v - 1);
            return i < 0 ? E(ERR.value, 'Text not found') : N(i + 1);
        } },
        VALUE: { min: 1, max: 1, syntax: 'VALUE(text)', desc: 'Converts text to a number.', fn: function (a, ctx) { return toNum(scalar(evalNode(a[0], ctx))); } },
        TODAY: { min: 0, max: 0, syntax: 'TODAY()', desc: 'Today\'s date.', fn: function () { return N(FM.todaySerial(), 'date'); } },
        NOW: { min: 0, max: 0, syntax: 'NOW()', desc: 'Current date and time.', fn: function () { return N(FM.nowSerial(), 'datetime'); } },
        DATE: { min: 3, max: 3, syntax: 'DATE(year, month, day)', desc: 'Builds a date.', fn: function (a, ctx) {
            var y = argNum(a[0], ctx), m = argNum(a[1], ctx), d = argNum(a[2], ctx);
            if (isErr(y)) return y; if (isErr(m)) return m; if (isErr(d)) return d;
            return N(FM.dateToSerial(Math.floor(y.v), Math.floor(m.v), Math.floor(d.v)), 'date');
        } },
        YEAR: { min: 1, max: 1, syntax: 'YEAR(date)', desc: 'Year of a date.', fn: function (a, ctx) { return datePart(a, ctx, 'y'); } },
        MONTH: { min: 1, max: 1, syntax: 'MONTH(date)', desc: 'Month of a date (1-12).', fn: function (a, ctx) { return datePart(a, ctx, 'm'); } },
        DAY: { min: 1, max: 1, syntax: 'DAY(date)', desc: 'Day of a date.', fn: function (a, ctx) { return datePart(a, ctx, 'd'); } },
        SUMIF: { min: 2, max: 3, syntax: 'SUMIF(range, criterion, [sum_range])', desc: 'Sum of cells that meet a condition.', fn: function (a, ctx) {
            var rv = evalNode(a[0], ctx); if (rv.t !== 'range') return E(ERR.value, 'SUMIF needs a range');
            var test = criteria(evalNode(a[1], ctx));
            var sv = a.length > 2 ? evalNode(a[2], ctx) : rv; if (sv.t !== 'range') return E(ERR.value);
            var total = 0;
            for (var i = 0; i < rangeRows(rv); i++) for (var j = 0; j < rangeCols(rv); j++) {
                if (test(rangeAt(rv, i, j))) { var v = rangeAt(sv, i, j); if (v.t === 'n') total += v.v; }
            }
            return N(total);
        } },
        COUNTIF: { min: 2, max: 2, syntax: 'COUNTIF(range, criterion)', desc: 'Counts cells that meet a condition.', fn: function (a, ctx) {
            var rv = evalNode(a[0], ctx); if (rv.t !== 'range') return E(ERR.value, 'COUNTIF needs a range');
            var test = criteria(evalNode(a[1], ctx)), n = 0;
            rangeEach(rv, function (v) { if (test(v)) n++; });
            return N(n);
        } },
        AVERAGEIF: { min: 2, max: 3, syntax: 'AVERAGEIF(range, criterion, [average_range])', desc: 'Average of cells that meet a condition.', fn: function (a, ctx) {
            var rv = evalNode(a[0], ctx); if (rv.t !== 'range') return E(ERR.value);
            var test = criteria(evalNode(a[1], ctx));
            var sv = a.length > 2 ? evalNode(a[2], ctx) : rv; if (sv.t !== 'range') return E(ERR.value);
            var total = 0, n = 0;
            for (var i = 0; i < rangeRows(rv); i++) for (var j = 0; j < rangeCols(rv); j++) {
                if (test(rangeAt(rv, i, j))) { var v = rangeAt(sv, i, j); if (v.t === 'n') { total += v.v; n++; } }
            }
            return n ? N(total / n) : E(ERR.div0);
        } },
        VLOOKUP: { min: 3, max: 4, syntax: 'VLOOKUP(search_key, range, index, [is_sorted])', desc: 'Finds a value in the first column and returns a cell from the same row.', fn: function (a, ctx) { return lookupFn(a, ctx, false); } },
        HLOOKUP: { min: 3, max: 4, syntax: 'HLOOKUP(search_key, range, index, [is_sorted])', desc: 'Finds a value in the first row and returns a cell from the same column.', fn: function (a, ctx) { return lookupFn(a, ctx, true); } },
        MATCH: { min: 2, max: 3, syntax: 'MATCH(search_key, range, [type])', desc: 'Position of a value in a row or column.', fn: function (a, ctx) {
            var key = scalar(evalNode(a[0], ctx)), rv = evalNode(a[1], ctx);
            if (isErr(key)) return key; if (rv.t !== 'range') return E(ERR.value);
            var type = a.length > 2 ? argNum(a[2], ctx) : N(1); if (isErr(type)) return type;
            var isRow = rangeRows(rv) === 1;
            var i = lookupMatch(rv, isRow, 0, key, type.v === 1);
            return i < 0 ? E(ERR.na, 'Value not found') : N(i + 1);
        } },
        INDEX: { min: 2, max: 3, syntax: 'INDEX(range, row, [column])', desc: 'Value at a position in a range.', fn: function (a, ctx) {
            var rv = evalNode(a[0], ctx); if (rv.t !== 'range') return E(ERR.value);
            var r = argNum(a[1], ctx), c = a.length > 2 ? argNum(a[2], ctx) : N(1);
            if (isErr(r)) return r; if (isErr(c)) return c;
            var ri = Math.floor(r.v) || 1, ci = Math.floor(c.v) || 1;
            if (rangeRows(rv) === 1 && a.length === 2) { ci = ri; ri = 1; }
            if (ri < 1 || ci < 1 || ri > rangeRows(rv) || ci > rangeCols(rv)) return E(ERR.ref, 'Index out of range');
            return rangeAt(rv, ri - 1, ci - 1);
        } },
        ISBLANK: { min: 1, max: 1, syntax: 'ISBLANK(value)', desc: 'TRUE if empty.', fn: function (a, ctx) { return B(scalar(evalNode(a[0], ctx)).t === 'empty'); } },
        ISNUMBER: { min: 1, max: 1, syntax: 'ISNUMBER(value)', desc: 'TRUE if a number.', fn: function (a, ctx) { return B(scalar(evalNode(a[0], ctx)).t === 'n'); } },
        ISTEXT: { min: 1, max: 1, syntax: 'ISTEXT(value)', desc: 'TRUE if text.', fn: function (a, ctx) { return B(scalar(evalNode(a[0], ctx)).t === 's'); } },
        ISERROR: { min: 1, max: 1, lazy: true, syntax: 'ISERROR(value)', desc: 'TRUE if an error.', fn: function (a, ctx) { return B(isErr(scalar(evalNode(a[0], ctx)))); } },
        HYPERLINK: { min: 1, max: 2, syntax: 'HYPERLINK(url, [label])', desc: 'A clickable link.', fn: function (a, ctx) {
            var u = argStr(a[0], ctx); if (ifIsStr(u)) return u;
            var label = a.length > 1 ? argStr(a[1], ctx) : u; if (ifIsStr(label)) return label;
            var v = S(label);
            var safe = CS.safeUrl(u);
            if (safe) v.link = safe;
            return v;
        } },
    };

    function kindOfFirst(args, ctx) {
        // SUM of a currency/date column keeps that display kind.
        for (var i = 0; i < args.length; i++) {
            var v = evalNode(args[i], ctx);
            if (v.t === 'range') {
                for (var r = v.r1; r <= Math.min(v.r2, v.r1 + 50); r++) for (var c = v.c1; c <= v.c2; c++) {
                    var cv = v.ctx.cell(v.sheet, r, c);
                    if (cv.t === 'n') return cv.kind === 'currency' ? 'currency' : undefined;
                }
            } else if (v.t === 'n') {
                return v.kind === 'currency' ? 'currency' : undefined;
            }
        }
        return undefined;
    }
    function roundFn(a, ctx, mode) {
        var x = argNum(a[0], ctx); if (isErr(x)) return x;
        var d = a.length > 1 ? argNum(a[1], ctx) : N(0); if (isErr(d)) return d;
        return N(round(x.v, Math.floor(d.v), mode), x.kind);
    }
    function concatFn(a, ctx) {
        var vals = flatValues(a, ctx), out = '';
        for (var i = 0; i < vals.length; i++) { if (isErr(vals[i])) return vals[i]; out += toStr(vals[i]); }
        return S(out);
    }
    function sliceFn(a, ctx, side) {
        var s = argStr(a[0], ctx); if (ifIsStr(s)) return s;
        var n = a.length > 1 ? argNum(a[1], ctx) : N(1); if (isErr(n)) return n;
        if (n.v < 0) return E(ERR.value);
        var k = Math.floor(n.v);
        return S(side === 'left' ? s.slice(0, k) : (k ? s.slice(-k) : ''));
    }
    function datePart(a, ctx, part) {
        var n = argNum(a[0], ctx); if (isErr(n)) return n;
        var d = FM.serialToDate(n.v);
        return N(part === 'y' ? d.getUTCFullYear() : part === 'm' ? d.getUTCMonth() + 1 : d.getUTCDate());
    }
    function lookupFn(a, ctx, horizontal) {
        var key = scalar(evalNode(a[0], ctx)), rv = evalNode(a[1], ctx);
        if (isErr(key)) return key; if (rv.t !== 'range') return E(ERR.value);
        var idx = argNum(a[2], ctx); if (isErr(idx)) return idx;
        var sorted = a.length > 3 ? toBool(scalar(evalNode(a[3], ctx))) : B(true); if (isErr(sorted)) return sorted;
        var k = Math.floor(idx.v);
        if (k < 1 || k > (horizontal ? rangeRows(rv) : rangeCols(rv))) return E(ERR.ref, 'Index out of range');
        var i = lookupMatch(rv, horizontal, 0, key, sorted.v);
        if (i < 0) return E(ERR.na, 'Value not found');
        return horizontal ? rangeAt(rv, k - 1, i) : rangeAt(rv, i, k - 1);
    }

    function callFn(node, ctx) {
        var def = FUNCS[node.name];
        if (!def) return E(ERR.name, 'Unknown function ' + node.name);
        var n = node.args.length;
        if (n < def.min || (def.max !== undefined && n > def.max)) {
            return E(ERR.value, node.name + ' expects ' + (def.max === def.min ? def.min : def.min + (def.max !== undefined ? '-' + def.max : '+')) + ' argument(s)');
        }
        var res = def.fn(node.args, ctx);
        return res && res.t === 'range' ? scalar(res) : res;
    }

    /**
     * Evaluate formula text (without the leading '=') against ctx:
     *   ctx.cell(sheetName|null, r, c) -> value
     *   ctx.size(sheetName|null) -> {rows, cols, usedRows, usedCols} | null
     */
    X.evaluate = function (src, ctx) {
        var compiled = X.compile(src);
        if (compiled.error) return E(ERR.parse, compiled.error);
        try {
            var v = scalar(evalNode(compiled.ast, ctx));
            return v || EMPTY;
        } catch (e) {
            if (e && e.crmSheetCycle) return E(ERR.cycle, 'Circular reference');
            return E(ERR.parse, e && e.message ? e.message : 'Formula error');
        }
    };

    X.functions = function () {
        return Object.keys(FUNCS).sort().map(function (k) { return { name: k, syntax: FUNCS[k].syntax, desc: FUNCS[k].desc }; });
    };
    X.fn = function (name) { return FUNCS[name] ? { name: name, syntax: FUNCS[name].syntax, desc: FUNCS[name].desc } : null; };

    // ── Rewriting references ────────────────────────────────────────────
    function partText(p) {
        var s = '';
        if (p.c !== null) s += (p.absC ? '$' : '') + CS.colName(p.c);
        if (p.r !== null) s += (p.absR ? '$' : '') + (p.r + 1);
        return s;
    }
    function refText(tok, a, b) {
        var pre = tok.sheet !== null && tok.sheet !== undefined ? X.quoteSheet(tok.sheet) + '!' : '';
        return pre + partText(a) + (b ? ':' + partText(b) : '');
    }

    /**
     * Rewrite every reference in a formula. fn(tok, a, b) returns
     * {a, b} (new parts), the string '#REF!', or null to keep it.
     * Returns the original text if the formula doesn't tokenize.
     */
    X.rewrite = function (formula, fn) {
        if (typeof formula !== 'string' || formula.charAt(0) !== '=') return formula;
        var src = formula.slice(1), toks;
        try { toks = X.tokenize(src); } catch (e) { return formula; }
        var out = '', last = 0, changed = false;
        toks.forEach(function (t) {
            if (t.type !== 'ref') return;
            var a = Object.assign({}, t.ref.a), b = t.ref.b ? Object.assign({}, t.ref.b) : null;
            var res = fn(t, a, b);
            if (res === null || res === undefined) return;
            out += src.slice(last, t.start) + (res === '#REF!' ? '#REF!' : refText(t, res.a, res.b));
            last = t.end;
            changed = true;
        });
        return changed ? '=' + out + src.slice(last) : formula;
    };

    /** Copy/paste: move relative references by (dr, dc). */
    X.shift = function (formula, dr, dc) {
        if (!dr && !dc) return formula;
        return X.rewrite(formula, function (t, a, b) {
            var bad = false;
            [a, b].forEach(function (p) {
                if (!p) return;
                if (p.r !== null && !p.absR) { p.r += dr; if (p.r < 0) bad = true; }
                if (p.c !== null && !p.absC) { p.c += dc; if (p.c < 0) bad = true; }
            });
            return bad ? '#REF!' : { a: a, b: b };
        });
    };

    /**
     * Rows/columns inserted (count > 0) or deleted (count < 0) at `at` on
     * sheet `target`. `own` is the name of the sheet holding the formula
     * (unprefixed references point there).
     */
    X.adjust = function (formula, own, target, axis, at, count) {
        var key = axis === 'row' ? 'r' : 'c';
        return X.rewrite(formula, function (t, a, b) {
            var sheet = t.sheet !== null && t.sheet !== undefined ? t.sheet : own;
            if (String(sheet).toLowerCase() !== String(target).toLowerCase()) return null;
            if (a[key] === null) return null; // whole-column ref vs row change etc.
            if (count > 0) {
                var moved = false;
                [a, b].forEach(function (p) { if (p && p[key] >= at) { p[key] += count; moved = true; } });
                return moved ? { a: a, b: b } : null;
            }
            var del = -count, end = at + del - 1;
            if (!b) {
                if (a[key] >= at && a[key] <= end) return '#REF!';
                if (a[key] > end) { a[key] -= del; return { a: a, b: b }; }
                return null;
            }
            var lo = Math.min(a[key], b[key]), hi = Math.max(a[key], b[key]);
            if (lo >= at && hi <= end) return '#REF!';
            var nlo = lo > end ? lo - del : (lo >= at ? at : lo);
            var nhi = hi > end ? hi - del : (hi >= at ? at - 1 : hi);
            if (nlo === lo && nhi === hi) return null;
            if (a[key] <= b[key]) { a[key] = nlo; b[key] = nhi; } else { b[key] = nlo; a[key] = nhi; }
            return { a: a, b: b };
        });
    };

    /** A sheet was renamed: update references that name it. */
    X.renameSheet = function (formula, oldName, newName) {
        return X.rewrite(formula, function (t, a, b) {
            if (t.sheet === null || t.sheet === undefined || t.sheet.toLowerCase() !== oldName.toLowerCase()) return null;
            t.sheet = newName;
            return { a: a, b: b };
        });
    };

    /** Sheets referenced by a formula (lower-cased names). */
    X.referencedSheets = function (formula) {
        var out = [];
        if (typeof formula !== 'string' || formula.charAt(0) !== '=') return out;
        try {
            X.tokenize(formula.slice(1)).forEach(function (t) { if (t.type === 'ref' && t.sheet) out.push(t.sheet.toLowerCase()); });
        } catch (e) { /* ignore */ }
        return out;
    };
})();
