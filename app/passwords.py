import hashlib
import re

from werkzeug.security import check_password_hash, generate_password_hash


_SHA256_HEX_RE = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)


def is_sha256_hex(value):
    return bool(_SHA256_HEX_RE.match(value or ''))


def sha256_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def canonical_password_value(password):
    """Return the value wrapped by Werkzeug's password hash.

    The application historically stores bcrypt(SHA256(plain password)).  Keep
    that storage format. Server-side configured plaintext values, such as the
    root password, are normalized here before storage.
    """
    return password if is_sha256_hex(password) else sha256_password(password)


def generate_user_password_hash(password):
    return generate_password_hash(canonical_password_value(password))


def check_user_password(stored_hash, password):
    if not is_sha256_hex(password):
        return False
    return check_password_hash(stored_hash, password)
