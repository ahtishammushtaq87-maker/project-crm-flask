import os
from flask import (Blueprint, render_template, request, redirect, url_for, flash, send_from_directory,
                   current_app, jsonify, abort)
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import Media, MediaFolder
from app import db
from app.utils import log_activity
from werkzeug.utils import secure_filename
from datetime import datetime

bp = Blueprint('media', __name__)

MODULE = 'Media'  # Activity Log module name for everything done here


def _size(n):
    n = n or 0
    return f'{n / 1024 / 1024:.2f} MB' if n >= 1024 * 1024 else f'{n / 1024:.1f} KB'


def _where(folder_id):
    """'Media Library' or the folder's full path, for log details."""
    if not folder_id:
        return 'Media Library'
    parts, node, seen = [], MediaFolder.query.get(folder_id), set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        parts.append(node.name)
        node = node.parent
    return 'Media Library / ' + ' / '.join(reversed(parts)) if parts else 'Media Library'

# Blocked extensions for security
BLOCKED_EXTENSIONS = {'exe', 'bat', 'sh', 'cmd', 'ps1', 'vbs', 'php'}

def allowed_file(filename):
    if '.' not in filename:
        return True
    ext = filename.rsplit('.', 1)[1].lower()
    return ext not in BLOCKED_EXTENSIONS

def ensure_upload_dir():
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'media')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    return upload_dir


def _can_view():
    return current_user.is_admin or current_user.can_view_media

def _can_add():
    return current_user.is_admin or current_user.can_add_media

def _can_delete():
    return current_user.is_admin or current_user.can_delete_media


def _folder_or_none(folder_id):
    """MediaFolder for an id from a form/JSON/query value; None = top level."""
    try:
        folder_id = int(folder_id) if folder_id not in (None, '', 'null', 'root') else None
    except (TypeError, ValueError):
        return None
    return MediaFolder.query.get(folder_id) if folder_id else None


def _index_url(folder_id):
    return url_for('media.index', folder=folder_id) if folder_id else url_for('media.index')


def _clean_folder_name(name):
    name = ' '.join((name or '').split())
    if not name:
        return None, 'Folder name cannot be empty.'
    if len(name) > 150:
        return None, 'Folder name is too long (max 150 characters).'
    if any(ch in name for ch in '\\/:*?"<>|'):
        return None, 'Folder name cannot contain any of: \\ / : * ? " < > |'
    return name, None


def _name_taken(name, parent_id, exclude_id=None):
    q = MediaFolder.query.filter(func.lower(MediaFolder.name) == name.lower(),
                                 MediaFolder.parent_id.is_(None) if parent_id is None
                                 else MediaFolder.parent_id == parent_id)
    if exclude_id:
        q = q.filter(MediaFolder.id != exclude_id)
    return q.first() is not None


def _is_inside(folder, possible_ancestor):
    """True if `folder` is `possible_ancestor` or anywhere below it."""
    node, seen = folder, set()
    while node is not None and node.id not in seen:
        if node.id == possible_ancestor.id:
            return True
        seen.add(node.id)
        node = node.parent
    return False


