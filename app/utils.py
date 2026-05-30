import hashlib
import random
import smtplib
import json
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from flask import current_app
from app.models import VerificationCode, db


def send_verification_code(email):
    """生成并发送6位数字验证码到指定邮箱"""
    # 检查60秒内是否已发送
    recent = VerificationCode.query.filter_by(email=email, used=False)\
        .order_by(VerificationCode.created_at.desc()).first()
    if recent and (datetime.utcnow() - recent.created_at).total_seconds() < 60:
        return False, '发送太频繁，请60秒后再试'

    # 生成6位数字验证码
    code = ''.join(random.choices('0123456789', k=6))

    # 保存到数据库
    vc = VerificationCode(email=email, code=code)
    db.session.add(vc)
    db.session.commit()

    # 发送邮件
    try:
        msg = MIMEText(f'您的验证码是：{code}\n验证码有效期为10分钟。', 'plain', 'utf-8')
        msg['Subject'] = 'AmiyaNetDisk 注册验证码'
        msg['From'] = current_app.config['SMTP_FROM']
        msg['To'] = email

        server = smtplib.SMTP(current_app.config['SMTP_SERVER'],
                              current_app.config['SMTP_PORT'], timeout=10)
        server.ehlo()
        # 尝试 STARTTLS（QQ邮箱等需要加密）
        if server.has_extn('STARTTLS'):
            server.starttls()
            server.ehlo()
        if current_app.config['SMTP_USERNAME']:
            server.login(current_app.config['SMTP_USERNAME'],
                         current_app.config['SMTP_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True, '验证码已发送'
    except Exception as e:
        current_app.logger.error(f'发送验证码失败: {e}')
        return False, '验证码发送失败，请检查邮箱配置'


def verify_code(email, code):
    """验证验证码是否正确且未过期"""
    vc = VerificationCode.query.filter_by(email=email, code=code, used=False)\
        .order_by(VerificationCode.created_at.desc()).first()
    if not vc:
        return False
    if vc.is_expired():
        return False
    # 标记为已使用
    vc.used = True
    db.session.commit()
    return True


def compute_file_hash(file_data):
    """计算文件内容的SHA-256哈希值"""
    sha256 = hashlib.sha256()
    sha256.update(file_data)
    return sha256.hexdigest()


def allowed_file(filename):
    """检查文件扩展名是否在白名单中"""
    from app.config import Config
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in Config.ALLOWED_EXTENSIONS


def get_file_extension(filename):
    """获取文件扩展名"""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def format_file_size(size_bytes):
    """格式化文件大小为可读字符串"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'


def get_client_ip():
    """获取客户端IP地址"""
    from flask import request
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def load_json_tags(tags_str):
    """从JSON字符串加载标签列表"""
    if not tags_str:
        return []
    try:
        return json.loads(tags_str)
    except (json.JSONDecodeError, TypeError):
        return []


def dump_json_tags(tags_list):
    """将标签列表转为JSON字符串"""
    return json.dumps(tags_list, ensure_ascii=False)
