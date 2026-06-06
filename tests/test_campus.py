import os
import re

import pytest


@pytest.fixture
def campus_app(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "campus.db"}')
    monkeypatch.setenv('SECRET_KEY', 'campus-test-secret')
    monkeypatch.setenv('CAMPUS_VERIFY_ENABLED', 'true')
    monkeypatch.setenv('CAMPUS_VERIFY_MIN_SUCCESS', '1')
    monkeypatch.setenv('EMBEDDING_ENABLED', 'false')

    from app import create_app

    app = create_app()
    app.config.update(
        TESTING=True,
        CAMPUS_VERIFY_ENABLED=True,
        CAMPUS_VERIFY_MIN_SUCCESS=1,
    )
    return app


@pytest.fixture
def campus_client(campus_app):
    return campus_app.test_client()


def test_campus_config_returns_challenge(campus_client):
    response = campus_client.get('/campus_verify/config')
    assert response.status_code == 200
    assert response.json['enabled'] is True
    assert response.json['nonce']
    assert len(response.json['images']) >= 1


def test_send_code_requires_csrf_and_campus_verification(campus_client):
    no_csrf = campus_client.post('/send_code', json={
        'email': 'student@example.com',
        'purpose': 'register',
    })
    assert no_csrf.status_code == 400

    register_page = campus_client.get('/register')
    token = csrf_from_meta(register_page.data)
    gated = campus_client.post('/send_code', json={
        'email': 'student@example.com',
        'purpose': 'register',
    }, headers={'X-CSRFToken': token})
    assert gated.status_code == 403
    assert gated.json['success'] is False


def test_campus_check_rejects_empty_proofs(campus_client):
    register_page = campus_client.get('/register')
    token = csrf_from_meta(register_page.data)
    campus_client.get('/campus_verify/config')

    response = campus_client.post('/campus_verify/check', json={'proofs': []},
                                  headers={'X-CSRFToken': token})
    assert response.status_code == 400
    assert response.json['success'] is False


def test_campus_image_url_normalization_rejects_untrusted_inputs(campus_app):
    from app.campus import normalize_campus_image_url

    with campus_app.app_context():
        assert normalize_campus_image_url('http://zb.hit.edu.cn/images/help/x.png') is None
        assert normalize_campus_image_url('https://evil.example/images/help/x.png') is None
        assert normalize_campus_image_url('https://user@zb.hit.edu.cn/images/help/x.png') is None
        assert normalize_campus_image_url('https://zb.hit.edu.cn:443/images/help/x.png') is None
        assert normalize_campus_image_url('https://zb.hit.edu.cn/not-allowed/x.png') is None
        assert (
            normalize_campus_image_url('https://zb.hit.edu.cn/images/help/x.png?cache=1#frag') ==
            'https://zb.hit.edu.cn/images/help/x.png'
        )


def csrf_from_meta(data):
    match = re.search(r'name="csrf-token" content="([^"]+)"', data.decode('utf-8'))
    assert match
    return match.group(1)
