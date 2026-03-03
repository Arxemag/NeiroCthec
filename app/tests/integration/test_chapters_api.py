from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_process_chapter_not_found():
    """
    Интеграционный тест: запрос обработки главы без подготовленного текста
    должен вернуть 404, как определено в маршруте.
    """
    response = client.post("/api/chapters/999/process")

    assert response.status_code == 404
    assert response.json().get("detail") == "Chapter text not found"

