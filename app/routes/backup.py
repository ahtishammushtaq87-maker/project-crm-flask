"""
Database Backup module — admin-only. Daily automatic backups at 10 PM
Pakistan time (see app/scheduler.py:start_backup_scheduler), plus manual
backup/restore/delete here. Only ever operates on SQLite (see _get_sqlite_path);
gracefully refuses on any other database engine rather than guessing.

Safety design:
  - Backups and restores both go through sqlite3's own online backup API
    (Connection.backup()), never a raw file copy — this is safe to run
    against a live database that's still serving requests, unlike copying
    the file's bytes directly which can grab a half-written page.
  - Every backup file is verified (_verify_sqlite_file: openable + has the
    'users' table) right after it's written, BEFORE a DatabaseBackup row is
    ever created for it — a backup that failed silently or came out empty
    never gets indexed as if it were good.
  - A restore verifies the CHOSEN backup file the same way before it's
    allowed to touch the live database, and verifies the live database
    again immediately after the swap — so a corrupt backup can never be
    used to wipe good data.
  - A restore takes an automatic "safety" snapshot of the outgoing database
    first (also verified), so an accidental or wrong restore can always be
    undone.
  - Restoring requires the admin to type RESTORE to confirm, on top of the
    is_admin gate on every route in this module.
  - Backup filenames include a random suffix so two backups requested at
    the same wall-clock second can never collide/race on the same path.
"""
import os
import sqlite3
import uuid
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                    flash, send_file, current_app, has_request_context)
from flask_login import login_required, current_user

from app import db
from app.models import DatabaseBackup, ActivityLog
from app.utils import pk_now

bp = Blueprint('backup', __name__)

MAX_BACKUPS = 10


def _verify_sqlite_file(path, min_size_bytes=4096):
    """A backup/restore source is only trustworthy if it's a real, openable
    SQLite database that actually has our schema in it — not just a file
    that exists. Catches the empty-file case (a failed/interrupted copy)
    that a bare os.path.exists()/getsize() check would miss reliably."""
    if not os.path.exists(path) or os.path.getsize(path) < min_size_bytes:
        return False, 'file is missing or too small to be a real database'
    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cur.fetchall()}
            if 'users' not in tables:
                return False, "opens, but doesn't contain the expected 'users' table"
            cur.execute('PRAGMA quick_check')
            result = cur.fetchone()
            if not result or result[0] != 'ok':
                return False, f'failed SQLite integrity check ({result})'
        finally:
            conn.close()
    except sqlite3.Error as e:
        return False, f'not a valid SQLite database ({e})'
    return True, None


def _get_sqlite_path():
    """Absolute path to the live SQLite file, parsed from the app's own
    SQLALCHEMY_DATABASE_URI — returns None if this deployment isn't SQLite
    (e.g. DATABASE_URL points at Postgres), so callers can no-op cleanly."""
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('sqlite'):
        return None
    return uri.split('sqlite:///', 1)[-1] if 'sqlite:///' in uri else uri.replace('sqlite://', '')


def _get_backup_dir():
    db_path = _get_sqlite_path()
    if not db_path:
        return None
    return os.path.join(os.path.dirname(db_path), 'backups')


def _log(action, details=None, user_id=None):
    """Same intent as app.utils.log_activity, but safe to call from the
    nightly scheduler job, which has no request/current_user context."""
    ip = request.remote_addr if has_request_context() else None
    entry = ActivityLog(user_id=user_id, module='Backup', action=action, details=details, ip_address=ip)
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def create_backup(backup_type='manual', user_id=None, note=None):
    """Safely snapshot the live database. Returns the new DatabaseBackup row.
    Raises RuntimeError with a human-readable message on failure (missing
    file, non-SQLite deployment, etc.) — callers decide how to surface it."""
    db_path = _get_sqlite_path()
    if not db_path:
        raise RuntimeError('Database Backup only supports SQLite. This deployment is using a different database engine.')
    if not os.path.exists(db_path):
        raise RuntimeError(f'Live database file not found at {db_path}')

    backup_dir = _get_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = pk_now().strftime('%Y-%m-%d_%H%M%S')
    # A random suffix (not a check-then-create loop) rules out two requests
    # landing on the same path if they land in the same wall-clock second.
    filename = f'{backup_type}_{timestamp}_{uuid.uuid4().hex[:8]}.db'
    dest_path = os.path.join(backup_dir, filename)

    src_conn = sqlite3.connect(db_path)
    dest_conn = sqlite3.connect(dest_path)
    try:
        with dest_conn:
            src_conn.backup(dest_conn)
    finally:
        src_conn.close()
        dest_conn.close()

    ok, reason = _verify_sqlite_file(dest_path)
    if not ok:
        try:
            os.remove(dest_path)
        except OSError:
            pass
        raise RuntimeError(f'Backup verification failed ({reason}) — no backup was recorded. Please try again.')

    backup = DatabaseBackup(
        filename=filename,
        size_bytes=os.path.getsize(dest_path),
        backup_type=backup_type,
        note=note,
        created_by=user_id,
        created_at=datetime.utcnow(),
    )
    db.session.add(backup)
    db.session.commit()

    _enforce_retention()
    return backup


