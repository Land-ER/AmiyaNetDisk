# AmiyaNetDisk Folder Tree, Embedding Search, and Campus Verification TDD

## Background

AmiyaNetDisk currently stores files in a flat `files` table and saves physical file content in the `uploads/` directory using SHA-256 based filenames. Public search is implemented with SQL `LIKE` over `File.title` and `File.search_tags`. Registration uses email verification codes only.

The target change is to evolve the app into a course-resource style net disk:

- Files are categorized by a tree of folders.
- Admins can create, rename, delete, and use folders when managing files.
- The public UI becomes a cleaner folder browser with search.
- Search gains embedding-based semantic matching.
- Registration can require campus-network verification, inspired by `HIT-Fireworks/fireworks-notes-society`.

The reference repository represents categories as real repository folders such as `数学学院/专业基础课/数学分析/index.md`, and each page binds a remote resource directory using an `OList path="/..."` component. Its campus check is not CAS/SSO: it loads selected HIT-hosted images, uses their reachable dimensions plus known MD5 metadata, and derives a proof that the browser can access campus-restricted resources.

## Goals

1. Add a logical folder tree independent of physical storage.
2. Let admins manage folders and assign files to folders.
3. Provide public folder browsing with breadcrumbs and a compact file list.
4. Preserve existing file download behavior and SHA-256 deduplication.
5. Add semantic search over file metadata and folder paths.
6. Gate registration behind optional campus-network verification.
7. Keep the app easy to deploy with SQLite and Docker.

## Non-Goals

1. Do not physically store files in nested folders under `uploads/`.
2. Do not parse every uploaded document's full text in the first version.
3. Do not replace email verification with campus verification.
4. Do not implement HIT CAS/SSO unless a later requirement provides official integration details.
5. Do not add a full frontend SPA framework.

## Current System Summary

Relevant existing files:

- `app/models.py`: `User`, `File`, `VerificationCode`, `DownloadLog`, `OperationLog`.
- `app/routes/main.py`: public index, search, and file detail.
- `app/routes/admin.py`: upload, edit file, delete file, logs, users.
- `app/routes/auth.py`: register, login, logout, send code, reset password.
- `app/templates/search_results.html`: current public file search UI.
- `app/templates/admin/upload.html`: upload form with tags.
- `app/static/js/main.js`: password hashing and tag input behavior.

Current search:

```python
File.title.like(like_pattern) | File.search_tags.like(like_pattern)
```

Current file storage:

```text
uploads/<sha256>.<ext>
```

## Proposed Architecture

### Data Model

Add `Folder`:

```python
class Folder(db.Model):
    __tablename__ = 'folders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    path = db.Column(db.String(1000), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    parent = db.relationship(
        'Folder',
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic'),
    )
```

Modify `File`:

```python
folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True, index=True)
folder = db.relationship('Folder', backref=db.backref('files', lazy='dynamic'))
```

Add `FileEmbedding`:

```python
class FileEmbedding(db.Model):
    __tablename__ = 'file_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False, unique=True)
    embedding_model = db.Column(db.String(120), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    vector = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    file = db.relationship('File', backref=db.backref('embedding', uselist=False))
```

Modify `User`:

```python
campus_verified_at = db.Column(db.DateTime, nullable=True)
campus_verify_method = db.Column(db.String(50), nullable=True)
```

### Folder Invariants

1. Root is represented by `parent_id IS NULL`.
2. Folder path is absolute and starts with `/`.
3. The root path is `/`.
4. Sibling folder names are unique.
5. Folder names cannot contain `/`.
6. Moving or renaming a folder updates descendant paths.
7. A folder cannot be moved under itself or one of its descendants.
8. By default, folders must be empty before deletion.

SQLite cannot easily enforce partial unique constraints across all supported setups in this lightweight app, so sibling uniqueness should be enforced in service-layer validation first. A database unique index on `(parent_id, name)` can be added where practical, with special handling for root-level folders.

### Folder Services

Add `app/folders.py`:

- `get_root_folder()`
- `build_folder_path(name, parent)`
- `create_folder(name, parent_id, description=None, sort_order=0)`
- `rename_folder(folder, new_name)`
- `move_folder(folder, new_parent_id)`
- `delete_folder(folder)`
- `folder_has_content(folder)`
- `get_descendant_ids(folder)`
- `build_folder_tree()`
- `get_breadcrumbs(folder)`

The route layer should call these helpers instead of duplicating path logic.

### Schema Migration Strategy

The project currently uses `db.create_all()` without Alembic. For the first implementation, use a small compatibility initializer:

- Create new tables with `db.create_all()`.
- Add missing columns with SQLite `ALTER TABLE` checks.
- Create a root folder if none exists.
- Backfill existing files to the root folder.

