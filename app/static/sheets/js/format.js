/* Spreadsheet module - turning typed input into values, and values into
 * display text according to the cell's number format. */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var F = CS.Format = {};

    // Dates are stored as Excel-compatible serial numbers (days since
    // 1899-12-30) so they sort, compare and do arithmetic like numbers.
    var EPOCH = Date.UTC(1899, 11, 30);
    var DAY = 86400000;

    F.dateToSerial = function (y, m, d, hh, mm, ss) {
        return (Date.UTC(y, m - 1, d, hh || 0, mm || 0, ss || 0) - EPOCH) / DAY;
    };
    F.serialToDate = function (n) { return new Date(EPOCH + Math.round(n * DAY)); };
    F.todaySerial = function () {
        var d = new Date();
        return F.dateToSerial(d.getFullYear(), d.getMonth() + 1, d.getDate());
    };
    F.nowSerial = function () {
        var d = new Date();
        return F.dateToSerial(d.getFullYear(), d.getMonth() + 1, d.getDate(), d.getHours(), d.getMinutes(), d.getSeconds());
    };

    function validDate(y, m, d) {
        if (m < 1 || m > 12 || d < 1 || d > 31 || y < 1900 || y > 9999) return false;
        var dt = new Date(Date.UTC(y, m - 1, d));
        return dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
    }

    var NUM_RE = /^[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:[eE][-+]?\d+)?$/;
    var CUR_RE = /^(-)?\s*(Rs\.?|PKR|\$|€|£|₨)\s?(.+)$/i;

    /**
     * Typed value of raw cell input:
     *   {t:'n', v:number, kind?:'date'|'time'|'datetime'|'percent'|'currency', cur?}
     *   {t:'s', v:string}  {t:'b', v:bool}  {t:'empty'}
     * Formulas are not handled here (see model.js).
     */
    F.parse = function (raw) {
        if (raw === null || raw === undefined || raw === '') return { t: 'empty' };
        var s = String(raw);
        if (s.charAt(0) === "'") return { t: 's', v: s.slice(1) };
        var t = s.trim();
        if (t === '') return { t: 's', v: s };
        var up = t.toUpperCase();
        if (up === 'TRUE' || up === 'FALSE') return { t: 'b', v: up === 'TRUE' };
        if (NUM_RE.test(t) && /\d/.test(t)) return { t: 'n', v: parseFloat(t.replace(/,/g, '')) };
        var m;
        if ((m = /^([-+]?[\d,]*\.?\d+)\s*%$/.exec(t)) && NUM_RE.test(m[1])) {
            return { t: 'n', v: parseFloat(m[1].replace(/,/g, '')) / 100, kind: 'percent' };
        }
        if ((m = CUR_RE.exec(t)) && NUM_RE.test(m[3].trim()) && /\d/.test(m[3])) {
            var cur = m[2].toUpperCase() === 'PKR' || /^rs/i.test(m[2]) ? 'Rs' : m[2];
            return { t: 'n', v: (m[1] ? -1 : 1) * parseFloat(m[3].replace(/,/g, '')), kind: 'currency', cur: cur };
        }
        // 2026-10-07, 2026-10-07 14:30(:15)
        if ((m = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$/.exec(t))) {
            var y = +m[1], mo = +m[2], d = +m[3];
            if (validDate(y, mo, d)) {
                return { t: 'n', v: F.dateToSerial(y, mo, d, +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)), kind: m[4] ? 'datetime' : 'date' };
            }
        }
        // 07/10/2026 or 7-10-2026 (day first)
        if ((m = /^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/.exec(t))) {
            if (validDate(+m[3], +m[2], +m[1])) return { t: 'n', v: F.dateToSerial(+m[3], +m[2], +m[1]), kind: 'date' };
        }
        // 14:30 or 14:30:15 or 2:30 PM
        if ((m = /^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?$/i.exec(t))) {
            var h = +m[1], mi = +m[2], se = +(m[3] || 0);
            if (m[4]) { if (h > 12 || h === 0) return { t: 's', v: s }; h = (h % 12) + (/pm/i.test(m[4]) ? 12 : 0); }
            if (h < 24 && mi < 60 && se < 60) return { t: 'n', v: (h * 3600 + mi * 60 + se) / 86400, kind: 'time' };
        }
        return { t: 's', v: s };
    };

    function pad(n) { return (n < 10 ? '0' : '') + n; }
    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    F.formatDate = function (n) {
        var d = F.serialToDate(n);
        return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate());
    };
    F.formatDateLong = function (n) {
        var d = F.serialToDate(n);
        return pad(d.getUTCDate()) + ' ' + MONTHS[d.getUTCMonth()] + ' ' + d.getUTCFullYear();
    };
    F.formatTime = function (n, seconds) {
        var total = Math.round((n - Math.floor(n)) * 86400);
        var h = Math.floor(total / 3600) % 24, m = Math.floor(total / 60) % 60, s = total % 60;
        return pad(h) + ':' + pad(m) + (seconds ? ':' + pad(s) : '');
    };

    F.grouped = function (n, decimals) {
        var neg = n < 0;
        var fixed = Math.abs(n).toFixed(decimals);
        var parts = fixed.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        return (neg && +fixed !== 0 ? '-' : '') + parts.join('.');
    };

    function autoNumber(n) {
        if (!isFinite(n)) return '#NUM!';
        if (Number.isInteger(n) && Math.abs(n) < 1e15) return String(n);
        var a = Math.abs(n);
        if (a !== 0 && (a < 1e-9 || a >= 1e15)) return n.toExponential(4).replace(/\.?0+e/, 'e');
        return String(parseFloat(n.toPrecision(12)));
    }

    /**
     * Display text for a computed value.
     * value: {t, v, kind?, cur?}; nf: cell number format {t, d, cur} or null.
     */
    F.display = function (value, nf) {
        if (!value || value.t === 'empty') return '';
        if (value.t === 'e') return value.v;
        if (value.t === 'b') return value.v ? 'TRUE' : 'FALSE';
        if (value.t === 's') return value.v;
        var n = value.v;
        var t = nf && nf.t ? nf.t : (value.kind || 'auto');
        if (t === 'text') return value.raw !== undefined ? value.raw : autoNumber(n);
        var d = nf && nf.d !== undefined ? nf.d : null;
        switch (t) {
            case 'number': return F.grouped(n, d === null ? 0 : d);
            case 'decimal': return F.grouped(n, d === null ? 2 : d);
            case 'currency': {
                var cur = (nf && nf.cur) || value.cur || 'Rs';
                var dd = d === null ? (Number.isInteger(n) ? 0 : 2) : d;
                var body = F.grouped(Math.abs(n), dd);
                return (n < 0 ? '-' : '') + cur + (cur.length > 1 ? ' ' : '') + body;
            }
            case 'percent': return F.grouped(n * 100, d === null ? (Number.isInteger(n * 100) ? 0 : 2) : d) + '%';
            case 'date': return F.formatDate(n);
            case 'datetime': return F.formatDate(n) + ' ' + F.formatTime(n, false);
            case 'time': return F.formatTime(n, true);
            default: return autoNumber(n);
        }
    };

    /** Inline CSS for a cell's style. */
    F.css = function (f) {
        if (!f) return '';
        var css = '';
        if (f.b) css += 'font-weight:700;';
        if (f.i) css += 'font-style:italic;';
        var deco = (f.u ? 'underline ' : '') + (f.s ? 'line-through' : '');
        if (deco) css += 'text-decoration:' + deco.trim() + ';';
        if (f.fs) css += 'font-size:' + (+f.fs) + 'pt;';
        if (f.ff) css += 'font-family:"' + String(f.ff).replace(/["\\;]/g, '') + '",sans-serif;';
        if (f.c && /^#[0-9a-f]{3,8}$/i.test(f.c)) css += 'color:' + f.c + ';';
        if (f.bg && /^#[0-9a-f]{3,8}$/i.test(f.bg)) css += 'background-color:' + f.bg + ';';
        return css;
    };

    F.borderCss = function (f) {
        if (!f) return '';
        var css = '';
        [['bt', 'top'], ['bb', 'bottom'], ['bl', 'left'], ['br', 'right']].forEach(function (p) {
            var b = f[p[0]];
            if (!b) return;
            var c = /^#[0-9a-f]{3,8}$/i.test(b.c || '') ? b.c : '#000';
            var s = ['solid', 'dashed', 'dotted', 'double'].indexOf(b.s) >= 0 ? b.s : 'solid';
            var w = b.s === 'double' ? 3 : Math.min(3, Math.max(1, +b.w || 1));
            css += 'border-' + p[1] + ':' + w + 'px ' + s + ' ' + c + ';';
        });
        return css;
    };

    F.NUMBER_FORMATS = [
        { t: 'auto', label: 'Automatic', sample: '1000.12' },
        { t: 'text', label: 'Plain text', sample: '1000.12' },
        { t: 'number', label: 'Number', sample: '1,000', d: 0 },
        { t: 'decimal', label: 'Decimal', sample: '1,000.12', d: 2 },
        { t: 'currency', label: 'Currency (Rs)', sample: 'Rs 1,000', cur: 'Rs', d: 0 },
        { t: 'currency', label: 'Currency ($)', sample: '$1,000.00', cur: '$', d: 2 },
        { t: 'currency', label: 'Currency (€)', sample: '€1,000.00', cur: '€', d: 2 },
        { t: 'percent', label: 'Percent', sample: '10.12%', d: 2 },
        { t: 'date', label: 'Date', sample: '2026-10-07' },
        { t: 'time', label: 'Time', sample: '14:30:00' },
        { t: 'datetime', label: 'Date time', sample: '2026-10-07 14:30' },
    ];
})();
