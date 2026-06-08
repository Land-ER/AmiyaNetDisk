import hashlib
import json
import math

from flask import current_app

from app.models import db, File, FileEmbedding
from app.utils import load_json_tags

_model_cache = {}


def is_embedding_enabled():
    return bool(current_app.config.get('EMBEDDING_ENABLED'))


def get_model_name():
    return current_app.config.get('EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5')


def build_file_embedding_text(file_record):
    folder_path = file_record.folder.path if file_record.folder else '/'
    parts = [
        file_record.title,
        file_record.original_filename,
        folder_path,
        ' '.join(load_json_tags(file_record.search_tags)),
        ' '.join(load_json_tags(file_record.display_tags)),
    ]
    return '\n'.join(part for part in parts if part)


def compute_text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def serialize_vector(vector):
    return json.dumps([float(item) for item in vector], separators=(',', ':'))


def deserialize_vector(value):
    try:
        return [float(item) for item in json.loads(value)]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def encode_text(text):
    model_name = get_model_name()
    if model_name not in _model_cache:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError('sentence-transformers 未安装，无法启用 embedding 搜索') from exc
        _model_cache[model_name] = SentenceTransformer(model_name)
    vector = _model_cache[model_name].encode(text, normalize_embeddings=True)
    return [float(item) for item in vector]


def upsert_file_embedding(file_record):
    if not is_embedding_enabled():
        return None

    text = build_file_embedding_text(file_record)
    content_hash = compute_text_hash(text)
    model_name = get_model_name()
    existing = FileEmbedding.query.filter_by(file_id=file_record.id).first()
    if existing and existing.content_hash == content_hash and existing.embedding_model == model_name:
        return existing

    vector = encode_text(text)
    if existing:
        existing.embedding_model = model_name
        existing.content_hash = content_hash
        existing.vector = serialize_vector(vector)
        return existing

    item = FileEmbedding(
        file_id=file_record.id,
        embedding_model=model_name,
        content_hash=content_hash,
        vector=serialize_vector(vector),
    )
    db.session.add(item)
    return item


def delete_file_embedding(file_id):
    FileEmbedding.query.filter_by(file_id=file_id).delete()


def semantic_search(query_text, folder_id=None, folder_ids=None, limit=None):
    if not is_embedding_enabled() or not query_text.strip():
        return []

    limit = limit or current_app.config.get('EMBEDDING_TOP_K', 50)
    query_vector = encode_text(query_text)
    query = FileEmbedding.query.join(File)
    if folder_ids:
        query = query.filter(File.folder_id.in_(folder_ids))
    elif folder_id:
        query = query.filter(File.folder_id == folder_id)

    scored = []
    for item in query.all():
        score = cosine_similarity(query_vector, deserialize_vector(item.vector))
        if score > 0:
            scored.append((item.file, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]


def rebuild_all_embeddings():
    if not is_embedding_enabled():
        return 0
    count = 0
    for file_record in File.query.all():
        upsert_file_embedding(file_record)
        count += 1
    db.session.commit()
    return count
