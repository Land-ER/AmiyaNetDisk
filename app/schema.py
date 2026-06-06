from sqlalchemy import inspect, text

from app.models import db
from app.folders import assign_unfiled_files_to_root


def ensure_schema(app):
    """Apply lightweight SQLite-compatible schema additions."""
    db.create_all()
    inspector = inspect(db.engine)

    _add_column_if_missing(inspector, 'users', 'campus_verified_at', 'DATETIME')
    _add_column_if_missing(inspector, 'users', 'campus_verify_method', 'VARCHAR(50)')
    _add_column_if_missing(inspector, 'files', 'folder_id', 'INTEGER')

    db.session.commit()
    assign_unfiled_files_to_root()
    db.session.commit()


def _add_column_if_missing(inspector, table, column, ddl_type):
    columns = {item['name'] for item in inspector.get_columns(table)}
    if column in columns:
        return
    db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))
