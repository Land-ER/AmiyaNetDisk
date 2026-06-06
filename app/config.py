import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基础配置"""
    # 项目根目录 (config.py 所在目录的父目录)
    _basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL',
                                         f'sqlite:///{os.path.join(_basedir, "app.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 104857600))  # 100MB

    # SMTP 邮件配置
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'localhost')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 25))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'noreply@example.com')

    # Root 账号配置
    ROOT_EMAIL = os.getenv('ROOT_EMAIL', 'root@example.com')
    ROOT_PASSWORD = os.getenv('ROOT_PASSWORD', 'root123456')

    # Embedding 搜索配置（默认关闭，避免轻量部署下载模型）
    EMBEDDING_ENABLED = os.getenv('EMBEDDING_ENABLED', 'false').lower() == 'true'
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5')
    EMBEDDING_TOP_K = int(os.getenv('EMBEDDING_TOP_K', 50))

    # 校园网注册验证配置（默认关闭）
    CAMPUS_VERIFY_ENABLED = os.getenv('CAMPUS_VERIFY_ENABLED', 'false').lower() == 'true'
    CAMPUS_VERIFY_MIN_SUCCESS = int(os.getenv('CAMPUS_VERIFY_MIN_SUCCESS', 1))
    CAMPUS_VERIFY_TTL_SECONDS = int(os.getenv('CAMPUS_VERIFY_TTL_SECONDS', 600))
    CAMPUS_VERIFY_ALLOWED_HOST = os.getenv('CAMPUS_VERIFY_ALLOWED_HOST', 'zb.hit.edu.cn')

    # 上传文件扩展名白名单
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                          'jpg', 'png', 'gif', 'zip', 'rar', '7z', 'mp4', 'txt'}

    # Session 安全
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # 上传文件存储目录
    UPLOAD_FOLDER = os.path.join(_basedir, 'uploads')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
