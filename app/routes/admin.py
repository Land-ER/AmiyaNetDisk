import os
import json
import hashlib
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename
from app.models import db, File, DownloadLog, OperationLog, User
from app.forms import UploadForm, FileEditForm
from app.decorators import admin_required
from app.utils import allowed_file, get_file_extension, format_file_size, load_json_tags, dump_json_tags

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """管理员仪表盘"""
    total_files = File.query.count()
    total_downloads = db.session.query(db.func.sum(File.download_count)).scalar() or 0
    total_users = User.query.count()

    # 最近上传
    recent_files = File.query.order_by(File.created_at.desc()).limit(10).all()

    # 下载排行 Top 10
    top_files = File.query.order_by(File.download_count.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           total_files=total_files,
                           total_downloads=total_downloads,
                           total_users=total_users,
                           recent_files=recent_files,
                           top_files=top_files)


@admin_bp.route('/files')
@admin_required
def file_list():
    """文件管理列表"""
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 20

    query = File.query
    if q:
        like_pattern = f'%{q}%'
        query = query.filter(File.title.like(like_pattern) | File.original_filename.like(like_pattern))

    query = query.order_by(File.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/files.html',
                           files=pagination.items,
                           pagination=pagination,
                           query=q)


@admin_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    """上传文件"""
    form = UploadForm()
    if form.validate_on_submit():
        uploaded_file = form.file.data
        title = form.title.data.strip()
        search_tags_str = form.search_tags.data.strip()
        display_tags_str = form.display_tags.data.strip()

        # 检查文件扩展名
        if not allowed_file(uploaded_file.filename):
            flash('不支持的文件类型', 'danger')
            return render_template('admin/upload.html', form=form)

        # 读取文件内容并计算哈希
        file_data = uploaded_file.read()
        sha256 = hashlib.sha256()
        sha256.update(file_data)
        file_hash = sha256.hexdigest()

        # 保留原始扩展名
        ext = get_file_extension(uploaded_file.filename)
        filename_on_disk = f'{file_hash}.{ext}' if ext else file_hash

        # 处理标签
        search_tags = [t.strip() for t in search_tags_str.split(',') if t.strip()] if search_tags_str else []
        display_tags = [t.strip() for t in display_tags_str.split(',') if t.strip()] if display_tags_str else []

        # 保存文件（如果已存在则秒传）
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename_on_disk)
        if not os.path.exists(file_path):
            with open(file_path, 'wb') as f:
                f.write(file_data)

        # 创建数据库记录
        file_record = File(
            title=title,
            filename_on_disk=filename_on_disk,
            original_filename=uploaded_file.filename,
            file_size=len(file_data),
            search_tags=dump_json_tags(search_tags),
            display_tags=dump_json_tags(display_tags),
            uploader_id=current_user.id,
        )
        db.session.add(file_record)
        db.session.flush()

        # 操作日志
        log = OperationLog(
            admin_id=current_user.id,
            action='upload',
            target_id=file_record.id,
            detail=json.dumps({'title': title, 'filename': uploaded_file.filename, 'size': len(file_data)}),
        )
        db.session.add(log)
        db.session.commit()

        flash(f'文件 "{title}" 上传成功', 'success')
        return redirect(url_for('admin.file_list'))

    return render_template('admin/upload.html', form=form)


@admin_bp.route('/file/<int:file_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_file(file_id):
    """编辑文件信息"""
    file_record = db.session.get(File, file_id)
    if not file_record:
        flash('文件不存在', 'danger')
        return redirect(url_for('admin.file_list'))

    form = FileEditForm(obj=file_record)
    if form.validate_on_submit():
        file_record.title = form.title.data.strip()
        search_tags_str = form.search_tags.data.strip()
        display_tags_str = form.display_tags.data.strip()

        file_record.search_tags = dump_json_tags(
            [t.strip() for t in search_tags_str.split(',') if t.strip()]
        ) if search_tags_str else '[]'
        file_record.display_tags = dump_json_tags(
            [t.strip() for t in display_tags_str.split(',') if t.strip()]
        ) if display_tags_str else '[]'
        file_record.updated_at = datetime.now(timezone.utc)

        # 操作日志
        log = OperationLog(
            admin_id=current_user.id,
            action='edit_tags',
            target_id=file_record.id,
            detail=json.dumps({'title': file_record.title}),
        )
        db.session.add(log)
        db.session.commit()

        flash('文件信息已更新', 'success')
        return redirect(url_for('admin.file_list'))

    # 预填标签
    form.search_tags.data = ', '.join(load_json_tags(file_record.search_tags))
    form.display_tags.data = ', '.join(load_json_tags(file_record.display_tags))

    return render_template('admin/edit_file.html', form=form, file=file_record)


@admin_bp.route('/file/<int:file_id>/delete', methods=['POST'])
@admin_required
def delete_file(file_id):
    """删除文件"""
    file_record = db.session.get(File, file_id)
    if not file_record:
        flash('文件不存在', 'danger')
        return redirect(url_for('admin.file_list'))

    filename_on_disk = file_record.filename_on_disk
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, filename_on_disk)

    # 删除数据库记录
    db.session.delete(file_record)

    # 检查文件是否还被其他记录引用
    remaining = File.query.filter_by(filename_on_disk=filename_on_disk).count()
    if remaining == 1:  # 只有当前这条（已删除，但计数可能为0）
        pass  # 已删除，检查物理文件
    if remaining <= 1 and os.path.exists(file_path):
        os.remove(file_path)

    # 操作日志
    log = OperationLog(
        admin_id=current_user.id,
        action='delete',
        target_id=file_record.id,
        detail=json.dumps({'title': file_record.title, 'filename': filename_on_disk}),
    )
    db.session.add(log)
    db.session.commit()

    flash(f'文件 "{file_record.title}" 已删除', 'success')
    return redirect(url_for('admin.file_list'))


@admin_bp.route('/download_logs')
@admin_required
def download_logs():
    """下载日志查看"""
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 30

    query = DownloadLog.query

    if q:
        # 按文件名或用户邮箱搜索
        query = query.join(File).join(User, DownloadLog.user_id == User.id).filter(
            File.title.like(f'%{q}%') | User.email.like(f'%{q}%')
        )

    query = query.order_by(DownloadLog.downloaded_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/download_logs.html',
                           logs=pagination.items,
                           pagination=pagination,
                           query=q)


@admin_bp.route('/users')
@admin_required
def user_list():
    """用户管理列表"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    users = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('admin/users.html', users=users)


@admin_bp.route('/user/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    """禁用用户"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('admin.user_list'))

    if user.is_root():
        flash('不能禁用 root 用户', 'danger')
        return redirect(url_for('admin.user_list'))

    user.is_active = False

    log = OperationLog(
        admin_id=current_user.id,
        action='ban_user',
        target_id=user.id,
        detail=json.dumps({'email': user.email}),
    )
    db.session.add(log)
    db.session.commit()

    flash(f'用户 {user.email} 已被禁用', 'success')
    return redirect(url_for('admin.user_list'))


@admin_bp.route('/user/<int:user_id>/unban', methods=['POST'])
@admin_required
def unban_user(user_id):
    """启用用户"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('admin.user_list'))

    user.is_active = True

    log = OperationLog(
        admin_id=current_user.id,
        action='unban_user',
        target_id=user.id,
        detail=json.dumps({'email': user.email}),
    )
    db.session.add(log)
    db.session.commit()

    flash(f'用户 {user.email} 已启用', 'success')
    return redirect(url_for('admin.user_list'))
