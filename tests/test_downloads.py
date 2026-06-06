from app.folders import get_root_folder
from app.models import DownloadLog, File
from conftest import login_as


def test_web_download_missing_physical_file_does_not_log(client, app, db_session, root_user):
    with app.app_context():
        root = get_root_folder()
        file_record = File(
            title='网页登录缺失文件',
            filename_on_disk='missing-web.txt',
            original_filename='missing-web.txt',
            file_size=1,
            folder_id=root.id,
            uploader_id=root_user.id,
        )
        db_session.add(file_record)
        db_session.commit()
        file_id = file_record.id

    login_as(client, root_user)
    response = client.get(f'/download/{file_id}')
    assert response.status_code == 404

    with app.app_context():
        file_record = File.query.get(file_id)
        assert file_record.download_count == 0
        assert DownloadLog.query.filter_by(file_id=file_id).count() == 0
