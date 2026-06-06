from io import BytesIO

from app.folders import get_root_folder
from app.models import File, Folder
from conftest import csrf_from_response, login_as


def test_root_folder_and_public_tree(client, app):
    with app.app_context():
        root = get_root_folder()
        assert root.path == '/'

    response = client.get('/api/folders/tree')
    assert response.status_code == 200
    assert response.json['tree'][0]['path'] == '/'


def test_admin_creates_folder_and_uploads_file(client, app, root_user):
    login_as(client, root_user)

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
        'file': (BytesIO(b'linear algebra notes'), 'algebra.txt'),
    }, content_type='multipart/form-data')
    assert response.status_code == 302

    with app.app_context():
        file_record = File.query.filter_by(title='高等代数期末复习资料').first()
        assert file_record is not None
        assert file_record.folder_id == folder_id

    folder_page = client.get(f'/folder/{folder_id}')
    assert folder_page.status_code == 200
    assert '高等代数期末复习资料'.encode('utf-8') in folder_page.data

    search_page = client.get('/search?q=代数&mode=keyword')
    assert search_page.status_code == 200
    assert '高等代数期末复习资料'.encode('utf-8') in search_page.data


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
