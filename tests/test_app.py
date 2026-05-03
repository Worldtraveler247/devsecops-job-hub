from fastapi.testclient import TestClient

from devsecops_job_hub.main import app


def test_healthz():
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_index_renders_with_no_jobs():
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "DevSecOps" in resp.text
    assert "No jobs ingested yet" in resp.text


def test_index_accepts_filters():
    with TestClient(app) as client:
        resp = client.get(
            "/",
            params={"stage": "senior", "clearance": "secret", "remote": "remote"},
        )
    assert resp.status_code == 200
