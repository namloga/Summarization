import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from src.api.app import app
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "summarization-api"


def test_root(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "endpoints" in body
    assert "POST /summarize" in body["endpoints"]


def test_summarize_empty(client: TestClient):
    r = client.post("/summarize", json={})
    assert r.status_code == 400
    body = r.json()
    assert body.get("success") is False
    assert "error" in body
    assert body["error"].get("code") == "EMPTY_INPUT"


def test_summarize_empty_text(client: TestClient):
    r = client.post("/summarize", json={"text": "   "})
    assert r.status_code == 400


@patch("src.api.routes._get_pipeline")
def test_summarize_single_text(mock_get_pipeline, client: TestClient):
    mock_pipe = mock_get_pipeline.return_value
    mock_pipe.summarize_batch.return_value = ["Короткая сводка."]

    r = client.post("/summarize", json={"text": "Длинный текст, который нужно суммаризовать в одно предложение."})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["count"] == 1
    assert len(data["summaries"]) == 1
    assert data["summaries"][0]["summary"] == "Короткая сводка."


@patch("src.api.routes._get_pipeline")
def test_summarize_texts_list(mock_get_pipeline, client: TestClient):
    mock_pipe = mock_get_pipeline.return_value
    mock_pipe.summarize_batch.return_value = ["S1", "S2"]

    r = client.post(
        "/summarize",
        json={"texts": ["Первый длинный текст.", "Второй длинный текст."]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["count"] == 2
    assert [s["summary"] for s in data["summaries"]] == ["S1", "S2"]


def test_summarize_file_empty(client: TestClient):
    r = client.post(
        "/summarize-file",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400
    body = r.json()
    assert body.get("success") is False
    assert body["error"]["code"] == "EMPTY_FILE"


def test_summarize_file_unsupported_format(client: TestClient):
    r = client.post(
        "/summarize-file",
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "UNSUPPORTED_FORMAT"


@patch("src.api.routes._get_pipeline")
def test_summarize_file_csv_ok(mock_get_pipeline, client: TestClient):
    mock_pipe = mock_get_pipeline.return_value
    mock_pipe.summarize_batch.return_value = ["Сводка 1"]
    mock_pipe.summarize_one.return_value = "Сводка 1"

    csv_content = b"text\nTekst dlya summarizatsii."
    r = client.post(
        "/summarize-file",
        files={"file": ("sample.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["stats"]["extracted_texts"] == 1
    assert data["stats"]["summarized"] == 1
    assert len(data["summaries"]) == 1
    assert data["summaries"][0]["summary"] == "Сводка 1"


@patch("src.api.routes._get_pipeline")
def test_summarize_file_json_ok(mock_get_pipeline, client: TestClient):
    mock_pipe = mock_get_pipeline.return_value
    mock_pipe.summarize_batch.return_value = ["S1", "S2"]

    json_content = b'[{"text": "Pervyy."}, {"content": "Vtoroy."}]'
    r = client.post(
        "/summarize-file?combine=false",
        files={"file": ("data.json", io.BytesIO(json_content), "application/json")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["stats"]["extracted_texts"] == 2
    assert len(data["summaries"]) == 2