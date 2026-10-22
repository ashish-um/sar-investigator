"""Check the investigator surface and evidence lookups without model requests."""

from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_dashboard_and_alerts():
    response = client.get("/")
    assert response.status_code == 200
    assert "AML Investigator" in response.text
    assert "/sar-editor" not in response.text
    assert "/rules-editor" not in response.text
    assert "Proceed to SAR Generation" not in response.text
    alerts = client.get("/api/alerts").json()
    assert alerts["tp"] and alerts["fp"]
    assert client.get("/health").json() == {"status": "ok"}


def test_evidence_lookup():
    response = client.get("/data/customers/CUST-UK-004821")
    assert response.status_code == 200
    assert response.json()["data"]["customer_id"] == "CUST-UK-004821"


def test_editor_and_generation_routes_removed():
    for path in ("/sar-editor", "/rules-editor", "/generate-sar-mock"):
        assert client.get(path).status_code == 404
    assert client.post("/generate-section/section_1", json={}).status_code == 404
    for name in ("aml-rules", "glossary-codes", "legal-snippets"):
        path = f"/api/rules/{name}"
        assert client.get(path).status_code == 404
        assert client.put(path, json={}).status_code == 404
