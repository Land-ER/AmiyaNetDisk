import hashlib
import re

from werkzeug.security import check_password_hash, generate_password_hash


_SHA256_HEX_RE = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)


def is_sha256_hex(value):
    """检查是否为 64 位十六进制 SHA-256 哈希值"""
    return bool(_SHA256_HEX_RE.match(value or ''))


def sha256_password(password):
    """计算字符串的 SHA-256 哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def canonical_password_value(password):
    """返回统一规范的密码值（用于生成 bcrypt）。

    应用历史格式为 bcrypt(SHA256(明文密码))。
    如果是 64 位十六进制则直接使用（已哈希），否则自动 SHA-256。
    这适用于 root 配置密码等明文来源。
    """
    return password if is_sha256_hex(password) else sha256_password(password)


def generate_user_password_hash(password):
    """生成用户密码的 bcrypt 哈希（输入需为 SHA-256 或明文）"""
    return generate_password_hash(canonical_password_value(password))


def check_user_password(stored_hash, password):
    """校验用户密码。

    后端只接受 SHA-256 格式的密码输入（来自前端隐藏字段）。
    非 SHA-256 格式直接拒绝。
    """
    if not is_sha256_hex(password):
        return False
    return check_password_hash(stored_hash, password)
