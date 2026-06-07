from app.embedding import (
    build_file_embedding_text,
    cosine_similarity,
    deserialize_vector,
    semantic_search,
    serialize_vector,
    upsert_file_embedding,
)
from app.folders import get_root_folder
from app.models import File


def test_vector_serialization_and_deserialization():
    vector = [0.1, 2, -3.5]
    encoded = serialize_vector(vector)
    assert deserialize_vector(encoded) == [0.1, 2.0, -3.5]
    assert deserialize_vector('not-json') == []
    assert deserialize_vector('[1, \"bad\"]') == []


def test_cosine_similarity_boundaries():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([], [1, 0]) == 0.0
    assert cosine_similarity([0, 0], [1, 0]) == 0.0
    assert cosine_similarity([1], [1, 0]) == 0.0


def test_embedding_text_includes_folder_and_tags(app, db_session, root_user):
    with app.app_context():
        root = get_root_folder()
        file_record = File(
            title='数学分析笔记',
            filename_on_disk='analysis.txt',
            original_filename='analysis.txt',
            file_size=1,
            folder_id=root.id,
            search_tags='["微积分", "数学"]',
            display_tags='["期末"]',
            uploader_id=root_user.id,
        )
        db_session.add(file_record)
        db_session.commit()

        text = build_file_embedding_text(file_record)
        assert '数学分析笔记' in text
        assert 'analysis.txt' in text
        assert '/' in text
        assert '微积分' in text
        assert '期末' in text


def test_embedding_disabled_paths_are_safe(app, db_session, root_user):
    with app.app_context():
        app.config['EMBEDDING_ENABLED'] = False
        root = get_root_folder()
        file_record = File(
            title='禁用语义搜索测试',
            filename_on_disk='disabled.txt',
            original_filename='disabled.txt',
            file_size=1,
            folder_id=root.id,
            uploader_id=root_user.id,
        )
        db_session.add(file_record)
        db_session.commit()

        assert upsert_file_embedding(file_record) is None
        assert semantic_search('语义') == []
