import hashlib
import json
import secrets
from datetime import datetime

from flask import request, jsonify, g
from sqlalchemy import update

from app.models import db, ApiToken


# Public token prefix, not a secret.
TOKEN_PREFIX = 'and_'  # nosec B105
KNOWN_SCOPES = {
    'folders:read',
    'folders:write',
    'files:read',
    'files:upload',
    'search:read',
}


def generate_api_token():
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def normalize_scopes(scopes):
    selected = []
    for scope in scopes or []:
        scope = scope.strip()
        if scope in KNOWN_SCOPES and scope not in selected:
            selected.append(scope)
    return selected


def dump_scopes(scopes):
    return json.dumps(normalize_scopes(scopes), ensure_ascii=False)


def load_scopes(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def create_api_token(name, scopes, created_by):
    plain = generate_api_token()
    record = ApiToken(
        name=(name or '').strip()[:120] or '未命名 Token',
        token_hash=hash_token(plain),
        scopes=dump_scopes(scopes),
        created_by=created_by,
    )
    db.session.add(record)
    db.session.flush()
    return record, plain


def api_token_required(required_scope):
    def decorator(view):
        from functools import wraps

        @wraps(view)
        def wrapped(*args, **kwargs):
            token = _extract_bearer_token()
            if not token:
                return jsonify({'error': 'missing_bearer_token'}), 401

            record = ApiToken.query.filter_by(token_hash=hash_token(token),
                                              is_active=True).first()
            if not record:
                return jsonify({'error': 'invalid_token'}), 401
            if not record.creator or not record.creator.is_active or not record.creator.is_admin():
                return jsonify({'error': 'invalid_token_owner'}), 401

            if record.expires_at and record.expires_at < datetime.utcnow():
                return jsonify({'error': 'token_expired'}), 401

            scopes = load_scopes(record.scopes)
            if required_scope not in scopes:
                return jsonify({'error': 'insufficient_scope',
                                'required_scope': required_scope}), 403

            _touch_last_used(record.id)
            g.api_token = record
            return view(*args, **kwargs)

        return wrapped
    return decorator


def _extract_bearer_token():
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    return header.removeprefix('Bearer ').strip()


def _touch_last_used(token_id):
    with db.engine.begin() as connection:
        connection.execute(
            update(ApiToken)
            .where(ApiToken.id == token_id)
            .values(last_used_at=datetime.utcnow())
        )
