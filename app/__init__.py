import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from app.config import config_map
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录'
login_manager.login_message_category = 'warning'


def create_app(config_name=None):
    """应用工厂函数"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)

    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.file import file_bp
    from app.routes.admin import admin_bp
    from app.routes.root import root_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(root_bp, url_prefix='/root')

    # 确保上传目录存在
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # 创建数据库表和 root 用户
    with app.app_context():
        db.create_all()
        _ensure_root_user(app)

    return app


def _ensure_root_user(app):
    """确保 root 用户存在（首次启动时创建）"""
    root_email = app.config['ROOT_EMAIL']
    root_password = app.config['ROOT_PASSWORD']

    root_user = User.query.filter_by(role='root').first()
    if not root_user:
        # 检查是否有对应邮箱的用户
        existing = User.query.filter_by(email=root_email).first()
        if existing:
            existing.role = 'root'
            db.session.commit()
            app.logger.info(f'已将用户 {root_email} 升级为 root')
        else:
            user = User(
                email=root_email,
                password_hash=generate_password_hash(root_password),
                role='root',
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            app.logger.info(f'已创建 root 用户: {root_email}')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
