from fastapi.testclient import TestClient
from main import app
import main

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_delete_inquiry_returns_deleted_status(monkeypatch):
    monkeypatch.setattr(main, "delete_inquiry", lambda inquiry_id: True)

    response = client.delete("/inquiries/inq-123")

    assert response.status_code == 200
    assert response.json() == {"inquiry_id": "inq-123", "status": "deleted"}


def test_delete_inquiry_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(main, "delete_inquiry", lambda inquiry_id: False)

    response = client.delete("/inquiries/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "inquiry not found"}
