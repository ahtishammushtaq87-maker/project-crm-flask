/* Spreadsheet module - home page (list, search, create, import) and the
 * admin access page. */
(function () {
    'use strict';
    var CS = window.CrmSheet;
    var esc = CS.esc;

    function storage(key, value) {
        try {
            if (value === undefined) return window.localStorage.getItem('crmSheet.' + key);
            window.localStorage.setItem('crmSheet.' + key, value);
        } catch (e) { return null; }
        return null;
    }

    function Home(root) {
        this.root = root;
        this.isAdmin = root.dataset.admin === '1';
        this.state = { q: '', sort: storage('sort') || 'modified', scope: 'all', view: storage('view') || 'grid' };
        this.templates = [];
        this.bind();
        this.load();
        this.loadTemplates();
        if (/[?&]new=1/.test(window.location.search)) this.newDialog();
    }
    var H = Home.prototype;

    H.el = function (s) { return this.root.querySelector(s); };

    H.bind = function () {
        var self = this;
        var search = this.el('.crm-sheet-search input');
        search.addEventListener('input', CS.debounce(function () { self.state.q = search.value; self.load(); }, 250));
        search.addEventListener('keydown', function (e) { if (e.key === 'Escape') { search.value = ''; self.state.q = ''; self.load(); } });
        this.el('[data-new]').addEventListener('click', function () { self.newDialog(); });
        this.el('[data-import]').addEventListener('click', function () {
            CS.Dialogs.importFile({ onDone: function (d) { window.location.href = CS.base() + '/' + d.id; } });
        });
        var sortSel = this.el('[data-sort]');
        sortSel.value = this.state.sort;
        sortSel.addEventListener('change', function () { self.state.sort = sortSel.value; storage('sort', sortSel.value); self.load(); });
        this.root.querySelectorAll('[data-view]').forEach(function (b) {
            b.addEventListener('click', function () { self.state.view = b.dataset.view; storage('view', b.dataset.view); self.render(); });
        });
        this.root.querySelectorAll('[data-scope]').forEach(function (b) {
            b.addEventListener('click', function () { self.state.scope = b.dataset.scope; self.load(); });
        });
        this.el('.crm-sheet-results').addEventListener('click', function (e) { self.onClick(e); });
        this.el('.crm-sheet-recent').addEventListener('click', function (e) { self.onClick(e); });
        document.addEventListener('keydown', function (e) {
            if (e.key === '/' && document.activeElement && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); search.focus(); }
        });
    };

    H.load = function () {
        var self = this, s = this.state;
        this.root.querySelectorAll('[data-scope]').forEach(function (b) {
            var on = b.dataset.scope === s.scope;
            b.classList.toggle('crm-sheet-on', on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        var results = this.el('.crm-sheet-results');
        if (!this.items) results.innerHTML = '<div class="crm-sheet-cards">' + new Array(6).join('<div class="crm-sheet-skel" aria-hidden="true"></div>') + '</div><span class="visually-hidden">Loading spreadsheets…</span>';
        var token = this.loadToken = {};
        CS.api('GET', '/spreadsheets?q=' + encodeURIComponent(s.q) + '&sort=' + encodeURIComponent(s.sort) + '&scope=' + encodeURIComponent(s.scope)).then(function (res) {
            if (token !== self.loadToken) return;
            if (!res.ok) { results.innerHTML = '<div class="alert alert-danger">' + esc(CS.errorText(res, 'Could not load spreadsheets.')) + '</div>'; return; }
            self.items = res.data.items;
            if (s.scope === 'all' && !s.q) self.recent = res.data.recent;
            self.render();
        });
    };

    H.loadTemplates = function () {
        var self = this;
        CS.api('GET', '/templates').then(function (res) {
            if (!res.ok) return;
            self.templates = res.data.templates;
            self.el('.crm-sheet-templates').innerHTML = self.templates.map(function (t) {
                return '<button type="button" class="crm-sheet-template" data-template="' + esc(t.key) + '" title="' + esc(t.description) + '">' +
                    '<span class="crm-sheet-tpl-ico"><i class="fas ' + esc(t.icon) + '"></i></span><span class="crm-sheet-tpl-label">' + esc(t.label) + '</span></button>';
            }).join('');
            self.el('.crm-sheet-templates').querySelectorAll('[data-template]').forEach(function (b) {
                b.addEventListener('click', function () { self.newDialog(b.dataset.template); });
            });
        });
    };

    function roleChip(item) {
        return item.role ? '<span class="crm-sheet-rolechip crm-sheet-role-' + esc(item.role) + '">' + esc(item.role_label) + '</span>' : '';
    }
    function sharedText(item) {
        return item.shared_count ? 'Shared with ' + item.shared_count + ' user' + (item.shared_count > 1 ? 's' : '') : 'Not shared';
    }

    H.render = function () {
        var self = this, s = this.state, items = this.items || [];
        this.root.querySelectorAll('[data-view]').forEach(function (b) {
            var on = b.dataset.view === s.view;
            b.classList.toggle('active', on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        var recentWrap = this.el('.crm-sheet-recentwrap');
        var showRecent = s.scope === 'all' && !s.q && this.recent && this.recent.length && items.length > 4;
        recentWrap.style.display = showRecent ? '' : 'none';
        if (showRecent) this.el('.crm-sheet-recent').innerHTML = '<div class="crm-sheet-cards">' + this.recent.map(function (i) { return self.card(i, true); }).join('') + '</div>';
        this.el('.crm-sheet-templatewrap').style.display = s.scope === 'all' && !s.q ? '' : 'none';
        var results = this.el('.crm-sheet-results');
        var title = this.el('.crm-sheet-results-title');
        var labels = { all: 'All spreadsheets', mine: 'Owned by me', shared: 'Shared with me', favorites: 'Starred', admin_all: 'Every spreadsheet (administrator)', deleted: 'Deleted spreadsheets' };
        title.textContent = s.q ? 'Results for "' + s.q + '"' : labels[s.scope];
        if (!items.length) {
            results.innerHTML = s.q || s.scope !== 'all'
                ? '<div class="crm-sheet-emptystate"><i class="fas fa-magnifying-glass crm-sheet-emptyicon text-muted"></i><h5>No spreadsheets found</h5><p class="text-muted mb-0">' + (s.q ? 'Nothing matches your search. Try a different name, description or owner.' : 'Nothing here yet.') + '</p></div>'
                : '<div class="crm-sheet-emptystate"><i class="fas fa-table crm-sheet-emptyicon"></i><h5>No spreadsheets yet</h5><p class="text-muted">Create your first spreadsheet to start organising your CRM data.</p>' +
                  '<button type="button" class="btn btn-primary" data-empty-new><i class="fas fa-plus me-1"></i>Create spreadsheet</button></div>';
            var b = results.querySelector('[data-empty-new]');
            if (b) b.onclick = function () { self.newDialog(); };
            return;
        }
        if (s.view === 'list') {
            results.innerHTML = '<div class="crm-sheet-listview" role="table" aria-label="Spreadsheets"><div class="crm-sheet-listrow crm-sheet-listhead" role="row"><div></div><div>Name</div><div class="crm-sheet-hide-xs">Owner</div><div class="crm-sheet-hide-xs">Last modified</div><div class="crm-sheet-hide-xs">Access</div><div class="crm-sheet-hide-xs">Created</div><div></div></div>' +
                items.map(function (i) { return self.row(i); }).join('') + '</div>';
        } else {
            results.innerHTML = '<div class="crm-sheet-cards">' + items.map(function (i) { return self.card(i); }).join('') + '</div>';
        }
    };

    H.href = function (item) { return CS.base() + '/' + item.id; };
    H.actionsHtml = function (item) {
        return '<button type="button" class="crm-sheet-iconbtn" data-fav="' + item.id + '" aria-pressed="' + (item.favorite ? 'true' : 'false') + '" title="' + (item.favorite ? 'Unstar' : 'Star') + '" aria-label="' + (item.favorite ? 'Unstar ' : 'Star ') + esc(item.name) + '"><i class="' + (item.favorite ? 'fas' : 'far') + ' fa-star"></i></button>' +
            '<button type="button" class="crm-sheet-iconbtn" data-more="' + item.id + '" title="More actions" aria-label="More actions for ' + esc(item.name) + '"><i class="fas fa-ellipsis-vertical"></i></button>';
    };
    H.card = function (item, compact) {
        return '<div class="crm-sheet-card">' +
            (item.deleted ? '' : '') +
            '<span class="crm-sheet-card-thumb" aria-hidden="true"><i class="fas fa-table"></i></span>' +
            '<div class="crm-sheet-card-actions">' + this.actionsHtml(item) + '</div>' +
            '<div class="crm-sheet-card-body">' +
            (item.deleted ? '<span class="crm-sheet-card-name text-muted">' + esc(item.name) + '</span>' : '<a class="crm-sheet-card-name" href="' + this.href(item) + '" title="' + esc(item.name) + '">' + esc(item.name) + '</a>') +
            '<div class="crm-sheet-card-meta">' + (compact && item.last_opened_at ? 'Opened ' + esc(CS.timeAgo(item.last_opened_at)) : 'Modified ' + esc(CS.timeAgo(item.updated_at)) + ' by ' + esc(item.updated_by)) + '</div>' +
            '<div class="crm-sheet-card-meta">Owner: ' + esc(item.owner) + ' · ' + esc(sharedText(item)) + '</div>' +
            '<div class="mt-1">' + roleChip(item) + (item.deleted ? ' <span class="crm-sheet-rolechip crm-sheet-role-admin">Deleted</span>' : '') + '</div>' +
            '</div></div>';
    };
    H.row = function (item) {
        return '<div class="crm-sheet-listrow" role="row">' +
            '<div><i class="fas fa-table text-success"></i></div>' +
            '<div>' + (item.deleted ? '<span class="crm-sheet-card-name text-muted">' + esc(item.name) + '</span>' : '<a class="crm-sheet-card-name" href="' + this.href(item) + '">' + esc(item.name) + '</a>') +
            (item.description ? '<div class="small text-muted text-truncate">' + esc(item.description) + '</div>' : '') + '</div>' +
            '<div class="crm-sheet-hide-xs">' + esc(item.owner) + '</div>' +
            '<div class="crm-sheet-hide-xs" title="' + esc(CS.dateTime(item.updated_at)) + '">' + esc(CS.timeAgo(item.updated_at)) + '<div class="small text-muted">by ' + esc(item.updated_by) + '</div></div>' +
            '<div class="crm-sheet-hide-xs">' + roleChip(item) + '<div class="small text-muted">' + esc(sharedText(item)) + '</div></div>' +
            '<div class="crm-sheet-hide-xs small text-muted">' + esc(CS.dateTime(item.created_at).split(',').slice(0, 2).join(',')) + '</div>' +
            '<div class="d-flex gap-1 justify-content-end">' + this.actionsHtml(item) + '</div></div>';
    };

    H.find = function (id) {
        var all = (this.items || []).concat(this.recent || []);
        for (var i = 0; i < all.length; i++) if (String(all[i].id) === String(id)) return all[i];
        return null;
    };
    H.onClick = function (e) {
        var self = this;
        var fav = e.target.closest('[data-fav]'), more = e.target.closest('[data-more]');
        if (fav) {
            e.preventDefault();
            var item = this.find(fav.dataset.fav);
            CS.api('POST', '/spreadsheets/' + item.id + '/favorite', { favorite: !item.favorite }).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                (self.items || []).concat(self.recent || []).forEach(function (i) { if (i.id === item.id) i.favorite = res.data.favorite; });
                if (self.state.scope === 'favorites') self.load(); else self.render();
            });
        } else if (more) {
            e.preventDefault();
            this.moreMenu(this.find(more.dataset.more), more);
        }
    };

    H.moreMenu = function (item, anchor) {
        var self = this;
        var canManage = ['owner', 'admin', 'manager'].indexOf(item.role) >= 0;
        var canDelete = ['owner', 'admin'].indexOf(item.role) >= 0;
        var items;
        if (item.deleted) {
            items = [{ label: 'Restore', icon: 'fas fa-rotate-left', action: function () {
                CS.api('POST', '/spreadsheets/' + item.id + '/restore').then(function (res) {
                    if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                    CS.toast('Restored.', 'success'); self.load();
                });
            } }];
        } else {
            items = [
                { label: 'Open', icon: 'fas fa-up-right-from-square', action: function () { window.location.href = self.href(item); } },
                { label: 'Open in new tab', icon: 'fas fa-arrow-up-right-from-square', action: function () { window.open(self.href(item), '_blank'); } },
                { divider: true },
                { label: 'Rename', icon: 'fas fa-pen', disabled: !canManage, action: function () { self.rename(item); } },
                { label: 'Make a copy', icon: 'fas fa-copy', action: function () { self.duplicate(item); } },
                { label: canManage ? 'Share' : 'People with access', icon: 'fas fa-user-plus', action: function () { CS.Dialogs.share(null, item.id, { name: item.name, onChange: function () { self.load(); } }); } },
                { divider: true },
                { label: 'Delete', icon: 'fas fa-trash', disabled: !canDelete, action: function () { self.remove(item); } },
            ];
        }
        CS.menu(items, 0, 0, anchor);
    };
    H.rename = function (item) {
        var self = this;
        CS.prompt('Rename spreadsheet', 'Name', item.name, { ok: 'Rename' }).then(function (name) {
            if (!name || name === item.name) return;
            CS.api('PATCH', '/spreadsheets/' + item.id, { name: name }).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                CS.toast('Renamed.', 'success'); self.load();
            });
        });
    };
    H.duplicate = function (item) {
        var self = this;
        CS.prompt('Make a copy', 'Name', 'Copy of ' + item.name, { ok: 'Make a copy' }).then(function (name) {
            if (!name) return;
            CS.api('POST', '/spreadsheets/' + item.id + '/duplicate', { name: name }).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                CS.toast('Copy created.', 'success'); self.load();
            });
        });
    };
    H.remove = function (item) {
        var self = this;
        CS.confirm('Delete "' + item.name + '"? People it is shared with will lose access. An administrator can restore it.', { ok: 'Delete', danger: true, title: 'Delete spreadsheet' }).then(function (ok) {
            if (!ok) return;
            CS.api('DELETE', '/spreadsheets/' + item.id).then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                CS.toast('Spreadsheet deleted.', 'success'); self.load();
            });
        });
    };

    H.newDialog = function (template) {
        var tpls = this.templates.length ? this.templates : [{ key: 'blank', label: 'Blank spreadsheet', icon: 'fa-file', description: 'Start from an empty grid.' }];
        var chosen = template || 'blank';
        var body =
            '<div class="mb-3"><label class="form-label fw-semibold" for="crmNewName">Spreadsheet name</label>' +
            '<input type="text" class="form-control" id="crmNewName" maxlength="200" placeholder="e.g. Monthly Sales" autofocus></div>' +
            '<div class="mb-3"><label class="form-label" for="crmNewDesc">Description <span class="text-muted">(optional)</span></label>' +
            '<textarea class="form-control" id="crmNewDesc" rows="2" maxlength="2000"></textarea></div>' +
            '<div><div class="form-label">Start with</div><div class="crm-sheet-tplpick">' + tpls.map(function (t) {
                return '<label><input type="radio" class="form-check-input" name="crmNewTpl" value="' + esc(t.key) + '"' + (t.key === chosen ? ' checked' : '') + '>' +
                    '<span><i class="fas ' + esc(t.icon) + ' text-success me-1"></i><b>' + esc(t.label) + '</b><br><small class="text-muted">' + esc(t.description) + '</small></span></label>';
            }).join('') + '</div></div>';
        var dlg = CS.dialog({
            title: 'New spreadsheet', body: body, size: 'lg',
            buttons: [
                { label: 'Cancel', cls: 'btn-outline-secondary' },
                {
                    label: 'Create', cls: 'btn-primary', action: function (el) {
                        var nameEl = el.querySelector('#crmNewName');
                        var name = nameEl.value.trim();
                        var tpl = el.querySelector('input[name=crmNewTpl]:checked').value;
                        if (!name) {
                            var t = tpls.filter(function (x) { return x.key === tpl; })[0];
                            name = tpl === 'blank' ? 'Untitled spreadsheet' : t.label;
                        }
                        return CS.api('POST', '/spreadsheets', { name: name, description: el.querySelector('#crmNewDesc').value, template: tpl }).then(function (res) {
                            if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return false; }
                            window.location.href = CS.base() + '/' + res.data.id;
                        });
                    },
                },
            ],
        });
        void dlg;
    };

    // ── Admin access page ───────────────────────────────────────────────
    function Admin(root) {
        this.root = root;
        var self = this;
        var search = root.querySelector('.crm-sheet-search input');
        search.addEventListener('input', CS.debounce(function () { self.load(search.value); }, 250));
        root.addEventListener('click', function (e) {
            var m = e.target.closest('[data-manage]');
            if (m) CS.Dialogs.share(null, +m.dataset.manage, { name: m.dataset.name, onChange: function () { self.load(search.value); } });
            var r = e.target.closest('[data-restore]');
            if (r) CS.api('POST', '/spreadsheets/' + r.dataset.restore + '/restore').then(function (res) {
                if (!res.ok) { CS.toast(CS.errorText(res), 'error'); return; }
                CS.toast('Restored.', 'success'); self.load(search.value);
            });
        });
        root.querySelector('[data-show-deleted]').addEventListener('change', function () { self.load(search.value); });
        this.load('');
    }
    Admin.prototype.load = function (q) {
        var root = this.root, tbody = root.querySelector('tbody');
        var deleted = root.querySelector('[data-show-deleted]').checked;
        tbody.innerHTML = '<tr><td colspan="6" class="text-muted">Loading…</td></tr>';
        CS.api('GET', '/spreadsheets?scope=' + (deleted ? 'deleted' : 'admin_all') + '&sort=modified&q=' + encodeURIComponent(q || '')).then(function (res) {
            if (!res.ok) { tbody.innerHTML = '<tr><td colspan="6" class="text-danger">' + esc(CS.errorText(res)) + '</td></tr>'; return; }
            var items = res.data.items;
            if (!items.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-muted">No spreadsheets.</td></tr>'; return; }
            tbody.innerHTML = items.map(function (i) {
                return '<tr><td>' + (i.deleted ? esc(i.name) : '<a href="' + CS.base() + '/' + i.id + '">' + esc(i.name) + '</a>') + '</td>' +
                    '<td>' + esc(i.owner) + '</td><td>' + esc(sharedText(i)) + '</td>' +
                    '<td title="' + esc(CS.dateTime(i.updated_at)) + '">' + esc(CS.timeAgo(i.updated_at)) + ' <span class="text-muted small">by ' + esc(i.updated_by) + '</span></td>' +
                    '<td>' + esc(CS.dateTime(i.created_at)) + '</td>' +
                    '<td class="text-end text-nowrap">' + (i.deleted
                        ? '<button type="button" class="btn btn-sm btn-outline-success" data-restore="' + i.id + '"><i class="fas fa-rotate-left me-1"></i>Restore</button>'
                        : '<button type="button" class="btn btn-sm btn-outline-primary" data-manage="' + i.id + '" data-name="' + esc(i.name) + '"><i class="fas fa-user-shield me-1"></i>Manage access</button>') + '</td></tr>';
            }).join('');
        });
    };

    document.addEventListener('DOMContentLoaded', function () {
        var home = document.querySelector('.crm-sheet-home[data-page="home"]');
        if (home) window.CrmSheetHome = new Home(home);
        var admin = document.querySelector('.crm-sheet-home[data-page="admin"]');
        if (admin) window.CrmSheetAdmin = new Admin(admin);
    });
})();