@bp.route('/')
@login_required
def index():
    if not _can_view():
        flash('You do not have permission to view media.', 'danger')
        return redirect(url_for('dashboard.index'))

    folder = _folder_or_none(request.args.get('folder'))
    if request.args.get('folder') and folder is None:
        flash('That folder no longer exists.', 'warning')
        return redirect(url_for('media.index'))
    parent_id = folder.id if folder else None

    folders = (MediaFolder.query
               .filter(MediaFolder.parent_id.is_(None) if parent_id is None else MediaFolder.parent_id == parent_id)
               .order_by(func.lower(MediaFolder.name)).all())
    documents = (Media.query
                 .filter(Media.folder_id.is_(None) if parent_id is None else Media.folder_id == parent_id)
                 .order_by(Media.uploaded_at.desc()).all())

    # "N items" under every folder tile: its sub-folders + files (2 queries)
    ids = [f.id for f in folders]
    counts = {i: 0 for i in ids}
    if ids:
        for pid, n in db.session.query(MediaFolder.parent_id, func.count(MediaFolder.id)) \
                .filter(MediaFolder.parent_id.in_(ids)).group_by(MediaFolder.parent_id):
            counts[pid] += n
        for fid, n in db.session.query(Media.folder_id, func.count(Media.id)) \
                .filter(Media.folder_id.in_(ids)).group_by(Media.folder_id):
            counts[fid] += n

    # Every folder, for the "Move to" picker
    all_folders = MediaFolder.query.all()
    by_id = {f.id: f for f in all_folders}

    def label(f):
        parts, node, seen = [], f, set()
        while node is not None and node.id not in seen:
            seen.add(node.id)
            parts.append(node.name)
            node = by_id.get(node.parent_id)
        return ' / '.join(reversed(parts))
    folder_options = sorted(({'id': f.id, 'label': label(f)} for f in all_folders), key=lambda x: x['label'].lower())

    # Records whose file isn't on this server (e.g. after restoring a database
    # from another machine without copying its uploads folder).
    media_dir = os.path.join(current_app.static_folder, 'uploads', 'media')
    missing_ids = {d.id for d in documents
                   if not os.path.isfile(os.path.join(media_dir, os.path.basename(d.filepath or '')))}

    return render_template('media/list.html', folder=folder, folders=folders, documents=documents,
                           missing_ids=missing_ids,
                           folder_counts=counts, folder_options=folder_options,
                           can_add=_can_add(), can_delete=_can_delete())


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if not _can_add():
        return jsonify({'error': 'Permission denied'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed for security reasons'}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    folder_id = request.form.get('folder_id')
    folder = _folder_or_none(folder_id)
    if folder_id not in (None, '', 'null', 'root') and folder is None:
        return jsonify({'error': 'Folder not found'}), 400

    # Add timestamp to avoid filename collisions
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_filename = f"{timestamp}_{filename}"

    upload_dir = ensure_upload_dir()
    filepath = os.path.join(upload_dir, unique_filename)
    file.save(filepath)

    # Store relative path for DB
    db_path = 'uploads/media/' + unique_filename

    new_media = Media()
    new_media.filename = filename
    new_media.filepath = db_path
    new_media.file_type = file.content_type or 'application/octet-stream'
    new_media.file_size = os.path.getsize(filepath)
    new_media.uploaded_by_id = current_user.id
    new_media.folder_id = folder.id if folder else None
    db.session.add(new_media)
    db.session.commit()
    log_activity(MODULE, f'Uploaded file: {new_media.filename}',
                 f'File ID: {new_media.id}, Size: {_size(new_media.file_size)}, '
                 f'Type: {new_media.file_type}, Folder: {_where(new_media.folder_id)}')

    return jsonify({
        'message': 'File uploaded successfully',
        'id': new_media.id,
        'filename': new_media.filename
    }), 200

# ── Open / preview / download ────────────────────────────────────────────
# Clicking a file opens the in-app preview (media/preview.html) — nothing is
# downloaded until the Download button is pressed. /view serves the raw file
# INLINE for the preview to display; /download is the only route that sends
# it as an attachment.

TEXT_EXTENSIONS = {'txt', 'log', 'md', 'json', 'xml', 'html', 'htm', 'yaml', 'yml', 'ini', 'cfg', 'conf',
                   'py', 'js', 'css', 'sql', 'sh', 'bat', 'tsv'}
# Markup a browser would execute if opened directly from our origin: always
# served with a sandbox CSP, so an uploaded .html/.svg can never run scripts
# as the logged-in user.
ACTIVE_MARKUP_EXTENSIONS = {'html', 'htm', 'xhtml', 'svg', 'xml', 'xsl'}
ACTIVE_MARKUP_MIMETYPES = {'text/html', 'application/xhtml+xml', 'image/svg+xml', 'text/xml', 'application/xml'}
PREVIEW_TEXT_LIMIT = 2 * 1024 * 1024  # bigger text files: first 2 MB shown
ZIP_LIST_LIMIT = 500


def _ext(document):
    return document.filename.rsplit('.', 1)[-1].lower() if '.' in (document.filename or '') else ''


def file_kind(document):
    """Same buckets as the file_kind macro in media/list.html."""
    t, ext = (document.file_type or '').lower(), _ext(document)
    if 'image' in t or ext in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'):
        return 'image'
    if 'pdf' in t or ext == 'pdf':
        return 'pdf'
    if 'word' in t or ext in ('doc', 'docx'):
        return 'word'
    if 'excel' in t or 'sheet' in t or 'csv' in t or ext in ('xls', 'xlsx', 'csv'):
        return 'excel'
    if 'presentation' in t or 'powerpoint' in t or ext in ('ppt', 'pptx'):
        return 'ppt'
    if 'zip' in t or 'compressed' in t or ext in ('zip', 'rar', '7z'):
        return 'zip'
    if 'video' in t:
        return 'video'
    if 'audio' in t:
        return 'audio'
    if 'text' in t or 'json' in t or ext in TEXT_EXTENSIONS:
        return 'text'
    return 'other'


def _can_open_document():
    return current_user.is_admin or current_user.can_view_media_document


def _stored(document):
    directory = os.path.join(current_app.static_folder, 'uploads', 'media')
    return directory, os.path.basename(document.filepath)


@bp.route('/download/<int:media_id>')
@login_required
def download(media_id):
    if not _can_open_document():
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))

    document = Media.query.get_or_404(media_id)
    directory, stored_filename = _stored(document)
    if not os.path.isfile(os.path.join(directory, stored_filename)):
        flash(f'"{document.filename}" cannot be downloaded: the file is missing from this server '
              f'(app/static/{document.filepath}). The record exists, but the file itself was never copied here.',
              'danger')
        return redirect(_index_url(document.folder_id))
    log_activity(MODULE, f'Downloaded file: {document.filename}',
                 f'File ID: {document.id}, Size: {_size(document.file_size)}, Folder: {_where(document.folder_id)}')
    return send_from_directory(directory, stored_filename, as_attachment=True, download_name=document.filename)


