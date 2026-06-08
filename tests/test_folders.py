from io import BytesIO

from app.folders import create_folder, get_root_folder
from app.models import File, Folder
from app.utils import compute_file_hash
from conftest import csrf_from_response, login_as


def test_root_folder_and_public_tree(client, app):
    with app.app_context():
        root = get_root_folder()
        assert root.path == '/'

    response = client.get('/api/folders/tree')
    assert response.status_code == 200
    assert response.json['tree'][0]['path'] == '/'


def test_admin_creates_folder_and_uploads_file(client, app, root_user, monkeypatch):
    login_as(client, root_user)
    file_data = b'linear algebra notes'
    hash_calls = []

    def fake_compute_file_hash(data):
        hash_calls.append(data)
        return compute_file_hash(data)

    from app.routes import admin as admin_routes
    monkeypatch.setattr(admin_routes, 'compute_file_hash', fake_compute_file_hash)

    page = client.get('/admin/folders')
    token = csrf_from_response(page)

    response = client.post('/admin/folder/create', data={
        'csrf_token': token,
        'parent_id': get_root_id(app),
        'name': '数学学院',
    })
    assert response.status_code == 302

    with app.app_context():
        folder = Folder.query.filter_by(name='数学学院').first()
        assert folder is not None
        assert folder.path == '/数学学院'
        folder_id = folder.id

    upload_page = client.get('/admin/upload')
    token = csrf_from_response(upload_page)
    response = client.post('/admin/upload', data={
        'csrf_token': token,
        'title': '高等代数期末复习资料',
        'folder_id': str(folder_id),
        'search_tags': '数学, 代数, 期末',
        'display_tags': '数学, 期末',
        'file': (BytesIO(file_data), 'algebra.txt'),
    }, content_type='multipart/form-data')
    assert response.status_code == 302

    with app.app_context():
        file_record = File.query.filter_by(title='高等代数期末复习资料').first()
        assert file_record is not None
        assert file_record.folder_id == folder_id
        assert file_record.filename_on_disk == f'{compute_file_hash(file_data)}.txt'
    assert hash_calls == [file_data]

    folder_page = client.get(f'/folder/{folder_id}')
    assert folder_page.status_code == 200
    assert '高等代数期末复习资料'.encode('utf-8') in folder_page.data

    search_page = client.get('/search?q=代数&mode=keyword')
    assert search_page.status_code == 200
    assert '高等代数期末复习资料'.encode('utf-8') in search_page.data


def test_folder_search_includes_descendants(client, app, db_session, root_user):
    with app.app_context():
        root = get_root_folder()
        school = create_folder('计算学部', parent_id=root.id)
        course = create_folder('数据结构', parent_id=school.id)
        sibling = create_folder('物理学院', parent_id=root.id)
        deep_file = File(
            title='递归搜索命中资料',
            filename_on_disk='recursive.txt',
            original_filename='recursive.txt',
            file_size=128,
            search_tags='["递归搜索"]',
            display_tags='["测试"]',
            folder_id=course.id,
            uploader_id=root_user.id,
        )
        sibling_file = File(
            title='兄弟目录资料',
            filename_on_disk='sibling.txt',
            original_filename='sibling.txt',
            file_size=128,
            search_tags='["兄弟目录"]',
            display_tags='["测试"]',
            folder_id=sibling.id,
            uploader_id=root_user.id,
        )
        db_session.add_all([deep_file, sibling_file])
        db_session.commit()
        root_id = root.id
        school_id = school.id
        sibling_id = sibling.id

    root_search = client.get(f'/search?q=递归搜索&mode=keyword&folder_id={root_id}')
    assert root_search.status_code == 200
    assert '递归搜索命中资料'.encode('utf-8') in root_search.data

    parent_search = client.get(f'/search?q=递归搜索&mode=keyword&folder_id={school_id}')
    assert parent_search.status_code == 200
    assert '递归搜索命中资料'.encode('utf-8') in parent_search.data

    sibling_search = client.get(f'/search?q=递归搜索&mode=keyword&folder_id={sibling_id}')
    assert sibling_search.status_code == 200
    assert '递归搜索命中资料'.encode('utf-8') not in sibling_search.data


def test_home_search_is_global_but_child_folder_search_is_scoped(client, app, db_session):
    with app.app_context():
        root = get_root_folder()
        child = create_folder('首页搜索范围', parent_id=root.id)
        db_session.commit()
        child_id = child.id

    home_page = client.get('/')
    assert home_page.status_code == 200
    assert f'name="folder_id" value="{get_root_id(app)}"'.encode('utf-8') not in home_page.data
    assert '搜索全部文件...'.encode('utf-8') in home_page.data

    child_page = client.get(f'/folder/{child_id}')
    assert child_page.status_code == 200
    assert f'name="folder_id" value="{child_id}"'.encode('utf-8') in child_page.data
    assert '在当前文件夹搜索...'.encode('utf-8') in child_page.data


def test_folder_validation_rejects_abuse(client, app, root_user, db_session):
    login_as(client, root_user)
    root_id = get_root_id(app)

    page = client.get('/admin/folders')
    token = csrf_from_response(page)
    response = client.post('/admin/folder/create', data={
        'csrf_token': token,
        'parent_id': root_id,
        'name': '../escape',
    }, follow_redirects=True)
    assert '文件夹名称不能包含路径分隔符'.encode('utf-8') in response.data

    page = client.get('/admin/folders')
    token = csrf_from_response(page)
    client.post('/admin/folder/create', data={
        'csrf_token': token,
        'parent_id': root_id,
        'name': '安全测试',
    })

    page = client.get('/admin/folders')
    token = csrf_from_response(page)
    response = client.post('/admin/folder/create', data={
        'csrf_token': token,
        'parent_id': root_id,
        'name': '安全测试',
    }, follow_redirects=True)
    assert '同级目录下已存在同名文件夹'.encode('utf-8') in response.data

    with app.app_context():
        parent = Folder.query.filter_by(name='安全测试').first()
        child = Folder(name='子目录', parent_id=parent.id, path=f'{parent.path}/子目录')
        db_session.add(child)
        db_session.commit()
        parent_id = parent.id
        child_id = child.id

    page = client.get('/admin/folders')
    token = csrf_from_response(page)
    response = client.post(f'/admin/folder/{parent_id}/move', data={
        'csrf_token': token,
        'parent_id': child_id,
    }, follow_redirects=True)
    assert '不能移动到自己的子文件夹下'.encode('utf-8') in response.data


def get_root_id(app):
    with app.app_context():
        return get_root_folder().id
