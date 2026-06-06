from datetime import datetime

from app.models import db, Folder, File


ROOT_FOLDER_NAME = '全部资料'


def normalize_folder_name(name):
    return (name or '').strip()


def validate_folder_name(name):
    name = normalize_folder_name(name)
    if not name:
        raise ValueError('文件夹名称不能为空')
    if '/' in name or '\\' in name:
        raise ValueError('文件夹名称不能包含路径分隔符')
    if len(name) > 120:
        raise ValueError('文件夹名称不能超过120个字符')
    return name


def get_root_folder():
    root = Folder.query.filter_by(parent_id=None).order_by(Folder.id.asc()).first()
    if root:
        return root

    root = Folder(name=ROOT_FOLDER_NAME, parent_id=None, path='/')
    db.session.add(root)
    db.session.flush()
    return root


def build_folder_path(name, parent):
    if not parent:
        return '/'
    parent_path = parent.path.rstrip('/')
    return f'{parent_path}/{name}' if parent_path else f'/{name}'


def ensure_unique_sibling(name, parent_id, exclude_id=None):
    query = Folder.query.filter_by(name=name, parent_id=parent_id)
    if exclude_id is not None:
        query = query.filter(Folder.id != exclude_id)
    if query.first():
        raise ValueError('同级目录下已存在同名文件夹')


def create_folder(name, parent_id=None, description=None, sort_order=0):
    name = validate_folder_name(name)
    parent = db.session.get(Folder, parent_id) if parent_id else get_root_folder()
    if parent and parent.parent_id is None and parent.path == '/' and parent_id is None:
        parent_id = parent.id
    if not parent:
        raise ValueError('父文件夹不存在')

    ensure_unique_sibling(name, parent.id)
    folder = Folder(
        name=name,
        parent_id=parent.id,
        path=build_folder_path(name, parent),
        description=(description or '').strip() or None,
        sort_order=sort_order or 0,
    )
    db.session.add(folder)
    db.session.flush()
    return folder


def rename_folder(folder, new_name):
    if folder.parent_id is None:
        raise ValueError('根目录不能重命名')
    new_name = validate_folder_name(new_name)
    ensure_unique_sibling(new_name, folder.parent_id, exclude_id=folder.id)
    old_path = folder.path
    folder.name = new_name
    folder.path = build_folder_path(new_name, folder.parent)
    folder.updated_at = datetime.utcnow()
    _update_descendant_paths(folder, old_path)
    return folder


def move_folder(folder, new_parent_id):
    if folder.parent_id is None:
        raise ValueError('根目录不能移动')
    new_parent = db.session.get(Folder, new_parent_id)
    if not new_parent:
        raise ValueError('目标文件夹不存在')
    if new_parent.id == folder.id:
        raise ValueError('不能移动到自身下')
    descendant_ids = set(get_descendant_ids(folder))
    if new_parent.id in descendant_ids:
        raise ValueError('不能移动到自己的子文件夹下')

    ensure_unique_sibling(folder.name, new_parent.id, exclude_id=folder.id)
    old_path = folder.path
    folder.parent_id = new_parent.id
    folder.path = build_folder_path(folder.name, new_parent)
    folder.updated_at = datetime.utcnow()
    _update_descendant_paths(folder, old_path)
    return folder


def delete_folder(folder):
    if folder.parent_id is None:
        raise ValueError('根目录不能删除')
    if folder.children.count() > 0 or folder.files.count() > 0:
        raise ValueError('请先清空文件夹后再删除')
    db.session.delete(folder)


def _update_descendant_paths(folder, old_path):
    descendants = Folder.query.filter(
        Folder.path.like(f'{old_path.rstrip("/")}/%')
    ).order_by(Folder.path.asc()).all()
    for child in descendants:
        suffix = child.path[len(old_path.rstrip('/')):]
        child.path = f'{folder.path.rstrip("/")}{suffix}'
        child.updated_at = datetime.utcnow()


def get_descendant_ids(folder):
    ids = []
    queue = list(folder.children.order_by(Folder.sort_order.asc(), Folder.name.asc()).all())
    while queue:
        current = queue.pop(0)
        ids.append(current.id)
        queue.extend(current.children.order_by(Folder.sort_order.asc(), Folder.name.asc()).all())
    return ids


def get_breadcrumbs(folder):
    breadcrumbs = []
    current = folder
    while current:
        breadcrumbs.append(current)
        current = current.parent
    return list(reversed(breadcrumbs))


def get_folder_options():
    root = get_root_folder()
    folders = Folder.query.order_by(Folder.path.asc()).all()
    options = []
    for folder in folders:
        label = '全部资料' if folder.id == root.id else folder.path
        options.append((folder.id, label))
    return options


def build_folder_tree():
    folders = Folder.query.order_by(Folder.parent_id.asc(), Folder.sort_order.asc(),
                                    Folder.name.asc()).all()
    by_parent = {}
    for folder in folders:
        by_parent.setdefault(folder.parent_id, []).append(folder)

    def serialize(folder):
        return {
            'id': folder.id,
            'name': folder.name,
            'path': folder.path,
            'children': [serialize(child) for child in by_parent.get(folder.id, [])],
        }

    roots = by_parent.get(None, [])
    return [serialize(folder) for folder in roots]


def assign_unfiled_files_to_root():
    root = get_root_folder()
    File.query.filter(File.folder_id.is_(None)).update(
        {'folder_id': root.id},
        synchronize_session=False,
    )
    return root