Add helper:

- `app/schema.py`
  - `ensure_schema(app)`
  - `_column_exists(table, column)`
  - `_ensure_folder_defaults()`

Later, `Flask-Migrate` can replace this when the app needs production-grade migrations.

## Backend Routes

### Public Routes

Update:

- `GET /`
  - Show root folder browser.

Add:

- `GET /folder/<int:folder_id>`
  - Show selected folder.
  - Includes child folders and files.

- `GET /api/folders/tree`
  - Return full or shallow folder tree.
  - Used by public UI and admin folder picker.

Update:

- `GET /search`
  - Keep `q`.
  - Add `mode=hybrid|keyword|semantic`.
  - Add optional `folder_id` to scope search.

### Admin Routes

Add:

- `GET /admin/folders`
  - Folder management page.

- `POST /admin/folder/create`
  - Create folder.

- `POST /admin/folder/<int:folder_id>/rename`
  - Rename folder.

- `POST /admin/folder/<int:folder_id>/move`
  - Move folder.

- `POST /admin/folder/<int:folder_id>/delete`
  - Delete empty folder.

Update:

- `GET/POST /admin/upload`
  - Add folder selection.

- `GET/POST /admin/file/<int:file_id>/edit`
  - Allow moving file to another folder.

- `GET /admin/files`
  - Add folder filter and folder path column.

### Campus Verification Routes

Add:

- `GET /campus_verify/config`
  - Returns enabled verification image metadata.

- `POST /campus_verify/check`
  - Validates proof sent by browser.
  - Stores short-lived verification state in session.

Update:

- `POST /send_code`
  - If `CAMPUS_VERIFY_ENABLED` and purpose is registration, require session campus verification.

- `POST /register`
  - If enabled, require campus verification before creating account.
  - Store `campus_verified_at`.

## Frontend Design

### Public Browser

Replace the current first screen with:

- Header with global search.
- Left folder navigation on desktop.
- Top folder selector or collapsible tree on mobile.
- Right content area:
  - Breadcrumbs.
  - Child folder rows.
  - File rows/cards.
  - Empty state.

Recommended templates:

- `app/templates/folder_browser.html`
- Reuse `file_detail.html`.
- Keep `search_results.html`, but compact it and include folder paths.

### Admin Folder UI

Add `app/templates/admin/folders.html`:

- Tree list.
- Create child folder button.
- Rename button.
- Move button.
- Delete button disabled when non-empty.

Upload/edit forms:

- Add a folder selector.
- Prefer a plain `<select>` first for simplicity.
- Later upgrade to searchable tree picker if the folder count grows.

## Embedding Search

### Search Corpus

First version embeds metadata only:

```text
title
original_filename
search_tags
display_tags
folder path
folder description
```

This avoids file parsing complexity and already improves Chinese course-resource search significantly.

### Module

Add `app/embedding.py`:

- `is_embedding_enabled()`
- `get_embedding_model()`
- `build_file_embedding_text(file)`
- `compute_text_hash(text)`
- `encode_text(text)`
- `serialize_vector(vector)`
- `deserialize_vector(value)`
- `cosine_similarity(a, b)`
- `upsert_file_embedding(file)`
- `delete_file_embedding(file_id)`
- `semantic_search(query, folder_id=None, limit=50)`
- `hybrid_search(query, folder_id=None, page=1, per_page=12)`
- `rebuild_all_embeddings()`

### Model Choice

Default local model:

```text
BAAI/bge-small-zh-v1.5
```

Dependencies:

```text
sentence-transformers
numpy
```

Config:

```python
EMBEDDING_ENABLED = os.getenv('EMBEDDING_ENABLED', 'false').lower() == 'true'
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5')
EMBEDDING_TOP_K = int(os.getenv('EMBEDDING_TOP_K', 50))
```

Embeddings should be disabled by default so local deployment remains lightweight. When disabled, search falls back to keyword behavior.

### Ranking

Hybrid score:

```text
score = keyword_score * 0.45 + semantic_score * 0.45 + popularity_score * 0.10
```

Keyword score can be simple:

- Title hit: `1.0`
- Tag hit: `0.7`
- Folder path hit: `0.5`

Popularity score:

```text
log(1 + download_count) normalized within candidate set
```

## Campus Verification

### Principle

Use browser-side loading of selected HIT-hosted images to prove network reachability. The reference repository checks images from `zb.hit.edu.cn`, validates host/path, reads natural image dimensions, and derives MD5-based passwords.

For this Flask app, use the idea as a registration gate:

