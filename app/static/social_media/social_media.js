/* Social Media module - page behaviour. No tokens or secrets ever reach this
   script; it only talks to the CRM's own endpoints with the CSRF token. */
(function () {
    'use strict';

    var LIMITS = {facebook: 63206, instagram: 2200, linkedin: 3000};
    var LABELS = {facebook: 'Facebook', instagram: 'Instagram', linkedin: 'LinkedIn'};

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
        });
    }

    function fullText(body, tags) {
        body = (body || '').trim();
        var t = (tags || '').replace(/,/g, ' ').split(/\s+/).filter(Boolean)
            .map(function (x) { return x.charAt(0) === '#' ? x : '#' + x; }).join(' ');
        return t ? (body + '\n\n' + t).trim() : body;
    }

    /* Client-side mirror of services/media.validate_for_platform (the server re-checks). */
    function validate(platform, text, media, link) {
        var p = [];
        var imgs = media.filter(function (m) { return m.kind === 'image'; });
        var vids = media.filter(function (m) { return m.kind === 'video'; });
        if (text.length > LIMITS[platform]) p.push(LABELS[platform] + ' text is limited to ' + LIMITS[platform].toLocaleString() + ' characters.');
        if (platform === 'instagram') {
            if (!media.length) p.push('Instagram requires at least one image or video.');
            if (media.length > 10) p.push('Instagram carousels can contain at most 10 items.');
            if ((text.match(/#/g) || []).length > 30) p.push('Instagram allows at most 30 hashtags.');
            imgs.forEach(function (m) { if (m.mime && m.mime !== 'image/jpeg') p.push('Instagram only accepts JPEG images (' + m.name + ').'); });
        } else {
            if (vids.length && (imgs.length || vids.length > 1)) p.push(LABELS[platform] + ': a video post can contain only one video and no images.');
            if (!text && !media.length && !(platform === 'facebook' && link)) p.push(LABELS[platform] + ': add text' + (platform === 'facebook' ? ', a link' : '') + ' or media.');
            if (platform === 'linkedin' && imgs.length > 20) p.push('LinkedIn allows at most 20 images per post.');
        }
        return p;
    }

    function postJSON(url, data) {
        return fetch(url, {method: 'POST', credentials: 'same-origin',
            headers: {'X-CSRFToken': window.SM_CSRF, 'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify(data || {})}).then(function (r) {
            return r.json().catch(function () { return {ok: false, message: 'Unexpected response (' + r.status + ').'}; });
        });
    }

    /* ── Composer ───────────────────────────────────────────── */
    function composer(form) {
        if (!form) return;
        var body = form.querySelector('#smBody'), tags = form.querySelector('#smTags'), link = form.querySelector('#smLink');
        var fileInput = form.querySelector('#smFiles'), list = form.querySelector('#smMediaList'), drop = form.querySelector('#smDrop');
        var mediaErr = form.querySelector('#smMediaErrors');
        var maxImg = +form.dataset.maxImageMb * 1048576, maxVid = +form.dataset.maxVideoMb * 1048576;
        var pvPlatform = 'facebook';
        var newFiles = [];   // File objects not yet uploaded, in display order
        var dirty = false;

        function accounts() {
            return Array.prototype.slice.call(form.querySelectorAll('input[name="account_ids"]:checked')).map(function (i) {
                return {id: i.value, platform: i.dataset.platform, name: i.dataset.name, picture: i.dataset.picture, type: i.dataset.type};
            });
        }

        function mediaItems() {
            return Array.prototype.slice.call(list.children).filter(function (el) { return !el.classList.contains('sm-removed'); })
                .map(function (el) { return {kind: el.dataset.kind, mime: el.dataset.mime, src: el.dataset.src, name: el.getAttribute('aria-label') || el.dataset.name || ''}; });
        }

        function syncFiles() {
            try {
                var dt = new DataTransfer();
                newFiles.forEach(function (f) { dt.items.add(f); });
                fileInput.files = dt.files;
            } catch (e) { /* very old browsers: files stay as originally chosen */ }
            Array.prototype.forEach.call(list.querySelectorAll('[data-existing]'), function (el, i) {
                var o = el.querySelector('input[name^="media_order_"]');
                if (o) o.value = i + 1;
            });
        }

        function addFiles(files) {
            mediaErr.innerHTML = '';
            Array.prototype.forEach.call(files, function (f) {
                var kind = /^video\//.test(f.type) ? 'video' : (/^image\//.test(f.type) ? 'image' : null);
                if (!kind) { mediaErr.innerHTML += '<li>' + esc(f.name) + ': not an image or video.</li>'; return; }
                if (f.size > (kind === 'image' ? maxImg : maxVid)) { mediaErr.innerHTML += '<li>' + esc(f.name) + ' is larger than the ' + kind + ' limit.</li>'; return; }
                newFiles.push(f);
                var url = URL.createObjectURL(f);
                var el = document.createElement('div');
                el.className = 'sm-media-item';
                el.dataset.kind = kind; el.dataset.mime = f.type; el.dataset.src = url; el.dataset.name = f.name;
                el._file = f;
                el.innerHTML = (kind === 'image' ? '<img alt="' + esc(f.name) + '" src="' + url + '">' : '<video muted preload="metadata" src="' + url + '"></video>') +
                    '<div class="sm-media-tools"><button type="button" class="sm-btn sm-btn-sm" data-move="-1" aria-label="Move left">‹</button>' +
                    '<button type="button" class="sm-btn sm-btn-sm sm-btn-danger" data-remove aria-label="Remove ' + esc(f.name) + '"><i class="fas fa-trash"></i></button>' +
                    '<button type="button" class="sm-btn sm-btn-sm" data-move="1" aria-label="Move right">›</button></div>';
                list.appendChild(el);
            });
            syncFiles(); dirty = true; render();
        }

        list.addEventListener('click', function (e) {
            var btn = e.target.closest('button'); if (!btn) return;
            var item = btn.closest('.sm-media-item');
            if (btn.hasAttribute('data-remove')) {
                if (item.dataset.existing) {
                    var cb = item.querySelector('input[name="remove_media"]');
                    cb.checked = !cb.checked;
                    item.classList.toggle('sm-removed', cb.checked);
                } else {
                    newFiles = newFiles.filter(function (f) { return f !== item._file; });
                    item.remove();
                }
            } else if (btn.dataset.move) {
                var sib = btn.dataset.move === '-1' ? item.previousElementSibling : item.nextElementSibling;
                // New uploads always come after already-saved media.
                if (sib && !!sib.dataset.existing === !!item.dataset.existing) {
                    if (btn.dataset.move === '-1') list.insertBefore(item, sib); else list.insertBefore(sib, item);
                    if (!item.dataset.existing) {
                        newFiles = Array.prototype.slice.call(list.children).filter(function (el) { return el._file; }).map(function (el) { return el._file; });
                    }
                }
            }
            syncFiles(); dirty = true; render();
        });
        fileInput.addEventListener('change', function () {
            var chosen = Array.prototype.slice.call(fileInput.files).filter(function (f) { return newFiles.indexOf(f) < 0; });
            addFiles(chosen);
        });
        ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('sm-over-drop'); }); });
        ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('sm-over-drop'); }); });
        drop.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files); });
        drop.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); } });
        drop.tabIndex = 0;

        function textFor(acc) {
            var custom = acc && form.querySelector('textarea[name="custom_text_' + acc.id + '"]');
            return custom && custom.value.trim() ? custom.value.trim() : fullText(body.value, tags.value);
        }

        function renderPreview() {
            var accs = accounts().filter(function (a) { return a.platform === pvPlatform; });
            var acc = accs[0];
            var text = textFor(acc);
            var media = mediaItems();
            var name = acc ? acc.name : 'Your ' + LABELS[pvPlatform] + ' account';
            var avatar = acc && acc.picture ? '<img class="sm-avatar" src="' + esc(acc.picture) + '" alt="">' : '<span class="sm-avatar"><i class="fas fa-user"></i></span>';
            var htmlText = esc(text).replace(/(^|\s)(#[\wÀ-￿]+)/g, '$1<span class="sm-tag">$2</span>');
            var shown = pvPlatform === 'instagram' ? media.slice(0, 1) : media.slice(0, 4);
            var mediaHtml = shown.length ? '<div class="sm-pv-media ' + (shown.length === 1 ? 'sm-one' : '') + '">' + shown.map(function (m) {
                return m.kind === 'image' ? '<img src="' + esc(m.src) + '" alt="">' : '<video src="' + esc(m.src) + '" muted controls preload="metadata"></video>';
            }).join('') + '</div>' : '';
            var extra = (pvPlatform === 'instagram' && media.length > 1) ? '<div class="sm-pv-carousel-note"><i class="fas fa-clone"></i> Carousel · ' + media.length + ' items</div>' :
                (media.length > 4 ? '<div class="sm-pv-carousel-note">+' + (media.length - 4) + ' more</div>' : '');
            var linkHtml = (!media.length && link.value && pvPlatform !== 'instagram') ? '<div class="sm-pv-link"><i class="fas fa-link"></i> ' + esc(link.value) + '</div>' : '';
            var meta = pvPlatform === 'linkedin' ? 'Now · <i class="fas fa-globe-americas"></i>' : (pvPlatform === 'facebook' ? 'Just now · <i class="fas fa-earth-asia"></i>' : '');
            var bar = {facebook: '<span><i class="far fa-thumbs-up"></i> Like</span><span><i class="far fa-comment"></i> Comment</span><span><i class="fas fa-share"></i> Share</span>',
                instagram: '<span><i class="far fa-heart"></i></span><span><i class="far fa-comment"></i></span><span><i class="far fa-paper-plane"></i></span><span><i class="far fa-bookmark"></i></span>',
                linkedin: '<span><i class="far fa-thumbs-up"></i> Like</span><span><i class="far fa-comment"></i> Comment</span><span><i class="fas fa-retweet"></i> Repost</span><span><i class="fas fa-paper-plane"></i> Send</span>'}[pvPlatform];
            var head = '<div class="sm-pv-head">' + avatar + '<div><div class="sm-pv-name">' + esc(name) + '</div><div class="sm-pv-meta">' + meta + '</div></div></div>';
            var html = pvPlatform === 'instagram'
                ? head + mediaHtml + extra + '<div class="sm-pv-bar">' + bar + '</div><div class="sm-pv-text" style="padding-top:8px"><strong>' + esc(acc ? (name) : 'account') + '</strong> ' + htmlText + '</div>'
                : head + '<div class="sm-pv-text">' + (htmlText || '<span class="sm-muted">Your text will appear here.</span>') + '</div>' + mediaHtml + extra + linkHtml + '<div class="sm-pv-bar">' + bar + '</div>';
            document.getElementById('smPreview').innerHTML = '<div class="sm-pv sm-pv-' + pvPlatform.slice(0, 2) + (pvPlatform === 'instagram' ? ' sm-pv-ig' : '') + (pvPlatform === 'linkedin' ? ' sm-pv-li' : '') + '">' + html + '</div>' +
                (acc ? '' : '<div class="sm-help mt-2">No ' + LABELS[pvPlatform] + ' destination selected — shown for reference only.</div>');
            var probs = validate(pvPlatform, text, media, link.value);
            document.getElementById('smPreviewProblems').innerHTML = probs.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('');
        }

        function render() {
            var media = mediaItems();
            var t = fullText(body.value, tags.value);
            var counter = document.getElementById('smCounter');
            counter.innerHTML = ['facebook', 'instagram', 'linkedin'].map(function (p) {
                return '<span class="' + (t.length > LIMITS[p] ? 'sm-over' : '') + '">' + LABELS[p] + ': ' + t.length.toLocaleString() + ' / ' + LIMITS[p].toLocaleString() + '</span>';
            }).join('');
            var selected = accounts().map(function (a) { return a.id; });
            Array.prototype.forEach.call(form.querySelectorAll('#smPerPlatform details'), function (d) {
                var on = selected.indexOf(d.dataset.for) >= 0;
                d.hidden = !on;
                if (!on) return;
                var ta = d.querySelector('textarea');
                var probs = validate(ta.dataset.platform, ta.value.trim() || t, media, link.value);
                d.querySelector('[data-problems]').innerHTML = probs.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('');
                d.querySelector('[data-problem-count]').textContent = probs.length ? probs.length + ' issue' + (probs.length > 1 ? 's' : '') : '';
                if (probs.length) d.open = true;
            });
            var label = form.querySelector('#smPerPlatform .sm-label');
            if (label) label.hidden = !selected.length;
            renderPreview();
        }

        form.addEventListener('input', function (e) { dirty = true; if (e.target.matches('textarea, input')) render(); });
        form.addEventListener('change', function () { dirty = true; render(); });
        Array.prototype.forEach.call(form.querySelectorAll('[data-pv]'), function (b) {
            b.addEventListener('click', function () {
                pvPlatform = b.dataset.pv;
                Array.prototype.forEach.call(form.querySelectorAll('[data-pv]'), function (x) { x.classList.toggle('sm-active', x === b); x.setAttribute('aria-selected', x === b); });
                renderPreview();
            });
        });
        Array.prototype.forEach.call(form.querySelectorAll('[data-sm-scroll]'), function (b) {
            b.addEventListener('click', function () { document.querySelector(b.dataset.smScroll).scrollIntoView({behavior: 'smooth'}); });
        });
        Array.prototype.forEach.call(form.querySelectorAll('button[data-action]'), function (b) {
            b.addEventListener('click', function () { form.querySelector('#smAction').value = b.dataset.action; form.querySelector('#smConfirmed').value = '0'; dirty = false; });
        });

        /* Confirmation summary before scheduling / publishing */
        var modalEl = document.getElementById('smConfirmModal');
        Array.prototype.forEach.call(form.querySelectorAll('[data-confirm-action]'), function (b) {
            b.addEventListener('click', function () {
                var action = b.dataset.confirmAction;
                var accs = accounts(), media = mediaItems();
                var when = form.querySelector('#smWhen').value;
                var problems = [];
                if (!accs.length) problems.push('Select at least one destination account.');
                if (action === 'schedule' && !when) problems.push('Choose the date and time to schedule.');
                var rows = accs.map(function (a) {
                    var text = textFor(a), probs = validate(a.platform, text, media, link.value);
                    probs.forEach(function (p) { problems.push(a.name + ': ' + p); });
                    return '<div class="sm-dest-card"><div class="d-flex align-items-center gap-2 mb-1"><span class="sm-plat sm-plat-' + a.platform + '"><i class="fab fa-' + (a.platform === 'facebook' ? 'facebook-f' : a.platform === 'linkedin' ? 'linkedin-in' : 'instagram') + '"></i></span><strong>' + esc(a.name) + '</strong><span class="sm-small sm-muted">' + LABELS[a.platform] + ' ' + esc(a.type) + '</span></div>' +
                        '<div class="sm-small" style="white-space:pre-wrap;max-height:140px;overflow:auto;background:#f6f8fb;border-radius:8px;padding:8px">' + (esc(text) || '<em class="sm-muted">(no text)</em>') + '</div></div>';
                }).join('');
                var heading = action === 'publish' ? 'Publish now to ' + accs.length + ' destination(s)?' :
                    'Schedule for ' + (when ? when.replace('T', ' ') : '—') + ' ({{tz}})?';
                document.getElementById('smConfirmTitle').textContent = heading.replace('{{tz}}', document.querySelector('label[for="smWhen"] .sm-muted') ? document.querySelector('label[for="smWhen"] .sm-muted').textContent.replace(/[()]/g, '') : '');
                document.getElementById('smConfirmBody').innerHTML =
                    (problems.length ? '<div class="sm-alert sm-alert-danger"><strong>Fix these first:</strong><ul class="mb-0">' + problems.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul></div>' : '') +
                    '<p class="sm-small sm-muted">Media: ' + (media.length ? media.length + ' file(s)' : 'none') + (link.value ? ' · Link: ' + esc(link.value) : '') + '</p>' + rows +
                    (action === 'publish' ? '<div class="sm-alert sm-alert-info mb-0">The post goes live immediately on each selected account. Each destination is tracked separately — one may succeed while another fails.</div>' :
                        '<div class="sm-alert sm-alert-info mb-0">The server publishes at the chosen time even if nobody is signed in. You can edit, reschedule or cancel until then.</div>');
                var go = document.getElementById('smConfirmGo');
                go.disabled = problems.length > 0;
                go.textContent = action === 'publish' ? 'Publish now' : 'Schedule';
                go.onclick = function () { form.querySelector('#smAction').value = action; form.querySelector('#smConfirmed').value = '1'; dirty = false; };
                bootstrap.Modal.getOrCreateInstance(modalEl).show();
            });
        });
        form.addEventListener('submit', function () {
            dirty = false;
            Array.prototype.forEach.call(form.querySelectorAll('button[type="submit"]'), function (b) { b.disabled = true; b.insertAdjacentHTML('afterbegin', '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> '); });
        });
        window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
        render();
    }

    /* ── Generic behaviours ─────────────────────────────────── */
    document.addEventListener('click', function (e) {
        var copyBtn = e.target.closest('[data-sm-copy]');
        if (copyBtn) {
            var v = copyBtn.dataset.smCopy;
            (navigator.clipboard ? navigator.clipboard.writeText(v) : Promise.reject()).then(function () {
                copyBtn.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(function () { copyBtn.innerHTML = '<i class="fas fa-copy"></i>'; }, 1500);
            }, function () { window.prompt('Copy this value:', v); });
        }
        var testBtn = e.target.closest('[data-sm-test]');
        if (testBtn) {
            var out = testBtn.nextElementSibling;
            testBtn.disabled = true;
            out.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running a real check on the server…';
            postJSON(testBtn.dataset.smTest).then(function (r) {
                out.innerHTML = '<div class="sm-alert ' + (r.ok ? 'sm-alert-ok' : 'sm-alert-danger') + ' mb-0"><strong>' + esc(r.label || (r.ok ? 'Connection successful' : 'Failed')) + '.</strong> ' +
                    esc(r.message || r.error || '') + (r.next ? '<div class="mt-1"><strong>Next step:</strong> ' + esc(r.next) + '</div>' : '') + '</div>';
            }).catch(function () { out.innerHTML = '<div class="sm-alert sm-alert-danger mb-0">The test request failed (network or session). Reload and try again.</div>'; })
                .then(function () { testBtn.disabled = false; });
        }
    });

    /* <form data-sm-confirm="message"> asks before submitting */
    document.addEventListener('submit', function (e) {
        var f = e.target;
        if (f.dataset && f.dataset.smConfirm && !window.confirm(f.dataset.smConfirm)) { e.preventDefault(); }
    }, true);

    /* Guided wizard (ads) */
    function wizard(root) {
        if (!root) return;
        var panes = root.querySelectorAll('.sm-wiz-pane'), chips = root.querySelectorAll('.sm-wiz-steps span');
        var i = +(root.dataset.start || 0);
        function show(n) {
            i = Math.max(0, Math.min(panes.length - 1, n));
            Array.prototype.forEach.call(panes, function (p, k) { p.classList.toggle('sm-active', k === i); });
            Array.prototype.forEach.call(chips, function (c, k) { c.classList.toggle('sm-active', k === i); });
        }
        root.addEventListener('click', function (e) {
            if (e.target.closest('[data-wiz-next]')) { e.preventDefault(); show(i + 1); }
            if (e.target.closest('[data-wiz-prev]')) { e.preventDefault(); show(i - 1); }
        });
        show(i);
    }

    window.SocialMedia = {composer: composer, wizard: wizard, postJSON: postJSON};
})();