def _delete_backup_files_and_row(backup):
    backup_dir = _get_backup_dir()
    if backup_dir:
        path = os.path.join(backup_dir, backup.filename)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            current_app.logger.exception(f'Failed to delete backup file {path}')
    db.session.delete(backup)
    db.session.commit()


def _enforce_retention(limit=MAX_BACKUPS):
    """Keep only the most recent `limit` backups; delete the rest (file +
    row) — oldest first — whenever a new one pushes the count over."""
    all_backups = DatabaseBackup.query.order_by(DatabaseBackup.created_at.desc()).all()
    for stale in all_backups[limit:]:
        _delete_backup_files_and_row(stale)


def _reconcile_backup_index():
    """The database_backups TABLE lives inside the same SQLite file it
    describes, so restoring (which replaces that whole file) can leave the
    table not knowing about backup files created after the restored
    snapshot was taken — including the safety snapshot a restore itself
    takes of the outgoing database. Treat backups/ on disk as the source of
    truth and add back any row missing for a file that's still there."""
    backup_dir = _get_backup_dir()
    if not backup_dir or not os.path.isdir(backup_dir):
        return
    known = {b.filename for b in DatabaseBackup.query.all()}
    changed = False
    for fname in sorted(os.listdir(backup_dir)):
        if not fname.endswith('.db') or fname in known:
            continue
        fpath = os.path.join(backup_dir, fname)
        if not os.path.isfile(fpath):
            continue
        prefix = fname.split('_', 1)[0]
        backup_type = prefix if prefix in ('manual', 'auto', 'safety') else 'unknown'
        stat = os.stat(fpath)
        db.session.add(DatabaseBackup(
            filename=fname,
            size_bytes=stat.st_size,
            backup_type=backup_type,
            note='Recovered index entry — file found on disk without a matching record (likely from a prior database restore).',
            created_by=None,
            created_at=datetime.utcfromtimestamp(stat.st_mtime),
        ))
        changed = True
    if changed:
        db.session.commit()


def _require_admin():
    if not current_user.is_admin:
        flash('Only an admin can access Database Backup.', 'danger')
        return redirect(url_for('dashboard.index'))
    return None


@bp.route('/')
@login_required
def index():
    guard = _require_admin()
    if guard:
        return guard
    _reconcile_backup_index()
    _enforce_retention()
    backups = DatabaseBackup.query.order_by(DatabaseBackup.created_at.desc()).all()
    return render_template('backup/index.html', backups=backups,
                           sqlite_ok=bool(_get_sqlite_path()), max_backups=MAX_BACKUPS)


@bp.route('/create', methods=['POST'])
@login_required
def create():
    guard = _require_admin()
    if guard:
        return guard
    try:
        backup = create_backup(backup_type='manual', user_id=current_user.id)
        _log(f'Created manual backup {backup.filename}', f'Size: {backup.size_bytes:,} bytes', user_id=current_user.id)
        flash(f'Backup created: {backup.filename}', 'success')
    except Exception as e:
        current_app.logger.exception('Manual backup failed')
        flash(f'Backup failed: {e}', 'danger')
    return redirect(url_for('backup.index'))


