from conftest import csrf_from_response, login_as, sha256_password
from app.models import db, User
from werkzeug.security import check_password_hash


def test_admin_routes_require_login(client):
    for path in ('/admin/folders', '/admin/files', '/admin/upload'):
        response = client.get(path)
        assert response.status_code == 302
        assert '/login' in response.location


def test_normal_user_cannot_access_admin(client, normal_user):
    login_as(client, normal_user)
    response = client.get('/admin/folders')
    assert response.status_code == 302
    assert response.location == '/'


def test_admin_post_requires_csrf(client, app, root_user):
    login_as(client, root_user)

    response = client.post('/admin/folder/create', data={
        'parent_id': get_root_id(app),
        'name': 'no-csrf',
    })
    assert response.status_code == 400

    page = client.get('/admin/folders')
    token = csrf_from_response(page)
    response = client.post('/admin/folder/create', data={
        'csrf_token': token,
        'parent_id': get_root_id(app),
        'name': 'with-csrf',
    })
    assert response.status_code == 302


def test_login_rejects_external_next_redirect(client):
    page = client.get('/login?next=https://evil.example/phish')
    token = csrf_from_response(page)
    response = client.post('/login?next=https://evil.example/phish', data={
        'csrf_token': token,
        'email': 'root@example.com',
        'password': sha256_password('root123456'),
    })
    assert response.status_code == 302
    assert not response.location.startswith('https://evil.example')
    assert response.location == '/'


def test_login_rejects_plain_password_from_form(client):
    response = client.post('/login', data={
        'csrf_token': csrf_from_response(client.get('/login')),
        'email': 'root@example.com',
        'password': 'root123456',
    })

    assert response.status_code == 200
    assert '密码安全处理失败'.encode('utf-8') in response.data


def test_login_accepts_saved_sha256_password_without_double_hashing(client):
    response = client.post('/login', data={
        'csrf_token': csrf_from_response(client.get('/login')),
        'email': 'root@example.com',
        'password': sha256_password('root123456'),
    })

    assert response.status_code == 302
    assert response.location == '/'


def test_admin_reset_password_page_hashes_password_before_submit(client, root_user, normal_user):
    login_as(client, root_user)

    response = client.get(f'/admin/user/{normal_user.id}/reset_password')

    assert response.status_code == 200
    assert b'id="adminResetPasswordForm"' in response.data
    assert b'submitFormWithHashedPassword(this, pwd)' in response.data


def test_password_hash_submitter_does_not_overwrite_visible_password(client):
    response = client.get('/login')

    assert response.status_code == 200
    assert b'submitFormWithHashedPassword(this, pwd)' in response.data
    assert b'pwd.value = hash' not in response.data
    assert b'submitWithPassword(currentValue);' not in response.data


def test_admin_reset_password_matches_login_hash_flow(client, app, root_user, normal_user):
    login_as(client, root_user)

    page = client.get(f'/admin/user/{normal_user.id}/reset_password')
    token = csrf_from_response(page)
    response = client.post(f'/admin/user/{normal_user.id}/reset_password', data={
        'csrf_token': token,
        'password': sha256_password('new-password'),
    })
    assert response.status_code == 302

    client.get('/logout')
    response = client.post('/login', data={
        'csrf_token': csrf_from_response(client.get('/login')),
        'email': normal_user.email,
        'password': sha256_password('new-password'),
    })

    assert response.status_code == 302
    assert response.location == '/'

    with app.app_context():
        user = db.session.get(User, normal_user.id)
        assert check_password_hash(user.password_hash, sha256_password('new-password'))


def test_admin_reset_password_rejects_plain_password_without_javascript(client, app, root_user, normal_user):
    login_as(client, root_user)

    page = client.get(f'/admin/user/{normal_user.id}/reset_password')
    token = csrf_from_response(page)
    response = client.post(f'/admin/user/{normal_user.id}/reset_password', data={
        'csrf_token': token,
        'password': 'plain-new-password',
    })
    assert response.status_code == 200
    assert '密码安全处理失败'.encode('utf-8') in response.data

    with app.app_context():
        user = db.session.get(User, normal_user.id)
        assert not check_password_hash(user.password_hash, sha256_password('plain-new-password'))


def get_root_id(app):
    from app.folders import get_root_folder

    with app.app_context():
        return get_root_folder().id
