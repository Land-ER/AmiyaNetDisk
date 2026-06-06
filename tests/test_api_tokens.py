from io import BytesIO
import uuid

from app.api_tokens import create_api_token
from app.folders import get_root_folder
from app.models import ApiToken, File, Folder, OperationLog, DownloadLog
from conftest import csrf_from_response, login_as


def test_api_requires_bearer_token(client):
    response = client.get('/api/v1/folders/tree')
    assert response.status_code == 401
    assert response.json['error'] == 'missing_bearer_token'


def test_api_scope_enforcement_and_read_endpoints(client, app, db_session, root_user):
    with app.app_context():
        folders_token, folders_plain = create_api_token('folders', ['folders:read'], root_user.id)
        search_token, search_plain = create_api_token('search', ['search:read', 'files:read'], root_user.id)
        root = get_root_folder()
        file_record = File(
            title='机器人接口测试资料',
            filename_on_disk='api-test.txt',
            original_filename='api-test.txt',
            file_size=4,
            folder_id=root.id,
            uploader_id=root_user.id,
        )
        db_session.add(file_record)
        db_session.commit()
        folders_token_id = folders_token.id
        file_id = file_record.id

    response = client.get('/api/v1/folders/tree',
                          headers={'Authorization': f'Bearer {folders_plain}'})
    assert response.status_code == 200
    assert response.json['tree'][0]['path'] == '/'

    response = client.get('/api/v1/search?q=机器人',
                          headers={'Authorization': f'Bearer {folders_plain}'})
    assert response.status_code == 403
    assert response.json['error'] == 'insufficient_scope'

    response = client.get('/api/v1/search?q=机器人',
                          headers={'Authorization': f'Bearer {search_plain}'})
    assert response.status_code == 200
    assert response.json['files'][0]['title'] == '机器人接口测试资料'

    response = client.get(f'/api/v1/files/{file_id}',
                          headers={'Authorization': f'Bearer {search_plain}'})
    assert response.status_code == 200
    assert response.json['file']['download_url'] == f'/api/v1/files/{file_id}/download'

    with app.app_context():
        token_record = ApiToken.query.get(folders_token_id)
        assert token_record.last_used_at is not None


def test_api_search_limit_is_clamped(client, app, db_session, root_user):
    with app.app_context():
        _, plain = create_api_token('search-limit', ['search:read'], root_user.id)
        root = get_root_folder()
        for index in range(30):
            db_session.add(File(
                title=f'limit item {index}',
                filename_on_disk=f'limit-{index}.txt',
                original_filename=f'limit-{index}.txt',
                file_size=1,
                folder_id=root.id,
                uploader_id=root_user.id,
            ))
        db_session.commit()

    response = client.get('/api/v1/search?q=limit&limit=-1',
                          headers={'Authorization': f'Bearer {plain}'})
    assert response.status_code == 200
    assert len(response.json['files']) == 1

    response = client.get('/api/v1/search?q=limit&limit=500',
                          headers={'Authorization': f'Bearer {plain}'})
    assert response.status_code == 200
    assert len(response.json['files']) == 30


