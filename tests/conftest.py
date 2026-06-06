import hashlib
import os
import re
import uuid

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "test.db"}')
    monkeypatch.setenv('SECRET_KEY', 'test-secret')
    monkeypatch.setenv('EMBEDDING_ENABLED', 'false')
    monkeypatch.setenv('CAMPUS_VERIFY_ENABLED', 'false')

    from app import create_app

    app = create_app(config_overrides={
        'TESTING': True,
        'WTF_CSRF_ENABLED': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "test.db"}',
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'SECRET_KEY': 'test-secret',
        'EMBEDDING_ENABLED': False,
        'CAMPUS_VERIFY_ENABLED': False,
    })
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    from app.models import db

    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def root_user(app):
    from app.models import User

    with app.app_context():
        return User.query.filter_by(role='root').first()


@pytest.fixture
def normal_user(app, db_session):
    from app.models import User

    email = f'user-{uuid.uuid4().hex}@example.com'
    user = User(
        email=email,
        password_hash=generate_password_hash('password'),
        role='user',
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def login_as(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


def csrf_from_response(response):
    text = response.data.decode('utf-8')
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', text)
    if not match:
        match = re.search(r'name="csrf-token" content="([^"]+)"', text)
    assert match, 'CSRF token not found in response'
    return match.group(1)


def sha256_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()
