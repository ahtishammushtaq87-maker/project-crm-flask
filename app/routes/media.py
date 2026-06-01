import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from flask_login import login_required, current_user
from app.models import Media
from app import db
from werkzeug.utils import secure_filename
from datetime import datetime

bp = Blueprint('media', __name__)

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

@bp.route('/')
@login_required
def index():
    if not current_user.is_admin and not current_user.can_view_media:
        flash('You do not have permission to view media.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    documents = Media.query.order_by(Media.uploaded_at.desc()).all()
    return render_template('media/list.html', documents=documents)

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if not current_user.is_admin and not current_user.can_add_media:
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
    db.session.add(new_media)
    db.session.commit()
    
    return jsonify({
        'message': 'File uploaded successfully',
        'id': new_media.id,
        'filename': new_media.filename
    }), 200

@bp.route('/download/<int:media_id>')
@login_required
def download(media_id):
    if not current_user.is_admin and not current_user.can_view_media_document:
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))
    
    document = Media.query.get_or_404(media_id)
    directory = os.path.join(current_app.static_folder, 'uploads', 'media')
    stored_filename = os.path.basename(document.filepath)
    
    return send_from_directory(directory, stored_filename, as_attachment=True, download_name=document.filename)

@bp.route('/view/<int:media_id>')
@login_required
def view(media_id):
    if not current_user.is_admin and not current_user.can_view_media_document:
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))
    
    document = Media.query.get_or_404(media_id)
    return redirect(url_for('static', filename=document.filepath))

@bp.route('/delete/<int:media_id>', methods=['POST'])
@login_required
def delete(media_id):
    if not current_user.is_admin and not current_user.can_delete_media:
        flash('Permission denied', 'danger')
        return redirect(url_for('media.index'))
    
    document = Media.query.get_or_404(media_id)
    
    # Delete file from filesystem
    rel_path = document.filepath.replace('/', os.sep)
    filepath = os.path.join(current_app.static_folder, rel_path)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            current_app.logger.error(f"Error deleting file: {e}")
    
    db.session.delete(document)
    db.session.commit()
    
    flash('Document deleted successfully.', 'success')
    return redirect(url_for('media.index'))
