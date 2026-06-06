from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# SQLite 不保存时区信息，统一使用 naive UTC
def _utcnow():
    return datetime.utcnow()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # user, admin, root
    is_active = db.Column(db.Boolean, default=True)
    campus_verified_at = db.Column(db.DateTime, nullable=True)
    campus_verify_method = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def is_admin(self):
        return self.role in ('admin', 'root')

    def is_root(self):
        return self.role == 'root'


class Folder(db.Model):
    __tablename__ = 'folders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True, index=True)
    path = db.Column(db.String(1000), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow,
                           onupdate=_utcnow)

    parent = db.relationship(
        'Folder',
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic'),
    )

    def __repr__(self):
        return f'<Folder {self.path}>'


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename_on_disk = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    search_tags = db.Column(db.Text, default='[]')  # JSON array string
    display_tags = db.Column(db.Text, default='[]')  # JSON array string
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow,
                           onupdate=_utcnow)

    uploader = db.relationship('User', backref=db.backref('uploaded_files', lazy='dynamic'))
    folder = db.relationship('Folder', backref=db.backref('files', lazy='dynamic'))

    def __repr__(self):
        return f'<File {self.title}>'


class VerificationCode(db.Model):
    __tablename__ = 'verification_codes'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    used = db.Column(db.Boolean, default=False)

    def is_expired(self):
        """验证码是否过期（有效期10分钟）"""
        from datetime import timedelta
        expire_time = self.created_at + timedelta(minutes=10)
        return datetime.utcnow() > expire_time


class DownloadLog(db.Model):
    __tablename__ = 'download_logs'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    downloaded_at = db.Column(db.DateTime, default=_utcnow)

    file = db.relationship('File', backref=db.backref('download_logs', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('download_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<DownloadLog file={self.file_id} user={self.user_id}>'


class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    admin = db.relationship('User', backref=db.backref('operation_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<OperationLog {self.action} by admin={self.admin_id}>'


class ApiToken(db.Model):
    __tablename__ = 'api_tokens'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    scopes = db.Column(db.Text, nullable=False, default='[]')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    creator = db.relationship('User', backref=db.backref('api_tokens', lazy='dynamic'))

    def __repr__(self):
        return f'<ApiToken {self.name}>'


class FileEmbedding(db.Model):
    __tablename__ = 'file_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False,
                        unique=True, index=True)
    embedding_model = db.Column(db.String(120), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    vector = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow,
                           onupdate=_utcnow)

    file = db.relationship('File', backref=db.backref('embedding', uselist=False))

    def __repr__(self):
        return f'<FileEmbedding file={self.file_id} model={self.embedding_model}>'
