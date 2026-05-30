import os
from flask import Blueprint, send_from_directory, abort, current_app
from flask_login import login_required, current_user
from app.models import db, File, DownloadLog, User
from app.utils import get_client_ip

file_bp = Blueprint('file', __name__)


@file_bp.route('/download/<int:file_id>')
@login_required
def download(file_id):
    """文件下载"""
    file_record = db.session.get(File, file_id)
    if not file_record:
        abort(404)

    # 记录下载日志
    log = DownloadLog(
        file_id=file_record.id,
        user_id=current_user.id,
        ip_address=get_client_ip(),
    )
    db.session.add(log)

    # 更新下载计数
    file_record.download_count += 1
    db.session.commit()

    # 发送文件
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(
        upload_folder,
        file_record.filename_on_disk,
        download_name=file_record.original_filename,
        as_attachment=True,
    )
