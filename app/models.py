from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # user, admin, root
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename_on_disk = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    search_tags = db.Column(db.Text, default='[]')  # JSON array string
    display_tags = db.Column(db.Text, default='[]')  # JSON array string
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    uploader = db.relationship('User', backref=db.backref('uploaded_files', lazy='dynamic'))

    def __repr__(self):
        return f'<File {self.title}>'


class VerificationCode(db.Model):
    __tablename__ = 'verification_codes'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    used = db.Column(db.Boolean, default=False)

    def is_expired(self):
        """验证码是否过期（有效期10分钟）"""
        from datetime import timedelta
        expire_time = self.created_at + timedelta(minutes=10)
        return datetime.now(timezone.utc) > expire_time


class DownloadLog(db.Model):
    __tablename__ = 'download_logs'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    downloaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    admin = db.relationship('User', backref=db.backref('operation_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<OperationLog {self.action} by admin={self.admin_id}>'