1. Server sends a sanitized list of verification image URLs and known MD5 values.
2. Browser attempts to load images.
3. Browser computes per-image proof from known MD5 plus image dimensions.
4. Browser sends successful proofs to server.
5. Server accepts if at least `CAMPUS_VERIFY_MIN_SUCCESS` proofs match expected values.
6. Server records session state for registration.

### Config

```python
CAMPUS_VERIFY_ENABLED = os.getenv('CAMPUS_VERIFY_ENABLED', 'false').lower() == 'true'
CAMPUS_VERIFY_MIN_SUCCESS = int(os.getenv('CAMPUS_VERIFY_MIN_SUCCESS', 1))
CAMPUS_VERIFY_TTL_SECONDS = int(os.getenv('CAMPUS_VERIFY_TTL_SECONDS', 600))
CAMPUS_VERIFY_ALLOWED_HOST = os.getenv('CAMPUS_VERIFY_ALLOWED_HOST', 'zb.hit.edu.cn')
```

### Verification Data

Add:

- `app/static/campus-verify.json`

Shape:

```json
{
  "images": [
    {
      "url": "https://zb.hit.edu.cn/images/help/example.png",
      "md5": "..."
    }
  ],
  "generatedAt": "2026-06-06T00:00:00Z"
}
```

Do not blindly copy stale URLs from the reference repository forever. They should be refreshable and validated.

### Security Notes

This verifies network environment, not student identity. It can be bypassed by someone with campus VPN or shared access. That is acceptable only if the product requirement is "campus-network gated registration." If the requirement is "only real HIT students," use official CAS/SSO instead.

Server-side checks must:

- Reject non-HTTPS URLs.
- Reject hosts other than configured HIT host.
- Reject paths outside known image prefixes.
- Never let the client submit arbitrary verification URLs.
- Expire session verification quickly.

## Test Plan

The first pytest suite has been added under `tests/` and can be run with:

```bash
python -m pytest -q
```

It currently covers folder creation and upload assignment, public tree/search rendering, admin access control, CSRF enforcement, external redirect rejection, folder abuse cases, and the campus verification gate.

### Unit Tests

Folder services:

- Create root folder only once.
- Create child folder under root.
- Reject duplicate sibling names.
- Reject names containing `/`.
- Rename folder and update descendant paths.
- Move folder and update descendant paths.
- Reject moving folder under itself.
- Reject moving folder under descendant.
- Reject deleting non-empty folder.
- Return breadcrumbs in root-to-leaf order.

Embedding:

- Build embedding text includes title, tags, and folder path.
- Content hash changes when searchable metadata changes.
- Vector serialization round-trips.
- Cosine similarity ranks closer vectors higher.
- Search falls back to keyword when embeddings are disabled.

Campus verification:

- Normalize valid campus image URL.
- Reject HTTP URL.
- Reject non-campus host.
- Reject unexpected path prefix.
- Accept proof with enough matching images.
- Reject proof below threshold.
- Expire session verification after TTL.

### Integration Tests

Public browsing:

- `GET /` shows root folder.
- `GET /folder/<id>` shows child folders and files.
- Unknown folder returns 404.
- Search result includes folder path.

Admin:

- Admin can create folder.
- Admin can upload file into folder.
- Admin can move file between folders.
- Admin can rename folder.
- Admin cannot delete folder containing files.
- Non-admin cannot access folder admin routes.

Auth:

- With campus verification disabled, registration works as before.
- With campus verification enabled, registration send-code requires verified session.
- Verified session allows send-code.

### Manual QA

- Existing flat files appear under root after migration.
- Download URLs remain stable.
- File detail page shows folder path.
- Mobile layout does not overlap.
- Admin folder page remains usable with 3+ levels.
- Semantic search returns useful results for Chinese course synonyms.

## Rollout Plan

1. Add models and schema initializer.
2. Add folder service functions and tests.
3. Add public folder browser routes and templates.
4. Add admin folder management and file folder assignment.
5. Add search path awareness.
6. Add optional embedding module behind config flag.
7. Add campus verification behind config flag.
8. Update README and `.env.example`.

## Backward Compatibility

- Existing files remain downloadable.
- Existing search still works when embedding is disabled.
- Existing users remain valid.
- Existing registration flow remains valid when campus verification is disabled.
- Existing `uploads/` physical storage layout does not change.

## Open Questions

1. Should root-level folders follow the reference repository's school/course taxonomy by default, or should admins create them manually?
2. Should admins be allowed to recursively delete folders after a second confirmation?
3. Should semantic search include parsed PDF/DOCX/TXT content in a later phase?
4. Should campus verification be required for password reset, or only registration?
5. Is campus network verification enough, or is official HIT identity authentication required?
