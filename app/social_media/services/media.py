"""Media upload validation, private storage and signed public URLs.

Files are stored under instance/social_media_media/ (never under static/).
Facebook and LinkedIn receive the bytes directly from the server. Instagram
only accepts a public URL that Meta's servers download, so for Instagram the
publisher marks the post's media ``public_enabled`` and hands Meta a signed,
expiring URL (social_media.public_media). Nothing else in instance/ - and no
media of unpublished drafts - is reachable through it.
"""
import os
import uuid

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.social_media import media_root
from app.social_media.services import core

EXT_FOR_MIME = {'image/jpeg': '.jpg', 'image/png': '.png', 'video/mp4': '.mp4', 'video/quicktime': '.mov'}
SIGNER_SALT = 'social-media-public-media'


class MediaError(ValueError):
    pass


def _sniff(head):
    """Content type from the file's first bytes; the browser's claim is not trusted."""
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if len(head) >= 12 and head[4:8] == b'ftyp':
        brand = head[8:12]
        return 'video/quicktime' if brand == b'qt  ' else 'video/mp4'
    return None


def allowed_types():
    img = [t.strip() for t in core.get('allowed_image_types').split(',') if t.strip()]
    vid = [t.strip() for t in core.get('allowed_video_types').split(',') if t.strip()]
    return img, vid


def save_upload(file_storage):
    """Validate and store one werkzeug FileStorage. Returns a dict of
    SocialPostMedia fields. Raises MediaError with a user-facing message."""
    name = os.path.basename(file_storage.filename or 'upload')
    head = file_storage.stream.read(64)
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    mime = _sniff(head)
    img_types, vid_types = allowed_types()
    if mime is None or mime not in img_types + vid_types:
        raise MediaError(f'"{name}" is not an allowed file type. Allowed: '
                         f'{", ".join(img_types + vid_types)}.')
    kind = 'image' if mime.startswith('image/') else 'video'
    limit_mb = core.get_int('max_image_mb' if kind == 'image' else 'max_video_mb', 8)
    if size > limit_mb * 1024 * 1024:
        raise MediaError(f'"{name}" is {size / 1048576:.1f} MB; the limit for {kind}s is {limit_mb} MB.')
    if size == 0:
        raise MediaError(f'"{name}" is empty.')
    width = height = None
    if kind == 'image':
        try:
            from PIL import Image
            with Image.open(file_storage.stream) as im:
                im.verify()
            file_storage.stream.seek(0)
            with Image.open(file_storage.stream) as im:
                width, height = im.size
        except Exception:
            raise MediaError(f'"{name}" is not a valid image.')
        finally:
            file_storage.stream.seek(0)
    stored = uuid.uuid4().hex + EXT_FOR_MIME[mime]
    file_storage.save(os.path.join(media_root(), stored))
    return {'kind': kind, 'stored_name': stored, 'original_name': name[:255], 'mime_type': mime,
            'size_bytes': size, 'width': width, 'height': height}


def path_for(media):
    root = os.path.realpath(media_root())
    path = os.path.realpath(os.path.join(root, media.stored_name))
    if not path.startswith(root + os.sep):
        raise MediaError('Invalid media path.')
    return path


def read_bytes(media):
    with open(path_for(media), 'rb') as fh:
        return fh.read()


def delete_file(media):
    try:
        os.remove(path_for(media))
    except (OSError, MediaError):
        pass


def _signer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=SIGNER_SALT)


def public_url(media):
    """Signed URL Meta can download; '' if no public base URL is configured."""
    token = _signer().dumps({'m': media.id, 'n': media.stored_name})
    return core.external_url('social_media.public_media', token=token)


def resolve_token(token):
    """SocialPostMedia for a valid, unexpired token whose media was released for publishing, else None."""
    from app.social_media.models import SocialPostMedia
    max_age = max(1, core.get_int('public_media_hours', 72)) * 3600
    try:
        data = _signer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    media = SocialPostMedia.query.get(data.get('m'))
    if media is None or media.stored_name != data.get('n') or not media.public_enabled:
        return None
    return media


def validate_for_platform(platform, post, media_list, text, ig_media_type=None):
    """Content rules per platform. Returns a list of problems (empty = OK).
    Limits from the platforms' publishing docs; the platform has the final word."""
    problems = []
    images = [m for m in media_list if m.kind == 'image']
    videos = [m for m in media_list if m.kind == 'video']
    if platform == 'facebook':
        if len(text) > 63206:
            problems.append('Facebook posts are limited to 63,206 characters.')
        if videos and (images or len(videos) > 1):
            problems.append('Facebook: a video post can contain only one video and no images.')
        if not text and not media_list and not post.link_url:
            problems.append('Facebook: add text, a link or media.')
    elif platform == 'instagram':
        if not media_list:
            problems.append('Instagram requires at least one image or video.')
        if len(media_list) > 10:
            problems.append('Instagram carousels can contain at most 10 items.')
        if len(text) > 2200:
            problems.append('Instagram captions are limited to 2,200 characters.')
        if text.count('#') > 30:
            problems.append('Instagram allows at most 30 hashtags.')
        for m in images:
            if m.mime_type != 'image/jpeg':
                problems.append(f'Instagram only accepts JPEG images ("{m.original_name}" is {m.mime_type}).')
            if m.size_bytes > 8 * 1024 * 1024:
                problems.append(f'Instagram images must be 8 MB or smaller ("{m.original_name}").')
            if m.width and m.height and len(media_list) == 1:
                ratio = m.width / m.height
                if ratio < 0.8 - 0.005 or ratio > 1.91 + 0.005:
                    problems.append(f'Instagram feed images need an aspect ratio between 4:5 and 1.91:1 '
                                    f'("{m.original_name}" is {m.width}x{m.height}).')
    elif platform == 'linkedin':
        if len(text) > 3000:
            problems.append('LinkedIn posts are limited to 3,000 characters.')
        if videos and (images or len(videos) > 1):
            problems.append('LinkedIn: a video post can contain only one video and no images.')
        if len(images) > 20:
            problems.append('LinkedIn multi-image posts can contain at most 20 images.')
        if not text and not media_list:
            problems.append('LinkedIn: add text or media.')
    return problems