@bp.route('/<int:id>/download')
@login_required
def download(id):
    guard = _require_admin()
    if guard:
        return guard
    backup = DatabaseBackup.query.get_or_404(id)
    backup_dir = _get_backup_dir()
    path = os.path.join(backup_dir, backup.filename) if backup_dir else None
    if not path or not os.path.exists(path):
        flash('Backup file is missing on disk.', 'danger')
        return redirect(url_for('backup.index'))
    _log(f'Downloaded backup {backup.filename}', user_id=current_user.id)
    return send_file(path, as_attachment=True, download_name=backup.filename)


@bp.route('/<int:id>/restore', methods=['POST'])
@login_required
def restore(id):
    guard = _require_admin()
    if guard:
        return guard

    if request.form.get('confirm_text', '').strip().upper() != 'RESTORE':
        flash('Restore cancelled — confirmation text did not match.', 'warning')
        return redirect(url_for('backup.index'))

    backup = DatabaseBackup.query.get_or_404(id)
    db_path = _get_sqlite_path()
    backup_dir = _get_backup_dir()
    if not db_path or not backup_dir:
        flash('Restore only supports SQLite.', 'danger')
        return redirect(url_for('backup.index'))

    backup_path = os.path.join(backup_dir, backup.filename)

    # Verify the chosen backup BEFORE it's allowed anywhere near the live
    # database — a corrupt/incomplete backup file must never be used to
    # overwrite good data.
    ok, reason = _verify_sqlite_file(backup_path)
    if not ok:
        flash(f'Restore aborted: {backup.filename} failed verification ({reason}). '
              f'The live database was not touched.', 'danger')
        return redirect(url_for('backup.index'))

    try:
        # Safety net: snapshot the CURRENT database before overwriting it,
        # so this restore can always be undone if it turns out to be wrong.
        # create_backup() verifies this snapshot itself before it's recorded.
        safety = create_backup(
            backup_type='safety', user_id=current_user.id,
            note=f'Automatic safety snapshot taken immediately before restoring backup #{backup.id} ({backup.filename}).'
        )

        # Release pooled connections/locks before touching the file on disk.
        db.session.remove()
        db.engine.dispose()

        src_conn = sqlite3.connect(backup_path)
        dest_conn = sqlite3.connect(db_path)
        try:
            with dest_conn:
                src_conn.backup(dest_conn)
        finally:
            src_conn.close()
            dest_conn.close()

        db.engine.dispose()  # drop any pooled connections still holding the old file's state

        # Verify the LIVE file itself immediately after the swap — belt and
        # suspenders on top of verifying the source above. If this ever
        # fails, the safety snapshot just taken is the way back.
        ok, reason = _verify_sqlite_file(db_path)
        if not ok:
            flash(f'CRITICAL: the live database failed verification after restoring ({reason}). '
                  f'Restore it immediately from the safety snapshot {safety.filename} (or an earlier backup) '
                  f'via this same page, then investigate before using the app further.', 'danger')
            _log(f'Restore from {backup.filename} left the live database in a bad state — see safety snapshot {safety.filename}',
                 user_id=current_user.id)
            return redirect(url_for('backup.index'))

        # The DB file we just wrote back is a snapshot from BEFORE this
        # restore and before the safety backup above, so it doesn't contain
        # rows for either — reconcile from disk so nothing looks lost.
        _reconcile_backup_index()

        restored_row = DatabaseBackup.query.filter_by(filename=backup.filename).first()
        if restored_row:
            restored_row.last_restored_at = datetime.utcnow()
            db.session.commit()

        _log(f'Restored database from backup {backup.filename}',
             f'Safety snapshot taken first: {safety.filename}', user_id=current_user.id)
        flash(f'Database restored from {backup.filename}. A safety snapshot of the previous state was saved as '
              f'{safety.filename}. For a fully clean state (all connections/sessions refreshed), restart the '
              f'application now.', 'success')
    except Exception as e:
        current_app.logger.exception('Restore failed')
        flash(f'Restore failed: {e}', 'danger')

    return redirect(url_for('backup.index'))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    guard = _require_admin()
    if guard:
        return guard
    backup = DatabaseBackup.query.get_or_404(id)
    filename = backup.filename
    _delete_backup_files_and_row(backup)
    _log(f'Deleted backup {filename}', user_id=current_user.id)
    flash(f'Backup {filename} deleted.', 'success')
    return redirect(url_for('backup.index'))
