"""Pytest fixtures: in-memory SQLite, swap engine before importing app code."""

import os
import tempfile

import pytest

# Set DATABASE_URL to a tmp sqlite file BEFORE importing anything that touches the engine.
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".sqlite")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path}"


@pytest.fixture(autouse=True)
def _reset_db():
    from devsecops_job_hub.db import engine, init_db
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(engine)
    init_db()
    yield


def _slim_response_body(response: dict) -> dict:
    # Both Lever (mode=json) and Greenhouse (content=true) return full posting
    # descriptions — megabytes per company. Adapter unit tests just verify
    # parsing/schema, so we drop description fields from cassettes. Description-
    # aware classification is exercised in test_classify.py with hand-crafted
    # text, not via cassettes.
    import json

    body = response.get("body", {})
    raw = body.get("string")
    if not raw:
        return response
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return response

    # Description fields are stripped because the adapter unit tests don't
    # exercise classifier behavior — we test classification with hand-crafted
    # strings in test_classify.py. salaryRange is NOT stripped: Slice 3 parses
    # it, and the cassette test verifies the structured field round-trips.
    lever_heavy_keys = {
        "description",
        "descriptionPlain",
        "descriptionBody",
        "descriptionBodyPlain",
        "opening",
        "openingPlain",
        "lists",
        "additional",
        "additionalPlain",
    }
    greenhouse_heavy_keys = {"content"}

    if isinstance(payload, list):
        for posting in payload:
            if isinstance(posting, dict):
                for k in lever_heavy_keys:
                    posting.pop(k, None)
    elif isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        for job in payload["jobs"]:
            if isinstance(job, dict):
                for k in greenhouse_heavy_keys:
                    job.pop(k, None)
    else:
        return response

    body["string"] = json.dumps(payload).encode() if isinstance(raw, bytes) else json.dumps(payload)
    return response


@pytest.fixture(scope="module")
def vcr_config():
    # Public unauthenticated endpoints, but scrub anyway so a future header
    # (auth token, cookie, custom UA leaking machine info) never lands in git.
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("cookie", "REDACTED"),
            ("set-cookie", "REDACTED"),
            ("user-agent", "devsecops-job-hub-test"),
        ],
        "record_mode": "once",
        "before_record_response": _slim_response_body,
    }


def pytest_sessionfinish(session, exitstatus):
    try:
        os.close(_tmp_db_fd)
        os.remove(_tmp_db_path)
    except OSError:
        pass
