import os
import hashlib
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash
from app.config import config_map
from app.models import db, User
from app.schema import ensure_schema

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect()


def create_app(config_name=None):
    """应用工厂函数"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.file import file_bp
    from app.routes.admin import admin_bp
    from app.routes.root import root_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(root_bp, url_prefix='/root')
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp)

    # 确保上传目录存在
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # 创建数据库表和 root 用户
    with app.app_context():
        ensure_schema(app)
        _ensure_root_user(app)

    # 模板上下文注入
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    return app


def _ensure_root_user(app):
    """确保 root 用户存在（每次启动时检查配置一致性）"""
    root_email = app.config['ROOT_EMAIL']
    root_password = app.config['ROOT_PASSWORD']

    # 前端传输的是 SHA-256(明文)，所以 root 密码也要哈希后存储
    hashed_pwd = hashlib.sha256(root_password.encode('utf-8')).hexdigest()
    pwd_hash = generate_password_hash(hashed_pwd)

    root_user = User.query.filter_by(role='root').first()
    if root_user:
        root_user.email = root_email
        root_user.password_hash = pwd_hash
        db.session.commit()
        app.logger.info(f'root 账号已同步配置: {root_email}')
        return

    # 检查配置邮箱是否已被其他用户使用
    existing = User.query.filter_by(email=root_email).first()
    if existing:
        existing.role = 'root'
        existing.password_hash = pwd_hash
        db.session.commit()
        app.logger.info(f'已将用户 {root_email} 升级为 root')
    else:
        user = User(
            email=root_email,
            password_hash=pwd_hash,
            role='root',
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        app.logger.info(f'已创建 root 用户: {root_email}')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