@bp.route('/view/<int:media_id>')
@login_required
def view(media_id):
    """The raw file, inline (Content-Disposition: inline) — what the preview
    shows. Never forces a download."""
    if not _can_open_document():
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))

    document = Media.query.get_or_404(media_id)
    directory, stored_filename = _stored(document)
    if not os.path.isfile(os.path.join(directory, stored_filename)):
        abort(404)
    mimetype = document.file_type if document.file_type and '/' in document.file_type else None
    response = send_from_directory(directory, stored_filename, as_attachment=False,
                                   download_name=document.filename, mimetype=mimetype)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    mime = (document.file_type or '').split(';')[0].strip().lower()
    if _ext(document) in ACTIVE_MARKUP_EXTENSIONS or mime in ACTIVE_MARKUP_MIMETYPES:
        response.headers['Content-Security-Policy'] = 'sandbox'
    return response


@bp.route('/preview/<int:media_id>')
@login_required
def preview(media_id):
    """In-app viewer for any file (images, PDF, video/audio, Word .docx,
    Excel/CSV, text, ZIP contents); `embed=1` drops the page's own header for
    the popup on the Media page. Unsupported types get a clear message and a
    Download button — the file itself is never downloaded automatically."""
    if not _can_open_document():
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))

    document = Media.query.get_or_404(media_id)
    kind = file_kind(document)
    ext = _ext(document)
    # One entry per open. The preview's own fetch of /view isn't logged, so an
    # open is never counted twice.
    log_activity(MODULE, f'Viewed file: {document.filename}',
                 f'File ID: {document.id}, Opened in preview, Folder: {_where(document.folder_id)}')
    directory, stored_filename = _stored(document)
    path = os.path.join(directory, stored_filename)
    exists = os.path.isfile(path)

    zip_entries, zip_truncated, zip_error = [], False, None
    if exists and kind == 'zip' and ext == 'zip':
        import zipfile
        try:
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                zip_truncated = len(infos) > ZIP_LIST_LIMIT
                zip_entries = [{'name': i.filename, 'size': i.file_size, 'is_dir': i.is_dir()}
                               for i in infos[:ZIP_LIST_LIMIT]]
        except (zipfile.BadZipFile, OSError) as e:
            zip_error = str(e)

    return render_template('media/preview.html', document=document, kind=kind, ext=ext, exists=exists,
                           embed=request.args.get('embed') == '1',
                           zip_entries=zip_entries, zip_truncated=zip_truncated, zip_error=zip_error,
                           text_limit=PREVIEW_TEXT_LIMIT)


@bp.route('/delete/<int:media_id>', methods=['POST'])
@login_required
def delete(media_id):
    document = Media.query.get_or_404(media_id)
    back = _index_url(document.folder_id)
    if not _can_delete():
        flash('Permission denied', 'danger')
        return redirect(back)

    # Delete file from filesystem
    rel_path = document.filepath.replace('/', os.sep)
    filepath = os.path.join(current_app.static_folder, rel_path)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            current_app.logger.error(f"Error deleting file: {e}")

    name, doc_id, size, where = document.filename, document.id, document.file_size, _where(document.folder_id)
    db.session.delete(document)
    db.session.commit()
    log_activity(MODULE, f'Deleted file: {name}', f'File ID: {doc_id}, Size: {_size(size)}, Folder: {where}')

    flash('Document deleted successfully.', 'success')
    return redirect(back)


# ── Folders ──────────────────────────────────────────────────────────────

