/* WhatsApp inbox. Talks only to /whatsapp/api/* (session login + CSRF header).
   Everything from the server is inserted as text (esc()) - never as raw HTML. */
(function () {
    'use strict';
    const root = document.getElementById('waInbox');
    if (!root) return;

    const U = window.WA_URLS;
    const canReply = root.dataset.canReply === '1';
    const maxMb = parseInt(root.dataset.maxMb || '16', 10);
    const POLL_MS = 5000;
    const $ = (id) => document.getElementById(id);

    const state = {
        filter: 'all', q: '', tag: '', from: '', to: '', page: 1, hasMore: false,
        convs: new Map(), openId: null, conv: null, lastMsgId: 0, firstMsgId: null, hasOlder: false,
        since: null, replyTo: null, file: null, sending: false, pollTimer: null, loadingOlder: false,
        firstUnreadId: null, msgWamids: {},
    };

    // ── helpers ──────────────────────────────────────────────────────────
    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }
    function fmtTime(iso) {
        if (!iso) return '';
        const d = new Date(iso), now = new Date();
        if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        const y = new Date(now); y.setDate(now.getDate() - 1);
        if (d.toDateString() === y.toDateString()) return 'Yesterday';
        if ((now - d) < 6 * 864e5) return d.toLocaleDateString([], { weekday: 'short' });
        return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
    }
    function dayLabel(iso) {
        const d = new Date(iso), now = new Date();
        if (d.toDateString() === now.toDateString()) return 'Today';
        const y = new Date(now); y.setDate(now.getDate() - 1);
        if (d.toDateString() === y.toDateString()) return 'Yesterday';
        return d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    function toast(msg, isErr) {
        const t = document.createElement('div');
        t.className = 'wa-toast' + (isErr ? ' wa-toast-err' : '');
        t.setAttribute('role', isErr ? 'alert' : 'status');
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), isErr ? 7000 : 3000);
    }
    async function api(url, opts = {}) {
        const o = Object.assign({ credentials: 'same-origin', headers: {} }, opts);
        o.headers = Object.assign({ 'X-CSRFToken': window.WA_CSRF, 'Accept': 'application/json' }, o.headers);
        if (o.json !== undefined) {
            o.body = JSON.stringify(o.json);
            o.headers['Content-Type'] = 'application/json';
            delete o.json;
        }
        const r = await fetch(url, o);
        let data = null;
        try { data = await r.json(); } catch (e) { data = null; }
        if (!r.ok && !(data && data.message)) {
            const err = new Error((data && data.error) || (r.status === 403 ? 'You do not have permission for this.' :
                r.status === 400 ? 'Request rejected - reload the page and try again.' : 'Server error (' + r.status + ').'));
            err.status = r.status; err.data = data;
            throw err;
        }
        return data || {};
    }
    function convUrl(id, suffix) { return U.conversation + id + (suffix || ''); }

    // ── conversation list ────────────────────────────────────────────────
    function listParams() {
        const p = new URLSearchParams({ filter: state.filter, page: state.page });
        if (state.q) p.set('q', state.q);
        if (state.tag) p.set('tag', state.tag);
        if (state.from) p.set('from', state.from);
        if (state.to) p.set('to', state.to);
        return p;
    }
    async function loadList(reset) {
        if (reset) { state.page = 1; state.convs.clear(); }
        try {
            const data = await api(U.conversations + '?' + listParams());
            data.items.forEach((c) => state.convs.set(c.id, c));
            state.hasMore = data.has_more;
            renderList();
        } catch (e) {
            $('waConvList').innerHTML = '<div class="wa-empty"><i class="fas fa-triangle-exclamation"></i>' + esc(e.message) + '</div>';
        }
    }
    function sortedConvs() {
        return Array.from(state.convs.values()).sort((a, b) => (b.last_at || '').localeCompare(a.last_at || '') || b.id - a.id);
    }
    function convRow(c) {
        const tags = c.tags.slice(0, 2).map((t) => '<span class="wa-badge">' + esc(t) + '</span>').join('');
        return '<button type="button" class="wa-conv' + (c.unread ? ' wa-unread' : '') + (c.id === state.openId ? ' wa-active' : '') +
            '" data-id="' + c.id + '" aria-label="' + esc(c.name) + (c.unread ? ', ' + c.unread + ' unread' : '') + '">' +
            '<span class="wa-avatar">' + esc(c.initials) + '</span>' +
            '<span class="wa-conv-main"><span class="wa-conv-top"><span class="wa-conv-name">' +
            (c.starred ? '<i class="fas fa-star" style="color:#e0a800;font-size:.75em"></i> ' : '') + esc(c.name) + '</span>' +
            '<span class="wa-conv-time">' + esc(fmtTime(c.last_at)) + '</span></span>' +
            '<span class="wa-conv-top"><span class="wa-conv-preview">' + (c.direction === 'out' ? '<i class="fas fa-reply fa-flip-horizontal" style="font-size:.7em"></i> ' : '') +
            esc(c.preview) + '</span>' + (c.unread ? '<span class="wa-unread-count">' + c.unread + '</span>' : '') + '</span>' +
            '<span class="wa-conv-meta">' +
            (c.status !== 'open' ? '<span class="wa-badge ' + (c.status === 'pending' ? 'wa-badge-amber' : '') + '">' + esc(c.status) + '</span>' : '') +
            (c.assigned_to ? '<span class="wa-badge"><i class="fas fa-user" style="font-size:.8em"></i> ' + esc(c.assigned_to) + '</span>' : '') +
            (c.opted_out ? '<span class="wa-badge wa-badge-red">opted out</span>' : '') + tags + '</span></span></button>';
    }
    function renderList() {
        const list = $('waConvList');
        const items = sortedConvs();
        if (!items.length) {
            list.innerHTML = '<div class="wa-empty"><i class="far fa-comments"></i>No conversations match.</div>';
            return;
        }
        list.innerHTML = items.map(convRow).join('') +
            (state.hasMore ? '<div class="p-2 text-center"><button class="wa-btn wa-btn-sm" id="waMore">Load more</button></div>' : '');
    }
    $('waConvList').addEventListener('click', (e) => {
        if (e.target.id === 'waMore') { state.page += 1; loadList(false); return; }
        const row = e.target.closest('.wa-conv');
        if (row) openConversation(parseInt(row.dataset.id, 10));
    });
    document.querySelectorAll('.wa-chip[data-filter]').forEach((b) => b.addEventListener('click', () => {
        document.querySelectorAll('.wa-chip[data-filter]').forEach((x) => x.classList.remove('wa-active'));
        b.classList.add('wa-active');
        state.filter = b.dataset.filter;
        loadList(true);
    }));
    let searchTimer;
    $('waSearch').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { state.q = e.target.value.trim(); loadList(true); }, 300);
    });
    $('waTagFilter').addEventListener('change', (e) => { state.tag = e.target.value; loadList(true); });
    $('waFrom').addEventListener('change', (e) => { state.from = e.target.value; loadList(true); });
    $('waTo').addEventListener('change', (e) => { state.to = e.target.value; loadList(true); });

    // ── open conversation ────────────────────────────────────────────────
    async function openConversation(id) {
        state.openId = id; state.lastMsgId = 0; state.firstMsgId = null; state.replyTo = null; state.firstUnreadId = null;
        clearAttachment(); setReply(null);
        root.classList.add('wa-chat-open');
        $('waPlaceholder').classList.add('d-none');
        $('waChat').classList.remove('d-none');
        $('waThread').innerHTML = '<div class="wa-empty"><span class="wa-spinner"></span></div>';
        history.replaceState(null, '', '?c=' + id);
        renderList();
        try {
            const [info, msgs] = await Promise.all([api(convUrl(id)), api(convUrl(id, '/messages'))]);
            if (state.openId !== id) return;
            state.conv = info;
            const c = state.convs.get(id);
            if (c && c.unread) state.firstUnreadId = 'pending:' + c.unread;
            state.convs.set(id, Object.assign(info.conversation, { unread: 0 }));
            renderHeader(); renderInfo(); renderWindow(info.window);
            $('waThread').innerHTML = '';
            state.hasOlder = msgs.has_more;
            appendMessages(msgs.items, false);
            renderList();
            if (canReply) $('waText') && $('waText').focus();
        } catch (e) {
            $('waThread').innerHTML = '<div class="wa-empty"><i class="fas fa-triangle-exclamation"></i>' + esc(e.message) + '</div>';
        }
    }
    function renderHeader() {
        const c = state.conv.conversation;
        $('waChatAvatar').textContent = c.initials;
        $('waChatName').textContent = c.name;
        $('waChatPhone').textContent = c.phone + (c.assigned_to ? ' · ' + c.assigned_to : '');
        $('waStatus').value = c.status;
        $('waStatus').disabled = !state.conv.can.reply;
        const star = $('waStar');
        star.innerHTML = c.starred ? '<i class="fas fa-star" style="color:#e0a800"></i>' : '<i class="far fa-star"></i>';
        star.setAttribute('aria-pressed', c.starred ? 'true' : 'false');
        if ($('waAssign')) $('waAssign').value = c.assigned_to_id || '';
    }
    function renderWindow(w) {
        const bar = $('waWindow');
        state.windowOpen = !!(w && w.open);
        if (w && w.open) {
            const left = Math.max(0, (new Date(w.expires_at) - new Date()) / 36e5);
            bar.className = 'wa-window-bar wa-window-open';
            bar.innerHTML = '<i class="fas fa-clock"></i> Customer service window open — free-form replies allowed for ' +
                (left >= 1 ? Math.floor(left) + ' h ' : '') + Math.round((left % 1) * 60) + ' min more.';
        } else {
            bar.className = 'wa-window-bar wa-window-closed';
            bar.innerHTML = '<i class="fas fa-lock"></i> ' + (w && w.last_inbound_at ? 'The 24-hour window closed ' + esc(fmtTime(w.expires_at)) + '.' :
                'The customer has not messaged yet.') + ' Only approved templates can be sent.';
        }
        const text = $('waText');
        if (text) {
            text.disabled = !state.windowOpen;
            text.placeholder = state.windowOpen ? 'Type a message' : 'Window closed — use a template';
            $('waSend').disabled = !state.windowOpen;
            document.querySelector('label[aria-label="Attach file"]').setAttribute('aria-disabled', state.windowOpen ? 'false' : 'true');
            $('waFile').disabled = !state.windowOpen;
            $('waEmojiBtn').disabled = !state.windowOpen;
        }
    }
    function renderInfo() {
        const d = state.conv, ct = d.contact, c = d.conversation;
        const consent = { opted_in: '<span class="wa-badge wa-badge-green">Opted in</span>', opted_out: '<span class="wa-badge wa-badge-red">Opted out</span>',
            unknown: '<span class="wa-badge">Unknown</span>' }[ct.consent];
        let html = '<div class="wa-info-section text-center"><span class="wa-avatar mx-auto mb-2" style="width:54px;height:54px;font-size:1.1rem">' + esc(c.initials) + '</span>' +
            '<div class="fw-bold">' + esc(c.name) + '</div><div class="wa-small wa-muted">' + esc(ct.phone) + '</div>' +
            (ct.edit_url ? '<a class="wa-btn wa-btn-sm mt-2" href="' + esc(ct.edit_url) + '"><i class="fas fa-pen"></i> Edit contact</a>' : '') + '</div>';
        html += '<div class="wa-info-section"><h4>Contact</h4><dl class="wa-kv">' +
            '<dt>WhatsApp name</dt><dd>' + esc(ct.profile_name || '—') + '</dd>' +
            '<dt>Email</dt><dd>' + esc(ct.email || '—') + '</dd>' +
            '<dt>Status</dt><dd>' + esc(c.status) + '</dd>' +
            '<dt>Assigned</dt><dd>' + esc(c.assigned_to || 'Unassigned') + '</dd>' +
            '<dt>Last inbound</dt><dd>' + esc(ct.last_inbound_at ? new Date(ct.last_inbound_at).toLocaleString() : '—') + '</dd>' +
            '<dt>Window</dt><dd>' + (d.window.open ? '<span class="wa-badge wa-badge-green">Open</span>' : '<span class="wa-badge wa-badge-amber">Closed</span>') + '</dd>' +
            '<dt>Consent</dt><dd>' + consent + (ct.consent_source ? '<div class="wa-small wa-muted">' + esc(ct.consent_source) + '</div>' : '') + '</dd>' +
            '</dl></div>';
        html += '<div class="wa-info-section"><h4>CRM customer</h4>' + (ct.customer ?
            '<div class="fw-semibold">' + esc(ct.customer.name) + '</div>' + (ct.customer.company ? '<div class="wa-small wa-muted">' + esc(ct.customer.company) + '</div>' : '') +
            (ct.customer.url ? '<a class="wa-btn wa-btn-sm mt-2" href="' + esc(ct.customer.url) + '"><i class="fas fa-user"></i> Open profile</a>' : '')
            : '<div class="wa-small wa-muted">Not linked to a CRM customer.' + (ct.edit_url ? ' Link one from <a href="' + esc(ct.edit_url) + '">Edit contact</a>.' : '') + '</div>') + '</div>';
        html += '<div class="wa-info-section"><h4>Tags</h4><div class="d-flex flex-wrap gap-1 mb-2" id="waTags">' +
            (ct.tags.length ? ct.tags.map((t) => '<span class="wa-badge">' + esc(t) + '</span>').join('') : '<span class="wa-small wa-muted">No tags</span>') + '</div>' +
            (d.can.reply || d.can.contacts ? '<form id="waTagForm" class="d-flex gap-1"><input class="wa-input" id="waTagInput" placeholder="tag1, tag2" value="' + esc(ct.tags.join(', ')) + '" aria-label="Tags">' +
                '<button class="wa-btn wa-btn-sm">Save</button></form>' : '') + '</div>';
        html += '<div class="wa-info-section"><h4>Internal notes</h4><form id="waNoteForm" class="mb-2"><textarea class="wa-input" id="waNoteInput" rows="2" placeholder="Visible to staff only" aria-label="New note"></textarea>' +
            '<button class="wa-btn wa-btn-sm mt-1">Add note</button></form><div id="waNotes">' +
            d.notes.map((n) => '<div class="wa-note">' + esc(n.body) + '<small>' + esc(n.user) + ' · ' + esc(new Date(n.at).toLocaleString()) + '</small></div>').join('') + '</div></div>';
        $('waInfo').innerHTML = html;
        const tf = $('waTagForm');
        if (tf) tf.addEventListener('submit', async (e) => {
            e.preventDefault();
            await update({ tags: $('waTagInput').value.split(',') }, 'Tags saved.');
        });
        $('waNoteForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = $('waNoteInput').value.trim();
            if (!body) return;
            try {
                const r = await api(convUrl(state.openId, '/notes'), { method: 'POST', json: { body } });
                state.conv.notes.unshift(r.note); renderInfo();
            } catch (err) { toast(err.message, true); }
        });
    }

    // ── messages ─────────────────────────────────────────────────────────
    const TICKS = {
        sending: '<i class="far fa-clock" title="Sending"></i>', accepted: '<i class="fas fa-check" title="Accepted by WhatsApp"></i>',
        sent: '<i class="fas fa-check" title="Sent"></i>', delivered: '<i class="fas fa-check-double" title="Delivered"></i>',
        read: '<i class="fas fa-check-double wa-tick-read" title="Read"></i>', failed: '<i class="fas fa-circle-exclamation" style="color:#c63c3c" title="Failed"></i>',
        unknown: '<i class="fas fa-circle-question" style="color:#b7791f" title="Outcome unknown"></i>',
    };
    function mediaHtml(m) {
        if (!m.media) return '';
        const url = esc(m.media.url);
        if (m.type === 'image' || m.type === 'sticker') return '<div class="wa-bubble-media"><a href="' + url + '" target="_blank" rel="noopener"><img src="' + url + '" alt="Image" loading="lazy"></a></div>';
        if (m.type === 'video') return '<div class="wa-bubble-media"><video src="' + url + '" controls preload="none"></video></div>';
        if (m.type === 'audio' || m.type === 'voice') return '<div class="wa-bubble-media"><audio src="' + url + '" controls preload="none"></audio></div>';
        return '<a class="wa-doc" href="' + url + '?download=1"><i class="fas fa-file-lines fa-lg"></i><span>' + esc(m.media.filename || 'Document') +
            (m.media.size ? '<br><small class="wa-muted">' + Math.ceil(m.media.size / 1024) + ' KB</small>' : '') + '</span></a>';
    }
    function bodyHtml(m) {
        if (m.type === 'location' && m.extra && m.extra.latitude) {
            const q = encodeURIComponent(m.extra.latitude + ',' + m.extra.longitude);
            return '<div class="wa-bubble-text"><i class="fas fa-location-dot"></i> ' + esc(m.body) +
                ' <a href="https://www.google.com/maps?q=' + q + '" target="_blank" rel="noopener noreferrer">Open map</a></div>';
        }
        if (m.type === 'reaction') return '<div class="wa-bubble-text">Reacted ' + esc(m.body) + '</div>';
        if (m.type === 'template') return '<div class="wa-small wa-muted"><i class="fas fa-file-lines"></i> Template: ' + esc(m.template) + '</div>' +
            '<div class="wa-bubble-text">' + esc(m.body) + '</div>';
        return m.body ? '<div class="wa-bubble-text">' + esc(m.body) + '</div>' : '';
    }
    function msgHtml(m) {
        const out = m.direction === 'out';
        const err = m.error ? '<div class="wa-bubble-error"><strong>' + esc(m.error.title || 'Failed') + '</strong>' +
            (m.error.code ? ' (' + esc(m.error.code) + ')' : '') + (m.error.detail ? '<br>' + esc(m.error.detail) : '') + '</div>' : '';
        const actions = '<span class="wa-bubble-actions">' + (canReply && m.wamid ? '<button type="button" data-act="reply" title="Reply">Reply</button>' : '') +
            (canReply && out && (m.status === 'failed' || m.status === 'unknown') ? '<button type="button" data-act="retry">Retry</button>' : '') + '</span>';
        return '<div class="wa-msg ' + (out ? 'wa-msg-out' : 'wa-msg-in') + (m.status === 'failed' ? ' wa-msg-failed' : '') + '" data-id="' + m.id + '" data-ts="' + esc(m.ts) + '">' +
            '<div class="wa-bubble">' + actions +
            (out && m.sent_by ? '<div class="wa-bubble-by">' + esc(m.sent_by) + '</div>' : '') +
            (m.quoted ? '<div class="wa-bubble-quote">' + esc(m.quoted.body) + '</div>' : (m.context_wamid && m.type !== 'reaction' ? '<div class="wa-bubble-quote wa-muted">Reply to an earlier message</div>' : '')) +
            mediaHtml(m) + bodyHtml(m) + err +
            '<div class="wa-bubble-meta"><span>' + esc(new Date(m.ts).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })) + '</span>' +
            (out ? '<span class="wa-tick">' + (TICKS[m.status] || '') + '</span>' : '') + '</div></div></div>';
    }
    function appendMessages(items, prepend) {
        // wamids are kept here (for quoted replies), not in the DOM
        items.forEach((m) => { if (m.wamid) state.msgWamids[m.id] = m.wamid; });
        const thread = $('waThread');
        const atBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 80;
        const prevHeight = thread.scrollHeight;
        let html = '';
        let lastDay = prepend ? null : (thread.dataset.lastDay || null);
        const unread = state.firstUnreadId && state.firstUnreadId.startsWith('pending:') ? parseInt(state.firstUnreadId.split(':')[1], 10) : 0;
        const inbound = items.filter((m) => m.direction === 'in');
        const markerId = unread && !prepend && inbound.length >= unread ? inbound[inbound.length - unread].id : null;
        items.forEach((m) => {
            const existing = thread.querySelector('.wa-msg[data-id="' + m.id + '"]');
            if (existing) { existing.outerHTML = msgHtml(m); return; }
            const day = new Date(m.ts).toDateString();
            if (day !== lastDay) { html += '<div class="wa-day"><span>' + esc(dayLabel(m.ts)) + '</span></div>'; lastDay = day; }
            if (m.id === markerId) html += '<div class="wa-new-marker"><span>New messages</span></div>';
            html += msgHtml(m);
            if (m.id > state.lastMsgId) state.lastMsgId = m.id;
            if (state.firstMsgId === null || m.id < state.firstMsgId) state.firstMsgId = m.id;
        });
        if (markerId) state.firstUnreadId = null;
        if (prepend) {
            const older = thread.querySelector('.wa-older');
            if (older) older.remove();
            thread.insertAdjacentHTML('afterbegin', html);
            thread.scrollTop = thread.scrollHeight - prevHeight;
        } else {
            thread.insertAdjacentHTML('beforeend', html);
            thread.dataset.lastDay = lastDay || '';
            if (atBottom || !prepend) thread.scrollTop = thread.scrollHeight;
        }
        if (state.hasOlder && !thread.querySelector('.wa-older')) {
            thread.insertAdjacentHTML('afterbegin', '<div class="text-center wa-older my-2"><button class="wa-btn wa-btn-sm" data-act="older">Load earlier messages</button></div>');
        }
    }
    async function loadOlder() {
        if (state.loadingOlder || !state.firstMsgId) return;
        state.loadingOlder = true;
        try {
            const data = await api(convUrl(state.openId, '/messages?before=' + state.firstMsgId));
            state.hasOlder = data.has_more;
            appendMessages(data.items, true);
        } catch (e) { toast(e.message, true); }
        state.loadingOlder = false;
    }
    $('waThread').addEventListener('click', async (e) => {
        const btn = e.target.closest('button[data-act]');
        if (!btn) return;
        if (btn.dataset.act === 'older') return loadOlder();
        const row = btn.closest('.wa-msg');
        const id = parseInt(row.dataset.id, 10);
        if (btn.dataset.act === 'reply') {
            const text = row.querySelector('.wa-bubble-text');
            setReply({ id, wamid: state.msgWamids[id], text: text ? text.textContent : '[media]' });
            $('waText') && $('waText').focus();
        } else if (btn.dataset.act === 'retry') {
            const uncertain = row.querySelector('.fa-circle-question');
            if (uncertain && !confirm('WhatsApp may already have delivered this message. Send it again anyway?')) return;
            if (!uncertain && !confirm('Send this message again?')) return;
            try {
                const r = await api(U.retry + id + '/retry', { method: 'POST', json: { confirm: !!uncertain } });
                appendMessages([r.message], false);
                if (!r.ok) toast(r.error || 'Not sent', true);
            } catch (err) { toast(err.message, true); }
        }
    });
    $('waThread').addEventListener('scroll', () => { if ($('waThread').scrollTop < 40 && state.hasOlder) loadOlder(); });

    // ── conversation actions ─────────────────────────────────────────────
    async function update(payload, okMsg) {
        try {
            const r = await api(convUrl(state.openId, '/update'), { method: 'POST', json: payload });
            if (r.removed) {
                toast('Conversation assigned — it is no longer in your list.');
                state.convs.delete(state.openId); state.openId = null;
                $('waChat').classList.add('d-none'); $('waPlaceholder').classList.remove('d-none');
                root.classList.remove('wa-chat-open'); renderList();
                return;
            }
            state.conv.conversation = r.conversation;
            if (payload.tags) state.conv.contact.tags = r.conversation.tags;
            state.convs.set(r.conversation.id, r.conversation);
            renderHeader(); renderInfo(); renderList();
            if (okMsg) toast(okMsg);
        } catch (e) { toast(e.message, true); renderHeader(); }
    }
    $('waStatus').addEventListener('change', (e) => update({ status: e.target.value }, 'Status updated.'));
    $('waStar').addEventListener('click', () => update({ starred: !state.conv.conversation.starred }));
    if ($('waAssign')) $('waAssign').addEventListener('change', (e) => update({ assigned_to_id: e.target.value || null }, 'Assignment updated.'));
    $('waInfoToggle').addEventListener('click', () => root.classList.toggle('wa-show-info'));
    $('waBack').addEventListener('click', () => { root.classList.remove('wa-chat-open'); });

    // ── composer ─────────────────────────────────────────────────────────
    function setReply(r) {
        state.replyTo = r;
        if (!$('waReplyTo')) return;
        $('waReplyTo').classList.toggle('d-none', !r);
        $('waReplyText').textContent = r ? 'Replying to: ' + r.text : '';
    }
    function clearAttachment() {
        state.file = null;
        if (!$('waFile')) return;
        $('waFile').value = '';
        $('waAttachPreview').classList.add('d-none');
    }
    if (canReply && $('waComposer')) {
        const text = $('waText');
        const autosize = () => { text.style.height = 'auto'; text.style.height = Math.min(160, text.scrollHeight) + 'px'; };
        text.addEventListener('input', autosize);
        text.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
        });
        $('waSend').addEventListener('click', send);
        $('waReplyCancel').addEventListener('click', () => setReply(null));
        $('waAttachCancel').addEventListener('click', clearAttachment);
        $('waFile').addEventListener('change', (e) => {
            const f = e.target.files[0];
            if (!f) return;
            if (f.size > maxMb * 1024 * 1024) { toast('Files can be at most ' + maxMb + ' MB.', true); clearAttachment(); return; }
            state.file = f;
            $('waAttachName').textContent = f.name + ' (' + Math.ceil(f.size / 1024) + ' KB) — the message text becomes the caption';
            $('waAttachPreview').classList.remove('d-none');
            text.focus();
        });

        // Emoji picker (built in, no external library)
        const EMOJI = '😀 😁 😂 🤣 😊 😍 😘 😎 🤔 😅 😢 😭 😡 👍 👎 👏 🙏 💪 👌 ✌️ 🤝 🙌 👋 ❤️ 💚 💯 🔥 ⭐ ✅ ❌ ⚠️ 📦 🚚 💰 🧾 📄 📞 📍 ⏰ 📅 🎉 🎁 ☕ 😇 🙂 😉 🤗 😴 🤩'.split(' ');
        const panel = $('waEmojiPanel');
        panel.innerHTML = EMOJI.map((e) => '<button type="button" role="option" aria-label="' + e + '">' + e + '</button>').join('');
        $('waEmojiBtn').addEventListener('click', () => {
            const open = panel.classList.toggle('d-none') === false;
            $('waEmojiBtn').setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        panel.addEventListener('click', (e) => {
            const b = e.target.closest('button');
            if (!b) return;
            const s = text.selectionStart || text.value.length, en = text.selectionEnd || s;
            text.value = text.value.slice(0, s) + b.textContent + text.value.slice(en);
            text.selectionStart = text.selectionEnd = s + b.textContent.length;
            panel.classList.add('d-none'); text.focus(); autosize();
        });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') panel.classList.add('d-none'); });
        $('waTemplateBtn').addEventListener('click', openTemplatePicker);
    }

    async function send() {
        if (state.sending || !state.openId) return;
        const text = $('waText');
        const body = text.value.trim();
        if (!state.file && !body) return;
        if (!state.windowOpen) { toast('The 24-hour window is closed. Use a template.', true); return; }
        state.sending = true;
        $('waSend').disabled = true;
        $('waSend').innerHTML = '<span class="wa-spinner"></span>';
        try {
            let r;
            if (state.file) {
                r = await uploadMedia(state.file, body);
            } else {
                r = await api(convUrl(state.openId, '/send'), { method: 'POST', json: { text: body, reply_to: state.replyTo && state.replyTo.wamid } });
            }
            if (r.message) appendMessages([r.message], false);
            if (r.ok) { text.value = ''; text.style.height = 'auto'; clearAttachment(); setReply(null); }
            else toast(r.error || 'Message not sent.', true);
        } catch (e) {
            toast(e.message, true);
        } finally {
            state.sending = false;
            $('waSend').disabled = !state.windowOpen;
            $('waSend').innerHTML = '<i class="fas fa-paper-plane"></i>';
            $('waUploadBar').style.width = '0';
        }
    }
    function uploadMedia(file, caption) {
        return new Promise((resolve, reject) => {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('caption', caption);
            if (state.replyTo && state.replyTo.wamid) fd.append('reply_to', state.replyTo.wamid);
            const xhr = new XMLHttpRequest();
            xhr.open('POST', convUrl(state.openId, '/send-media'));
            xhr.setRequestHeader('X-CSRFToken', window.WA_CSRF);
            xhr.setRequestHeader('Accept', 'application/json');
            xhr.upload.onprogress = (e) => { if (e.lengthComputable) $('waUploadBar').style.width = Math.round(e.loaded / e.total * 100) + '%'; };
            xhr.onload = () => {
                let data = null;
                try { data = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
                if (data && (data.message || xhr.status < 300)) resolve(data);
                else reject(new Error((data && data.error) || (xhr.status === 413 ? 'File too large.' : 'Upload failed (' + xhr.status + ').')));
            };
            xhr.onerror = () => reject(new Error('Network error while uploading.'));
            xhr.send(fd);
        });
    }

    // ── modals: templates / new conversation ─────────────────────────────
    function modal(title, bodyHtml) {
        const back = document.createElement('div');
        back.className = 'wa-modal-backdrop';
        back.innerHTML = '<div class="wa-modal" role="dialog" aria-modal="true" aria-label="' + esc(title) + '"><div class="wa-card-head"><h3>' + esc(title) +
            '</h3><button class="wa-btn wa-btn-sm" data-close aria-label="Close">×</button></div><div class="wa-card-body wa-form">' + bodyHtml + '</div></div>';
        const close = () => { back.remove(); document.removeEventListener('keydown', onKey); };
        const onKey = (e) => { if (e.key === 'Escape') close(); };
        back.addEventListener('click', (e) => { if (e.target === back || e.target.closest('[data-close]')) close(); });
        document.addEventListener('keydown', onKey);
        document.body.appendChild(back);
        const first = back.querySelector('input, select, textarea, button:not([data-close])');
        if (first) first.focus();
        return { el: back, close };
    }
    async function openTemplatePicker() {
        if (!state.openId) return;
        if (state.conv.contact.consent === 'opted_out') { toast('This contact opted out — templates cannot be sent.', true); return; }
        let data;
        try { data = await api(U.templates); } catch (e) { toast(e.message, true); return; }
        if (!data.items.length) {
            modal('Send template', '<div class="wa-empty"><i class="fas fa-file-lines"></i>No approved templates. Sync or create templates in Message Templates.</div>');
            return;
        }
        const m = modal('Send template', '<div class="wa-row"><label for="waTplSel">Approved template</label><select id="waTplSel">' +
            data.items.map((t) => '<option value="' + t.id + '">' + esc(t.name) + ' · ' + esc(t.language) + ' · ' + esc((t.category || '').toLowerCase()) + '</option>').join('') +
            '</select></div><div id="waTplVars"></div><label>Preview</label><div class="wa-preview-bubble" id="waTplPreview"></div>' +
            '<div class="wa-alert wa-alert-info wa-small mt-2">Templates can be sent even when the 24-hour window is closed. Meta may charge per template message.</div>' +
            '<div class="text-end mt-2"><button class="wa-btn" data-close>Cancel</button> <button class="wa-btn wa-btn-primary" id="waTplSend"><i class="fas fa-paper-plane"></i> Send</button></div>');
        const sel = m.el.querySelector('#waTplSel');
        const current = () => data.items.find((t) => String(t.id) === sel.value);
        const values = () => { const v = {}; m.el.querySelectorAll('[data-key]').forEach((i) => { v[i.dataset.key] = i.value; }); return v; };
        let pt;
        const preview = () => {
            clearTimeout(pt);
            pt = setTimeout(async () => {
                try {
                    const r = await api(U.templatePreview + sel.value + '/preview', { method: 'POST', json: { values: values() } });
                    m.el.querySelector('#waTplPreview').textContent = r.preview;
                } catch (e) { /* preview is optional */ }
            }, 200);
        };
        const renderVars = () => {
            const t = current();
            m.el.querySelector('#waTplVars').innerHTML = t.variables.map((v) => '<div class="wa-row"><label>' + esc(v.label) + '</label><input type="text" data-key="' + esc(v.key) + '" maxlength="1024"></div>').join('') ||
                '<div class="wa-small wa-muted mb-2">This template has no variables.</div>';
            m.el.querySelector('#waTplPreview').textContent = t.preview;
        };
        sel.addEventListener('change', () => { renderVars(); preview(); });
        m.el.addEventListener('input', preview);
        renderVars();
        m.el.querySelector('#waTplSend').addEventListener('click', async (e) => {
            const btn = e.currentTarget;
            const missing = Array.from(m.el.querySelectorAll('[data-key]')).find((i) => !i.value.trim());
            if (missing) { missing.focus(); toast('Fill in every variable.', true); return; }
            btn.disabled = true; btn.innerHTML = '<span class="wa-spinner"></span> Sending';
            try {
                const r = await api(convUrl(state.openId, '/send-template'), { method: 'POST', json: { template_id: sel.value, values: values() } });
                if (r.message) appendMessages([r.message], false);
                if (r.ok) { m.close(); toast('Template sent.'); } else { toast(r.error || 'Not sent.', true); btn.disabled = false; btn.textContent = 'Send'; }
            } catch (err) { toast(err.message, true); btn.disabled = false; btn.textContent = 'Send'; }
        });
    }
    if ($('waNewConv')) $('waNewConv').addEventListener('click', () => {
        const m = modal('New conversation', '<div class="wa-row"><label for="waNcQ">Find a contact</label><input type="search" id="waNcQ" placeholder="Name or number"></div>' +
            '<div id="waNcRes" class="wa-list-plain"></div><div class="wa-small wa-muted mt-2">Not listed? Add the contact in Contacts first (with their consent).</div>');
        const q = m.el.querySelector('#waNcQ');
        let t;
        const search = async () => {
            try {
                const r = await api(U.contactSearch + '?q=' + encodeURIComponent(q.value));
                m.el.querySelector('#waNcRes').innerHTML = r.items.map((c) => '<button type="button" class="wa-conv" data-cid="' + c.id + '"><span class="wa-conv-main"><span class="wa-conv-name">' +
                    esc(c.name) + '</span><span class="wa-conv-preview">' + esc(c.phone) + (c.consent === 'opted_out' ? ' · opted out' : '') + '</span></span></button>').join('') ||
                    '<div class="wa-empty">No contacts found.</div>';
            } catch (e) { toast(e.message, true); }
        };
        q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(search, 250); });
        m.el.querySelector('#waNcRes').addEventListener('click', async (e) => {
            const b = e.target.closest('[data-cid]');
            if (!b) return;
            try {
                const r = await api(U.contactOpen + b.dataset.cid + '/open', { method: 'POST', json: {} });
                state.convs.set(r.conversation.id, r.conversation);
                m.close(); openConversation(r.conversation.id);
            } catch (err) { toast(err.message, true); }
        });
        search();
    });

    // ── live updates (polling; paused while the tab is hidden) ───────────
    async function poll() {
        if (document.hidden) return schedule();
        const p = new URLSearchParams({ since: state.since || '' });
        if (state.openId) { p.set('open', state.openId); p.set('after', state.lastMsgId); p.set('visible', document.hasFocus() ? '1' : '0'); }
        try {
            const r = await api(U.poll + '?' + p);
            state.since = r.now;
            let changed = false;
            r.conversations.forEach((c) => {
                if (c.id === state.openId && document.hasFocus()) c.unread = 0;
                state.convs.set(c.id, c); changed = true;
            });
            if (changed) renderList();
            if (state.openId && r.messages && r.messages.length) appendMessages(r.messages, false);
            if (state.openId && r.window) renderWindow(r.window);
            document.title = (r.unread_total ? '(' + r.unread_total + ') ' : '') + document.title.replace(/^\(\d+\)\s*/, '');
        } catch (e) { /* transient; try again next tick */ }
        schedule();
    }
    function schedule() { clearTimeout(state.pollTimer); state.pollTimer = setTimeout(poll, POLL_MS); }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
    window.addEventListener('beforeunload', () => clearTimeout(state.pollTimer));

    // ── start ────────────────────────────────────────────────────────────
    (async () => {
        await loadList(true);
        state.since = new Date().toISOString().slice(0, 19);
        const open = parseInt(root.dataset.open || '0', 10);
        if (open) openConversation(open);
        schedule();
    })();
})();
