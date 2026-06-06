import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import current_app, session


SESSION_KEY = 'campus_verify'
ALLOWED_PREFIXES = ('/upload/hit/image/', '/images/help/')


def campus_verification_enabled():
    return bool(current_app.config.get('CAMPUS_VERIFY_ENABLED'))


def load_campus_verify_config():
    path = os.path.join(current_app.static_folder, 'campus-verify.json')
    if not os.path.exists(path):
        return {'images': [], 'generatedAt': None}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    images = []
    for item in data.get('images', []):
        url = normalize_campus_image_url(item.get('url', ''))
        md5 = (item.get('md5') or '').strip().lower()
        if url and len(md5) == 32:
            images.append({'url': url, 'md5': md5})
    return {'images': images, 'generatedAt': data.get('generatedAt')}


def normalize_campus_image_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    allowed_host = current_app.config.get('CAMPUS_VERIFY_ALLOWED_HOST', 'zb.hit.edu.cn')
    path = '/' + parsed.path.lstrip('/')
    if parsed.scheme != 'https' or parsed.hostname != allowed_host:
        return None
    if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return None
    return parsed._replace(path=path, fragment='').geturl()


def issue_campus_challenge():
    config = load_campus_verify_config()
    nonce = secrets.token_urlsafe(24)
    session[SESSION_KEY] = {
        'nonce': nonce,
        'issued_at': datetime.utcnow().isoformat(),
        'verified': False,
    }
    return {'nonce': nonce, 'images': config['images'], 'generatedAt': config['generatedAt']}


def expected_proof(nonce, url, md5, width, height):
    payload = f'{nonce}|{url}|{md5}|{int(width)}x{int(height)}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def verify_campus_proofs(proofs):
    state = session.get(SESSION_KEY) or {}
    nonce = state.get('nonce')
    issued_at = _parse_time(state.get('issued_at'))
    if not nonce or not issued_at:
        return False, '校园网验证会话已过期，请重试'

    ttl = current_app.config.get('CAMPUS_VERIFY_TTL_SECONDS', 600)
    if datetime.utcnow() - issued_at > timedelta(seconds=ttl):
        session.pop(SESSION_KEY, None)
        return False, '校园网验证已过期，请重试'

    config = load_campus_verify_config()
    by_url = {item['url']: item for item in config['images']}
    matched = 0
    for proof in proofs or []:
        url = normalize_campus_image_url(proof.get('url', ''))
        if not url or url not in by_url:
            continue
        width = proof.get('width')
        height = proof.get('height')
        digest = (proof.get('proof') or '').strip().lower()
        if not width or not height or not digest:
            continue
        expected = expected_proof(nonce, url, by_url[url]['md5'], width, height)
        if secrets.compare_digest(expected, digest):
            matched += 1

    minimum = current_app.config.get('CAMPUS_VERIFY_MIN_SUCCESS', 1)
    if matched < minimum:
        return False, '校园网验证失败，请连接校园网或 VPN 后重试'

    session[SESSION_KEY] = {
        'nonce': nonce,
        'issued_at': state.get('issued_at'),
        'verified': True,
        'verified_at': datetime.utcnow().isoformat(),
        'matched': matched,
    }
    return True, '校园网验证通过'


def campus_session_verified():
    if not campus_verification_enabled():
        return True
    state = session.get(SESSION_KEY) or {}
    if not state.get('verified'):
        return False
    verified_at = _parse_time(state.get('verified_at'))
    if not verified_at:
        return False
    ttl = current_app.config.get('CAMPUS_VERIFY_TTL_SECONDS', 600)
    return datetime.utcnow() - verified_at <= timedelta(seconds=ttl)


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
