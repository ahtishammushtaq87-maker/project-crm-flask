/* Spreadsheet module - shared helpers (namespace window.CrmSheet).
 * Everything here is isolated under CrmSheet; nothing is added to the
 * global scope besides that one object. */
(function () {
    'use strict';
    var CS = window.CrmSheet = window.CrmSheet || {};

    // ── Text / HTML ─────────────────────────────────────────────────────
    var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    CS.esc = function (s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ESC[c]; });
    };

    /** Only http(s) and mailto links are ever made clickable. */
    CS.safeUrl = function (s) {
        if (typeof s !== 'string') return null;
        var t = s.trim();
        if (/^https?:\/\/[^\s<>"']+$/i.test(t) || /^mailto:[^\s<>"']+$/i.test(t)) return t;
        if (/^www\.[^\s<>"']+\.[a-z]{2,}[^\s<>"']*$/i.test(t)) return 'https://' + t;
        return null;
    };

    // ── A1 addressing ───────────────────────────────────────────────────
    CS.colName = function (c) {
        var s = '';
        c += 1;
        while (c > 0) {
            var m = (c - 1) % 26;
            s = String.fromCharCode(65 + m) + s;
            c = Math.floor((c - 1) / 26);
        }
        return s;
    };
    CS.colIndex = function (name) {
        var n = 0;
        name = name.toUpperCase();
        for (var i = 0; i < name.length; i++) n = n * 26 + (name.charCodeAt(i) - 64);
        return n - 1;
    };
    CS.addr = function (r, c) { return CS.colName(c) + (r + 1); };
    CS.parseAddr = function (s) {
        var m = /^\$?([A-Za-z]{1,3})\$?(\d+)$/.exec(String(s).trim());
        if (!m) return null;
        var r = parseInt(m[2], 10) - 1;
        return r < 0 ? null : { r: r, c: CS.colIndex(m[1]) };
    };
    CS.normRange = function (a) {
        return { r1: Math.min(a.r1, a.r2), c1: Math.min(a.c1, a.c2), r2: Math.max(a.r1, a.r2), c2: Math.max(a.c1, a.c2) };
    };
    CS.rangeStr = function (rg) {
        rg = CS.normRange(rg);
        if (rg.r1 === rg.r2 && rg.c1 === rg.c2) return CS.addr(rg.r1, rg.c1);
        return CS.addr(rg.r1, rg.c1) + ':' + CS.addr(rg.r2, rg.c2);
    };
    /** "B3", "A1:C5", "C" / "C:E" (columns), "5" / "5:9" (rows). */
    CS.parseRange = function (s, maxRows, maxCols) {
        s = String(s || '').trim().toUpperCase();
        var m;
        if ((m = /^([A-Z]{1,3})(?::([A-Z]{1,3}))?$/.exec(s))) {
            var c1 = CS.colIndex(m[1]), c2 = CS.colIndex(m[2] || m[1]);
            return CS.normRange({ r1: 0, c1: c1, r2: maxRows - 1, c2: c2 });
        }
        if ((m = /^(\d+)(?::(\d+))?$/.exec(s))) {
            var r1 = parseInt(m[1], 10) - 1, r2 = parseInt(m[2] || m[1], 10) - 1;
            if (r1 < 0 || r2 < 0) return null;
            return CS.normRange({ r1: r1, c1: 0, r2: r2, c2: maxCols - 1 });
        }
        var parts = s.split(':');
        var a = CS.parseAddr(parts[0]);
        var b = parts.length > 1 ? CS.parseAddr(parts[1]) : a;
        if (!a || !b || parts.length > 2) return null;
        return CS.normRange({ r1: a.r, c1: a.c, r2: b.r, c2: b.c });
    };
    CS.inRange = function (rg, r, c) { return r >= rg.r1 && r <= rg.r2 && c >= rg.c1 && c <= rg.c2; };
    CS.key = function (r, c) { return r + ',' + c; };

    // ── API ─────────────────────────────────────────────────────────────
    CS.csrf = function () {
        var m = document.querySelector('meta[name="crm-sheet-csrf"]');
        return m ? m.getAttribute('content') : '';
    };
    CS.base = function () {
        var m = document.querySelector('meta[name="crm-sheet-base"]');
        return m ? m.getAttribute('content').replace(/\/$/, '') : '/sheets';
    };
    /**
     * Resolves to {ok, status, data}. Never rejects; network failures come
     * back as status 0 so callers can show "Unable to save - Retry".
     */
    CS.api = function (method, path, body, opts) {
        opts = opts || {};
        var init = { method: method, credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } };
        if (method !== 'GET') init.headers['X-CSRFToken'] = CS.csrf();
        if (body instanceof FormData) {
            init.body = body;
        } else if (body !== undefined && body !== null) {
            init.headers['Content-Type'] = 'application/json';
            init.body = JSON.stringify(body);
        }
        if (opts.keepalive) init.keepalive = true;
        return fetch(CS.base() + '/api' + path, init).then(function (res) {
            return res.json().catch(function () { return {}; }).then(function (data) {
                if (res.status === 401) CS.sessionExpired();
                return { ok: res.ok && data.ok !== false, status: res.status, data: data };
            });
        }).catch(function () {
            return { ok: false, status: 0, data: { error: 'You appear to be offline. Changes will be saved when the connection returns.' } };
        });
    };
    CS.errorText = function (res, fallback) {
        return (res && res.data && res.data.error) || fallback || 'Something went wrong.';
    };
    var expiredShown = false;
    CS.sessionExpired = function () {
        if (expiredShown) return;
        expiredShown = true;
        CS.dialog({
            title: 'Session expired',
            body: '<p class="mb-0">Your session has expired. Sign in again to continue - unsaved changes in this tab may be lost.</p>',
            buttons: [{ label: 'Sign in', cls: 'btn-primary', action: function () { window.location.reload(); } }],
        });
    };

    // ── Toasts ──────────────────────────────────────────────────────────
    CS.toast = function (message, type) {
        var host = document.querySelector('.crm-sheet-toasts');
        if (!host) {
            host = document.createElement('div');
            host.className = 'crm-sheet-toasts';
            host.setAttribute('aria-live', 'polite');
            document.body.appendChild(host);
        }
        var el = document.createElement('div');
        el.className = 'crm-sheet-toast crm-sheet-toast-' + (type || 'info');
        el.setAttribute('role', type === 'error' ? 'alert' : 'status');
        el.innerHTML = '<span>' + CS.esc(message) + '</span><button type="button" aria-label="Dismiss">&times;</button>';
        el.querySelector('button').onclick = function () { el.remove(); };
        host.appendChild(el);
        setTimeout(function () { el.classList.add('crm-sheet-toast-out'); }, type === 'error' ? 6000 : 3000);
        setTimeout(function () { el.remove(); }, type === 'error' ? 6500 : 3500);
    };

    // ── Dialogs (Bootstrap modal built on the fly) ──────────────────────
    /**
     * opts: {title, body (HTML string or Element), size: 'sm'|'lg'|'xl',
     *        buttons: [{label, cls, action(modalEl) -> false keeps it open}],
     *        onOpen(modalEl), onClose()}
     */
    CS.dialog = function (opts) {
        var wrap = document.createElement('div');
        wrap.className = 'modal fade crm-sheet-modal';
        wrap.tabIndex = -1;
        wrap.setAttribute('aria-modal', 'true');
        wrap.setAttribute('role', 'dialog');
        var size = opts.size ? ' modal-' + opts.size : '';
        wrap.innerHTML =
            '<div class="modal-dialog modal-dialog-centered modal-dialog-scrollable' + size + '"><div class="modal-content">' +
            '<div class="modal-header"><h5 class="modal-title">' + CS.esc(opts.title || '') + '</h5>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>' +
            '<div class="modal-body"></div><div class="modal-footer"></div></div></div>';
        var bodyEl = wrap.querySelector('.modal-body');
        if (typeof opts.body === 'string') bodyEl.innerHTML = opts.body; else if (opts.body) bodyEl.appendChild(opts.body);
        var footer = wrap.querySelector('.modal-footer');
        var buttons = opts.buttons || [{ label: 'Close', cls: 'btn-secondary' }];
        if (!buttons.length) footer.remove();
        var modal;
        buttons.forEach(function (b) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn ' + (b.cls || 'btn-secondary');
            btn.textContent = b.label;
            btn.onclick = function () {
                var res = b.action ? b.action(wrap, btn) : undefined;
                if (res && typeof res.then === 'function') {
                    btn.disabled = true;
                    res.then(function (keep) { btn.disabled = false; if (keep !== false) modal.hide(); });
                } else if (res !== false) {
                    modal.hide();
                }
            };
            footer.appendChild(btn);
        });
        document.body.appendChild(wrap);
        modal = new bootstrap.Modal(wrap);
        wrap.addEventListener('shown.bs.modal', function () {
            var first = wrap.querySelector('[autofocus], .modal-body input:not([type=hidden]), .modal-body select, .modal-body textarea');
            if (first) { first.focus(); if (first.select) first.select(); }
            if (opts.onOpen) opts.onOpen(wrap);
        });
        wrap.addEventListener('hidden.bs.modal', function () {
            if (opts.onClose) opts.onClose();
            modal.dispose();
            wrap.remove();
        });
        // Enter in a single-line input presses the primary button.
        wrap.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type !== 'checkbox') {
                var primary = footer.querySelector('.btn-primary, .btn-danger');
                if (primary) { e.preventDefault(); primary.click(); }
            }
            e.stopPropagation();
        });
        modal.show();
        wrap.crmModal = modal;
        return wrap;
    };

    CS.confirm = function (message, opts) {
        opts = opts || {};
        return new Promise(function (resolve) {
            var answered = false;
            CS.dialog({
                title: opts.title || 'Please confirm',
                body: '<p class="mb-0">' + CS.esc(message) + '</p>',
                size: 'sm',
                buttons: [
                    { label: opts.cancel || 'Cancel', cls: 'btn-outline-secondary' },
                    { label: opts.ok || 'OK', cls: opts.danger ? 'btn-danger' : 'btn-primary', action: function () { answered = true; resolve(true); } },
                ],
                onClose: function () { if (!answered) resolve(false); },
            });
        });
    };

    CS.prompt = function (title, label, value, opts) {
        opts = opts || {};
        return new Promise(function (resolve) {
            var done = false;
            CS.dialog({
                title: title,
                size: 'sm',
                body: '<label class="form-label">' + CS.esc(label) + '</label>' +
                    '<input type="text" class="form-control" maxlength="' + (opts.maxlength || 200) + '" value="' + CS.esc(value || '') + '">',
                buttons: [
                    { label: 'Cancel', cls: 'btn-outline-secondary' },
                    {
                        label: opts.ok || 'OK', cls: 'btn-primary', action: function (m) {
                            var v = m.querySelector('input').value.trim();
                            if (!v && !opts.allowEmpty) { m.querySelector('input').classList.add('is-invalid'); return false; }
                            done = true; resolve(v);
                        },
                    },
                ],
                onClose: function () { if (!done) resolve(null); },
            });
        });
    };

    // ── Context / dropdown menus ────────────────────────────────────────
    /**
     * items: [{label, icon, hint, action, disabled, checked, divider, submenu:[...]}]
     * Shown at page coordinates (x, y) or under an anchor element.
     */
    var openMenu = null;
    CS.closeMenu = function () {
        if (openMenu) { openMenu.remove(); openMenu = null; document.removeEventListener('mousedown', outside, true); }
    };
    function outside(e) { if (openMenu && !openMenu.contains(e.target)) CS.closeMenu(); }
    function buildMenu(items) {
        var ul = document.createElement('div');
        ul.className = 'crm-sheet-menu';
        ul.setAttribute('role', 'menu');
        items.forEach(function (it) {
            if (!it) return;
            if (it.divider) { var hr = document.createElement('div'); hr.className = 'crm-sheet-menu-divider'; ul.appendChild(hr); return; }
            if (it.header) { var h = document.createElement('div'); h.className = 'crm-sheet-menu-header'; h.textContent = it.header; ul.appendChild(h); return; }
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'crm-sheet-menu-item';
            b.setAttribute('role', 'menuitem');
            b.disabled = !!it.disabled;
            b.innerHTML = '<span class="crm-sheet-menu-ico">' + (it.checked ? '<i class="fas fa-check"></i>' : (it.icon ? '<i class="' + CS.esc(it.icon) + '"></i>' : '')) + '</span>' +
                '<span class="crm-sheet-menu-label">' + (it.html || CS.esc(it.label)) + '</span>' +
                (it.hint ? '<span class="crm-sheet-menu-hint">' + CS.esc(it.hint) + '</span>' : '') +
                (it.submenu ? '<span class="crm-sheet-menu-hint"><i class="fas fa-caret-right"></i></span>' : '');
            if (it.submenu) {
                var sub = null;
                b.addEventListener('mouseenter', function () {
                    ul.querySelectorAll('.crm-sheet-menu.crm-sheet-sub').forEach(function (s) { s.remove(); });
                    sub = buildMenu(it.submenu);
                    sub.classList.add('crm-sheet-sub');
                    ul.appendChild(sub);
                    var r = b.getBoundingClientRect(), mr = ul.getBoundingClientRect();
                    sub.style.top = (r.top - mr.top - 4) + 'px';
                    sub.style.left = (mr.width - 4) + 'px';
                    var sr = sub.getBoundingClientRect();
                    if (sr.right > window.innerWidth) sub.style.left = (-sr.width + 4) + 'px';
                    if (sr.bottom > window.innerHeight) sub.style.top = Math.max(-mr.top, r.top - mr.top - (sr.bottom - window.innerHeight) - 8) + 'px';
                });
                b.onclick = function (e) { e.preventDefault(); b.dispatchEvent(new Event('mouseenter')); };
            } else {
                b.addEventListener('mouseenter', function () {
                    ul.querySelectorAll(':scope > .crm-sheet-menu.crm-sheet-sub').forEach(function (s) { s.remove(); });
                });
                b.onclick = function () {
                    CS.closeMenu();
                    if (it.action) it.action();
                    if (CS.afterMenuAction) CS.afterMenuAction();
                };
            }
            ul.appendChild(b);
        });
        return ul;
    }
    CS.menu = function (items, x, y, anchor) {
        CS.closeMenu();
        var el = buildMenu(items);
        el.classList.add('crm-sheet-menu-root');
        document.body.appendChild(el);
        if (anchor) {
            var r = anchor.getBoundingClientRect();
            x = r.left; y = r.bottom + 2;
        }
        var w = el.offsetWidth, h = el.offsetHeight;
        if (x + w > window.innerWidth - 4) x = Math.max(4, window.innerWidth - w - 4);
        if (y + h > window.innerHeight - 4) y = Math.max(4, (anchor ? anchor.getBoundingClientRect().top - h - 2 : window.innerHeight - h - 4));
        el.style.left = x + 'px';
        el.style.top = y + 'px';
        openMenu = el;
        setTimeout(function () { document.addEventListener('mousedown', outside, true); }, 0);
        el.addEventListener('keydown', function (e) {
            var btns = Array.prototype.slice.call(el.querySelectorAll(':scope > .crm-sheet-menu-item:not(:disabled)'));
            var i = btns.indexOf(document.activeElement);
            if (e.key === 'ArrowDown') { e.preventDefault(); (btns[i + 1] || btns[0]).focus(); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); (btns[i - 1] || btns[btns.length - 1]).focus(); }
            else if (e.key === 'Escape') { e.preventDefault(); CS.closeMenu(); }
            e.stopPropagation();
        });
        var first = el.querySelector('.crm-sheet-menu-item:not(:disabled)');
        if (first) first.focus({ preventScroll: true });
        return el;
    };
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') CS.closeMenu(); });
    window.addEventListener('blur', CS.closeMenu);

    // ── Popover (colour pickers etc.) ───────────────────────────────────
    CS.popover = function (anchor, content) {
        CS.closeMenu();
        var el = document.createElement('div');
        el.className = 'crm-sheet-menu crm-sheet-menu-root crm-sheet-popover';
        if (typeof content === 'string') el.innerHTML = content; else el.appendChild(content);
        document.body.appendChild(el);
        var r = anchor.getBoundingClientRect();
        var x = r.left, y = r.bottom + 2;
        if (x + el.offsetWidth > window.innerWidth - 4) x = window.innerWidth - el.offsetWidth - 4;
        el.style.left = Math.max(4, x) + 'px';
        el.style.top = y + 'px';
        openMenu = el;
        setTimeout(function () { document.addEventListener('mousedown', outside, true); }, 0);
        el.addEventListener('keydown', function (e) { if (e.key === 'Escape') CS.closeMenu(); e.stopPropagation(); });
        return el;
    };

    // ── Time ────────────────────────────────────────────────────────────
    CS.parseIso = function (iso) { return iso ? new Date(iso) : null; };
    CS.timeAgo = function (iso) {
        var d = CS.parseIso(iso);
        if (!d) return '';
        var s = Math.round((Date.now() - d.getTime()) / 1000);
        if (s < 45) return 'just now';
        if (s < 90) return '1 minute ago';
        if (s < 3600) return Math.round(s / 60) + ' minutes ago';
        if (s < 5400) return '1 hour ago';
        if (s < 86400) return Math.round(s / 3600) + ' hours ago';
        if (s < 172800) return 'yesterday';
        if (s < 604800) return Math.round(s / 86400) + ' days ago';
        return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
    };
    CS.dateTime = function (iso) {
        var d = CS.parseIso(iso);
        return d ? d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
    };

    CS.debounce = function (fn, ms) {
        var t = null;
        var wrapped = function () {
            var args = arguments, self = this;
            clearTimeout(t);
            t = setTimeout(function () { t = null; fn.apply(self, args); }, ms);
        };
        wrapped.cancel = function () { clearTimeout(t); t = null; };
        return wrapped;
    };

    CS.isMac = /Mac|iPhone|iPad/.test(navigator.platform || '');
    CS.mod = function (e) { return CS.isMac ? e.metaKey : e.ctrlKey; };
})();
