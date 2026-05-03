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


def test_index_tolerates_empty_form_values():
    # The HTML filter form submits empty strings for "Any" selections, e.g.:
    # `?role=linux_admin&stage=&clearance=&remote=&min_salary=`. Pydantic
    # otherwise 422s on "" → enum/int. Empty values must be coerced to None.
    with TestClient(app) as client:
        resp = client.get(
            "/",
            params=[
                ("role", "linux_admin"),
                ("stage", ""),
                ("clearance", ""),
                ("remote", ""),
                ("location_scope", ""),
                ("min_salary", ""),
            ],
        )
    assert resp.status_code == 200