@bp.route('/folder/create', methods=['POST'])
@login_required
def create_folder():
    parent = _folder_or_none(request.form.get('parent_id'))
    back = _index_url(parent.id if parent else None)
    if not _can_add():
        flash('Permission denied', 'danger')
        return redirect(back)
    name, err = _clean_folder_name(request.form.get('name'))
    if not err and _name_taken(name, parent.id if parent else None):
        err = f'A folder named "{name}" already exists here.'
    if err:
        flash(err, 'danger')
        return redirect(back)
    db.session.add(MediaFolder(name=name, parent_id=parent.id if parent else None, created_by_id=current_user.id))
    db.session.commit()
    log_activity(MODULE, f'Created folder: {name}', f'In: {_where(parent.id if parent else None)}')
    flash(f'Folder "{name}" created.', 'success')
    return redirect(back)


@bp.route('/folder/<int:folder_id>/rename', methods=['POST'])
@login_required
def rename_folder(folder_id):
    folder = MediaFolder.query.get_or_404(folder_id)
    back = _index_url(folder.parent_id)
    if not _can_add():
        flash('Permission denied', 'danger')
        return redirect(back)
    name, err = _clean_folder_name(request.form.get('name'))
    if not err and _name_taken(name, folder.parent_id, exclude_id=folder.id):
        err = f'A folder named "{name}" already exists here.'
    if err:
        flash(err, 'danger')
        return redirect(back)
    old_name = folder.name
    folder.name = name
    db.session.commit()
    if old_name != name:
        log_activity(MODULE, f'Renamed folder: {old_name} → {name}', f'Folder ID: {folder.id}, In: {_where(folder.parent_id)}')
    flash(f'Folder renamed to "{name}".', 'success')
    return redirect(back)


@bp.route('/folder/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    """Removes the folder only - everything inside moves up to its parent."""
    folder = MediaFolder.query.get_or_404(folder_id)
    parent_id = folder.parent_id
    back = _index_url(parent_id)
    if not _can_delete():
        flash('Permission denied', 'danger')
        return redirect(back)
    moved = 0
    for f in Media.query.filter_by(folder_id=folder.id).all():
        f.folder_id = parent_id
        moved += 1
    for child in MediaFolder.query.filter_by(parent_id=folder.id).all():
        new_name, n = child.name, 2
        while _name_taken(new_name, parent_id, exclude_id=child.id):
            new_name = f'{child.name} ({n})'
            n += 1
        child.name = new_name
        child.parent_id = parent_id
        moved += 1
    name, folder_id, where = folder.name, folder.id, _where(parent_id)
    db.session.delete(folder)
    db.session.commit()
    log_activity(MODULE, f'Deleted folder: {name}',
                 f'Folder ID: {folder_id}, In: {where}'
                 + (f', {moved} item(s) inside moved up to {where}' if moved else ', it was empty'))
    flash(f'Folder "{name}" deleted.' + (f' {moved} item(s) inside it were moved up one level.' if moved else ''),
          'success')
    return redirect(back)


@bp.route('/move', methods=['POST'])
@login_required
def move():
    """JSON: {items: [{type: 'file'|'folder', id}], target_folder_id: id|null}."""
    if not _can_add():
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json(silent=True) or {}
    raw_target = data.get('target_folder_id')
    target = _folder_or_none(raw_target)
    if raw_target not in (None, '', 'null', 'root') and target is None:
        return jsonify({'error': 'Target folder not found'}), 400
    target_id = target.id if target else None

    moved, skipped, names = 0, [], []
    for it in data.get('items') or []:
        try:
            item_id = int(it.get('id'))
        except (TypeError, ValueError, AttributeError):
            continue
        if it.get('type') == 'folder':
            f = MediaFolder.query.get(item_id)
            if not f or f.parent_id == target_id:
                continue
            if target and _is_inside(target, f):
                skipped.append(f'"{f.name}" cannot be moved into itself')
                continue
            if _name_taken(f.name, target_id, exclude_id=f.id):
                skipped.append(f'a folder named "{f.name}" already exists there')
                continue
            f.parent_id = target_id
            moved += 1
            names.append(f'folder "{f.name}"')
        else:
            m = Media.query.get(item_id)
            if not m or m.folder_id == target_id:
                continue
            m.folder_id = target_id
            moved += 1
            names.append(f'"{m.filename}"')
    db.session.commit()
    if moved:
        shown = ', '.join(names[:20]) + (f' and {len(names) - 20} more' if len(names) > 20 else '')
        log_activity(MODULE, f'Moved {moved} item(s) to {_where(target_id)}',
                     shown + (f'. Skipped: {"; ".join(skipped)}' if skipped else ''))
    return jsonify({'moved': moved, 'skipped': skipped,
                    'target': target.name if target else 'Media Library'})