def test_api_token_owner_must_remain_active_admin(client, app, db_session):
    from werkzeug.security import generate_password_hash
    from app.models import User

    with app.app_context():
        admin = User(
            email='token-owner@example.com',
            password_hash=generate_password_hash('password'),
            role='admin',
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()
        _, plain = create_api_token('owned-token', ['folders:read'], admin.id)
        db_session.commit()
        admin.is_active = False
        db_session.commit()

    response = client.get('/api/v1/folders/tree',
                          headers={'Authorization': f'Bearer {plain}'})
    assert response.status_code == 401
    assert response.json['error'] == 'invalid_token_owner'


def test_admin_can_create_and_disable_api_token(client, app, root_user):
    login_as(client, root_user)

    page = client.get('/admin/api_tokens')
    assert page.status_code == 200
    token = csrf_from_response(page)

    response = client.post('/admin/api_token/create', data={
        'csrf_token': token,
        'name': '检索机器人',
        'scopes': ['folders:read', 'search:read'],
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'API Token 已创建'.encode('utf-8') in response.data
    assert b'and_' in response.data

    with app.app_context():
        token_record = ApiToken.query.filter_by(name='检索机器人').first()
        assert token_record is not None
        token_id = token_record.id

    page = client.get('/admin/api_tokens')
    token = csrf_from_response(page)
    response = client.post(f'/admin/api_token/{token_id}/disable',
                           data={'csrf_token': token},
                           follow_redirects=True)
    assert response.status_code == 200
    assert 'API Token 已停用'.encode('utf-8') in response.data

    with app.app_context():
        assert ApiToken.query.get(token_id).is_active is False


def test_admin_rejects_unknown_api_token_scopes(client, app, root_user):
    login_as(client, root_user)

    page = client.get('/admin/api_tokens')
    token = csrf_from_response(page)
    response = client.post('/admin/api_token/create', data={
        'csrf_token': token,
        'name': '伪造权限',
        'scopes': ['unknown:scope'],
    }, follow_redirects=True)

    assert response.status_code == 200
    assert '请至少选择一个权限范围'.encode('utf-8') in response.data
    with app.app_context():
        assert ApiToken.query.filter_by(name='伪造权限').first() is None


def test_api_write_scopes_create_folder_and_upload_file(client, app, db_session, root_user):
    folder_name = f'API 创建目录 {uuid.uuid4().hex[:8]}'
    with app.app_context():
        _, read_plain = create_api_token('read-only', ['folders:read'], root_user.id)
        _, write_plain = create_api_token(
            'writer',
            ['folders:write', 'files:upload', 'files:read', 'search:read'],
            root_user.id,
        )
        root_id = get_root_folder().id
        db_session.commit()

    denied = client.post('/api/v1/folders', json={
        'parent_id': root_id,
        'name': folder_name,
    }, headers={'Authorization': f'Bearer {read_plain}'})
    assert denied.status_code == 403

    created = client.post('/api/v1/folders', json={
        'parent_id': root_id,
        'name': folder_name,
    }, headers={'Authorization': f'Bearer {write_plain}'})
    assert created.status_code == 201
    assert created.json['folder']['path'] == f'/{folder_name}'
    folder_id = created.json['folder']['id']

    upload = client.post('/api/v1/files', data={
        'title': 'API 上传资料',
        'folder_id': str(folder_id),
        'search_tags': 'api, 自动化',
        'display_tags': 'API',
        'file': (BytesIO(b'api upload'), 'api.txt'),
    }, content_type='multipart/form-data',
        headers={'Authorization': f'Bearer {write_plain}'})
    assert upload.status_code == 201
    assert upload.json['file']['title'] == 'API 上传资料'
    assert upload.json['file']['folder_id'] == folder_id
    file_id = upload.json['file']['id']

    with app.app_context():
        folder = Folder.query.get(folder_id)
        file_record = File.query.get(file_id)
        assert folder.path == f'/{folder_name}'
        assert file_record.original_filename == 'api.txt'
        assert OperationLog.query.filter_by(action='api_create_folder',
                                            target_id=folder_id).first() is not None
        assert OperationLog.query.filter_by(action='api_upload_file',
                                            target_id=file_id).first() is not None

    search = client.get('/api/v1/search?q=上传',
                        headers={'Authorization': f'Bearer {write_plain}'})
    assert search.status_code == 200
    assert search.json['files'][0]['id'] == file_id


def test_api_upload_uses_runtime_allowed_extensions(client, app, db_session, root_user):
    with app.app_context():
        _, plain = create_api_token('runtime-upload-policy', ['files:upload'], root_user.id)
        root_id = get_root_folder().id
        db_session.commit()
        app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

    response = client.post('/api/v1/files', data={
        'title': '不允许的文本',
        'folder_id': str(root_id),
        'file': (BytesIO(b'text'), 'note.txt'),
    }, content_type='multipart/form-data',
        headers={'Authorization': f'Bearer {plain}'})

    assert response.status_code == 400
    assert response.json['error'] == 'unsupported_file_type'


def test_api_download_records_logs_and_disabled_token_is_rejected(client, app, db_session, root_user):
    with app.app_context():
        token_record, plain = create_api_token('downloader', ['files:read'], root_user.id)
        root = get_root_folder()
        upload_dir = app.config['UPLOAD_FOLDER']
        file_path = f'{upload_dir}/api-download.txt'
        with open(file_path, 'wb') as f:
            f.write(b'download me')
        file_record = File(
            title='API 下载资料',
            filename_on_disk='api-download.txt',
            original_filename='original.txt',
            file_size=11,
            folder_id=root.id,
            uploader_id=root_user.id,
        )
        db_session.add(file_record)
        db_session.commit()
        file_id = file_record.id
        token_id = token_record.id

    response = client.get(f'/api/v1/files/{file_id}/download',
                          headers={'Authorization': f'Bearer {plain}'})
    assert response.status_code == 200
    assert response.data == b'download me'
    assert 'attachment' in response.headers['Content-Disposition']
    assert 'original.txt' in response.headers['Content-Disposition']

    with app.app_context():
        file_record = File.query.get(file_id)
        assert file_record.download_count == 1
        assert DownloadLog.query.filter_by(file_id=file_id,
                                           user_id=root_user.id).count() == 1
        assert OperationLog.query.filter_by(action='api_download_file',
                                            target_id=file_id).first() is not None
        ApiToken.query.get(token_id).is_active = False
        db_session.commit()

    rejected = client.get(f'/api/v1/files/{file_id}/download',
                          headers={'Authorization': f'Bearer {plain}'})
    assert rejected.status_code == 401
    assert rejected.json['error'] == 'invalid_token'


def test_api_download_missing_physical_file_does_not_log(client, app, db_session, root_user):
    with app.app_context():
        _, plain = create_api_token('downloader-missing', ['files:read'], root_user.id)
        root = get_root_folder()
        file_record = File(
            title='缺失文件',
            filename_on_disk='missing.txt',
            original_filename='missing.txt',
            file_size=1,
            folder_id=root.id,
            uploader_id=root_user.id,
        )
        db_session.add(file_record)
        db_session.commit()
        file_id = file_record.id

    response = client.get(f'/api/v1/files/{file_id}/download',
                          headers={'Authorization': f'Bearer {plain}'})
    assert response.status_code == 404

    with app.app_context():
        file_record = File.query.get(file_id)
        assert file_record.download_count == 0
        assert DownloadLog.query.filter_by(file_id=file_id).count() == 0
