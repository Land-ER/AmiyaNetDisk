import hashlib
import json
import os

from flask import Blueprint, jsonify, request, abort, url_for, current_app, g, send_from_directory
from sqlalchemy import or_

from app.api_tokens import api_token_required
from app.folders import build_folder_tree, create_folder
from app.models import db, File, Folder, OperationLog, DownloadLog
from app.utils import load_json_tags, dump_json_tags, allowed_file, get_file_extension, get_client_ip
from app.embedding import upsert_file_embedding


api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


@api_bp.route('/folders/tree')
@api_token_required('folders:read')
def folders_tree():
    return jsonify({'tree': build_folder_tree()})


@api_bp.route('/folders', methods=['POST'])
@api_token_required('folders:write')
def create_folder_api():
    payload = request.get_json(silent=True) or {}
    try:
        folder = create_folder(
            payload.get('name', ''),
            parent_id=payload.get('parent_id'),
            description=payload.get('description'),
        )
        _log_api_operation('api_create_folder', folder.id, {'path': folder.path})
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'error': 'invalid_folder', 'message': str(exc)}), 400

    return jsonify({'folder': serialize_folder(folder)}), 201


@api_bp.route('/files/<int:file_id>')
@api_token_required('files:read')
def file_detail(file_id):
    file_record = File.query.get(file_id)
    if not file_record:
        abort(404)
    return jsonify({'file': serialize_file(file_record, include_download_url=True)})


@api_bp.route('/files/<int:file_id>/download')
@api_token_required('files:read')
def download_file_api(file_id):
    file_record = File.query.get(file_id)
    if not file_record:
        abort(404)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, file_record.filename_on_disk)
    if not os.path.exists(file_path):
        abort(404)

    file_record.download_count += 1
    db.session.add(DownloadLog(
        file_id=file_record.id,
        user_id=g.api_token.created_by,
        ip_address=get_client_ip(),
    ))
    _log_api_operation('api_download_file', file_record.id, {
        'title': file_record.title,
        'api_token_id': g.api_token.id,
    })
    db.session.commit()

    return send_from_directory(
        upload_folder,
        file_record.filename_on_disk,
        as_attachment=True,
        download_name=file_record.original_filename,
    )


@api_bp.route('/files', methods=['POST'])
@api_token_required('files:upload')
def upload_file_api():
    uploaded_file = request.files.get('file')
    title = (request.form.get('title') or '').strip()
    folder_id = request.form.get('folder_id', type=int)
    if not uploaded_file or not title or not folder_id:
        return jsonify({'error': 'missing_fields',
                        'message': 'file、title、folder_id 均为必填'}), 400

    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify({'error': 'folder_not_found'}), 404

    if not allowed_file(uploaded_file.filename):
        return jsonify({'error': 'unsupported_file_type'}), 400

    file_data = uploaded_file.read()
    file_hash = hashlib.sha256(file_data).hexdigest()
    ext = get_file_extension(uploaded_file.filename)
    filename_on_disk = f'{file_hash}.{ext}' if ext else file_hash

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename_on_disk)
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(file_data)

    search_tags = _split_tags(request.form.get('search_tags', ''))
    display_tags = _split_tags(request.form.get('display_tags', ''))
    file_record = File(
        title=title,
        filename_on_disk=filename_on_disk,
        original_filename=uploaded_file.filename,
        file_size=len(file_data),
        folder_id=folder_id,
        search_tags=dump_json_tags(search_tags),
        display_tags=dump_json_tags(display_tags),
        uploader_id=g.api_token.created_by,
    )
    db.session.add(file_record)
    db.session.flush()
    try:
        upsert_file_embedding(file_record)
    except RuntimeError as exc:
        current_app.logger.warning('API 刷新语义索引失败: %s', exc)
    _log_api_operation('api_upload_file', file_record.id, {
        'title': title,
        'filename': uploaded_file.filename,
        'folder_id': folder_id,
        'size': len(file_data),
    })
    db.session.commit()
    return jsonify({'file': serialize_file(file_record, include_download_url=True)}), 201


@api_bp.route('/search')
@api_token_required('search:read')
def search():
    q = request.args.get('q', '').strip()
    folder_id = request.args.get('folder_id', type=int)
    requested_limit = request.args.get('limit', 20, type=int)
    limit = min(max(requested_limit or 20, 1), 100)

    query = File.query
    if folder_id:
        query = query.filter(File.folder_id == folder_id)
    if q:
        for keyword in q.split():
            like = f'%{keyword}%'
            query = query.outerjoin(Folder, File.folder_id == Folder.id).filter(
                or_(
                    File.title.like(like),
                    File.original_filename.like(like),
                    File.search_tags.like(like),
                    Folder.path.like(like),
                )
            )

    files = query.order_by(File.download_count.desc(), File.created_at.desc()).limit(limit).all()
    return jsonify({'files': [serialize_file(item) for item in files]})


def serialize_folder(folder):
    return {
        'id': folder.id,
        'name': folder.name,
        'parent_id': folder.parent_id,
        'path': folder.path,
        'description': folder.description,
        'created_at': folder.created_at.isoformat() if folder.created_at else None,
        'updated_at': folder.updated_at.isoformat() if folder.updated_at else None,
    }


def serialize_file(file_record, include_download_url=False):
    data = {
        'id': file_record.id,
        'title': file_record.title,
        'original_filename': file_record.original_filename,
        'file_size': file_record.file_size,
        'folder_id': file_record.folder_id,
        'folder_path': file_record.folder.path if file_record.folder else '/',
        'display_tags': load_json_tags(file_record.display_tags),
        'search_tags': load_json_tags(file_record.search_tags),
        'download_count': file_record.download_count,
        'created_at': file_record.created_at.isoformat() if file_record.created_at else None,
        'updated_at': file_record.updated_at.isoformat() if file_record.updated_at else None,
    }
    if include_download_url:
        data['download_url'] = url_for('api.download_file_api', file_id=file_record.id,
                                       _external=False)
    return data


def _split_tags(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def _log_api_operation(action, target_id, detail):
    db.session.add(OperationLog(
        admin_id=g.api_token.created_by,
        action=action,
        target_id=target_id,
        detail=json.dumps({
            'api_token_id': g.api_token.id,
            'api_token_name': g.api_token.name,
            **detail,
        }, ensure_ascii=False),
    ))
