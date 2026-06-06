from flask import Blueprint, render_template, request, abort, jsonify
from sqlalchemy import or_
from app.models import db, File, User, Folder
from app.folders import get_root_folder, get_breadcrumbs, build_folder_tree
from app.embedding import semantic_search, is_embedding_enabled
from app.utils import load_json_tags, format_file_size

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """根目录浏览页"""
    root = get_root_folder()
    return folder_browser(root.id)


@main_bp.route('/folder/<int:folder_id>')
def folder_browser(folder_id):
    """文件夹浏览页"""
    folder = db.session.get(Folder, folder_id)
    if not folder:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = 20
    child_folders = folder.children.order_by(Folder.sort_order.asc(),
                                             Folder.name.asc()).all()
    pagination = File.query.filter_by(folder_id=folder.id)\
        .order_by(File.download_count.desc(), File.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('folder_browser.html',
                           folder=folder,
                           breadcrumbs=get_breadcrumbs(folder),
                           child_folders=child_folders,
                           files=[_file_to_view(f, include_folder=False)
                                  for f in pagination.items],
                           pagination=pagination,
                           query='')


@main_bp.route('/api/folders/tree')
def folder_tree_api():
    """公开文件夹树"""
    return jsonify({'tree': build_folder_tree()})


@main_bp.route('/search')
def search():
    """公开搜索页面"""
    q = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'hybrid').strip()
    folder_id = request.args.get('folder_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = File.query
    if folder_id:
        query = query.filter(File.folder_id == folder_id)

    if q:
        if mode in ('semantic', 'hybrid') and is_embedding_enabled():
            try:
                files = _semantic_or_hybrid_files(q, folder_id, mode)
                total = len(files)
                start = (page - 1) * per_page
                selected = files[start:start + per_page]
                pagination = _ListPagination(selected, page, per_page, total)
                return render_template('search_results.html',
                                       files=[_file_to_view(f) for f in selected],
                                       pagination=pagination,
                                       query=q,
                                       mode=mode,
                                       embedding_enabled=True)
            except RuntimeError:
                mode = 'keyword'

        keywords = q.split()
        for keyword in keywords:
            like_pattern = f'%{keyword}%'
            query = query.outerjoin(Folder, File.folder_id == Folder.id).filter(
                or_(
                    File.title.like(like_pattern),
                    File.original_filename.like(like_pattern),
                    File.search_tags.like(like_pattern),
                    Folder.path.like(like_pattern),
                )
            )

    # 按下载量倒序，其次按上传时间倒序
    query = query.order_by(File.download_count.desc(), File.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('search_results.html',
                           files=[_file_to_view(f) for f in pagination.items],
                           pagination=pagination,
                           query=q,
                           mode=mode,
                           embedding_enabled=is_embedding_enabled())


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
                           breadcrumbs=get_breadcrumbs(f.folder) if f.folder else [],
                           display_tags=load_json_tags(f.display_tags),
                           search_tags=load_json_tags(f.search_tags))


def _file_to_view(f, include_folder=True):
    return {
        'id': f.id,
        'title': f.title,
        'display_tags': load_json_tags(f.display_tags),
        'file_size': f.file_size,
        'created_at': f.created_at,
        'download_count': f.download_count,
        'folder': f.folder,
        'folder_path': f.folder.path if include_folder and f.folder else '',
        'semantic_score': getattr(f, '_semantic_score', None),
    }


def _semantic_or_hybrid_files(q, folder_id, mode):
    semantic_pairs = semantic_search(q, folder_id=folder_id)
    semantic_by_id = {file_record.id: score for file_record, score in semantic_pairs}
    candidates = {file_record.id: file_record for file_record, _ in semantic_pairs}

    if mode == 'hybrid':
        keyword_query = File.query
        if folder_id:
            keyword_query = keyword_query.filter(File.folder_id == folder_id)
        for keyword in q.split():
            like_pattern = f'%{keyword}%'
            keyword_query = keyword_query.outerjoin(Folder, File.folder_id == Folder.id).filter(
                or_(
                    File.title.like(like_pattern),
                    File.original_filename.like(like_pattern),
                    File.search_tags.like(like_pattern),
                    Folder.path.like(like_pattern),
                )
            )
        for file_record in keyword_query.limit(100).all():
            candidates[file_record.id] = file_record

    max_downloads = max((f.download_count for f in candidates.values()), default=0)

    def score(file_record):
        semantic = semantic_by_id.get(file_record.id, 0.0)
        keyword = _keyword_score(file_record, q) if mode == 'hybrid' else 0.0
        popularity = file_record.download_count / max_downloads if max_downloads else 0.0
        total = semantic * 0.45 + keyword * 0.45 + popularity * 0.10
        file_record._semantic_score = semantic
        return total

    return sorted(candidates.values(), key=score, reverse=True)


def _keyword_score(file_record, q):
    haystacks = [
        file_record.title or '',
        file_record.original_filename or '',
        file_record.search_tags or '',
        file_record.folder.path if file_record.folder else '',
    ]
    keywords = q.split()
    if not keywords:
        return 0.0
    hits = sum(1 for keyword in keywords if any(keyword in item for item in haystacks))
    return hits / len(keywords)


class _ListPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = (total + per_page - 1) // per_page if total else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, left_edge=1, left_current=2, right_current=2, right_edge=1):
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge or
                self.page - left_current <= num <= self.page + right_current or
                num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num
