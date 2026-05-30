import json
from flask import Blueprint, render_template, request, abort
from app.models import db, File, User
from app.utils import load_json_tags, format_file_size

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页重定向到搜索页"""
    return search()


@main_bp.route('/search')
def search():
    """公开搜索页面"""
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = File.query

    if q:
        # 空格分隔的多词模糊匹配
        keywords = q.split()
        for keyword in keywords:
            like_pattern = f'%{keyword}%'
            query = query.filter(
                File.title.like(like_pattern) |
                File.search_tags.like(like_pattern)
            )

    # 按下载量倒序，其次按上传时间倒序
    query = query.order_by(File.download_count.desc(), File.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    files = pagination.items

    # 处理每文件的标签
    file_list = []
    for f in files:
        file_list.append({
            'id': f.id,
            'title': f.title,
            'display_tags': load_json_tags(f.display_tags),
            'file_size': f.file_size,
            'created_at': f.created_at,
            'download_count': f.download_count,
        })

    return render_template('search_results.html',
                           files=file_list,
                           pagination=pagination,
                           query=q)


@main_bp.route('/file/<int:file_id>')
def file_detail(file_id):
    """文件详情页（公开访问）"""
    f = db.session.get(File, file_id)
    if not f:
        abort(404)

    uploader = db.session.get(User, f.uploader_id)

    return render_template('file_detail.html',
                           file=f,
                           uploader=uploader,
                           display_tags=load_json_tags(f.display_tags),
                           search_tags=load_json_tags(f.search_tags))
